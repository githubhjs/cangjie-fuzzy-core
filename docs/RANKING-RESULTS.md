# KAN-225: bounded ranking follow-up

Codex, 2026-11-10 ~19:20 Asia/Taipei. **Ranking regression remains unresolved.** The isolated spelling-penalty variants preserve the tested typo availability but fail to preserve baseline exact-code ordering. No production schema or existing spike evaluator/generator was changed.

## Experiment

`spike/ranking_probe.py` creates `spike/ranking_env` with baseline plus four PC-marker schemas: 0, 2, 4, or 8 additional fuzzy penalties. Each additional stage is:

```yaml
- 'fuzz/^([a-z]*[A-Z][a-z]*)$/~$1/'
- 'erase/^[a-z]*[A-Z][a-z]*$/'
- 'xform/^~//'
```

The erasure is essential to the design: fuzz retains the input spelling, and retaining the lower-penalty copy would let it survive a later merge. These stages operate only on the uppercase typo marker and cannot change the original lowercase spelling. Existing final lowercase conversion remains after all stages. This changes cumulative spelling credibility, not an explicit hard ordering policy. Local `src/algebra.cc` shows accumulated credibility and best-credibility merging; `src/script_translator.cc` combines weights, initial quality and normal-spelling status. The experiment does not isolate every ranking path or prove a root cause.

Build of all five isolated schemas succeeded in 49.472 seconds using existing local binaries/data. All four variants passed the five candidate inclusion/exclusion cases (complete pagination), including 顏 available for `yhmbv` and absent for `yhnbv`. All four retained 9/9 top-1 on the prior tiny sentence smoke test. The exact `yhmbc` still ranked 須 first in every fuzzy variant, while baseline ranked 頻 first; 顏 remained rank 2 for typo `yhmbv`.

## Wider exact-code comparison

`spike/ranking_compare.py` selects 100 evenly spaced entries from the sorted unique 2–5-letter code set in the existing single-character test dictionary, then evaluates the same inputs under all five schemas. This is deterministic coverage, **not a representative frequency-weighted user corpus**. It uses existing octagram/model configuration, does not commit candidates or train the user dictionary, and compares the baseline first page against the same-length prefix of the variant page.

| Extra fuzzy penalties | Changed top-1 / 100 | Baseline first-page prefix changed / 100 |
|---:|---:|---:|
| 0 | 58 | 78 |
| 2 | 58 | 78 |
| 4 | 57 | 77 |
| 8 | 57 | 77 |

Example: exact `bgb` baseline `[爯]` becomes `[骨, 姌, 爯, 胿]` in every tested variant. Increasing penalty alone therefore does **not** meet the goal. “Changed first-page prefix” includes extra candidates inserted ahead of baseline entries, not just reversal of shared entries. Full candidate sets were not compared for ordering beyond page one.

## Validation and artifacts

Run from the spike directory:

```sh
python3 ranking_probe.py > ranking_summary.log 2>&1
python3 ranking_compare.py > ranking_compare.jsonl
python3 -m py_compile ranking_probe.py ranking_compare.py
```

Both commands completed successfully and compilation passed. Probe outputs are `ranking_<schema>_acceptance.jsonl`, `ranking_<schema>_sentences.jsonl` and matching stderr files; sample outputs are `ranking_<schema>_sample.jsonl`. `ranking_compare.jsonl` contains counts plus concrete differing candidates. Build diagnostics: `ranking_build.log`. Generated schemas/data are local experimental artifacts under `ranking_env`, not shipping code.

Authored files: `ranking_probe.py`, `ranking_compare.py`, `ranking_cases_sample.jsonl`, this report, and the described logs/results. Existing generator, maps, evaluator, earlier evidence and production files remain unchanged. No dependency installation and no commit by this worker.

## Remaining decision / next implementation boundary

A stricter architecture should preserve the exact translator's candidate stream and append or deliberately merge a separate fuzzy stream, with explicit sentence and partial-match policy. That is a recommendation for a subsequent scoped experiment, **not a verified working fix**. The `strict_spelling` path in the inspected source rejects fuzzy full-input single words, so it cannot simply be enabled to satisfy `yhmbv` → 顏. Separate exact/fuzzy translators, Lua candidate arbitration and C++ changes were not implemented in this bounded pass. Android licensing/provenance review remains separate.
