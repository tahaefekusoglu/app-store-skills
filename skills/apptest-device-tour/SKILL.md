---
name: apptest-device-tour
description: "Runs main flows end to end on a real simulator: temporary simulator, clean install, permission denial, real keyboard, large text / dark mode / language. integration_test, XCUITest, Detox, Maestro. E2E test."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-device-tour — real simulator tour

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.3 (§5, §6, §7) · group principles
`../apptest/shared/test-methods.md` (T1–T10) · report
`../apptest/shared/report.md`. Shared tool: `../apptest/shared/sim_session.py`.

**Default contract:** Runs the tests; does not add hooks to app code
silently (T3). The user's simulator / device is not used (DT-P1).

## When

- Before release (device tours): the real keyboard, permissions, fonts and external
  links show up only here.
- A flow passes in a widget / unit test but is broken for users.
- Integration tests have not run for a long time (first find the
  stale ones with test-health TH-10).

## Out of scope

- Tapping every element one by one → crawl. Image comparison → visual.
  Store screenshots → store-assets. This member runs FLOWS.

## Step 0

CONVENTIONS §5, heavy work: lock, temporary simulator, processes with PIDs,
free disk check; time estimate and approval (§6).

## Member principles

- **DT-P1** Does not use the user's simulator; runs every tour in its own temporary
  simulator (`sim_session.py`).
  *Why:* the app is reinstalled, settings and data get polluted (e.g. in a budgeting
  app's tours the user's iPhone 18 Pro was never used).
- **DT-P2** A stuck step does not hold up the tour: every step has a timeout;
  when stuck, it says "stuck: <step>" and moves on, splitting the tour and
  re-running the remainder.
  *Why:* one hang locks the whole tour and session (e.g. 15-minute freezes
  from display sleep and themes failing in a chain).

## Profile

`python3 -I ~/.claude/skills/apptest/shared/profile.py <root>` → technology
(tour tool), `platforms` (iPad → also an iPad simulator), permissions (denial
path), `languages`.

## Setup (good to know from day one)

1. **Element ids** (Key / testID / accessibilityIdentifier) from the start;
   the tour relies on ids, not text, so it does not break when the language changes.
2. **A launch path with demo data and a fixed clock** (in-memory database,
   launch argument): the tour starts from the same state every time.
3. **Ability to fake external effects** (external link, sharing, purchase,
   notification permission): otherwise the tour falls into Safari and hangs (T2; e.g. a budgeting
   app's `externalLinkOverride`).

## Test

### 1. Session

```sh
U=$(python3 -I ~/.claude/skills/apptest/shared/sim_session.py create --project <root> --software-keyboard)
# … tour …
python3 -I ~/.claude/skills/apptest/shared/sim_session.py cleanup --project <root> --udid "$U"
```

`--software-keyboard`: makes the on-screen keyboard really open (for keyboard scenarios);
the old setting is saved and cleanup restores it. If screenshots are needed,
`--status-bar`.

### 2. Run (by technology; T10)

| Technology | Command |
|---|---|
| Flutter | `caffeinate -dimsu flutter test integration_test/<file> -d $U` |
| SwiftUI / UIKit | `caffeinate -dimsu xcodebuild test -scheme <scheme> -destination "id=$U" -only-testing:<UITest target>` |
| React Native (Detox) | `caffeinate -dimsu npx detox test -c <configuration>` (device: $U) |
| Maestro | `caffeinate -dimsu maestro --device $U test .maestro/` |

`caffeinate`: if the Mac display sleeps the simulator stops producing frames and the tour
freezes; it applies only for the duration of the command (T4). Run long tours section by section
(per file / scenario) and in the background; if interrupted, continue from the
remaining section (§6).

### 3. Scenarios (at least these in every tour)

- **Clean install:** first launch, setup flow, empty states.
- **Permission denial:** `xcrun simctl privacy $U revoke <service> <bundle>` →
  does the app work when the feature is denied, does it direct to Settings
  (services: `xcrun simctl help privacy`; the simulator has no camera).
- **Real keyboard:** the keyboard opens in every field, the field stays above the keyboard,
  right keyboard type, closes on tapping outside (e.g. a budgeting app's keyboard tour).
- **Large text / dark mode / language:** `xcrun simctl ui $U content_size
  accessibility-extra-extra-extra-large`, `appearance dark`; language via a launch
  argument (locale-time). The main flow in at least one combination.
- **Main flows:** the app's 3–5 most valuable flows end to end.

## Release (before submitting)

1. test-health TH-10: fix stale tours first (saves time over running them).
2. All device tours on a temporary simulator; re-run a failed tour section to
   separate flaky from real (test-health).
3. Cleanup (`sim_session.py cleanup --udid "$U"`) and report.

## Report

`shared/report.md`. Per tour: passed / failed / stuck (step), duration,
device · iOS · language · text size · appearance. A re-run command for every failed
step (T5).
