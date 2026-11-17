import pytest

from backend.dam.models import Config
from backend.dam.pipeline import Pipeline


@pytest.mark.parametrize('request_threshold,default_threshold,expected_flag', [
    (0.0, 0.5, False), (0.5, 0.5, True), (None, 0.0, False), (None, 0.5, True)
])
def test_request_timeout_respects_effective_threshold(
    core_client, monkeypatch, request_threshold, default_threshold, expected_flag
):
    async def timed_out(self, *args, **kwargs):
        raise TimeoutError('Simulated request deadline')

    monkeypatch.setattr(Pipeline, 'run', timed_out)
    with core_client.app.state.sessions() as db:
        settings = db.get(Config, 'settings')
        settings.value = {**settings.value, 'confidence_threshold': default_threshold}
        db.commit()
    text = '  Earth orbits the Sun.\n'
    payload = {'text': text, 'source_app_id': 'demo-app'}
    if request_threshold is not None:
        payload['confidence_threshold'] = request_threshold
    response = core_client.post('/verify', json=payload)
    assert response.status_code == 200
    report = response.json()
    claim = report['claims'][0]
    assert claim['verdict'] == 'Not-Checkable'
    assert claim['confidence_score'] == 0
    assert claim['flagged'] is expected_flag
    assert report['hallucination_score'] == (1.0 if expected_flag else 0.0)
    assert report['original_text'] == text
    assert text[claim['start']:claim['end']] == claim['text']
    saved = core_client.get('/api/jobs/' + report['job_id'])
    assert saved.status_code == 200
    assert saved.json()['claims'][0]['flagged'] is expected_flag
