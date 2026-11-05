#!/usr/bin/env python3
"""apptest: runs the static scans of the installed members in order and gives one report.

Standard library only; never WRITES to the project. STATIC scans only: simulator
tours, manual lists and reading Apple's current rules page (principle 7) are still
done separately, following each member's SKILL.md. This report alone does not
mean "ready to submit".

    python3 -I run_all.py <project_root> [--only SR,PP] [--json]
                          [--check-links] [--policy-url URL]

Order (family head's Release mode): store-readiness → privacy-permissions →
monetization → network → layout-a11y → locale-time → data-integrity →
input-actions → content-safety → product-fit.
Findings at the same place merge only if they are the SAME ISSUE (SAME_ISSUE); different issues stay separate (CONVENTIONS §2).
Exit: 0 scan complete · 2 wrong usage · 3 scan incomplete (script missing or a member errored).
The number of findings does not change the exit code. A scan that read only part of some files still exits 0.
JSON: `execution_complete` = every member ran; `coverage_partial` = what was not read in full;
`complete` = both, so only true when nothing failed and nothing was cut short.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

# A non-UTF-8 Windows console must not crash on non-ASCII letters (every OS).
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SKILLS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MEMBERS = [  # (code, folder, script)
    ("SR", "apptest-store-readiness", "readiness_scan.py"),
    ("PP", "apptest-privacy-permissions", "privacy_scan.py"),
    ("MO", "apptest-monetization", "monetization_scan.py"),
    ("NW", "apptest-network", "network_scan.py"),
    ("LA", "apptest-layout-a11y", "layout_scan.py"),
    ("LT", "apptest-locale-time", "locale_scan.py"),
    ("DI", "apptest-data-integrity", "data_scan.py"),
    ("IA", "apptest-input-actions", "input_scan.py"),
    ("CS", "apptest-content-safety", "content_scan.py"),
    ("PF", "apptest-product-fit", "product_scan.py"),
    ("TS", "apptest-test-strategy", "strategy_scan.py"),
    ("TH", "apptest-test-health", "health_scan.py"),
    ("TT", "apptest-time-travel", "tt_scan.py"),
    ("PE", "apptest-persona", "pe_plan.py"),
    ("RI", "apptest-rapid-input", "ri_scan.py"),
    ("LC", "apptest-lifecycle", "lc_scan.py"),
    ("VI", "apptest-visual", "vi_scan.py"),
    ("NC", "apptest-network-chaos", "nc_scan.py"),
]
# store-assets checks an IMAGE FOLDER (not the project root), so run it separately:
#   python3 -I <skills>/apptest-store-assets/scripts/assets_check.py <folder>
ORDER = {"REJECTION RISK": 0, "USER BUG": 1, "SUGGESTION": 2, "INFO": 3}
# Pairs where two members report the same bug from their own angle. If not listed, it is a separate issue even on the same line.
SAME_ISSUE = {frozenset(x) for x in (("TS-12", "TH-14"), ("TS-16", "TH-11"), ("SR-41", "NW-13"), ("SR-21", "PP-12"))}


def dedupe_key(evidence: str) -> str | None:
    """Evidence pointing at the same place: "file:line ..." or "file › KEY ..."."""
    ev = evidence.strip("`")
    if "›" in ev:
        file, rest = ev.split("›", 1)
        return file.strip() + " › " + rest.strip().split(" ")[0].strip("'\"")
    first = ev.split(" ")[0]
    return first if ":" in first and first.split(":")[-1].isdigit() else None


def invalid_report(data) -> str | None:
    """What is wrong with a member's report, or None. A broken member is reported; it must not stop the others."""
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        return "no findings list"
    for i, f in enumerate(data["findings"]):
        if not isinstance(f, dict):
            return f"finding {i} is not an object"
        if not isinstance(f.get("id"), str) or not f["id"]:
            return f"finding {i} has no id"
        if not isinstance(f.get("severity"), str) or f["severity"] not in ORDER:
            return f"finding {i} has an unknown severity"
        if not isinstance(f.get("title"), str) or not f["title"].strip():
            return f"finding {i} has no title"
        for k in ("evidence", "note"):
            if not isinstance(f.get(k, ""), str):
                return f"finding {i}: {k} is not text"
    for k, kind in (("suppressed", dict), ("suppressed_risk", list), ("skipped", list), ("truncated", list)):
        if not isinstance(data.get(k, kind()), kind):
            return f"{k} has the wrong type"
    # Their items are joined and sorted into the report, so each one must be text.
    for k in ("suppressed_risk", "skipped", "truncated"):
        if not all(isinstance(x, str) for x in data.get(k, [])):
            return f"{k} holds something that is not text"
    if not all(isinstance(k, str) and isinstance(v, (int, str)) for k, v in data.get("suppressed", {}).items()):
        return "suppressed holds something that is not a count"
    return None


