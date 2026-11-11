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
| touchpad | oracle | 88.3 | 99.3 | 99.9 | 97.8 / 100.0 |
| touchpad | low | 83.1 (83.0-83.1) | 97.9 (97.7-98.0) | 99.5 (99.5-99.6) | 90.4 / 99.8 |
| touchpad | mid | 55.6 (55.5-55.7) | 79.1 (78.8-79.6) | 86.6 (86.2-86.9) | 61.7 / 85.7 |
| touchpad | high | 22.6 (22.5-22.7) | 39.0 (38.7-39.3) | 47.5 (47.2-47.9) | 26.0 / 47.8 |
| touchpad | vhigh | 6.0 (5.9-6.0) | 12.2 (12.0-12.3) | 16.1 (15.9-16.2) | 7.6 / 16.6 |
| finger | oracle | 80.0 | 96.7 | 98.9 | 96.6 / 99.8 |
| finger | low | 68.2 (68.1-68.2) | 88.6 (88.5-88.8) | 92.8 (92.7-93.0) | 90.4 / 96.1 |
| finger | mid | 42.0 (41.9-42.2) | 66.3 (66.1-66.7) | 75.9 (75.8-76.1) | 71.9 / 89.1 |
| finger | high | 16.0 (15.9-16.0) | 30.8 (30.8-30.9) | 39.0 (38.6-39.2) | 32.2 / 53.5 |
| finger | vhigh | 4.6 (4.6-4.7) | 10.2 (9.8-10.4) | 14.0 (13.6-14.3) | 13.9 / 23.6 |
| touchscreen | oracle | 87.3 | 99.2 | 99.9 | 97.6 / 100.0 |
| touchscreen | low | 83.9 (83.8-84.0) | 98.2 (98.1-98.2) | 99.6 (99.6-99.6) | 94.6 / 99.9 |
| touchscreen | mid | 67.7 (67.6-67.9) | 89.3 (88.9-89.8) | 94.6 (94.3-94.9) | 79.2 / 95.7 |
| touchscreen | high | 35.2 (35.0-35.3) | 56.8 (56.7-56.9) | 66.3 (66.2-66.4) | 40.2 / 65.5 |
| touchscreen | vhigh | 11.1 (11.0-11.2) | 21.7 (21.3-22.0) | 28.1 (27.7-28.4) | 14.1 / 29.2 |

## 2. By code length and code type at level mid (top-1 / top-5, %)

| profile | all | len2 | len3 | len4 | len5 | repeat | shared | clean |
|---|---|---|---|---|---|---|---|---|
| mouse | 82 / 99 | 53 / 98 | 71 / 99 | 82 / 99 | 88 / 99 | 77 / 98 | 40 / 98 | 89 / 100 |
| mouse oracle | 88 / 100 | 59 / 99 | 80 / 100 | 89 / 100 | 93 / 100 | 87 / 100 | 44 / 100 | 95 / 100 |
| touchpad | 56 / 87 | 30 / 73 | 43 / 80 | 54 / 86 | 66 / 91 | 48 / 80 | 26 / 80 | 62 / 89 |
| touchpad oracle | 88 / 100 | 59 / 99 | 80 / 100 | 89 / 100 | 93 / 100 | 88 / 100 | 44 / 100 | 95 / 100 |
| finger | 42 / 76 | 32 / 72 | 35 / 73 | 42 / 76 | 46 / 77 | 39 / 75 | 22 / 69 | 45 / 77 |
| finger oracle | 80 / 99 | 54 / 96 | 70 / 98 | 81 / 99 | 85 / 99 | 82 / 98 | 41 / 96 | 85 / 99 |
| touchscreen | 68 / 95 | 45 / 89 | 58 / 93 | 67 / 94 | 74 / 96 | 49 / 85 | 33 / 91 | 77 / 97 |
| touchscreen oracle | 87 / 100 | 57 / 99 | 78 / 100 | 88 / 100 | 93 / 100 | 87 / 100 | 43 / 99 | 94 / 100 |

Row sizes (n): all=16481, len2=445, len3=2274, len4=8320, len5=5442, repeat=2772, shared=2064, clean=11979

## 3. Noise sweep (top-1 / top-5, %), tuned config of the same profile

| profile | k=0.25 | k=0.5 | k=1 | k=1.6 | k=2.5 |
|---|---|---|---|---|---|
| mouse | 86 / 100 | 86 / 100 | 81 / 99 | 60 / 90 | 28 / 56 |
| touchpad | 85 / 100 | 83 / 99 | 55 / 86 | 22 / 47 | 6 / 16 |
| finger | 72 / 94 | 67 / 93 | 42 / 77 | 15 / 38 | 5 / 15 |
| touchscreen | 85 / 100 | 83 / 99 | 67 / 94 | 33 / 66 | 11 / 28 |

## 4. Transfer: config tuned for ROW profile, noise of COLUMN profile, level mid (top-1 / top-5)

| tuned for \ noise | mouse | touchpad | finger | touchscreen |
|---|---|---|---|---|
| mouse | 81 / 99 | 55 / 86 | 49 / 82 | 68 / 95 |
| touchpad | 81 / 99 | 55 / 86 | 48 / 81 | 67 / 94 |
| finger | 66 / 90 | 41 / 71 | 42 / 77 | 56 / 88 |
| touchscreen | 81 / 99 | 54 / 84 | 48 / 81 | 67 / 94 |
| untuned SweepConfig() | 81 / 99 | 55 / 86 | 49 / 82 | 68 / 95 |

