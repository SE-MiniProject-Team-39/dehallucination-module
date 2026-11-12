# Unit testing cases

Scope: individual extraction, scoring, model constraints, security hashing, proposition parsing, and SDK behavior. Use isolated inputs; do not call live providers without mocks.

| ID / requirements | Scenario and test data | Steps | Expected result | Automation test function |
| --- | --- | --- | --- | --- |
| UT-01 / REQ-2 | Exclude nonfacts. Input: `Hello! Is Paris nice? I think Paris is wonderful. France is in Europe.` | Call `fallback_extract(text)`; inspect returned claim texts. | Exactly one claim: `France is in Europe.` Greetings, questions, and opinions are excluded. | `test_req02_extraction_excludes_nonfacts` |
| UT-02 / REQ-3 | Unicode offsets and abbreviation. Input: `  🌍 Earth orbits the Sun.\nDr. Ada was born in London. ` | Call `fallback_extract`; slice original text using each start/end pair. | Two claims; every slice exactly equals its claim text. `Dr.` does not split the second claim. Offsets count Unicode code points. | `test_req03_offsets_unicode_and_abbreviation` |
| UT-03 / REQ-6 | No usable evidence after timeout. Input: `score([{'status':'timeout','evidence':[]}], 0.5)`. | Call `score`; inspect verdict, confidence, flag, and correction. | Verdict `Not-Checkable`, confidence 0, flagged true, no correction. | `test_req06_unavailable_notcheckable` |
| UT-04 / REQ-9 | Trust weighting. Compare trust weights 1.0 and 0.2 on identical Supported evidence. | Score each item separately at threshold 0.5. | Both scores are within 0–1; lower-trust item produces lower confidence. | `test_req09_trust_agreement_recency` |
| UT-05 / REQ-9 | Conflicting evidence tie-breaking. Equal quality and trust Supported vs Contradicted. | Score both together at threshold 0.5. | Tie produces `Contradicted` under conservative tie rule. Confidence is 0.5. | `test_score_tie_chooses_contradicted` |
| UT-06 / REQ-9 | Evidence recency decay. Compare fresh evidence vs 10-year-old evidence. | Score each item with the same trust and threshold. | Older evidence produces lower confidence; capped at 0.5 minimum floor. | `test_score_recency_floor_at_10_years` |
| UT-07 / REQ-12 | Correction confidence cutoff. Contradicted evidence with quality 0.6 vs 0.95. | Pass items to `score` at threshold 0.5. | `suggested_correction` is null when alternative $\le 0.7$; populated when alternative $> 0.7$. | `test_suggested_correction_requires_high_alternative_weight` |
| UT-08 / REQ-6, REQ-7 | Reject unsupported template reasoning (negations, qualifiers, digits). | Pass negated/qualified inputs to `proposition()`. | Returns `None`. Simple positive templates do not guess on complex reasoning. | `test_proposition_rejects_qualifiers_and_conjunctions` |
| UT-09 / REQ-2, REQ-3 | Segment abbreviations and decimals. Inputs with `Prof. Dr.`, `3.14`, and multiple newlines. | Call `segment(text)`. | Preserves decimals and multiple titles without incorrect splits. | `TestSegment::test_segment_decimal_numbers` |
| UT-10 / REQ-2 | LLM valid extraction path. Mock LLM returning valid non-overlapping spans. | Call `extract(text)` with `DAM_LLM_URL` set. | Returns extracted claims with mode `llm` without fallback. | `TestExtractLLM::test_extract_with_successful_llm_response` |
| UT-11 / REQ-11 | Document hallucination score aggregation across mixed verdicts. | Call `summarize(report)` with mixed flagged/unflagged claims. | Correctly averages $(1 - \text{confidence})$ over total claims. | `TestPipelineSummarize::test_summarize_mixed_claims_score` |
| UT-12 / security | PBKDF2 password hashing with salt and constant-time verification. | Call `hash_password(pwd)` and `check_password(pwd, hash)`. | Produces 32-char salt, 64-char digest; verifies correct password; rejects wrong password. | `TestSecurityPasswordHashing::test_check_password_success` |
| UT-13 / security | API key deterministic hashing. Key input `test-key`. | Call `hash_key(key)`. | Returns consistent 64-character SHA-256 hex digest. | `TestSecurityHashKey::test_hash_key_returns_sha256_hex` |
| UT-14 / data | SQLAlchemy model constraints and defaults. | Insert User, ApiKey, Job, Audit, Config, Cache into test DB. | Fields, timestamps (`now()`), JSON serialization, and unique constraints enforced. | `TestModelsAndDatabase::test_user_unique_username_constraint` |
| UT-15 / sources | CuratedSource supported, contradicted, and unknown fact lookups. | Await `CuratedSource().query(text, None)`. | Paris returns Supported; Lyon returns Contradicted with Paris correction; unknown returns []. | `TestCuratedSource::test_curated_contradicted` |
| UT-16 / sources | Mocked Wikipedia source sentence matching. | Await `WikipediaSource().query(text, client)`. | Matches extracted sentence against Wikipedia extract and returns Supported. | `TestWikipediaSource::test_wikipedia_query_match` |
| UT-17 / reliability | Source error isolation in `lookup()`. Adapter raises `ValueError`. | Await `lookup(FailingAdapter(), ...)`. | Catches error cleanly and returns `status: "unavailable"` without bubbling. | `TestLookupWrapper::test_lookup_error_isolation` |
| UT-18 / SDK | DAMClient initialization, payload construction, headers, and error handling. | Call `client.verify(...)` with mock urlopen. | Request sent to `/verify` with Bearer auth, JSON body, custom timeout, error propagation. | `TestDAMClientSDK::test_verify_payload_and_headers_default` |

