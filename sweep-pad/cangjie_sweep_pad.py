#!/usr/bin/env python3
"""Desktop Cangjie sweep pad. Python 3.8+, standard library only."""
import argparse
import ctypes
import ctypes.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
# Source checkout and extracted release both work; no writes to the decoder tree.
if not (HERE / 'sweep').is_dir():
    sys.path.insert(0, str(HERE.parent))
from sweep.keyboard import default_layout, key_sequence, to_key_units
from sweep.decoder import Lexicon, SweepConfig, SweepDecoder

DEFAULTS = dict(strictness=1.0, top_k=5, mode='keys', window_size='640x300',
                keysize=48.0, always_on_top=True)


def config_path():
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', str(Path.home() / 'AppData/Roaming')))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    return base / 'cangjie-sweep-pad/config.json'


def positive(value):
    n = float(value)
    if not math.isfinite(n) or n <= 0:
        raise argparse.ArgumentTypeError('must be a finite positive number')
    return n


def parse_args(argv=None):
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument('--config', type=Path, default=config_path())
    preliminary, _ = pre.parse_known_args(argv)
    defaults = dict(DEFAULTS)
    if preliminary.config.exists():
        with preliminary.config.open(encoding='utf-8') as f:
            values = json.load(f)
        if not isinstance(values, dict) or set(values) - set(DEFAULTS):
            raise ValueError('config must be an object containing only documented settings')
        defaults.update(values)
    ap = argparse.ArgumentParser(description=__doc__, parents=[pre])
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument('--decode-file', type=Path)
    modes.add_argument('--inject-test')
    modes.add_argument('--print-layout', action='store_true')
    modes.add_argument('--self-check', action='store_true')
    ap.add_argument('--strictness', type=positive, default=defaults['strictness'])
    ap.add_argument('--top-k', type=int, default=defaults['top_k'])
    ap.add_argument('--mode', choices=('keys', 'commit'), default=defaults['mode'])
    ap.add_argument('--window-size', default=defaults['window_size'])
    ap.add_argument('--keysize', type=positive, default=None,
                    help='GUI key width; with --decode-file, convert pixel coordinates by this width')
    ap.add_argument('--always-on-top', dest='always_on_top', action='store_true')
    ap.add_argument('--no-always-on-top', dest='always_on_top', action='store_false')
    ap.set_defaults(always_on_top=defaults['always_on_top'])
    ap.add_argument('--delay', type=float, default=3.0, help='seconds before --inject-test')
    ap.add_argument('--save-config', action='store_true')
    ap.add_argument('--table', type=Path, default=HERE / 'data/cangjie3.tsv')
    a = ap.parse_args(argv)
    a.pixel_input = a.keysize is not None
    a.keysize = a.keysize if a.keysize is not None else defaults['keysize']
    if (isinstance(a.top_k, bool) or not isinstance(a.top_k, int) or not 1 <= a.top_k <= 100
            or a.mode not in ('keys', 'commit') or not isinstance(a.always_on_top, bool)
            or not isinstance(a.window_size, str) or not re.fullmatch(r'[1-9]\d*x[1-9]\d*', a.window_size)):
        ap.error('invalid settings: top-k 1..100, mode keys/commit, window-size WIDTHxHEIGHT, topmost boolean')
    for name in ('strictness', 'keysize'):
        val = getattr(a, name)
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val <= 0:
            ap.error(name + ' must be a finite positive number')
    if not math.isfinite(a.delay) or a.delay < 0:
        ap.error('delay must be finite and nonnegative')
    return a


def save_config(a):
    a.config.parent.mkdir(parents=True, exist_ok=True)
    with a.config.open('w', encoding='utf-8') as f:
        json.dump({k: getattr(a, k) for k in DEFAULTS}, f, indent=2)
        f.write('\n')


def key_rects():
    return {k: (x - .5, y - .5, x + .5, y + .5)
            for k, (x, y) in default_layout().centers.items()}