## 5. Ablations (one change at a time from the tuned config; level mid; 6000 test entries; top-1 / top-5 %, then (w = frequency-weighted top-1 / top-5). Unweighted top-1 cannot see the prior: ordering inside a group of characters sharing one code does not change how many entries are first)

| variant | mouse | finger |
|---|---|---|
| full | 80.8 / 99.1 (w 91.9 / 99.7) | 41.6 / 76.6 (w 64.7 / 83.3) |
| no shape channel | 80.7 / 99.1 (w 92.6 / 99.6) | 41.6 / 76.6 (w 64.7 / 83.3) |
| no location channel | 60.0 / 93.5 (w 82.3 / 96.5) | 8.6 / 33.2 (w 42.8 / 69.3) |
| no start/end term, flat alphas | 78.6 / 98.4 (w 90.9 / 98.9) | 35.1 / 70.3 (w 60.9 / 82.2) |
| no prior | 81.1 / 99.1 (w 75.1 / 99.6) | 46.9 / 80.2 (w 35.0 / 72.9) |
| repeat_mode=ignore (no dwell) | 76.1 / 98.6 (w 89.6 / 99.7) | 39.1 / 74.8 (w 70.9 / 89.8) |
| 2-key shape weight x1 (shape_short_scale=1) | 80.9 / 99.1 (w 91.9 / 99.7) | 41.6 / 76.6 (w 64.7 / 83.3) |
| 2-key shape weight x0 | 80.8 / 99.1 (w 91.3 / 99.7) | 41.6 / 76.6 (w 64.7 / 83.3) |
| cover_weight 4 | 80.9 / 99.1 (w 91.9 / 99.7) | 41.3 / 76.3 (w 64.3 / 82.8) |
| loc_tolerance 0.25 | 79.8 / 98.9 (w 90.7 / 99.7) | 38.5 / 73.8 (w 65.4 / 82.6) |
| N=16 | 80.9 / 99.1 (w 90.2 / 99.7) | 41.0 / 75.9 (w 64.5 / 82.9) |
| N=24 | 80.8 / 99.1 (w 91.9 / 99.7) | 41.6 / 76.6 (w 64.7 / 83.3) |
| N=32 | 81.0 / 99.1 (w 91.2 / 99.7) | 41.5 / 76.8 (w 64.6 / 84.0) |
| N=48 | 80.9 / 99.1 (w 91.2 / 99.7) | 42.0 / 76.7 (w 64.8 / 84.0) |
| N=64 | 80.9 / 99.1 (w 91.1 / 99.7) | 42.1 / 77.0 (w 64.9 / 84.1) |
| prune_radius 0.8 | 80.8 / 99.1 (w 92.1 / 99.6) | 42.1 / 75.9 (w 62.2 / 77.6) |
| prune_radius 1.0 | 80.8 / 99.1 (w 91.9 / 99.7) | 42.0 / 77.1 (w 64.8 / 84.1) |
| prune_radius 2.0 | 80.8 / 99.1 (w 91.9 / 99.7) | 41.6 / 76.1 (w 64.7 / 82.8) |
| no pruning (radius 99) | 80.8 / 99.1 (w 91.9 / 99.7) | 41.6 / 76.1 (w 64.7 / 82.8) |

## 5b. Stress test: large systematic per-stroke offset (sigma_bias 0.4 key widths; level mid; top-1 / top-5 %)

| variant | finger + bias | mouse + bias |
|---|---|---|
| full (tuned) | 22.5 / 49.2 | 45.2 / 72.6 |
| no shape channel | 22.5 / 49.2 | 41.8 / 69.3 |
| shape x3 | 22.5 / 49.2 | 49.9 / 76.8 |
| no location channel | 4.5 / 18.0 | 33.5 / 62.6 |

## 6. Repeated-letter codes ('hh'): effect of dwell behaviour (level mid; top-1 / top-5 on the `repeat` rows, %)

| profile | user dwells 100% | 80% | 0% (never) | 0% and decoder ignores dwell |
|---|---|---|---|---|
| mouse | 80 / 99 | 71 / 97 | 36 / 88 | 56 / 97 |
| finger | 43 / 81 | 37 / 76 | 14 / 51 | 26 / 68 |

## 7. Lexicon size (random character subsets; level mid; top-1 / top-5 %)

| entries | mouse | finger |
|---|---|---|
| 2213 | 97.0 / 100.0 | 77.1 / 96.7 |
| 5532 | 93.3 / 100.0 | 63.4 / 90.8 |
| 11062 | 89.4 / 99.9 | 54.4 / 85.5 |
| 22142 | 82.2 / 99.2 | 43.2 / 75.7 |

## 8. Layout robustness: phone-like layout (row pitch 1.3 key widths) for both simulator and decoder (top-1 / top-5 %)

| profile | mid | high |
|---|---|---|
| mouse | 82.9 / 99.4 | 67.5 / 94.5 |
| finger | 50.8 / 84.5 | 21.7 / 48.1 |

## 9. Latency, pure Python 3.12, one core (ms per decode, 300 mid-noise mouse paths)

| config | mean | p50 | p95 | max |
|---|---|---|---|---|
| bucket index (default), N=24 | 7.0 | 6.8 | 14.0 | 20.4 |
| full scan, no index | 8.8 | 8.6 | 15.6 | 21.7 |
| bucket index, N=16 | 5.0 | 4.8 | 9.9 | 14.4 |
| bucket index, prune_radius 1.0 | 2.7 | 2.5 | 5.4 | 7.3 |
| bucket index, N=48 | 12.5 | 12.1 | 24.8 | 37.2 |
| bucket index, prune_radius 2.5 | 50.7 | 53.2 | 79.0 | 92.5 |

Lexicon build (templates + index) 0.30 s one-time.
