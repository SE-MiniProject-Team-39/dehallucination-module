"""Isolated fixtures for Ashrit's core/extraction regression tests."""
import pytest
from fastapi.testclient import TestClient

from backend.dam.main import create_app


@pytest.fixture
def core_client(tmp_path, monkeypatch):
    for name in ('ADMIN', 'REVIEWER', 'DEVELOPER'):
        monkeypatch.setenv(f'DAM_{name}_PASSWORD', '')
    monkeypatch.setenv('DAM_API_KEY', 'ashrit-core-test-key')
    monkeypatch.setenv('DAM_SESSION_SECRET', 'isolated-core-test-session-secret')
    monkeypatch.setenv('DAM_LIVE_SOURCES', 'false')
    monkeypatch.delenv('DAM_LLM_URL', raising=False)
    app = create_app('sqlite:///' + (tmp_path / 'core.db').as_posix(), testing=True)
    with TestClient(app) as client:
        client.headers['Authorization'] = 'Bearer ashrit-core-test-key'
        yield client
