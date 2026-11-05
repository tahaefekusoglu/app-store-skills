---
name: apptest-test-strategy
description: "Use when asking which tests an app needs, where the riskiest untested code is, or for a test plan: layer map, money / date / data modules without tests, tests not run in CI, which member closes which risk."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-test-strategy: test strategy

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.10 (principles 11, 14, 15) ·
group principles `../apptest/shared/test-methods.md` · report
`../apptest/shared/report.md`. No App Store rule of its own; 2.1 (crashes,
missing features) indirectly.
Talking with the user: `../apptest/shared/CONVENTIONS.md` §11 (when to ask, status lines, one next step).

**Default contract:** Gives a report and a plan; does NOT run tests and does
NOT write tests (it writes them if the user asks; CONVENTIONS §5.5).

## When

- A new project needs a test setup.
- "Which tests should I write", "why are the tests misleading", "what should I
  run before release".
- A bug reached production and no test caught it.
- Before release (the family head's Release mode), to list which tours to run.

## Out of scope

- The health of individual tests (flaky, stale, skipped) → test-health
  (this member points them out, that member classifies them).
- Running the tests themselves → the relevant test method member.

## Step 0

CONVENTIONS §5. Read-only.

## Member-specific principles

- **TS-P1** Does not suggest changing the project's test tool or framework;
  looks for the most value with the current tool.
  *Why:* changing tools is expensive and breaks principle 2.
- **TS-P2** Measures the CLASSES of bugs caught, not the test count or
  coverage percentage.
  *Why:* high coverage can miss clock / data / concurrency bugs (e.g. in a
  budgeting app, with hundreds of tests passing, month-end and DST bugs only
  surfaced with fixed-clock and time zone tours).

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
technology (tools and commands), `has_tests`, test flags, CI files;
capabilities (risk areas).

## Setup (good to know from the start)

1. **Risk first:** the areas with the most expensive bugs (money, dates,
   persistent data, purchases, sign-in) get the first tests; UI cosmetics last.
2. **Make the clock and randomness injectable** (the method is up to you):
   month-end, DST and midnight tests can only be written this way.
3. **Invariants:** rules such as "saved = shown", "total = parts", "a rejected
   action does not change data" are written once and checked at every step of
   a random use tour (state-sim).
4. **Layers and speed:** fast unit tests on every change; device tours (real
   keyboard, fonts, permissions, external links) at least before release and
   preferably in CI.
5. **Upgrade test** on every schema change, with populated old data
   (data-integrity, upgrade).
6. **Every bug found becomes a regression test** (test-methods T8).

## Test (while developing)

### 1. Static scan (seconds)

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-test-strategy/scripts/strategy_scan.py" <root> [--json]
```

| Id | Topic | Severity |
|---|---|---|
| TS-10 | Layer map + run commands | INFO |
| TS-11 | Module in a risk area (money / dates / data / purchases / sign-in) with no test matching its name | SUGGESTION |
| TS-12 | Test that checks calendar-dependent logic with the real clock | SUGGESTION |
| TS-13 | Unseeded randomness (that affects the result) | SUGGESTION |
| TS-14 | No tests at all / no tests that run on a device | SUGGESTION |
| TS-15 | No CI, or device tests do not run in CI | SUGGESTION |
| TS-16 | Skipped / conditional test markers (details in test-health) | INFO |

The output is CANDIDATES (principle 6). TS-11 is a rough measure based on name
matching (file names are split into words; model / request / response files are
excluded).

### 2. Risk → member plan

For each risk area, suggest in a table which member's tour closes it (the user
chooses, principle 3):

| Risk | Member | Tour |
|---|---|---|
| Calendar / clock | time-travel | day rollover, month / year end, Feb 29, DST, clock back |
| State / ledger / totals | state-sim | seeded random use + invariants |
| Schema / backup | upgrade, data-integrity | from every old version, with populated data |
| UI breakage | crawl, layout-a11y | tap every element; large text × small screen |
| Real device behaviour | device-tour | clean install, permission denied, real keyboard |
| Double tap / concurrency | rapid-input | save / pay / delete |
| Lifecycle | lifecycle | background, close and reopen, memory |
| Network | network-chaos | no network / slow / errors |
| User types | persona | beginner, large text, another language |
| The tests themselves | test-health | flaky, stale, skipped |

## Release (before submitting)

1. Static scan.
2. The list of tours to run before release (layer commands + chosen members),
   with a time estimate (principle 13). Device tours run on a temporary
   simulator with no user data.
3. Report.

## Report

`shared/report.md`. Also: the risk → member plan table (chosen ones marked) and
the commands per layer.
