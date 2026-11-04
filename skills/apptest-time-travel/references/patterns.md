# time-travel patterns: fixing and moving the clock

The Mac's clock and time zone are NOT TOUCHED (TT-P1, T4). Time only changes
inside the test process: the app's clock hook, the test framework's fake clock,
the `TZ=` environment variable, `SIMCTL_CHILD_TZ` on the simulator.

## Scenario list (the minimum under TT-P2)

`python3 -I scripts/tt_scan.py --moments --tz <zone> --year <year>` gives the
exact moments. Run each scenario in one zone with DST (e.g. Europe/Berlin,
America/Los_Angeles) and one zone without DST (e.g. Europe/Istanbul):

| Id | Moment | Check |
|---|---|---|
| TT-S1 | Midnight (23:59:59 → 00:00:00) | "today / yesterday", day counts, start-of-day writes |
| TT-S2 | Month end (31 → 1, 30 → 1, end of February) | day-of-month rule (months without a 31st), period closing |
| TT-S3 | Feb 29 (leap year) and a non-leap year | yearly repeats, "the 29th of every month" |
| TT-S4 | Year end | per-year summaries, week number |
| TT-S5 | DST FORWARD (23-hour day) | day difference, scheduled notification time |
| TT-S6 | DST BACK (25-hour day) | the same hour happening twice, duplicate writes |
| TT-S7 | Clock moved BACK (by the user or network time) | future-dated records, a closed period reopening |
| TT-S8 | Long gap (30+ days unopened) | missed work written exactly once, chained closings |
| TT-S9 | Time zone change (travel) | local / UTC mix-ups |

## Dart / Flutter

```dart
// If the app takes a clock hook (e.g. Riverpod clockProvider):
ProviderScope(overrides: [clockProvider.overrideWithValue(() => fakeNow)], child: const App());
// With package:clock:
withClock(Clock.fixed(DateTime(2026, 3, 29, 1, 59)), () => body());
// Time zone: at process level
//   TZ=Europe/Berlin flutter test
//   TZ=America/Los_Angeles flutter test test/<file>
```

## Swift

```swift
// Clock as a dependency:
struct Env { var now: () -> Date = Date.init }
// in the test:
env.now = { ISO8601DateFormatter().date(from: "2026-03-29T00:59:00Z")! }
// Time zone: at the start of the test
NSTimeZone.default = TimeZone(identifier: "Europe/Berlin")!
// or the environment variable TZ=Europe/Berlin in the test plan
// For the app on the simulator: SIMCTL_CHILD_TZ=Europe/Berlin xcrun simctl launch <UDID> <bundle>
```

## JavaScript / TypeScript (Jest)

```ts
jest.useFakeTimers();
jest.setSystemTime(new Date('2026-03-29T00:59:00Z'));
// ... action ...
jest.advanceTimersByTime(2 * 60 * 60 * 1000);
// Time zone: TZ=Europe/Berlin npx jest
```

## If there is no clock hook (TT-P2)

Not a finding. Options: (1) a time zone tour with `TZ=` alone, (2)
`SIMCTL_CHILD_TZ` for the app on the simulator, (3) suggesting a small hook; the
user decides, and it is not added without approval (T3).
