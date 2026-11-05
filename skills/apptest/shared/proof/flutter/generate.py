"""Flutter proof rig: writes a project from app.dart and the Dart templates in the skills' references.
A template passes only if it passes on the clean app and fails on the build with the planned bug.

    python3 -I generate.py <empty folder>     # run.py calls this
"""
import os
import re
import shutil
import sys

P = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
APP = "import 'package:proof/main.dart';\n"


def block(rel, has):
    with open(os.path.join(SKILLS, rel), encoding="utf-8") as fh:
        found = [x for x in re.findall(r"```dart\n(.*?)```", fh.read(), re.S) if has in x]
    if not found:
        sys.exit(f"template not found: {rel}: {has}")
    return found[0]


def add_import(code, after, line=APP):
    if after not in code:
        sys.exit(f"import anchor missing: {after}")
    return code.replace(after, after + "\n" + line.rstrip(), 1)


def write(rel, text):
    path = os.path.join(P, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


FT = "import 'package:flutter_test/flutter_test.dart';"
shutil.os.makedirs(os.path.join(P, "lib"), exist_ok=True)
shutil.copy(os.path.join(HERE, "app.dart"), os.path.join(P, "lib", "main.dart"))
write("pubspec.yaml", """name: proof
publish_to: none
environment:
  sdk: '>=3.0.0 <4.0.0'
dependencies:
  flutter:
    sdk: flutter
  http: any
  clock: any
dev_dependencies:
  flutter_test:
    sdk: flutter
  integration_test:
    sdk: flutter
  test: any
""")
write("dart_test.yaml", "tags:\n  crawl:\n")
MEM = """
class MemRepo implements OrderRepo {
  final rows = <Order>[];
  @override
  Future<void> save(Order o) async => rows.add(o);
}
"""

# ── Crawl: the Flutter section of the crawl template, as written
crawl = add_import(block("apptest-crawl/references/templates.md", "every button"), FT, APP + "import 'package:flutter/widgets.dart';\n")
for name, flag in (("crawl_test", ""), ("crawl_crash_bug_test", "crash: true"), ("crawl_a11y_bug_test", "a11y: true")):
    code = crawl
    if flag:
        code = code.replace("'every button", "'BUG every button")
    write(f"test/{name}.dart", code + MEM + f"""
Future<void> openApp(WidgetTester t) async {{
  await t.pumpWidget(const SizedBox());
  await t.pumpWidget(buildApp(MemRepo(), bugs: const Bugs({flag})));
  await t.pump();
}}
""")

# ── Rapid input
ri = add_import(block("apptest-rapid-input/references/templates.md", "SlowRepo"), "import 'dart:async';")
write("test/rapid_test.dart", ri + "\nWidget appWith(OrderRepo r) => buildApp(r, formFirst: true);\n")
write("test/rapid_double_bug_test.dart", ri.replace("'RI-S2:", "'BUG RI-S2:") +
      "\nWidget appWith(OrderRepo r) => buildApp(r, formFirst: true, bugs: const Bugs(doubleSave: true));\n")
write("test/rapid_dispose_bug_test.dart", ri.replace("'RI-S4:", "'BUG RI-S4:") +
      "\nWidget appWith(OrderRepo r) => buildApp(r, formFirst: true, bugs: const Bugs(afterDispose: true));\n")
snippet = block("apptest-rapid-input/references/templates.md", "Future.wait([writer.addExpense").replace("// Dart\n", "")
write("test/rapid_service_test.dart", "import 'package:flutter_test/flutter_test.dart';\n" + APP + f"""
void main() {{
  for (final bug in [false, true]) {{
    test('${{bug ? 'BUG ' : ''}}concurrent calls write once', () async {{
      final writer = Writer(bug: bug);
      const e = 'lunch';
      int countExpenses(Writer db) => db.list.length;
      final db = writer;
      {snippet.replace("await countExpenses(db)", "countExpenses(db)")}
    }});
  }}
}}
""")

# ── State simulation: template, with the app under test filled in
sim = block("apptest-state-sim/references/templates.md", "class Sim").replace(
    "late final AppUnderTest app;", "final AppUnderTest app = AppUnderTest(%BUG%);")
TAIL = """
class RejectedError implements Exception {}

class Snap {
  Snap(this.total, this.parts);
  final int total;
  final List<int> parts;
  @override
  bool operator ==(Object o) => o is Snap && o.total == total && o.parts.join() == parts.join();
  @override
  int get hashCode => total;
}

class TestClock {
  void advance(Duration d) {}
}

class AppUnderTest {
  AppUnderTest([this.bug = false]);
  final bool bug;
  final parts = <int>[];
  var total = 0;
  final clock = TestClock();
  Future<void> add({required int amount}) async {
    parts.add(amount);
    total += amount;
  }
  Future<void> editRandom(Random r) async {
    if (parts.isEmpty) throw RejectedError();
    final i = r.nextInt(parts.length), v = 1 + r.nextInt(100);
    total += v - parts[i];
    parts[i] = v;
  }
  Future<void> deleteRandom(Random r) async {
    if (parts.isEmpty) {
      if (bug) total += 1; // planned bug: a rejected action changes state
      throw RejectedError();
    }
    final v = parts.removeAt(r.nextInt(parts.length));
    if (!bug) total -= v; // planned bug: the total does not go down
  }
  Future<Snap> snapshot() async => Snap(total, List.of(parts));
}
"""
write("test/sim_test.dart", sim.replace("%BUG%", "") + TAIL)
write("test/sim_bug_test.dart", sim.replace("%BUG%", "true").replace("'simulation (seed", "'BUG simulation (seed")
      .replace("'every action succeeded", "'BUG-EXEMPT every action succeeded") + TAIL)

# ── Persona agent: the template plus the per-project helpers it asks for
persona = add_import(block("apptest-persona/references/templates.md", "runPersona"), FT)
HELP = MEM + """
Bugs proofBugs = const Bugs();
Future<void> openApp(WidgetTester t, Persona p) async {
  await t.pumpWidget(const SizedBox());
  await t.pumpWidget(buildApp(MemRepo(), bugs: proofBugs));
  await t.pump();
}
Future<void> settle(WidgetTester t) async {
  for (var i = 0; i < 12; i++) {
    await t.pump(const Duration(milliseconds: 100));
  }
}
Future<void> maybePopTop(WidgetTester t) async {
  await t.binding.handlePopRoute();
  await settle(t);
}
Future<void> goHome(WidgetTester t) async {
  for (var i = 0; i < 4 && find.byKey(const Key('add')).evaluate().isEmpty; i++) {
    await maybePopTop(t);
  }
}
final people = [
  for (final (name, scale, size, hurried) in [
    ('new user', 1.0, const Size(390, 844), false),
    ('hurried user', 1.0, const Size(390, 844), true),
    ('largest text', 3.0, const Size(320, 568), false),
  ])
    Persona(name: name, locale: 'en', scale: scale, size: size, hurried: hurried, goals: [
      Goal('add an order', const ['add', 'save'], (t) async => find.text('Saved 1').evaluate().isNotEmpty, typing: '250'),
    ]),
];
"""
write("test/persona_test.dart", persona + HELP + """
void main() {
  for (final who in people) {
    testWidgets('persona ${who.name}', (t) async {
      final out = await runPersona(t, who, 1);
      expect(out.where((l) => l.startsWith('✓')).length, 1, reason: out.join('\\n'));
    });
  }
}
""")
write("test/persona_bug_test.dart", persona + HELP + """
void main() {
  testWidgets('BUG persona dead end', (t) async {
    proofBugs = const Bugs(deadEnd: true);
    final out = await runPersona(t, people.first, 1);
    expect(out.where((l) => l.startsWith('✓')).length, 1, reason: out.join('\\n'));
  });
}
""")
write("integration_test/tour_test.dart", persona.replace("import 'package:flutter/widgets.dart';",
      "import 'package:flutter/widgets.dart';\nimport 'package:integration_test/integration_test.dart';") + HELP + """
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('persona on a real simulator', (t) async {
    final out = await runPersona(t, people.first, 1, device: true);
    expect(out.where((l) => l.startsWith('✓')).length, 1, reason: out.join('\\n'));
  });
}
""")

# ── Lifecycle
lc = add_import(block("apptest-lifecycle/references/transitions.md", "toBackground"), FT, APP + "import 'dart:convert';\nimport 'dart:io';\n")
DB = """
class Db implements OrderRepo {
  Db([this.file]);
  final String? file;
  var rows = <String>[];
  @override
  Future<void> save(Order o) async {
    rows.add(o.amount);
    if (file != null) File(file!).writeAsStringSync(jsonEncode(rows));
  }
}
Db openTestDb() => Db();
String tempDbFile() => '${Directory.systemTemp.createTempSync('proof').path}/db.json';
Db openDb(String file) => Db(file)..rows = File(file).existsSync() ? List<String>.from(jsonDecode(File(file).readAsStringSync()) as List) : <String>[];
Future<void> closeDb(Db db) async {}
Future<Map<String, int>> snapshotCounts(Db db) async => {'orders': db.rows.length};
"""
write("test/lifecycle_test.dart", lc + DB + "\nWidget appWith(Db db) => buildApp(db, formFirst: true);\n")
write("test/lifecycle_bug_test.dart", lc.replace("'LC-S1:", "'BUG LC-S1:") + DB +
      "\nWidget appWith(Db db) => buildApp(db, formFirst: true, bugs: const Bugs(workOnResume: true));\n")

# ── Network faults: the template's fake clients against the app's fetch
nc = block("apptest-network-chaos/references/faults.md", "MockClient").replace(
    "import 'package:http/testing.dart';", "import 'package:http/testing.dart';\n" + FT + "\n" + APP)
write("test/network_test.dart", nc + """
void main() {
  for (final bug in [false, true]) {
    final tag = bug ? 'BUG ' : '';
    test('${tag}bad JSON becomes a message', () async => expect(await fetchStatus(garbage, bug: bug), 'try again'));
    if (bug) continue;
    test('connection reset becomes a message', () async => expect(await fetchStatus(failing), 'try again'));
    test('server error becomes a message', () async => expect(await fetchStatus(serverError), 'try again'));
    test('flaky: one retry succeeds', () async {
      expect(await fetchStatus(flaky), 'try again');
      expect(calls, 1);
    });
    test('slow reply can be bounded', () async {
      await expectLater(fetchStatus(slow).timeout(const Duration(milliseconds: 50)), throwsA(anything));
    });
  }
}
""")

# ── Time: clock template line, and a date bug that shows only in a daylight saving time zone
line = [x for x in block("apptest-time-travel/references/patterns.md", "withClock").splitlines() if x.startswith("withClock")][0]
write("test/time_test.dart", "import 'package:clock/clock.dart';\nimport 'package:flutter_test/flutter_test.dart';\n" + APP + f"""
void main() {{
  test('fixed clock decides what is due', () {{
    var result = false;
    void body() => result = isDueToday(DateTime(2026, 3, 29));
    {line}
    expect(result, isTrue);
  }});
  test('calendar days across the clock change', () => expect(daysBetween(DateTime(2026, 3, 28), DateTime(2026, 3, 30)), 2));
}}
""")
write("test/time_dst_bug_test.dart", "import 'package:flutter_test/flutter_test.dart';\n" + APP + """
void main() {
  test('BUG-DST calendar days across the clock change', () => expect(daysBetween(DateTime(2026, 3, 28), DateTime(2026, 3, 30), bug: true), 2));
}
""")