def run(script: str, root: str, extra: list[str]) -> tuple[dict | None, str, float]:
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, "-I", "-X", "utf8", script, root, "--json", *extra],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    except subprocess.TimeoutExpired:
        return None, "timed out (300 s)", time.time() - t0
    if r.returncode != 0:
        return None, (r.stderr.strip().splitlines() or ["error"])[-1][:200], time.time() - t0
    try:
        data = json.loads(r.stdout)
    except ValueError:
        # technology not recognized: the script prints plain text. Empty output is not "clean".
        return None, r.stdout.strip()[:200] or "script produced no output", time.time() - t0
    bad = invalid_report(data)
    if bad:
        return None, f"script output is not in the expected format: {bad}", time.time() - t0
    return data, "", time.time() - t0


# These stop an upload or commonly cause a rejection, so they come first when choosing what to fix.
FIRST_RULES = ("SR-61", "SR-13", "SR-10", "SR-11", "SR-22", "SR-21", "SR-23", "SR-30", "SR-31", "PP-10", "NW-10", "MO-13", "MO-14")
START_HERE_LIMIT = 5
SHOW_PER_RULE = 5


def start_here(merged):
    """At most five things to look at first: the most serious, one line per rule, with how many there are."""
    serious = [f for f in merged if f["severity"] in ("REJECTION RISK", "USER BUG")]
    counts = {}
    for f in serious:
        counts[f["id"]] = counts.get(f["id"], 0) + 1
    first = {}
    for f in serious:
        first.setdefault(f["id"], f)

    def rank(f):
        fixed = FIRST_RULES.index(f["id"]) if f["id"] in FIRST_RULES else len(FIRST_RULES)
        return (0 if f["severity"] == "REJECTION RISK" else 1, fixed, f["id"])

    return [{"id": f["id"], "severity": f["severity"], "title": f["title"], "evidence": f["evidence"],
             "count": counts[f["id"]]} for f in sorted(first.values(), key=rank)[:START_HERE_LIMIT]]


# Which short command looks closer at each scan. Only the ones a person would run next.
NEXT_COMMAND = {"SR": "c ready", "PP": "c privacy", "MO": "c money", "NW": "c account", "PF": "c product", "CS": "c content",
                "LA": "c layout", "LT": "c locale", "DI": "c data", "IA": "c input", "TS": "t plan", "TH": "t health",
                "TT": "t time", "RI": "t double", "LC": "t lifecycle", "VI": "t visual", "NC": "t network", "PE": "t persona"}


def next_steps(first):
    """The member to open for each Start here item, in the same order, without repeats. The skill's own name
    comes with the short command, so the step works whatever names a translated /app uses."""
    folders = {code: folder for code, folder, _script in MEMBERS}
    steps = {}
    for x in first:
        code = x["id"].split("-")[0]
        if code in NEXT_COMMAND:
            steps.setdefault(NEXT_COMMAND[code], {"skill": folders.get(code, ""), "rules": []})["rules"].append(x["id"])
    return [{"command": c, "skill": v["skill"], "rules": v["rules"]} for c, v in steps.items()]


