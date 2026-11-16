"""US-03 (REQ-8): per-source deadlines and graceful degradation.

Acceptance criteria covered:
  1. An individual source lookup times out when its configured deadline is exceeded.
  2. Evidence from other sources is still returned when one source times out.
  3. The timed-out source is reported as unavailable without failing the whole request.
"""
import asyncio
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.dam import pipeline as pipeline_module
from backend.dam.main import create_app
from backend.dam.models import Config
from backend.dam.sources import CuratedSource, lookup

KEY = 'us03-test-key'


class Hanging:
    """Adapter that never answers within any realistic deadline."""
    name = 'wikidata'

    def __init__(self, *args):
        pass

    async def query(self, text, client):
        await asyncio.sleep(30)
        return []


class Exploding:
    name = 'wikidata'

    def __init__(self, *args):
        pass

    async def query(self, text, client):
        raise RuntimeError('adapter bug')


def make_client(tmp_path, monkeypatch, source_timeout=None):
    monkeypatch.setenv('DAM_API_KEY', KEY)
    monkeypatch.setenv('DAM_LIVE_SOURCES', 'false')
    monkeypatch.delenv('DAM_LLM_URL', raising=False)
    app = create_app('sqlite:///' + (tmp_path / 'us03.db').as_posix(), testing=True)
    if source_timeout is not None:
        with app.state.sessions() as db:
            row = db.get(Config, 'settings')
            row.value = {**row.value, 'source_timeout': source_timeout}
            db.commit()
    return TestClient(app)


def verify(client, text='The capital of France is Paris.'):
    return client.post('/verify', headers={'Authorization': 'Bearer ' + KEY},
                       json={'text': text, 'source_app_id': 'demo-app'})


# --- AC1: individual lookup deadline -------------------------------------------------------

def test_lookup_enforces_deadline_promptly():
    async def run():
        started = time.monotonic()
        result = await lookup(Hanging(), 'x', None, .05, 1)
        return result, time.monotonic() - started
    result, elapsed = asyncio.run(run())
    assert result == {'source': 'wikidata', 'status': 'timeout', 'evidence': []}
    assert elapsed < 2  # nowhere near the 30s the adapter wanted


def test_lookup_reports_httpx_timeout_as_timeout():
    class HttpTimeout:
        name = 'wikipedia'

        async def query(self, text, client):
            raise httpx.ReadTimeout('slow')
    assert asyncio.run(lookup(HttpTimeout(), 'x', None, 1, 1))['status'] == 'timeout'


@pytest.mark.parametrize('error', [RuntimeError('bug'), AttributeError('x'), OSError('socket'), ValueError('bad json')])
def test_lookup_converts_any_adapter_failure_to_unavailable(error):
    class Failing:
        name = 'wikidata'

        async def query(self, text, client):
            raise error
    assert asyncio.run(lookup(Failing(), 'x', None, 1, 1)) == {'source': 'wikidata', 'status': 'unavailable', 'evidence': []}


def test_lookup_does_not_swallow_cancellation():
    async def run():
        task = asyncio.ensure_future(lookup(Hanging(), 'x', None, 30, 1))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())


def test_configured_source_timeout_is_applied_to_pipeline(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, 'WikidataSource', Hanging)
    with make_client(tmp_path, monkeypatch, source_timeout=.2) as client:
        started = time.monotonic()
        response = verify(client)
        elapsed = time.monotonic() - started
    assert response.status_code == 200
    assert elapsed < 5
    statuses = {r['source']: r['status'] for r in response.json()['claims'][0]['source_results']}
    assert statuses['wikidata'] == 'timeout'


# --- AC2 + AC3: degradation through the full request ---------------------------------------

def test_one_source_times_out_other_source_still_supplies_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, 'WikidataSource', Hanging)
    with make_client(tmp_path, monkeypatch, source_timeout=.2) as client:
        response = verify(client)
    assert response.status_code == 200
    claim = response.json()['claims'][0]
    statuses = {r['source']: r['status'] for r in claim['source_results']}
    assert statuses == {'curated': 'ok', 'wikidata': 'timeout'}
    assert claim['verdict'] == 'Supported'
    assert [e['source'] for e in claim['evidence']] == ['curated']
    assert claim['evidence'][0]['url'].startswith('https://')


def test_timed_out_source_does_not_mask_contradiction_from_other_source(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, 'WikidataSource', Hanging)
    with make_client(tmp_path, monkeypatch, source_timeout=.2) as client:
        claim = verify(client, 'The capital of France is London.').json()['claims'][0]
    assert claim['verdict'] == 'Contradicted'
    assert any(r['status'] == 'timeout' for r in claim['source_results'])


def test_unexpected_adapter_exception_does_not_fail_request(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, 'WikidataSource', Exploding)
    with make_client(tmp_path, monkeypatch) as client:
        response = verify(client)
    assert response.status_code == 200
    claim = response.json()['claims'][0]
    statuses = {r['source']: r['status'] for r in claim['source_results']}
    assert statuses == {'curated': 'ok', 'wikidata': 'unavailable'}
    assert claim['verdict'] == 'Supported'


def test_all_sources_timing_out_yields_not_checkable_not_an_error(tmp_path, monkeypatch):
    class HangingCurated(Hanging):
        name = 'curated'
    monkeypatch.setattr(pipeline_module, 'CuratedSource', HangingCurated)
    monkeypatch.setattr(pipeline_module, 'WikidataSource', Hanging)
    with make_client(tmp_path, monkeypatch, source_timeout=.2) as client:
        response = verify(client)
    assert response.status_code == 200
    report = response.json()
    assert report['claims'][0]['verdict'] == 'Not-Checkable'
    assert {r['status'] for r in report['claims'][0]['source_results']} == {'timeout'}


def test_sources_run_concurrently_not_sequentially(tmp_path, monkeypatch):
    class Slow(Hanging):
        async def query(self, text, client):
            await asyncio.sleep(.5)
            return []

    class SlowCurated(Slow):
        name = 'curated'
    monkeypatch.setattr(pipeline_module, 'CuratedSource', SlowCurated)
    monkeypatch.setattr(pipeline_module, 'WikidataSource', Slow)
    with make_client(tmp_path, monkeypatch, source_timeout=5) as client:
        started = time.monotonic()
        assert verify(client).status_code == 200
        elapsed = time.monotonic() - started
    assert elapsed < 0.95  # two 0.5s lookups overlap; sequential would be >= 1.0s


def test_failed_lookups_are_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, 'WikidataSource', Hanging)
    with make_client(tmp_path, monkeypatch, source_timeout=.2) as client:
        assert verify(client).json()['claims'][0]['cached'] is False
        assert verify(client).json()['claims'][0]['cached'] is False


def test_curated_lookup_still_works_alongside_timeout():
    async def run():
        async with httpx.AsyncClient() as client:
            return await asyncio.gather(lookup(Hanging(), 'x', client, .05, 1),
                                        lookup(CuratedSource(), 'Earth orbits the Sun.', client, .05, .8))
    slow, fast = asyncio.run(run())
    assert slow['status'] == 'timeout'
    assert fast['status'] == 'ok' and fast['evidence'][0]['trust_weight'] == .8