## Execution record

| Case ID | Date / environment | Observed result | Pass / Fail / Blocked | Evidence / test function |
| --- | --- | --- | --- | --- |
| UT-01 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Exactly 1 claim returned, nonfacts excluded | Pass | `test_req02_extraction_excludes_nonfacts` |
| UT-02 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Slices match Unicode offsets exactly | Pass | `test_req03_offsets_unicode_and_abbreviation` |
| UT-03 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Verdict Not-Checkable, confidence 0.0 | Pass | `test_req06_unavailable_notcheckable` |
| UT-04 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Lower trust yields lower confidence | Pass | `test_req09_trust_agreement_recency` |
| UT-05 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Tie-break yields Contradicted | Pass | `test_score_tie_chooses_contradicted` |
| UT-06 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | 10-year recency clamped at 0.5 | Pass | `test_score_recency_floor_at_10_years` |
| UT-07 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Correction suppressed when alternative $\le 0.7$ | Pass | `test_suggested_correction_requires_high_alternative_weight` |
| UT-08 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Qualifiers and negations return None | Pass | `test_proposition_rejects_qualifiers_and_conjunctions` |
| UT-09 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Multiple titles and decimal numbers preserved | Pass | `test_segment_decimal_numbers` |
| UT-10 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Valid LLM spans parsed into claims with mode 'llm' | Pass | `test_extract_with_successful_llm_response` |
| UT-11 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Aggregates document score as 0.725 | Pass | `test_summarize_mixed_claims_score` |
| UT-12 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | PBKDF2 hash verified and rejected correctly | Pass | `test_check_password_success` |
| UT-13 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | SHA-256 64-char key hash generated | Pass | `test_hash_key_returns_sha256_hex` |
| UT-14 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Unique username constraint raised IntegrityError | Pass | `test_user_unique_username_constraint` |
| UT-15 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Curated returns Contradicted with correction | Pass | `test_curated_contradicted` |
| UT-16 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Wikipedia extract matched and returns Supported | Pass | `test_wikipedia_query_match` |
| UT-17 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | Error isolated and returns status 'unavailable' | Pass | `test_lookup_error_isolation` |
| UT-18 | 2026-11-02 / Win64 Py3.14.6 pytest-9.1.1 | SDK builds Request, headers, handles 401 & timeout | Pass | `test_verify_payload_and_headers_default` |
