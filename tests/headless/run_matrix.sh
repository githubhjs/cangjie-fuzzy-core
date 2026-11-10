#!/usr/bin/env bash
# Run the headless engine test on all three platforms against REAL release bundles.
#   Linux = this host, macOS = ssh alias m (MacBook Air, Squirrel), Windows 11 = ssh alias w (Weasel, Windows PowerShell 5.1)
# usage: run_matrix.sh LINUX_FULL_ZIP MAC_FULL_ZIP WIN_FULL_ZIP [RANGE=normal] [EXTRA_ARGS_LINUX_MAC] [EXTRA_ARGS_WIN]
#   e.g. run_matrix.sh a-linux.zip a-macos.zip a-win.zip wide "--fuzzy-default" "-FuzzyDefault"
set -u
LZ="$1"; MZ="$2"; WZ="$3"; RANGE="${4:-normal}"; XUNIX="${5:-}"; XWIN="${6:-}"
FIRST="${FIRST_SCHEMA:-}"            # e.g. FIRST_SCHEMA=cangjie3_fuzzy for the typo-tolerant-by-default projects
FS=""; [ -z "$FIRST" ] || FS="--first-schema $FIRST"
H="$(cd "$(dirname "$0")" && pwd)"
rc=0
echo "=== Linux (librime from the distro, octagram plugin)"
T="$(mktemp -d /tmp/cjm.XXXXXX)"
unzip -q "$LZ" -d "$T/b" && ( cd "$T"/b/* && bash install.sh --offline --no-deps --no-deploy --frontend ibus --with-cangjie5 --fuzzy-range "$RANGE" $XUNIX --rime-dir "$T/rime" >/dev/null 2>&1 ) || { echo "installer failed"; rc=1; }
LIB=/usr/lib/aarch64-linux-gnu; [ -e "$LIB/librime.so.1" ] || LIB=/usr/lib/x86_64-linux-gnu
python3 "$H/cj_headless.py" --lib "$LIB/librime.so.1" --user "$T/rime" --shared /usr/share/rime-data \
  --preload-plugin "$LIB/rime-plugins/librime-octagram.so:_Z28rime_require_module_octagramv" --modules default,octagram \
  --gens 3,5 --range "$RANGE" --require cangjie3_fluency,cangjie3_fuzzy $FS 2>&1 | tail -n 1 || rc=1
echo "=== macOS (Squirrel's librime)"
scp -q "$MZ" "$H/cj_headless.py" m:/tmp/ || rc=1
ssh m "cd /tmp && rm -rf cjm && mkdir cjm && cd cjm && unzip -q /tmp/$(basename "$MZ") && cd */ && bash install.sh --offline --no-deps --no-deploy --with-cangjie5 --fuzzy-range $RANGE $XUNIX --rime-dir /tmp/cjm/rime >/dev/null 2>&1; F='/Library/Input Methods/Squirrel.app/Contents/Frameworks'; /opt/homebrew/bin/python3 /tmp/cj_headless.py --lib \"\$F/librime.1.dylib\" --user /tmp/cjm/rime --shared '/Library/Input Methods/Squirrel.app/Contents/SharedSupport' --gens 3,5 --range $RANGE --require cangjie3_fluency,cangjie3_fuzzy $FS 2>&1 | tail -n 1" || rc=1
echo "=== Windows 11 (Weasel's rime.dll, PowerShell 5.1)"
scp -q "$WZ" "$H/cj_headless.py" "$H/win_run.ps1" 'w:C:/Users/huang/' || rc=1
# the remote shell is cmd.exe: single quotes are literal characters there, so only pass options that have a value, with double quotes
WA="-Zip C:\\Users\\huang\\$(basename "$WZ") -Range $RANGE"
[ -z "$XWIN" ] || WA="$WA -InstallArgs \"$XWIN\""
[ -z "$FIRST" ] || WA="$WA -FirstSchema $FIRST"
ssh w "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\huang\\win_run.ps1 $WA" 2>&1 | tail -n 1 || rc=1
exit $rc
