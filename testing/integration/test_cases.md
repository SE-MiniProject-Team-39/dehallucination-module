# Integration testing cases

Scope: connected components with an isolated SQLite database, mocked external providers, and real HTTP client communication.

| ID / requirements | Preconditions / test data | Steps | Expected result | Existing automation |
| --- | --- | --- | --- | --- |
| IT-01 / REQ-5 | Offline mode; curated and Wikidata snapshot adapters enabled. Text: `The capital of France is Paris.` | Submit authenticated verification request; inspect source_results and evidence. | Both `curated` and `wikidata` appear; snapshot evidence is explicitly labeled. | `test_req05_sources_queried` |
| IT-02 / REQ-8 | Slow adapter sleeps 1s; timeout 0.02s. CuratedSource fast. Text: `Earth orbits the Sun.` | Run both lookups concurrently. | Slow source reports timeout; curated returns Supported without cancellation. | `test_req08_parallel_source_timeout` |
| IT-03 / REQ-8 | Fake source raises `httpx.ConnectError`. | Invoke lookup wrapper. | Returns `status: unavailable` and empty evidence list without crashing. | `test_source_error_isolation` |
| IT-04 / REQ-7, 12, 13 | Authenticated API; text variants Paris and London as capital of France. | Verify both variants; inspect original text, verdict, snippet, URL, and correction. | Supported/Contradicted have evidence and HTTPS URLs. London receives Paris correction; original preserved. | `test_req07_evidence` |
| IT-05 / REQ-10 | Empty cache; text `The capital of France is Paris.` | Verify once; verify again with threshold 0.99. Measure latency. | First is uncached; second is cached and flagged under new threshold in $< 500$ ms. | `test_cache_reuse_and_threshold_recalculation` |
| IT-06 / REQ-2, 3 | Mock LLM response contains span start 0, end 9999 for short text. | Configure mocked extraction endpoint; call `extract`. | Invalid offsets rejected; rule-based fallback returns valid claim. | `test_invalid_llm_offsets_fall_back` |
| IT-07 / REQ-5, 6, 7 | Mock Wikidata returns Paris; mock Wikipedia returns sentence. | Call live graph adapter and Wikipedia adapter with mocked transport. | Graph adapter returns Contradicted with Paris correction; Wikipedia returns Supported. | `test_live_adapters_with_mocked_official_responses` |
| IT-08 / REQ-18 | Create Supported job; log in as reviewer. | Override claim to Unsupported (0.2, reason); approve job. | Verdict changes; automated verdict preserved; audit trail recorded; job approved. | `test_req18_override_audit_and_approval` |
| IT-09 / REQ-10 | Warmed cache entry aged > 86400 seconds (expired). | Query verification endpoint with identical text. | Expired cache entry triggers fresh lookup; `cached: False` returned. | `TestIntegrationCacheLifecycle::test_cache_expiration_and_failure_retry` |
| IT-10 / REQ-14, RBAC | Admin creates developer key for `isolated-app`. | Developer verifies text; lists jobs; tries to view foreign job. | Developer sees only their own jobs; cannot access other jobs (404) or admin endpoints (403). | `TestIntegrationDeveloperIsolation::test_key_creation_job_isolation_and_revocation` |
| IT-11 / REQ-14 | Admin revokes developer key via `DELETE /api/keys/{key_id}`. | Developer retries API call with revoked key. | Request rejected with HTTP 401 Unauthorized. | `TestIntegrationDeveloperIsolation::test_key_creation_job_isolation_and_revocation` |
| IT-12 / session | Authenticated user calls `/api/logout`. | Check session after logout. | Session cookie cleared; subsequent session calls return HTTP 401. | `TestIntegrationReviewLifecycle::test_complete_review_audit_and_analytics_flow` |
| IT-13 / REQ-16 | Client sends > 10 invalid login attempts in 300s window. | POST 11 invalid login requests to `/api/login`. | 11th request rejected with HTTP 429 and `Retry-After` header. | `TestIntegrationRateLimitingAndHealth::test_login_rate_limiting_brute_force_protection` |
| IT-14 / REQ-5 | Live mode pipeline with mocked Wikidata and Wikipedia HTTP services. | Run full pipeline verification in live mode. | Claims verified against both live mocked knowledge graph and Wikipedia extract. | `TestIntegrationLivePipelineSimulation::test_live_pipeline_with_mock_external_endpoints` |

## Execution record

| Case ID | Date / environment | Observed result | Pass / Fail / Blocked | Evidence / test function |
| --- | --- | --- | --- | --- |
| IT-01 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Curated and Wikidata queried; snapshot label present | Pass | `test_req05_sources_queried` |
| IT-02 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Timeout reported; fast source completed | Pass | `test_req08_parallel_source_timeout` |
| IT-03 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Status unavailable returned cleanly | Pass | `test_source_error_isolation` |
| IT-04 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Evidence snippets, HTTPS URLs, corrections verified | Pass | `test_req07_evidence` |
| IT-05 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Cached response verified under 500 ms | Pass | `test_cache_reuse_and_threshold_recalculation` |
| IT-06 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Invalid LLM offsets rejected; fallback used | Pass | `test_invalid_llm_offsets_fall_back` |
| IT-07 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Mocked live adapters return Contradicted & Supported | Pass | `test_live_adapters_with_mocked_official_responses` |
| IT-08 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Override and audit trail saved; job approved | Pass | `test_req18_override_audit_and_approval` |
| IT-09 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Expired cache entry triggers fresh source query | Pass | `test_cache_expiration_and_failure_retry` |
| IT-10 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Developer restricted to own jobs; admin routes return 403 | Pass | `test_key_creation_job_isolation_and_revocation` |
| IT-11 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Revoked key immediately returns 401 | Pass | `test_key_creation_job_isolation_and_revocation` |
| IT-12 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Session logout clears cookie; returns 401 on next call | Pass | `test_complete_review_audit_and_analytics_flow` |
| IT-13 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | 11th failed login returns 429 Rate Limit Exceeded | Pass | `test_login_rate_limiting_brute_force_protection` |
| IT-14 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Live pipeline simulation queries Wikidata and Wikipedia | Pass | `test_live_pipeline_with_mock_external_endpoints` |
