# App Store Skills

Claude Code skills for building, testing and shipping iPhone and iPad apps.

Use them from the first day of a project, not only the day before submission. They help you make the decisions that are expensive to change later, test what you just wrote, and catch rejection reasons before Apple does.

```
/app t new       starting an app: what to get right on day one
/app d design    which screens and system components to use
/app t suggest   you changed some code: what to test now
/app t double    double taps, taps while saving, duplicate records
/app t quick     fast static scan of the whole project
/app t release   the full tour before you submit
/app t rejected  Apple said no: a plan from the rejection message
```

## Contents

- [Install](#install)
- [Use them while you build](#use-them-while-you-build)
- [Use them before you submit](#use-them-before-you-submit)
- [Use them after a rejection](#use-them-after-a-rejection)
- [All skills and commands](#all-skills-and-commands)
- [Reading the results](#reading-the-results)
- [How the skills behave](#how-the-skills-behave)
- [Scope](#scope)
- [How this was tested](#how-this-was-tested)
- [Contributing](#contributing)

## Install

**As a plugin** (Claude Code 2.1 or newer, easiest to keep up to date). Run these inside Claude Code:

```text
/plugin marketplace add tahaefekusoglu/app-store-skills
/plugin install app-store-skills@app-store-skills
```

`/app` then works as usual. If another command already uses that name, use `/app-store-skills:app`.

**By copying**:

```sh
git clone https://github.com/tahaefekusoglu/app-store-skills.git
cd app-store-skills
python3 tools/install.py
```

This copies the skills to `~/.claude/skills`. It replaces only the folders this repo ships and leaves your other skills alone.

**Requirements**

| For | You need |
|---|---|
| Static scans | Python 3.9 or newer, no packages |
| Simulator tours and templates | macOS and Xcode, plus your project's own tools (Flutter, Node...) |
| Reading Apple's rules and design guidelines | Internet. Without it, skills say they could not check instead of guessing |

Run the commands from your app's folder, or add a path: `/app t quick ~/code/my-app`.

You do not have to use `/app`. Asking in your own words also works, such as "does my app lose data after this schema change?". Claude picks a skill on its own most of the time, not always, so use `/app` when you want a specific one.

## Use them while you build

### Starting an app

`/app t new` gives you a short list of things that are cheap to decide now and expensive later, fitted to your app:

- iPad support, and whether your iPhone app also appears on Mac and Vision Pro
- whether text can be translated later without touching hundreds of strings
- whether date logic can be tested, which means the clock can be changed in tests
- what large text and dark mode will do to your layouts
- where data lives, how old data moves when the schema changes, how people delete it
- whether you need an account at all, and what that requires
- how you will charge, and how people restore purchases
- which permissions you ask for, when, and what happens if someone says no

Most skills also have a Setup section with advice for their own area. For example, `/app c locale` explains why "tomorrow" must not be calculated by adding 24 hours.

### Designing a screen

`/app d design` suggests navigation, screens and system components, with the SwiftUI, Flutter or React Native equivalent, and points to the Apple guideline behind each suggestion. It reads your existing theme first and fits in with it.

It only suggests. If you say "do it my way", it does, and it mentions a difference from Apple's guidelines at most once. The single exception is App Store rejection rules: it will not write a design that breaks one, such as an account with no way to delete it, but it will offer the closest design that passes.

### After you write some code

`/app t suggest` looks at what changed and suggests at most three checks, each with a reason. For example, date math leads to `t time`, and a new form field leads to `c input`.

Or go straight to the one you need:

| You just... | Run | It looks for |
|---|---|---|
| added a form or a save button | `c input`, `t double` | decimal comma bugs, money stored as a float, double taps creating two records |
| changed the database schema | `c data`, `t upgrade` | destructive migrations, old versions' data failing to open |
| added date or time logic | `t time`, `c locale` | month ends, Feb 29, daylight saving, the clock moved back |
| added a purchase or paywall | `c money` | missing Restore, missing subscription terms, hardcoded prices |
| added login | `c account` | missing account deletion, sign-in rules, hardcoded secrets |
| added a permission | `c privacy` | missing usage text, asking too early, privacy manifest |
| added user comments or AI output | `c content` | reporting and blocking, age rating answers |
| added a screen | `c layout`, `t crawl` | clipped large text, unlabeled buttons, overflows, crashes |
| added network calls | `t network`, `c account` | endless spinners, lost data on a dropped connection |
| wrote new text | `c copy` | text that promises something the code does not do |

### Setting up tests

These skills give you templates and adapt them to your project. They write into your project only when you approve.

| Run | What you get |
|---|---|
| `t plan` | Where your riskiest untested code is, and which test closes which risk |
| `t crawl` | A test that taps every control and reports crashes and overflows |
| `t sim` | Seeded random use of your app that checks your rules hold after every step |
| `t persona` | Main tasks walked as different users: first-timer, hurried, largest text, VoiceOver |
| `t lifecycle` | Backgrounding, being killed, cold start, app lock |
| `t visual` | Pixel comparison of screens with the previous version |
| `t health` | Skipped, stale and flaky tests in the suite you already have |

## Use them before you submit

1. `/app t quick` runs every static scan in about a minute and gives one report. It does not run your app.
2. `/app t release` estimates the time and lets you choose quick or full.
3. `/app t full` adds simulator tours and takes roughly 30 to 90 minutes.

The tour covers submission settings, privacy, monetization, accounts, content rules, store fit, layout, languages, copy, data safety and tests, then device tours, upgrade from the previous version, and store screenshots. Each skill reads Apple's current rules first.

Nothing is uploaded or submitted. Those steps stay with you.

## Use them after a rejection

Run `/app t rejected` and paste Apple's message. You get the current text of each cited guideline, what Apple most likely saw, where that is in your code, ways to fix it, and a draft reply for App Store Connect that you send yourself.

## All skills and commands

`/app` alone lists these. Numbers work too: `t3` is `t double`. The first word of a name is enough.

### t: run and try the app

| Command | Skill | What it does |
|---|---|---|
| `t crawl` | `apptest-crawl` | Taps every control; collects overflows, errors and crashes |
| `t sim` | `apptest-state-sim` | Seeded random use with invariant checks |
| `t double` | `apptest-rapid-input` | Double taps, back while saving, duplicate records |
| `t time` | `apptest-time-travel` | Month ends, daylight saving, clock moved back |
| `t upgrade` | `apptest-upgrade` | New version on the old version's data |
| `t device` | `apptest-device-tour` | End-to-end flows on a real simulator |
| `t persona` | `apptest-persona` | Main tasks as different kinds of user |
| `t lifecycle` | `apptest-lifecycle` | Background, killed, cold start, app lock |
| `t visual` | `apptest-visual` | Pixel comparison with the previous version |
| `t network` | `apptest-network-chaos` | Slow, broken and malformed network, through a local proxy |
| `t health` | `apptest-test-health` | Stale, skipped and flaky tests |
| `t plan` | `apptest-test-strategy` | Which test closes which risk |

### c: check rules and code

| Command | Skill | What it does |
|---|---|---|
| `c ready` | `apptest-store-readiness` | Submission settings, icon, Info.plist, TestFlight |
| `c privacy` | `apptest-privacy-permissions` | Permissions, privacy label, privacy manifest |
| `c money` | `apptest-monetization` | Purchases, subscriptions, Restore |
| `c account` | `apptest-network` | Account deletion, sign-in, offline use, secrets |
| `c product` | `apptest-product-fit` | Web wrappers, copycats, name and metadata |
| `c content` | `apptest-content-safety` | Reporting, AI output, age rating |
| `c layout` | `apptest-layout-a11y` | Large text, screen sizes, VoiceOver |
| `c locale` | `apptest-locale-time` | Translation, dates, money format, right-to-left |
| `c data` | `apptest-data-integrity` | Migrations, backups, data loss |
| `c input` | `apptest-input-actions` | Validation, decimal comma, delete confirmation |
| `c copy` | `apptest-copy-audit` | Does the text tell the truth, wordiness |
| `c assets` | `apptest-store-assets` | Store images, sizes, alpha channel |

### d: Apple design

| Command | Skill | What it does |
|---|---|---|
| `d audit` | `apple-design-audit` | Compares an existing app with Apple's guidelines |
| `d design` | `apple-design-advisor` | Suggests a new screen or app |

### Combined commands

| Command | What it does |
|---|---|
| `t quick` | All static scans, one report |
| `t suggest` | Up to three checks for what you changed |
| `t new` | Day-one decisions for a new project |
| `t release` | Pre-submission tour; you choose quick or full |
| `t full` | Full tour with simulator steps |
| `t rejected` | A plan from Apple's rejection message |

## Reading the results

| Label | Meaning |
|---|---|
| **REJECTION RISK** | Apple could reject the app for this |
| **USER BUG** | Users can lose data or hit a real defect |
| **SUGGESTION** | Worth considering; your call |
| **INFO** | For your awareness |

**Findings are candidates, not verdicts.** Scans search code and text patterns; they do not understand your app. Each skill explains how to confirm a finding. On an app that is already live, a rejection risk is first suspected to be a false alarm.

"Nothing found" and "did not run" are different results. A report can say:

- **clean**: it checked and found nothing
- **not applicable**: it does not apply here, such as a network check on an offline app
- **could not check**: for example, there was no internet
- **error**: the check itself failed
- **partial**: only part of a large file was read

**To stop seeing a finding you have decided to accept**, add it to `.apptest/profile.md` in your project:

```markdown
## Suppressed
- DS-16 — we use our own icon set (2026-11-04)
- LT-* — this app stays in one language
```

Suppressed rejection risks stay visible as a count, labelled as rejection risks.

`t quick` exits 0 when the scan ran, whatever it found, and says so when some files were read only in part. It exits 2 on wrong usage and 3 when a member could not run. With `--json`, `execution_complete` means every member ran, `coverage_partial` lists what was not read in full, and `complete` is true only when both are clean.

## How the skills behave

- **They report; they do not change your code**, unless you ask.
- **They leave your things alone.** Tours use a temporary simulator with demo data and delete it afterwards. They do not use your own simulator or real user data, and they never send faults to a production server.
- **They read Apple's rules every time**, because Apple changes them. The list in this repo is only an index.
- **Apple's Human Interface Guidelines are advice.** Design differences are suggestions and a deliberate design is not an error. App Store rejection rules are the exception.
- **They do not push themselves on you.** A skill may suggest itself in one line; long jobs wait for your yes.

To make Claude always ask before using one of these skills on its own, add this to `~/.claude/CLAUDE.md`:

```markdown
Before using an `apptest*` or `apple-design*` skill on your own, ask in one line.
Do not ask if I called it with `/app` or by name.
```

### Languages

The skills are written in English. Claude replies and writes reports in the language you use, though raw script output stays in English.

App text is recognized in English, Turkish, German, Italian, Spanish, French and Portuguese, including the list of buttons the crawl test must not press. To add a language, edit `skills/apptest/shared/terms.py`.

### Your own command names

`python3 tools/install.py --overlay <folder>` applies a personal layer without changing the repo. The folder may hold `app-SKILL.md` (your own short commands) and `descriptions-<lang>.json` (skill descriptions in your language).

## Scope

**Built for** iPhone and iPad apps on the App Store. These project types are recognized: SwiftUI, UIKit, Flutter, React Native and Expo, Kotlin Multiplatform, .NET MAUI, Capacitor and Cordova, Unity, Godot, and libGDX.

**Not for:**

- Mac-only apps. Scans say "Not applicable"; the design skills still work.
- Google Play.
- Server or web projects on their own.

**Not a guarantee.** A clean report does not mean Apple will approve your app, and it does not replace testing on real devices.

## How this was tested

- **Seeded defects.** Every rule in the scan scripts has a tiny project with that defect in `tests/detection/`, and CI fails if a rule has no case or stops firing. Healthy Swift and Flutter projects must stay free of rejection risks and user bugs. Three rules need live network access and are checked by hand: `SR-51`, `PP-60` and `PP-61`.
- **Real projects.** Scans ran read-only on about 50 open-source apps. False alarms found there became regression tests in `skills/apptest/shared/regressions.py`.
- **Real runs of the test templates.** `skills/apptest/shared/proof/` builds a small app with deliberate defects, in SwiftUI (XCUITest templates) and in Flutter (Dart templates). Each template must pass on the clean app and fail on the broken one, and part of each run happens on a temporary simulator.
- `skills/apptest/shared/selftest.py` checks that the scripts run on your OS and Python version.

**Known limits**

- A seeded defect proves a rule can fire. Real projects are more varied, so scans still miss things and raise false alarms.
- The TypeScript, Jest, Detox and Maestro templates are not exercised by the proof apps. Check them in your project.
- The fault-injection proxy has been used only with the proof app.
- Development happened on macOS. Linux and Windows are covered only by the CI workflow in this repo.
- Claude's automatic choice of skill was measured on Sonnet only, in a partial run: it missed some requests, but no request went to a wrong skill and unrelated requests did not trigger one.

## Contributing

Bug reports are most useful with the finding's id, such as `SR-22`, and the code it pointed at. False alarms count as bugs.

Before sending a change:

```sh
python3 skills/apptest/shared/selftest.py
python3 -B skills/apptest/shared/regressions.py
python3 -B tests/detection/run.py                            # if you changed a scan
sh skills/apptest/shared/proof/run.sh <empty folder>         # if you changed an XCUITest template (macOS)
python3 -I skills/apptest/shared/proof/flutter/run.py <empty folder>   # if you changed a Dart template (add --device for a simulator run)
```

A new rule needs a seeded case in `tests/detection/cases.py`, or the detection run fails.

When you fix a false alarm, add a test that reproduces the real case, then undo your fix and confirm the test fails. The family's writing rules are in `skills/apptest/shared/CONVENTIONS.md`.

Skill descriptions must stay short (about 250 characters): all skills share a small listing budget in Claude Code, and a long description pushes others out.

## License

MIT. See [LICENSE](LICENSE).
