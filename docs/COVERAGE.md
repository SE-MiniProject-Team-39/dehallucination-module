# Code and branch coverage report — 11 November 2026

Command (from the repository root, project virtual environment):

```
python -m pytest -q --cov=backend/dam --cov-branch --cov-report=term-missing --cov-report=xml:docs/coverage.xml
```

Tooling: pytest 9.1.1, pytest-cov 7.1.0, coverage.py 7.17.2, Python 3.11.9 (Windows). Result: **66 passed, 0 failed**. Machine-readable output: [coverage.xml](coverage.xml).

| Module | Statements | Missed | Branches | Partial branches | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| `extraction.py` | 64 | 1 | 34 | 2 | 97% |
| `main.py` | 292 | 21 | 70 | 15 | 90% |
| `models.py` | 60 | 0 | 2 | 1 | 98% |
| `pipeline.py` | 68 | 1 | 16 | 2 | 96% |
| `security.py` | 21 | 0 | 8 | 0 | 100% |
| `sources.py` | 92 | 5 | 32 | 5 | 92% |
| **Total** | **597** | **28** | **162** | **25** | **93%** |

Statement coverage: 569 / 597 = 95.3%. Branch coverage: 135 / 162 branch outcomes taken = 83.3%. The combined figure (93%) is coverage.py's branch-aware total.

## Uncovered code and assessment

- **`main.py` lines 71–73:** a production start-up refusal when `DAM_SESSION_SECRET` is unset. Tests always build the app with `testing=True`, which generates a secret. **Lines 231–235:** the history filters that skip non-matching jobs (text query, verdict status, maximum confidence). The remaining misses are other negative paths in API routes. Next step: add negative-path API tests for history filtering and one start-up test without the secret.
- **`sources.py` lines 85–88:** the Wikidata entity search for claims that don't match a known relation template. **Line 99:** a SPARQL query with no bindings. **Line 103:** several values where none matches the claim. These need extra mocked response fixtures, not live calls.
- **`pipeline.py` line 57:** the Wikipedia adapter is only added in live mode, and the suite runs offline.
- **`extraction.py` line 53:** the subjective-word filter (`best`, `wonderful`, `should` …). UT-01 uses "I think Paris is wonderful", which is caught earlier by the opinion-prefix rule, so this filter never fires. A sentence such as "Paris is the best city." would cover it.

## Gate

CI ([ci.yml](../.github/workflows/ci.yml)) now runs the same command with `--cov-fail-under=85`. A pull request that drops total coverage below 85% fails the backend job, and `coverage.xml` is uploaded as a build artifact next to the JUnit results.
