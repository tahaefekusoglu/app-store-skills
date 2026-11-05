#!/usr/bin/env python3
"""apptest-store-readiness — automatic pre-submission scan.

Standard library only. Does NOT write to the project. The output is a list of
CANDIDATES: each item carries the ID from SKILL.md (SR-xx) and must be read and
verified.

    python3 -I readiness_scan.py <project_root> [--json] [--check-links]

--check-links: sends GET to public https links found in the code (privacy,
support, terms…) (read-only, 8 s timeout). Sends NO requests to the app's own
API endpoints (only links that look like pages).
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import struct
import sys
import importlib.util
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
# shared/profile.py is loaded by file path: the name "profile" clashes with a
# Python standard module, so importing via sys.path could load the wrong one.
_spec = importlib.util.spec_from_file_location(
    "apptest_profile", os.path.join(HERE, "..", "..", "apptest", "shared", "profile.py"))
prof = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prof)
_spec2 = importlib.util.spec_from_file_location(
    "apptest_scanlib", os.path.join(HERE, "..", "..", "apptest", "shared", "scanlib.py"))
scanlib = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(scanlib)

findings: list[dict] = []


def add(fid, severity, title, evidence, note=""):
    findings.append({"id": fid, "severity": severity, "title": title,
                     "evidence": evidence, "note": note})


def read(path, limit=2_000_000):
    return prof.read(path, limit)


# ------------------------------------------------------------------ icon

def png_info(path):
    """(width, height, has_alpha_channel, has_transparent_pixels), or None if not a PNG.
    Transparency is measured by decoding alpha values (a fully opaque alpha channel ≠ a transparent icon)."""
    import zlib
    try:
        with open(path, "rb") as fh:
            data = fh.read(30_000_000)
    except OSError:
        return None
    if data[:30].startswith(b"version https://git-lfs"):
        return "lfs"  # Git LFS pointer: the real image is not in this clone, could not check
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if len(data) < 29:
        return None  # cut off before the header ends
    w, h = struct.unpack(">II", data[16:24])
    bit, ctype, interlace = data[24], data[25], data[28]
    has_trns = b"tRNS" in data[:200000]
    alpha = ctype in (4, 6) or has_trns
    if not alpha:
        return w, h, False, False
    if has_trns and ctype not in (4, 6):
        return w, h, True, True
    if bit != 8 or interlace:
        return w, h, True, None  # could not measure
    pos, idat = 8, b""
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        if typ == b"IDAT":
            idat += data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
    try:
        raw = zlib.decompress(idat)
    except zlib.error:
        return w, h, True, None
    bpp = 4 if ctype == 6 else 2
    stride = w * bpp
    prev = bytearray(stride)
    o = 0
    for _y in range(h):
        ft = raw[o]
        line = bytearray(raw[o + 1:o + 1 + stride])
        o += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if ft == 1:
                line[x] = (line[x] + a) & 255
            elif ft == 2:
                line[x] = (line[x] + b) & 255
            elif ft == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif ft == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        if any(line[i] != 255 for i in range(bpp - 1, stride, bpp)):
            return w, h, True, True
        prev = line
    return w, h, True, False


def check_icons(p):
    """Only the MAIN app icon (the Release name; excluding alternate / debug / beta / extension
    icons). Xcode 26 Icon Composer (.icon) is accepted too."""
    names = prof.primary_icon_names(p)
    ext_dirs = prof.extension_dirs(p)
    icon_docs = [f for f in p.files if f.endswith(".icon/icon.json") and prof.ios_path(f)
                 and os.path.basename(os.path.dirname(f))[:-5] in names]
    sets = [f for f in p.files if f.endswith(".appiconset/Contents.json") and prof.ios_path(f)
            and os.path.basename(os.path.dirname(f))[:-len(".appiconset")] in names
            and not any(f.startswith(d + "/") for d in ext_dirs)
            and not re.search(r"(?i)(extension|widget|watch|notification|intents|sticker|imessage|previews?/|"
                              r"appclip|demo|sample)", p.rel(f))]
    if icon_docs and not sets:
        add("SR-12", "INFO", "Main icon is in Icon Composer (.icon) format", p.rel(icon_docs[0]),
            "Layered format; Xcode generates it at build time. Verify the 1024 px icon in the built app.")
        return
    maui_icon = [f for f in p.files if f.endswith(".csproj") and "<MauiIcon" in read(f)]
    if not sets and maui_icon:
        add("SR-12", "INFO", "Main icon is generated by MAUI (MauiIcon)", p.rel(maui_icon[0]),
            "Verify in the built app that the 1024 px icon is not transparent.")
        return
    if not sets:
        if p.items.get("ios:Xcode projesi") is None:
            add("SR-10", "REJECTION RISK", f"Main app icon set not found ({', '.join(sorted(names))})",
                "*.appiconset / *.icon", "The icon name in Release may differ: not verified.")
        return
    for cs in sets:
        try:
            meta = json.loads(read(cs))
        except ValueError:
            continue
        folder = os.path.dirname(cs)
        has_marketing = lfs = False
        images = meta.get("images") if isinstance(meta, dict) else None
        for img in images if isinstance(images, list) else []:
            if not isinstance(img, dict) or not isinstance(img.get("filename", ""), str):
                continue  # a damaged entry
            fn = img.get("filename")
            if not fn:
                continue
            info = png_info(os.path.join(folder, fn))
            if info == "lfs":
                lfs = True
                continue
            if info is None:
                if os.path.isfile(os.path.join(folder, fn)) and img.get("size") == "1024x1024" and \
                        img.get("idiom") in ("ios-marketing", "universal") and not img.get("appearances"):
                    has_marketing = True  # e.g. OpenEdX appicon.jpg, Kiwix 1024.png is actually WebP
                    add("SR-11", "SUGGESTION", "1024 px icon is not a PNG", p.rel(os.path.join(folder, fn)),
                        "Use PNG for the App Store icon; verify at build and upload.")
                continue
            w, h, alpha, transparent = info
            appearance = ",".join(a.get("value", "") for a in img.get("appearances", []) or [])
            if img.get("idiom") in ("ios-marketing", "universal") and w == 1024 and not appearance:
                has_marketing = True
                where = p.rel(os.path.join(folder, fn))
                if transparent:
                    add("SR-11", "REJECTION RISK", "1024 px app icon has TRANSPARENT pixels", where,
                        "The App Store icon cannot be transparent (upload error). Place it on an opaque background and export as RGB.")
                elif alpha:
                    add("SR-11", "SUGGESTION", "1024 px icon has an alpha channel (pixels are opaque)", where,
                        "Some validations reject the channel itself; exporting as RGB (no alpha) is safe.")
            if img.get("size") == "1024x1024" and (w, h) != (1024, 1024):
                add("SR-11", "REJECTION RISK", f"Wrong icon size: {w}×{h} (must be 1024×1024)", p.rel(os.path.join(folder, fn)))
        if lfs and not has_marketing:
            add("SR-11", "INFO", "Icons are Git LFS pointers: could not check", p.rel(cs),
                "The real images are not in this clone (git lfs pull). Cannot say whether they exist.")
        elif not has_marketing:
            add("SR-11", "REJECTION RISK", "Main icon set has no 1024×1024 (App Store) icon", p.rel(cs))


# ------------------------------------------------------------------ Info.plist

def ios_plists(p):
    """Info.plists that ship to the store (profile.shipping_info_plists: Release, variants filtered
    out, excluding framework / test bundles; including Xcode's generated INFOPLIST_KEY_*)."""
    return prof.shipping_info_plists(p)


def is_app_plist(pl):
    return prof.is_app_plist_dict(pl)


PLACEHOLDER_PURPOSE = re.compile(r"^\s*$|\bTODO\b|\bFIXME\b|(?i:\blorem ipsum\b|\bplaceholder\b|^test\b|^\$\([^)]*\)\s*$|usage description$)")


def check_plists(p):
    for f in p.files:  # a broken plist skipped silently would leave every permission and settings check empty
        if prof.is_info_plist(f) and prof.load_plist(f) is None:
            add("SR-13", "USER BUG", "Info.plist cannot be read (corrupt file)", p.rel(f),
                "The build fails; this file's permission and settings checks could not run either.")
    plists = ios_plists(p)
    apps = [(f, pl) for f, pl in plists if is_app_plist(pl)]
    expo = any(k.startswith("tech:React Native (Expo)") for k in p.items)
    if not apps and not expo:
        return
    # App-level keys can be split across several sources (file + build setting, one Info.plist
    # per configuration): presence is checked on the UNION.
    union = {}
    for _f, pl in apps:
        union.update(pl)
    seen_modes: set = set()
    # iPad orientations (ITMS-90474): on the UNION; watchOS projects excluded.
    ipad = "iPad" in (p.items.get("target:devices", {}).get("value") or [])
    ios_apps = [(f, pl) for f, pl in apps if not re.search(r"(?i)watch", f)]
    full = any(pl.get("UIRequiresFullScreen") in (True, "YES") for _f, pl in ios_apps)
    o_ipad = set().union(*[set(pl.get("UISupportedInterfaceOrientations~ipad") or []) for _f, pl in ios_apps]) \
        if ios_apps else set()
    o_gen = set().union(*[set(pl.get("UISupportedInterfaceOrientations") or []) for _f, pl in ios_apps]) \
        if ios_apps else set()
    o = o_ipad or o_gen
    need = {"UIInterfaceOrientationPortrait", "UIInterfaceOrientationPortraitUpsideDown",
            "UIInterfaceOrientationLandscapeLeft", "UIInterfaceOrientationLandscapeRight"}
    if ipad and not full and o and not need <= o:
        add("SR-23", "REJECTION RISK", "iPad is supported but not all four orientations are on and UIRequiresFullScreen is absent",
            ", ".join(sorted(x.replace("UIInterfaceOrientation", "") for x in o)),
            "Upload error (ITMS-90474). Either enable all four orientations or set UIRequiresFullScreen=YES.")
    for f, pl in apps:
        r = p.rel(f.replace(" (build setting)", "")) + (" (build setting)" if f.endswith("(build setting)") else "")
        if "ITSAppUsesNonExemptEncryption" not in union and f == apps[0][0]:
            add("SR-20", "SUGGESTION", "No encryption declaration (ITSAppUsesNonExemptEncryption)",
                r, "App Store Connect asks again on every build; if you know the answer, add it to Info.plist.")
        for k, label in prof.USAGE_KEYS.items():
            if k in pl and PLACEHOLDER_PURPOSE.search(str(pl[k]) or ""):
                add("SR-21", "REJECTION RISK", f"Usage description empty or placeholder: {prof.display(label)}", f"{r} › {k}",
                    "5.1.1(ii): must tell the user concretely WHY it is requested.")
        if not (union.get("UILaunchStoryboardName") or union.get("UILaunchScreen") is not None) and f == apps[0][0]:
            add("SR-22", "REJECTION RISK", "No launch screen definition (UILaunchStoryboardName / UILaunchScreen)",
                r, "Without it the app does not open full screen; upload warning / rejection.")
        name = pl.get("CFBundleDisplayName") or pl.get("CFBundleName")
        if isinstance(name, str) and not name.startswith("$(") and re.search(r"(?i)\b(test|debug|dev|staging|beta)\b", name):
            # A separate development target does not ship (e.g. Standard Notes StandardNotesDev-Info.plist).
            dev = re.search(r"(?i)(dev|debug|staging|beta|test)", os.path.basename(f.replace(" (build setting)", ""))) and len(apps) > 1
            add("SR-24", "SUGGESTION" if dev else "REJECTION RISK", f"Display name looks like test/beta: {name!r}", r,
                "Looks like a separate development target; verify it does not ship." if dev else "2.2 / 2.3.")
        for mode in pl.get("UIBackgroundModes", []) or []:
            if mode in seen_modes:
                continue
            seen_modes.add(mode)
            add("SR-25", "SUGGESTION", f"Background mode declared: {mode}. Is it really used?", r,
                "2.5.4: an unused mode is grounds for rejection; if used, explain in the review note how to see it.")
        ats = pl.get("NSAppTransportSecurity")
        if isinstance(ats, dict) and ats.get("NSAllowsArbitraryLoads"):
            add("SR-26", "REJECTION RISK", "ATS fully disabled (NSAllowsArbitraryLoads)", r,
                "Apple: if the value is YES a justification is REQUIRED in review. An app connecting to addresses "
                "the user enters (RSS reader, self-hosted server) has a legitimate reason (e.g. NetNewsWire, Immich are live); "
                "otherwise define an exception only for the domain that needs it.")


# ------------------------------------------------------------------ privacy manifest

REQUIRED_REASON = {
    "NSPrivacyAccessedAPICategoryUserDefaults":
        r"\bUserDefaults\b|NSUserDefaults|@AppStorage|shared_preferences|react-native-default-preference|"
        r"expo-secure-store|NSUbiquitousKeyValueStore",
    # File timestamp APIs (URLResourceKey / FileAttributeKey / POSIX). A model's
    # "creationDate" PROPERTY is not this API: only the key forms are searched.
    "NSPrivacyAccessedAPICategoryFileTimestamp":
        r"creationDateKey|contentModificationDateKey|attributeModificationDateKey|contentAccessDateKey|"
        r"FileAttributeKey\.(creationDate|modificationDate)|\[\s*\.(creationDate|modificationDate)\s*\]|"
        r"NSFileCreationDate|NSFileModificationDate|NSURLCreationDateKey|NSURLContentModificationDateKey|"
        r"\bgetattrlist\(|\bfstat\(|\blstat\(|\bstat\(",
    # Apple's list: systemUptime, mach_absolute_time() (CACurrentMediaTime is not on it).
    "NSPrivacyAccessedAPICategorySystemBootTime":
        r"systemUptime|mach_absolute_time|kern\.boottime",
    "NSPrivacyAccessedAPICategoryDiskSpace":
        r"volumeAvailableCapacity|NSFileSystemFreeSize|NSFileSystemSize|\bstatfs\(|\bstatvfs\(|"
        r"systemFreeSize|getFreeDiskStorage|disk_space",
    "NSPrivacyAccessedAPICategoryActiveKeyboards": r"activeInputModes",
}


def check_privacy_manifest(p):
    manifests = [f for f in p.files if os.path.basename(f) == "PrivacyInfo.xcprivacy"
                 and prof.ios_path(f) and "/Pods/" not in p.rel(f) and ".framework/" not in p.rel(f)]
    declared = set()
    for m in manifests:
        pl = prof.load_plist(m)
        if isinstance(pl, dict):
            types = pl.get("NSPrivacyAccessedAPITypes")
            for e in types if isinstance(types, list) else []:
                if isinstance(e, dict):
                    declared.add(e.get("NSPrivacyAccessedAPIType"))
    code = [f for f in p.files if os.path.splitext(f)[1] in prof.CODE_EXT and prof.ios_path(f)
            and "/test" not in "/" + p.rel(f).lower() and "Tests/" not in p.rel(f)]
    deps = "\n".join(read(f) for f in p.files if os.path.basename(f) in
                     ("pubspec.yaml", "package.json", "Podfile", "Package.swift"))
    used = {}
    for cat, pat in REQUIRED_REASON.items():
        rx = re.compile(pat)
        m = rx.search(deps)
        if m:
            used[cat] = ("dependency", m.group(0))
            continue
        for f in code[:6000]:
            mm = rx.search(read(f, 300_000))
            if mm and mm.group(0).endswith("stat(") and not f.endswith((".swift", ".m", ".mm", ".c", ".cc", ".cpp", ".h")):
                continue  # the C function is meant; Dart's File.stat() and Node's fs.stat() are not it
            if mm:
                used[cat] = (p.rel(f), mm.group(0))
                break
    techs = [k.split(":", 1)[1] for k in p.items if k.startswith("tech:") and k != "tech:?"]
    generated = [t for t in techs if t.startswith(("React Native (Expo)", "Unity", "Unreal", "Godot"))]
    expo_manifest = any(isinstance(v.get("value"), list) and "app.json" in str(v["value"])
                        for k, v in p.items.items() if k == "store:privacy manifest")
    if not manifests and techs and not expo_manifest:
        if generated:
            if "Expo" in generated[0]:
                where = "app.json › expo.ios.privacyManifests (or prebuild output)"
            elif generated[0] == "Unity":
                where = "Xcode export / Unity's privacy manifest setting"
            else:
                where = "the Xcode project generated by the engine"
            add("SR-30", "SUGGESTION", "No privacy manifest in the source: the iOS project is generated at build time",
                where, "Verify that the generated project has PrivacyInfo.xcprivacy (ITMS-91053). Not verified.")
        else:
            add("SR-30", "REJECTION RISK", "App has no privacy manifest (PrivacyInfo.xcprivacy)",
                "—", "Apple: an app that does not declare a required-reason API cannot be uploaded to App Store Connect (ITMS-91053). "
                "Dependencies' own manifests may cover the declaration (e.g. Ice Cubes and Immich are live with no "
                "app-level manifest); the definitive result comes at upload; not verified.")
    for cat, (where, snip) in used.items():
        if cat not in declared:
            sev = "REJECTION RISK" if where != "dependency" else "SUGGESTION"
            add("SR-31", sev, f"Required-reason API use may be undeclared: {cat.replace('NSPrivacyAccessedAPICategory', '')}",
                f"{where} ({snip})",
                "If it is in your own code, add a reason code to the manifest. If only a package uses it, the package "
                "may have its own manifest: check the package's docs (not verified).")


# ------------------------------------------------------------------ placeholders / test leftovers

# Case-sensitive: Spanish "todo" (= all) and words like "Mastodon" are not findings.
# Format samples such as "XXXXX-XXXXX" (invite code) are not placeholders: only when the WHOLE text is X.
PLACEHOLDER = re.compile(r"\bTODO\b|\bFIXME\b|\bTBD\b|^\s*X{3,}\s*$|(?i:lorem ipsum|^\s*placeholder\s*$)")
# "Coming soon" written for a FEATURE is a 2.1 rejection; a content label (an upcoming product) is not.
COMING_SOON = re.compile(scanlib.terms.rx("coming_soon"))
DEV_URL = re.compile(r"https?://([A-Za-z0-9.-]+)", re.I)
_DEV_LABEL = re.compile(r"(?i)^(dev|develop|staging|stage|stg|test|testing|qa|uat|sandbox|preprod|local)(\d*|-.*)$|"
                        r"-(dev|staging|stage|stg|test|qa|uat|sandbox)\d*$")
_LOCAL_HOST = re.compile(r"^(localhost|127\.0\.0\.1|10\.0\.2\.2|0\.0\.0\.0|192\.168\.\d+\.\d+)$")


def dev_host(host: str) -> bool:
    """Is this a development/test server: localhost / private IP, or one LABEL is dev, staging, test …
    (not words that merely START with "dev", such as developer.apple.com)."""
    host = host.lower().split(":")[0]
    if _LOCAL_HOST.match(host):
        return True
    labels = host.split(".")
    if len(labels) < 2 or labels[-2] in ("apple", "google", "mozilla", "microsoft", "xamarin", "github"):
        return False
    return any(_DEV_LABEL.match(l) for l in labels[:-1])
STRING_LIT = re.compile(r"""(["'])((?:\\.|(?!\1).){3,200})\1""")


def string_files(p):
    exts = (".arb", ".strings", ".xcstrings", ".json", ".yaml", ".yml", ".po")
    out = []
    for f in p.files:
        low = "/" + p.rel(f).lower()
        if not prof.ios_path(f) or "/test" in low or "node_modules" in low:
            continue
        if re.search(r"(^|/)(qqq|qps-ploc|en-xa|en-xb)(\.lproj)?/|_qqq\.|\.qqq\.", low):
            continue  # translator notes / pseudo-languages: never shown to users
        if low.endswith(exts) and re.search(r"(l10n|locale|i18n|lang|lproj|translations|strings)", low):
            out.append(f)
    return out


def user_strings(path):
    """(key, text): user-visible values only. In ARB/JSON, meta keys starting with
    "@" (placeholders, description) are skipped."""
    t = read(path)
    low = path.lower()
    if low.endswith((".arb", ".json")):
        try:
            data = json.loads(t)
        except ValueError:
            return []
        out = []

        def walk(o, prefix=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if str(k).startswith("@"):
                        continue
                    walk(v, f"{prefix}{k}.")
            elif isinstance(o, str):
                out.append((prefix.rstrip("."), o))
        walk(data)
        return out
    if low.endswith(".xcstrings"):
        try:
            data = json.loads(t)
        except ValueError:
            return []
        out = []
        strings = data.get("strings") if isinstance(data, dict) else None
        for k, v in (strings.items() if isinstance(strings, dict) else []):
            locs = v.get("localizations") if isinstance(v, dict) else None
            for lang, loc in (locs.items() if isinstance(locs, dict) else []):
                unit = loc.get("stringUnit") if isinstance(loc, dict) else None
                val = unit.get("value") if isinstance(unit, dict) else None
                if val:
                    out.append((f"{k}[{lang}]", val))
        return out
    if low.endswith(".strings"):
        return re.findall(r'^\s*"((?:\\.|[^"])*)"\s*=\s*"((?:\\.|[^"])*)"\s*;', t, re.M)
    if low.endswith(".po"):
        return [("msgstr", m) for m in re.findall(r'^msgstr\s+"(.*)"', t, re.M)]
    return [(str(i), line) for i, line in enumerate(t.splitlines(), 1)
            if ":" in line and not line.lstrip().startswith("#")]


LANG_TAG = re.compile(r"(?:^|[/_.-])([a-z]{2})(?:[-_][A-Za-z]{2,4})?(?:\.lproj/|\.json$|\.arb$)")


def is_source_language(path, files):
    """With an English or Base file present, translations of the same text are not reported again."""
    if not any(re.search(r"(?:^|[/_.-])en(?:[-_][A-Za-z]{2,4})?(?:\.lproj/|\.json$|\.arb$)|Base\.lproj/", x) for x in files):
        return True
    if "Base.lproj/" in path:
        return True
    tag = LANG_TAG.search(path)
    return tag is None or tag.group(1) in ("en", "tr")


def check_placeholders(p):
    hits = 0
    files = string_files(p)
    for f in files:
        for key, text in user_strings(f):
            m = PLACEHOLDER.search(text)
            if m and re.search(r"(?i)placeholder", str(key)):
                continue  # the feature's own name (e.g. Home Assistant "text_input_placeholder.title")
            if m and hits < 25:
                hits += 1
                add("SR-40", "REJECTION RISK", f"Placeholder in user-facing text: {m.group(0)!r} ({text[:60]!r})",
                    f"{p.rel(f)} › {key}", "2.1: the final version must not contain placeholder content.")
            elif COMING_SOON.search(text) and hits < 25 and is_source_language(f, files):
                hits += 1
                add("SR-42", "SUGGESTION", f"'Coming soon' wording: {text[:60]!r}", f"{p.rel(f)} › {key}",
                    "If it describes a FEATURE that does not work yet, it is rejected under 2.1; a content label is not a finding.")
    code = [f for f in p.files if os.path.splitext(f)[1] in prof.CODE_EXT and prof.ios_path(f)
            and "/test" not in "/" + p.rel(f).lower() and "Tests/" not in p.rel(f)
            and "generated" not in p.rel(f).lower()
            and not re.search(r"(?i)/(scripts|tools|fastlane|command line tools|ci|integration_test|test_driver|"
                              r"uitests?)/|\.(test|spec)\.(t|j)sx?$|"
                              r"_test\.dart$|/__tests__/|/__e2e__/|/e2e/|/mocks?/", "/" + p.rel(f))]
    dev = 0
    for f in code[:6000]:
        t = read(f, 300_000)
        for m in DEV_URL.finditer(t):
            if not dev_host(m.group(1)):
                continue
            ls = t.rfind("\n", 0, m.start()) + 1
            le = t.find("\n", m.end())
            if re.search(r"hasPrefix|startsWith|\.replace\(|replacingOccurrences|\.listen\(|process\.argv", t[ls:le]):
                continue  # recognizes or rewrites an address, or is a helper script
            if re.match(r"\s*(//|/\*|\*|#|<!--|--)", t[ls:m.start()]):
                continue  # comment line (sample / docs)
            line = t.count("\n", 0, m.start()) + 1
            ctx = t[max(0, m.start() - 120):m.start()]
            if re.search(r"(?i)debug|kDebugMode|#if DEBUG|__DEV__|assert|isLocal|selfHost|self-host|custom ?(server|url|environment)|"
                         r"\b(local|dev|development|staging|emulator|android|test)\w*\s*(=|:|\(|->)", ctx):
                continue
            if dev < 15:
                dev += 1
                add("SR-41", "SUGGESTION", f"Development/test server address: {m.group(0)}",
                    f"{p.rel(f)}:{line}", "A problem only if used in the RELEASE build: the reviewer sees a non-working "
                    "app (2.1). Usually a development branch (e.g. all 19 candidates across 4 live apps); "
                    "check which address the release configuration selects.")


# ------------------------------------------------------------------ links

PAGE_HINT = re.compile(r"(?i)privacy|gizlilik|terms|kosul|koşul|support|destek|help|legal|kvkk|eula|about|contact|policy")
URL = re.compile(r"https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")


def collect_links(p):
    links = {}
    # Only what is inside the app: code and string files (not docs or README).
    files = [f for f in p.files if (os.path.splitext(f)[1] in prof.CODE_EXT
                                    or f.endswith((".arb", ".strings", ".xcstrings", ".json", ".plist")))
             and prof.ios_path(f) and "/test" not in "/" + p.rel(f).lower() and "node_modules" not in f
             and "/docs/" not in f and "package" not in os.path.basename(f)]
    for f in files[:8000]:
        t = read(f, 300_000)
        for m in URL.finditer(t):
            u = m.group(0).rstrip(".,;)'\"`")
            host = u.split("/")[2] if len(u.split("/")) > 2 else ""
            if "apple.com/legal" in u or (PAGE_HINT.search(u) and not host.endswith("apple.com")):
                links.setdefault(u, p.rel(f))
    return links


def check_links(p, do_fetch):
    links = collect_links(p)
    kinds = {
        "privacy": (scanlib.terms.rx("privacy") + "|policy", "REJECTION RISK",
                     "5.1.1(i): the privacy policy must be easily reachable both in App Store Connect and inside "
                     "the app. If the link comes from a server, verify by hand."),
        "support": (scanlib.terms.rx("support") + "|help|contact", "SUGGESTION",
                   "A support address is required in App Store Connect (1.5, 2.1); having one in the app is good for users."),
    }
    words = {"privacy": scanlib.terms.rx("privacy"), "support": scanlib.terms.rx("support")}
    strings_text = "\n".join(read(f, 2_000_000) for f in string_files(p)[:40])
    for kind, (rx, sev, note) in kinds.items():
        if not any(re.search(rx, u) for u in links):
            if re.search(words[kind], strings_text):
                continue  # present in the strings: the link may come from a server / constructed in code

            add("SR-50", sev, f"No {kind} link found in the app", "code/string scan", note)
    if not do_fetch:
        if links:
            sample = list(links.items())[:6]
            add("SR-51", "INFO", f"{len(links)} page links in the app (do they open: --check-links)",
                "; ".join(u for u, _w in sample) + (" …" if len(links) > 6 else ""))
        return
    if links and not scanlib.online():
        add("SR-51", "INFO", f"No internet: could not check {len(links)} links", "—",
            "This result shows neither that the links work nor that they do not; run again with internet.")
        return
    for u, where in list(links.items())[:30]:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "apptest-store-readiness"})
            with urllib.request.urlopen(req, timeout=8) as r:
                code = r.status
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None) or type(e).__name__
        if code != 200:
            add("SR-51", "REJECTION RISK", f"Link does not open ({code}): {u}", where, "2.1 / 5.1: broken link.")


