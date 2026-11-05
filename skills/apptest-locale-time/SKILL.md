---
name: apptest-locale-time
description: "Language, region and time zone audit: days shifting at DST, hardcoded date / money / number formats, right-to-left, untranslated text, plurals, calendars. Localization, timezone, RTL, DST."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - WebFetch
metadata:
  version: "1.0.0"
---

# apptest-locale-time — language, region, calendar, time

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.10 · report
`../apptest/shared/report.md`. Read Apple's localization guide in its current
version every time (principle 7):
https://developer.apple.com/documentation/xcode/localization
Talking with the user: `../apptest/shared/CONVENTIONS.md` §11 (when to ask, status lines, one next step).

**Default contract:** Reports only, does not change code. Does NOT TOUCH the
Mac's clock, time zone or language (test-methods T4): only inside the test
process and its own simulator.

## When

- Code with dates / times / day counts / due dates / calendars was written or
  changed ("tomorrow", "N days left", "last day of the month").
- A new language is being added, or a right-to-left language (Arabic, Hebrew,
  Persian, Urdu) is being considered.
- Money, numbers or units of measure are displayed.
- Before release (the family head's Release mode).

## Out of scope

- Meaning and tone of a translation → copy-audit (its `copy_inventory.py`
  script is used for missing keys and placeholder mismatches).
- Whether the app's clock is testable → time-travel (this member states the
  rule, that member moves the clock).

## Step 0

CONVENTIONS §5. The static scan only reads. Tour: its own temporary simulator
(§5.4); language / time zone / calendar are given only to the LAUNCHED app
(launch argument and `SIMCTL_CHILD_` environment variable) and do not change
the simulator as a whole; if a global change is needed, it is written to the
registry and reverted (§7).

## Principles specific to this member

- **LT-P1** Treats a calendar / time calculation as "correct" only if it was
  also tried in a time zone with DST.
  *Why:* in a region without DST the day shift is invisible (e.g. a budgeting
  app's tests passed in Istanbul and shifted in Berlin / California).
- **LT-P2** Counts missing, broken, overflowing and wrongly formatted (date /
  number / plural / direction) text as findings, not translation quality.
  *Why:* meaning and tone are copy-audit's job; two members should not judge
  the same text by different measures.

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
`languages` (the languages flag; with one language LT-40 does not apply; with a
right-to-left language, LT-30 and the RTL tour apply), technology (tour
commands below).

## Setup (good to know from the start)

1. **Calendar day ≠ 24 hours.** "Tomorrow", "N days later", "how many days
   left" are calculated with a calendar function or a UTC date; adding seconds
   shifts a day across a DST change. Elapsed TIME (a timer, "older than one
   day") is correct in seconds.
2. **Make the clock testable:** if the app gets "now" from a single place,
   midnight / month-end / DST tests become possible (the method is yours; see
   time-travel).
3. **Local formats:** date, time (12/24), number, money and unit of measure go
   through a formatter; nothing shown to the user is written with a fixed
   pattern. Formats going to a server or a file name, however, are fixed and
   `en_US_POSIX` / ISO 8601.
4. **Text goes into the translation system from the start;** text with a
   number follows plural rules (1, 2 or 6 forms depending on the language).
5. **Leading/trailing, not left/right** (leading/trailing, start/end) — the
   layout survives even if a right-to-left language is added later.
6. **Calendar:** if a business rule depends on the Gregorian calendar (year
   boundary, month end), calculate explicitly in Gregorian; display in the
   user's calendar.

## Test (while developing)

### 1. Static scan (seconds)

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-locale-time/scripts/locale_scan.py" <root> [--json]
```

For missing / untranslated keys and placeholder mismatches:
`python3 -I "${CLAUDE_SKILL_DIR}/../apptest-copy-audit/scripts/copy_inventory.py" <root> --out <temp>`

| ID | Topic | Severity |
|---|---|---|
| LT-10 | Calendar day calculated as 24 hours (adding seconds to a date, dividing a duration by 86400, local `difference().inDays`) | USER BUG |
| LT-20 | Hardcoded date pattern shown to the user | SUGGESTION |
| LT-21 | Money / number in a fixed format (separator, symbol) | SUGGESTION |
| LT-30 | Hardcoded left/right — only if a right-to-left language is supported | SUGGESTION |
| LT-40 | Translation system exists but text is hardcoded — only if multi-language | USER BUG |
| LT-41 | Number + fixed plural word | SUGGESTION |
| LT-50 | Calendar calculation in the user's calendar (non-Gregorian risk) | SUGGESTION |
| LT-60 | Fixed time zone / offset (except UTC) | SUGGESTION |

Output is a CANDIDATE (principle 6). The script filters known false alarms:
calculations in UTC, elapsed times, server / file name formats, preview and
measurement text, developer screens. Verify the rest by opening the code: in
LT-10, is the result a CALENDAR day or a DURATION — if a duration, it is not a
finding.

### 2. Time zone tour (unit tests; minutes)

Run the project's own tests in different time zones — at least one with DST
(two for the northern hemisphere's different change dates):

```sh
TZ=Europe/Berlin <test command>            # last Sunday of March/October
TZ=America/Los_Angeles <test command>      # 2nd Sunday of March / 1st of November
TZ=Australia/Sydney <test command>         # southern hemisphere (opposite season)
TZ=Asia/Kolkata <test command>             # half-hour offset
```

Sample commands: `flutter test`, `npx jest`, `swift test`. For Xcode tests the
environment variable goes in the test plan / scheme. If tests depend on local
time the result changes (report to test-health too). Midnight, month / year
end, Feb 29 and DST-night scenarios are in time-travel.

### 3. Language / region / calendar tour (simulator; principle 13: duration + approval)

Your own temporary simulator. Given to the app as a launch argument — the
simulator as a whole does not change:

```sh
# language + region
xcrun simctl launch <UDID> <bundle> -AppleLanguages "(ar)" -AppleLocale ar_SA
# Buddhist calendar / 24 hour
xcrun simctl launch <UDID> <bundle> -AppleLocale "th_TH@calendar=buddhist"
# time zone (this app process only)
SIMCTL_CHILD_TZ=America/Los_Angeles xcrun simctl launch <UDID> <bundle>
# pseudo-localization: double-length text / right-to-left direction
xcrun simctl launch <UDID> <bundle> -NSDoubleLocalizedStrings YES
xcrun simctl launch <UDID> <bundle> -AppleTextDirection YES -NSForceRightToLeftWritingDirection YES
```

(Flutter / RN also read these arguments from iOS; if the app takes its language
from its own setting, use that.) Screenshot every main screen and downscale to
~700 px (principle 17). Look for: untranslated text, overflowing long text,
icon / arrow / progress direction that did not flip, wrongly formatted date /
number / money, wrong plural, calendar year difference.

## Release (before submitting)

1. Check Apple (principle 7) — do the languages in App Store Connect match the
   app's real languages (T-07; store-readiness).
2. Static scan + unit tests in at least one DST time zone.
3. If multi-language: missing key scan (copy_inventory) + main screen
   screenshots in the longest language and (if any) a right-to-left language.
4. Report.

## Report

`shared/report.md`. Each finding: the language / region / calendar / time zone
combination, screen or file:line, expected ↔ seen (e.g. "October 28 instead of
October 29"), one or several ways to fix it. Environment: time zones and
languages tried, "Apple rules: Last Updated <date>, read on <today>".
