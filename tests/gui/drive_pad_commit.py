"""Drive the real Sweep Pad in --mode commit into a GTK3 Entry that uses a REAL IBus + Rime input method.

usage: DISPLAY=... IBUS_ADDRESS=... GTK_IM_MODULE=ibus PANEL_LOG=<log_panel.py log> \
       PATH=<dir with xdotool>:$PATH python3 drive_pad_commit.py OUTDIR [extra pad args...]
Same rig as drive_pad_ime.py. Checks, for each case: after ONE click on the wanted pad candidate the
Entry holds exactly that text, Rime shows no preedit and no candidate table (nothing composing, no
digit/Return keys pressed), and X focus / _NET_ACTIVE_WINDOW never leave the GTK target.
Also runs the headless `--commit-text` path first.
"""
import json
import os
import subprocess
import sys
import threading
import time

from PIL import Image

OUT = sys.argv[1]
PAD_ARGS = ['--mode', 'commit'] + sys.argv[2:]
HERE = os.path.dirname(os.path.abspath(__file__))
PAD = os.environ.get('PAD', os.path.join(HERE, '..', '..', 'sweep-pad', 'cangjie_sweep_pad.py'))
PANEL_LOG = os.environ['PANEL_LOG']
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, 'gtk.log')
open(LOG, 'w').close()
report = []


def say(*a):
    line = ' '.join(str(x) for x in a)
    print(line, flush=True)
    report.append(line)


def xdo(*args):
    return subprocess.run(['xdotool'] + [str(a) for a in args], capture_output=True, text=True).stdout.strip()


def shot(name):
    path = os.path.join(OUT, name)
    subprocess.run(['import', '-window', 'root', path], check=True)
    return path


def events(path, kind, since=0.0):
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split(' ', 2)
            if len(parts) == 3 and parts[1] == kind and float(parts[0]) >= since:
                out.append(json.loads(parts[2]))
    return out


def entry_text():
    t = events(LOG, 'TEXT')
    return t[-1] if t else ''


def ime_activity(since):
    """Non-empty preedit in the Entry, or a visible Rime table / preedit in the panel, since `since`."""
    pe = [p for p in events(LOG, 'PREEDIT', since) if p]
    tables = [t['candidates'] for t in events(PANEL_LOG, 'TABLE', since) if t['visible'] and t['candidates']]
    ppe = [p['text'] for p in events(PANEL_LOG, 'PREEDIT', since) if p['visible'] and p['text']]
    return pe, tables, ppe


def reset():
    xdo('key', 'Escape'); time.sleep(0.3)
    open(LOG + '.clear', 'w').close()
    time.sleep(0.5)


def decode_index(seq, want):
    r = subprocess.run([sys.executable, PAD, '--decode-string', seq], capture_output=True, text=True)
    ranked = [d['char'] for d in json.loads(r.stdout)][:5]
    say('pad ranking for', repr(seq), ranked)
    return ranked.index(want)


target = subprocess.Popen([sys.executable, os.path.join(HERE, 'gtk_target.py'), LOG])
time.sleep(3)
T = xdo('search', '--name', '^GtkTarget$').split()[0]
xdo('windowactivate', '--sync', T)
time.sleep(0.5)
focus0, active0 = xdo('getwindowfocus'), xdo('getactivewindow')
say('target window', T, 'focus', focus0, 'active', active0, 'GTK_IM_MODULE', os.environ.get('GTK_IM_MODULE'),
    'ibus engine', subprocess.run(['ibus', 'engine'], capture_output=True, text=True).stdout.strip())

ok = []
# Headless path: --commit-text into the focused Entry while Rime is the active engine.
for text in ('顏值', '顏'):
    reset()
    t0 = time.time()
    r = subprocess.run([sys.executable, PAD, '--commit-text', text, '--delay', '0'], capture_output=True, text=True)
    time.sleep(1.0)
    got, act = entry_text(), ime_activity(t0)
    good = r.returncode == 0 and got == text and not any(act)
    say('HEADLESS --commit-text %r rc=%d entry=%r ime_activity=%s %s' % (text, r.returncode, got, act, 'PASS' if good else 'FAIL'))
    ok.append(good)
reset()

pad_err = open(os.path.join(OUT, 'pad.stderr'), 'w')
pad = subprocess.Popen([sys.executable, PAD] + PAD_ARGS, stdout=pad_err, stderr=subprocess.STDOUT)
time.sleep(10)
say('pad', PAD, 'args', PAD_ARGS, 'running', pad.poll() is None,
    'focus after pad start', xdo('getwindowfocus'), 'active', xdo('getactivewindow'))

