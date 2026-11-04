#!/usr/bin/env python3
"""apptest-lifecycle — inventory and candidates for lifecycle transitions (foreground / inactive / background /
killed / cold start): transition listeners, draft protection or state restoration, leaving saves to willTerminate,
the app switcher cover in a locked / sensitive app, re-reading permissions on returning to the foreground,
memory warnings.

Standard library only (Python 3.8+); does NOT write to the project.

    python3 -I lc_scan.py <project_root> [--json]
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

# Transition listener (any of these).
LIFECYCLE = r"WidgetsBindingObserver|didChangeAppLifecycleState|AppLifecycleListener|AppLifecycleState\.|" \
            r"@Environment\(\\\.scenePhase\)|\.onChange\(of:\s*scenePhase|scenePhase\b|" \
            r"applicationDidEnterBackground|applicationWillResignActive|applicationDidBecomeActive|" \
            r"applicationWillEnterForeground|sceneDidEnterBackground|sceneWillResignActive|sceneDidBecomeActive|" \
            r"sceneWillEnterForeground|didEnterBackgroundNotification|willResignActiveNotification|" \
            r"didBecomeActiveNotification|willEnterForegroundNotification|AppState\.addEventListener|" \
            r"useAppState\b|\bOnSleep\(\)|\bOnResume\(\)|Window\.(Stopped|Resumed|Deactivated|Activated)\b|" \
            r"override\s+(async\s+)?void\s+(OnResignActivation|DidEnterBackground|WillEnterForeground|OnActivated)\b|" \
            r"OnApplicationPause|OnApplicationFocus|NOTIFICATION_APPLICATION_(PAUSED|RESUMED|FOCUS_OUT)"
# Game engines: Unity OnApplicationPause, Godot NOTIFICATION_APPLICATION_*; libGDX separately (file level, GDX_APP).
GDX_APP = re.compile(r"implements\s+[\w., ]*ApplicationListener|extends\s+(ApplicationAdapter|Game)\b")
GDX_PAUSE = re.compile(r"public\s+void\s+(pause|resume)\s*\(\s*\)")
# Return to foreground / activation.
# ".active" only in a scenePhase context; "active" only in an AppState comparison (other enums are excluded).
RESUME = r"AppLifecycleState\.resumed|onResume\s*:|(scenePhase|newPhase|phase)\s*==\s*\.active|\.onChange\(of:\s*scenePhase|" \
         r"applicationDidBecomeActive|sceneDidBecomeActive|applicationWillEnterForeground|sceneWillEnterForeground|" \
         r"didBecomeActiveNotification|willEnterForegroundNotification|OnApplicationFocus|NOTIFICATION_APPLICATION_RESUMED|" \
         r"(nextAppState|appState|state)\w*\s*===?\s*" \
         r"['\"]active['\"]|\bOnResume\(\)|Window\.(Resumed|Activated)\b|void\s+(WillEnterForeground|OnActivated)\b"
# Inactive (app switcher, Control Center, auth dialog).
INACTIVE = r"AppLifecycleState\.inactive|onInactive\s*:|(scenePhase|newPhase|phase)\s*==\s*\.inactive|" \
           r"case\s+\.inactive\b|applicationWillResignActive|sceneWillResignActive|willResignActiveNotification|" \
           r"(nextAppState|appState|state)\w*\s*===?\s*['\"]inactive['\"]|Window\.Deactivated\b|" \
           r"void\s+OnResignActivation\b"
# Work that covers content in the body of an inactive handler (adding a view, a hidden state, blur).
COVER_BODY = re.compile(r"(?i)addSubview|AddSubview|overlay|obscur|blur|isHidden\s*=\s*true|"
                        r"alpha\s*=\s*0|opacity\s*\(\s*0|cover|splash|snapshot|privacy|redact|" \
                        r"setState\(\s*\(\)\s*=>\s*_?\w*(obscur|hid|cover|blur|lock)\w*\s*=\s*true")
WRITE_BODY = re.compile(r"(?i)\b(save|persist|flush|commit|write|sync|backup|store|kaydet|yedek)\w*\s*\(")
TERMINATE = r"applicationWillTerminate|willTerminateNotification|onDetach\s*:|override\s+void\s+WillTerminate\b"
# Draft / state protection.
RESTORE = r"@SceneStorage|restorationIdentifier|stateRestorationActivity|NSUserActivity|RestorationMixin|" \
          r"restorationScopeId|RestorableProperty|PageStorageKey|\bdraft\w*\b|\bDraft\w*\b|taslak|" \
          r"autosave|autoSave|persistNavigationState|initialState\s*=\s*\{|onStateChange\s*=\s*\{"
TEXT_INPUT = r"TextField\(|TextFormField\(|TextEditor\(|UITextView\b|UITextField\b|<TextInput\b|\bEntry\b|\bEditor\b"
# App lock / biometrics (sensitive content) and cover.
LOCK = r"LocalAuthentication|LAContext|local_auth|LocalAuthentication\.authenticate|expo-local-authentication|" \
       r"react-native-biometrics|BiometricAuthentication|Plugin\.Fingerprint"
COVER = r"(?i)privacy\w*(screen|cover|overlay|shield|blur)|blur\w*(on|when)\w*(background|inactive)|" \
        r"secure\w*(screen|cover|overlay)|appSwitcher\w*(cover|overlay|blur)|snapshot\w*(cover|blur|hide)"
# Reading permission status (checks whether it is re-read).
PERMISSION_READ = r"authorizationStatus|getNotificationSettings|notificationSettings\(|Permission\.\w+\.status|" \
                  r"\.status\b.*Permission|check(Notifications|Permission)\w*\(|getPermissionsAsync|" \
                  r"Permissions\.(check|query)|permissionGranted\(|CheckStatusAsync"
MEMORY = r"didReceiveMemoryWarning|didReceiveMemoryWarningNotification|didHaveMemoryPressure|" \
         r"handleMemoryPressure|AppState\.addEventListener\(\s*['\"]memoryWarning|OnTrimMemory|onLowMemory"
HEAVY = r"Image\.network|CachedNetworkImage|AsyncImage|SDWebImage|Kingfisher|Nuke\b|FastImage|PHImageManager|" \
        r"AVPlayer|VideoPlayer|video_player|MapKit|GoogleMap|mapbox"


def _files_with(p, pattern, files):
    rx = re.compile(pattern)
    out = []
    for f in files:
        for n, line in scan.lines(f):
            if rx.search(line):
                out.append((f, n))
                break
    return out


_CASE = re.compile(r"^\s*(case\b|default\b)")


def _body(rows, i, cap=60):
    """The BODY starting at the header line: up to the next case in a switch branch; otherwise to the end of the
    block by matching braces (at most `cap` lines). Braces inside strings are counted roughly."""
    head = rows[i][1]
    out = [head]
    if _CASE.match(head):
        for _, line in rows[i + 1:i + cap]:
            if _CASE.match(line) or line.strip().startswith("}"):
                break
            out.append(line)
        return " ".join(out)
    depth, opened = 0, False
    for _, line in rows[i:i + cap]:
        if line is not head:
            out.append(line)
        depth += line.count("{") - line.count("}")
        opened = opened or "{" in line
        if opened and depth <= 0:
            break
    return " ".join(out)


def _bodies(p, head, files, span=None):
    """(file, line, body) — the body of each place matching the header pattern (at most `span` lines if given)."""
    rx = re.compile(head)
    for f in files:
        rows = list(scan.lines(f))
        for i, (n, line) in enumerate(rows):
            if rx.search(line):
                yield f, n, _body(rows, i, cap=span or 60)


def scan_project(root: str, as_json: bool):
    p = scan.load_profile(root)
    if scan.guard_unknown(p):
        return 0
    flags = p.mod.summary_flags(p)
    rep = scan.Report("LC", p, "lifecycle — transitions and state protection")
    app = scan.code_files(p)

    lc = _files_with(p, LIFECYCLE, app)
    resume = _files_with(p, RESUME, app)
    # libGDX: pause()/resume() are lifecycle only in the application class (not in game objects).
    for f in app:
        if scan.lang_of(f) in ("java", "kotlin"):
            t = scan.p_read(f, 300_000)
            m = GDX_PAUSE.search(t) if GDX_APP.search(t) else None
            if m:
                n = t.count("\n", 0, m.start()) + 1
                lc.append((f, n))
                if "resume" in t[m.start():m.end() + 400]:
                    resume.append((f, n))
    inactive = _files_with(p, INACTIVE, app)
    if lc:
        rep.add("LC-10", "INFO", f"Transition listeners: {len(lc)} files (foreground return {len(resume)}, inactive "
                f"{len(inactive)})", "; ".join(f"{p.rel(f)}:{n}" for f, n in lc[:6]),
                "The test tour triggers every transition in these files (references/transitions.md).")
    else:
        rep.add("LC-10", "INFO", "No transition listener found", "—",
                "The app does not react to going to the background; still run the kill-and-reopen and restore tour.")

    # LC-11: text fields exist, no trace of draft / state protection.
    inputs = _files_with(p, TEXT_INPUT, app)
    restore = _files_with(p, RESTORE, app)
    if len(inputs) >= 2 and not restore:
        rep.add("LC-11", "SUGGESTION", f"Text fields in {len(inputs)} files; no trace of draft protection / state restoration",
                "; ".join(p.rel(f) for f, _ in inputs[:5]),
                "If the system kills the app in the background, a half-filled form is lost. Show it with a test first (LC-S3); "
                "it matters on long forms, on short forms it is a design decision.")
    elif restore:
        rep.add("LC-11", "INFO", f"Trace of draft / state protection: {len(restore)} files",
                "; ".join(f"{p.rel(f)}:{n}" for f, n in restore[:4]), "Verify the forms it covers with LC-S3.")

    # LC-12: saving in willTerminate.
    for f, n, body in _bodies(p, TERMINATE, app):
        if not WRITE_BODY.search(body):
            continue
        rep.add("LC-12", "SUGGESTION", "Saving is tied to the termination event (applicationWillTerminate)",
                f"{p.rel(f)}:{n}",
                "iOS does NOT call this event when it kills an app in the background: a save done here usually "
                "never runs. Save on going to the background or at the moment of change; verify with LC-S4.")

    # LC-13: lock / biometrics exist, no trace of a cover in the inactive state.
    lock = _files_with(p, LOCK, app)
    if lock:
        # Body = the handler itself (in a switch branch only that case): neighbouring cases do not count as a cover.
        cover = _files_with(p, COVER, app) + [(f, n) for f, n, b in _bodies(p, INACTIVE, app)
                                              if COVER_BODY.search(b)]
        if not cover:
            rep.add("LC-13", "SUGGESTION", "App lock / biometrics exist; no trace of covering content in the app switcher",
                    "; ".join(f"{p.rel(f)}:{n}" for f, n in lock[:3]),
                    "The app switcher shows an image of the last screen; in a locked app the content is visible. "
                    "The cover may exist under another name: verify the image with LC-S2.")
        else:
            rep.add("LC-13", "INFO", "Lock exists; trace of a cover while inactive",
                    f"{p.rel(cover[0][0])}:{cover[0][1]}", "LC-S2: verify that locking happens only on going to the background, "
                    "NOT during the 'inactive' caused by the auth dialog.")

    # LC-14: permissions are used and status is read, but there is no foreground-return listener.
    if flags.get("permissions") or any(k.startswith("capability:notifications") for k in p.items):
        reads = _files_with(p, PERMISSION_READ, app)
        if reads and not resume:
            rep.add("LC-14", "SUGGESTION", "Permission status is read, apparently not re-read on returning to the foreground",
                    "; ".join(f"{p.rel(f)}:{n}" for f, n in reads[:3]),
                    "When the user changes the permission in Settings and returns, the screen shows the old state. Verify with LC-S5.")

    # LC-15: heavy images / media, no memory warning listener.
    heavy = [x for x in _files_with(p, HEAVY, app) if os.path.basename(x[0]) != "Package.swift"]
    mem = _files_with(p, MEMORY, app)
    if mem:
        rep.add("LC-15", "INFO", f"Memory warning listener: {len(mem)} files", f"{p.rel(mem[0][0])}:{mem[0][1]}",
                "Verify with LC-S6 that there is no data loss / crash during the warning.")
    elif len(heavy) >= 3:
        # INFO: image cache libraries (SDWebImage, Kingfisher, Nuke, AsyncImage, NSCache,
        # CachedNetworkImage) purge themselves on a memory warning; no listener is not an error by itself
        # (e.g. it fired on all 6 live apps tested).
        rep.add("LC-15", "INFO", f"Images / video / maps in {len(heavy)} files, the app has no memory warning listener",
                "; ".join(p.rel(f) for f, _ in heavy[:4]),
                "Cache libraries usually purge themselves. If the app has its own large in-memory cache, "
                "try LC-S6 (no crash / data loss on the warning).")

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
