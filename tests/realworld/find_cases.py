#!/usr/bin/env python3
"""Finds commits that really fixed a defect a scan rule claims to catch, for tests/realworld/run.py.

A commit counts only if its diff adds what the rule looks for. Needs the GitHub CLI. Writes cases.json.

    python3 -B tests/realworld/find_cases.py [SR-30 PP-10 ...]
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SEARCH = {
    "SR-30": (["add privacy manifest", "add PrivacyInfo.xcprivacy", "privacy manifest ios"], r"(?m)^PrivacyInfo\.xcprivacy$|/PrivacyInfo\.xcprivacy$", None),
    "PP-10": (["add camera usage description", "add NSPhotoLibraryUsageDescription", "add NSMicrophoneUsageDescription", "missing usage description info.plist"], None, r"(?m)^\+.*<key>NS\w+UsageDescription</key>"),
    "MO-13": (["add restore purchases button", "add restore purchase ios", "restore purchases storekit"], None, r"(?m)^\+.*(restorePurchases|AppStore\.sync|restoreCompletedTransactions|restoreTransactions)"),
    "NW-10": (["add delete account feature ios", "add account deletion app", "implement delete account flutter"], None, r"(?im)^\+.*(delete_?account|account_?deletion|deleteUser)"),
    "LA-20": (["add accessibility label icon button", "add tooltip IconButton accessibility", "add accessibilityLabel pressable"], None, r"(?m)^\+.*(accessibilityLabel|tooltip\s*:|semanticLabel)"),
    "IA-11": (["add delete confirmation dialog", "confirm before delete", "add confirmation alert delete swiftui"], None, r"(?im)^\+.*(showDialog|Alert\.alert|confirmationDialog|\.alert\(|UIAlertController|showCupertinoDialog)"),
    "LT-10": (["fix days calculation daylight saving", "fix day difference DST"], None, r"(?m)^\+.*(calendarDays|startOfDay|dateComponents|DateTime\.utc|differenceInCalendarDays)"),
}
PER_RULE = 12
MOBILE = re.compile(r"\.(swift|dart|tsx|jsx|m|plist|xcprivacy)$")


def gh(*a):
    """Waits and retries on GitHub's rate limit, so that a limit is never mistaken for "no results"."""
    for wait in (0, 90, 180, 300):
        time.sleep(wait)
        r = subprocess.run(["gh", *a], capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            return r.stdout
        if "rate limit" not in r.stderr.lower():
            return ""
    sys.exit("GitHub's rate limit did not clear; results would be incomplete")


def main():
    path = os.path.join(HERE, "cases.json")
    wanted = sys.argv[1:] or list(SEARCH)
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            out = [c for c in json.load(fh) if c["rule"] not in wanted]
    for rule, (queries, filename, patch) in SEARCH.items():
        if rule not in wanted:
            continue
        kept, seen = 0, set()
        for q in queries:
            time.sleep(3)
            raw = gh("search", "commits", q, "--limit", "50", "--json", "repository,sha")
            for item in json.loads(raw or "[]"):
                repo, sha = item["repository"]["fullName"], item["sha"]
                if kept >= PER_RULE or repo in seen:
                    continue
                seen.add(repo)
                info = gh("api", f"repos/{repo}")
                if not info or json.loads(info).get("size", 10**9) > 120_000 or json.loads(info).get("fork"):
                    continue
                c = gh("api", f"repos/{repo}/commits/{sha}")
                if not c:
                    continue
                c = json.loads(c)
                if len(c.get("parents", [])) != 1:
                    continue
                files = [f for f in c.get("files", []) if MOBILE.search(f["filename"])]
                if not files or len(c.get("files", [])) > 25:
                    continue
                if filename and not any(f["status"] == "added" and re.search(filename, f["filename"]) for f in files):
                    continue
                if patch and not any(re.search(patch, f.get("patch", "")) for f in files):
                    continue
                tree = gh("api", f"repos/{repo}/git/trees/{sha}")
                if not tree or not re.search(r'"(ios|[\w.-]+\.xcodeproj|pubspec\.yaml|package\.json|Package\.swift)"', tree):
                    continue
                out.append({"rule": rule, "repo": repo, "fix": sha, "before": c["parents"][0]["sha"],
                            "files": [f["filename"] for f in files][:8], "title": c["commit"]["message"].split("\n")[0][:90]})
                kept += 1
                print(rule, repo, out[-1]["title"], flush=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    print(len(out), "cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
