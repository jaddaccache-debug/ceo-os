from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_stale_detection_filters_value_stage_and_recency():
    ids = [o['id'] for o in client.get('/crm/stale-opportunities').json()]
    # opp-1003 is too small, opp-1004 is active, opp-1005 is closed.
    assert ids == ['opp-1001', 'opp-1002']


def test_follow_ups_are_drafts_behind_approval_and_idempotent():
    first = client.post('/crm/follow-ups').json()
    assert len(first) == 2
    assert all(a['type'] == 'draft_email' and a['status'] == 'proposed' for a in first)
    assert first[0]['payload']['to'] == 'dana.whitfield@example.com'
    assert 'Dana' in first[0]['payload']['body']

    second = client.post('/crm/follow-ups').json()
    assert [a['id'] for a in second] == [a['id'] for a in first]
    assert len(client.get('/actions').json()) == 2


def test_stale_deal_becomes_briefing_item():
    from app.providers import mock_crm
    from app.services import crm

    item = crm.to_work_item(crm.find_stale(mock_crm.list_opportunities())[0])
    assert item.source.value == 'crm'
    assert item.requires_reply
    assert item.importance == 5