# ------------------------------------------------------------------ version

MIN_IOS = 13  # Apple: uploads must target iOS 13 or later, since 2026-09-09.


NOT_THE_APP = re.compile(r"(?i)(^|/)(pods|carthage|sourcepackages|checkouts|\.build|node_modules|"
                         r"third_?party|vendor|samples?|examples?|demos?|\w*tests?)(/|$)")
TEST_TARGET = re.compile(r"\b(TEST_HOST|BUNDLE_LOADER|TEST_TARGET_NAME)\s*=")


def check_deployment_target(p):
    """SR-61. What ships counts: the app's own project and Podfile, not samples, dependencies or test
    targets. A Swift package's minimum is not the app's either."""
    for f in p.files:
        rel = p.rel(f)
        if not prof.ios_path(f) or NOT_THE_APP.search(os.path.dirname(rel)):
            continue
        base = os.path.basename(f)
        if base == "project.pbxproj":
            text = read(f, 8_000_000)
            if "com.apple.product-type.application" not in text:
                continue  # a library's project: its minimum does not limit the app
            found = []
            for body, _name in prof.build_configs(text):
                if not TEST_TARGET.search(body):
                    found += re.findall(r"IPHONEOS_DEPLOYMENT_TARGET\s*=\s*\"?(\d+)(?:\.\d+)*\"?\s*;", body)
        elif base == "Podfile":
            found = re.findall(r"(?m)^\s*platform\s*:ios\s*,\s*['\"](\d+)(?:\.\d+)*['\"]", read(f))
        else:
            continue
        low = min((int(v) for v in found), default=MIN_IOS)
        if low < MIN_IOS:
            add("SR-61", "REJECTION RISK", f"iOS deployment target {low} is below iOS {MIN_IOS}", rel,
                "Since 2026-09-09 App Store Connect accepts only uploads that target iOS 13 or later. "
                "Check Apple's Upcoming Requirements page for the current minimum.")


