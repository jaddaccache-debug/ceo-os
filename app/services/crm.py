from __future__ import annotations

import os
from datetime import datetime, timezone

from app.models import ActionProposal, CrmOpportunity, ProposedAction, Source, StaleOpportunity, WorkItem
from app.providers.openai_provider import generate_text
from app.services import actions

CLOSED_STAGES = {"closed_won", "closed_lost"}


def _min_value() -> float:
    return float(os.getenv("CRM_STALE_MIN_VALUE", "50000"))


def _stale_days() -> int:
    return int(os.getenv("CRM_STALE_DAYS", "5"))


def find_stale(opportunities: list[CrmOpportunity]) -> list[StaleOpportunity]:
    """Open, high-value opportunities with no activity for CRM_STALE_DAYS or more, largest first."""
    now = datetime.now(timezone.utc)
    stale = []
    for opp in opportunities:
        if opp.stage in CLOSED_STAGES or opp.value < _min_value():
            continue
        last = opp.last_activity_at if opp.last_activity_at.tzinfo else opp.last_activity_at.replace(tzinfo=timezone.utc)
        days = int((now - last).total_seconds() // 86400)
        if days >= _stale_days():
            stale.append(StaleOpportunity(**opp.model_dump(), days_inactive=days))
    return sorted(stale, key=lambda o: o.value, reverse=True)


def to_work_item(opp: StaleOpportunity) -> WorkItem:
    return WorkItem(
        id=f"crm-{opp.id}",
        source=Source.crm,
        title=f"Stalled deal: {opp.account} ({opp.currency} {opp.value:,.0f})",
        summary=f"{opp.stage} stage, no activity for {opp.days_inactive} days. Next step: {opp.next_step or 'none recorded'}.",
        sender_or_owner=opp.owner,
        importance=5 if opp.value >= 250_000 else 4,
        urgency=4 if opp.days_inactive >= 7 else 3,
        requires_reply=True,
        metadata={"opportunity_id": opp.id, "value": opp.value, "days_inactive": opp.days_inactive},
    )


def _draft_body(opp: StaleOpportunity) -> str:
    prompt = (
        "Write a short, warm follow-up email (under 90 words, no subject line) from a CEO to a "
        f"prospect. Contact: {opp.contact_name} at {opp.account}. Deal stage: {opp.stage}. "
        f"Last agreed next step: {opp.next_step or 'none recorded'}. Do not invent facts, prices or dates."
    )
    ai = generate_text(prompt)
    if ai:
        return ai
    next_step = f" on {opp.next_step[0].lower() + opp.next_step[1:]}" if opp.next_step else ""
    return (
        f"Hi {opp.contact_name.split()[0]},\n\n"
        f"I wanted to check in personally on where things stand with {opp.account}. "
        f"Is there anything you need from us to move forward{next_step}? "
        "Happy to find 20 minutes this week if useful.\n\nBest regards"
    )


def propose_follow_ups(opportunities: list[CrmOpportunity], actor: str = "crm-watcher") -> list[ProposedAction]:
    """Create one draft follow-up per stale episode, behind the approval gate.

    The idempotency key includes the last-activity date, so re-running the watcher (or an
    n8n retry) does not duplicate drafts, while a deal that goes stale again later gets a new one.
    """
    proposed = []
    for opp in find_stale(opportunities):
        key = f"crm-followup:{opp.id}:{opp.last_activity_at.date().isoformat()}"
        existing = actions.get_by_idempotency_key(key)
        if existing:
            proposed.append(existing)
            continue
        action, _ = actions.propose(ActionProposal(
            type="draft_email",
            description=f"Follow-up draft for stalled {opp.account} opportunity ({opp.days_inactive} days inactive)",
            payload={
                "to": opp.contact_email,
                "subject": f"Checking in — {opp.account}",
                "body": _draft_body(opp),
                "opportunity_id": opp.id,
            },
            risk="low",
            source_item_id=f"crm-{opp.id}",
        ), idempotency_key=key, actor=actor)
        proposed.append(action)
    return proposed
