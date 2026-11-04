#!/usr/bin/env python3
"""apptest-persona — (1) a persona plan defined by BEHAVIOUR from the app profile
(every level of every dimension in at least one persona; risky pairs deliberately
together); (2) inventory of test hooks that set a persona up (test entry point,
in-memory data, clock, purchase / external link / network / notification fakes);
(3) personas in existing tests named by an age / gender / occupation stereotype.

Standard library only; does NOT write to the project.

    python3 -I pe_plan.py <project_root> [--json]
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import re
import sys

_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apptest", "shared", "scanlib.py")
_s = importlib.util.spec_from_file_location("apptest_scanlib", _p)
scan = importlib.util.module_from_spec(_s)
_s.loader.exec_module(scan)

# Test hooks: (key, name, pattern, which persona dimension needs it, condition flag)
SEAMS = [
    ("giris", "test launch entry point (launch arguments / dependency override)",
     r"launchArguments|launchEnvironment|ProcessInfo\.processInfo\.(arguments|environment)|overrideWithValue\(|"
     r"ProviderScope\(\s*overrides|withDependencies\b|DependencyValues\b|\.environmentObject\(\s*Mock|"
     r"jest\.mock\(|setUpWithError|withEnvironment\(|AppEnvironment\.(push|replaceCurrent)Environment|"
     r"Substitute\.For<|new Mock<",
     "every persona: the app cannot open with demo data in the persona's state", None),
    ("bellek", "in-memory / temporary data store",
     r"NativeDatabase\.memory|\binMemory(Store|Database|Db|Container|Configuration)?\b|isStoredInMemoryOnly\s*:\s*true|[\"']:memory:[\"']|NSInMemoryStoreType|"
     r"InMemory\w*Store|inMemoryDatabaseBuilder|Realm\.Configuration\(\s*inMemoryIdentifier|MockKeyValueStore",
     "‘first launch’ and ‘returning user’ data cannot be set up without touching real data", None),
    ("saat", "clock hook",
     r"\bclockProvider\b|\bclock\.now\(\)|package:clock|withClock|protocol\s+\w*Clock\b|\bnowProvider\b|"
     r"\bdateProvider\b|\bDateProvider\b|\bTimeProvider\b|ISystemClock|IClock\b|now\s*:\s*\(\)\s*=>|Clock\.fixed|"
     r"@Dependency\(\\\.date\)|\bMockDate\b|jest\.useFakeTimers|setSystemTime\(",
     "the ‘returning user’s past periods and due dates cannot be set up with a fixed date", None),
    ("satin", "purchase fake",
     r"SKTestSession|StoreKitTest|Mock\w*Purchase\w*|Fake\w*Purchase\w*|Purchase\w*(Mock|Fake|Stub)\b|"
     r"MockStore\b|Mock\w*Paywall|Purchases\w*Mock|setMockInitialValues",
     "‘paid’ / ‘free’ / ‘expired’ personas cannot be set up without a real purchase", "purchases"),
    ("link", "external link / share fake",
     r"externalLinkOverride|openURL\w*(Override|Mock|Spy)|Mock\w*(URL|Url)(Opener|Launcher|Handler)|"
     r"UrlLauncherPlatform\.instance\s*=|jest\.mock\([\"'](react-native/Libraries/Linking|expo-linking|"
     r"expo-web-browser|react-native-share)|Mock\w*Share\w*|ShareService\w*Mock",
     "the journey sends the app to the background when Safari or a share sheet opens, and the tour silently hangs", None),
    ("network", "network fake",
     r"URLProtocol|OHHTTPStubs|\bMocker\b|MockWebServer|MockClient\(|http_mock_adapter|DioAdapter|nock\(|"
     r"\bmsw\b|setupServer\(|fetchMock|jest\.mock\([\"']axios|MockURLSession|Stub\w*Session|"
     r"(Mock|Fake)\w*(Api|API|Network|Http|HTTP)\w*|\bMockService\(",
     "the ‘slow / dropping network’ persona and a serverless tour cannot be set up", "network"),
    ("notifications", "notification / permission fake",
     r"(Mock|Fake|Quiet|Stub)\w*Notification(Center|Scheduler|Service|Manager|Permission|Client)\w*|"
     r"implements\s+\w*Notification(Scheduler|Service|Center)\b|"
     r"UNUserNotificationCenter\w*(Mock|Fake)|simctl\s+privacy|addUIInterruptionMonitor|"
     r"jest\.mock\([\"'](expo-notifications|@notifee|react-native-permissions)",
     "the ‘denies permission’ persona gets stuck on the real permission dialog", "permission"),
]

# Stereotype in a persona name: age / gender / occupation (PE-P1). The line must also show a persona context.
STEREOTYPE = re.compile(
    r"(?i)\b(yaşlı|ihtiyar|elderly|senior citizen|seniors?\s+user|grandma|grandpa|granny|grandmother|grandfather|"
    r"teyze|ev hanımı|housewife|boomer|old (lady|man|person|people|user)s?|soccer mom|"
    r"tech[- ]illiterate|computer[- ]illiterate|bilgisayar bilmeyen)\b")
PERSONA_CTX = re.compile(r"(?i)persona|profil|profile|\buser\b|kullanıcı|name\s*[:=]|title\s*[:=]|describe\(|"
                         r"testWidgets\(|func\s+test|\bit\(|\btest\(")
JOURNEY = re.compile(r"(?i)\bpersonas?\b|user[ _-]?journey|kullanıcı yolculu|kullanıcı profili|\busability\b")


LONG = ("de", "fi", "ru", "pl", "nl", "hu", "el", "uk", "fr", "pt", "es", "it", "tr", "sv", "cs")
RTL = ("ar", "he", "fa", "ur", "yi", "ps", "sd", "ug", "dv", "ckb")


def pick_langs(langs: list[str]) -> list[str]:
    """At most 3 languages for the journey: the development language (en if present), a second language,
    and a right-to-left language if any. The rest are scanned with crawl / visual / locale-time, not journeys (PE-P4)."""
    base = "en" if "en" in langs else langs[0]
    rest = [x for x in langs if x != base]
    rtl = next((x for x in rest if x in RTL), None)
    # Second language: those that usually run longer than English first (overflow and truncation show there).
    long_first = [x for x in LONG if x in rest] + [x for x in rest if x not in LONG]
    second = next((x for x in long_first if x != rtl), None)
    return [x for x in (base, second, rtl) if x]


def dimensions(flags: dict, has_notif: bool) -> list[tuple[str, list[str]]]:
    """Behaviour dimensions and levels that fit the app (order = distribution to personas A, B, C, D)."""
    dims = [
        ("experience", ["first launch (empty data, goes through setup)", "returning (months of data)"]),
        ("pace", ["careful (reads, waits)", "hurried (accepts defaults, taps the first button, leaves things half done)"]),
        ("reading", ["normal text", "largest accessibility text", "VoiceOver (decides by labels only)"]),
        ("screen", ["smallest supported", "largest"]),
    ]
    langs = flags.get("languages") or []
    if len(langs) > 1:
        dims.append(("language", pick_langs(langs)))
    if flags.get("purchases") or flags.get("subscriptions"):
        lv = ["free", "paid"]
        if flags.get("subscriptions"):
            lv.append("subscription expired")
        dims.append(("account", lv))
    if flags.get("account"):
        dims.append(("session", ["signed out", "signed in"]))
    if flags.get("network"):
        dims.append(("network", ["good", "slow / dropping"]))
    if flags.get("permissions") or has_notif:
        dims.append(("permission", ["denies", "grants"]))
    return dims


# Persona templates: level index per dimension. -1 = last level. Risky pairs:
# C = largest text + smallest screen (overflow), D = VoiceOver + first launch (setup labels).
_PICK = {
    "A": {"experience": 0, "pace": 0, "reading": 0, "screen": 0, "language": 0, "account": 0, "session": 0, "network": 0, "permission": 0},
    "B": {"experience": 1, "pace": 1, "reading": 0, "screen": 1, "language": 1, "account": 1, "session": 1, "network": 1, "permission": 1},
    "C": {"experience": 1, "pace": 0, "reading": 1, "screen": 0, "language": 1, "account": 0, "session": 1, "network": 0, "permission": 1},
    "D": {"experience": 0, "pace": 0, "reading": 2, "screen": 1, "language": 0, "account": -1, "session": 0, "network": 1, "permission": 0},
}


def plan(dims) -> list[dict]:
    out = []
    for key, pick in _PICK.items():
        out.append({"persona": key, **{d: lv[pick.get(d, 0) if pick.get(d, 0) < len(lv) else -1]
                                    for d, lv in dims}})
    names = dict(dims)
    # Right-to-left language: to D (VoiceOver), not C (largest text), so the two layout risks stay in separate personas.
    langs = names.get("language", [])
    if len(langs) == 3:
        out[3]["dil"] = langs[2]
    # Every level at least once? (if not, add the missing level to a copy of A)
    for d, lv in dims:
        for level in lv:
            if not any(p.get(d) == level for p in out):
                out.append({**out[0], "persona": f"A-{d}", d: level})
    return out


def scan_project(root: str, as_json: bool):
    p = scan.load_profile(root)
    if scan.guard_unknown(p):
        return 0
    flags = p.mod.summary_flags(p)
    has_notif = any(k.startswith("capability:notifications") for k in p.items)
    rep = scan.Report("PE", p, "persona — persona plan and test hooks")
    every = scan.code_files(p, include_tests=True)
    tests = [f for f in every if scan.TEST_PATH.search("/" + p.rel(f))]

    for key, name, pat, why, need in SEAMS:
        if need == "permission" and not (flags.get("permissions") or has_notif):
            rep.skip(f"PE-10:{key}", "no permissions / notifications")
            continue
        if need and need != "permission" and not flags.get(need):
            rep.skip(f"PE-10:{key}", "no " + {"purchases": "in-app purchase", "network": "networking"}.get(need, need))
            continue
        c, first = scan.count(p, pat, files=every)
        if c:
            rep.add("PE-10", "INFO", f"Hook found: {name} ({c} place(s))", f"{p.rel(first[0])}:{first[1]}",
                    "Use this in persona setup.")
        else:
            rep.add("PE-10", "INFO", f"Hook not found: {name}", "—",
                    f"Cannot test: {why}. Suggest a hook to the user once, only if it cannot be solved in test code alone (T3).")

    seen = set()
    for f, n, line, m in scan.grep(p, STEREOTYPE, files=tests, include_tests=True):
        if not PERSONA_CTX.search(line):
            continue
        key = (p.rel(f), m.group(1).lower())
        if key in seen:
            continue
        seen.add(key)
        rep.add("PE-11", "SUGGESTION", f"Persona named by a stereotype: “{m.group(1)}”", f"{p.rel(f)}:{n}",
                "Name it by behaviour (e.g. ‘largest text · smallest screen’); a stereotype sets up the wrong scenario (PE-P1).")

    jc, jfirst = scan.count(p, JOURNEY, files=tests)
    if jc:
        rep.add("PE-12", "INFO", f"Existing persona / journey test ({jc} place(s))", f"{p.rel(jfirst[0])}:{jfirst[1]}",
                "Extending this may be cheaper than writing a new template.")

    dims = dimensions(flags, has_notif)
    people = plan(dims)

    if as_json:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rep.emit(True)
        data = json.loads(buf.getvalue())
        data["dimensions"] = [{"dimension": d, "levels": lv} for d, lv in dims]
        data["plan"] = people
        json.dump(data, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0

    rep.emit(False)
    allL = flags.get("languages") or []
    if len(allL) > 3:
        print(f"\nLanguages: {len(pick_langs(allL))} of {len(allL)} go on the journey; the rest with crawl / visual / "
              "locale-time (PE-P4).")
    cols = [d for d, _ in dims]
    print("\n## Persona plan (by behaviour; every level in at least one persona)\n")
    print("| persona | " + " | ".join(cols) + " |")
    print("|" + "---|" * (len(cols) + 1))
    for row in people:
        print(f"| {row['persona']} | " + " | ".join(row.get(c, "—") for c in cols) + " |")
    print("\nGoals (5–8 per persona) by hand: the app's main jobs; success measured by data or screen "
          "(references/personas.md §Goal). Seeds: at least 2 per persona.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    return scan_project(os.path.abspath(a.root), a.json)


if __name__ == "__main__":
    sys.exit(main())
