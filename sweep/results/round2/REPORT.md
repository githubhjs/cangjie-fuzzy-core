# Sweep decoder: held-out results on SYNTHETIC sweeps

Table sha256 `eeffc957306b58c046ab13a16373e0d0c0999026f5700be50f5799e3942bff1d`; 22142 entries with code length >= 2; test split = 16481 entries (characters hashed out of the tuning split). Noise seeds 1..3, mean (min-max). Levels multiply the profile's spatial errors: low x0.5, mid x1, high x1.6; oracle = noiseless path through the exact code keys (the CEILING: characters sharing one code cannot all be first).

Analytic ceiling on the test split (exact code known, ties broken by weight): top-1 91.4, top-3 99.8, top-5 100.0.

## 1. Tuned defaults per profile, test split

| profile | level | top-1 | top-3 | top-5 | freq-weighted top-1 / top-5 |
|---|---|---|---|---|---|
| mouse | oracle | 88.2 | 99.3 | 99.9 | 97.8 / 100.0 |
| mouse | low | 86.2 (86.1-86.3) | 98.7 (98.6-98.8) | 99.8 (99.8-99.8) | 95.5 / 99.9 |
| mouse | mid | 81.5 (81.3-81.8) | 97.3 (97.2-97.4) | 99.2 (99.2-99.3) | 91.9 / 99.8 |
| mouse | high | 61.0 (60.7-61.2) | 83.7 (83.1-84.2) | 90.2 (89.8-90.5) | 66.8 / 88.3 |
| mouse | vhigh | 27.9 (27.4-28.3) | 47.0 (46.7-47.4) | 56.1 (55.7-56.3) | 32.5 / 54.4 |
| touchpad | oracle | 54.3 | 79.8 | 85.3 | 91.5 / 99.9 |
| touchpad | low | 48.3 (48.1-48.5) | 75.1 (75.0-75.2) | 82.0 (82.0-82.1) | 88.7 / 99.2 |
| touchpad | mid | 31.7 (31.2-32.1) | 57.6 (57.3-58.0) | 68.4 (68.1-68.7) | 78.3 / 94.7 |
| touchpad | high | 14.4 (14.3-14.5) | 29.6 (29.0-30.1) | 38.4 (37.8-38.7) | 50.2 / 69.0 |
| touchpad | vhigh | 4.5 (4.4-4.7) | 10.2 (10.2-10.3) | 13.9 (13.8-13.9) | 18.4 / 28.8 |
| finger | oracle | 74.2 | 93.8 | 97.5 | 95.8 / 99.9 |
| finger | low | 63.9 (63.7-64.0) | 86.1 (85.9-86.3) | 92.1 (91.9-92.3) | 92.0 / 99.1 |
| finger | mid | 39.8 (39.4-40.0) | 64.5 (64.1-64.8) | 74.7 (74.6-74.9) | 76.0 / 93.4 |
| finger | high | 15.3 (15.3-15.4) | 30.4 (30.2-30.8) | 38.8 (38.4-39.2) | 40.8 / 61.9 |
| finger | vhigh | 4.5 (4.4-4.7) | 10.0 (9.7-10.2) | 14.0 (13.5-14.3) | 15.7 / 25.8 |
| touchscreen | oracle | 80.6 | 97.2 | 99.1 | 96.6 / 100.0 |
| touchscreen | low | 76.7 (76.6-76.9) | 95.7 (95.7-95.8) | 98.6 (98.6-98.6) | 95.3 / 99.9 |
| touchscreen | mid | 62.1 (62.0-62.3) | 86.5 (86.2-86.8) | 93.0 (92.9-93.2) | 87.4 / 97.9 |
| touchscreen | high | 32.4 (32.2-32.6) | 53.9 (53.9-54.1) | 64.0 (63.9-64.2) | 50.2 / 75.1 |
| touchscreen | vhigh | 10.2 (10.0-10.3) | 20.4 (20.0-20.6) | 26.7 (26.4-27.0) | 20.0 / 32.3 |

## 2. By code length and code type at level mid (top-1 / top-5, %)

