#!/usr/bin/env python3
"""apptest: app profile (shared/CONVENTIONS.md §4).

Standard library only. Never WRITES to the project; read-only.

    python3 -I profile.py <project_root>           # markdown
    python3 -I profile.py <project_root> --json    # for machines

What it extracts:
  - technology (SwiftUI/UIKit, Flutter, React Native/Expo, KMP, .NET MAUI,
    web wrapper, Unity/Unreal/Godot) and the iOS project folder
  - targets: iPhone/iPad, Mac (Catalyst / Designed for iPad), Vision,
    Watch, extensions (widget, notification, share, App Clip ...)
  - capabilities: account/sign-in, purchases, ads, network, tracking/analytics,
    AI, location/camera/... permissions, notifications, background, database,
    localization, health, kids SDKs
  - store files: privacy manifest, encryption declaration, icon
  - test infrastructure

Every finding carries a confidence: certain (explicit in configuration) · hint
(dependency or code search) · unknown (cannot be derived from code).

Item keys in the groups below are INTERNAL ids that member scripts match on, so
they stay as they are: teknoloji, yetenek, izin, arka plan, plus "setting:bundle id",
"setting:version", "target:devices", the two "designed for iPhone/iPad" targets,
"ios:Xcode projesi", "store:privacy manifest", USAGE_KEYS labels, the summary
flag names and the BUILD_SETTING_MARK suffix. Output goes through display().
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import sys

# A non-UTF-8 Windows console must not crash on non-ASCII letters (every OS).
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SKIP_DIRS = {
    ".git", "node_modules", "Pods", "build", "Build", "DerivedData", ".dart_tool",
    ".gradle", ".idea", ".vscode", "dist", ".next", ".expo", "vendor", "Carthage",
    ".build", ".swiftpm", "obj", "bin", "coverage", ".fvm",
    "ephemeral", ".symlinks", "xcuserdata", "__pycache__", ".apptest",
    ".buildkite", ".husky",
}
# Non-iOS folders in multi-platform projects (Flutter, RN, KMP): the Info.plist,
# Xcode project and permissions here do not belong to the iOS app.
# "/mac/": a separate Mac app folder (e.g. NetNewsWire Mac/, mistaken for the iOS icon).
NON_IOS_DIRS = ("/macos/", "/mac/", "/android/", "/windows/", "/linux/", "/web/", "/tvos/", "-tvos/", "_tvos/", "/desktop/",
                " tv app/", "/tvapp/", "/watchos/", "/example/", "/examples/")


_ROOT = ""  # Set when Profile is built: path patterns look INSIDE the project (the user name "mac", ~/web/... trap).


def _inner(f: str) -> str:
    """The part after the project root, with a leading "/". Searching the absolute path would treat every file as
    non-iOS when the project lives under ~/web or /Users/mac, and the scan would silently come out empty."""
    n = f.replace("\\", "/")
    root = _ROOT.replace("\\", "/").rstrip("/")
    return n[len(root):] if root and n.startswith(root + "/") else n


def ios_path(f: str) -> bool:
    low = _inner(f).lower()
    if any(low.startswith(x) for x in _UNUSED_PACKAGES):
        return False
    return not any(d in low for d in NON_IOS_DIRS)


_UNUSED_PACKAGES: tuple = ()


def _monorepo_unused(p: "Profile") -> tuple:
    """Sibling packages in a JS monorepo that the mobile app never names: not part of the app (e.g. the Joplin
    packages/clipper browser extension). Links are followed through package.json text (packages copied by a script count)."""
    pk = {}
    for f in p.files:
        if os.path.basename(f) == "package.json" and "/node_modules/" not in f:
            rel = _inner(f)[:-len("package.json")]
            if rel.count("/") == 3:  # /packages/name/
                text = read(f, 300_000)
                m = re.search(r'"name"\s*:\s*"([^"]+)"', text)
                pk[rel] = (m.group(1) if m else "", text)
    mobile = [r for r, (_n, t) in pk.items() if re.search(r'"(react-native|expo|@capacitor/ios|cordova-ios)"\s*:', t)]
    if len(pk) < 3 or not mobile:
        return ()
    used, todo = set(mobile), list(mobile)
    while todo:
        text = pk[todo.pop()][1]
        for r, (n, _t) in pk.items():
            if r not in used and n and n in text:
                used.add(r)
                todo.append(r)
    return tuple(r.lower() for r in pk if r not in used)


# Internal suffix on virtual Info.plist paths; member scripts match it, so it stays. display() translates it.
BUILD_SETTING_MARK = " (build setting)"
# Output names for internal ids. Lookups are exact; display() also handles the technology names.


def display(text: str) -> str:
    return text


def display_key(key: str) -> str:
    return key


def display_flags(flags: dict) -> dict:
    return flags


CODE_EXT = {".swift", ".m", ".mm", ".dart", ".ts", ".tsx", ".js", ".jsx", ".kt",
            ".cs", ".gd", ".cpp", ".h"}
MAX_FILES = 40000
MAX_CODE_BYTES = 400_000  # most bytes read per file


class Profile:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        global _ROOT
        _ROOT = self.root
        self.items: dict[str, dict] = {}
        self.files: list[str] = []
        self.truncated = False

    def add(self, key: str, value, confidence: str, evidence: str | None = None):
        """If a key comes twice the higher confidence wins and evidence accumulates."""
        rank = {"certain": 2, "hint": 1, "unknown": 0}
        cur = self.items.get(key)
        ev = [evidence] if evidence else []
        if cur is None or rank[confidence] > rank[cur["confidence"]]:
            prev_ev = cur["evidence"] if cur else []
            self.items[key] = {"value": value, "confidence": confidence,
                               "evidence": (ev + prev_ev)[:5]}
        elif evidence and evidence not in cur["evidence"] and len(cur["evidence"]) < 5:
            cur["evidence"].append(evidence)

    def rel(self, path: str) -> str:
        return os.path.relpath(path, self.root).replace("\\", "/")


# Unity cache folders: skipped ONLY in a Unity project (ProjectSettings next to them);
# elsewhere "Library" can be real code (e.g. Kickstarter iOS).
UNITY_CACHE_DIRS = {"Library", "Temp", "Logs", "UserSettings"}


# Server / web / tool folders at the root (other projects in the app's repo). ONLY at the root:
# iOS code can have a submodule called "Server" too. e.g. KotlinConf backend/, Immich server/ web/,
# Bluesky bskylink/ (Dockerfile.bskylink at the root).
ROOT_NON_APP = {"backend", "server", "servers", "functions", "cloud-functions", "website", "web", "docs",
                "machine-learning", "deployment", "docker", "dev-env", "infra", "terraform"}


def _root_non_app(root: str, d: str) -> bool:
    return d.lower() in ROOT_NON_APP or os.path.exists(os.path.join(root, "Dockerfile." + d)) \
        or os.path.exists(os.path.join(root, d, "Dockerfile"))


def walk(p: Profile):
    for dirpath, dirnames, filenames in os.walk(p.root):
        unity = "ProjectSettings" in dirnames
        at_root = os.path.abspath(dirpath) == os.path.abspath(p.root)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".xcarchive")
                       and not (unity and d in UNITY_CACHE_DIRS)
                       and not (at_root and _root_non_app(p.root, d))]
        for f in filenames:
            # Paths use "/" on every OS: test / generated file patterns look for "/" (Windows gives "\\").
            p.files.append(os.path.join(dirpath, f).replace("\\", "/"))
            if len(p.files) >= MAX_FILES:
                p.truncated = True
                _set_unused(p)
                return
    _set_unused(p)


def _set_unused(p: Profile):
    global _UNUSED_PACKAGES
    _UNUSED_PACKAGES = ()
    _UNUSED_PACKAGES = _monorepo_unused(p)


def read(path: str, limit: int = MAX_CODE_BYTES) -> str:
    try:
        with open(path, "rb") as fh:
            return fh.read(limit).decode("utf-8", "replace")
    except OSError:
        return ""


def find(p: Profile, pred) -> list[str]:
    return [f for f in p.files if pred(f)]


def name(f: str) -> str:
    return os.path.basename(f)


# ---------------------------------------------------------------- technology

def detect_tech(p: Profile) -> dict:
    deps_text: dict[str, str] = {}
    techs = []

    pubspecs = find(p, lambda f: name(f) == "pubspec.yaml")
    for ps in pubspecs:
        t = read(ps)
        deps_text[ps] = t
        if re.search(r"^\s*flutter\s*:\s*$", t, re.M) or "sdk: flutter" in t:
            techs.append(("Flutter", ps))

    for pj in find(p, lambda f: name(f) == "package.json"):
        t = read(pj)
        deps_text[pj] = t
        if '"expo"' in t:
            techs.append(("React Native (Expo)", pj))
        elif '"react-native"' in t:
            techs.append(("React Native", pj))
        if re.search(r'"@capacitor/(core|ios)"', t):
            techs.append(("Capacitor (web wrapper)", pj))  # id; display() translates
        if '"cordova-ios"' in t or ('"@ionic/' in t and "capacitor" not in t):
            techs.append(("Cordova/Ionic (web wrapper)", pj))

    for f in find(p, lambda f: name(f) in ("app.json", "app.config.json")):
        try:
            cfg = json.loads(read(f))
        except ValueError:
            continue
        ios = (cfg.get("expo") or cfg).get("ios") if isinstance(cfg, dict) else None
        if isinstance(ios, dict):
            r = p.rel(f)
            if ios.get("bundleIdentifier"):
                p.add("setting:bundle id", ios["bundleIdentifier"], "certain", r)
            if "supportsTablet" in ios:
                p.add("target:devices", ["iPhone", "iPad"] if ios["supportsTablet"] else ["iPhone"], "certain", r)
            info = ios.get("infoPlist") or {}
            for k, label in USAGE_KEYS.items():
                if k in info:
                    p.add("permission:" + label, str(info[k])[:80], "certain", r)
            if "usesNonExemptEncryption" in (ios.get("config") or {}):
                p.add("store:encryption declaration (ITSAppUsesNonExemptEncryption)",
                      ios["config"]["usesNonExemptEncryption"], "certain", r)
            if "ITSAppUsesNonExemptEncryption" in info:
                p.add("store:encryption declaration (ITSAppUsesNonExemptEncryption)",
                      info["ITSAppUsesNonExemptEncryption"], "certain", r)
            for mode in info.get("UIBackgroundModes", []) or []:
                p.add("background:" + str(mode), True, "certain", r)
            if ios.get("privacyManifests"):
                p.add("store:privacy manifest", ["app.json › ios.privacyManifests"], "certain", r)
        ver = (cfg.get("expo") or {}).get("version") if isinstance(cfg, dict) else None
        if ver:
            p.add("setting:version (app.json)", ver, "certain", p.rel(f))
    for f in find(p, lambda f: name(f) in ("build.gradle.kts", "build.gradle")):
        t = read(f)
        deps_text[f] = t
        # Version catalog aliases too (alias(libs.plugins.kotlinMultiplatform), e.g. KotlinConf).
        if "kotlin(\"multiplatform\")" in t or "org.jetbrains.kotlin.multiplatform" in t or \
                re.search(r"libs\.plugins\.kotlin[.-]?[mM]ultiplatform|id\(\s*\"kotlin-multiplatform\"", t):
            techs.append(("Kotlin Multiplatform", f))
    for f in find(p, lambda f: f.endswith(".csproj")):
        t = read(f)
        if "<UseMaui>true" in t:
            techs.append((".NET MAUI", f))
    for f in find(p, lambda f: f.endswith("ProjectSettings/ProjectVersion.txt")):
        techs.append(("Unity", f))
    for f in find(p, lambda f: f.endswith("Packages/manifest.json")):
        deps_text[f] = read(f)  # Unity package manager
    for f in find(p, lambda f: f.endswith(".uproject")):
        techs.append(("Unreal", f))
    for f in find(p, lambda f: name(f) == "project.godot"):
        techs.append(("Godot", f))
    # Java / Kotlin games and apps compile to iOS with RoboVM (MobiVM); libGDX is the most common case
    # (e.g. Shattered Pixel Dungeon, live on the store; this used to say "technology not recognized").
    for f in find(p, lambda f: name(f) == "robovm.xml" or (name(f) in ("build.gradle", "build.gradle.kts")
                                                           and re.search(r"robovm", read(f, 200_000)))):
        gdx = any(re.search(r"gdx|libgdx", read(g, 200_000)) for g in find(p, lambda g: name(g) in
                                                                        ("build.gradle", "build.gradle.kts")))
        techs.append(("libGDX (RoboVM)" if gdx else "RoboVM (Java/Kotlin)", f))
        break

    pbx = find(p, lambda f: f.endswith(".xcodeproj/project.pbxproj") and ios_path(f))
    swift = find(p, lambda f: f.endswith(".swift"))
    native = not techs and (pbx or swift)
    if native:
        ui = []
        sample = " ".join(read(f, 20000) for f in swift[:400])
        if "import SwiftUI" in sample:
            ui.append("SwiftUI")
        if "import UIKit" in sample or find(p, lambda f: f.endswith(".storyboard")):
            ui.append("UIKit")
        if find(p, lambda f: f.endswith((".m", ".mm"))) and not swift:
            ui.append("Objective-C")
        if "import AppKit" in sample:
            ui.append("AppKit")
        kind = "Native Mac" if _mac_only(p, pbx) else "Native iOS"
        if kind == "Native Mac" and "import UIKit" not in sample:  # On Mac a storyboard is AppKit (e.g. Rectangle)
            ui = [x for x in ui if x != "UIKit"]
        techs.append((kind + " (" + ("/".join(ui) or "Swift") + ")",
                      pbx[0] if pbx else swift[0]))

    # DIRECT dependencies only: lock files (pubspec.lock, Podfile.lock,
    # package-lock.json ...) list transitive packages too and produce false alarms.
    for f in find(p, lambda f: name(f) in ("Podfile", "Package.swift", "Cartfile")):
        deps_text[f] = read(f, 2_000_000)
    for f in pbx:
        refs = re.findall(r'repositoryURL = "([^"]+)"', read(f, 5_000_000))
        if refs:
            deps_text[f + "#spm"] = "\n".join(refs)
    for ps in pubspecs:
        m = re.search(r"^version:\s*([^\s#]+)", deps_text.get(ps, ""), re.M)
        if m:
            p.add("setting:version (pubspec)", m.group(1), "certain", p.rel(ps))

    seen = set()
    for tname, ev in techs:
        if tname in seen:
            continue
        seen.add(tname)
        p.add("tech:" + tname, True, "certain", p.rel(ev))
    if not techs:
        p.add("tech:?", "not recognized", "unknown")

    return {"deps": "\n".join(deps_text.values()), "pbx": pbx, "swift": swift}


# ------------------------------------------------------------ iOS configuration

PRODUCT_TYPES = {
    "com.apple.product-type.application": "app",
    "com.apple.product-type.application.on-demand-install-capable": "App Clip",
    "com.apple.product-type.app-extension": "extension",
    "com.apple.product-type.extensionkit-extension": "extension",
    "com.apple.product-type.application.watchapp2": "Watch app",
    "com.apple.product-type.application.watchapp2-container": "Watch app",
    "com.apple.product-type.watchkit2-extension": "Watch extension",
    "com.apple.product-type.app-extension.messages": "iMessage extension",
    "com.apple.product-type.app-extension.messages-sticker-pack": "sticker pack",
    "com.apple.product-type.bundle.unit-test": "unit test",
    "com.apple.product-type.bundle.ui-testing": "UI test",
}
EXT_POINTS = {
    "com.apple.widgetkit-extension": "widget",
    "com.apple.usernotifications.service": "notification service extension",
    "com.apple.usernotifications.content-extension": "notification content extension",
    "com.apple.share-services": "share extension",
    "com.apple.keyboard-service": "keyboard extension",
    "com.apple.intents-service": "Siri/Intents extension",
    "com.apple.broadcast-services-upload": "broadcast extension",
    "com.apple.photo-editing": "photo editing extension",
    "com.apple.Safari.web-extension": "Safari extension",
    "com.apple.networkextension.packet-tunnel": "VPN (packet tunnel)",
    "com.apple.FileProvider-nonUI": "file provider",
    "com.apple.deviceactivity.monitor-extension": "Screen Time extension",
    "com.apple.services": "action extension (Action)",
    "com.apple.ui-services": "action extension (Action, with UI)",
    "com.apple.message-payload-provider": "iMessage app",
    "com.apple.widget-extension": "Today widget (OLD, being deprecated since iOS 14)",
    "com.apple.watchkit": "WatchKit extension",
    "com.apple.authentication-services-credential-provider-ui": "password autofill (Credential Provider)",
    "com.apple.authentication-services-account-authentication-modification-ui": "account security upgrade extension",
    "com.apple.fileprovider-nonui": "file provider",
    "com.apple.fileprovider-actionsui": "file provider actions",
    "com.apple.callkit.call-directory": "call blocking / identification (Call Directory)",
    "com.apple.classkit.context-provider": "ClassKit",
    "com.apple.spotlight.import": "Spotlight import",
    "com.apple.intents-ui-service": "Siri/Intents UI extension",
    "com.apple.appintents-extension": "App Intents extension",
    "com.apple.Safari.content-blocker": "Safari content blocker",
    "com.apple.background-asset-downloader-extension": "background asset downloader",
}
# Labels are internal ids: member scripts compare them (see the module docstring); display() translates.
USAGE_KEYS = {
    "NSCameraUsageDescription": "camera",
    "NSMicrophoneUsageDescription": "microphone",
    "NSPhotoLibraryUsageDescription": "photos",
    "NSPhotoLibraryAddUsageDescription": "adding photos",
    "NSLocationWhenInUseUsageDescription": "location (when in use)",
    "NSLocationAlwaysAndWhenInUseUsageDescription": "location (always)",
    "NSContactsUsageDescription": "contacts",
    "NSCalendarsUsageDescription": "calendar",
    "NSCalendarsFullAccessUsageDescription": "calendar",
    "NSRemindersUsageDescription": "reminders",
    "NSHealthShareUsageDescription": "health (read)",
    "NSHealthUpdateUsageDescription": "health (write)",
    "NSMotionUsageDescription": "motion",
    "NSBluetoothAlwaysUsageDescription": "bluetooth",
    "NSFaceIDUsageDescription": "Face ID",
    "NSSpeechRecognitionUsageDescription": "speech recognition",
    "NSUserTrackingUsageDescription": "tracking permission (ATT)",
    "NSLocalNetworkUsageDescription": "local network",
    "NSAppleMusicUsageDescription": "media library",
    "NFCReaderUsageDescription": "NFC",
    "NSHomeKitUsageDescription": "HomeKit",
}


def _mac_only(p: "Profile", pbx) -> bool:
    """A project that builds for Mac only. With an iOS / visionOS target too it is multi-platform and does not count."""
    ios = r"iphoneos|IPHONEOS_DEPLOYMENT_TARGET|TARGETED_DEVICE_FAMILY|xros|SUPPORTS_MACCATALYST"
    if pbx:
        # Settings can live in .xcconfig too; UIKit is also iOS evidence (e.g. NetNewsWire's iOS target is in xcconfig).
        conf = [f for f in p.files if f.endswith(".xcconfig") and ios_path(f)]
        text = "\n".join(read(f, 5_000_000) for f in list(pbx) + conf)
        code = " ".join(read(f, 20000) for f in p.files if f.endswith(".swift") and ios_path(f))
        return "macosx" in text and not re.search(ios, text) and "import UIKit" not in code
    pkg = "\n".join(read(f, 200_000) for f in p.files if os.path.basename(f) == "Package.swift" and ios_path(f))
    return bool(re.search(r"\.macOS\(", pkg)) and not re.search(r"\.(iOS|visionOS|watchOS|tvOS)\(", pkg)


def ios_project_missing(p: "Profile") -> bool:
    """A multi-platform project whose iOS project does not exist yet (no ios/ from flutter create; unfinished projects).
    Expo and game engines generate the iOS project at build time, so they do not count."""
    t = [k.split(":", 1)[1] for k in p.items if k.startswith("tech:")]
    if any("Expo" in x or x in ("Unity", "Unreal", "Godot") or "RoboVM" in x for x in t):
        return False
    if not any(x == "Flutter" or x.startswith(("React Native", "Capacitor", "Cordova")) or x == "Kotlin Multiplatform"
               for x in t):
        return False
    return not any(f.endswith(".xcodeproj/project.pbxproj") and ios_path(f) for f in p.files)


def project_kind(root: str) -> str:
    """What is a folder with no recognized technology REALLY? Told to the user instead of "not recognized"."""
    try:
        top = os.listdir(root)
    except OSError:
        return "unreadable"
    top = [x for x in top if x not in (".DS_Store", ".git", ".gitignore")]
    if not top:
        return "empty folder"
    names, exts = set(), set()
    pkg = ""
    for d, dirs, files in os.walk(root):
        depth = os.path.relpath(d, root).count(os.sep)
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and x not in (".venv", "venv") and depth < 2]
        for f in files:
            names.add(f)
            exts.add(os.path.splitext(f)[1].lower())
            if f == "package.json":
                pkg += read(os.path.join(d, f), 100_000)
    if "pubspec.yaml" in names:
        return "pubspec.yaml exists but no Flutter dependency could be read (corrupt file or a pure Dart package)"
    kinds = []
    if re.search(r'"(next|vite|react|vue|@angular/core|svelte)"', pkg):
        kinds.append("web frontend")
    if re.search(r'"(express|fastify|@nestjs/core|koa)"', pkg):
        kinds.append("Node server")
    if names & {"requirements.txt", "pyproject.toml", "requirements-dev.txt", "Pipfile"} or ".py" in exts:
        kinds.append("Python")
    if ".pine" in exts:
        kinds.append("Pine Script")
    if not kinds and exts and exts <= {".md", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".svg", ".csv", ".zip", ".ai",
                                       ".psd", ".mp4", ".mov", ".docx", ".xlsx", ""}:
        kinds.append("documents / images only")
    return " + ".join(kinds) or "no app code found"


def load_plist(path: str):
    try:
        with open(path, "rb") as fh:
            return plistlib.load(fh)
    except Exception:
        return None


NOT_INFO_PLISTS = ("GoogleService-Info.plist",)


def is_info_plist(f: str) -> bool:
    """Info.plist or a custom name (Wikipedia-Info.plist, App-Info.plist ...); not Firebase configuration."""
    b = os.path.basename(f)
    inner = _inner(f)
    if re.search(r"(?i)/(sample|demo)\w*/", inner):  # sample app that never ships (e.g. Firefox SampleBrowser)
        return False
    return (b.endswith("Info.plist") and b not in NOT_INFO_PLISTS and ios_path(f)
            and not any(x in inner for x in ("/Pods/", ".framework/", "/Frameworks/", ".bundle/", "/Carthage/")))


def info_plists(p: "Profile") -> list[tuple[str, dict]]:
    """All Info.plist contents of the app and its extensions + the Info.plist keys Xcode GENERATES
    (GENERATE_INFOPLIST_FILE: `INFOPLIST_KEY_*` build settings, pbxproj and .xcconfig).
    Generated keys are gathered in one virtual entry whose path is "<pbxproj>" + BUILD_SETTING_MARK."""
    out = []
    seen = set()
    for f in p.files:
        if is_info_plist(f):
            pl = load_plist(f)
            if isinstance(pl, dict):
                out.append((f, pl))
                seen.add(os.path.normpath(f))
    # A file not named "Info.plist": the project setting (INFOPLIST_FILE) names it (e.g. Nextcloud Brand/iOSClient.plist).
    for pbx in p.files:
        if not pbx.endswith("project.pbxproj") or not ios_path(pbx):
            continue
        srcroot = os.path.dirname(os.path.dirname(pbx))
        for raw in set(re.findall(r'(?<![A-Z_])INFOPLIST_FILE = "?([^";]+)"?;', read(pbx, 5_000_000))):
            rel = re.sub(r"^\$[({]SRCROOT[)}]/", "", raw.strip())
            if "$" in rel or not rel.endswith(".plist"):
                continue
            path = os.path.normpath(os.path.join(srcroot, rel))
            if path in seen or not os.path.isfile(path) or re.search(r"(?i)tests?[/._-]|(^|/)(sample|demo)\w*/", rel):
                continue
            pl = load_plist(path)
            if isinstance(pl, dict):
                out.append((path.replace("\\", "/"), pl))
                seen.add(path)
    gen: dict = {}
    src = None
    for f in p.files:
        if not (f.endswith("project.pbxproj") or f.endswith(".xcconfig")) or not ios_path(f) or "/Pods/" in _inner(f):
            continue
        # Forms: INFOPLIST_KEY_X = value;  "INFOPLIST_KEY_X[sdk=iphoneos*]" = value;
        for k, v in re.findall(r'"?INFOPLIST_KEY_([A-Za-z_]+)(?:\[[^\]]*\])?"?\s*=\s*("(?:\\.|[^"])*"|[^;\n]+)',
                               read(f, 5_000_000)):
            v = v.strip().strip('"').replace('\\"', '"')
            src = src or f
            if k.startswith("UILaunchScreen") or k == "UILaunchStoryboardName":
                gen.setdefault("UILaunchScreen", {})
                continue
            if k.startswith("UISupportedInterfaceOrientations"):
                # one space-separated string in the build setting; _iPad / _iPhone suffixes
                suffix = {"_iPad": "~ipad", "_iPhone": "~iphone"}.get(k[len("UISupportedInterfaceOrientations"):], "")
                gen.setdefault("UISupportedInterfaceOrientations" + suffix, v.split())
                continue
            gen.setdefault(k, {"YES": True, "NO": False}.get(v, v))
    # XcodeGen project.yml and Cordova config.xml generate the same keys (e.g. Kiwix, Moodle).
    for f in p.files:
        b = os.path.basename(f)
        if b in ("project.yml", "project.yaml") and ios_path(f):
            for k, v in re.findall(r"^\s*INFOPLIST_KEY_([A-Za-z_]+)\s*:\s*(.+?)\s*$", read(f, 2_000_000), re.M):
                src = src or f
                if k.startswith("UILaunchScreen") or k == "UILaunchStoryboardName":
                    gen.setdefault("UILaunchScreen", {})
                else:
                    gen.setdefault(k, {"YES": True, "NO": False}.get(v, v.strip("'\"")))
        elif b == "config.xml" and ios_path(f):
            for k, v in re.findall(r'target="(NS\w+UsageDescription)"[^>]*>\s*(?:<string>)?([^<]*)', read(f, 2_000_000)):
                src = src or f
                gen.setdefault(k, v.strip())
    if gen:
        gen["__generated__"] = True
        out.append((src + BUILD_SETTING_MARK, gen))
    return out


def detect_ios(p: Profile, ctx: dict):
    pbx_files = ctx["pbx"]
    app_projects = []
    for pbx in pbx_files:
        t = read(pbx, 5_000_000)
        types = set(re.findall(r'productType = "([^"]+)"', t))
        if "com.apple.product-type.application" in types:
            app_projects.append(pbx)
        for ty in types:
            label = PRODUCT_TYPES.get(ty)
            if label in ("unit test", "UI test"):
                p.add("test:Xcode " + label + " target", True, "certain", p.rel(pbx))
            elif label and label != "app":
                p.add("target:" + label, True, "certain", p.rel(pbx))
        fam = set(re.findall(r'TARGETED_DEVICE_FAMILY = "?([0-9,]+)"?;', t))
        devices = set()
        for f in fam:
            for d in f.split(","):
                devices.add({"1": "iPhone", "2": "iPad", "3": "TV", "4": "Watch",
                             "6": "Mac (Catalyst)", "7": "Vision"}.get(d.strip(), d))
        if devices:
            p.add("target:devices", sorted(devices), "certain", p.rel(pbx))
        if re.search(r"SUPPORTS_MACCATALYST = YES", t):
            p.add("target:Mac Catalyst", True, "certain", p.rel(pbx))
        m = re.search(r'SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD = (YES|NO)', t)
        if m:
            p.add("target:iPhone/iPad app on Mac", m.group(1) == "YES", "certain", p.rel(pbx))
        m = re.search(r'SUPPORTS_XR_DESIGNED_FOR_IPHONE_IPAD = (YES|NO)', t)
        if m:
            p.add("target:iPhone/iPad app on Vision Pro", m.group(1) == "YES", "certain", p.rel(pbx))
        for v in sorted(set(re.findall(r"IPHONEOS_DEPLOYMENT_TARGET = ([0-9.]+);", t))):
            p.add("setting:minimum iOS", v, "certain", p.rel(pbx))
        for v in sorted(set(re.findall(r"PRODUCT_BUNDLE_IDENTIFIER = \"?([A-Za-z0-9.\-$(){}_]+)\"?;", t)))[:6]:
            p.add("setting:bundle id", v, "certain", p.rel(pbx))
        vers = sorted(set(v.strip('"') for v in re.findall(r"MARKETING_VERSION = ([^;]+);", t)))
        if vers:
            p.add("setting:version (MARKETING_VERSION)", vers, "certain", p.rel(pbx))
    if pbx_files and not app_projects:
        p.add("target:app target", "not found", "unknown", p.rel(pbx_files[0]))
    if not pbx_files:
        p.add("ios:Xcode projesi", "none (not created yet, or the engine generates it)",
              "unknown")

    for ipl, pl in info_plists(p):
        if "/test/" in _inner(ipl).lower() or "Tests/" in _inner(ipl):
            continue
        r = p.rel(ipl.replace(BUILD_SETTING_MARK, "")) + (BUILD_SETTING_MARK if ipl.endswith(BUILD_SETTING_MARK) else "")
        for k, label in USAGE_KEYS.items():
            if k in pl:
                p.add("permission:" + label, str(pl[k])[:80], "certain", r)
        for mode in pl.get("UIBackgroundModes", []) or []:
            p.add("background:" + str(mode), True, "certain", r)
        if "ITSAppUsesNonExemptEncryption" in pl:
            p.add("store:encryption declaration (ITSAppUsesNonExemptEncryption)",
                  pl["ITSAppUsesNonExemptEncryption"], "certain", r)
        ext = (pl.get("NSExtension") or {}).get("NSExtensionPointIdentifier")
        if ext:
            p.add("target:" + EXT_POINTS.get(ext, ext), True, "certain", r)
        locs = pl.get("CFBundleLocalizations")
        if locs:
            p.add("lang:Info.plist CFBundleLocalizations", locs, "certain", r)
        if pl.get("UIRequiresFullScreen"):
            p.add("setting:UIRequiresFullScreen", True, "certain", r)
        orient = pl.get("UISupportedInterfaceOrientations")
        if orient:
            p.add("setting:orientations (iPhone)", [o.replace("UIInterfaceOrientation", "") for o in orient], "certain", r)
        if pl.get("NSAppTransportSecurity", {}).get("NSAllowsArbitraryLoads"):
            p.add("network:ATS relaxed (NSAllowsArbitraryLoads)", True, "certain", r)
        if pl.get("LSApplicationQueriesSchemes"):
            p.add("setting:queried URL schemes", pl["LSApplicationQueriesSchemes"][:8], "certain", r)

    for ent in find(p, lambda f: f.endswith(".entitlements") and ios_path(f)):
        pl = load_plist(ent)
        if not isinstance(pl, dict):
            continue
        r = p.rel(ent)
        for k in pl:
            label = {
                "com.apple.developer.applesignin": "capability:Sign in with Apple",
                "aps-environment": "capability:remote notifications (push)",
                "com.apple.developer.healthkit": "capability:HealthKit",
                "com.apple.developer.icloud-container-identifiers": "capability:iCloud",
                "com.apple.developer.ubiquity-container-identifiers": "capability:iCloud Drive",
                "com.apple.developer.in-app-payments": "capability:Apple Pay",
                "com.apple.developer.associated-domains": "capability:associated domains",
                "com.apple.developer.family-controls": "capability:Family Controls",
                "com.apple.developer.networking.networkextension": "capability:Network Extension (VPN etc.)",
                "com.apple.developer.homekit": "capability:HomeKit",
                "com.apple.developer.nfc.readersession.formats": "capability:NFC",
                "com.apple.developer.weatherkit": "capability:WeatherKit",
                "com.apple.security.application-groups": "capability:App Group",
                "com.apple.developer.usernotifications.time-sensitive": "capability:time-sensitive notifications",
                "com.apple.developer.usernotifications.critical-alerts": "capability:critical alerts",
            }.get(k)
            if label:
                p.add(label, True, "certain", r)

    manifests = find(p, lambda f: name(f) == "PrivacyInfo.xcprivacy" and ios_path(f) and "/Pods/" not in f)
    if manifests:
        p.add("store:privacy manifest", [p.rel(m) for m in manifests][:6], "certain")
    elif pbx_files:
        p.add("store:privacy manifest", "not found in the app", "certain")

    icons = find(p, lambda f: f.endswith(".appiconset/Contents.json") and ios_path(f))
    if icons:
        p.add("store:app icon set", [p.rel(i) for i in icons][:4], "certain")
    xcstrings = find(p, lambda f: f.endswith(".xcstrings"))
    if xcstrings:
        p.add("lang:String Catalog (.xcstrings)", [p.rel(x) for x in xcstrings][:4], "certain")
    lproj = sorted({os.path.basename(os.path.dirname(f))[:-6]
                    for f in p.files if os.path.dirname(f).endswith(".lproj")})
    lproj = [l for l in lproj if l and l != "Base"]
    if lproj:
        p.add("lang:.lproj folders", lproj, "certain")
    storekit = find(p, lambda f: f.endswith(".storekit"))
    if storekit:
        p.add("purchase:StoreKit configuration file", [p.rel(s) for s in storekit], "certain")


# ------------------------------------------------------------- dependencies

# (key, pattern): the pattern is searched in dependency text. Keys are internal ids; see the module docstring.
DEPENDENCY_SIGNS = [
    ("in-app purchase", r"com\.unity\.purchasing|\bin_app_purchase\b|purchases_flutter|react-native-iap|react-native-purchases|"
                   r"RevenueCat|expo-in-app-purchases|flutter_inapp_purchase|\"purchases\"|Adapty|Qonversion|"
                   r"cordova-plugin-purchase|@capgo/capacitor-purchases|SwiftyStoreKit|Glassfy"),
    ("ads", r"com\.unity\.ads|com\.google\.ads|google_mobile_ads|Google-Mobile-Ads|GoogleMobileAds|react-native-google-mobile-ads|"
               r"AppLovin|applovin|ironsource|IronSource|UnityAds|unity_ads|FBAudienceNetwork|"
               r"Vungle|InMobi|chartboost|Chartboost|AdMob|admob"),
    ("sign-in:Firebase Auth", r"firebase_auth|FirebaseAuth|@react-native-firebase/auth|firebase/auth"),
    ("sign-in:with Google", r"google_sign_in|GoogleSignIn|@react-native-google-signin"),
    ("sign-in:with Facebook", r"flutter_facebook_auth|FBSDKLoginKit|FacebookLogin|react-native-fbsdk"),
    ("sign-in:with Apple", r"sign_in_with_apple|expo-apple-authentication|@invertase/react-native-apple-authentication|"
                        r"AuthenticationServices"),
    ("sign-in:Supabase/Auth0/Clerk/Amplify", r"supabase|auth0|Auth0|@clerk/|aws-amplify|Amplify"),
    ("network:HTTP client", r"\bdio\b|\bhttp:\s|\"axios\"|Alamofire|Moya|ktor-client|graphql|apollo|"
                          r"retrofit|grpc|socket_io|socket.io|web_socket_channel|Starscream"),
    ("network:Firebase/BaaS", r"cloud_firestore|firebase_database|FirebaseFirestore|@react-native-firebase/firestore|"
                         r"supabase_flutter|appwrite|parse_server_sdk|Realm.*Sync"),
    ("tracking/analytics", r"firebase_analytics|FirebaseAnalytics|@react-native-firebase/analytics|Mixpanel|mixpanel|"
                       r"amplitude|Amplitude|appsflyer|AppsFlyer|adjust_sdk|Adjust|Branch|branch_sdk|"
                       r"facebook_app_events|FBSDKCoreKit|Segment|segment_analytics|posthog|PostHog|"
                       r"singular|Singular|kochava"),
    ("Firebase (product unclear)", r"firebase-ios-sdk|firebase_core|@react-native-firebase/app"),
    ("crash reporting", r"firebase_crashlytics|FirebaseCrashlytics|sentry|Sentry|bugsnag|Bugsnag|instabug|Datadog"),
    ("AI", r"openai|anthropic|google_generative_ai|generative-ai|firebase_vertexai|firebase_ai|"
                   r"langchain|dart_openai|ollama|mistral|cohere|replicate|huggingface|groq|"
                   r"FoundationModels|CoreML|mlkit|google_mlkit|tflite|onnx"),
    ("notifications:remote", r"firebase_messaging|FirebaseMessaging|@react-native-firebase/messaging|OneSignal|onesignal|"
                      r"expo-notifications|pusher|Pushwoosh|braze|Braze|Airship"),
    ("notifications:local", r"flutter_local_notifications|awesome_notifications|@notifee|notifee|"
                       r"react-native-push-notification|UserNotifications"),
    ("location", r"geolocator|location:|CoreLocation|react-native-geolocation|expo-location|"
              r"@capacitor/geolocation|background_location|google_maps_flutter|react-native-maps|MapKit|mapbox"),
    ("camera/media", r"\bcamera:|image_picker|AVFoundation|react-native-vision-camera|expo-camera|"
                     r"expo-image-picker|PhotosUI|photo_manager|mobile_scanner|qr_code_scanner"),
    ("health", r"\bhealth:|HealthKit|react-native-health|@kingstinct/react-native-healthkit|health_kit"),
    ("database", r"\bdrift\b|sqflite|\bhive\b|isar|objectbox|realm|Realm|CoreData|SwiftData|GRDB|"
                   r"WatermelonDB|@nozbe|react-native-mmkv|AsyncStorage|async-storage|expo-sqlite|"
                   r"sqldelight|Room|shared_preferences|UserDefaults"),
    ("biometric lock", r"local_auth|LocalAuthentication|react-native-biometrics|expo-local-authentication"),
    ("payment (physical goods/services)", r"stripe|Stripe|braintree|Braintree|paypal|PayPal|iyzico|adyen|Adyen|"
                                r"square|razorpay|apple_pay|pay:"),
    ("webview", r"webview_flutter|flutter_inappwebview|WKWebView|react-native-webview|SFSafariViewController"),
    ("kids/parental", r"SuperAwesome|kidoz|PRIVO|kids_safe"),
    ("crypto", r"\bweb3\b|\bethers\b|walletconnect|WalletConnect|\bsolana\b|\bbitcoin\b|BitcoinKit|web3dart"),
]

# Hints searched in code (not visible in dependencies)
CODE_SIGNS = [
    ("ads", r"UnityEngine\.Advertisements|GoogleMobileAds\.Api|MaxSdk\.|IronSource\.Agent"),
    # "import StoreKit" ALONE is not a purchase (SKOverlay and review requests use it too).
    ("in-app purchase", r"UnityEngine\.Purchasing|Product\.products\(|SKPaymentQueue|Transaction\.currentEntitlements|"
                   r"SKProductsRequest|\.purchase\(\s*(options|product)|StoreView\(|SubscriptionStoreView|"
                   r"ProductView\(|InAppPurchase\.instance|purchaseStream"),
    ("account deletion hint", r"(?i)delete[_ ]?account|deleteAccount|hesab[ıi]\s*sil|deleteUser\("),
    ("user content hint", r"(?i)\breport[_ ]?(user|post|content|comment|account)|\bblock[_ ]?(user|account)|flagContent|"
                                r"\bmoderation\b|\bugc\b|createPost|uploadPost|postComment|publishPost|"
                                r"submitComment|\.createComment\(\s*\{|sendChatMessage"),
    ("account hint", r"ASWebAuthenticationSession|\boauth|OAuth2?|signInWith|func (sign_?in|log_?in)\b|"
                    r"\b(signIn|logIn|login)\(|createAccount|register\(email|FirebaseAuth\.instance"),
    ("AI hint", r"api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis|"
                         r"chat/completions|/v1/messages|LanguageModelSession"),
    ("network request hint", r"\bhttp\.(get|post|put|delete)\(|URLSession\.shared\.(data|dataTask)|"
                        r"\bfetch\(\s*[`'\"]https?:|axios\.(get|post)|Dio\(\)|HttpClient\(\)|"
                        r"AF\.request|WebSocket\(|URLSessionWebSocketTask"),
    ("subscription hint", r"SubscriptionStoreView|autoRenewable|auto[_-]renewable|subscriptionGroupID|"
                       r"subscriptionPeriod|SubscriptionPeriod|introductoryOffer|SKProductSubscriptionPeriod|"
                       r"subscriptionOfferDetails|PurchasesPackage|entitlements\.active"),
    ("tracking denial hint", r"requestTrackingAuthorization|ATTrackingManager|app_tracking_transparency"),
    ("review request", r"SKStoreReviewController|requestReview|in_app_review|expo-store-review|"
                             r"react-native-rate"),
    ("private API hint", r"(?i)\b_UI[A-Z]\w+|valueForKey:@\"_|NSClassFromString\(@?\"_"),
]


def detect_capabilities(p: Profile, ctx: dict):
    deps = ctx["deps"]
    for key, pat in DEPENDENCY_SIGNS:
        m = re.search(pat, deps)
        if m:
            p.add("capability:" + key, " ".join(m.group(0).split())[:40], "hint", "dependency file")

    code_files = [f for f in p.files if os.path.splitext(f)[1] in CODE_EXT
                  and "/test" not in _inner(f).lower() and "generated" not in _inner(f).lower()
                  and not f.endswith((".g.dart", ".freezed.dart", ".min.js"))
                  and not re.search(r"(?i)/(vendor|third_?party|public|assets)/", _inner(f))]  # bundled web libraries
    budget = 6000
    hits: dict[str, tuple[str, str]] = {}
    for f in code_files[:budget]:
        t = read(f, 200_000)
        for key, pat in CODE_SIGNS:
            if key in hits:
                continue
            m = re.search(pat, t)
            if m:
                hits[key] = (p.rel(f), " ".join(m.group(0).split())[:50])
        if len(hits) == len(CODE_SIGNS):
            break
    if len(code_files) > budget:
        p.add("note:code search", f"{budget}/{len(code_files)} files scanned", "hint")
    for key, (where, snippet) in hits.items():
        p.add("capability:" + key, snippet, "hint", where)


# ------------------------------------------------------------------ localization

def detect_l10n(p: Profile):
    arbs = find(p, lambda f: f.endswith(".arb"))
    if arbs:
        langs = sorted({re.sub(r"^.*?_([a-zA-Z]{2,3}(?:_[A-Za-z]+)?)\.arb$", r"\1", name(a))
                        for a in arbs if re.search(r"_[a-zA-Z]{2,3}(?:_[A-Za-z]+)?\.arb$", name(a))})
        p.add("lang:Flutter .arb", langs or [p.rel(a) for a in arbs[:4]], "certain", p.rel(arbs[0]))
    loc_json = find(p, lambda f: re.search(r"/(locales?|i18n|translations|lang)/", _inner(f))
                    and f.endswith((".json", ".yml", ".yaml")))
    if loc_json:
        langs = set()
        for f in loc_json:
            parts = p.rel(f).replace("\\", "/").split("/")
            cands = parts[-2:-1] + [os.path.splitext(parts[-1])[0]]
            for c in cands:
                if re.fullmatch(r"[a-z]{2,3}([_-][A-Za-z]{2,4})?", c):
                    langs.add(c)
                    break
        p.add("lang:web/RN translation files", sorted(langs) or len(loc_json), "certain", p.rel(loc_json[0]))
    rtl = {"ar", "he", "fa", "ur"}
    found = set()
    for k, v in p.items.items():
        if k.startswith("lang:") and isinstance(v["value"], list):
            found |= {str(x).split("_")[0].split("-")[0].lower() for x in v["value"]}
    if found & rtl:
        p.add("lang:right-to-left language", sorted(found & rtl), "certain")
    if not any(k.startswith("lang:") for k in p.items):
        p.add("lang:localization setup", "not found (one language, strings in code)", "hint")


# ------------------------------------------------------------------ tests

def detect_tests(p: Profile):
    signs = [
        ("Flutter unit/widget test", lambda f: "/test/" in _inner(f) and f.endswith("_test.dart")),
        ("Flutter integration test", lambda f: "/integration_test/" in _inner(f) and f.endswith(".dart")),
        ("Patrol", lambda f: "/patrol_test/" in f),
        ("XCTest", lambda f: f.endswith(".swift") and re.search(r"Tests?/", _inner(f)) is not None),
        ("Jest", lambda f: re.search(r"\.(test|spec)\.(t|j)sx?$", f) is not None),
        ("Detox", lambda f: name(f) in (".detoxrc.js", ".detoxrc.json", "detox.config.js")),
        ("Maestro", lambda f: "/.maestro/" in f or "/maestro/" in f and f.endswith(".yaml")),
        ("Kotlin test", lambda f: "/commonTest/" in f or "/iosTest/" in f),
    ]
    any_test = False
    for label, pred in signs:
        hits = [f for f in p.files if pred(f)]
        if hits:
            any_test = True
            p.add("test:" + label, len(hits), "certain", p.rel(hits[0]))
    if not any_test:
        p.add("test:infrastructure", "not found", "certain")
    ci = find(p, lambda f: "/.github/workflows/" in f or name(f) in (
        ".gitlab-ci.yml", "bitrise.yml", "codemagic.yaml", "Fastfile", ".circleci", "ci_post_clone.sh"))
    if ci:
        p.add("test:CI", [p.rel(c) for c in ci][:4], "certain")


# ------------------------------------------------------------------ unknowns

UNKNOWN = [
    ("unknown:target age / Kids category", "1.3, 5.1.4: only content-safety / privacy ask"),
    ("unknown:regulated domain (health, finance, crypto, gambling, VPN)",
     "5.x, 3: only product-fit asks"),
    ("unknown:store countries", "regional payment and content rules: monetization / store-readiness ask"),
    ("unknown:demo account for review", "2.1: store-readiness asks, only if there is an account"),
]


def build(root: str) -> Profile:
    p = Profile(root)
    walk(p)
    ctx = detect_tech(p)
    detect_ios(p, ctx)
    detect_capabilities(p, ctx)
    detect_l10n(p)
    detect_tests(p)
    for k, why in UNKNOWN:
        p.add(k, why, "unknown")
    if p.truncated:
        p.add("note:file limit", f"first {MAX_FILES} files scanned", "hint")
    return p


def summary_flags(p: Profile) -> dict:
    """Flat flags so members can decide quickly. Flag names are internal ids (see the module docstring)."""
    keys = p.items.keys()

    def has(prefix):
        return any(k.startswith(prefix) for k in keys)

    return {
        "purchases": has("capability:in-app purchase") or has("purchase:"),
        "subscriptions": has("capability:subscription"),
        "ads": has("capability:ads"),
        "account": has("capability:sign-in") or has("capability:Sign in with Apple") or has("capability:account hint"),
        "third_party_login": any(k.startswith("capability:sign-in:") and "Apple" not in k for k in keys),
        "network": has("capability:network:") or has("capability:network request") or has("capability:sign-in")
              or has("capability:notifications:remote") or has("capability:AI hint"),
        "tracking": has("capability:tracking") or has("permission:tracking"),
        "ai": has("capability:AI"),
        "user_content": has("capability:user content"),
        "permissions": sorted(k.split(":", 1)[1] for k in keys if k.startswith("permission:")),
        "platforms": sorted(set(p.items.get("target:devices", {}).get("value") or [])
                              | {k.split(":", 1)[1] for k in keys
                                 if k.startswith("target:") and ("Mac" in k or "Vision" in k)
                                 and p.items[k]["value"] is True}),
        "extensions": sorted(k.split(":", 1)[1] for k in keys if k.startswith("target:")
                            and k != "target:devices" and "Mac" not in k and "Vision" not in k
                            and k != "target:app target"),
        "languages": sorted({str(x).split("_")[0].split("-")[0].lower()
                          for k, v in p.items.items()
                          if k.startswith("lang:") and k != "lang:right-to-left language"
                          and isinstance(v["value"], list)
                          for x in v["value"] if re.fullmatch(r"[A-Za-z]{2,3}([_-][A-Za-z]+)?", str(x))
                          and str(x).lower() not in ("qqq", "qps", "base", "dev")}),
        "has_tests": "test:infrastructure" not in keys,
        "privacy_manifest": isinstance(p.items.get("store:privacy manifest", {}).get("value"), list),
    }


def to_markdown(p: Profile) -> str:
    out = [f"# App profile: `{p.root}`", ""]
    groups: dict[str, list] = {}
    for k, v in sorted(p.items.items()):
        g, _, label = k.partition(":")
        groups.setdefault(g, []).append((label, v))
    order = ["tech", "target", "setting", "capability", "permission", "background", "network", "purchase",
             "lang", "store", "test", "ios", "unknown", "note"]
    for g in order + [g for g in groups if g not in order]:
        if g not in groups:
            continue
        out.append(f"## {g}")
        for label, v in groups[g]:
            val = v["value"]
            if isinstance(val, list):
                val = ", ".join(map(str, val))
            ev = f" (`{display(v['evidence'][0])}`)" if v["evidence"] else ""
            out.append(f"- **{display(label)}**: {val} _({v['confidence']})_{ev}")
        out.append("")
    out.append("## summary flags")
    for k, v in display_flags(summary_flags(p)).items():
        out.append(f"- {k}: {v}")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="apptest app profile (read-only)")
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.root):
        print(f"Folder not found: {a.root}", file=sys.stderr)
        return 2
    p = build(a.root)
    if a.json:
        items = {display_key(k): dict(v, evidence=[display(e) for e in v["evidence"]]) for k, v in p.items.items()}
        json.dump({"root": p.root, "items": items, "flags": display_flags(summary_flags(p))},
                  sys.stdout, ensure_ascii=False, indent=1, default=str)
        print()
    else:
        print(to_markdown(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ------------------------------------------------------------ Release configuration
# (Defined after main() on purpose: importing scripts call these.)

_RELEASE_NAME = re.compile(r"(?i)release|appstore|app store|production|\bprod\b|distribution")
# Non-store flavor names: if one appears in a file / icon / target name and a flavorless twin
# exists, it is assumed not to ship (e.g. Wikipedia: Alpha-, Experimental-, Local-Info.plist).
FLAVOR = re.compile(r"(?i)(alpha|beta|experimental|local|debug|\bdev\b|develop|staging|stage|test|"
                    r"internal|enterprise|\bqa\b|sandbox|nightly|canary|preview)")


def build_configs(pbx_text: str):
    """(settings_text, configuration_name): XCBuildConfiguration blocks (by counting braces)."""
    for m in re.finditer(r"isa = XCBuildConfiguration;\s*buildSettings = \{", pbx_text):
        i, depth = m.end(), 1
        while depth and i < len(pbx_text):
            c = pbx_text[i]
            depth += (c == "{") - (c == "}")
            i += 1
        nm = re.match(r'\s*;\s*name = "?([^;"]+)"?;', pbx_text[i:i + 200])
        yield pbx_text[m.end():i - 1], (nm.group(1) if nm else "?")


def release_settings(p: "Profile") -> dict:
    """Info.plist files and icon names in Release configurations (flavors included;
    filtered in shipping_info_plists / primary_icon_names)."""
    plists, icons = set(), set()
    for pbx in p.files:
        if not pbx.endswith("project.pbxproj") or not ios_path(pbx) or "/Pods/" in pbx:
            continue
        srcroot = os.path.dirname(os.path.dirname(pbx))
        for body, cname in build_configs(read(pbx, 8_000_000)):
            if not _RELEASE_NAME.search(cname):
                continue
            m = re.search(r'(?<![A-Z_])INFOPLIST_FILE = "?([^";]+)"?;', body)
            if m:
                path = re.sub(r"^\$[({]SRCROOT[)}]/", "", m.group(1).strip())
                plists.add(os.path.normpath(os.path.join(srcroot, path)))
            m = re.search(r'ASSETCATALOG_COMPILER_APPICON_NAME = "?([^";]+)"?;', body)
            if m:
                icons.add(m.group(1).strip())
    return {"info_plists": plists, "icon_names": icons}


def is_app_plist_dict(pl: dict) -> bool:
    """Is this an app Info.plist (not an extension, watch, framework or test bundle)?"""
    if any(k in pl for k in ("NSExtension", "WKApplication", "WKWatchKitApp", "EXAppExtensionAttributes")):
        return False
    return str(pl.get("CFBundlePackageType", "APPL")) not in ("FMWK", "BNDL", "XPC!", "AAPL-FMWK")


def is_bundle_plist_dict(pl: dict) -> bool:
    """Framework or test bundle: stays out of store checks."""
    return str(pl.get("CFBundlePackageType", "")) in ("FMWK", "BNDL", "XPC!")


def _flavor(path: str) -> bool:
    path = _inner(path)
    return bool(FLAVOR.search(os.path.basename(path).replace("Info.plist", "")))


def shipping_info_plists(p: "Profile") -> list:
    """Info.plists that ship to the store: extensions + Xcode-generated keys + app plists; from the app plists,
    (1) those unused in Release (when that can be determined) and (2) flavor plists with a flavorless twin are removed."""
    allp = info_plists(p)
    rel = release_settings(p)["info_plists"]
    # Test bundles stay out of the selection; otherwise they eliminate the app's plist (e.g. Mastodon UITests).
    is_test = re.compile(r"(?i)(^|/)\w*tests?/|tests?_info")
    apps = [f for f, pl in allp if is_app_plist_dict(pl) and not f.endswith(BUILD_SETTING_MARK) and not is_test.search(_inner(f))]
    # Filter per project: one repo can hold several apps (e.g. Ente: one app's Release plist
    # eliminated the Flutter Runner's).
    roots = sorted({os.path.dirname(os.path.dirname(x)) for x in p.files
                    if x.endswith(".xcodeproj/project.pbxproj") and ios_path(x)}, key=len, reverse=True)
    groups: dict = {}
    for f in apps:
        owner = next((r for r in roots if f.startswith(r + "/")), "")
        groups.setdefault(owner, []).append(f)
    keep = set()
    for members in groups.values():
        chosen = [f for f in members if os.path.normpath(f) in rel] or members
        plain = [f for f in chosen if not _flavor(f)]
        keep |= set(plain or chosen)
    return [(f, pl) for f, pl in allp
            if not is_bundle_plist_dict(pl) and not re.search(r"(?i)(^|/)\w*tests?/|tests?_info", _inner(f))
            and (f.endswith(BUILD_SETTING_MARK) or not is_app_plist_dict(pl) or f in keep)]


def extension_dirs(p: "Profile") -> list:
    return [os.path.dirname(f) for f, pl in info_plists(p)
            if not f.endswith(BUILD_SETTING_MARK) and not is_app_plist_dict(pl)]


def primary_icon_names(p: "Profile") -> set:
    # AppIcon${BUNDLE_ID_SUFFIX}: the variable is empty in release builds (e.g. Home Assistant).
    names = {re.sub(r"\$[({]\w+[)}]", "", n) for n in release_settings(p)["icon_names"]} or {"AppIcon"}
    plain = {n for n in names if not FLAVOR.search(n)}
    return plain or names
