---
name: apptest-store-readiness
description: "Is my iOS app ready for App Store submission? Checks icon, Info.plist, encryption declaration, iPad orientations, privacy manifest, placeholder text, test servers, App Store Connect and TestFlight lists, ITMS errors."
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

# apptest-store-readiness — submission readiness

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.10 (principles 0–17, §2–§10).
Rejection list: `../apptest/shared/rejections.md` (an index only; the source
is Apple's page). Report: `../apptest/shared/report.md`.

**Default contract:** Report only. It writes to nothing: not code, not
settings, not App Store Connect. Upload and submit commands are only
prepared, never run (principle 16). If the user says "fix it", it proposes
the relevant fix and follows the project's own workflow (branch, PR)
(principle 0).
Talking with the user: `../apptest/shared/CONVENTIONS.md` §11 (when to ask, status lines, one next step).

## When

- The user is getting ready to submit to the App Store or TestFlight external.
- "Why was it rejected / what is missing": the family head's Rejection mode calls this member.
- A review note, "What to Test" or Test Information text is needed.
- If you notice the need yourself, suggest it in ONE line (principle 3); do not run without approval.

## Out of scope

- Price, business model, product decisions (product-fit / monetization look at them from the rejection angle).
- Screenshot production → store-assets. Purchase flow details →
  monetization. Privacy label contents → privacy-permissions. This member
  only checks "does it exist / is it connected" and leaves the depth to
  the relevant member.

## Step 0

CONVENTIONS §5. This member mostly just reads; no build is needed. With no
heavy work, no lock is needed. `--check-links` only sends GET requests to
public pages (read-only).

## Member-specific principles

- **SR-P1** Does not guess the state of App Store Connect; asks the user for
  a screenshot or information, or says "not verified".
  *Why:* ASC is not visible in the repo; a guessed "ready" sends the wrong
  build to review (e.g. a budgeting app with build 3 and build 4 in play).
- **SR-P2** Writes what Apple REQUIRES and what is merely "nice to have" at
  separate grades (`references/asc-checklist.md`: Required / Conditional / Optional).
  *Why:* presenting something optional (a dark icon variant) as required
  causes needless work and loss of trust.
- **SR-P3** Writes the review note, Test Information and "What's New" from
  this app's real flow; no boilerplate.
  *Why:* a generic note leaves the reviewer unable to find the feature and
  leads to 2.1 / 2.3.12 rejections.

## Profile

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>
```

From the flags: `platforms` (platforms; iPad → SR-23, the iPad set in SR-81;
Mac/Vision → SR-79), `purchases` (in-app purchase; SR-71, SR-87, SR-99),
`account` (account; SR-88 demo account), `extensions` (extensions; icon /
manifest / Info.plist checked separately for each), technology (Expo / Unity /
Capacitor: the iOS project is generated at build time → verify in the
generated project).

## Setup (new project: good to know from the start)

Mention only what fits the profile; how to solve it is the user's call (principle 2).

1. **Bundle id and app name** cannot change later or are expensive to change
   (bundle id never). The name may already be taken on the App Store:
   register it in ASC early.
2. **Support and privacy pages** must be live BEFORE release (SR-77,
   SR-83); link to the privacy policy from inside the app (SR-50).
3. **Encryption declaration** in Info.plist from the start (SR-20): it removes
   the question on every build.
4. **Target platform decision:** will iPad be supported (if so, all four
   orientations or full screen — SR-23; iPad screenshots — SR-81); will it
   appear as an iPhone app on Mac / Vision (on by default — SR-79).
5. **Privacy manifest** from the start; any new code using a required-reason
   API (UserDefaults, file timestamps, boot time, disk space, keyboards)
   also updates the declaration (SR-30/31).
6. **Version / build number** increases from one source; the build goes up
   with every upload (SR-93).
7. **Release and development builds** are kept separate for server address,
   logging and test menus (SR-41).
8. **If an account is needed,** plan a permanent demo account for review (SR-88).

## Test (during development: TestFlight)

`references/testflight.md`: internal vs external, Beta App Review,
Test Information, public link limit and common snags
(SR-95 … SR-100). When the user asks about TestFlight, first work out which
group they mean; if there is a screenshot, go by it (SR-P1).

## Release (before submitting)

Time: automatic scan < 1 min; link check ~1 min; manual list with the
user 10–20 min.

1. **Check Apple (principle 7).** Read the guidelines page's "Last Updated"
   date and compare it with the date in `../apptest/shared/rejections.md`;
   check developer news for the minimum SDK and new requirements (SR-92). If
   they differ, write "Rules changed" in the report.
2. **Profile** (above).
3. **Automatic scan:**
   ```sh
   python3 -I "${CLAUDE_SKILL_DIR}/../apptest-store-readiness/scripts/readiness_scan.py" <root>
   python3 -I "${CLAUDE_SKILL_DIR}/../apptest-store-readiness/scripts/readiness_scan.py" <root> --check-links
   ```
   The output is CANDIDATES: verify each item by reading the file (principle 6).
   E.g. SR-31 may be covered by a package's own manifest; SR-41 may be used
   only in the development build.
   The script reads Info.plist as it ships to the store (custom-named files,
   Xcode's generated `INFOPLIST_KEY_*`, the Release configuration; excluding
   Alpha / Debug / Experimental variants, framework and test bundles) and
   checks only the MAIN icon (excluding alternate / debug / extension icons).
4. **Extensions:** icon, Info.plist and privacy manifest separately for each
   extension in the profile (R-32, R-44).
5. **Manual list:** `references/asc-checklist.md` — ask the user section by
   section or request screenshots; anything unanswered is "not verified".
6. **Review note draft** (end of asc-checklist; SR-P3).
7. **Other members:** if needed, suggest in one line (privacy-permissions,
   monetization, store-assets, layout-a11y …); for unwritten ones, the family
   head's "Instead of a planned member" path.
8. **Report** (`shared/report.md`).

### Automatic scan IDs

| ID | Topic | Rule |
|---|---|---|
| SR-10 / 11 | No main icon set · TRANSPARENT pixels in the 1024 px icon (REJECTION RISK) or an opaque alpha channel (SUGGESTION) or wrong size | T-02 |
| SR-09 | No iOS project in the repo yet: checks that need one are skipped (info) | — |
| SR-13 | Info.plist cannot be read: permission and settings checks would be empty (USER BUG) | — |
| SR-12 | Main icon generated at build time (Icon Composer `.icon`, MAUI) — info | T-02 |
| SR-20 | No encryption declaration (SUGGESTION) | T-04 |
| SR-21 | Usage description empty / placeholder | 5.1.1(ii) |
| SR-22 | No launch screen definition | 2.1 / technical |
| SR-23 | iPad: not all four orientations and not full screen | ITMS-90474 |
| SR-24 | Display name "test / beta / dev" | 2.2 / 2.3 |
| SR-25 | Is the background mode actually used (SUGGESTION) | 2.5.4 |
| SR-26 | ATS fully disabled | 1.6 |
| SR-30 / 31 | No privacy manifest · required-reason API may be undeclared | ITMS-91053 |
| SR-40 | Placeholder in user-facing text (TODO, FIXME, lorem ipsum …; case-sensitive) | 2.1 |
| SR-42 | "Coming soon" wording: for a feature or a content label (SUGGESTION) | 2.1 |
| SR-41 | Development / staging server address | 2.1 |
| SR-50 / 51 | No privacy / support link · does not open | 5.1.1(i), 1.5 |
| SR-60 | Version numbers (info) | T-05 |
| SR-61 | iOS deployment target below the current minimum (iOS 13 since 2026-09-09) | Upcoming Requirements |

Manual list IDs: SR-70 … SR-94 (`references/asc-checklist.md`),
TestFlight: SR-95 … SR-100 (`references/testflight.md`).

## Report

`shared/report.md`. One-sentence verdict in the summary: "Ready to submit /
ready once these N rejection risks are resolved / N items not verified". The
line "Apple rules: Last Updated <date>, read <today>" under Environment is
mandatory. ASC items that are not verified but carry no rejection risk go in
a separate list.