| profile | all | len2 | len3 | len4 | len5 | repeat | shared | clean |
|---|---|---|---|---|---|---|---|---|
| mouse | 82 / 99 | 53 / 98 | 71 / 99 | 82 / 99 | 88 / 99 | 77 / 98 | 40 / 98 | 89 / 100 |
| mouse oracle | 88 / 100 | 59 / 99 | 80 / 100 | 89 / 100 | 93 / 100 | 87 / 100 | 44 / 100 | 95 / 100 |
| touchpad | 32 / 68 | 25 / 64 | 24 / 63 | 31 / 69 | 37 / 70 | 18 / 54 | 18 / 58 | 37 / 73 |
| touchpad oracle | 54 / 85 | 42 / 84 | 45 / 83 | 55 / 86 | 57 / 85 | 41 / 84 | 31 / 77 | 61 / 87 |
| finger | 40 / 75 | 32 / 73 | 33 / 72 | 39 / 75 | 44 / 76 | 29 / 59 | 22 / 66 | 45 / 79 |
| finger oracle | 74 / 97 | 53 / 93 | 64 / 96 | 75 / 98 | 79 / 98 | 76 / 98 | 39 / 92 | 79 / 98 |
| touchscreen | 62 / 93 | 42 / 87 | 52 / 90 | 62 / 93 | 69 / 95 | 45 / 86 | 31 / 87 | 70 / 95 |
| touchscreen oracle | 81 / 99 | 53 / 96 | 69 / 98 | 81 / 99 | 87 / 100 | 74 / 99 | 41 / 97 | 88 / 100 |

Row sizes (n): all=16481, len2=445, len3=2274, len4=8320, len5=5442, repeat=2772, shared=2064, clean=11979

## 3. Noise sweep (top-1 / top-5, %), tuned config of the same profile

| profile | k=0.25 | k=0.5 | k=1 | k=1.6 | k=2.5 |
|---|---|---|---|---|---|
| mouse | 86 / 100 | 86 / 100 | 81 / 99 | 60 / 90 | 28 / 56 |
| touchpad | 53 / 83 | 48 / 82 | 32 / 68 | 14 / 38 | 4 / 14 |
| finger | 68 / 94 | 63 / 92 | 40 / 74 | 15 / 39 | 5 / 15 |
| touchscreen | 78 / 99 | 76 / 99 | 61 / 93 | 32 / 63 | 10 / 27 |

## 4. Transfer: config tuned for ROW profile, noise of COLUMN profile, level mid (top-1 / top-5)

| tuned for \ noise | mouse | touchpad | finger | touchscreen |
|---|---|---|---|---|
| mouse | 81 / 99 | 55 / 86 | 49 / 82 | 68 / 95 |
| touchpad | 46 / 82 | 32 / 68 | 28 / 64 | 37 / 75 |
| finger | 64 / 92 | 44 / 78 | 40 / 74 | 53 / 86 |
| touchscreen | 74 / 98 | 49 / 82 | 45 / 79 | 61 / 93 |
| untuned SweepConfig() | 81 / 99 | 55 / 86 | 49 / 82 | 68 / 95 |

## 5. Ablations (one change at a time from the tuned config; level mid; 6000 test entries; top-1 / top-5 %, then (w = frequency-weighted top-1 / top-5). Unweighted top-1 cannot see the prior: ordering inside a group of characters sharing one code does not change how many entries are first)

