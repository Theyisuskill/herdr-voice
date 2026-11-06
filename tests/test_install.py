"""Installer transactions exercised in scratch homes, with simulated app/service."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'install.py')
i = importlib.util.module_from_spec(spec)
spec.loader.exec_module(i)


def emit_toml(data):
    lines = []
    def emit(node, prefix=''):
        scalars = {k: v for k, v in node.items() if not isinstance(v, dict)}
        if prefix:
            lines.append('[' + prefix + ']')
        for k, v in scalars.items():
            lines.append(k + ' = ' + json.dumps(v, ensure_ascii=False))
        for k, v in node.items():
            if isinstance(v, dict): emit(v, (prefix + '.' if prefix else '') + k)
    emit(data)
    return '\n'.join(lines) + '\n'


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.paths = {'config': root/'config', 'app': root/'app', 'own': root/'config/herdr-voice',
            'bin': root/'bin', 'share': root/'share', 'voxtype': root/'config/voxtype/config.toml'}
        self.runtime = root / 'runtime'
        self.runtime.mkdir()
        self.env = patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(self.runtime)})
        self.env.start(); self.addCleanup(self.env.stop)
        self.layout = {'id': 'root', 'type': 'column', 'children': [
            {'id': 'main', 'type': 'block', 'content': {'tab': 'active'}},
            {'id': 'status', 'type': 'block', 'size': {'px': 28}, 'content': {'mod': 'workspace-status'}}]}
        i.json_write(self.paths['app'] / 'layouts/main.json', self.layout)
        self.config = {'whisper': {'model': 'large-v3-turbo', 'language': 'es'}, 'output': {'mode': 'clipboard'}, 'audio': {'max_duration_secs': 60}}
        self.write_config()
        self.original = self.paths['voxtype'].read_bytes()
        self.current_layout = 'main'
        self.args = argparse.Namespace(upgrade=False, ui_language='es', speech_language='es', legacy_config_backup=None)
        for name, value in [('paths', lambda: self.paths), ('service_active', lambda: True), ('restart', lambda: None), ('run', self.fake_run), ('set_key', self.set_key)]:
            p = patch.object(i, name, side_effect=value)
            p.start(); self.addCleanup(p.stop)
        p = patch.object(i.shutil, 'which', return_value='/fake/tool')
        p.start(); self.addCleanup(p.stop)

    def write_config(self):
        i.atomic(self.paths['voxtype'], emit_toml(self.config).encode())

    def set_key(self, key, record):
        node = self.config
        parts = key.split('.')
        for part in parts[:-1]: node = node.setdefault(part, {})
        if record['present']: node[parts[-1]] = record['value']
        else: node.pop(parts[-1], None)
        self.write_config()

    def fake_run(self, argv):
        output = ''
        if argv == ['herdr-app', 'status']:
            output = json.dumps({'layout': self.current_layout, 'errors': []})
        elif argv == ['voxtype', 'status']:
            output = 'idle'
        elif argv[:3] == ['herdr-app', 'do', 'layout.switch']:
            self.current_layout = json.loads(argv[3])['name']
        return subprocess.CompletedProcess(argv, 0, output)

    def test_install_upgrade_and_uninstall_preserve_external_setting(self):
        i.install(self.args)
        m = i.load(i.manifest_path())
        self.assertEqual(m['version'], 2)
        self.assertEqual(self.current_layout, 'dictado')
        self.assertIn('Odoo', self.config['whisper']['initial_prompt'])
        self.assertFalse(self.config['output']['notification']['on_transcription'])
        self.assertNotIn('post_output_command', self.config['output'])
        self.config['whisper']['language'] = 'fr'
        self.write_config()
        self.args.upgrade = True
        i.install(self.args)
        self.assertEqual(self.config['whisper']['language'], 'fr')
        i.uninstall()
        self.assertEqual(self.current_layout, 'main')
        self.assertEqual(self.config['whisper']['language'], 'fr')
        self.assertEqual(self.config['output']['mode'], 'clipboard')
        self.assertFalse((self.paths['bin'] / 'dictado-control').exists())
        self.assertFalse(i.manifest_path().exists())

    def test_failed_restart_restores_files_and_exact_config(self):
        with patch.object(i, 'restart', side_effect=[RuntimeError('failed startup'), None]):
            with self.assertRaises(RuntimeError): i.install(self.args)
        self.assertEqual(self.paths['voxtype'].read_bytes(), self.original)
        self.assertFalse(i.manifest_path().exists())
        self.assertFalse((self.paths['app'] / 'layouts/dictado.json').exists())
        self.assertEqual(self.current_layout, 'main')

    def test_missing_status_causes_no_install_mutations(self):
        i.json_write(self.paths['app'] / 'layouts/main.json', {'type': 'block', 'id': 'main'})
        with self.assertRaises(RuntimeError): i.install(self.args)
        self.assertEqual(self.paths['voxtype'].read_bytes(), self.original)
        self.assertFalse((self.paths['bin'] / 'dictado-control').exists())

    def test_failed_update_preserves_previous_installation(self):
        i.install(self.args)
        manifest = i.manifest_path().read_bytes()
        config = self.paths['voxtype'].read_bytes()
        self.args.upgrade = True
        with patch.object(i, 'restart', side_effect=[RuntimeError('failed startup'), None]):
            with self.assertRaises(RuntimeError): i.install(self.args)
        self.assertEqual(i.manifest_path().read_bytes(), manifest)
        self.assertEqual(self.paths['voxtype'].read_bytes(), config)
        self.assertTrue((self.paths['bin'] / 'dictado-control').exists())

    def legacy(self):
        data = i.attach_control(copy.deepcopy(self.layout))
        data['cloned_from'] = {'name': 'main'}
        i.json_write(self.paths['app'] / 'layouts/dictado.json', data)
        mod = self.paths['app'] / 'mods/dictado/main.js'
        i.atomic(mod, b'// legacy dictado-alternar')
        for name in ('dictado-alternar', 'dictado-herdr-pegar'):
            i.atomic(self.paths['bin'] / name, b'#!/usr/bin/python3\n# voxtype dictado-herdr-texto.txt\n', 0o700)
        self.config['output']['post_output_command'] = str(self.paths['bin'] / 'dictado-herdr-pegar')
        self.write_config()
        self.current_layout = 'dictado'
        self.args.upgrade = True

    def test_legacy_without_baseline_will_not_destructively_uninstall(self):
        self.legacy()
        i.install(self.args)
        config = self.paths['voxtype'].read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'baseline is unknown'): i.uninstall()
        self.assertEqual(self.paths['voxtype'].read_bytes(), config)
        self.assertTrue(i.manifest_path().exists())

    def test_legacy_known_backup_restores_original_hook_and_output(self):
        backup = Path(self.tmp.name) / 'before.toml'
        backup.write_bytes(self.original)
        self.legacy()
        self.args.legacy_config_backup = str(backup)
        i.install(self.args)
        i.uninstall()
        self.assertNotIn('post_output_command', self.config['output'])
        self.assertEqual(self.config['output']['mode'], 'clipboard')

    def test_legacy_does_not_overwrite_unknown_controller(self):
        self.legacy()
        other = self.paths['bin'] / 'dictado-control'
        i.atomic(other, b'unrelated')
        with self.assertRaisesRegex(RuntimeError, 'Conflicting controller'): i.install(self.args)
        self.assertEqual(other.read_bytes(), b'unrelated')

    def test_uninstall_preserves_modified_managed_files(self):
        i.install(self.args)
        helper = self.paths['bin'] / 'dictado-alternar'
        helper.write_text('user modification')
        i.uninstall()
        self.assertEqual(helper.read_text(), 'user modification')

    def test_transaction_rolls_back_deleted_and_new_files(self):
        old = Path(self.tmp.name) / 'old'
        new = Path(self.tmp.name) / 'new'
        old.write_text('before')
        tx = i.Transaction()
        tx.write(old, b'after')
        tx.write(new, b'created')
        tx.rollback()
        self.assertEqual(old.read_text(), 'before')
        self.assertFalse(new.exists())

    def test_settings_failure_rolls_back_preferences_and_config(self):
        i.install(self.args)
        pref = self.paths['own'] / 'preferences.json'
        before_pref = pref.read_bytes()
        before_cfg = self.paths['voxtype'].read_bytes()
        with patch.object(i, 'restart', side_effect=[RuntimeError('failed startup'), None]):
            with self.assertRaises(RuntimeError): i.update_preferences(['new term'], [])
        self.assertEqual(pref.read_bytes(), before_pref)
        self.assertEqual(self.paths['voxtype'].read_bytes(), before_cfg)


if __name__ == '__main__': unittest.main()
