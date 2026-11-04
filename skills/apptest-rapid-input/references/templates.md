# rapid-input — scenarios and templates

## Core method: widen the window, count the result from the data

Rapid input bugs appear **mid-operation**: a second tap, back or background
before the first tap's write has finished. On a real device this window is
milliseconds; relying on timing in a test gives flaky results (T6).
Instead:

1. **Open the window:** make the dependency that writes (database, network,
   purchase) HOLDABLE in the test: Dart `Completer`, Swift
   `CheckedContinuation` / `AsyncStream`, a manually resolved JS `Promise`, a delay in the
   network fake. If the app has no test entry point of its own, set this up in test
   code only; never add it to app code silently (T3).
2. **Attack:** with the window open, a second tap / submit / back /
   background.
3. **Close the window:** complete the held operation (or end it with an error).
4. **Count:** rows in the database, calls to the fake, requests
   sent (RI-P1). On-screen flicker or a loading indicator shown twice is NOT
   a finding.

## Scenarios

| Id | Scenario | How | Expected |
|---|---|---|---|
| RI-S1 | Double tap (same frame) | two taps, no `pump` / wait between | one record |
| RI-S2 | Repeated submit (window open) | 1st tap → operation held → 2nd tap → complete | one record; 2nd tap is ignored or does not queue |
| RI-S3 | Keyboard submit + button | "send/return" in the field and Save at the same time | one record |
| RI-S4 | Back mid-operation | held → back / swipe the sheet closed → complete | no crash; the record is written fully or not at all (nothing partial); no attempt to update the closed screen |
| RI-S5 | Background mid-operation | held → background → complete → foreground | record once; screen correct on return |
| RI-S6 | Two concurrent operations (service level) | call the same action twice AT THE SAME TIME (`Future.wait`, `async let`, `Promise.all`) | the app's rule: one record or two full records; no intermediate state / lost update |
| RI-S7 | Two different actions at once | e.g. edit + delete, add + bulk delete | invariants hold (total = parts); deleted items do not come back |
| RI-S8 | Purchase / payment double tap | RI-S1 / RI-S2 on the faked purchase service | purchase request ONCE (counter); no real purchase (T2) |
| RI-S9 | Retry after error | 1st request held → timeout / error → user retries → 1st request also returns late with success | one record (idempotency key or server defence) |

Finding ids:

| Id | What | Severity |
|---|---|---|
| RI-20 | Second record on double / repeated tap (RI-S1, S2, S3) | USER BUG (if the static cause is IA-10, written under that id) |
| RI-21 | Crash, uncaught error or partial record on back / background mid-operation (RI-S4, S5) | USER BUG |
| RI-22 | Lost update / broken invariant in concurrent operations (RI-S6, S7) | USER BUG |
| RI-23 | Payment / purchase request sent twice (RI-S8) | USER BUG |
| RI-24 | Duplicate record on retry after error (RI-S9) | USER BUG |
| RI-25 | Second tap is ignored but the user is shown nothing (unclear whether the operation is running) | SUGGESTION |

## Flutter (widget test)

```dart
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

// PER PROJECT: the app's repository and test entry point (via dependency override).
// abstract class OrderRepo { Future<void> save(Order o); }
// Widget appWith(OrderRepo repo) => ProviderScope(overrides: [...], child: const MyApp());

/// Window: a fake repository that holds the write.
class SlowRepo implements OrderRepo {
  final gate = Completer<void>();
  final _rows = <Order>[];
  var calls = 0;
  int get count => _rows.length;
  @override
  Future<void> save(Order o) async {
    calls++;
    await gate.future;
    _rows.add(o);
  }
}

void main() {
  testWidgets('RI-S2: second Save while in flight gives one record', (t) async {
    final repo = SlowRepo();
    await t.pumpWidget(appWith(repo));
    await t.enterText(find.byKey(const Key('amount')), '250');
    await t.tap(find.byKey(const Key('save')));
    await t.pump();                                  // 1st record held
    await t.tap(find.byKey(const Key('save')), warnIfMissed: false);  // may be hidden / disabled
    await t.pump();
    repo.gate.complete();
    await t.pumpAndSettle();
    expect(repo.count, 1, reason: 'one record in the data (RI-P1)');
  });

  testWidgets('RI-S4: back while in flight, no crash and no partial record', (t) async {
    final repo = SlowRepo();
    await t.pumpWidget(appWith(repo));
    await t.tap(find.byKey(const Key('save')));
    await t.pump();
    await t.binding.handlePopRoute();                // system back
    await t.pump();
    repo.gate.complete();
    await t.pumpAndSettle();
    expect(t.takeException(), isNull);               // no setState / context on the closed screen
    expect(repo.count, anyOf(0, 1));                 // narrow per the app's rule (RI-P3)
  });

  testWidgets('RI-S5: background while in flight', (t) async {
    final repo = SlowRepo();
    await t.pumpWidget(appWith(repo));
    await t.tap(find.byKey(const Key('save')));
    await t.pump();                                  // held
    for (final s in [AppLifecycleState.inactive, AppLifecycleState.hidden, AppLifecycleState.paused]) {
      t.binding.handleAppLifecycleStateChanged(s);
      await t.pump();
    }
    repo.gate.complete();
    for (final s in [AppLifecycleState.hidden, AppLifecycleState.inactive, AppLifecycleState.resumed]) {
      t.binding.handleAppLifecycleStateChanged(s);
      await t.pump();
    }
    await t.pumpAndSettle();
    expect(repo.count, 1);
  });
}
```

