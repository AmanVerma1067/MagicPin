from datetime import datetime, timezone
from app.signals import (
    TYPE_WEIGHTS,
    compute_trigger_score,
    select_top_candidates,
)
from app.suppression import generate_suppression_key


def test_type_weights_order():
    assert TYPE_WEIGHTS["regulation_change"] > TYPE_WEIGHTS["perf_dip"]
    assert TYPE_WEIGHTS["perf_dip"] > TYPE_WEIGHTS["category_seasonal"]
    assert TYPE_WEIGHTS["category_seasonal"] > TYPE_WEIGHTS["competitor_opened"]
    assert TYPE_WEIGHTS["competitor_opened"] > TYPE_WEIGHTS["customer_lapsed_soft"]
    assert TYPE_WEIGHTS["customer_lapsed_soft"] > TYPE_WEIGHTS["perf_spike"]
    assert TYPE_WEIGHTS["perf_spike"] > TYPE_WEIGHTS["research_digest"]


def test_compute_trigger_score():
    now = datetime(2026, 4, 26, 10, 0, 0, tzinfo=timezone.utc)
    trigger = {"kind": "regulation_change", "urgency": 4, "payload": {"drop_pct": 0.25}}
    merchant = {
        "merchant_id": "m_1",
        "category_slug": "dentists",
        "signals": ["engaged_in_last_48h"],
    }
    category = {"slug": "dentists"}

    score = compute_trigger_score(now, trigger, merchant, category)
    assert score > 1.5


def test_select_top_candidates_max_and_per_merchant():
    now = datetime(2026, 4, 26, 10, 0, 0, tzinfo=timezone.utc)
    mock_db = {
        "category": {"dentists": {"slug": "dentists"}},
        "merchant": {},
        "trigger": {},
    }

    trigger_ids = []
    # Create 30 triggers across 25 merchants (some merchants have multiple triggers)
    for i in range(30):
        mid = f"m_{i % 25}"
        tid = f"trg_{i}"
        mock_db["merchant"][mid] = {
            "merchant_id": mid,
            "category_slug": "dentists",
            "signals": [],
        }
        mock_db["trigger"][tid] = {
            "id": tid,
            "kind": "perf_dip" if i % 2 == 0 else "research_digest",
            "merchant_id": mid,
            "urgency": (i % 4) + 1,
            "detected_at": f"2026-04-26T10:{i:02d}:00Z",
            "payload": {},
        }
        trigger_ids.append(tid)

    suppressed_keys = set()

    def store_getter(scope, cid):
        return mock_db.get(scope, {}).get(cid)

    selected = select_top_candidates(
        now=now,
        trigger_ids=trigger_ids,
        store_getter=store_getter,
        is_suppressed_fn=lambda k: k in suppressed_keys,
        suppression_key_fn=generate_suppression_key,
        max_actions=20,
    )

    # 1. Strictly capped at <= 20
    assert len(selected) <= 20
    assert len(selected) == 20

    # 2. At most 1 action per merchant
    mids = [c.merchant_id for c in selected]
    assert len(mids) == len(set(mids))

    # 3. Deterministic order: descending by score
    scores = [c.score for c in selected]
    assert scores == sorted(scores, reverse=True)
