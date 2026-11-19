# Local verification results

## Final run — 19 November 2026 (submission)

Run on `main` after PRs #42 and #43, Windows 11, Python 3.11.9.

| Check | Result |
| --- | --- |
| Backend tests (unit, integration, acceptance, regression) | **280 passed**, 0 failed. JUnit: [test-results.xml](test-results.xml) |
| Code and branch coverage | **98.8%** combined: 99.5% statements, 96.3% branches. Details: [COVERAGE.md](COVERAGE.md) |
| Browser end-to-end (Playwright, headless Edge) | **1 full workflow passed**. Covers sign-in, wrong password, input limits, error handling, 4 verdict colours, correction, override, approval, JSON export, history filters, analytics, settings, audit |
| Manual UI walkthrough | All five pages checked at 1440 px and 390 px widths. No JavaScript errors, no horizontal scrolling |
| One-click launcher | `launch.cmd -Check` passed with a uv-created venv, with a pip-less venv and no uv, and on a second run with installs skipped |
| Docker Compose + PostgreSQL 16 | Image built, database healthy, dashboard HTTP 200. A verification request returned the correct verdicts. All 6 tables present in PostgreSQL; the stored job survived an app restart |
| Live sources (`DAM_LIVE_SOURCES=true`, real Wikidata/Wikipedia) | All sources status `ok`. "The capital of Germany is Berlin" and "…Kenya is Nairobi": Supported. "…Italy is Madrid": Contradicted, with suggested correction "Rome" |
| CI on GitHub Actions | Green on `main`: run #73 (backend tests + coverage gate, Bandit, pip-audit, npm audit, Vite build, Playwright) |

**Defect found and fixed in this run.** Before PR #42, live mode returned Not-Checkable for every claim. Wikimedia now rejects User-Agents with no contact URL (HTTP 403), and the adapters reported each source as `unavailable`. The mocked tests could not catch this. A regression test now simulates the 403.

**Local load check** (offline mode, SQLite, one worker): 50 simultaneous verification requests all returned HTTP 200. Each took about 17.5 s, because requests are effectively serialised by SQLite writes in a single process. The per-key rate limiter then returned HTTP 429 as designed. This is the expected limit of the single-instance design; see deviation 6 in [DELIVERY.md](DELIVERY.md).

## Re-run — 12 November 2026 (after merging main, including PR #16)

- Backend: **203 passed**, 0 failed. The suite grew from 32 (22 Oct) to 66 (PRs #4–#7) to 203 (PR #16 unit and integration suites). JUnit output: [test-results.xml](test-results.xml).
- Coverage of `backend/dam` and `sdk`: **98.3%** combined (99.3% statements, 94.5% branches). The CI gate at 85% passes. Details: [COVERAGE.md](COVERAGE.md).
- The browser, security and performance results below are from the 22 October run and were not repeated.

## Initial run — 22 October 2026

- Backend: **32 passed** in 32.91 seconds. JUnit output: [test-results.xml](test-results.xml). One dependency deprecation warning: Starlette warns about future migration from its HTTPX test client integration. No test failed.
- Dashboard: production build passed with Vite 6.4.5; bundle approximately 249 kB JavaScript and 17 kB CSS before compression.
- Browser: **1 full workflow passed** in installed headless Microsoft Edge. Verified sign-in, sample extraction, supported/contradicted/unsupported highlights, correction and source URL, reviewer override to Not-Checkable, all four resulting highlight states, approval, JSON download, history filtering, analytics, settings save, audit, 390-pixel viewport overflow and sign-out. No JavaScript page errors. Screenshot: [workspace.png](workspace.png).
- Security: Bandit found no issues at medium/high severity; pip-audit found no known vulnerabilities in requirements.lock; the installed frontend dependency audit reported no known vulnerabilities.
- Local running service: `/` returned HTTP 200; `/health` returned `status: ok`, mode `offline snapshot`.
- Warm-cache measurements: 10 sequential samples had 22.82 ms median and 26.91 ms nearest-rank p95. All 20 simultaneous requests returned HTTP 200; the slowest completed in 437.08 ms. Raw results: [local-performance.json](local-performance.json).

These measurements used SQLite, one local server worker, the offline corpus and warmed caches. They do not establish live-source p95, cold-cache throughput, production queueing limits, factual accuracy on arbitrary prose, or PostgreSQL performance. Live adapters were tested against mocked response shapes. Docker daemon was unavailable, so containers/PostgreSQL were not executed. CI is configured but had not run on GitHub as of 22 October. No GitHub activity or demo recordings are claimed.
