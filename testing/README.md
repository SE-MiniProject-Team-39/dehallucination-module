# Project Testing & Quality Assurance

This repository implements a multi-tier testing strategy covering **unit, integration, system, acceptance, and regression testing** for the Dehallucination Module (DAM).

## Test Suite Architecture

Final count, 20 November 2026: **315 automated backend tests, all passing**, plus the Playwright browser workflow. Coverage is 97.7% of statements and 92.4% of branches (96.5% combined); see [COVERAGE.md](../docs/COVERAGE.md).

| Test file | Level | What it covers | Tests |
|---|---|---|---:|
| `test_unit_extraction.py` | Unit | Sentence segmentation, abbreviations, opinion/question filters, LLM spans | 46 |
| `test_unit_sources.py` | Unit | Proposition parsing; curated, Wikidata and Wikipedia adapters | 39 |
| `test_unit_pipeline.py` | Unit | Scoring formula, trust, recency, summary | 12 |
| `test_unit_security.py` | Unit | PBKDF2 password hashing, salts, API-key hashes | 11 |
| `test_unit_models.py` | Unit | SQLAlchemy models, timestamps, constraints | 7 |
| `test_unit_sdk.py` | Unit | Python SDK requests, headers, timeouts, errors | 6 |
| `test_dam.py` | System | REQ-1 to REQ-19 end to end through the API | 44 |
| `test_integration_flow.py` | Integration | Review lifecycle, developer isolation, cache lifetime, rate limit | 6 |
| `test_us02_trusted_adapters.py` | Acceptance | US-02 trusted graph and text adapters | 16 |
| `test_us03_source_deadlines.py` | Acceptance | US-03 source deadlines and graceful degradation | 15 |
| `test_us05_authenticated_api.py` | Acceptance | US-05 authenticated integration API | 16 |
| `test_us10_admin_source_policy.py` | Acceptance | US-10 admin source policy and access control | 26 |
| `test_injection_and_llm_quotes.py` | Unit + system | Prompt-injection detection, claim detection, LLM quote mode | 26 |
| `test_judge_evidence.py` | Unit + system | LLM evidence judge, uncited model knowledge, settings | 9 |
| `test_regression.py` | Regression | Confirmed bugs and edge cases | 14 |
| `ashrit/` (4 files) | Regression | Issue-linked fixes: quotes, LLM spans, SQLite foreign keys, timeout threshold | 22 |
| **Total** | | | **315** |

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
