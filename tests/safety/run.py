#!/usr/bin/env python3
"""Can using these skills harm a project, or mislead the person using them? Standard library only.

Each test is one bad outcome that must not happen: a changed or deleted file, a deleted simulator or app data,
output written over someone's files, a private file read through a link, a leaked secret, or a report that looks
clean when it is not. Simulator commands are mocked; nothing real is deleted.

    python3 -B tests/safety/run.py
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SKILLS = os.path.join(ROOT, "skills")
sys.path.insert(0, os.path.join(ROOT, "tests", "detection"))
sys.dont_write_bytecode = True
import cases as C  # noqa: E402
from run import SCRIPTS  # noqa: E402


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SKILLS, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(body if isinstance(body, bytes) else body.encode("utf-8"))


def snapshot(root):
    """Every path with its type, mode and content hash: any write, delete, rename or new file changes it."""
    out = {}
    for base, dirs, files in os.walk(root):
        for n in dirs + files:
            p = os.path.join(base, n)
            st = os.lstat(p)
            key = os.path.relpath(p, root)
            if stat.S_ISREG(st.st_mode):
                with open(p, "rb") as fh:
                    out[key] = ("file", stat.S_IMODE(st.st_mode), hashlib.sha256(fh.read()).hexdigest())
            else:
                out[key] = ("dir" if stat.S_ISDIR(st.st_mode) else "other", stat.S_IMODE(st.st_mode), None)
    return out


def run(*args, cwd=None):
    return subprocess.run([sys.executable, "-I", "-X", "utf8", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, cwd=cwd)


def rich_project():
    """A project with something for every scanner to read: defects, translations, tests, images and metadata."""
    files = C.swift()
    for c in C.CASES:
        if c["scan"] != "SA" and not c.get("clean"):
            for rel, body in c["files"].items():
                files.setdefault(rel, body)
    files.update({".apptest/profile.md": "## Suppressed\n- PE-* — not used here\n",
                  "screens/en/iphone/a.png": C.png(1320, 2868)})
    return files


class Safety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="apptest-safety-")
        self.addCleanup(self.tmp.cleanup)
        self.base = self.tmp.name
        self.project = os.path.join(self.base, "project")
        os.makedirs(self.project)

    def every_tool(self, project, out_dir):
        """Runs every scan, the combined report, the profile and the text inventory, the way the skills do."""
        runs = []
        for code, rel in SCRIPTS.items():
            target = os.path.join(project, "screens", "en", "iphone") if code == "SA" else project
            runs.append((code, run(os.path.join(SKILLS, rel), target, "--json")))
        runs.append(("run_all", run(os.path.join(SKILLS, "apptest/shared/run_all.py"), project)))
        runs.append(("run_all json", run(os.path.join(SKILLS, "apptest/shared/run_all.py"), project, "--json")))
        runs.append(("profile", run(os.path.join(SKILLS, "apptest/shared/profile.py"), project)))
        runs.append(("inventory", run(os.path.join(SKILLS, "apptest-copy-audit/scripts/copy_inventory.py"), project,
                                      "--out", os.path.join(out_dir, "inventory"))))
        # Started from inside the project, as a person often does.
        runs.append(("run_all from inside", run(os.path.join(SKILLS, "apptest/shared/run_all.py"), ".", cwd=project)))
        return runs

    def test_no_tool_changes_the_project(self):
        write(self.project, rich_project())
        before = snapshot(self.project)
        for name, r in self.every_tool(self.project, self.base):
            self.assertNotIn("Traceback", r.stderr, name)
        self.assertEqual(snapshot(self.project), before, "a tool wrote to, removed or renamed something in the project")

    @unittest.skipIf(os.name == "nt", "POSIX permissions")
    def test_a_read_only_project_scans_fully_and_stays_unchanged(self):
        write(self.project, rich_project())
        for base, dirs, files in os.walk(self.project):
            for n in files:
                os.chmod(os.path.join(base, n), 0o444)
        for base, dirs, files in os.walk(self.project, topdown=False):
            os.chmod(base, 0o555)
        self.addCleanup(lambda: [os.chmod(b, 0o755) for b, _d, _f in os.walk(self.project)])
        before = snapshot(self.project)
        for name, r in self.every_tool(self.project, self.base):
            self.assertNotIn("Traceback", r.stderr, name)
            self.assertIn(r.returncode, (0, 3), f"{name}: exit {r.returncode}: {r.stderr[-200:]}")
        self.assertEqual(snapshot(self.project), before)

    def test_text_inventory_never_writes_into_the_project_or_over_other_files(self):
        write(self.project, C.flutter({"lib/l10n/app_en.arb": '{"a": "Hello"}'}))
        before = snapshot(self.project)
        inv = os.path.join(SKILLS, "apptest-copy-audit/scripts/copy_inventory.py")
        r = run(inv, self.project, "--out", os.path.join(self.project, "audit"))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(snapshot(self.project), before)
        theirs = os.path.join(self.base, "Desktop")
        write(theirs, {"notes.txt": "mine"})
        r = run(inv, self.project, "--out", theirs)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(os.listdir(theirs), ["notes.txt"])
        ours = os.path.join(self.base, "inventory")
        self.assertEqual(run(inv, self.project, "--out", ours).returncode, 0)
        self.assertEqual(run(inv, self.project, "--out", ours).returncode, 0, "a second run into its own folder works")

    def test_visual_diff_never_writes_over_other_files(self):
        a, b, theirs = (os.path.join(self.base, x) for x in ("a", "b", "theirs"))
        write(a, {"s.png": C.png(4, 4)})
        write(b, {"s.png": C.png(4, 4, alpha=True)})
        write(theirs, {"s.png": b"my own picture"})
        r = run(os.path.join(SKILLS, "apptest-visual/scripts/vi_diff.py"), a, b, "--out", theirs)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        with open(os.path.join(theirs, "s.png"), "rb") as fh:
            self.assertEqual(fh.read(), b"my own picture")

    @unittest.skipIf(os.name == "nt", "symbolic links")
    def test_links_out_of_the_project_are_not_read(self):
        outside = os.path.join(self.base, "private")
        write(outside, {"Secrets.swift": f'let k = "{C.FAKE_KEY}"\nlet u = "http://private.acme.io"\n'})
        write(self.project, C.swift())
        os.symlink(os.path.join(outside, "Secrets.swift"), os.path.join(self.project, "Acme", "Linked.swift"))
        os.symlink(outside, os.path.join(self.project, "Acme", "LinkedDir"))
        for code in ("NW", "SR"):
            r = run(os.path.join(SKILLS, SCRIPTS[code]), self.project, "--json")
            self.assertNotIn("Linked", r.stdout, code)
            self.assertNotIn("private.acme.io", r.stdout, code)

    def test_secrets_are_never_printed_in_full(self):
        write(self.project, C.swift({"Acme/K.swift": f'let k = "{C.FAKE_KEY}"\nlet a = "AKIA' + "ABCDEFGHIJKLMNOP" + '"\n'}))
        for args in ((os.path.join(SKILLS, SCRIPTS["NW"]), self.project, "--json"),
                     (os.path.join(SKILLS, "apptest/shared/run_all.py"), self.project)):
            out = run(*args).stdout
            self.assertNotIn(C.FAKE_KEY, out)
            self.assertNotIn("AKIA" + "ABCDEFGHIJKLMNOP", out)

    def test_an_incomplete_scan_is_never_reported_as_clean(self):
        write(self.project, C.swift())
        runner = load("safety_runner", "apptest/shared/run_all.py")
        out = io.StringIO()
        with patch.object(runner, "MEMBERS", [("SR", "apptest-store-readiness", "missing.py")]), contextlib.redirect_stdout(out):
            rc = runner.main([self.project])
        self.assertEqual(rc, 3)
        self.assertIn("INCOMPLETE", out.getvalue())
        self.assertNotIn("No rejection risks", out.getvalue())

    def test_a_cut_off_scan_says_so(self):
        write(self.project, C.swift())
        profile = load("safety_profile", "apptest/shared/profile.py")
        with patch.object(profile, "MAX_FILES", 3):
            p = profile.build(self.project)
        self.assertTrue(p.truncated, "a project over the file limit must be marked as only partly read")

    def test_suppressed_rejection_risks_stay_visible(self):
        write(self.project, C.swift(target="12.0", extra={".apptest/profile.md": "## Suppressed\n- SR-* — later\n"}))
        out = run(os.path.join(SKILLS, "apptest/shared/run_all.py"), self.project, "--only", "SR").stdout
        # The member's row must say a rejection risk was hidden, not just that something was.
        self.assertRegex(out, r"suppressed: SR-[^|]*\(rejection risk\)", "a hidden rejection risk must stay visible")
        self.assertIn("hidden, not fixed", out, "the summary must not read as clean while rejection risks are hidden")

    def test_a_project_that_is_not_an_ios_app_is_not_called_clean(self):
        write(self.project, {"index.html": "<html></html>", "package.json": '{"dependencies": {"react": "18.0.0"}}'})
        r = run(os.path.join(SKILLS, "apptest/shared/run_all.py"), self.project)
        self.assertNotIn("No rejection risks", r.stdout)
        self.assertIn("Not applicable", r.stdout + r.stderr)


@unittest.skipIf(os.name == "nt", "simulators exist only on macOS; sim_session.py needs POSIX file locks")
class Simulators(unittest.TestCase):
    """The user's own simulators and the apps on them must never be touched."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="apptest-safety-sim-")
        self.addCleanup(self.tmp.cleanup)
        self.sim = load("safety_sim", "apptest/shared/sim_session.py")
        self.project = os.path.join(self.tmp.name, "p")
        os.makedirs(self.project)
        for p in (patch.object(self.sim, "CACHE", os.path.join(self.tmp.name, "cache")),
                  patch.object(subprocess, "run", side_effect=AssertionError("a real command ran"))):
            p.start()
            self.addCleanup(p.stop)

    def devices(self, name):
        return json.dumps({"devices": {"iOS-26": [{"udid": "U1", "name": name}]}})

    def cleanup_with(self, listing_rc, listing):
        self.sim.take_lock(self.project)
        self.sim._note_udid(self.project, "U1")
        self.sim.save_state(self.project, {"udid": "U1", "changes": []})
        calls = []

        def sh_rc(*a):
            calls.append(a)
            return 0, ""

        def sh_out(*a):  # the device list comes on standard output
            calls.append(a)
            return listing_rc, listing
        with patch.object(self.sim, "sh_rc", side_effect=sh_rc), patch.object(self.sim, "sh_out", side_effect=sh_out), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = self.sim.cleanup(SimpleNamespace(project=self.project, udid="U1", force=False))
        return rc, calls

    def test_cleanup_never_deletes_a_simulator_it_did_not_create(self):
        rc, calls = self.cleanup_with(0, self.devices("iPhone 18 Pro"))
        self.assertFalse(any("delete" in c or "shutdown" in c for c in calls), calls)
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.sim.load_state(self.project).get("udid"), "U1", "the record is kept so nothing is lost")

    def test_cleanup_deletes_nothing_when_it_cannot_tell_whose_simulator_it_is(self):
        rc, calls = self.cleanup_with(1, "")
        self.assertFalse(any("delete" in c for c in calls), calls)
        self.assertNotEqual(rc, 0)

    def test_cleanup_still_removes_its_own_simulator(self):
        rc, calls = self.cleanup_with(0, self.devices("apptest-ab12"))
        self.assertTrue(any("delete" in c for c in calls))
        self.assertEqual(rc, 0)

    def test_upgrade_tour_refuses_a_simulator_it_did_not_create(self):
        upgrade = load("safety_upgrade", "apptest-upgrade/scripts/upgrade_tour.py")
        apps = os.path.join(self.tmp.name, "apps")
        for v in ("Old.app", "New.app"):
            os.makedirs(os.path.join(apps, v))
        ran = []
        with patch.object(upgrade, "simulator_name", return_value="iPhone 18 Pro"), \
                patch.object(upgrade, "sh", side_effect=lambda *a, **k: ran.append(a) or ""):
            with self.assertRaises(SystemExit) as e:
                upgrade.main(["--udid", "U1", "--bundle", "com.acme.a", "--old", os.path.join(apps, "Old.app"),
                              "--new", os.path.join(apps, "New.app"), "--seed", "true"])
        self.assertIn("not a temporary simulator", str(e.exception))
        self.assertEqual(ran, [], "nothing may be uninstalled or installed")


if __name__ == "__main__":
    unittest.main(verbosity=1)
