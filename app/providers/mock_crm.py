from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.models import CrmOpportunity

SAMPLE_PATH = Path(__file__).resolve().parent.parent.parent / "sample_data" / "crm_opportunities.json"


def list_opportunities(path: Path = SAMPLE_PATH) -> list[CrmOpportunity]:
    """Stand-in for a HubSpot/Salesforce client.

    The sample file stores activity as "days ago" so the demo never goes stale; a real
    connector returns absolute timestamps and maps them to the same model.
    """
    now = datetime.now(timezone.utc)
    opportunities = []
    for raw in json.loads(path.read_text()):
        raw = dict(raw)
        days_ago = raw.pop("last_activity_days_ago")
        raw["last_activity_at"] = now - timedelta(days=days_ago)
        opportunities.append(CrmOpportunity.model_validate(raw))
    return opportunities
