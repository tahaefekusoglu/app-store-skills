#!/usr/bin/env python3
"""apptest-network-chaos — inventory and candidates for network fault resilience: client libraries,
whether the base URL can change in tests, network mocks, clients WITHOUT a timeout (Flutter `http`,
axios, fetch, dio default), handling session loss (401), showing raw error text to the user,
offline queue / retry.

Connectivity never being monitored → network NW-12 (not repeated here).
Standard library only (Python 3.9+); does NOT write to the project. "Not applicable" for an app with no network.

    python3 -I nc_scan.py <project_root> [--json]
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

# (pattern, languages) — a client is searched only in files of its own language (Core Data fetch() in Swift and
# http.get() in a Node test server must not count as clients).
CLIENTS = {
    "URLSession": (r"\bURLSession\b|NSURLSession\b", {"swift", "objc"}),
    "Alamofire": (r"\bimport Alamofire\b|\bAF\.request\(", {"swift"}),
    "Flutter http": (r"package:http/http\.dart", {"dart"}),
    "dio": (r"package:dio/|\bDio\(", {"dart"}),
    "fetch": (r"(?<![\w.])fetch\(\s*[`'\"\w]", {"js"}),
    "axios": (r"\bfrom ['\"]axios['\"]|require\(['\"]axios['\"]\)|\baxios\.(get|post|put|create)\(", {"js"}),
    "HttpClient (.NET)": (r"\bnew HttpClient\(|IHttpClientFactory|\bHttpClient\s+\w+\s*[=;]", {"csharp"}),
    "GraphQL / Apollo": (r"\bimport Apollo\b|ApolloClient|graphql_flutter|@apollo/client|\burql\b", None),
    "WebSocket": (r"URLSessionWebSocketTask|WebSocketChannel|new WebSocket\(|web_socket_channel|Starscream", None),
    "Firebase / Supabase": (r"cloud_firestore|FirebaseFirestore|Firestore\.firestore\(\)|supabase_flutter|"
                            r"@supabase/|SupabaseClient", None),
}
# Ways to change the base URL in tests.
# Only sources that can be given from OUTSIDE (environment variable, launch argument, build define, xcconfig).
BASE_URL = r"(?i)(base_?url|api_?url|api_?host|server_?url|endpoint|host)\w*\s*[:=]\s*[^;\n]{0,40}(process\.env|" \
           r"Platform\.environment|String\.fromEnvironment|ProcessInfo\.processInfo\.(environment|arguments)|" \
           r"Bundle\.main\.object\(forInfoDictionaryKey|Environment\.GetEnvironmentVariable|dotenv|Config\.\w+_URL|" \
           r"Constants\.expoConfig|launchArguments)|fromEnvironment\(\s*['\"]\w*(URL|HOST|SERVER|ENDPOINT)"
MOCK = r"URLProtocol|OHHTTPStubs|\bMocker\b|MockWebServer|MockClient\(|http_mock_adapter|DioAdapter|nock\(|" \
       r"\bmsw\b|setupServer\(|fetchMock|jest\.mock\([\"']axios|MockURLSession|\bMockService\(|" \
       r"(Mock|Fake)\w*(Api|API|Network|Http|HTTP)\w*"
# Timeout setting (per client).
TIMEOUT = {
    "Flutter http": r"\.timeout\(\s*(const\s+)?Duration|IOClient\(|connectionTimeout\s*=",
    "dio": r"connectTimeout|receiveTimeout|sendTimeout",
    "axios": r"\btimeout\s*:\s*\d|axios\.defaults\.timeout|\.timeout\s*=\s*\d",
    "fetch": r"AbortController|AbortSignal\.timeout|signal\s*:|timeoutPromise|Promise\.race\(",
    "HttpClient (.NET)": r"\.Timeout\s*=|TimeSpan\.From\w+\(\s*\d+\s*\)",
}
DEFAULT_NOTE = {
    "Flutter http": "package:http has no default timeout: if the connection hangs, the request never ends.",
    "dio": "dio has no timeout defined by default (waits without limit).",
    "axios": "axios default timeout is 0 = unlimited.",
    "fetch": "fetch has no timeout of its own (on iOS URLSession's ~60 s applies underneath; the UI waits that long).",
    "HttpClient (.NET)": "HttpClient default is 100 s.",
}
# 401 only in a status code context (an enum value of 401 must not count).
UNAUTH = r"(?i)(status\w*|code)\s*(==|===|!=|:|case|is)\s*401\b|case\s+401\b|401\s*(=>|:)\s|HttpStatusCode\.Unauthorized|" \
         r"\.unauthorized\b|refresh_?token|token_?expired|session_?expired|session_?ended|force_?logout|" \
         r"invalid_?token|\breauth\w*"
RAW_ERROR = {
    "dart": r"Text\(\s*(e|err|error|exception)\.toString\(\)|Text\(\s*['\"]\$\{?(e|err|error)\b|"
            r"SnackBar\(\s*content\s*:\s*Text\(\s*(e|err|error)\.toString\(\)",
    "swift": r"Text\(\s*(error|err|e)\.localizedDescription|message\s*:\s*Text\(\s*(error|err)\.localizedDescription|"
             r"\.alert\([^)]*(error|err)\.localizedDescription|message:\s*(error|err)\.localizedDescription",
    "js": r"Alert\.alert\([^)]*(error|err|e)\.message|<Text[^>]*>\s*\{\s*(error|err|e)\.message\s*\}|"
          r"toast\w*\(\s*(error|err|e)\.message",
    "csharp": r"DisplayAlert\([^)]*(ex|e|exception)\.Message",
}
RETRY = r"(?i)retry\w*|backoff|exponential|maxAttempts|max_attempts|offline\w*queue|pending\w*(requests|uploads)|" \
        r"outbox|syncQueue|sync_queue"


def _deps(p) -> str:
    out = []
    for f in p.files:
        b = os.path.basename(f)
        if b in ("pubspec.yaml", "package.json", "Podfile", "Package.swift", "Package.resolved") or b.endswith(".csproj"):
            if "/node_modules/" not in f and p.mod.ios_path(f):
                out.append(scan.p_read(f, 200_000))
    return "\n".join(out)


def scan_project(root: str, as_json: bool):
    p = scan.load_profile(root)
    if scan.guard_unknown(p):
        return 0
    flags = p.mod.summary_flags(p)
    rep = scan.Report("NC", p, "network-chaos — network fault resilience")
    if not flags.get("network"):
        rep.skip("NC-*", "the app does not use the network (profile: no ag)")
        rep.emit(as_json)
        return 0
    app = scan.code_files(p)
    everything = scan.code_files(p, include_tests=True)
    deps = _deps(p)

    used = {}
    for name, (pat, langs) in CLIENTS.items():
        files = [f for f in app if not langs or scan.lang_of(f) in langs]
        c, first = scan.count(p, pat, files=files)
        if c:
            used[name] = (c, first)
    if used:
        rep.add("NC-10", "INFO", "Network clients: " + ", ".join(f"{k} ({v[0]})" for k, v in used.items()),
                "; ".join(f"{p.rel(v[1][0])}:{v[1][1]}" for v in list(used.values())[:4]),
                "Fault injection goes below this layer (mock) or in front of it (proxy).")

    bc, bfirst = scan.count(p, BASE_URL, files=app)
    mc, mfirst = scan.count(p, MOCK, files=everything)
    rep.add("NC-11", "INFO",
            f"Base URL changeable in tests: {'yes' if bc else 'not found'} · network mock: "
            f"{'present' if mc else 'absent'}",
            (f"{p.rel(bfirst[0])}:{bfirst[1]}" if bc else "—") + (f"; {p.rel(mfirst[0])}:{mfirst[1]}" if mc else ""),
            "If the address can change, point the app at nc_proxy.py; if there is a mock, give faults at unit "
            "level. If neither, a manual tour only (references/faults.md §By hand).")

    for name, (c, first) in used.items():
        tp = TIMEOUT.get(name)
        if not tp:
            continue
        if not scan.count(p, tp, files=app)[0]:
            rep.add("NC-12", "SUGGESTION", f"{name}: no timeout setting found", f"{p.rel(first[0])}:{first[1]}",
                    DEFAULT_NOTE[name] + " Try NC-S3 (hanging connection) to see what the user sees.")

    if flags.get("account"):
        uc, ufirst = scan.count(p, UNAUTH, files=app)
        if not uc:
            rep.add("NC-13", "SUGGESTION", "Accounts exist; no trace of handling session loss (401 / expired token)", "—",
                    "What does the app do when the token becomes invalid on the server? Try NC-S6.")
        else:
            rep.add("NC-13", "INFO", f"Trace of handling session loss ({uc} places)", f"{p.rel(ufirst[0])}:{ufirst[1]}",
                    "NC-S6: is unfinished work / a draft kept after logging in again?")

    seen = 0
    for lg, pat in RAW_ERROR.items():
        files = [f for f in app if scan.lang_of(f) == lg]
        for f, n, _l, _m in scan.grep(p, pat, files=files, max_hits=50):
            rep.add("NC-14", "SUGGESTION", "Raw error text shown to the user", f"{p.rel(f)}:{n}",
                    "On a network error, technical and often untranslated text appears, like 'The operation couldn't be "
                    "completed (NSURLErrorDomain -1001)'. See which text it shows with NC-S1 … S5.")
            seen += 1
    rc, rfirst = scan.count(p, RETRY, files=app)
    rep.add("NC-15", "INFO", f"Trace of retry / offline queue: {'present (' + str(rc) + ' places)' if rc else 'absent'}",
            f"{p.rel(rfirst[0])}:{rfirst[1]}" if rc else "—",
            "If present, try NC-S8 (when the network returns the queue sends once, no double record — rapid-input RI-S9).")
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
