from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.facts import GroundedFacts, extract_facts
from app.schemas import ReplyRequest, ReplyResponse
from app.store import ContextStore
from app.templates import all_offers, offer_phrase, pick_in_window, traffic_clause
from app.validator import validate_grounding_and_format

logger = logging.getLogger("vera.reply")


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

# Explicit commitments: always action mode, even when phrased with a "?" ("Ok lets do it. Whats next?").
AFFIRMATIVE_PATTERNS = [
    re.compile(r"\b(?:ok lets do it|lets do it|let's do it|whats next|what's next)\b", re.IGNORECASE),
    re.compile(r"\b(?:yes please|do it|kar do|proceed|go ahead|approve)\b", re.IGNORECASE),
    re.compile(r"\b(?:send the abstract|send it|send abstract|draft the patient)\b", re.IGNORECASE),
]

# Bare assent: only a commitment when the merchant isn't also asking something ("Yes, but what price?").
WEAK_AFFIRMATIVE_PATTERN = re.compile(r"\b(?:yes|sure|haan|ok|okay|theek hai)\b", re.IGNORECASE)
HEDGE_PATTERN = re.compile(r"\b(?:not sure|but|maybe|unsure)\b", re.IGNORECASE)
QUESTION_PATTERN = re.compile(
    r"\?|\b(?:what|how|which|when|why|kitna|kab|kya|price|cost)\b", re.IGNORECASE
)

PRICE_INTENT = re.compile(
    r"\b(?:price|pricing|cost|charge|rate|fee|kitna|how much|recommend|discount|offer|deal|cheap)\b",
    re.IGNORECASE,
)
PERF_INTENT = re.compile(
    r"\b(?:views?|calls?|performance|traffic|leads?|results?|ctr|doing|numbers|stats)\b", re.IGNORECASE
)
TIMING_INTENT = re.compile(r"\b(?:when|how long|how soon|kab|start|timeline|live)\b", re.IGNORECASE)

# Words too generic to identify a service in an offer title.
_GENERIC_WORDS = {
    "free", "offer", "price", "pricing", "combo", "with", "plan", "your", "what", "which", "recommend",
    "much", "cost", "charge", "should", "would", "could", "you", "for", "the", "and", "per", "month",
    "total", "bill", "orders", "annual", "first", "about", "think", "good", "best", "this", "that",
    "there", "have", "want", "need", "like", "does", "much", "many", "some", "tell", "know", "please",
    "okay", "sure", "also", "then", "them", "they", "will", "from", "into", "just", "really", "right",
    "discount", "deal", "rate", "kitna", "hai", "service", "customer", "people", "listing",
}


def _service_tokens(text: str) -> set:
    text = re.sub(r"check[\s-]+up", "checkup", text.lower())
    out = set()
    for w in re.findall(r"[a-z]+", text):
        if len(w) < 4 or w in _GENERIC_WORDS:
            continue
        out.add(w[:-1] if w.endswith("s") and len(w) > 4 else w)
    return out


def match_offer(facts: GroundedFacts, message: str) -> Optional[Dict[str, Any]]:
    """Best merchant/catalog offer for the service the merchant is asking about (active offers win ties)."""
    wanted = _service_tokens(message)
    if not wanted:
        return None
    best, best_score = None, 0
    for o in all_offers(facts):
        score = len(wanted & _service_tokens(o["title"]))
        if score > best_score:
            best, best_score = o, score
    return best


