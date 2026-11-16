"""US-10: admin source policy and access control.

Acceptance criteria covered:
  1. Only administrators can edit source weights.
  2. Only administrators can edit source timeouts and API keys.
  3. All configuration changes are recorded in the audit log.

All credentials below are throwaway test fixtures.
"""
import copy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.dam.main import create_app
from backend.dam.models import ApiKey, Audit, Config

ENV_KEY = 'us10-env-key-fixture'


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('DAM_ADMIN_PASSWORD', 'test-admin-password')
    monkeypatch.setenv('DAM_REVIEWER_PASSWORD', 'test-reviewer-password')
    monkeypatch.setenv('DAM_DEVELOPER_PASSWORD', 'test-developer-password')
    monkeypatch.setenv('DAM_API_KEY', ENV_KEY)
    monkeypatch.setenv('DAM_LIVE_SOURCES', 'false')
    monkeypatch.delenv('DAM_LLM_URL', raising=False)
    return create_app('sqlite:///' + (tmp_path / 'us10.db').as_posix(), testing=True)


def session_client(app, username):
    client = TestClient(app)
    response = client.post('/api/login', json={'username': username, 'password': f'test-{username}-password'})
    assert response.status_code == 200
    client.headers['X-CSRF-Token'] = response.json()['csrf']
    return client


def bearer_client(app):
    client = TestClient(app)
    client.headers['Authorization'] = 'Bearer ' + ENV_KEY
    return client


def current_settings(app):
    with app.state.sessions() as db:
        return copy.deepcopy(db.get(Config, 'settings').value)


def audit_rows(app, action=None):
    with app.state.sessions() as db:
        query = select(Audit).order_by(Audit.created_at)
        if action:
            query = query.where(Audit.action == action)
        return list(db.scalars(query))


def audit_count(app):
    with app.state.sessions() as db:
        return db.scalar(select(func.count()).select_from(Audit))


def key_count(app):
    with app.state.sessions() as db:
        return db.scalar(select(func.count()).select_from(ApiKey))


def changed_settings(app, **overrides):
    settings = current_settings(app)
    settings['sources']['curated']['weight'] = 0.4
    settings['sources']['wikidata']['weight'] = 0.7
    settings.update(overrides)
    return settings


CALLERS = ['reviewer', 'developer-session', 'developer-key']


def caller(app, kind):
    if kind == 'developer-key':
        return bearer_client(app)
    return session_client(app, kind.split('-')[0])


# --- AC1 + AC2: administrators can change policy ------------------------------------------

def test_administrator_can_update_weights_timeouts_and_limits(app):
    admin = session_client(app, 'admin')
    payload = changed_settings(app, source_timeout=2.5, request_timeout=10, rate_limit=30)
    response = admin.put('/api/settings', json=payload)
    assert response.status_code == 200
    stored = current_settings(app)
    assert stored['sources']['curated']['weight'] == 0.4
    assert stored['sources']['wikidata']['weight'] == 0.7
    assert (stored['source_timeout'], stored['request_timeout'], stored['rate_limit']) == (2.5, 10, 30)
    assert admin.get('/api/settings').json() == stored


def test_updated_source_weight_changes_verification_trust(app):
    admin = session_client(app, 'admin')
    assert admin.put('/api/settings', json=changed_settings(app)).status_code == 200
    report = bearer_client(app).post('/verify', json={'text': 'The capital of France is Paris.', 'source_app_id': 'demo-app'}).json()
    weights = {e['source']: e['trust_weight'] for e in report['claims'][0]['evidence']}
    assert weights == {'curated': 0.4, 'wikidata': 0.7}


def test_administrator_can_create_and_revoke_keys(app):
    admin = session_client(app, 'admin')
    created = admin.post('/api/keys', json={'name': 'new-app'})
    assert created.status_code == 200
    assert admin.delete('/api/keys/' + created.json()['id']).status_code == 200


# --- Non-administrators are denied --------------------------------------------------------

@pytest.mark.parametrize('kind', CALLERS)
def test_non_admin_cannot_read_or_edit_settings(app, kind):
    before, audits = current_settings(app), audit_count(app)
    client = caller(app, kind)
    assert client.get('/api/settings').status_code == 403
    assert client.put('/api/settings', json=changed_settings(app, source_timeout=1)).status_code == 403
    assert current_settings(app) == before
    assert audit_count(app) == audits


@pytest.mark.parametrize('kind', CALLERS)
def test_non_admin_cannot_manage_api_keys(app, kind):
    client = caller(app, kind)
    keys, audits = key_count(app), audit_count(app)
    with app.state.sessions() as db:
        existing = db.scalar(select(ApiKey)).id
    assert client.get('/api/keys').status_code == 403
    assert client.post('/api/keys', json={'name': 'sneaky'}).status_code == 403
    assert client.delete('/api/keys/' + existing).status_code == 403
    assert key_count(app) == keys
    with app.state.sessions() as db:
        assert db.get(ApiKey, existing).active is True  # not revoked
    assert audit_count(app) == audits


