# Pointer jitter robustness (synthetic data)

All results use the section 12 `decode_auto` policy, profile-specific character config, ANSI geometry, the full Cangjie table and all usable 2–4 character words with frequency >= 1000. Existing profile noise is at mid; sigma is **additional iid Gaussian noise per axis per sample**, in key widths. Sigma 0 is the clean-control condition (ordinary profile noise remains). Paths, boundaries, and random draws are paired across variants and jitter levels.

Candidates: 22174 character entries (including one-letter codes in the word list), 31576 usable words, 49743 word-list templates. Evaluation: 1000 held-out character entries and 270 held-out stratified words per seed, 1 noise seed(s). Character split/sample seed 4; words stratified by length 2/3/4 and frequency 1k–3k/3k–10k/>=10k, sample seed 5. Word boundaries use the existing hash-selected 50% continuous / 25% dwell / 25% lift rule.

Table SHA-256 `eeffc957306b58c046ab13a16373e0d0c0999026f5700be50f5799e3942bff1d`; essay SHA-256 `3e8512ebaa6657e35961b1f5762060717c647e3bf471d5e3b86e783b4e934ffb`.

Reproduce (local corpora required; no network):

```sh
python3 -m sweep.report_jitter --chars 1000 --per-cell 30 --workers 4 --variants off,smooth --owners 100 --latency 30 --latency-repeats 3 --latency-sigmas 0,.2,.3 --ablation sweep/results/jitter_pilot.json --out sweep/results/jitter.json --report sweep/results/JITTER.md
```

`off` explicitly disables the stage in BOTH decoder configs and is the unchanged baseline. `smooth` filters scoring geometry and length; `length` filters only length, keeping raw scoring geometry; `window` widens the raw length window from estimated inflation; `smooth_window` combines smoothing with widening. All enabled variants estimate jitter from the path and bypass clean paths below the configured gate. The implementation and exact defaults are in SPEC.md.

The default is `pointer_filter="smooth"` with `pointer_jitter_floor=0.045`. Length-only correction and adaptive widening help, but leave noisy arc-length resampling and key-touch alignment intact. Smoothing addresses those as well. Widening on top of smoothing did not improve the pilot consistently, so the narrower original length window remains the default.

These character rows also use the product policy. They can fail more sharply than the characters-only decoder reported in section 8: if the noisy one-list decoder puts a word first, `decode_auto` returns that word list. The word-population mean need not reach zero, because candidate fallback can reopen an unbounded length window when very few candidates survive. The literal owner table below tests the original specific cliff.

Top-1 / top-5 percentages:

