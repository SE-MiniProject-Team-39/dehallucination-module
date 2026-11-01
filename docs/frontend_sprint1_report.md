# Frontend Sprint 1 audit and implementation report

## Repository and scope

- Repository: `SE-MiniProject-Team-39/dehallucination-module`
- Branch: `badri/frontend-ui`
- Initial worktree: clean; local `HEAD` and fetched `origin/badri/frontend-ui` both pointed to `baeb9b10a140a1982614d54aba78f337d1b30166`.
- Frontend: React 19, Vite 6, one application entry point in `frontend/src/main.jsx`, styles in `frontend/src/styles.css`, and a Playwright end-to-end test in `frontend/tests/workspace.spec.js`.
- The frontend is served by FastAPI and uses session plus CSRF authentication for reviewer/admin actions. Verification sends `text`, `context`, `source_app_id`, and optional `confidence_threshold` to `POST /api/verify`. Claim offsets are explicitly converted with `Array.from` before highlighting, preserving Unicode code-point offsets.
- Inspected the root README, `docs/ARCHITECTURE.md`, `docs/TEST_PLAN.md`, `docs/DELIVERY.md`, `docs/TEST_RESULTS.md`, frontend source, styles, Vite/Playwright configuration, and package manifest/lockfile.

## Audit findings and issue tracking

GitHub CLI (`gh`) is not installed in this environment, so no GitHub issue was created. The following issue descriptions are prepared for manual creation. No issue number or URL is claimed.

### FE-1 — Align verification text limits with Unicode code-point limits

- **Severity:** Medium
- **Affected component:** `Verify` in `frontend/src/main.jsx`
- **Finding:** The browser's `maxLength={10000}` and `text.length` counter count UTF-16 code units, but the backend accepts up to 10,000 Python Unicode code points. Non-BMP characters such as emoji count as two in the browser and one in the API, so users cannot enter the full supported amount and the displayed count does not match the server's contract.
- **Reproduction:** In Verify content, enter a string of 5,001 emoji. The browser rejects it at 10,000 UTF-16 units even though it is within the API's 10,000-code-point limit. The counter also reports 10,000 rather than 5,000.
- **Expected:** Enforce and display the same 10,000 Unicode code-point limit as the API while retaining code-point claim highlighting.
- **Actual:** Native `maxLength` and the counter use UTF-16 code units.
- **Acceptance criteria:** Input accepts up to 10,000 code points, prevents additional code points, displays the code-point count, and keeps claim highlighting aligned for emoji and other non-BMP characters.
- **Testing requirements:** Cover a short emoji-containing string, the exact 10,000-code-point boundary, and attempted input beyond the boundary; verify submitted text and highlighted offsets.
- **Status:** Locally prepared; GitHub issue creation pending.

### FE-2 — Add negative and boundary coverage to the browser workflow

- **Severity:** Low
- **Affected component:** `frontend/tests/workspace.spec.js`
- **Finding:** The existing end-to-end test exercises a successful login and the main successful reviewer/admin workflow, but does not exercise invalid login, Unicode input limits, or API/network error presentation.
- **Reproduction:** Inspect the current test; it signs in only with valid credentials and submits only the short ASCII sample.
- **Expected:** The browser suite covers rejection and boundary behavior for high-impact form and API interactions.
- **Actual:** Those paths are not asserted by the current browser test.
- **Acceptance criteria:** Add assertions for failed authentication, Unicode code-point boundary behavior, and at least one failed API request without relying on a live external service.
- **Testing requirements:** Run the complete existing Playwright suite with isolated test credentials and mocked/intercepted failure responses where appropriate.
- **Status:** Coverage added locally; GitHub issue creation remains pending.

## Baseline checks

- Production build: passed when rerun with normal filesystem access after the sandbox blocked esbuild's config-path traversal.
- Playwright initially could not start because the configured `../.venv/Scripts/python.exe` was absent. An ignored local virtual environment using installed system packages was prepared, after which the browser workflow ran successfully.
- npm dependency audit initially could not reach its endpoint in the sandbox; it passed on retry with network access and reported zero vulnerabilities.
- No lint or type-check scripts are defined in `frontend/package.json`.

## Implementation

- Updated the Verify content field to count and cap input with `Array.from`, matching Python's Unicode code-point limit of 10,000. The submit handler also guards the same limit before making an API request.
- Kept the existing code-point conversion for claim highlighting unchanged.
- Expanded the Playwright workflow to cover invalid login, whitespace-only verification input, below-limit emoji input, an exact mixed BMP/non-BMP 10,000-code-point value, safe truncation above the limit, a simulated 503 response, and mobile overflow.
- No backend code, dependencies, or API contracts were changed.

## Testing and checks

- `npm.cmd run build`: passed with Vite 6.4.5; output includes 249.44 kB JavaScript and 16.99 kB CSS before compression. Re-run during this workflow also passed.
- `DAM_BROWSER_CHANNEL=msedge npm.cmd run test:e2e`: **1 passed, 0 failed, 0 skipped**. Latest run passed in 6.8 seconds and exited normally. The workflow covered invalid and valid login, empty/whitespace and Unicode boundaries, failed and successful verification, all four verdict states, evidence/correction, override, approval, export, history filtering, analytics, settings, audit, 390-pixel overflow, and logout.
- `npm.cmd audit --audit-level=moderate`: passed; 0 vulnerabilities.
- `git diff --check`: passed.
- Unit/component, lint, and type-check scripts are not configured in the frontend package. No backend pytest suite was run as part of this frontend change.
- Backend integration: the Playwright test started the isolated FastAPI service on port 8001 and exercised real session, verification, review, history, analytics, settings, and audit endpoints. One 503 response was intercepted in the browser to test error rendering. No API or backend changes were needed.

## Screenshots

- [Verified workspace with results, evidence, and human review](workspace.png)
- [Verification API error state](frontend-sprint1-error.png)
- [Mobile Access & audit view at 390 pixels](frontend-sprint1-mobile.png)

Screenshots were captured by the Playwright browser run. The existing `docs/workspace.png` was refreshed with the current test run.

## Git and pull request readiness

- Branch: `badri/frontend-ui`; commits `cf4237f` (`Fix Unicode verification input limits`), `9ee5fe3` (`Record frontend branch push status`), and `75216e6` (`Cover verification input validation boundaries`) are pushed to origin.
- No backend teammate files were modified. `git diff --check` is clean.
- Add the created GitHub issue URLs/IDs here and link them from the PR. No issue numbers or PR URL are recorded in this report yet.
- Suggested PR title: `Align verification input limits with Unicode code points`
- PR summary: Align the verifier's input counter and limit with the backend's 10,000-code-point contract; expand browser coverage for authentication errors, Unicode input boundaries, API failures, and mobile overflow; include current workflow screenshots. Build, browser workflow, npm audit, and diff checks pass.

## Remaining manual tasks

- Create FE-1 and FE-2 in GitHub and add their issue numbers/URLs here.
- Open a PR from `badri/frontend-ui` into `main`, link the issues, and add the PR URL here. The branch commits are pushed; nothing has been merged.
