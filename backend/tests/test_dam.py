import asyncio
import copy
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.dam.extraction import extract, fallback_extract
from backend.dam.main import create_app
from backend.dam.models import ApiKey, Audit, Config
from backend.dam.pipeline import score
from backend.dam.security import hash_key
from backend.dam.sources import CuratedSource, WikidataSource, WikipediaSource, evidence, lookup


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DAM_ADMIN_PASSWORD', 'test-admin-password')
    monkeypatch.setenv('DAM_REVIEWER_PASSWORD', 'test-reviewer-password')
    monkeypatch.setenv('DAM_API_KEY', 'test-integrator-key')
    monkeypatch.setenv('DAM_LIVE_SOURCES', 'false')
    monkeypatch.delenv('DAM_LLM_URL', raising=False)
    app = create_app('sqlite:///' + (tmp_path / 'test.db').as_posix(), testing=True)
    with TestClient(app) as client:
        yield client


def login(client, name='admin'):
    response = client.post('/api/login', json={'username': name, 'password': f'test-{name}-password'})
    assert response.status_code == 200
    client.headers['X-CSRF-Token'] = response.json()['csrf']


def verify(client, text='The capital of France is Paris.', **extra):
    return client.post('/verify', headers={'Authorization': 'Bearer test-integrator-key'}, json={'text': text, 'source_app_id': 'demo-app', **extra})


def test_req01_limits_and_validation(client):
    assert verify(client, 'a' * 10000).status_code == 200
    assert verify(client, 'a' * 10001).status_code == 422
    assert verify(client, '', context='a' * 2001).status_code == 422
    assert verify(client, confidence_threshold=1.1).status_code == 422


def test_req02_extraction_excludes_nonfacts():
    result = fallback_extract('Hello! Is Paris nice? I think Paris is wonderful. France is in Europe.')
    assert [c['text'] for c in result] == ['France is in Europe.']


def test_req03_offsets_unicode_and_abbreviation():
    text = '  🌍 Earth orbits the Sun.\nDr. Ada was born in London. '
    claims = fallback_extract(text)
    assert len(claims) == 2
    assert claims[1]['text'] == 'Dr. Ada was born in London.'
    for claim in claims:
        assert text[claim['start']:claim['end']] == claim['text']


def test_req04_empty_claim_list(client):
    report = verify(client, 'Hello! Thank you. What is your name?').json()
    assert report['claims'] == []
    assert report['hallucination_score'] == 0


def test_req05_sources_queried(client):
    claim = verify(client).json()['claims'][0]
    assert {s['source'] for s in claim['source_results']} == {'wikidata', 'curated'}
    assert any(e.get('snapshot') for e in claim['evidence'])


@pytest.mark.parametrize('text,verdict', [
    ('The capital of France is Paris.', 'Supported'),
    ('The capital of France is London.', 'Contradicted'),
    ('The Moon is made of cheese.', 'Unsupported'),
])
def test_req06_verdicts(client, text, verdict):
    assert verify(client, text).json()['claims'][0]['verdict'] == verdict


def test_req06_unavailable_notcheckable():
    result = score([{'status': 'timeout', 'evidence': []}], .5)
    assert result['verdict'] == 'Not-Checkable'


def test_req07_evidence(client):
    for text in ['The capital of France is Paris.', 'The capital of France is London.']:
        claim = verify(client, text).json()['claims'][0]
        assert claim['evidence'][0]['url'].startswith('https://')
        assert claim['evidence'][0]['snippet']


def test_req08_parallel_source_timeout():
    class Slow:
        name = 'slow'
        async def query(self, text, client):
            await asyncio.sleep(1)
    async def run():
        async with httpx.AsyncClient() as client:
            return await asyncio.gather(lookup(Slow(), 'x', client, .02, 1), lookup(CuratedSource(), 'Earth orbits the Sun.', client, .02, 1))
    results = asyncio.run(run())
    assert results[0]['status'] == 'timeout'
    assert results[1]['evidence'][0]['verdict'] == 'Supported'


