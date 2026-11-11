# Sweep Pad round 2 delivery

All source/data changes are under `sweep-pad/`. No network, commits, or pushes. `sweep/` was read and bundled without source changes.

## Files changed

- `cangjie_sweep_pad.py`: word decoding; ranked word/character buttons with codes below; delayed gesture completion and quick-repress lift indices; loading status and queued decoding; profile/separator/lift settings; JSON gesture objects, literal CLI, expectation exit codes, data self-check.
- `pad_words.py` (new): published `defaults_words.json`, frequency >=100 and 2–4 character words plus table characters; pad candidate-code adapter; SHA-256 keyed built-template JSON cache; atomic writes and background worker. All profiles currently use the same published word defaults, because upstream provides no separate device word defaults.
- `injectors/{__init__,windows,macos,linux}.py`: explicit Space/apostrophe separator keys across backends. Default word separator is empty. Rime schema behavior remains unverified; Space may select/commit, so no automatic separator is assumed.
- `data/cangjie3.tsv`: three owner-case character entries added to the existing demo (30 entries total).
- `data/essay.txt` (new): unchanged full local essay copy, LGPL-3.0; `data/LICENSE-essay.txt` (new), `data/README.md`: licence and provenance.
- `tests/test_pad.py`, `tests/test_injectors.py`, `tests/test_words_pad.py` (new): word path, cache, loading, lift and separator regressions. Tests preserve the single-key tap and use mocked injection/UI.
- `make-release.sh`: bundles pad modules, injectors, current sweep/core Python, defaults and vectors, table, essay, documentation/licences; extracts and validates the resulting zip from an independent working directory with an empty cache.
- `README.md`: zh-Hant and English instructions and verified/unverified boundaries.
- `REPORT.md` (this report).
- Generated `dist/cangjie-sweep-pad-0.2.0.zip` and `.zip.sha256` (dist is ignored by Git).

## Final test output

```
python3 -m unittest discover -s sweep-pad/tests
Ran 43 tests in 1.845s
OK

python3 sweep/tests/test_sweep.py
Ran 24 tests in 0.810s
OK

python3 sweep/tests/test_words.py
Ran 13 tests in 0.565s
OK
```

All 80 tests passed with no skips. Python bytecode generation was disabled during final runs. New tests cover both owners in continuous/lift/dwell modes, cold/warm/corrupt/unwritable/invalidation cache behavior, background worker success/error, queued loading and persistent loading failures, quick/late represses, retained timestamps, key taps, separators, JSON lift validation, CLI expected-result success/failure, and Windows literal sampler fallback. Shell syntax, `git diff --check`, and Python 3.8 grammar checks passed; execution was on Python 3.12, not a Python 3.8 runtime.

## Headless output

Both commands below returned exit 0, including when executed from the extracted release. Fresh commands with `--top-k 1` emitted:

```
--decode-string "yhmnbvc ojhbnm" --boundary continuous --expect 顏值 --top-k 1
[{"char": "顏值", "code": "yhmbcojbm", "score": 0.21775047509674295}]

--decode-string "yhjmnbvc yuiokjhj" --boundary continuous --expect 頻率 --top-k 1
[{"char": "頻率", "code": "yhmbcyioj", "score": -21.24854842268707}]
```

Both also passed through the pad with the full local research table supplied via `--table /tmp/fw/f5a/app/src/main/assets/fuzzy/cangjie3.tsv`, with the same top-1 codes/scores. The full table was not copied into the release because its redistribution provenance remains unresolved. The bundle has the complete essay but only words supported by its 30-entry demo character table; arbitrary Chinese input needs a full authorized character table.

## Extracted release

`./sweep-pad/make-release.sh 0.2.0` succeeded, including both owner expectation checks in the actual extracted zip. Archive SHA-256 verification:

```
cangjie-sweep-pad-0.2.0.zip: OK
```

Extracted `--self-check` returned exit 1 with:

```json
{"platform":"linux","session":"tty","display":false,"tkinter":8.6,"injector_available":false,"injector_message":"Missing xdotool; install it to inject keys.","table_available":true,"essay_available":true}
```

This proves the decoder/data import and loading paths are self-contained; it does not establish desktop injection availability.

## Not verified

- Live GUI interaction, real mouse/touchpad/touchscreen traces, long-running use, and full-table accuracy claims.
- Actual Rime composition of concatenated codes or schema-specific separators.
- Native Windows/macOS injection and focus; Linux target injection, window managers, Wayland compositors, ydotoold/uinput permissions. The available session has no desktop or xdotool.
- Execution under Python 3.8 or native Windows/macOS (only syntax/platform API mocks were checked).
- Remote machine execution and upstream licence provenance via network (network was prohibited).