@pytest.mark.parametrize('kind', CALLERS)
def test_non_admin_cannot_read_audit_log(app, kind):
    assert caller(app, kind).get('/api/audit').status_code == 403


def test_unauthenticated_requests_get_401_not_403(app):
    anonymous = TestClient(app)
    assert anonymous.get('/api/settings').status_code == 401
    assert anonymous.put('/api/settings', json=current_settings(app)).status_code == 401
    assert anonymous.post('/api/keys', json={'name': 'x'}).status_code == 401
    assert anonymous.delete('/api/keys/any').status_code == 401
    assert anonymous.get('/api/audit').status_code == 401


def test_administrator_mutations_require_csrf_token(app):
    admin = session_client(app, 'admin')
    del admin.headers['X-CSRF-Token']
    before, keys = current_settings(app), key_count(app)
    assert admin.put('/api/settings', json=changed_settings(app)).status_code == 403
    assert admin.post('/api/keys', json={'name': 'csrf-test'}).status_code == 403
    assert current_settings(app) == before and key_count(app) == keys


def test_api_keys_never_grant_admin_rights_even_if_named_admin(app):
    # API keys always carry the Developer role, whatever their name.
    admin = session_client(app, 'admin')
    created = admin.post('/api/keys', json={'name': 'admin'}).json()
    client = TestClient(app)
    client.headers['Authorization'] = 'Bearer ' + created['key']
    assert client.get('/api/settings').status_code == 403
    assert client.post('/api/keys', json={'name': 'escalate'}).status_code == 403


# --- Validation does not partially apply policy -------------------------------------------

@pytest.mark.parametrize('mutate', [
    lambda s: s['sources']['curated'].update(weight=0),
    lambda s: s['sources']['curated'].update(weight=1.5),
    lambda s: s.update(source_timeout=0),
    lambda s: s.update(source_timeout=60),
    lambda s: s.update(rate_limit=0),
    lambda s: s['sources'].pop('wikipedia'),
    lambda s: s['sources'].update(unknown={'enabled': True, 'weight': 1}),
])
def test_invalid_policy_is_rejected_unchanged_and_unaudited(app, mutate):
    admin = session_client(app, 'admin')
    payload = current_settings(app)
    mutate(payload)
    before, audits = current_settings(app), audit_count(app)
    assert admin.put('/api/settings', json=payload).status_code == 422
    assert current_settings(app) == before
    assert audit_count(app) == audits


# --- AC3: audit log -----------------------------------------------------------------------

def test_settings_change_is_audited_with_actor_before_and_after(app):
    admin = session_client(app, 'admin')
    before = current_settings(app)
    payload = changed_settings(app, source_timeout=1.5)
    assert admin.put('/api/settings', json=payload).status_code == 200
    (row,) = audit_rows(app, 'settings_changed')
    assert row.actor == 'admin'
    assert row.created_at
    assert row.details['before'] == before
    assert row.details['after']['source_timeout'] == 1.5
    assert row.details['after']['sources']['curated']['weight'] == 0.4
    feed = admin.get('/api/audit').json()
    assert feed[0]['action'] == 'settings_changed' and feed[0]['actor'] == 'admin'


def test_key_creation_and_revocation_are_audited_without_secret(app):
    admin = session_client(app, 'admin')
    created = admin.post('/api/keys', json={'name': 'audited-app'}).json()
    assert admin.delete('/api/keys/' + created['id']).status_code == 200
    (made,) = audit_rows(app, 'key_created')
    (revoked,) = audit_rows(app, 'key_revoked')
    assert made.actor == revoked.actor == 'admin'
    assert made.details == {'key_id': created['id'], 'name': 'audited-app'}
    assert revoked.details == {'key_id': created['id']}
    assert created['key'] not in str(admin.get('/api/audit').json())


def test_each_successive_change_gets_its_own_audit_record(app):
    admin = session_client(app, 'admin')
    for timeout in (1, 2, 3):
        assert admin.put('/api/settings', json=changed_settings(app, source_timeout=timeout)).status_code == 200
    rows = audit_rows(app, 'settings_changed')
    assert [r.details['after']['source_timeout'] for r in rows] == [1, 2, 3]
    assert rows[1].details['before']['source_timeout'] == 1


def test_revoking_unknown_key_changes_nothing_and_is_not_audited(app):
    admin = session_client(app, 'admin')
    audits = audit_count(app)
    assert admin.delete('/api/keys/does-not-exist').status_code == 404
    assert audit_count(app) == audits
