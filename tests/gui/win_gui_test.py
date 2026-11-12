"""Windows GUI test for the installed Sweep Pad. Run INSIDE the interactive session (scheduled task /it).

usage: python win_gui_test.py OUTDIR PAD_DIR
Real SendInput mouse events drive the pad; a Tk target Entry logs what it receives.
Every injecting step first checks that the target window is the foreground window, else aborts.
Screenshots cover only the pad window rectangle.
Launch (from ssh, into the logged-on console session):
  schtasks /create /f /tn cjgui_test /sc once /st 23:59 /ru <user> /it [/rl highest] /tr "<pythonw.exe> <this file> <OUTDIR> <PAD_DIR>"
  schtasks /run /tn cjgui_test
/rl highest is needed when an elevated window (for example an admin terminal) is in the foreground:
UIPI then silently drops all medium-integrity SendInput/SetCursorPos.
"""
import ctypes
from ctypes import wintypes as w
import json
import os
import struct
import subprocess
import sys
import threading
import time

OUT, PAD_DIR = sys.argv[1], sys.argv[2]
PAD = os.path.join(PAD_DIR, 'cangjie_sweep_pad.py')
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
PYW = os.path.join(os.path.dirname(PY), 'pythonw.exe')
NOWIN = 0x08000000
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, 'target.log')
open(LOG, 'w').close()
lines = []


def say(*a):
    s = ' '.join(str(x) for x in a)
    lines.append(s)
    with open(os.path.join(OUT, 'report.txt'), 'a', encoding='utf-8') as f:
        f.write(s + '\n')


try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception as e:
    say('dpi awareness call failed', e)
u = ctypes.WinDLL('user32', use_last_error=True)
g = ctypes.WinDLL('gdi32')
u.GetForegroundWindow.restype = w.HWND
u.FindWindowW.restype = w.HWND
u.FindWindowW.argtypes = [w.LPCWSTR, w.LPCWSTR]
u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
u.GetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int]
u.GetDC.restype = w.HDC
g.CreateCompatibleDC.restype = w.HDC
g.CreateCompatibleBitmap.restype = w.HBITMAP
g.SelectObject.restype = w.HGDIOBJ
u.GetDC.argtypes = [w.HWND]
u.ReleaseDC.argtypes = [w.HWND, w.HDC]
g.CreateCompatibleDC.argtypes = [w.HDC]
g.CreateCompatibleBitmap.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int]
g.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]
g.BitBlt.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HDC, ctypes.c_int, ctypes.c_int, w.DWORD]
g.GetDIBits.argtypes = [w.HDC, w.HBITMAP, w.UINT, w.UINT, ctypes.c_void_p, ctypes.c_void_p, w.UINT]
g.DeleteObject.argtypes = [w.HGDIOBJ]
g.DeleteDC.argtypes = [w.HDC]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_int32), ('dy', ctypes.c_int32), ('mouseData', ctypes.c_uint32),
                ('dwFlags', ctypes.c_uint32), ('time', ctypes.c_uint32), ('dwExtraInfo', ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', ctypes.c_uint16), ('wScan', ctypes.c_uint16), ('dwFlags', ctypes.c_uint32),
                ('time', ctypes.c_uint32), ('dwExtraInfo', ctypes.c_size_t)]