def test_req09_trust_agreement_recency():
    supported = evidence('test', 'fact', 'urn:test', 'Supported')
    supported['trust_weight'] = 1
    original = score([{'status': 'ok', 'evidence': [supported]}], .5)['confidence_score']
    conflicting = {**supported, 'verdict': 'Contradicted'}
    assert score([{'status': 'ok', 'evidence': [supported, conflicting]}], .5)['confidence_score'] < original
    stale = {**supported, 'observed_at': '2010-01-01T00:00:00+00:00'}
    assert score([{'status': 'ok', 'evidence': [stale]}], .5)['confidence_score'] < original
    assert 0 <= original <= 1
    low_trust = {**supported, 'trust_weight': .2}
    assert score([{'status': 'ok', 'evidence': [low_trust]}], .5)['confidence_score'] < original


def test_req10_configurable_flag_threshold(client):
    assert verify(client, confidence_threshold=.99).json()['claims'][0]['flagged']
    assert not verify(client, confidence_threshold=.1).json()['claims'][0]['flagged']
    assert not verify(client, 'The Moon is made of cheese.', confidence_threshold=0).json()['claims'][0]['flagged']


def test_req11_document_score(client):
    report = verify(client, 'The capital of France is Paris. The capital of India is Mumbai.').json()
    assert report['hallucination_score'] == .5
    assert report['counts']['Contradicted'] == 1


def test_req12_correction_threshold(client):
    report = verify(client, 'The capital of Australia is Sydney.').json()
    assert report['claims'][0]['suggested_correction'] == 'The capital of Australia is Canberra.'
    item = evidence('test', 'correct', 'urn:test', 'Contradicted', 'correct')
    item.update(quality=.6, trust_weight=1)
    assert score([{'status': 'ok', 'evidence': [item]}], .5)['suggested_correction'] is None


def test_req13_original_preserved(client):
    text = '  The capital of France is London.\n'
    assert verify(client, text).json()['original_text'] == text


