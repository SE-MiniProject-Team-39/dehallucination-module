# Code and branch coverage report — 20 November 2026 (final)

This report covers the final suite on `main`:
- the core regression tests (PRs #4–#7);
- the unit and integration suites (PR #16);
- the US-02, US-03, US-05 and US-10 acceptance suites (PRs #31–#35);
- the live-source regression tests (PR #42);
- prompt-injection and LLM quote-mode tests (PR #46);
- the evidence-judge tests (PR #47).

The command, run from the repository root with the project virtual environment, is:

```
python -m pytest -q --junitxml=docs/test-results.xml --cov=backend/dam --cov=sdk --cov-branch --cov-report=term-missing --cov-report=xml:docs/coverage.xml
```

Tooling: pytest 9.1.1, pytest-cov 7.1.0, Python 3.11.9 (Windows 11). Result: **315 passed, 0 failed** (199 s). Machine-readable output: [coverage.xml](coverage.xml). JUnit output: [test-results.xml](test-results.xml).

| Module | Statements | Missed | Branches | Partial | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| `backend/dam/extraction.py` | 99 | 1 | 56 | 2 | 98% |
| `backend/dam/judge.py` | 39 | 4 | 8 | 2 | 87% |
| `backend/dam/main.py` | 300 | 4 | 72 | 5 | 98% |
| `backend/dam/models.py` | 60 | 0 | 2 | 1 | 98% |
| `backend/dam/pipeline.py` | 78 | 1 | 20 | 1 | 98% |
| `backend/dam/security.py` | 21 | 0 | 8 | 0 | 100% |
| `backend/dam/sources.py` | 165 | 8 | 56 | 6 | 94% |
| `sdk/dam_client.py` | 15 | 0 | 2 | 0 | 100% |
| **Total** | **777** | **18** | **224** | **17** | **96.5%** |

- **Statement coverage:** 759 / 777 = **97.7%**.
- **Branch coverage:** 207 / 224 branch outcomes = **92.4%**.
- **Combined (statements + branches):** 966 / 1001 = **96.5%**.

## History

| Date | Tests | Combined | Statements | Branches | Change |
| --- | ---: | ---: | ---: | ---: | --- |
| 11 Nov | 66 | 93.0% | 95.3% | 83.3% | First measurement (PRs #4–#7) |
| 12 Nov | 203 | 98.3% | 99.3% | 94.5% | Unit and integration suites (PR #16) |
| 19 Nov | 280 | 98.8% | 99.5% | 96.3% | Acceptance suites (PRs #31–#35) and regression tests (PR #42) |
| 20 Nov | 315 | 96.5% | 97.7% | 92.4% | Injection detection and LLM evidence judge (PRs #46–#47); new code adds paths only reachable with a live model |

## Remaining uncovered code

- **`judge.py` 46–49, 52:** the OpenAI-compatible request path, and the rejection of a judge answer that is not a JSON object. Tests use Ollama's native path; the remote path shares the same parsing and validation.
- **`sources.py` 132–217:** judged-source edge cases:
  - a Wikipedia search with no results;
  - skipping passages once three have been chosen;
  - a judge answer with no usable label;
  - the knowledge source's timeout property and no-label path.

  They were exercised by hand against the live APIs; see [TEST_RESULTS.md](TEST_RESULTS.md).
- **`pipeline.py` 67:** adding the model-knowledge source inside a full pipeline run with a judge configured. The source itself is unit-tested.
- **`main.py`:**
  - line 74: the test-only session-secret path;
  - line 127: rate-limiter eviction, which needs a test that advances the clock 60 s;
  - line 214: labelling the report with the LLM model name;
  - lines 354–361: the dashboard-file fallback, which depends on whether `frontend/dist` is built.
- **`extraction.py` 146:** skipping a blank quote returned by an LLM in quote mode.
- **`models.py` 71→79:** the PostgreSQL connection path. It was exercised with Docker Compose on 19 November.

## Gate

CI ([ci.yml](../.github/workflows/ci.yml)) runs the same command and fails the backend job if total coverage drops below 85%. It uploads `coverage.xml` and `test-results.xml` as build artifacts.
