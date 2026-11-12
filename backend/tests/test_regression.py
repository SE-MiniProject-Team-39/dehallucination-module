import asyncio
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.dam.main import create_app
from backend.dam.models import Config
from backend.dam.pipeline import score
from backend.dam.sources import evidence


@pytest.fixture
def app_and_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DAM_ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setenv("DAM_REVIEWER_PASSWORD", "test-reviewer-password")
    monkeypatch.setenv("DAM_API_KEY", "test-integrator-key")
    monkeypatch.setenv("DAM_LIVE_SOURCES", "false")
    monkeypatch.delenv("DAM_LLM_URL", raising=False)

    app = create_app("sqlite:///" + (tmp_path / "regression.db").as_posix(), testing=True)
    with TestClient(app) as client:
        yield app, client


def login(client, username="admin"):
    res = client.post("/api/login", json={"username": username, "password": f"test-{username}-password"})
    assert res.status_code == 200
    client.headers["X-CSRF-Token"] = res.json()["csrf"]


class TestBugRegressionPipeline:
    def test_regression_score_naive_datetime_unhandled_type_error(self):
        """
        REGRESSION BUG: pipeline.py:23 computes:
        (datetime.now(timezone.utc) - datetime.fromisoformat(item['observed_at'])).days
        If an adapter or custom evidence item contains an offset-naive datetime string
        (e.g., '2026-09-05T00:00:00'), Python raises TypeError: can't subtract offset-naive and offset-aware datetimes.
        This test documents and isolates this confirmed behavior.
        """
        naive_ev = evidence("test", "Fact", "urn:test", "Supported", observed_at="2026-09-05T00:00:00")
        with pytest.raises(TypeError, match="can't subtract offset-naive and offset-aware datetimes"):
            score([{"status": "ok", "evidence": [naive_ev]}], threshold=0.5)

    def test_regression_score_schema_consistency_missing_correction_label(self):
        """
        REGRESSION BUG: When evidence is empty, score() returns:
        {"verdict": ..., "confidence_score": ..., "flagged": ..., "evidence": [], "suggested_correction": None}
        Notice 'correction_label' is absent when evidence is empty, but present when evidence is non-empty.
        Code indexing claim['correction_label'] will raise KeyError unless using .get().
        """
        empty_res = score([], threshold=0.5)
        assert "suggested_correction" in empty_res
        assert empty_res.get("correction_label") is None
        # Confirms 'correction_label' key is missing from the dictionary returned on empty evidence
        assert "correction_label" not in empty_res

        # Conversely, with evidence, the key is always present
        now_iso = datetime.now(timezone.utc).isoformat()
        ev = evidence("test", "Fact", "urn:test", "Supported", observed_at=now_iso)
        ev["trust_weight"] = 1.0
        ev_res = score([{"status": "ok", "evidence": [ev]}], threshold=0.5)
        assert "correction_label" in ev_res