def path_keys(points):
    """Hit-test actual drawn key rectangles, including their corners."""
    sequence = []
    for x, y, _ in points:
        for key, (left, top, right, bottom) in key_rects().items():
            if left <= x < right and top <= y < bottom:
                if not sequence or sequence[-1] != key:
                    sequence.append(key)
                break
    return sequence


def read_points(path, scale=1.0):
    with Path(path).open(encoding='utf-8') as f:
        pts = json.load(f)
    if not isinstance(pts, list) or not pts:
        raise ValueError('path must be a nonempty JSON list of [x,y,t_ms]')
    last = -float('inf')
    for p in pts:
        if (not isinstance(p, list) or len(p) != 3 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in p)):
            raise ValueError('each sample must contain three finite numbers')
        if p[2] < last:
            raise ValueError('timestamps must be nondecreasing')
        last = p[2]
    return to_key_units(pts, scale)


def make_decoder(a):
    cfg = SweepConfig(top_k=a.top_k, loc_weight=4 * a.strictness,
                      end_weight=4 * a.strictness, prune_radius=1.5 / math.sqrt(a.strictness))
    return SweepDecoder(Lexicon.from_tsv(str(a.table), min_len=1), cfg)


def injector():
    from injectors import windows, macos, linux
    return windows if sys.platform == 'win32' else macos if sys.platform == 'darwin' else linux


def wayland():
    return os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland' or bool(os.environ.get('WAYLAND_DISPLAY'))


class FocusPolicy:
    """Configure before mapping. X11 override redirect prevents WM click activation."""
    def __init__(self, root):
        self.root = root
        self.previous_pid = None
        if sys.platform == 'darwin':
            print('macOS Tk may take focus. Restoring the previous application before injection; Automation and Accessibility permissions may be needed.', file=sys.stderr)
            self.poll_mac()
        elif sys.platform != 'win32':
            if wayland():
                print('Wayland: the pad cannot guarantee non-activation; injection requires ydotool/uinput. Focus the target before --inject-test; GUI injection is disabled.', file=sys.stderr)
            else:
                root.wm_attributes('-type', 'dock')
                root.overrideredirect(True)

    def install(self):
        if sys.platform == 'win32':
            from ctypes import wintypes as w
            u = ctypes.WinDLL('user32', use_last_error=True)
            u.GetParent.argtypes = [w.HWND]; u.GetParent.restype = w.HWND
            hwnd = u.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            get = u.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else u.GetWindowLongW
            put = u.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else u.SetWindowLongW
            get.argtypes = [w.HWND, ctypes.c_int]; get.restype = ctypes.c_ssize_t
            put.argtypes = [w.HWND, ctypes.c_int, ctypes.c_ssize_t]; put.restype = ctypes.c_ssize_t
            ctypes.set_last_error(0)
            result = put(hwnd, -20, get(hwnd, -20) | 0x08000000 | 0x80)
            if not result and ctypes.get_last_error():
                raise ctypes.WinError(ctypes.get_last_error())
        elif sys.platform != 'darwin' and not wayland():
            # Tk focus model passive may still accept WM_TAKE_FOCUS; remove that protocol.
            self.root.tk.call('wm', 'protocol', self.root._w, 'WM_TAKE_FOCUS', '')
            lib = ctypes.CDLL(ctypes.util.find_library('X11') or 'libX11.so.6')
            class Hints(ctypes.Structure):
                _fields_ = [('flags', ctypes.c_long), ('input', ctypes.c_int), ('state', ctypes.c_int),
                            ('pixmap', ctypes.c_ulong), ('window', ctypes.c_ulong),
                            ('x', ctypes.c_int), ('y', ctypes.c_int), ('mask', ctypes.c_ulong), ('group', ctypes.c_ulong)]
            lib.XOpenDisplay.argtypes = [ctypes.c_char_p]; lib.XOpenDisplay.restype = ctypes.c_void_p
            lib.XSetWMHints.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Hints)]
            lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
            d = lib.XOpenDisplay(None)
            if not d:
                raise RuntimeError('Cannot open X11 display for non-activating window')
            try:
                hints = Hints(); hints.flags = 1; hints.input = 0
                lib.XSetWMHints(d, self.root.winfo_id(), ctypes.byref(hints))
            finally:
                lib.XCloseDisplay(d)

    def poll_mac(self):
        try:
            r = subprocess.run(['osascript', '-e', 'tell application "System Events" to get unix id of first application process whose frontmost is true'],
                               capture_output=True, text=True, timeout=2)
            if r.returncode == 0 and r.stdout.strip().isdigit():
                pid = int(r.stdout.strip())
                if pid != os.getpid():
                    self.previous_pid = pid
        except (OSError, subprocess.SubprocessError):
            pass
        self.root.after(700, self.poll_mac)

    def restore(self):
        if sys.platform == 'darwin':
            if self.previous_pid is None:
                raise RuntimeError('Previous app unknown. Allow Automation for System Events and focus the target app first.')
            subprocess.run(['osascript', '-e', 'tell application "System Events" to set frontmost of first application process whose unix id is %d to true' % self.previous_pid],
                           check=True, capture_output=True, timeout=3)
        elif wayland():
            raise RuntimeError('Wayland GUI injection disabled: target focus cannot be preserved. Use --inject-test after focusing the target.')