def test_req14_auth_key_hash_and_ownership(client):
    assert client.post('/verify', json={'text': 'x', 'source_app_id': 'x'}).status_code == 401
    assert client.get('/api/jobs', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    assert client.post('/verify', headers={'Authorization': 'Bearer test-integrator-key'}, json={'text': 'x', 'source_app_id': 'spoofed-app'}).status_code == 403
    with client.app.state.sessions() as db:
        key = db.scalar(select(ApiKey))
        assert key.key_hash == hash_key('test-integrator-key')
        assert key.key_hash != 'test-integrator-key'


def test_req15_openapi(client):
    schema = client.get('/openapi.json').json()
    assert '/verify' in schema['paths']
    assert schema['paths']['/verify']['post']['security']
    assert client.get('/docs').status_code == 200


def test_req16_rate_limit(client):
    with client.app.state.sessions() as db:
        row = db.get(Config, 'settings')
        row.value = {**row.value, 'rate_limit': 1}
        db.commit()
    assert verify(client).status_code == 200
    response = verify(client)
    assert response.status_code == 429
    assert int(response.headers['Retry-After']) > 0


def test_req17_dashboard_assets_and_verdict_contract(client):
    assert client.get('/').status_code == 200
    report = verify(client, 'The capital of France is Paris. The capital of Australia is Sydney. The Moon is made of cheese.').json()
    assert report['counts'] == {'Supported': 1, 'Contradicted': 1, 'Unsupported': 1, 'Not-Checkable': 0}
    assert all(c['text'] == report['original_text'][c['start']:c['end']] for c in report['claims'])


def test_req18_override_audit_and_approval(client):
    job = verify(client).json()
    claim = job['claims'][0]
    login(client, 'reviewer')
    response = client.post(f"/api/jobs/{job['job_id']}/claims/{claim['claim_id']}/override", json={'verdict': 'Unsupported', 'confidence_score': .2, 'reason': 'Source needs further review'})
    assert response.status_code == 200
    overridden = response.json()['claims'][0]
    assert overridden['automated_verdict'] == 'Supported'
    assert overridden['verdict'] == 'Unsupported'
    assert overridden['override']['reviewer'] == 'reviewer'
    assert overridden['override']['timestamp']
    with client.app.state.sessions() as db:
        audit = db.scalar(select(Audit).where(Audit.action == 'verdict_override'))
        assert audit.details['before']['verdict'] == 'Supported'
        assert audit.details['after']['verdict'] == 'Unsupported'
    approved = client.post(f"/api/jobs/{job['job_id']}/approve").json()
    assert approved['approved_by'] == 'reviewer'
    assert client.get('/api/settings').status_code == 403


def test_req19_analytics_filters_and_effective_verdicts(client):
    job = verify(client).json()
    login(client, 'reviewer')
    assert client.get('/api/analytics?source_app_id=missing').json()['total_jobs'] == 0
    assert client.get('/api/analytics?start=2100-01-01').json()['total_jobs'] == 0
    assert client.get('/api/analytics?key_id=missing').json()['total_jobs'] == 0
    client.post(f"/api/jobs/{job['job_id']}/claims/{job['claims'][0]['claim_id']}/override", json={'verdict': 'Unsupported', 'confidence_score': .1, 'reason': 'Uncertain evidence'})
    data = client.get('/api/analytics').json()
    assert data['hallucination_rate'] == 1
    assert data['override_count'] == 1
    assert data['reports'][0]['reviewers'] == ['reviewer']


def test_cache_reuse_and_threshold_recalculation(client):
    assert not verify(client).json()['claims'][0]['cached']
    before = time.monotonic()
    cached = verify(client, confidence_threshold=.99).json()['claims'][0]
    assert cached['cached'] and cached['flagged']
    assert time.monotonic() - before < .5


def test_sessions_csrf_and_admin_configuration(client):
    login(client)
    settings = client.get('/api/settings').json()
    del client.headers['X-CSRF-Token']
    assert client.put('/api/settings', json=settings).status_code == 403
    token = client.get('/api/session').json()['csrf']
    client.headers['X-CSRF-Token'] = token
    settings['confidence_threshold'] = .75
    assert client.put('/api/settings', json=settings).status_code == 200
    assert client.get('/api/audit').json()[0]['action'] == 'settings_changed'


def test_key_create_revocation_and_developer_isolation(client):
    job = verify(client).json()
    login(client)
    key = client.post('/api/keys', json={'name': 'another-app'}).json()
    headers = {'Authorization': 'Bearer ' + key['key']}
    assert client.get('/api/jobs', headers=headers).json() == []
    assert client.get('/api/jobs/' + job['job_id'], headers=headers).status_code == 404
    assert client.get('/api/settings', headers=headers).status_code == 403
    assert client.delete('/api/keys/' + key['id']).status_code == 200
    assert client.get('/api/jobs', headers=headers).status_code == 401


def test_invalid_llm_offsets_fall_back(monkeypatch):
    monkeypatch.setenv('DAM_LLM_URL', 'https://example.test/chat/completions')
    async def post(self, *args, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', args[0]), json={'choices': [{'message': {'content': '{"claims":[{"start":0,"end":9999}]}'}}]})
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    claims, mode = asyncio.run(extract('Earth orbits the Sun.'))
    assert mode.startswith('rule-based') and len(claims) == 1


def test_live_adapters_with_mocked_official_responses():
    def handler(request):
        if request.url.host == 'query.wikidata.org':
            return httpx.Response(200, json={'results': {'bindings': [{'valueLabel': {'value': 'Paris'}}]}})
        return httpx.Response(200, json={'query': {'pages': {'1': {'pageid': 1, 'extract': 'Earth orbits the Sun.'}}}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            graph = await WikidataSource(True).query('The capital of France is London.', client)
            wiki = await WikipediaSource().query('Earth orbits the Sun.', client)
            return graph, wiki
    graph, wiki = asyncio.run(run())
    assert graph[0]['verdict'] == 'Contradicted'
    assert graph[0]['correction'] == 'The capital of France is Paris.'
    assert wiki[0]['verdict'] == 'Supported'


def test_source_error_isolation():
    class Broken:
        name = 'broken'
        async def query(self, text, client):
            raise httpx.ConnectError('unreachable')
    assert asyncio.run(lookup(Broken(), 'x', None, 1, 1))['status'] == 'unavailable'


@pytest.mark.parametrize('text', [
    'The capital of France is not London.',
    'The capital of France is Paris and its largest city.',
    'The capital of France is Paris, which is in Europe.',
    'The capital of France was Paris in 1900.',
])
def test_templates_do_not_guess_negation_or_qualified_claims(text):
    assert asyncio.run(CuratedSource().query(text, None)) == []
