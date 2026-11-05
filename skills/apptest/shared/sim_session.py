#!/usr/bin/env python3
"""apptest: temporary simulator session (CONVENTIONS §5.2–5.4, §7).

Opens a temporary simulator for a tour WITHOUT TOUCHING the user's simulator;
writes every change to a persistent ledger and reverts it with `cleanup`.
macOS + Xcode only (xcrun simctl).

    python3 -I sim_session.py create  --project <root> [--device "iPhone 18 Pro"] [--runtime latest]
                                      [--status-bar] [--appearance light|dark] [--content-size <size>]
                                      [--software-keyboard]
    python3 -I sim_session.py status  --project <root>
    python3 -I sim_session.py cleanup --project <root> --udid <UDID> [--force]

create prints the UDID; the UDID also proves ownership of the session. Lock:
~/.cache/apptest/<project-key>/lock, taken atomically; a second tour in the same project
will not start. The lock carries an EXPIRY (--ttl-hours, default 6): the shell that calls
create closes right away, so PID lifetime says nothing about the session. An expired
session is stale and is taken over. cleanup deletes only its own session: on a live session the UDID must
match; --force only if the user explicitly asks. A failed step says "Cleanup failed" (exit 1) and
the record is kept; a second cleanup resumes where it stopped. create refuses to run while an
uncleaned old session exists.
Ledger: ~/.cache/apptest/<project-key>/state.json. The hardware keyboard setting
affects all simulators: ~/.cache/apptest/keyboard.json counts across projects.

Wrap a long tour with `caffeinate -dimsu <command>` so the Mac screen does not sleep
(for that command only; changes no setting). Details: store-assets
references/shot-tour.md, "Known traps".
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid

# A non-UTF-8 Windows console must not crash on non-ASCII letters (every OS).
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

CACHE = os.path.expanduser("~/.cache/apptest")
KEYBOARD_WAIT = 60  # seconds


def sh(*args, check=True) -> str:
    r = subprocess.run(list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(args)}\n{r.stderr.strip()}")
    return r.stdout.strip()


def sh_rc(*args) -> tuple[int, str]:
    r = subprocess.run(list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stderr or "").strip()


def key_of(project: str) -> str:
    # realpath: symlinked paths to the same folder share one key (so the lock does not split).
    return hashlib.sha1(os.path.realpath(project).encode()).hexdigest()[:12]


def state_dir(project: str) -> str:
    d = os.path.join(CACHE, key_of(project))
    os.makedirs(d, exist_ok=True)
    return d


def load_state(project: str) -> dict:
    try:
        with open(os.path.join(state_dir(project), "state.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"changes": []}


def save_state(project: str, st: dict):
    # Atomic: if interrupted the old record stays intact (recovery info is not lost).
    path = os.path.join(state_dir(project), "state.json")
    tmp = f"{path}.{uuid.uuid4().hex}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_lock(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            info = json.load(fh)
        return info if isinstance(info, dict) else {}
    except (OSError, ValueError):
        return {}


def lock_is_live(info: dict) -> bool:
    if info.get("expires"):
        return time.time() < float(info["expires"])
    return bool(info.get("pid")) and pid_alive(int(info["pid"]))  # old-format lock


def take_lock(project: str, ttl_hours: float = 6.0) -> str:
    """Atomic: content goes to a temp file first; os.link never writes over an existing lock (no half-written lock is read)."""
    path = os.path.join(state_dir(project), "lock")
    token = uuid.uuid4().hex
    tmp = f"{path}.{token}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"token": token, "pid": os.getppid(), "started": time.strftime("%Y-%m-%d %H:%M"),
                   "expires": time.time() + ttl_hours * 3600, "job": "sim_session"}, fh)
    try:
        for _ in range(3):
            try:
                os.link(tmp, path)
                return token
            except FileExistsError:
                pass
            info = _read_lock(path)
            if lock_is_live(info):
                raise SystemExit(f"another tour is running in this project (started {info.get('started')}, {info.get('job')}); "
                                 "wait for it to finish")
            # Stale lock: rename succeeds for only one racer; a fresh lock taken in between is put back.
            aside = f"{path}.{token}.stale"
            try:
                os.rename(path, aside)
            except FileNotFoundError:
                continue
            if _read_lock(aside) != info:
                try:
                    os.link(aside, path)
                except FileExistsError:
                    pass
                os.remove(aside)
                continue
            os.remove(aside)
        raise SystemExit("could not take the lock; try again")
    finally:
        os.remove(tmp)


def _release_lock(project: str):
    try:
        os.remove(os.path.join(state_dir(project), "lock"))
    except FileNotFoundError:
        pass


class _KeyboardBook:
    """The hardware keyboard setting is system-wide: the first tour saves the old value, the last one restores it."""
    def __enter__(self):
        os.makedirs(CACHE, exist_ok=True)
        self.path = os.path.join(CACHE, "keyboard.json")
        self.fh = open(self.path + ".lock", "w")
        # Held across the `defaults` call too, so no tour can slip in between the record and the setting.
        # The OS releases it if the process dies. A timeout means a stuck tour must not hang this one.
        deadline = time.time() + KEYBOARD_WAIT
        while True:
            try:
                fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.time() >= deadline:
                    self.fh.close()
                    raise SystemExit("hardware keyboard setting is busy: another tour holds it; try again")
                time.sleep(0.05)
        try:
            with open(self.path, encoding="utf-8") as fh:
                self.data = json.load(fh)
        except (OSError, ValueError):
            self.data = {"holders": [], "old": None}
        return self

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh)
        os.replace(tmp, self.path)

    def __exit__(self, *exc):
        self.fh.close()


def latest_runtime() -> str:
    out = json.loads(sh("xcrun", "simctl", "list", "runtimes", "--json"))
    ios = [r for r in out.get("runtimes", []) if r.get("platform") == "iOS" and r.get("isAvailable")]
    if not ios:
        raise SystemExit("no usable iOS runtime")
    ios.sort(key=lambda r: [int(x) for x in re.findall(r"\d+", r.get("version", "0"))])
    return ios[-1]["identifier"]


def device_type(name: str) -> str:
    out = json.loads(sh("xcrun", "simctl", "list", "devicetypes", "--json"))
    for d in out.get("devicetypes", []):
        if d.get("name") == name:
            return d["identifier"]
    raise SystemExit(f"no such device type: {name!r} (xcrun simctl list devicetypes)")


def create(a):
    # The lock comes first: reading the record before it would race with another create.
    take_lock(a.project, getattr(a, "ttl_hours", 6.0))
    prev = load_state(a.project)
    if prev.get("udid") or prev.get("changes"):
        # Overwriting would lose the old simulator and the setting's old value.
        _release_lock(a.project)
        raise SystemExit(f"previous session not cleaned ({prev.get('udid') or 'settings record'}): run `cleanup` first; "
                         "if another tour is running, wait for it to finish")
    try:
        _create(a)
    except BaseException:
        # No half-finished setup: everything this call opened is reverted; if that fails, the record stays.
        _cleanup(a.project, quiet=True, udid=getattr(a, "_udid", None))
        raise


def _create(a):
    rt = latest_runtime() if a.runtime == "latest" else a.runtime
    udid = sh("xcrun", "simctl", "create", f"apptest-{key_of(a.project)}", device_type(a.device), rt)
    a._udid = udid  # the only record until a write below succeeds
    st = {"udid": udid, "device": a.device, "runtime": rt, "created": time.strftime("%Y-%m-%d %H:%M"), "changes": []}
    _note_udid(a.project, udid)
    save_state(a.project, st)
    sh("xcrun", "simctl", "boot", udid)
    sh("xcrun", "simctl", "bootstatus", udid, "-b", check=False)
    if a.status_bar:
        sh("xcrun", "simctl", "status_bar", udid, "override", "--time", "9:41", "--dataNetwork", "wifi",
           "--wifiMode", "active", "--wifiBars", "3", "--cellularMode", "active", "--cellularBars", "4",
           "--batteryState", "charged", "--batteryLevel", "100")
        st["changes"].append({"what": "status_bar", "undo": "status_bar clear"})
    if a.appearance:
        sh("xcrun", "simctl", "ui", udid, "appearance", a.appearance)
    if a.content_size:
        sh("xcrun", "simctl", "ui", udid, "content_size", a.content_size)
    if a.software_keyboard:
        with _KeyboardBook() as book:
            if not book.data["holders"]:
                book.data["old"] = sh("defaults", "read", "com.apple.iphonesimulator", "ConnectHardwareKeyboard",
                                      check=False) or None
            book.data["holders"].append(udid)
            # Record first, then change: if interrupted, the undo info survives.
            st["changes"].append({"what": "ConnectHardwareKeyboard"})
            save_state(a.project, st)
            book.save()
            sh("defaults", "write", "com.apple.iphonesimulator", "ConnectHardwareKeyboard", "-bool", "false")
    save_state(a.project, st)
    size = ""
    try:
        tmp = os.path.join(state_dir(a.project), "probe.png")
        sh("xcrun", "simctl", "io", udid, "screenshot", "--type=png", tmp)
        w = sh("sips", "-g", "pixelWidth", tmp).split()[-1]
        h = sh("sips", "-g", "pixelHeight", tmp).split()[-1]
        size = f" {w}×{h}"
        os.remove(tmp)
    except SystemExit:
        pass
    print(udid)
    print(f"# temporary simulator ready: {a.device} · {rt}{size} · cleanup: sim_session.py cleanup --project {a.project} --udid {udid}",
          file=sys.stderr)


def _note_udid(project: str, udid: str):
    path = os.path.join(state_dir(project), "lock")
    info = _read_lock(path)
    if info:
        info["udid"] = udid
        tmp = f"{path}.{uuid.uuid4().hex}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(info, fh)
        os.replace(tmp, path)


def _write_keyboard(old) -> str | None:
    if old is None:
        rc, err = sh_rc("defaults", "delete", "com.apple.iphonesimulator", "ConnectHardwareKeyboard")
        return None if rc == 0 or "does not exist" in err else err or "defaults delete failed"
    rc, err = sh_rc("defaults", "write", "com.apple.iphonesimulator", "ConnectHardwareKeyboard", "-bool",
                    "true" if str(old) in ("1", "true", "YES") else "false")
    return None if rc == 0 else err or "defaults write failed"


def _restore_keyboard(ch: dict, udid: str | None) -> str | None:
    """Error text or None. An old-format record ("old" field) belongs to this session only.
    The saved value is dropped only after the setting really changed, and the book stays locked
    meanwhile, so a failed restore can be retried and a new tour cannot be overridden."""
    if "old" in ch:
        return _write_keyboard(ch.get("old"))
    with _KeyboardBook() as book:
        holders = [h for h in book.data["holders"] if h != udid]
        if holders:  # another tour still uses it: it needs the setting
            book.data["holders"] = holders
            book.save()
            return None
        err = _write_keyboard(book.data.get("old"))
        if err:
            return err
        book.data = {"holders": [], "old": None}
        book.save()
    return None


def simulator_name(udid: str):
    """The simulator's name, "" if it no longer exists, None if the list could not be read."""
    rc, out = sh_rc("xcrun", "simctl", "list", "devices", "--json")
    if rc != 0:
        return None
    try:
        devices = json.loads(out).get("devices", {})
    except (ValueError, AttributeError):
        return None
    for group in devices.values() if isinstance(devices, dict) else []:
        for d in group if isinstance(group, list) else []:
            if isinstance(d, dict) and d.get("udid") == udid:
                return str(d.get("name") or "")
    return ""


