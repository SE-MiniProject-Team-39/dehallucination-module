# Project Testing & Quality Assurance

This repository implements a multi-tier testing strategy covering **unit, integration, system, acceptance, and regression testing** for the Dehallucination Module (DAM).

## Test Suite Architecture

```
backend/tests/
  ├── test_dam.py                 # Core requirements suite (REQ-01 to REQ-19) [32 tests]
  ├── test_unit_extraction.py     # Segmentation, abbreviations, filters, LLM spans [46 tests]
  ├── test_unit_pipeline.py       # Scoring formula, trust, recency, summarize [12 tests]
  ├── test_unit_security.py       # PBKDF2 hashing, salts, key hashes [11 tests]
  ├── test_unit_models.py         # SQLAlchemy models, timestamps, constraints [7 tests]
  ├── test_unit_sources.py        # Proposition parsing, Curated/Wikidata/Wiki adapters [39 tests]
  ├── test_unit_sdk.py            # DAMClient SDK requests, headers, timeouts, errors [6 tests]
  ├── test_integration_flow.py    # Review lifecycle, developer isolation, cache TTL, rate limit [6 tests]
  └── test_regression.py          # Regression tests for confirmed bugs and edge cases [10 tests]
```

Total automated backend test count: **169 tests** (100% passing).

---

## Code Coverage Summary

Automated testing achieved **99% total statement coverage** across the core codebase:

| Module | Statements | Missing | Coverage | Notes |
| :--- | :---: | :---: | :---: | :--- |
| `backend/dam/extraction.py` | 50 | 0 | **100%** | Full segmentation, rule-based fallback, and LLM span extraction |
| `backend/dam/models.py` | 53 | 0 | **100%** | All models, SQLite configurations, and sessionmaker factory |
| `backend/dam/pipeline.py` | 68 | 0 | **100%** | Full pipeline, scoring formulas, recency decay, and caching |
| `backend/dam/security.py` | 12 | 0 | **100%** | PBKDF2 hashing, salts, constant-time comparisons, key hashing |
| `backend/dam/sources.py` | 92 | 0 | **100%** | CuratedSource, WikidataSource (offline & live), WikipediaSource, lookup wrapper |
| `sdk/dam_client.py` | 15 | 0 | **100%** | Client initialization, headers, payload serialization, error propagation |
| `backend/dam/main.py` | 290 | 2 | **99%** | All endpoints, auth, RBAC, filters, overrides, and rate limiting |
| **TOTAL** | **580** | **2** | **99%** | Highly comprehensive automated verification |

---

## Test Execution Commands

### 1. Environment Setup
Activate the virtual environment containing the locked dependencies:

```powershell
# Create venv if not already created
py -m venv .venv

# Install locked dependencies
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install bandit pip-audit pytest-cov
```

### 2. Running Backend Tests

Run the full suite with concise output:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run with line-by-line coverage analysis:
```powershell
.\.venv\Scripts\python.exe -m pytest --cov=backend/dam --cov=sdk --cov-report=term-missing
```

Run specific test modules:
```powershell
# Unit tests
.\.venv\Scripts\python.exe -m pytest backend/tests/test_unit_extraction.py -v
.\.venv\Scripts\python.exe -m pytest backend/tests/test_unit_pipeline.py -v
.\.venv\Scripts\python.exe -m pytest backend/tests/test_unit_security.py -v
.\.venv\Scripts\python.exe -m pytest backend/tests/test_unit_models.py -v
.\.venv\Scripts\python.exe -m pytest backend/tests/test_unit_sources.py -v
.\.venv\Scripts\python.exe -m pytest backend/tests/test_unit_sdk.py -v

# Integration tests
.\.venv\Scripts\python.exe -m pytest backend/tests/test_integration_flow.py -v

# Regression tests
.\.venv\Scripts\python.exe -m pytest backend/tests/test_regression.py -v
```

### 3. Running Security Scans
```powershell
# Static analysis with Bandit
.\.venv\Scripts\bandit.exe -r backend/dam sdk -ll

# Dependency vulnerability audit with pip-audit
.\.venv\Scripts\pip-audit.exe -r requirements.lock
```

### 4. Running Browser Acceptance Tests
```powershell
cd frontend
npm ci
npm run build
$env:DAM_BROWSER_CHANNEL='msedge' # or omit for installed Chromium
npm run test:e2e
```

---

## Detailed Test Case Catalogs

Specific test cases and verification records are documented in their respective subdirectories:
- [Unit Testing Catalog](unit/test_cases.md) (UT-01 to UT-18)
- [Integration Testing Catalog](integration/test_cases.md) (IT-01 to IT-14)
- [System Testing Catalog](system/test_cases.md) (ST-01 to ST-08)
- [Acceptance Testing Catalog](acceptance/test_cases.md) (AT-01 to AT-08)
