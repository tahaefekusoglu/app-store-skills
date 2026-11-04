#!/usr/bin/env python3
"""apptest-time-travel: (1) where the app gets "now" from: is there a clock
hook (an injectable clock), and how many places call now() directly; (2) time
travel moments for the given time zones and years: DST transitions, month and
year ends, Feb 29, midnight.

Standard library only (zoneinfo, Python 3.9+); does NOT write to the project.

    python3 -I tt_scan.py <project_root> [--json]
    python3 -I tt_scan.py --moments --tz Europe/Berlin --year 2026 [--year 2027]
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apptest", "shared", "scanlib.py")
_s = importlib.util.spec_from_file_location("apptest_scanlib", _p)
scan = importlib.util.module_from_spec(_s)
_s.loader.exec_module(scan)

NOW = {
    "dart": r"DateTime\.now\(\)",
    "swift": r"\bDate\(\)|Date\.now\b|NSDate\(\)",
    "objc": r"\[NSDate date\]",
    "js": r"\bnew Date\(\)|Date\.now\(\)",
    "kotlin": r"Clock\.System\.now\(\)|System\.currentTimeMillis\(\)",
    "csharp": r"DateTime\.(Now|UtcNow|Today)\b|DateTimeOffset\.(Now|UtcNow)\b",
}
CLOCK_HOOK = r"clockProvider|\bclock\.now\(\)|package:clock|withClock|Clock\s*\{|protocol\s+\w*Clock\b|\bvar now\s*:\s*\(\)|" \
             r"nowProvider|dateProvider|currentDate\s*:\s*\(\)|DateProvider|TimeProvider|ISystemClock|IClock\b|" \
             r"getNow\s*[:=]|now\s*:\s*\(\)\s*=>|Clock\.fixed|@Dependency\(\\\.date\)|\\\.date\.now"


def scan_project(root: str, as_json: bool):
    p = scan.load_profile(root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("TT", p, "time-travel scan")
    files = scan.code_files(p)
    hook_c, hook_first = scan.count(p, CLOCK_HOOK, files=files)
    direct = []
    for lg, pat in NOW.items():
        for f, n, line, m in scan.grep(p, pat, langs={lg}, files=[x for x in files if scan.lang_of(x) == lg],
                                       max_hits=2000):
            direct.append((p.rel(f), n))
    if hook_c:
        rep.add("TT-10", "INFO", f"Clock hook found ({hook_c} place(s))", f"{p.rel(hook_first[0])}:{hook_first[1]}",
                "Tests fix / advance the clock here. Places that BYPASS the hook and call now() directly are below.")
    else:
        rep.add("TT-10", "INFO", "No injectable clock found", "—",
                "Not a finding (TT-P2): if the clock cannot be changed, time travel is done with manual scenarios / time zones; "
                "a small optional hook can be suggested (the user decides).")
    per_file: dict[str, int] = {}
    for rel, _n in direct:
        per_file[rel] = per_file.get(rel, 0) + 1
    if direct:
        top = sorted(per_file.items(), key=lambda x: -x[1])[:8]
        rep.add("TT-11", "SUGGESTION" if hook_c else "INFO", f"Direct now() use: {len(direct)} place(s), {len(per_file)} file(s)",
                "; ".join(f"{r} ×{c}" for r, c in top),
                "A business rule that calls now() directly while a hook exists cannot be fixed in tests: prioritize files "
                "that compute dates, due dates or cycles.")
    rep.emit(as_json)
    return 0


def month_ends(year):
    for m in range(1, 13):
        nxt = dt.date(year + (m == 12), m % 12 + 1, 1)
        yield nxt - dt.timedelta(days=1)


def dst_transitions(tz: str, year: int):
    """Moments when the local UTC offset changes (hourly scan + narrowing to the minute)."""
    z = ZoneInfo(tz)
    out = []
    t = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
    end = dt.datetime(year + 1, 1, 1, tzinfo=dt.timezone.utc)
    prev = t.astimezone(z).utcoffset()
    while t < end:
        nt = t + dt.timedelta(hours=1)
        off = nt.astimezone(z).utcoffset()
        if off != prev:
            lo, hi = t, nt
            while (hi - lo) > dt.timedelta(minutes=1):
                mid = lo + (hi - lo) / 2
                if mid.astimezone(z).utcoffset() == prev:
                    lo = mid
                else:
                    hi = mid
            before = lo.astimezone(z)
            after = hi.astimezone(z)
            kind = "forward (23-hour day)" if off > prev else "back (25-hour day)"
            out.append({"utc": hi.strftime("%Y-%m-%d %H:%M"), "local_before": before.strftime("%Y-%m-%d %H:%M %Z"),
                        "local_after": after.strftime("%Y-%m-%d %H:%M %Z"), "kind": kind})
            prev = off
        t = nt
    return out


def moments(tzs, years, as_json):
    if ZoneInfo is None:
        print("zoneinfo is missing (requires Python 3.9+)", file=sys.stderr)
        return 2
    data = {}
    for tz in tzs:
        for y in years:
            leap = dt.date(y, 2, 29) if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else None
            data[f"{tz} {y}"] = {
                "dst": dst_transitions(tz, y),
                "month_ends": [d.isoformat() for d in month_ends(y)],
                "feb_29": leap.isoformat() if leap else None,
                "year_end": f"{y}-12-31 23:59 → {y + 1}-01-01 00:00",
            }
    if as_json:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    for k, v in data.items():
        print(f"## {k}")
        if v["dst"]:
            for t in v["dst"]:
                print(f"- DST {t['kind']}: {t['local_before']} → {t['local_after']} (UTC {t['utc']})")
        else:
            print("- NO DST transition (day shifts do not show up in this zone; also try at least one zone with DST)")
        print(f"- Feb 29: {v['feb_29'] or 'none (not a leap year)'}")
        print(f"- year end: {v['year_end']}")
        print(f"- month ends: {', '.join(v['month_ends'])}\n")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--moments", action="store_true")
    ap.add_argument("--tz", action="append")
    ap.add_argument("--year", action="append", type=int)
    a = ap.parse_args(argv)
    if a.moments:
        return moments(a.tz or ["Europe/Berlin", "America/Los_Angeles", "Australia/Sydney"],
                       a.year or [dt.date.today().year], a.json)
    if not a.root:
        ap.error("project root or --moments")
    return scan_project(a.root, a.json)


if __name__ == "__main__":
    sys.exit(main())
