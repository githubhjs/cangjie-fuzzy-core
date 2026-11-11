#!/bin/sh
# Local archive builder; does not contact GitHub or install dependencies.
set -eu
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 VERSION" >&2
    exit 2
fi
case "$1" in
    ''|*[!A-Za-z0-9._-]*) echo "VERSION must contain only letters, digits, dot, underscore, or hyphen" >&2; exit 2 ;;
esac
PAD_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 - "$PAD_DIR" "$1" <<'PY'
import hashlib
import pathlib
import json
import os
import subprocess
import tempfile
import sys
import zipfile

pad = pathlib.Path(sys.argv[1])
repo = pad.parent
version = sys.argv[2]
files = [(source, source.name) for source in sorted(pad.glob('*.py'))]
files += [(pad / 'README.md', 'README.md'), (pad / 'LICENSE', 'LICENSE')]
for folder in ('injectors', 'data'):
    for source in sorted((pad / folder).rglob('*')):
        if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc':
            files.append((source, source.relative_to(pad).as_posix()))
# keyboard.py imports core.layout; core/__init__.py also imports matcher/config.
for folder in ('sweep', 'core'):
    for source in sorted((repo / folder).glob('*.py')):
        files.append((source, source.relative_to(repo).as_posix()))
for source in sorted((repo / 'sweep' / 'results').glob('defaults*.json')):
    files.append((source, source.relative_to(repo).as_posix()))
for folder in ('vectors',):
    for source in sorted((repo / 'sweep' / folder).glob('*.json')):
        files.append((source, source.relative_to(repo).as_posix()))
for name in ('data/cangjie3.tsv', 'data/essay.txt', 'data/LICENSE-essay.txt',
             'sweep/results/defaults_words.json'):
    if not any(archive_name == name for _, archive_name in files):
        raise SystemExit('Missing required release file: ' + name)
for source, name in files:
    if not source.is_file():
        raise SystemExit('Missing required release file: ' + name)
if not any(name == 'injectors/__init__.py' for _, name in files):
    raise SystemExit('Missing injector package')
if not any(name == 'sweep/decoder.py' for _, name in files):
    raise SystemExit('Missing sweep decoder package')
dist = pad / 'dist'
dist.mkdir(exist_ok=True)
archive = dist / ('cangjie-sweep-pad-' + version + '.zip')
with zipfile.ZipFile(str(archive), 'w', compression=zipfile.ZIP_DEFLATED) as output:
    for source, name in files:
        output.write(str(source), name)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
checksum = archive.with_suffix(archive.suffix + '.sha256')
checksum.write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
print(archive)
print(checksum)
# Test the actual archive from a foreign cwd, with no checkout imports or cache.
with tempfile.TemporaryDirectory(prefix='release-check-', dir=str(pad)) as temporary:
    work = pathlib.Path(temporary)
    extracted = work / 'bundle'
    with zipfile.ZipFile(str(archive)) as output:
        output.extractall(str(extracted))
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.update(PYTHONDONTWRITEBYTECODE='1', XDG_CACHE_HOME=str(work / 'cache'),
               LOCALAPPDATA=str(work / 'cache'), HOME=str(work / 'home'))
    script = str(extracted / 'cangjie_sweep_pad.py')
    config = str(work / 'config.json')
    for sequence, target in (('yhmnbvc ojhbnm', '顏值'), ('yhjmnbvc yuiokjhj', '頻率')):
        result = subprocess.run([sys.executable, script, '--config', config,
                                 '--decode-string', sequence, '--expect', target],
                                cwd=str(work), env=env, capture_output=True, text=True)
        print('Extracted decode ' + target + ': ' + result.stdout.strip())
        if result.returncode:
            raise SystemExit('Extracted decode failed: ' + result.stderr.strip())
    check = subprocess.run([sys.executable, script, '--config', config, '--self-check'],
                           cwd=str(work), env=env, capture_output=True, text=True)
    print('Extracted self-check (exit %d): %s' % (check.returncode, check.stdout.strip()))
    if check.stderr:
        print(check.stderr.strip(), file=sys.stderr)
    try:
        status = json.loads(check.stdout)
    except ValueError:
        raise SystemExit('Extracted self-check did not return a valid diagnostic object')
    if check.returncode not in (0, 1) or not status.get('table_available') or not status.get('essay_available'):
        raise SystemExit('Extracted self-check failed: bundle data unavailable')
    if check.returncode:
        print('Desktop prerequisites are unavailable; live injection remains unverified.')
print('Archive extraction and both owner decodes verified.')
PY
