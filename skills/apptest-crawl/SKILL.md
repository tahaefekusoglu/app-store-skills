---
name: apptest-crawl
description: "Sets up an automated crawl test that taps every tappable element: crashes, overflow, errors, accessibility; screen × text size × language matrix, demo data. Flutter, XCUITest, Detox. Monkey test, UI crawler."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-crawl: tap every element

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.3 · group principles
`../apptest/shared/test-methods.md` (T1–T10) · rules in layout-a11y (the
measurements live there) · report `../apptest/shared/report.md`.

**Default contract:** Adapts the test template to the project and writes it to
the test folder with approval; does not add hooks to app code (T3). If it runs
on a simulator, it uses a temporary simulator (`sim_session.py`).

## When

- A UI with many screens; checking every corner by hand is no longer possible.
- Large text / a small screen / a new language was added.
- Before release: the assurance that "no button crashes the app".

## Out of scope

- Walking a specific flow end to end → device-tour. Image diffs → visual.
  Measurement rules (contrast ratio, tap target) → layout-a11y; this member
  applies them to EVERY element.

## Step 0

CONVENTIONS §5. A crawl is long (e.g. a budgeting app: 7 combinations, minutes
per combination): time estimate, approval, `caffeinate`, timeout (§6).

## Member-specific principles

- **CR-P1** Does NOT tap destructive or outward-facing elements: delete, buy,
  log out, close account, share, external link, send. The label list is built
  in the app's languages; skipped elements are counted in the report.
  *Why:* a crawl must not delete data, spend money or send messages out (T2).
  These elements are tested separately, with mocks.
- **CR-P2** The app is reopened from scratch (or returned to its initial state)
  for every target.
  *Why:* a dialog opened by the previous tap covers the next target; the error
  gets attributed to the wrong element and the result depends on order.
- **CR-P3** Elements are found through the accessibility tree, not memorized
  coordinates; a tappable element missing from the accessibility tree is itself
  a finding (layout-a11y: unlabeled button).
  *Why:* a coordinate list goes stale silently when the design changes; the tree
  is what a VoiceOver user sees.
- **CR-P4** Minimum matrix: smallest supported screen × normal text and the
  largest accessibility text × tall screen; every language of the app; paid and
  free if there are paid features.
  *Why:* overflow only shows at large text, locks only in free, long text only
  in one language (e.g. a budgeting app's crawl at ×3.0 text and EN).

## Profile

`python3 -I ~/.claude/skills/apptest/shared/profile.py <root>` →
technology (template choice), `languages`, `purchases`, `has_tests`.

## Setup (good to know from the start)

1. Every important element has a stable id (Flutter `Key`, `testID`,
   `accessibilityIdentifier`).
2. The app can open for testing with demo data + a fixed clock + mocked external
   services (a single entry point).
3. Destructive actions go through a confirmation dialog (the crawl can see the
   confirmation and back out).

## Test

Templates: `references/templates.md` (Flutter semantics, XCUITest, React
Native). Adaptation steps:

1. A helper that opens the app (`openApp`): demo data, fixed clock, mocked
   purchases / network / notifications.
2. The list of labels to skip (CR-P1), in the app's languages.
3. The matrix (CR-P4) and level 2 depth (inside the page that opens).
4. Issues collected: uncaught exception, overflow, crash / falling out of the
   foreground, contrast, tap target, label.
5. A tag separate from the normal tour (`crawl`); runs before release and on
   big UI changes.

Every finding: combination + screen + element label / id + error (T5).

## Release (before submitting)

1. The full matrix is clean once.
2. Do the skipped destructive elements have their own mocked tests?

## Report

`shared/report.md`. Per combination: number of elements tapped / skipped,
findings (screen › element › error). If the same error hits many elements, one
finding with the element list.
