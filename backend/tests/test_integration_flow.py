import asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.dam.main import create_app
from backend.dam.models import ApiKey, Audit, Cache, Config, Job, now
from backend.dam.pipeline import Pipeline
from backend.dam.security import hash_key


@pytest.fixture
def app_and_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DAM_ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setenv("DAM_REVIEWER_PASSWORD", "test-reviewer-password")
    monkeypatch.setenv("DAM_DEVELOPER_PASSWORD", "test-dev-password")
    monkeypatch.setenv("DAM_API_KEY", "test-integrator-key")
    monkeypatch.setenv("DAM_LIVE_SOURCES", "false")
    monkeypatch.delenv("DAM_LLM_URL", raising=False)

    app = create_app("sqlite:///" + (tmp_path / "integration.db").as_posix(), testing=True)
    with TestClient(app) as client:
        yield app, client


def login_user(client, username="admin"):
    res = client.post("/api/login", json={"username": username, "password": f"test-{username}-password"})
    assert res.status_code == 200
    client.headers["X-CSRF-Token"] = res.json()["csrf"]
    return res.json()


class TestIntegrationReviewLifecycle:
    def test_complete_review_audit_and_analytics_flow(self, app_and_client):
        app, client = app_and_client

        # 1. Integrator submits verification request
        verify_res = client.post(
            "/verify",
            headers={"Authorization": "Bearer test-integrator-key"},
            json={
                "text": "The capital of France is Paris. The capital of Australia is Sydney.",
                "source_app_id": "demo-app",
                "context": "Geography exam"
            }
        )
        assert verify_res.status_code == 200
        job_data = verify_res.json()
        job_id = job_data["job_id"]
        assert len(job_data["claims"]) == 2
        claim_id = job_data["claims"][0]["claim_id"]

        # 2. Reviewer signs in
        login_user(client, "reviewer")

        # 3. Check /api/session
        session_info = client.get("/api/session").json()
        assert session_info["username"] == "reviewer"
        assert session_info["role"] == "Reviewer"

        # 4. Reviewer overrides claim verdict
        override_res = client.post(
            f"/api/jobs/{job_id}/claims/{claim_id}/override",
            json={
                "verdict": "Unsupported",
                "confidence_score": 0.15,
                "reason": "Source requires manual confirmation"
            }
        )
        assert override_res.status_code == 200
        overridden = override_res.json()
        claim_overridden = next(c for c in overridden["claims"] if c["claim_id"] == claim_id)
        assert claim_overridden["verdict"] == "Unsupported"
        assert claim_overridden["automated_verdict"] == "Supported"
        assert claim_overridden["override"]["reviewer"] == "reviewer"

        # 5. Reviewer approves job
        approve_res = client.post(f"/api/jobs/{job_id}/approve")
        assert approve_res.status_code == 200
        assert approve_res.json()["approved_by"] == "reviewer"

        # 6. Admin checks audit log
        login_user(client, "admin")
        audit_events = client.get("/api/audit").json()
        actions = [a["action"] for a in audit_events]
        assert "verdict_override" in actions
        assert "job_approved" in actions

        # 7. Reviewer checks analytics
        login_user(client, "reviewer")
        analytics = client.get("/api/analytics").json()
        assert analytics["total_jobs"] >= 1
        assert analytics["override_count"] >= 1
        assert len(analytics["timeline"]) >= 1
        assert "reviewer" in analytics["reports"][0]["reviewers"]

        # 8. Logout
        logout_res = client.post("/api/logout")
        assert logout_res.status_code == 200
        assert client.get("/api/session").status_code == 401


class TestIntegrationDeveloperIsolation:
    def test_key_creation_job_isolation_and_revocation(self, app_and_client):
        app, client = app_and_client

        # Admin logs in and creates a new developer key
        login_user(client, "admin")
        key_create_res = client.post("/api/keys", json={"name": "isolated-app"})
        assert key_create_res.status_code == 200
        new_key_info = key_create_res.json()
        dev_token = new_key_info["key"]
        dev_key_id = new_key_info["id"]

        # Verify key is listed in /api/keys
        keys_list = client.get("/api/keys").json()
        assert any(k["id"] == dev_key_id and k["active"] is True for k in keys_list)

        # Clear session headers to act purely as the developer API client
        client.headers.pop("X-CSRF-Token", None)
        client.cookies.clear()
        dev_headers = {"Authorization": f"Bearer {dev_token}"}

        # Developer submits a verification job
        dev_verify_res = client.post(
            "/verify",
            headers=dev_headers,
            json={"text": "France is in Europe.", "source_app_id": "isolated-app"}
        )
        assert dev_verify_res.status_code == 200
        dev_job_id = dev_verify_res.json()["job_id"]

        # Developer lists their jobs
        dev_jobs = client.get("/api/jobs", headers=dev_headers).json()
        assert len(dev_jobs) == 1
        assert dev_jobs[0]["job_id"] == dev_job_id

        # Developer cannot access administrative/reviewer routes
        assert client.get("/api/settings", headers=dev_headers).status_code == 403
        assert client.get("/api/audit", headers=dev_headers).status_code == 403
        assert client.get("/api/keys", headers=dev_headers).status_code == 403
        assert client.get("/api/analytics", headers=dev_headers).status_code == 403
        assert client.post(f"/api/jobs/{dev_job_id}/approve", headers=dev_headers).status_code == 403

        # Admin revokes key
        login_user(client, "admin")
        revoke_res = client.delete(f"/api/keys/{dev_key_id}")
        assert revoke_res.status_code == 200

        # Developer can no longer use the key
        client.headers.pop("X-CSRF-Token", None)
        client.cookies.clear()
        assert client.get("/api/jobs", headers=dev_headers).status_code == 401
        assert client.post(
            "/verify",
            headers=dev_headers,
            json={"text": "France is in Europe.", "source_app_id": "isolated-app"}
        ).status_code == 401


