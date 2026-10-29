import asyncio
import copy
import os
import secrets
import time
from collections import defaultdict, deque
from datetime import date
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from .models import ApiKey, Audit, Config, Job, User, database, now
from .pipeline import Pipeline, summarize
from .security import check_password, hash_key, hash_password

load_dotenv()
Verdict = Literal['Supported', 'Contradicted', 'Unsupported', 'Not-Checkable']
bearer = HTTPBearer(auto_error=False)


class VerifyInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=10000)
    source_app_id: str = Field(min_length=1, max_length=64)
    context: str = Field(default='', max_length=2000)
    confidence_threshold: float | None = Field(default=None, ge=0, le=1)


class LoginInput(BaseModel):
    username: str = Field(max_length=80)
    password: str = Field(max_length=256)


class OverrideInput(BaseModel):
    verdict: Verdict
    confidence_score: float = Field(ge=0, le=1)
    reason: str = Field(min_length=5, max_length=1000)


class SourceConfig(BaseModel):
    enabled: bool = True
    weight: float = Field(default=1, gt=0, le=1)


class SettingsInput(BaseModel):
    confidence_threshold: float = Field(default=0.5, ge=0, le=1)
    source_timeout: float = Field(default=5, ge=0.1, le=5)
    request_timeout: float = Field(default=15, ge=1, le=30)
    rate_limit: int = Field(default=60, ge=1, le=1000)
    sources: dict[Literal['curated', 'wikidata', 'wikipedia'], SourceConfig]


