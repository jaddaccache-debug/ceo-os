from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


def test_demo_briefing():
    r = client.get('/demo/briefing')
    assert r.status_code == 200
    body = r.json()
    assert body['top_priorities']
    assert body['decisions_required']
    assert 'executive_summary' in body


def test_human_approval_gate():
    action = {
        'id': 'a-1',
        'type': 'send_email',
        'description': 'Send investor response',
        'payload': {'to': 'demo@example.com', 'body': 'Demo'},
        'risk': 'high',
        'status': 'proposed'
    }
    r = client.post('/actions/propose', json=action)
    assert r.status_code == 201
    assert r.json()['status'] == 'proposed'

    r = client.post('/actions/decide', json={
        'action_id': 'a-1', 'decision': 'approve', 'approver': 'CEO'
    })
    assert r.status_code == 200
    assert r.json()['status'] == 'approved'
