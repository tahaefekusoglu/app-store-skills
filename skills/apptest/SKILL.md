---
name: apptest
description: "Use when Apple rejected an app (plan from the rejection message), before App Store submission (full pre-release tour) or when starting a new iOS project (day-one decisions). Head of the App Store testing family."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - WebFetch
  - WebSearch
metadata:
  version: "1.0.0"
---

# apptest: family head

The family's shared rules are in `shared/CONVENTIONS.md` (≥ 1.3); test method
members also follow `shared/test-methods.md`; each member has its own "specific
principles" in its SKILL.md. Precedence (principle 0): the user's word > project
instructions (CLAUDE.md etc.) > family > group > member; a lower layer can only
tighten. Do not run a member without reading this file and the shared rules. The
three most important rules:

1. **Never pushes** (principle 3): suggest a member to the user in ONE LINE; do
   not start a long audit unless the user asks. Block nothing.
2. **Stays out of design** (principle 2): check the outcome, do not impose a method.
3. **Check Apple every time** (principle 7): every job based on a rule starts by
   reading https://developer.apple.com/app-store/review/guidelines/ and comparing
   its "Last Updated" date with `shared/rejections.md`.

## When

| Situation | What to do |
|---|---|
| New project / big new feature | **Setup mode** (below) |
| The user finished a feature and asks what to test | **Test mode**: suggest 1–3 members based on the change |
| "I'm submitting / ready to ship? / TestFlight" | **Release mode**: full tour suggestion + time estimate |
| "Rejected" + Apple's message | **Rejection mode** |
| The user asks about one topic (e.g. "is it broken on iPad?") | Go straight to that member; the family head is not needed |

