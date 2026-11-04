# persona templates — end-to-end journey per persona

The skeleton is the same in every technology: **set up the persona (data, clock, text, language, account,
permission) → seeded agent loop per goal (personas.md §Agent) → measure goal
success by data or screen → journey report**. Findings do NOT fail the test
(exploration); only a crash / uncaught error and a setup error fail it.
Runs under a tag separate from the normal suite (`persona` / `crawl`).

Source example: a budgeting app's `test/features/persona_harness.dart` (agent + three
personas), `persona_usability_test.dart` (fast, test font) and
`integration_test/persona_tour_test.dart` (simulator, real iOS
font; persona via `--dart-define=PERSONA=<n>`).

## 1. Any technology: XCUITest (drives the built app from outside)

Verification status (2026-11-03): the template compiled for Swift 5 / 6 and iOS 15 / 17, but has NOT yet RUN on a real
app. First use may need small adjustments; read the result with that in mind.

SwiftUI, UIKit, React Native, MAUI, Flutter: all can be driven as a built `.app`
with XCUITest. It uses the app's own test entry point
(`launchArguments` / `launchEnvironment`) if there is one; otherwise
only text, language and permission personas are set up, and data / clock / account personas are
written as "could not test" (T3, PE-10).

```swift
import XCTest

fileprivate struct SplitMix64: RandomNumberGenerator {          // seeded (principle 14)
    var s: UInt64
    mutating func next() -> UInt64 {
        s &+= 0x9E3779B97F4A7C15
        var z = s; z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB; return z ^ (z >> 31)
    }
}

struct Goal { let name: String; let words: [String]; let typing: String?; let done: (XCUIApplication) -> Bool }
struct Persona {
    let name: String                 // by behaviour: "returning · largest text · small screen · de"
    let launch: [String]             // the app's OWN test entry point: ["-uitest", "-seed-rich"]
    let lang: String?                // "de"
    let largestText: Bool
    let voiceOver: Bool              // sees only labelled elements
    let hurried: Bool
    let goals: [Goal]
}

final class PersonaTour: XCTestCase {
    override func setUp() { continueAfterFailure = true }

    func run(_ p: Persona, seed: UInt64) throws -> [String] {
        var rng = SplitMix64(s: seed)
        let app = XCUIApplication()
        app.launchArguments = p.launch
        if let l = p.lang { app.launchArguments += ["-AppleLanguages", "(\(l))", "-AppleLocale", l] }
        if p.largestText {
            app.launchArguments += ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        }
        // Permission denial: simctl privacy revoke (Mac-side script) BEFORE launch, or:
        addUIInterruptionMonitor(withDescription: "permission") { alert in
            let deny = alert.buttons.element(boundBy: 0)      // "Don't Allow" (localized) is the first button
            if deny.exists { deny.tap(); return true }; return false
        }
        app.launch()
        var report: [String] = ["=== \(p.name) · seed \(seed)"]

        func targets() throws -> [(CGRect, String)] {
            let snap = try app.snapshot()
            let win = app.windows.firstMatch.frame
            var out: [(CGRect, String)] = []
            func walk(_ e: XCUIElementSnapshot) {
                let tappable: Set<XCUIElement.ElementType> = [.button, .cell, .link, .switch, .tab, .segmentedControl, .menuItem, .textField]
                if tappable.contains(e.elementType), e.isEnabled, win.intersects(e.frame), !e.frame.isEmpty {
                    let label = [e.label, e.value as? String ?? "", e.placeholderValue ?? ""].filter { !$0.isEmpty }.joined(separator: " ")
                    if !(p.voiceOver && label.isEmpty) { out.append((e.frame, label.isEmpty ? "(unnamed)" : label)) }
                }
                e.children.forEach(walk)
            }
            walk(snap); return out
        }
        func signature() -> String {
            app.staticTexts.allElementsBoundByIndex.prefix(10).map { $0.label }.joined(separator: "|")
        }
        func back() {
            let b = app.navigationBars.buttons.element(boundBy: 0)
            if b.exists && b.isHittable { b.tap() } else { app.swipeDown() } // sheet: swipe down to dismiss
        }

        for goal in p.goals {
            var next = 0, steps = 0, dead = 0, backs = 0, scrolls = 0, ok = false
            var recent: [String] = []
            while steps < 40 {
                steps += 1
                if goal.done(app) { ok = true; break }
                if let t = goal.typing, app.textFields.firstMatch.exists,
                   (app.textFields.firstMatch.value as? String ?? "").isEmpty {
                    app.textFields.firstMatch.tap(); app.textFields.firstMatch.typeText(t); continue
                }
                let all = try targets()
                if all.isEmpty { back(); backs += 1; continue }
                func score(_ l: String) -> Int {
                    let low = l.lowercased(); var s = 0
                    for (i, w) in goal.words.enumerated() where low.contains(w) { s += i == next ? 6 : (i > next ? 2 : 0) }
                    return recent.contains(l) ? s - 4 : s
                }
                let best = all.max { score($0.1) < score($1.1) }!
                // Goal word not visible: scroll first. The counter resets only on a tap / back (scrolling changes
                // the visible text, so a signature-based counter never fills up). No change means end of list: stop.
                if score(best.1) <= 0 && scrolls < 3 {
                    let before = signature()
                    app.swipeUp(); scrolls += 1
                    if signature() == before { scrolls = 3 }
                    continue
                }
                scrolls = 0
                let roll = Double.random(in: 0..<1, using: &rng)
                if roll < (p.hurried ? 0.15 : 0.08) { back(); backs += 1; continue }
                let pick = (score(best.1) > 0 && roll < 0.82) ? best : all.randomElement(using: &rng)!
                let before = signature()
                app.coordinate(withNormalizedOffset: .zero)
                   .withOffset(CGVector(dx: pick.0.midX, dy: pick.0.midY)).tap()
                _ = app.wait(for: .runningForeground, timeout: 5)              // T6: condition
                if app.state != .runningForeground { report.append("PE-25 left the foreground: \(pick.1)"); break }
                if next < goal.words.count && pick.1.lowercased().contains(goal.words[next]) { next += 1 }
                recent = Array((recent + [pick.1]).suffix(3))
                if signature() == before { dead += 1; report.append("  dead: \(pick.1)") }
            }
            report.append("\(ok ? "✓" : "✗ PE-20") \(goal.name): \(steps) steps, \(dead) dead, \(backs) back")
            app.terminate(); app.launch()                                   // each goal starts clean
        }
        if #available(iOS 17.0, *) {                                        // on the VoiceOver / large-text persona
            // Without a handler the call fails the test on a finding and the report stays partial: write findings to the report.
            var issues: [String] = []
            do {
                try app.performAccessibilityAudit { issue in
                    issues.append("audit: \(issue.compactDescription)")
                    return true
                }
            } catch { issues.append("audit did not run: \(error)") }
            report += issues
        }
        return report
    }
}
```

