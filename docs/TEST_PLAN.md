# Test plan

The [four-level test-case catalog](../testing/README.md) contains unit, integration, system and acceptance testing folders, with eight scenarios each, requirement mappings, execution steps and expected results.

Run `python -m pytest -q` from the root with the project virtual environment. Tests use isolated temporary SQLite databases, generated test-only credentials, no real providers, and mocked official API response shapes. Test accounts and keys never enter the development database. The initial bootstrap is tested through application construction; login establishes real signed sessions and CSRF tokens.

Functional tests cover input limits, nonfacts, Unicode offsets, empty reports, graph/text adapter invocation, four-way classification, required evidence, timeouts and source errors, confidence/trust/recency/flags, document severity, corrections, immutable original text, authentication/authorization, OpenAPI security declarations, per-key rate limits, dashboard report contracts, reviewer audit trails and filtered analytics. Additional tests cover cache behavior, key revocation/ownership, LLM span fallback and mocked live adapters.

The backend REQ-17 check covers report contracts and static asset delivery. `frontend/tests/workspace.spec.js` also exercises a real browser: sign-in, sample verification, all four highlight colors (including a reviewer override), evidence/corrections, approval, JSON download, history filters, analytics, settings saving, audit, mobile overflow and logout. The React dashboard renders source offsets in code-point space. Keyboard/accessibility auditing, additional browsers, error states and one-time key visibility still merit manual checks.

After building the dashboard, run `npm run test:e2e` from frontend. By default it uses installed Playwright Chromium (`npx playwright install chromium`); on Windows with installed Edge set `$env:DAM_BROWSER_CHANNEL='msedge'`. The test starts an isolated server on port 8001 and uses a separate `frontend/playwright-test.db`, test credentials and no live providers. It creates a screenshot at `docs/workspace.png`. CI installs Chromium and runs the same test after building. Test data may accumulate in the ignored test database across local runs; it never changes the development database.

Run `npm audit --audit-level=moderate` and `npm run build` in frontend. CI also runs Bandit, pip-audit and GitHub dependency review. Passing static checks do not establish security or accuracy of arbitrary content.

Performance acceptance uses a cached-claim integration check below 500 ms, a local 20-concurrent-request run, and a short-input latency sample. Live source/network p95 and queueing SLAs are not asserted from mocked/offline runs. SQLite local results do not establish PostgreSQL throughput.

Known boundary cases: rules lack general compound-claim splitting and general opinion detection; abbreviations only cover a short list. Unrecognized facts yield Unsupported rather than a guessed verdict. Source failures with no evidence yield Not-Checkable. LLM offset validation requires ordered non-overlapping spans and does not itself establish extraction quality.
