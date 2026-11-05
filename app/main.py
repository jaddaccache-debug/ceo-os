from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Response

from app.models import (
    ActionProposal, ApprovalDecision, AuditEntry, BriefingRequest, BriefingResponse, ProposedAction,
    StaleOpportunity, WorkItem,
)
from app.providers import mock_crm
from app.services import actions, crm
from app.services.briefing import build_briefing

load_dotenv()
app = FastAPI(title="CEO OS", version="0.2.0", description="AI executive operating system MVP")


@app.get("/health")
def health():
    return {"status": "ok", "service": "ceo-os"}


@app.post("/briefing", response_model=BriefingResponse)
def briefing(req: BriefingRequest):
    return build_briefing(req.items, req.max_items)


@app.get("/demo/briefing", response_model=BriefingResponse)
def demo_briefing():
    path = Path(__file__).resolve().parent.parent / "sample_data" / "work_items.json"
    raw = json.loads(path.read_text())
    items = [WorkItem.model_validate(x) for x in raw]
    return build_briefing(items, 10)


@app.get("/briefing/google", response_model=BriefingResponse)
def google_briefing(max_items: int = 10, include_crm: bool = True):
    """Live briefing from the authorized Gmail + Calendar account (plus mock CRM)."""
    from app.providers import google_workspace

    try:
        items = google_workspace.fetch_work_items()
    except google_workspace.GoogleNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if include_crm:
        items += [crm.to_work_item(o) for o in crm.find_stale(mock_crm.list_opportunities())]
    return build_briefing(items, max_items)


# --- Approval gate ---

@app.post("/actions/propose", response_model=ProposedAction)
def propose_action(proposal: ActionProposal, response: Response, idempotency_key: str | None = Header(default=None)):
    try:
        action, created = actions.propose(proposal, idempotency_key)
    except actions.ActionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    response.status_code = 201 if created else 200
    return action


@app.post("/actions/decide", response_model=ProposedAction)
def decide_action(decision: ApprovalDecision):
    try:
        return actions.decide(decision.action_id, decision.decision, decision.approver)
    except actions.ActionNotFound:
        raise HTTPException(status_code=404, detail="Action not found")
    except actions.ActionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/actions/{action_id}/execute", response_model=ProposedAction)
def execute_action(action_id: str):
    try:
        return actions.run(action_id)
    except actions.ActionNotFound:
        raise HTTPException(status_code=404, detail="Action not found")
    except actions.ActionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/actions", response_model=list[ProposedAction])
def list_actions(status: str | None = None):
    return actions.list_actions(status)


@app.get("/actions/{action_id}", response_model=ProposedAction)
def get_action(action_id: str):
    try:
        return actions.get(action_id)
    except actions.ActionNotFound:
        raise HTTPException(status_code=404, detail="Action not found")


@app.get("/audit", response_model=list[AuditEntry])
def audit(action_id: str | None = None, limit: int = 200):
    return actions.audit_entries(action_id, limit)


# --- CRM ---

@app.get("/crm/stale-opportunities", response_model=list[StaleOpportunity])
def stale_opportunities():
    return crm.find_stale(mock_crm.list_opportunities())


@app.post("/crm/follow-ups", response_model=list[ProposedAction])
def propose_crm_follow_ups():
    """Draft follow-ups for stalled deals. Safe to call repeatedly (e.g. from a schedule)."""
    return crm.propose_follow_ups(mock_crm.list_opportunities())
