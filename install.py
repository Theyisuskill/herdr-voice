#!/usr/bin/env python3
"""Transactional install, upgrade, check and removal of Herdr Voice."""
import argparse
import copy
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tomllib
import uuid

VERSION = 2
ROOT = Path(__file__).resolve().parent
TERMS = ['Odoo', 'PostgreSQL', 'Python', 'Mercantil', 'EcoFlow', 'Herdr', 'Voxtype', 'Claude', 'Codex']


def paths():
    home = Path.home()
    cfg = Path(os.environ.get('XDG_CONFIG_HOME', str(home / '.config')))
    return {'config': cfg, 'app': Path(os.environ.get('HERDR_APP_HOME', str(cfg / 'herdr-app'))),
            'own': cfg / 'herdr-voice', 'bin': home / '.local/bin', 'share': home / '.local/share/herdr-voice',
            'voxtype': cfg / 'voxtype/config.toml'}


def run(argv):
    return subprocess.run(argv, capture_output=True, text=True, check=True, timeout=45)


def load(path, default=None):
    return json.loads(path.read_text()) if path.exists() else copy.deepcopy(default or {})


def atomic(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        with tmp.open('xb') as f:
            os.chmod(tmp, mode)
            f.write(data)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def json_write(path, value):
    atomic(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def get_key(data, key):
    for part in key.split('.'):
        if not isinstance(data, dict) or part not in data:
            return {'present': False}
        data = data[part]
    return {'present': True, 'value': data}


def config_data():
    p = paths()['voxtype']
    return tomllib.loads(p.read_text()) if p.exists() else {}


def set_key(key, record):
    if not record.get('present'):
        run(['voxtype', 'config', 'unset', key])
    else:
        v = record['value']
        v = str(v).lower() if isinstance(v, bool) else json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v)
        run(['voxtype', 'config', 'set', key, v])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Transaction:
    """Durable snapshots of every touched file; also used for failed uninstalls."""
    def __init__(self):
        self.dir = paths()['own'] / 'backups' / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
        self.dir.mkdir(parents=True, mode=0o700)
        paths()['own'].chmod(0o700)
        self.snapshots = {}

    def capture(self, path):
        path = Path(path)
        if str(path) in self.snapshots:
            return
        if path.is_symlink():
            raise RuntimeError(f'Refusing to overwrite symlink: {path}')
        record = {'exists': path.exists()}
        if record['exists']:
            record.update(mode=path.stat().st_mode & 0o777, backup=str(len(self.snapshots)))
            atomic(self.dir / record['backup'], path.read_bytes())
        self.snapshots[str(path)] = record
        json_write(self.dir / 'files.json', self.snapshots)

    def write(self, path, data, mode=0o600):
        self.capture(path)
        atomic(path, data, mode)

    def rollback(self):
        for name, record in reversed(list(self.snapshots.items())):
            path = Path(name)
            if record['exists']:
                atomic(path, (self.dir / record['backup']).read_bytes(), record['mode'])
            else:
                path.unlink(missing_ok=True)


def service_active():
    return subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'voxtype'], timeout=10).returncode == 0


def wait_ready():
    for _ in range(40):
        if service_active():
            try:
                if run(['voxtype', 'status']).stdout.strip() == 'idle':
                    return
            except subprocess.SubprocessError:
                pass
        time.sleep(0.5)
    raise RuntimeError('Voxtype did not become ready after restart')


def restart():
    run(['systemctl', '--user', 'daemon-reload'])
    run(['systemctl', '--user', 'restart', 'voxtype'])
    wait_ready()


def contains_mod(node):
    return node.get('content', {}).get('mod') == 'dictado' or any(contains_mod(c) for c in node.get('children', []))


def attach_control(data):
    if contains_mod(data):
        def resize(node):
            if node.get('id') == 'dictado-control':
                node['size'] = {'px': 350}
            for child in node.get('children', []):
                resize(child)
        resize(data)
        return data
    def visit(node):
        for i, child in enumerate(node.get('children', [])):
            if child.get('id') == 'status':
                child.pop('size', None)
                node['children'][i] = {'id': 'dictado-status-row', 'type': 'row', 'size': {'px': 30},
                    'resizable': False, 'children': [
                        {'id': 'dictado-control', 'type': 'block', 'size': {'px': 350}, 'content': {'mod': 'dictado'}}, child]}
                return True
            if visit(child):
                return True
        return False
    if not visit(data):
        raise RuntimeError('The active layout has no status block; nothing was installed')
    return data


