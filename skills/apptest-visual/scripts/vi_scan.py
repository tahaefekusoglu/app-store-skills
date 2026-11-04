#!/usr/bin/env python3
"""apptest-visual — visual comparison infrastructure and matrix: existing image (golden / snapshot)
tests, size of baselines committed to the repo, hooks that pin the image (animation, clock,
status bar), theme / language / text / device matrix suggestion.

Standard library only (Python 3.8+); does NOT write to the project.

    python3 -I vi_scan.py <project_root> [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys

_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apptest", "shared", "scanlib.py")
_s = importlib.util.spec_from_file_location("apptest_scanlib", _p)
scan = importlib.util.module_from_spec(_s)
_s.loader.exec_module(scan)

# Tests that compare (verify against a baseline image).
GOLDEN = r"matchesGoldenFile\(|screenMatchesGolden\(|multiScreenGolden\(|goldenTest\(|assertSnapshot\(|" \
         r"verifySnapshot\(|FBSnapshotVerify\w*\(|iOSSnapshotTestCase|toMatchImageSnapshot\(|assertScreenshot\b"
# Code that only CAPTURES (does not compare): store images, tour evidence.
CAPTURE = r"takeScreenshot\s*[:(]|- takeScreenshot|captureScreen\(|XCTAttachment\(screenshot|\.screenshot\(\)|" \
          r"snapshot\(\s*[\"']|simctl\s+io\s+\S+\s+screenshot"
STABLE = {
    "animation disabling": r"setAnimationsEnabled\(\s*false|UIView\.setAnimationsEnabled|timeDilation\s*=|"
                        r"disableAnimations|-UIAnimationDragCoefficient|reduceMotion|\.transaction\s*\{\s*\$0\.disablesAnimations|"
                        r"TickerMode\(\s*enabled\s*:\s*false|jest\.useFakeTimers|Animated\.timing.*duration\s*:\s*0",
    "status bar pinning": r"status_bar\s+\S+\s+override|SimulatorStatusMagic|statusBarOverride|override_status_bar|"
                              r"--time\s+[\"']?9:41",
    "clock pinning": r"\bclockProvider\b|withClock|Clock\.fixed|\bMockDate\b|jest\.useFakeTimers|setSystemTime\(|"
                      r"@Dependency\(\\\.date\)|\bnowProvider\b|\bDateProvider\b",
    "font loading (Flutter golden)": r"loadAppFonts\(|loadFonts\(|FontLoader\(",
}
GOLDEN_DIR = re.compile(r"(?i)/(goldens?|__snapshots__|__image_snapshots__|__Snapshots__|ReferenceImages\w*|snapshots?)/")
FIXED_STYLE = re.compile(r"<key>UIUserInterfaceStyle</key>\s*<string>(Light|Dark)</string>")
CI_LINUX = re.compile(r"runs-on:\s*\[?\s*['\"]?ubuntu|image:\s*['\"]?(ubuntu|debian|cirrusci/flutter|ghcr\.io/cirruslabs/flutter)")


LONG = ("de", "fi", "ru", "pl", "nl", "hu", "el", "uk", "fr", "pt", "es", "it", "tr")
RTL = ("ar", "he", "fa", "ur")
CJK = ("ja", "zh", "ko")


def pick_langs(langs):
    """Representative languages: development language, a long-text language, a right-to-left language, a CJK
    language (font). The rest only on a full tour or on changed screens (VI-P3)."""
    if len(langs) <= 4:
        return list(langs)
    base = "en" if "en" in langs else langs[0]
    out = [base]
    for group in (LONG, RTL, CJK):
        hit = next((x for x in group if x in langs and x not in out), None)
        if hit:
            out.append(hit)
    return out


def scan_project(root: str, as_json: bool):
    p = scan.load_profile(root)
    if scan.guard_unknown(p):
        return 0
    flags = p.mod.summary_flags(p)
    rep = scan.Report("VI", p, "visual — visual comparison infrastructure and matrix")
    everything = scan.code_files(p, include_tests=True)
    tests = [f for f in everything if scan.TEST_PATH.search("/" + p.rel(f))]

    sh = [f for f in p.files if f.endswith((".sh", ".yml", ".yaml", ".rb", ".py", "Fastfile", "Snapfile"))
          and p.mod.ios_path(f) and "/node_modules/" not in f]
    gc, gfirst = scan.count(p, GOLDEN, files=tests)
    cc, cfirst = scan.count(p, CAPTURE, files=tests + sh)
    if gc:
        rep.add("VI-10", "INFO", f"Image comparison (golden / snapshot) test present ({gc} places)",
                f"{p.rel(gfirst[0])}:{gfirst[1]}", "Use this first: running the matrix from here is cheaper than vi_diff.")
    else:
        rep.add("VI-10", "INFO", "No image comparison test found", "—",
                "Done with a simulator tour + vi_diff.py (references/stabilize.md).")
    if cc:
        rep.add("VI-10", "INFO", f"Code that CAPTURES screenshots present ({cc} places; does not compare)",
                f"{p.rel(cfirst[0])}:{cfirst[1]}", "These captures can be given to vi_diff as the base / new set.")

    # VI-11: size of baselines in the repo (VI-P1).
    total, count, biggest = 0, 0, None
    for f in p.files:
        rel = "/" + p.rel(f)
        if f.lower().endswith(".png") and GOLDEN_DIR.search(rel):
            try:
                sz = os.path.getsize(f)
            except OSError:
                continue
            total += sz
            count += 1
            if not biggest or sz > biggest[1]:
                biggest = (p.rel(f), sz)
    if count and not gc:
        rep.add("VI-11", "SUGGESTION", f"{count} baselines ({total / 1_048_576:.1f} MB) in the repo, no comparison "
                "test using them was found", biggest[0] if biggest else "—",
                "They may be orphaned (test deleted): if unused, removing them from the repo shrinks clones. "
                "Before deleting, check whether test targets and schemes mention them.")
    elif count:
        mb = total / 1_048_576
        sev = "SUGGESTION" if mb >= 50 else "INFO"
        rep.add("VI-11", sev, f"{count} baselines in the repo, {mb:.1f} MB", biggest[0] if biggest else "—",
                "Over 50 MB slows the repo and every clone; consider Git LFS or storing outside the repo (VI-P1)."
                if sev == "SUGGESTION" else "New baselines are kept OUTSIDE the project; into the repo only with permission.")

    # VI-12: pinning hooks (VI-P2).
    for name, pat in STABLE.items():
        if name.startswith("font") and not ("Flutter" in scan.techs(p) and gc):
            continue
        # The clock hook lives in app code; animation / status bar pinning means something only in tests and scripts
        # (temporarily disabling animation in app code is not pinning).
        c, first = scan.count(p, pat, files=(everything if name == "clock pinning" else tests) + sh)
        if c:
            rep.add("VI-12", "INFO", f"Pinning present: {name} ({c} places)", f"{p.rel(first[0])}:{first[1]}", "")
        else:
            note = {"animation disabling": "A frame captured mid-animation differs on every tour.",
                    "status bar pinning": "Time / battery differ on every tour: `xcrun simctl status_bar <UDID> override "
                                          "--time 9:41 …` or a top mask (vi_diff --mask-top).",
                    "clock pinning": "If the screen shows a date / 'N days left', the image differs every day.",
                    "font loading (Flutter golden)": "A Flutter golden test draws square letters with the default test "
                                                     "font; the real font must be loaded."}[name]
            rep.add("VI-12", "INFO", f"Pinning not found: {name}", "—", note)

    # VI-13: Flutter golden + Linux CI → font / antialiasing difference.
    if gc and "Flutter" in scan.techs(p):
        for f in p.files:
            rel = p.rel(f)
            if rel.startswith((".github/workflows/", ".gitlab-ci", "codemagic", "bitrise", ".circleci/")) and \
                    f.endswith((".yml", ".yaml")):
                text = scan.p_read(f)
                if CI_LINUX.search(text) and "flutter test" in text:
                    rep.add("VI-13", "SUGGESTION", "Image tests also run on Linux CI", rel,
                            "A baseline produced on a Mac draws text edges differently on Linux: produce baselines on the "
                            "platform the test runs on, or use a tag to keep golden tests on one platform.")
                    break

    # Matrix suggestion.
    all_langs = flags.get("languages") or []
    langs = pick_langs(all_langs)
    fixed = None
    for f in p.files:
        if f.endswith("Info.plist") and p.mod.ios_path(f):
            m = FIXED_STYLE.search(scan.p_read(f))
            if m:
                fixed = m.group(1)
                break
    looks = [fixed] if fixed else ["light", "dark"]
    devices = ["smallest iPhone (e.g. iPhone SE 3rd generation)", "largest iPhone (Pro Max)"]
    if "iPad" in (flags.get("platforms") or []):
        devices.append("iPad 13\"")
    sizes = ["default text", "largest accessibility text"]
    n = max(1, len(langs)) * len(looks) * len(devices) * len(sizes)
    rep.add("VI-14", "INFO", f"Matrix: {max(1, len(langs))} languages × {len(looks)} appearances × {len(devices)} devices × "
            f"{len(sizes)} text sizes = {n} captures / screen",
            f"languages: {', '.join(langs) or 'one'}{f' (representative; of {len(all_langs)} languages)' if len(all_langs) > len(langs) else ''} · appearance: {', '.join(looks)} · devices: {'; '.join(devices)}",
            "Quick tour: development language × two appearances × large iPhone; full tour before release. If the app has "
            "its own themes, use the theme count instead of appearances.")
    rep.emit(as_json)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    return scan_project(os.path.abspath(a.root), a.json)


if __name__ == "__main__":
    sys.exit(main())
