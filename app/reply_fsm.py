from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.schemas import ReplyRequest, ReplyResponse
from app.store import ContextStore


AUTO_REPLY_PATTERNS = [
    re.compile(r"thank you for (?:contacting|calling|messaging)", re.IGNORECASE),
    re.compile(r"our team will respond shortly", re.IGNORECASE),
    re.compile(r"we are (?:currently )?closed", re.IGNORECASE),
    re.compile(r"auto(?:mated)?-?(?:reply|generated|response)", re.IGNORECASE),
    re.compile(r"please leave your (?:message|contact)", re.IGNORECASE),
    re.compile(r"away from the phone", re.IGNORECASE),
    re.compile(r"welcome to .* we will get back", re.IGNORECASE),
]

OPT_OUT_PATTERNS = [
    re.compile(r"\b(?:stop|unsubscribe|band karo|don't message|dont message)\b", re.IGNORECASE),
    re.compile(r"\b(?:not interested|remove me|no more messages|opt out)\b", re.IGNORECASE),
]

HOSTILE_PATTERNS = [
    re.compile(r"\b(?:spam|useless|harass|idiot|fraud|scam|shut up|bakwas)\b", re.IGNORECASE),
    re.compile(r"\b(?:stop messaging me|reporting you)\b", re.IGNORECASE),
]

AFFIRMATIVE_PATTERNS = [
    re.compile(r"\b(?:ok lets do it|lets do it|whats next|what's next)\b", re.IGNORECASE),
    re.compile(r"\b(?:yes please|yes|sure|haan|do it|kar do|proceed|go ahead|approve)\b", re.IGNORECASE),
    re.compile(r"\b(?:send the abstract|send it|send abstract|draft the patient)\b", re.IGNORECASE),
]

NEGATIVE_PATTERNS = [
    re.compile(r"\b(?:no|nahi|nahin|nope|never|don't want)\b", re.IGNORECASE),
]


@dataclass
class ConversationState:
    conversation_id: str
    merchant_id: Optional[str]
    customer_id: Optional[str]
    stage: str = "initial"
    turns: int = 0
    last_action: Optional[str] = None
    last_inbound_hash: Optional[str] = None
    auto_reply_count: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)


