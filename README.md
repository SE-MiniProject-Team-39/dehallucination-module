# DAM — Dehallucination Add-On Module

A local FastAPI service and React reviewer workspace built from the two supplied PDFs. It extracts English factual claims, preserves their offsets, gathers evidence, scores and flags claims, and supports human review with an audit trail.

**This is a runnable course-project implementation with bounded verification coverage.** The offline demonstration recognizes seven seeded relationships (capital cities, Hamlet's author, Earth's orbit). It does not establish the truth of arbitrary prose. Unmatched claims remain Unsupported; unavailable sources produce Not-Checkable when no evidence remains. Confidence is a heuristic, not a calibrated probability.

## Run on Windows

Run the whole application with one command (or double-click `launch.cmd`):

```powershell
.\launch.cmd
```

The launcher creates `.venv` if needed, installs the locked Python and npm dependencies on first use or when their lockfiles change, builds the dashboard, creates `.env` only if it is missing, and opens **http://127.0.0.1:8000** once the service is ready. The backend serves both the dashboard and API. Python 3.11+ with venv support and Node.js/npm must already be installed; the first setup needs internet access. Existing credentials and data are preserved.

Keep the terminal open and press **Ctrl+C** to stop the server. Server logs are written to `.venv/dam-server.log` and `.venv/dam-server.err.log`. If port 8000 is occupied, choose another port:

```powershell
.\launch.cmd -Port 8001
```

Optional flags: `-NoBrowser` runs without opening a browser; `-SkipInstall` uses dependencies already installed; `-Check` builds, starts and verifies the app, then stops it. The PowerShell script can also be called directly with `powershell -NoProfile -ExecutionPolicy Bypass -File .\launch.ps1`.

For manual setup instead:

Use Python 3.11+ and Node.js 20.19+ or 22+. From the project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe manage.py init
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn backend.dam.main:create_app --factory --host 127.0.0.1 --port 8000
```

If the Python launcher (`py`) is unavailable, use the full path to your Python 3.11+ executable for the first command. A virtual environment has already been prepared in this workspace.

Open **http://127.0.0.1:8000**. Sign in as `admin` or `reviewer` using the corresponding generated password in `.env`. No shared default password is shipped. `manage.py init` refuses to overwrite an existing `.env`. Credentials bootstrap only missing accounts; changing an environment password does not reset an existing user.

The service provides **http://127.0.0.1:8000/docs** and `/openapi.json`. The public `/health` endpoint reports live or offline mode. Generated build assets must exist before starting the backend. For development, run the backend on port 8000 and `npm.cmd run dev` in `frontend` (port 5173, with an API proxy).

## Use the API

Set a bearer token from `DAM_API_KEY` in your private `.env`, or create a new key in **Access & audit**. Keys are stored as SHA-256 hashes; a newly issued key is displayed once. `source_app_id` must equal the key's application name (`demo-app` for the bootstrap key).

```python
import os
from dotenv import load_dotenv
from sdk.dam_client import DAMClient

