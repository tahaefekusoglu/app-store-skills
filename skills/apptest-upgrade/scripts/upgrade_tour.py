#!/usr/bin/env python3
"""apptest-upgrade — tour that installs the new version OVER the old one (simulator).

Installs and launches the old .app, enters FULL data (by hand or with --seed),
snapshots the app container, installs the new .app OVER it (the container is
kept), launches it, lists the container again and runs --verify if given.
Never uses the user's simulator: run sim_session.py create first.

    python3 -I upgrade_tour.py --udid <UDID> --bundle <bundle_id> --old <old.app> --new <new.app>
                               [--seed "<command>"] [--verify "<command>"] [--wait <sec>]

--seed / --verify receive the environment variables APPTEST_UDID,
APPTEST_BUNDLE, APPTEST_CONTAINER (path of the data container). Without --seed
the script pauses for the user to enter data by hand (Enter). The data is demo
data and lives only in the temporary simulator (DI-P1).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

# Non-ASCII characters must not crash output on a non-UTF-8 Windows console (any OS).
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def sh(*args, check=True):
    r = subprocess.run(list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(args)}\n{r.stderr.strip()}")
    return r.stdout.strip()


def container(udid, bundle):
    return sh("xcrun", "simctl", "get_app_container", udid, bundle, "data", check=False)


# Places iOS itself regenerates or may delete: not user data.
TRANSIENT = ("Library/SplashBoard/", "Library/Caches/", "tmp/", "Library/Saved Application State/",
             "Library/Cookies/", "Library/WebKit/", "SystemData/", ".com.apple.mobile_container_manager")


def listing(path):
    """({relative file: size}, [what could not be read]). A folder that cannot be read is not an empty one."""
    out, unread = {}, []
    if not path or not os.path.isdir(path):
        return out, [path or "(no container path)"]
    for d, _dirs, files in os.walk(path, onerror=lambda e: unread.append(str(e.filename))):
        for f in files:
            p = os.path.join(d, f)
            if os.path.relpath(p, path).startswith(TRANSIENT):
                continue
            try:
                out[os.path.relpath(p, path)] = os.path.getsize(p)
            except OSError:
                unread.append(p)
    return out, unread


def could_not_check(why):
    print(f"\n## upgrade tour\n- could not check: {why}")
    return 3


def version_of(app):
    try:
        import plistlib
        pl = plistlib.load(open(os.path.join(app, "Info.plist"), "rb"))
        return f"{pl.get('CFBundleShortVersionString')} ({pl.get('CFBundleVersion')})"
    except Exception:  # noqa: BLE001
        return "?"


def run_hook(cmd, env):
    if not cmd:
        return True
    r = subprocess.run(cmd, shell=True, env={**os.environ, **env})
    return r.returncode == 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--udid", required=True)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--seed")
    ap.add_argument("--verify")
    ap.add_argument("--wait", type=int, default=8)
    a = ap.parse_args(argv)
    for app in (a.old, a.new):
        if not os.path.isdir(app) or not app.endswith(".app"):
            raise SystemExit(f"not an .app folder: {app}")
    print(f"old: {version_of(a.old)} → new: {version_of(a.new)}")
    sh("xcrun", "simctl", "uninstall", a.udid, a.bundle, check=False)
    sh("xcrun", "simctl", "install", a.udid, a.old)
    sh("xcrun", "simctl", "launch", a.udid, a.bundle)
    time.sleep(a.wait)
    env = {"APPTEST_UDID": a.udid, "APPTEST_BUNDLE": a.bundle, "APPTEST_CONTAINER": container(a.udid, a.bundle)}
    if a.seed:
        if not run_hook(a.seed, env):
            raise SystemExit("--seed command failed")
    else:
        input("Enter realistic, FULL demo data in the old version, then press Enter… ")
    sh("xcrun", "simctl", "terminate", a.udid, a.bundle, check=False)
    before, unread = listing(env["APPTEST_CONTAINER"])
    if unread:
        return could_not_check("cannot read the old version's data folder: " + ", ".join(unread[:5]))
    if not before:
        return could_not_check("no data files before the upgrade, so the tour would prove nothing: enter demo data first")
    sh("xcrun", "simctl", "install", a.udid, a.new)  # install over: the container is kept
    sh("xcrun", "simctl", "launch", a.udid, a.bundle)
    time.sleep(a.wait)
    running = sh("xcrun", "simctl", "spawn", a.udid, "launchctl", "list", check=False)
    alive = a.bundle in running
    after_path = container(a.udid, a.bundle)
    after, unread = listing(after_path)
    if unread:
        return could_not_check("cannot read the new version's data folder: " + ", ".join(unread[:5]))
    gone = sorted(set(before) - set(after))
    shrunk = sorted(k for k in before if k in after and after[k] < before[k] * 0.5 and before[k] > 4096)
    ok_verify = run_hook(a.verify, {**env, "APPTEST_CONTAINER": after_path}) if a.verify else None
    print("\n## upgrade tour")
    print(f"- running after launch: {'yes' if alive else 'NO (may have crashed; check the crash log)'}")
    print(f"- files in container: before {len(before)} → after {len(after)}")
    if gone:
        print(f"- files GONE ({len(gone)}): " + ", ".join(gone[:10]))
    if shrunk:
        print(f"- files SHRUNK by more than half: " + ", ".join(shrunk[:10]))
    if ok_verify is not None:
        print(f"- verify command: {'passed' if ok_verify else 'FAILED'}")
    print("- by hand: does the old data look the same in the new version (counts, totals, latest record)?")
    return 0 if alive and not gone and ok_verify is not False else 1


if __name__ == "__main__":
    sys.exit(main())