If this skill triggered on its own, first suggest in ONE line ("If you like, I can
build the app profile and run the pre-release checklist."); do not start long work
without approval.

## Step 1: Profile

```sh
python3 -I ~/.claude/skills/apptest/shared/profile.py <project_root>
```

Read-only. The "summary flags" in the output say which members are relevant (table
below). Ask about "unknown" items only if the relevant member needs them. If the
technology is not recognized, ask the user one question.

## Members

Status: ✅ ready · ⏳ planned (not written yet; for that topic see "Instead of a
planned member" in this file).

**Rule members** (WHAT must hold):

| Member | Status | Relevant when (flag) | Topic |
|---|---|---|---|
| apptest-store-readiness | ✅ | always | submission settings, rejection list, review notes, TestFlight |
| apptest-layout-a11y | ✅ | always | large text, screen sizes, iPad/Mac/Vision, keyboard, dark mode, VoiceOver, contrast |
| apptest-locale-time | ✅ | always (`languages`, date/time use) | translation, RTL, plurals, date/number formats, time zones, daylight saving |
| apptest-privacy-permissions | ✅ | always | permissions, privacy label, privacy manifest, ATT, data sent to AI, policy = behaviour |
| apptest-copy-audit | ✅ | has text | text = behaviour, tone, clutter, across languages |
| apptest-input-actions | ✅ | form / input field | validation, paste, resubmission, destructive confirmation |
| apptest-data-integrity | ✅ | local data / database | schema upgrade, backup, deletion, atomicity |
| apptest-monetization | ✅ | `purchases`, `subscriptions`, `ads` | 3.1.x, restore, gates, purchase screen |
| apptest-network | ✅ | `network`, `account` | offline, account deletion, 4.8 sign-in, demo account, hidden features |
| apptest-content-safety | ✅ | `user_content`, `ai`, kids | 1.x, age rating, report/block |
| apptest-product-fit | ✅ | always (release) | 4.2/4.3/4.1, metadata = app, regulated domains |
| apptest-store-assets | ✅ | release | screenshots / previews: size, alpha, theme×language tour |
| apptest-test-strategy | ✅ | always | test layers, fixed clock/seed, stale tests |

**Test method members** (HOW to try it):

| Member | Status | Relevant when | Method |
|---|---|---|---|
| apptest-crawl | ✅ | has UI | press every tappable element, collect overflow/exceptions/a11y |
| apptest-state-sim | ✅ | stateful app | seeded random actions + invariants |
| apptest-time-travel | ✅ | date/time behaviour | day rollover, month end, daylight saving, clock moved back |
| apptest-upgrade | ✅ | from the second version on | new version with old data, old backups |
| apptest-device-tour | ✅ | simulator available | flows on a real simulator, clean install |
| apptest-persona | ✅ | has UI | journeys to main tasks with behaviour-defined people |
| apptest-rapid-input | ✅ | form / action | double tap, back or background mid-operation, concurrent calls; result from the data |
| apptest-lifecycle | ✅ | always | background, killed while suspended + cold start, memory, lock, permission changes |
| apptest-visual | ✅ | theme / language | theme×language×device×text images, pixel diff against the previous version |
| apptest-network-chaos | ✅ | `network` | no network / slow / hung / 5xx / corrupt / 401 / dropped; mock or local proxy |
| apptest-test-health | ✅ | `has_tests` | date-dependent, skipped, stale, flaky tests |

Boundary: a rule member says "what must be right", a test member says "how to try
it". The same finding appears once in the report, under the rule member's name.

Short names: `/app` (t = test members, k = rule members, d = design). Design
commentary is not this family's job (principle 2): HIG review is
`apple-design-audit`, suggestions are `apple-design-advisor`; neither is part of the
full tour, and HIG is guidance. Rules that are rejection reasons live in this family and take priority.

## Setup mode (new project / big feature)

From the profile + the product the user describes, give a list of "**good to know
from the start**". Each item: what · why it is expensive later · one sample way to
solve it (not mandatory). Write only what fits the profile; at most ~12 items, in
order of importance. Core topics:

- Target platforms: will iPad be supported; will it appear as an iPhone app on Mac /
  Vision Pro (ON by default; R-14).
- Is text translatable from the start (moving hundreds of hardcoded strings later is
  expensive); which languages.
- Can date/time-dependent behaviour be tested (can the clock be changed).
- What happens to text size and colours at large text / in dark mode.
- Data: where it is stored, how old data moves when the schema changes, how the user
  deletes / backs it up.
- Will an account be needed (5.1.1(v): do not require one if not needed; if there is
  one, in-app deletion); 4.8 if there is third-party sign-in.
- Monetization model (3.1.x) and restoring purchases.
- What data is collected / who gets it (privacy label, ATT, 5.1.2(i) AI).
- Permissions: which, at what moment, what happens on denial.
- Test layers: what is automated, what is checked by hand.
- Store: bundle id, name, category, age, support and privacy pages (must be live
  before release).

Source: the Setup sections of the relevant members (those written) +
the "Profile" column of `shared/rejections.md`. Check Apple's rules per principle 7.

## Test mode

Look at the changed files and the profile; suggest at most 3 members, each with a
one-line reason. e.g. "You touched date math → time-travel; new form field →
input-actions." The user chooses.

## Release mode (full tour)

1. Profile + principle 7 (Apple's current rules page + "Last Updated").
2. Give a time estimate (quick: scan only ~5–15 min; full: with simulator
   tours 30–90 min). The user chooses.
3. **All static scans with one command:**
   `python3 -I ~/.claude/skills/apptest/shared/run_all.py <root> --check-links`
   (one report, the same place once, suppressed items are counted). Then the
   verification, manual list and simulator steps in each member's SKILL.md.
   Order (all members ready; if a ⏳ member is added later, use the interim path below):
   store-readiness → privacy-permissions → monetization (if any) →
   network (if any) → content-safety (if any) → product-fit → layout-a11y →
   locale-time → copy-audit → data-integrity → test-strategy → test-health → (on a full tour)
   state-sim if there is money, state or records; time-travel if there is date or time logic (if it does not apply,
   the report states why; the `TT` scan does not mean the scenarios were run) → crawl, device-tour, persona, rapid-input, lifecycle, network-chaos (if any), upgrade → visual → store-assets.
4. Each member writes its own report; at the end ONE combined report
   (`shared/report.md`): all REJECTION RISKs first, then USER BUGs,
   the same finding once.
5. No outward-facing steps (principle 16): upload / submission are only prepared.

### Instead of a planned member (interim path)

If a member is not written yet: take that member's rows in `shared/rejections.md`,
compare each with the official rule text (principle 7) and the code; report findings
with the note "manual check (member does not exist yet)". Do not invent checks
(principle 9).

## Rejection mode

1. Extract the rule numbers from Apple's message; read the CURRENT official text of
   each (principle 7).
2. For each number: what exactly Apple saw (screenshot / device / steps in the
   message), the matching code, the relevant member.
3. Ways to fix + a short, polite, concrete draft reply for Resolution Center (the
   user sends it; principle 16).
4. If needed, suggest store-readiness's Release section for the new build.

## Report

Template in `shared/report.md`. The report's Environment section must have the line
"Apple rules: Last Updated <date>, read on <today>".
