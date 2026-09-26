import json
from pathlib import Path
import pytest

from app.composer import compose
from app.facts import extract_facts
from app.templates import render_fallback_template
from app.validator import validate_grounding_and_format

EXPANDED_DIR = Path("expanded")


@pytest.mark.asyncio
async def test_composer_all_five_verticals():
    verticals = ["dentists", "salons", "restaurants", "gyms", "pharmacies"]

    for slug in verticals:
        cat_file = EXPANDED_DIR / "categories" / f"{slug}.json"
        assert cat_file.exists(), f"Missing category file: {cat_file}"
        category = json.load(open(cat_file))

        # Find a merchant in this vertical
        merchant = None
        for mf in (EXPANDED_DIR / "merchants").glob("*.json"):
            data = json.load(open(mf))
            if data.get("category_slug") == slug:
                merchant = data
                break
        assert merchant is not None, f"No merchant found for {slug}"

        # Find a trigger for this merchant or general trigger
        trigger = None
        for tf in (EXPANDED_DIR / "triggers").glob("*.json"):
            data = json.load(open(tf))
            if data.get("merchant_id") == merchant["merchant_id"]:
                trigger = data
                break
        if not trigger:
            trigger = {
                "id": f"trg_mock_{slug}",
                "kind": "perf_dip",
                "merchant_id": merchant["merchant_id"],
                "urgency": 2,
                "payload": {"drop_pct": 0.15},
            }

        # Compose message (with fallback since LLM key is empty in test)
        action = await compose(category=category, merchant=merchant, trigger=trigger)

        assert action["merchant_id"] == merchant["merchant_id"]
        assert action["category"] == slug
        assert len(action["body"]) >= 80
        assert len(action["body"]) <= 280
        assert action["cta"] is not None
        assert action["rationale"] is not None
        assert action["suppression_key"] is not None

        # Verify the message passes the hard validation gate
        facts = extract_facts(category, merchant, trigger)
        v_res = validate_grounding_and_format(action["body"], action["cta"], facts)
        assert v_res.is_valid is True, f"Vertical {slug} failed validation: {v_res.reasons}"


def test_fallback_templates_validity():
    category = {
        "slug": "restaurants",
        "peer_stats": {"avg_rating": 4.2, "avg_review_count": 88, "avg_views_30d": 3200},
        "voice": {"tone": "operator", "vocab_taboo": ["best food in world"]},
    }
    merchant = {
        "merchant_id": "m_rest_1",
        "category_slug": "restaurants",
        "identity": {"name": "Madras Express", "locality": "Indiranagar", "city": "Bangalore", "owner_first_name": "Suresh"},
        "performance": {"views": 4120, "calls": 35},
        "offers": [{"id": "o_1", "title": "Corporate Thali @ ₹199", "status": "active"}],
    }
    trigger = {"id": "t_1", "kind": "perf_dip", "urgency": 3, "payload": {"drop_pct": 0.20}}

    facts = extract_facts(category, merchant, trigger)
    body, cta, rationale = render_fallback_template(facts)

    v_res = validate_grounding_and_format(body, cta, facts)
    assert v_res.is_valid is True, f"Fallback failed validation: {v_res.reasons}"
