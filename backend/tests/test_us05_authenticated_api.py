"""US-05 (REQ-14, REQ-15, REQ-16): authenticated integration API.

Acceptance criteria covered:
  1. Only hashed bearer API keys are stored.
  2. The API is documented through OpenAPI.
  3. Per-key rate limits are enforced and 429 responses carry Retry-After.

All key values below are throwaway test fixtures.
"""
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.dam.main import create_app
from backend.dam.models import Config
from backend.dam.security import hash_key

ENV_KEY = 'us05-env-key-fixture'
TABLES = ['users', 'api_keys', 'jobs', 'audit', 'config', 'claim_cache']


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DAM_ADMIN_PASSWORD', 'test-admin-password')
    monkeypatch.setenv('DAM_API_KEY', ENV_KEY)
    monkeypatch.setenv('DAM_LIVE_SOURCES', 'false')
    monkeypatch.delenv('DAM_LLM_URL', raising=False)
    app = create_app('sqlite:///' + (tmp_path / 'us05.db').as_posix(), testing=True)
    with TestClient(app) as client:
        yield client


def bearer(key):
    return {'Authorization': 'Bearer ' + key}


def admin_login(client):
    response = client.post('/api/login', json={'username': 'admin', 'password': 'test-admin-password'})
    assert response.status_code == 200
    client.headers['X-CSRF-Token'] = response.json()['csrf']


def create_key(client, name):
    admin_login(client)
    response = client.post('/api/keys', json={'name': name})
    assert response.status_code == 200
    return response.json()


def verify(client, key, app_id='demo-app'):
    return client.post('/verify', headers=bearer(key), json={'text': 'The capital of France is Paris.', 'source_app_id': app_id})


def set_rate_limit(client, limit):
    with client.app.state.sessions() as db:
        row = db.get(Config, 'settings')
        row.value = {**row.value, 'rate_limit': limit}
        db.commit()


def dump_database(client):
    with client.app.state.sessions() as db:
        return '\n'.join(str(row) for table in TABLES for row in db.execute(text(f'SELECT * FROM {table}')))


# --- AC1: hashed storage ------------------------------------------------------------------

def test_only_sha256_hash_of_bootstrap_key_is_stored(client):
    stored = dump_database(client)
    assert ENV_KEY not in stored
    assert hash_key(ENV_KEY) in stored


def test_generated_key_is_returned_once_and_never_stored_raw(client):
    created = create_key(client, 'second-app')
    raw = created['key']
    assert len(raw) >= 32
    stored = dump_database(client)
    assert raw not in stored  # not in api_keys, audit details, jobs, config or cache
    assert hash_key(raw) in stored
    assert verify(client, raw, 'second-app').status_code == 200
    assert raw not in dump_database(client)


def test_key_listing_never_exposes_key_material(client):
    created = create_key(client, 'second-app')
    listing = client.get('/api/keys').json()
    assert listing and all(set(item) == {'id', 'name', 'active'} for item in listing)
    body = client.get('/api/keys').text
    assert created['key'] not in body and hash_key(created['key']) not in body


def test_raw_keys_are_not_written_to_logs(client, caplog):
    with caplog.at_level(logging.DEBUG):
        created = create_key(client, 'logged-app')
        verify(client, created['key'], 'logged-app')
        verify(client, 'definitely-wrong-key')
    assert created['key'] not in caplog.text
    assert 'definitely-wrong-key' not in caplog.text


# --- Bearer authentication ----------------------------------------------------------------

@pytest.mark.parametrize('headers', [
    {},
    {'Authorization': 'Bearer '},
    {'Authorization': 'Bearer not-a-real-key'},
    {'Authorization': 'Basic ' + ENV_KEY},
    {'Authorization': ENV_KEY},
])
def test_missing_malformed_or_unknown_credentials_are_rejected(client, headers):
    response = client.post('/verify', headers=headers, json={'text': 'x', 'source_app_id': 'demo-app'})
    assert response.status_code == 401


def test_key_hash_cannot_be_used_as_a_credential(client):
    assert verify(client, hash_key(ENV_KEY)).status_code == 401


def test_revoked_key_is_rejected_on_every_endpoint(client):
    created = create_key(client, 'short-lived')
    assert verify(client, created['key'], 'short-lived').status_code == 200
    assert client.delete('/api/keys/' + created['id']).status_code == 200
    anonymous = {'Authorization': 'Bearer ' + created['key']}
    other = TestClient(client.app)  # no session cookie: only the bearer key is presented
    with other:
        assert other.post('/verify', headers=anonymous, json={'text': 'x', 'source_app_id': 'short-lived'}).status_code == 401
        assert other.get('/api/jobs', headers=anonymous).status_code == 401
        assert other.get('/api/session', headers=anonymous).status_code == 401
    assert next(k for k in client.get('/api/keys').json() if k['id'] == created['id'])['active'] is False


# --- AC2: OpenAPI -------------------------------------------------------------------------

def test_openapi_document_describes_bearer_authenticated_verify_endpoint(client):
    response = client.get('/openapi.json')
    assert response.status_code == 200
    schema = response.json()
    assert schema['openapi'].startswith('3.')
    assert schema['info']['title'] and schema['info']['version']
    schemes = schema['components']['securitySchemes']
    assert any(s.get('type') == 'http' and s.get('scheme') == 'bearer' for s in schemes.values())
    for path in ('/verify', '/api/verify'):
        operation = schema['paths'][path]['post']
        assert operation['security']
        assert '422' in operation['responses']
    assert 'VerifyInput' in schema['components']['schemas']


def test_interactive_documentation_is_reachable_without_authentication(client):
    assert client.get('/docs').status_code == 200
    assert client.get('/redoc').status_code == 200
    assert client.get('/openapi.json').status_code == 200


# --- AC3: per-key rate limits -------------------------------------------------------------

def test_rate_limit_is_tracked_separately_for_each_key(client):
    second = create_key(client, 'second-app')
    set_rate_limit(client, 2)
    anonymous = TestClient(client.app)
    with anonymous:
        assert [anonymous.get('/api/jobs', headers=bearer(ENV_KEY)).status_code for _ in range(2)] == [200, 200]
        assert anonymous.get('/api/jobs', headers=bearer(ENV_KEY)).status_code == 429
        # Exhausting the first key must not throttle the second.
        assert [anonymous.get('/api/jobs', headers=bearer(second['key'])).status_code for _ in range(2)] == [200, 200]
        assert anonymous.get('/api/jobs', headers=bearer(second['key'])).status_code == 429


def test_rate_limited_response_has_retry_after_and_error_body(client):
    set_rate_limit(client, 1)
    assert verify(client, ENV_KEY).status_code == 200
    response = verify(client, ENV_KEY)
    assert response.status_code == 429
    retry_after = int(response.headers['Retry-After'])
    assert 1 <= retry_after <= 61
    assert response.json() == {'error': {'code': '429', 'message': 'Rate limit exceeded'}}


def test_rejected_requests_do_not_consume_a_valid_keys_budget(client):
    set_rate_limit(client, 1)
    for _ in range(5):
        assert verify(client, 'wrong-key').status_code == 401
    assert verify(client, ENV_KEY).status_code == 200