class TestIntegrationCacheLifecycle:
    def test_cache_expiration_and_failure_retry(self, app_and_client):
        app, client = app_and_client
        sessions = app.state.sessions

        # 1. Warm the cache by verifying a fact
        headers = {"Authorization": "Bearer test-integrator-key"}
        payload = {"text": "The capital of France is Paris.", "source_app_id": "demo-app"}

        res1 = client.post("/verify", headers=headers, json=payload)
        assert res1.status_code == 200
        assert res1.json()["claims"][0]["cached"] is False

        # 2. Immediate repeat is a cache hit
        res2 = client.post("/verify", headers=headers, json=payload)
        assert res2.status_code == 200
        assert res2.json()["claims"][0]["cached"] is True

        # 3. Simulate cache age > 86400 seconds (expired)
        with sessions() as db:
            caches = list(db.scalars(select(Cache)))
            assert len(caches) > 0
            for c in caches:
                # Set created_at to 2 days ago
                two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
                c.created_at = two_days_ago
            db.commit()

        # 4. Next request treats expired entry as cache miss and refetches
        res3 = client.post("/verify", headers=headers, json=payload)
        assert res3.status_code == 200
        assert res3.json()["claims"][0]["cached"] is False


class TestIntegrationRateLimitingAndHealth:
    def test_health_endpoint(self, app_and_client):
        _, client = app_and_client
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok", "mode": "offline snapshot"}

    def test_login_rate_limiting_brute_force_protection(self, app_and_client):
        _, client = app_and_client
        # 10 attempts allowed in 300s
        for _ in range(10):
            res = client.post("/api/login", json={"username": "admin", "password": "wrong-password"})
            assert res.status_code == 401

        # 11th attempt is rate limited
        blocked_res = client.post("/api/login", json={"username": "admin", "password": "wrong-password"})
        assert blocked_res.status_code == 429
        assert "Retry-After" in blocked_res.headers


class TestIntegrationLivePipelineSimulation:
    def test_live_pipeline_with_mock_external_endpoints(self, tmp_path, monkeypatch):
        # Enable live sources and mock LLM
        monkeypatch.setenv("DAM_LIVE_SOURCES", "true")
        monkeypatch.setenv("DAM_ADMIN_PASSWORD", "admin")
        monkeypatch.setenv("DAM_API_KEY", "live-key")

        def handler(request):
            url_str = str(request.url)
            if "wikidata.org/sparql" in url_str:
                return httpx.Response(200, json={"results": {"bindings": [{"valueLabel": {"value": "Paris"}}]}})
            elif "en.wikipedia.org" in url_str:
                return httpx.Response(200, json={
                    "query": {
                        "pages": {
                            "99": {"pageid": 99, "extract": "The capital of France is Paris."}
                        }
                    }
                })
            return httpx.Response(404)

        # Patch httpx.AsyncClient transport to intercept live calls
        orig_init = httpx.AsyncClient.__init__

        def mock_init(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            orig_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", mock_init)

        app = create_app("sqlite:///" + (tmp_path / "live_sim.db").as_posix(), testing=True)
        with TestClient(app) as client:
            health = client.get("/health").json()
            assert health["mode"] == "live"

            res = client.post(
                "/verify",
                headers={"Authorization": "Bearer live-key"},
                json={"text": "The capital of France is Paris.", "source_app_id": "demo-app"}
            )
            assert res.status_code == 200
            claim = res.json()["claims"][0]
            assert claim["verdict"] == "Supported"
            sources_queried = {s["source"] for s in claim["source_results"]}
            assert "wikidata" in sources_queried
            assert "wikipedia" in sources_queried