class Pad:
    def __init__(self, root, a):
        import tkinter as tk
        self.root, self.args = root, a
        self.decoder = make_decoder(a)
        self.points = []
        self.start = 0
        self.results = []
        root.withdraw()
        root.title('倉頡 Sweep Pad')
        root.geometry(a.window_size)
        root.attributes('-topmost', a.always_on_top)
        self.focus = FocusPolicy(root)
        bar = tk.Frame(root); bar.pack(fill='x')
        handle = tk.Label(bar, text='倉頡 Sweep Pad   ⋮ drag to move', cursor='fleur'); handle.pack(side='left')
        handle.bind('<ButtonPress-1>', lambda e: setattr(self, 'move', (e.x_root-root.winfo_x(), e.y_root-root.winfo_y())))
        handle.bind('<B1-Motion>', lambda e: root.geometry('+%d+%d' % (e.x_root-self.move[0], e.y_root-self.move[1])))
        tk.Button(bar, text='×', command=root.destroy, takefocus=False).pack(side='right')
        self.code = tk.StringVar(value='Drag across letter keys; release to rank, then choose a candidate.')
        # Read-only code box: editable widgets would require stealing target focus.
        box = tk.Entry(root, textvariable=self.code, state='disabled', takefocus=False)
        box.pack(fill='x')
        row = tk.Frame(root); row.pack(fill='x')
        self.buttons = []
        for i in range(5):
            b = tk.Button(row, text='—', state='disabled', takefocus=False, command=lambda j=i: self.choose(j))
            b.pack(side='left', expand=True, fill='x'); self.buttons.append(b)
        self.canvas = tk.Canvas(root, background='#17222c', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.rects = key_rects()
        self.canvas.bind('<Configure>', self.draw)
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.motion)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        root.update_idletasks()
        self.focus.install()
        root.deiconify()

    def draw(self, event=None):
        c = self.canvas; c.delete('all')
        self.scale = min(self.args.keysize, max(1, (c.winfo_width()-12)/10), max(1, (c.winfo_height()-12)/3))
        self.origin = (6 - 1.5*self.scale, 6 + .5*self.scale)
        for k, rect in self.rects.items():
            x1,y1,x2,y2 = rect
            ox,oy = self.origin; s = self.scale
            c.create_rectangle(ox+x1*s+1, oy+y1*s+1, ox+x2*s-1, oy+y2*s-1, fill='#304655', outline='#708999')
            c.create_text(ox+(x1+x2)*s/2, oy+(y1+y2)*s/2, text=k.upper(), fill='white')

    def sample(self, event):
        ox,oy = self.origin
        return ((event.x-ox)/self.scale, (event.y-oy)/self.scale, (time.monotonic()-self.start)*1000)

    def press(self, event):
        self.canvas.delete('trail'); self.start = time.monotonic()
        self.points = [self.sample(event)]
        self.results = []
        for b in self.buttons:
            b.configure(text='—', state='disabled')

    def motion(self, event):
        if not self.points:
            return
        p = self.sample(event); old = self.points[-1]; self.points.append(p)
        ox,oy = self.origin; s = self.scale
        self.canvas.create_line(ox+old[0]*s, oy+old[1]*s, ox+p[0]*s, oy+p[1]*s, fill='#ffcd59', width=3, tags='trail')

    def release(self, event):
        if not self.points:
            return
        self.motion(event)
        points, self.points = self.points, []
        seq = path_keys(points)
        if len(set(seq)) < 2:
            if seq:
                self.send(seq[0], seq[0], single=True)
            return
        self.results = self.decoder.decode(points, top_k=self.args.top_k)
        self.code.set('  |  '.join('%s %s' % (ch, code) for ch,code,_ in self.results))
        for b, result in zip(self.buttons, self.results):
            b.configure(text='%s %s' % result[:2], state='normal')

    def choose(self, index):
        ch,code,_ = self.results[index]
        self.send(code, ch)

    def send(self, code, char, single=False):
        try:
            self.focus.restore()
            def perform():
                try:
                    if self.args.mode == 'commit' and not single:
                        if sys.platform != 'win32':
                            raise RuntimeError('commit mode is supported only on Windows')
                        injector().inject_unicode(char)
                    else:
                        injector().inject_keys(code)
                    self.code.set('Sent: ' + code)
                except (OSError, RuntimeError, ValueError) as e:
                    self.code.set(str(e)); print(str(e), file=sys.stderr)
            self.root.after(150 if sys.platform == 'darwin' else 15, perform)
        except (OSError, RuntimeError, subprocess.SubprocessError) as e:
            self.code.set(str(e)); print(str(e), file=sys.stderr)


