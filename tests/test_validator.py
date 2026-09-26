from app.facts import extract_facts
from app.validator import validate_grounding_and_format


def _sample_context():
    category = {
        "slug": "dentists",
        "voice": {
            "tone": "peer_clinical",
            "vocab_taboo": ["guaranteed", "100% safe", "miracle"],
        },
        "offer_catalog": [
            {"id": "den_001", "title": "Dental Cleaning @ ₹299", "value": "299"}
        ],
        "peer_stats": {"avg_rating": 4.4, "avg_views_30d": 1820},
    }
    merchant = {
        "merchant_id": "m_001_drmeera",
        "category_slug": "dentists",
        "identity": {
            "name": "Dr. Meera's Dental Clinic",
            "locality": "Lajpat Nagar",
            "city": "Delhi",
            "owner_first_name": "Meera",
        },
        "performance": {"views": 2410, "calls": 18, "ctr": 0.021},
        "offers": [
            {"id": "o_1", "title": "Dental Cleaning @ ₹299", "status": "active"}
        ],
    }
    trigger = {
        "id": "trg_01",
        "kind": "perf_dip",
        "urgency": 3,
        "payload": {"drop_pct": 0.18},
    }
    return category, merchant, trigger


def test_validator_valid_message():
    category, merchant, trigger = _sample_context()
    facts = extract_facts(category, merchant, trigger)

    body = (
        "Dr. Meera, your listing reached 2,410 views in Lajpat Nagar with calls at 18. "
        "Shall we spotlight your Dental Cleaning @ ₹299 to maintain positive patient momentum?"
    )
    cta = "binary_yes_no"

    res = validate_grounding_and_format(body, cta, facts)
    assert res.is_valid is True
    assert len(res.reasons) == 0


def test_validator_unverified_number_rejected():
    category, merchant, trigger = _sample_context()
    facts = extract_facts(category, merchant, trigger)

    # 99999 is NOT in context facts!
    body = (
        "Dr. Meera, your listing reached 99999 views in Lajpat Nagar. "
        "Shall we spotlight your Dental Cleaning @ ₹299 to maintain patient momentum?"
    )
    cta = "binary_yes_no"

    res = validate_grounding_and_format(body, cta, facts)
    assert res.is_valid is False
    assert any("Unverified number" in r for r in res.reasons)


def test_validator_missing_anchor_number():
    category, merchant, trigger = _sample_context()
    facts = extract_facts(category, merchant, trigger)

    body = (
        "Dr. Meera, your clinic had great performance in Lajpat Nagar recently. "
        "Shall we spotlight your dental cleaning offer to maintain positive patient momentum?"
    )
    cta = "binary_yes_no"

    res = validate_grounding_and_format(body, cta, facts)
    assert res.is_valid is False
    assert any("Missing anchor number" in r for r in res.reasons)


def test_validator_missing_merchant_name():
    category, merchant, trigger = _sample_context()
    facts = extract_facts(category, merchant, trigger)

    body = (
        "Hello there, your listing reached 2,410 views in Lajpat Nagar with calls at 18. "
        "Shall we spotlight your Dental Cleaning @ ₹299 to maintain positive patient momentum?"
    )
    cta = "binary_yes_no"

    res = validate_grounding_and_format(body, cta, facts)
    assert res.is_valid is False
    assert any("Personalization missing" in r for r in res.reasons)


def test_validator_length_constraints():
    category, merchant, trigger = _sample_context()
    facts = extract_facts(category, merchant, trigger)

    # Too short (< 80 chars)
    short_body = "Dr. Meera, ₹299 cleaning active. Shall we launch?"
    res_short = validate_grounding_and_format(short_body, "binary", facts)
    assert res_short.is_valid is False
    assert any("under minimum 80 characters" in r for r in res_short.reasons)

    # Too long (> 280 chars)
    long_body = "Dr. Meera, " + ("views 2,410 in Lajpat Nagar with calls at 18. " * 8) + "Shall we launch?"
    res_long = validate_grounding_and_format(long_body, "binary", facts)
    assert res_long.is_valid is False
    assert any("exceeds maximum 280 characters" in r for r in res_long.reasons)


def test_validator_taboo_violation():
    category, merchant, trigger = _sample_context()
    facts = extract_facts(category, merchant, trigger)

    body = (
        "Dr. Meera, your listing reached 2,410 views in Lajpat Nagar with 100% safe guaranteed results. "
        "Shall we spotlight your Dental Cleaning @ ₹299 to maintain positive patient momentum?"
    )
    cta = "binary_yes_no"

    res = validate_grounding_and_format(body, cta, facts)
    assert res.is_valid is False
    assert any("Taboo violation" in r for r in res.reasons)