def preflight(removing=False):
    for name in ('herdr-app', 'voxtype', 'wl-copy', 'notify-send', 'systemctl', 'hc'):
        if not shutil.which(name):
            raise RuntimeError(f'Missing dependency: {name}')
    if not os.environ.get('XDG_RUNTIME_DIR'):
        raise RuntimeError('XDG_RUNTIME_DIR is required')
    status = json.loads(run(['herdr-app', 'status']).stdout)
    if status.get('errors') and not removing:
        raise RuntimeError('Resolve existing Herdr errors before installation')
    state = run(['voxtype', 'status']).stdout.strip()
    if state not in (('idle', 'stopped') if removing else ('idle',)) or not removing and not service_active():
        raise RuntimeError('Voxtype must be active and idle; finish the current recording first')
    state = load(Path(os.environ['XDG_RUNTIME_DIR']) / 'herdr-voice/state.json')
    if state.get('phase') in ('starting', 'recording', 'stopping', 'transcribing', 'delivering', 'cancelling', 'updating'):
        raise RuntimeError('Wait for Herdr Voice to finish delivery or cancellation first')
    return status


def manifest_path():
    return paths()['own'] / 'installation.json'


def make_prompt(terms, original):
    base = original.get('value', '') if original.get('present') else ''
    return ' '.join(s for s in (base, ', '.join(terms)) if s)