def _cleanup(project: str, quiet: bool = False, udid: str | None = None) -> int:
    lock_path = os.path.join(state_dir(project), "lock")
    my_lock = _read_lock(lock_path)
    st = load_state(project)
    # The lock and the caller also know the UDID: a failed first write must not forget the simulator.
    udid = st.get("udid") or my_lock.get("udid") or udid
    done, failed = [], []
    remaining = []
    for ch in st.get("changes", []):
        if ch.get("what") == "ConnectHardwareKeyboard":
            err = _restore_keyboard(ch, udid)
            if err:
                failed.append(f"hardware keyboard setting: {err}")
                remaining.append(ch)
            else:
                done.append("hardware keyboard setting")
        elif ch.get("what") == "status_bar":
            done.append("status bar")  # goes away with the simulator
        else:
            remaining.append(ch)
    st["changes"] = remaining
    if udid:
        st["udid"] = udid

    def still_mine():
        # Another cleanup may finish meanwhile and a new session take the lock: its record is not ours to write.
        current = _read_lock(lock_path)
        return not current or current.get("token") == my_lock.get("token")

    try:
        if still_mine():
            save_state(project, st)
    except OSError as e:
        failed.append(f"record: {e}")
    name = simulator_name(udid) if udid else ""
    if udid and name is None:
        failed.append(f"simulator {udid}: could not read the simulator list to confirm it is ours, so it was left untouched")
        udid = None
    elif udid and name and not name.startswith("apptest"):
        # The record is damaged or not ours: never delete a simulator this family did not create.
        failed.append(f"simulator {udid} is named {name!r}, not one this family created: left untouched")
        udid = None
    if udid:
        rc, err = sh_rc("xcrun", "simctl", "shutdown", udid)  # errors if already off too: delete is the real result
        rc, err = sh_rc("xcrun", "simctl", "delete", udid)
        if rc == 0 or "Invalid device" in err:
            done.append(f"simulator {udid} deleted")
        else:
            failed.append(f"simulator {udid}: {err or f'exit {rc}'}")
    if failed:
        print("Cleanup failed: " + "; ".join(failed) + ". The record is kept; run `cleanup` again.", file=sys.stderr)
        if done:
            print("completed: " + ", ".join(done), file=sys.stderr)
        return 1
    # Last write BEFORE the lock goes, and only while the session is still ours.
    if still_mine():
        save_state(project, {"changes": []})
    current = _read_lock(lock_path)
    if current:
        if current.get("token") == my_lock.get("token"):
            _release_lock(project)
            done.append("lock")
        else:
            print("note: the lock now belongs to another session; left in place", file=sys.stderr)
    if not quiet:
        print("cleaned: " + (", ".join(done) if done else "nothing to clean"))
    return 0


