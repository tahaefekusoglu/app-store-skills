---
name: apptest-store-assets
description: "App Store screenshots and preview videos: accepted sizes, alpha, required devices, theme × language capture tour, demo data, 9:41 status bar. Store screenshots, app preview."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - WebFetch
metadata:
  version: "1.0.0"
---

# apptest-store-assets: store images

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.10 · long jobs §6 · cleanup
§7 · report `../apptest/shared/report.md` · rejection index (R-08, T-03).
Sizes and requirements come from the official page EVERY TIME (principle 7); in 2026
the required class changed (6.9" → "Dynamic Island medium"):
https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/ ·
https://developer.apple.com/help/app-store-connect/reference/app-information/app-preview-specifications/

**Default contract:** Produces and checks images; does NOT upload to App Store
Connect (principle 16). Produced images go to the folder the user picks and are
NOT deleted.
Talking with the user: `../apptest/shared/CONVENTIONS.md` §11 (when to ask, status lines, one next step).

## When

- Store screenshots, ad images or a preview video are being prepared.
- Design, theme or language changed and the images are out of date.
- "Image not accepted" (size / alpha) or a 2.3.3 rejection.
- An in-app purchase review screenshot is about to be uploaded (alpha rule).

## Out of scope

- Designing captions or frames over the images (this skill produces PLAIN images;
  the design layer belongs to the user or a designer).
- Store text → product-fit / copy-audit.

## Step 0

CONVENTIONS §5: its own temporary simulator (NOT the user's), lock, processes by
PID (no `pkill -f`), settings registry. Heavy job: time estimate and approval (§6).

## Member-specific principles

- **SA-P1** An image is the app's REAL screen; edits happen only in the frame /
  caption layer.
  *Why:* 2.3.3: an appearance or feature the app does not have is a rejection reason.
- **SA-P2** Demo data is fictional (no real people, brands or copyrighted content)
  and the user's own simulator or data is not used.
  *Why:* 5.2 copyright / trademark and personal data leaks (e.g. a budgeting app's
  images were taken on a separate simulator with in-memory demo data; the user's
  iPhone 18 Pro was not touched).

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
`platforms` (iPad → the 13" iPad set is required), `languages` (one set per
language), technology (tour tool, `references/shot-tour.md`).

## Setup (good to know from the start)

1. **Demo data path:** if the app can open with an in-memory or temporary database
   and a fixed clock, the screenshot tour becomes one command (the method is yours).
2. **If theme and language can be picked inside the app**, each one is a separate
   set; screens that depend on a name or person are extra.
3. **Debug banner, developer menu, test data** must not show in the release look.

## Test (during development)

This member's "test" is checking the images:

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-store-assets/scripts/assets_check.py" <image_folder> [--ipad] [--json]
```

| ID | Topic | Severity |
|---|---|---|
| SA-10 | Unreadable or unsupported format (png / jpg / jpeg only) | REJECTION RISK |
| SA-11 | Alpha channel (with or without transparent pixels) | REJECTION RISK |
| SA-12 | Pixel size not accepted | REJECTION RISK |
| SA-13 | More than 10 images in a class | REJECTION RISK |
| SA-14 | Mixed portrait and landscape | SUGGESTION |
| SA-15 | No large-screen iPhone set (6.9" or 6.5"); medium alone is not enough | REJECTION RISK |
| SA-16 | iPad supported, no 13" iPad set | REJECTION RISK |
| SA-20 | Preview video length (15–30 s) / size (≤500 MB) | REJECTION RISK |
| SA-21 | More than 3 preview videos per device and language | REJECTION RISK |

Use the same script for in-app purchase review screenshots (only the alpha rule
applies; ignore the size warning).

## Release (producing and delivering images)

1. **Check Apple (principle 7):** required classes and sizes.
2. **Agree the scope with the user:** which screens (usually "the main screens"),
   which themes and languages, name / person variants.
3. **Capture tour:** `references/shot-tour.md` (simulator, status bar, demo data,
   `scripts/shot_host.sh` handshake, tour tool per technology, sample:
   your own `integration_test` tour written from `references/shot-tour.md`).
4. **Export without alpha:** `scripts/noalpha.swift`.
5. **Check:** `assets_check.py`.
6. **Deliver:** to the user's folder as `<person>/<lang>/<theme>/<NN screen>.png`
   plus a preview HTML with relative paths; zip for sharing (not compressed when
   sent as a "document").
7. **Cleanup (§7):** status bar, simulator, receiver process, raw images.

## Report

`shared/report.md`. Also: number of images produced and their folder, count per
class, check result, "size table <date>; Apple page read <today>". State clearly
anything that could not be cleaned up (e.g. the status bar).
