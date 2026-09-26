import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_full_api_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET /v1/healthz
        res = await client.get("/v1/healthz")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "contexts_loaded" in data

        # 2. GET /v1/metadata
        res = await client.get("/v1/metadata")
        assert res.status_code == 200
        data = res.json()
        assert data["team_name"] == "Team Vera"
        assert data["version"] == "1.0.0"

        # 3. POST /v1/context (Category push)
        cat_payload = {
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": {
                "slug": "dentists",
                "voice": {"tone": "peer_clinical", "vocab_taboo": ["guaranteed"]},
                "peer_stats": {"avg_rating": 4.4, "avg_views_30d": 1820},
                "offer_catalog": [{"id": "d1", "title": "Dental Cleaning @ ₹299", "value": "299"}],
            },
        }
        res = await client.post("/v1/context", json=cat_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["accepted"] is True
        assert data["status"] == "stored"

        # Push merchant
        merch_payload = {
            "scope": "merchant",
            "context_id": "m_test_1",
            "version": 1,
            "payload": {
                "merchant_id": "m_test_1",
                "category_slug": "dentists",
                "identity": {"name": "Dr. Meera's Clinic", "locality": "Lajpat Nagar", "city": "Delhi", "owner_first_name": "Meera"},
                "performance": {"views": 2410, "calls": 18},
                "offers": [{"id": "o1", "title": "Dental Cleaning @ ₹299", "status": "active"}],
            },
        }
        res = await client.post("/v1/context", json=merch_payload)
        assert res.status_code == 200
        assert res.json()["accepted"] is True

        # Push trigger
        trg_payload = {
            "scope": "trigger",
            "context_id": "trg_test_1",
            "version": 1,
            "payload": {
                "id": "trg_test_1",
                "kind": "perf_dip",
                "merchant_id": "m_test_1",
                "urgency": 3,
                "payload": {"drop_pct": 0.20},
            },
        }
        res = await client.post("/v1/context", json=trg_payload)
        assert res.status_code == 200
        assert res.json()["accepted"] is True

        # Check healthz reflects context count
        res = await client.get("/v1/healthz")
        counts = res.json()["contexts_loaded"]
        assert counts["category"] >= 1
        assert counts["merchant"] >= 1
        assert counts["trigger"] >= 1

        # 4. POST /v1/tick
        tick_payload = {
            "now": "2026-04-26T10:35:00Z",
            "available_triggers": ["trg_test_1"],
        }
        res = await client.post("/v1/tick", json=tick_payload)
        assert res.status_code == 200
        tick_data = res.json()
        assert "actions" in tick_data
        assert len(tick_data["actions"]) == 1
        action = tick_data["actions"][0]
        assert action["merchant_id"] == "m_test_1"
        assert len(action["body"]) >= 80

        # 5. POST /v1/reply (Affirmative)
        reply_affirm = {
            "conversation_id": "conv_test_1",
            "merchant_id": "m_test_1",
            "from_role": "merchant",
            "message": "Ok lets do it. Whats next?",
            "turn_number": 2,
        }
        res = await client.post("/v1/reply", json=reply_affirm)
        assert res.status_code == 200
        reply_data = res.json()
        assert reply_data["action"] == "send"
        assert any(w in reply_data["body"].lower() for w in ["done", "sending", "confirm", "proceed", "next"])

        # 6. POST /v1/reply (Auto-reply)
        reply_auto = {
            "conversation_id": "conv_test_auto",
            "merchant_id": "m_test_1",
            "from_role": "merchant",
            "message": "Thank you for contacting us! Our team will respond shortly.",
            "turn_number": 2,
        }
        res = await client.post("/v1/reply", json=reply_auto)
        assert res.status_code == 200
        assert res.json()["action"] == "wait"
        assert res.json()["wait_seconds"] > 0