load_dotenv()
client = DAMClient('http://127.0.0.1:8000', os.environ['DAM_API_KEY'], 'demo-app')
report = client.verify('The capital of France is Paris. The capital of Australia is Sydney.')
print([(c['text'], c['verdict'], c['suggested_correction']) for c in report['claims']])
```

Text is never silently rewritten. Character offsets are Unicode code-point indices, start inclusive and end exclusive; the dashboard converts JavaScript text to code points before highlighting. The report contains the untouched original, evidence snippets/URLs, per-source outcomes, automated verdicts, cache indicators, effective review verdicts, and an aggregate score.

## Review and administration

- **Verify content:** paste text, try the example, optionally set context and a threshold, inspect highlighted claims and citations, export the report as JSON, override verdicts with a reason, and approve the review.
- **Review history:** search and filter by status, date, application, key ID, and maximum claim confidence.
- **Analytics:** view effective reviewer results, daily document scores, counts, and per-job report details. The review rate is the fraction of flagged claims; a document score averages the severity of flagged claims across all claims.
- **Settings:** administrators configure trusted adapter activation, trust weights, timeouts, rate limits, and the default threshold. Changes invalidate cache identities and are audited.
- **Access & audit:** administrators issue/revoke integration keys and inspect configuration, approval, and override events. Original automatic verdicts survive overrides. Audit records are retained indefinitely, exceeding the 90-day requirement; backups must preserve them.

Integration keys can access only their own jobs and cannot review or administer. Session users require a CSRF token for writes. Login attempts and per-key requests are rate limited, with HTTP 429 and Retry-After. Swagger, login, health, and static assets are intentionally public; business operations require authentication.

## Live sources and extraction

Set `DAM_LIVE_SOURCES=true` in `.env` and restart to query Wikidata and Wikipedia alongside the corpus. There are no paid API dependencies. Each enabled adapter is called for each uncached claim, with an individual timeout (default 5 seconds) and a request deadline (default 15 seconds). Evidence from remaining sources can still yield a verdict if one source fails. A timeout without usable evidence yields Not-Checkable. Source failures are not cached. API quotas/unavailability degrade to source-error states rather than blocking the whole service.

Live Wikidata handles capital, author, and orbital relationships; unsupported relationships receive entity retrieval only and no inferred verdict. Wikipedia retrieval establishes support only on a normalized exact sentence match. Search relevance is never treated as entailment. The offline Wikidata adapter is explicitly a snapshot, **not** a live REQ-5 query. Known relationships in [corpus.json](backend/dam/corpus.json) are small educational fixtures with attributed source identifiers and a fixed snapshot date. Duplicated snapshot evidence does not increase confidence above the average evidence strength.

Rules provide an offline sentence extractor and filter obvious nonfacts; they cannot reliably split arbitrary compound sentences into atomic facts. For an LLM-assisted extractor, configure `DAM_LLM_URL` (a full HTTPS chat-completions endpoint), `DAM_LLM_KEY`, and `DAM_LLM_MODEL`. Responses must contain valid, non-overlapping offsets into the original. Malformed responses and provider errors fall back to rules. Input and optional context are sent to this configured provider; enable it only for text you may send there. Context aids extraction, and does not become evidence.

Adapter references: [MediaWiki Search API](https://www.mediawiki.org/wiki/API:Search) and [Wikidata SPARQL interface](https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service). Both external content sources require attribution and compliance with their service policies. Adapter HTTP calls have fixed Wikimedia destinations; administrators cannot inject arbitrary URLs.

## Validate

The [testing folder](testing/README.md) organizes 32 documented scenarios into unit, integration, system and acceptance testing, with links to the existing automated checks.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm.cmd audit --audit-level=moderate
npm.cmd run build
```

For browser integration checks, run `npm.cmd run test:e2e` from frontend with Playwright Chromium installed. On this Windows machine, the installed Edge browser can be selected using `$env:DAM_BROWSER_CHANNEL='msedge'`. See [test instructions](docs/TEST_PLAN.md).

Tests cover all 19 functional requirement paths, including Unicode offsets, empty input results, evidence, timeout isolation, correction thresholds, API authentication, ownership, CSRF, rate limits, override auditing, filtering, cache reuse, and mocked live adapter responses. This is not a claim of unrestricted language accuracy or production performance. [Traceability](docs/TRACEABILITY.md), [architecture](docs/ARCHITECTURE.md), [test plan](docs/TEST_PLAN.md), and [delivery plan](docs/DELIVERY.md) describe scope and remaining validation. CI runs automated tests, static security analysis, dependency vulnerability checks, PR dependency review, and the dashboard build.

## Docker / PostgreSQL

After generating `.env`, run `docker compose up --build`. This builds the dashboard into the API image and starts PostgreSQL with persistent storage. SQLite is the default zero-setup local database; set `DATABASE_URL=postgresql+psycopg://...` for a separate PostgreSQL instance. PostgreSQL/Docker operation requires Docker and is not validated by the local SQLite test suite.

For internet-facing deployment, terminate HTTPS at a reverse proxy and set `DAM_SECURE_COOKIES=true`. Start with one API worker: rate-limit and login counters are process-local. Multiple workers require a shared limiter. There is no automatic deployment from CI because no target or credentials were supplied. Schema creation is suitable for the initial version; introduce migrations before evolving a deployed schema. Review [documented deviations](docs/DELIVERY.md) before the final demo.