Two tests per persona (`seed: 1`, `seed: 2`); report as an `XCTAttachment` or a
file. From outside, the only success measure is the SCREEN: "new row in the list",
"Settings shows 15". If a data measure is needed, the app's test
entry point can show a counter / state label in test builds only
(T3: suggested to the user, never added silently).

Notes:
- `-UIPreferredContentSizeCategoryName` works in UIKit / SwiftUI;
  in Flutter and React Native, confirm with the first screenshot that the text
  really grew (if it did not, use Settings ›
  Accessibility in the temporary simulator, or `xcrun simctl ui <UDID> content_size
  accessibility-extra-extra-extra-large`).
- Real VoiceOver cannot be driven automatically in the simulator. The VoiceOver persona is an
  APPROXIMATION: it sees only labelled elements and takes the order from the tree. Write the result
  as "VoiceOver approximation"; definitive verification is by hand on a device.
- Permission denial is most reliable with, before launch:
  `xcrun simctl privacy <UDID> revoke <photos|location|contacts|…> <bundle>`
  (TEMPORARY simulator only, `sim_session.py`).

## 2. Flutter (widget / integration test, semantics tree)

A plain version of a budgeting app's agent. Fast in a widget test (test font: truncated
text findings are CANDIDATES), real font on a simulator with `integration_test`
(PE-P5).

