from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class Source(str, Enum):
    email = "email"
    calendar = "calendar"
    crm = "crm"
    whatsapp = "whatsapp"
    task = "task"
    news = "news"


class WorkItem(BaseModel):
    id: str
    source: Source
    title: str
    summary: str = ""
    sender_or_owner: str | None = None
    due_at: datetime | None = None
    importance: int = Field(default=3, ge=1, le=5)
    urgency: int = Field(default=3, ge=1, le=5)
    requires_decision: bool = False
    requires_reply: bool = False
    metadata: dict = Field(default_factory=dict)


class RankedItem(WorkItem):
    score: float
    priority: Literal["critical", "high", "medium", "low"]
    rationale: str
    recommended_action: str


class BriefingRequest(BaseModel):
    items: list[WorkItem]
    max_items: int = Field(default=10, ge=1, le=50)


class BriefingResponse(BaseModel):
    generated_at: datetime
    executive_summary: str
    top_priorities: list[RankedItem]
    decisions_required: list[RankedItem]
    follow_ups: list[RankedItem]
    schedule_risks: list[RankedItem]


ActionType = Literal["draft_email", "send_email", "create_task", "calendar_update", "crm_update", "whatsapp_draft"]
Risk = Literal["low", "medium", "high"]
ActionStatus = Literal["proposed", "approved", "rejected", "executing", "executed", "failed"]


class ActionProposal(BaseModel):
    """What a caller (n8n, a connector, the UI) may submit.

    Status, timestamps and approver are server-controlled, so a client cannot submit an
    action that is already approved. Risk can be raised by the caller but never lowered
    below the policy floor for the action type.
    """
    id: str | None = None
    type: ActionType
    description: str
    payload: dict
    risk: Risk = "low"
    source_item_id: str | None = None


class ProposedAction(BaseModel):
    id: str
    type: ActionType
    description: str
    payload: dict
    risk: Risk
    status: ActionStatus
    source_item_id: str | None = None
    created_at: datetime
    updated_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None
    executed_at: datetime | None = None
    result: dict | None = None


class ApprovalDecision(BaseModel):
    action_id: str
    decision: Literal["approve", "reject"]
    approver: str = "CEO"


class AuditEntry(BaseModel):
    id: int
    at: datetime
    actor: str
    event: str
    action_id: str | None
    detail: dict


class CrmOpportunity(BaseModel):
    id: str
    account: str
    contact_name: str
    contact_email: str | None = None
    owner: str
    stage: str
    value: float
    currency: str = "USD"
    last_activity_at: datetime
    next_step: str | None = None


class StaleOpportunity(CrmOpportunity):
    days_inactive: int
