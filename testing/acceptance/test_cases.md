# Acceptance testing cases

Scope: user-visible reviewer and administrator workflows. Build the dashboard before execution. Use a disposable test environment with administrator access, offline sources and the default threshold 0.5. For local manual use, bootstrap credentials with `manage.py init`; do not copy passwords into this document.

The [existing Playwright workflow](../../frontend/tests/workspace.spec.js) checks these flows together using its isolated browser-test environment. These eight scenarios are not eight separate automated scripts. Stakeholder acceptance remains pending until a reviewer records results and signs off.

Sample text: `The capital of France is Paris. The capital of Australia is Sydney. Earth orbits the Sun. The Moon is made of cheese.`

| ID / requirements | User goal / preconditions | Steps | Expected result | Automation coverage |
| --- | --- | --- | --- | --- |
| AT-01 / REQ-1, REQ-2, REQ-17 | Administrator or reviewer wants to check an AI response. | Sign in; choose Verify content; click Try an example; submit verification. | Workspace opens and shows four extracted claims, with no silent rewrite of the input. | Sign-in, example submission and four-row assertions. |
| AT-02 / REQ-7, REQ-12, REQ-13 | Reviewer needs evidence for a questionable claim. | Select the Australia/Sydney claim; inspect evidence and correction; inspect or open View source. | Evidence identifies Canberra; suggested correction is separate from the original Sydney text; source link uses HTTPS. | Correction text and source URL asserted; loading the external source page requires manual verification. |
| AT-03 / REQ-6, REQ-17 | Reviewer must distinguish verdicts without guessing from color alone. | Inspect initial claim highlights and textual badges; complete AT-04 to introduce Not-Checkable. | Initial sample shows two Supported, one Contradicted and one Unsupported claim. After the override, Not-Checkable is clearly labeled and highlighted. | Supported/Contradicted/Unsupported class counts and post-override Not-Checkable count. |
| AT-04 / REQ-18 | Reviewer requests more evidence. | On the Sydney claim, choose Override verdict; select Not-Checkable; enter confidence 0.1 and reason `Browser test reviewer requests further evidence.`; save. | Selected claim reflects the new verdict; reviewer and reason are visible; original automatic verdict remains available; audit contains an override event. | Override form, review note, highlight update and audit checks. |
| AT-05 / REQ-13, REQ-18 | Reviewer completes a review and keeps a report. | Approve the verification job; export JSON. | Approval displays the reviewer's username; a `dam-<job-id>.json` file downloads. Inspect the file manually to confirm original text, evidence and override details are retained. | Approval and download filename asserted; downloaded JSON content is covered separately by backend report tests, not read by the browser test. |
| AT-06 / REQ-19, history UI | Reviewer locates content and checks trends. | Open Review history; search for `no-such-text-unique`; apply filters; open Analytics. | An explicit no-matching-jobs state appears; Analytics opens with the daily-score chart section. Manually inspect report counts against the reviewed job if performing stakeholder sign-off. | Empty history result and analytics heading asserted; numeric analytics covered by backend tests. |
| AT-07 / administration, audit | Administrator confirms policy can be saved and changes tracked. | Open Settings; save valid default settings; open Access & audit. | Visible success feedback confirms the saved policy; audit view is available and includes prior override activity. Inspect the settings-change event during manual acceptance. | Settings success message, audit heading and override-event text asserted; settings-change audit covered by backend tests. |
| AT-08 / usability, session security | User works on a narrow display and signs out. | Resize to 390 × 844; inspect navigation and horizontal overflow; restore desktop width and sign out. | Document fits the viewport without horizontal page overflow; sign-out returns to the login screen. Check keyboard navigation and actual touch usability manually. | Document-width overflow check and return to login asserted; comprehensive accessibility is not claimed. |

## Execution and stakeholder sign-off

| Case ID | Date / browser / role | Observed result | Pass / Fail / Blocked | Evidence / defect ID |
| --- | --- | --- | --- | --- |
| — | Not executed as part of catalog creation | — | — | — |

Acceptance decision: Pending.

Reviewer / stakeholder: ____________________

Date: ____________________

Conditions or unresolved defects: ____________________
