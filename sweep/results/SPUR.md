# Spur / backtrack tolerance: before and after (SYNTHETIC sweeps)

Noise class `backtrack_prob`: at each interior waypoint the simulated path goes back toward the previous waypoint (70-100% of the way) before continuing, e.g. y-h-y-j-m-n-b-v-c for yhmbc. Rates: 0 (none), 0.15, 0.4 per interior waypoint, on top of the profile's normal noise at level mid. Before = `align_weight` 0; after = defaults (`align_weight` 2.49, `align_gate` 2.00, `align_ins` 0.42, `hit_radius` 0.58, rerank of the best 40). Held-out test characters (16481) and words.

## Characters (top-1 / top-5 / frequency-weighted top-1, %)

| profile | backtrack rate | before | after |
|---|---|---|---|
| mouse | 0.00 | 81.3 / 99.2 / 91.3 | 79.8 / 99.1 / 86.6 |
| mouse | 0.15 | 70.4 / 89.9 / 81.7 | 73.2 / 93.9 / 81.1 |
| mouse | 0.40 | 54.0 / 75.6 / 68.3 | 62.9 / 85.8 / 73.1 |
| touchpad | 0.00 | 55.5 / 86.4 / 58.9 | 51.6 / 82.6 / 55.2 |
| touchpad | 0.15 | 47.8 / 77.1 / 51.4 | 47.0 / 77.3 / 51.7 |
| touchpad | 0.40 | 36.2 / 63.2 / 41.6 | 39.7 / 69.1 / 46.5 |
| finger | 0.00 | 50.0 / 82.0 / 60.3 | 49.9 / 81.3 / 58.5 |
| finger | 0.15 | 43.4 / 74.3 / 49.4 | 46.0 / 76.6 / 53.1 |
| finger | 0.40 | 33.5 / 61.5 / 41.4 | 39.4 / 68.9 / 47.1 |

## The literal example (noiseless polylines through the keys, chars decoder)

| path | before: top-3 codes | after: top-3 codes |
|---|---|---|
| yhyjmnbvc | ytmbc yhmbc htmc | yhmbc ytmbc yjmbc |
| yhyhmbc | ytmbc htmc yhmbc | yhmbc ynmbc yrmbc |
| yuyjmnbc | ytmbc yujbc yjmbc | yujbc yjmbc ytmbc |
| yhmbc | yhmbc ynmbc yjmbc | yhmbc ynmbc yjmbc |
| yhjmnbvc | yhmbc yjmbc ynmbc | yhmbc yjmbc ymmbc |
| yhmnbvc | yhmbc ynmbc yjmbc | yhmbc ynmbc yjmbc |

## Words (243k words + chars; mixed continuous / dwell / lift boundaries; top-1 / top-5 %)

| profile | backtrack rate | before | after |
|---|---|---|---|
| mouse | 0.00 | 95.9 / 99.9 | 96.1 / 100.0 |
| mouse | 0.15 | 75.8 / 84.6 | 81.9 / 88.1 |
| mouse | 0.40 | 52.6 / 65.0 | 63.7 / 72.2 |
| finger | 0.00 | 76.6 / 91.1 | 78.1 / 91.9 |
| finger | 0.15 | 57.5 / 75.3 | 65.1 / 79.6 |
| finger | 0.40 | 41.6 / 57.1 | 48.8 / 64.6 |

## Latency (pure Python, one core, mean / p95 ms)

| decoder | before | after |
|---|---|---|
| single character | 7.1 / 14.2 | 10.5 / 17.8 |
| word (243k) | 11.5 / 17.6 | 21.2 / 31.5 |
