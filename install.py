#!/usr/bin/env python3
"""Install the Herdr dictation mod for the current Linux desktop user."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description='Install Herdr Voice for Herdr App')
parser.add_argument('--ui-language', choices=('en', 'es'), default='en', help='Button language (default: en)')
parser.add_argument('--speech-language', default='auto', help='Whisper language code, e.g. es or en; default: auto')
args = parser.parse_args()
root = Path(__file__).resolve().parent
home = Path.home()
app = home / '.config/herdr-app'
bin_dir = home / '.local/bin'
runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
for name in ('herdr-app', 'voxtype', 'wl-copy'):
    if not shutil.which(name):
        sys.exit(f'Missing {name}. Install it and add it to PATH before continuing.')
status = json.loads(subprocess.check_output(['herdr-app', 'status'], text=True))
layout_name = 'dictado'
layout_path = app / 'layouts' / (layout_name + '.json')
if layout_path.exists():
    sys.exit(f'{layout_path} already exists; no existing layout was changed.')
bin_dir.mkdir(parents=True, exist_ok=True)
mod_dir = app / 'mods/dictado'
if mod_dir.exists():
    sys.exit(f'{mod_dir} already exists; no existing mod was changed.')
for name in ('dictado-alternar', 'dictado-herdr-pegar'):
    if (bin_dir / name).exists():
        sys.exit(f'{bin_dir / name} already exists; remove or rename it before installation.')
shutil.copytree(root / 'mods' / 'dictado', mod_dir)
if args.ui_language == 'en':
    js = mod_dir / 'main.js'
    text = js.read_text()
    for old, new in [('comprobando','checking'), ('no disponible','unavailable'), ('Detener dictado','Stop dictation'), ('Transcribiendo…','Transcribing…'), ('Dictar','Dictate'), ('Dictado:','Dictation:')]:
        text = text.replace(old, new)
    js.write_text(text)
for name in ('dictado-alternar', 'dictado-herdr-pegar'):
    target = bin_dir / name
    shutil.copy2(root / name, target)
    target.chmod(0o700)
subprocess.run(['herdr-app', 'check', str(mod_dir)], check=True)
subprocess.run(['herdr-app', 'do', 'layout.clone', json.dumps({'name':status['layout'], 'as':layout_name})], check=True)
data = json.loads(layout_path.read_text())
def add_control(node):
    for i, child in enumerate(node.get('children', [])):
        if child.get('id') == 'status':
            child.pop('size', None)
            node['children'][i] = {'id':'dictado-status-row', 'type':'row', 'size':{'px':28}, 'resizable':False, 'children':[{'id':'dictado-control','type':'block','size':{'px':155},'content':{'mod':'dictado'}},child]}
            return True
        if add_control(child):
            return True
    return False
if not add_control(data):
    sys.exit('The cloned layout has no status block; add the dictado mod to it manually.')
layout_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
for key, value in [('output.mode','file'), ('output.file_path',str(runtime/'dictado-herdr-texto.txt')), ('output.file_mode','overwrite'), ('output.post_output_command',str(bin_dir/'dictado-herdr-pegar')), ('output.auto_submit','false'), ('whisper.language',args.speech_language)]:
    subprocess.run(['voxtype','config','set',key,value], check=True)
subprocess.run(['systemctl','--user','restart','voxtype'], check=True)
print('Installed. Select an agent pane and click Dictate / Dictar in the bottom bar.')
