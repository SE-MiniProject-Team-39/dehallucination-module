# Test plan: DAM 1.0 (Dehallucination Module)

| Item | Value |
| --- | --- |
| Product | DAM 1.0: factual-claim extraction and verification service with reviewer dashboard |
| Basis | [Dehallucination_Module_SRS_Phase1](Dehallucination_Module_SRS_Phase1.txt), REQ-1 to REQ-19 |
| Test catalog | [testing/](../testing/README.md): 32 scenarios (UT, IT, ST, AT ×8) |
| Traceability | [TRACEABILITY.md](TRACEABILITY.md) |
| Results | [TEST_RESULTS.md](TEST_RESULTS.md), [COVERAGE.md](COVERAGE.md) |
| Plan version | 2.1 (12 November 2026). Replaces the prose-only v1. |

## 1. Objectives

1. Show that every SRS requirement REQ-1 to REQ-19 has at least one passing test, or is listed as a known deviation in [DELIVERY.md](DELIVERY.md).
2. Prevent regressions on every push and pull request through CI.
3. Measure statement and branch coverage of `backend/dam` and `sdk` and keep it at 85% or above.
4. Find security defects (authentication, authorization, CSRF, rate limiting, dependency CVEs) before release.

## 2. Scope

**In scope:** claim extraction and offsets, source adapters (curated corpus, Wikidata, Wikipedia via mocks), scoring/verdicts/corrections, REST API and OpenAPI contract, bearer-key and session authentication, role-based access, rate limits, caching, persistence, reviewer workflows in the React dashboard, analytics and audit.

**Out of scope (and why):**
- Live Wikidata/Wikipedia availability and quotas. These are third-party services, so the tests use mocked response shapes.
- Factual accuracy on arbitrary prose. There is no labeled benchmark; see DELIVERY.md deviation 1.
- PostgreSQL and Docker deployment. No Docker daemon was available locally.
- Production p95 latency under load, TLS configuration, and a full accessibility audit.

## 3. Test levels and approach

| Level | Cases | Technique | Tooling | Automation |
| --- | --- | --- | --- | --- |
| Unit | UT-01 – UT-08 | Equivalence partitioning, boundary values (scores 0–1, threshold 0.7), white-box branch tests | pytest | Automated |
| Integration | IT-01 – IT-08 | Adapter/pipeline/DB interaction, fault injection (timeouts, source errors), cache hits | pytest + FastAPI TestClient, mocked HTTP | Automated |
| System | ST-01 – ST-08 | Black-box HTTP: input limits, auth, OpenAPI, rate limit + `Retry-After`, RBAC | pytest + TestClient | Automated |
| Acceptance | AT-01 – AT-08 | End-to-end reviewer and admin scenarios in a real browser, including a 390 px mobile check | Playwright (Chromium / Edge) | Automated + manual walkthrough at demo |
| Static / security | – | Static analysis, dependency audit | Bandit, pip-audit, npm audit, GitHub dependency review | CI |
| Coverage | – | Statement + branch coverage | pytest-cov (coverage.py) | CI gate ≥ 85% |
| Performance | – | Warm-cache latency (<500 ms), 20 concurrent requests | pytest check + local script | Partly automated |

## 4. Test environment

- Python 3.11, dependencies from `requirements.lock`, project `.venv`.
- Each test gets an isolated temporary SQLite database, generated test-only credentials and `testing=True` app construction. Test accounts and keys never reach the development DB.
- Offline source mode (`DAM_LIVE_SOURCES=false`). Live adapters run against mocked official response shapes.
- Browser tests use an isolated server on port 8001 and `frontend/playwright-test.db`. On Windows, set `$env:DAM_BROWSER_CHANNEL='msedge'`.
- CI runs on GitHub Actions `ubuntu-latest` ([ci.yml](../.github/workflows/ci.yml)).

## 5. Entry and exit criteria

**Entry:** the feature branch builds; a PR is open against `main` with the template filled in; the new behavior has test cases in the catalog.

