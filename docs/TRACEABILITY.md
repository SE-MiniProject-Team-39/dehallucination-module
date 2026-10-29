# Requirement traceability

Paths below are relative to the project root. Each row maps a functional requirement to implementation and a matching automated test in `backend/tests/test_dam.py`. Coverage means the bounded behavior is exercised, not that general fact-verification accuracy or external SLAs have been proven.

| Requirement | Implementation | Test function / qualification |
|---|---|---|
| REQ-1, 10,000 characters | main.VerifyInput | test_req01_limits_and_validation |
| REQ-2, factual extraction | extraction.py | test_req02_extraction_excludes_nonfacts; rules have documented scope |
| REQ-3, exact offsets | extraction.py, frontend Annotated | test_req03_offsets_unicode_and_abbreviation |
| REQ-4, empty claim list | extraction.py, pipeline.py | test_req04_empty_claim_list |
| REQ-5, graph + text source | sources.py, Pipeline.run | test_req05_sources_queried; live adapter test; offline snapshot is a deviation |
| REQ-6, four verdicts | sources.py, pipeline.score | test_req06_verdicts, test_req06_unavailable_notcheckable |
| REQ-7, evidence and URL | sources.evidence | test_req07_evidence |
| REQ-8, source timeout | sources.lookup | test_req08_parallel_source_timeout, test_source_error_isolation |
| REQ-9, confidence | pipeline.score | test_req09_trust_agreement_recency |
| REQ-10, flags | pipeline.score, SettingsInput | test_req10_configurable_flag_threshold |
| REQ-11, aggregate score | pipeline.summarize | test_req11_document_score |
| REQ-12, correction threshold | pipeline.score | test_req12_correction_threshold |
| REQ-13, preserve original | main.verify, Job.text | test_req13_original_preserved |
| REQ-14, authentication | main.identity, security.py | test_req14_auth_key_hash_and_ownership |
| REQ-15, Swagger / OpenAPI | FastAPI /docs and /openapi.json | test_req15_openapi |
| REQ-16, per-key limits | main.throttle | test_req16_rate_limit |
| REQ-17, dashboard colors | main.jsx, styles.css | test_req17_dashboard_assets_and_verdict_contract; browser QA remains separate |
| REQ-18, override audit | main.override, Audit | test_req18_override_audit_and_approval |
| REQ-19, analytics filters | main.analytics, Analytics UI | test_req19_analytics_filters_and_effective_verdicts |

Nonfunctional requirements: performance and concurrency need measured runs; CI includes automated tests/security checks; passwords/keys are hashed; RBAC and CSRF have integration tests; audit retention is indefinite; HTTPS is a deployment responsibility. PostgreSQL and Docker are configured but not locally exercised. See DELIVERY.md for every declared deviation and external delivery item.
