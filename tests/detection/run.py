#!/usr/bin/env python3
"""Do the scans find what they claim to? Standard library only.

Every rule ID in the scan scripts needs a case in cases.py: a tiny project with that defect. A case
states which rules must fire on it, and which must stay silent. Clean projects check the other side.

    python3 -B tests/detection/run.py              # all cases, exit 1 on any miss
    python3 -B tests/detection/run.py --only SR    # one scanner
    python3 -B tests/detection/run.py --json       # results for machines

This measures seeded defects, not real-world recall: it proves each rule can fire, and that the clean
projects stay quiet. Real projects are more varied than these.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import cases as C  # noqa: E402

for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SCRIPTS = {
    "SR": "apptest-store-readiness/scripts/readiness_scan.py",
    "PP": "apptest-privacy-permissions/scripts/privacy_scan.py",
    "MO": "apptest-monetization/scripts/monetization_scan.py",
    "NW": "apptest-network/scripts/network_scan.py",
    "LA": "apptest-layout-a11y/scripts/layout_scan.py",
    "LT": "apptest-locale-time/scripts/locale_scan.py",
    "DI": "apptest-data-integrity/scripts/data_scan.py",
    "IA": "apptest-input-actions/scripts/input_scan.py",
    "CS": "apptest-content-safety/scripts/content_scan.py",
    "PF": "apptest-product-fit/scripts/product_scan.py",
    "TS": "apptest-test-strategy/scripts/strategy_scan.py",
    "TH": "apptest-test-health/scripts/health_scan.py",
    "TT": "apptest-time-travel/scripts/tt_scan.py",
    "PE": "apptest-persona/scripts/pe_plan.py",
    "RI": "apptest-rapid-input/scripts/ri_scan.py",
    "LC": "apptest-lifecycle/scripts/lc_scan.py",
    "VI": "apptest-visual/scripts/vi_scan.py",
    "NC": "apptest-network-chaos/scripts/nc_scan.py",
    "DS": "apple-design-audit/scripts/hig_scan.py",
    "SA": "apptest-store-assets/scripts/assets_check.py",
}


def catalog():
    """Every rule ID the scan scripts can report."""
    ids = set()
    for rel in SCRIPTS.values():
        with open(os.path.join(ROOT, "skills", rel), encoding="utf-8") as fh:
            ids |= set(re.findall(r"""["']([A-Z]{2,3}-\d{1,3})["']""", fh.read()))
    return ids


def write(root, files):
    for rel, body in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(body if isinstance(body, bytes) else body.encode("utf-8"))


def scan(code, root, args):
    script = os.path.join(ROOT, "skills", SCRIPTS[code])
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", script, root, "--json"] + list(args),
                       capture_output=True, text=True, encoding="utf-8", timeout=180)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return None, (r.stdout + r.stderr).strip()[-300:]
    return d.get("findings", []), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    fired, problems = set(), []
    work = tempfile.mkdtemp(prefix="detect-")
    try:
        for i, c in enumerate(C.CASES):
            if a.only and c["scan"] != a.only:
                continue
            root = os.path.join(work, f"{i:03d}")
            os.makedirs(root)
            write(root, c["files"])
            found, err = scan(c["scan"], root, c.get("args", ()))
            if err is not None:
                problems.append(f'{c["name"]}: scanner gave no JSON: {err}')
                continue
            got = {f["id"] for f in found}
            titles = {f["id"]: " ".join(x["title"] for x in found if x["id"] == f["id"]) for f in found}
            for rule in c.get("expect", ()):
                if rule in got:
                    fired.add(rule)
                else:
                    problems.append(f'{c["name"]}: {rule} did not fire (got {sorted(got)})')
            for rule, text in c.get("expect_title", {}).items():
                if text not in titles.get(rule, ""):
                    problems.append(f'{c["name"]}: {rule} has no title with "{text}" ({titles.get(rule, "not fired")!r})')
                elif rule in got:
                    fired.add(rule)
            for rule in c.get("absent", ()):
                if rule in got:
                    problems.append(f'{c["name"]}: {rule} should stay silent: {titles[rule][:110]}')
            for f in found:
                if c.get("clean") and f["severity"] in ("REJECTION RISK", "USER BUG"):
                    problems.append(f'{c["name"]}: clean project got {f["id"]} {f["severity"]}: {f["title"][:90]}')
    finally:
        shutil.rmtree(work, ignore_errors=True)

    rules = catalog()
    if a.only:
        rules = {r for r in rules if r.startswith(a.only + "-")}
    excluded = {r for r in rules if r in C.NOT_TESTED}
    wanted = rules - excluded
    missing = sorted(wanted - fired)
    for rule in missing:
        if not any(rule in p for p in problems):
            problems.append(f"{rule}: no case covers this rule")
    if a.json:
        json.dump({"rules": len(rules), "fired": len(fired & wanted), "not_tested": C.NOT_TESTED if not a.only else {},
                   "problems": problems}, sys.stdout, indent=2, ensure_ascii=False)
        print()
    else:
        print(f"{len(fired & wanted)} of {len(wanted)} testable rules fired on a seeded defect; "
              f"{len(excluded)} not tested here.")
        for rule in sorted(excluded):
            print(f"  not tested: {rule}: {C.NOT_TESTED[rule]}")
        for p in problems:
            print("  PROBLEM:", p)
        if not problems:
            print("No misses, and clean projects stayed quiet.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
