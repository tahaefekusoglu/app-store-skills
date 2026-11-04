# crawl templates: tap every tappable element

Skeleton: **open the app with demo data → find the tappable elements on screen
through the accessibility tree → tap each one (except destructive / external
elements, CR-P1) → collect error / overflow / accessibility issues → tap the
inner elements of the page that opens (level 2) → reopen the app from scratch
for every target** (so the state from one tap does not affect the next). Runs
with a screen size × text scale × language matrix. Source example: a budgeting
app's `test/features/button_crawl_test.dart` (7 combinations: small / tall screen,
×1 / ×1.6 / ×3.0 text, paid / free, TR / EN; each tab a separate test;
`@Tags(['crawl'])`, skipped in the normal tour).

## Flutter (widget test, semantics tree)

```dart
@Tags(['crawl'])
library;
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

final skipLabel = RegExp(r'delete|remove|erase|buy|purchase|subscribe|log ?out|sign ?out|account|share|sil|kaldır|satın|abone|çıkış|hesab|paylaş|löschen|entfernen|kaufen|abonnieren|abmelden|konto|teilen|elimina|cancella|rimuovi|acquista|abbonati|esci|disconnetti|condividi|borrar|quitar|comprar|suscrib|cerrar sesión|salir|cuenta|compartir|supprimer|retirer|acheter|abonner|déconnexion|compte|partager|excluir|remover|apagar|assinar|sair|conta', caseSensitive: false);  // terms.py SKIP_LABELS: 7 languages

List<Offset> targets(WidgetTester t) {
  final dpr = t.view.devicePixelRatio, out = <Offset>[], seen = <String>{};
  for (final node in find.semantics.byAction(SemanticsAction.tap).evaluate()) {
    if (node.isInvisible || node.isMergedIntoParent) continue;
    if (skipLabel.hasMatch(node.getSemanticsData().label)) continue; // CR-P1
    var rect = node.rect;
    for (SemanticsNode? n = node; n != null; n = n.parent) {
      if (n.transform != null) rect = MatrixUtils.transformRect(n.transform!, rect);
    }
    final c = rect.center / dpr;
    if (seen.add('${c.dx.round()}:${c.dy.round()}')) out.add(c);
  }
  return out;
}

void main() {
  for (final (size, scale) in [(const Size(375, 667), 1.0), (const Size(430, 4200), 3.0)]) {
    testWidgets('every button $size ×$scale', (t) async {
      await t.binding.setSurfaceSize(size);
      t.platformDispatcher.textScaleFactorTestValue = scale;
      final problems = <String>[];
      final sem = t.ensureSemantics();
      await openApp(t); // demo data + fixed clock + mocked external effects (T2)
      final level1 = targets(t);
      for (final p in level1) {
        await openApp(t);
        await t.tapAt(p);
        await t.pump(const Duration(milliseconds: 300));
        final e = t.takeException();
        if (e != null) problems.add('$p: $e');
        // level 2: the same for targets(t) on the page that opened
      }
      for (final g in [textContrastGuideline, iOSTapTargetGuideline, labeledTapTargetGuideline]) {
        final r = await g.evaluate(t);
        if (!r.passed) problems.add(r.reason ?? '$g');
      }
      sem.dispose();
      expect(problems, isEmpty, reason: problems.join('\n'));
    }, timeout: const Timeout(Duration(minutes: 40)));
  }
}
```

In an app that uses Drift / Timer, taps go inside `tester.runAsync`, with a
`settle` that really waits (e.g. a budgeting app).

## SwiftUI / UIKit (XCUITest)

```swift
import XCTest

final class CrawlTests: XCTestCase {
    let skip = try! NSRegularExpression(pattern: "(?i)delete|remove|erase|buy|purchase|subscribe|log ?out|sign ?out|account|share|sil|kaldır|satın|abone|çıkış|hesab|paylaş|löschen|entfernen|kaufen|abonnieren|abmelden|konto|teilen|elimina|cancella|rimuovi|acquista|abbonati|esci|disconnetti|condividi|borrar|quitar|comprar|suscrib|cerrar sesión|salir|cuenta|compartir|supprimer|retirer|acheter|abonner|déconnexion|compte|partager|excluir|remover|apagar|assinar|sair|conta")  // terms.py SKIP_LABELS: 7 languages

    func testCrawl() throws {
        let app = XCUIApplication()
        app.launchArguments += ["-demoData", "-fixedNow", "2026-10-28T10:00:00Z"]  // the app's own hook
        app.launch()
        var issues = Set<String>()
        let ids = app.descendants(matching: .any)
            .matching(NSPredicate(format: "elementType == %d OR elementType == %d OR elementType == %d",
                                  XCUIElement.ElementType.button.rawValue,
                                  XCUIElement.ElementType.cell.rawValue,
                                  XCUIElement.ElementType.link.rawValue))
            .allElementsBoundByIndex.filter { $0.isHittable }   // isHittable is invalid in a query: fails at runtime
            .map { ($0.identifier, $0.label) }
        for (id, label) in ids where skip.firstMatch(in: label, range: NSRange(label.startIndex..., in: label)) == nil {
            app.terminate(); app.launch()
            let el = id.isEmpty ? app.buttons[label].firstMatch : app.descendants(matching: .any)[id].firstMatch
            guard el.waitForExistence(timeout: 3), el.isHittable else { continue }
            el.tap()
            _ = app.wait(for: .notRunning, timeout: 1)   // a crash shows up a moment later; checking immediately misses it
            XCTAssertEqual(app.state, .runningForeground, "crashed / fell to background on tap: \(id) \(label)")
            guard app.state == .runningForeground else { continue }
            if #available(iOS 17.0, *) {
                // Findings are collected so one violation does not hide a crash. "nearly passed" is only a near-pass warning.
                try app.performAccessibilityAudit { issue in
                    let text = issue.compactDescription
                    if !text.contains("nearly passed") { issues.insert("\(text) · \(label)") }
                    return true
                }
            }
        }
        XCTAssertTrue(issues.isEmpty, "accessibility:\n" + issues.sorted().joined(separator: "\n"))
    }
}
```

## React Native

Detox: instead of `element(by.type('RCTView')).atIndex(i)`, a loop that walks
accessible elements from a `testID` / `accessibilityLabel` list.
Maestro: a `tapOn` list per screen, no `assertNoDefectsWithAI`; only crash and
visibility checks. Destructive elements are still skipped.
