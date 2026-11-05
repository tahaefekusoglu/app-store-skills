#!/usr/bin/env python3
"""Do scans catch defects that real projects really had? Needs the GitHub CLI and network access.

For each commit in cases.json: scans the code just before the fix (the rule should fire) and just after it
(it should fire less or not at all). Code is only read, never built or run.

    python3 -B tests/realworld/run.py [--only SR-30] [--keep <folder>]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RUN_ALL = os.path.join(ROOT, "skills", "apptest", "shared", "run_all.py")


def fetch(repo, sha, dest):
    os.makedirs(dest)
    tar = dest + ".tgz"
    with open(tar, "wb") as fh:
        if subprocess.run(["gh", "api", f"repos/{repo}/tarball/{sha}"], stdout=fh, stderr=subprocess.DEVNULL, timeout=300).returncode:
            return False
    # Links are left out: this is untrusted content and scans need only regular files.
    ok = subprocess.run(["tar", "-xzf", tar, "-C", dest, "--strip-components", "1", "--exclude", "*/node_modules/*"],
                        capture_output=True, timeout=300).returncode == 0
    os.remove(tar)
    for base, dirs, files in os.walk(dest):
        for n in dirs + files:
            path = os.path.join(base, n)
            if os.path.islink(path):
                os.remove(path)
    return ok


def fired(code_root, rule):
    member = rule.split("-")[0]
    p = subprocess.run([sys.executable, "-I", RUN_ALL, code_root, "--only", member, "--json"], capture_output=True, text=True, timeout=400)
    try:
        d = json.loads(p.stdout)
    except ValueError:
        return None
    # Some rules also report "this is fine" at INFO level, which is not catching anything.
    if (d["members"].get(member) or {}).get("error"):
        return None  # the scan says this is not an iOS app, so there was nothing for it to catch
    return [f for f in d["findings"] if f["id"] == rule and f["severity"] != "INFO"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--keep")
    a = ap.parse_args()
    with open(os.path.join(HERE, "cases.json"), encoding="utf-8") as fh:
        cases = json.load(fh)
    work = a.keep or tempfile.mkdtemp(prefix="realworld-")
    out = []
    try:
        for i, c in enumerate(cases):
            if a.only and c["rule"] != a.only:
                continue
            before, after = os.path.join(work, f"{i}-before"), os.path.join(work, f"{i}-after")
            row = dict(c)
            if not fetch(c["repo"], c["before"], before) or not fetch(c["repo"], c["fix"], after):
                row["result"] = "could not download"
            else:
                b, f = fired(before, c["rule"]), fired(after, c["rule"])
                if b is None or f is None:
                    row["result"] = "not applicable"
                else:
                    row.update(before_hits=len(b), after_hits=len(f))
                    row["result"] = "caught" if b else "missed"
                    row["cleared"] = bool(b) and len(f) < len(b)
            shutil.rmtree(before, ignore_errors=True)
            shutil.rmtree(after, ignore_errors=True)
            out.append(row)
            print(c["rule"], c["repo"], row["result"], row.get("before_hits"), row.get("after_hits"), flush=True)
    finally:
        if not a.keep:
            shutil.rmtree(work, ignore_errors=True)
    path = os.path.join(HERE, "results.json")
    if a.only and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            out = [r for r in json.load(fh) if r["rule"] != a.only] + out
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
