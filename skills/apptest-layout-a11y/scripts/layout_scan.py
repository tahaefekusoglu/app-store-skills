#!/usr/bin/env python3
"""apptest-layout-a11y: static scan (large text, unlabeled elements, tap
targets, keyboard, appearance, iPad, reduce motion).

Standard library only; does NOT write to the project. Output is CANDIDATES
(verify against the LA-xx ids in SKILL.md). The real evidence is the simulator
tour (SKILL.md "Test"): the static scan only shows where to look.

    python3 -I layout_scan.py <project_root> [--json]
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

# --- LA-10: large text (Dynamic Type) turned off / fixed font size
SCALE_OFF = [
    ("dart", r"textScaleFactor\s*:\s*1(\.0)?\b|TextScaler\.noScaling|TextScaler\.linear\(\s*1(\.0)?\s*\)|"
             r"withNoTextScaling|textScaler\s*:\s*const\s+TextScaler\.linear\(\s*1",
     "Text scale fixed in Flutter"),
    ("js", r"allowFontScaling\s*=\s*\{\s*false\s*\}|allowFontScaling\s*=\s*false|"
           r"maxFontSizeMultiplier\s*=\s*\{\s*1(\.0)?\s*\}",
     "Font scaling turned off in React Native"),
    ("swift", r"\.dynamicTypeSize\(\s*\.\.\.?\s*\.?(xSmall|small|medium|large|xLarge)\b|"
              r"\.dynamicTypeSize\(\s*\.(xSmall|small|medium|large|xLarge|xxLarge)\s*\)|"
              r"\\\.sizeCategory\s*,\s*\.|adjustsFontForContentSizeCategory\s*=\s*false",
     "Text size clamped to a small range in SwiftUI/UIKit"),
    ("xaml", r'FontAutoScalingEnabled\s*=\s*"False"', "Font scaling turned off in MAUI"),
    ("csharp", r"FontAutoScalingEnabled\s*=\s*false", "Font scaling turned off in MAUI"),
]
ROOT_FILE = re.compile(r"(?i)/(main\.dart|app\.dart|\w*App\.swift|AppDelegate\.(swift|m)|SceneDelegate\.swift|"
                       r"App\.(tsx|jsx|js|ts)|index\.(tsx|jsx|js|ts)|_layout\.tsx|MauiProgram\.cs|App\.xaml(\.cs)?)$")
SWIFT_FIXED_FONT = re.compile(r"\.font\(\s*\.system\(\s*size\s*:|Font\.system\(\s*size\s*:|"
                              r"\.font\(\s*\.custom\([^)]*size\s*:\s*[\d.]+\s*\)\s*\)")
SWIFT_RELATIVE = re.compile(r"relativeTo\s*:|@ScaledMetric|UIFontMetrics|scaledFont")
UIKIT_FIXED_FONT = re.compile(r"UIFont\.(systemFont|boldSystemFont|monospacedDigitSystemFont)\(\s*ofSize\s*:|"
                              r"UIFont\(\s*name\s*:[^)]*size\s*:")

# --- LA-20: unlabeled icon-only elements
FLUTTER_ICONBUTTON = re.compile(r"\bIconButton\s*\(")
RN_PRESSABLE = re.compile(r"<\s*(TouchableOpacity|TouchableHighlight|TouchableWithoutFeedback|Pressable)\b")

# --- LA-22: SwiftUI button whose whole label is a symbol. The body must hold nothing but the image.
SWIFT_ICON_BUTTON = re.compile(r"\bButton\s*(?:\([^()]*(?:\([^()]*\)[^()]*)*\))?\s*(?:label\s*:\s*)?\{\s*"
                               r"Image\(\s*systemName\s*:\s*\"[^\"]+\"\s*\)"
                               r"(?:\s*\.\w+(?:\([^(){}]*\))?)*\s*\}")
SWIFT_A11Y_LABEL = re.compile(r"accessibilityLabel|accessibility\(label")

# --- LA-30: small tap target
SMALL_TAP = [
    # Both dimensions must be below 44 (0 = "fit content", sets no limit).
    ("dart", r"MaterialTapTargetSize\.shrinkWrap|"
             r"minimumSize\s*:\s*(const\s+)?Size\(\s*([1-9]|[1-3]\d|4[0-3])(\.\d+)?\s*,\s*([1-9]|[1-3]\d|4[0-3])(\.\d+)?\s*\)",
     "Tap target shrunk in Flutter"),
    ("swift", r"Button[^\n]*\.frame\(\s*width\s*:\s*([1-9]|[1-3]\d|4[0-3])\s*,\s*height\s*:\s*([1-9]|[1-3]\d|4[0-3])\s*\)",
     "Button in a frame smaller than 44 pt"),
]

# --- LA-40/41: appearance
FORCED_THEME = [
    ("swift", r"\.preferredColorScheme\(\s*\.(light|dark)\s*\)|overrideUserInterfaceStyle\s*=\s*\.(light|dark)"),
    ("dart", r"themeMode\s*:\s*ThemeMode\.(light|dark)"),
    ("js", r"userInterfaceStyle\"?\s*:\s*\"(light|dark)\""),
]
HARD_COLOR = {
    "swift": r"Color\(\s*red\s*:|UIColor\(\s*red\s*:|Color\(\s*hex|UIColor\(\s*hex|#colorLiteral",
    "dart": r"\bColor\(\s*0x[0-9A-Fa-f]{8}\s*\)",
    "js": r"color\s*:\s*['\"]#[0-9A-Fa-f]{3,8}['\"]",
}
ADAPTIVE_COLOR = {
    "swift": r"Color\(\s*\"|UIColor\(\s*named|\.primary\b|\.secondary\b|UIColor\.(label|systemBackground)|"
             r"Color\(uiColor|colorScheme\s*==|traitCollection\.userInterfaceStyle",
    "dart": r"Theme\.of\(context\)|ColorScheme|brightness\s*==|MediaQuery\.platformBrightnessOf",
    "js": r"useColorScheme|Appearance\.getColorScheme|PlatformColor|DynamicColorIOS",
}

# --- LA-50: adaptive layout (iPad)
ADAPTIVE_LAYOUT = r"horizontalSizeClass|UITraitCollection|ViewThatFits|GeometryReader|NavigationSplitView|" \
                  r"LayoutBuilder|MediaQuery\.(of\([^)]*\)\.)?size|MediaQuery\.sizeOf|useWindowDimensions|" \
                  r"Dimensions\.get|UISplitViewController|\.regular\b"

# --- LA-60: reduce motion
REDUCE_MOTION = r"accessibilityReduceMotion|isReduceMotionEnabled|UIAccessibility\.isReduceMotionEnabled|" \
                r"disableAnimations|MediaQuery\.of\([^)]*\)\.disableAnimations|AccessibilityInfo\.isReduceMotionEnabled|" \
                r"reduceMotion"
ANIMATION = r"withAnimation|\.animation\(|UIView\.animate|AnimationController|AnimatedContainer|" \
            r"Animated\.(timing|spring)|useAnimatedStyle|Lottie|lottie|matchedGeometryEffect|Hero\("

# --- LA-70: keyboard
KEYBOARD = [
    ("dart", r"resizeToAvoidBottomInset\s*:\s*false", "Content may not move up when the keyboard opens"),
    ("swift", r"\.ignoresSafeArea\(\s*\.keyboard|\.ignoresSafeArea\(\s*\[[^\]]*\.keyboard", "Keyboard safe area is ignored"),
]


def tag_text(text: str, start: int, max_len: int = 1200) -> str:
    """Text of a JSX tag up to its closing '>' (counting nested {})."""
    depth = 0
    for i in range(start, min(len(text), start + max_len)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == ">" and depth == 0:
            return text[start:i]
    return text[start:start + max_len]


def call_text(text: str, start: int, max_len: int = 1500) -> str:
    """Text up to the end of a parenthesized call."""
    depth = 0
    for i in range(start, min(len(text), start + max_len)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:start + max_len]


def is_measurement(path: str, line_no: int) -> bool:
    """Is the line inside a TextPainter / measurement call (last ~12 lines)?"""
    text = scan.p_read(path).splitlines()
    window = "\n".join(text[max(0, line_no - 12):line_no])
    return bool(re.search(r"TextPainter\s*\(|\.layout\(|measure|ölç", window))


def palette_like(p, pat, files) -> bool:
    """Are most fixed colors (>= 60%) in one file: a theme or color palette file?"""
    per: dict[str, int] = {}
    for f, _n, _l, _m in scan.grep(p, pat, files=files, max_hits=10_000):
        per[f] = per.get(f, 0) + 1
    total = sum(per.values())
    return bool(total) and max(per.values()) >= 0.6 * total


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p = scan.load_profile(a.root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("LA", p, "layout-a11y scan")
    files = scan.code_files(p)
    by_lang: dict[str, list[str]] = {}
    for f in files:
        by_lang.setdefault(scan.lang_of(f), []).append(f)
    xaml = [f for f in p.files if f.endswith(".xaml") and "/obj/" not in f]
    if xaml:
        by_lang["xaml"] = xaml

    # LA-10
    for lg, pat, title in SCALE_OFF:
        for f, n, line, m in scan.grep(p, pat, files=by_lang.get(lg, [])):
            if lg == "dart" and is_measurement(f, n):
                continue  # MEASURING with TextPainter: draws nothing on screen
            # App-wide (root / entry file, RN defaultProps) = USER BUG; single element = SUGGESTION
            # (e.g. Ice Cubes action icons, Element X map button: shipped, intentional design).
            whole = ROOT_FILE.search("/" + p.rel(f)) or re.search(r"defaultProps|MaterialApp|CupertinoApp|"
                                                                 r"WindowGroup|builder\s*:", line)
            rep.add("LA-10", "USER BUG" if whole else "SUGGESTION",
                    title + (" (app-wide)" if whole else " (single element)"), f"{p.rel(f)}:{n} `{m.group(0).strip()}`",
                    "Someone who uses large text cannot enlarge this text." + (
                        "" if whole else " May be intentional on a single element (icon row, counter); text people must read "
                                         "should be able to grow: verify on screen at the largest text size."))
    for f in by_lang.get("swift", []):
        text = scan.p_read(f)
        fixed = len(SWIFT_FIXED_FONT.findall(text)) + len(UIKIT_FIXED_FONT.findall(text))
        if fixed and not SWIFT_RELATIVE.search(text):
            m = SWIFT_FIXED_FONT.search(text) or UIKIT_FIXED_FONT.search(text)
            n = text.count("\n", 0, m.start()) + 1
            rep.add("LA-11", "SUGGESTION", "Fixed point size text (does not grow with Dynamic Type)",
                    f"{p.rel(f)}:{n} ({fixed} places)",
                    "relativeTo: / @ScaledMetric / UIFontMetrics is one way; verify in the simulator at the largest text size.")

    # LA-20
    for f in by_lang.get("dart", []):
        text = scan.p_read(f)
        for m in FLUTTER_ICONBUTTON.finditer(text):
            body = call_text(text, m.end() - 1)
            if "tooltip" not in body and "semanticLabel" not in body and "Semantics(" not in text[max(0, m.start() - 200):m.start()]:
                n = text.count("\n", 0, m.start()) + 1
                rep.add("LA-20", "USER BUG", "Unlabeled icon button (VoiceOver cannot say what it does)",
                        f"{p.rel(f)}:{n}", "tooltip: or Semantics(label:) is one way.")
    for f in by_lang.get("js", []):
        text = scan.p_read(f)
        for m in RN_PRESSABLE.finditer(text):
            tag = tag_text(text, m.start())
            if "accessibilityLabel" not in tag and "aria-label" not in tag and "accessible={false}" not in tag:
                after = text[m.end():m.end() + 600]
                close = after.find("</")
                inner = after[:close if close > 0 else 600]
                if "<Text" in inner or re.search(r">\s*[A-Za-zÀ-ÿ]{2,}", inner):
                    continue  # contains text: VoiceOver reads it
                n = text.count("\n", 0, m.start()) + 1
                rep.add("LA-20", "USER BUG", "No accessibilityLabel on a tappable element without text",
                        f"{p.rel(f)}:{n}", "If it holds only an icon, VoiceOver just says 'button'.")
    sw = by_lang.get("swift", [])
    for f in sw:
        text = scan.p_read(f)
        for m in SWIFT_ICON_BUTTON.finditer(text):
            if not SWIFT_A11Y_LABEL.search(text[m.start():m.end() + 160]):
                rep.add("LA-22", "SUGGESTION", "Icon-only button without an accessibility label",
                        f"{p.rel(f)}:{text.count(chr(10), 0, m.start()) + 1}",
                        "VoiceOver falls back to the symbol's name, or says only 'button'. Add .accessibilityLabel, "
                        "or use Label with .labelStyle(.iconOnly).")
    icon_only, _ = scan.count(p, r"Image\(\s*systemName\s*:", files=sw)
    labels, _ = scan.count(p, r"accessibilityLabel|accessibility\(label|Label\(", files=sw)
    if icon_only > 20 and labels < icon_only / 10:
        rep.add("LA-21", "SUGGESTION", "Many SF Symbols, few accessibility labels",
                f"{icon_only} Image(systemName:) · {labels} labels",
                "Try icon-only buttons with VoiceOver (Label(_:systemImage:) reads its text automatically).")

    # LA-30
    for lg, pat, title in SMALL_TAP:
        for f, n, line, m in scan.grep(p, pat, files=by_lang.get(lg, [])):
            rep.add("LA-30", "USER BUG", title, f"{p.rel(f)}:{n} `{m.group(0).strip()[:60]}`",
                    "Tap targets must be at least 44×44 pt (HIG); the visible size can stay small while the target grows.")

    # LA-40 / LA-41
    forced = False
    for f, pl in [(f, p.mod.load_plist(f)) for f in p.files
                  if os.path.basename(f) == "Info.plist" and p.mod.ios_path(f) and "/Pods/" not in f]:
        if isinstance(pl, dict) and pl.get("UIUserInterfaceStyle") in ("Light", "Dark"):
            forced = True
            rep.add("LA-40", "INFO", f"Appearance fixed: {pl['UIUserInterfaceStyle']} (does not follow dark/light mode)",
                    p.rel(f), "A design decision, not a finding. No dark mode test is needed in this case.")
    for lg, pat in FORCED_THEME:
        c, first = scan.count(p, pat, files=by_lang.get(lg, []))
        if c:
            forced = True
            rep.add("LA-40", "INFO", "Appearance may be fixed in code", f"{p.rel(first[0])}:{first[1]}",
                    "A design decision; the dark mode question only arises if the user cannot choose the theme.")
    if not forced:
        for lg, pat in HARD_COLOR.items():
            c, first = scan.count(p, pat, files=by_lang.get(lg, []))
            adaptive, _ = scan.count(p, ADAPTIVE_COLOR[lg], files=by_lang.get(lg, []))
            if c >= 10 and adaptive < c / 5 and not palette_like(p, pat, by_lang.get(lg, [])):
                rep.add("LA-41", "SUGGESTION", "Many fixed colors, few adaptive ones: contrast risk in dark mode",
                        f"{c} fixed colors (first: {p.rel(first[0])}:{first[1]}) · {adaptive} adaptive",
                        "Measure in the simulator with dark mode + increased contrast (LA-P1: measurement, not taste).")

    # LA-50
    platforms = set(p.mod.summary_flags(p)["platforms"])
    if "iPad" in platforms:
        c, _ = scan.count(p, ADAPTIVE_LAYOUT, files=files)
        if c == 0:
            rep.add("LA-50", "REJECTION RISK", "iPad is supported but the code shows no sign of adapting to screen size",
                    "size class / LayoutBuilder / MediaQuery / useWindowDimensions not found",
                    "2.4.1: the app must be usable on iPad. Try it in the iPad simulator (not verified).")
    # Profile targets: Mac Catalyst, or the iPhone/iPad app available on Mac or Vision Pro.
    if any(x == "Mac Catalyst" or ("iPhone/iPad" in x and ("Mac" in x or "Vision" in x)) for x in platforms):
        rep.add("LA-51", "SUGGESTION", "Set up to run on Mac / Vision Pro too",
                ", ".join(sorted(getattr(p.mod, "display", str)(x) for x in platforms)), "Try it there or turn off availability in App Store Connect (R-14).")

    # LA-60
    anim, first = scan.count(p, ANIMATION, files=files)
    rm, _ = scan.count(p, REDUCE_MOTION, files=files)
    if anim >= 15 and rm == 0:
        rep.add("LA-60", "SUGGESTION", "Many animations, the Reduce Motion setting is never read",
                f"{anim} animations (first: {p.rel(first[0])}:{first[1]})",
                "For users sensitive to motion; required if 'Reduced Motion' will be declared on the Accessibility label.")

    # LA-70
    for lg, pat, title in KEYBOARD:
        for f, n, line, m in scan.grep(p, pat, files=by_lang.get(lg, [])):
            rep.add("LA-70", "SUGGESTION", title, f"{p.rel(f)}:{n}",
                    "If this screen has a text field, try in the simulator whether the keyboard covers it.")

    rep.emit(a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