def check_versions(p):
    vals = {k: v["value"] for k, v in p.items.items() if k.startswith("setting:version")}
    if vals:
        add("SR-60", "INFO", "Version numbers (must match the version in App Store Connect; the build number must increase on every upload)",
            "; ".join(f"{prof.display(k.split(':', 1)[1])}={v}" for k, v in vals.items()))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check-links", action="store_true")
    a = ap.parse_args(argv)
    p = prof.build(a.root)
    p.mod = prof
    if scanlib.guard_unknown(p):
        return 0
    if prof.ios_project_missing(p):
        # Unfinished project: saying icon / Info.plist / manifest are "missing" would be a false alarm; there is no iOS project yet.
        add("SR-09", "INFO", "No iOS project yet.", "—",
            "Icon, Info.plist, usage description and privacy manifest checks do not apply; run again once an iOS "
            "project is added (e.g. flutter create --platforms=ios .).")
    else:
        check_icons(p)
        check_plists(p)
        check_privacy_manifest(p)
        check_links(p, a.check_links)
    check_placeholders(p)
    check_deployment_target(p)
    check_versions(p)
    order = {"REJECTION RISK": 0, "USER BUG": 1, "SUGGESTION": 2, "INFO": 3}
    suppressed = scanlib.load_suppressed(p.root)  # CONVENTIONS §9
    hits: dict = {}
    risk: set = set()
    for f in [f for f in findings if scanlib.is_suppressed(f["id"], suppressed)]:
        hits[f["id"]] = hits.get(f["id"], 0) + 1
        if f["severity"] == "REJECTION RISK":
            risk.add(f["id"])
        findings.remove(f)
    findings.sort(key=lambda f: (order.get(f["severity"], 9), f["id"]))
    if a.json:
        json.dump({"member": "SR", "root": p.root, "flags": prof.summary_flags(p), "findings": findings,
                   "suppressed": hits, "suppressed_risk": sorted(risk)}, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    print(f"# store-readiness scan — `{p.root}`\n")
    print("This list is CANDIDATES; verify each item against its ID in SKILL.md.\n")
    cur = None
    for f in findings:
        if f["severity"] != cur:
            cur = f["severity"]
            print(f"\n## {cur}")
        note = f" — {f['note']}" if f["note"] else ""
        print(f"- [{f['id']}] {f['title']} — `{f['evidence']}`{note}")
    if hits:
        print("\n## Suppressed (user decision, .apptest/profile.md)\n" +
              ", ".join(f"{k} ×{v}" for k, v in sorted(hits.items())))
    if not findings:
        print("No candidates in the automatic scan. Move on to the manual checklist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
