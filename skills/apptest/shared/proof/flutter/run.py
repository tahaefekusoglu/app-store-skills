#!/usr/bin/env python3
"""Runs the Dart templates on a small Flutter app. Needs Flutter; --device also needs a Mac with Xcode.

    python3 -I run.py <empty folder>            # widget and unit tests, about 2 minutes
    python3 -I run.py <empty folder> --device   # also a persona tour on a TEMPORARY simulator, deleted afterwards

Tests named BUG run against a planned defect and must FAIL. Everything else must pass.
Exit: 0 proof holds · 1 a template failed its proof · 2 could not run.
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def flutter_test(project, *args, env=None):
    """Runs flutter test and returns (results, process). Each result is one test, keyed by its own id rather than
    its name, since different files can hold tests with the same name. process.finished says whether the run
    reached its end: a runner that dies partway must not look like a short, successful run."""
    p = subprocess.run(["flutter", "test", "--machine", *args], cwd=project, capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, **(env or {})}, timeout=1200)
    suites, tests, results = {}, {}, []
    p.finished = False
    for line in p.stdout.splitlines():
        if not line.startswith(("[", "{")):
            continue
        try:
            items = json.loads(line)
        except ValueError:
            continue
        for e in items if isinstance(items, list) else [items]:
            if not isinstance(e, dict):
                continue
            kind = e.get("type")
            if kind == "suite" and isinstance(e.get("suite"), dict):
                suites[e["suite"].get("id")] = e["suite"].get("path") or ""
            elif kind == "testStart" and isinstance(e.get("test"), dict):
                t = e["test"]
                tests[t.get("id")] = (t.get("name") or "?", suites.get(t.get("suiteID"), ""))
            elif kind == "testDone" and not e.get("hidden"):
                name, path = tests.get(e.get("testID"), ("?", ""))
                results.append({"id": e.get("testID"), "name": name, "file": os.path.basename(path),
                                "result": e.get("result"), "skipped": bool(e.get("skipped"))})
            elif kind == "done":
                p.finished = True
    return results, p


def check(results, problems, files=()):
    """Every planned defect must fail, everything else must pass, nothing may be skipped, and every file asked
    for must report at least one test. Returns how many results were as expected."""
    good, seen = 0, set()
    for r in results if isinstance(results, list) else []:
        name, where = r["name"], (r["file"] or "?") + ": " + r["name"]
        seen.add(r["file"])
        if name.startswith("loading "):
            if r["result"] != "success":
                problems.append(f"did not compile: {r['file'] or name}")
            continue
        if name.startswith("BUG-EXEMPT"):
            continue
        if r["skipped"]:
            problems.append(f"SKIPPED, so not proven: {where}")
        elif name.startswith("BUG"):
            if r["result"] == "success":
                problems.append(f"SHOULD HAVE FAILED: {where}")
            else:
                good += 1
        elif r["result"] != "success":
            problems.append(f"FAILED: {where} ({r['result']})")
        else:
            good += 1
    if not isinstance(results, list):
        problems.append("test results could not be read")
    for f in files:
        if os.path.basename(f) not in seen:
            problems.append(f"no result from {os.path.basename(f)}: the run stopped early or the file did not load")
        elif "_bug_" in f and not any(r["file"] == os.path.basename(f) and r["name"].startswith("BUG") and not r["name"].startswith("BUG-EXEMPT")
                                       and r["result"] != "success" and not r["skipped"] for r in results):
            problems.append(f"{os.path.basename(f)}: no planned defect was caught")
    return good


def finished(p, problems, what):
    """Exit 1 is expected (the planned defects fail); anything else, or no end-of-run event, means the runner broke."""
    if not getattr(p, "finished", False):
        problems.append(f"{what}: the test run did not reach its end")
    if p.returncode not in (0, 1):
        problems.append(f"{what}: the test runner exited with {p.returncode}: " + ((p.stderr or "") + (p.stdout or ""))[-300:])


def device_tour(project, problems):
    subprocess.run(["flutter", "create", "--platforms=ios", "--org", "dev.proof", "."], cwd=project, capture_output=True)
    runtimes = subprocess.run(["xcrun", "simctl", "list", "runtimes"], capture_output=True, text=True).stdout
    rt = re.findall(r"com\.apple\.CoreSimulator\.SimRuntime\.iOS-[\d-]+", runtimes)
    if not rt:
        problems.append("no iOS simulator runtime")
        return
    ud = None
    for model in ("iPhone 17 Pro", "iPhone 16 Pro", "iPhone 15 Pro"):
        c = subprocess.run(["xcrun", "simctl", "create", "apptest-proof-flutter", model, rt[0]], capture_output=True, text=True)
        if c.returncode == 0:
            ud = c.stdout.strip()
            break
    if not ud:
        problems.append("could not create a temporary simulator")
        return
    try:
        subprocess.run(["xcrun", "simctl", "boot", ud], capture_output=True)
        subprocess.run(["xcrun", "simctl", "bootstatus", ud, "-b"], capture_output=True, timeout=400)
        done, p = flutter_test(project, "integration_test/tour_test.dart", "-d", ud)
        before = len(problems)
        check(done, problems, ["integration_test/tour_test.dart"])
        finished(p, problems, "device tour")
        if len(problems) == before:
            print("device tour passed on temporary simulator: " + ", ".join(r["name"] for r in done if not r["name"].startswith("loading ")))
    finally:
        subprocess.run(["xcrun", "simctl", "shutdown", ud], capture_output=True)
        subprocess.run(["xcrun", "simctl", "delete", ud], capture_output=True)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    if not shutil.which("flutter"):
        print("Flutter not found")
        return 2
    project = os.path.abspath(sys.argv[1])
    os.makedirs(project, exist_ok=True)
    if os.listdir(project):
        print("The folder must be empty")
        return 2
    subprocess.run([sys.executable, "-I", os.path.join(HERE, "generate.py"), project], check=True)
    pub = subprocess.run(["flutter", "pub", "get"], cwd=project, capture_output=True, text=True)
    if pub.returncode:
        print(pub.stdout[-800:], pub.stderr[-400:])
        return 2
    problems = []
    # The planned date bug exists only where the clocks change, so it runs in Berlin only.
    files = sorted(os.path.join("test", f) for f in os.listdir(os.path.join(project, "test")) if "_dst_" not in f)
    done, p = flutter_test(project, *files)
    n = check(done, problems, files)
    finished(p, problems, "main run")
    tz_files = ("test/time_test.dart", "test/time_dst_bug_test.dart")
    berlin, pb = flutter_test(project, *tz_files, env={"TZ": "Europe/Berlin"})
    n += check(berlin, problems, tz_files)
    finished(pb, problems, "Berlin run")
    if "--device" in sys.argv:
        device_tour(project, problems)
    print(f"{n} results as expected · {len(problems)} problems")
    for x in problems:
        print(" ", x)
    print("PROOF-OK" if not problems else "PROOF-FAILED")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
