---
name: apptest-visual
description: "Compares screens pixel by pixel with the previous version: theme × language × device × text size, diff images, plain Python. Pins clock and animations before comparing. Use for visual regression, golden or snapshot tests."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
metadata:
  version: "1.0.0"
---

# apptest-visual — visual diff

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.3 · group principles
`../apptest/shared/test-methods.md` (T1–T10) · measurement rules
layout-a11y, language rules locale-time · capture tool store-assets
(`shot_host.sh`) · report `../apptest/shared/report.md`.

**Default contract:** Scans, suggests a matrix, compares captures; writes
baseline and diff images OUTSIDE the project. Writes into the project (tests,
baselines) only with approval; adds no hooks to app code (T3).

## When to use

- A shared component, theme, font or layout code changed: "did it break other
  screens?"
- A new language, dark mode or large text support was added.
- Before release: screen-by-screen comparison with the previous released version.

## Out of scope

- Measurement rules (contrast, cut-off text, 44 pt) → layout-a11y; this member
  finds the CHANGE, they say whether the change breaks a rule.
- Size / alpha rules for store images → store-assets.
- Interaction (what happens on tap) → crawl / persona.

## Step 0

CONVENTIONS §5 and §6. A capture tour takes screens × matrix (16 captures per
screen is typical): estimate the time and get approval; a quick tour is
recommended. Disk: full-size PNG ~0.5–1.5 MB; 20 screens × 16 = ~300 MB per set
(§5.6 free space). This member's items do not rest on an App Store rule.

## Principles specific to this member

- **VI-P1** Keeps baselines outside the project; puts them in the project only
  with the user's permission.
  *Why:* hundreds of MB of images bloat the repo (e.g. the Kickstarter iOS repo
  has 1609 baselines, 156 MB). `vi_diff --out` refuses to write if it points
  inside a git repo.
- **VI-P2** Reports differences with measurements (pixels / ratio / box); does
  not compare until animation, clock and random content are pinned.
  *Why:* unpinned screens produce false differences on every tour; noise hides
  real differences and the tool gets abandoned.
- **VI-P3** The matrix is representative, not the full product: languages are
  development language + a long-text language + right-to-left + CJK; appearance
  light / dark (or the app's themes); devices smallest and largest (+ iPad); text
  default and largest. The full language set only on request.
  *Why:* in a 163-language app the full product is ~2000 captures per screen;
  language bugs mostly show up in the representative languages.
- **VI-P4** The default threshold is 0: every pixel outside tolerance is reported;
  the threshold is raised only with a reason.
  *Why:* on a full-size iPhone screen, a changed button label is ~0.02%; "ignore
  under 0.1%" silently passes this kind of regression.
- **VI-P5** An expected difference (a screen deliberately changed in this version)
  is not a finding: show it to the user for approval; after approval the new set
  becomes the baseline, and the old baseline is not deleted.
  *Why:* updating the baseline silently also marks real regressions as "accepted".

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
`languages`, `platforms` (iPad), technology (golden tool).

## Scan

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-visual/scripts/vi_scan.py" <root> [--json]
```

| Id | What | Severity |
|---|---|---|
| VI-10 | Image comparison (golden / snapshot) test present / absent; code that only CAPTURES | INFO |
| VI-11 | Baselines in the repo (count, MB); may be orphaned if no comparing test exists | INFO / SUGGESTION |
| VI-12 | Pinning hooks: animation, status bar, clock, (Flutter golden) font | INFO |
| VI-13 | Flutter golden tests also run on Linux CI (a baseline produced on a Mac renders differently) | SUGGESTION |
| VI-14 | Matrix suggestion (representative languages, appearance, device, text) and capture count | INFO |

## Comparison

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-visual/scripts/vi_diff.py" <base> <new> --out <diff_folder> \
        [--tolerance 8] [--max-ratio 0] [--mask-top <px>] [--mask x,y,w,h] [--mask-file masks.json] [--json]
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-visual/scripts/vi_diff.py" --self-test
```

Files are matched by relative path. Exit code 0 = no difference above threshold,
1 = difference / size difference / missing, 2 = usage or read error. JPEG is not
read (lossy; capture PNG). Details: `references/stabilize.md`.

## Setup (good to know from the start)

1. The app can launch for tests with demo data, a fixed clock and animations off
   (a single entry point).
2. Screens can be opened directly from the test entry (without navigating).
3. Status bar and appearance / text / language can be set on the simulator
   (temporary simulator, `sim_session.py`).
4. A baseline set is kept for each release (outside the project, named by version).

## Test

1. `vi_scan.py` → infrastructure, orphaned baselines, missing pinning, matrix.
2. If the project has its own image test, run the matrix from there; otherwise:
3. Pin (`references/stabilize.md` §1) → capture the baseline set (previous
   version's commit in a worktree, CONVENTIONS §5) → capture the new set (same
   simulator and iOS version).
4. `vi_diff.py` → list of differences; open each with its image.
5. Sort: expected (get approval, VI-P5) / regression (VI-20, VI-21) / environment
   (VI-22, VI-24: mask or pin, capture again).

## Release (before submitting)

1. Quick matrix against the previous released version: no unexpected differences.
2. Screens changed in this version were shown to the user and approved.
3. The approved set was stored as the new baseline (outside the project).

## Report

`shared/report.md`. Per image: name (screen · language · appearance · device ·
text), status, changed pixels / ratio, box, path to the diff image
(≈700 px downscaled samples, principle 17). In the environment: simulator model,
iOS version, tolerance, threshold, masks.