def main(argv=None):
    try:
        a = parse_args(argv)
        if a.save_config:
            save_config(a)
        if a.print_layout:
            print(json.dumps(key_rects(), sort_keys=True)); return 0
        if a.decode_file:
            pts = read_points(a.decode_file, a.keysize if a.pixel_input else 1)
            print(json.dumps([dict(char=ch, code=code, score=sc) for ch,code,sc in make_decoder(a).decode(pts)], ensure_ascii=False)); return 0
        if a.self_check:
            import tkinter
            ok, msg = injector().availability()
            table_ok = a.table.is_file()
            print(json.dumps(dict(platform=sys.platform, session=os.environ.get('XDG_SESSION_TYPE', ''),
                                  display=bool(os.environ.get('DISPLAY')), tkinter=tkinter.TkVersion,
                                  injector_available=ok, injector_message=msg, table_available=table_ok), ensure_ascii=False))
            if wayland():
                print('Wayland: requires ydotool/uinput; non-activating GUI is unavailable.', file=sys.stderr)
            if table_ok:
                make_decoder(a)
            return 0 if ok and table_ok else 1
        if a.inject_test is not None:
            if not re.fullmatch('[a-z]+', a.inject_test):
                raise ValueError('--inject-test accepts lowercase ASCII letters a-z only')
            print('Focus the target application; injecting in %g seconds.' % a.delay, file=sys.stderr)
            time.sleep(a.delay); injector().inject_keys(a.inject_test); return 0
        if a.mode == 'commit' and sys.platform != 'win32':
            raise ValueError('commit mode is supported only on Windows')
        import tkinter as tk
        try:
            root = tk.Tk(); Pad(root, a); root.mainloop(); return 0
        except tk.TclError as e:
            raise RuntimeError('Tk GUI unavailable: ' + str(e)) from e
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as e:
        print('Sweep Pad: ' + str(e), file=sys.stderr); return 1


if __name__ == '__main__':
    sys.exit(main())
