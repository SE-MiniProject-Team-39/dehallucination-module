# Unit testing cases

Scope: individual extraction, scoring and conservative matching behavior. Use isolated inputs; do not call live providers. Automation references name functions in [test_dam.py](../../backend/tests/test_dam.py). Where a referenced test also exercises other layers, the steps below specify only the unit-level assertion.

| ID / requirements | Scenario and test data | Steps | Expected result | Existing automation |
| --- | --- | --- | --- | --- |
| UT-01 / REQ-2 | Exclude nonfacts. Input: `Hello! Is Paris nice? I think Paris is wonderful. France is in Europe.` | Call `fallback_extract(text)`; inspect the returned claim texts. | Exactly one claim: `France is in Europe.` Greetings, the question and the opinion are excluded. | `test_req02_extraction_excludes_nonfacts` |
| UT-02 / REQ-3 | Unicode offsets and abbreviation. Input: `  🌍 Earth orbits the Sun.\nDr. Ada was born in London. `, with a real newline. | Call `fallback_extract`; slice the original using each start/end pair. | Two claims; every slice exactly equals its claim text. `Dr.` does not split the second claim. Offsets count Unicode code points. | `test_req03_offsets_unicode_and_abbreviation` |
| UT-03 / REQ-6 | No usable evidence after timeout. Input: `score([{'status':'timeout','evidence':[]}], 0.5)`. | Call `score`; inspect verdict, confidence, flag and correction. | Verdict Not-Checkable, confidence 0, flagged true, no correction. | `test_req06_unavailable_notcheckable` |
| UT-04 / REQ-9 | Trust weighting. Use one Supported evidence item with quality 0.95 and the same observed_at date; compare trust weights 1.0 and 0.2. | Score each item separately at threshold 0.5. | Both scores are within 0–1; the lower-trust item produces lower confidence. | `test_req09_trust_agreement_recency` |
| UT-05 / REQ-9 | Conflicting evidence. Use a Supported item and an equally weighted Contradicted item with identical quality and date. | Score the Supported item alone, then score both together. | Adding contradictory evidence lowers factual confidence; equal support and contradiction choose Contradicted under the documented conservative tie rule. | `test_req09_trust_agreement_recency` covers the confidence decrease; inspect the tie verdict separately. |
| UT-06 / REQ-9 | Evidence recency. Compare otherwise identical Supported evidence dated at the fixture snapshot and `2010-01-01T00:00:00+00:00`. | Score each item with the same trust and threshold. | The older evidence produces lower confidence; both scores remain within 0–1. | `test_req09_trust_agreement_recency` |
| UT-07 / REQ-12 | Correction confidence cutoff. One Contradicted evidence item with quality 0.6, trust weight 1 and correction `correct`. | Pass the item to `score` at threshold 0.5. | `suggested_correction` is null because alternative evidence confidence does not exceed 0.7. | Unit assertion within `test_req12_correction_threshold` |
| UT-08 / REQ-6, REQ-7 | Reject unsupported template reasoning. Inputs: `The capital of France is not London.`, `The capital of France is Paris and its largest city.`, `The capital of France is Paris, which is in Europe.`, and `The capital of France was Paris in 1900.` | For each input, await `CuratedSource().query(text, None)`. | Empty evidence list for each input. Simple positive templates do not assert support/contradiction for negated, compound or qualified claims. | `test_templates_do_not_guess_negation_or_qualified_claims` |

## Execution record

Create one row per executed case; use one UT-08 row per input if recording individual variations.

| Case ID | Date / environment | Observed result | Pass / Fail / Blocked | Evidence / defect ID |
| --- | --- | --- | --- | --- |
| — | Not executed as part of catalog creation | — | — | — |
