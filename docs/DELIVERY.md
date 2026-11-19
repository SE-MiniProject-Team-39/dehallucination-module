# Delivery plan and declared deviations

Both supplied PDFs were read in full; extracted text is retained beside this document. The SRS defines DAM 1.0 and REQ-1 through REQ-19. The Part-2 deliverables define GitHub backlog creation, two sprints, PR review, CI, documentation and demo recordings.

## Submission status (19 November 2026)

| Lesson-plan / Part-2 deliverable | Evidence |
| --- | --- |
| D1 – SRS | [Dehallucination_Module_SRS_Phase1.pdf](../Dehallucination_Module_SRS_Phase1.pdf) |
| D2 – Test plan; complete backlog | [TEST_PLAN.md](TEST_PLAN.md); GitHub Project **DAM 1.0 Backlog** linked to this repo. It holds 14 user stories (US-01 to US-14, 65 story points), each with an owner, story points and a sprint, plus 11 supporting task issues. Planning copy: [backlog.csv](backlog.csv) |
| D3 – Software Architecture Document | [DAM_Software_Architecture_Document_SAD.docx](DAM_Software_Architecture_Document_SAD.docx), [ARCHITECTURE.md](ARCHITECTURE.md), [architecture diagram](architecture.png), [pipeline diagram](pipeline.png) |
| D4 – Software Design Document | [DAM_Software_Design_Document.docx](DAM_Software_Design_Document.docx), [use-case diagram](use-case.png), [TRACEABILITY.md](TRACEABILITY.md) |
| Sprint 1 – working product, unit/integration tests, CI/CD | GitHub Actions on every push and PR; 1-minute demo [sprint-1.mp4](sprint-1.mp4) |
| Sprint 2 – system tests, remaining features, docs, freeze | Acceptance suites (PRs #31–#35, #39–#41); 2-minute demo [sprint-2.mp4](sprint-2.mp4) |
| Final – all test reports incl. code and branch coverage | [TEST_RESULTS.md](TEST_RESULTS.md) (280 tests passing), [COVERAGE.md](COVERAGE.md) (98.8% combined, 96.3% branch), [testing/](../testing/README.md) (32 documented scenarios across 4 levels) |

Development is frozen as of this commit; only documentation changes follow.

## Course schedule

- Backlog due: 12 October 2026; practice 12–16 October; final changes allowed 19 October.
- Sprint 1: 19–23 October 2026. Deliver extraction, verification, basic API, tests and a working one-minute demo.
- Sprint 2: 26–30 October 2026. Deliver review controls, analytics, hardening, final documentation and a two-minute demo; freeze development.

The backlog in [backlog.csv](backlog.csv) was the initial plan, with story points and proposed owners from the SRS team roster. Final ownership is on the GitHub Project and follows the branches each member actually worked on:

| Member | Stories |
| --- | --- |
| Ashrit Nair | US-01, US-04, US-07, US-11 |
| Chinmay N S | US-02, US-03, US-05, US-10 |
| Badri Harinivas | US-06, US-08, US-09 |
| Aditya Shet | US-12, US-13, US-14 |

Each member worked in their own branch (`ashrit/…`, `chinmay/…`, `badri/…`, `aditya/…`) and raised their own PRs. CI runs on every push and pull request.

Actual local check results are recorded in [TEST_RESULTS.md](TEST_RESULTS.md).

## Implemented scope

The local project includes the FastAPI API, React dashboard, four verdict states, claim offsets, source failure isolation, timeout fallback, scoring and review flags, citation/correction display, hashed integration keys, session/CSRF authentication, role checks, rate limits, cached source results, durable jobs, overrides and audits, filtered history/analytics, administration, SDK, OpenAPI, Docker/PostgreSQL configuration and automated checks.

## Deviations and evidence still needed

1. **General verification accuracy:** Offline operation is limited to seven seeded relationships. Live graph reasoning covers three relation templates; Wikipedia support requires a normalized exact sentence match. This is conservative evidence checking, not a general NLI fact-verification model. Broader accuracy needs an evaluated entailment model and labeled benchmark.

2. **Claim extraction:** Rules are the default so a demonstration runs without a paid provider. An optional LLM endpoint exists, but no provider credentials or model were supplied. Compound-sentence atomicity and subjective-language filtering remain limited in rule mode. External LLM behavior has been mocked, not live-tested.

3. **REQ-5 live sources:** Offline mode queries a structured snapshot and curated statements. Only live mode queries actual Wikidata and Wikipedia. A snapshot must not be presented as a live-source pass. Public API HTTP responses are unit-tested through mocks. On 19 November, live mode was also checked against the real Wikidata and Wikipedia APIs. That check found that Wikimedia rejected the service's User-Agent (HTTP 403), which made every live claim Not-Checkable. PR #42 fixed this, and live capital, author and orbit lookups now return real verdicts. Live reliability and quotas under load still need deployment-specific checks. No paid search API is used.

4. **Corpus/vector DB:** The bounded corpus uses exact relationship matching in a JSON fixture, rather than FAISS/Chroma semantic indexing. This prevents similarity from being presented as truth, but reduces domain coverage. Production corpus ingestion, embedding search and evidence entailment are not implemented.

5. **Database:** SQLite provides a zero-setup local path. SQLAlchemy/psycopg and Compose support PostgreSQL. Docker image build and local PostgreSQL validation were completed: both containers started successfully, all six database tables were verified, and the tables remained available after restarting PostgreSQL. Production database backup, recovery and deployment validation remain outstanding. Claims/evidence are nested report JSON rather than normalized claim/evidence tables.

6. **Performance:** Cached requests have an automated local under-500-ms check. A 20-request local concurrency check and measured short-input latency are included in the test report when run. External p95 of 5 seconds or less, queueing under load, long-document behavior and production resource limits require a deployed load test. Defaults allow a 15-second request deadline even though the source deadline is 5 seconds. Rate-limit counters and login counters are process-local; run one worker until a shared limiter exists. A local check on 19 November sent 50 simultaneous cold requests. All succeeded, but each took about 17.5 s because SQLite writes in one process serialise them. Scaling needs PostgreSQL (already supported), several workers, a shared Redis cache and rate limiter, and a job queue for verification.

7. **HTTPS:** Local development uses loopback HTTP. A deployment must configure TLS 1.2+ and secure cookies. No hosting target or certificate is assumed. HTTPS reverse-proxy configuration and secure-cookie guidance are documented; production TLS deployment has not been performed.

8. **Audit:** Records are retained without automatic deletion. A production backup, retention and recovery policy is still required. Concurrent edits use last-commit-wins report updates; row locking/version checks should be added before multi-reviewer production deployment.

9. **Delivery process:** Done:
   - the GitHub Project is created and linked;
   - every story is an issue assigned to its owner's account, with story points and a sprint;
   - every member raised PRs from their own branch;
   - CI runs on every push and PR;
   - the Sprint 1 and Sprint 2 recordings are in `docs/sprint-1.mp4` and `docs/sprint-2.mp4`.

   The deviation is code review. The handout asks repository owners to review and merge PRs, but a formal GitHub approval is recorded only on PR #17. The repository owner merged PRs #1–#16. Later PRs (#18–#19, #31–#35, #39–#43) were merged by their authors during the final sprint without a recorded review. CI ran on each of them. There is no automatic deployment, because no hosting target was supplied.

10. **UI verification:** Production assets are build-tested and the full reviewer flow passed a headless Edge browser integration test, including all four verdict colors, correction display, override, approval, export, filters, settings, audit and a 390-pixel mobile-width overflow check. This is not a comprehensive accessibility audit or cross-browser certification.

## Demo recording scripts

**Sprint 1, one minute:** Sign in; paste the provided sample; verify; inspect Paris support, Sydney contradiction/Canberra correction and the unmatched Moon claim; follow an evidence link; export JSON; show `/docs` and a passing test run.

**Sprint 2, two minutes:** Repeat verification and show cache indicators; reviewer overrides a verdict with a reason; approve; filter history; inspect updated analytics; as administrator change a trust weight, issue/revoke a key and inspect the audit trail; show CI. State offline and live limitations explicitly. Actual recordings should be retained in the team's repository; no synthetic recording evidence is supplied.