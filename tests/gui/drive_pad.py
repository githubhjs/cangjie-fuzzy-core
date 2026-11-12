"""Drive the real Sweep Pad under Xvfb+openbox with real XTEST mouse events (xdotool).

usage: DISPLAY=:77 PATH=<dir with xdotool>:$PATH python3 drive_pad.py OUTDIR [pad args...]
Setup used on GX10 (no sudo): Xvfb :77 -screen 0 1280x800x24; xdotool and openbox from
`apt-get download xdotool libxdo3 openbox libobt2v5 libobrender32v5 libimlib2t64` + `dpkg -x`,
run through wrapper scripts that set LD_LIBRARY_PATH (openbox also XDG_CONFIG_DIRS/XDG_DATA_DIRS).
Checks: char sweep, single key click, two-word continuous and lift sweeps inject the
first candidate's code into a focused Tk Entry (target_app.py), and X input focus /
_NET_ACTIVE_WINDOW never leave the target window (sampled every ~30 ms).
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
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, 'target.log')
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


def entry_text():
    last = ''
    with open(LOG, encoding='utf-8') as f:
        for line in f:
            if ' TEXT ' in line:
                last = json.loads(line.split(' TEXT ', 1)[1])
    return last


def clear():
    open(LOG + '.clear', 'w').close()
    time.sleep(0.5)


target = subprocess.Popen([sys.executable, os.path.join(HERE, 'target_app.py'), LOG])
time.sleep(2.5)
T = xdo('search', '--name', '^TargetApp$').split()[0]
xdo('windowactivate', '--sync', T)
time.sleep(0.5)
focus0, active0 = xdo('getwindowfocus'), xdo('getactivewindow')
say('target window', T, 'focus', focus0, 'active', active0)

pad_err = open(os.path.join(OUT, 'pad.stderr'), 'w')
pad = subprocess.Popen([sys.executable, PAD] + PAD_ARGS, stdout=pad_err, stderr=subprocess.STDOUT)
time.sleep(10)
say('pad running', pad.poll() is None, 'focus after pad start', xdo('getwindowfocus'), 'active', xdo('getactivewindow'))

samples = []
stop = False


def monitor():
    while not stop:
        samples.append((time.time(), xdo('getwindowfocus'), xdo('getactivewindow')))
        time.sleep(0.03)


th = threading.Thread(target=monitor, daemon=True)
th.start()

# Locate the drawn keyboard from real pixels: key outline colour #708999.
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
            # real lift: release at the last key of word 1, press again on the first key of word 2
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


def case(name, keys, expect, lift_after=None):
    clear()
    sweep(keys, lift_after=lift_after)
    time.sleep(1.2)
    shot(name + '_candidates.png')
    click(*candidate(0))
    time.sleep(0.8)
    got = entry_text()
    say('CASE', name, 'path', ' '.join(keys), 'entry=%r' % got, 'expect=%r' % expect, 'PASS' if got == expect else 'FAIL')
    return got == expect


ok = []
ok.append(case('01_char_yhmbc', list('yhyjmnbvc'), 'yhmbc'))
clear()
x, y = centre['k']; click(int(x), int(y)); time.sleep(0.6)
got = entry_text(); say('CASE 02_single_key k entry=%r expect=%r %s' % (got, 'k', 'PASS' if got == 'k' else 'FAIL')); ok.append(got == 'k')
ok.append(case('03_word_continuous', list('yhmnbvcojhbnm'), 'yhmbcojbm'))
ok.append(case('04_word_lift', list('yhmnbvc') + list('ojhbnm'), 'yhmbcojbm', lift_after=6))

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
