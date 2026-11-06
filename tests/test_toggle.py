"""Controller regression tests: no microphone, clipboard or user terminal access."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
loader = importlib.machinery.SourceFileLoader('controller', str(ROOT / 'dictado-control'))
spec = importlib.util.spec_from_loader(loader.name, loader)
c = importlib.util.module_from_spec(spec)
loader.exec_module(c)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(root / 'runtime'), 'XDG_CONFIG_HOME': str(root / 'config')})
        self.env.start()
        self.addCleanup(self.env.stop)
        Path(os.environ['XDG_RUNTIME_DIR']).mkdir()
        self.sid = 'a' * 32
        self.other = 'b' * 32
        self.target = {'space': 's', 'tab': 't', 'focused_pane': 'p', 'terminal': 'test'}
        self.calls = []
        self.state = 'idle'
        self.run_mock = patch.object(c, 'run', side_effect=self.fake_run)
        self.run_mock.start()
        self.addCleanup(self.run_mock.stop)
        self.target_mock = patch.object(c, 'target', return_value=self.target)
        self.target_mock.start()
        self.addCleanup(self.target_mock.stop)
        self.notify_mock = patch.object(c, 'notify')
        self.notifications = self.notify_mock.start()
        self.addCleanup(self.notify_mock.stop)
        self.paste_patch = patch('targeted_paste.PasteConnection')
        self.connection = self.paste_patch.start().return_value
        self.addCleanup(self.paste_patch.stop)

    def fake_run(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if argv == ['voxtype', 'status']:
            return subprocess.CompletedProcess(argv, 0, self.state)
        return subprocess.CompletedProcess(argv, 0, '')

    def setup_session(self, **kwargs):
        data = {'id': self.sid, 'phase': 'recording', 'started': 0, 'target': self.target,
                'limit': 300, 'valid': True, 'worker_pid': os.getpid()}
        data.update(kwargs)
        c.save_session(data)
        return data

    def last(self):
        return {'id': self.sid, 'raw': 'udo con python', 'text': 'Odoo con Python', 'target': self.target}

    def test_start_is_unique_and_does_not_delete_previous_result(self):
        c.write_json(c.runtime_dir() / 'last.json', self.last())
        with patch.object(c.subprocess, 'Popen', return_value=Mock(pid=os.getpid())):
            c.start()
            with self.assertRaises(RuntimeError):
                c.start()
        starts = [args for args, _ in self.calls if args[:3] == ['voxtype', 'record', 'start']]
        self.assertEqual(len(starts), 1)
        self.assertIn('--no-auto-submit', starts[0])
        self.assertIn('--no-smart-auto-submit', starts[0])
        self.assertTrue(any(a.startswith('--file=') for a in starts[0]))
        output = Path(next(a[len('--file='):] for a in starts[0] if a.startswith('--file=')))
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(c.read_json(c.runtime_dir() / 'last.json'), self.last())

    def test_transcribing_cannot_start_or_stop_another_recording(self):
        self.setup_session(phase='transcribing')
        self.state = 'transcribing'
        with self.assertRaises(RuntimeError):
            c.start()
        c.stop()
        self.assertFalse(any(args[:2] == ['voxtype', 'record'] for args, _ in self.calls))

    def test_cancel_discards_late_output_and_preserves_previous_result(self):
        self.setup_session()
        c.write_json(c.runtime_dir() / 'last.json', {'text': 'previous'})
        out = c.runtime_dir() / (self.sid + '.txt')
        out.write_text('late result')
        c.cancel()
        with patch.object(c.time, 'sleep'):
            c.worker(self.sid)
        self.connection.paste.assert_not_called()
        self.assertFalse(out.exists())
        self.assertEqual(c.read_json(c.runtime_dir() / 'last.json')['text'], 'previous')

    def test_old_worker_does_not_touch_new_session(self):
        self.setup_session(id=self.other)
        with patch.object(c.time, 'sleep'):
            c.worker(self.sid)
        self.assertEqual(c.session()['id'], self.other)
        self.connection.paste.assert_not_called()

    def test_delayed_cancel_during_paste_preparation_prevents_input(self):
        self.setup_session(phase='delivering')
        def cancel_during_prepare(terminal):
            c.cancel()
            return self.connection
        with patch('targeted_paste.PasteConnection', side_effect=cancel_during_prepare):
            self.assertIsNone(c.deliver(self.last(), sid=self.sid))
        self.connection.paste.assert_not_called()
        self.assertFalse((c.runtime_dir() / 'last.json').exists())

    def test_changed_target_copies_instead_of_pasting(self):
        self.setup_session(phase='delivering')
        with patch.object(c, 'target', return_value={**self.target, 'tab': 'other'}):
            code = c.deliver(self.last(), sid=self.sid)
        self.assertEqual(code, 'changed')
        self.connection.paste.assert_not_called()
        self.assertEqual(c.read_json(c.runtime_dir() / 'last.json')['text'], self.last()['text'])

    def test_retry_requires_original_space_tab_and_pane(self):
        for field in ('space', 'tab', 'focused_pane', 'terminal'):
            with self.subTest(field=field), patch.object(c, 'target', return_value={**self.target, field: 'other'}):
                self.assertEqual(c.deliver(self.last(), retry=True), 'wrong_target')
        self.connection.paste.assert_not_called()

    def test_clipboard_failure_preserves_text(self):
        self.setup_session(phase='delivering')
        from targeted_paste import PasteUnavailable
        def fail(argv, **kwargs):
            raise subprocess.CalledProcessError(1, argv)
        with patch('targeted_paste.PasteConnection', side_effect=PasteUnavailable('unsupported')), patch.object(c, 'run', side_effect=fail):
            self.assertEqual(c.deliver(self.last(), sid=self.sid), 'copy_failed')
        self.assertEqual(c.read_json(c.runtime_dir() / 'last.json')['raw'], 'udo con python')

    def test_copy_raw_and_clear(self):
        c.write_json(c.runtime_dir() / 'last.json', self.last())
        c.recover('copy-raw')
        self.assertEqual(self.calls[-1][1]['input'], 'udo con python')
        c.recover('clear')
        self.assertFalse((c.runtime_dir() / 'last.json').exists())

    def test_worker_retains_raw_and_applies_rules_once(self):
        self.setup_session()
        c.write_json(c.config_home() / 'herdr-voice/preferences.json', {'rules': [{'from': 'udo', 'to': 'Odoo'}]})
        states = iter(['recording', 'transcribing', 'idle', 'idle'])
        def engine():
            state = next(states)
            if state == 'idle':
                path = c.runtime_dir() / (self.sid + '.txt')
                if not path.exists(): path.write_text('udo con python')
            return state
        with patch.object(c, 'engine_state', side_effect=engine), patch.object(c.time, 'sleep'), patch.object(c.time, 'monotonic', side_effect=[1, 2, 3, 4]):
            c.worker(self.sid)
        last = c.read_json(c.runtime_dir() / 'last.json')
        self.assertEqual(last['raw'], 'udo con python')
        self.assertEqual(last['text'], 'Odoo con python')
        self.connection.paste.assert_called_once_with('Odoo con python')
        self.assertFalse((c.runtime_dir() / (self.sid + '.txt')).exists())

    def test_limit_warning_and_automatic_stop_notice(self):
        self.setup_session(limit=60)
        states = iter(['recording', 'transcribing', 'idle', 'idle'])
        def engine():
            state = next(states)
            if state == 'idle':
                path = c.runtime_dir() / (self.sid + '.txt')
                if not path.exists(): path.write_text('result')
            return state
        with patch.object(c, 'engine_state', side_effect=engine), patch.object(c.time, 'sleep'), patch.object(c.time, 'monotonic', side_effect=[31, 60, 61, 62]):
            c.worker(self.sid)
        self.notifications.assert_any_call('warning')
        self.notifications.assert_any_call('limit')

    def test_silence_no_result_does_not_replace_previous_text(self):
        self.setup_session()
        c.write_json(c.runtime_dir() / 'last.json', {'text': 'previous'})
        with patch.object(c, 'engine_state', side_effect=['recording', 'idle', 'idle']), patch.object(c.time, 'sleep'), patch.object(c.time, 'monotonic', side_effect=[1, 2, 6]):
            c.worker(self.sid)
        self.assertEqual(c.session()['notice'], 'no_result')
        self.assertEqual(c.read_json(c.runtime_dir() / 'last.json')['text'], 'previous')

    def test_runtime_files_are_private(self):
        self.setup_session()
        self.assertEqual(c.runtime_dir().stat().st_mode & 0o777, 0o700)
        self.assertEqual((c.runtime_dir() / 'state.json').stat().st_mode & 0o777, 0o600)

    def test_whole_words_and_no_cascading(self):
        rules = [{'from': 'udo', 'to': 'Odoo'}, {'from': 'Odoo', 'to': 'wrong'}, {'from': 'python', 'to': 'Python'}]
        self.assertEqual(c.apply_rules('UDO, todo y escudo. python.', rules), 'Odoo, todo y escudo. Python.')

    def test_duplicate_rule_is_rejected(self):
        with self.assertRaises(ValueError):
            c.settings([], [{'from': 'UDO', 'to': 'Odoo'}, {'from': 'udo', 'to': 'other'}])

    def test_settings_are_detached_and_block_new_recordings(self):
        with patch.object(c.subprocess, 'Popen', return_value=Mock(pid=os.getpid())) as spawn:
            c.settings(['Odoo'], [])
        self.assertEqual(c.session()['phase'], 'updating')
        self.assertIn('settings-worker', spawn.call_args.args[0])
        with self.assertRaises(RuntimeError): c.start()

    def test_status_remains_responsive_during_mutation_lock(self):
        self.setup_session(phase='updating')
        with c.locked():
            self.assertEqual(c.status()['state'], 'updating')


if __name__ == '__main__':
    unittest.main()
