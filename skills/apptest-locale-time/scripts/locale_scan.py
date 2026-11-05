#!/usr/bin/env python3
"""apptest-locale-time — static scan (day calculation, date/number/money format,
right-to-left, hardcoded text, plurals, time zone).

Standard library only; does NOT WRITE to the project. Output is a CANDIDATE (verify
against the LT-xx ids in SKILL.md). The real evidence is the time zone / language tour.

    python3 -I locale_scan.py <project_root> [--json]
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

# LT-10: adding 24 hours to a DATE to produce a calendar day, or dividing a duration
# by 24 hours to get a day COUNT (a 23/25-hour day at DST → one day shift).
# Pure DURATIONS (cookie lifetime, "older than one day", timers) are not findings.
_D = r"(?:\d+\s*\*\s*)?(?:86_?400|24\s*\*\s*60\s*\*\s*60|60\s*\*\s*60\s*\*\s*24|24\s*\*\s*3600|3600\s*\*\s*24)"
_DMS = r"(?:\d+\s*\*\s*)?(?:86_?400_?000|24\s*\*\s*60\s*\*\s*60\s*\*\s*1000|1000\s*\*\s*60\s*\*\s*60\s*\*\s*24)"
DAY_MATH = {
    "swift": r"addingTimeInterval\(\s*-?\s*" + _D + r"|Date\(\)\s*[+-]\s*" + _D +
             r"|timeIntervalSince(Now|1970|ReferenceDate)?\b[^\n]*/\s*" + _D + r"|/\s*" + _D + r"\s*\)?\s*\)?\s*$",
    "objc": r"dateByAddingTimeInterval:\s*-?\s*" + _D + r"|/\s*" + _D,
    "dart": r"\.(add|subtract)\(\s*(const\s+)?Duration\(\s*days\s*:|\.difference\([^)]*\)\.inDays\b",
    "js": r"getTime\(\)\s*[+-]\s*" + _DMS + r"|Date\.now\(\)\s*[+-]\s*" + _DMS + r"|/\s*" + _DMS + r"\b|"
          r"setDate\([^)]*getDate\(\)\s*[+-]",
    "kotlin": r"plusSeconds\(\s*" + _D + r"|plus\(\s*\d+\s*,\s*ChronoUnit\.DAYS|Duration\.ofDays",
}
UTC_SAFE = re.compile(r"(?i)\butc\b|toUtc|DateTime\.utc|isUtc|TimeZone\(identifier:\s*\"UTC|GMT")
DEV_SCREEN = re.compile(r"(?i)(debug|developer|betatools|beta ?tools|designsystem|design ?system|internal|"
                        r"playground|sample|example|preview|storybook|fixture|mock|feature_?flags?|featureflags?|"
                        r"automation|component_?library|dev_?mode|\.cl\.tsx)")


# LT-20: hardcoded date pattern shown to the user
FIXED_DATE_FMT = {
    "swift": r"\.dateFormat\s*=\s*\"[^\"]*[dMyHhm][^\"]*\"",
    "objc": r"setDateFormat:\s*@\"",
    "dart": r"DateFormat\(\s*['\"][^'\"]*[dMyHhm][^'\"]*['\"]\s*\)",
    "js": r"\.format\(\s*['\"](DD|MM|YYYY|dd|yyyy|HH|hh)[^'\"]*['\"]\s*\)|toLocale(Date|Time)?String\(\s*['\"][a-z]{2}-[A-Z]{2}['\"]",
    "csharp": r"\.ToString\(\s*\"(dd|MM|yyyy|HH)[^\"]*\"\s*\)",
}
POSIX = re.compile(r"en_US_POSIX|'GMT'|ISO8601|iso8601|\.iso\b|RFC|parse|Parse|decode|encode|api|API|server|json|JSON|log")

# LT-21: fixed money / number format
FIXED_MONEY = {
    "swift": r"String\(\s*format\s*:\s*\"[^\"]*%\.\d*f[^\"]*\"|\"[$€£₺¥]\s*\"\s*\+|\"[$€£₺¥]\\\(",
    "dart": r"toStringAsFixed\(\s*2\s*\)|['\"][$€£₺¥]\$\{?|['\"][$€£₺¥]['\"]\s*\+",
    "js": r"\.toFixed\(\s*2\s*\)|[`'\"][$€£₺¥]\$\{|['\"][$€£₺¥]['\"]\s*\+",
    "csharp": r"\.ToString\(\s*\"(0\.00|N2|F2)\"\s*\)",
}
MONEY_CONTEXT = re.compile(r"(?i)price|amount|total|cost|money|balance|fiyat|tutar|bakiye|ücret|currency|para|pay")

# LT-30: right-to-left (only if an RTL language is supported)
LEFT_RIGHT = {
    "swift": r"textAlignment\s*=\s*\.left\b|textAlignment\s*=\s*\.right\b|contentHorizontalAlignment\s*=\s*\.left\b|"
             r"\.padding\(\s*\.left\b|\.padding\(\s*\.right\b|NSTextAlignment\.left",
    # forceLeftToRight is a deliberate choice (e.g. Wikipedia — supports RTL well, forces LTR for certain content).
    "dart": r"EdgeInsets\.only\(\s*(left|right)\s*:|EdgeInsets\.fromLTRB|Alignment\.(center|top|bottom)(Left|Right)\b|"
            r"TextAlign\.(left|right)\b|Positioned\([^)]*\b(left|right)\s*:",
    # React Native flips left and right margins, padding and positions by itself in RTL, so only text alignment is left.
    "js": r"textAlign\s*:\s*['\"](left|right)['\"]",
}

# LT-40: hardcoded user text in code while a translation system exists
HARDCODED_UI = {
    "dart": r"\bText\(\s*['\"](?=[^'\"$]*[A-Za-zÇĞİÖŞÜçğıöşüÀ-ÿ]{3})[^'\"$]{3,}['\"]",
    "swift": r"Text\(\s*verbatim\s*:\s*\"[^\"]*[A-Za-z]{3}|\.text\s*=\s*\"[^\"]*[A-Za-z]{3}[^\"]*\"|"
             r"setTitle\(\s*\"[^\"]*[A-Za-z]{3}[^\"]*\"\s*,\s*for|title\s*:\s*\"[^\"]*[A-Za-z]{3}[^\"]*\"\s*,\s*message\s*:",
    "js": r"<Text[^>]*>\s*[A-Za-zÀ-ÿ][^<{]{3,}</Text>|Alert\.alert\(\s*['\"][A-Za-z]{3}",
}
L10N_CALL = re.compile(r"NSLocalizedString|String\(localized|LocalizedStringKey|\.localized|AppLocalizations|"
                       r"\bl10n\b|\bS\.of\(|\bt\(['\"]|i18n|intl\.|translate\(|tr\(")

# LT-41: plural by hand (number + fixed plural word)
_NUM = r"\w*(?:count|Count|number|Number|total|Total|num|Num|amount|Amount|length|size)\w*(?:\.(?:count|length))?|\w+\.(?:count|length)"
_PL = r"\s+(?!(?:is|was|has|this|does|its|yes|us|as|less|class|plus|minus|bonus|status)\b)[A-Za-z]{2,}s\b"
PLURAL = {
    "swift": r"\"\\\((?:" + _NUM + r")\)" + _PL,
    "dart": r"['\"]\$\{?(?:" + _NUM + r")\}?" + _PL,
    "js": r"`\$\{(?:" + _NUM + r")\}" + _PL,
}

# LT-60: fixed time zone
FIXED_TZ = {
    "swift": r"TimeZone\(\s*(identifier|abbreviation)\s*:\s*\"(?!UTC|GMT)|TimeZone\(\s*secondsFromGMT\s*:\s*-?[1-9]",
    "dart": r"Duration\(\s*hours\s*:\s*[1-9]\d?\s*\)\s*\)|\.add\(\s*const\s+Duration\(\s*hours\s*:\s*3\s*\)",
    "js": r"timeZone\s*:\s*['\"](?!UTC)[A-Z][a-z]+/[A-Za-z_]+['\"]|getTimezoneOffset\(\)",
}


def window(path, n, before=3, after=1):
    t = scan.p_read(path).splitlines()
    return "\n".join(t[max(0, n - 1 - before):n + after])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p = scan.load_profile(a.root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("LT", p, "locale-time scan")
    files = scan.code_files(p)
    by_lang: dict[str, list[str]] = {}
    for f in files:
        by_lang.setdefault(scan.lang_of(f), []).append(f)
    flags = p.mod.summary_flags(p)
    langs = flags["languages"]
    rtl = sorted(set(langs) & {"ar", "he", "fa", "ur", "ps", "sd", "ckb", "yi", "dv", "ug"})

    # LT-10
    for lg, pat in DAY_MATH.items():
        for f, n, line, m in scan.grep(p, pat, files=by_lang.get(lg, [])):
            if UTC_SAFE.search(window(f, n, 2, 0)) or DEV_SCREEN.search(p.rel(f)):
                continue  # in UTC 24 hours = 1 day: DST has no effect; developer screen
            counting = re.search(r"inDays|/\s*\(?\s*(\d+\s*\*\s*)?(86|24|60|1000)", m.group(0))
            # Threshold ("last 7 days", < / >): a one-hour shift is harmless. An exact day count (== 1, streak, displayed number) is critical.
            threshold = re.search(r"inDays\s*(<=?|>=?)\s*\d|(<=?|>=?)\s*[\w.()]*\.inDays", line)
            rep.add("LT-10", "USER BUG" if counting and not threshold else "SUGGESTION",
                    "Day COUNT calculated by dividing by 24 hours (one day short / over on a DST night)" if counting
                    else "24-hour day added to a date (the hour shifts on a DST night; if the result is a CALENDAR day, the day can shift too)",
                    f"{p.rel(f)}:{n} `{m.group(0).strip()[:50]}`",
                    "If the result is a CALENDAR day or day count, a calendar function (Calendar.date(byAdding:.day), "
                    "dateComponents([.day]), UTC date difference) is one way; if it is elapsed TIME, not a finding. Verify in a DST time zone.")

    # LT-20
    for lg, pat in FIXED_DATE_FMT.items():
        for f, n, line, m in scan.grep(p, pat, files=by_lang.get(lg, [])):
            if POSIX.search(window(f, n, 4, 2)) or re.search(r"(?i)file|export|backup|filename|name\b|key|id\b|path",
                                                             window(f, n, 2, 1)):
                continue  # parsing / server format: fixed is correct
            rep.add("LT-20", "SUGGESTION", "Fixed date pattern (if shown to the user, it does not change with language)",
                    f"{p.rel(f)}:{n} `{m.group(0)[:50]}`",
                    "For display, a localized pattern (dateStyle, setLocalizedDateFormatFromTemplate, DateFormat.yMMMd(locale)) is one way.")

    # LT-21
    for lg, pat in FIXED_MONEY.items():
        for f, n, line, m in scan.grep(p, pat, files=by_lang.get(lg, [])):
            if not MONEY_CONTEXT.search(window(f, n, 2, 1)):
                continue
            rep.add("LT-21", "SUGGESTION", "Money / number written in a fixed format (separator and symbol do not change with language)",
                    f"{p.rel(f)}:{n} `{m.group(0)[:40]}`",
                    "If shown to the user, a localized formatter (NumberFormatter / NumberFormat.currency / Intl.NumberFormat).")

    # LT-30
    if rtl:
        for lg, pat in LEFT_RIGHT.items():
            for f, n, line, m in scan.grep(p, pat, files=by_lang.get(lg, [])):
                # A line asking for the direction is correct RTL support (e.g. Wikipedia `== .forceRightToLeft ? .right : .left`).
                if re.search(r"RTL|[Rr]tl(?=\W)|(?i:RightToLeft|LeftToRight|layoutDirection|TextDirection\.|"
                             r"Directionality|semanticContentAttribute|I18nManager)", line):
                    continue
                rep.add("LT-30", "SUGGESTION", f"Hardcoded left/right — wrong in right-to-left languages ({', '.join(rtl)})",
                        f"{p.rel(f)}:{n} `{m.group(0)[:40]}`",
                        "leading/trailing, start/end, EdgeInsetsDirectional are one way; verify in the simulator in an RTL language.")
    else:
        rep.skip("LT-30", "no right-to-left language")

    # LT-40
    if len(langs) > 1:
        for lg, pat in HARDCODED_UI.items():
            for f, n, line, m in scan.grep(p, pat, files=by_lang.get(lg, [])):
                literal = re.sub(r"\\\([^)]*\)?|\$\{[^}]*\}?|\$\w+", "", m.group(0))
                if re.search(r"://|^\W*[\w.-]+@[\w.-]+|\.(com|org|net|io|app)\b", literal.split("(", 1)[-1]):
                    continue  # address / email sample: not text to translate
                ctx = window(f, n, 12, 2)
                if re.search(r"#Preview|PreviewProvider|sizeThatFits|layoutOnly|placeholderCell|estimat|measur", ctx):
                    continue  # text for preview or measurement only
                if re.search(r"\bDEBUG\b", literal) or re.search(r"#if\s+DEBUG|kDebugMode|__DEV__", ctx):
                    continue  # text visible only in developer builds (e.g. Pocket Casts "(DEBUG)" warning)
                if L10N_CALL.search(line) or DEV_SCREEN.search(p.rel(f)) or \
                        not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşüÀ-ÿ]{3}", re.sub(r"\\\([^)]*\)|\$\{[^}]*\}|\$\w+", "",
                                                                      literal.split("(", 1)[-1].split("=", 1)[-1].replace("verbatim", ""))):
                    continue
                rep.add("LT-40", "USER BUG", "Translation system exists but text is hardcoded (will not be translated)",
                        f"{p.rel(f)}:{n} `{m.group(0)[:60]}`",
                        "Intentional if the text is not to be translated, such as a brand name / symbol.")
    else:
        rep.skip("LT-40", "single language")

    # LT-41
    for lg, pat in PLURAL.items():
        for f, n, line, m in scan.grep(p, pat, files=by_lang.get(lg, [])):
            if DEV_SCREEN.search(p.rel(f)) or re.search(
                    r"plural\(|Plural|\bone\s*:|\bother\s*:|\bfew\s*:|\bmany\s*:|, plural,|Intl\.plural|"
                    r"\.plural\b|localizedStringWithFormat", window(f, n, 3, 0)):
                continue  # already inside a plural construct (ICU / Lingui / Intl / stringsdict)
            rep.add("LT-41", "SUGGESTION", "Number + fixed plural word (wrong for 1; plural rules differ in other languages)",
                    f"{p.rel(f)}:{n} `{m.group(0)[:40]}`",
                    "stringsdict / String Catalog plurals, ICU plural, Intl.plural are one way.")

    # LT-60
    for lg, pat in FIXED_TZ.items():
        for f, n, line, m in scan.grep(p, pat, files=by_lang.get(lg, [])):
            rep.add("LT-60", "SUGGESTION", "Fixed time zone / offset", f"{p.rel(f)}:{n} `{m.group(0)[:50]}`",
                    "Unless intentional (e.g. stock market hours), use the user's time zone; verify in another time zone.")

    # LT-50: non-Gregorian calendar risk — note if there are calendar calculations
    cal, first = scan.count(p, r"Calendar\.current|Calendar\.autoupdatingCurrent|NSCalendar\.current", files=by_lang.get("swift", []))
    greg, _ = scan.count(p, r"Calendar\(\s*identifier\s*:\s*\.(gregorian|iso8601)", files=by_lang.get("swift", []))
    if cal >= 5 and greg == 0:
        rep.add("LT-50", "SUGGESTION", "Calendar calculation uses the user's calendar (the year differs in Buddhist / Japanese calendars)",
                f"{cal} Calendar.current (first: {p.rel(first[0])}:{first[1]})",
                "Correct for display; if a business rule (due date, year boundary) assumes Gregorian, try the Buddhist calendar in the simulator.")

    rep.emit(a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
