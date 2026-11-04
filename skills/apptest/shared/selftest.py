#!/usr/bin/env python3
"""apptest family self-test: do the scripts work on this OS and Python version?
Builds sample projects in a temporary folder whose name has spaces and non-ASCII letters, then runs every scan; the
same result is expected on Mac, Linux and Windows. Needs no simulator or Xcode; without internet, online checks must say "could not check".

    python3 -I selftest.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SHARED = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(os.path.dirname(SHARED))
fails: list[str] = []


def write(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict><key>CFBundleDisplayName</key><string>Örnek</string></dict></plist>
"""


def flutter(root):
    write(root, "pubspec.yaml", "name: sample\ndependencies:\n  flutter:\n    sdk: flutter\n")
    write(root, "ios/Runner/Info.plist", PLIST)
    write(root, "ios/Runner.xcodeproj/project.pbxproj", 'productType = "com.apple.product-type.application";\n')
    write(root, "lib/main.dart", "import 'package:flutter/material.dart';\n"
                                 "final a = [Icons.add, Icons.home, Icons.star, Icons.menu, Icons.close];\n"
                                 "final b = Text('İşlem tamamlandı ₺12,50');\n"
                                 "final c = double.parse('12,5');\n")


def swift(root):
    write(root, "Demo.xcodeproj/project.pbxproj", 'SDKROOT = iphoneos;\nproductType = "com.apple.product-type.application";\n'
                                                  "INFOPLIST_FILE = Demo/Info.plist;\n")
    write(root, "Demo/Info.plist", PLIST)
    write(root, "Demo/App.swift", 'import SwiftUI\nimport AVFoundation\nstruct A: View { var body: some View { Text("x") } }\n'
                                  "let s = AVCaptureSession()\n")


def rn(root):
    write(root, "package.json", '{"name":"sample","dependencies":{"react-native":"0.76.0"}}')
    write(root, "ios/Sample/Info.plist", PLIST)
    write(root, "ios/Sample.xcodeproj/project.pbxproj", 'productType = "com.apple.product-type.application";\n')
    write(root, "src/App.tsx", "import {Text} from 'react-native';\nexport default () => <Text>Merhaba</Text>;\n")


def mac(root):
    write(root, "M.xcodeproj/project.pbxproj", "SDKROOT = macosx;\n")
    write(root, "M/App.swift", "import AppKit\n")


def run(*cmd):
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", *cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    return r.returncode, r.stdout, r.stderr


def check(cond, name):
    print(("  passed: " if cond else "  FAILED: ") + name)
    if not cond:
        fails.append(name)


def main():
    print(f"Python {sys.version.split()[0]} · {sys.platform}")
    base = tempfile.mkdtemp(prefix="apptest self-test ığüşçö ")
    run_all = os.path.join(SHARED, "run_all.py")
    hig_scan = os.path.join(SKILLS, "apple-design-audit", "scripts", "hig_scan.py")
    try:
        for name, build, want in (("Flutter", flutter, "Flutter"), ("SwiftUI", swift, "Native iOS"), ("React Native", rn, "React Native")):
            root = os.path.join(base, name)
            os.makedirs(root)
            build(root)
            print(name)
            code, out, err = run(run_all, root, "--json")
            check(code == 0 and "Traceback" not in err, f"{name}: combined scan ran (exit {code})")
            try:
                data = json.loads(out)
            except ValueError:
                data = None
            check(data is not None, f"{name}: JSON output is readable")
            if os.sep == "\\":
                check("\\" not in json.dumps(data or {}).replace("\\\\", "/").replace("\\u", "") , f"{name}: paths use '/'")
            members = (data or {}).get("members") or {}
            broken = [k for k, v in members.items() if v.get("error") and not str(v["error"]).startswith("Not applicable")]
            check(bool(members) and not broken, f"{name}: no member errors {broken or ''}")
            check(any(l.startswith("Technology") and want in l for l in run(hig_scan, root)[1].splitlines()), f"{name}: technology {want}")
        print("Honest statuses")
        root = os.path.join(base, "Mac")
        os.makedirs(root)
        mac(root)
        check("Not applicable" in run(run_all, root)[1], "Mac-only project says 'Not applicable'")
        check("designing-for-macos" in run(hig_scan, root)[1], "Design scan suggests the Mac page")
        check(run(run_all, os.path.join(base, "missing"))[0] == 2, "Missing folder gives exit 2")
        print("Tools")
        for script in (("apptest-visual", "vi_diff.py"), ("apptest-network-chaos", "nc_proxy.py")):
            code, out, err = run(os.path.join(SKILLS, script[0], "scripts", script[1]), "--self-test")
            check(code == 0, f"{script[1]} self-test (exit {code}) {err[-200:] if code else ''}")
        code, out, err = run(os.path.join(SKILLS, "apple-design-audit", "scripts", "hig.py"), "read", "../broken")
        check(code != 0 and "Traceback" not in err, "hig.py rejects a bad name")
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print(f"\n{'FAILED: ' + str(len(fails)) if fails else 'All passed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
