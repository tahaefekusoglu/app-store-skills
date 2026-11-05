---
name: apptest-lifecycle
description: "Tests app lifecycle transitions: background, killed while suspended, cold start, memory warning, permission revoked in Settings, app lock, launch from a notification. Use for lost data or state after returning to the app."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-lifecycle — data and state across transitions

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.3 · group principles
`../apptest/shared/test-methods.md` (T1–T10) · related rules
data-integrity (persistent data), privacy-permissions (permissions), time-travel
(long background) · report `../apptest/shared/report.md`.

**Default contract:** Scans and provides a transition plan and templates; writes
tests into the project only with approval. Adds no hooks to app code (T3).
Simulator steps run on a temporary simulator (`sim_session.py`).

## When to use

- The app stores records, has forms, uses a lock / biometrics, requests
  permissions, or does work when going to the background (backup, sync).
- A report like "it was gone when I came back / it saved twice / the lock
  won't open".
- Launch, lock, backup or permission code changed.

## Out of scope

- Going to the background / back WHILE an operation runs → rapid-input (RI-S4,
  RI-S5); this member tests the transition itself with no operation running.
- Launching with an old version's data → upgrade. Clock and date calculations →
  time-travel (LC-S7 only checks whether recalculation happens on return).
- Permission descriptions and when they are requested → privacy-permissions.

## Step 0

CONVENTIONS §5. Unit / widget level takes seconds; XCUITest and simulator
transitions take minutes per scenario (§6). This member's items do not rest
on an App Store rule; if a finding touches one (e.g. crash on launch → 2.1),
apply principle 7.

## Principles specific to this member

- **LC-P1** Reports a finding as "going from which state to which state"
  (foreground → background → killed → launched), along with what was done
  before.
  *Why:* lifecycle bugs appear only on a specific transition; a finding with
  no transition cannot be reproduced.
- **LC-P2** Simulates "the system killed it" WITHOUT TELLING the app: after
  going to the background, the process is ended without running any code.
  *Why:* iOS runs no code when it kills a suspended app; a save relying on
  `willTerminate` / `dispose` / `detached` is really lost, and a polite
  shutdown simulation hides that.
- **LC-P3** The cold-start test uses a PERSISTENT store (temporary file), not
  an in-memory store.
  *Why:* an in-memory store empties on close; a "data lost" result would come
  from the test setup (same distinction as PE-P6).
- **LC-P4** Delivers transitions in the framework's valid ORDER (e.g. Flutter:
  resumed → inactive → hidden → paused and back).
  *Why:* a fake transition that skips an intermediate state creates a path that
  does not exist in reality; listeners fire wrongly or the framework asserts.
- **LC-P5** Inactive ≠ background: Face ID / a system dialog also causes
  "inactive"; the lock and the cover are tested separately.
  *Why:* e.g. in a budgeting app, treating the auth dialog's "inactive" as a
  lock event made the dialog reopen as soon as it closed; locking belongs only
  on going to the background, while the cover must also apply on inactive.

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
technology (template), `permissions`, `capability:biometric lock`,
`capability:database`, notifications, `has_tests`.

## Scan

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-lifecycle/scripts/lc_scan.py" <root> [--json]
```

| Id | What | Severity |
|---|---|---|
| LC-10 | Transition listeners (files; count of foreground-return / inactive) — test list | INFO |
| LC-11 | Text fields exist, no trace of draft protection / state restoration (inventory if present) | SUGGESTION / INFO |
| LC-12 | Saving in `applicationWillTerminate` / a termination event | SUGGESTION |
| LC-13 | Lock / biometrics exist, nothing covers content while inactive (info if present) | SUGGESTION / INFO |
| LC-14 | Permission status is read, apparently not re-read on returning to the foreground | SUGGESTION |
| LC-15 | Heavy on images / video / maps, no memory warning listener (info if present) | SUGGESTION / INFO |

Results are CANDIDATES. LC-13 looks for the cover in the handler's BODY (adding
a view, a hidden state, blur); a cover delegated to another class is invisible
to it: verify with a screenshot. LC-12 flags only termination handlers with a
save / write call in their body.

## Setup (good to know from the start)

1. Records persist at the moment of change or on going to the background; they
   are not left to the termination event.
2. Long forms and drafts come back even if the system kills the app (how much
   to keep is the app's decision).
3. A locked / sensitive app covers content while "inactive"; the lock is set
   only on going to the background.
4. Permission, date and session state are re-read on returning to the foreground.
5. Work run on going to the background (backup, sync) does not run twice on the
   second event of the same transition.

## Test

Scenarios and templates: `references/transitions.md` (states, facts from Apple's
documentation, LC-S1 … LC-S9, trigger table, Flutter, XCUITest, unit level,
React Native).

1. `lc_scan.py` → listener list and candidates.
2. Pick the scenarios that fit the app (no lock: drop LC-S2 / S8; no
   permissions: drop S5).
3. Unit / widget level first (fast), then XCUITest or a real transition on a
   temporary simulator (LC-S3, S4, S5).
4. Each scenario: set up state first → transition → look (data count, screen,
   errors, app switcher image).
5. Findings: LC-20 … LC-27 (references), with their transition (LC-P1).

## Release (before submitting)

1. LC-S3 and LC-S4: saved data is in place after a cold start.
2. If there is a lock, LC-S2 and LC-S8 are clean.
3. If permissions are used, LC-S5: no crash / dead end.
4. A regression test was suggested for every LC-2x found (T8).

## Report

`shared/report.md`. Per scenario: transition (from → to), prior state, expected,
observed, evidence (counter / screenshot / error), how to re-run (T5). A
transition that could not be tested (e.g. the app switcher in XCUITest) is an
INFO saying "must be verified by hand".
