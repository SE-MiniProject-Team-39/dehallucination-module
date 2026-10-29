# Project testing

The four testing levels used here are **unit, integration, system, and acceptance**. Each folder contains eight project-specific test-case specifications with inputs, steps, expected results, requirement references, and links to existing automation.

| Folder | Focus | Cases |
| --- | --- | --- |
| [unit](unit/test_cases.md) | Individual extraction, scoring and matching rules | UT-01–UT-08 |
| [integration](integration/test_cases.md) | Interactions between adapters, pipeline, API, cache and database | IT-01–IT-08 |
| [system](system/test_cases.md) | Complete service behavior through its HTTP interface | ST-01–ST-08 |
| [acceptance](acceptance/test_cases.md) | Reviewer and administrator workflows in the browser | AT-01–AT-08 |

These are **32 documented scenarios**, not 32 newly added automated tests. They describe and map the existing pytest and Playwright coverage; some scenarios share an automated test. The IDs are local to this catalog and do not replace the provisional IDs in the original SRS.

## Execution

From the project root, run the backend suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_dam.py -q
```

To run one mapped test, use its exact node ID, for example:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_dam.py::test_req03_offsets_unicode_and_abbreviation -q
```

For browser coverage, first build the frontend, then run its existing workflow test:

```powershell
cd frontend
npm.cmd run build
$env:DAM_BROWSER_CHANNEL='msedge'
npm.cmd run test:e2e
```

On platforms without Edge, omit DAM_BROWSER_CHANNEL and install Playwright Chromium with `npx playwright install chromium`. The browser test starts its own isolated server on port 8001. Backend tests use temporary databases. Both use test credentials and offline/mocked sources.

## Recording results

The case specifications are ready for execution. Record date, environment, observed result, Pass/Fail/Blocked, evidence and defect ID in the execution tables in each folder. No new execution or stakeholder approval is claimed by creating this catalog. Earlier measured results are in [docs/TEST_RESULTS.md](../docs/TEST_RESULTS.md).

Unit/integration/system automation is in [backend/tests/test_dam.py](../backend/tests/test_dam.py). Acceptance workflow automation is in [frontend/tests/workspace.spec.js](../frontend/tests/workspace.spec.js). Browser checks support acceptance review; final acceptance requires a stakeholder to review the results and sign off. Live accuracy, production load, TLS and PostgreSQL need the separate validation described in [docs/DELIVERY.md](../docs/DELIVERY.md).
