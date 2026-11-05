---
name: apptest-layout-a11y
description: "Screen size and accessibility audit: truncation at the largest text size, Dynamic Type, VoiceOver labels, 44 pt targets, fields covered by the keyboard, dark mode, contrast, iPad / Mac / Vision. Layout, accessibility."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - WebFetch
metadata:
  version: "1.0.0"
---

# apptest-layout-a11y: layout and accessibility

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.2 · report
`../apptest/shared/report.md` · rejection index `../apptest/shared/rejections.md`
(R-13, R-14, R-18, R-36). Apple rules and the HIG come from the official site every
time (principle 7): https://developer.apple.com/design/human-interface-guidelines/accessibility

**Default contract:** Reports, does not change code. The simulator tour does NOT
use the user's simulator (§5.4); it restores settings (§7).

## When

- A new screen or component was added and the question is whether it breaks at
  large text or on a small screen.
- A decision on iPad / Mac / Vision Pro support, or the check before one.
- The Accessibility Nutrition Label in App Store Connect is about to be filled in:
  every declared feature must really work.
- Before release (the family head's Release mode).

## Out of scope

- Color palette, font, layout preference: taste is not a finding (LA-P1).
- Meaning and tone of text → copy-audit. Missing translation, date format →
  locale-time. An automatic tour that presses every button → crawl (this member
  gives the rules and measurements, crawl does the tapping).

## Step 0

CONVENTIONS §5. The static scan is read-only. The simulator tour is a heavy job:
lock (§5.2), its own temporary simulator (§5.4), settings registry and restore (§7:
content size, appearance and contrast settings are per simulator, so they go away
when the tour deletes its own simulator).

## Member-specific principles

- **LA-P1** Counts what can be measured as a finding (contrast ratio, tap target,
  truncated or overflowing text, unreadable or unlabeled element); does not count
  taste as a finding.
  *Why:* flagging an unusual design as "against the HIG" breaks principle 2 and
  drowns real problems in noise.
- **LA-P2** Gives every finding with its device + text size + appearance + language
  combination.
  *Why:* overflows often appear in only one combination; a finding without the
  combination cannot be reproduced (e.g. a budgeting app's cycle forecast overflow
  appeared only on a small screen + large text).

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
`platforms` (iPad → LA-50 and an iPad tour; Mac/Vision → LA-51),
`languages` (tour with the longest translation too; RTL tour if there is a
right-to-left language), technology (choice of audit tool, below).

## Setup (good to know from the start)

1. **Keep text scaling on from the start.** Turning off Dynamic Type or clamping it
   to a small range is the most expensive layout job to undo later: every screen
   gets reworked.
2. **Fixed height and single lines** truncate text at large sizes; flexible height
   + line wrapping, or proportional shrinking for elements that cannot be shortened
   like amounts, whichever fits.
3. **Colors from one place** (theme / asset catalog): adding dark mode and increased
   contrast is cheap then.
4. **Decide on iPad early:** an iPhone app also runs on iPad (2.4.1); either adapt
   it for iPad or target iPhone only. Appearing as an iPhone app on Mac / Vision Pro
   is ON by default (R-14).
5. **Label icon-only buttons from the start** (VoiceOver name).
6. **Tap target ≥ 44×44 pt**; the visible icon can be small.
7. **Keyboard:** every screen with a text field stays usable with the keyboard open.

## Test (during development)

### 1. Static scan (seconds)

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-layout-a11y/scripts/layout_scan.py" <root> [--json]
```

Output is a CANDIDATE: verify each line by opening the code (principle 6). Known
false alarm types: a fixed scale used for measuring (Flutter TextPainter; the script
filters it), an intentional limit (counter badge), `ignoresSafeArea` for a
background. If intentional, write "intentional (reason)" in the report.

| ID | Topic | Severity |
|---|---|---|
| LA-10 | Dynamic Type turned off or clamped to a small range | USER BUG |
| LA-11 | Fixed point size text (SwiftUI/UIKit; does not grow) | SUGGESTION |
| LA-20 | No label on a tappable element without text (Flutter IconButton, RN Pressable) | USER BUG |
| LA-21 | Many SF Symbols, few labels (density) | SUGGESTION |
| LA-22 | SwiftUI button whose whole label is a symbol, with no accessibility label | SUGGESTION (a11y) |
| LA-30 | Tap target shrunk below 44 pt | USER BUG |
| LA-40 | Appearance fixed (light/dark): info | INFO |
| LA-41 | Scattered fixed colors, few adaptive colors (palette file excluded) | SUGGESTION |
| LA-50 | iPad supported but no sign of adapting to screen size | REJECTION RISK (2.4.1): verify in the simulator |
| LA-51 | Set up to run on Mac / Vision too | SUGGESTION (R-14) |
| LA-60 | Many animations, "Reduce Motion" not read | SUGGESTION |
| LA-70 | Keyboard safe area ignored / content does not move | SUGGESTION |

### 2. The technology's own audit (if in the project, with approval)

- **Native (XCUITest, iOS 17+):** per screen
  `try app.performAccessibilityAudit()` (a call without a handler fails the test on the first finding; "nearly passed" is only a warning): contrast, tap target,
  label, Dynamic Type truncation. If the project has no UI tests, suggest it; do not add it.
- **Flutter (widget test):** `expect(tester, meetsGuideline(textContrastGuideline))`,
  `iOSTapTargetGuideline`, `labeledTapTargetGuideline`; for large text
  `tester.platformDispatcher.textScaleFactorTestValue = 3.0` (iOS AX5 ≈ ×3.1).
- **React Native:** `accessibilityLabel` queries with Detox / Maestro; otherwise
  Xcode Accessibility Inspector (by hand).
- **Game engine / canvas / web wrapper:** the accessibility tree is weak or absent
  → screenshot tour + a manual VoiceOver trial (test-methods T10).

### 3. Simulator tour (minutes; principle 13: state the time, get approval)

Your own temporary simulator (§5.4). Matrix (shorten by profile):

| Axis | Values |
|---|---|
| Device | SMALLEST supported iPhone · largest iPhone · (if iPad) iPad |
| Text size | `large` (default) · `accessibility-extra-extra-extra-large` |
| Appearance | `light` · `dark` (only that one if appearance is fixed) |
| Contrast | normal · `increase_contrast enabled` (in one tour, with the largest text) |
| Language | default · longest translation · (if any) right-to-left |

```sh
xcrun simctl ui <UDID> content_size accessibility-extra-extra-extra-large
xcrun simctl ui <UDID> appearance dark
xcrun simctl ui <UDID> increase_contrast enabled
xcrun simctl io <UDID> screenshot --type=png <file>
```

Visit every main screen in every combination (with the project's UI or integration
tests if it has them; otherwise by hand or device-tour). Shrink images to ~700 px
and inspect (principle 17). Look for: truncated or overlapping text, elements
running off screen, unreadable colors, fields covered by the keyboard, elements
VoiceOver cannot read. Write each finding with its combination (LA-P2).

## Release (before submitting)

1. Check Apple (principle 7): 2.4.1, 4.0, HIG accessibility and the App Store
   Connect Accessibility label page (the requirement status may have changed).
2. Static scan + (if there is time) at least the "smallest iPhone × largest text"
   and "iPad" cells of the simulator tour.
3. **If the Accessibility label is filled in**, does every declared feature
   (VoiceOver, Voice Control, Larger Text, Dark Interface, Differentiate Without
   Color, Sufficient Contrast, Reduced Motion, Captions, Audio Descriptions) really
   work in the main flows? A declaration that does not work is misleading metadata (2.3).
4. If Mac / Vision availability is on, at least launch + main flow there (otherwise
   store-readiness SR-79: suggest turning it off).
5. Report.

## Report

`shared/report.md`. Each finding: combination (device · text · appearance ·
language), screen, evidence (file:line or image), impact, one or more ways to fix.
Environment: simulator, iOS version, "Apple rules: Last Updated <date>, read
<today>". Cleanup: was the temporary simulator deleted?
