# Ashrit: backend core and extraction contribution

Prepared on **1 November 2026** for the team's Sprint 1 review. This records work performed now; it does not backdate sprint activity.

GitHub identity: **Mlinzi (Ashrit)**. Branch: `ashrit/backend-core-extraction`. The branch was fast-forwarded to main commit `c483d9e` before implementation, retaining Chinmay's merged password-validation changes. Application edits are confined to the three files identified in the supplied archive's ownership README: `backend/dam/extraction.py`, `backend/dam/main.py`, and `backend/dam/models.py`. New tests are isolated under `backend/tests/ashrit/`. Pipeline, security, source adapters, frontend and CI workflow code are unchanged.

## Issues, fixes and regression evidence

| Issue | Reproduced behavior before the fix | Implementation | Regression cases | Fix commit |
| --- | --- | --- | --- | --- |
| [#4](https://github.com/SE-MiniProject-Team-39/dehallucination-module/issues/4) | Quoted questions become claims; punctuation followed by a closing quote fails to split adjacent sentences. | Recognize closing quotes/brackets at boundaries; exclude enclosing quote marks from the claim span using original offsets; exclude quoted questions. | 8 cases: straight/curly quotes, mixed fact/question, Unicode offsets through `/verify`, abbreviation/decimal/apostrophe controls. | `5362681` |
| [#5](https://github.com/SE-MiniProject-Team-39/dehallucination-module/issues/5) | Integer-bounded LLM spans containing only spaces or newline/tab characters are accepted as factual claims. | Reject whitespace-only source slices and use the established rule fallback. | 7 cases: two blank-span forms, invalid bounds/overlap/boolean offset, valid Unicode span and valid empty result. | `e6fd785` |
| [#6](https://github.com/SE-MiniProject-Team-39/dehallucination-module/issues/6) | Request-timeout fallback hardcodes a review flag, including when the effective threshold is zero. | Compute the fallback flag from `0.0 < threshold`; retain the Not-Checkable verdict and original text. | 4 cases: request/default thresholds at zero and 0.5, document severity, offsets and persisted results. | `2c7526a` |
| [#7](https://github.com/SE-MiniProject-Team-39/dehallucination-module/issues/7) | SQLite connections report `PRAGMA foreign_keys = 0`; a job referencing a nonexistent key commits despite the declared foreign key. | Enable foreign-key enforcement on each SQLite DBAPI connection before schema creation; PostgreSQL behavior is unchanged. | 3 cases: invalid key rejected, constraints enabled after reconnection, existing and nullable keys accepted. | `1519be3` |

Baseline evidence: the **22 newly added cases produced 13 failures and 9 passes** against unmodified main `c483d9e`. Each issue's failing cases were reproduced before editing the relevant implementation. The four focused files then passed independently after their corresponding fixes. These cases cover positive behavior, boundaries and error handling; they are not duplicate bug reports for the sake of increasing issue count.

Full regression: **66 passed** in 42.87 seconds (44 existing cases plus 22 new cases), with no failures. One upstream Starlette/HTTPX test-client deprecation warning remains. Bandit (`python -m bandit -r backend/dam sdk -ll`) passed with no reported issues. Remote CI is tracked separately in the PR and GitHub Actions; the local result is not presented as remote evidence.

## Reproduce validation

From this repository root, with the locked dependencies installed in an activated Python 3.11+ virtual environment:

```text
python -m pytest backend/tests/ashrit -q
python -m pytest -q
python -m bandit -r backend/dam sdk -ll
```

Fixtures use isolated temporary databases, test-only credentials, offline sources and mocked LLM responses. Existing local credentials/data and live providers are not used. GitHub's existing workflow discovers the new tests through pytest's recursive collection; no workflow edit is needed for these fixes. Local checks do not establish PostgreSQL or live-source performance.

## Review and integration

- Open a PR from `ashrit/backend-core-extraction` to `main`, with `Closes #4`, `Closes #5`, `Closes #6` and `Closes #7` in the description.
- Keep the issues open while the PR awaits review. Closing keywords resolve them automatically when the PR is merged into main.
- Inspect the PR's GitHub Actions backend, dashboard and dependency-review results. Record any failure and its cause; do not equate a local test pass with a successful remote run.
- A teammate should review and approve the PR before merging. This contribution does not merge itself or commit directly to main.
- The quote handling remains rule-based; arbitrary compound-claim splitting and semantic language understanding remain outside this fix.
- Enabling SQLite constraints prevents future invalid writes. It does not repair existing orphan rows. Before rollout to a database with existing content, run `PRAGMA foreign_key_check` and inspect any returned rows; no automatic cleanup is performed.

## Suggested review demonstration

1. Show the four assigned issues with reproduction steps, expected/actual behavior and severity.
2. Show the four issue-specific commits on Ashrit's branch and their linked regression files.
3. Explain why a quoted question used to pass the factual-claim filter and how the corrected offsets still slice the original text exactly.
4. Demonstrate the forced-timeout tests at threshold zero and 0.5 and the rejected SQLite orphan insert.
5. Run the focused and full backend suites; show the actual GitHub Actions result and the PR's closing references.
6. Ask the teammate reviewer to assess the diff, then follow the team's approval/merge process. Do not claim merged/closed status before it happens.