class KeyInput(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')


def create_app(db_url=None, testing=False):
    sessions = database(db_url)
    secret = os.getenv('DAM_SESSION_SECRET')
    if not secret:
        if not testing:
            raise RuntimeError('Run python manage.py init, or set DAM_SESSION_SECRET and bootstrap credentials before starting.')
        secret = secrets.token_hex(32)
    app = FastAPI(title='DAM · Dehallucination API', version='1.0.0', description='English factual-claim review service. API clients use bearer keys; dashboard users use CSRF-protected sessions. Offline mode has deliberately limited coverage.')
    app.add_middleware(SessionMiddleware, secret_key=secret, same_site='strict', https_only=os.getenv('DAM_SECURE_COOKIES') == 'true', max_age=28800)
    app.state.sessions = sessions
    live = os.getenv('DAM_LIVE_SOURCES', 'false').lower() == 'true'
    pipeline = Pipeline(sessions, live)
    requests = defaultdict(deque)
    login_attempts = defaultdict(deque)

    with sessions() as db:
        if not db.get(Config, 'settings'):
            db.add(Config(id='settings', value=SettingsInput(sources={name: SourceConfig() for name in ['curated', 'wikidata', 'wikipedia']}).model_dump()))
        for username, role in [('admin', 'Administrator'), ('reviewer', 'Reviewer'), ('developer', 'Developer')]:
            password = os.getenv(f'DAM_{username.upper()}_PASSWORD')
            if password and not db.scalar(select(User).where(User.username == username)):
                db.add(User(id=str(uuid4()), username=username, role=role, password_hash=hash_password(password)))
        key = os.getenv('DAM_API_KEY')
        if key and not db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(key))):
            db.add(ApiKey(id=str(uuid4()), name='demo-app', key_hash=hash_key(key)))
        db.commit()

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return JSONResponse(status_code=error.status_code, content={'error': {'code': str(error.status_code), 'message': error.detail}}, headers=error.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        messages = ['.'.join(str(x) for x in item['loc']) + ': ' + item['msg'] for item in error.errors()]
        return JSONResponse(status_code=422, content={'error': {'code': 'VALIDATION_ERROR', 'message': '; '.join(messages)}})

    @app.middleware('http')
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if request.url.path.startswith('/api') or request.url.path == '/verify':
            response.headers['Cache-Control'] = 'no-store'
        return response

    def settings():
        with sessions() as db:
            return db.get(Config, 'settings').value

    def audit(db, actor, action, details):
        db.add(Audit(id=str(uuid4()), actor=actor, action=action, details=details))

    def throttle(bucket, limit, period=60):
        current = time.monotonic()
        while bucket and current - bucket[0] >= period:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, 'Rate limit exceeded', headers={'Retry-After': str(max(1, int(period - (current - bucket[0])) + 1))})
        bucket.append(current)

    async def identity(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials:
            with sessions() as db:
                key = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(credentials.credentials), ApiKey.active.is_(True)))
                if key:
                    throttle(requests[key.id], settings()['rate_limit'])
                    return {'role': 'Developer', 'username': key.name, 'key_id': key.id, 'app_id': key.name}
            raise HTTPException(401, 'Invalid or revoked API key')
        user_id = request.session.get('user_id')
        with sessions() as db:
            user = db.get(User, user_id) if user_id else None
            if not user:
                raise HTTPException(401, 'Authentication required')
            if request.method not in ['GET', 'HEAD', 'OPTIONS']:
                token = request.headers.get('X-CSRF-Token', '')
                if not token or not secrets.compare_digest(token, request.session.get('csrf', '')):
                    raise HTTPException(403, 'Invalid CSRF token')
            throttle(requests['session:' + user.id], settings()['rate_limit'])
            return {'role': user.role, 'username': user.username, 'key_id': None}

    def staff(user):
        if user['role'] not in ['Administrator', 'Reviewer']:
            raise HTTPException(403, 'Reviewer access required')

    def admin(user):
        if user['role'] != 'Administrator':
            raise HTTPException(403, 'Administrator access required')

    def job_view(job):
        return {**job.report, 'job_id': job.id, 'created_at': job.created_at, 'source_app_id': job.source_app_id,
                'key_id': job.key_id, 'approved_by': job.approved_by}

    def owned_job(db, job_id, user):
        job = db.get(Job, job_id)
        if not job or (user['role'] == 'Developer' and job.key_id != user['key_id']):
            raise HTTPException(404, 'Verification job not found')
        return job

    @app.get('/health', tags=['Operations'])
    def health():
        return {'status': 'ok', 'mode': 'live' if live else 'offline snapshot'}

    @app.post('/api/login', tags=['Session'])
    async def login(data: LoginInput, request: Request):
        throttle(login_attempts[request.client.host if request.client else 'unknown'], 10, 300)
        with sessions() as db:
            user = db.scalar(select(User).where(User.username == data.username))
            if not user or not check_password(data.password, user.password_hash):
                raise HTTPException(401, 'Invalid username or password')
            request.session.clear()
            request.session.update({'user_id': user.id, 'csrf': secrets.token_hex(24)})
            return {'username': user.username, 'role': user.role, 'csrf': request.session['csrf']}

    @app.get('/api/session', tags=['Session'])
    async def session(request: Request, user=Depends(identity)):
        return {**user, 'csrf': request.session.get('csrf'), 'mode': 'live' if live else 'offline snapshot'}

    @app.post('/api/logout', tags=['Session'])
    async def logout(request: Request, user=Depends(identity)):
        request.session.clear()
        return {'ok': True}

    @app.post('/verify', tags=['Verification'])
    @app.post('/api/verify', tags=['Verification'])
    async def verify(data: VerifyInput, user=Depends(identity)):
        if user.get('app_id') and data.source_app_id != user['app_id']:
            raise HTTPException(403, 'source_app_id must match your API key application name')
        config = settings()
        threshold = data.confidence_threshold if data.confidence_threshold is not None else config['confidence_threshold']
        try:
            report = await asyncio.wait_for(pipeline.run(data.text, data.context, config, threshold), timeout=config['request_timeout'])
        except TimeoutError:
            from .extraction import fallback_extract
            report = summarize({'original_text': data.text, 'extractor': 'rule-based (request timeout)', 'mode': 'live' if live else 'offline snapshot', 'confidence_threshold': threshold,
                'claims': [{**c, 'claim_id': str(uuid4()), 'verdict': 'Not-Checkable', 'confidence_score': 0.0, 'flagged': True,
                            'evidence': [], 'source_results': [], 'cached': False, 'suggested_correction': None, 'reason': 'Request deadline exceeded'} for c in fallback_extract(data.text)]})
        for claim in report['claims']:
            claim['automated_verdict'] = claim['verdict']
            claim['automated_confidence_score'] = claim['confidence_score']
        with sessions() as db:
            job = Job(id=str(uuid4()), key_id=user['key_id'], source_app_id=data.source_app_id, text=data.text, context=data.context, threshold=threshold, report=report)
            db.add(job)
            db.commit()
            return job_view(job)

    @app.get('/api/jobs', tags=['Review'])
    async def jobs(q: str = '', status: Verdict | None = None, start: date | None = None, end: date | None = None,
                   source_app_id: str | None = None, max_confidence: float = 1, key_id: str | None = None, user=Depends(identity)):
        with sessions() as db:
            query = select(Job).order_by(Job.created_at.desc())
            if user['role'] == 'Developer':
                query = query.where(Job.key_id == user['key_id'])
            if start:
                query = query.where(Job.created_at >= start.isoformat())
            if end:
                query = query.where(Job.created_at < end.isoformat() + 'T23:59:59.999999Z')
            if source_app_id:
                query = query.where(Job.source_app_id == source_app_id)
            if key_id:
                query = query.where(Job.key_id == key_id)
            result = []
            for job in db.scalars(query):
                if q.casefold() not in job.text.casefold():
                    continue
                if status and not any(c['verdict'] == status for c in job.report['claims']):
                    continue
                if max_confidence < 1 and not any(c['confidence_score'] <= max_confidence for c in job.report['claims']):
                    continue
                result.append(job_view(job))
            return result

    @app.get('/api/jobs/{job_id}', tags=['Review'])
    async def get_job(job_id: str, user=Depends(identity)):
        with sessions() as db:
            return job_view(owned_job(db, job_id, user))

    @app.post('/api/jobs/{job_id}/claims/{claim_id}/override', tags=['Review'])
    async def override(job_id: str, claim_id: str, data: OverrideInput, user=Depends(identity)):
        staff(user)
        with sessions() as db:
            job = owned_job(db, job_id, user)
            report = copy.deepcopy(job.report)
            claim = next((c for c in report['claims'] if c['claim_id'] == claim_id), None)
            if not claim:
                raise HTTPException(404, 'Claim not found')
            previous = copy.deepcopy(claim)
            claim.update({'verdict': data.verdict, 'confidence_score': data.confidence_score,
                          'flagged': data.confidence_score < job.threshold,
                          'override': {'reviewer': user['username'], 'timestamp': now(), 'reason': data.reason}})
            job.report = summarize(report)
            job.approved_by = None
            audit(db, user['username'], 'verdict_override', {'job_id': job_id, 'claim_id': claim_id, 'before': previous, 'after': claim})
            db.commit()
            return job_view(job)

    @app.post('/api/jobs/{job_id}/approve', tags=['Review'])
    async def approve(job_id: str, user=Depends(identity)):
        staff(user)
        with sessions() as db:
            job = owned_job(db, job_id, user)
            job.approved_by = user['username']
            audit(db, user['username'], 'job_approved', {'job_id': job_id})
            db.commit()
            return job_view(job)

    @app.get('/api/analytics', tags=['Analytics'])
    async def analytics(start: date | None = None, end: date | None = None, source_app_id: str | None = None,
                        key_id: str | None = None, user=Depends(identity)):
        staff(user)
        rows = await jobs(start=start, end=end, source_app_id=source_app_id, key_id=key_id, user=user)
        by_day = defaultdict(list)
        for row in rows:
            by_day[row['created_at'][:10]].append(row)
        claims = [c for row in rows for c in row['claims']]
        return {'total_jobs': len(rows), 'total_claims': len(claims), 'flagged_claims': sum(c['flagged'] for c in claims),
                'override_count': sum('override' in c for c in claims),
                'hallucination_rate': sum(c['flagged'] for c in claims) / len(claims) if claims else 0,
                'timeline': [{'date': day, 'jobs': len(items), 'hallucination_score': sum(j['hallucination_score'] for j in items) / len(items)} for day, items in sorted(by_day.items())],
                'reports': [{k: v for k, v in row.items() if k not in ['original_text', 'claims']} | {'total_claims': len(row['claims']), 'override_count': sum('override' in c for c in row['claims']), 'reviewers': sorted({c['override']['reviewer'] for c in row['claims'] if 'override' in c})} for row in rows]}

    @app.get('/api/settings', tags=['Administration'])
    async def get_settings(user=Depends(identity)):
        admin(user)
        return settings()

    @app.put('/api/settings', tags=['Administration'])
    async def update_settings(data: SettingsInput, user=Depends(identity)):
        admin(user)
        config = data.model_dump()
        if set(config['sources']) != {'curated', 'wikidata', 'wikipedia'}:
            raise HTTPException(422, 'Configure all three source adapters')
        with sessions() as db:
            row = db.get(Config, 'settings')
            audit(db, user['username'], 'settings_changed', {'before': row.value, 'after': config})
            row.value = config
            db.commit()
        return config

    @app.get('/api/keys', tags=['Administration'])
    async def keys(user=Depends(identity)):
        admin(user)
        with sessions() as db:
            return [{'id': k.id, 'name': k.name, 'active': k.active} for k in db.scalars(select(ApiKey))]

    @app.post('/api/keys', tags=['Administration'])
    async def create_key(data: KeyInput, user=Depends(identity)):
        admin(user)
        raw = secrets.token_urlsafe(32)
        with sessions() as db:
            key = ApiKey(id=str(uuid4()), name=data.name, key_hash=hash_key(raw))
            db.add(key)
            audit(db, user['username'], 'key_created', {'key_id': key.id, 'name': data.name})
            db.commit()
            return {'id': key.id, 'name': key.name, 'key': raw, 'message': 'Save this key; it will not be shown again.'}

    @app.delete('/api/keys/{key_id}', tags=['Administration'])
    async def revoke_key(key_id: str, user=Depends(identity)):
        admin(user)
        with sessions() as db:
            key = db.get(ApiKey, key_id)
            if not key:
                raise HTTPException(404, 'API key not found')
            key.active = False
            audit(db, user['username'], 'key_revoked', {'key_id': key_id})
            db.commit()
            return {'ok': True}

    @app.get('/api/audit', tags=['Administration'])
    async def audit_log(user=Depends(identity)):
        admin(user)
        with sessions() as db:
            return [{'id': row.id, 'actor': row.actor, 'action': row.action, 'created_at': row.created_at, 'details': row.details} for row in db.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(500))]

    dist = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
    if (dist / 'assets').exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

    @app.get('/', include_in_schema=False)
    def dashboard():
        if (dist / 'index.html').exists():
            return FileResponse(dist / 'index.html')
        return JSONResponse({'message': 'Build frontend: cd frontend; npm install; npm run build. API docs: /docs'})

    return app
