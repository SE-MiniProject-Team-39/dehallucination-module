# Delivery plan and declared deviations

Both supplied PDFs were read in full; extracted text is retained beside this document. The SRS defines DAM 1.0 and REQ-1 through REQ-19. The Part-2 deliverables define GitHub backlog creation, two sprints, PR review, CI, documentation and demo recordings. No SAD or previously submitted test-plan file was present, so the implementation cannot be checked against those missing submissions. The included architecture and test plan describe the code that is actually here.

## Course schedule

- Backlog due: 12 October 2026; practice 12–16 October; final changes allowed 19 October.
- Sprint 1: 19–23 October 2026. Deliver extraction, verification, basic API, tests and a working one-minute demo.
- Sprint 2: 26–30 October 2026. Deliver review controls, analytics, hardening, final documentation and a two-minute demo; freeze development.

The backlog in [backlog.csv](backlog.csv) proposes story points and assignments based on the SRS team roster. These are planning suggestions, not claims that those members authored this code. Each team member must implement or improve their assigned feature in their own branch, open their own PR and retain authentic commit history. A repository owner must review and merge. CI configuration is supplied but only runs once pushed to a GitHub repository.

Actual local check results are recorded in [TEST_RESULTS.md](TEST_RESULTS.md).

## Implemented scope

The local project includes the FastAPI API, React dashboard, four verdict states, claim offsets, source failure isolation, timeout fallback, scoring and review flags, citation/correction display, hashed integration keys, session/CSRF authentication, role checks, rate limits, cached source results, durable jobs, overrides and audits, filtered history/analytics, administration, SDK, OpenAPI, Docker/PostgreSQL configuration and automated checks.

## Deviations and evidence still needed

1. **General verification accuracy:** offline operation is limited to seven seeded relationships. Live graph reasoning covers three relation templates; Wikipedia support requires a normalized exact sentence match. This is conservative evidence checking, not a general NLI fact-verification model. Broader accuracy needs an evaluated entailment model and labeled benchmark.
2. **Claim extraction:** rules are the default so a demonstration runs without a paid provider. An optional LLM endpoint exists, but no provider credentials or model were supplied. Compound-sentence atomicity and subjective-language filtering remain limited in rule mode. External LLM behavior has been mocked, not live-tested.
3. **REQ-5 live sources:** offline mode queries a structured snapshot and curated statements. Only live mode queries actual Wikidata and Wikipedia. A snapshot must not be presented as a live-source pass. Public API HTTP responses are unit-tested through mocks; live reliability, terms compliance and quotas still need deployment-specific checks. No paid search API is used.
4. **Corpus/vector DB:** the bounded corpus uses exact relationship matching in a JSON fixture, rather than FAISS/Chroma semantic indexing. This prevents similarity from being presented as truth, but reduces domain coverage. Production corpus ingestion, embedding search and evidence entailment are not implemented.
5. **Database:** SQLite provides a zero-setup local path. SQLAlchemy/psycopg and Compose support PostgreSQL, but no PostgreSQL server or Docker validation has been run here. Claims/evidence are nested report JSON rather than normalized claim/evidence tables.
6. **Performance:** cached requests have an automated local <500 ms check. A 20-request local concurrency check and measured short-input latency are included in the test report when run. External p95 ≤5 seconds, queueing under load, long-document behavior and production resource limits require a deployed load test. Defaults allow a 15-second request deadline even though the source deadline is 5 seconds. Rate-limit counters and login counters are process-local; run one worker until a shared limiter exists.
7. **HTTPS:** local development uses loopback HTTP. A deployment must configure TLS 1.2+ and secure cookies. No hosting target or certificate is assumed.
8. **Audit:** records are retained without automatic deletion. A production backup, retention and recovery policy is still required. Concurrent edits use last-commit-wins report updates; row locking/version checks should be added before multi-reviewer production deployment.
9. **Delivery process:** GitHub repository/Project creation, real issue assignment to account handles, PR ownership/review, deployment and video recordings require the team's repository and participation. These actions have not been fabricated or performed. The backlog, PR template, workflows and demo scripts are ready to use. Automated dependency review requires GitHub support for the repository's visibility/plan; human code review remains required.
10. **UI verification:** production assets are build-tested and the full reviewer flow passed a headless Edge browser integration test, including all four verdict colors, correction display, override, approval, export, filters, settings, audit and a 390-pixel mobile-width overflow check. This is not a comprehensive accessibility audit or cross-browser certification.

## Demo recording scripts

**Sprint 1, one minute:** sign in; paste the provided sample; verify; inspect Paris support, Sydney contradiction/Canberra correction and the unmatched Moon claim; follow an evidence link; export JSON; show `/docs` and a passing test run.

**Sprint 2, two minutes:** repeat verification and show cache indicators; reviewer overrides a verdict with a reason; approve; filter history; inspect updated analytics; as administrator change a trust weight, issue/revoke a key and inspect the audit trail; show CI. State offline and live limitations explicitly. Save actual recordings to the team's repository; no synthetic recording evidence is supplied.
