from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _proposal(**overrides):
    body = {
        'id': 'a-1',
        'type': 'send_email',
        'description': 'Send investor response',
        'payload': {'to': 'demo@example.com', 'body': 'Demo'},
    }
    body.update(overrides)
    return body


def test_client_cannot_self_approve():
    r = client.post('/actions/propose', json=_proposal(status='approved'))
    assert r.status_code == 201
    assert r.json()['status'] == 'proposed'


def test_risk_cannot_be_lowered_below_policy_floor():
    r = client.post('/actions/propose', json=_proposal(risk='low'))
    assert r.json()['risk'] == 'high'
    r = client.post('/actions/propose', json=_proposal(id='a-2', type='draft_email', risk='medium'))
    assert r.json()['risk'] == 'medium'


def test_replayed_proposal_is_idempotent():
    first = client.post('/actions/propose', json=_proposal(id=None), headers={'Idempotency-Key': 'k-1'})
    second = client.post('/actions/propose', json=_proposal(id=None), headers={'Idempotency-Key': 'k-1'})
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()['id'] == second.json()['id']
    assert len(client.get('/actions').json()) == 1


def test_reused_key_with_different_payload_conflicts():
    client.post('/actions/propose', json=_proposal())
    r = client.post('/actions/propose', json=_proposal(description='Something else'))
    assert r.status_code == 409


def test_decision_is_final():
    client.post('/actions/propose', json=_proposal())
    assert client.post('/actions/decide', json={'action_id': 'a-1', 'decision': 'reject'}).status_code == 200
    r = client.post('/actions/decide', json={'action_id': 'a-1', 'decision': 'approve'})
    assert r.status_code == 409
    assert client.get('/actions/a-1').json()['status'] == 'rejected'


def test_decide_unknown_action_is_404():
    r = client.post('/actions/decide', json={'action_id': 'missing', 'decision': 'approve'})
    assert r.status_code == 404


def test_execute_requires_approval_and_runs_once():
    client.post('/actions/propose', json=_proposal())
    assert client.post('/actions/a-1/execute').status_code == 409

    client.post('/actions/decide', json={'action_id': 'a-1', 'decision': 'approve', 'approver': 'jad'})
    r = client.post('/actions/a-1/execute')
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'executed'
    assert body['result']['dry_run'] is True
    assert body['decided_by'] == 'jad'

    assert client.post('/actions/a-1/execute').status_code == 409


def test_audit_trail_records_every_step():
    client.post('/actions/propose', json=_proposal())
    client.post('/actions/decide', json={'action_id': 'a-1', 'decision': 'approve', 'approver': 'jad'})
    client.post('/actions/a-1/execute')
    events = [e['event'] for e in reversed(client.get('/audit', params={'action_id': 'a-1'}).json())]
    assert events == ['action.proposed', 'action.approved', 'action.executing', 'action.executed']


def test_failed_execution_is_recorded(monkeypatch):
    from app.services import executors

    def boom(action):
        raise RuntimeError('provider down')

    monkeypatch.setenv('ALLOW_EXTERNAL_ACTIONS', 'true')
    monkeypatch.setitem(executors.LIVE_EXECUTORS, 'send_email', boom)
    client.post('/actions/propose', json=_proposal())
    client.post('/actions/decide', json={'action_id': 'a-1', 'decision': 'approve'})
    body = client.post('/actions/a-1/execute').json()
    assert body['status'] == 'failed'
    assert 'provider down' in body['result']['error']


def test_transient_errors_are_retried(monkeypatch):
    from app.services import executors

    calls = []

    def flaky(action):
        calls.append(1)
        if len(calls) < 3:
            raise executors.TransientError('429')
        return {'sent': True}

    monkeypatch.setattr(executors.time, 'sleep', lambda s: None)
    monkeypatch.setenv('ALLOW_EXTERNAL_ACTIONS', 'true')
    monkeypatch.setitem(executors.LIVE_EXECUTORS, 'send_email', flaky)
    client.post('/actions/propose', json=_proposal())
    client.post('/actions/decide', json={'action_id': 'a-1', 'decision': 'approve'})
    body = client.post('/actions/a-1/execute').json()
    assert body['status'] == 'executed'
    assert body['result'] == {'sent': True}
    assert len(calls) == 3
