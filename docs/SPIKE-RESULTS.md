# KAN-225: recovered Rime single-neighbor spike

Verified by Codex on GX10 ARM64 Linux, 2026-11-10 ~19:15 Asia/Taipei.
This continues Claude's interrupted experimental files, not a shipping implementation.

## Result

Rime spelling algebra **can express one adjacent-key substitution per dictionary spelling** without chaining, using the existing generator's uppercase marker and a final lowercase conversion. No Lua or C++ extension was needed for this bounded proof. Ordinary sequential lowercase fuzz rules do chain. Candidate ranking still needs work before release.

| Input | Intended test | Naive `fuzz/c/v/`, `fuzz/m/n/` | Marker PC | Marker phone |
|---|---|---|---|---|
| `yhmbc` | exact 顏 present | present | rank 3 | rank 3 |
| `yhmbv` | c → v adjacent typo | present | rank 2 | rank 2 |
| `yhnbc` | m → n adjacent typo | present | rank 2 | rank 2 |
| `yhnbv` | two substitutions rejected for 顏 | **FAIL: 顏 present** | 顏 absent | 顏 absent |
| `yhmbp` | non-neighbor c → p rejected for 顏 | 顏 absent | 顏 absent | 顏 absent |

All candidate pages were traversed to the engine's last-page marker, not merely the visible first five. The evaluator bounds traversal at 100 pages and an exclusion cannot pass unless traversal completed. Actual cases completed with 10–19 candidates in the marker profiles. PC also passed without loading the octagram module. The grammar runs load the installed octagram plugin and existing model via the shared directory; these are candidate-output observations, not proof that every output depends on the model.

The negative target is specifically Traditional 顏. `yhmbp` can offer Simplified 颜, whose dictionary coding is a separate entry; broader semantic-equivalence rejection is not established by these tests.

## Mechanism and boundary

A rule matches a wholly lowercase spelling and substitutes exactly one position with an uppercase neighbor. Later rules require wholly lowercase input, so they cannot match that derived spelling. Only after every fuzzy rule does `xlit` restore lowercase. Both local maps generated 130 position rules plus one final transliteration. This is a **per-spelling** edit budget: sentence composition can independently correct multiple character spellings. It does not impose a one-error budget across an entire sentence.

By contrast, `spike/src/algebra.cc`'s `Projection::Apply(Script*)` iterates rules and passes each round's merged output into the next. The two-rule naive experiment directly reproduced the cascade. The earlier all-pairs naive deployment was already terminated in Claude's log; it was not restarted, and no conclusion about its ultimate build time is claimed.

## Cost and ranking

| Measurement | Baseline | PC marker | Phone marker |
|---|---:|---:|---:|
| Prism bytes | 688,936 | 10,697,464 (~15.53×) | 9,543,560 (~13.85×) |
| Full isolated deployment wall time | not measured alone | 12.256 s | 10.780 s |
| Shared dictionary table bytes | 15,186,292 | same | same |

In the five-case grammar probes, per-case average key+frontend-context work was 0.07–0.12 ms; maximum observed individual key was 0.51 ms (PC), 0.49 ms (phone). These are short, warm, single-machine observations, **not p95/p99 benchmarks or Android performance evidence**. Pagination time is excluded from key timings. Deploy timings include both baseline and fuzzy schemas plus their dependencies in new isolated folders.

Ranking limitation: plain exact `yhmbc` has 頻 ahead of 顏; the fuzzy schema additionally puts 須 first, displacing 顏 to rank 3. `yhmbv` offers 顏 at rank 2 rather than making it the first candidate. Thus “must appear as a candidate” passes; “must always be top-1” does not.

## Small sentence probe

A fixed 9-case probe contains seven exact two-character strings (顏色, 顏面, 中國, 香港, 臺灣, 今天, 我們) and two c→v typo versions of 顏色/顏面. Baseline: 7/9 top-1, missing both typos. Marker PC: 9/9 top-1. All seven exact cases retained their desired top candidate. This is a smoke test, not an accuracy corpus; longer sentences, uncommon characters, homophones, and user-learning effects remain unmeasured.

## Changes made during recovery

- `spike/eval_driver.py`: fixed missing pointer-width argument type for `RimeDestroySession`, freed empty successful contexts, fail loudly on schema-selection failure; added candidate inclusion/exclusion checks, complete pagination and target rank.
- `spike/cases_acceptance.jsonl`, `cases_sentences.jsonl`: explicit candidate and top-1 cases.
- `spike/results_*.jsonl`, `results_*.stderr`, `marker_*_build.log`: fresh observed outputs.
- `spike/verify_results.py`: checks 15 candidate cases across PC/no-grammar, PC/grammar, phone/grammar; confirms the naive failure and nine sentence comparisons.
- Existing `gen_fuzzy.py`, adjacency maps and `build.sh` were reused unchanged. Defaults only were tested (`--tolerance 1 --min-len 2 --max-len 5 --stages 1`). Non-default options are not validated; `--tolerance` does not implement arbitrary edit distances, and repeated penalty stages should not be assumed to suppress their earlier retained variants.

## Reproduction

From `/home/hjs/projects/cangjie-fuzzy-spec/spike`:

```sh
export LD_LIBRARY_PATH=/home/hjs/projects/cangjie-fluency/rimebin/root/usr/lib/aarch64-linux-gnu
timeout 120 bash build.sh marker_pc --map neighbors_pc.json
python3 -I eval_driver.py --env "$PWD/testenv/marker_pc" --schema cangjie3_fuzzy_spike cases_acceptance.jsonl
python3 -I eval_driver.py --env "$PWD/testenv/marker_pc" --schema cangjie3_fuzzy_spike --no-grammar cases_acceptance.jsonl
python3 -I eval_driver.py --env "$PWD/testenv/casc_a" --schema casc_a --no-grammar cases_acceptance.jsonl
timeout 90 bash build.sh marker_phone --map neighbors_phone.json
python3 -I eval_driver.py --env "$PWD/testenv/marker_phone" --schema cangjie3_fuzzy_spike cases_acceptance.jsonl
python3 -I eval_driver.py --env "$PWD/testenv/marker_pc" --schema cangjie3_fluency cases_sentences.jsonl
python3 -I eval_driver.py --env "$PWD/testenv/marker_pc" --schema cangjie3_fuzzy_spike cases_sentences.jsonl
python3 verify_results.py
python3 -m py_compile eval_driver.py gen_fuzzy.py verify_results.py
bash -n build.sh
```

`verify_results.py` validates saved evidence, so regenerate the named result files when changing the generator or engine. Current result: `PASS: 15 bounded-candidate checks, reproduced cascade, 9 sentence comparisons`. Python compilation and shell syntax check also pass. No dependencies installed; no production IME configuration changed.

## Handoff / remaining work

1. Preserve exact-code ranking and evaluate a larger held-out corpus before release.
2. Define error budget per character vs whole sentence, and candidate inclusion vs top-1 expectations in SPEC.
3. Calibrate keyboard layouts on real PC/phone hardware; the local maps are idealized geometry.
4. Benchmark memory, cold start, long sentences, and repeated timings on Android and Windows.
5. Treat the existing dictionary, language model, plugin, source excerpts and binary dependencies as research inputs only. This spike does **not** establish suitability for the owner's no-GPL Android product. Do not commit/publish generated tables, copied upstream code, or models as original project code without the separate license/provenance review.
