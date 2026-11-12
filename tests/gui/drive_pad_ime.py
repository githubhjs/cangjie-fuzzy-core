"""Drive the real Sweep Pad into a GTK3 Entry that uses a REAL IBus + Rime input method.

usage: DISPLAY=:91 IBUS_ADDRESS=... GTK_IM_MODULE=ibus PANEL_LOG=<log_panel.py log> \
       PATH=<dir with xdotool>:$PATH python3 drive_pad_ime.py OUTDIR [pad args...]
Needs a private ibus-daemon whose panel is log_panel.py (so the Rime candidate list is readable)
and the rime engine selected (`ibus engine rime`). The pad injects the candidate's Cangjie code with
xdotool; this driver checks that Rime receives it as a composition (preedit, nothing committed yet),
reads Rime's candidate list, picks the wanted text with digit keys, commits with Return, and checks
the Entry text. X input focus / _NET_ACTIVE_WINDOW are sampled every ~30 ms and must never move.
"""
import json
import os
import subprocess
import sys
import threading
import time

from PIL import Image

OUT = sys.argv[1]
PAD_ARGS = sys.argv[2:]
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


def last(path, kind, since=0.0):
    val = None
    with open(path, encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split(' ', 2)
            if len(parts) == 3 and parts[1] == kind and float(parts[0]) >= since:
                val = json.loads(parts[2])
    return val


def entry_text():
    return last(LOG, 'TEXT') or ''


def preedit(since=0.0):
    return last(LOG, 'PREEDIT', since)


def table(since=0.0):
    t = last(PANEL_LOG, 'TABLE', since)
    return t['candidates'] if t and t['visible'] else []


def reset():
    xdo('key', 'Escape'); time.sleep(0.3)
    open(LOG + '.clear', 'w').close()
    time.sleep(0.5)


target = subprocess.Popen([sys.executable, os.path.join(HERE, 'gtk_target.py'), LOG])
time.sleep(3)
T = xdo('search', '--name', '^GtkTarget$').split()[0]
xdo('windowactivate', '--sync', T)
time.sleep(0.5)
focus0, active0 = xdo('getwindowfocus'), xdo('getactivewindow')
say('target window', T, 'focus', focus0, 'active', active0, 'GTK_IM_MODULE', os.environ.get('GTK_IM_MODULE'))

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

# Locate the drawn keyboard from real pixels: key outline colour #708999 (same as drive_pad.py).
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


def pick(want, t0):
    """Select `want` in Rime with digit keys (whole phrase if listed, else char by char); return keys."""
    keys = []
    done = ''
    for _ in range(len(want) + 1):
        if done == want:
            break
        cands = table(t0)
        rest = want[len(done):]
        hit = next((c for c in cands if c == rest), None) or next((c for c in cands if rest.startswith(c)), None)
        if hit is None:
            say('   no Rime candidate for', repr(rest), 'in', cands)
            return keys, False
        k = str(cands.index(hit) + 1)
        t0 = time.time()
        xdo('key', k); keys.append(k); done += hit
        time.sleep(0.8)
        say('   pressed', k, '->', repr(hit), 'preedit now', repr(preedit()), 'next table', table(t0))
    xdo('key', 'Return'); keys.append('Return')
    time.sleep(0.8)
    return keys, True


def case(name, keys, want, lift_after=None):
    reset()
    sweep(keys, lift_after=lift_after)
    time.sleep(1.2)
    shot(name + '_1_pad_candidates.png')
    t0 = time.time()
    click(*candidate(0))
    time.sleep(1.2)
    shot(name + '_2_rime_composing.png')
    pe, cands, txt = preedit(t0), table(t0), entry_text()
    composing = bool(pe) and txt == ''
    say('CASE', name, 'path', ' '.join(keys), 'lift_after', lift_after)
    say('   after pad click: entry=%r preedit=%r rime_candidates=%s composing=%s' % (txt, pe, cands, composing))
    pressed, found = pick(want, t0)
    got = entry_text()
    ok = composing and found and got == want
    say('   keys pressed in Rime', pressed, 'entry=%r want=%r' % (got, want), 'PASS' if ok else 'FAIL')
    shot(name + '_3_committed.png')
    return ok


CASES = os.environ.get('CASES', 'word,char1,char2,wordlift').split(',')
ok = []
for c in CASES:
    if c == 'word':
        ok.append(case('01_word_continuous', list('yhmnbvcojhbnm'), '顏值'))
    elif c == 'char1':
        ok.append(case('02_char_slip_pick_頻', list('yhyjmnbvc'), '頻'))
    elif c == 'char2':
        ok.append(case('03_char_slip_pick_顏', list('yhyjmnbvc'), '顏'))
    elif c == 'wordlift':
        ok.append(case('04_word_lift', list('yhmnbvc') + list('ojhbnm'), '顏值', lift_after=6))

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
