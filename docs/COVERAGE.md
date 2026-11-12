# Code and branch coverage report — 12 November 2026

This report covers the merged suite: the core regression tests (PRs #4–#7) plus the unit and integration suites from PR #16. The command, run from the repository root with the project virtual environment, is:

```
python -m pytest -q --cov=backend/dam --cov=sdk --cov-branch --cov-report=term-missing --cov-report=xml:docs/coverage.xml
```

Tooling: pytest 9.1.1, pytest-cov 7.1.0, coverage.py 7.17.2, Python 3.11.9 (Windows). Result: **203 passed, 0 failed**. Machine-readable output: [coverage.xml](coverage.xml). JUnit output: [test-results.xml](test-results.xml).

| Module | Statements | Missed | Branches | Partial | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| `backend/dam/extraction.py` | 64 | 0 | 34 | 1 | 99% |
| `backend/dam/main.py` | 292 | 4 | 70 | 6 | 97% |
| `backend/dam/models.py` | 60 | 0 | 2 | 1 | 98% |
| `backend/dam/pipeline.py` | 68 | 0 | 16 | 1 | 99% |
| `backend/dam/security.py` | 21 | 0 | 8 | 0 | 100% |
| `backend/dam/sources.py` | 92 | 0 | 32 | 0 | 100% |
| `sdk/dam_client.py` | 15 | 0 | 2 | 0 | 100% |
| **Total** | **612** | **4** | **164** | **9** | **98.3%** |

- **Statement coverage:** 608 / 612 = 99.3%.
- **Branch coverage:** 155 / 164 branch outcomes = 94.5%.

The first measurement, on 11 November with 66 tests, was 93% combined (95.3% statements, 83.3% branches). PR #16 closed most of the gaps listed in that report.

## Remaining uncovered code

- **`main.py` line 73:** the test-only path that generates a session secret. The suite now passes an explicit secret, so this line never runs.
- **`main.py` line 123:** the rate-limiter loop that evicts expired request timestamps. Covering it needs a test that advances the monotonic clock past the 60-second window.
- **`main.py` lines 343 and 348:** serving the built dashboard (`frontend/dist`). The backend suite runs without a frontend build. The Playwright E2E job in CI exercises these paths.
- **Partial branches.** Each of these is one side of a condition the tests never take:
  - `main.py` 83→85: start-up on a database that already has settings, i.e. a restart.
  - `main.py` 90→92: start-up where the demo API key is unset or already stored.
  - `extraction.py` 40→exit: trailing text that yields no valid sentence span.
  - `models.py` 71→79: a non-SQLite (PostgreSQL) database.
  - `pipeline.py` 77→81: a fresh lookup where a source didn't return `ok`, so nothing is cached.

## Gate

CI ([ci.yml](../.github/workflows/ci.yml)) runs the same command and fails the backend job if total coverage drops below 85%. It uploads `coverage.xml` and `test-results.xml` as build artifacts.
