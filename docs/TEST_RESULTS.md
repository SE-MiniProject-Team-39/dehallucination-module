# Local verification results

## Re-run — 11 November 2026 (after regression PRs #4–#7)

- Backend: **66 passed**, 0 failed (up from 32: PRs #4–#7 added regression suites under `backend/tests/ashrit/`). JUnit output: [test-results.xml](test-results.xml).
- Coverage of `backend/dam`: **92.75%** combined, 95.3% statements, 83.3% branches. CI gate at 85% passes. Details: [COVERAGE.md](COVERAGE.md).
- The browser, security and performance results below are from the 22 October run and were not repeated.

## Initial run — 22 October 2026

- Backend: **32 passed** in 32.91 seconds. JUnit output: [test-results.xml](test-results.xml). One dependency deprecation warning: Starlette warns about future migration from its HTTPX test client integration. No test failed.
- Dashboard: production build passed with Vite 6.4.5; bundle approximately 249 kB JavaScript and 17 kB CSS before compression.
- Browser: **1 full workflow passed** in installed headless Microsoft Edge. Verified sign-in, sample extraction, supported/contradicted/unsupported highlights, correction and source URL, reviewer override to Not-Checkable, all four resulting highlight states, approval, JSON download, history filtering, analytics, settings save, audit, 390-pixel viewport overflow and sign-out. No JavaScript page errors. Screenshot: [workspace.png](workspace.png).
- Security: Bandit found no issues at medium/high severity; pip-audit found no known vulnerabilities in requirements.lock; the installed frontend dependency audit reported no known vulnerabilities.
- Local running service: `/` returned HTTP 200; `/health` returned `status: ok`, mode `offline snapshot`.
- Warm-cache measurements: 10 sequential samples had 22.82 ms median and 26.91 ms nearest-rank p95. All 20 simultaneous requests returned HTTP 200; the slowest completed in 437.08 ms. Raw results: [local-performance.json](local-performance.json).

These measurements used SQLite, one local server worker, the offline corpus and warmed caches. They do not establish live-source p95, cold-cache throughput, production queueing limits, factual accuracy on arbitrary prose, or PostgreSQL performance. Live adapters were tested against mocked response shapes. Docker daemon was unavailable, so containers/PostgreSQL were not executed. No GitHub activity or demo recordings are claimed.
