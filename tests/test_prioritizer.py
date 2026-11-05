from app.models import WorkItem, Source
from app.services.prioritizer import rank_item


def test_high_priority_decision_scores_above_low_item():
    high = WorkItem(
        id="1", source=Source.email, title="Decision", importance=5, urgency=5,
        requires_decision=True, requires_reply=True
    )
    low = WorkItem(id="2", source=Source.news, title="FYI", importance=1, urgency=1)
    assert rank_item(high).score > rank_item(low).score
    assert rank_item(high).priority in {"critical", "high"}


def test_key_stakeholder_outranks_equal_peer():
    base = dict(source=Source.email, title="Ask", importance=4, urgency=3, requires_reply=True)
    investor = rank_item(WorkItem(id="i", sender_or_owner="Investor", **base))
    peer = rank_item(WorkItem(id="p", sender_or_owner="Vendor", **base))
    assert investor.score == peer.score + 1.5
    assert "key stakeholder" in investor.rationale


def test_key_stakeholder_matches_email_from_env(monkeypatch):
    monkeypatch.setenv("CEO_KEY_STAKEHOLDERS", "chair@board.example")
    item = WorkItem(id="c", source=Source.email, title="Agenda", sender_or_owner="Pat Chair",
                    metadata={"from_email": "chair@board.example"})
    assert "key stakeholder" in rank_item(item).rationale
