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
from pad_words import make_decoder, DecoderLoader

DEFAULTS = dict(strictness=1.0, top_k=5, mode='keys', window_size='640x300',
                keysize=48.0, always_on_top=True, profile='mouse',
                word_separator='', lift_ms=250.0)
# Two lines like a filled candidate ('字\ncode'): a constant button height keeps the
# keyboard canvas from moving or redrawing (and losing the trail) between gestures.
EMPTY_CANDIDATE = '—\n '


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
    modes.add_argument('--decode-string')
    ap.add_argument('--boundary', choices=('continuous', 'lift', 'dwell'), default='continuous')
    ap.add_argument('--expect')
    ap.add_argument('--expect-code', help='with --decode-string/--decode-file: the top candidate must have this main code')
    ap.add_argument('--profile', choices=('mouse', 'touchpad', 'touchscreen'), default=defaults['profile'])
    ap.add_argument('--word-separator', default=defaults['word_separator'])
    ap.add_argument('--lift-ms', type=positive, default=defaults['lift_ms'])
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
    ap.add_argument('--essay', type=Path, default=HERE / 'data/essay.txt')
    a = ap.parse_args(argv)
    a.pixel_input = a.keysize is not None
    a.keysize = a.keysize if a.keysize is not None else defaults['keysize']
    if (isinstance(a.top_k, bool) or not isinstance(a.top_k, int) or not 1 <= a.top_k <= 100
            or a.mode not in ('keys', 'commit') or not isinstance(a.always_on_top, bool)
            or not isinstance(a.window_size, str) or not re.fullmatch(r'[1-9]\d*x[1-9]\d*', a.window_size)):
        ap.error('invalid settings: top-k 1..100, mode keys/commit, window-size WIDTHxHEIGHT, topmost boolean')
    if a.profile not in ('mouse', 'touchpad', 'touchscreen') or a.word_separator not in ('', ' ', "'"):
        ap.error('profile must be mouse/touchpad/touchscreen; separator must be empty, space, or apostrophe')
    if (a.expect is not None or a.expect_code is not None) and not (a.decode_file or a.decode_string):
        ap.error('--expect and --expect-code require --decode-file or --decode-string')
    for name in ('strictness', 'keysize', 'lift_ms'):
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


def read_gesture(path, scale=1.0):
    with Path(path).open(encoding='utf-8') as f:
        data = json.load(f)
    lifts = []
    if isinstance(data, dict):
        if set(data) - {'points', 'lifts'}:
            raise ValueError('unknown gesture fields')
        pts, lifts = data.get('points'), data.get('lifts', [])
    else:
        pts = data
    if not isinstance(pts, list) or not pts:
        raise ValueError('path must contain a nonempty list of [x,y,t_ms]')
    last = -float('inf')
    for p in pts:
        if (not isinstance(p, list) or len(p) != 3 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in p)):
            raise ValueError('each sample must contain three finite numbers')
        if p[2] < last:
            raise ValueError('timestamps must be nondecreasing')
        last = p[2]
    if (not isinstance(lifts, list) or any(type(i) is not int or not 0 <= i < len(pts)-1 for i in lifts)):
        raise ValueError('lifts must be indices between consecutive points')
    return to_key_units(pts, scale), sorted(set(lifts))


def read_points(path, scale=1.0):
    return read_gesture(path, scale)[0]


