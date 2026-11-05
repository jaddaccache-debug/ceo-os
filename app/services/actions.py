from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.db import actions, audit_log, get_engine, now
from app.models import ActionProposal, AuditEntry, ProposedAction
from app.services.executors import execute

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

# Minimum risk per action type. Anything that leaves the building is high risk;
# changes to shared systems of record are medium; drafts and internal tasks are low.
RISK_FLOOR = {
    "draft_email": "low",
    "whatsapp_draft": "low",
    "create_task": "low",
    "calendar_update": "medium",
    "crm_update": "medium",
    "send_email": "high",
}


class ActionNotFound(Exception):
    pass


class ActionConflict(Exception):
    pass


def _row_to_action(row) -> ProposedAction:
    return ProposedAction.model_validate(dict(row._mapping))


def _effective_risk(proposal: ActionProposal) -> str:
    floor = RISK_FLOOR[proposal.type]
    return proposal.risk if RISK_ORDER[proposal.risk] >= RISK_ORDER[floor] else floor


def _audit(conn: Connection, actor: str, event: str, action_id: str | None, detail: dict | None = None) -> None:
    conn.execute(insert(audit_log).values(at=now(), actor=actor, event=event, action_id=action_id, detail=detail or {}))


def _same_proposal(row, proposal: ActionProposal) -> bool:
    return (
        row.type == proposal.type
        and row.description == proposal.description
        and row.payload == proposal.payload
    )


def propose(proposal: ActionProposal, idempotency_key: str | None = None, actor: str = "system") -> tuple[ProposedAction, bool]:
    """Store a proposal. Returns (action, created).

    The idempotency key (header, else the client id) makes retries safe: replaying the
    same proposal returns the stored action instead of creating a duplicate. Reusing a
    key for a different proposal is a conflict.
    """
    action_id = proposal.id or f"act-{uuid.uuid4().hex[:12]}"
    key = idempotency_key or proposal.id or action_id
    engine = get_engine()

    with engine.begin() as conn:
        existing = conn.execute(select(actions).where(actions.c.idempotency_key == key)).first()
        if existing is None and proposal.id:
            existing = conn.execute(select(actions).where(actions.c.id == proposal.id)).first()
    if existing is not None:
        if not _same_proposal(existing, proposal):
            raise ActionConflict(f"Idempotency key or id already used for a different action: {existing.id}")
        return _row_to_action(existing), False

    ts = now()
    risk = _effective_risk(proposal)
    try:
        with engine.begin() as conn:
            conn.execute(insert(actions).values(
                id=action_id, idempotency_key=key, type=proposal.type, description=proposal.description,
                payload=proposal.payload, risk=risk, status="proposed", source_item_id=proposal.source_item_id,
                created_at=ts, updated_at=ts,
            ))
            _audit(conn, actor, "action.proposed", action_id, {"type": proposal.type, "risk": risk, "requested_risk": proposal.risk})
    except IntegrityError:
        # Lost a race with a concurrent retry of the same request; return the winner.
        with engine.begin() as conn:
            row = conn.execute(select(actions).where(actions.c.idempotency_key == key)).first()
        if row is None or not _same_proposal(row, proposal):
            raise ActionConflict(f"Action id already exists: {action_id}")
        return _row_to_action(row), False
    return get(action_id), True


def get(action_id: str) -> ProposedAction:
    with get_engine().begin() as conn:
        row = conn.execute(select(actions).where(actions.c.id == action_id)).first()
    if row is None:
        raise ActionNotFound(action_id)
    return _row_to_action(row)


def get_by_idempotency_key(key: str) -> ProposedAction | None:
    with get_engine().begin() as conn:
        row = conn.execute(select(actions).where(actions.c.idempotency_key == key)).first()
    return _row_to_action(row) if row else None


def list_actions(status: str | None = None) -> list[ProposedAction]:
    query = select(actions).order_by(actions.c.created_at.desc())
    if status:
        query = query.where(actions.c.status == status)
    with get_engine().begin() as conn:
        return [_row_to_action(r) for r in conn.execute(query)]


def _transition(action_id: str, from_status: str, values: dict, actor: str, event: str, detail: dict | None = None) -> None:
    """Compare-and-set status change, so two concurrent decisions cannot both win."""
    with get_engine().begin() as conn:
        res = conn.execute(
            update(actions)
            .where(actions.c.id == action_id, actions.c.status == from_status)
            .values(updated_at=now(), **values)
        )
        if res.rowcount == 1:
            _audit(conn, actor, event, action_id, detail)
            return
    current = get(action_id)  # raises ActionNotFound
    raise ActionConflict(f"Action {action_id} is '{current.status}', expected '{from_status}'")


def decide(action_id: str, decision: str, approver: str) -> ProposedAction:
    status = "approved" if decision == "approve" else "rejected"
    _transition(action_id, "proposed", {"status": status, "decided_by": approver, "decided_at": now()},
                approver, f"action.{status}")
    return get(action_id)


def run(action_id: str, actor: str = "system") -> ProposedAction:
    """Execute an approved action exactly once.

    The approved -> executing claim is atomic, so a retried or duplicated execute call
    cannot run the side effect twice.
    """
    _transition(action_id, "approved", {"status": "executing"}, actor, "action.executing")
    action = get(action_id)
    try:
        result = execute(action)
    except Exception as exc:  # recorded, not swallowed: the caller sees status=failed
        with get_engine().begin() as conn:
            conn.execute(update(actions).where(actions.c.id == action_id)
                         .values(status="failed", updated_at=now(), result={"error": str(exc)}))
            _audit(conn, actor, "action.failed", action_id, {"error": str(exc)})
        return get(action_id)
    with get_engine().begin() as conn:
        conn.execute(update(actions).where(actions.c.id == action_id)
                     .values(status="executed", executed_at=now(), updated_at=now(), result=result))
        _audit(conn, actor, "action.executed", action_id, {"dry_run": result.get("dry_run", False)})
    return get(action_id)


def audit_entries(action_id: str | None = None, limit: int = 200) -> list[AuditEntry]:
    query = select(audit_log).order_by(audit_log.c.id.desc()).limit(limit)
    if action_id:
        query = query.where(audit_log.c.action_id == action_id)
    with get_engine().begin() as conn:
        return [AuditEntry.model_validate(dict(r._mapping)) for r in conn.execute(query)]
