"""Probe which X11 technique puts arbitrary Chinese text into a focused app while an IME (ibus-rime) is active.

usage: DISPLAY=... PATH=<dir with xdotool>:$PATH python3 probe_commit.py OUTDIR gtk|tk|qt
Run inside the isolated rig (private Xvfb/dbus/ibus-daemon with rime selected; PANEL_LOG optional).
Techniques: type = `xdotool type` (keysym remapping via XTEST); paste = xclip clipboard + Ctrl+V
(previous clipboard restored); keysym = `xdotool key U<hex>` per character.
Conditions: idle; after a Rime composition (`yhmbc`) was cancelled with Escape; while Rime is still
composing `yhmbc` (informational: shows what happens to a left-over preedit).
Writes OUTDIR/probe_<target>.json and prints one line per trial.
"""
import json
import os
import subprocess
import sys
import time

OUT, TARGET = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, 'probe_%s_target.log' % TARGET)
open(LOG, 'w').close()
TEXTS = ['顏', '顏值', '頻率', '中華民國', '倉頡輸入法測試']
TECHS = ['type', 'paste', 'keysym']
CONDS = ['idle', 'after_cancel', 'composing']
PREV_CLIP = 'previous-clipboard-内容'


def xdo(*args):
    return subprocess.run(['xdotool'] + [str(a) for a in args], capture_output=True, text=True).stdout.strip()


def last(kind):
    val = None
    with open(LOG, encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split(' ', 2)
            if len(parts) == 3 and parts[1] == kind:
                val = json.loads(parts[2])
    return val


def clip_set(text):
    p = subprocess.Popen(['xclip', '-selection', 'clipboard', '-i'], stdin=subprocess.PIPE,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p.communicate(text.encode('utf-8'))


def clip_get():
    r = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], capture_output=True, timeout=2)
    return r.stdout.decode('utf-8', 'replace') if r.returncode == 0 else None


def commit(tech, text):
    if tech == 'type':
        xdo('type', '--clearmodifiers', '--delay', '12', '--', text)
    elif tech == 'keysym':
        xdo('key', '--clearmodifiers', '--delay', '12', *['U%04X' % ord(c) for c in text])
    else:
        before = clip_get()
        clip_set(text)
        time.sleep(0.05)
        xdo('key', '--clearmodifiers', 'ctrl+v')
        time.sleep(0.3)
        if before is not None:
            clip_set(before)


scripts = {'gtk': 'gtk_target.py', 'tk': 'target_app.py'}
if TARGET == 'qt':
    script = os.path.join(OUT, 'qt_target.py')
    with open(script, 'w') as f:
        f.write('''import json, os, sys, time
from PyQt5.QtWidgets import QApplication, QLineEdit
from PyQt5.QtCore import QTimer
LOG = sys.argv[1]; log = open(LOG, 'a', encoding='utf-8', buffering=1)
app = QApplication(sys.argv); e = QLineEdit(); e.setWindowTitle('QtTarget'); e.resize(520, 60); e.move(40, 560)
e.textChanged.connect(lambda s: log.write('%.3f TEXT %s\\n' % (time.time(), json.dumps(s, ensure_ascii=False))))
def poll():
    if os.path.exists(LOG + '.clear'):
        os.remove(LOG + '.clear'); e.clear(); log.write('%.3f CLEARED ""\\n' % time.time())
t = QTimer(); t.timeout.connect(poll); t.start(100)
e.show(); QTimer.singleShot(400, lambda: (e.activateWindow(), e.setFocus()))
log.write('%.3f START %s\\n' % (time.time(), json.dumps(os.environ.get('QT_IM_MODULE', ''))))
app.exec_()
''')
else:
    script = os.path.join(HERE, scripts[TARGET])
name = {'gtk': '^GtkTarget$', 'tk': '^TargetApp$', 'qt': '^QtTarget$'}[TARGET]
proc = subprocess.Popen([sys.executable, script, LOG])
time.sleep(3)
win = xdo('search', '--name', name).split()[0]
xdo('windowactivate', '--sync', win); time.sleep(0.5)
print('target', TARGET, 'window', win, 'focus', xdo('getwindowfocus'), flush=True)
results = []
for tech in TECHS:
    for cond in CONDS:
        for text in TEXTS:
            xdo('key', 'Escape'); time.sleep(0.3)
            open(LOG + '.clear', 'w').close(); time.sleep(0.4)
            clip_set(PREV_CLIP)
            if cond != 'idle':
                xdo('key', '--delay', '20', 'y', 'h', 'm', 'b', 'c'); time.sleep(0.5)
                if cond == 'after_cancel':
                    xdo('key', 'Escape'); time.sleep(0.4)
            pre_text = last('TEXT') or ''
            commit(tech, text)
            time.sleep(0.8)
            got = last('TEXT') or ''
            pe = last('PREEDIT')  # only the GTK target logs preedit
            clip_after = clip_get() if tech == 'paste' else None
            ok = got == text and not pe
            r = dict(target=TARGET, tech=tech, cond=cond, text=text, entry_before=pre_text, entry=got,
                     preedit_left=pe, clipboard_restored=(clip_after == PREV_CLIP) if tech == 'paste' else None,
                     exact=ok)
            results.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            # leave nothing composing for the next trial
            xdo('key', 'Escape'); time.sleep(0.2)
proc.terminate()
with open(os.path.join(OUT, 'probe_%s.json' % TARGET), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
summary = {}
for r in results:
    k = (r['tech'], r['cond'])
    summary.setdefault(k, [0, 0])
    summary[k][0] += r['exact']; summary[k][1] += 1
for (tech, cond), (a, b) in summary.items():
    print('SUMMARY', TARGET, tech, cond, '%d/%d exact' % (a, b), flush=True)