class U(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ('u',)
    _fields_ = [('type', ctypes.c_uint32), ('u', U)]


VX, VY = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
VW, VH = u.GetSystemMetrics(78), u.GetSystemMetrics(79)


def mouse(flags, x=0, y=0):
    if flags & 0x8000:
        x = int((x - VX) * 65535 / max(1, VW - 1))
        y = int((y - VY) * 65535 / max(1, VH - 1))
    ev = INPUT(type=0, mi=MOUSEINPUT(x, y, 0, flags, 0, 0))
    if u.SendInput(1, ctypes.byref(ev), ctypes.sizeof(INPUT)) != 1:
        raise RuntimeError('SendInput mouse failed %d' % ctypes.get_last_error())


def move(x, y):
    mouse(0x0001 | 0x8000 | 0x4000, x, y)  # MOVE | ABSOLUTE | VIRTUALDESK


def down():
    mouse(0x0002)


def up():
    mouse(0x0004)


u.WindowFromPoint.restype = w.HWND
u.WindowFromPoint.argtypes = [w.POINT]
u.GetAncestor.restype = w.HWND
u.GetAncestor.argtypes = [w.HWND, ctypes.c_uint]


def root_at(x, y):
    h = u.WindowFromPoint(w.POINT(int(x), int(y)))
    return u.GetAncestor(h, 2) if h else 0  # GA_ROOT


def check_point(x, y, expect, what):
    got = root_at(x, y)
    if got != expect:
        raise SystemExit('ABORT: point %s for %s is covered by window %s, expected %s; no click sent' % ((x, y), what, got, expect))


def click(x, y, expect, what):
    check_point(x, y, expect, what)
    move(x, y); time.sleep(0.05); down(); time.sleep(0.04); up()


def rect(hwnd):
    r = w.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def fg():
    return u.GetForegroundWindow() or 0


def capture(box, name=None):
    """Return (width, height, bytes BGRA top-down) of a screen rectangle; optionally save a BMP."""
    x0, y0, x1, y1 = box
    W, H = x1 - x0, y1 - y0
    sdc = u.GetDC(None)
    mdc = g.CreateCompatibleDC(sdc)
    bmp = g.CreateCompatibleBitmap(sdc, W, H)
    g.SelectObject(mdc, bmp)
    g.BitBlt(mdc, 0, 0, W, H, sdc, x0, y0, 0x00CC0020)
    hdr = struct.pack('<IiiHHIIiiII', 40, W, -H, 1, 32, 0, 0, 0, 0, 0, 0)
    bi = ctypes.create_string_buffer(hdr + b'\0' * 16)
    buf = ctypes.create_string_buffer(W * H * 4)
    g.GetDIBits(mdc, bmp, 0, H, buf, bi, 0)
    g.DeleteObject(bmp); g.DeleteDC(mdc); u.ReleaseDC(None, sdc)
    data = buf.raw
    if name:
        with open(os.path.join(OUT, name), 'wb') as f:
            size = 14 + 40 + len(data)
            f.write(b'BM' + struct.pack('<IHHI', size, 0, 0, 54))
            f.write(struct.pack('<IiiHHIIiiII', 40, W, -H, 1, 32, 0, len(data), 2835, 2835, 0, 0))
            f.write(data)
    return W, H, data


def windows_of(pid):
    found = []
    PROC = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)

    def cb(h, _):
        p = w.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(h):
            found.append(h)
        return True
    u.EnumWindows(PROC(cb), 0)
    return found


def entry_text():
    last = ''
    with open(LOG, encoding='utf-8') as f:
        for line in f:
            if ' TEXT ' in line:
                last = json.loads(line.split(' TEXT ', 1)[1])
    return last


def clear():
    open(LOG + '.clear', 'w').close()
    time.sleep(0.6)


samples = []
stop = [False]


def monitor():
    while not stop[0]:
        samples.append((round(time.time(), 3), fg()))
        time.sleep(0.02)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]


li = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
u.GetLastInputInfo(ctypes.byref(li))
idle = ((ctypes.windll.kernel32.GetTickCount() & 0xffffffff) - li.dwTime) & 0xffffffff
say('owner idle seconds at start', idle / 1000.0)
for _ in range(90):  # our own earlier injected input also counts; wait up to 90 s for 2 idle minutes
    if idle >= 120000:
        break
    time.sleep(1)
    u.GetLastInputInfo(ctypes.byref(li))
    idle = ((ctypes.windll.kernel32.GetTickCount() & 0xffffffff) - li.dwTime) & 0xffffffff
say('idle seconds after wait', idle / 1000.0)
if idle < 120000:
    say('ABORT: owner input within the last 2 minutes; not touching the desktop'); sys.exit(0)
