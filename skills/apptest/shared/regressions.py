"""Safety tests for the shared tools (lock, cleanup, finding merge, scan limit). Standard library only.
All simulator commands are mocked; no real xcrun or defaults ever RUNS.

    python3 -B regressions.py
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import sys
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

_REAL = subprocess.run
_real_run = lambda *a: _REAL(list(a), capture_output=True, text=True, timeout=120)
ROOT = Path(__file__).resolve().parents[2]

def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

sim = load('review_sim', 'apptest/shared/sim_session.py')
runner = load('review_runner', 'apptest/shared/run_all.py')
scan = load('review_scan', 'apptest/shared/scanlib.py')
upgrade = load('review_upgrade', 'apptest-upgrade/scripts/upgrade_tour.py')

class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='skill-review-fixture-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = str(self.root / 'project')
        Path(self.project).mkdir()
        p = patch.object(sim, 'CACHE', str(self.root / 'cache'))
        p.start()
        self.addCleanup(p.stop)
        self.args = SimpleNamespace(project=self.project)
        self.lock = Path(sim.state_dir(self.project)) / 'lock'
        # Hard stop: none of these tests may execute real shell commands.
        p = patch.object(sim.subprocess, 'run', side_effect=AssertionError('UNMOCKED subprocess prohibited'))
        p.start()
        self.addCleanup(p.stop)

    def test_01_cleanup_must_not_destroy_foreign_live_session(self):
        self.lock.write_text(json.dumps({'pid': os.getpid(), 'job': 'other-agent'}))
        sim.save_state(self.project, {'udid': 'FAKE-FOREIGN-UDID', 'changes': []})
        calls = []
        with patch.object(sim, 'sh', side_effect=lambda *a, **kw: calls.append(a) or ''), \
             patch.object(sim, 'pid_alive', return_value=True), contextlib.redirect_stdout(io.StringIO()):
            try:
                sim.cleanup(self.args)
            except SystemExit:
                pass
        self.assertFalse(any('delete' in c for c in calls), 'cleanup sent DELETE for a live foreign session: ' + repr(calls))
        self.assertTrue(self.lock.exists())

    def test_02_lock_must_have_only_one_winner(self):
        real_exists = os.path.exists
        gate = threading.Barrier(2)
        outcomes = []
        def exists(p):
            if str(p) == str(self.lock):
                gate.wait(timeout=5)
                return False  # both callers reached the check before either writes
            return real_exists(p)
        def worker():
            try:
                sim.take_lock(self.project)
                outcomes.append('acquired')
            except BaseException as e:
                outcomes.append(type(e).__name__)
        with patch.object(sim.os.path, 'exists', side_effect=exists):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for t in threads: t.start()
            for t in threads: t.join(timeout=10)
        self.assertEqual(outcomes.count('acquired'), 1, 'lock results: ' + repr(outcomes))

    def test_03_failed_delete_must_preserve_recovery_state(self):
        sim.save_state(self.project, {'udid': 'FAKE-FAIL-UDID', 'changes': []})
        self.lock.write_text('{}')
        def command(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1 if 'delete' in argv else 0, '', 'injected deletion failure')
        output = io.StringIO()
        with patch.object(sim.subprocess, 'run', side_effect=command), contextlib.redirect_stdout(output):
            try: sim.cleanup(self.args)
            except SystemExit: pass
        self.assertEqual(sim.load_state(self.project).get('udid'), 'FAKE-FAIL-UDID',
                         'recovery state lost; printed: ' + output.getvalue())

    def test_04_create_must_preserve_uncleaned_session(self):
        old = {'udid': 'FAKE-OLD-UDID', 'changes': [{'what': 'ConnectHardwareKeyboard', 'old': '1'}]}
        sim.save_state(self.project, old)
        args = SimpleNamespace(project=self.project, runtime='fake-runtime', device='fake-device',
                               status_bar=False, appearance=None, content_size=None, software_keyboard=False)
        def command(*argv, **kwargs):
            if 'create' in argv: return 'FAKE-NEW-UDID'
            if 'screenshot' in argv: raise SystemExit('mock screenshot unsupported')
            return ''
        with patch.object(sim, 'sh', side_effect=command), patch.object(sim, 'device_type', return_value='fake-type'), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try: sim.create(args)
            except SystemExit: pass
        self.assertEqual(sim.load_state(self.project), old, 'uncleaned previous session and keyboard recovery entry overwritten')

    def test_05_different_findings_on_same_line_must_survive_merge(self):
        findings = [
            {'id':'SR-99','severity':'USER BUG','title':'Distinct problem A','evidence':'app.swift:42','note':'Fix A'},
            {'id':'PP-99','severity':'REJECTION RISK','title':'Distinct problem B','evidence':'app.swift:42','note':'Fix B'}]
        results = [({'findings':[f]}, '', 0.1) for f in findings]
        out = io.StringIO()
        with patch.object(runner, 'MEMBERS', runner.MEMBERS[:2]), patch.object(runner, 'run', side_effect=results), \
             contextlib.redirect_stdout(out):
            runner.main([self.project, '--json'])
        data = json.loads(out.getvalue())
        self.assertEqual(len(data['findings']), 2, 'second title and fix lost: ' + json.dumps(data['findings']))

    def test_06_missing_member_must_be_visible(self):
        out = io.StringIO()
        with patch.object(runner, 'MEMBERS', [('SR','missing-skill','missing.py')]), contextlib.redirect_stdout(out):
            rc = runner.main([self.project, '--json'])
        data = json.loads(out.getvalue())
        self.assertTrue(rc != 0 or data['problems'] or data['members'], 'missing scanner silently returned: ' + out.getvalue())

    def test_07_unknown_member_selection_must_be_rejected(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = runner.main([self.project, '--only', 'ZZ', '--json'])
        self.assertNotEqual(rc, 0, 'unknown --only returned success and empty report: ' + out.getvalue())

    def test_08_file_truncation_must_be_reported(self):
        f = self.root / 'large.swift'
        f.write_text('// padding\n' * 40001 + 'let sentinelRisk = true\n')
        scan.TRUNCATED.clear()
        hits = list(scan.grep(None, 'sentinelRisk', files=[str(f)]))
        self.assertTrue(hits or scan.TRUNCATED, 'risk after byte 400000 silently missed; no partial-scan marker')

    # --- The remaining paths of the lock and cleanup contract
    def _ok(self, argv, **kw):
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, '', '')

    def _patch_run(self, fn):
        p = patch.object(sim.subprocess, 'run', side_effect=fn)
        p.start()
        self.addCleanup(p.stop)

    def test_09_own_session_cleans_with_udid(self):
        self.calls = []
        self._patch_run(self._ok)
        sim.take_lock(self.project)
        sim.save_state(self.project, {'udid': 'U1', 'changes': []})
        with contextlib.redirect_stdout(io.StringIO()):
            rc = sim.cleanup(SimpleNamespace(project=self.project, udid='U1', force=False))
        self.assertEqual(rc, 0)
        self.assertFalse(self.lock.exists())
        self.assertTrue(any('delete' in c for c in self.calls))
        self.assertFalse(sim.load_state(self.project).get('udid'))

    def test_10_lock_outlives_short_shell_until_expiry(self):
        sim.take_lock(self.project)
        with patch.object(sim, 'pid_alive', return_value=False):  # the shell that started create has closed
            with self.assertRaises(SystemExit):
                sim.take_lock(self.project)
        info = json.loads(self.lock.read_text())
        info['expires'] = time.time() - 1
        self.lock.write_text(json.dumps(info))
        self.assertTrue(sim.take_lock(self.project))  # an expired lock is taken over

    def test_11_second_cleanup_resumes_after_failure(self):
        sim.save_state(self.project, {'udid': 'U2', 'changes': [{'what': 'status_bar'}]})
        fail = {'on': True}
        def command(argv, **kw):
            rc = 1 if fail['on'] and 'delete' in argv else 0
            return subprocess.CompletedProcess(argv, rc, '', 'x' if rc else '')
        self._patch_run(command)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(sim.cleanup(self.args), 1)
        self.assertIn('Cleanup failed', err.getvalue())
        fail['on'] = False
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sim.cleanup(self.args), 0)
        self.assertFalse(sim.load_state(self.project).get('udid'))

    def test_12_already_gone_simulator_counts_as_deleted(self):
        sim.save_state(self.project, {'udid': 'U3', 'changes': []})
        self._patch_run(lambda argv, **kw: subprocess.CompletedProcess(argv, 1, '', 'Invalid device: U3'))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sim.cleanup(self.args), 0)

    def test_13_keyboard_restored_only_by_last_holder(self):
        self.calls = []
        self._patch_run(self._ok)
        with sim._KeyboardBook() as b:
            b.data = {'holders': ['A', 'B'], 'old': '1'}
            b.save()
        self.assertIsNone(sim._restore_keyboard({'what': 'ConnectHardwareKeyboard'}, 'A'))
        self.assertEqual(self.calls, [], 'setting changed while another tour was using it')
        self.assertIsNone(sim._restore_keyboard({'what': 'ConnectHardwareKeyboard'}, 'B'))
        self.assertTrue(any('write' in c and 'true' in c for c in self.calls))

    def test_14_same_issue_merges_and_keeps_detail(self):
        fs = [{'id': 'TS-12', 'severity': 'SUGGESTION', 'title': 'A', 'evidence': 'x.swift:3', 'note': 'nA'},
              {'id': 'TH-14', 'severity': 'USER BUG', 'title': 'B', 'evidence': 'x.swift:3', 'note': 'nB'}]
        out = io.StringIO()
        with patch.object(runner, 'MEMBERS', runner.MEMBERS[:2]), \
             patch.object(runner, 'run', side_effect=[({'findings': [f]}, '', 0.1) for f in fs]), contextlib.redirect_stdout(out):
            runner.main([self.project, '--json'])
        data = json.loads(out.getvalue())['findings']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['severity'], 'USER BUG')
        self.assertEqual(data[0]['also_detail'][0]['note'], 'nB')

    def test_15_broken_member_output_is_not_clean(self):
        for stdout in ('', '{"x": 1}'):
            with patch.object(runner.subprocess, 'run',
                              return_value=subprocess.CompletedProcess([], 0, stdout, '')):
                data, err, _ = runner.run('a.py', self.project, [])
            self.assertIsNone(data)
            self.assertTrue(err)

    def test_16_missing_member_exits_3(self):
        with patch.object(runner, 'MEMBERS', [('SR', 'missing', 'missing.py')]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main([self.project, '--json']), 3)

    def test_17_mixed_only_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runner.main([self.project, '--only', 'SR,ZZ']), 2)

    def test_18_unreadable_file_reported(self):
        scan.TRUNCATED.clear()
        self.assertEqual(scan.p_read(str(self.root / 'missing.swift')), '')
        self.assertTrue(any('unreadable' in x for x in scan.TRUNCATED))

    def test_19_limit_boundary(self):
        scan.TRUNCATED.clear()
        f = self.root / 'exact.swift'
        f.write_bytes(b'a' * 1000)
        self.assertEqual(len(scan.p_read(str(f), 1000)), 1000)
        self.assertEqual(scan.TRUNCATED, [])
        self.assertEqual(len(scan.p_read(str(f), 999)), 999)
        self.assertTrue(scan.TRUNCATED)

    # --- Second independent review: hand-over, retry and half-finished paths
    def test_21_old_cleanup_keeps_next_sessions_record(self):
        sim.take_lock(self.project)
        sim.save_state(self.project, {'udid': 'OLD', 'changes': []})
        real = sim._release_lock
        def then_next(project):
            real(project)
            sim.take_lock(project)
            sim.save_state(project, {'udid': 'NEW', 'changes': []})
        with patch.object(sim, '_release_lock', side_effect=then_next), patch.object(sim, 'sh_rc', return_value=(0, '')), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sim._cleanup(self.project), 0)
        self.assertEqual(sim.load_state(self.project).get('udid'), 'NEW')

    def test_22_cleanup_does_not_release_a_lock_taken_meanwhile(self):
        sim.take_lock(self.project)
        sim.save_state(self.project, {'udid': 'OLD', 'changes': []})
        def command(*a):
            if a[-2:] == ('delete', 'OLD') or 'delete' in a:
                info = json.loads(self.lock.read_text())
                info['token'] = 'someone-else'
                self.lock.write_text(json.dumps(info))
            return 0, ''
        with patch.object(sim, 'sh_rc', side_effect=command), contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            sim._cleanup(self.project)
        self.assertEqual(json.loads(self.lock.read_text())['token'], 'someone-else')

    def test_23_keyboard_value_survives_a_failed_restore(self):
        sim.save_state(self.project, {'udid': 'A', 'changes': [{'what': 'ConnectHardwareKeyboard'}]})
        with sim._KeyboardBook() as b:
            b.data = {'holders': ['A'], 'old': '1'}
            b.save()
        system = {'value': 'false', 'fail': True}
        def command(*a):
            if a[0] == 'defaults':
                if system['fail']:
                    return 1, 'injected'
                system['value'] = a[-1]
            return 0, ''
        with patch.object(sim, 'sh_rc', side_effect=command), contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sim._cleanup(self.project), 1)
            system['fail'] = False
            self.assertEqual(sim._cleanup(self.project), 0)
        self.assertEqual(system['value'], 'true')

    def test_24_new_tour_cannot_slip_into_keyboard_restore(self):
        with sim._KeyboardBook() as b:
            b.data = {'holders': ['A'], 'old': '1'}
            b.save()
        system = {'value': 'false'}
        started, order = threading.Event(), []
        def tour_b():
            started.wait(5)
            with sim._KeyboardBook() as b:
                order.append('B in')
                b.data['old'] = system['value']
                b.data['holders'].append('B')
                b.save()
                system['value'] = 'false'
        t = threading.Thread(target=tour_b)
        t.start()
        def slow_write(*a):
            started.set()
            time.sleep(0.3)  # B is trying to get in now
            order.append('A wrote')
            system['value'] = a[-1]
            return 0, ''
        with patch.object(sim, 'sh_rc', side_effect=slow_write):
            self.assertIsNone(sim._restore_keyboard({'what': 'ConnectHardwareKeyboard'}, 'A'))
        t.join(5)
        self.assertEqual(order, ['A wrote', 'B in'])
        self.assertEqual(system['value'], 'false', 'B still owns the setting')

    def test_25_stuck_keyboard_lock_gives_an_error_not_a_hang(self):
        with patch.object(sim, 'KEYBOARD_WAIT', 0.1), sim._KeyboardBook():
            with self.assertRaises(SystemExit):
                with sim._KeyboardBook():
                    pass

    def test_26_failed_first_write_does_not_forget_the_simulator(self):
        calls, real, fail = [], sim.save_state, {'once': True}
        def save(project, state):
            if fail['once']:
                fail['once'] = False
                raise OSError('injected')
            real(project, state)
        args = SimpleNamespace(project=self.project, runtime='r', device='d', status_bar=False, appearance=None,
                               content_size=None, software_keyboard=False)
        with patch.object(sim, 'sh', side_effect=lambda *a, **k: 'CREATED' if 'create' in a else ''), \
             patch.object(sim, 'device_type', return_value='t'), patch.object(sim, 'save_state', side_effect=save), \
             patch.object(sim, 'sh_rc', side_effect=lambda *a: calls.append(a) or (0, '')), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(OSError):
                sim.create(args)
        self.assertTrue(any('delete' in c and 'CREATED' in c for c in calls), calls)

    def test_27_documented_cleanup_works_on_own_session(self):
        doc = (ROOT / 'apptest/shared/CONVENTIONS.md').read_text(encoding='utf-8')
        line = next(x for x in doc.splitlines() if 'sim_session.py cleanup --project' in x)
        self.assertIn('--udid', line)
        src = (ROOT / 'apptest/shared/sim_session.py').read_text(encoding='utf-8')
        self.assertIn('cleanup --project {a.project} --udid {udid}', src)

    def _upgrade(self, sh):
        for n in ('old.app', 'new.app'):
            (self.root / n).mkdir(exist_ok=True)
        out = io.StringIO()
        with patch.object(upgrade, 'sh', side_effect=sh), patch.object(upgrade, 'run_hook', return_value=True), \
             patch.object(upgrade, 'version_of', return_value='x'), patch.object(upgrade.time, 'sleep'), contextlib.redirect_stdout(out):
            rc = upgrade.main(['--udid', 'U', '--bundle', 'b.c', '--old', str(self.root / 'old.app'),
                               '--new', str(self.root / 'new.app'), '--seed', 's', '--wait', '0'])
        return rc, out.getvalue()

    def test_28_upgrade_without_a_data_folder_could_not_check(self):
        rc, out = self._upgrade(lambda *a, **k: '1 0 b.c' if 'launchctl' in a else '')
        self.assertEqual(rc, 3)
        self.assertIn('could not check', out)
        self.assertIn('cannot read', out)  # not the same as an empty folder

    def test_29_upgrade_with_no_data_could_not_check(self):
        empty = self.root / 'box'
        empty.mkdir()
        rc, out = self._upgrade(lambda *a, **k: str(empty) if 'get_app_container' in a else '1 0 b.c' if 'launchctl' in a else '')
        self.assertEqual(rc, 3)

    def test_30_upgrade_with_data_passes_and_lost_file_fails(self):
        box = self.root / 'box'
        box.mkdir()
        (box / 'data.db').write_text('x' * 100)
        sh = lambda *a, **k: str(box) if 'get_app_container' in a else '1 0 b.c' if 'launchctl' in a else ''
        self.assertEqual(self._upgrade(sh)[0], 0)
        def losing(*a, **k):
            if a[1:3] == ('simctl', 'install') and a[-1].endswith('new.app'):
                (box / 'data.db').unlink()
            return sh(*a, **k)
        self.assertEqual(self._upgrade(losing)[0], 1)

    def test_31_malformed_findings_are_reported_not_a_crash(self):
        for bad in ('{"findings":[null]}', '{"findings":[{"severity":"INFO"}]}',
                    '{"findings":[{"id":"X-1","severity":"NOPE"}]}',
                    '{"findings":[{"id":"X-1","severity":"INFO","evidence":3}]}', '{"findings":[],"skipped":3}'):
            with self.subTest(bad=bad):
                out = io.StringIO()
                with patch.object(runner, 'MEMBERS', runner.MEMBERS[:2]), \
                     patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, bad, '')), \
                     contextlib.redirect_stdout(out):
                    rc = runner.main([self.project, '--json'])
                self.assertEqual(rc, 3)
                self.assertEqual(len(json.loads(out.getvalue())['problems']), 2)

    def test_32_partial_scan_is_not_complete_but_did_run(self):
        out = io.StringIO()
        with patch.object(runner, 'MEMBERS', runner.MEMBERS[:1]), \
             patch.object(runner, 'run', return_value=({'findings': [], 'truncated': ['first 400 KB']}, '', 0.0)), \
             contextlib.redirect_stdout(out):
            rc = runner.main([self.project, '--json'])
        data = json.loads(out.getvalue())
        self.assertEqual(rc, 0)
        self.assertTrue(data['execution_complete'])
        self.assertFalse(data['complete'])
        self.assertEqual(data['coverage_partial'], ['first 400 KB'])

    def test_33_dart_template_runs_in_dart(self):
        t = (ROOT / 'apptest-crawl/references/templates.md').read_text(encoding='utf-8')
        line = next(x for x in t.splitlines() if x.startswith('final skipLabel'))
        self.assertNotIn('(?i)', line, 'Dart RegExp rejects inline flags')
        self.assertIn('caseSensitive: false', line)
        dart = shutil.which('dart')
        if not dart:
            self.skipTest('dart not installed; the text check above still ran')
        src = self.root / 'probe.dart'
        src.write_text(line.split('  //')[0] + "\nvoid main() { if (!skipLabel.hasMatch('Delete') || skipLabel.hasMatch('Open')) throw 'bad'; }\n", encoding='utf-8')
        real = _real_run(dart, str(src))
        self.assertEqual(real.returncode, 0, real.stderr[-300:])

    def test_20_all_members_exist_and_routed(self):
        for code, folder, script in runner.MEMBERS:
            self.assertTrue((ROOT / folder / 'scripts' / script).exists(), code)
        router = (ROOT / 'app' / 'SKILL.md').read_text(encoding='utf-8')
        for d in sorted(ROOT.iterdir()):
            if d.name.startswith(('apptest-', 'apple-design-')) and (d / 'SKILL.md').exists():
                self.assertIn(d.name, router, 'missing from the router')


class FalseAlarmCorpus(unittest.TestCase):
    """False alarms and false passes found in real projects: fixed once, must not come back."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='apptest fixture ığş ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def w(self, rel, text=''):
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding='utf-8')

    def scan(self, only):
        r = subprocess.run([sys.executable, '-I', '-X', 'utf8', str(ROOT / 'apptest/shared/run_all.py'), str(self.root),
                            '--only', only, '--json'], capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)['findings']

    def ids(self, only, sev=None):
        return {f['id'] for f in self.scan(only) if sev is None or f['severity'] == sev}

    def swift_app(self, code='import SwiftUI\n'):
        self.w('A.xcodeproj/project.pbxproj', 'SDKROOT = iphoneos;\nproductType = "com.apple.product-type.application";\n')
        self.w('A/App.swift', code)

    def test_xcodegen_keys_are_read(self):  # Kiwix
        self.w('project.yml', 'settings:\n  INFOPLIST_KEY_NSLocationWhenInUseUsageDescription: "Location for the map."\n'
                              '  INFOPLIST_KEY_UILaunchScreen_Generation: YES\n')
        self.w('A/App.swift', 'import SwiftUI\nimport CoreLocation\nlet m = CLLocationManager()\nfunc f() { m.requestWhenInUseAuthorization() }\n')
        self.assertNotIn('PP-10', self.ids('PP', 'REJECTION RISK'))

    def test_missing_permission_still_found(self):  # the fix must not drop the real finding
        self.swift_app('import SwiftUI\nimport CoreLocation\nlet m = CLLocationManager()\nfunc f() { m.requestWhenInUseAuthorization() }\n')
        self.assertIn('PP-10', self.ids('PP', 'REJECTION RISK'))

    def test_localized_only_permission_is_not_hard_risk(self):  # Mastodon
        self.swift_app('import SwiftUI\nimport AVFoundation\nlet s = AVCaptureSession()\n')
        self.w('A/en.lproj/InfoPlist.strings', '"NSCameraUsageDescription" = "Kamera";\n')
        hard = [f for f in self.scan('PP') if f['id'] == 'PP-10' and f['severity'] == 'REJECTION RISK' and 'camera' in f['title']]
        self.assertEqual(hard, [])

    def test_monorepo_unused_package_ignored(self):  # Joplin packages/clipper
        self.w('package.json', '{"name":"root","workspaces":["packages/*"]}')
        self.w('packages/app-mobile/package.json', '{"name":"@a/mobile","dependencies":{"react-native":"0.76.0","@a/lib":"1"}}')
        self.w('packages/lib/package.json', '{"name":"@a/lib"}')
        self.w('packages/clipper/package.json', '{"name":"@a/clipper"}')
        self.w('packages/app-mobile/ios/M.xcodeproj/project.pbxproj', 'productType = "com.apple.product-type.application";\n')
        self.w('packages/clipper/src/pay.js', 'const u = "https://checkout.stripe.com/pay";\n')
        self.assertNotIn('MO-16', self.ids('MO'))

    def networked_app(self):
        self.swift_app('import Foundation\nlet t = URLSession.shared.dataTask(with: URL(string: "https://api.sample.dev/x")!)\n')

    PEM = 'const k = `-----BEGIN RSA PRIVATE KEY-----\nFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE\n-----END RSA PRIVATE KEY-----`;\n'

    def test_key_in_test_helper_ignored(self):  # Joplin ppkTestUtils
        self.networked_app()
        self.w('src/ppkTestUtils.ts', self.PEM)
        self.assertNotIn('NW-16', self.ids('NW'))

    def test_key_in_app_code_found(self):  # control: the same key in app code is found
        self.networked_app()
        self.w('src/keys.ts', self.PEM)
        self.assertIn('NW-16', self.ids('NW'))

    def test_mock_is_not_account_deletion_evidence(self):  # PocketPal jest/setup.ts
        self.networked_app()
        self.w('src/Login.ts', 'export function signUp() { return createAccount(); }\n')
        self.w('jest/setup.ts', 'const deleteAccount = jest.fn();\n')
        titles = [f['title'] for f in self.scan('NW')]
        self.assertFalse(any('Account deletion flow exists' in t for t in titles), titles)

    def test_only_inside_string_is_not_focus(self):  # Joplin eslint rule test
        self.swift_app()
        self.w('t/a.test.ts', "const c = { code: 'describe.only(\\'Tag\\', () => {});' };\n")
        self.assertNotIn('TH-12', self.ids('TH'))

    def test_real_only_is_found(self):
        self.swift_app()
        self.w('t/a.test.ts', "describe.only('x', () => {});\n")
        self.assertIn('TH-12', self.ids('TH'))

    def test_manual_store_delete_is_soft(self):  # Apidash
        self.w('pubspec.yaml', 'name: a\ndependencies:\n  flutter:\n    sdk: flutter\n  hive: any\n')
        self.w('ios/Runner.xcodeproj/project.pbxproj', '')
        self.w('lib/s.dart', 'Future<void> clearAll() async {\n  await box.deleteFromDisk();\n}\n')
        di = [f for f in self.scan('DI') if f['id'] == 'DI-14']
        self.assertTrue(di)
        self.assertTrue(all(f['severity'] == 'SUGGESTION' for f in di))

    def test_store_delete_on_error_is_hard(self):
        self.w('pubspec.yaml', 'name: a\ndependencies:\n  flutter:\n    sdk: flutter\n  hive: any\n')
        self.w('ios/Runner.xcodeproj/project.pbxproj', '')
        self.w('lib/s.dart', 'Future<void> open() async {\n  try { await a(); } catch (e) {\n    await box.deleteFromDisk();\n  }\n}\n')
        self.assertTrue(any(f['id'] == 'DI-14' and f['severity'] == 'USER BUG' for f in self.scan('DI')))

    def test_test_plist_does_not_hide_app_plist(self):  # Mastodon: only the test plist stayed in the Release list
        self.w('A.xcodeproj/project.pbxproj',
               'productType = "com.apple.product-type.application";\n'
               'C1 = {isa = XCBuildConfiguration; buildSettings = { INFOPLIST_FILE = A/Info.plist; SDKROOT = iphoneos; }; name = Debug; };\n'
               'C2 = {isa = XCBuildConfiguration; buildSettings = { INFOPLIST_FILE = ATests/Info.plist; }; name = Release; };\n'
               'C3 = {isa = XCBuildConfiguration; buildSettings = { INFOPLIST_KEY_CFBundleDisplayName = "Extension"; }; name = Release; };\n')
        pl = '<?xml version="1.0"?><plist version="1.0"><dict>%s</dict></plist>'
        self.w('A/Info.plist', pl % '<key>UILaunchStoryboardName</key><string>Main</string>')
        self.w('ATests/Info.plist', pl % '')
        self.w('A/App.swift', 'import SwiftUI\n')
        self.assertNotIn('SR-22', self.ids('SR'))

    def test_mac_only_is_not_applicable(self):  # Maccy, Rectangle, Stats
        self.w('M.xcodeproj/project.pbxproj', 'SDKROOT = macosx;\n')
        self.w('M/App.swift', 'import AppKit\n')
        r = subprocess.run([sys.executable, '-I', '-X', 'utf8', str(ROOT / 'apptest/shared/run_all.py'), str(self.root)],
                           capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertIn('Not applicable', r.stdout)

    def test_multiplatform_is_not_mac_only(self):  # NetNewsWire: the iOS target is in xcconfig
        self.w('N.xcodeproj/project.pbxproj', 'SDKROOT = macosx;\n')
        self.w('x/ios.xcconfig', 'SDKROOT = iphoneos\n')
        self.w('N/App.swift', 'import SwiftUI\n')
        r = subprocess.run([sys.executable, '-I', '-X', 'utf8', str(ROOT / 'apptest/shared/run_all.py'), str(self.root)],
                           capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertNotIn('Not applicable: Mac-only', r.stdout)

    def test_suppressed_risk_is_labelled(self):  # §9
        self.w('A.xcodeproj/project.pbxproj', 'SDKROOT = iphoneos;\n')
        self.w('A/Info.plist', '<?xml version="1.0"?><plist version="1.0"><dict></dict></plist>')
        self.w('A/App.swift', 'import SwiftUI\n')
        self.w('.apptest/profile.md', '## Suppressed\n- SR-* — trial\n')
        r = subprocess.run([sys.executable, '-I', '-X', 'utf8', str(ROOT / 'apptest/shared/run_all.py'), str(self.root), '--only', 'SR'],
                           capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertIn('(rejection risk)', r.stdout)


class Languages(FalseAlarmCorpus):
    """Kural uygulamanın dilinde çalışmalı: her kavram her dilde, gerçek metinle."""
    TEXT = {
        'en': dict(a='Privacy Policy', b='Contact support', c='Beta version', d='Restore purchases', e='Report this post', f='Block user', g='Mute', h='Delete account'),
        'tr': dict(a='Gizlilik politikası', b='Destekle iletişime geç', c='Beta sürümü', d='Satın alımları geri yükle', e='Bu gönderiyi şikâyet et', f='Kullanıcıyı engelle', g='Sessize al', h='Hesabımı sil'),
        'de': dict(a='Datenschutzerklärung', b='Support kontaktieren', c='Betaversion', d='Käufe wiederherstellen', e='Beitrag melden', f='Nutzer blockieren', g='Stummschalten', h='Konto löschen'),
        'it': dict(a='Informativa sulla privacy', b='Contatta il supporto', c='Versione beta', d='Ripristina acquisti', e='Segnala questo post', f='Blocca utente', g='Silenzia', h='Elimina il tuo account'),
        'es': dict(a='Política de privacidad', b='Contactar con soporte', c='Versión beta', d='Restaurar compras', e='Denunciar esta publicación', f='Bloquear usuario', g='Silenciar', h='Eliminar mi cuenta'),
        'fr': dict(a='Politique de confidentialité', b='Contactez le support', c='Version bêta', d='Restaurer les achats', e='Signaler ce message', f='Bloquer utilisateur', g='Masquer', h='Supprimer mon compte'),
        'pt': dict(a='Política de privacidade', b='Contato com suporte', c='Versão beta', d='Restaurar compras', e='Denunciar publicação', f='Bloquear usuário', g='Silenciar', h='Excluir minha conta'),
    }

    def run_lang(self, lang):
        for f in self.root.rglob('*'):
            if f.is_file():
                f.unlink()
        self.w('pubspec.yaml', 'name: a\ndependencies:\n  flutter:\n    sdk: flutter\n')
        self.w('ios/Runner.xcodeproj/project.pbxproj', '')
        self.w(f'lib/l10n/app_{lang}.arb', json.dumps(self.TEXT[lang], ensure_ascii=False))
        self.w('lib/main.dart', 'class ChatScreen {}\nclass ConversationView {}\n')
        return self.scan('SR,CS,PF')

    def test_every_language_equal(self):
        for lang in self.TEXT:
            with self.subTest(lang=lang):
                got = self.run_lang(lang)
                ids = {f['id'] for f in got}
                self.assertNotIn('CS-10', ids, 'şikâyet / engel / sessize / iletişim metni dilinde bulunamadı')
                self.assertFalse([f for f in got if f['id'] == 'SR-50'], 'gizlilik / destek metni dilinde bulunamadı')
                self.assertIn('PF-18', ids, 'beta ifadesi dilinde bulunamadı')

    def test_german_login_is_not_report(self):  # "anmelden" giriş demektir, "melden" şikâyet
        self.assertIsNone(re.search(scan.terms.rx('report'), 'Jetzt anmelden'))
        self.assertTrue(re.search(scan.terms.rx('report'), 'Beitrag melden'))

    def test_skip_list_covers_destructive_words(self):  # tarama testi bunlara BASMAZ
        words = ['Delete', 'Sil', 'Löschen', 'Elimina', 'Eliminar', 'Supprimer', 'Excluir', 'Kaufen', 'Acquista', 'Comprar',
                 'Abmelden', 'Esci', 'Cerrar sesión', 'Déconnexion', 'Sair', 'Çıkış']
        for w in words:
            self.assertTrue(re.search('(?i)' + scan.terms.SKIP_LABELS, w), w)

    def test_templates_carry_same_skip_list(self):
        t = (ROOT / 'apptest-crawl/references/templates.md').read_text(encoding='utf-8')
        self.assertEqual(t.count(scan.terms.SKIP_LABELS), 2, 'şablon listesi terms.py ile ayrıldı')


class SkillFiles(unittest.TestCase):
    KNOWN = {'name', 'description', 'when_to_use', 'argument-hint', 'arguments', 'disable-model-invocation', 'user-invocable',
             'allowed-tools', 'disallowed-tools', 'model', 'effort', 'context', 'agent', 'background', 'hooks', 'paths', 'shell',
             'metadata', 'license', 'compatibility'}

    def test_frontmatter_is_valid_and_short(self):
        # Claude Code silently ignores unknown fields; descriptions share a common 1% budget.
        for f in sorted(ROOT.glob('app*/SKILL.md')):
            fm = f.read_text(encoding='utf-8').split('---')[1]
            keys = set(re.findall(r'^([a-zA-Z_-]+):', fm, re.M))
            self.assertLessEqual(keys, self.KNOWN, f.parent.name)
            self.assertEqual(re.search(r'^name: (.+)$', fm, re.M).group(1).strip(), f.parent.name)
            d = re.search(r'^description: (".*")\s*$', fm, re.M)
            self.assertTrue(d, f.parent.name)
            self.assertLessEqual(len(json.loads(d.group(1))), 260, f.parent.name)

    def test_no_skill_assumes_where_it_is_installed(self):
        # A plugin install lives elsewhere, so a fixed path would break every command.
        skills = Path(__file__).resolve().parents[2]
        for f in skills.rglob('SKILL.md'):
            self.assertNotIn('~/.claude/skills', f.read_text(encoding='utf-8'), f.parent.name)

    def test_every_scan_rule_is_documented(self):
        skills = Path(__file__).resolve().parents[2]
        for script in skills.glob('*/scripts/*.py'):
            ids = set(re.findall(r'''["']([A-Z]{2,3}-\d{1,3})["']''', script.read_text(encoding='utf-8')))
            doc = (script.parents[1] / 'SKILL.md').read_text(encoding='utf-8')
            for rule in ids:
                code, num = rule.split('-')
                self.assertTrue(rule in doc or re.search(rf'{code}-\d+[^|\n]*\b{num}\b', doc), f'{rule} missing from {script.parent.parent.name}')


if __name__ == '__main__':
    unittest.main(verbosity=1)
