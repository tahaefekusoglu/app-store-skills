---
name: apptest-persona
description: "Use when simulating different kinds of users on the main tasks: first-timer, hurried, largest text, VoiceOver, small screen, permission denied, slow network. Reports unreachable goals, dead taps and dead ends."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-persona — journeys by user type

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.3 · group principles
`../apptest/shared/test-methods.md` (T1–T10) · measurement rules in
layout-a11y · report `../apptest/shared/report.md`.

**Default contract:** Produces the persona plan and hook inventory and adapts the agent
template to the project; writes to the test folder only with approval. Does not add hooks to
app code (T3). If it runs on a simulator, a temporary simulator
(`sim_session.py`).

## When

- Before the first release: "can someone new find the main jobs in this app?"
- Setup, navigation or the main screen changed.
- Large text, VoiceOver, a new language or a paid / free split was added.
- Feedback that "users can't find X".

## Out of scope

- Tapping every element one by one → crawl. Running a specific flow with
  fixed steps → device-tour. Measurement rules (contrast, 44 pt, truncated text) →
  layout-a11y; this member sees them only ON THE PERSONA'S PATH and links them
  there. Double tap / backgrounding midway → rapid-input.
- Usability research with real people: this tour does not replace it;
  it is a cheap early estimate of where people will get stuck.

## Step 0

CONVENTIONS §5. The tour is long (persona × seed × goal; 5–20 min per persona on a
simulator): time estimate, approval, `caffeinate`, timeout (§6).
This member's items do not rest on an App Store rule; if a finding
touches a rule (e.g. crash → 2.1), principle 7 applies to that item.

## Member principles

- **PE-P1** Defines a persona by behaviour (beginner, hurried, large
  text / VoiceOver user, in another language, on a slow network); not by an age,
  gender or occupation stereotype.
  *Why:* a stereotype produces the wrong scenario and hurts people: people of every age
  use large text, while the name "elderly" hides the behaviour that should be tried
  (text scale, VoiceOver).
- **PE-P2** Reports where it got stuck by step and screen; does not leave a subjective
  comment such as "confusing" without evidence.
  *Why:* principle 6; a finding without a step sequence cannot be reproduced.
- **PE-P3** Measures goal success by DATA or SCREEN state ("expense
  count went up", "screen X is visible and tappable"); "Save was tapped"
  is not a measure, and a screen sitting in a back tab does not count.
  *Why:* tapping a button with no record created is exactly the bug to catch.
- **PE-P4** A journey runs in at most three languages: the development language, a language whose
  text runs long, and a right-to-left language if any. The remaining languages are scanned with crawl /
  visual / locale-time.
  *Why:* a journey takes minutes per language; a new language's bugs
  (truncation, reversed layout) are found by screen scanning, not by navigating.
- **PE-P5** Truncated text and layout findings are definitive only with the REAL font
  (simulator / device); those found with a test font are candidates.
  *Why:* e.g. the Flutter widget test font draws letters as squares,
  making text look wider than it really is.
- **PE-P6** Separates the agent's error from the app's error: a finding is not written until it
  appears in at least two seeds and setup errors (accessibility tree off,
  test clock different from the app clock, unfaked external link,
  wrong word list) are ruled out.
  *Why:* e.g. in a budgeting app's tour records were rejected as "before the start
  of use"; the cause was the test clock differing from the real today, not
  the app. Details: last section of `references/personas.md`.

## Profile

`python3 -I ~/.claude/skills/apptest/shared/profile.py <root>` →
technology (template), `languages`, `purchases` / `subscriptions`, `account`, `network`,
`permissions`, `has_tests`.

## Scan (plan and hooks)

```sh
python3 -I ~/.claude/skills/apptest-persona/scripts/pe_plan.py <root> [--json]
```

- **PE-10** (INFO) Hooks that set a persona up: test entry point, in-memory
  data, clock, purchase / external link / network / notification fakes; each one is
  "found (first place)" or "not found → this persona cannot be tested". Absence is NOT
  a finding; a hook is suggested to the user once, only if it cannot be solved in test code alone.
- **PE-11** (SUGGESTION) Personas in existing tests named by a stereotype
  ("yaşlı", "elderly", "grandma", "ev hanımı"…); comment lines do not count.
- **PE-12** (INFO) Existing persona / journey test: extending it may be cheaper
  than writing a new one.
- **Persona plan:** dimensions that fit the app (experience, pace, reading, screen,
  language, account, session, network, permission) and four personas (A–D); every level in at least one
  persona, the two riskiest pairs (largest text + smallest screen;
  VoiceOver + first launch) together. The plan is a suggestion; the user changes it.

The result is a CANDIDATE: verify that a "found" hook in PE-10 really is a test entry point
by looking at the first place (a dependency override path in app code
counts too).

## Setup (good to know from day one)

1. For tests the app opens from ONE entry point, in the desired state:
   empty or seeded rich data, fixed clock, paid / free, language.
2. External effects can be faked: purchase, external link and sharing,
   notification permission, network (including delay and errors).
3. The on-screen words for main jobs are, in every language, the words a user would look
   for (not code names); accessibility labels match the visible text.
4. Every modal / sheet closes with back or close (no dead ends).

## Test

Details: `references/personas.md` (dimensions, goal, agent, measurement,
sorting out agent errors) · `references/templates.md` (XCUITest: every
technology; Flutter; manual scenario for a UI with no tree; temporary simulator).

1. `pe_plan.py` → persona plan + hook inventory; if a hook is missing, tell the user which
   persona drops out.
2. Goals (5–8 per persona): main jobs, word sequence in the persona's language,
   data / screen success measure (PE-P3). A goal that does not fit the persona drops out ("last
   month" on first launch).
3. Adapt the agent (template), at least 2 seeds per persona; a budget of 40
   steps per goal, each goal starts clean.
4. A fast tour first (widget / unit level, if any), then personas C and D on a simulator
   with the real font (PE-P5).
5. Sort out (PE-P6), then write findings:

| Id | What | Severity |
|---|---|---|
| PE-20 | Goal not reached (≥2 seeds); if there is a concrete cause (unlabelled, off-screen, truncated, locked, no path after permission denial) | USER BUG, otherwise SUGGESTION |
| PE-21 | Reached, but longer than 2× the shortest path | SUGGESTION |
| PE-22 | Dead tap (same element, ≥2 seeds) | SUGGESTION; USER BUG if it promises an action |
| PE-23 | Going back and forth between the same screens ≥3 times | SUGGESTION |
| PE-24 | Dead end: no back / close | USER BUG |
| PE-25 | Crash / uncaught error during the journey | USER BUG |

Measurement issues on the path are written under the layout-a11y id, with the note
"(on persona C's path)" (§2: the same finding once).

## Release (before submitting)

1. Personas A and C clean on the simulator: all main jobs are reachable,
   no PE-24 / PE-25.
2. If there are paid features, the free persona can do the basic jobs and reach the
   lock screen; the expired-subscription persona can see their data.
3. A small regression test was suggested for every PE-20 / PE-24 found (T8).

## Report

`shared/report.md`. One block per persona: persona (with its dimensions), seeds,
goal table (✓ / ✗, steps, dead taps, backs), findings (id ·
goal · last 5 steps · screen · seed · re-run command, T5). At the end a
cross-persona summary: which goal failed for which persona. A persona that could not run because of a missing
hook is INFO: "could not test: <hook>".
