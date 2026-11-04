#!/usr/bin/env python3
"""apple-design-audit — candidates for places in an existing app that DIFFER from the HIG. Looks only at things
visible in code that have a counterpart in the HIG; does not judge "is it pretty" (screens use the manual steps in SKILL.md).
Each item names its HIG page; for the text: hig.py read <slug>.

Severities are SUGGESTION / INFO only: the HIG is guidance, not a rejection reason. Rejection reasons live in the apptest family.
Standard library only (Python 3.8+); does NOT write to the project.

    python3 -I hig_scan.py <project_root> [--json]
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

WEB = "https://developer.apple.com/design/human-interface-guidelines/"

MATERIAL = r"\b(FloatingActionButton|BottomNavigationBar|NavigationDrawer|Drawer|SnackBar|AlertDialog|ElevatedButton|" \
           r"BottomSheet|PopupMenuButton|DropdownButton)\s*\("
CUPERTINO = r"\bCupertino\w+\s*\(|\.adaptive\s*\("
RN_MATERIAL = r"react-native-paper|@react-navigation/material|createDrawerNavigator|@react-navigation/drawer|" \
              r"react-native-elements|@rneui"
ANDROID_NAV = r"\bFloatingActionButton\s*\(|\bDrawer\s*\(|NavigationDrawer\s*\(|createDrawerNavigator|<FAB\b|\bFAB\s*\("
TOAST = r"\bSnackBar\s*\(|\bFluttertoast\b|\bshowToast\s*\(|\bToast\.(show|makeText)\b|react-native-toast"
TAB_ITEM = {
    "dart": r"\b(BottomNavigationBarItem|NavigationDestination|CupertinoTabBar)\s*\(",
    "swift": r"\.tabItem\s*\{|\bTab\s*\(\s*\"",
    "js": r"<Tab\.Screen\b|<Tabs\.Screen\b",  # <HomeTab.Screen> is not a tab, it is a stack screen inside a tab (e.g. Bluesky)
}
SYSTEM_GESTURE = r"interactivePopGestureRecognizer\??\.isEnabled\s*=\s*false|\bgestureEnabled\s*:\s*false|" \
                 r"\.interactiveDismissDisabled\(\s*(true)?\s*\)|isModalInPresentation\s*=\s*true|" \
                 r"\bcanPop\s*:\s*false|\bisDismissible\s*:\s*false|\benableDrag\s*:\s*false"
OK_BUTTON = r"""Button\(\s*"(OK|Ok)"|\btext\s*:\s*['"](OK|Ok)['"]|\bText\(\s*['"](OK|Ok)['"]\s*\)|title\s*:\s*"(OK|Ok)"\s*,\s*style"""
MATERIAL_ICON = r"\bIcons\.\w+|MaterialIcons|MaterialCommunityIcons"
APPLE_ICON = r"\bCupertinoIcons\.\w+|systemName\s*:|\bSF[A-Z]\w*Symbol|sf-symbols|react-native-sfsymbols|expo-symbols"


def scan_project(root: str, as_json: bool):
    p = scan.load_profile(root)
    if scan.guard_unknown(p, allow_mac=True):
        return 0
    flags = p.mod.summary_flags(p)
    rep = scan.Report("DS", p, "apple-design-audit — places that differ from the HIG")
    files = scan.code_files(p)
    deps = "\n".join(scan.p_read(f) for f in p.files if os.path.basename(f) == "package.json"
                     and "/node_modules/" not in f and p.mod.ios_path(f))
    device = ["Mac"] if scan.mac_only(p) else (flags.get("platforms") or ["iPhone"])
    pages = ["design-principles"] + [{"iPhone": "designing-for-ios", "iPad": "designing-for-ipados",
                                      "Mac": "designing-for-macos"}.get(d, "") for d in device]
    rep.add("DS-09", "INFO", "HIG pages to read first", ", ".join(x for x in pages if x),
            f"Target: {', '.join(device)}. Only these platforms' rules apply. To read: hig.py read <slug>.")
    if p.mod.ios_project_missing(p):
        rep.add("DS-09", "INFO", "No iOS project yet", "—", "Code-level items still apply; the screen audit comes once it runs on iOS.")

    dart = [f for f in files if scan.lang_of(f) == "dart"]
    if dart:
        mc, mfirst = scan.count(p, MATERIAL, files=dart)
        cc, _ = scan.count(p, CUPERTINO, files=dart)
        # The ratio looks only at components that determine appearance (the Scaffold skeleton does not count).
        if mc and mc > cc * 2:
            rep.add("DS-10", "SUGGESTION", f"Flutter UI is heavily Material ({mc} Material, {cc} Cupertino / adaptive)",
                    f"{p.rel(mfirst[0])}:{mfirst[1]}", f"Some of these components do not carry the system look on iOS (alert, menu, picker); check by hand. "
                    f"Page transitions and swipe back are tried separately; this count does not show them. If a custom design language is deliberate, this is not a difference. "
                    f"See {WEB}design-principles")
    rn = re.search(RN_MATERIAL, deps)
    if rn:
        rep.add("DS-10", "SUGGESTION", f"Material library in React Native: {rn.group(0)}", "package.json",
                f"Components may not carry iOS system behaviour. See {WEB}design-principles")

    nc, nfirst = scan.count(p, ANDROID_NAV, files=files)
    if nc:
        rep.add("DS-11", "SUGGESTION", f"Pattern with no counterpart in the HIG: floating action button / side drawer ({nc} places)",
                f"{p.rel(nfirst[0])}:{nfirst[1]}", f"The HIG does not define these patterns; on iOS top-level navigation is a tab bar or "
                f"sidebar, and actions live in the toolbar. See {WEB}tab-bars · {WEB}toolbars")

    tc, tfirst = scan.count(p, TOAST, files=files)
    if tc:
        rep.add("DS-12", "INFO", f"Short message (toast / snackbar) in {tc} places", f"{p.rel(tfirst[0])}:{tfirst[1]}",
                f"The HIG has no such component; it says 'use system patterns for feedback'. A vanishing message can be missed in "
                f"VoiceOver: if it matters, try by hand. See {WEB}design-principles")

    for lg, pat in TAB_ITEM.items():
        for f in [x for x in files if scan.lang_of(x) == lg]:
            hits = [n for n, line in scan.lines(f) if re.search(pat, line)]
            if len(hits) >= 6:
                # In a custom bar, not all defined screens may be visible (e.g. Bluesky defines 10 screens, shows fewer).
                if lg == "js" and re.search(r"\btabBar\s*=\s*\{", scan.p_read(f)):
                    rep.add("DS-13", "INFO", f"Custom tab bar, {len(hits)} screens defined: the visible tab count cannot be read from code",
                            f"{p.rel(f)}:{hits[0]}", f"Count on screen. See {WEB}tab-bars")
                    continue
                rep.add("DS-13", "SUGGESTION", f"{len(hits)} tabs on one screen", f"{p.rel(f)}:{hits[0]}",
                        f"The HIG gives no fixed number but says to avoid overflow: a tab that does not fit falls into 'More' on iOS. "
                        f"See {WEB}tab-bars")

    for f, n, line, m in scan.grep(p, SYSTEM_GESTURE, files=files, max_hits=30):
        rep.add("DS-14", "INFO", "System back / dismiss gesture disabled", f"{p.rel(f)}:{n} `{m.group(0)[:44]}`",
                f"It may have a reason such as unsaved changes; otherwise the user does not find the gesture they expect. "
                f"See {WEB}gestures · {WEB}sheets")

    oc, ofirst = scan.count(p, OK_BUTTON, files=files)
    if oc:
        rep.add("DS-15", "SUGGESTION", f"Alert button 'OK' ({oc} places)", f"{p.rel(ofirst[0])}:{ofirst[1]}",
                f"HIG: OK only in a purely informational alert; elsewhere a verb that says the result. See {WEB}alerts")

    mi, mifirst = scan.count(p, MATERIAL_ICON, files=files)
    ai, _ = scan.count(p, APPLE_ICON, files=files)
    if mi >= 5 and mi > ai * 2:
        rep.add("DS-16", "SUGGESTION", f"Icons are heavily Material ({mi} Material, {ai} SF Symbols / Cupertino)",
                f"{p.rel(mifirst[0])}:{mifirst[1]}", f"If your own icon language is deliberate, this is not a difference; SF Symbols scale with text, and weight "
                f"and accessibility matching come ready-made. See {WEB}sf-symbols")
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
