#!/usr/bin/env python3
"""Fail closed on missing, duplicate, incomplete or failed saved target probes."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
for profile, count in [('pc', 300), ('phone', 239)]:
    cases = [json.loads(line) for line in (root / f'cases_target_{profile}.jsonl').read_text().splitlines()]
    results = [json.loads(line) for line in (root / f'results_target_{profile}.jsonl').read_text().splitlines()]
    if len(cases) != count or len(results) != count:
        raise SystemExit(f'{profile}: missing or extra cases/results')
    if len({row['id'] for row in results}) != count:
        raise SystemExit(f'{profile}: duplicate result IDs')
    for case, result in zip(cases, results):
        if any(result.get(field) != case[field] for field in ('id', 'keys')):
            raise SystemExit(f'{profile}: result ordering/identity mismatch')
        if result.get('ok') is not True or result.get('pages_complete') is not True:
            raise SystemExit(f'{profile}: failed or incomplete case {case["id"]}')
    print(f'{profile}: PASS {count} complete candidate checks')
