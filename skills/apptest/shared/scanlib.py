"""apptest: shared helpers for the members' scan scripts.

Standard library only; never WRITES to the project. Usage (in a member's script):

    import importlib.util, os
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", "..", "apptest", "shared", "scanlib.py")
    _s = importlib.util.spec_from_file_location("apptest_scanlib", _p)
    scan = importlib.util.module_from_spec(_s); _s.loader.exec_module(scan)

    p = scan.load_profile(root)          # result of shared/profile.py
    rep = scan.Report("LA", p)
    for f, n, line, m in scan.grep(p, r"...", langs={"swift"}):
        rep.add("LA-10", "USER BUG", "...", f"{p.rel(f)}:{n}")
    rep.emit(as_json=False)

Findings are CANDIDATES: the member's SKILL.md says how to verify each one.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys

# A non-UTF-8 Windows console must not crash on non-ASCII letters (every OS).
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = os.path.dirname(os.path.abspath(__file__))

LANG = {
    ".swift": "swift", ".m": "objc", ".mm": "objc", ".h": "objc",
    ".dart": "dart", ".ts": "js", ".tsx": "js", ".js": "js", ".jsx": "js",
    ".kt": "kotlin", ".java": "java", ".cs": "csharp", ".xaml": "xaml", ".gd": "gdscript",
}
SEVERITY_ORDER = {"REJECTION RISK": 0, "USER BUG": 1, "SUGGESTION": 2, "INFO": 3}
# Generated file: the marker comes BEFORE the extension (api.pb.swift, Foo+Generated.swift, Bar.generated.ts). The
# pattern used to look at the END of the name, so protobuf / SwiftGen output got scanned (e.g. Pocket Casts api.pb.swift).
GENERATED = re.compile(r"(\.g\.dart|\.freezed\.dart|\.gr\.dart|\.mocks\.dart|\.pb\.\w+|\.pbobjc\.[hm]|\.pbenum\.dart|"
                       r"\.pbjson\.dart|\.grpc\.\w+|[+._-][Gg]enerated\.\w+|\.designer\.cs|R\.generated\.swift|"
                       r"\.min\.js)$|/(generated|Generated|gen|SwiftGen)/")
TEST_PATH = re.compile(r"(?i)(/tests?/|/__tests__/|/spec/|Tests?/|UITests/|_test\.|\.test\.|\.spec\.|"
                       r"/tests?\.(tsx?|jsx?)$|[a-z]Tests?\.(swift|mm?|kt|cs)$|/detox/|/e2e/|/__e2e__/|"
                       r"/integration_test/|/test_driver/|Mock|Fixture|/Preview Content/|Previews?\.swift$|"
                       r"previews?\.(dart|tsx?|jsx?)$|/previews?/|/\.?storybook/|/widgetbook/|/jest/|/\.?maestro/|[a-z]Test(Utils?|Helpers?)\.|/test-?utils?/|\.stories\.(t|j)sx?$)")


def load_profile(root: str):
    spec = importlib.util.spec_from_file_location("apptest_profile", os.path.join(_HERE, "profile.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    p = mod.build(root)
    p.mod = mod
    return p


def techs(p) -> list[str]:
    return [k.split(":", 1)[1] for k in p.items if k.startswith("tech:") and k != "tech:?"]


def lang_of(path: str) -> str | None:
    return LANG.get(os.path.splitext(path)[1])


_ts = importlib.util.spec_from_file_location("apptest_terms", os.path.join(os.path.dirname(os.path.abspath(__file__)), "terms.py"))
terms = importlib.util.module_from_spec(_ts)
_ts.loader.exec_module(terms)

TRUNCATED: list[str] = []  # scans that hit a limit (written to the report)


def code_files(p, langs: set[str] | None = None, include_tests: bool = False,
               ios_only: bool = True, limit: int = 12000) -> list[str]:
    out = []
    for f in p.files:
        lg = lang_of(f)
        if not lg or (langs and lg not in langs):
            continue
        rel = "/" + p.rel(f)
        # Repo tooling is not code either (e.g. addresses in Expensify .github/actions); CI checks read p.files.
        if GENERATED.search(rel) or "/node_modules/" in rel or "/Pods/" in rel or "/vendor/" in rel \
                or "/.github/" in rel or "/.circleci/" in rel or "/.gitlab/" in rel:
            continue
        if not include_tests and TEST_PATH.search(rel):
            continue
        if ios_only and not p.mod.ios_path(f):
            continue
        out.append(f)
        if len(out) >= limit:
            msg = f"code file limit ({limit}) exceeded: only the first {limit} files were scanned"
            if msg not in TRUNCATED:
                TRUNCATED.append(msg)
            break
    return out


def load_suppressed(root: str) -> dict[str, str]:
    """CONVENTIONS §9: items the user suppressed. Lines under the "## Suppressed" heading of
    `<root>/.apptest/profile.md`, a file created only if the user asks:
        - LA-11 — reason (2026-10-28)
    The id can be a single item (LA-11) or a member prefix (LA-*). {id: reason}."""
    path = os.path.join(root, ".apptest", "profile.md")
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return {}
    m = re.search(r"(?ims)^##\s*(?:Suppressed|Kapat[ıi]lanlar)\s*$(.*?)(?=^##\s|\Z)", text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"\s*[-*]\s*`?([A-Z]{2}-(?:\d+|\*))`?\s*(?:[—:-]\s*(.*))?$", line)
        if mm:
            out[mm.group(1)] = (mm.group(2) or "").strip()
    return out


def is_suppressed(fid: str, suppressed: dict) -> bool:
    return fid in suppressed or (fid[:3] + "*") in suppressed


_COMMENT_START = re.compile(r"^\s*(//|#(?!(if|else|elif|endif|available|selector|Preview|warning|error))|\*|/\*|<!--|///)")


def lines(path: str, max_bytes: int = 400_000):
    """(line_no, line): skips comment lines only (strings inside code stay)."""
    text = p_read(path, max_bytes)
    in_block = False
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("/*") and "*/" not in s:
            in_block = True
            continue
        if _COMMENT_START.match(line):
            continue
        yield n, line


_PARTIAL_FILES: list[str] = []
_UNREADABLE: list[str] = []


def _note(bucket: list, what: str, path: str, label: str):
    """Gathers one kind of cut-off in a single line: "2 files ... (a, b)". The list stays short as the count grows."""
    name = os.path.basename(path)
    if name in bucket:
        return
    bucket.append(name)
    msg = f"{label}: {len(bucket)} files ({', '.join(bucket[:5])}{'...' if len(bucket) > 5 else ''})"
    for i, old in enumerate(TRUNCATED):
        if old.startswith(label + ":"):
            TRUNCATED[i] = msg
            return
    TRUNCATED.append(msg)


def p_read(path: str, limit: int = 400_000) -> str:
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit + 1)
    except OSError:
        _note(_UNREADABLE, "unreadable", path, "unreadable file")
        return ""
    if len(data) > limit:
        _note(_PARTIAL_FILES, "truncated", path, f"only the first {limit // 1000} KB read")
        data = data[:limit]
    return data.decode("utf-8", "replace")


def grep(p, pattern, langs: set[str] | None = None, files: list[str] | None = None,
         include_tests: bool = False, max_hits: int = 400):
    """Yields (file, line_no, line, match); comment lines are skipped."""
    rx = re.compile(pattern) if isinstance(pattern, str) else pattern
    hits = 0
    for f in files if files is not None else code_files(p, langs, include_tests):
        for n, line in lines(f):
            m = rx.search(line)
            if m:
                yield f, n, line, m
                hits += 1
                if hits >= max_hits:
                    msg = f"match limit ({max_hits}) reached, the rest was not scanned"
                    if msg not in TRUNCATED:
                        TRUNCATED.append(msg)
                    return


def count(p, pattern, langs=None, files=None) -> tuple[int, tuple | None]:
    """Match count and first example (file, line)."""
    first = None
    c = 0
    for f, n, _l, _m in grep(p, pattern, langs, files, max_hits=10_000):
        c += 1
        if first is None:
            first = (f, n)
    return c, first


class Report:
    def __init__(self, member: str, p, title: str | None = None):
        self.member = member
        self.p = p
        self.title = title or member
        self.items: list[dict] = []
        self.skipped: list[str] = []
        self._seen: dict[tuple, int] = {}
        self.suppressed = load_suppressed(p.root)
        self.suppressed_hits: dict[str, int] = {}
        self.suppressed_risk: set[str] = set()  # §9: a suppressed rejection risk is stated separately

    def add(self, fid, severity, title, evidence="", note="", group_limit: int = 8):
        """The same id + title is listed at most group_limit times; the rest are counted.
        Ids the user suppressed (§9) are not listed, only counted."""
        if is_suppressed(fid, self.suppressed):
            self.suppressed_hits[fid] = self.suppressed_hits.get(fid, 0) + 1
            if severity == "REJECTION RISK":
                self.suppressed_risk.add(fid)
            return
        key = (fid, title)
        n = self._seen.get(key, 0) + 1
        self._seen[key] = n
        if n > group_limit:
            if n == group_limit + 1:
                self.items.append({"id": fid, "severity": severity, "title": title,
                                   "evidence": "(more examples: count below)", "note": "", "more": True})
            return
        self.items.append({"id": fid, "severity": severity, "title": title,
                           "evidence": evidence, "note": note})

    def skip(self, fid: str, why: str):
        self.skipped.append(f"{fid} ({why})")

    def emit(self, as_json: bool = False):
        totals = {k: v for k, v in self._seen.items()}
        self.items.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["id"]))
        if as_json:
            json.dump({"member": self.member, "root": self.p.root,
                       "flags": self.p.mod.display_flags(self.p.mod.summary_flags(self.p)), "findings": self.items,
                       "counts": {f"{k[0]} {k[1]}": v for k, v in totals.items()},
                       "skipped": self.skipped, "suppressed": self.suppressed_hits, "suppressed_risk": sorted(self.suppressed_risk),
                       "truncated": TRUNCATED}, sys.stdout, ensure_ascii=False, indent=1)
            print()
            return
        print(f"# {self.title} — `{self.p.root}`\n")
        print("This list is CANDIDATES; verify each item against its id in SKILL.md.\n")
        print("Technology: " + (", ".join(self.p.mod.display(t) for t in techs(self.p)) or "not recognized"))
        cur = None
        for f in self.items:
            if f["severity"] != cur:
                cur = f["severity"]
                print(f"\n## {cur}")
            note = f" — {f['note']}" if f["note"] else ""
            print(f"- [{f['id']}] {f['title']} — `{f['evidence']}`{note}")
        big = [(k, v) for k, v in totals.items() if v > 8]
        if big:
            print("\n## Counts (candidates with many examples)")
            for (fid, t), v in big:
                print(f"- [{fid}] {t}: {v} places")
        if self.skipped:
            print("\n## Not applicable\n" + ", ".join(self.skipped))
        if self.suppressed_hits:
            print("\n## Suppressed (user decision, .apptest/profile.md)\n" + ", ".join(
                f"{k} ×{v}" + (" (rejection risk)" if k in self.suppressed_risk else "")
                for k, v in sorted(self.suppressed_hits.items())))
        if TRUNCATED:
            print("\n## Scan limit\n" + "; ".join(TRUNCATED) + ". Result is PARTIAL.")
        if not self.items:
            print("\nNo candidates from the automatic scan. Go on to the manual / simulator steps in SKILL.md.")


def mac_only(p) -> bool:
    t = techs(p)
    return bool(t) and all(x.startswith("Native Mac") for x in t)


def guard_unknown(p, allow_mac=False) -> bool:
    """When the scan cannot run, says WHY. A wrong path is an error (exit 2, so it is not taken for "clean"); a project
    that is not an iOS app is "Not applicable" (a result, not an error)."""
    if not os.path.isdir(p.root):
        print(f"Folder missing or not a folder: {p.root}", file=sys.stderr)
        sys.exit(2)
    if mac_only(p) and not allow_mac:
        print("Not applicable: Mac-only app. This scan follows iOS rules and has not been adapted to the Mac App Store. "
              "For design, apple-design-audit works with the Mac pages.")
        return True
    if not techs(p):
        mod = getattr(p, "mod", None)
        if mod is None:
            spec = importlib.util.spec_from_file_location("apptest_profile", os.path.join(_HERE, "profile.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        print(f"Not applicable: no iOS app found ({mod.project_kind(p.root)}). apptest is for iOS apps only.")
        return True
    return False


_ONLINE = None


def online(timeout: float = 5.0) -> bool:
    """Is there internet (tested once)? Without it a link check must not blame a 'broken link'."""
    global _ONLINE
    if _ONLINE is None:
        import urllib.error
        import urllib.request
        try:
            urllib.request.urlopen(urllib.request.Request("https://www.apple.com/", method="HEAD"), timeout=timeout)
            _ONLINE = True
        except urllib.error.HTTPError:
            _ONLINE = True  # the server answered
        except Exception:  # noqa: BLE001
            _ONLINE = False
    return _ONLINE
