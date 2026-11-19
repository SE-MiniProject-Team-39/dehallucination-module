# Code and branch coverage report — 19 November 2026 (final)

This report covers the final suite on `main`:
- the core regression tests (PRs #4–#7);
- the unit and integration suites (PR #16);
- the US-02, US-03, US-05 and US-10 acceptance suites (PRs #31–#35);
- the live-source and orbit-claim regression tests (PR #42).

The command, run from the repository root with the project virtual environment, is:

```
python -m pytest -q --junitxml=docs/test-results.xml --cov=backend/dam --cov=sdk --cov-branch --cov-report=term-missing --cov-report=xml:docs/coverage.xml
```

Tooling: pytest 9.1.1, pytest-cov 7.1.0, Python 3.11.9 (Windows 11). Result: **280 passed, 0 failed** (220 s). Machine-readable output: [coverage.xml](coverage.xml). JUnit output: [test-results.xml](test-results.xml).

| Module | Statements | Missed | Branches | Partial | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| `backend/dam/extraction.py` | 64 | 0 | 34 | 1 | 99% |
| `backend/dam/main.py` | 292 | 3 | 70 | 4 | 98% |
| `backend/dam/models.py` | 60 | 0 | 2 | 1 | 98% |
| `backend/dam/pipeline.py` | 68 | 0 | 16 | 0 | 100% |
| `backend/dam/security.py` | 21 | 0 | 8 | 0 | 100% |
| `backend/dam/sources.py` | 92 | 0 | 32 | 0 | 100% |
| `sdk/dam_client.py` | 15 | 0 | 2 | 0 | 100% |
| **Total** | **612** | **3** | **164** | **6** | **98.8%** |

- **Statement coverage:** 609 / 612 = **99.5%**.
- **Branch coverage:** 158 / 164 branch outcomes = **96.3%**.
- **Combined (statements + branches):** 767 / 776 = **98.8%**.

## History

| Date | Tests | Combined | Statements | Branches | Change |
| --- | ---: | ---: | ---: | ---: | --- |
| 11 Nov | 66 | 93.0% | 95.3% | 83.3% | First measurement (PRs #4–#7) |
| 12 Nov | 203 | 98.3% | 99.3% | 94.5% | Unit and integration suites (PR #16) |
| 19 Nov | 280 | 98.8% | 99.5% | 96.3% | Acceptance suites (PRs #31–#35) and regression tests (PR #42) |

## Remaining uncovered code

- **`main.py` line 73:** the test-only path that generates a session secret. The suite passes an explicit secret, so this line never runs.
- **`main.py` line 123:** the rate-limiter loop that evicts expired request timestamps. Covering it needs a test that advances the monotonic clock past the 60-second window.
- **`main.py` 342→345 and line 349:** serving the dashboard depends on whether `frontend/dist` has been built. With a build present (as here), the "build the frontend first" fallback never runs. Without one, the file-serving path is skipped. The Playwright end-to-end job in CI covers the built path.
- **Partial branches.** Four of the six are the conditions leading into the uncovered `main.py` lines above. The other two are each one side of a condition the tests never take:
  - `extraction.py` 40→exit: trailing text that yields no valid sentence span.
  - `models.py` 71→79: a non-SQLite (PostgreSQL) database. The PostgreSQL path was exercised manually with Docker Compose on 19 November; see [TEST_RESULTS.md](TEST_RESULTS.md).

## Gate

CI ([ci.yml](../.github/workflows/ci.yml)) runs the same command and fails the backend job if total coverage drops below 85%. It uploads `coverage.xml` and `test-results.xml` as build artifacts.
