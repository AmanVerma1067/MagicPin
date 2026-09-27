import json
from pathlib import Path

import pytest

from app.facts import extract_facts
from app.reply_fsm import ConversationManager
from app.schemas import ContextPush, ReplyRequest
from app.store import ContextStore
from app.templates import render_fallback_template
from app.validator import validate_grounding_and_format

DATASET = Path(__file__).resolve().parent.parent / "dataset"


def _load():
    cats = {}
    for f in (DATASET / "categories").glob("*.json"):
        d = json.loads(f.read_text())
        cats[d["slug"]] = d
    merchants = {m["merchant_id"]: m for m in json.loads((DATASET / "merchants_seed.json").read_text())["merchants"]}
    customers = {c["customer_id"]: c for c in json.loads((DATASET / "customers_seed.json").read_text())["customers"]}
    triggers = json.loads((DATASET / "triggers_seed.json").read_text())["triggers"]
    return cats, merchants, customers, triggers


CATS, MERCHANTS, CUSTOMERS, TRIGGERS = _load()


@pytest.fixture
def fsm():
    store = ContextStore()
    for slug, c in CATS.items():
        store.upsert(ContextPush(scope="category", context_id=slug, version=1, payload=c))
    for mid, m in MERCHANTS.items():
        store.upsert(ContextPush(scope="merchant", context_id=mid, version=1, payload=m))
    return ConversationManager(store)


@pytest.mark.parametrize("trigger", TRIGGERS, ids=[t["id"] for t in TRIGGERS])
def test_fallback_grounded_for_every_seed_trigger(trigger):
    merchant = MERCHANTS[trigger["merchant_id"]]
    customer = CUSTOMERS.get(trigger.get("customer_id") or "")
    facts = extract_facts(CATS[merchant["category_slug"]], merchant, trigger, customer)
    body, cta, _ = render_fallback_template(facts)
    v = validate_grounding_and_format(body, cta, facts)
    assert v.is_valid, (body, v.reasons)
    assert body.endswith("?")


def _ask(fsm, message, merchant_id="m_001_drmeera_dentist_delhi", conv="q1"):
    return fsm.process_reply(
        ReplyRequest(conversation_id=conv, merchant_id=merchant_id, message=message, turn_number=2)
    )


def test_price_question_cites_matching_offer(fsm):
    resp = _ask(fsm, "What price do you recommend for cleaning?")
    assert resp.action == "send"
    assert "₹299" in resp.body and "Dental Cleaning" in resp.body
    assert "7-day" not in resp.body
    assert 80 <= len(resp.body) <= 280 and resp.body.endswith("?")


def test_question_for_catalog_service_uses_catalog_price(fsm):
    resp = _ask(fsm, "How much should I charge for whitening?")
    assert "₹1,499" in resp.body and "Teeth Whitening" in resp.body


def test_unknown_service_does_not_invent_price(fsm):
    resp = _ask(fsm, "What should I charge for a facial?")
    assert "no facial offer" in resp.body
    assert "₹299" in resp.body  # anchors on the real live offer instead


def test_assent_with_question_is_answered_not_actioned(fsm):
    resp = _ask(fsm, "Yes, but what would cleaning cost?")
    assert not resp.body.startswith("Done!")
    assert "₹299" in resp.body


def test_commitment_uses_merchant_offer_not_hardcoded(fsm):
    resp = _ask(fsm, "Ok lets do it. Whats next?", merchant_id="m_003_studio11_salon_hyderabad")
    assert resp.body.startswith("Done!")
    assert "Dental" not in resp.body