| profile | sweep | added sigma | off | smooth |
|---|---|---|---|---|
| mouse | char | 0 | 78.7 / 98.9 | 78.7 / 98.9 |
| mouse | char | 0.05 | 71.6 / 95.1 | 75.6 / 98.8 |
| mouse | char | 0.1 | 45.0 / 65.9 | 74.3 / 98.9 |
| mouse | char | 0.2 | 8.5 / 16.6 | 65.4 / 96.5 |
| mouse | char | 0.3 | 1.6 / 4.3 | 53.2 / 86.9 |
| mouse | word | 0 | 97.8 / 98.9 | 97.8 / 98.9 |
| mouse | word | 0.05 | 93.7 / 94.8 | 97.4 / 98.9 |
| mouse | word | 0.1 | 48.5 / 50.4 | 97.8 / 98.9 |
| mouse | word | 0.2 | 26.3 / 30.0 | 94.8 / 96.3 |
| mouse | word | 0.3 | 37.8 / 44.1 | 86.7 / 92.6 |
| finger | char | 0 | 36.3 / 70.5 | 36.3 / 70.5 |
| finger | char | 0.05 | 32.0 / 66.7 | 35.0 / 70.7 |
| finger | char | 0.1 | 16.2 / 38.2 | 34.0 / 70.6 |
| finger | char | 0.2 | 1.3 / 5.1 | 28.1 / 62.5 |
| finger | char | 0.3 | 0.8 / 1.2 | 24.0 / 58.0 |
| finger | word | 0 | 87.4 / 93.7 | 87.4 / 93.7 |
| finger | word | 0.05 | 73.0 / 79.3 | 85.6 / 93.0 |
| finger | word | 0.1 | 28.1 / 33.3 | 84.1 / 91.5 |
| finger | word | 0.2 | 20.4 / 22.6 | 77.0 / 87.0 |
| finger | word | 0.3 | 29.3 / 35.9 | 69.6 / 82.6 |
| touchpad | char | 0 | 50.2 / 84.4 | 50.2 / 84.4 |
| touchpad | char | 0.05 | 43.7 / 78.2 | 47.5 / 83.6 |
| touchpad | char | 0.1 | 27.3 / 51.8 | 46.0 / 80.5 |
| touchpad | char | 0.2 | 6.0 / 14.0 | 38.0 / 72.7 |
| touchpad | char | 0.3 | 1.1 / 4.1 | 30.3 / 63.4 |
| touchpad | word | 0 | 90.0 / 94.8 | 90.0 / 94.8 |
| touchpad | word | 0.05 | 80.4 / 87.8 | 88.1 / 94.4 |
| touchpad | word | 0.1 | 43.7 / 46.7 | 86.3 / 93.0 |
| touchpad | word | 0.2 | 24.1 / 28.1 | 78.1 / 87.0 |
| touchpad | word | 0.3 | 31.9 / 38.5 | 68.1 / 81.9 |
| touchscreen | char | 0 | 64.2 / 94.3 | 64.2 / 94.3 |
| touchscreen | char | 0.05 | 56.0 / 87.0 | 61.2 / 93.1 |
| touchscreen | char | 0.1 | 27.7 / 50.7 | 58.8 / 91.7 |
| touchscreen | char | 0.2 | 3.0 / 7.5 | 49.0 / 83.9 |
| touchscreen | char | 0.3 | 1.2 / 2.0 | 40.1 / 78.2 |
| touchscreen | word | 0 | 95.6 / 97.8 | 95.6 / 97.8 |
| touchscreen | word | 0.05 | 83.7 / 85.6 | 93.7 / 97.4 |
| touchscreen | word | 0.1 | 29.6 / 32.2 | 93.3 / 97.4 |
| touchscreen | word | 0.2 | 22.6 / 24.4 | 89.6 / 94.4 |
| touchscreen | word | 0.3 | 33.3 / 37.8 | 84.8 / 92.2 |

Clean-control top-1 changes (`smooth` minus `off`, percentage points):

| profile | characters | words |
|---|---|---|
| mouse | +0.00 | +0.00 |
| finger | +0.00 | +0.00 |
| touchpad | +0.00 | +0.00 |
| touchscreen | +0.00 | +0.00 |

The required mouse/finger character/word clean groups pass the <=0.5-point top-1 regression gate on this sample (largest observed drop 0.00 points).

Candidate pilot (separate smaller evaluation: 200 characters and 90 words per profile, same corpus and seeds; top-1 / top-5 %). These measurements informed choosing the final default. The larger evaluation expands the same split/sample seeds: it is held out from original decoder tuning, but is not an independent untouched confirmation set for filter selection.

