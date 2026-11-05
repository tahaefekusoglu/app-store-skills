#!/usr/bin/env python3
"""apptest-network — static scan (account deletion, sign-in options, offline,
unencrypted connections, remote config, code updates, secret keys).

Standard library only; does NOT write to the project and does NOT use the network.
The output is CANDIDATES (verified against the NW-xx IDs in SKILL.md). Secret keys
are MASKED in the report (CONVENTIONS principle 17).

    python3 -I network_scan.py <project_root> [--json]
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

# Generic "register(" deliberately ABSENT (it collides with notification, cell and service registration).
CREATE_CODE = r"\bsignUp\b|\bsign_up\b|registerUser|registerAccount|registerWithEmail|auth\.register\(|" \
              r"createAccount|createUser(WithEmail)?\b|" \
              r"createUserWithEmailAndPassword|auth\.signUp|/register\b|/signup\b|/sign_up\b|/accounts?/create"
CREATE_TEXT = r"(?i)create (an |your )?account|sign up\b|register\b|hesap oluştur|kayıt ol|üye ol|konto erstellen|" \
              r"créer un compte|crear (una )?cuenta"
DELETE_CODE = r"deleteAccount|delete_account|deleteUser|accountDeletion|AccountDeletion|deactivateAccount|closeAccount|" \
              r"/account/delete|/accounts?/[^\s'\"]*delete|currentUser[^\n]{0,30}\.delete\(|user\.delete\(\)|" \
              r"removeAccount|requestAccountDeletion|deleteMyAccount"
DELETE_TEXT = scan.terms.rx("account_delete")
APPLE_LOGIN = r"ASAuthorizationAppleIDProvider|SignInWithAppleButton|sign_in_with_apple|expo-apple-authentication|" \
              r"appleAuth|AppleAuthentication|AppleIDProvider"
THIRD_LOGIN = {
    "Google": r"GoogleSignIn|google_sign_in|@react-native-google-signin|GIDSignIn",
    "Facebook": r"FBSDKLoginKit|LoginManager\(\)|flutter_facebook_auth|react-native-fbsdk|FacebookLogin",
    "X / Twitter": r"twitter_login|TwitterKit|@react-native-twitter-signin",
    "LinkedIn": r"linkedin_login|LinkedInSignIn",
    "Amazon": r"LoginWithAmazon|AMZNAuthorizationManager",
    "WeChat": r"WechatOpenSDK|fluwx|react-native-wechat",
}
REACHABILITY = r"NWPathMonitor|Reachability|SCNetworkReachability|connectivity_plus|internet_connection_checker|" \
               r"@react-native-community/netinfo|NetInfo\.|Connectivity\.|isConnected|networkStatus|onlineManager"
REMOTE_CONFIG = r"firebase_remote_config|RemoteConfig|LaunchDarkly|launchdarkly|Statsig|statsig|ConfigCat|configcat|" \
                r"Optimizely|optimizely|GrowthBook|growthbook|Unleash|unleash|Flagsmith|flagsmith|PostHog.*feature|" \
                r"featureFlag|FeatureFlag|feature_flag"
CODE_PUSH = {
    "react-native-code-push": ("SUGGESTION", "JavaScript update; must not change the app's main purpose or add features "
                                        "that skip review (developer agreement 3.3.1(B), 2.5.2, 2.3.1)."),
    "expo-updates": ("SUGGESTION", "OTA update; same conditions: main purpose unchanged, new features go through review (2.5.2, 2.3.1)."),
    "shorebird": ("SUGGESTION", "Dart code patches; same conditions (2.5.2, 2.3.1)."),
    "JSPatch": ("REJECTION RISK", "Changing native code with a downloaded script is rejected under 2.5.2."),
    "Rollout": ("REJECTION RISK", "Changing native code with a downloaded script is rejected under 2.5.2."),
}
HTTP_URL = re.compile(r"""['"`]http://([A-Za-z0-9.-]+)""")
HTTP_OK_HOST = re.compile(r"^(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|"
                          r"(www\.)?w3\.org|schemas\..*|.*\.schemas\..*|ns\.adobe\.com|purl\.org|xmlns\..*|"
                          r"(www\.)?example\.(com|org|net)|.*\.(local|test|invalid|example|localhost)|[^.]+)$", re.I)
# XML / XMP / RSS namespace identifiers: they look like addresses but are not network requests (e.g. NetNewsWire, Element X).
NS_HOST = re.compile(r"^(ns\.(apple|adobe)\.com|www\.w3\.org|purl\.org|xmlns\.com|search\.yahoo\.com|"
                     r"www\.rssboard\.org|www\.itunes\.com|backend\.userland\.com|schemas\.\S+|"
                     r"www\.georss\.org|webns\.net|wellformedweb\.org|madskills\.com)$")
FIXTURE_DIR = re.compile(r"(?i)/(templates?|fixtures?|mocks?|stubs?|samples?|testdata|sample-data)/")
SECRETS = [
    ("OpenAI API key", r"\bsk-(proj-)?[A-Za-z0-9_-]{20,}\b"),
    ("Anthropic API key", r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    ("AWS access key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("Stripe secret key", r"\b(sk|rk)_live_[A-Za-z0-9]{16,}\b"),
    ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    ("Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    ("Private key (PEM)", r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ("Google service account", r"\"type\"\s*:\s*\"service_account\""),
]
DEV_SCREEN = re.compile(r"(?i)(debug|developer|betatools|designsystem|internal|playground|sample|example|preview|"
                        r"mock|fixture|stub|fake)")


def text_files(p):
    return [f for f in p.files if f.lower().endswith((".arb", ".strings", ".xcstrings", ".json", ".po", ".yml", ".yaml"))
            and re.search(r"(?i)(l10n|locale|i18n|lproj|translations|strings|lang)", f) and "node_modules" not in f]


def mask(s: str) -> str:
    return s[:6] + "…" + s[-2:] if len(s) > 10 else "…"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p = scan.load_profile(a.root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("NW", p, "network scan")
    flags = p.mod.summary_flags(p)
    files = scan.code_files(p)
    tfiles = text_files(p)
    texts = "\n".join(scan.p_read(f, 3_000_000) for f in tfiles[:400])
    deps = "\n".join(scan.p_read(f) for f in p.files if os.path.basename(f) in
                     ("pubspec.yaml", "package.json", "Podfile", "Package.swift", "Cartfile"))
    deps += "\n".join(re.findall(r'repositoryURL = "([^"]+)"', "\n".join(
        scan.p_read(f, 5_000_000) for f in p.files if f.endswith("project.pbxproj"))))

    if not flags["network"] and not flags["account"]:
        rep.skip("NW-10…16", "no network and no accounts (offline app)")
    else:
        # NW-10: account creation ↔ deletion (5.1.1(v))
        cc, cfirst = scan.count(p, CREATE_CODE, files=files)
        ct = re.search(CREATE_TEXT, texts)
        dc, dfirst = scan.count(p, DELETE_CODE, files=files)
        dt = re.search(DELETE_TEXT, texts)
        if flags["account"]:
            if not (cc or ct):
                # Signing in with Apple, Google or a hosted auth service creates the account on first use, with no
                # "sign up" wording anywhere. Real fixes citing 5.1.1(v) showed this is the common case.
                # Google or Facebook sign-in alone is left out: it can be only for reaching a user's Drive or photos.
                hosted = any(k == "capability:Sign in with Apple" or k in ("capability:sign-in:with Apple", "capability:sign-in:Firebase Auth",
                                                                           "capability:sign-in:Supabase/Auth0/Clerk/Amplify") for k in p.items)
                if dc or dt:
                    rep.add("NW-10", "INFO", "Account deletion flow exists",
                            f"{p.rel(dfirst[0])}:{dfirst[1]}" if dfirst else f"text: {dt.group(0)!r}",
                            "Is it easy to find in Settings, does it really delete (not just sign out): verify by hand.")
                elif hosted:
                    rep.add("NW-10", "REJECTION RISK", "Sign-in creates accounts, but no account deletion found", "code + dependencies",
                            "5.1.1(v): an app that creates accounts, also through third-party sign-in, must let the user start "
                            "deletion from INSIDE the app. If deletion goes to a web page, it must go directly to that page.")
                else:
                    rep.add("NW-10", "SUGGESTION", "Accounts exist, no account deletion and no sign of account creation", "—",
                            "If accounts are only created elsewhere (a self-hosted server, an admin), read the scope of 5.1.1(v) "
                            "in Apple's current text. If the app can create them, deletion must be inside the app.")
            elif not (dc or dt):
                # The word "Register" alone is no proof: it may be device / server registration (e.g. Home Assistant).
                rep.add("NW-10", "REJECTION RISK" if cc else "SUGGESTION", "Accounts can be created in the app but no account deletion was found",
                        f"{p.rel(cfirst[0])}:{cfirst[1]}" if cfirst else f"text: {ct.group(0)!r}",
                        "5.1.1(v): an app that can create accounts must let the user start account deletion (not just deactivation) "
                        "from INSIDE the app. If deletion goes to a web page, it must go directly to that page.")
            elif dc or dt:
                rep.add("NW-10", "INFO", "Account deletion flow exists",
                        f"{p.rel(dfirst[0])}:{dfirst[1]}" if dfirst else f"text: {dt.group(0)!r}",
                        "Is it easy to find in Settings, does it really delete (not just sign out): verify by hand.")

        # NW-11: third-party sign-in ↔ equivalent privacy-conditioned sign-in (4.8)
        third = [name for name, rx in THIRD_LOGIN.items() if re.search(rx, deps) or scan.count(p, rx, files=files)[0]]
        apple = re.search(APPLE_LOGIN, deps) or scan.count(p, APPLE_LOGIN, files=files)[0]
        if third and not apple:
            # Google sign-in to connect a cloud service (Drive) is not a primary account (e.g. VLC) → outside 4.8.
            cloud = re.search(r"GoogleAPIClientForREST/Drive|googleapis/drive|drive\.file|DriveService", deps)
            rep.add("NW-11", "SUGGESTION" if cloud else "REJECTION RISK",
                    f"Third-party sign-in present ({', '.join(third)}), no Sign in with Apple",
                    "dependency / code",
                    "4.8: if third-party sign-in is used for the primary account, also offer an equivalent sign-in that collects only "
                    "name + email, allows hiding the email and does not track for ads (Sign in with Apple does "
                    "this). Exceptions (own account system only, education / enterprise, specific service client) come from the official text.")

        # NW-12: offline state
        if flags["network"] and not (scan.count(p, REACHABILITY, files=files)[0] or re.search(REACHABILITY, deps)):
            rep.add("NW-12", "SUGGESTION", "Network is used, connection state is never monitored",
                    "NWPathMonitor / connectivity_plus / NetInfo not found",
                    "What happens with no connection? Review can also happen with the network down or on IPv6-only; a crash or blank "
                    "screen is a 2.1 rejection. Try it on the simulator with no network (network-chaos).")

        # NW-13: unencrypted http
        seen = set()
        for f, n, line, m in scan.grep(p, HTTP_URL, files=files):
            host = m.group(1).lower()
            if host.endswith(".") or re.search(r"hasPrefix|startsWith|replacingOccurrences|\.replace\(|BEGINSWITH", line):
                continue  # code that recognizes or rewrites an address, not a connection
            if HTTP_OK_HOST.match(host) or DEV_SCREEN.search(p.rel(f)) or FIXTURE_DIR.search("/" + p.rel(f)) \
                    or host in seen or re.search(r"(?i)xmlns|namespace|\.dtd\b|dtds/|schema", line) \
                    or NS_HOST.match(host):
                continue
            near = "\n".join(scan.p_read(f).splitlines()[max(0, n - 3):n])
            if re.search(r"(?i)\b(fake|dummy|placeholder|throwaway|example|sample|parse only|just for parsing)\b", near):
                continue  # a fake address built only for parsing
            seen.add(host)
            rep.add("NW-13", "USER BUG", f"Unencrypted connection: http://{host}", f"{p.rel(f)}:{n}",
                    "Without an ATS exception iOS blocks this request (the feature fails); with one, data travels unencrypted (1.6). Use https.")

        # NW-14: remote config / feature flag (NW-P2)
        rc = re.search(REMOTE_CONFIG, deps)
        rcc, rfirst = scan.count(p, REMOTE_CONFIG, files=files)
        if rc or rcc:
            rep.add("NW-14", "INFO", "Remote config / feature flag present",
                    rc.group(0) if rc else f"{p.rel(rfirst[0])}:{rfirst[1]}",
                    "Gradual rollout and A/B testing are legitimate. Enabling a new feature AFTER review or hiding a feature "
                    "from the reviewer is grounds for rejection / removal under 2.3.1. Are flags in their store state during review?")

    # NW-15: code updates (independent of the network flag)
    for name, (sev, note) in CODE_PUSH.items():
        if re.search(re.escape(name), deps):
            rep.add("NW-15", sev, f"Code update from outside the app: {name}", "dependency file", note)

    # NW-16: secret key (masked)
    secret_files = [f for f in p.files if os.path.splitext(f)[1] in (".swift", ".m", ".dart", ".ts", ".tsx", ".js",
                    ".jsx", ".kt", ".cs", ".plist", ".json", ".xcconfig", ".env", ".yaml", ".yml", ".properties")
                    and "/node_modules/" not in f and "/Pods/" not in f and not scan.TEST_PATH.search("/" + p.rel(f))]
    for label, rx in SECRETS:
        for f, n, line, m in scan.grep(p, rx, files=secret_files, max_hits=20):
            if label.startswith("Private key"):  # the header text alone is not a key (e.g. Nextcloud E2EE formatting)
                rest = line[m.end():] + "".join(scan.p_read(f, 2_000_000).splitlines()[n:n + 1])
                if not re.search(r"[A-Za-z0-9+/]{40}", rest):
                    continue
            rep.add("NW-16", "USER BUG", f"Possible secret key in code: {label}", f"{p.rel(f)}:{n} `{mask(m.group(0))}`",
                    "It can be extracted from the app bundle. Revoke and rotate the key; move the secret work to a server. "
                    "A sample / test key is not a finding.")

    # NW-17: demo account reminder for review
    if flags["account"]:
        rep.add("NW-17", "INFO", "Features that require an account exist",
                "profile", "A working demo account for review goes in App Review Information (store-readiness SR-88); the account "
                "must stay open and the server up throughout review. Claude does not ask for passwords; the user types them into the field.")

    rep.emit(a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