| variant | mouse | finger |
|---|---|---|
| full | 80.8 / 99.1 (w 91.9 / 99.7) | 39.7 / 74.0 (w 75.5 / 92.9) |
| no shape channel | 80.7 / 99.1 (w 92.6 / 99.6) | 39.7 / 74.0 (w 75.5 / 92.9) |
| no location channel | 60.0 / 93.5 (w 82.3 / 96.5) | 7.1 / 29.3 (w 54.1 / 78.2) |
| no start/end term, flat alphas | 78.6 / 98.4 (w 90.9 / 98.9) | 31.9 / 67.5 (w 72.5 / 90.3) |
| no prior | 81.1 / 99.1 (w 75.1 / 99.6) | 48.5 / 82.5 (w 39.4 / 81.0) |
| repeat_mode=ignore (no dwell) | 76.1 / 98.6 (w 89.6 / 99.7) | 36.1 / 70.9 (w 73.4 / 92.1) |
| 2-key shape weight x1 (shape_short_scale=1) | 80.9 / 99.1 (w 91.9 / 99.7) | 39.7 / 74.0 (w 75.5 / 92.9) |
| 2-key shape weight x0 | 80.8 / 99.1 (w 91.3 / 99.7) | 39.7 / 74.0 (w 75.5 / 92.9) |
| cover_weight 4 | 80.9 / 99.1 (w 91.9 / 99.7) | 39.4 / 73.3 (w 75.2 / 93.0) |
| loc_tolerance 0.25 | 79.8 / 98.9 (w 90.7 / 99.7) | 36.6 / 71.7 (w 75.0 / 91.8) |
| N=16 | 80.9 / 99.1 (w 90.2 / 99.7) | 39.6 / 73.9 (w 75.2 / 92.9) |
| N=24 | 80.8 / 99.1 (w 91.9 / 99.7) | 39.7 / 74.0 (w 75.5 / 92.9) |
| N=32 | 81.0 / 99.1 (w 91.2 / 99.7) | 39.8 / 74.5 (w 75.0 / 93.5) |
| N=48 | 80.9 / 99.1 (w 91.2 / 99.7) | 40.2 / 74.6 (w 75.7 / 93.0) |
| N=64 | 80.9 / 99.1 (w 91.1 / 99.7) | 40.2 / 74.6 (w 75.7 / 93.0) |
| prune_radius 0.8 | 80.8 / 99.1 (w 92.1 / 99.6) | 40.6 / 74.5 (w 70.8 / 85.9) |
| prune_radius 1.0 | 80.8 / 99.1 (w 91.9 / 99.7) | 40.2 / 75.0 (w 75.6 / 92.6) |
| prune_radius 2.0 | 80.8 / 99.1 (w 91.9 / 99.7) | 39.6 / 73.6 (w 75.4 / 92.9) |
| no pruning (radius 99) | 80.8 / 99.1 (w 91.9 / 99.7) | 39.6 / 73.6 (w 75.4 / 92.9) |

## 5b. Stress test: large systematic per-stroke offset (sigma_bias 0.4 key widths; level mid; top-1 / top-5 %)

| variant | finger + bias | mouse + bias |
|---|---|---|
| full (tuned) | 21.3 / 48.9 | 45.2 / 72.6 |
| no shape channel | 21.3 / 48.9 | 41.8 / 69.3 |
| shape x3 | 21.3 / 48.9 | 49.9 / 76.8 |
| no location channel | 4.0 / 16.2 | 33.5 / 62.6 |

## 6. Repeated-letter codes ('hh'): effect of dwell behaviour (level mid; top-1 / top-5 on the `repeat` rows, %)

| profile | user dwells 100% | 80% | 0% (never) | 0% and decoder ignores dwell |
|---|---|---|---|---|
| mouse | 80 / 99 | 71 / 97 | 36 / 88 | 56 / 97 |
| finger | 34 / 66 | 29 / 58 | 4 / 23 | 23 / 64 |

## 7. Lexicon size (random character subsets; level mid; top-1 / top-5 %)

| entries | mouse | finger |
|---|---|---|
| 2213 | 97.0 / 100.0 | 75.8 / 97.5 |
| 5532 | 93.3 / 100.0 | 62.0 / 92.2 |
| 11062 | 89.4 / 99.9 | 52.6 / 85.3 |
| 22142 | 82.2 / 99.2 | 40.8 / 74.9 |

## 8. Layout robustness: phone-like layout (row pitch 1.3 key widths) for both simulator and decoder (top-1 / top-5 %)

| profile | mid | high |
|---|---|---|
| mouse | 82.9 / 99.4 | 67.5 / 94.5 |
| finger | 48.4 / 83.3 | 20.9 / 48.7 |

## 9. Latency, pure Python 3.12, one core (ms per decode, 300 mid-noise mouse paths)

| config | mean | p50 | p95 | max |
|---|---|---|---|---|
| bucket index (default), N=24 | 7.0 | 6.7 | 13.8 | 20.2 |
| full scan, no index | 8.8 | 8.5 | 15.5 | 21.4 |
| bucket index, N=16 | 5.0 | 4.8 | 10.0 | 14.3 |
| bucket index, prune_radius 1.0 | 2.7 | 2.4 | 5.4 | 7.3 |
| bucket index, N=48 | 12.5 | 12.1 | 24.7 | 36.4 |
| bucket index, prune_radius 2.5 | 50.8 | 53.1 | 78.9 | 93.4 |

Lexicon build (templates + index) 0.28 s one-time.