def install(args):
    p = paths()
    status = preflight()
    manifest = load(manifest_path())
    upgrading = args.upgrade
    if manifest and not upgrading:
        raise RuntimeError('Already installed; use --upgrade')
    if manifest:
        for name, expected in manifest['files'].items():
            path = Path(name)
            if path.name != 'dictado.json' and path.exists() and (path.is_symlink() or digest(path) != expected):
                raise RuntimeError(f'Preserve your modified managed file before upgrading: {path}')
    log_override = p['config'] / 'systemd/user/voxtype.service.d/herdr-voice.conf'
    if log_override.exists() and str(log_override) not in manifest.get('files', {}):
        raise RuntimeError('Unmanaged service override already exists: ' + str(log_override))
    layout = p['app'] / 'layouts/dictado.json'
    old_prefs = load(p['own'] / 'preferences.json')
    ui = args.ui_language or old_prefs.get('ui_language', 'en')
    current_config = config_data()
    speech = args.speech_language or old_prefs.get('speech_language') or get_key(current_config, 'whisper.language').get('value', 'auto')
    if layout.exists():
        if not upgrading or not contains_mod(load(layout)):
            raise RuntimeError('Existing dictado layout is not an upgradable installation')
        data = attach_control(load(layout))
        previous = manifest.get('previous_layout') or data.get('cloned_from', {}).get('name')
        if not manifest:
            # A legacy installation has no reliable pre-install values.
            if not (p['app'] / 'mods/dictado/main.js').exists() or 'dictado-alternar' not in (p['app'] / 'mods/dictado/main.js').read_text():
                raise RuntimeError('Cannot establish ownership of legacy dictado mod')
            if (p['bin'] / 'dictado-control').exists() or p['share'].exists():
                raise RuntimeError('Conflicting controller files without an installation manifest')
            for name in ('dictado-alternar', 'dictado-herdr-pegar'):
                helper = p['bin'] / name
                if not helper.exists() or helper.is_symlink() or 'voxtype' not in helper.read_text() and 'dictado-herdr-texto.txt' not in helper.read_text():
                    raise RuntimeError('Cannot establish legacy helper ownership: ' + name)
            if not args.legacy_config_backup:
                print('Legacy migration: original settings are unknown; destructive uninstall is disabled until a verified pre-install backup is supplied.')
    else:
        if upgrading or manifest:
            raise RuntimeError('Installation layout is missing; restore it before upgrading')
        for existing in (p['app'] / 'mods/dictado', p['bin'] / 'dictado-alternar', p['bin'] / 'dictado-herdr-pegar', p['bin'] / 'dictado-control', p['share']):
            if existing.exists():
                raise RuntimeError(f'Conflicting path: {existing}')
        previous = status['layout']
        data = attach_control(copy.deepcopy(load(p['app'] / 'layouts' / (previous + '.json'))))
        data['cloned_from'] = {'name': previous, 'version': 'herdr-voice-v2'}
    if not previous or previous == 'dictado':
        raise RuntimeError('Cannot identify the original layout')
    # Validate source and download VAD before changing installed files or config.
    run(['herdr-app', 'check', str(ROOT / 'mods/dictado')])
    run(['voxtype', 'setup', 'vad'])
    preferences = {**old_prefs, 'ui_language': ui, 'speech_language': speech,
                   'glossary': old_prefs.get('glossary', TERMS), 'rules': old_prefs.get('rules', []), 'max_duration': 300}
    manifest = copy.deepcopy(manifest) if manifest else {'version': VERSION, 'previous_layout': previous,
        'original': {}, 'applied': {}, 'files': {}, 'legacy_baseline': layout.exists()}
    if args.legacy_config_backup:
        if not manifest.get('legacy_baseline'):
            raise RuntimeError('--legacy-config-backup is only valid for a legacy migration')
        original_config = tomllib.loads(Path(args.legacy_config_backup).read_text())
        manifest['legacy_restore_known'] = True
    else:
        original_config = current_config
    changes = {'audio.max_duration_secs': 300, 'output.mode': 'file', 'output.file_mode': 'overwrite',
        'output.post_output_command': None, 'output.auto_submit': False, 'text.smart_auto_submit': False,
        'output.post_process.command': None, 'output.notification.on_transcription': False,
        'whisper.streaming': False, 'streaming.type_partials': False,
        'whisper.language': speech, 'vad.enabled': True, 'vad.backend': 'whisper'}
    original_prompt = manifest['original'].get('whisper.initial_prompt', get_key(original_config, 'whisper.initial_prompt'))
    changes['whisper.initial_prompt'] = make_prompt(preferences['glossary'], original_prompt)
    tx = Transaction()
    tx.capture(p['voxtype'])
    switched = False
    try:
        sources = [(ROOT / 'dictado-control', p['share'] / 'dictado-control', 0o700),
                   (ROOT / 'targeted_paste.py', p['share'] / 'targeted_paste.py', 0o600),
                   (ROOT / 'install.py', p['share'] / 'install.py', 0o600),
                   (ROOT / 'mods/dictado/main.js', p['app'] / 'mods/dictado/main.js', 0o600),
                   (ROOT / 'mods/dictado/mod.json', p['app'] / 'mods/dictado/mod.json', 0o600)]
        for source, dest, mode in sources:
            tx.write(dest, source.read_bytes(), mode)
            manifest['files'][str(dest)] = digest(dest)
        # Upstream INFO logs include full transcripts. Keep warnings and errors,
        # but prevent new dictated text from entering persistent journal history.
        tx.write(log_override, b'[Service]\nEnvironment="RUST_LOG=warn"\n')
        manifest['files'][str(log_override)] = digest(log_override)
        for name in ('dictado-control', 'dictado-alternar', 'dictado-herdr-pegar'):
            if name == 'dictado-control':
                content = '#!/usr/bin/env python3\nimport os\nimport sys\nos.execv(sys.executable, [sys.executable, ' + repr(str(p['share'] / 'dictado-control')) + '] + sys.argv[1:])\n'
            else:
                content = (ROOT / name).read_text()
            dest = p['bin'] / name
            tx.write(dest, content.encode(), 0o700)
            manifest['files'][str(dest)] = digest(dest)
        tx.write(layout, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())
        manifest['files'][str(layout)] = digest(layout)
        for key, value in changes.items():
            old = get_key(current_config, key)
            if key not in manifest['original'] or args.legacy_config_backup:
                manifest['original'][key] = get_key(original_config, key)
            # Preserve changes made outside the plugin, except its delivery/safety contract.
            required = key.startswith('output.') or key in ('audio.max_duration_secs', 'text.smart_auto_submit', 'whisper.streaming', 'streaming.type_partials')
            if not required and key in manifest['applied'] and old != manifest['applied'][key]:
                print('Preserved externally changed setting: ' + key)
                if key == 'whisper.language':
                    preferences['speech_language'] = old.get('value', 'auto')
                continue
            desired = {'present': value is not None, **({'value': value} if value is not None else {})}
            set_key(key, desired)
            manifest['applied'][key] = desired
        tx.write(p['own'] / 'preferences.json', (json.dumps(preferences, ensure_ascii=False, indent=2) + '\n').encode())
        manifest.update(version=VERSION, backup=str(tx.dir), app_home=str(p['app']))
        tx.write(manifest_path(), (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode())
        run(['herdr-app', 'check', str(p['app'] / 'mods/dictado')])
        restart()
        run(['herdr-app', 'do', 'layout.switch', json.dumps({'name': 'dictado'})])
        switched = True
        live = json.loads(run(['herdr-app', 'status']).stdout)
        if live.get('errors'):
            raise RuntimeError('Herdr rejected the updated mod')
    except Exception:
        tx.rollback()
        if switched:
            run(['herdr-app', 'do', 'layout.switch', json.dumps({'name': status['layout']})])
        restart()
        raise
    print('Installed Herdr Voice v2. Backups: ' + str(tx.dir))


def update_preferences(glossary, rules):
    p = paths()
    manifest = load(manifest_path())
    if not manifest:
        raise RuntimeError('Installation manifest missing; run --upgrade first')
    preferences = load(p['own'] / 'preferences.json')
    tx = Transaction()
    tx.capture(p['voxtype'])
    try:
        preferences.update(glossary=list(dict.fromkeys(t.strip() for t in glossary)), rules=rules)
        current_prompt = get_key(config_data(), 'whisper.initial_prompt')
        if current_prompt != manifest['applied'].get('whisper.initial_prompt'):
            manifest['original']['whisper.initial_prompt'] = current_prompt
        value = make_prompt(preferences['glossary'], manifest['original'].get('whisper.initial_prompt', {}))
        set_key('whisper.initial_prompt', {'present': True, 'value': value})
        manifest['applied']['whisper.initial_prompt'] = {'present': True, 'value': value}
        tx.write(p['own'] / 'preferences.json', (json.dumps(preferences, ensure_ascii=False, indent=2) + '\n').encode())
        tx.write(manifest_path(), (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode())
        restart()
    except Exception:
        tx.rollback()
        restart()
        raise


def uninstall():
    p = paths()
    state = preflight(removing=True)
    was_active = service_active()
    manifest = load(manifest_path())
    if not manifest:
        raise RuntimeError('No managed installation found; run --upgrade to migrate the legacy version first')
    if manifest.get('legacy_baseline') and not manifest.get('legacy_restore_known'):
        raise RuntimeError('Legacy restore baseline is unknown. Supply the pre-install config with --upgrade --legacy-config-backup PATH before uninstalling; files have not been removed.')
    tx = Transaction()
    tx.capture(p['voxtype'])
    try:
        current = config_data()
        for key, applied in manifest['applied'].items():
            if get_key(current, key) == applied:
                set_key(key, manifest['original'][key])
            else:
                print('Preserved externally changed setting: ' + key)
        if state['layout'] == 'dictado':
            run(['herdr-app', 'do', 'layout.switch', json.dumps({'name': manifest['previous_layout']})])
        for name, expected in manifest['files'].items():
            path = Path(name)
            if path.exists() and not path.is_symlink() and digest(path) == expected:
                tx.capture(path)
                path.unlink()
            elif path.exists():
                print('Preserved modified file: ' + name)
        tx.capture(manifest_path())
        manifest_path().unlink()
        if was_active:
            restart()
        else:
            run(['systemctl', '--user', 'daemon-reload'])
    except Exception:
        tx.rollback()
        run(['herdr-app', 'do', 'layout.switch', json.dumps({'name': state['layout']})])
        if was_active:
            restart()
        raise
    print('Uninstalled. Voxtype, models, preferences and backups were retained.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--upgrade', action='store_true')
    group.add_argument('--uninstall', action='store_true')
    group.add_argument('--check', action='store_true')
    parser.add_argument('--ui-language', choices=('en', 'es'))
    parser.add_argument('--speech-language')
    parser.add_argument('--legacy-config-backup', help='Verified Voxtype config from before the legacy plugin installation')
    args = parser.parse_args()
    try:
        if args.check:
            s = preflight()
            attach_control(copy.deepcopy(load(paths()['app'] / 'layouts' / (s['layout'] + '.json'))))
            print('Dependencies, service and layout are ready. No settings changed.')
        elif args.uninstall:
            with operation_lock():
                uninstall()
        else:
            with operation_lock():
                install(args)
    except Exception as exc:
        print(str(exc) if isinstance(exc, RuntimeError) else f'{type(exc).__name__}: operation failed; inspect the backup directory', file=sys.stderr)
        return 1
    return 0


@contextlib.contextmanager
def operation_lock():
    root = os.environ.get('XDG_RUNTIME_DIR')
    if not root:
        raise RuntimeError('XDG_RUNTIME_DIR is required')
    folder = Path(root) / 'herdr-voice'
    folder.mkdir(mode=0o700, exist_ok=True)
    if folder.is_symlink() or folder.stat().st_uid != os.getuid():
        raise RuntimeError('Unsafe runtime directory')
    with (folder / 'control.lock').open('a+') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


if __name__ == '__main__':
    sys.exit(main())
