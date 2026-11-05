---
name: apptest-content-safety
description: "Use when an app has user posts, comments, chat, AI output, gambling, medical claims or kids content and you ask what Apple requires: reporting and blocking (1.2), age rating, 5.3, 1.4.1. UGC, moderation."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - WebFetch
metadata:
  version: "1.0.0"
---

# apptest-content-safety: content safety and age

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.10 · report
`../apptest/shared/report.md` · rejection index (R-11, R-47, R-51 … R-53, R-34).
Rule text and the age rating questionnaire come from the official site EVERY TIME
(principle 7):
https://developer.apple.com/app-store/review/guidelines/#safety ·
https://developer.apple.com/help/app-store-connect/reference/app-information/age-ratings-values-and-definitions/
Talking with the user: `../apptest/shared/CONVENTIONS.md` §11 (when to ask, status lines, one next step).

**Default contract:** Reports; does not write to code or App Store Connect. The
user fills in the age rating questionnaire; this member prepares the items and
their evidence.

## When

- A feature is being added where users share content, message each other or open
  profiles, or one that generates content with AI.
- The age rating questionnaire is about to be filled in or updated (Apple renews it
  from time to time).
- An app aimed at kids, random rewards in a game, contests, health content.
- A 1.x or 2.3.6 rejection. Before release.

## Out of scope

- Moral judgment of the content itself; product decisions.
- Sending personal data to AI → privacy-permissions (PP-30).
- The purchase side of random rewards → monetization (MO-19).

## Step 0

CONVENTIONS §5. Read-only. If a filter or moderation trial is needed, use only
documented harmless test strings (CS-P1).

## Member-specific principles

- **CS-P1** Does NOT PRODUCE harmful content to try a filter or model; uses
  documented harmless test strings and the provider's samples.
  *Why:* safety; harmful content must not end up in test logs or the repo.
- **CS-P2** Suggests the age rating from Apple's current questionnaire (evidence
  from the code for each question), not from personal judgment; the user gives the
  answer.
  *Why:* a wrong rating is a 2.3.6 rejection; personal judgment gives inconsistent results.

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
`user_content`, `ai`, `ads`, `purchases`, health among the
permissions; "unknown: target age / Kids category" (one question if needed).

## Setup (good to know from the start)

1. **User content and messaging come with these from day one (1.2):** filtering of
   objectionable content, reporting with a timely response, blocking of abusive
   users, contact information published in the app. Adding them later changes the
   data model (report records, block list).
2. **Generative AI output counts like user content:** a filter, a "report this
   response" path, and its answer on the age rating.
3. **Decide the audience early:** if it is aimed at kids, the Kids category rules
   (no third-party ads or analytics, external links and purchases behind a parental
   gate, 1.3 / 5.1.4) affect the architecture.
4. **An in-app browser** that lets the user open any address means "Unrestricted
   Web Access" and a high age rating.
5. **Chance / rewards:** random reward odds are shown; real-money gambling needs a
   license and geo-restriction (5.3).
6. **Health / medical:** a measurement or diagnosis claim needs evidence and, if
   required, regulatory approval (1.4.1).

## Test (during development)

### 1. Static scan (seconds)

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-content-safety/scripts/content_scan.py" <root> [--json]
```

| ID | Topic | Severity |
|---|---|---|
| CS-10 | User content or messaging present; report / block / filter / contact missing | REJECTION RISK (1.2) |
| CS-11 | No report or feedback path for generative AI output | SUGGESTION |
| CS-12 | Items that may be "yes" on the age rating questionnaire (inventory with evidence) | INFO (2.3.6) |
| CS-16 | Social media signs, no Declared Age Range API (needed for "disabled for users under 13") | SUGGESTION |
| CS-13 | Gambling or game of chance wording (rejection risk if there are purchases or payments) | REJECTION RISK / SUGGESTION (5.3) |
| CS-14 | Medical or diagnostic wording | SUGGESTION (1.4.1) |
| CS-15 | Wording aimed at kids (+ third-party analytics / ads) | REJECTION RISK / INFO (1.3, 5.1.4) |

Output is a CANDIDATE (principle 6). Meaning searches (gambling, medical, kids)
run only on the source language (en / Base / tr). When verifying: for CS-10,
moderation may be on the server or a web panel (ask the user, ask for the path in
the app); for CS-15, is the app really aimed at kids?

### 2. Hands-on trial (temporary simulator)

On every surface with user content (post, comment, profile, message, AI response):
report → confirmation and feedback · block → the content disappears · filter / mute
works · contact information can be found inside the app. With demo accounts (the
user creates them; CS-P1).

## Release (before submitting)

1. **Check Apple (principle 7):** current text of 1.x and 2.3.6; the CURRENT
   questions of the age rating questionnaire (page above; Apple renews it).
2. Static scan + map the CS-12 inventory to the questionnaire with the user: yes /
   no and evidence for each question (CS-P2).
3. If there is user content, in the review notes: where report and block are, demo
   content for the reviewer.
4. Report.

## Report

`shared/report.md`. Separate table: questionnaire question · what the app does
(evidence) · suggested answer · user's answer. Environment: "Apple rules: Last
Updated <date>; age questionnaire read <today>".
