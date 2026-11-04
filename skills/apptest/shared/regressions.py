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
import sys
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

sim = load('review_sim', 'apptest/shared/sim_session.py')
runner = load('review_runner', 'apptest/shared/run_all.py')
scan = load('review_scan', 'apptest/shared/scanlib.py')

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


if __name__ == '__main__':
    unittest.main(verbosity=1)