def print_findings(merged):
    """Serious findings in full. Lower ones are capped per rule, and INFO is one line per rule: JSON keeps everything."""
    cur = None
    shown = {}
    for f in merged:
        if f["severity"] != cur:
            cur = f["severity"]
            print(f"\n## {cur}")
            if cur == "INFO":
                by_rule = {}
                for x in merged:
                    if x["severity"] == "INFO":
                        by_rule.setdefault(x["id"], []).append(x)
                for rule, items in by_rule.items():
                    text = "; ".join(i["title"] for i in items[:2])
                    more = f" (+{len(items) - 2} more)" if len(items) > 2 else ""
                    print(f"- [{rule}] {text}{more}")
                return
        limited = cur == "SUGGESTION"
        shown[f["id"]] = shown.get(f["id"], 0) + 1
        if limited and shown[f["id"]] > SHOW_PER_RULE:
            continue
        also = f" (also: {', '.join(f['also'])})" if f["also"] else ""
        note = f" — {f['note']}" if f.get("note") else ""
        print(f"- [{f['id']}]{also} {f['title']} — `{f['evidence']}`{note}")
        for d in f["also_detail"]:
            print(f"  - {d['id']} same issue: {d['title']}" + (f" — {d['note']}" if d.get("note") else ""))
        total = sum(1 for x in merged if x["id"] == f["id"] and x["severity"] == cur)
        if limited and shown[f["id"]] == SHOW_PER_RULE and total > SHOW_PER_RULE:
            print(f"- [{f['id']}] and {total - SHOW_PER_RULE} more like this (--json lists all)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--only", help="e.g. SR,PP")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check-links", action="store_true")
    ap.add_argument("--policy-url")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.root):
        print(f"Folder missing or not a folder: {a.root}", file=sys.stderr)
        return 2
    only = {x.strip().upper() for x in a.only.split(",") if x.strip()} if a.only is not None else None
    known = {m[0] for m in MEMBERS}
    if only is not None and (not only or only - known):
        print(f"Unknown member: {', '.join(sorted(only - known)) or '(empty)'}. Valid: {', '.join(sorted(known))}", file=sys.stderr)
        return 2
    results, problems, merged, seen = {}, [], [], {}
    for code, folder, script in MEMBERS:
        path = os.path.join(SKILLS, folder, "scripts", script)
        if only and code not in only:
            continue
        if not os.path.exists(path):
            err = f"script missing: {folder}/scripts/{script} (incomplete install); this member was NOT scanned"
            results[code] = {"seconds": 0, "error": err, "candidates": 0, "suppressed": {}, "suppressed_risk": [], "skipped": [], "partial": []}
            problems.append(f"{code}: {err}")
            continue
        extra = []
        if code == "SR" and a.check_links:
            extra.append("--check-links")
        if code == "PP" and a.policy_url:
            extra += ["--policy-url", a.policy_url]
        data, err, dur = run(path, a.root, extra)
        results[code] = {"seconds": round(dur, 1), "error": err or None,
                         "candidates": len(data["findings"]) if data else 0,
                         "suppressed": (data or {}).get("suppressed", {}),
                         "suppressed_risk": (data or {}).get("suppressed_risk", []),
                         "skipped": (data or {}).get("skipped", []),
                         "partial": (data or {}).get("truncated", [])}
        if err and not err.startswith("Not applicable"):
            problems.append(f"{code}: {err}")
        for f in (data or {}).get("findings", []):
            key = dedupe_key(f.get("evidence", ""))
            # Only a pair reporting the same issue merges; the second one's note is kept too.
            prev = seen.get(key) if key else None
            if prev and frozenset((prev["id"], f["id"])) in SAME_ISSUE and f["severity"] != "INFO":
                prev["also"].append(f["id"])
                prev["also_detail"].append({k: f.get(k) for k in ("id", "severity", "title", "note")})
                if ORDER.get(f["severity"], 9) < ORDER.get(prev["severity"], 9):
                    prev["severity"] = f["severity"]  # the higher severity stays (§2)
                continue
            f = dict(f, also=[], also_detail=[])
            merged.append(f)
            if key and key not in seen:
                seen[key] = f
    merged.sort(key=lambda f: (ORDER.get(f["severity"], 9), f["id"]))
    partial = sorted({x for r in results.values() for x in r["partial"]})
    if a.json:
        json.dump({"root": os.path.abspath(a.root), "members": results, "findings": merged, "start_here": start_here(merged), "next": next_steps(start_here(merged)),
                   "problems": problems, "execution_complete": not problems, "coverage_partial": partial,
                   "complete": not problems and not partial}, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 3 if problems else 0
    if results and all((r["error"] or "").startswith("Not applicable") for r in results.values()):
        print(next(iter(results.values()))["error"])
        return 0
    cnt = {s: sum(1 for f in merged if f["severity"] == s) for s in ORDER}
    print(f"# apptest combined scan: `{os.path.abspath(a.root)}`\n")
    print("STATIC scans only; these are candidates. Apple's current rules page (principle 7), simulator tours and "
          "manual lists are done SEPARATELY, following each member's SKILL.md.\n")
    for f in merged:
        if f["id"] == "SR-09":
            print(f"> **{f['title']}** {f.get('note', '')}\n")
    print("**Summary:** " + " · ".join(f"{k}: {v}" for k, v in cnt.items()) + "\n")
    first = start_here(merged)
    hidden = sorted({k for r in results.values() for k in r["suppressed_risk"]})
    print("## Start here\n")
    if first:
        for i, x in enumerate(first, 1):
            more = f" ({x['count']} places)" if x["count"] > 1 else ""
            print(f"{i}. **[{x['id']}] {x['title']}**{more} — `{x['evidence']}`")
    elif problems or partial:
        print("Nothing serious found in what was read, but the scan is INCOMPLETE (see below), so this is not a clean "
              "result.")
    elif hidden:
        print("Nothing serious is showing, but only because rejection risks are suppressed (below).")
    else:
        print("No rejection risks or user bugs among the static candidates. Tours and manual lists are still to do.")
    if hidden:
        # The user chose to hide these, but a summary must not read as if they were gone.
        print(f"\n**Suppressed rejection risks:** {', '.join(hidden)} (in `.apptest/profile.md`). "
              "They are hidden, not fixed.")
    print()
    if partial:
        print("**Partial scan:** " + "; ".join(partial) + "\n")
    print("| Member | Candidates | Time | Note |\n|---|---|---|---|")
    for code, r in results.items():
        note = r["error"] or ""
        if r["skipped"] and not r["candidates"]:  # "0 candidates" does not mean clean: this member did not run here
            note += "not applicable: " + "; ".join(r["skipped"])[:90]
        if r["partial"]:
            note += " PARTIAL: " + "; ".join(r["partial"])
        if r["suppressed"]:
            note += " suppressed: " + ", ".join(f"{k}×{v}" + (" (rejection risk)" if k in r["suppressed_risk"] else "") for k, v in r["suppressed"].items())
        print(f"| {code} | {r['candidates']} | {r['seconds']} s | {note.strip()} |")
    print_findings(merged)
    steps = next_steps(first)
    if steps:
        print("\n## Next\n\nThese scans only point. To verify an item against the code and Apple's current rules:\n")
        for x in steps:
            print(f"- `/app {x['command']}` ({x['skill']}) for {', '.join(x['rules'])}")
    if problems:
        print("\n## Scan incomplete\nThese members gave no result; this does not count as \"no findings\":\n" + "\n".join(f"- {x}" for x in problems))
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
