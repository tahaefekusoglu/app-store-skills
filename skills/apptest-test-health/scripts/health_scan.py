#!/usr/bin/env python3
"""apptest-test-health: the health of the tests themselves. Stale element ids
(the Key / testID / accessibilityIdentifier a test looks for is not in the app),
skipped / conditional tests, fixed waits (sleep), tests that depend on the real
date, time zone or network, focused (only) tests, empty tests.

Standard library only; does NOT write to the project, run tests or delete tests (TH-P1).

    python3 -I health_scan.py <project_root> [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys

_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apptest", "shared", "scanlib.py")
_s = importlib.util.spec_from_file_location("apptest_scanlib", _p)
scan = importlib.util.module_from_spec(_s)
_s.loader.exec_module(scan)

# Ids a test LOOKS FOR (per language) and the forms that DEFINE them in the app
FIND_ID = {
    "dart": r"find\.byKey\(\s*(?:const\s+)?(?:Value)?Key\(\s*['\"]([^'\"$]+)['\"]",
    "swift": r"(?:buttons|staticTexts|otherElements|textFields|secureTextFields|cells|switches|images|tables|"
             r"collectionViews|navigationBars|scrollViews|sliders|segmentedControls|links|"
             r"descendants\(matching:\s*\.\w+\))\[\s*\"([A-Za-z0-9_.\-]+)\"\s*\]",
    "js": r"(?:by\.id|getByTestId|queryByTestId|findByTestId|element\(by\.id)\(\s*['\"]([^'\"$]+)['\"]",
    "yaml": r"^\s*-?\s*(?:tapOn|assertVisible|assertNotVisible|scrollUntilVisible)\s*:\s*\n?\s*id\s*:\s*['\"]?([A-Za-z0-9_.\-]+)",
}
DEFINE_ID = {
    "dart": r"Key\(\s*['\"]([^'\"$]+)['\"]",
    "swift": r"accessibilityIdentifier(?:\s*=\s*|\(\s*)\"([A-Za-z0-9_.\-]+)\"",
    "js": r"testID\s*=\s*\{?\s*['\"]([^'\"$]+)['\"]",
}
SKIP = r"\bskip\s*:\s*(true|['\"])|@Skip\b|\bxit\(|\bxdescribe\(|\bit\.skip\(|\btest\.skip\(|describe\.skip\(|" \
       r"XCTSkip|throw XCTSkip|@Disabled|\.disabled\(|tags\s*:\s*\[?['\"](skip|flaky)"
# At line start: an example call inside text does not count (e.g. the Joplin eslint rule test).
ONLY = r"(?m)^[ \t]*(?:fit\(|fdescribe\(|it\.only\(|test\.only\(|describe\.only\()|\bsolo\s*:\s*true"
SLEEP = r"Future\.delayed\(|\bsleep\(|Thread\.sleep|usleep\(|await new Promise\(\s*\w+\s*=>\s*setTimeout|" \
        r"waitForTimeout\(|\.wait\(\s*\d|XCTWaiter\(\)\.wait"
REAL_NOW = r"DateTime\.now\(\)|\bDate\(\)|Date\.now\(\)|new Date\(\)"
CAL_LOGIC = r"(?i)\b(day|days|month|months|week|year|weekday|midnight|startOfDay|cycle|due|expire\w*|tomorrow|yesterday|" \
            r"inDays|byAdding|gün|ay|vade|döngü)\b"
CLOCK_FAKE = r"withClock|FakeAsync|fakeAsync|clockProvider|Clock\.fixed|jest\.useFakeTimers|setSystemTime|mockDate|" \
             r"TestClock|fixedNow|frozen"
TZ_DEP = r"(?i)TimeZone\.current|timeZoneOffset|\.toLocal\(\)|getTimezoneOffset|Locale\.current"
NET_DEP = r"https?://(?!localhost|127\.0\.0\.1|example\.(com|org)|0\.0\.0\.0)[a-z0-9.-]+\.[a-z]{2,}"
NET_MOCK = r"(?i)mock|stub|fake|nock|msw|MockClient|HttpOverrides|URLProtocol|intercept"
# A URL that only appears as data is not a network dependency: look for a real REQUEST call.
NET_CALL = r"\bhttp\.(get|post|put|delete)\(|URLSession\.shared|\.dataTask\(|\bfetch\(|\bDio\(|axios\.|" \
           r"HttpClient\(\)|\.getUrl\(|AF\.request|URLRequest\("
EMPTY_TEST = {
    "dart": r"(test|testWidgets)\(\s*['\"][^'\"]+['\"]\s*,\s*\([^)]*\)\s*(async\s*)?\{\s*\}\s*\)",
    "swift": r"func test\w+\(\)\s*(async\s*)?(throws\s*)?\{\s*\}",
    "js": r"\b(it|test)\(\s*['\"][^'\"]+['\"]\s*,\s*(async\s*)?\(\)\s*=>\s*\{\s*\}\s*\)",
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p = scan.load_profile(a.root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("TH", p, "test-health scan")
    tests = [f for f in scan.code_files(p, include_tests=True, ios_only=False)
             if scan.TEST_PATH.search("/" + p.rel(f))]
    tests += [f for f in p.files if f.endswith((".yaml", ".yml")) and re.search(r"/\.?maestro/", f)]
    app = [f for f in scan.code_files(p, ios_only=False) if not scan.TEST_PATH.search("/" + p.rel(f))]
    if not tests:
        rep.skip("TH-10…", "no test files")
        rep.emit(a.json)
        return 0

    # TH-10: stale element id
    defined: dict[str, set] = {}
    for f in app + tests:  # test helpers can define ids too ...
        lg = scan.lang_of(f)
        if lg in DEFINE_ID:
            t = scan.p_read(f, 600_000)
            if f in tests and lg in FIND_ID:
                t = re.sub(FIND_ID[lg], "", t)  # ... but an id the test LOOKS FOR is not a definition
            defined.setdefault(lg, set()).update(re.findall(DEFINE_ID[lg], t))
    all_defined = set().union(*defined.values()) if defined else set()
    # Ids defined in interface files (e.g. DuckDuckGo OmniBar.xib).
    # Separate set: these files alone do not switch the check on (e.g. Mastodon tests search by visible text).
    xib_ids = set()
    for f in p.files:
        if f.endswith((".xib", ".storyboard")):
            xib_ids.update(re.findall(r'(?:<accessibility[^>]*\bidentifier|accessibilityIdentifier|userLabel)="([^"]+)"', scan.p_read(f, 2_000_000)))
    # Ids built at runtime: Key('add-choice-${x}'), '$key-empty' ... String constants in the app and the
    # fixed starts of interpolations also count as "definitions".
    literals, prefixes = set(), set()
    for f in app:
        t = scan.p_read(f, 600_000)
        literals.update(re.findall(r"['\"`]([A-Za-z0-9_.\-]{3,80})['\"`]", t))
        prefixes.update(re.findall(r"['\"`]([A-Za-z0-9_.\-]{4,60})(?:\$\{?|\\\()", t))
    prefixes.update(x for x in literals if len(x) >= 8)
    ABSENT = re.compile(r"findsNothing|doesNotExist|\.exists\)?\s*\)?\s*==\s*false|XCTAssertFalse\([^)]*\.exists|"
                        r"not\.toBeVisible|toBeNull\(\)|assertNotVisible|waitForNonExistence")
    stale = {}
    # END-TO-END tests only (they drive the real app and rot silently if not run); component /
    # unit tests often create their own ids inside the test.
    e2e = re.compile(r"(?i)/integration_test/|/patrol_test/|UITests?/|/e2e/|/__e2e__/|/\.?maestro/|/detox/|"
                     r"\.e2e\.(t|j)sx?$")
    for f in [x for x in tests if e2e.search("/" + p.rel(x))]:
        lg = "yaml" if f.endswith((".yaml", ".yml")) else scan.lang_of(f)
        rx = FIND_ID.get(lg)
        if not rx:
            continue
        t = scan.p_read(f, 600_000)
        for m in re.finditer(rx, t, re.M):
            ident = m.group(1)
            line = t[t.rfind("\n", 0, m.start()) + 1:t.find("\n", m.end())]
            if ident in all_defined or ident in xib_ids or ident in literals or ABSENT.search(line) or \
                    any(ident.startswith(x) for x in prefixes if x != ident):
                continue  # defined / built at runtime / deliberately checked as absent
            if lg == "swift" and " " in ident:
                continue  # search by visible text (not an id)
            stale.setdefault((p.rel(f), ident), t.count("\n", 0, m.start()) + 1)
    if all_defined:
        for (rel, ident), n in sorted(stale.items())[:60]:
            rep.add("TH-10", "USER BUG", f"Element id the test looks for is not in the app: '{ident}'", f"{rel}:{n}",
                    "The test may be stale: when run it fails with 'not found'; if it searches through a 'tap if present' (tapIf) "
                    "helper, that step is SILENTLY skipped; if it does not run, it rots. "
                    "If the id is generated at runtime (string concatenation) this is not a finding (not verified). "
                    "(e.g. in a budgeting app, 4 integration tours turned out stale before a release for this reason.)")
    else:
        rep.skip("TH-10", "no element id definitions found in the app")

    # TH-11 / 12 / 13 / 14 / 15 / 16
    for f in tests:
        lg = scan.lang_of(f)
        t = scan.p_read(f, 600_000)
        rel = p.rel(f)
        for rx, fid, sev, title, note in (
            (SKIP, "TH-11", "SUGGESTION", "Skipped / disabled test",
             "A skipped test looks like a passed one (e.g. in a budgeting app, the crawl test never ran without --run-skipped). "
             "Is it written down why it is skipped and when it will run?"),
            (ONLY if lg in ("dart", "js") else r"(?!x)x", "TH-12", "USER BUG", "Only this test runs (only / fit)",
             "All other tests are silently skipped; it may have been left in by accident."),
        ):
            m = re.search(rx, t)
            if m:
                rep.add(fid, sev, title, f"{rel}:{t.count(chr(10), 0, m.start()) + 1} `{m.group(0)[:40]}`", note)
        m = re.search(SLEEP, t)
        if m and lg in ("swift", "js", "dart") and not re.search(r"pumpAndSettle|waitFor|expectation|eventually|until", t):
            rep.add("TH-13", "SUGGESTION", "Fixed-time wait (no condition wait)",
                    f"{rel}:{t.count(chr(10), 0, m.start()) + 1} `{m.group(0)[:30]}`",
                    "Fails on a slow machine, wastes time on a fast one: the most common cause of flakiness (test-methods T6).")
        for mm in re.finditer(REAL_NOW, t):
            ln = t.count("\n", 0, mm.start())
            win = "\n".join(t.splitlines()[max(0, ln - 4):ln + 5])
            if re.search(CAL_LOGIC, win) and not re.search(CLOCK_FAKE, t):
                rep.add("TH-14", "SUGGESTION", "Calendar logic is tested with the real date (passes today, may fail at month end)",
                        f"{rel}:{ln + 1} `{mm.group(0)}`",
                        "Fixed date + a run in at least one time zone with DST (time-travel).")
                break
        m = re.search(TZ_DEP, t)
        if m and not re.search(r"TZ=|TimeZone\(identifier|setTimeZone|timezone", t):
            rep.add("TH-15", "SUGGESTION", "The result may depend on the machine's time zone / language",
                    f"{rel}:{t.count(chr(10), 0, m.start()) + 1} `{m.group(0)}`",
                    "Fails when CI runs in another region; fix TZ / language (principle 14).")
        m = re.search(NET_DEP, t)
        if m and re.search(NET_CALL, t) and not re.search(NET_MOCK, t):
            rep.add("TH-16", "SUGGESTION", "Test may depend on the real network", f"{rel}:{t.count(chr(10), 0, m.start()) + 1} "
                    f"`{m.group(0)[:40]}`", "Fails with no network or when the server changes; a mock is one way out (test-methods T1).")
        if lg in EMPTY_TEST:
            m = re.search(EMPTY_TEST[lg], t)
            if m:
                rep.add("TH-17", "SUGGESTION", "Empty test (checks nothing)", f"{rel}:{t.count(chr(10), 0, m.start()) + 1}",
                        "Passes but verifies nothing.")

    rep.emit(a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
