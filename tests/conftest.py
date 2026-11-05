import os

import pytest

from app import db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets an empty database and dry-run-only execution.

    Defaults to a fresh SQLite file. Set TEST_DATABASE_URL to run the suite against
    Postgres; its tables are emptied before each test.
    """
    pg_url = os.getenv("TEST_DATABASE_URL")
    monkeypatch.setenv("DATABASE_URL", pg_url or f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("ALLOW_EXTERNAL_ACTIONS", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db.reset_engine()
    if pg_url:
        with db.get_engine().begin() as conn:
            for table in reversed(db.metadata.sorted_tables):
                conn.execute(table.delete())
    yield
    db.reset_engine()