class TestBugRegressionApiFiltersAndErrors:
    def test_regression_jobs_filtering_by_q_status_max_confidence_and_end(self, app_and_client):
        """
        Regression: tests main.py jobs query filters: q, status, max_confidence, and end date.
        """
        _, client = app_and_client
        login(client, "reviewer")

        # Submit jobs with different texts and verdicts
        # Job 1: Supported (Paris)
        j1 = client.post(
            "/verify",
            headers={"Authorization": "Bearer test-integrator-key"},
            json={"text": "The capital of France is Paris.", "source_app_id": "demo-app"}
        ).json()

        # Job 2: Contradicted (Australia is Sydney)
        j2 = client.post(
            "/verify",
            headers={"Authorization": "Bearer test-integrator-key"},
            json={"text": "The capital of Australia is Sydney.", "source_app_id": "demo-app"}
        ).json()

        # Job 3: Unsupported (Moon is made of cheese)
        j3 = client.post(
            "/verify",
            headers={"Authorization": "Bearer test-integrator-key"},
            json={"text": "The Moon is made of cheese.", "source_app_id": "demo-app"}
        ).json()

        # Filter by text query q (case-insensitive substring)
        q_france = client.get("/api/jobs?q=france").json()
        assert len(q_france) == 1
        assert q_france[0]["job_id"] == j1["job_id"]

        q_none = client.get("/api/jobs?q=nonexistent-query-text").json()
        assert len(q_none) == 0

        # Filter by status
        status_contra = client.get("/api/jobs?status=Contradicted").json()
        assert len(status_contra) == 1
        assert status_contra[0]["job_id"] == j2["job_id"]

        status_unsupp = client.get("/api/jobs?status=Unsupported").json()
        assert len(status_unsupp) == 1
        assert status_unsupp[0]["job_id"] == j3["job_id"]

        # Filter by max_confidence
        # Supported has confidence 1.0; Contradicted has confidence 0.0, Unsupported has 0.0
        low_conf = client.get("/api/jobs?max_confidence=0.1").json()
        assert len(low_conf) == 2  # Australia and Moon jobs

        # Filter by past end date excludes all
        past_end = client.get("/api/jobs?end=2020-01-01").json()
        assert len(past_end) == 0

        # Filter by future end date includes all
        future_end = client.get("/api/jobs?end=2099-12-31").json()
        assert len(future_end) >= 3

    def test_regression_override_claim_not_found_returns_404(self, app_and_client):
        _, client = app_and_client
        login(client, "reviewer")

        j = client.post(
            "/verify",
            headers={"Authorization": "Bearer test-integrator-key"},
            json={"text": "The capital of France is Paris.", "source_app_id": "demo-app"}
        ).json()

        res = client.post(
            f"/api/jobs/{j['job_id']}/claims/non-existent-claim-id/override",
            json={"verdict": "Unsupported", "confidence_score": 0.1, "reason": "Testing 404"}
        )
        assert res.status_code == 404
        assert res.json()["error"]["message"] == "Claim not found"

    def test_regression_revoke_non_existent_key_returns_404(self, app_and_client):
        _, client = app_and_client
        login(client, "admin")

        res = client.delete("/api/keys/non-existent-key-uuid")
        assert res.status_code == 404
        assert res.json()["error"]["message"] == "API key not found"

    def test_regression_settings_put_incomplete_sources_returns_422(self, app_and_client):
        _, client = app_and_client
        login(client, "admin")

        # Config only has 'curated' and 'wikidata', missing 'wikipedia'
        incomplete_payload = {
            "confidence_threshold": 0.5,
            "source_timeout": 3,
            "request_timeout": 10,
            "rate_limit": 60,
            "sources": {
                "curated": {"enabled": True, "weight": 1.0},
                "wikidata": {"enabled": True, "weight": 1.0}
            }
        }
        res = client.put("/api/settings", json=incomplete_payload)
        assert res.status_code == 422
        assert "Configure all three source adapters" in res.json()["error"]["message"]

    def test_regression_csrf_mismatched_token_returns_403(self, app_and_client):
        _, client = app_and_client
        login(client, "admin")

        # Explicitly supply a mismatched token
        client.headers["X-CSRF-Token"] = "completely-wrong-token"
        res = client.put(
            "/api/settings",
            json={
                "confidence_threshold": 0.5,
                "source_timeout": 3,
                "request_timeout": 10,
                "rate_limit": 60,
                "sources": {
                    "curated": {"enabled": True, "weight": 1.0},
                    "wikidata": {"enabled": True, "weight": 1.0},
                    "wikipedia": {"enabled": True, "weight": 1.0}
                }
            }
        )
        assert res.status_code == 403
        assert res.json()["error"]["message"] == "Invalid CSRF token"

    def test_regression_request_timeout_deadline_exceeded_fallback(self, app_and_client, monkeypatch):
        app, client = app_and_client

        # Configure request_timeout to 0.05s in DB settings
        sessions = app.state.sessions
        with sessions() as db:
            conf = db.get(Config, "settings")
            conf.value = {**conf.value, "request_timeout": 0.05}
            db.commit()

        # Make pipeline take longer than request_timeout
        async def slow_run(*args, **kwargs):
            await asyncio.sleep(0.5)

        monkeypatch.setattr(app.state.sessions, "slow", True, raising=False)
        from backend.dam.pipeline import Pipeline
        monkeypatch.setattr(Pipeline, "run", slow_run)

        res = client.post(
            "/verify",
            headers={"Authorization": "Bearer test-integrator-key"},
            json={"text": "France is in Europe.", "source_app_id": "demo-app"}
        )
        assert res.status_code == 200
        report = res.json()
        assert report["extractor"] == "rule-based (request timeout)"
        assert len(report["claims"]) == 1
        claim = report["claims"][0]
        assert claim["verdict"] == "Not-Checkable"
        assert claim["confidence_score"] == 0.0
        assert claim["reason"] == "Request deadline exceeded"

    def test_regression_create_app_requires_secret_in_production(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DAM_SESSION_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="Run python manage.py init, or set DAM_SESSION_SECRET"):
            create_app("sqlite:///" + (tmp_path / "prod.db").as_posix(), testing=False)

    def test_regression_throttle_eviction_after_period(self, app_and_client, monkeypatch):
        _, client = app_and_client
        import time
        orig_monotonic = time.monotonic

        # Advance monotonic clock by 61 seconds on subsequent call to trigger bucket.popleft()
        current_time = orig_monotonic()
        def mock_monotonic():
            nonlocal current_time
            t = current_time
            current_time += 65.0
            return t

        monkeypatch.setattr(time, "monotonic", mock_monotonic)
        res1 = client.get("/health")
        assert res1.status_code == 200
        # Call a throttled endpoint twice to exercise bucket eviction
        login(client, "admin")
        res2 = client.get("/api/settings")
        assert res2.status_code == 200
