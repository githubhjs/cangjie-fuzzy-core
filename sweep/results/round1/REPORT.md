# Sweep decoder: held-out results on SYNTHETIC sweeps

Table sha256 `eeffc957306b58c046ab13a16373e0d0c0999026f5700be50f5799e3942bff1d`; 22142 entries with code length >= 2; test split = 16481 entries (characters hashed out of the tuning split). Noise seeds 1..3, mean (min-max). Levels multiply the profile's spatial errors: low x0.5, mid x1, high x1.6; oracle = noiseless path through the exact code keys (the CEILING: characters sharing one code cannot all be first).

Analytic ceiling on the test split (exact code known, ties broken by weight): top-1 91.4, top-3 99.8, top-5 100.0.

## 1. Tuned defaults per profile, test split

| profile | level | top-1 | top-3 | top-5 | freq-weighted top-1 / top-5 |
|---|---|---|---|---|---|
| mouse | oracle | 88.1 | 99.3 | 99.9 | 97.8 / 100.0 |
| mouse | low | 85.7 (85.7-85.8) | 98.4 (98.3-98.5) | 99.6 (99.6-99.6) | 95.2 / 99.4 |
| mouse | mid | 81.1 (80.9-81.4) | 96.9 (96.9-97.0) | 99.0 (99.0-99.1) | 92.0 / 99.5 |
| mouse | high | 60.6 (60.5-60.9) | 83.4 (83.1-83.8) | 90.2 (90.0-90.4) | 66.6 / 90.0 |
| mouse | vhigh | 27.8 (27.1-28.2) | 46.8 (46.4-47.2) | 56.2 (55.9-56.4) | 32.3 / 55.4 |
| touchpad | oracle | 87.1 | 99.2 | 99.9 | 97.7 / 100.0 |
| touchpad | low | 81.7 (81.6-81.8) | 97.5 (97.5-97.6) | 99.4 (99.4-99.5) | 93.3 / 99.9 |
| touchpad | mid | 52.8 (52.6-53.0) | 76.7 (76.4-76.9) | 85.1 (84.9-85.4) | 62.2 / 86.3 |
| touchpad | high | 21.4 (21.3-21.5) | 38.1 (37.9-38.6) | 47.0 (46.8-47.4) | 26.7 / 48.8 |
| touchpad | vhigh | 6.2 (6.1-6.3) | 12.6 (12.6-12.7) | 16.9 (16.8-16.9) | 8.7 / 17.9 |
| finger | oracle | 86.4 | 99.1 | 99.9 | 97.4 / 100.0 |
| finger | low | 81.1 (80.9-81.3) | 97.2 (97.1-97.4) | 99.2 (99.2-99.3) | 93.3 / 99.8 |
| finger | mid | 50.1 (50.1-50.3) | 73.9 (73.8-73.9) | 82.2 (82.1-82.5) | 59.0 / 82.0 |
| finger | high | 18.6 (18.4-18.9) | 33.9 (33.8-34.1) | 42.5 (42.4-42.6) | 20.2 / 42.2 |
| finger | vhigh | 5.1 (4.9-5.2) | 11.1 (10.9-11.3) | 15.2 (15.1-15.2) | 7.0 / 17.3 |
| touchscreen | oracle | 86.5 | 99.1 | 99.9 | 97.4 / 100.0 |
| touchscreen | low | 83.5 (83.4-83.6) | 98.2 (98.0-98.3) | 99.6 (99.6-99.6) | 94.6 / 99.9 |
| touchscreen | mid | 68.8 (68.5-69.0) | 90.3 (90.0-90.6) | 95.1 (94.9-95.4) | 80.0 / 96.2 |
| touchscreen | high | 36.4 (36.4-36.4) | 58.4 (58.3-58.6) | 68.1 (68.0-68.3) | 43.5 / 67.6 |
| touchscreen | vhigh | 11.7 (11.6-11.7) | 23.1 (22.8-23.3) | 29.9 (29.6-30.0) | 15.2 / 29.8 |

## 2. By code length and code type at level mid (top-1 / top-5, %)

| profile | all | len2 | len3 | len4 | len5 | repeat | shared | clean |
|---|---|---|---|---|---|---|---|---|
| mouse | 81 / 99 | 53 / 98 | 71 / 99 | 82 / 99 | 87 / 99 | 75 / 96 | 40 / 98 | 88 / 100 |
| mouse oracle | 88 / 100 | 59 / 99 | 79 / 100 | 89 / 100 | 93 / 100 | 87 / 100 | 44 / 100 | 95 / 100 |
| touchpad | 53 / 85 | 27 / 70 | 39 / 77 | 51 / 85 | 64 / 90 | 44 / 78 | 25 / 78 | 59 / 88 |
| touchpad oracle | 87 / 100 | 59 / 99 | 78 / 100 | 88 / 100 | 92 / 100 | 84 / 100 | 43 / 99 | 94 / 100 |
| finger | 50 / 82 | 33 / 75 | 41 / 78 | 49 / 82 | 57 / 85 | 34 / 67 | 24 / 76 | 58 / 86 |
| finger oracle | 86 / 100 | 58 / 99 | 76 / 100 | 87 / 100 | 92 / 100 | 86 / 100 | 43 / 99 | 93 / 100 |
| touchscreen | 69 / 95 | 44 / 91 | 59 / 94 | 68 / 95 | 76 / 96 | 52 / 86 | 34 / 92 | 78 / 97 |
| touchscreen oracle | 86 / 100 | 58 / 99 | 77 / 100 | 87 / 100 | 92 / 100 | 86 / 100 | 43 / 99 | 93 / 100 |

