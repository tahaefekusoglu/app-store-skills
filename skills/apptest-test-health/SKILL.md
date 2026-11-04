---
name: apptest-test-health
description: "Use when looking for skipped, flaky or stale tests: leftover only / fit, fixed sleeps, UI test ids that no longer exist, tests tied to today's date, the time zone or the real network, empty tests."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-test-health: the health of the tests

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.3 (principles 11, 14, 15) ·
group principles `../apptest/shared/test-methods.md` (T5, T6, T9) · report
`../apptest/shared/report.md`.

**Default contract:** Gives a report. Does NOT delete, disable or loosen tests
(TH-P1, T9); a suggested fix is applied only with the user's approval.

## When

- "Tests sometimes fail", "fails in CI, passes for me".
- UI / element ids changed; device tests have not run for a long time.
- Before release: finding stale device tours before running them (saves hours
  of running).

## Out of scope

- Writing new tests / test strategy → test-strategy.
- App bugs: if a test fails correctly, the topic belongs to the relevant
  member, not this one.

## Step 0

CONVENTIONS §5. The static scan is read-only. The flakiness trial (below) runs
tests, so it is heavy work: lock, temporary simulator (device tests), time
estimate (§6).

## Member-specific principles

- **TH-P1** Does not delete, disable or loosen a test (T9); it only flags it,
  and suggests the cause and the way to fix it.
  *Why:* disabling a test "to turn red into green" hides the bug.
- **TH-P2** Treats a silently skipped test (via a tag, `skip`, an unconditional
  skip, or a step skipped by a "tap if present" helper) as being as important
  as a broken test.
  *Why:* a skipped test looks like a passed one (e.g. in a budgeting app, the
  crawl test never ran without `--run-skipped`, and a tour step looking for a
  removed pill was silently skipped through `tapIf`).

## Profile

`python3 -I ~/.claude/skills/apptest/shared/profile.py <root>` → test flags,
technology (test tool).

## Setup (good to know from the start)

1. **Element ids are constants defined in one place** (if the component and the
   test share a constant, changing the id breaks the build instead of leaving
   a test silently stale).
2. **Wait on conditions**, not fixed times (T6).
3. **Clock, language, time zone and network are fixed in tests** (principle 14).
4. **A skipped test has a reason and a deadline:** why, and when it will be
   turned back on.
5. **Device tours run regularly** (CI or a pre-release rule); a tour that does
   not run goes stale.

## Test (while developing)

### 1. Static scan (seconds)

```sh
python3 -I ~/.claude/skills/apptest-test-health/scripts/health_scan.py <root> [--json]
```

| Id | Topic | Severity |
|---|---|---|
| TH-10 | Element id an end-to-end test looks for is not in the app | USER BUG |
| TH-11 | Skipped / disabled test | SUGGESTION |
| TH-12 | "only / fit": other tests are silently skipped (Dart / JS) | USER BUG |
| TH-13 | Fixed-time wait | SUGGESTION |
| TH-14 | Calendar logic tested with the real date | SUGGESTION |
| TH-15 | Result depends on time zone / language | SUGGESTION |
| TH-16 | Test that makes requests to the real network | SUGGESTION |
| TH-17 | Empty test | SUGGESTION |

TH-10 looks only at END-TO-END tests (integration_test, UITests, e2e, Detox,
Maestro); ids built at runtime (string concatenation, interpolation), string
constants in the app, and elements deliberately checked as absent
(`findsNothing`, `doesNotExist`, `assertNotVisible`) are filtered out. The
output is CANDIDATES (principle 6).

### 2. Flakiness trial (runs tests; principle 13)

Run the suspect test N times (e.g. 5) under the same conditions; then in a time
zone with DST and in a different language:

```sh
for i in 1 2 3 4 5; do <test command> <test> || echo "failed: $i"; done
TZ=Europe/Berlin <test command> <test>
```

Classification: **flaky** (sometimes fails under the same conditions) ·
**environment-dependent** (time zone / language / machine) · **stale** (fails
every time, the app has changed) · **real bug** (the app is wrong). A real bug
is handed over to the relevant rule member. A suggestion for each class; applied
with the user's approval (T9).

## Release (before submitting)

1. Static scan, especially TH-10: fix stale device tours before running them
   (e.g. in a budgeting app, 4 tours turned out stale in one pre-release round).
2. The list of skipped tests and their reasons (TH-P2).
3. Report.

## Report

`shared/report.md`. Also: if a flakiness trial was done, the failure count in N
runs and the class, per test.
