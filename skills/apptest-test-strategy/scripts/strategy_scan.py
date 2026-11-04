#!/usr/bin/env python3
"""apptest-test-strategy: test layer map, critical modules without tests,
layers that do not run in CI, tests that depend on the real clock or on
unseeded randomness, and run commands per layer.

Standard library only; does NOT write to the project and does NOT run tests.
Output is CANDIDATES (verify against the TS-xx ids in SKILL.md). Does not
suggest changing the test tool (TS-P1).

    python3 -I strategy_scan.py <project_root> [--json]
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

# (layer, file pattern)
LAYERS = [
    ("unit", r"(/test/(?!.*(widget|golden)).*_test\.dart$|Tests/.*Tests?\.swift$|\.(test|spec)\.(t|j)sx?$|"
              r"/commonTest/|/iosTest/|Tests?\.cs$)"),
    ("UI component (widget / component)", r"(/test/.*(widget|golden|screen|page|view).*_test\.dart$|"
                                           r"\.test\.tsx$|SnapshotTests?\.swift$)"),
    ("integration / UI (on device)", r"(/integration_test/.*\.dart$|/patrol_test/|UITests?/.*\.swift$|"
                                     r"/e2e/.*\.(t|j)s$|/__e2e__/|/\.maestro/.*\.ya?ml$|/maestro/.*\.ya?ml$|\.detoxrc)"),
]
# The file NAME is split into words (camelCase / snake_case): the "date" inside "Prevalidate" or "UpdateTemp" does not count.
RISK = [
    ("money / payment", {"money", "price", "amount", "payment", "wallet", "ledger", "invoice", "currency", "kurus",
                         "tutar", "bakiye", "defter", "odeme", "billing", "checkout", "balance"}),
    ("date / calendar", {"date", "dates", "calendar", "cycle", "cycles", "schedule", "recurring", "recurrence", "period",
                           "donem", "dongu", "calendar", "vade", "reminder", "timezone"}),
    ("persistent data", {"database", "db", "repository", "persistence", "migration", "migrations", "dao", "backup",
                         "restore", "yedek", "storage"}),
    ("purchases", {"iap", "storekit", "purchase", "purchases", "subscription", "subscriptions", "paywall"}),
    ("sign-in / session", {"auth", "authentication", "login", "session", "signin", "credential", "credentials"}),
]
DATA_HOLDER_DIR = re.compile(r"(?i)/(models?|requests?|responses?|enums?|dto|entities|types)/")


def name_tokens(path: str) -> set:
    base = os.path.splitext(os.path.basename(path))[0]
    return {t.lower() for t in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", base.replace("_", " ").replace("-", " "))}
REAL_NOW = r"DateTime\.now\(\)|\bDate\(\)|Date\.now\(\)|new Date\(\)|clock\.now|LocalDateTime\.now"
# The real clock is a risk only when the test checks something CALENDAR-dependent, not when it just produces a timestamp.
CALENDAR_LOGIC = r"(?i)\b(day|days|month|months|week|weeks|year|years|weekday|midnight|startOfDay|endOfMonth|cycle|due|" \
                 r"expire\w*|deadline|ago|tomorrow|yesterday|inDays|daysBetween|addingTimeInterval|byAdding|" \
                 r"gün|ay|hafta|vade|döngü)\b"
CLOCK_FAKE = r"withClock|FakeAsync|fakeAsync|clockProvider|Clock\.fixed|jest\.useFakeTimers|setSystemTime|mockDate|" \
             r"overrideNow|TestClock|fixedNow|frozen"
# UUID() is a unique id, not randomness that affects the result.
RANDOM = r"\bRandom\(\)|Math\.random\(\)|\.random\(\)|\.random\(in:|arc4random|\.shuffled\(\)|\.shuffle\(\)"
SEED = r"Random\(\s*\d+\s*\)|seed|Seed|SystemRandomNumberGenerator|seeded"
SKIP = r"\bskip\s*:|@Skip\b|\bxit\(|\bit\.skip\(|\btest\.skip\(|XCTSkip|describe\.skip\(|@Disabled|\.skip\b"
CI_FILES = r"(/\.github/workflows/.*\.ya?ml$|\.gitlab-ci\.yml$|bitrise\.ya?ml$|codemagic\.ya?ml$|/\.circleci/|Fastfile$|" \
           r"ci_post_clone\.sh$|azure-pipelines\.ya?ml$|Jenkinsfile$)"


def test_files(p):
    return [f for f in p.files if scan.lang_of(f) or f.endswith((".yaml", ".yml"))
            if scan.TEST_PATH.search("/" + p.rel(f)) or re.search(LAYERS[2][1], "/" + p.rel(f))]


def run_commands(p, layers_present: dict) -> list[str]:
    techs = " ".join(scan.techs(p))
    cmds = []
    if "Flutter" in techs:
        cmds.append("flutter test  (unit + widget)")
        if layers_present.get("integration / UI (on device)"):
            cmds.append("flutter test integration_test/<file> -d <TEMP_SIMULATOR>")
    if "Native iOS" in techs or "Native iOS" in techs or "Kotlin" in techs:
        cmds.append("xcodebuild test -scheme <scheme> -destination 'platform=iOS Simulator,id=<TEMP_SIMULATOR>'")
    if "React Native" in techs:
        cmds.append("npx jest")
        if any("detox" in f.lower() for f in p.files):
            cmds.append("npx detox test -c <configuration>")
        if any("/.maestro/" in f or "/maestro/" in f for f in p.files):
            cmds.append("maestro test .maestro/")
    if ".NET MAUI" in techs:
        cmds.append("dotnet test")
    return cmds


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p = scan.load_profile(a.root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("TS", p, "test-strategy scan")
    tfiles = test_files(p)
    rels = ["/" + p.rel(f) for f in tfiles]

    # TS-10: layer map
    present = {}
    for name, rx in LAYERS:
        present[name] = sum(1 for r in rels if re.search(rx, r))
    rep.add("TS-10", "INFO", "Test layers", " · ".join(f"{k}: {v}" for k, v in present.items()),
            "Commands: " + " ; ".join(run_commands(p, present)) if run_commands(p, present) else "")
    if not tfiles:
        rep.add("TS-14", "SUGGESTION", "The project has no automated tests", "—",
                "Start with a few unit tests on the riskiest business rule (money, dates, data), using the current tool (TS-P1).")
    elif not present["integration / UI (on device)"]:
        rep.add("TS-14", "SUGGESTION", "No tests run on a device / simulator", "—",
                "The real keyboard, fonts, permission dialogs and external links only show up on a device (device-tour).")

    # TS-11: critical modules without tests (name matching; rough)
    code = scan.code_files(p)
    test_names = {re.sub(r"(_test|Tests?|\.test|\.spec)$", "", os.path.splitext(os.path.basename(f))[0]).lower()
                  for f in tfiles}
    test_blob = "\n".join(scan.p_read(f, 200_000) for f in tfiles[:3000])
    for label, rx in RISK:  # rx: keyword set
        mods = [f for f in code if name_tokens(f) & rx and not DATA_HOLDER_DIR.search("/" + p.rel(f))
                and not name_tokens(f) & {"view", "screen", "page", "widget", "cell", "button", "style", "theme", "icon",
                                          "color", "l10n", "generated", "plugin", "with", "entitlements", "config"}]
        untested = [f for f in mods if os.path.splitext(os.path.basename(f))[0].lower() not in test_names
                    and os.path.splitext(os.path.basename(f))[0] not in test_blob]
        if mods and len(untested) == len(mods) and len(mods) >= 1:
            rep.add("TS-11", "SUGGESTION", f"{label} code exists, but no test matches any of it by name",
                    ", ".join(p.rel(f) for f in untested[:4]) + (" …" if len(untested) > 4 else ""),
                    "Name matching is a rough measure; it may be tested under another name (not verified). Bugs in this "
                    "area are the most expensive: start here.")

    # TS-12: real clock / unseeded randomness
    unit = [f for f in tfiles if scan.lang_of(f)]
    for f in unit:
        t = scan.p_read(f, 300_000)
        m = None
        for mm in re.finditer(REAL_NOW, t):
            ln = t.count("\n", 0, mm.start())
            win = "\n".join(t.splitlines()[max(0, ln - 4):ln + 5])
            if re.search(CALENDAR_LOGIC, win):
                m = mm
                break
        if m and not re.search(CLOCK_FAKE, t):
            n = t.count("\n", 0, m.start()) + 1
            rep.add("TS-12", "SUGGESTION", "Test uses the real clock (the result may depend on the day, hour or time zone)",
                    f"{p.rel(f)}:{n} `{m.group(0)}`",
                    "Month-end, DST and midnight tests can pass today and fail tomorrow (e.g. a budgeting app had a test that "
                    "failed in the last 7 days of each month). A fixed clock is one way out.")
    for f in unit:
        t = scan.p_read(f, 300_000)
        m = re.search(RANDOM, t)
        if m and not re.search(SEED, t):
            n = t.count("\n", 0, m.start()) + 1
            rep.add("TS-13", "SUGGESTION", "Test uses unseeded randomness (a failure cannot be reproduced)",
                    f"{p.rel(f)}:{n} `{m.group(0)}`", "Fix the seed and print it on failure (principle 14).")

    # TS-15: CI and layers
    ci = [f for f in p.files if re.search(CI_FILES, "/" + p.rel(f))]
    if not ci and tfiles:
        rep.add("TS-15", "SUGGESTION", "Tests exist but there is no CI configuration", "—",
                "Tests that only run by hand get forgotten and rot (test-health).")
    elif ci:
        ci_text = "\n".join(scan.p_read(f) for f in ci)
        if present["integration / UI (on device)"] and not re.search(r"(?i)integration_test|UITests|detox|maestro|e2e|"
                                                                   r"xcodebuild test|patrol", ci_text):
            rep.add("TS-15", "SUGGESTION", "Device / integration tests do not run in CI", ", ".join(p.rel(f) for f in ci[:3]),
                    "A test that does not run goes stale silently (e.g. in a budgeting app, 4 integration tours turned out stale "
                    "before a release). At minimum, a rule to run them by hand before each release.")

    # TS-16: skipped tests (details in test-health)
    sk, first = scan.count(p, SKIP, files=unit)
    if sk:
        rep.add("TS-16", "INFO", f"Skipped / conditional test markers: {sk}", f"{p.rel(first[0])}:{first[1]}",
                "A skipped test looks like a passed one; details and classification in test-health.")

    rep.emit(a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
