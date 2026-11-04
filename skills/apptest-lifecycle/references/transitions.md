# lifecycle — transitions, scenarios, templates

## States

```
not running ──launch──▶ foreground (active)
foreground ⇄ inactive    (app switcher, Control Center, incoming call, system / Face ID dialog)
inactive ⇄ background    (home screen, another app)
background ──▶ suspended ──▶ system kills (memory, permission change, update) ──▶ not running
```

Important facts (Apple documentation):
- When the system kills a suspended app, **no code runs**;
  `applicationWillTerminate` is not called in most cases. Save on going to the
  background or at the moment of change.
  https://developer.apple.com/documentation/uikit/uiapplicationdelegate/applicationwillterminate(_:)
- Observation (not written as a rule in the docs): when a privacy permission
  (photos, location, contacts…) is turned off in Settings, iOS usually ends the
  running app; the next launch is cold. Do not assume this for every permission
  and version — observe it in LC-S5 (did it stay open, did it restart).
- The app switcher shows the last screenshot taken on going to the background.
  https://developer.apple.com/documentation/uikit/managing-your-app-s-life-cycle
- When the Face ID / Touch ID dialog opens, the app becomes "inactive"; lock
  logic must not treat this as a new lock event.

## Scenarios

Each scenario is a TRANSITION (LC-P1): "from → to", what was done before, what
to look at afterwards.

