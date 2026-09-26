from datetime import datetime
import pytest
from pydantic import ValidationError

from app.schemas import (
    ContextAck,
    ContextPush,
    Health,
    Metadata,
    OutboundAction,
    ReplyRequest,
    ReplyResponse,
    TickRequest,
    TickResponse,
)


def test_extra_fields_allowed_on_inputs():
    push = ContextPush(
        scope="merchant",
        context_id="m_001",
        version=1,
        payload={"some": "data"},
        extra_judge_field="arbitrary_value",
    )
    assert push.context_id == "m_001"
    assert getattr(push, "extra_judge_field") == "arbitrary_value"

    tick = TickRequest(
        now=datetime.fromisoformat("2026-04-26T10:00:00Z"),
        available_triggers=["trg_01"],
        extra_harness_meta={"sim_speed": 10},
    )
    assert len(tick.available_triggers) == 1
    assert getattr(tick, "extra_harness_meta") == {"sim_speed": 10}

    reply = ReplyRequest(
        conversation_id="conv_1",
        merchant_id="m_001",
        message="Hello",
        received_at=datetime.fromisoformat("2026-04-26T10:05:00Z"),
        unexpected_debug=True,
    )
    assert reply.message == "Hello"
    assert getattr(reply, "unexpected_debug") is True


def test_context_ack_model():
    ack = ContextAck(
        accepted=True,
        status="stored",
        scope="category",
        context_id="dentists",
        stored_version=1,
    )
    assert ack.accepted is True
    assert ack.status == "stored"


def test_tick_response_max_actions():
    actions = [
        OutboundAction(
            merchant_id=f"m_{i}",
            trigger_id=f"t_{i}",
            category="dentists",
            body=f"Test body {i}",
            cta="Yes/No",
            send_as="vera",
            suppression_key=f"sup_{i}",
            rationale=f"Rationale {i}",
        )
        for i in range(20)
    ]
    resp = TickResponse(actions=actions)
    assert len(resp.actions) == 20

    with pytest.raises(ValidationError):
        actions_21 = actions + [
            OutboundAction(
                merchant_id="m_21",
                trigger_id="t_21",
                category="dentists",
                body="Overflow",
                cta="Yes/No",
                send_as="vera",
                suppression_key="sup_21",
                rationale="Over",
            )
        ]
        TickResponse(actions=actions_21)


def test_reply_response_actions():
    resp_send = ReplyResponse(action="send", body="Message", cta="binary", rationale="Ok")
    assert resp_send.action == "send"

    resp_wait = ReplyResponse(action="wait", wait_seconds=3600, rationale="Auto-reply")
    assert resp_wait.action == "wait"
    assert resp_wait.wait_seconds == 3600

    resp_end = ReplyResponse(action="end", rationale="Opt-out")
    assert resp_end.action == "end"


def test_health_and_metadata():
    h = Health(
        status="ok",
        uptime_seconds=12.5,
        contexts_loaded={"category": 5, "merchant": 50, "customer": 200, "trigger": 100},
    )
    assert h.status == "ok"
    assert h.contexts_loaded["merchant"] == 50

    m = Metadata(
        team_name="Team Vera",
        team_members=["Aman Verma"],
        model="gemini-2.5-flash",
        approach="Grounded Composer",
        version="1.0.0",
    )
    assert m.team_name == "Team Vera"
