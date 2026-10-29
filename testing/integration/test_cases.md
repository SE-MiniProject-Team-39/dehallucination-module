# Integration testing cases

Scope: connected components with an isolated SQLite database and mocked external providers. Use the existing pytest fixtures; no development credentials or live network access are needed. References name functions in [test_dam.py](../../backend/tests/test_dam.py).

| ID / requirements | Preconditions / test data | Steps | Expected result | Existing automation |
| --- | --- | --- | --- | --- |
| IT-01 / REQ-5 | Offline mode; curated and Wikidata snapshot adapters enabled. Text: `The capital of France is Paris.` | Submit an authenticated verification request; inspect the first claim's source_results and evidence. | Both `curated` and `wikidata` appear; snapshot evidence is explicitly labeled. This does not establish live Wikidata compliance. | `test_req05_sources_queried` |
| IT-02 / REQ-8 | One fake adapter sleeps 1 second; timeout 0.02 seconds. Second adapter is CuratedSource. Text: `Earth orbits the Sun.` | Run both lookups concurrently. | Slow source reports timeout; curated evidence still returns Supported. One source does not cancel the other. | `test_req08_parallel_source_timeout` |
| IT-03 / REQ-8, reliability | Fake source raises `httpx.ConnectError`. | Invoke the source lookup wrapper. | It returns `status: unavailable` and an empty evidence list instead of propagating an exception to the caller. | `test_source_error_isolation` |
| IT-04 / REQ-7, REQ-12, REQ-13 | Authenticated API; text variants `The capital of France is Paris.` and `The capital of France is London.` | Verify both variants; inspect original text, verdict, evidence snippet, URL and correction. | Supported/Contradicted claims have nonempty evidence and HTTPS source URLs. London receives the Paris correction separately; original input is preserved. | `test_req07_evidence`, `test_req12_correction_threshold`, `test_req13_original_preserved` |
| IT-05 / UC-4, REQ-10, cache performance | Empty temporary cache; source settings unchanged. Text: `The capital of France is Paris.` | Verify once; verify again with request threshold 0.99. Measure the second request. | First result is uncached; second is cached and flagged under the new threshold. Cached request completes in under 500 ms on the local test environment. | `test_cache_reuse_and_threshold_recalculation` |
| IT-06 / REQ-2, REQ-3, fallback reliability | Mock LLM response contains span start 0, end 9999 for `Earth orbits the Sun.` | Configure the mocked extraction endpoint; call `extract`. | Invalid offsets are rejected; the rule-based fallback returns one valid claim and identifies fallback mode. | `test_invalid_llm_offsets_fall_back` |
| IT-07 / REQ-5, REQ-6, REQ-7 | Mock Wikidata returns Paris for France's capital; mock Wikipedia returns the exact sentence `Earth orbits the Sun.` | Call live-mode graph adapter with the London claim and Wikipedia adapter with the orbit claim. | Graph adapter returns Contradicted with Paris correction and a source URL; Wikipedia returns Supported. No real provider is queried. | `test_live_adapters_with_mocked_official_responses` |
| IT-08 / REQ-18 | Create a Supported France job; log in as reviewer. | Override the claim to Unsupported, confidence 0.2, reason `Source needs further review`; inspect the response and Audit table; approve the job. | Effective verdict changes; original automatic verdict remains Supported; reviewer/timestamp/reason and before/after audit are stored; approval records reviewer identity. | `test_req18_override_audit_and_approval` |

## Execution record

| Case ID | Date / environment | Observed result | Pass / Fail / Blocked | Evidence / defect ID |
| --- | --- | --- | --- | --- |
| — | Not executed as part of catalog creation | — | — | — |