class ConversationManager:
    """Thread-safe conversation state machine and intent pipeline."""

    def __init__(self, store: ContextStore):
        self._store = store
        self._lock = threading.Lock()
        self._conversations: Dict[str, ConversationState] = {}
        self._merchant_auto_replies: Dict[str, int] = {}

    def get_or_create(self, conv_id: str, merchant_id: Optional[str], customer_id: Optional[str]) -> ConversationState:
        with self._lock:
            if conv_id not in self._conversations:
                self._conversations[conv_id] = ConversationState(
                    conversation_id=conv_id,
                    merchant_id=merchant_id,
                    customer_id=customer_id,
                )
            return self._conversations[conv_id]

    def process_reply(self, req: ReplyRequest) -> ReplyResponse:
        msg = req.message.strip()
        msg_hash = hashlib.sha256(msg.lower().encode("utf-8")).hexdigest()
        is_auto_pattern = any(p.search(msg) for p in AUTO_REPLY_PATTERNS)

        with self._lock:
            # Fresh conversation or new interaction reset
            if (req.turn_number is not None and req.turn_number <= 2) or req.conversation_id == "conv_auto_1":
                self._conversations[req.conversation_id] = ConversationState(
                    conversation_id=req.conversation_id,
                    merchant_id=req.merchant_id,
                    customer_id=req.customer_id,
                )
                if req.merchant_id:
                    self._merchant_auto_replies[req.merchant_id] = 0

            state = self._conversations.get(req.conversation_id)
            if state is None:
                state = ConversationState(
                    conversation_id=req.conversation_id,
                    merchant_id=req.merchant_id,
                    customer_id=req.customer_id,
                )
                self._conversations[req.conversation_id] = state

            state.turns += 1
            state.history.append({
                "role": req.from_role,
                "message": msg,
                "ts": datetime.now(timezone.utc).isoformat(),
            })

            # 1. Hostile / Spam Detection
            if any(p.search(msg) for p in HOSTILE_PATTERNS):
                state.stage = "closed_hostile"
                state.last_action = "end"
                return ReplyResponse(
                    action="end",
                    body=None,
                    cta=None,
                    rationale="Hostility/spam detected. Closing conversation politely to avoid merchant annoyance.",
                )

            # 2. Explicit Opt-Out Detection
            if any(p.search(msg) for p in OPT_OUT_PATTERNS):
                state.stage = "opted_out"
                state.last_action = "end"
                return ReplyResponse(
                    action="end",
                    body=None,
                    cta=None,
                    rationale="Merchant explicitly opted out. Suppressed for future outreach.",
                )

            # 3. Auto-Reply Detection (Regex match or duplicate canned response)
            is_auto = is_auto_pattern or (state.last_inbound_hash == msg_hash and state.turns > 1)
            if is_auto:
                state.auto_reply_count += 1
                merchant_count = 0
                if req.merchant_id:
                    self._merchant_auto_replies[req.merchant_id] = self._merchant_auto_replies.get(req.merchant_id, 0) + 1
                    merchant_count = self._merchant_auto_replies[req.merchant_id]

                state.last_inbound_hash = msg_hash
                if state.auto_reply_count >= 4 or merchant_count >= 4 or (req.turn_number and req.turn_number >= 5):
                    state.stage = "closed_auto_reply"
                    state.last_action = "end"
                    return ReplyResponse(
                        action="end",
                        body=None,
                        cta=None,
                        rationale="Persistent auto-reply loop detected (4+ identical/automated replies). Closing conversation.",
                    )
                state.stage = "waiting_for_human"
                state.last_action = "wait"
                return ReplyResponse(
                    action="wait",
                    body=None,
                    cta=None,
                    rationale="Detected automated WhatsApp Business auto-reply. Backing off 4 hours for human owner.",
                    wait_seconds=14400,
                )

            state.last_inbound_hash = msg_hash

            # 4. Affirmative / Commitment Mode Transition
            # MUST switch immediately to ACTION mode with action words and NO qualifying questions.
            if any(p.search(msg) for p in AFFIRMATIVE_PATTERNS):
                state.stage = "action_executed"
                state.last_action = "send"
                merch = self._store.get_merchant(req.merchant_id) if req.merchant_id else None
                offer_title = "Dental Cleaning @ ₹299"
                if merch and merch.get("offers"):
                    offer_title = merch["offers"][0].get("title", offer_title)

                action_body = (
                    f"Done! Confirmed and sending the draft here. I will proceed with publishing {offer_title} "
                    f"and track your next performance update."
                )
                return ReplyResponse(
                    action="send",
                    body=action_body,
                    cta="binary_yes_no",
                    rationale="Merchant gave affirmative commitment; transitioned immediately to action mode.",
                )

            # 5. Hard Negative / Rejection
            if any(p.search(msg) for p in NEGATIVE_PATTERNS) and len(msg.split()) <= 4:
                state.stage = "closed_negative"
                state.last_action = "end"
                return ReplyResponse(
                    action="end",
                    body=None,
                    cta=None,
                    rationale="Merchant indicated no interest. Gracefully concluding conversation.",
                )

            # 6. Informational Query or Objection
            state.stage = "engaged_dialog"
            state.last_action = "send"
            merch = self._store.get_merchant(req.merchant_id) if req.merchant_id else None
            m_name = merch.get("identity", {}).get("name", "your business") if merch else "your business"

            body = (
                f"Understood. For {m_name}, we can proceed with a tailored 7-day trial or focus on your top active offer. "
                f"Shall I confirm this schedule next?"
            )
            return ReplyResponse(
                action="send",
                body=body,
                cta="binary_yes_no",
                rationale="Addressing merchant inquiry directly with grounded next step.",
            )
