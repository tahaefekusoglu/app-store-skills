# state-sim templates: seeded random use + invariants

Shared skeleton (same in every language): **seed → N steps → a random action at
each step → all invariants after the action → a rejected action must not have
changed state → coverage at the end (did every action SUCCEED at least once)**.
On failure, print the seed + step number + a log of the last 20 steps (T5).
Source example: a budgeting app's `test/state/ledger_simulation_test.dart`
(8 seeds × 400 steps; clock forward / BACK; concurrent write bursts; a tagged long
stress tour).

Invariants come from the app's DOMAIN (SS-P1: suggested from the code, the user
approves). General ones valid in every app:
- no crash / uncaught exception;
- saved = read / shown (write → read → same);
- a rejected action does not change state (before / after snapshots equal);
- total = sum of parts (counters, balances, carts);
- what must be unique is unique (single active record, unique name);
- what was deleted appears in no list.

## Dart (flutter_test / test)

```dart
import 'dart:math';
import 'package:test/test.dart';

class Sim {
  Sim(this.seed) : rnd = Random(seed);
  final int seed;
  final Random rnd;
  final log = <String>[];
  final ok = <String>{};
  late final AppUnderTest app; // set up with an in-memory database and a fixed clock

  late final actions = <String, Future<void> Function()>{
    'add': () => app.add(amount: 1 + rnd.nextInt(100000)),
    'edit': () => app.editRandom(rnd),
    'delete': () => app.deleteRandom(rnd),
    'clock forward': () async => app.clock.advance(Duration(hours: rnd.nextInt(72))),
    'clock BACK': () async => app.clock.advance(-Duration(hours: rnd.nextInt(24))),
  };

  Future<void> run(int steps) async {
    for (var i = 0; i < steps; i++) {
      final name = actions.keys.elementAt(rnd.nextInt(actions.length));
      final before = await app.snapshot();
      try {
        await actions[name]!();
        ok.add(name);
        log.add('$i $name');
      } on RejectedError catch (e) {
        log.add('$i $name → rejected: $e');
        expect(await app.snapshot(), before, reason: 'rejected action changed state\n${tail()}');
      }
      await checkInvariants(i);
    }
  }

  Future<void> checkInvariants(int step) async {
    final s = await app.snapshot();
    expect(s.total, s.parts.fold<int>(0, (a, b) => a + b), reason: 'step $step, seed $seed\n${tail()}');
    // ... domain-specific invariants ...
  }

  String tail() => log.skip(log.length > 20 ? log.length - 20 : 0).join('\n');
}

void main() {
  final succeeded = <String>{};
  for (final seed in [1, 2, 3, 4, 5, 6, 7, 8]) {
    test('simulation (seed $seed)', () async {
      final sim = Sim(seed);
      await sim.run(400);
      succeeded.addAll(sim.ok);
    });
  }
  test('every action succeeded at least once', () {
    for (final a in ['add', 'edit', 'delete']) {
      expect(succeeded, contains(a), reason: '$a never ran: coverage was silently lost');
    }
  });
}
```

Time zone tour: `TZ=Europe/Berlin flutter test <file>` (time-travel).
Long stress run: `tags: ['stress']` + a seed range from an environment variable;
skipped in the normal tour, run with `--run-skipped --tags stress`.

## Swift (XCTest)

Swift's standard random generator takes no seed; here is a small seeded one:

```swift
import XCTest

fileprivate struct SplitMix64: RandomNumberGenerator {
    var state: UInt64
    init(seed: UInt64) { state = seed }
    mutating func next() -> UInt64 {
        state &+= 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }
}

final class StateSimTests: XCTestCase {
    func testSimulation() async throws {
        for seed: UInt64 in 1...8 {
            var rng = SplitMix64(seed: seed)
            let app = try AppUnderTest.inMemory(now: Date(timeIntervalSince1970: 1_790_000_000))
            var log: [String] = []
            for step in 0..<400 {
                let action = Action.allCases.randomElement(using: &rng)!
                let before = try app.snapshot()
                do {
                    try await app.perform(action, using: &rng)
                    log.append("\(step) \(action)")
                } catch let e as RejectedError {
                    log.append("\(step) \(action) → rejected: \(e)")
                    XCTAssertEqual(try app.snapshot(), before, "rejected action changed state\n\(log.suffix(20))")
                }
                let s = try app.snapshot()
                // Stop at the first violation: the log shows that step. continueAfterFailure = false kills the runner in an async test.
                guard s.total == s.parts.reduce(0, +) else {
                    XCTFail("seed \(seed) step \(step): \(s.total) ≠ parts\n\(log.suffix(20).joined(separator: "\n"))")
                    return
                }
            }
        }
    }
}
```

## TypeScript (Jest)

```ts
function mulberry32(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

describe.each([1, 2, 3, 4, 5, 6, 7, 8])('simulation (seed %i)', (seed) => {
  it('invariants hold', async () => {
    const rnd = mulberry32(seed);
    const app = await createAppUnderTest({ now: new Date('2026-10-28T10:00:00Z') });
    const log: string[] = [];
    for (let step = 0; step < 400; step++) {
      const actions = Object.keys(app.actions);
      const name = actions[Math.floor(rnd() * actions.length)];
      const before = await app.snapshot();
      try {
        await app.actions[name](rnd);
        log.push(`${step} ${name}`);
      } catch (e) {
        if (!(e instanceof RejectedError)) throw e;
        expect(await app.snapshot()).toEqual(before);
      }
      const s = await app.snapshot();
      expect(s.total).toBe(s.parts.reduce((a, b) => a + b, 0));
    }
  });
});
```

## Shrinking a failure (SS-P2)

1. Take the failing seed and step number.
2. With the same seed, halve the step count to find the shortest N that fails.
3. Remove actions one by one from the last steps of the log and check whether
   it still fails; the shortest remaining sequence = the regression test (T8).
