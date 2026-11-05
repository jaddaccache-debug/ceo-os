from __future__ import annotations

from datetime import datetime, timezone
from app.models import BriefingResponse, WorkItem
from app.services.prioritizer import rank_items
from app.providers.openai_provider import generate_text


def _fallback_summary(ranked):
    critical = sum(1 for x in ranked if x.priority == "critical")
    high = sum(1 for x in ranked if x.priority == "high")
    decisions = sum(1 for x in ranked if x.requires_decision)
    replies = sum(1 for x in ranked if x.requires_reply)
    return (
        f"{critical} critical and {high} high-priority items require attention. "
        f"There are {decisions} decisions and {replies} pending replies. "
        "Focus first on time-bound decisions, then unblock delegated execution."
    )


def build_briefing(items: list[WorkItem], max_items: int = 10) -> BriefingResponse:
    ranked = rank_items(items)
    top = ranked[:max_items]

    compact_context = "\n".join(
        f"- [{x.priority.upper()}] {x.title}: {x.summary} | action={x.recommended_action}"
        for x in top[:8]
    )
    prompt = (
        "You are an executive chief-of-staff system. Produce a 3-sentence morning briefing. "
        "Be direct, decision-oriented and do not invent facts.\n\n" + compact_context
    )
    ai_summary = generate_text(prompt)

    return BriefingResponse(
        generated_at=datetime.now(timezone.utc),
        executive_summary=ai_summary or _fallback_summary(top),
        top_priorities=top,
        decisions_required=[x for x in ranked if x.requires_decision][:max_items],
        follow_ups=[x for x in ranked if x.requires_reply][:max_items],
        schedule_risks=[x for x in ranked if x.source.value == "calendar" and x.priority in {"critical", "high"}][:max_items],
    )
