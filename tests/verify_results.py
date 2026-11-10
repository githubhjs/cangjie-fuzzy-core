#!/usr/bin/env python3
"""Check saved end-to-end Rime candidate evidence; no external dependencies."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def rows(name):
    return [json.loads(line) for line in (ROOT / name).read_text().splitlines() if line]

for name in ('results_marker_pc.jsonl', 'results_marker_pc_grammar.jsonl',
             'results_marker_phone_grammar.jsonl'):
    data = rows(name)
    assert len(data) == 5, name
    assert all(row['ok'] and row['pages_complete'] for row in data), name
cascade = rows('results_cascade.jsonl')
assert next(row for row in cascade if row['id'] == 'two-errors')['ok'] is False
baseline = rows('results_sentences_baseline.jsonl')
marker = rows('results_sentences_marker.jsonl')
assert len(baseline) == len(marker) == 9
assert sum(row['ok'] for row in baseline) == 7
assert all(row['ok'] for row in marker)
print('PASS: 15 bounded-candidate checks, reproduced cascade, 9 sentence comparisons')
