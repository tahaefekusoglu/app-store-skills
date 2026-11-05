---
name: apptest-product-fit
description: "Use when asking whether Apple will reject an app as a web wrapper or thin app (4.2), copycat (4.3), or for other platform names (2.3.10), trademark (5.2), metadata or beta wording, hidden menus, regulated fields."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - WebFetch
  - WebSearch
metadata:
  version: "1.0.0"
---

# apptest-product-fit: fit for the store

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.3 · report
`../apptest/shared/report.md` · rejection index (R-08 … R-10, R-27 … R-31,
R-49, R-50). Rule text comes from the official site EVERY TIME (principle 7); 4.2 /
4.3 got stricter in June 2026 with an emphasis on "low quality":
https://developer.apple.com/app-store/review/guidelines/#design

**Default contract:** Reports; does not write to code, metadata or App Store
Connect.

## When

- A new app idea, or before the first submission (so 4.2 / 4.3 risk shows early).
- The app name, subtitle, keywords or description are being written.
- An app built with web technology (Capacitor, Cordova, WebView-heavy).
- A 4.2, 4.3, 2.3.x or 5.2 rejection. Before release.

## Out of scope

- Market, competition, revenue estimates, whether the product is good (PF-P1).
- Screenshot accuracy → store-assets. Meaning and tone of text → copy-audit.
  Content safety → content-safety.

## Step 0

CONVENTIONS §5. Read-only; no network. If a competitor comparison is needed, only
the App Store's public pages (PF-P2).

## Member-specific principles

- **PF-P1** Does not judge the product idea, market or chance of success; only
  states the rejection risk under 4.1 / 4.2 / 4.3 / 2.3 / 5.x and Apple's reason.
  *Why:* principle 2: discouraging the user is not this family's job.
- **PF-P2** Shows evidence (an App Store link) before saying "a similar app exists"
  or "copy"; without evidence it does not say it.
  *Why:* a 4.3 claim without evidence creates needless worry.

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
technology (is it a web wrapper?), `network`, unknown: "regulated field" (one question
if needed).

## Setup (good to know from the start)

1. **"App-like" value (4.2):** the app is not a copy of the website; functionality
   running on the device, offline use, notifications, device features, native UI.
   Web technology is not banned; showing a remote site is not accepted.
2. **One app, many variants (4.3):** submitting color or topic variants of the same
   app separately counts as spam; one app + an in-app choice.
3. **Name and trademark (5.2, 2.3.7):** no Apple product names or other brands in
   the name; name and subtitle are 30 characters, no prices or wording like "best".
4. **Other platforms (2.3.10):** Android and Google Play do not appear in the app
   or metadata (watch out in projects that share text across platforms).
5. **Regulated fields:** VPN, crypto exchange or wallet, loans, banking, health,
   real-money gaming: plan the right account type (organization), license and
   submitting legal entity from the start (5.x, 3.1.5).
6. **No hidden features (2.3.1):** the developer menu is off in the release build;
   everything is open to review.

## Test (during development)

### 1. Static scan (seconds)

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-product-fit/scripts/product_scan.py" <root> [--json]
```

| ID | Topic | Severity |
|---|---|---|
| PF-10 | Shows a remote website / mostly web content | REJECTION RISK / SUGGESTION (4.2) |
| PF-11 | Very small codebase | SUGGESTION (4.2) |
| PF-12 | Other platform name in user-facing text or metadata | REJECTION RISK (2.3.10) |
| PF-13 | Apple trademark in the display name | REJECTION RISK (5.2.5) |
| PF-14 | Other brand in the name or keywords | REJECTION RISK (5.2.1, 2.3.7) |
| PF-15 | Price or superlative wording in the name or subtitle | REJECTION RISK (2.3.7) |
| PF-16 | Metadata character limit exceeded (fastlane/metadata) | REJECTION RISK |
| PF-17 | Vague "What's New" | SUGGESTION (2.3.12) |
| PF-18 | Beta, demo or trial version in user-facing text | REJECTION RISK (2.2) |
| PF-19 | Hidden or developer menu may be enabled in the release build | SUGGESTION (2.3.1) |
| PF-20 | Signs of a regulated field | INFO (5.x) |

Output is a CANDIDATE (principle 6). Text searches run only on the source language,
with comments stripped. When verifying: for PF-12, is the text really shown on iOS
(it may be a text file shared with Android); for PF-18, is it the beta label of a
FEATURE; for PF-20, is the app really in that field?

### 2. Manual assessment

- **4.2:** describe the app's main flow in three sentences; how does it differ from
  the website? What shows when it opens offline?
- **4.3 / 4.1:** does the same developer have a similar app? A name or icon that
  gives a copycat impression? (No evidence, no claim: PF-P2.)
- **Metadata ↔ app:** is every feature in the description in the app, are paid ones
  marked (2.3.2); are the screenshots real (store-assets)?

## Release (before submitting)

1. **Check Apple (principle 7):** current text of 2.2, 2.3.x, 4.1 – 4.3, 5.2 +
   "Last Updated".
2. Static scan; if the metadata is not in the repo, ask the user for the name,
   subtitle, keywords and description text from App Store Connect and assess them
   by the same rules.
3. If in a regulated field: account type, license, submitting legal entity (ask the
   user).
4. Report.

## Report

`shared/report.md`. On rejection risk findings, Apple's reason (from the official
text) and the evidence in the app side by side. Environment: "Apple rules: Last
Updated <date>, read <today>".
