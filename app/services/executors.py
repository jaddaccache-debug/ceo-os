from __future__ import annotations

import os
import time
from typing import Callable

from app.models import ProposedAction


class TransientError(Exception):
    """Raised by a live executor for retryable failures (timeouts, 429s, 5xx)."""


# Live connectors register here once they exist, e.g. LIVE_EXECUTORS["send_email"] = gmail_send.
# Until then every type runs in dry-run mode, which records what would have happened.
LIVE_EXECUTORS: dict[str, Callable[[ProposedAction], dict]] = {}


def external_actions_enabled() -> bool:
    return os.getenv("ALLOW_EXTERNAL_ACTIONS", "false").lower() == "true"


def _dry_run(action: ProposedAction) -> dict:
    return {"dry_run": True, "would_execute": action.type, "payload": action.payload}


def with_retries(fn: Callable[[], dict], attempts: int = 3, base_delay: float = 0.5) -> dict:
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except TransientError:
            if attempt == attempts:
                raise
            time.sleep(base_delay * 2 ** (attempt - 1))
    raise RuntimeError("unreachable")


def execute(action: ProposedAction) -> dict:
    live = LIVE_EXECUTORS.get(action.type)
    if not external_actions_enabled() or live is None:
        return _dry_run(action)
    return with_retries(lambda: live(action))
