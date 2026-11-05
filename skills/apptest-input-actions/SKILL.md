---
name: apptest-input-actions
description: "Input and action audit: duplicate saves, delete without confirmation, comma decimals, float for money, emoji length, keyboard type, paste and boundary values. Form validation, double submit."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-input-actions — input and actions

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.10 · report
`../apptest/shared/report.md`. Focused on USER BUG more than App Store rules;
for system behaviour (keyboard, text), the current HIG page (principle 7):
https://developer.apple.com/design/human-interface-guidelines/entering-data
Talking with the user: `../apptest/shared/CONVENTIONS.md` §11 (when to ask, status lines, one next step).

**Default contract:** Reports only, does not change code.

## When

- A form, amount / number field, save / pay / send button, or delete / remove
  action was written or changed.
- Bug reports like "it saved twice", "typing a comma doesn't work", "the limit
  is wrong with emoji".
- Before release (the family head's Release mode).

## Out of scope

- Field appearance, masks, keyboard design (IA-P2).
- Systematic trial of fast taps → rapid-input (this member gives the rule).
- Meaning of text → copy-audit. Date / money FORMAT (display) → locale-time.

## Step 0

CONVENTIONS §5. The static scan only reads. Manual tries run in a temporary
simulator, with demo data.

## Principles specific to this member

- **IA-P1** Reads limits from code and configuration (maximum length, decimal
  places, unit, allowed range); does not assume them.
  *Why:* testing with an assumed limit misses the bug at the real limit or
  finds a bug that does not exist (e.g. in a budgeting app, currencies without
  minor units and the 100% cap on percent fields).
- **IA-P2** Does not interfere with the input format (mask, keyboard type
  choice, field design); counts only data loss, wrong saves and duplicate saves
  as findings.
  *Why:* principle 2 — format is a product decision, not a data error.

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
technology, `languages` (languages; IA-12 matters if any use a comma decimal),
`purchases` (purchases; a double tap on a pay button is the most expensive).

## Setup (good to know from the start)

1. **Every saving action must not repeat:** the button is disabled while
   working, or single-flight; requests going to a server carry an idempotency
   key.
2. **Money as an integer in the smallest unit** (cents) or Decimal; an
   amount kept in double drifts by cents in totals.
3. **Number input is parsed by locale** (comma / dot, thousands separator);
   a pasted "1.250,50" is read correctly.
4. **Length limits are measured in characters the user sees** (graphemes);
   emoji and combining letters count as one character.
5. **Confirmation or undo on destructive actions;** say clearly what cannot be
   undone.
6. **Validation in one place** (also in the service layer if possible): if UI
   validation is bypassed (paste, accessibility input), data is still protected.
7. **Empty, whitespace only, at the limit and one past the limit** are
   considered for every field.

## Test (while developing)

### 1. Static scan (seconds)

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-input-actions/scripts/input_scan.py" <root> [--json]
```

| ID | Topic | Severity |
|---|---|---|
| IA-10 | Save / pay button open to a second tap while working | SUGGESTION |
| IA-11 | Destructive action without confirmation / undo | SUGGESTION |
| IA-12 | Number from a text field parsed without regard to the decimal separator | USER BUG |
| IA-13 | Money amount kept in double / Float | USER BUG |
| IA-14 | Text length measured in UTF-16 units | SUGGESTION |
| IA-15 | No keyboard type on a number / phone field | SUGGESTION |

Output is a CANDIDATE (principle 6). The script filters known false alarms:
constants and theme values (a font size named "amount"), number-to-number
conversion, parsing of server / API data, developer screens. When verifying: in
IA-10 is the guard in another layer (view model, request lock); in IA-11 is the
confirmation in another file; in IA-13 is the value actually money.

### 2. Manual try list (temporary simulator; principle 13)

For every input field (`references/input-cases.md`):
empty · whitespace only · shortest · limit · limit + 1 · very long paste ·
emoji and skin tone (👍🏽) · combining letter (é = e + ´) · right-to-left text ·
number with comma / dot / thousands separator · minus · zero · very large
number · leading / trailing space · line break · formatting via copy-paste
(rich text). For every action: double tap · back while working · sending to
background while working (rapid-input / lifecycle do this systematically).

## Release (before submitting)

1. Static scan.
2. Were double tap and confirmation tried by hand in pay / save / delete flows.
3. Report.

## Report

`shared/report.md`. Each finding: field / action, entered value ↔ expected ↔
seen, evidence. Environment: simulator, language / region (for the decimal
separator).