| profile | sweep | added sigma | off | smooth | length | window | smooth_window |
|---|---|---|---|---|---|---|---|
| mouse | char | 0 | 81.0 / 99.0 | 81.0 / 99.0 | 81.0 / 99.0 | 81.0 / 99.0 | 81.0 / 99.0 |
| mouse | char | 0.05 | 72.5 / 94.5 | 78.0 / 99.0 | 74.0 / 97.5 | 74.0 / 97.5 | 78.0 / 99.0 |
| mouse | char | 0.1 | 43.5 / 63.5 | 77.5 / 99.5 | 66.5 / 96.0 | 66.5 / 96.0 | 77.5 / 99.5 |
| mouse | char | 0.2 | 8.0 / 15.0 | 65.0 / 98.0 | 48.0 / 89.5 | 47.5 / 89.5 | 65.0 / 98.0 |
| mouse | char | 0.3 | 0.5 / 3.0 | 50.5 / 84.5 | 30.5 / 71.5 | 28.5 / 71.0 | 50.5 / 85.0 |
| mouse | word | 0 | 97.8 / 98.9 | 97.8 / 98.9 | 97.8 / 98.9 | 97.8 / 98.9 | 97.8 / 98.9 |
| mouse | word | 0.05 | 86.7 / 87.8 | 97.8 / 98.9 | 96.7 / 97.8 | 95.6 / 97.8 | 97.8 / 98.9 |
| mouse | word | 0.1 | 35.6 / 36.7 | 97.8 / 98.9 | 91.1 / 97.8 | 91.1 / 97.8 | 97.8 / 98.9 |
| mouse | word | 0.2 | 30.0 / 32.2 | 91.1 / 96.7 | 81.1 / 91.1 | 81.1 / 93.3 | 91.1 / 96.7 |
| mouse | word | 0.3 | 42.2 / 51.1 | 91.1 / 96.7 | 64.4 / 86.7 | 65.6 / 87.8 | 88.9 / 94.4 |
| finger | char | 0 | 34.0 / 67.5 | 34.0 / 67.5 | 34.0 / 67.5 | 34.0 / 67.5 | 34.0 / 67.5 |
| finger | char | 0.05 | 30.5 / 62.0 | 34.0 / 68.5 | 32.5 / 68.5 | 32.5 / 68.0 | 34.0 / 68.5 |
| finger | char | 0.1 | 13.5 / 34.5 | 34.0 / 69.0 | 30.0 / 67.5 | 29.0 / 65.5 | 34.0 / 69.0 |
| finger | char | 0.2 | 0.0 / 2.5 | 28.0 / 61.5 | 18.5 / 50.0 | 18.5 / 51.5 | 28.0 / 61.0 |
| finger | char | 0.3 | 1.0 / 2.0 | 21.0 / 55.0 | 13.5 / 40.5 | 12.0 / 39.0 | 21.0 / 55.0 |
| finger | word | 0 | 81.1 / 91.1 | 81.1 / 91.1 | 81.1 / 91.1 | 81.1 / 91.1 | 81.1 / 91.1 |
| finger | word | 0.05 | 56.7 / 64.4 | 86.7 / 93.3 | 74.4 / 88.9 | 72.2 / 88.9 | 86.7 / 93.3 |
| finger | word | 0.1 | 31.1 / 35.6 | 86.7 / 94.4 | 73.3 / 88.9 | 71.1 / 87.8 | 85.6 / 92.2 |
| finger | word | 0.2 | 21.1 / 24.4 | 76.7 / 87.8 | 58.9 / 78.9 | 58.9 / 78.9 | 74.4 / 86.7 |
| finger | word | 0.3 | 31.1 / 37.8 | 70.0 / 88.9 | 50.0 / 72.2 | 46.7 / 71.1 | 70.0 / 84.4 |

Literal owner paths, continuous, 100 jitter draws each (top-1 / top-5 %). These reproduce the specific section 8 failure independently of the simulator corpus.

| target | added sigma | off | smooth |
|---|---|---|---|
| 顏值 | 0 | 100.0 / 100.0 | 100.0 / 100.0 |
| 顏值 | 0.05 | 100.0 / 100.0 | 100.0 / 100.0 |
| 顏值 | 0.1 | 100.0 / 100.0 | 100.0 / 100.0 |
| 顏值 | 0.2 | 0.0 / 0.0 | 100.0 / 100.0 |
| 顏值 | 0.3 | 0.0 / 0.0 | 100.0 / 100.0 |
| 頻率 | 0 | 100.0 / 100.0 | 100.0 / 100.0 |
| 頻率 | 0.05 | 100.0 / 100.0 | 100.0 / 100.0 |
| 頻率 | 0.1 | 0.0 / 0.0 | 100.0 / 100.0 |
| 頻率 | 0.2 | 0.0 / 0.0 | 99.0 / 100.0 |
| 頻率 | 0.3 | 0.0 / 0.0 | 100.0 / 100.0 |

Literal owner arc length in key widths, averaged over the same jitter draws. Filtering reduces jitter's excess travel before the length window and equidistant resampling.

| target | samples | added sigma | clean | raw mean | filtered mean |
|---|---|---|---|---|---|
| 顏值 | 97 | 0 | 18.59 | 18.59 | 18.59 |
| 顏值 | 97 | 0.05 | 18.59 | 20.31 | 17.08 |
| 顏值 | 97 | 0.1 | 18.59 | 25.45 | 16.23 |
| 顏值 | 97 | 0.2 | 18.59 | 39.48 | 14.75 |
| 顏值 | 97 | 0.3 | 18.59 | 55.03 | 13.83 |
| 頻率 | 121 | 0 | 17.41 | 17.41 | 17.41 |
| 頻率 | 121 | 0.05 | 17.41 | 19.82 | 16.30 |
| 頻率 | 121 | 0.1 | 17.41 | 26.91 | 16.15 |
| 頻率 | 121 | 0.2 | 17.41 | 45.59 | 15.24 |
| 頻率 | 121 | 0.3 | 17.41 | 65.83 | 14.62 |

Serial paired warm-cache latency, mean / p95 milliseconds (mean change relative to off). No accuracy workers are running during these measurements.

