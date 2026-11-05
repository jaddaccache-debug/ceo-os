from __future__ import annotations

import os
from datetime import datetime, timezone
from app.models import WorkItem, RankedItem


def _due_pressure(item: WorkItem) -> float:
    if not item.due_at:
        return 0.0
    now = datetime.now(timezone.utc)
    due = item.due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    hours = (due - now).total_seconds() / 3600
    if hours <= 0:
        return 3.0
    if hours <= 4:
        return 2.5
    if hours <= 24:
        return 1.5
    if hours <= 72:
        return 0.75
    return 0.0


DEFAULT_KEY_STAKEHOLDERS = "investor,board,chair,lead investor"
KEY_STAKEHOLDER_BOOST = 1.5


def _key_stakeholders() -> set[str]:
    raw = os.getenv("CEO_KEY_STAKEHOLDERS", DEFAULT_KEY_STAKEHOLDERS)
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


def _is_key_stakeholder(item: WorkItem) -> bool:
    """Items from people the CEO answers to (investors, board) outrank equal-looking peers.

    Matches the sender/owner name or email against CEO_KEY_STAKEHOLDERS, or an explicit
    metadata flag set by a connector that knows better (e.g. a CRM tier).
    """
    if item.metadata.get("key_stakeholder") is True:
        return True
    stakeholders = _key_stakeholders()
    candidates = [item.sender_or_owner, item.metadata.get("from_email")]
    return any(c and c.strip().lower() in stakeholders for c in candidates)


def rank_item(item: WorkItem) -> RankedItem:
    key_stakeholder = _is_key_stakeholder(item)
    score = (
        item.importance * 1.8
        + item.urgency * 1.6
        + (2.0 if item.requires_decision else 0.0)
        + (1.0 if item.requires_reply else 0.0)
        + _due_pressure(item)
        + (KEY_STAKEHOLDER_BOOST if key_stakeholder else 0.0)
    )

    if score >= 18:
        priority = "critical"
    elif score >= 14:
        priority = "high"
    elif score >= 9:
        priority = "medium"
    else:
        priority = "low"

    reasons = [f"importance {item.importance}/5", f"urgency {item.urgency}/5"]
    if item.requires_decision:
        reasons.append("CEO decision required")
    if item.requires_reply:
        reasons.append("reply pending")
    if item.due_at:
        reasons.append("time-bound")
    if key_stakeholder:
        reasons.append("key stakeholder")

    if item.requires_decision:
        action = "Review context, make decision, then delegate execution."
    elif item.requires_reply:
        action = "Draft a concise reply and route for approval."
    elif item.source.value == "calendar":
        action = "Prepare meeting brief and confirm dependencies."
    else:
        action = "Assign owner and next action; monitor to closure."

    return RankedItem(**item.model_dump(), score=round(score, 2), priority=priority, rationale=", ".join(reasons), recommended_action=action)


def rank_items(items: list[WorkItem]) -> list[RankedItem]:
    ranked = [rank_item(i) for i in items]
    return sorted(ranked, key=lambda x: x.score, reverse=True)