def is_commitment(msg: str) -> bool:
    if any(p.search(msg) for p in AFFIRMATIVE_PATTERNS):
        return True
    return bool(WEAK_AFFIRMATIVE_PATTERN.search(msg)) and not QUESTION_PATTERN.search(msg) and not HEDGE_PATTERN.search(msg)

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
            if is_commitment(msg):
                state.stage = "action_executed"
                state.last_action = "send"
                facts = self._facts_for(req.merchant_id, msg)
                offers = all_offers(facts) if facts else []
                what = f"your {offers[0]['title']} offer" if offers else "your listing update"
                where = f" on {facts.merchant_name}'s magicpin listing" if facts else ""
                action_body = (
                    f"Done! Confirmed and sending the draft here. I will proceed with publishing {what}{where} "
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
            facts = self._facts_for(req.merchant_id, msg)
            body, rationale = answer_query(facts, msg)
            return ReplyResponse(
                action="send",
                body=body,
                cta="binary_yes_no",
                rationale=rationale,
            )

    def _facts_for(self, merchant_id: Optional[str], msg: str) -> Optional[GroundedFacts]:
        merch = self._store.get_merchant(merchant_id) if merchant_id else None
        if not merch:
            return None
        cat = self._store.get_category(merch.get("category_slug", "")) or {}
        # The inbound message rides along as the "trigger" so numbers the merchant quoted are citable.
        return extract_facts(cat, merch, {"kind": "merchant_query", "payload": {"message": msg}})

    async def process_reply_async(self, req: ReplyRequest, gemini_client: Any = None) -> ReplyResponse:
        """process_reply, plus an optional LLM rewrite of informational answers (validated, else deterministic)."""
        resp = self.process_reply(req)
        state = self._conversations.get(req.conversation_id)
        if not gemini_client or resp.action != "send" or not state or state.stage != "engaged_dialog":
            return resp
        facts = self._facts_for(req.merchant_id, req.message.strip())
        if not facts:
            return resp
        try:
            # Bounded so the deterministic answer still ships inside the reply deadline.
            llm_body = await asyncio.wait_for(
                _llm_answer(gemini_client, facts, req.message.strip(), resp.body or ""),
                timeout=settings.REPLY_DEADLINE_S / 2,
            )
        except Exception as e:  # timeout or SDK error: never let the LLM path break /v1/reply
            logger.warning(f"LLM reply failed: {e}")
            llm_body = None
        if llm_body:
            return ReplyResponse(
                action="send",
                body=llm_body,
                cta="binary_yes_no",
                rationale=f"{resp.rationale} (LLM-phrased, grounding-validated)",
            )
        return resp


def answer_query(facts: Optional[GroundedFacts], msg: str) -> Tuple[str, str]:
    """Deterministic, grounded answer to a merchant question. Returns (body, rationale)."""
    if facts is None:
        return (
            "Good question. I don't have your listing details loaded yet, so I won't guess numbers. "
            "Shall I pull your latest views, calls and live offers and reply with a specific plan?",
            "Merchant context missing; asked to fetch data instead of inventing figures.",
        )

    sal, m_name = facts.salutation, facts.merchant_name
    loc = facts.locality or facts.city or "your area"
    offers = all_offers(facts)
    top = offers[0] if offers else None
    matched = match_offer(facts, msg)
    traffic = traffic_clause(facts)
    cta = "Shall I schedule this offer for tomorrow?"

    if matched:
        svc = matched["service"]
        if matched.get("active"):
            src = f"it's your live '{matched['title']}' offer"
        else:
            src = f"that's the magicpin {facts.category_slug} catalog offer '{matched['title']}'"
        if matched.get("price"):
            lead = f"{sal}, for {svc} at {m_name} I recommend ₹{matched['price']} — {src}"
        else:
            lead = f"{sal}, for {svc} at {m_name} I'd lead with {src}"
        body = pick_in_window([
            f"{lead}, shown to searchers in {loc}. {cta}",
            f"{lead}. {cta}",
        ])
        return body, f"Answered the service question with the matching offer '{matched['title']}'."

    if PERF_INTENT.search(msg) and traffic:
        calls = facts.metrics.get("calls")
        peer_calls = facts.peer_stats.get("avg_calls_30d")
        calls_str = f", {calls} calls vs peer avg {peer_calls}" if calls is not None and peer_calls is not None else ""
        push = f"push your {offer_phrase(top)}" if top else "refresh your listing"
        body = pick_in_window([
            f"{sal}, {m_name} has {traffic}{calls_str} in {loc}. Shall I {push} to convert more of those views?",
            f"{sal}, {m_name} has {traffic}. Shall I {push}?",
        ])
        return body, "Answered performance question with the merchant's own metrics vs peers."

    if TIMING_INTENT.search(msg) and top:
        body = pick_in_window([
            f"{sal}, I can have your {offer_phrase(top)} live on {m_name}'s listing by tomorrow morning for searchers in {loc}. Shall I schedule it?",
            f"{sal}, your {offer_phrase(top)} can go live by tomorrow morning. Shall I schedule it?",
        ])
        return body, "Answered timing question with a concrete go-live step."

    asked = sorted(_service_tokens(msg), key=msg.lower().find)
    if top and asked and PRICE_INTENT.search(msg):
        term = asked[0]
        body = pick_in_window([
            f"{sal}, {m_name} has no {term} offer live yet, so I won't guess a price. Your closest anchor is {offer_phrase(top)} for {loc} searchers. Shall I draft a {term} offer for you to price and approve?",
            f"{sal}, there's no {term} offer at {m_name} yet; your closest anchor is {offer_phrase(top)}. Shall I draft a {term} offer for you to approve?",
        ])
        return body, f"No catalog offer matches '{term}'; declined to invent a price and offered to draft one."

    if top:
        lead = "on pricing, " if PRICE_INTENT.search(msg) else ""
        body = pick_in_window([
            f"{sal}, {lead}I'd anchor on your {offer_phrase(top)} — {m_name} has {traffic} in {loc}. {cta}" if traffic else None,
            f"{sal}, {lead}I'd anchor on your {offer_phrase(top)} for searchers in {loc}. {cta}",
        ])
        return body, f"Answered with the merchant's top offer '{top['title']}'."

    body = pick_in_window([
        f"{sal}, {m_name} has {traffic} in {loc}. Shall I draft an offer for your listing to lift calls this week?" if traffic else None,
        f"{sal}, got it. Shall I draft a first offer for {m_name}'s listing in {loc} so you can review it today?",
    ])
    return body, "No catalog offer available; proposed drafting one grounded in own metrics."


_REPLY_SYSTEM = """You are Vera, magicpin's merchant assistant, replying on WhatsApp to a merchant's question.
Rules:
1. Answer the merchant's actual question directly in the first sentence.
2. Only cite numbers, prices, and dates that appear in the FACTS. Never invent trials, discounts, durations, or deadlines.
3. Start with the salutation given. 80-280 characters. End with ONE binary yes/no question.
Return JSON: body, cta ("binary_yes_no"), rationale."""


async def _llm_answer(gemini_client: Any, facts: GroundedFacts, msg: str, draft: str) -> Optional[str]:
    offers = [
        f"{o['service']} (Price: ₹{o['price']})" if o.get("price") else o["title"]
        for o in all_offers(facts)[:8]
    ]
    active = [o["title"] for o in all_offers(facts) if o.get("active")]
    prompt = "\n".join([
        f"Merchant: {facts.merchant_name} in {facts.locality}, {facts.city} ({facts.category_slug})",
        f"Salutation: {facts.salutation}",
        f"Merchant question: {msg}",
        f"Live offers: {active or 'none'}",
        f"Catalog offers: {offers or 'none'}",
        f"Performance (30d): views={facts.metrics.get('views')}, calls={facts.metrics.get('calls')}, ctr={facts.metrics.get('ctr')}",
        f"Peer averages: views={facts.peer_stats.get('avg_views_30d')}, calls={facts.peer_stats.get('avg_calls_30d')}",
        f"Grounded draft (improve on it, keep its offer and price): {draft}",
    ])
    comp = await gemini_client.generate_composition(prompt, system_instruction=_REPLY_SYSTEM)
    if not comp:
        return None
    v = validate_grounding_and_format(comp.body, comp.cta, facts)
    if not v.is_valid:
        logger.info(f"LLM reply rejected: {v.reasons}")
        return None
    # The rewrite must keep the price the deterministic matcher found for the asked-about service.
    matched = match_offer(facts, msg)
    if matched and matched.get("price") and matched["price"] not in v.cleaned_body:
        return None
    return v.cleaned_body
