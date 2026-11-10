# KAN-225 expanded validation — 2026-11-10

Codex continued after the owner asked to do available tasks.

## Actual Rime engine

Generated cases for target 顏 (local third-generation dictionary has exactly one 顏 row: `yhmbc`). Tested the existing isolated PC and phone marker builds using `eval_driver.py`, with complete candidate pagination.

| Profile | Cases | Passing | Pagination complete |
|---|---:|---:|---:|
| PC | 300 | 300 | 300 |
| Phone | 239 | 239 | 239 |

Each suite contains the exact code, all 125 possible single-position replacements, and every combination of two positions changed to their respective neighboring keys (174 PC; 113 phone). Adjacent single substitutions must include 顏; non-adjacent single substitutions and double substitutions must exclude it. Different profile geometry explains case-count differences. No candidate-selection/commit operation was used, so these probes do not train the user dictionary.

This verifies this target with these engine builds and dictionaries. It is not an exhaustive engine test over the complete dictionary or proof of keyboard geometry on real hardware.

Reproduce under `spike/`:

```sh
python3 make_target_cases.py
export LD_LIBRARY_PATH=/home/hjs/projects/cangjie-fluency/rimebin/root/usr/lib/aarch64-linux-gnu
python3 -I eval_driver.py --env "$PWD/testenv/marker_pc" --schema cangjie3_fuzzy_spike cases_target_pc.jsonl > results_target_pc.jsonl
python3 -I eval_driver.py --env "$PWD/testenv/marker_phone" --schema cangjie3_fuzzy_spike cases_target_phone.jsonl > results_target_phone.jsonl
```

Check every saved row's `ok` and `pages_complete` flags, not only evaluator exit status: that evaluator emits failed assertions as JSON rows without a failing exit code.

## Generator contract

`python3 test_generator_contract.py -v`: four tests pass. Compared complete output sets of the default generated rules against an independently specified adjacency oracle for 447 PC and 445 phone codes (892 total), including repeated letters and lengths 1–5. Checked disabled tolerance, symmetric maps, no self edges, and the owner's positive/negative examples.

The small Python projection models only the generator's default one-stage fuzz plus final transliteration; real-engine tests above provide a separate check. Neither test establishes ranking, sentence accuracy, Android redistribution rights, or performance on target hardware. Non-default generator options remain outside the validated contract.

`python3 spike/verify_target_results.py` passes and returns failure on missing counts, duplicate IDs, mismatched input identity, failed assertions or incomplete pagination. Preserve this check when rerunning or expanding the suites.
