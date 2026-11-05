#!/usr/bin/env python3
"""Can bad input break a scan? Standard library only.

Every scanner runs on projects full of damaged and odd files. Each must finish in time, exit cleanly and print
valid JSON. A finding's content is not judged here, only that the scan survives and says what it could not read.

    python3 -B tests/stress/run.py [--only SR]
"""
import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tests", "detection"))
sys.dont_write_bytecode = True
import cases as C  # noqa: E402
from run import SCRIPTS  # noqa: E402

for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

LIMIT = 60
GARBAGE = bytes(range(256)) * 64


def base(kind):
    return C.swift() if kind == "swift" else C.flutter()


HOSTILE = {
    "binary source files": {"Acme/Bin.swift": GARBAGE, "lib/bin.dart": GARBAGE, "src/bin.tsx": GARBAGE},
    "invalid utf-8 in strings": {"Acme/en.lproj/Localizable.strings": b'"a" = "\xff\xfe\xfa";\n', "lib/l10n/app_en.arb": b'{"a": "\xff"}'},
    "empty files everywhere": {"Acme/Empty.swift": b"", "Acme/en.lproj/Localizable.strings": b"", "lib/l10n/app_en.arb": b"", "Podfile": b"", "package.json": b""},
    "damaged json": {"package.json": b'{ "dependencies": ', "capacitor.config.json": b"[1,2", "app.json": b"null", "lib/l10n/app_en.arb": b"[]", "Acme/Assets.xcassets/AppIcon.appiconset/Contents.json": b"{ nope"},
    "json of unexpected shape": {"package.json": b'{"dependencies": 5, "scripts": null}', "app.json": b'{"expo": "x"}', "Acme/Assets.xcassets/AppIcon.appiconset/Contents.json": b'{"images": [1, null, {"size": 5, "filename": 7}]}', "Acme/L.xcstrings": b'{"strings": {"a": 1, "b": {"localizations": 3}}}', "Acme/Products.storekit": b'{"products": 5, "subscriptionGroups": [null]}'},
    "damaged plists": {"Acme/Info.plist": b"<plist><dict><key>a", "Acme/PrivacyInfo.xcprivacy": b"not xml", "Acme/Acme.entitlements": GARBAGE},
    "plist of unexpected shape": {"Acme/Info.plist": b'<?xml version="1.0"?><plist version="1.0"><array><string>x</string></array></plist>', "Acme/PrivacyInfo.xcprivacy": b'<?xml version="1.0"?><plist version="1.0"><dict><key>NSPrivacyAccessedAPITypes</key><string>x</string><key>NSPrivacyCollectedDataTypes</key><integer>3</integer></dict></plist>'},
    "plist values of the wrong type": {"Acme/Info.plist": (C.PLIST % "<key>UIBackgroundModes</key><string>audio</string><key>NSAppTransportSecurity</key><string>x</string><key>NSCameraUsageDescription</key><integer>3</integer><key>CFBundleDisplayName</key><array/>").encode()},
    "damaged project file": {"Acme.xcodeproj/project.pbxproj": b"isa = XCBuildConfiguration; buildSettings = { { { IPHONEOS_DEPLOYMENT_TARGET = ;"},
    "damaged images": {"Acme/Assets.xcassets/AppIcon.appiconset/icon.png": b"\x89PNG\r\n\x1a\nbroken", "Acme/a.png": b""},
    "very long line": {"Acme/Long.swift": b"let a = \"" + b"x" * 3_000_000 + b"\"\n", "Acme/en.lproj/Localizable.strings": b'"a" = "' + b"y" * 2_000_000 + b'";\n'},
    "regex-heavy text": {"Acme/R.swift": b"Button(" * 40000, "lib/r.dart": b"Text('" + b"a'" * 40000, "src/r.tsx": b"<Pressable " * 40000, "Acme/D.swift": b"{" * 200000},
    "many small files": {f"Acme/F{i}.swift": b"import SwiftUI\n" for i in range(1500)},
    "bom and crlf": {"Acme/B.swift": b"\xef\xbb\xbfimport SwiftUI\r\nlet a = 1\r\n", "Acme/en.lproj/Localizable.strings": "﻿\"a\" = \"b\";\r\n".encode("utf-16"), "Podfile": b"\xef\xbb\xbfplatform :ios, '12.0'\r\n"},
    "odd names": {"Acme/ş p a c e &$ (1).swift": b"let a = 1\n", "Acme/日本語/テスト.swift": b"let a = 1\n", "Acme/'quote\".swift": b"let a = 1\n", "-rf.swift": b"let a = 1\n", "Acme/--json.swift": b"let a = 1\n"},
    "suppression file damaged": {".apptest/profile.md": GARBAGE, ".apptest/x": b""},
    "suppression file odd": {".apptest/profile.md": b"## Suppressed\n- \n- ***\n- ((( \n- SR-* \n- [ -- \n"},
}


def add_special(root, name):
    """Things that can't be plain file writes."""
    os.makedirs(os.path.join(root, "Acme"), exist_ok=True)
    if name == "folders named like files":
        for rel in ("Acme/Secret/Info.plist/x", "Podfile/x", "package.json/x", "Acme/Bad.swift/x", "pubspec.lock/x"):
            os.makedirs(os.path.join(root, rel), exist_ok=True)
    elif name == "links":
        os.symlink(root, os.path.join(root, "Acme", "loop"))
        os.symlink(os.path.join(root, "gone"), os.path.join(root, "Acme", "Dead.swift"))
        os.symlink("/dev/zero", os.path.join(root, "Acme", "Zero.swift"))
    elif name == "named pipe":
        os.mkfifo(os.path.join(root, "Acme", "Pipe.swift"))
        os.mkfifo(os.path.join(root, "package.json"))
    elif name == "unreadable files":
        for rel in ("Acme/Locked.swift", "Acme/en.lproj/Localizable.strings", "Podfile"):
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as fh:
                fh.write("let a = 1\n")
            os.chmod(p, 0)
        d = os.path.join(root, "Acme", "LockedDir")
        os.makedirs(d)
        os.chmod(d, 0)
    elif name == "very deep folders":
        p = root
        for _ in range(60):
            p = os.path.join(p, "d")
        os.makedirs(p, exist_ok=True)
        with open(os.path.join(p, "Deep.swift"), "w") as fh:
            fh.write("let a = 1\n")


