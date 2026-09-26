from app.reply_fsm import ConversationManager
from app.schemas import ReplyRequest
from app.store import ContextStore


def test_reply_fsm_auto_reply_detection():
    store = ContextStore()
    fsm = ConversationManager(store)

    req = ReplyRequest(
        conversation_id="conv_auto_1",
        merchant_id="m_1",
        message="Thank you for contacting Dr. Meera's Dental Clinic! Our team will respond shortly.",
    )
    resp = fsm.process_reply(req)
    assert resp.action == "wait"
    assert resp.wait_seconds is not None
    assert resp.wait_seconds > 0
    assert resp.body is None


def test_reply_fsm_auto_reply_hell_ends_after_4_turns():
    store = ContextStore()
    fsm = ConversationManager(store)
    auto_msg = "Thank you for contacting us! We are currently closed."

    for i in range(1, 4):
        req = ReplyRequest(conversation_id="conv_auto_hell", merchant_id="m_1", message=auto_msg)
        resp = fsm.process_reply(req)
        assert resp.action == "wait"

    # Turn 4
    req4 = ReplyRequest(conversation_id="conv_auto_hell", merchant_id="m_1", message=auto_msg)
    resp4 = fsm.process_reply(req4)
    assert resp4.action == "end"


def test_reply_fsm_hostile_handling():
    store = ContextStore()
    fsm = ConversationManager(store)

    req = ReplyRequest(
        conversation_id="conv_hostile",
        merchant_id="m_1",
        message="Stop messaging me. This is useless spam.",
    )
    resp = fsm.process_reply(req)
    assert resp.action == "end"


def test_reply_fsm_opt_out():
    store = ContextStore()
    fsm = ConversationManager(store)

    req = ReplyRequest(
        conversation_id="conv_optout",
        merchant_id="m_1",
        message="Please unsubscribe me from this service.",
    )
    resp = fsm.process_reply(req)
    assert resp.action == "end"


def test_reply_fsm_affirmative_action_mode():
    store = ContextStore()
    fsm = ConversationManager(store)

    req = ReplyRequest(
        conversation_id="conv_affirmative",
        merchant_id="m_1",
        message="Ok lets do it. Whats next?",
    )
    resp = fsm.process_reply(req)
    assert resp.action == "send"
    assert resp.body is not None

    body_lower = resp.body.lower()
    # Must contain actioning words
    actioning = ["done", "sending", "draft", "here", "confirm", "proceed", "next"]
    assert any(w in body_lower for w in actioning), f"No action word in: {resp.body}"

    # Must NOT contain qualifying words
    qualifying = ["would you", "do you", "can you tell", "what if", "how about"]
    assert not any(w in body_lower for w in qualifying), f"Found qualifying word in: {resp.body}"
