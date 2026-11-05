"""Seeded defects for tests/detection/run.py. Each project is the smallest thing that shows the defect."""
import struct
import zlib

NOT_TESTED = {
    "PP-60": "needs a live privacy policy address",
    "PP-61": "needs a live privacy policy address",
    "SR-51": "needs network access to open links",
}


# Fake, and assembled at run time so that secret scanners don't take this file for a leak.
FAKE_KEY = "sk_" + "live_" + "abcdefghijklmnopqrstuvwx"


def png(w, h, alpha=False):
    """A valid solid PNG, built by hand so that tests need no image library."""
    kind, depth = (6, 4) if alpha else (2, 3)
    pixel = b"\x10\x20\x30\x80"[:depth] if alpha else b"\x10\x20\x30"
    raw = b"".join(b"\x00" + pixel * w for _ in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, kind, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))


PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>com.example.app</string>
<key>CFBundleShortVersionString</key><string>1.2.0</string>
<key>CFBundleVersion</key><string>7</string>
<key>CFBundleDisplayName</key><string>Example</string>
<key>ITSAppUsesNonExemptEncryption</key><false/>
<key>UILaunchScreen</key><dict/>
%s
</dict></plist>
"""
PBX = """// !$*UTF8*$!
{ objects = {
  A1 /* App */ = { isa = PBXNativeTarget; productType = "com.apple.product-type.application"; name = App; };
  B1 = { isa = XCBuildConfiguration; buildSettings = { IPHONEOS_DEPLOYMENT_TARGET = %s; MARKETING_VERSION = 1.2.0; TARGETED_DEVICE_FAMILY = "1"; SDKROOT = iphoneos; }; };
}; }
"""
ICON = """{ "images": [ { "filename": "icon.png", "idiom": "universal", "platform": "ios", "size": "1024x1024" } ], "info": { "version": 1 } }"""
MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>NSPrivacyTracking</key><false/><key>NSPrivacyCollectedDataTypes</key><array/><key>NSPrivacyAccessedAPITypes</key><array/></dict></plist>
"""


def swift(extra=None, plist="", target="16.0", icon=True, manifest=True, code="""import SwiftUI
@main struct AcmeApp: App { var body: some Scene { WindowGroup { Text("Hello") } } }
"""):
    files = {
        "Acme.xcodeproj/project.pbxproj": PBX % target,
        "Acme/Info.plist": PLIST % plist,
        "Acme/AcmeApp.swift": code,
    }
    if icon:
        files["Acme/Assets.xcassets/AppIcon.appiconset/Contents.json"] = ICON
        files["Acme/Assets.xcassets/AppIcon.appiconset/icon.png"] = png(1024, 1024)
    if manifest:
        files["Acme/PrivacyInfo.xcprivacy"] = MANIFEST
    files.update(extra or {})
    return files


def flutter(extra=None, deps="", plist=""):
    files = {
        "pubspec.yaml": "name: demo\nversion: 1.2.0+7\nenvironment:\n  sdk: '>=3.0.0 <4.0.0'\ndependencies:\n  flutter:\n    sdk: flutter\n" + deps,
        "lib/main.dart": "import 'package:flutter/material.dart';\nvoid main() => runApp(const MaterialApp(home: Text('Hello')));\n",
        "ios/Runner.xcodeproj/project.pbxproj": PBX % "16.0",
        "ios/Runner/Info.plist": PLIST % plist,
        "ios/Runner/PrivacyInfo.xcprivacy": MANIFEST,
        "ios/Runner/Assets.xcassets/AppIcon.appiconset/Contents.json": ICON,
        "ios/Runner/Assets.xcassets/AppIcon.appiconset/icon.png": png(1024, 1024),
    }
    files.update(extra or {})
    return files


def case(name, code, files, expect=(), absent=(), **kw):
    return dict(name=name, scan=code, files=files, expect=list(expect), absent=list(absent), **kw)