pt = w.POINT(); u.GetCursorPos(ctypes.byref(pt)); cursor0 = (pt.x, pt.y)
procs = []
results = {}
try:
    target = subprocess.Popen([PYW, os.path.join(HERE, 'target_app.py'), LOG, '420x80+60+460'])
    procs.append(target)
    time.sleep(3)
    T = None
    for _ in range(50):
        hs = windows_of(target.pid)
        if hs:
            T = hs[0]; break
        time.sleep(0.1)
    if not T:
        raise SystemExit('target window not found')
    tr = rect(T)
    say('target hwnd', T, 'rect', tr, 'foreground', fg())
    u.SetWindowPos(T, w.HWND(-1), 0, 0, 0, 0, 0x13)  # topmost, no move/size/activate: so the real click lands on it
    time.sleep(0.3)
    click((tr[0] + tr[2]) // 2, tr[1] + (tr[3] - tr[1]) * 2 // 3, T, 'target')  # real click into the target window
    time.sleep(0.5)
    cp = w.POINT(); u.GetCursorPos(ctypes.byref(cp))
    say('after clicking target: foreground', fg(), 'is target', fg() == T, 'cursor', (cp.x, cp.y), 'root at cursor', root_at(cp.x, cp.y))
    if fg() != T:
        # Fallback, logged separately: attach to the foreground thread and ask for activation.
        k32 = ctypes.windll.kernel32
        ft = u.GetWindowThreadProcessId(fg(), None)
        me = k32.GetCurrentThreadId()
        a1 = u.AttachThreadInput(me, ft, True)
        s1 = u.SetForegroundWindow(T)
        u.AttachThreadInput(me, ft, False)
        time.sleep(0.5)
        say('fallback AttachThreadInput', a1, 'SetForegroundWindow', s1, 'foreground', fg(), 'is target', fg() == T)
    if fg() != T:
        raise SystemExit('ABORT: target is not foreground, no injection attempted')
    threading.Thread(target=monitor, daemon=True).start()

    # A. --inject-test through injectors/windows.py SendInput, no pad window, no Rime.
    clear()
    p = subprocess.Popen([PY, PAD, '--inject-test', 'yhmbc', '--delay', '3'], creationflags=NOWIN,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    t0 = time.time()
    while p.poll() is None:
        if fg() != T:
            p.kill(); raise SystemExit('ABORT: foreground drifted during --inject-test countdown')
        time.sleep(0.1)
    time.sleep(0.5)
    got = entry_text()
    say('A inject-test rc', p.returncode, 'entry=%r' % got, 'PASS' if got == 'yhmbc' else 'FAIL', 'fg is target', fg() == T)
    results['A_inject_test'] = got == 'yhmbc'

    # B. live pad window
    clear()
    fg_before_pad = fg()
    pad = subprocess.Popen([PYW, PAD]); procs.append(pad)
    P = None
    for _ in range(200):
        hs = windows_of(pad.pid)
        if hs:
            P = max(hs, key=lambda h: (lambda r: (r[2] - r[0]) * (r[3] - r[1]))(rect(h))); break
        time.sleep(0.05)
    if not P:
        raise SystemExit('pad window not found')
    time.sleep(0.3)
    fg_after_pad = fg()
    style = u.GetWindowLongPtrW(P, -20)
    say('pad hwnd', P, 'rect', rect(P), 'exstyle 0x%x' % style, 'NOACTIVATE', bool(style & 0x08000000),
        'TOOLWINDOW', bool(style & 0x80), 'TOPMOST', bool(style & 0x8))
    say('foreground before pad start', fg_before_pad, 'after pad shown', fg_after_pad, 'target kept foreground', fg_after_pad == T)
    results['B0_pad_start_keeps_foreground'] = fg_after_pad == T
    results['B0_exstyle_noactivate'] = bool(style & 0x08000000)
    if fg() != T:
        click((tr[0] + tr[2]) // 2, tr[1] + (tr[3] - tr[1]) * 2 // 3, T, 'target'); time.sleep(0.5)
        if fg() != T:
            raise SystemExit('ABORT: cannot restore target foreground')
    time.sleep(10)  # decoder load
    pr = rect(P)
    Wd, Hd, data = capture(pr, 'win_00_pad_idle.bmp')

    def pix(x, y):
        i = (y * Wd + x) * 4
        return data[i + 2], data[i + 1], data[i]
    xs, ys = [], []
    for y in range(Hd):
        for x in range(Wd):
            r_, g_, b_ = pix(x, y)
            if abs(r_ - 0x70) < 10 and abs(g_ - 0x89) < 10 and abs(b_ - 0x99) < 10:
                xs.append(x); ys.append(y)
    # keep only rows that contain long horizontal key edges (other widgets can share the colour)
    from collections import Counter
    rows = Counter(ys)
    good = set(y for y, c in rows.items() if c >= 30)
    xs = [x for x, y in zip(xs, ys) if y in good]
    ys = [y for y in ys if y in good]
    if not xs:
        raise SystemExit('ABORT: keyboard outline colour not found in pad capture')
    L, Tp = pr[0] + min(xs) - 1, pr[1] + min(ys) - 1
    s = (max(xs) - min(xs) + 2) / 10.0
    lay = json.loads(subprocess.run([PY, PAD, '--print-layout'], capture_output=True, text=True, creationflags=NOWIN).stdout)
    centre = {k: (L + ((r[0] + r[2]) / 2 - 1.5) * s, Tp + ((r[1] + r[3]) / 2 + 0.5) * s) for k, r in lay.items()}
    say('key grid left/top', (L, Tp), 'key px', s)

    def guard():
        if fg() != T:
            raise SystemExit('ABORT: target not foreground before pad action')

    def sweep(keys, step=6.0, dt=0.008):
        pts = [centre[k] for k in keys]
        for x_, y_ in pts:
            check_point(x_, y_, P, 'sweep key')
        move(*map(int, pts[0])); time.sleep(0.05); down()
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(1, int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** .5 / step))
            for j in range(1, n + 1):
                move(int(x0 + (x1 - x0) * j / n), int(y0 + (y1 - y0) * j / n)); time.sleep(dt)
        up()

    cand0 = (int(pr[0] + (pr[2] - pr[0]) * 0.07), int(Tp - 0.55 * s))

    guard(); n0 = len(samples)
    click(*map(int, centre['k']), P, 'pad key k'); time.sleep(0.8)
    got = entry_text()
    keep = all(h == T for _, h in samples[n0:])
    say('B1 single key k entry=%r' % got, 'PASS' if got == 'k' else 'FAIL', 'foreground stayed target during click', keep)
    results['B1_single_key'] = got == 'k'
    results['B1_focus_kept'] = keep

    for name, keys, expect in (('B2_char', 'yhyjmnbvc', 'yhmbc'), ('B3_word', 'yhmnbvcojhbnm', 'yhmbcojbm')):
        clear(); guard(); n0 = len(samples)
        sweep(list(keys)); time.sleep(1.5)
        capture(pr, 'win_%s_candidates.bmp' % name)  # pad rectangle only
        guard(); click(*cand0, P, 'candidate 1'); time.sleep(0.8)
        got = entry_text()
        keep = all(h == T for _, h in samples[n0:])
        say(name, 'path', keys, 'entry=%r' % got, 'expect=%r' % expect, 'PASS' if got == expect else 'FAIL', 'foreground stayed target', keep)
        results[name] = got == expect
        results[name + '_focus_kept'] = keep
except BaseException as e:
    import traceback
    say('EXIT', repr(e))
    say(traceback.format_exc())
finally:
    stop[0] = True
    for p in procs:
        try:
            p.kill()
        except Exception:
            pass
    try:
        u.SetCursorPos(*cursor0)
    except Exception:
        pass
    bad = [(t, h) for t, h in samples if samples and h != samples[0][1]]
    say('foreground samples', len(samples), 'distinct', sorted(set(h for _, h in samples)), 'first deviations', bad[:3])
    say('RESULTS', json.dumps(results))
