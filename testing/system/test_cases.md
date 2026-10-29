# System testing cases

Scope: externally visible service behavior through HTTP. Automated execution uses FastAPI TestClient and temporary SQLite databases; it is not proof of deployed PostgreSQL, TLS or production performance. References name functions in [test_dam.py](../../backend/tests/test_dam.py).

| ID / requirements | Preconditions / test data | Steps | Expected result | Existing automation |
| --- | --- | --- | --- | --- |
| ST-01 / REQ-1 | Valid integration key and matching application ID. Inputs: 10,000 `a` characters; 10,001 `a` characters; empty text with 2,001-character context; confidence threshold 1.1. | POST each payload to `/verify`. | 10,000-character text is accepted with HTTP 200; oversized/invalid payloads return HTTP 422 and the JSON error envelope. No factual claims are expected from repeated `a` text. | `test_req01_limits_and_validation` covers status codes; inspect error envelope separately. |
| ST-02 / REQ-4, REQ-6, REQ-11 | Offline mode and a valid key. Input variants: Paris as France's capital; London as France's capital; Moon made of cheese; `Hello! Thank you. What is your name?` | Verify each variant. | First three return Supported, Contradicted and Unsupported respectively. Nonfactual-only text returns an empty claims list and document score 0. | `test_req06_verdicts`, `test_req04_empty_claim_list` |
| ST-03 / REQ-14 | One valid integration key. | Send a verification request without credentials; query jobs with a wrong key; submit valid-key text with a spoofed application ID. | Missing/wrong credentials return 401; application mismatch returns 403. Keys are stored hashed rather than as plaintext. | `test_req14_auth_key_hash_and_ownership` |
| ST-04 / REQ-15 | Service initialized; no login needed for documentation. | GET `/openapi.json` and `/docs`; inspect verification endpoint security declarations. | OpenAPI includes `/verify` and its security requirement; Swagger page returns 200. | `test_req15_openapi` |
| ST-05 / REQ-16 | Set the test key's limit to one request per minute; unused request counter. | Submit two valid verification requests immediately. | First returns 200; second returns 429 with a positive integer Retry-After header. | `test_req16_rate_limit` |
| ST-06 / security, administration | Administrator session and valid settings payload. | Remove X-CSRF-Token and attempt settings PUT; retrieve the session token and retry with threshold 0.75; inspect audit. | Missing CSRF returns 403; valid write succeeds; settings change is audited. Reviewer role cannot read administrator settings. | `test_sessions_csrf_and_admin_configuration`, role check in `test_req18_override_audit_and_approval` |
| ST-07 / REQ-14, RBAC | Create a job under the bootstrap key; administrator creates a second application's key. | With the second key, list jobs, request the first application's job and request settings. Revoke the second key and retry. | No other application's jobs are listed; direct foreign job access returns 404; settings access returns 403; revoked key returns 401. | `test_key_create_revocation_and_developer_isolation` |
| ST-08 / REQ-18, REQ-19 | A Supported job and reviewer session. | Filter analytics by nonexistent app, future start date and nonexistent key ID; override the claim to Unsupported at confidence 0.1; query unfiltered analytics. | Filters yield zero matching jobs. Effective analytics show review rate 1, one overridden claim and reviewer identity; the original automated verdict remains retained. | `test_req19_analytics_filters_and_effective_verdicts` plus original-verdict assertion in `test_req18_override_audit_and_approval` |

## Execution record

| Case ID | Date / environment | Observed result | Pass / Fail / Blocked | Evidence / defect ID |
| --- | --- | --- | --- | --- |
| — | Not executed as part of catalog creation | — | — | — |