CASES = [
    # Store readiness
    case("sr-missing-icon", "SR", swift(icon=False), ["SR-10"]),
    case("sr-alpha-icon", "SR", swift({"Acme/Assets.xcassets/AppIcon.appiconset/icon.png": png(1024, 1024, True)}), ["SR-11"]),
    case("sr-corrupt-plist", "SR", swift({"Acme/Info.plist": "<plist><dict><key>broken"}), ["SR-13"]),
    case("sr-plist-gaps", "SR", swift({"Acme/Info.plist": """<?xml version="1.0"?><plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>com.example.app</string><key>CFBundleDisplayName</key><string>Demo Test Build</string>
<key>NSCameraUsageDescription</key><string>TODO</string>
<key>NSAppTransportSecurity</key><dict><key>NSAllowsArbitraryLoads</key><true/></dict>
<key>UIBackgroundModes</key><array><string>audio</string></array>
</dict></plist>"""}), ["SR-20", "SR-21", "SR-22", "SR-24", "SR-25", "SR-26"]),
    case("sr-ipad-orientations", "SR", swift({"Acme.xcodeproj/project.pbxproj": (PBX % "16.0").replace('"1"', '"1,2"')},
         plist="<key>UISupportedInterfaceOrientations~ipad</key><array><string>UIInterfaceOrientationPortrait</string></array>"), ["SR-23"]),
    case("sr-no-manifest", "SR", swift(manifest=False), ["SR-30"]),
    case("sr-required-reason", "SR", swift({"Acme/Prefs.swift": "import Foundation\nlet v = UserDefaults.standard.string(forKey: \"a\")\nlet t = ProcessInfo.processInfo.systemUptime\n"}), ["SR-31"]),
    case("sr-placeholder", "SR", swift({"Acme/en.lproj/Localizable.strings": '"a" = "Lorem ipsum dolor";\n"b" = "Coming soon";\n'}), ["SR-40", "SR-42"]),
    case("sr-dev-server", "SR", swift({"Acme/Api.swift": 'let base = "https://staging.example.com/api"\n'}), ["SR-41"]),
    case("sr-no-links", "SR", swift({"Acme/Auth.swift": 'import AuthenticationServices\nlet a = ASAuthorizationAppleIDProvider()\n'}), ["SR-50"]),
    case("sr-old-target", "SR", swift(target="12.0"), ["SR-61", "SR-60"]),
    case("sr-old-podfile", "SR", swift({"Podfile": "platform :ios, '11.0'\ntarget 'Acme' do\nend\n"}), ["SR-61"]),
    case("sr-icon-composer", "SR", swift({"Acme/AppIcon.icon/icon.json": "{}"}, icon=False), ["SR-12"]),
    case("sr-no-ios-project", "SR", {"lib/main.dart": "void main() {}\n", "pubspec.yaml": "name: demo\ndependencies:\n  flutter:\n    sdk: flutter\n"}, ["SR-09"]),
    case("sr-clean", "SR", swift({"Acme/en.lproj/Localizable.strings": '"p" = "Privacy Policy";\n"s" = "Support";\n'}), absent=["SR-10", "SR-11", "SR-22", "SR-30", "SR-61"], clean=True),
    case("sr-target-13-is-fine", "SR", swift(target="13.0"), absent=["SR-61"]),
    case("sr-quoted-old-target", "SR", swift(target='"12.4"'), ["SR-61"]),
    case("sr-only-old-config-counts", "SR", swift({"Acme.xcodeproj/project.pbxproj": (PBX % "16.0").replace("}; }\n", 'C1 = { isa = XCBuildConfiguration; buildSettings = { IPHONEOS_DEPLOYMENT_TARGET = 11.0; }; };\n}; }\n')}), ["SR-61"]),
    case("sr-old-sample-and-dependencies-do-not-count", "SR", swift({
        "example/ios/Runner.xcodeproj/project.pbxproj": PBX % "9.0",
        "samples/Old/Old.xcodeproj/project.pbxproj": PBX % "8.0",
        "android/x/project.pbxproj": PBX % "9.0",
        "AcmeTests/Sub.xcodeproj/project.pbxproj": PBX % "10.0",
        "Pods/Pods.xcodeproj/project.pbxproj": PBX % "9.0",
        "SourcePackages/checkouts/lib/Lib.xcodeproj/project.pbxproj": PBX % "9.0",
        "Carthage/Checkouts/z/Z.xcodeproj/project.pbxproj": PBX % "9.0",
        "ThirdParty/Dep/Dep.xcodeproj/project.pbxproj": PBX % "8.0",
        "packages/lib/ios/Lib.xcodeproj/project.pbxproj": (PBX % "9.0").replace("product-type.application", "product-type.framework"),
        "Podfile": "# platform :ios, '9.0'\nplatform :ios, '14.0'\n"}), absent=["SR-61"]),
    case("sr-old-test-target-does-not-count", "SR", swift({"Acme.xcodeproj/project.pbxproj": (PBX % "16.0").replace("}; }\n", 'C1 = { isa = XCBuildConfiguration; buildSettings = { IPHONEOS_DEPLOYMENT_TARGET = 11.0; TEST_HOST = "x"; }; };\n}; }\n')}), absent=["SR-61"]),
    case("sr-inherited-target", "SR", swift(target="$(inherited)"), absent=["SR-61"]),
    case("sr-package-minimum-is-not-the-app", "SR", swift({"Package.swift": 'platforms: [.iOS(.v12)]\n'}), absent=["SR-61"]),

    # Content safety and the age rating questionnaire
    case("cs-ugc", "CS", swift({"Acme/Feed.swift": "\n".join(["struct Post {}", "struct CommentsView {}", "func createPost() {}", "func uploadPost() {}", "struct PostComposer {}"])}), ["CS-10"]),
    case("cs-ai", "CS", swift({"Acme/AI.swift": 'let u = "https://api.openai.com/v1/chat/completions"\nimport OpenAI\nfunc generate() {}\n'}), ["CS-11"]),
    case("cs-location", "CS", swift({"Acme/Share.swift": 'func shareLocation() {}\n'}), ["CS-12"], expect_title={}),
    case("cs-social", "CS", swift({"Acme/Feed.swift": "\n".join([f"let followers{i} = 1 // followers" for i in range(12)])}), ["CS-16"]),
    case("cs-gambling", "CS", swift({"Acme/en.lproj/Localizable.strings": '"a" = "Play casino poker and win";\n'}), ["CS-13"]),
    case("cs-medical", "CS", swift({"Acme/en.lproj/Localizable.strings": '"h" = "Your health diagnosis and blood pressure treatment";\n'}), ["CS-14"]),
    case("cs-kids", "CS", swift({"Acme/en.lproj/Localizable.strings": '"a" = "Fun for kids";\n"b" = "For children and toddlers";\n"c" = "kids games";\n'}), ["CS-15"]),
    case("cs-clean", "CS", swift(), absent=["CS-10", "CS-11", "CS-13", "CS-16"], clean=True),
    case("cs-dating-app", "CS", swift({"Acme/en.lproj/Localizable.strings": '"a" = "Dating near you";\n'}), ["CS-12"]),
    case("cs-backdating-and-gestures-are-not-dating", "CS", swift({"Acme/D.swift": "// back-dating it covers clock skew\n// contacts dating from the old era\n", "Acme/en.lproj/Localizable.strings": '"s" = "Swipe right/left to skip";\n'}), absent=["CS-12"]),
    case("cs-following-is-an-everyday-word", "CS", swift({"Acme/F.swift": "\n".join("// the following items" for _ in range(15)) + "\nlet following = 1\n"}), absent=["CS-12", "CS-16"]),
    case("cs-updating-is-not-dating", "CS", swift({"Acme/U.swift": 'let t = "Updating your data"\n'}), absent=["CS-12"]),


    # Privacy and permissions
    case("pp-camera-no-text", "PP", swift({"Acme/C.swift": "import AVFoundation\nfunc go() { AVCaptureDevice.requestAccess(for: .video) { _ in } }\n"}), ["PP-10"]),
    case("pp-unused-and-vague", "PP", swift(plist="<key>NSMicrophoneUsageDescription</key><string>Needed</string>"), ["PP-11", "PP-12"]),
    case("pp-not-translated", "PP", swift({"Acme/en.lproj/Localizable.strings": '"a" = "A";\n', "Acme/tr.lproj/Localizable.strings": '"a" = "B";\n',
         "Acme/C.swift": "import AVFoundation\nfunc go() { AVCaptureDevice.requestAccess(for: .video) { _ in } }\n"},
         plist="<key>NSCameraUsageDescription</key><string>Takes a photo of your receipt for the expense.</string>"), ["PP-13"]),
    case("pp-ask-at-launch", "PP", swift(code="""import SwiftUI
import AVFoundation
@main struct AcmeApp: App { init() { AVCaptureDevice.requestAccess(for: .video) { _ in } }
var body: some Scene { WindowGroup { Text("Hello") } } }
""", plist="<key>NSCameraUsageDescription</key><string>Takes a photo of your receipt for the expense.</string>"), ["PP-14"]),
    case("pp-tracking-sdk", "PP", swift({"Podfile": "platform :ios, '15.0'\npod 'Google-Mobile-Ads-SDK'\npod 'FBSDKCoreKit'\n", "Acme/Ads.swift": "import GoogleMobileAds\nlet a = GADMobileAds.sharedInstance()\n"}), ["PP-20", "PP-21", "PP-22", "PP-50"]),
    case("pp-tracking-no-domains", "PP", swift({"Acme/PrivacyInfo.xcprivacy": MANIFEST.replace("<key>NSPrivacyTracking</key><false/>", "<key>NSPrivacyTracking</key><true/>")}), ["PP-21"]),
    case("pp-ai-no-consent", "PP", swift({"Acme/AI.swift": 'let u = "https://api.openai.com/v1/chat/completions"\nimport OpenAI\n'}), ["PP-30"]),
    case("pp-health-icloud", "PP", swift({"Acme/H.swift": "import HealthKit\nlet s = HKHealthStore()\nfunc r() { s.requestAuthorization(toShare: nil, read: nil) { _, _ in } }\n",
         "Acme/Acme.entitlements": '<?xml version="1.0"?><plist version="1.0"><dict><key>com.apple.developer.healthkit</key><true/><key>com.apple.developer.icloud-services</key><array><string>CloudKit</string></array><key>com.apple.developer.icloud-container-identifiers</key><array><string>iCloud.x</string></array></dict></plist>'},
         plist="<key>NSHealthShareUsageDescription</key><string>Reads your steps to show a weekly summary.</string>"), ["PP-40"]),
    case("pp-always-location", "PP", swift({"Acme/L.swift": "import CoreLocation\nlet m = CLLocationManager()\nfunc r() { m.requestAlwaysAuthorization() }\n"},
         plist="<key>NSLocationAlwaysAndWhenInUseUsageDescription</key><string>Tracks your route while recording a run.</string><key>UIBackgroundModes</key><array><string>location</string></array>"), ["PP-41"]),
    case("pp-clean", "PP", swift(), absent=["PP-10", "PP-20", "PP-30"], clean=True),

    # Purchases
    case("mo-no-restore", "MO", swift({"Acme/Store.swift": 'import StoreKit\nimport SwiftUI\nlet productIDs = ["com.acme.pro.monthly"]\nlet a = "com.acme.pro.monthly"\nstruct PaywallView: View { var body: some View { SubscriptionStoreView(productIDs: productIDs) } }\nfunc buy() async throws { let p = try await Product.products(for: productIDs); _ = try await p[0].purchase() }\nlet g = Product.SubscriptionInfo.self\nlet price = "$4.99"\n',
         "Acme/en.lproj/Localizable.strings": '"t" = "Subscribe now for $4.99 per month";\n'}), ["MO-10", "MO-12", "MO-13", "MO-14", "MO-15"]),
    case("mo-product-not-in-config", "MO", swift({"Acme/Store.swift": 'import StoreKit\nlet productID = "com.acme.pro.monthly"\nfunc buy() async throws { let p = try await Product.products(for: [productID]); _ = try await p[0].purchase() }\nfunc r() async throws { try await AppStore.sync() }\n',
         "Acme/Products.storekit": '{ "products": [ { "productID": "com.example.other" } ], "subscriptionGroups": [] }'}), ["MO-11"]),
    case("mo-external-pay", "MO", swift({"Podfile": "platform :ios, '15.0'\npod 'Stripe'\n", "Acme/P.swift": 'import Stripe\nimport StoreKit\nlet u = "https://acme.io/checkout/premium"\nlet s = "Buy premium on our website"\nfunc redeem(licenseKey: String) {}\nlet coupon = "promo_code"\nfunc buy() async throws { let p = try await Product.products(for: ["a"]); _ = try await p[0].purchase() }\n'}), ["MO-16", "MO-17"]),
    case("mo-review-reward", "MO", swift({"Acme/en.lproj/Localizable.strings": '"r" = "Rate us and get 100 coins";\n"l" = "Open a loot box";\n',
         "Acme/P.swift": 'import StoreKit\nfunc buy() async throws { let p = try await Product.products(for: ["a"]); _ = try await p[0].purchase() }\nfunc r() async throws { try await AppStore.sync() }\n'}), ["MO-18", "MO-19"]),
    case("mo-ads", "MO", swift({"Podfile": "platform :ios, '15.0'\npod 'Google-Mobile-Ads-SDK'\n", "Acme/A.swift": "import GoogleMobileAds\nlet a = GADMobileAds.sharedInstance()\n"}), ["MO-20"]),
    case("mo-clean", "MO", swift(), absent=["MO-13", "MO-14", "MO-15", "MO-16"], clean=True),

    # Accounts and network
    case("nw-no-delete", "NW", swift({"Acme/A.swift": 'func signUp(email: String, password: String) {}\nstruct RegisterView {}\nfunc createAccount() {}\nfunc signIn() {}\nimport GoogleSignIn\nlet g = GIDSignIn.sharedInstance\nlet u = "http://api.acme.io/v1"\nlet key = "' + FAKE_KEY + '"\nimport FirebaseRemoteConfig\nlet rc = RemoteConfig.remoteConfig()\nfunc f() { URLSession.shared.dataTask(with: URL(string: u)!).resume() }\n'}), ["NW-10", "NW-11", "NW-12", "NW-13", "NW-14", "NW-16", "NW-17"]),
    case("nw-code-push", "NW", flutter(deps="  shorebird_code_push: ^1.0.0\n"), ["NW-15"]),
    case("nw-clean", "NW", swift(), absent=["NW-10", "NW-13", "NW-16"], clean=True),

    # Layout and accessibility
    case("la-fixed", "LA", swift({"Acme/V.swift": "\n".join(["import SwiftUI", "struct V: View { var body: some View { VStack {",
         'Text("Long title").font(.system(size: 14)).lineLimit(1)', 'Button(action: {}) { Image(systemName: "trash") }', "Button(\"x\") { }.frame(width: 20, height: 20)", ".dynamicTypeSize(.large)", ".ignoresSafeArea(.keyboard)",
         "Color(red: 0.1, green: 0.2, blue: 0.3)"] + [f"Color(red: 0.{i}, green: 0.2, blue: 0.3)" for i in range(1, 6)] + ["} } }"] +
         [f"let a{i} = withAnimation {{ }}" for i in range(16)] + ['let d = UIScreen.main.bounds.width'] + [f'let s{i} = Image(systemName: "star")' for i in range(22)])}), ["LA-10", "LA-11", "LA-21", "LA-22", "LA-30", "LA-60", "LA-70"]),
    case("la-fixed-colors-everywhere", "LA", swift({f"Acme/C{i}.swift": "import SwiftUI\n" + "\n".join(f"let c{i}{j} = Color(red: 0.{j}, green: 0.2, blue: 0.3)" for j in range(1, 4)) + "\n" for i in range(4)}), ["LA-41"]),
    case("la-icon-button-many-lines", "LA", swift({"Acme/V.swift": 'import SwiftUI\nlet b = Button(action: { go() }) {\n    Image(systemName: "gear")\n        .font(.title2)\n        .foregroundColor(.blue)\n}\n'}), ["LA-22"]),
    case("la-labelled-many-lines-is-fine", "LA", swift({"Acme/V.swift": 'import SwiftUI\nlet b = Button { go() } label: {\n    Image(systemName: "gear")\n}\n.accessibilityLabel("Settings")\n'}), absent=["LA-22"]),
    case("la-icon-and-text-is-fine", "LA", swift({"Acme/V.swift": 'import SwiftUI\nlet b = Button(action: {}) {\n    Image(systemName: "gear")\n    Text("Settings")\n}\n'}), absent=["LA-22"]),
    case("la-labelled-icon-is-fine", "LA", swift({"Acme/V.swift": 'import SwiftUI\nlet b = Button(action: {}) { Image(systemName: "trash") }.accessibilityLabel("Delete")\n'}), absent=["LA-22"]),
    case("la-flutter-icon", "LA", flutter({"lib/v.dart": "import 'package:flutter/material.dart';\nfinal b = IconButton(onPressed: null, icon: Icon(Icons.add));\n"}), ["LA-20"]),
    case("la-appearance", "LA", swift(plist="<key>UIUserInterfaceStyle</key><string>Light</string>"), ["LA-40"]),
    case("la-ipad-no-adapt", "LA", swift({"Acme.xcodeproj/project.pbxproj": (PBX % "16.0").replace('"1"', '"1,2"'), "Acme/V.swift": 'import SwiftUI\nstruct V: View { var body: some View { Text("x") } }\n'}), ["LA-50"]),
    case("la-catalyst", "LA", swift({"Acme.xcodeproj/project.pbxproj": (PBX % "16.0").replace('"1"', '"1,2,6"').replace("SDKROOT = iphoneos;", "SDKROOT = iphoneos; SUPPORTS_MACCATALYST = YES;")}), ["LA-51"]),
    case("la-clean", "LA", swift(), absent=["LA-10", "LA-20", "LA-50"], clean=True),

    # Locale and time
    case("lt-mixed", "LT", swift({"Acme/L.swift": "\n".join(["import SwiftUI", "import Foundation",
         "func days(a: Date, b: Date) -> Double { return b.timeIntervalSince(a) / 86400 }", "func next(a: Date) -> Date { a.addingTimeInterval(24 * 60 * 60) }",
         'let f = DateFormatter(); func x() { f.dateFormat = "dd/MM/yyyy" }', 'func price(v: Double) -> String { return "$\\(v)0" }', 'let tz = TimeZone(identifier: "America/New_York")',
         'struct V: View { var body: some View { VStack { Text(verbatim: "Save your work").padding(.left, 8); Text("\\(count) items") } } }'] + [f"let c{i} = Calendar.current.component(.year, from: Date())" for i in range(6)]),
         "Acme/en.lproj/Localizable.strings": '"a" = "A";\n', "Acme/ar.lproj/Localizable.strings": '"a" = "B";\n'}), ["LT-10", "LT-20", "LT-21", "LT-30", "LT-40", "LT-41", "LT-50", "LT-60"]),
    case("lt-clean", "LT", swift(), absent=["LT-10", "LT-30", "LT-40"], clean=True),

    # Data integrity
    case("di-drift", "DI", flutter({"lib/db.dart": "import 'package:drift/drift.dart';\nclass D extends _$D { @override int get schemaVersion => 3; }\n"}, deps="  drift: ^2.0.0\n"), ["DI-10", "DI-11", "DI-15"]),
    case("di-coredata", "DI", swift({"Acme/M.xcdatamodeld/A.xcdatamodel/contents": "<model/>", "Acme/M.xcdatamodeld/B.xcdatamodel/contents": "<model/>",
         "Acme/P.swift": 'import CoreData\nlet c = NSPersistentContainer(name: "M")\nfunc s(d: NSPersistentStoreDescription) { d.shouldMigrateStoreAutomatically = false; d.shouldInferMappingModelAutomatically = false }\n'}), ["DI-12"]),
    case("di-swiftdata", "DI", swift({"Acme/M.swift": "import SwiftData\n@Model final class Item { var a = 0 }\n"}), ["DI-13"]),
    case("di-wipe", "DI", swift({"Acme/P.swift": 'import CoreData\nlet c = NSPersistentContainer(name: "M")\nfunc l(storeURL: URL) { c.loadPersistentStores { _, e in if e != nil { try? FileManager.default.removeItem(at: storeURL) } } }\n'}), ["DI-14"]),
    case("di-secret-plain", "DI", swift({"Acme/S.swift": 'import Foundation\nfunc s(t: String) { UserDefaults.standard.set(t, forKey: "authToken") }\nfunc b() throws { try FileManager.default.copyItem(at: URL(fileURLWithPath: "app.sqlite"), to: URL(fileURLWithPath: "backup.sqlite")) }\nlet docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("cache/downloads")\n'}), ["DI-16", "DI-17", "DI-18"]),
    case("di-clean", "DI", swift(), absent=["DI-11", "DI-14", "DI-16"], clean=True),

    # Input and actions
    case("ia-swift", "IA", swift({"Acme/F.swift": "\n".join(["import SwiftUI", "struct F: View { @State var t = \"\"; var body: some View { VStack {",
         'Button("Save") { Task { await save() } }', 'Button("Delete", role: .destructive) { items.removeAll(); delete(item) }', 'TextField("Amount", text: $t)', "} } }",
         "func save() async {}", "func delete(_ i: Int) {}", "let amount = Double(amountText) ?? 0", "var price: Double = 0", "var total: Float = 0", "let n = name.count", "if name.count > 20 { }"])}), ["IA-10", "IA-11", "IA-12", "IA-13"]),
    case("ia-dart", "IA", flutter({"lib/f.dart": "\n".join(["import 'package:flutter/material.dart';", "final m = TextField(controller: c, decoration: InputDecoration(labelText: 'Amount'));", "final n = name.length > 20;", "final v = double.parse(c.text);", "final maxLen = name.length;"])}), ["IA-14", "IA-15"]),
    case("ia-clean", "IA", swift(), absent=["IA-10", "IA-13"], clean=True),


    # Product fit
    case("pf-remote-web", "PF", {"capacitor.config.json": '{ "appId": "com.acme.a", "server": { "url": "https://acme.io/app" } }', "package.json": '{ "dependencies": { "@capacitor/core": "6.0.0", "@capacitor/ios": "6.0.0" } }',
         "ios/App/App.xcodeproj/project.pbxproj": PBX % "16.0", "ios/App/App/Info.plist": PLIST % "", "src/index.js": "x\n"}, ["PF-10"]),
    case("pf-tiny", "PF", swift(), ["PF-11"]),
    case("pf-display-name", "PF", swift({"Acme/Info.plist": (PLIST % "").replace(">Example<", ">Free iPhone Instagram Best<")}), ["PF-13", "PF-14", "PF-15"]),
    case("pf-metadata", "PF", swift({"fastlane/metadata/en-US/name.txt": "A name that is much too long for the thirty character limit",
         "fastlane/metadata/en-US/subtitle.txt": "The best on Android", "fastlane/metadata/en-US/release_notes.txt": "Bug fixes and improvements",
         "fastlane/metadata/en-US/keywords.txt": "instagram,budget"}), ["PF-12", "PF-14", "PF-15", "PF-16", "PF-17"]),
    case("pf-beta-menu", "PF", swift({"Acme/en.lproj/Localizable.strings": '"a" = "This is a beta version";\n"b" = "Download our Android app";\n',
         "Acme/DebugMenu.swift": 'import SwiftUI\nstruct DeveloperMenuView: View { var body: some View { Text("x") } }\n'}), ["PF-12", "PF-18", "PF-19"]),
    case("pf-regulated", "PF", swift({"Acme/en.lproj/Localizable.strings": '"a" = "Trade crypto and bitcoin with your wallet";\n'}), ["PF-20"]),

    # Test strategy
    case("ts-no-tests", "TS", swift({"Acme/PaymentEngine.swift": "struct PaymentEngine { func charge() {} }\n"}), ["TS-10", "TS-11", "TS-14"]),
    case("ts-weak-tests", "TS", flutter({"integration_test/app_test.dart": "import 'package:integration_test/integration_test.dart';\nvoid main() { IntegrationTestWidgetsFlutterBinding.ensureInitialized(); }\n",
         "test/a_test.dart": "import 'dart:math';\nimport 'package:test/test.dart';\nvoid main() { test('x', () { final n = DateTime.now();\n final m = n.add(const Duration(days: 30)).month;\n final r = Random().nextInt(3); expect(m, isNotNull); }, skip: true); }\n"}), ["TS-12", "TS-13", "TS-15", "TS-16"]),

    # Test health
    case("th-swift", "TH", swift({"AcmeUITests/A.swift": 'import XCTest\nfinal class A: XCTestCase { func testA() { let a = XCUIApplication(); a.buttons["gone-button"].tap(); sleep(3) } func testEmpty() { } }\n',
         "Acme/V.swift": 'import SwiftUI\nlet b = Text("x").accessibilityIdentifier("real-button")\n'}), ["TH-10", "TH-13", "TH-17"]),
    case("th-dart", "TH", flutter({"test/a_test.dart": "import 'package:test/test.dart';\nimport 'package:http/http.dart' as http;\nvoid main() { test('month end', () { final d = DateTime.now(); final n = DateTime(d.year, d.month + 1, 0); expect(n.day, 30); }); test('fmt', () { expect(DateTime(2026).toLocal().hour, 0); }); test('net', () async { await http.get(Uri.parse('https://acme.io')); }); }\n"}), ["TH-14", "TH-15", "TH-16"]),

    case("th-skip-and-only", "TH", flutter({"test/s_test.dart": "import 'package:test/test.dart';\nvoid main() { test('a', () { expect(1, 1); }, skip: true); }\n", "test/o_test.dart": "import 'package:test/test.dart';\nvoid main() { solo_test('b', () { expect(1, 1); }); }\n"}), ["TH-11"]),
    case("th-only-js", "TH", {"package.json": '{ "dependencies": { "react-native": "0.74.0" } }', "index.js": "x\n", "ios/A.xcodeproj/project.pbxproj": PBX % "16.0", "ios/A/Info.plist": PLIST % "", "__tests__/a.test.js": "it.only('a', () => { expect(1).toBe(1); });\n"}, ["TH-12"]),

    # Time travel
    case("tt-direct-now", "TT", swift({"Acme/T.swift": "import Foundation\nlet a = Date()\nfunc d() -> Date { Date() }\n"}), ["TT-10", "TT-11"]),

    # Persona
    case("pe-plan", "PE", flutter({"integration_test/persona_test.dart": "// Elderly user journey\nfinal persona = 'grandma';\nvoid journeyTest() {}\n"}), ["PE-10", "PE-11", "PE-12"]),

    # Rapid input
    case("ri-swift", "RI", swift({"Acme/V.swift": 'import SwiftUI\nstruct V: View { var body: some View { Button("Pay") { Task { await pay() } } } }\nfunc pay() async { _ = URLSession.shared }\n'}), ["RI-10", "RI-11", "RI-12"]),
    case("ri-dart", "RI", flutter({"analysis_options.yaml": "linter:\n  rules:\n    use_build_context_synchronously: false\n", "lib/d.dart": "void a(db) async {\n  await db.insert('t', {});\n  await db.insert('t', {});\n  await db.update('t', {});\n}\n"}, deps="  sqflite: ^2.0.0\n"), ["RI-13", "RI-14"]),

    # Lifecycle
    case("lc-swift", "LC", swift({"Acme/A.swift": "\n".join(["import UIKit", "import LocalAuthentication", "import AVFoundation", "class D: NSObject, UIApplicationDelegate { func applicationWillTerminate(_ a: UIApplication) {\n  saveAll()\n} }", "func saveAll() {}",
         "let c = LAContext()", "func p() { _ = AVCaptureDevice.authorizationStatus(for: .video) }"]), "Acme/F1.swift": 'import SwiftUI\nlet a = TextField("a", text: .constant(""))\n', "Acme/F2.swift": 'import SwiftUI\nlet b = TextField("b", text: .constant(""))\n',
         "Acme/I1.swift": 'import SwiftUI\nlet a = AsyncImage(url: nil)\n', "Acme/I2.swift": 'import SwiftUI\nlet b = AsyncImage(url: nil)\n', "Acme/I3.swift": 'import SwiftUI\nlet c = AsyncImage(url: nil)\n'}), ["LC-10", "LC-11", "LC-12", "LC-13", "LC-15"]),
    case("lc-permission-not-rechecked", "LC", swift({"Acme/C.swift": "import AVFoundation\nfunc p() { _ = AVCaptureDevice.authorizationStatus(for: .video); AVCaptureDevice.requestAccess(for: .video) { _ in } }\n"},
         plist="<key>NSCameraUsageDescription</key><string>Takes a photo of your receipt for the expense.</string>"), ["LC-14"]),

    # Visual
    case("vi-baselines", "VI", flutter({"test/goldens/a.png": png(4, 4), "test/goldens/b.png": png(4, 4), "test/g_test.dart": "void main() { expectLater(f, matchesGoldenFile('goldens/a.png')); }\n",
         ".github/workflows/ci.yml": "jobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: flutter test\n"}), ["VI-10", "VI-11", "VI-12", "VI-13", "VI-14"]),

    # Network behaviour
    case("nc-swift", "NC", swift({"Acme/N.swift": 'import SwiftUI\nfunc f() async throws -> Data { let (d, _) = try await URLSession.shared.data(from: URL(string: "https://acme.io")!); return d }\nfunc signIn() {}\nlet token = "bearer"\nstruct E: View { let error: Error; var body: some View { Text(error.localizedDescription) } }\n'}), ["NC-10", "NC-11", "NC-13", "NC-14", "NC-15"]),
    case("nc-dart-no-timeout", "NC", flutter({"lib/n.dart": "import 'package:http/http.dart' as http;\nFuture<void> f() async { await http.get(Uri.parse('https://acme.io')); }\n"}, deps="  http: ^1.0.0\n"), ["NC-12"]),

    # Store assets (checks an image folder, not a project)
    case("sa-bad-size", "SA", {"en/iphone/a.png": png(100, 100)}, ["SA-12"]),
    case("sa-alpha", "SA", {"en/iphone/a.png": png(1320, 2868, True)}, ["SA-11"]),
    case("sa-unreadable", "SA", {"en/iphone/a.png": b"not an image"}, ["SA-10"]),
    case("sa-too-many", "SA", {f"en/iphone/{i}.png": png(1320, 2868) for i in range(11)}, ["SA-13"]),
    case("sa-mixed", "SA", {"en/iphone/a.png": png(1320, 2868), "en/iphone/b.png": png(2868, 1320)}, ["SA-14"]),
    case("sa-no-large", "SA", {"en/iphone/a.png": png(750, 1334)}, ["SA-15"]),
    case("sa-no-ipad", "SA", {"en/iphone/a.png": png(1320, 2868)}, ["SA-16"], args=["--ipad"]),
    case("sa-video", "SA", {"en/iphone/a.mov": b"x", "en/iphone/b.mov": b"x", "en/iphone/c.mov": b"x", "en/iphone/d.mov": b"x"}, ["SA-20", "SA-21"]),
    case("sa-clean", "SA", {"en/iphone/a.png": png(1320, 2868)}, clean=True),

    # Design audit
    case("ds-material", "DS", flutter({"lib/s.dart": "\n".join(["import 'package:flutter/material.dart';", "final a = FloatingActionButton(onPressed: null);"] +
         [f"final s{i} = Scaffold(); final e{i} = ElevatedButton(onPressed: null, child: const Text('x')); final t{i} = TextField(); final i{i} = Icon(Icons.add);" for i in range(8)] +
         ["void m(c) { ScaffoldMessenger.of(c).showSnackBar(const SnackBar(content: Text('x'))); showDialog(context: c, builder: (_) => AlertDialog(actions: [TextButton(onPressed: null, child: const Text('OK'))])); }",
          "final p = PopScope(canPop: false, child: Text('x'));"])}), ["DS-09", "DS-10", "DS-11", "DS-12", "DS-14", "DS-15", "DS-16"]),
    case("ds-tabs", "DS", swift({"Acme/T.swift": "import SwiftUI\nstruct T: View { var body: some View { TabView {\n" + "\n".join(f'Text("{i}").tabItem {{ Text("{i}") }}' for i in range(7)) + "\n} } }\n"}), ["DS-13"]),
]

# A plain, healthy app must get no rejection risk and no user bug from any project scanner.
_LINKS = {"privacy": '"p" = "Privacy Policy";\n"s" = "Support";\n'}
for _code in ("SR", "PP", "MO", "NW", "LA", "LT", "DI", "IA", "CS", "PF", "TS", "TH", "TT", "PE", "RI", "LC", "VI", "NC", "DS"):
    CASES.append(case(f"clean-swift-{_code}", _code, swift({"Acme/en.lproj/Localizable.strings": _LINKS["privacy"]}), clean=True))
    CASES.append(case(f"clean-flutter-{_code}", _code, flutter({"lib/l10n/app_en.arb": '{ "privacy": "Privacy Policy", "support": "Support" }'}), clean=True))
