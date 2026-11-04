#!/usr/bin/env python3
"""apptest-product-fit: static scan (web wrapper / thin functionality, other
platform names, trademarks, store metadata limits and wording, beta / demo
wording, hidden menus, regulated fields).

Standard library only; does NOT write to the project and does NOT use the network.
Output is CANDIDATES (verify against the PF-xx ids in SKILL.md). Does not judge the
product idea (PF-P1); only states App Store rejection risk.

    python3 -I product_scan.py <project_root> [--json]
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

OTHER_PLATFORM = r"\b(Android|Google Play|Play Store|Galaxy Store|Huawei AppGallery|Windows Phone|BlackBerry)\b"
APPLE_MARKS = r"(?i)\b(iPhone|iPad|iOS|Apple|App Store|Siri|FaceTime|iMessage|macOS|watchOS|AirPods|iCloud)\b"
OTHER_BRANDS = r"(?i)\b(instagram|whatsapp|tiktok|chatgpt|openai|youtube|facebook|google|spotify|netflix|twitter|" \
               r"snapchat|telegram|threads|discord|uber|amazon|microsoft)\b"
NAME_PUFFERY = r"(?i)\b(free|best|#1|no\.? ?1|top ?\d*|cheap|sale|discount|ücretsiz|bedava|en iyi|ucuz|indirim|1 numara)\b"
BETA_WORDS = scan.terms.rx("beta")
HIDDEN_MENU = r"(?i)(debugMenu|DebugMenu|DeveloperMenu|developerMenu|SecretMenu|secretMenu|easterEgg|EasterEgg|" \
              r"hiddenSettings|HiddenSettings|godMode|GodMode)"
REGULATED = [
    ("VPN", r"packet-tunnel|NEPacketTunnelProvider|NETunnelProvider", "5.4: a VPN app needs an organization "
     "developer account; data cannot be sold or shared."),
    ("crypto", r"(?i)\bweb3\b|walletconnect|\bethers\b|web3dart|\bsolana\b|\bbitcoin\b|crypto ?wallet|\bblockchain\b", "3.1.5: wallets and exchanges "
     "need an organization account and a license; mining is banned."),
    ("loans / finance", r"(?i:\b(loan|lending|payday|kredi başvuru|borç ver|faiz oranı|interest rate)\b)|\bAPR\b", "3.2.2(ix) / 5: "
     "personal loan terms and a license; banking services are submitted by the legal entity providing them."),
    ("health records / medical device", r"(?i)HealthKit|HKClinical|blood (pressure|glucose)|medical device|tıbbi cihaz",
     "1.4.1 / 5.1.3: regulatory approval and health data rules."),
    ("real-money gaming", r"(?i)real[- ]money|gerçek para(yla)?|sports ?betting|bahis", "5.3: license, geo-restriction, free app."),
]
META_LIMITS = {"name.txt": 30, "subtitle.txt": 30, "keywords.txt": 100, "promotional_text.txt": 170,
               "description.txt": 4000, "release_notes.txt": 4000}
VAGUE_NOTES = r"(?i)^\s*(bug fixes( and (performance )?improvements)?|improvements|hata düzeltmeleri( ve iyileştirmeler)?|" \
              r"iyileştirmeler|minor fixes)\.?\s*$"


def strip_comments(t: str, low: str) -> str:
    """Comments in translation files are not visible to users (.po "#:" source lines, .strings /* */)."""
    if low.endswith(".po"):
        return "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("#"))
    if low.endswith(".strings"):
        return re.sub(r"(?s)/\*.*?\*/", "", re.sub(r"(?m)^\s*//.*$", "", t))
    return t


def source_texts(p) -> str:
    out, src = [], []
    for f in p.files:
        low = f.lower()
        if low.endswith((".arb", ".strings", ".xcstrings", ".json", ".po")) and \
                re.search(r"(l10n|locale|i18n|lproj|translations|strings|lang)", low) and "node_modules" not in low \
                and not re.search(r"(^|/)(qqq|qps-ploc)(\.lproj)?/", low):
            t = strip_comments(scan.p_read(f, 3_000_000), low)
            out.append(t)
            if re.search(r"(?i)(^|[/_.-])(en|en[-_]us|base|tr)([/_.-]|\.lproj|$)", p.rel(f)):
                src.append(t)
    return "\n".join(src or out)


def display_names(p) -> list[tuple[str, str]]:
    out = []
    for f, pl in p.mod.shipping_info_plists(p):
        if not p.mod.is_app_plist_dict(pl):
            continue
        for k in ("CFBundleDisplayName", "CFBundleName"):
            v = pl.get(k)
            if isinstance(v, str) and v and not v.startswith("$("):
                # profile.py marks generated plists with a "(build ...)" suffix.
                out.append((v, p.rel(re.sub(r" \(build [^)]*\)$", "", f))))
                break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p = scan.load_profile(a.root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("PF", p, "product-fit scan")
    techs = scan.techs(p)
    files = scan.code_files(p)
    texts = source_texts(p)
    deps = "\n".join(scan.p_read(f) for f in p.files if os.path.basename(f) in
                     ("pubspec.yaml", "package.json", "Podfile", "Package.swift"))

    # PF-10: web wrapper / thin functionality (4.2)
    remote_server = None
    for f in p.files:
        if os.path.basename(f).startswith("capacitor.config"):
            m = re.search(r"server\s*:\s*\{[^}]*url\s*:\s*['\"](https?://[^'\"]+)", scan.p_read(f), re.S)
            if m:
                remote_server = (m.group(1), p.rel(f))
    web_root = None
    for f, n, line, m in scan.grep(p, r"(load\(\s*URLRequest\(\s*url\s*:\s*URL\(string:\s*\"https?://|"
                                      r"loadRequest\(\s*Uri\.parse\(\s*['\"]https?://|source\s*=\s*\{\s*\{\s*uri\s*:\s*['\"]https?://|"
                                      r"initialUrl\s*:\s*['\"]https?://)", files=files, max_hits=3):
        web_root = (f, n)
        break
    wrapper_tech = any(t.startswith(("Capacitor", "Cordova")) for t in techs)
    if remote_server:
        rep.add("PF-10", "REJECTION RISK", f"The app shows a remote website (server.url: {remote_server[0]})",
                remote_server[1], "4.2 / 2.5.2: a repackaged website is not accepted; content and functionality must be "
                "inside the app and offer app-specific value.")
    elif (wrapper_tech or web_root) and len(files) < 30:
        rep.add("PF-10", "REJECTION RISK" if web_root else "SUGGESTION",
                "The app may be mostly web content (little native code" + (", a remote page is loaded)" if web_root else ")"),
                f"{p.rel(web_root[0])}:{web_root[1]}" if web_root else ", ".join(getattr(p.mod, "display", str)(t) for t in techs),
                "4.2: show 'app-like' value: offline use, notifications, device features, native UI.")
    elif len(files) < 8:
        rep.add("PF-11", "SUGGESTION", f"Very small codebase ({len(files)} files)", "—",
                "4.2: lasting value and enough functionality; describe the app's purpose and main flow in the review notes.")

    # PF-12: other platform names (2.3.10)
    code = None
    for m in re.finditer(OTHER_PLATFORM, texts):
        ls = texts.rfind("\n", 0, m.start()) + 1
        km = re.match(r'\s*"([^"]{2,120})"\s*[=:]', texts[ls:m.start()])
        if km:  # translation key: if iOS code never uses it, the string is shared across platforms and not shown
            if code is None:  # (e.g. Kickstarter "rate_us_play_store", unused on iOS)
                parts = []
                for f in scan.code_files(p, include_tests=False):
                    t = scan.p_read(f, 2_000_000)
                    # A generated accessor table holding every key (Strings.swift, L10n.swift…) does not count as use.
                    if len(re.findall(r'\bkey\s*:\s*"|NSLocalizedString\(\s*"', t)) > 150:
                        continue
                    parts.append(t)
                code = "\n".join(parts)
            key = km.group(1)
            accessor = re.sub(r"\W", "_", key)
            if key not in code and accessor not in code:
                continue
        ctx = texts[max(0, m.start() - 80):m.end() + 40]
        # In a cross-platform project the string may only show on that platform (e.g. Joplin "Android API level").
        native = all(x.startswith(("Native",)) for x in scan.techs(p))
        rep.add("PF-12", "REJECTION RISK" if native else "SUGGESTION", f"Other platform name in user-facing text: {m.group(0)!r}",
                f"`…{ctx.strip()[:90]}…`", "2.3.10: the app and metadata do not mention other mobile platforms, "
                "except for 'approved interactive functionality'. Functional mentions such as explaining cross-platform sync or "
                "subscriptions exist in shipped apps (Pocket Casts, Wikipedia); a download or rating prompt is a rejection reason.")
        break

    # PF-13 / PF-14: name and trademarks (5.2)
    for name, where in display_names(p):
        am = re.search(APPLE_MARKS, name)
        if am:
            rep.add("PF-13", "REJECTION RISK", f"Apple trademark in the display name: {name!r}", where,
                    "5.2.5: Apple product names are not used in the app name or icon (the 'for iPhone' form is restricted too).")
        om = re.search(OTHER_BRANDS, name)
        if om:
            rep.add("PF-14", "REJECTION RISK", f"Another brand's name in the display name: {om.group(0)!r}", where,
                    "5.2.1 / 4.1: unauthorized brand use and an impression of imitation; without an official relationship the name must change.")
        pm = re.search(NAME_PUFFERY, name)
        if pm:
            rep.add("PF-15", "REJECTION RISK", f"Price or superlative wording in the display name: {pm.group(0)!r}", where, "2.3.7.")

    # PF-16: store metadata (fastlane / metadata folder)
    meta = [f for f in p.files if re.search(r"/(fastlane/)?metadata/[A-Za-z_-]+/[a-z_]+\.txt$", f)]
    for f in meta:
        b = os.path.basename(f)
        t = scan.p_read(f, 50_000).strip()
        lim = META_LIMITS.get(b)
        if lim and len(t) > lim:
            rep.add("PF-16", "REJECTION RISK", f"{b}: {len(t)} characters (limit {lim})", p.rel(f), "App Store Connect does not accept it.")
        if b in ("name.txt", "subtitle.txt", "keywords.txt"):
            if b != "keywords.txt" and re.search(NAME_PUFFERY, t):
                rep.add("PF-15", "REJECTION RISK", f"{b}: price or superlative wording", p.rel(f), "2.3.7.")
            om = re.search(OTHER_BRANDS, t)
            if om and b == "keywords.txt":
                rep.add("PF-14", "REJECTION RISK", f"Other brand in keywords: {om.group(0)!r}", p.rel(f), "2.3.7 / 5.2.")
            if re.search(OTHER_PLATFORM, t):
                rep.add("PF-12", "REJECTION RISK", f"{b}: other platform name", p.rel(f), "2.3.10.")
        if b == "release_notes.txt" and re.search(VAGUE_NOTES, t):
            rep.add("PF-17", "SUGGESTION", "Vague \"What's New\" text", p.rel(f), "2.3.12: describe significant changes concretely.")
    if not meta:
        rep.skip("PF-16", "no store metadata in the repo (fastlane/metadata); check the App Store Connect text by hand")

    # PF-18: beta / demo wording
    bm = re.search(BETA_WORDS, texts)
    if bm:
        rep.add("PF-18", "REJECTION RISK", f"Trial or beta wording in user-facing text: {bm.group(0)!r}", "strings",
                "2.2: beta, demo or trial versions do not go to the App Store (that is TestFlight's job). Not a finding if it is "
                "the beta label of a FEATURE that works.")

    # PF-19: hidden menu (2.3.1)
    for f, n, line, m in scan.grep(p, HIDDEN_MENU, files=files, max_hits=3):
        t = scan.p_read(f)
        if re.search(r"#if\s+DEBUG|kDebugMode|__DEV__|BuildConfig\.DEBUG|isDebug|#if\s+INTERNAL", t):
            continue
        rep.add("PF-19", "SUGGESTION", "Hidden or developer menu may be enabled in the release build", f"{p.rel(f)}:{n}",
                "2.3.1: an undocumented hidden feature is a rejection reason; verify it is off in the release build.")
        break

    # PF-20: regulated field (info)
    for label, rx, note in REGULATED:
        hay = deps + "\n" + texts + "\n" + "\n".join(p.items.keys())
        no_icons = [f for f in files[:3000] if not re.search(r"(?i)(icon|glyph|emoji|font|symbol)s?\.\w+$", f)]
        if re.search(rx, hay) or scan.count(p, rx, files=no_icons)[0]:
            rep.add("PF-20", "INFO", f"Signs of a regulated field: {label}", "dependencies / strings / code",
                    note + " Not a finding if the app is not really in this field.")

    rep.emit(a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
