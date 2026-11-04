#!/usr/bin/env python3
"""apptest-privacy-permissions — static scan (usage descriptions, when permissions
are asked, tracking / ATT, privacy manifest, data sent to AI, privacy policy).

Standard library only; does NOT write to the project. The output is CANDIDATES
(verified against the PP-xx IDs in SKILL.md).

    python3 -I privacy_scan.py <project_root> [--json] [--policy-url URL]

--policy-url: reads the public privacy policy page with GET (read-only) and checks
whether it mentions what the app does. Without a URL, a privacy link found in the
code is suggested but NOT read.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import os
import re
import sys
import urllib.request

_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apptest", "shared", "scanlib.py")
_s = importlib.util.spec_from_file_location("apptest_scanlib", _p)
scan = importlib.util.module_from_spec(_s)
_s.loader.exec_module(scan)

# capability → (required Info.plist keys [any one is enough], code pattern, dependency pattern)
CAPS = {
    "camera": (["NSCameraUsageDescription"],
               r"AVCaptureDevice|AVCaptureSession|sourceType\s*=\s*\.camera|\.camera\b[^\n]*UIImagePickerController|"
               r"ImageSource\.camera|launchCamera|takePictureAsync|DataScannerViewController|"
               r"MediaPicker(\.Default)?\.Capture|CameraView|ZXing|BarcodeReader|CameraBarcodeReaderView",
               r"\bcamera:|mobile_scanner|qr_code_scanner|react-native-vision-camera|expo-camera|"
               r"react-native-camera|@capacitor/camera|barcode_scan"),
    "photo library (read)": (["NSPhotoLibraryUsageDescription"],
               r"PHPhotoLibrary\.(requestAuthorization|authorizationStatus)|PHAsset\.fetch|ALAssetsLibrary|"
               r"MediaLibrary\.|PHAssetCollection\.fetch|PHImageManager",
               # System pickers (PHPickerViewController, SwiftUI PhotosPicker, picking from the library with iOS 11+
               # UIImagePickerController) run in a separate process and need NO permission (e.g. Element X PhotosPicker,
               # no description, live). Flutter image_picker / RN pickers are only a dependency hint (SUGGESTION).
               r"image_picker|photo_manager|expo-media-library|react-native-image-picker|"
               r"@react-native-camera-roll|expo-image-picker"),
    "saving to photos": (["NSPhotoLibraryAddUsageDescription", "NSPhotoLibraryUsageDescription"],
               r"UIImageWriteToSavedPhotosAlbum|UISaveVideoAtPathToSavedPhotosAlbum|creationRequestForAsset|"
               r"PHAssetCreationRequest|ImageGallerySaver|saveToLibraryAsync|CameraRoll\.save",
               r"image_gallery_saver|gallery_saver|gal:"),
    "location": (["NSLocationWhenInUseUsageDescription", "NSLocationAlwaysAndWhenInUseUsageDescription"],
              r"requestWhenInUseAuthorization|requestAlwaysAuthorization|startUpdatingLocation|CLLocationUpdate|"
              r"Geolocator\.|(?<![\w])getCurrentPosition(Async)?\(|requestForegroundPermissionsAsync|(?<![\w])watchPosition\(|"
              r"Geolocation(\.Default)?\.GetLocationAsync",
              r"geolocator|\blocation:|expo-location|react-native-geolocation|@capacitor/geolocation|"
              r"background_location|flutter_background_geolocation"),
    "microphone": (["NSMicrophoneUsageDescription"],
                 r"AVAudioRecorder|requestRecordPermission|AVAudioApplication\.requestRecordPermission|"
                 r"\.record\b[^\n]*AVAudioSession|setCategory\(\s*\.(playAndRecord|record)|Audio\.Recording|startRecording",
                 r"\brecord:|flutter_sound|speech_to_text|audio_recorder|expo-av|react-native-audio-recorder|"
                 r"@react-native-voice"),
    "contacts": (["NSContactsUsageDescription"], r"CNContactStore|ContactsService|Contacts\.getContacts|getAll\(\)[^\n]*Contacts",
                r"flutter_contacts|contacts_service|expo-contacts|react-native-contacts"),
    "calendar": (["NSCalendarsFullAccessUsageDescription", "NSCalendarsWriteOnlyAccessUsageDescription",
                "NSCalendarsUsageDescription", "NSRemindersFullAccessUsageDescription", "NSRemindersUsageDescription"],
                # EKEventStore is used for reminders too (e.g. Home Assistant).
               r"EKEventStore|requestFullAccessToEvents|requestWriteOnlyAccessToEvents|Calendar\.requestCalendarPermissions",
               r"device_calendar|expo-calendar|add_2_calendar|react-native-calendar-events"),
    "health": (["NSHealthShareUsageDescription", "NSHealthUpdateUsageDescription"], r"HKHealthStore",
               r"\bhealth:|react-native-health|@kingstinct/react-native-healthkit"),
    "bluetooth": (["NSBluetoothAlwaysUsageDescription"], r"CBCentralManager|CBPeripheralManager",
                  r"flutter_blue|flutter_blue_plus|react-native-ble|bluetooth"),
    "Face ID": (["NSFaceIDUsageDescription"], r"LAContext\(\)|evaluatePolicy|biometryType|LocalAuthentication\.authenticate",
                r"local_auth|expo-local-authentication|react-native-biometrics|react-native-touch-id"),
    "speech recognition": (["NSSpeechRecognitionUsageDescription"], r"SFSpeechRecognizer|SpeechRecognizer\(",
                       r"speech_to_text|@react-native-voice|expo-speech-recognition"),
    "motion (steps/activity)": (["NSMotionUsageDescription"], r"CMPedometer|CMMotionActivityManager|CMAltimeter",
                                r"pedometer|expo-sensors"),
    "tracking permission (ATT)": (["NSUserTrackingUsageDescription"],
                         r"requestTrackingAuthorization|ATTrackingManager|AppTrackingTransparency\.request",
                         r"app_tracking_transparency|expo-tracking-transparency|react-native-tracking-transparency"),
    "local network": (["NSLocalNetworkUsageDescription"], r"NWBrowser|NetServiceBrowser|NWListener|DNSServiceBrowse|multicast",
                 r"multicast_dns|bonsoir|react-native-zeroconf"),
    "NFC": (["NFCReaderUsageDescription"], r"NFCNDEFReaderSession|NFCTagReaderSession", r"nfc_manager|react-native-nfc-manager"),
    "media library": (["NSAppleMusicUsageDescription"], r"MPMediaLibrary|MPMediaQuery", r"on_audio_query"),
    "HomeKit": (["NSHomeKitUsageDescription"], r"HMHomeManager", r"homekit"),
}
# Vague = states no PURPOSE. "needs access to your photos to let you add images" states the purpose: not vague
# (e.g. AppFlowy, live). Vague if the pattern is not followed by a purpose ("to / so / for", or the Turkish equivalents).
# Test: does a purpose follow "access (to your X)" with to / so / for / when (e.g. Signal "needs access to your
# microphone to make and receive calls"); keeping a verb list was always incomplete.
VAGUE = re.compile(r"(?i)^(?!.*\baccess( to (your |the )?[\w' ]{1,40}?)?\s+(to|so|for|when|in order)\b)"
                   r"(?!.*\b(için|amacıyla)\b).*(needs? (your )?access|"
                   r"requires? (your )?access|for (app )?functionality|app (wants|would like) to|to work properly|"
                   r"erişim gerek|erişmesi gerek|izin gerek|\$\(PRODUCT_NAME\) (needs|requires))")
REQUEST_CALL = r"requestWhenInUseAuthorization|requestAlwaysAuthorization|requestTrackingAuthorization|" \
               r"requestAccess\(|requestRecordPermission|requestFullAccessToEvents|PHPhotoLibrary\.requestAuthorization|" \
               r"UNUserNotificationCenter\.current\(\)\.requestAuthorization|requestAuthorization\(options|" \
               r"Permission\.\w+\.request\(|requestPermission\(|request\w*PermissionsAsync\(|" \
               r"AppTrackingTransparency\.request"
# registerForRemoteNotifications does NOT open a permission prompt (it only gets a device token): deliberately absent.
ENTRY_FILES = re.compile(r"(AppDelegate|SceneDelegate|\w+App)\.swift$|/main\.dart$|/app\.dart$|"
                         r"/App\.(t|j)sx?$|/index\.(t|j)sx?$|/_layout\.(t|j)sx?$|MauiProgram\.cs$|AppDelegate\.cs$")
TRACKING_SDK = re.compile(r"appsflyer|AppsFlyer|adjust_sdk|\bAdjust\b|branch_sdk|Branch\b|FBSDKCoreKit|facebook_app_events|"
                          r"react-native-fbsdk|google_mobile_ads|GoogleMobileAds|AppLovin|applovin|IronSource|ironsource|"
                          r"UnityAds|com\.unity\.ads|singular|kochava|Tenjin|tenjin")
_CONSENT = scan.terms.rx("ai_consent")[4:]
_AI_NAMES = scan.terms.rx_case("ai") + "|OpenAI|ChatGPT|Gemini|Claude|LLM|third[- ]party|üçüncü taraf|yapay zek|künstliche intelligenz|intelligenza artificiale|inteligencia artificial"
AI_CONSENT = re.compile(rf"(?i)({_CONSENT})[^\n]{{0,80}}({_AI_NAMES})|({_AI_NAMES})[^\n]{{0,80}}({_CONSENT}|share|paylaş|teilen|condivid|compart|partag)")
POLICY_TOPICS = {
    "tracking/analytics": (lambda f, p: f["tracking"], scan.terms.rx("policy_analytics")),
    "crash reporting": (lambda f, p: any(k.startswith("capability:crash") for k in p.items), scan.terms.rx("policy_crash")),
    "ads": (lambda f, p: f["ads"], scan.terms.rx("policy_ads")),
    "location": (lambda f, p: any("location" in x for x in f["permissions"]), scan.terms.rx("policy_location")),
    "camera/photos": (lambda f, p: any(x in ("camera", "photos") for x in f["permissions"]), scan.terms.rx("policy_media")),
    "health": (lambda f, p: any("health" in x for x in f["permissions"]), scan.terms.rx("policy_health")),
    "AI": (lambda f, p: f["ai"], scan.terms.rx_case("ai") + "|(?i:artificial intelligence|yapay zek|künstliche intelligenz|intelligenza artificiale|inteligencia artificial|intelligence artificielle|inteligência artificial|language model)|OpenAI|LLM"),
    "account": (lambda f, p: f["account"], scan.terms.rx("policy_account")),
    "account deletion": (lambda f, p: f["account"], scan.terms.rx("policy_delete")),
}


def plist_keys(p) -> dict[str, tuple[str, str]]:
    """Permission keys in the Info.plists of the app (and extensions) + Expo app.json."""
    out: dict[str, tuple[str, str]] = {}
    for f, pl in p.mod.shipping_info_plists(p):  # those that ship to the store (excluding variant / test / framework)
        where = p.rel(f.replace(" (build setting)", "")) + (" (build setting)" if f.endswith("(build setting)") else "")
        for k, v in pl.items():
            if k.endswith("UsageDescription") or k == "NFCReaderUsageDescription":
                out.setdefault(k, (str(v), where))
    for k, v in p.items.items():
        if k.startswith("permission:") and v["evidence"] and v["evidence"][0].endswith("app.json"):
            for key, label in p.mod.USAGE_KEYS.items():
                if label == k.split(":", 1)[1]:
                    out.setdefault(key, (str(v["value"]), v["evidence"][0]))
    # Expo app.config.js / .ts (JS; cannot be read as JSON): ios.infoPlist keys and plugins' permission
    # options (e.g. Bluesky: NSCameraUsageDescription and contactsPermission live here).
    for f in p.files:
        if os.path.basename(f) in ("app.config.js", "app.config.ts", "app.json") and "/node_modules/" not in f:
            t = scan.p_read(f, 1_000_000)
            for m in re.finditer(r"""["']?(NS\w+UsageDescription)["']?\s*:\s*(["'`])(.{0,200}?)\2""", t, re.S):
                out.setdefault(m.group(1), (m.group(3), p.rel(f)))
            for opt, key in EXPO_PERMISSION_OPTIONS.items():
                m = re.search(r"""["']?%s["']?\s*:\s*(["'`])(.{0,200}?)\1""" % opt, t, re.S)
                if m:
                    out.setdefault(key, (m.group(2), p.rel(f) + " › " + opt))
    return out


EXPO_PERMISSION_OPTIONS = {
    "cameraPermission": "NSCameraUsageDescription",
    "microphonePermission": "NSMicrophoneUsageDescription",
    "photosPermission": "NSPhotoLibraryUsageDescription",
    "savePhotosPermission": "NSPhotoLibraryAddUsageDescription",
    "locationWhenInUsePermission": "NSLocationWhenInUseUsageDescription",
    "locationAlwaysAndWhenInUsePermission": "NSLocationAlwaysAndWhenInUseUsageDescription",
    "contactsPermission": "NSContactsUsageDescription",
    "calendarPermission": "NSCalendarsFullAccessUsageDescription",
    "remindersPermission": "NSRemindersFullAccessUsageDescription",
    "faceIDPermission": "NSFaceIDUsageDescription",
    "motionPermission": "NSMotionUsageDescription",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "apptest-privacy-permissions"})
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read(3_000_000).decode("utf-8", "replace")
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--policy-url")
    a = ap.parse_args(argv)
    p = scan.load_profile(a.root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("PP", p, "privacy-permissions scan")
    flags = p.mod.summary_flags(p)
    files = scan.code_files(p)
    deps = "\n".join(scan.p_read(f) for f in p.files if os.path.basename(f) in
                     ("pubspec.yaml", "package.json", "Podfile", "Package.swift", "app.json"))
    deps += "\n".join(re.findall(r'repositoryURL = "([^"]+)"', "\n".join(
        scan.p_read(f, 5_000_000) for f in p.files if f.endswith("project.pbxproj"))))
    keys = plist_keys(p)
    generated_ios = any(t.startswith(("React Native (Expo)", "Unity", "Unreal", "Godot")) for t in scan.techs(p)) \
        or p.mod.ios_project_missing(p)  # no iOS project yet: nowhere to add a description either

    # PP-10 / PP-11
    strings_keys = set()
    for f in p.files:
        if os.path.basename(f).lower() in ("infoplist.strings", "infoplist.xcstrings") and p.mod.ios_path(f):
            strings_keys.update(re.findall(r"\bNS\w+UsageDescription\b", scan.p_read(f, 2_000_000)))

    for cap, (need, code_pat, dep_pat) in CAPS.items():
        c, first = scan.count(p, code_pat, files=files)
        dm = re.search(dep_pat, deps)
        used = c > 0 or dm
        has = [k for k in need if k in keys]
        if used and not has:
            where = f"{p.rel(first[0])}:{first[1]}" if first else f"dependency: {dm.group(0)}"
            # A match in a prebuilt SDK's header is only a hint (e.g. Expensify GIBMobileSdk.xcframework).
            vendored = bool(first) and re.search(r"\.(xc)?framework/|/Frameworks/|/vendor/|/ThirdParty/", first[0])
            sev = "REJECTION RISK" if c > 0 and not vendored and not generated_ios else "SUGGESTION"
            note = ("ITMS-90683 / 5.1.1(ii): if this capability is used a description is required; if missing, the upload is "
                    "rejected or the app crashes on the permission request.")
            localized = [k for k in need if k in strings_keys]
            if localized and c > 0:
                # Seen in a live app (e.g. Mastodon): the text is in a language file, the key is not in the main plist.
                sev = "SUGGESTION"
                note = (f"{localized[0]} was found only in a language file (InfoPlist.strings / .xcstrings), not in the main Info.plist. "
                        "Check the built app's Info.plist and the permission request; this scan cannot decide.")
            if generated_ios:
                note += " The iOS project is generated at build time: the description may come from a plugin / app.json / engine setting (not verified)."
            if c == 0:
                note = "Package present but no use found in code: if it is used a description is required, otherwise the package may be unnecessary."
            rep.add("PP-10", sev, f"No usage description: {cap} ({' / '.join(need)})", where, note)
        if has and not used and cap not in ("Face ID",):
            rep.add("PP-11", "SUGGESTION", f"Usage description present but no use found: {cap}",
                    f"{keys[has[0]][1]} › {has[0]}",
                    "5.1.1(iii): unnecessary permissions get questioned. A package may be using it: not verified.")

    # PP-12: description quality
    for k, (text, where) in keys.items():
        if text.startswith("$(") or not text.strip():
            continue
        if VAGUE.search(text) or len(text.strip()) < 12:
            rep.add("PP-12", "REJECTION RISK", f"Usage description vague or short: {k}", f"{where} › {k} = {text[:60]!r}",
                    "5.1.1(ii): must say concretely WHY it is requested (e.g. 'To photograph your receipt and read the total').")
    if len(flags["languages"]) > 1 and keys:
        loc = [f for f in p.files if os.path.basename(f) in ("InfoPlist.strings", "InfoPlist.xcstrings") and p.mod.ios_path(f)]
        if not loc and not generated_ios:
            rep.add("PP-13", "SUGGESTION", "App is multi-language but usage descriptions are not translated",
                    f"languages: {', '.join(flags['languages'][:8])}", "In every language, with InfoPlist.strings / InfoPlist.xcstrings.")

    # PP-14: asking for permission at launch
    for f, n, line, m in scan.grep(p, REQUEST_CALL, files=[f for f in files if ENTRY_FILES.search(f)]):
        rep.add("PP-14", "SUGGESTION", "Permission may be requested at the app entry point (without context)",
                f"{p.rel(f)}:{n} `{m.group(0)}`",
                "HIG: ask when the user needs that feature; a permission asked at launch is often denied.")

    # PP-20: tracking SDK present, no ATT
    tm = TRACKING_SDK.search(deps)
    att = scan.count(p, CAPS["tracking permission (ATT)"][1], files=files)[0] > 0 or re.search(CAPS["tracking permission (ATT)"][2], deps)
    if tm and not att:
        rep.add("PP-20", "REJECTION RISK", f"Ad / attribution SDK present but tracking permission (ATT) is not requested: {tm.group(0)}",
                "dependency file",
                "5.1.2 / ATT: matching with other companies' data or using IDFA requires permission. If the SDK does not track, "
                "verify it is turned off by configuration and the privacy label says 'Tracking: No' (PP-P1).")

    # PP-21/22: privacy manifest contents
    manifests = [f for f in p.files if os.path.basename(f) == "PrivacyInfo.xcprivacy" and p.mod.ios_path(f)
                 and "/Pods/" not in f and ".framework/" not in f]
    for mf in manifests:
        pl = p.mod.load_plist(mf) or {}
        trk = bool(pl.get("NSPrivacyTracking"))
        domains = pl.get("NSPrivacyTrackingDomains") or []
        collected = pl.get("NSPrivacyCollectedDataTypes") or []
        r = p.rel(mf)
        if trk and not domains:
            rep.add("PP-21", "SUGGESTION", "NSPrivacyTracking is on but the tracking domain list is empty", r,
                    "If tracking domains are not listed, iOS may or may not block connecting to them without permission: see the docs.")
        if tm and not trk:
            rep.add("PP-21", "SUGGESTION", "Tracking SDK present, manifest 'NSPrivacyTracking' is off", r,
                    "Correct if the SDK really does not track; if it does, the manifest and privacy label do not match (PP-P2).")
        if not collected and (flags["tracking"] or flags["account"] or any(k.startswith("capability:crash") for k in p.items)):
            rep.add("PP-22", "SUGGESTION", "No collected data types in the manifest, but analytics / account / crash reporting exist", r,
                    "Collected data must be declared in the manifest and the App Store Connect privacy label (5.1.1, R-43).")

    # PP-30: third-party AI
    if flags["ai"]:
        texts = files + [f for f in p.files if f.endswith((".arb", ".strings", ".xcstrings", ".json"))
                         and re.search(r"(?i)(l10n|locale|i18n|lproj|translations)", f)]
        consent = scan.count(p, AI_CONSENT, files=texts)[0]
        if consent == 0:
            rep.add("PP-30", "REJECTION RISK", "AI is used but no user consent / disclosure was found",
                    "AI dependency / endpoint (profile)",
                    "5.1.2(i): if personal data goes to a third-party AI, disclose it clearly and get EXPLICIT permission. "
                    "A model running on the device (Core ML, Foundation Models) is not a finding: not verified.")
        else:
            rep.add("PP-30", "INFO", "Consent / disclosure text for AI exists", f"{consent} matches",
                    "Verify that consent is obtained BEFORE sending the data and says which data goes to whom.")

    # PP-40/41: health + iCloud, always-on location
    if any("health" in x for x in flags["permissions"]) and any("iCloud" in k for k in p.items):
        rep.add("PP-40", "REJECTION RISK", "Health data and iCloud together", "entitlements",
                "5.1.3: personal health data cannot be stored in iCloud: verify what goes to iCloud.")
    if "location (always)" in flags["permissions"] or "background:location" in p.items:
        rep.add("PP-41", "SUGGESTION", "Background / always-on location", "Info.plist",
                "5.1.5 / 2.5.4: the reason must be clear in the app and the review note; is it really needed?")

    # PP-50: third-party SDK inventory (no guessing, PP-P1)
    sdk_keys = [k.split(":", 1)[1] for k in p.items if k.startswith("capability:") and any(
        s in k for s in ("tracking", "crash", "ads", "sign-in:", "network:Firebase", "Firebase", "AI", "notifications:remote"))]
    if sdk_keys:
        rep.add("PP-50", "INFO", "Third-party components that may collect data (inventory)", ", ".join(sorted(p.mod.display(k) for k in sdk_keys)),
                "Read what each collects from the SDK's docs / privacy manifest; the privacy label and "
                "policy follow from that (PP-P1).")

    # PP-60: privacy policy
    if a.policy_url:
        try:
            text = fetch(a.policy_url)
        except Exception as e:  # noqa: BLE001
            if scan.online():
                rep.add("PP-60", "REJECTION RISK", f"Privacy policy could not be read ({type(e).__name__})", a.policy_url,
                        "5.1.1(i): the link must work.")
            else:
                rep.add("PP-60", "INFO", "No internet: could not check the privacy policy", a.policy_url,
                        "This shows neither that the policy link works nor that it does not; run again with internet.")
            text = ""
        if text:
            for topic, (applies, rx) in POLICY_TOPICS.items():
                if applies(flags, p) and not re.search(rx, text):
                    rep.add("PP-61", "REJECTION RISK", f"App includes '{topic}' but the policy does not mention it",
                            a.policy_url, "5.1.1(i): the policy must describe the data collected, its use and sharing (not verified: "
                            "a synonym may be in use).")
    else:
        urls = sorted({m.group(0) for f, n, l, m in scan.grep(
            p, r"https://[^\s'\"`)]*(privacy|gizlilik|kvkk|datenschutz|privacidad|confidentialit|privacidade)[^\s'\"`)]*", files=files, max_hits=5)})
        rep.skip("PP-61", "policy not read; use --policy-url " + (urls[0] if urls else "<address>"))

    rep.emit(a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
