---
name: app
description: "Short commands for the app-store-skills family: /app t double, c privacy, d design. t = run and try the app, c = check rules and code, d = Apple design suggestions. Also t quick, t release, t rejected."
argument-hint: "[t|c|d] [name] [project path]"
allowed-tools:
  - Skill
  - Read
  - Bash
---

# app: short names

Routes only: turns a short name into a member and calls it with the `Skill` tool. The member's own contract applies.

## Reading rule

- Form: `<letter><space?><name or number> [project path]`. "t double", "t double tap", "t 3" and "t3" are the same.
- The first word of the name is enough; case is ignored. `k` still works for `c`.
- Several names run in order ("c privacy data", "t double + c copy").
- No project path means the working folder. The path and any extra words go to the member as `args`.
- In chat this runs only on a known name. A lone "t", or similar words inside a sentence, is not a call.
- No match or an empty call: show the list below, suggest the closest name, run nothing.

## t: runs and tries the app

| # | Short name | Member | What it does |
|---|---|---|---|
| 1 | t crawl | apptest-crawl | Taps every control, collects overflows and errors |
| 2 | t sim | apptest-state-sim | Seeded random use; checks that invariants hold |
| 3 | t double | apptest-rapid-input | Double taps, back while saving, duplicate records |
| 4 | t time | apptest-time-travel | Month ends, daylight saving, clock moved back |
| 5 | t upgrade | apptest-upgrade | New version on old version's data |
| 6 | t device | apptest-device-tour | End-to-end flows on a real simulator |
| 7 | t persona | apptest-persona | Main tasks as different kinds of user |
| 8 | t lifecycle | apptest-lifecycle | Background, killed, cold start, app lock |
| 9 | t visual | apptest-visual | Pixel comparison with the previous version |
| 10 | t network | apptest-network-chaos | Slow, broken and malformed network |
| 11 | t health | apptest-test-health | Stale, skipped and flaky tests |
| 12 | t plan | apptest-test-strategy | Which test closes which risk |

Combined:

| Short name | What it does |
|---|---|
| t quick | Static scan only: `python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/run_all.py" <root>`. Does not run the app. |
| t suggest | `apptest` Test mode: suggests at most 3 members for the change |
| t full | The full tour of `apptest` Release mode: scan plus simulator tours (30 to 90 minutes) |
| t release | `apptest` Release mode: estimates time, offers quick or full |
| t rejected | `apptest` Rejection mode: a plan from Apple's message |
| t new | `apptest` Setup mode: first-day decisions for a new project |

## c: checks rules and code

| # | Short name | Member | What it does |
|---|---|---|---|
| 1 | c ready | apptest-store-readiness | Submission settings, icon, Info.plist, TestFlight |
| 2 | c privacy | apptest-privacy-permissions | Permissions, privacy label, privacy manifest |
| 3 | c money | apptest-monetization | Purchases, subscriptions, Restore |
| 4 | c account | apptest-network | Account deletion, sign-in, offline, secrets |
| 5 | c product | apptest-product-fit | Web wrappers, copycats, name and metadata |
| 6 | c content | apptest-content-safety | Reporting, AI output, age rating |
| 7 | c layout | apptest-layout-a11y | Large text, screen sizes, VoiceOver |
| 8 | c locale | apptest-locale-time | Translation, dates, money format, right-to-left |
| 9 | c data | apptest-data-integrity | Migrations, backups, data loss |
| 10 | c input | apptest-input-actions | Validation, decimal comma, delete confirmation |
| 11 | c copy | apptest-copy-audit | Does the text tell the truth, wordiness |
| 12 | c assets | apptest-store-assets | Store images, sizes, alpha |

## d: Apple design (suggestions)

| # | Short name | Member | What it does |
|---|---|---|---|
| 1 | d audit | apple-design-audit | Compares an existing app with the HIG; differences are suggestions |
| 2 | d design | apple-design-advisor | Suggests a new screen or app; your decision wins |

Empty `/app`: show these three tables briefly and ask which one.