| Id | Transition | Before | Look at afterwards |
|---|---|---|---|
| LC-S1 | foreground → background → foreground (short) | in the middle of a screen, list scrolled | same screen, same data; work does NOT run TWICE on return (backup, sync, save) |
| LC-S2 | foreground → inactive → foreground | sensitive screen open (in a locked app) | app switcher image is covered; the auth dialog's "inactive" causes no lock loop |
| LC-S3 | background → system kills → cold start | half-filled form / draft, a deep screen | draft and saved data in place; navigation position (the app's decision) |
| LC-S4 | save → immediately background → system kills → launch | record just made | record persisted (LC-12) |
| LC-S5 | revoke permission (app is killed) → launch; grant permission → return to foreground | screen using the permission | no crash / dead end, clear state; the screen updates when the permission is granted (LC-14) |
| LC-S6 | memory warning (in foreground and background) | big list / image / video open | no crash, no data loss; screen rebuilds on return |
| LC-S7 | long background (hours / next day) → foreground | screen showing "today" info | date, duration, session recalculated (clock: time-travel hook) |
| LC-S8 | lock on → background → foreground; auth cancelled; old auth finishing in the background | app lock on | locked on return; "unlock" path after cancel; an old auth result does NOT open the new lock |
| LC-S9 | cold start by tapping a notification / deep link | app closed | correct screen; routing happens AFTER launch work (migration, cycle check) finishes |

Findings:

| Id | What | Severity |
|---|---|---|
| LC-20 | Saved data lost during a transition (LC-S3, S4, S6) | USER BUG |
| LC-21 | Crash / uncaught error during a transition | USER BUG |
| LC-22 | Locked / sensitive content visible in the app switcher (LC-S2) | USER BUG (if the app promises a lock), otherwise SUGGESTION |
| LC-23 | Work ran twice on return (double record / double backup / double request) | USER BUG (if data was duplicated), otherwise SUGGESTION |
| LC-24 | Crash or dead end after a permission change (LC-S5) | USER BUG |
| LC-25 | Half-filled form / draft lost (LC-S3) | SUGGESTION (may be USER BUG on a long form; ask the user) |
| LC-26 | Stale screen on return: date, permission state, session not updated (LC-S5, S7) | SUGGESTION; USER BUG if it shows wrong data |
| LC-27 | Lock loop, or an old auth in the background opens the lock (LC-S8) | USER BUG |

Example (a budgeting app): the app lock engages only on going to the BACKGROUND
(hidden / paused); the "inactive" caused by the auth dialog does not count as a
lock (otherwise the dialog reopened as soon as it closed); in the app switcher
(inactive) content is still covered; each lock is a new session, so an old auth
finishing in the background cannot open the new lock. In automatic backup, the
second event of the same exit (within 1 min) is skipped (LC-23).

## How to trigger

| Transition | Flutter (widget / integration) | XCUITest (any technology) | Temporary simulator (Mac) |
|---|---|---|---|
| foreground → background → foreground | state sequence (below) | `XCUIDevice.shared.press(.home)` → `app.activate()` | — |
| inactive | `AppLifecycleState.inactive` | not directly: post the notification at unit level (below) | — |
| system kills → cold start | rebuild the app with the same data store (`pumpWidget`) | `app.terminate()` → `app.launch()` | `xcrun simctl terminate <UDID> <bundle>` → `xcrun simctl launch …` |
| revoke / grant permission | change the permission mock's state + `resumed` | `xcrun simctl privacy` (before the test) | `xcrun simctl privacy <UDID> revoke|grant <service> <bundle>` |
| memory warning | `tester.binding.handleMemoryPressure()` | unit: `NotificationCenter.default.post(name: UIApplication.didReceiveMemoryWarningNotification, object: nil)` | Simulator › Debug › Simulate Memory Warning (by hand) |
| long background | advance the clock hook + `resumed` | clock via `launchArguments` (if the app has a test entry) | — (the Mac's clock is NOT touched, T4) |
| cold start from a notification | pass the notification payload to the launch path | `xcrun simctl push <UDID> <bundle> payload.apns` then tap | `xcrun simctl push …` (local simulator only) |
| deep link | pass to the route / link handler | `app.open(URL)` (iOS 16.4+) | `xcrun simctl openurl <UDID> <url>` |

When comparing screenshots: on returning from another app, iOS puts a
"◀ <previous app>" back link in the status bar; mask this false difference with
`vi_diff --mask-top` (e.g. a budgeting app's LC-S1 tour).

`simctl push` only drops a local notification on the simulator; it sends nothing
outside (complies with T2).

## Flutter

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

// PER PROJECT (the app's test entry and store):
//   Widget appWith(Db db)              opens the app with the given store
//   Db openTestDb()                    in-memory store (LC-S1, S6)
//   String tempDbFile()                temporary FILE path (LC-P3: cold start with a persistent store)
//   Db openDb(String file)             open from file;  Future<void> closeDb(Db db)
//   Future<Map<String, int>> snapshotCounts(Db db)   row count per table

/// Transition in valid order (LC-P4): AppLifecycleListener expects the intermediate states.
Future<void> toBackground(WidgetTester t) async {
  for (final s in [AppLifecycleState.inactive, AppLifecycleState.hidden, AppLifecycleState.paused]) {
    t.binding.handleAppLifecycleStateChanged(s);
    await t.pump();
  }
}

Future<void> toForeground(WidgetTester t) async {
  for (final s in [AppLifecycleState.hidden, AppLifecycleState.inactive, AppLifecycleState.resumed]) {
    t.binding.handleAppLifecycleStateChanged(s);
    await t.pump();
  }
}

void main() {
  testWidgets('LC-S1: short background — same data, work runs once', (t) async {
    final db = openTestDb();
    await t.pumpWidget(appWith(db));
    final before = await snapshotCounts(db);
    await toBackground(t);
    await toForeground(t);
    await t.pumpAndSettle();
    expect(await snapshotCounts(db), before);        // returning created no new record / duplicate work
    expect(t.takeException(), isNull);
  });

  testWidgets('LC-S3: system kills while suspended → cold start', (t) async {
    final file = tempDbFile();
    final first = openDb(file);
    await t.pumpWidget(appWith(first));
    await t.enterText(find.byKey(const Key('note')), 'half-written draft');
    await toBackground(t);
    await closeDb(first);                            // killed while suspended: NO code runs, just close (LC-P2)
    await t.pumpWidget(const SizedBox());            // old tree goes away
    await t.pumpWidget(appWith(openDb(file)));       // cold start
    await t.pumpAndSettle();
    // The expectation is the app's rule: does the draft come back? Is saved data in place?
  });

  testWidgets('LC-S6: memory warning', (t) async {
    await t.pumpWidget(appWith(openTestDb()));
    t.binding.handleMemoryPressure();
    await t.pumpAndSettle();
    expect(t.takeException(), isNull);
  });
}
```

After `toBackground`, the "kill" is simulated without saving: on real iOS no code
runs in a suspended app; a save relying on a dispose / detached handler is lost
in this test (the correct result).

## XCUITest

Verification status (2026-11-03): compiled, not yet run on a real app (the Flutter
template and simctl transitions were run).

```swift
import XCTest

final class LifecycleTour: XCTestCase {
    func testBackgroundAndBack() {
        let app = XCUIApplication()                  // inside the test: also compiles in Swift 6 mode
        app.launchArguments = ["-uitest"]            // if the app has its OWN test entry
        app.launch()
        let title = app.navigationBars.firstMatch.identifier
        XCUIDevice.shared.press(.home)
        XCTAssertTrue(app.wait(for: .runningBackgroundSuspended, timeout: 10)
                      || app.wait(for: .runningBackground, timeout: 1))
        app.activate()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10))
        XCTAssertEqual(app.navigationBars.firstMatch.identifier, title)
    }

    func testKilledInBackgroundKeepsSavedData() {
        let app = XCUIApplication()
        app.launch()
        // … save …
        XCUIDevice.shared.press(.home)
        app.terminate()                              // kill while suspended
        app.launch()                                 // cold start
        XCTAssertTrue(app.cells.firstMatch.waitForExistence(timeout: 10))
    }
}
```

The app switcher image (LC-S2) cannot be read from XCUITest: verify by hand on a
temporary simulator (screenshot), or at unit level that the "inactive" handler
sets up the cover.

## Unit level (UIKit / SwiftUI)

```swift
NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
NotificationCenter.default.post(name: UIApplication.didEnterBackgroundNotification, object: nil)
NotificationCenter.default.post(name: UIApplication.didReceiveMemoryWarningNotification, object: nil)
NotificationCenter.default.post(name: UIApplication.willEnterForegroundNotification, object: nil)
```

This triggers the code listening for the notification (it is not a real system
transition); whether the cover was set, the save happened, and the work ran once
are measured here.

## React Native

```ts
import { AppState } from 'react-native';
// Jest: capture the AppState listener and call it by hand
const listeners: Array<(s: string) => void> = [];
jest.spyOn(AppState, 'addEventListener').mockImplementation((_e, cb: any) => {
  listeners.push(cb); return { remove: () => {} } as any;
});
// … render …
listeners.forEach(cb => cb('background'));
listeners.forEach(cb => cb('active'));
```

For a real transition use XCUITest or Detox (`device.sendToHome()`,
`device.launchApp({ newInstance: false })`, `device.terminateApp()`).