SPECIAL = ["folders named like files"] + ([] if os.name == "nt" else ["links", "named pipe", "unreadable files", "very deep folders"])


def write(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(body if isinstance(body, bytes) else body.encode("utf-8"))


def scan(code, root):
    script = os.path.join(ROOT, "skills", SCRIPTS[code])
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, "-I", "-X", "utf8", script, root, "--json"], capture_output=True, timeout=LIMIT)
    except subprocess.TimeoutExpired:
        return f"hung for over {LIMIT} s"
    out = r.stdout.decode("utf-8", "replace")
    err = r.stderr.decode("utf-8", "replace")
    if "Traceback" in err or r.returncode not in (0, 2):
        tail = [x for x in err.strip().splitlines() if x.strip()]
        where = [x.strip() for x in tail if x.strip().startswith('File "')][-1:] or [""]
        return f"crashed (exit {r.returncode}): {tail[-1][:120] if tail else ''} {where[0][-70:]}"
    try:
        json.loads(out)
    except ValueError:
        if not out.strip().startswith("Not applicable"):
            return f"not JSON: {out[:90]!r}"
    if time.time() - t0 > LIMIT / 2:
        return f"slow: {time.time() - t0:.0f} s"
    return None


def clean_up(path):
    for base_dir, dirs, files in os.walk(path):
        for n in dirs + files:
            p = os.path.join(base_dir, n)
            if not os.path.islink(p):
                try:
                    os.chmod(p, stat.S_IRWXU)
                except OSError:
                    pass
    shutil.rmtree(path, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--scenario", help="run only scenarios whose name contains this")
    a = ap.parse_args()
    problems, runs = [], 0
    codes = [c for c in SCRIPTS if not a.only or c == a.only]
    work = tempfile.mkdtemp(prefix="stress-")
    try:
        names = [n for n in list(HOSTILE) + SPECIAL if not a.scenario or a.scenario in n]
        for kind in ("swift", "flutter"):
            for name in names:
                root = os.path.join(work, f"{kind}-{names.index(name)}")
                os.makedirs(root)
                write(root, {**base(kind), **HOSTILE.get(name, {})})
                if name in SPECIAL:
                    if name == "named pipe" and os.path.exists(os.path.join(root, "package.json")):
                        os.remove(os.path.join(root, "package.json"))
                    if name == "folders named like files":
                        for rel in ("Podfile", "package.json"):
                            p = os.path.join(root, rel)
                            if os.path.isfile(p):
                                os.remove(p)
                    add_special(root, name)
                for code in codes:
                    if code == "SA":
                        continue
                    runs += 1
                    r = scan(code, root)
                    if r:
                        problems.append(f"{kind} / {name} / {code}: {r}")
                        print("  found:", problems[-1], flush=True)
                clean_up(root)
        # The text inventory reads every translation file, in formats of its own.
        root = os.path.join(work, "inventory")
        os.makedirs(root)
        write(root, {**base("flutter"), "lib/l10n/app_en.arb": b"[]", "lib/l10n/app_de.arb": GARBAGE, "Acme/en.lproj/Localizable.strings": GARBAGE,
                     "public/locales/en/common.json": b'{"a": {"b": 5}, "c": null, "d": [1]}', "public/locales/de/common.json": b"{ nope",
                     "android/res/values/strings.xml": b"<resources><string", "po/en.po": GARBAGE, "Acme/L.xcstrings": b'{"strings": {"a": 1, "b": {"localizations": 3}}}',
                     "config/locales/en.yml": b"a: [", "Acme/x.stringsdict": GARBAGE})
        out = os.path.join(work, "inventory-out")
        r = subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(ROOT, "skills/apptest-copy-audit/scripts/copy_inventory.py"), root, "--out", out], capture_output=True, timeout=LIMIT)
        runs += 1
        if b"Traceback" in r.stderr:
            problems.append("text inventory: crashed: " + r.stderr.decode("utf-8", "replace").strip().splitlines()[-1][:120])
        clean_up(root)
        # The image folder scanner, and the combined run.
        for name, files in (("damaged images", {"en/a.png": b"\x89PNG\r\n\x1a\nbroken", "en/b.png": b"", "en/c.jpg": GARBAGE, "en/d.mov": b"", "en/e/f.png": C.png(1, 1)}),
                            ("no images", {"en/a.txt": b"x"})):
            root = os.path.join(work, "sa")
            os.makedirs(root)
            write(root, files)
            if not a.only or a.only == "SA":
                runs += 1
                r = scan("SA", root)
                if r:
                    problems.append(f"store assets / {name}: {r}")
            clean_up(root)
    finally:
        clean_up(work)
    print(f"{runs} runs, {len(problems)} problems")
    seen = {}
    for p in problems:
        key = p.split(": ", 1)[-1][:90]
        seen.setdefault(key, []).append(p.split(": ", 1)[0])
    for key, where in seen.items():
        print(f"  {len(where)}× {key}\n     e.g. {where[0]}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
