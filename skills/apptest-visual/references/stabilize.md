# visual — pinning, capture and comparison

Visual comparison means something only if the ONLY difference between two captures
is the app's changed code (VI-P2). Every false difference (clock, animation, random
data) buries real differences in noise, and the user turns the tool off.

## 1. Pin (baseline and new capture under the SAME conditions)

| What | Why it differs | How to pin |
|---|---|---|
| Simulator model and iOS version | font rendering and antialiasing change between versions | same model + same runtime; write it in the baseline folder name (`iPhone-17-Pro_iOS-26.1`) |
| Status bar | time, battery, signal | `xcrun simctl status_bar <UDID> override --time 9:41 --batteryState charged --batteryLevel 100 --cellularBars 4 --wifiBars 3` (`sim_session.py create --status-bar`); or `vi_diff --mask-top <px>` |
| Clock / date content | "N days left", "today", relative time | the app's clock hook (time-travel TT-10); otherwise mask that region |
| Animation | captured mid-transition | wait on a condition before capturing (element in place) and disable animation from the test entry (`UIView.setAnimationsEnabled(false)`, Flutter `timeDilation` / `pumpAndSettle`, RN `jest.useFakeTimers`); mask endless animations (loading) |
| Data | random / real data | seeded demo data, fixed order |
| Network images | late-loading image | network mock or fixed placeholder; wait for it to load |
| Cursor | blinking cursor | capture with no focus or mask the cursor region |
| Text scale / appearance / language | captures get mixed up | each in the file name; `sim_session.py --appearance`, `--content-size`; language `-AppleLanguages (xx) -AppleLocale xx_YY` |
| Switching apps and returning | iOS puts a "◀ <previous app>" back link in the status bar (e.g. a 252×83 px difference on a budgeting app's lifecycle tour) | return via the home screen or use `--mask-top` (~150 px on a 3× screen) |
| Keyboard | hardware / software keyboard difference | `sim_session.py --software-keyboard` (or always off) |

Example: a budgeting app's store tour (`store_shots_test.dart`) uses the same
approach: matrix via `SHOT_LOCALE`, `SHOT_THEMES`, `SHOT_SCREENS`; demo data and a
fixed clock; status bar 9:41; the receiver `shot_host.sh` (store-assets) captures
with `simctl io screenshot`.

## 2. Capture

Naming (vi_diff matches files by relative path):

```
<root>/<screen>/<language>__<appearance>__<device>__<text>.png
e.g. today/tr__dark__iPhone-SE__xxxl.png
```

Baseline set OUTSIDE the project (VI-P1):
`~/.cache/apptest/<project-key>/visual/<version-or-commit>/`
(project key: `printf %s "$PWD" | shasum | cut -c1-12`). The new set goes in a
separate folder with the same structure. Into the repo only if the user asks.

Capture paths (whichever the project has):
- The project's image test (Flutter `matchesGoldenFile`, swift-snapshot-testing
  `assertSnapshot`, iOSSnapshotTestCase, `jest-image-snapshot`): compares against
  its own baseline; vi_diff is not needed. Run the matrix from there.
- Simulator tour: open each screen via the app's test entry, then the receiver
  (`apptest-store-assets/scripts/shot_host.sh`) or directly
  `xcrun simctl io <UDID> screenshot --type=png <file>`.
- XCUITest: `XCUIScreen.main.screenshot().pngRepresentation` → file
  (into the chosen folder, not a test attachment).

## 3. Compare

```sh
python3 -I ~/.claude/skills/apptest-visual/scripts/vi_diff.py <base> <new> --out <diff> \
        --mask-top 0 --tolerance 8 [--mask-file masks.json] [--max-ratio 0]
```

- `--tolerance`: per-channel difference ignored (0–255). 8 removes antialiasing
  noise and keeps color changes. 0–2 also works on the same simulator and version.
- `--max-ratio`: default 0 — every pixel outside tolerance is reported. A small
  button label on a 1320×2868 screen is ~0.02%; a 0.1% threshold misses it. Raise
  the threshold only for a known noise, with a reason.
- `masks.json`: `{"today/*": [[0, 0, 1320, 160]], "*__dark__*": [[40, 900, 300, 60]]}`
  (file pattern → x, y, w, h in pixels).
- Output: changed pixel count and ratio, the change's box, diff image (faded
  background + red changed pixels), size difference, missing / new image. Exit code
  1 = there is something to look at.
- Assurance: `vi_diff.py --self-test` (all PNG types, interlaced, known difference).
  The reader matched macOS ImageIO exactly on 926 real PNGs (8/16 bit, RGB/RGBA,
  palette, interlaced).
- Speed: pure Python; an unchanged image is instant (byte / data equality), a changed
  full-size (1320×2868) pair takes ~6 s on one core (measured: Python 3.9, Apple
  Silicon); parallel with `--jobs` (default core count).

## 4. Interpret

| Id | What | Severity |
|---|---|---|
| VI-20 | Difference on a screen that should not have changed in this version (regression) | USER BUG (visible breakage: cut-off text, shifted button, missing element) or SUGGESTION (style only) |
| VI-21 | Breakage in only one language / appearance / text size | USER BUG — written under the layout-a11y / locale-time id |
| VI-22 | Size difference (different pixel size on the same device) | environment: different simulator / scale — not a finding, capture again |
| VI-23 | Missing / new screen | INFO: did the matrix change? |
| VI-24 | False difference that cannot be pinned (different on every tour) | environment: mask or pin; not a finding |

An expected difference (a screen deliberately changed in this version) is not a
finding: show the difference to the user for APPROVAL; after approval the new set
becomes the baseline (the old baseline is not deleted, it stays in its version folder).