**Exit (per sprint / release):**
- 100% of automated tests pass. No test is skipped without a recorded reason.
- Combined branch-aware coverage of `backend/dam` is at least 85% (CI enforced).
- No Bandit findings of medium or high severity, and no known CVEs from pip-audit or npm audit.
- Every REQ is mapped in TRACEABILITY.md to a passing test or a declared deviation.
- At least one reviewer has approved the PR.

**Suspension / resumption:** pause testing if the build or the test database setup fails. Resume once the fix is merged and the suite has been re-run from a clean state.

## 6. Schedule and responsibilities

| Period | Activity | Owner (per backlog) |
| --- | --- | --- |
| Sprint 1 (19–23 Oct 2026) | Unit + integration tests for extraction, adapters, scoring; CI pipeline | Chinmay N S, Badri Harinivas, Ashrit Nair, Aditya S |
| Sprint 2 (26–30 Oct 2026) | System + acceptance tests, browser E2E, security scans, remaining unit/integration | Aditya S (testing/CI lead), all members for their features |
| 1–11 Nov 2026 | Regression fixes (PRs #4–#7), coverage measurement, final test report | Ashrit Nair + reviewers |
| Final week | Re-run the full suite on `main`, attach CI artifacts, demo | Whole team |

## 7. Deliverables

The test plan (this document), the test case catalog ([testing/](../testing/README.md)), JUnit results ([test-results.xml](test-results.xml)), the coverage report ([COVERAGE.md](COVERAGE.md), [coverage.xml](coverage.xml)), the results summary ([TEST_RESULTS.md](TEST_RESULTS.md)), a browser screenshot ([workspace.png](workspace.png)) and CI artifacts per run.

## 8. Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Mocked live-source responses drift from the real APIs | Live-mode defects not caught | Mocks follow the official response shapes; run a manual live-mode smoke test before the demo |
| SQLite vs PostgreSQL behavior differences | Production-only DB bugs | Foreign keys are enforced on SQLite (PR #7); Compose PostgreSQL config is supplied for later validation |
| Rule-based extraction misses compound or subjective claims | False "Unsupported" verdicts | Documented boundary cases (below); optional LLM extractor with offset validation |
| Process-local rate limiter | Limits bypassed with several workers | Run a single worker; listed as a deviation |
| Flaky browser test timing | False CI failures | Isolated port and DB; Playwright auto-waits |

## 9. Defect management

Defects are logged as GitHub Issues labeled `bug` and linked to the failing test ID and REQ. Each fix lands through a PR that adds a regression test (see PRs #4–#7 and [ashrit-core-extraction.md](ashrit-core-extraction.md)). Severity: **Critical** = wrong verdict shown as verified or a security bypass; **Major** = a requirement not met; **Minor** = cosmetic or a documentation issue.

## 10. Execution details

Run `python -m pytest -q` from the root with the project virtual environment. For coverage, run `python -m pytest -q --cov=backend/dam --cov-branch --cov-report=term-missing`.

Functional tests cover input limits, nonfacts, Unicode offsets, empty reports, graph/text adapter invocation, four-way classification, required evidence, timeouts and source errors, confidence/trust/recency/flags, document severity, corrections, immutable original text, authentication/authorization, OpenAPI security declarations, per-key rate limits, dashboard report contracts, reviewer audit trails and filtered analytics. Additional tests cover cache behavior, key revocation/ownership, LLM span fallback and mocked live adapters.

`frontend/tests/workspace.spec.js` exercises a real browser: sign-in, sample verification, all four highlight colors (including a reviewer override), evidence/corrections, approval, JSON download, history filters, analytics, settings saving, audit, mobile overflow and logout. After building the dashboard, run `npm run test:e2e` from `frontend` (install Chromium with `npx playwright install chromium`). The test also writes `docs/workspace.png`.

Run `npm audit --audit-level=moderate` and `npm run build` in `frontend`. Passing static checks don't establish security or the accuracy of results on arbitrary content.

**Known boundary cases:** the rules don't split general compound claims and don't detect general opinions; abbreviation handling covers only a short list. Unrecognized facts yield Unsupported rather than a guessed verdict. Source failures with no evidence yield Not-Checkable. LLM offset validation requires ordered, non-overlapping spans and doesn't by itself establish extraction quality.