If the real database stream (drift etc.) uses real timers, run inside
`tester.runAsync`. If the button hides or disables mid-operation, the second `tap` warns of a
"miss": with `warnIfMissed: false` this too is a VALID result (the user cannot press it
either).

## Service level (any language; cheapest, most definitive)

```dart
// Dart
await Future.wait([writer.addExpense(e), writer.addExpense(e)]);
expect(await countExpenses(db), 1 /* or whatever the rule says */);
```
```swift
// Swift
async let a: Void = store.add(item)
async let b: Void = store.add(item)
_ = try await (a, b)
XCTAssertEqual(try store.count(), 1)
```
```ts
// TypeScript
await Promise.all([api.createPost(p), api.createPost(p)]);
expect(mockServer.requests('POST /posts')).toHaveLength(1); // or whatever the rule says
```
```csharp
// C#
await Task.WhenAll(service.SaveAsync(x), service.SaveAsync(x));
Assert.Equal(1, await repo.CountAsync());
```

The expectation is the app's rule: for some actions two records are correct
(entering two separate expenses). The test may also be "two calls → two FULL records, no intermediate state";
if the rule is not in the code / docs, ask the user.

## XCUITest (any technology, built app)

Verification status (2026-11-03): compiled, not yet run on a real app.

```swift
func testDoubleTapSaveCreatesOneRecord() {
    let app = XCUIApplication()
    app.launchArguments = ["-uitest", "-slow-writes"]   // if the app has its OWN test entry point (T3)
    app.launch()
    let save = app.buttons["save"]                     // accessibilityIdentifier
    XCTAssertTrue(save.waitForExistence(timeout: 5))
    // Same frame: two taps by coordinate (doubleTap may count as one gesture)
    let c = save.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
    c.tap(); c.tap()
    // Result from the screen: one row in the list
    // In SwiftUI the identifier is often on the row's content, not the cell: do not bind to the type
    let rows = app.descendants(matching: .any).matching(identifier: "order-row")
    XCTAssertTrue(rows.firstMatch.waitForExistence(timeout: 10))
    XCTAssertEqual(rows.count, 1)
}

func testBackgroundWhileSaving() {
    let app = XCUIApplication()
    app.launchArguments = ["-uitest", "-slow-writes"]
    app.launch()
    app.buttons["save"].tap()                          // while the operation is held:
    XCUIDevice.shared.press(.home)
    app.activate()
    XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10))   // the transition is not instant: wait on a condition
}
```

If the window cannot be opened from inside the app (no test entry point), only RI-S1 is reliable in XCUITest;
RI-S2 and later are done at the service level.

## React Native (Jest + Testing Library; Detox)

```tsx
test('RI-S1: double press gives one request', async () => {
  let release!: () => void;
  const create = jest.fn(() => new Promise<void>(r => { release = r; }));
  render(<NewPost create={create} />);
  const btn = screen.getByRole('button', { name: /post|gönder/i });
  fireEvent.press(btn); fireEvent.press(btn);       // same tick
  release();
  await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
});
```

Detox: `await element(by.id('save')).multiTap(2);` then count the list.

## Purchases (RI-S8)

Fake the purchase service (StoreKit test session, a fake service for
`in_app_purchase`, RevenueCat test mode): the fake counts `buy` calls
and holds the first call. RI-S1 / RI-S2 on the paywall's buy button; expected
counter = 1. NO real purchases and no automated taps with a sandbox account
(T2).

## By hand (UI with no tree, games)

In the temporary simulator: add a 3 s delay to the network fake (network-chaos's
proxy or the app's test setting) → three rapid taps on the action button →
count the result from the screen and (if any) the exported data.