```dart
@Tags(['crawl'])
library;
import 'dart:math';
import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

class Goal { final String name; final List<String> words; final String? typing;
  final Future<bool> Function(WidgetTester) done;
  const Goal(this.name, this.words, this.done, {this.typing}); }

class Persona { final String name; final String locale; final double scale; final Size size;
  final bool voiceOver, hurried, rich, paid; final List<Goal> goals;
  const Persona({required this.name, required this.locale, required this.scale, required this.size,
    this.voiceOver = false, this.hurried = false, this.rich = false, this.paid = false, required this.goals}); }

Future<List<String>> runPersona(WidgetTester t, Persona p, int seed, {bool device = false}) async {
  if (!device) { await t.binding.setSurfaceSize(p.size); addTearDown(() => t.binding.setSurfaceSize(null)); }
  t.platformDispatcher.textScaleFactorTestValue = p.scale;
  addTearDown(t.platformDispatcher.clearTextScaleFactorTestValue);
  final sem = t.ensureSemantics();               // the tree is not on by itself on a device
  addTearDown(sem.dispose);
  final rnd = Random(seed * 31 + p.name.length), out = <String>['=== ${p.name} · seed $seed'];
  // openApp: the app's own dependency override path: in-memory data (seeded history if p.rich),
  // fixed clock, purchase / external link / notification fakes (T2). Write it per project.
  await openApp(t, p);

  List<(Offset, String)> targets() {
    final dpr = t.view.devicePixelRatio, screen = t.binding.renderViews.first.size, r = <(Offset, String)>[];
    for (final n in find.semantics.byAction(SemanticsAction.tap).evaluate()) {
      if (n.isInvisible || n.isMergedIntoParent) continue;
      var rect = n.rect;
      for (SemanticsNode? x = n; x != null; x = x.parent) {
        if (x.transform != null) rect = MatrixUtils.transformRect(x.transform!, rect);
      }
      final c = rect.center / dpr;
      if (c.dx < 0 || c.dy < 0 || c.dx > screen.width || c.dy > screen.height) continue;
      final d = n.getSemanticsData();
      final label = [d.label, d.value, d.tooltip].where((s) => s.isNotEmpty).join(' ');
      if (p.voiceOver && label.isEmpty) continue;
      r.add((c, label.isEmpty ? '(unnamed)' : label));
    }
    return r;
  }
  String sig() => find.byType(RichText).hitTestable().evaluate().take(10)
      .map((e) => (e.renderObject! as RenderParagraph).text.toPlainText()).join('|');

  for (final g in p.goals) {
    await goHome(t);                              // with real back, one at a time, then the first tab
    var next = 0, steps = 0, dead = 0, backs = 0, scrolls = 0, ok = false; final recent = <String>[];
    for (; steps < 40; steps++) {
      if (await g.done(t)) { ok = true; break; }
      final fields = find.byType(EditableText);
      if (g.typing != null && fields.evaluate().isNotEmpty &&
          t.widget<EditableText>(fields.first).controller.text.isEmpty) {
        await t.enterText(fields.first, g.typing!); await settle(t); continue;
      }
      final all = targets();
      // Goal word not visible: scroll first (at most 3; the counter resets only on a tap / back,
      // not tied to the signature because scrolling changes the visible text). No change means end of list: stop.
      int best0(String l) { final s = l.toLowerCase(); return g.words.any(s.contains) ? 1 : 0; }
      final scrollable = find.byType(Scrollable).hitTestable();
      if (all.every((e) => best0(e.$2) == 0) && scrolls < 3 && scrollable.evaluate().isNotEmpty) {
        final before = sig();
        await t.drag(scrollable.first, const Offset(0, -300));
        await settle(t);
        scrolls = sig() == before ? 3 : scrolls + 1;
        continue;
      }
      scrolls = 0;
      final roll = rnd.nextDouble();
      if (all.isEmpty || roll < (p.hurried ? .15 : .08)) { await maybePopTop(t); backs++; continue; }
      int score(String l) { final s = l.toLowerCase(); var v = 0;
        for (var i = 0; i < g.words.length; i++) { if (s.contains(g.words[i])) v += i == next ? 6 : (i > next ? 2 : 0); }
        return recent.contains(l) ? v - 4 : v; }
      all.sort((a, b) => score(b.$2).compareTo(score(a.$2)));
      final pick = score(all.first.$2) > 0 && roll < .82 ? all.first : all[rnd.nextInt(all.length)];
      final before = sig();
      await t.tapAt(pick.$1); await settle(t);
      final e = t.takeException(); if (e != null) out.add('PE-25 ${pick.$2}: $e');
      if (next < g.words.length && pick.$2.toLowerCase().contains(g.words[next])) next++;
      recent..add(pick.$2)..removeRange(0, max(0, recent.length - 3));
      if (sig() == before) { dead++; out.add('  dead: ${pick.$2}'); }
    }
    out.add('${ok ? '✓' : '✗ PE-20'} ${g.name}: $steps steps, $dead dead, $backs back');
  }
  return out;
}
```

`settle`: a fixed `pumpAndSettle` hangs on endless animation; use short
`pump` rounds + `takeException`. If the database stream uses real timers,
the agent runs inside `tester.runAsync` (e.g. drift).

## 3. UI with no tree (game engine, canvas)

Instead of an agent, a **manual scenario**: a persona × goal table, each cell with steps
and the expected screen; run in the temporary simulator with screenshots + coordinates
(T10). A fixed step list instead of seeds; report with the same ids.

## 4. Mac side (temporary simulator)

```sh
SS=~/.claude/skills/apptest/shared/sim_session.py
python3 -I $SS create --project <root> --software-keyboard \
        --content-size accessibility-extra-extra-extra-large      # persona C; returns the UDID
xcrun simctl privacy <UDID> revoke photos <bundle>               # the permission-denying persona (A, D)
# … run the tests per persona (caffeinate -dimsu <command>) …
python3 -I $SS cleanup --project <root>                           # simulator and settings restored (§7)
```
