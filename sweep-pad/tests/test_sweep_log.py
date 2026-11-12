"""Tests for opt-in local sweep logging and log replay/tuning tools."""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

PAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAD))
if not (PAD / 'sweep').is_dir():
    sys.path.insert(0, str(PAD.parent))

import cangjie_sweep_pad as pad
import pad_words
from sweep.keyboard import default_layout
from sweep.make_vectors import polyline_path
try:
    from tools import replay_log
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location('replay_log', PAD / 'tools' / 'replay_log.py')
    replay_log = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay_log)


class SweepLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(PAD))
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.config = self.tmp_path / 'config.json'
        self.cache = self.tmp_path / 'cache'
        self.cache_patch = patch.object(pad_words, 'cache_dir', return_value=self.cache)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)

    def args(self, *values):
        return pad.parse_args(['--config', str(self.config)] + list(values))

    def test_log_line_format(self):
        points = [(2.0, 0.0, 0), (2.5, 0.5, 50), (3.0, 1.0, 100)]
        lifts = [1]
        results = [('顏', 'yhmbc', -1.2), ('頻', 'yhmbc', -1.5)]
        chosen = {'text': '顏', 'code': 'yhmbc'}

        entry = pad.make_sweep_entry(
            points, lifts, results, chosen=chosen,
            profile='mouse', mode='keys', keysize=48.0, t=1700000000.123
        )

        self.assertEqual(entry['v'], 1)
        self.assertEqual(entry['t'], 1700000000.123)
        self.assertEqual(entry['profile'], 'mouse')
        self.assertEqual(entry['mode'], 'keys')
        self.assertEqual(entry['layout']['keysize'], 48.0)
        self.assertIn('q', entry['layout']['centers'])
        self.assertEqual(len(entry['layout']['centers']['q']), 2)
        self.assertEqual(entry['points'], [[2.0, 0.0, 0], [2.5, 0.5, 50], [3.0, 1.0, 100]])
        self.assertEqual(entry['lifts'], [1])
        self.assertEqual(len(entry['top']), 2)
        self.assertEqual(entry['top'][0], {'text': '顏', 'code': 'yhmbc', 'score': -1.2})
        self.assertEqual(entry['chosen'], {'text': '顏', 'code': 'yhmbc'})

        # Check serialization and null chosen
        entry_null = pad.make_sweep_entry(points, lifts, results, chosen=None)
        self.assertIsNone(entry_null['chosen'])
        dumped = json.dumps(entry_null)
        self.assertIn('"chosen": null', dumped)
        restored = json.loads(dumped)
        self.assertIsNone(restored['chosen'])
        self.assertEqual(restored['v'], 1)

    def test_0600_file_permissions(self):
        log_file = self.tmp_path / 'sub' / 'sweeps.jsonl'
        entry = pad.make_sweep_entry(
            [(1.0, 1.0, 0)], [], [('甲', 'k', 0.0)], chosen={'text': '甲', 'code': 'k'}
        )

        pad.append_sweep_log(log_file, entry)
        self.assertTrue(log_file.is_file())

        if sys.platform != 'win32':
            mode = stat.S_IMODE(log_file.stat().st_mode)
            self.assertEqual(mode, 0o600, f"Expected 0600 file permissions, got {oct(mode)}")

        # Append another line; verify permissions stay 0600 and file has 2 lines
        pad.append_sweep_log(log_file, entry)
        lines = [line.strip() for line in log_file.read_text(encoding='utf-8').splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        if sys.platform != 'win32':
            mode = stat.S_IMODE(log_file.stat().st_mode)
            self.assertEqual(mode, 0o600)

    def test_chosen_candidate_recorded_on_replace_and_close(self):
        log_file = self.tmp_path / 'gui_test.jsonl'
        a = self.args('--log-sweeps', str(log_file))

        widget = pad.Pad.__new__(pad.Pad)
        widget.args = a
        widget.root = Mock()
        widget.canvas = Mock()
        widget.code = Mock()
        widget.buttons = [Mock() for _ in range(5)]
        widget.decoder = Mock()
        widget.decoder.decode.return_value = [('顏', 'yhmbc', -1.0), ('頻', 'yhmbc', -1.2)]
        widget.decoder.injection_code.return_value = 'yhmbc'
        widget.points, widget.lifts, widget.results = [], [], []
        widget.last_sweep = None
        widget.send = Mock()

        # Sweep 1 is ranked
        widget.rank([(2.0, 0.0, 0), (2.1, 0.0, 10)], [])
        self.assertFalse(log_file.exists(), "Log should not be written before candidate pick or next gesture")
        self.assertIsNotNone(widget.last_sweep)
        self.assertIsNone(widget.last_sweep['chosen'])

        # User chooses candidate 0 ('顏')
        widget.choose(0)
        self.assertEqual(widget.last_sweep['chosen'], {'text': '顏', 'code': 'yhmbc'})
        self.assertFalse(log_file.exists(), "Log write is deferred until next gesture or close")

        # Next sweep replaces the candidate -> Sweep 1 must be flushed with chosen candidate
        widget.decoder.decode.return_value = [('頻', 'yhmbc', -0.5)]
        widget.rank([(1.0, 1.0, 20), (1.1, 1.0, 30)], [])
        self.assertTrue(log_file.exists())
        lines = [json.loads(line) for line in log_file.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['chosen'], {'text': '顏', 'code': 'yhmbc'})
        self.assertEqual(lines[0]['top'][0]['text'], '顏')

        # User does not choose for sweep 2 and closes the pad -> Sweep 2 written with chosen=None
        widget.close()
        lines = [json.loads(line) for line in log_file.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(lines), 2)
        self.assertIsNone(lines[1]['chosen'])
        self.assertEqual(lines[1]['top'][0]['text'], '頻')

    def test_press_new_gesture_flushes_pending_sweep(self):
        log_file = self.tmp_path / 'press_test.jsonl'
        a = self.args('--log-sweeps', str(log_file))

        widget = pad.Pad.__new__(pad.Pad)
        widget.args = a
        widget.root = Mock()
        widget.canvas = Mock()
        widget.code = Mock()
        widget.buttons = [Mock() for _ in range(5)]
        widget.decoder = Mock()
        widget.decoder.decode.return_value = [('頻率', 'yhmbcyioj', 0.0)]
        widget.decoder.injection_code.return_value = 'yhmbcyioj'
        widget.points, widget.lifts, widget.results = [], [], []
        widget.finish_timer = None
        widget.released_at = None
        widget.last_sweep = None
        widget.origin, widget.scale, widget.start = (0, 0), 48.0, 0
        widget.send = Mock()

        # Rank sweep 1 and choose
        widget.rank([(2.0, 0.0, 0), (3.0, 0.0, 10)], [])
        widget.choose(0)
        self.assertFalse(log_file.exists())

        # User presses canvas for new sweep (not continuing)
        event = type('E', (), {'x': 20, 'y': 20})()
        widget.press(event)

        # Sweep 1 must be flushed
        self.assertTrue(log_file.exists())
        lines = [json.loads(line) for line in log_file.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['chosen'], {'text': '頻率', 'code': 'yhmbcyioj'})

    def test_replay_report_on_synthetic_log(self):
        a = self.args()
        decoder = pad_words.make_decoder(a)

        # Synthetic sweep 1: character 'yhmbc'
        pts1 = polyline_path('yhmbc', default_layout())
        res1 = decoder.decode(pts1, [])
        self.assertTrue(res1)
        e1 = pad.make_sweep_entry(pts1, [], res1, chosen={'text': res1[0][0], 'code': res1[0][1]})

        # Synthetic sweep 2: word 'yhmnbvc ojhbnm'
        pts2, lifts2 = pad.literal_gesture('yhmnbvc ojhbnm', 'continuous')
        res2 = decoder.decode(pts2, lifts2)
        self.assertTrue(res2)
        e2 = pad.make_sweep_entry(pts2, lifts2, res2, chosen={'text': res2[0][0], 'code': res2[0][1]})

        # Synthetic sweep 3: unchosen sweep
        e3 = pad.make_sweep_entry(pts1, [], res1, chosen=None)

        # Synthetic sweep 4: deliberate miss where chosen is rank > 1
        fake_chosen = {'text': res1[1][0], 'code': res1[1][1]} if len(res1) > 1 else {'text': '錯', 'code': 'x'}
        e4 = pad.make_sweep_entry(pts1, [], res1, chosen=fake_chosen)

        log_path = self.tmp_path / 'synthetic.jsonl'
        for entry in (e1, e2, e3, e4):
            pad.append_sweep_log(log_path, entry)

        report = replay_log.evaluate_log([log_path], decoder)

        self.assertEqual(report['total_sweeps'], 4)
        self.assertEqual(report['chosen_sweeps'], 3)
        self.assertEqual(report['top1_count'], 2)
        self.assertAlmostEqual(report['top1_rate'], 2 / 3, places=3)
        self.assertGreaterEqual(report['top3_rate'], report['top1_rate'])
        self.assertGreaterEqual(report['top5_rate'], report['top3_rate'])

        # Check breakdown by type
        by_type = report['breakdown']['by_type']
        self.assertIn('char', by_type)
        self.assertIn('word', by_type)
        self.assertEqual(by_type['word']['n'], 1)
        self.assertEqual(by_type['word']['top1_rate'], 1.0)
        self.assertEqual(by_type['char']['n'], 2)

        # Check breakdown by path length
        by_length = report['breakdown']['by_length']
        self.assertIn('<5', by_length)
        self.assertIn('5-10', by_length)
        self.assertIn('10-15', by_length)
        self.assertIn('>=15', by_length)

        # Check misses
        self.assertEqual(len(report['worst_misses']), 1)
        self.assertEqual(report['worst_misses'][0]['text'], fake_chosen['text'])
        self.assertIn('points_count', report['worst_misses'][0])
        self.assertIn('rank', report['worst_misses'][0])

        # Test CLI text output
        stdout_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            ret = replay_log.main([str(log_path), '--table', str(a.table), '--essay', str(a.essay)])
        self.assertEqual(ret, 0)
        text_out = stdout_buf.getvalue()
        self.assertIn('Replay Report', text_out)
        self.assertIn('Top-1 accuracy', text_out)
        self.assertIn('Breakdown by type:', text_out)
        self.assertIn('Breakdown by path length', text_out)
        self.assertIn('Worst misses', text_out)

        # Test CLI JSON output
        json_buf = io.StringIO()
        with contextlib.redirect_stdout(json_buf):
            ret_json = replay_log.main([str(log_path), '--json', '--table', str(a.table), '--essay', str(a.essay)])
        self.assertEqual(ret_json, 0)
        parsed = json.loads(json_buf.getvalue())
        self.assertEqual(parsed['total_sweeps'], 4)
        self.assertEqual(parsed['chosen_sweeps'], 3)
        self.assertIn('breakdown', parsed)

    def test_tune_refusal_below_50_sweeps(self):
        log_path = self.tmp_path / 'small.jsonl'
        entry = pad.make_sweep_entry(
            [(1.0, 1.0, 0), (2.0, 2.0, 50)], [], [('甲', 'k', 0.0)],
            chosen={'text': '甲', 'code': 'k'}
        )
        # Write only 3 sweeps (< 50)
        for _ in range(3):
            pad.append_sweep_log(log_path, entry)

        # Refusal in text mode
        stderr_buf = io.StringIO()
        with contextlib.redirect_stderr(stderr_buf):
            ret = replay_log.main([str(log_path), '--tune'])
        self.assertEqual(ret, 1)
        err_msg = stderr_buf.getvalue()
        self.assertIn('50 sweeps', err_msg)
        self.assertIn('found 3', err_msg)

        # Refusal in JSON mode
        stdout_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf):
            ret_json = replay_log.main([str(log_path), '--tune', '--json'])
        self.assertEqual(ret_json, 1)
        parsed = json.loads(stdout_buf.getvalue())
        self.assertIn('error', parsed)
        self.assertIn('50 sweeps', parsed['error'])

    def test_cli_and_config_log_sweeps(self):
        log_dest = self.tmp_path / 'custom.jsonl'
        a = self.args('--log-sweeps', str(log_dest))
        self.assertEqual(a.log_sweeps, log_dest)

        # Test config setting
        self.config.write_text(json.dumps({'log_sweeps': str(log_dest)}))
        a_cfg = self.args()
        self.assertEqual(a_cfg.log_sweeps, log_dest)

        # Test save_config roundtrip
        pad.save_config(a)
        saved = json.loads(self.config.read_text())
        self.assertEqual(saved['log_sweeps'], str(log_dest))

        # Test invalid config type
        self.config.write_text(json.dumps({'log_sweeps': True}))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises((ValueError, SystemExit)):
            self.args()


if __name__ == '__main__':
    unittest.main()