| profile | sweep | added sigma | off | smooth |
|---|---|---|---|---|
| mouse | char | 0 | 12.37 / 18.99 (+0.0%) | 12.19 / 18.17 (-1.4%) |
| mouse | char | 0.2 | 14.09 / 23.67 (+0.0%) | 10.98 / 15.88 (-22.1%) |
| mouse | char | 0.3 | 16.06 / 23.76 (+0.0%) | 11.25 / 17.80 (-30.0%) |
| mouse | word | 0 | 14.04 / 19.59 (+0.0%) | 13.95 / 19.66 (-0.6%) |
| mouse | word | 0.2 | 20.36 / 42.09 (+0.0%) | 12.90 / 18.81 (-36.7%) |
| mouse | word | 0.3 | 23.90 / 42.01 (+0.0%) | 12.25 / 17.94 (-48.7%) |
| finger | char | 0 | 11.76 / 19.46 (+0.0%) | 11.63 / 18.77 (-1.1%) |
| finger | char | 0.2 | 14.85 / 26.17 (+0.0%) | 11.90 / 18.91 (-19.9%) |
| finger | char | 0.3 | 18.50 / 29.85 (+0.0%) | 11.31 / 19.16 (-38.9%) |
| finger | word | 0 | 12.98 / 21.45 (+0.0%) | 12.92 / 20.74 (-0.5%) |
| finger | word | 0.2 | 17.42 / 30.71 (+0.0%) | 12.89 / 19.86 (-26.0%) |
| finger | word | 0.3 | 27.03 / 49.06 (+0.0%) | 12.57 / 18.28 (-53.5%) |
| touchpad | char | 0 | 10.84 / 15.66 (+0.0%) | 10.73 / 15.30 (-1.0%) |
| touchpad | char | 0.2 | 15.21 / 22.50 (+0.0%) | 12.00 / 18.62 (-21.1%) |
| touchpad | char | 0.3 | 16.38 / 31.38 (+0.0%) | 11.76 / 19.91 (-28.2%) |
| touchpad | word | 0 | 12.82 / 18.75 (+0.0%) | 12.72 / 18.64 (-0.8%) |
| touchpad | word | 0.2 | 16.12 / 25.38 (+0.0%) | 12.83 / 18.99 (-20.4%) |
| touchpad | word | 0.3 | 20.29 / 49.99 (+0.0%) | 13.51 / 29.11 (-33.4%) |
| touchscreen | char | 0 | 8.36 / 12.67 (+0.0%) | 8.24 / 12.17 (-1.5%) |
| touchscreen | char | 0.2 | 11.93 / 19.27 (+0.0%) | 8.00 / 10.80 (-33.0%) |
| touchscreen | char | 0.3 | 13.22 / 19.24 (+0.0%) | 8.58 / 11.00 (-35.1%) |
| touchscreen | word | 0 | 9.93 / 14.60 (+0.0%) | 9.87 / 14.22 (-0.6%) |
| touchscreen | word | 0.2 | 14.79 / 24.41 (+0.0%) | 10.14 / 13.85 (-31.4%) |
| touchscreen | word | 0.3 | 23.83 / 50.36 (+0.0%) | 9.96 / 13.45 (-58.2%) |

The +20% mean latency gate passes for every measured group; largest smooth/off ratio 0.995 (-0.5%).

Regression verification: `python3 sweep/tests/test_sweep.py` (30), `python3 sweep/tests/test_words.py` (14), `python3 sweep/tests/test_auto.py` (7), and `python3 sweep/tests/test_jitter.py` (10) pass: 61 tests total. Existing ANSI, phone, character, word, and auto vectors pass unchanged; no existing vectors were regenerated. A full-product-lexicon smoke check also preserved `yhmbc` as the first code for `yhyjmnbvc`, `yhjmnbvc`, and `yhmbc` on ANSI and phone geometry, and preserved 顏值/頻率 top-1 on both geometries. Both owner words stayed top-1 in all six ANSI continuous/lift/dwell cases.

These are synthetic results, not measured mouse, finger, touchpad, or touchscreen accuracy. The finite held-out sample does not establish a population-level 0.5-point bound. Real sensor traces, device sampling/coalescing, and Kotlin/desktop latency are not validated. The jitter estimate is gesture-global; local bursts may be missed. Spans with fewer than seven samples or gaps >32 ms are left unchanged. Smoothing rounds sharp corners and can shorten literal paths below their noiseless length; the arc-length table quantifies this tradeoff. The auto character branch receives no lift indices, so a lift with a gap <=32 ms can be filtered across in that branch; the word branch respects explicit lifts.
