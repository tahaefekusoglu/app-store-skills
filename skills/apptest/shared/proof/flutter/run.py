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
    p = subprocess.run(["flutter", "test", "--machine", *args], cwd=project, capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, **(env or {})}, timeout=1200)
    names, done = {}, {}
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
            if e.get("type") == "testStart":
                names[e["test"]["id"]] = e["test"]["name"]
            elif e.get("type") == "testDone" and not e.get("hidden"):
                done[names.get(e["testID"], "?")] = e["result"]
    return done, p


def check(done, problems):
    good = 0
    for name, result in sorted(done.items()):
        if name.startswith("loading "):
            if result != "success":
                problems.append(f"did not compile: {name}")
        elif name.startswith("BUG-EXEMPT"):
            continue
        elif name.startswith("BUG"):
            if result == "success":
                problems.append(f"SHOULD HAVE FAILED: {name}")
            else:
                good += 1
        elif result != "success":
            problems.append(f"FAILED: {name} ({result})")
        else:
            good += 1
    return good


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
        real = {k: v for k, v in done.items() if not k.startswith("loading ")}
        if not real or any(v != "success" for v in real.values()):
            problems.append("device tour failed: " + (p.stdout + p.stderr)[-500:])
        else:
            print(f"device tour passed on temporary simulator: {list(real)}")
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
    n = check(done, problems)
    berlin, _ = flutter_test(project, "test/time_test.dart", "test/time_dst_bug_test.dart", env={"TZ": "Europe/Berlin"})
    n += check(berlin, problems)
    if not done or not berlin:
        problems.append("no tests ran: " + (p.stdout + p.stderr)[-600:])
    if "--device" in sys.argv:
        device_tour(project, problems)
    print(f"{n} results as expected · {len(problems)} problems")
    for x in problems:
        print(" ", x)
    print("PROOF-OK" if not problems else "PROOF-FAILED")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