samples = []
stop = False


def monitor():
    while not stop:
        samples.append((time.time(), xdo('getwindowfocus'), xdo('getactivewindow')))
        time.sleep(0.03)


th = threading.Thread(target=monitor, daemon=True)
th.start()

img = Image.open(shot('00_pad_idle.png')).convert('RGB')
W, H = img.size
px = img.load()
xs, ys = [], []
for y in range(H):
    for x in range(W):
        if px[x, y] == (0x70, 0x89, 0x99):
            xs.append(x); ys.append(y)
minx, maxx, miny = min(xs), max(xs), min(ys)
s = (maxx - minx + 2) / 10.0
cl, ct = minx - 7, miny - 7
ox, oy = 6 - 1.5 * s, 6 + .5 * s
layout = json.loads(subprocess.run([sys.executable, PAD, '--print-layout'], capture_output=True, text=True).stdout)
centre = {k: (cl + ox + (r[0] + r[2]) / 2 * s, ct + oy + (r[1] + r[3]) / 2 * s) for k, r in layout.items()}
bg = (0x17, 0x22, 0x2c)
row = [x for x in range(W) if px[x, ct + 2] == bg]
cw = max(row) - min(row) + 1
say('canvas origin', (cl, ct), 'scale', s, 'canvas width', cw)


def sweep(keys, step=6.0, dt=0.008, lift_after=None):
    pts = [centre[k] for k in keys]
    xdo('mousemove', int(pts[0][0]), int(pts[0][1])); time.sleep(0.05)
    xdo('mousedown', 1)
    for i, ((x0, y0), (x1, y1)) in enumerate(zip(pts, pts[1:])):
        if lift_after is not None and i == lift_after:
            xdo('mouseup', 1); time.sleep(0.04)
            xdo('mousemove', int(x1), int(y1)); time.sleep(0.04)
            xdo('mousedown', 1)
            continue
        n = max(1, int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** .5 / step))
        for j in range(1, n + 1):
            xdo('mousemove', int(x0 + (x1 - x0) * j / n), int(y0 + (y1 - y0) * j / n)); time.sleep(dt)
    xdo('mouseup', 1)


def candidate(i):
    return int(cl + cw * (2 * i + 1) / 10.0), int(ct - 16)


def click(x, y):
    xdo('mousemove', x, y); time.sleep(0.05); xdo('click', 1)


def case(name, keys, want, index, lift_after=None):
    reset()
    sweep(keys, lift_after=lift_after)
    time.sleep(1.2)
    shot(name + '_1_pad_candidates.png')
    t0 = time.time()
    click(*candidate(index))
    time.sleep(1.5)
    shot(name + '_2_committed.png')
    got = entry_text()
    pe, tables, ppe = ime_activity(t0)
    good = got == want and not pe and not tables and not ppe
    say('CASE', name, 'path', ' '.join(keys), 'lift_after', lift_after, 'clicked pad candidate', index + 1)
    say('   entry=%r want=%r gtk_preedit=%s rime_tables=%s rime_preedit=%s keys pressed in Rime [] %s'
        % (got, want, pe, tables, ppe, 'PASS' if good else 'FAIL'))
    return good


CASES = os.environ.get('CASES', 'word,char_yan,char_pin,wordlift').split(',')
for c in CASES:
    if c == 'word':
        ok.append(case('01_word_continuous', list('yhmnbvcojhbnm'), '顏值', decode_index('yhmnbvc ojhbnm', '顏值')))
    elif c == 'char_yan':
        ok.append(case('02_char_slip_顏', list('yhyjmnbvc'), '顏', decode_index('yhyjmnbvc', '顏')))
    elif c == 'char_pin':
        ok.append(case('03_char_slip_頻', list('yhyjmnbvc'), '頻', decode_index('yhyjmnbvc', '頻')))
    elif c == 'wordlift':
        ok.append(case('04_word_lift', list('yhmnbvc') + list('ojhbnm'), '顏值', decode_index('yhmnbvc ojhbnm', '顏值'), lift_after=6))

stop = True
th.join()
bad = [(t, f, a) for t, f, a in samples if f != focus0 or a != active0]
say('focus samples', len(samples), 'deviations', len(bad), 'first', bad[:3])
ok.append(not bad)
with open(os.path.join(OUT, 'focus_samples.json'), 'w') as f:
    json.dump(samples, f)
pad.terminate(); target.terminate()
say('ALL', 'PASS' if all(ok) else 'FAIL')
with open(os.path.join(OUT, 'report.txt'), 'w') as f:
    f.write('\n'.join(report) + '\n')
