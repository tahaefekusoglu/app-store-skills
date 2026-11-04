# Store screenshot tour: theme × language × screen

Goal: REAL images of the main screens in every theme and language (2.3.3), at a
size the App Store accepts, without alpha, with a clean status bar. The image is
taken by `xcrun simctl io … screenshot` on the Mac, not by the app itself:
status bar included, at the device's real resolution.

## Preparation (CONVENTIONS §5, §7)

1. **Your own simulator** (not the user's): a device in the required size class.
   Take the size table from the current page (principle 7), because the page
   changes: the table read as "medium required" on 28 October 2026 said on 29
   October "6.5" is required if there is no 6.9", medium is scaled from the large
   set". Safe default: BOTH 6.9" (1320×2868, e.g. iPhone 18 Pro Max) and medium
   (1206×2622, e.g. iPhone 18 Pro). Also 13" iPad if iPad is supported.
   `xcrun simctl create apptest-shots "<device>" <runtime>` → after the tour,
   `simctl delete`.
2. **Status bar:** `xcrun simctl status_bar <UDID> override --time "9:41"
   --dataNetwork wifi --wifiMode active --wifiBars 3 --cellularMode active
   --cellularBars 4 --batteryState charged --batteryLevel 100` → after the tour,
   `status_bar <UDID> clear` (while the device is ON; it does not clear when off).
3. **Appearance:** `xcrun simctl ui <UDID> appearance light|dark` (if the app
   follows the system).
4. **Demo data (SA-P2):** in memory or in a temporary database, fictional:
   no real people, brands or copyrighted content; names, amounts and dates look
   realistic; the clock is FIXED (if the app has a clock hook) and consistent with
   today (form screens show the real date; e.g. a budgeting app's tour moved its
   demo data's dates to today).
5. **Debug banner / developer items hidden** (Flutter:
   `WidgetsApp.debugAllowBannerOverride = false`).

## Handshake capture (any technology)

```sh
sh ~/.claude/skills/apptest-store-assets/scripts/shot_host.sh <UDID> <OUT> &
# … the tour runs …
kill "$(cat <OUT>/host.pid)"
```

On each screen the tour: (1) prepares the screen and waits for animations to
finish, (2) writes `"<theme>/<lang>_<NN>_<screen>"` to `<OUT>/req.txt`, (3) waits
until `<OUT>/ack.txt` shows the same name (with a timeout). This works with any
technology because an app in the simulator can write to the Mac's file system.
Write the tour with the app's own test tool:

| Technology | Tour tool | Note |
|---|---|---|
| Flutter | `integration_test` (`flutter test integration_test/… -d <UDID> --dart-define=SHOT_DIR=…`) |a tour written for your app: seed demo data, walk the screens, ask the host script for each shot|
| SwiftUI / UIKit | XCUITest (UI test target): demo data through `XCUIApplication` launch arguments; handshake or `XCUIScreen.main.screenshot()` + `XCTAttachment` (status bar separately) | fastlane `snapshot` does the same with a language × device matrix |
| React Native / Expo | Detox (`device.takeScreenshot`) or Maestro (`takeScreenshot`) | `runScript` in Maestro for the handshake |
| Game engine | the engine's own test tool or by hand; capture is still `simctl io` | |

**Known traps (from real tours):**
- **The tour freezes when the Mac's display sleeps.** With a headless simulator,
  if the Mac's display goes to sleep, screen refresh stops; the test waits for a
  frame, hangs for minutes and hits its own time limit (`'!_expectingFrame'`
  error). Wrap the tour in `caffeinate -dimsu <command>`: valid only while the
  command runs, it does NOT change settings (T4). Newer Xcode versions may not
  include the Simulator app; do not rely on opening a window to solve this (e.g.
  a budgeting app's 1206×2622 tour, 2026-10-28).
- **Request folder = the folder the receiver watches.** The tour writes to
  `SHOT_DIR`, `shot_host.sh` watches the same folder; create the folder first. If
  they differ, the tour fails with `PathNotFoundException` or a timeout.
- **A dialog that will not close:** put an upper limit on the "close open pages"
  loop (e.g. 12 tries, then `popUntil(isFirst)`); otherwise a dialog that will not
  close locks the tour forever.
- **If one theme fails, the next ones fail in a chain** (the binding state breaks
  within the same test): rerun only the remaining themes with `SHOT_THEMES`, do
  not delete the finished ones.

Long job: give a time estimate, run in the background, split it up (principle 13).
Image count = themes × languages × screens; the user may say "the main screens are
enough" (e.g. a budgeting app went from 23 screens to 8 main ones). For screens
that depend on a name (greeting, profile), recapture only those.

## Afterwards

1. **Remove alpha:** `swiftc -O scripts/noalpha.swift -o <temp>/noalpha &&
   <temp>/noalpha <raw> <final>` (the input does not change).
2. **Check:** `python3 -I scripts/assets_check.py <final> [--ipad]`.
3. **Organize and name:** `<person>/<lang>/<NN theme>/<NN screen>.png`; a preview
   HTML (with relative paths) in the user's folder for viewing.
4. **Clean up (§7):** status bar `clear`, shut down / delete the simulator, stop
   the receiver with `host.pid`, delete the raw images from the temp folder; the
   delivered folder is NOT deleted.
5. **Sharing:** to send uncompressed, zip and send as a "document" (WhatsApp and
   email compress images sent as photos).
