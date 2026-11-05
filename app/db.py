from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Column, DateTime, Engine, Integer, MetaData, String, Table, Text, create_engine,
)

metadata = MetaData()

# Tables are prefixed so they can share a Postgres database with other tools without colliding.
actions = Table(
    "ceo_actions",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("idempotency_key", String(256), unique=True, nullable=False),
    Column("type", String(32), nullable=False),
    Column("description", Text, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("risk", String(16), nullable=False),
    Column("status", String(16), nullable=False),
    Column("source_item_id", String(128)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("decided_by", String(128)),
    Column("decided_at", DateTime(timezone=True)),
    Column("executed_at", DateTime(timezone=True)),
    Column("result", JSON),
)

audit_log = Table(
    "ceo_audit_log",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("at", DateTime(timezone=True), nullable=False),
    Column("actor", String(128), nullable=False),
    Column("event", String(64), nullable=False),
    Column("action_id", String(128)),
    Column("detail", JSON, nullable=False),
)

_engine: Engine | None = None


def now() -> datetime:
    return datetime.now(timezone.utc)


def database_url() -> str:
    return os.getenv("DATABASE_URL") or "sqlite:///./ceoos.db"


def get_engine() -> Engine:
    """Create the engine on first use and make sure the schema exists.

    Lazy creation keeps tests and scripts free of startup hooks. Schema changes beyond
    additive tables should move to Alembic migrations before a real pilot.
    """
    global _engine
    if _engine is None:
        url = database_url()
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
        _engine = create_engine(url, **kwargs)
        metadata.create_all(_engine)
    return _engine


def reset_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