def cleanup(a):
    info = _read_lock(os.path.join(state_dir(a.project), "lock"))
    st = load_state(a.project)
    mine = getattr(a, "udid", None) and a.udid == (st.get("udid") or info.get("udid"))
    if lock_is_live(info) and not mine and not getattr(a, "force", False):
        raise SystemExit(f"another live session exists (started {info.get('started')}): left untouched. If it is your own, "
                         "pass `--udid <UDID>`; use `--force` only if the user explicitly asks.")
    return _cleanup(a.project)


def status(a):
    st = load_state(a.project)
    print(json.dumps(st, ensure_ascii=False, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--project", required=True)
    c.add_argument("--device", default="iPhone 18 Pro")
    c.add_argument("--runtime", default="latest")
    c.add_argument("--status-bar", action="store_true")
    c.add_argument("--appearance", choices=["light", "dark"])
    c.add_argument("--content-size")
    c.add_argument("--software-keyboard", action="store_true")
    c.add_argument("--ttl-hours", type=float, default=6.0, help="lock lifetime; an expired session is taken over")
    for name in ("status", "cleanup"):
        s = sub.add_parser(name)
        s.add_argument("--project", required=True)
        if name == "cleanup":
            s.add_argument("--udid", help="the UDID create printed: proof that the session is yours")
            s.add_argument("--force", action="store_true", help="only if the user explicitly asks")
    a = ap.parse_args(argv)
    return {"create": create, "cleanup": cleanup, "status": status}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
