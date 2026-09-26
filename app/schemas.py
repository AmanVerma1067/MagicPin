from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

Scope = Literal["category", "merchant", "customer", "trigger"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ContextPush(_Base):
    scope: Scope
    context_id: str
    version: int = Field(ge=0)
    payload: dict[str, Any]
    delivered_at: Optional[datetime] = None


class ContextAck(_Base):
    accepted: bool
    status: Literal["stored", "noop", "rejected"]
    scope: Scope
    context_id: str
    stored_version: int
    ack_id: Optional[str] = None
    stored_at: Optional[str] = None
    reason: Optional[str] = None


class TickRequest(_Base):
    now: datetime
    available_triggers: List[str]


class OutboundAction(_Base):
    conversation_id: Optional[str] = None
    merchant_id: str
    customer_id: Optional[str] = None
    trigger_id: str
    category: str
    body: str
    cta: str
    send_as: str = "vera"
    suppression_key: str
    rationale: str
    template_name: Optional[str] = None
    template_params: Optional[List[str]] = None


class TickResponse(_Base):
    actions: List[OutboundAction] = Field(default_factory=list, max_length=20)


class ReplyRequest(_Base):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: Literal["merchant", "customer"] = "merchant"
    message: str
    received_at: Optional[datetime] = None
    turn_number: Optional[int] = None


class ReplyResponse(_Base):
    action: Literal["send", "wait", "end"]
    body: Optional[str] = None
    cta: Optional[str] = None
    rationale: str
    wait_seconds: Optional[int] = None


class Health(_Base):
    status: Literal["ok"]
    uptime_seconds: float
    contexts_loaded: dict[str, int]


class Metadata(_Base):
    team_name: str
    team_members: List[str]
    model: str
    approach: str
    version: str
    contact_email: Optional[str] = "team.vera@magicpin.in"
    submitted_at: Optional[str] = "2026-04-26T08:00:00Z"
