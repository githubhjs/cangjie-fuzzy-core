import importlib.util
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAD))
spec = importlib.util.spec_from_file_location('pad', PAD / 'cangjie_sweep_pad.py')
pad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pad)


class PadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(PAD))
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name) / 'config.json'
        cache = patch('pad_words.cache_dir', return_value=Path(self.tmp.name) / 'cache')
        cache.start()
        self.addCleanup(cache.stop)

    def args(self, *args):
        return pad.parse_args(['--config', str(self.config)] + list(args))

    def test_geometry_and_rect_centres(self):
        rects = pad.key_rects()
        self.assertEqual(len(rects), 26)
        self.assertEqual(rects['q'], (1.5, -.5, 2.5, .5))
        self.assertEqual(rects['a'], (1.75, .5, 2.75, 1.5))
        for key, (x1, y1, x2, y2) in rects.items():
            self.assertEqual(((x1+x2)/2, (y1+y2)/2), pad.default_layout().centers[key])

    def test_path_mapping(self):
        points = [(*pad.default_layout().centers[k], i*10) for i,k in enumerate('yhyjmnbvc')]
        self.assertEqual(''.join(pad.key_sequence(pad.default_layout(), points)), 'yhyjmnbvc')

    def test_key_corners_and_outside(self):
        self.assertEqual(pad.path_keys([(2.45, .45, 0)]), ['q'])
        self.assertEqual(pad.path_keys([(0, 0, 0), (20, 20, 10)]), [])
        self.assertEqual(pad.path_keys([(2, 0, 0), (2.45, .45, 10)]), ['q'])

    def test_settings_precedence_and_roundtrip(self):
        self.config.write_text(json.dumps(dict(strictness=2, top_k=9, keysize=60, always_on_top=False)))
        a = self.args('--top-k', '3')
        self.assertEqual((a.strictness, a.top_k, a.keysize, a.always_on_top), (2,3,60,False))
        self.assertFalse(a.pixel_input)
        pad.save_config(a)
        self.assertEqual(self.args().top_k, 3)

    def test_invalid_config(self):
        for val in ({'unknown': 1}, [], {'keysize': -2}, {'always_on_top': 'false'}, {'top_k': True}, {'mode': 'oops'}):
            self.config.write_text(json.dumps(val))
            with self.subTest(val=val), contextlib.redirect_stderr(io.StringIO()), self.assertRaises((ValueError, SystemExit)):
                self.args()

    def test_cli_validation(self):
        for args in [('--keysize', 'nan'), ('--top-k', '0'), ('--delay', '-1'), ('--window-size', '0x0')]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.args(*args)

    def test_pixel_and_unit_points(self):
        path = Path(self.tmp.name) / 'path.json'
        path.write_text('[[96,0,0],[108,48,20]]')
        self.assertEqual(pad.read_points(path, 48), [(2,0,0),(2.25,1,20)])
        self.assertEqual(pad.read_points(path)[0], (96,0,0))
        self.assertTrue(self.args('--keysize', '48').pixel_input)

    def test_reject_bad_paths(self):
        path = Path(self.tmp.name) / 'path.json'
        for data in ('[]', '{}', '[[1,2]]', '[[1,2,3],[1,2,0]]', '[[true,2,3]]', '[[NaN,2,3]]'):
            path.write_text(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                pad.read_points(path)

    def test_demo_decode_exact(self):
        a = self.args()
        d = pad.make_decoder(a)
        pts = [(*pad.default_layout().centers[k], i*80) for i,k in enumerate('yhmbc')]
        results = d.decode(pts)
        self.assertIn(('顏', 'yhmbc'), [r[:2] for r in results])
        self.assertIn(results[0][0], ('顏', '頻'))  # same code; no word context

    def test_headless_cli(self):
        r = subprocess.run([sys.executable, str(PAD/'cangjie_sweep_pad.py'), '--config', str(self.config), '--print-layout'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(json.loads(r.stdout)), 26)

    def test_inject_test_no_actual_injection(self):
        from unittest.mock import Mock
        inj = Mock()
        with patch.object(pad, 'injector', return_value=inj), patch.object(pad.time, 'sleep') as sleep:
            self.assertEqual(pad.main(['--config', str(self.config), '--inject-test', 'abc', '--delay', '0']), 0)
            inj.inject_keys.assert_called_once_with('abc')
            sleep.assert_called_once_with(0)


class VectorTests(unittest.TestCase):
    def test_sweep_vectors(self):
        source = PAD.parent/'sweep/vectors/vectors.json'
        if not source.exists():
            source = PAD/'sweep/vectors/vectors.json'
        if not source.exists():
            self.skipTest('upstream sweep/vectors/vectors.json not present yet')
        vectors = json.loads(source.read_text(encoding='utf-8'))
        cfg = pad.SweepConfig(**vectors['config'])
        lex = pad.Lexicon(vectors['lexicon'], n=cfg.n)
        decoder = pad.SweepDecoder(lex,cfg)
        for case in vectors['cases']:
            with self.subTest(case=case['id']):
                result = decoder.decode(case['points'], top_k=5)
                self.assertEqual([r[0] for r in result], case['expected'])
                for actual,expected in zip(result,case['expected_scores']):
                    self.assertAlmostEqual(actual[2], expected, places=5)


@unittest.skipUnless(sys.platform.startswith('linux') and pad.os.environ.get('DISPLAY') and not pad.wayland(),
                     'needs an X11 display (for example Xvfb)')
class PadLayoutTests(unittest.TestCase):
    """Real Tk widgets: the keyboard must not move when candidates appear or clear."""

    def test_keyboard_does_not_move_and_trail_survives(self):
        import tkinter as tk

        class Loader:
            def __init__(self, a): pass
            def poll(self): return None

        class Decoder:
            def decode(self, points, lifts, top_k=5):
                return [('顏值', 'yhmbcojbm', 0.0)] * 5

        with tempfile.TemporaryDirectory() as tmp, patch.object(pad, 'DecoderLoader', Loader):
            a = pad.parse_args(['--config', str(Path(tmp) / 'none.json')])
            root = tk.Tk()
            self.addCleanup(root.destroy)
            p = pad.Pad(root, a)
            root.update()
            before = (p.canvas.winfo_rooty(), p.canvas.winfo_height())
            p.canvas.create_line(10, 10, 50, 50, tags='trail')
            p.decoder = Decoder()
            p.rank([], [])
            root.update()
            self.assertEqual((p.canvas.winfo_rooty(), p.canvas.winfo_height()), before)
            self.assertTrue(p.canvas.find_withtag('trail'), 'candidate display redrew the keyboard and erased the trail')
            p.press(type('E', (), {'x': 20, 'y': 20})())
            root.update()
            self.assertEqual((p.canvas.winfo_rooty(), p.canvas.winfo_height()), before)


if __name__ == '__main__':
    unittest.main()
