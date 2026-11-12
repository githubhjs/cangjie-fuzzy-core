"""Regression tests for the pad's word integration; no desktop or injection."""
import contextlib
import builtins
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

PAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAD))
spec = importlib.util.spec_from_file_location('word_test_pad', PAD / 'cangjie_sweep_pad.py')
pad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pad)
import pad_words

OWNER = [('顏值', 'yhmnbvc ojhbnm', 'yhmbcojbm'),
         ('頻率', 'yhjmnbvc yuiokjhj', 'yhmbcyioj')]


class WordPadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(PAD))
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.config = self.directory / 'config.json'
        self.cache = self.directory / 'cache'
        self.cache_patch = patch.object(pad_words, 'cache_dir', return_value=self.cache)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)

    def args(self, *values):
        return pad.parse_args(['--config', str(self.config)] + list(values))

    def test_owner_cases_through_pad_decoder_all_boundaries(self):
        decoder = pad.make_decoder(self.args())
        for expected, sequence, code in OWNER:
            for boundary in ('continuous', 'lift', 'dwell'):
                with self.subTest(expected=expected, boundary=boundary):
                    points, lifts = pad.literal_gesture(sequence, boundary)
                    result = decoder.decode(points, lifts)
                    self.assertEqual(result[0][:2], (expected, code))
                    self.assertEqual(len(result), 5)

    def test_single_character_owner_slip_decodes_yhmbc_first_through_the_pad_path(self):
        # y h y j m n b v c is the slip over ONE character (顏 / 頻, code yhmbc); the one-list decoder alone ranks ytmbc first
        decoder = pad.make_decoder(self.args())
        for sequence in ('yhyjmnbvc', 'yhjmnbvc', 'yhmnbvc', 'yhmbc'):  # not yhyhmbc: with 243k words it matches a spurious word (SPEC 12)
            with self.subTest(sequence=sequence):
                points, lifts = pad.literal_gesture(sequence, 'continuous')
                result = decoder.decode(points, lifts)
                self.assertEqual(result[0][1], 'yhmbc')
                self.assertIn(result[0][0], ('頻', '顏'))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(pad.main(['--config', str(self.config), '--decode-string', 'yhyjmnbvc', '--expect-code', 'yhmbc']), 0)
            self.assertEqual(pad.main(['--config', str(self.config), '--decode-string', 'yhyjmnbvc', '--expect-code', 'ytmbc']), 1)
        points, lifts = pad.literal_gesture('yhyjmnbvc', 'continuous')
        path = self.directory / 'slip.json'
        path.write_text(json.dumps(dict(points=points, lifts=lifts)))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pad.main(['--config', str(self.config), '--decode-file', str(path), '--expect-code', 'yhmbc']), 0)

    def test_windows_literal_fallback_matches_report_sampler(self):
        original_import = builtins.__import__

        def without_resource(name, *args, **kwargs):
            if name == 'sweep.report_words':
                raise ModuleNotFoundError("No module named 'resource'", name='resource')
            return original_import(name, *args, **kwargs)

        for expected, sequence, code in OWNER:
            for boundary in ('continuous', 'lift', 'dwell'):
                with self.subTest(sequence=sequence, boundary=boundary):
                    reference = pad.literal_gesture(sequence, boundary)
                    with patch.object(builtins, '__import__', side_effect=without_resource):
                        fallback = pad.literal_gesture(sequence, boundary)
                    self.assertEqual(fallback, reference)

    def test_word_injection_joins_main_codes_with_configurable_separator(self):
        decoder = pad.make_decoder(self.args())
        self.assertEqual(decoder.injection_code('顏值'), 'yhmbcojbm')
        self.assertEqual(decoder.injection_code('頻率', "'"), "yhmbc'yioj")
        widget = self.widget()
        widget.decoder = decoder
        widget.results = [('顏值', 'yhmbcojbm', 0)]
        widget.args.word_separator = ' '
        widget.choose(0)
        widget.send.assert_called_once_with('yhmbc ojbm', '顏值')

    def test_json_cache_restores_built_templates_without_rebuilding(self):
        args = self.args()
        cold = pad.make_decoder(args)
        files = list(self.cache.glob('*.json'))
        self.assertEqual(len(files), 1)
        self.assertIn('templates', json.loads(files[0].read_text()))
        points, lifts = pad.literal_gesture(OWNER[0][1], 'lift')
        with patch.object(pad_words.WordLexicon, '__init__', side_effect=AssertionError('rebuilt')):
            warm = pad.make_decoder(args)
        self.assertEqual(warm.decode(points, lifts), cold.decode(points, lifts))

    def test_cache_invalidates_when_either_data_file_changes(self):
        table = self.directory / 'table.tsv'
        essay = self.directory / 'essay.txt'
        table.write_text('ab\t明\t1\nbk\t甲\t1\n', encoding='utf-8')
        essay.write_text('明甲\t100\n', encoding='utf-8')
        args = self.args('--table', str(table), '--essay', str(essay))
        self.assertEqual(pad.make_decoder(args).lex.n_words, 1)
        essay.write_text('明甲\t99\n', encoding='utf-8')
        self.assertEqual(pad.make_decoder(args).lex.n_words, 0)
        table.write_text('ab\t明\t1\nbk\t甲\t1\nkb\t乙\t1\n', encoding='utf-8')
        self.assertIn('乙', pad.make_decoder(args).codes)
        self.assertEqual(len(list(self.cache.glob('*.json'))), 3)

    def test_corrupt_cache_is_rebuilt(self):
        args = self.args()
        pad.make_decoder(args)
        target = next(self.cache.glob('*.json'))
        target.write_text('{broken', encoding='utf-8')
        self.assertGreater(pad.make_decoder(args).lex.n_words, 0)
        self.assertEqual(json.loads(target.read_text())['version'], 1)

    def test_unwritable_cache_does_not_prevent_decode(self):
        self.cache.write_text('a file blocks mkdir', encoding='utf-8')
        result = pad.make_decoder(self.args())
        points, lifts = pad.literal_gesture(OWNER[0][1], 'continuous')
        self.assertEqual(result.decode(points, lifts)[0][0], '顏值')

    def test_loading_runs_off_caller_thread_and_publishes_result(self):
        entered, release = threading.Event(), threading.Event()
        token = object()
        caller = threading.get_ident()
        worker_ids = []

        def build(args):
            worker_ids.append(threading.get_ident())
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test timed out')
            return token

        loader = pad_words.DecoderLoader(self.args(), factory=build)
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(2))
        self.assertIsNone(loader.poll())
        self.assertNotEqual(worker_ids, [caller])
        release.set()
        loader.thread.join(3)
        self.assertFalse(loader.thread.is_alive())
        self.assertEqual(loader.poll(), (token, None))
        self.assertIsNone(loader.poll())

    def test_loading_error_is_returned_to_ui(self):
        def fail(args):
            raise ValueError('bad table')
        loader = pad_words.DecoderLoader(self.args(), factory=fail)
        loader.thread.join(3)
        self.assertEqual(loader.poll(), (None, 'bad table'))

    def widget(self):
        widget = pad.Pad.__new__(pad.Pad)
        widget.args = self.args()
        widget.root = Mock()
        widget.root.after.return_value = 'timer'
        widget.canvas = Mock()
        widget.code = Mock()
        widget.buttons = [Mock() for _ in range(5)]
        widget.decoder = Mock()
        widget.decoder.decode.return_value = [('顏值', 'yhmbcojbm', -1)]
        widget.points, widget.lifts, widget.results = [], [], []
        widget.finish_timer = widget.released_at = widget.pending = None
        widget.origin, widget.scale, widget.start = (0, 0), 1, 0
        widget.send = Mock()
        return widget

    def event(self, key):
        x, y = pad.default_layout().centers[key]
        return SimpleNamespace(x=x, y=y)

    def test_quick_repress_adds_lift_and_keeps_original_timestamp_origin(self):
        widget = self.widget()
        with patch.object(pad.time, 'monotonic', return_value=1):
            widget.press(self.event('y'))
        with patch.object(pad.time, 'monotonic', return_value=1.1):
            widget.release(self.event('c'))
        end_index = len(widget.points) - 1
        with patch.object(pad.time, 'monotonic', return_value=1.349):
            widget.press(self.event('o'))
        self.assertEqual(widget.lifts, [end_index])
        self.assertAlmostEqual(widget.points[-1][2], 349)
        widget.root.after_cancel.assert_called_once_with('timer')
        with patch.object(pad.time, 'monotonic', return_value=1.5):
            widget.release(self.event('m'))
        expected = list(widget.points)
        widget.finish()
        widget.decoder.decode.assert_called_once_with(expected, [end_index], top_k=5)
        widget.buttons[0].configure.assert_called_with(text='顏值\nyhmbcojbm', state='normal')

    def test_late_repress_finishes_old_gesture_and_starts_new(self):
        widget = self.widget()
        with patch.object(pad.time, 'monotonic', return_value=1):
            widget.press(self.event('y'))
        with patch.object(pad.time, 'monotonic', return_value=1.1):
            widget.release(self.event('c'))
        old = list(widget.points)
        with patch.object(pad.time, 'monotonic', return_value=1.351):
            widget.press(self.event('o'))
        widget.decoder.decode.assert_called_once_with(old, [], top_k=5)
        self.assertEqual(widget.lifts, [])
        self.assertEqual(widget.points, [(*pad.default_layout().centers['o'], 0)])

    def test_sweep_waits_for_loading_then_decodes_with_lifts(self):
        widget = self.widget()
        decoder = widget.decoder
        widget.decoder = None
        widget.points = [(1, 2, 0), (2, 2, 100)]
        widget.lifts = [0]
        widget.finish()
        self.assertEqual(widget.pending, ([(1, 2, 0), (2, 2, 100)], [0]))
        decoder.decode.assert_not_called()
        widget.loader = Mock()
        widget.loader.poll.return_value = (decoder, None)
        widget.poll_loader()
        decoder.decode.assert_called_once_with([(1, 2, 0), (2, 2, 100)], [0], top_k=5)
        self.assertIsNone(widget.pending)

    def test_loading_failure_clears_queue_and_stays_visible_after_future_sweep(self):
        widget = self.widget()
        decoder = widget.decoder
        widget.decoder = None
        widget.pending = ([(1, 2, 0), (2, 2, 100)], [0])
        widget.loader = Mock()
        widget.loader.poll.return_value = (None, 'bad table')
        widget.poll_loader()
        self.assertEqual(widget.loading_error, 'bad table')
        self.assertIsNone(widget.pending)
        widget.code.set.assert_called_with('Loading failed: bad table')
        widget.points = [(2, 3, 0), (3, 3, 120)]
        widget.lifts = [0]
        widget.finish()
        self.assertIsNone(widget.pending)
        self.assertEqual(widget.points, [])
        self.assertEqual(widget.lifts, [])
        widget.code.set.assert_called_with('Loading failed: bad table')
        decoder.decode.assert_not_called()
        widget.root.after.assert_not_called()

    def test_single_key_click_still_sends_letter_while_loading(self):
        widget = self.widget()
        widget.decoder = None
        with patch.object(pad.time, 'monotonic', return_value=1):
            widget.press(self.event('a'))
        with patch.object(pad.time, 'monotonic', return_value=1.05):
            widget.release(self.event('a'))
        widget.send.assert_called_once_with('a', 'a', single=True)
        self.assertEqual(widget.points, [])
        widget.root.after.assert_not_called()

    def test_object_input_preserves_lifts_and_scales_only_coordinates(self):
        path = self.directory / 'path.json'
        path.write_text(json.dumps({'points': [[96, 0, 3], [108, 48, 20]], 'lifts': [0]}))
        self.assertEqual(pad.read_gesture(path, 48), ([(2, 0, 3), (2.25, 1, 20)], [0]))
        for lifts in ([True], [-1], [1], '0', [0.0]):
            with self.subTest(lifts=lifts):
                path.write_text(json.dumps({'points': [[1, 2, 0], [2, 2, 1]], 'lifts': lifts}))
                with self.assertRaises(ValueError):
                    pad.read_gesture(path)

    def test_cli_expect_checks_top_one_for_string_and_file(self):
        for target, sequence, code in OWNER:
            for expect, status in ((target, 0), ('錯', 1)):
                with self.subTest(target=target, expect=expect):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        result = pad.main(['--config', str(self.config), '--decode-string', sequence,
                                           '--boundary', 'lift', '--expect', expect, '--top-k', '2'])
                    self.assertEqual(result, status)
                    ranked = json.loads(output.getvalue())
                    self.assertEqual(len(ranked), 2)
                    self.assertEqual((ranked[0]['char'], ranked[0]['code']), (target, code))
        points, lifts = pad.literal_gesture(OWNER[0][1], 'lift')
        path = self.directory / 'gesture.json'
        path.write_text(json.dumps(dict(points=points, lifts=lifts)))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pad.main(['--config', str(self.config), '--decode-file', str(path),
                                       '--expect', '顏值']), 0)


if __name__ == '__main__':
    unittest.main()