Row sizes (n): all=16481, len2=445, len3=2274, len4=8320, len5=5442, repeat=2772, shared=2064, clean=11979

## 3. Noise sweep (top-1 / top-5, %), tuned config of the same profile

| profile | k=0.25 | k=0.5 | k=1 | k=1.6 | k=2.5 |
|---|---|---|---|---|---|
| mouse | 86 / 100 | 85 / 99 | 80 / 99 | 59 / 90 | 28 / 56 |
| touchpad | 84 / 100 | 81 / 99 | 52 / 85 | 21 / 47 | 6 / 17 |
| finger | 84 / 100 | 80 / 99 | 49 / 82 | 18 / 41 | 5 / 15 |
| touchscreen | 84 / 100 | 83 / 100 | 68 / 95 | 35 / 67 | 11 / 30 |

## 4. Transfer: config tuned for ROW profile, noise of COLUMN profile, level mid (top-1 / top-5)

| tuned for \ noise | mouse | touchpad | finger | touchscreen |
|---|---|---|---|---|
| mouse | 80 / 99 | 54 / 85 | 49 / 83 | 68 / 95 |
| touchpad | 79 / 99 | 52 / 85 | 43 / 78 | 63 / 92 |
| finger | 80 / 99 | 55 / 86 | 49 / 82 | 68 / 95 |
| touchscreen | 81 / 99 | 55 / 86 | 50 / 82 | 68 / 95 |
| untuned SweepConfig() | 80 / 99 | 54 / 85 | 49 / 83 | 68 / 95 |

## 5. Ablations (one change at a time from the tuned config; level mid; 6000 test entries; top-1 / top-5 %)

| variant | mouse | finger |
|---|---|---|
| full | 80.5 / 98.9 | 49.3 / 81.9 |
| no shape channel | 80.3 / 98.8 | 48.7 / 82.0 |
| no location channel | 59.5 / 92.9 | 29.7 / 64.8 |
| no start/end term, flat alphas | 77.6 / 97.4 | 44.0 / 76.6 |
| no prior | 80.7 / 98.9 | 49.2 / 81.9 |
| repeat_mode=ignore (no dwell) | 76.1 / 98.5 | 46.4 / 79.8 |
| 2-key shape weight x1 (shape_short_scale=1) | 80.6 / 98.9 | 49.3 / 81.9 |
| 2-key shape weight x0 | 80.4 / 98.9 | 49.0 / 81.7 |
| cover_weight 4 | 80.4 / 98.9 | 49.3 / 81.9 |
| loc_tolerance 0.25 | 79.1 / 98.5 | 49.3 / 81.8 |
| N=16 | 80.4 / 98.9 | 48.9 / 82.0 |
| N=24 | 80.5 / 98.9 | 49.3 / 81.9 |
| N=32 | 80.5 / 98.9 | 49.2 / 81.9 |
| N=48 | 80.5 / 98.9 | 49.1 / 81.8 |
| N=64 | 80.5 / 98.9 | 49.1 / 81.8 |
| prune_radius 0.8 | 80.5 / 98.9 | 48.7 / 79.5 |
| prune_radius 1.0 | 80.5 / 98.9 | 49.3 / 81.8 |
| prune_radius 2.0 | 80.5 / 98.9 | 49.3 / 81.9 |
| no pruning (radius 99) | 80.5 / 98.9 | 49.3 / 81.9 |

## 6. Repeated-letter codes ('hh'): effect of dwell behaviour (level mid; top-1 / top-5 on the `repeat` rows, %)

| profile | user dwells 100% | 80% | 0% (never) | 0% and decoder ignores dwell |
|---|---|---|---|---|
| mouse | 79 / 98 | 68 / 94 | 24 / 79 | 56 / 97 |
| finger | 35 / 66 | 32 / 66 | 22 / 65 | 33 / 75 |

## 7. Lexicon size (random character subsets; level mid; top-1 / top-5 %)

| entries | mouse | finger |
|---|---|---|
| 2213 | 97.0 / 100.0 | 81.8 / 98.1 |
| 5532 | 93.2 / 99.9 | 69.6 / 94.1 |
| 11062 | 88.7 / 99.7 | 62.1 / 89.0 |
| 22142 | 81.8 / 99.2 | 50.3 / 81.5 |

## 8. Layout robustness: phone-like layout (row pitch 1.3 key widths) for both simulator and decoder (top-1 / top-5 %)

| profile | mid | high |
|---|---|---|
| mouse | 82.8 / 99.3 | 67.1 / 94.0 |
| finger | 57.6 / 88.5 | 23.7 / 52.1 |

## 9. Latency, pure Python 3.12, one core (ms per decode, 300 mid-noise mouse paths)

| config | mean | p50 | p95 | max |
|---|---|---|---|---|
| bucket index (default), N=24 | 14.1 | 13.7 | 26.1 | 34.3 |
| full scan, no index | 15.6 | 15.1 | 27.2 | 34.9 |
| bucket index, N=16 | 10.0 | 9.6 | 18.6 | 24.0 |
| bucket index, N=48 | 25.2 | 24.2 | 46.5 | 61.5 |
| bucket index, prune_radius 2.5 | 50.9 | 53.6 | 78.7 | 93.5 |

Lexicon build (templates + index) 0.29 s one-time.
