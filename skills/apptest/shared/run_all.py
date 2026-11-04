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
The number of findings does not change the exit code.
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
#   python3 -I ~/.claude/skills/apptest-store-assets/scripts/assets_check.py <folder>
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
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        return None, "script output is not in the expected format", time.time() - t0
    return data, "", time.time() - t0


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
    if a.json:
        json.dump({"root": os.path.abspath(a.root), "members": results, "findings": merged,
                   "problems": problems, "complete": not problems}, sys.stdout, ensure_ascii=False, indent=1)
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
    cur = None
    for f in merged:
        if f["severity"] != cur:
            cur = f["severity"]
            print(f"\n## {cur}")
        also = f" (also: {', '.join(f['also'])})" if f["also"] else ""
        note = f" — {f['note']}" if f.get("note") else ""
        print(f"- [{f['id']}]{also} {f['title']} — `{f['evidence']}`{note}")
        for d in f["also_detail"]:
            print(f"  - {d['id']} same issue: {d['title']}" + (f" — {d['note']}" if d.get("note") else ""))
    if problems:
        print("\n## Scan incomplete\nThese members gave no result; this does not count as \"no findings\":\n" + "\n".join(f"- {x}" for x in problems))
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
