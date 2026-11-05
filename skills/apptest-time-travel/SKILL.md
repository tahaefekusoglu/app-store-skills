---
name: apptest-time-travel
description: "Tests date and time behaviour: date bugs, DST, midnight, month end, Feb 29, clock moved back, app unopened for 30 days, time zone change. Never touches the Mac's clock."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-time-travel: time travel

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.10 · group principles
`../apptest/shared/test-methods.md` (T1–T10) · rules in locale-time (LT-10 day
counting, LT-50 fixed time zone) · report `../apptest/shared/report.md`.
Talking with the user: `../apptest/shared/CONVENTIONS.md` §11 (when to ask, status lines, one next step).

**Default contract:** Scans and suggests writing / running tests; does not
quietly add a clock hook to app code (T3). A test it writes goes into the
project's own test folder, with the user's approval.

## When

- The app has date-dependent rules: period / cycle, due date, subscription
  length, streak, reminder, a "today" list, scheduled notifications.
- A report of "it broke on the 31st / at DST / abroad".
- Date code changed (time zone tour before release).

## Out of scope

- Date / number FORMATTING and translation → locale-time. This member MOVES time
  forward and looks at the result.
- A test depending on the real date (a test that fails at month end) →
  test-health / test-strategy.

## Step 0

CONVENTIONS §5. The scan is light (read-only). The time zone tour runs the full
test suite several times: time estimate and approval (§6).

## Member-specific principles

- **TT-P1** NEVER touches the Mac's clock or time zone; time only changes inside
  the test process (the app's clock hook, the test framework's fake clock, the
  `TZ=` environment variable, `SIMCTL_CHILD_TZ` for the simulator).
  *Why:* changing the system clock breaks signatures, certificates, the build
  cache and the user's other work; if it is not restored, nobody notices (T4).
- **TT-P2** The lack of an injectable clock is NOT a finding; just say which
  scenarios could not be tested, and suggest a small hook once.
  *Why:* the architecture decision is the user's; a `TZ=` tour and manual scenarios
  are possible in a hookless app too.
- **TT-P3** Every scenario runs in at least one zone WITH DST; a zone without DST
  is not enough on its own.
  *Why:* code that computes local date differences in hours always looks right in
  a zone without DST (e.g. a budgeting app's day count passed in Istanbul and
  shifted by a day in Berlin; that made the `TZ=Europe/Berlin` tour mandatory,
  plus California for notification times).
- **TT-P4** The clock is moved BACK as well as forward, and the user's future-dated
  data from that gap must be preserved.
  *Why:* a closed period reopening, automatic records written twice and lost
  records show up most when the clock goes back (e.g. a budgeting app's
  clock-rollback recovery).

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
technology, test framework (`has_tests`), notification capability.

## Scan

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-time-travel/scripts/tt_scan.py" <root> [--json]
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-time-travel/scripts/tt_scan.py" --moments --tz Europe/Berlin --tz America/Los_Angeles --year 2026
```

- **TT-10** (INFO) whether a clock hook exists, and its first location.
- **TT-11** direct `now()` use per file (SUGGESTION if a hook exists: a business
  rule that bypasses the hook cannot be fixed in tests; prioritize files that
  compute dates / due dates / cycles). The result is a CANDIDATE: "now" in view
  code (showing the time, animation) is not a problem, so open the file and look.
- `--moments`: for the chosen zones and years, the exact local moment of DST
  transitions (forward = 23-hour day, back = 25-hour day), month ends, Feb 29,
  year end. Scenario dates come from here, not from memory.

## Setup (good to know from the start)

1. "Now" comes from one place (a clock provider / dependency); business rules do
   not call `now()` directly.
2. Dates are stored as calendar days; day differences are computed with the
   calendar, not in hours (locale-time LT-10).
3. Scheduled work / notifications are set in local time and stay at the same local
   time across DST.
4. Moving the clock back is thought through as a state (what happens to
   future-dated records?).

## Test

Scenarios and per-technology clock-fixing patterns: `references/patterns.md`
(TT-S1 … TT-S9). In each scenario:

1. Set the clock just BEFORE the scenario moment and build the app state.
2. Advance the clock past the moment (or move it back) and call the app's "launch"
   / "recalculate" path.
3. Check: record count (duplicates / missing), the date and day count shown, the
   period boundary, notification times, invariants (can be combined with
   state-sim: add "clock forward / BACK" to the random steps).

Time zone tour (works in a hookless app too):

```sh
TZ=Europe/Berlin <project's test command>
TZ=America/Los_Angeles <project's test command>   # DST transition on different days
TZ=Pacific/Kiritimati <project's test command>     # UTC+14: UTC and local day differ
```

Time zone for the app on a simulator: `SIMCTL_CHILD_TZ=<zone> xcrun simctl
launch <UDID> <bundle>` (temporary simulator, `sim_session.py`).

## Release (before submitting)

1. If date code changed: a full test tour in two zones with DST.
2. If notification times changed: is the local time the same on transition days?
3. Did any of the business rule files in TT-11 change in this version?

## Report

`shared/report.md`. Per scenario: id (TT-S…), zone, moment, expected, observed,
how to reproduce (clock + zone + steps, T5). If there is no hook, a list of
"scenarios that could not be tested" as INFO.
