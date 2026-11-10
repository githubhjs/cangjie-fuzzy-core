"""Generate all single-key substitutions and deterministic two-error probes for 顏."""
import itertools
import json
from pathlib import Path
import random
import string
import gen_fuzzy

root = Path(__file__).resolve().parent
for profile in ('pc', 'phone'):
    neighbors = gen_fuzzy.layout_neighbors(profile)
    code = 'yhmbc'
    cases = [{'id': 'exact', 'keys': code, 'contains': '顏'}]
    for i, key in enumerate(code):
        for replacement in string.ascii_lowercase:
            if replacement != key:
                typed = code[:i] + replacement + code[i+1:]
                check = 'contains' if replacement in neighbors[key] else 'excludes'
                cases.append({'id': f'single-{i}-{replacement}', 'keys': typed, check: '顏'})
    doubles = set()
    for i, j in itertools.combinations(range(len(code)), 2):
        for a in neighbors[code[i]]:
            for b in neighbors[code[j]]:
                chars = list(code)
                chars[i], chars[j] = a, b
                doubles.add(''.join(chars))
    for index, typed in enumerate(sorted(doubles)):
        cases.append({'id': f'double-{index}', 'keys': typed, 'excludes': '顏'})
    (root / f'cases_target_{profile}.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in cases))
    print(profile, len(cases), 'cases')
