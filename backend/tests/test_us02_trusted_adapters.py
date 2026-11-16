"""US-02 (REQ-5, REQ-6, REQ-7): trusted graph and text adapters.

Acceptance criteria covered:
  1. The configured knowledge-graph source and the curated corpus are queried for each eligible claim.
  2. All four verdicts (Supported, Contradicted, Unsupported, Not-Checkable) can be returned.
  3. Every Supported or Contradicted claim carries a source citation.

Offline mode uses a bundled Wikidata *snapshot*; only DAM_LIVE_SOURCES=true performs network queries.
"""
import httpx
import pytest
from fastapi.testclient import TestClient

from backend.dam import pipeline as pipeline_module
from backend.dam.main import create_app

KEY = 'us02-test-key'


def make_client(tmp_path, monkeypatch, live=False):
    monkeypatch.setenv('DAM_API_KEY', KEY)
    monkeypatch.setenv('DAM_LIVE_SOURCES', 'true' if live else 'false')
    monkeypatch.delenv('DAM_LLM_URL', raising=False)
    app = create_app('sqlite:///' + (tmp_path / 'us02.db').as_posix(), testing=True)
    return TestClient(app)


def verify(client, text):
    response = client.post('/verify', headers={'Authorization': 'Bearer ' + KEY},
                           json={'text': text, 'source_app_id': 'demo-app'})
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def offline(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        yield client


def test_offline_mode_queries_graph_snapshot_and_curated_corpus_per_claim(offline):
    report = verify(offline, 'The capital of France is Paris. Earth orbits the Sun.')
    assert report['mode'] == 'offline snapshot'
    assert len(report['claims']) == 2
    for claim in report['claims']:
        assert {r['source'] for r in claim['source_results']} == {'curated', 'wikidata'}
        assert all(r['status'] == 'ok' for r in claim['source_results'])


def test_offline_mode_makes_no_network_calls_and_marks_snapshot(tmp_path, monkeypatch):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(500)

    original = httpx.AsyncClient.__init__

    def patched(self, *args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(handler)
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, '__init__', patched)
    with make_client(tmp_path, monkeypatch) as client:
        claim = verify(client, 'The capital of France is Paris.')['claims'][0]
    assert calls == []  # offline mode must not claim, or perform, live graph queries
    graph = [e for e in claim['evidence'] if e['source'] == 'wikidata']
    assert graph and all(e.get('snapshot') is True for e in graph)


def test_live_mode_issues_sparql_query_and_wikipedia_search(tmp_path, monkeypatch):
    seen = []

    def handler(request):
        seen.append(request.url.host)
        if request.url.host == 'query.wikidata.org':
            return httpx.Response(200, json={'results': {'bindings': [{'valueLabel': {'value': 'Paris'}}]}})
        return httpx.Response(200, json={'query': {'pages': {}}})

    original = httpx.AsyncClient.__init__

    def patched(self, *args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(handler)
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, '__init__', patched)
    with make_client(tmp_path, monkeypatch, live=True) as client:
        report = verify(client, 'The capital of France is Paris.')
    assert report['mode'] == 'live'
    assert 'query.wikidata.org' in seen and 'en.wikipedia.org' in seen
    claim = report['claims'][0]
    assert claim['verdict'] == 'Supported'
    live_graph = [e for e in claim['evidence'] if e['source'] == 'wikidata']
    assert live_graph and not any(e.get('snapshot') for e in live_graph)


@pytest.mark.parametrize('text,verdict', [
    ('The capital of France is Paris.', 'Supported'),
    ('The capital of France is London.', 'Contradicted'),
    ('The Moon is made of cheese.', 'Unsupported'),
])
def test_verdicts_via_api(offline, text, verdict):
    assert verify(offline, text)['claims'][0]['verdict'] == verdict


def test_not_checkable_when_every_source_is_unavailable(tmp_path, monkeypatch):
    class Down:
        def __init__(self, *args):
            pass

        name = 'curated'

        async def query(self, text, client):
            raise httpx.ConnectError('unreachable')

    class AlsoDown(Down):
        name = 'wikidata'

    monkeypatch.setattr(pipeline_module, 'CuratedSource', Down)
    monkeypatch.setattr(pipeline_module, 'WikidataSource', AlsoDown)
    with make_client(tmp_path, monkeypatch) as client:
        report = verify(client, 'The capital of France is Paris.')
    claim = report['claims'][0]
    assert claim['verdict'] == 'Not-Checkable'
    assert claim['evidence'] == []
    assert {r['status'] for r in claim['source_results']} == {'unavailable'}
    assert report['counts']['Not-Checkable'] == 1


def test_all_four_verdicts_in_one_report_counts(tmp_path, monkeypatch):
    # Unsupported / Supported / Contradicted come from real adapters; Not-Checkable needs a
    # failing source, so verify the count contract using a source that fails only for one claim.
    class Flaky:
        def __init__(self, *args):
            pass

        name = 'wikidata'

        async def query(self, text, client):
            if 'Moon' in text:
                raise httpx.ConnectError('unreachable')
            return []

    monkeypatch.setattr(pipeline_module, 'WikidataSource', Flaky)
    with make_client(tmp_path, monkeypatch) as client:
        report = verify(client, 'The capital of France is Paris. The capital of France is London. '
                                'Earth is round. The Moon is made of cheese.')
    verdicts = {c['text']: c['verdict'] for c in report['claims']}
    assert verdicts['The capital of France is Paris.'] == 'Supported'
    assert verdicts['The capital of France is London.'] == 'Contradicted'
    assert verdicts['Earth is round.'] == 'Unsupported'
    assert verdicts['The Moon is made of cheese.'] == 'Not-Checkable'
    assert report['counts'] == {'Supported': 1, 'Contradicted': 1, 'Unsupported': 1, 'Not-Checkable': 1}


@pytest.mark.parametrize('text', [
    'The capital of France is Paris.',
    'The capital of India is New Delhi.',
    'The capital of France is London.',
    'The capital of Australia is Sydney.',
    'Earth orbits the Sun.',
    'Hamlet was written by Charles Dickens.',
    'Hamlet was written by William Shakespeare.',
])
def test_supported_and_contradicted_claims_cite_a_source(offline, text):
    claim = verify(offline, text)['claims'][0]
    assert claim['verdict'] in {'Supported', 'Contradicted'}, claim['verdict']
    assert claim['evidence']
    for item in claim['evidence']:
        assert item['source'] in {'curated', 'wikidata', 'wikipedia'}
        assert item['url'].startswith('https://')
        assert item['snippet'].strip()


def test_unsupported_claims_have_no_fabricated_citation(offline):
    claim = verify(offline, 'The Moon is made of cheese.')['claims'][0]
    assert claim['verdict'] == 'Unsupported'
    assert claim['evidence'] == []
