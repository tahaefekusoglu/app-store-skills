---
name: apptest-rapid-input
description: "Use when writing or running tests for double taps, taps while saving, back or background mid-save, race conditions and duplicate records or payments. Holds the write open and counts the result from the data."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-rapid-input — rapid and concurrent input

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.3 · group principles
`../apptest/shared/test-methods.md` (T1–T10) · rule member
input-actions (IA-10 double submit, IA-11 delete without confirmation) · report
`../apptest/shared/report.md`.

**Default contract:** Scans, gives a test plan and templates; writes the test to the project
only with approval. Does not add hooks to app code (T3); the fake dependency needed to hold
a write is set up in test code.

## When

- There is a button that writes a record, spends money, sends a message or deletes.
- "Sometimes it saves twice / charged me twice" reports.
- The save path, database layer or network layer changed.
- Before release: assurance for payment and main record actions.

## Out of scope

- Reading a button's guard in code (static) → input-actions IA-10;
  this member tries the same risk by RUNNING it. The same finding appears once in the report,
  under the IA id.
- The background / close-reopen transition itself (no operation running) → lifecycle.
- How network errors and slowness affect the user → network-chaos (RI-S9
  only measures duplicates on retry).

## Step 0

CONVENTIONS §5. Service-level tests take seconds; UI tests take
minutes per action (time estimate, §6). This member's items do not rest on an App
Store rule; if a finding such as a double payment touches a purchase rule,
monetization and principle 7.

## Member principles

- **RI-P1** Counts a duplicate as a finding only if a second record really appeared in the
  data; does not count visual flicker.
  *Why:* to separate a data bug that affects the user from a cosmetic difference.
  Counter: row count, calls to the fake, requests sent.
- **RI-P2** Sets up the "mid-operation" moment not by timing but by holding the
  write (a held fake dependency); then completes it deliberately.
  *Why:* the real window is milliseconds; a timing-based test passes on one
  machine and fails on another (T6, flaky test).
- **RI-P3** The expected result is the app's rule, not an assumption: for some
  actions two records are correct (two separate expenses). If the rule is not in the code or
  docs, ask the user; do not impose "there must be one record".
  *Why:* principle 2; a wrong expectation reports correct behaviour as a bug.
- **RI-P4** Tries the service level first (the same call twice at once), then
  the UI.
  *Why:* a service test is the cheapest and most definitive; even if the UI lock is missed
  (two fingers, keyboard submit, retry) it shows whether the data is
  protected.
- **RI-P5** Tries payments and purchases only with a fake; no automated tapping even with a
  sandbox account.
  *Why:* T2; a sandbox purchase also changes account state and breaks the
  next tour.

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
technology (template), `capability:database`, `purchases`, `network`, `has_tests`.

## Scan

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-rapid-input/scripts/ri_scan.py" <root> [--json]
```

| Id | What | Severity |
|---|---|---|
| RI-10 | Action sites that write / spend (per file) and actions named payment / purchase: the try list | INFO |
| RI-11 | Data-layer defence against duplicates (unique constraint, `INSERT OR IGNORE`, upsert, idempotency key); if none | INFO / SUGGESTION |
| RI-12 | Existing rapid-tap and concurrent call tests; if none | INFO / SUGGESTION |
| RI-13 | Flutter: `use_build_context_synchronously` turned off (a back-mid-operation error is not caught at compile time) | SUGGESTION |
| RI-14 | Database writes exist, no transaction block | SUGGESTION |

The result is a CANDIDATE. RI-11's "no defence" cannot see the server side; the RI-10
list relies on calls within 6 lines of the handler (a write
delegated to another file is invisible). Not every action with a payment name spends real
money (in a budgeting app "paid" is a record): open the file.

## Setup (good to know from day one)

1. A saving / paying action cannot run a second time mid-operation (in the UI
   and the service layer).
2. A repeated record-creating request does not create a second record (unique
   constraint, idempotency key or server defence), especially on a retry after a
   network error.
3. An action changing several rows together is inside one transaction.
4. If the screen has closed when the write finishes, no update is made (no state is
   written to a closed screen).
5. The writing dependency can be held in a test (a fake of the repository / client
   can be supplied).

## Test

Details and templates: `references/templates.md` (core method, scenarios RI-S1 …
RI-S9, Flutter, service level Dart / Swift / TS / C#,
XCUITest, React Native, purchases, by hand).

1. `ri_scan.py` → action list (RI-10). Money spenders first, then
   main record actions, then deletion.
2. The rule for each action: one record, or two full records (RI-P3).
3. Service level RI-S6 / S7 (cheapest), then RI-S1 … S5 in the UI,
   RI-S8 for payments, RI-S9 in networked apps.
4. In every test, count from the data (RI-P1); crash / uncaught error separately.
5. Findings: RI-20 … RI-25 (references). If the static cause is IA-10, under the IA
   id with the note "confirmed by a rapid-input test".

## Release (before submitting)

1. RI-S1 and RI-S2 on the payment / purchase button: the request goes once.
2. RI-S1, RI-S2, RI-S4 on the main record action: one record, no crash.
3. A regression test was suggested for every RI-2x found (T8).

## Report

`shared/report.md`. One row per action: action · scenario · expected
(rule) · observed counter · result; for findings, the re-run command and
the holding method (T5). Actions that could not be tried: "could not test: <reason>"
(e.g. the write cannot be held).
