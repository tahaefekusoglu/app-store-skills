---
name: apple-design-audit
description: "Audits an existing Apple app's design against the Human Interface Guidelines: navigation, components, materials, icons, alert wording. Differences are suggestions only; deliberate design is not an error. Rejection rules are in apptest."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apple-design-audit — review an existing design against the HIG

Depends on: `../apptest/shared/CONVENTIONS.md` (§4 profile, §5 safety, §7 cleanup, §9 suppressed items) ·
sibling `../apple-design-advisor/SKILL.md` · measurements in apptest-layout-a11y.

**Default contract:** Reports, does not change code. Runs only when the user asks; it is not part of
apptest's full tour and is not suggested unprompted. apptest keeps its "stays out of design" principle;
design commentary happens only in this family.

## When to use

- "Does the design fit Apple's style?", "does it feel native?"
- Before release, if the user asks.
- A new iOS version changed the system look (e.g. Liquid Glass).

## Out of scope

- **Rejection reasons** → apptest (store-readiness, product-fit, monetization, privacy-permissions,
  network). Here only a pointer: "see this member".
- **Measured accessibility** (contrast ratio, 44 pt, cut-off at large text, VoiceOver labels) →
  apptest-layout-a11y. The same finding is not written in two places.
- Brand, color palette, font choice: these are the user's. Noted only if they conflict with a specific
  statement in the HIG and affect legibility.

## Principles specific to this member

- **TD-P1 Guidance, not rules.** Severities are SUGGESTION and INFO only; REJECTION RISK or USER BUG
  never come from this member. *Why:* the HIG describes itself as guidance and best practices; not
  following it is usually not a rejection reason. Harsh language overshadows real rejection risks.
- **TD-P2 Every difference cites a source.** A finding has the HIG page and a short summary of the
  relevant sentence; the page is read at that moment. An "in my view" comment with no source is not even
  a SUGGESTION: it goes under a separate "opinion" heading, labelled as such. *Why:* a design judgment
  without evidence turns into a debate about taste. No rules from memory: e.g. the HIG gives no fixed
  number for tabs.
- **TD-P3 A deliberate design language is not an error.** A consistent custom design language (its own
  cards, themes, icons) is not faulted for being "not like Apple"; the question is "is behaviour the user
  expects from the system lost?" (swipe back, large text, dark mode, reduce motion, system menus).
  *Why:* e.g. a budgeting app's bucket and card language is deliberate. Lost behaviour matters, not a
  different look.
- **TD-P4 Target platforms only.** The app's targets are read from the profile (iPhone, iPad, Mac,
  Watch, TV, Vision); the HIG covers all of them, and rules for an unrelated platform are not applied.
- **TD-P5 Remembers the decision, does not push.** If the user says "keep it this way", and only if they
  want, it is written to `.apptest/profile.md` under Suppressed (`DS-16 — our own icon language`); it is
  not asked again.
- **TD-P6 Every difference is labelled honestly:** seen in a code scan, a screenshot, or on a real
  device. No visual judgment without seeing the screen.

## Step 0

CONVENTIONS §5. The code scan only reads. If screenshots are needed, a temporary simulator
(`sim_session.py`, `--status-bar`) or images the user provides.

## Reading the HIG (every use)

```sh
H="${CLAUDE_SKILL_DIR}/../apple-design-audit/scripts/hig.py"
python3 -I $H read design-principles
python3 -I $H read designing-for-ios        # per target: designing-for-ipados, -macos, -watchos, -tvos, -visionos
python3 -I $H find "tab"                    # search topics
python3 -I $H list                          # all topics (158)
python3 -I $H read tab-bars --max 12000
```

The first line of output names the source. If you see "WARNING: … copy from <date>", write it in the
report. Exit 3 means the HIG could not be read: the report opens with "HIG could not be read, evaluation has
no source" and no visual audit is done; the code scan continues. Rule text is not copied into the skill;
only a short summary goes into the report.

## Code scan

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apple-design-audit/scripts/hig_scan.py" <root> [--json]
```

| Id | What | Severity | HIG |
|---|---|---|---|
| DS-09 | Target platform and pages to read first | INFO | designing-for-* |
| DS-10 | Flutter / RN UI heavily Material | SUGGESTION | design-principles |
| DS-11 | Floating action button / side drawer | SUGGESTION | tab-bars, toolbars |
| DS-12 | Toast / snackbar (no such component in the HIG) | INFO | design-principles |
| DS-13 | 6+ tabs on one screen (overflow) | SUGGESTION | tab-bars |
| DS-14 | System back / dismiss gesture disabled | INFO | gestures, sheets |
| DS-15 | Alert button "OK" | SUGGESTION | alerts |
| DS-16 | Icons heavily Material | SUGGESTION | sf-symbols |

Results are CANDIDATES at code level: a scan cannot see a custom-drawn screen and does not judge looks.

## Screen audit

For the main screens (the user's 5–8 important screens), on screenshots, reading the relevant HIG page:

| Id | Question | HIG |
|---|---|---|
| DS-20 | Is top-level navigation clear, is the tab bar used for actions, is it always visible? | tab-bars, navigation-and-search |
| DS-21 | Does the screen have one main task, are secondary controls in the background? | designing-for-ios |
| DS-22 | Are important controls in the thumb zone? | designing-for-ios |
| DS-23 | Is the sheet / alert in the right place; are Cancel and Done where they belong? | sheets, alerts, modality |
| DS-24 | System material: is glass used in the content layer? | materials |
| DS-25 | Does the layout adapt in dark mode and large text? (measurement in layout-a11y) | dark-mode, typography |
| DS-26 | Are empty, loading and error states designed? | loading, launching |
| DS-27 | Feedback: are state changes visible, is haptic feedback excessive? | feedback, playing-haptics |

Practical notes for screenshot tours:

- The simulator may open in the device language, which may not be the language you expect. A tour must
  look up tab and button labels in the language the simulator is actually running.
- Demo data seeded behind the app's back (for example written straight into its database) may not appear
  until the app's own refresh path runs. Run that path and confirm the data is on screen before judging
  the screen; an empty screen caused by this is not a DS-26 finding.

## Setup · Release

In setup: `apple-design-advisor` for a new design. In release: this member is not mandatory and its result does
not block submission; apptest's rejection risk items are closed first.

## Report

Three sections, with separate headings:
1. **Required by Apple (link to apptest):** only if any; this member does not decide.
2. **Differences from the HIG:** id · screen / file · HIG page and short summary · effect on the user · one or
   two ways forward · where it was seen (code / screenshot).
3. **Opinion:** design views with no source, labelled as such.

At the end: the user is asked "apply / keep as is" for each difference; the report changes no code.
