"""Proof rig: a small SwiftUI app + the family's XCUITest templates (source: references/*.md).
A template that compiles does not mean it works: it must pass on the clean app and fail on the deliberately buggy build.

    python3 -I generate.py <empty folder>     # then run.sh
"""
import re,sys,os,hashlib,shutil
P=sys.argv[1]; HERE=os.path.dirname(os.path.abspath(__file__)); H=os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
os.makedirs(P+'/ProofApp',exist_ok=True); os.makedirs(P+'/ProofUITests',exist_ok=True)
shutil.copy(HERE+'/App.swift',P+'/ProofApp/App.swift')
def code(rel,has):
    return [x for x in re.findall(r'```swift\n(.*?)```',open(H+'/'+rel,encoding='utf-8').read(),re.S) if has in x][0]
open(P+'/ProofApp/Chaos.swift','w').write(code('apptest-network-chaos/references/faults.md','ChaosProtocol: URLProtocol'))
open(P+'/ProofUITests/PersonaTour.swift','w').write(code('apptest-persona/references/templates.md','PersonaTour'))
open(P+'/ProofUITests/LC.swift','w').write(code('apptest-lifecycle/references/transitions.md','LifecycleTour'))
open(P+'/ProofUITests/RI.swift','w').write('import XCTest\nfinal class RI: XCTestCase {\n'+code('apptest-rapid-input/references/templates.md','testDoubleTapSaveCreatesOneRecord')+'\n}\n')
def swift(path,i=0): return re.findall(r'```swift\n(.*?)```',open(path,encoding='utf-8').read(),re.S)[i]
crawl=swift(H+'/apptest-crawl/references/templates.md')
open(P+'/ProofUITests/Crawl.swift','w').write(crawl)
bug=crawl.replace('CrawlTests','CrawlBugCrashTests').replace('"-demoData", "-fixedNow", "2026-10-28T10:00:00Z"','"-bug-crash"')
a11y=crawl.replace('CrawlTests','CrawlBugA11yTests').replace('"-demoData", "-fixedNow", "2026-10-28T10:00:00Z"','"-bug-a11y"')
open(P+'/ProofUITests/CrawlBug.swift','w').write(bug+a11y.replace('import XCTest\n',''))
ri=open(P+'/ProofUITests/RI.swift').read()
ri=ri.replace('["-uitest", "-slow-writes"]','["-uitest", "-slow-writes", "-reset"]')
open(P+'/ProofUITests/RI.swift','w').write(ri)
open(P+'/ProofUITests/RIBug.swift','w').write(ri.replace('final class RI:','final class RIBug:').replace('"-reset"]','"-reset", "-bug-double"]'))
sim=swift(H+'/apptest-state-sim/references/templates.md')
open(P+'/ProofUITests/Sim.swift','w').write(sim+'''
enum Action: CaseIterable { case add, remove, reject }
struct RejectedError: Error {}
struct Snap: Equatable { var total: Int; var parts: [Int] }
final class AppUnderTest {
    var parts: [Int] = []; var total = 0; var bug = false
    static func inMemory(now: Date) throws -> AppUnderTest { AppUnderTest() }
    func snapshot() throws -> Snap { Snap(total: total, parts: parts) }
    func perform<R: RandomNumberGenerator>(_ a: Action, using r: inout R) async throws {
        switch a {
        case .add: let v = Int.random(in: 1...9, using: &r); parts.append(v); total += v
        case .remove: if let v = parts.popLast() { total -= v }
        case .reject: throw RejectedError()
        }
    }
}
''')
open(P+'/ProofUITests/SimBug.swift','w').write('''import XCTest
fileprivate struct SplitMix64: RandomNumberGenerator {
    var state: UInt64
    init(seed: UInt64) { state = seed }
    mutating func next() -> UInt64 { state &+= 0x9E3779B97F4A7C15; var z = state; z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9; z = (z ^ (z >> 27)) &* 0x94D049BB133111EB; return z ^ (z >> 31) }
}
'''+sim[sim.index('final class StateSimTests'):].replace('StateSimTests','StateSimBugTests').replace('AppUnderTest.inMemory','BuggyApp.inMemory')+'''
final class BuggyApp {
    var parts: [Int] = []; var total = 0
    static func inMemory(now: Date) throws -> BuggyApp { BuggyApp() }
    func snapshot() throws -> Snap { Snap(total: total, parts: parts) }
    func perform<R: RandomNumberGenerator>(_ a: Action, using r: inout R) async throws {
        switch a {
        case .add: let v = Int.random(in: 1...9, using: &r); parts.append(v); total += v
        case .remove: _ = parts.popLast()   // planned bug: the total does not go down
        case .reject: throw RejectedError()
        }
    }
}
''')
open(P+'/ProofUITests/Proof.swift','w').write('''import XCTest
final class Proof: XCTestCase {
    func launch(_ a: [String]) -> XCUIApplication { let x = XCUIApplication(); x.launchArguments = a; x.launch(); return x }
    func netStatus(_ a: [String], _ want: String, timeout: TimeInterval = 12) {
        let app = launch(a)
        app.buttons["fetch"].tap()
        let p = NSPredicate(format: "label CONTAINS %@", want)
        let e = app.staticTexts.matching(identifier: "net-status").matching(p).firstMatch
        XCTAssertTrue(e.waitForExistence(timeout: timeout), "expected \\(want), saw: \\(app.staticTexts["net-status"].label)")
    }
    // real connection through nc_proxy: 127.0.0.1:8897 pass, 8891 503, 8892 corrupt, 8893 reset, 8894 hang
    func testProxyPass() { netStatus(["-baseURL", "http://127.0.0.1:8897"], "HTTP 200") }
    func testProxy503() { netStatus(["-baseURL", "http://127.0.0.1:8891"], "HTTP 503") }
    func testProxyGarbage() { netStatus(["-baseURL", "http://127.0.0.1:8892"], "corrupt") }
    func testProxyReset() { netStatus(["-baseURL", "http://127.0.0.1:8893"], "network error") }
    func testProxyHang() { netStatus(["-baseURL", "http://127.0.0.1:8894"], "network error") }
    // ChaosProtocol template
    func testChaos503() { netStatus(["-chaos", "503"], "HTTP 503") }
    func testChaosOffline() { netStatus(["-chaos-offline"], "network error") }
    func testChaosGarbage() { netStatus(["-chaos-garbage"], "corrupt") }
    // Lifecycle: what was saved survives a cold start
    func testSaveKillColdStart() {
        var app = launch(["-reset"])
        app.buttons["save"].tap()
        XCTAssertTrue(app.staticTexts["Record 1"].waitForExistence(timeout: 5))
        XCUIDevice.shared.press(.home)
        app.terminate()
        app = launch([])
        XCTAssertTrue(app.staticTexts["Record 1"].waitForExistence(timeout: 10))
    }
}
extension PersonaTour {
    func testPersonaReachesGoal() throws {
        let g = Goal(name: "open details", words: ["detail"], typing: nil) { $0.navigationBars["Details"].exists }
        let g2 = Goal(name: "missing goal", words: ["no-such-thing"], typing: nil) { $0.navigationBars["Missing"].exists }
        let p = Persona(name: "returning", launch: ["-reset"], lang: nil, largestText: false, voiceOver: false, hurried: false, goals: [g, g2])
        let r = try run(p, seed: 1)
        print("PERSONA-REPORT\\n" + r.joined(separator: "\\n"))
        XCTAssertTrue(r.contains { $0.hasPrefix("✓") && $0.contains("open details") }, r.joined(separator: "\\n"))
        XCTAssertTrue(r.contains { $0.hasPrefix("✗ PE-20") && $0.contains("missing goal") }, r.joined(separator: "\\n"))
    }
}
''')
# pbxproj
def uid(s): return hashlib.md5(s.encode()).hexdigest()[:24].upper()
app=sorted(f for f in os.listdir(P+'/ProofApp') if f.endswith('.swift')); ts=sorted(f for f in os.listdir(P+'/ProofUITests') if f.endswith('.swift'))
fr=lambda d,f:f'{uid("fr"+d+f)} /* {f} */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {f}; sourceTree = "<group>"; }};'
bf=lambda d,f:f'{uid("bf"+d+f)} /* {f} */ = {{isa = PBXBuildFile; fileRef = {uid("fr"+d+f)}; }};'
A,T=uid('A'),uid('T'); PR=uid('PR')
cfg=lambda n,extra:f'{uid(n)} /* Debug */ = {{isa = XCBuildConfiguration; buildSettings = {{ {extra} }}; name = Debug; }};'
common='ALWAYS_SEARCH_USER_PATHS = NO; CLANG_ENABLE_MODULES = YES; IPHONEOS_DEPLOYMENT_TARGET = 17.0; SDKROOT = iphoneos; SWIFT_VERSION = 5.0; ONLY_ACTIVE_ARCH = YES; ENABLE_TESTABILITY = YES; CODE_SIGNING_ALLOWED = NO; CODE_SIGN_IDENTITY = ""; SWIFT_OPTIMIZATION_LEVEL = "-Onone"; TARGETED_DEVICE_FAMILY = "1,2";'
appS='GENERATE_INFOPLIST_FILE = YES; INFOPLIST_KEY_UILaunchScreen_Generation = YES; INFOPLIST_KEY_CFBundleDisplayName = Proof; PRODUCT_BUNDLE_IDENTIFIER = local.apptest.proof; PRODUCT_NAME = ProofApp; INFOPLIST_FILE = ProofApp/Info.plist; LD_RUNPATH_SEARCH_PATHS = "@executable_path/Frameworks";'
tS='GENERATE_INFOPLIST_FILE = YES; PRODUCT_BUNDLE_IDENTIFIER = local.apptest.proof.tests; PRODUCT_NAME = ProofUITests; TEST_TARGET_NAME = ProofApp; LD_RUNPATH_SEARCH_PATHS = "@executable_path/Frameworks @loader_path/Frameworks";'
pb=f'''// !$*UTF8*$!
{{ archiveVersion = 1; classes = {{}}; objectVersion = 56; objects = {{
{chr(10).join(bf('a',f) for f in app)}
{chr(10).join(bf('t',f) for f in ts)}
{chr(10).join(fr('a',f) for f in app)}
{chr(10).join(fr('t',f) for f in ts)}
{uid('prodA')} = {{isa = PBXFileReference; explicitFileType = wrapper.application; path = ProofApp.app; sourceTree = BUILT_PRODUCTS_DIR; }};
{uid('prodT')} = {{isa = PBXFileReference; explicitFileType = wrapper.cfbundle; path = ProofUITests.xctest; sourceTree = BUILT_PRODUCTS_DIR; }};
{uid('plist')} = {{isa = PBXFileReference; lastKnownFileType = text.plist.xml; path = Info.plist; sourceTree = "<group>"; }};
{uid('gMain')} = {{isa = PBXGroup; children = ({uid('gA')}, {uid('gT')}, {uid('gP')}); sourceTree = "<group>"; }};
{uid('gA')} = {{isa = PBXGroup; children = ({', '.join(uid('fr'+'a'+f) for f in app)}, {uid('plist')}); path = ProofApp; sourceTree = "<group>"; }};
{uid('gT')} = {{isa = PBXGroup; children = ({', '.join(uid('fr'+'t'+f) for f in ts)}); path = ProofUITests; sourceTree = "<group>"; }};
{uid('gP')} = {{isa = PBXGroup; children = ({uid('prodA')}, {uid('prodT')}); name = Products; sourceTree = "<group>"; }};
{uid('srcA')} = {{isa = PBXSourcesBuildPhase; files = ({', '.join(uid('bf'+'a'+f) for f in app)}); runOnlyForDeploymentPostprocessing = 0; }};
{uid('srcT')} = {{isa = PBXSourcesBuildPhase; files = ({', '.join(uid('bf'+'t'+f) for f in ts)}); runOnlyForDeploymentPostprocessing = 0; }};
{A} = {{isa = PBXNativeTarget; buildConfigurationList = {uid('clA')}; buildPhases = ({uid('srcA')}); buildRules = (); dependencies = (); name = ProofApp; productName = ProofApp; productReference = {uid('prodA')}; productType = "com.apple.product-type.application"; }};
{T} = {{isa = PBXNativeTarget; buildConfigurationList = {uid('clT')}; buildPhases = ({uid('srcT')}); buildRules = (); dependencies = ({uid('dep')}); name = ProofUITests; productName = ProofUITests; productReference = {uid('prodT')}; productType = "com.apple.product-type.bundle.ui-testing"; }};
{uid('dep')} = {{isa = PBXTargetDependency; target = {A}; targetProxy = {uid('prox')}; }};
{uid('prox')} = {{isa = PBXContainerItemProxy; containerPortal = {PR}; proxyType = 1; remoteGlobalIDString = {A}; remoteInfo = ProofApp; }};
{PR} = {{isa = PBXProject; attributes = {{ LastUpgradeCheck = 1600; TargetAttributes = {{ {T} = {{TestTargetID = {A}; }}; }}; }}; buildConfigurationList = {uid('clP')}; compatibilityVersion = "Xcode 14.0"; developmentRegion = en; hasScannedForEncodings = 0; knownRegions = (en, Base); mainGroup = {uid('gMain')}; productRefGroup = {uid('gP')}; projectDirPath = ""; projectRoot = ""; targets = ({A}, {T}); }};
{cfg('cP',common)}
{cfg('cA',appS)}
{cfg('cT',tS)}
{uid('clP')} = {{isa = XCConfigurationList; buildConfigurations = ({uid('cP')}); defaultConfigurationName = Debug; }};
{uid('clA')} = {{isa = XCConfigurationList; buildConfigurations = ({uid('cA')}); defaultConfigurationName = Debug; }};
{uid('clT')} = {{isa = XCConfigurationList; buildConfigurations = ({uid('cT')}); defaultConfigurationName = Debug; }};
}}; rootObject = {PR}; }}
'''
os.makedirs(P+'/Proof.xcodeproj',exist_ok=True); open(P+'/Proof.xcodeproj/project.pbxproj','w').write(pb)
open(P+'/ProofApp/Info.plist','w').write('''<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict></dict></plist>''')
