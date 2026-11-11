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
import sys
import zipfile

pad = pathlib.Path(sys.argv[1])
repo = pad.parent
version = sys.argv[2]
files = [(pad / 'cangjie_sweep_pad.py', 'cangjie_sweep_pad.py'),
         (pad / 'README.md', 'README.md'), (pad / 'LICENSE', 'LICENSE')]
for folder in ('injectors', 'data'):
    for source in sorted((pad / folder).rglob('*')):
        if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc':
            files.append((source, source.relative_to(pad).as_posix()))
# keyboard.py imports core.layout; core/__init__.py also imports matcher/config.
for folder in ('sweep', 'core'):
    for source in sorted((repo / folder).glob('*.py')):
        files.append((source, source.relative_to(repo).as_posix()))
for folder in ('vectors',):
    for source in sorted((repo / 'sweep' / folder).glob('*.json')):
        files.append((source, source.relative_to(repo).as_posix()))
if not (pad / 'data' / 'cangjie3.tsv').is_file():
    raise SystemExit('Missing bundled data/cangjie3.tsv; refusing an incomplete archive')
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
PY
