from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


TYPE_WEIGHTS: Dict[str, float] = {
    # Compliance / Regulatory
    "regulation_change": 1.10,
    "gbp_unverified": 1.10,
    "renewal_due": 1.10,
    # Performance Dip
    "perf_dip": 1.00,
    "seasonal_perf_dip": 1.00,
    # Seasonal Event
    "category_seasonal": 0.95,
    "festival_upcoming": 0.95,
    "ipl_match_today": 0.95,
    # Peer Gap / Market Changes
    "competitor_opened": 0.90,
    "review_theme_emerged": 0.90,
    # Customer Lapse
    "customer_lapsed_hard": 0.85,
    "customer_lapsed_soft": 0.85,
    "recall_due": 0.85,
    "chronic_refill_due": 0.85,
    "winback_eligible": 0.85,
    # Performance Spike
    "perf_spike": 0.80,
    "milestone_reached": 0.80,
    # Research Digest / Educational / Inquiries
    "research_digest": 0.60,
    "cde_opportunity": 0.60,
    "supply_alert": 0.65,
    "curious_ask_due": 0.70,
    "active_planning_intent": 0.75,
    "trial_followup": 0.70,
    "wedding_package_followup": 0.75,
    "dormant_with_vera": 0.65,
    "appointment_tomorrow": 0.85,
}

DEFAULT_WEIGHT = 0.70


@dataclass
class CandidateAction:
    trigger_id: str
    merchant_id: str
    customer_id: Optional[str]
    category_slug: str
    score: float
    trigger: Dict[str, Any]
    merchant: Dict[str, Any]
    category: Dict[str, Any]
    customer: Optional[Dict[str, Any]]
    detected_at: str


def compute_trigger_score(
    now: datetime,
    trigger: Dict[str, Any],
    merchant: Dict[str, Any],
    category: Dict[str, Any],
) -> float:
    """Compute score = W_type * Urgency * Magnitude * Novelty * CategoryFit."""
    kind = trigger.get("kind", "")
    w_type = TYPE_WEIGHTS.get(kind, DEFAULT_WEIGHT)

    # 1. Urgency: from trigger.urgency (1-5) and expiration
    base_urgency = float(trigger.get("urgency", 2))
    urgency_factor = 0.8 + (base_urgency * 0.15)  # e.g., urgency 2 -> 1.1, urgency 4 -> 1.4

    # 2. Magnitude: payload signals (e.g. lapse count, delta, drop %)
    payload = trigger.get("payload", {})
    mag_val = 1.0
    if "delta_pct" in payload:
        mag_val = 1.0 + min(0.5, abs(float(payload["delta_pct"])))
    elif "drop_pct" in payload:
        mag_val = 1.0 + min(0.5, abs(float(payload["drop_pct"])))
    elif "lapsed_count" in payload:
        mag_val = 1.0 + min(0.4, float(payload["lapsed_count"]) / 50.0)
    elif "query_growth_pct" in payload:
        mag_val = 1.0 + min(0.4, float(payload["query_growth_pct"]) / 100.0)

    # 3. Novelty: based on merchant signals & conversation recency
    signals = merchant.get("signals", [])
    novelty = 1.0
    if "engaged_in_last_48h" in signals:
        novelty = 1.15
    elif "stale_posts:22d" in signals:
        novelty = 1.10

    # 4. CategoryFit
    cat_slug = merchant.get("category_slug", "")
    trg_cat = payload.get("category")
    cat_fit = 1.0
    if trg_cat and trg_cat == cat_slug:
        cat_fit = 1.1
    elif not trg_cat:
        cat_fit = 1.0

    return round(w_type * urgency_factor * mag_val * novelty * cat_fit, 4)


def select_top_candidates(
    now: datetime,
    trigger_ids: List[str],
    store_getter: Callable[[str, str], Optional[Dict[str, Any]]],
    is_suppressed_fn: Callable[[str], bool],
    suppression_key_fn: Callable[[str, str, str, datetime], str],
    max_actions: int = 20,
) -> List[CandidateAction]:
    """
    Score triggers, enforce suppression, limit to 1 action per merchant,
    tie-break deterministically, and select top max_actions (<= 20).
    """
    scored_candidates: List[CandidateAction] = []

    for tid in trigger_ids:
        trg = store_getter("trigger", tid)
        if not trg:
            continue

        mid = trg.get("merchant_id")
        if not mid:
            continue

        merch = store_getter("merchant", mid)
        if not merch:
            continue

        cat_slug = merch.get("category_slug", "")
        cat = store_getter("category", cat_slug) or {}

        cid = trg.get("customer_id")
        cust = store_getter("customer", cid) if cid else None

        # Check suppression key
        sup_key = suppression_key_fn(trg.get("kind", "trigger"), cat_slug, mid, now)
        if is_suppressed_fn(sup_key):
            continue

        score = compute_trigger_score(now, trg, merch, cat)
        det_at = trg.get("detected_at", "") or trg.get("created_at", "") or ""

        scored_candidates.append(
            CandidateAction(
                trigger_id=tid,
                merchant_id=mid,
                customer_id=cid,
                category_slug=cat_slug,
                score=score,
                trigger=trg,
                merchant=merch,
                category=cat,
                customer=cust,
                detected_at=det_at,
            )
        )

    # Sort deterministically: (-score, detected_at descending, trigger_id)
    scored_candidates.sort(key=lambda c: (-c.score, c.detected_at, c.trigger_id))

    # Constraint: Limit to at most 1 action per merchant per tick
    selected: List[CandidateAction] = []
    seen_merchants: Set[str] = set()

    for cand in scored_candidates:
        if cand.merchant_id in seen_merchants:
            continue
        seen_merchants.add(cand.merchant_id)
        selected.append(cand)
        if len(selected) >= max_actions:
            break

    return selected