def literal_gesture(sequence, boundary):
    if re.fullmatch(r'[a-z]+', sequence):
        # one key sequence = one character sweep (for example the slip y h y j m n b v c -> yhyjmnbvc); boundary does not apply
        from sweep.make_vectors import polyline_path
        return polyline_path(sequence, default_layout()), []
    if not re.fullmatch(r'[a-z]+ [a-z]+', sequence):
        raise ValueError('--decode-string requires one lowercase key sequence (a character) or two separated by one space (a word)')
    # report_words imports resource for report metrics (absent on Windows).
    # Import only when this headless diagnostic is requested.
    try:
        from sweep.report_words import literal
    except ModuleNotFoundError as error:
        if error.name != 'resource':
            raise
        # Windows lacks report_words' Unix-only reporting dependency. Keep the
        # same literal sampling contract there without importing report metrics.
        from sweep.make_vectors import polyline_path
        a, b = sequence.split(' ')
        layout = default_layout()
        pa, pb = polyline_path(a, layout), polyline_path(b, layout)
        if boundary == 'lift':
            return pa + [(x, y, t + pa[-1][2] + 250) for x, y, t in pb], [len(pa)-1]
        points = polyline_path(a + b, layout)
        if boundary == 'dwell':
            cut = len(pa)-1
            x, y, t = points[cut]
            points = (points[:cut+1] + [(x, y, t+10*i) for i in range(1, 36)]
                      + [(x, y, t+350) for x, y, t in points[cut+1:]])
        return points, []
    return literal(sequence, boundary)


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
        self.decoder = None
        self.loading_error = None
        self.loader = DecoderLoader(a)
        self.pending = None
        self.lifts = []
        self.finish_timer = None
        self.released_at = None
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
        self.code = tk.StringVar(value='Loading word lexicon… / 載入詞庫中…')
        # Read-only code box: editable widgets would require stealing target focus.
        box = tk.Entry(root, textvariable=self.code, state='disabled', takefocus=False)
        box.pack(fill='x')
        row = tk.Frame(root); row.pack(fill='x')
        self.buttons = []
        for i in range(5):
            b = tk.Button(row, text=EMPTY_CANDIDATE, state='disabled', takefocus=False, command=lambda j=i: self.choose(j))
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
        root.after(30, self.poll_loader)

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

    def poll_loader(self):
        result = self.loader.poll()
        if result is None:
            self.root.after(30, self.poll_loader)
            return
        self.decoder, error = result
        if error:
            self.loading_error = error
            self.pending = None
            self.code.set('Loading failed: ' + error)
            return
        self.code.set('Ready / 就緒 — ' + self.args.profile)
        if self.pending is not None:
            points, lifts = self.pending
            self.pending = None
            self.rank(points, lifts)

    def press(self, event):
        now = time.monotonic()
        continuing = (self.finish_timer is not None and self.released_at is not None
                      and (now - self.released_at) * 1000 < self.args.lift_ms)
        if self.finish_timer is not None:
            self.root.after_cancel(self.finish_timer)
            self.finish_timer = None
            if not continuing:
                self.finish()
        if continuing:
            self.lifts.append(len(self.points) - 1)
            self.points.append(self.sample(event))
        else:
            self.canvas.delete('trail'); self.start = now
            self.points = [self.sample(event)]
            self.lifts = []
            self.pending = None
        self.released_at = None
        self.results = []
        for b in self.buttons:
            b.configure(text=EMPTY_CANDIDATE, state='disabled')

    def motion(self, event):
        if not self.points or self.released_at is not None:
            return
        p = self.sample(event); old = self.points[-1]; self.points.append(p)
        ox,oy = self.origin; s = self.scale
        self.canvas.create_line(ox+old[0]*s, oy+old[1]*s, ox+p[0]*s, oy+p[1]*s, fill='#ffcd59', width=3, tags='trail')

    def release(self, event):
        if not self.points or self.released_at is not None:
            return
        self.motion(event)
        seq = path_keys(self.points)
        if not self.lifts and len(set(seq)) < 2:
            self.points = []
            if seq:
                self.send(seq[0], seq[0], single=True)
            return
        self.released_at = time.monotonic()
        self.finish_timer = self.root.after(math.ceil(self.args.lift_ms), self.finish)

    def finish(self):
        self.finish_timer = None
        points, lifts = self.points, self.lifts
        self.points, self.lifts = [], []
        self.released_at = None
        if not points:
            return
        if self.decoder is None:
            if getattr(self, 'loading_error', None):
                self.code.set('Loading failed: ' + self.loading_error)
                return
            self.pending = (points, lifts)
            self.code.set('Loading word lexicon… sweep queued / 手勢已暫存')
            return
        self.rank(points, lifts)

    def rank(self, points, lifts):
        self.results = self.decoder.decode(points, lifts, top_k=self.args.top_k)
        self.code.set('  |  '.join('%s %s' % (ch, code) for ch,code,_ in self.results))
        for b in self.buttons:
            b.configure(text=EMPTY_CANDIDATE, state='disabled')
        for b, (text, code, score) in zip(self.buttons, self.results):
            b.configure(text=text + '\n' + code, state='normal')

    def choose(self, index):
        ch,code,_ = self.results[index]
        self.send(self.decoder.injection_code(ch, self.args.word_separator), ch)

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
        if a.decode_file or a.decode_string:
            if a.decode_file:
                pts, lifts = read_gesture(a.decode_file, a.keysize if a.pixel_input else 1)
            else:
                pts, lifts = literal_gesture(a.decode_string, a.boundary)
            results = make_decoder(a).decode(pts, lifts)
            print(json.dumps([dict(char=ch, code=code, score=sc) for ch,code,sc in results], ensure_ascii=False))
            ok = results and (a.expect is None or results[0][0] == a.expect) and (a.expect_code is None or results[0][1] == a.expect_code)
            return 0 if (a.expect is None and a.expect_code is None) or ok else 1
        if a.self_check:
            import tkinter
            ok, msg = injector().availability()
            table_ok = a.table.is_file()
            essay_ok = a.essay.is_file()
            print(json.dumps(dict(platform=sys.platform, session=os.environ.get('XDG_SESSION_TYPE', ''),
                                  display=bool(os.environ.get('DISPLAY')), tkinter=tkinter.TkVersion,
                                  injector_available=ok, injector_message=msg, table_available=table_ok, essay_available=essay_ok), ensure_ascii=False))
            if wayland():
                print('Wayland: requires ydotool/uinput; non-activating GUI is unavailable.', file=sys.stderr)
            if table_ok and essay_ok:
                make_decoder(a)
            return 0 if ok and table_ok and essay_ok else 1
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
