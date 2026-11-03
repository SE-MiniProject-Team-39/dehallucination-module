from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.dam.models import ApiKey, Audit, Cache, Config, Job, User, database, now


class TestModelsAndDatabase:
    def test_now_format_is_utc_iso(self):
        timestamp = now()
        parsed = datetime.fromisoformat(timestamp)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0

    def test_database_creation_and_sessionmaker(self, tmp_path):
        db_path = tmp_path / "models_test.db"
        sessions = database(f"sqlite:///{db_path.as_posix()}")
        assert sessions is not None

        with sessions() as db:
            user = User(
                id="user-1",
                username="test-admin",
                password_hash="salt$digest",
                role="Administrator"
            )
            db.add(user)
            db.commit()

            fetched = db.get(User, "user-1")
            assert fetched is not None
            assert fetched.username == "test-admin"
            assert fetched.role == "Administrator"

    def test_user_unique_username_constraint(self, tmp_path):
        sessions = database(f"sqlite:///{(tmp_path / 'unique_user.db').as_posix()}")
        with sessions() as db:
            db.add(User(id="u1", username="duplicate", password_hash="hash1", role="Reviewer"))
            db.commit()

            db.add(User(id="u2", username="duplicate", password_hash="hash2", role="Developer"))
            with pytest.raises(IntegrityError):
                db.commit()

    def test_api_key_model_and_defaults(self, tmp_path):
        sessions = database(f"sqlite:///{(tmp_path / 'keys.db').as_posix()}")
        with sessions() as db:
            key = ApiKey(id="k1", name="app-1", key_hash="hash-key-1")
            db.add(key)
            db.commit()

            fetched = db.get(ApiKey, "k1")
            assert fetched.active is True  # default True
            assert fetched.name == "app-1"

    def test_job_model_and_json_report(self, tmp_path):
        sessions = database(f"sqlite:///{(tmp_path / 'jobs.db').as_posix()}")
        with sessions() as db:
            report_data = {
                "original_text": "Sample text",
                "claims": [{"claim_id": "c1", "text": "Sample text", "verdict": "Supported"}]
            }
            job = Job(
                id="j1",
                key_id=None,
                source_app_id="demo-app",
                text="Sample text",
                context="",
                threshold=0.5,
                report=report_data
            )
            db.add(job)
            db.commit()

            fetched = db.get(Job, "j1")
            assert fetched.id == "j1"
            assert fetched.report["original_text"] == "Sample text"
            assert fetched.created_at is not None
            assert fetched.approved_by is None

    def test_audit_model(self, tmp_path):
        sessions = database(f"sqlite:///{(tmp_path / 'audit.db').as_posix()}")
        with sessions() as db:
            audit = Audit(
                id="a1",
                actor="reviewer",
                action="verdict_override",
                details={"before": "Supported", "after": "Unsupported"}
            )
            db.add(audit)
            db.commit()

            fetched = db.get(Audit, "a1")
            assert fetched.actor == "reviewer"
            assert fetched.details["before"] == "Supported"
            assert fetched.created_at is not None

    def test_config_and_cache_models(self, tmp_path):
        sessions = database(f"sqlite:///{(tmp_path / 'config_cache.db').as_posix()}")
        with sessions() as db:
            db.add(Config(id="settings", value={"rate_limit": 60, "threshold": 0.5}))
            db.add(Cache(id="cache-sha", value=[{"source": "curated", "status": "ok"}]))
            db.commit()

            conf = db.get(Config, "settings")
            assert conf.value["rate_limit"] == 60

            cache_entry = db.get(Cache, "cache-sha")
            assert cache_entry.value[0]["source"] == "curated"
            assert cache_entry.created_at is not None
