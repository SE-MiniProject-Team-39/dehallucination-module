from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.dam.models import ApiKey, Job, database


def job(key_id):
    return Job(id=str(uuid4()), key_id=key_id, source_app_id='test-app', text='Earth orbits the Sun.',
               context='', threshold=0.5, report={'claims': []})


def test_sqlite_rejects_nonexistent_api_key_reference(tmp_path):
    sessions = database('sqlite:///' + (tmp_path / 'orphan.db').as_posix())
    with sessions() as db:
        with pytest.raises(IntegrityError):
            with db.begin():
                db.add(job(str(uuid4())))


def test_sqlite_enables_constraints_for_new_connections(tmp_path):
    sessions = database('sqlite:///' + (tmp_path / 'connections.db').as_posix())
    engine = sessions.kw['bind']
    for _ in range(2):
        with engine.connect() as connection:
            assert connection.execute(text('PRAGMA foreign_keys')).scalar_one() == 1
        engine.dispose()


def test_sqlite_allows_valid_key_and_dashboard_jobs(tmp_path):
    sessions = database('sqlite:///' + (tmp_path / 'valid.db').as_posix())
    key_id = str(uuid4())
    with sessions() as db:
        db.add(ApiKey(id=key_id, name='test-app', key_hash='a' * 64))
        db.commit()
        linked, dashboard = job(key_id), job(None)
        db.add_all([linked, dashboard])
        db.commit()
        assert db.get(Job, linked.id).key_id == key_id
        assert db.get(Job, dashboard.id).key_id is None
