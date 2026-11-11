# Spur / backtrack tolerance: before and after (SYNTHETIC sweeps)

Noise class `backtrack_prob`: at each interior waypoint the simulated path goes back toward the previous waypoint (70-100% of the way) before continuing, e.g. y-h-y-j-m-n-b-v-c for yhmbc. Rates: 0 (none), 0.15, 0.4 per interior waypoint, on top of the profile's normal noise at level mid. Before = `align_weight` 0; after = defaults (`align_weight` 2.34, `align_gate` 0.66, `align_ins` 0.40, `hit_radius` 0.58, rerank of the best 40). Held-out test characters (16481) and words.

## Characters (top-1 / top-5 / frequency-weighted top-1, %)

| profile | backtrack rate | before | after |
|---|---|---|---|
| mouse | 0.00 | 81.3 / 99.2 / 91.3 | 81.1 / 99.2 / 88.3 |
| mouse | 0.15 | 70.4 / 89.9 / 81.7 | 73.4 / 93.3 / 82.4 |
| mouse | 0.40 | 54.0 / 75.6 / 68.3 | 61.1 / 84.1 / 72.1 |
| touchpad | 0.00 | 55.5 / 86.4 / 58.9 | 55.4 / 85.9 / 58.1 |
| touchpad | 0.15 | 47.8 / 77.1 / 51.4 | 49.7 / 79.5 / 52.8 |
| touchpad | 0.40 | 36.2 / 63.2 / 41.6 | 40.9 / 69.9 / 46.7 |
| finger | 0.00 | 50.0 / 82.0 / 60.3 | 52.7 / 83.8 / 59.8 |
| finger | 0.15 | 43.4 / 74.3 / 49.4 | 47.8 / 78.1 / 52.3 |
| finger | 0.40 | 33.5 / 61.5 / 41.4 | 39.9 / 69.0 / 45.5 |

## The literal example (noiseless polylines through the keys, chars decoder)

| path | before: top-3 codes | after: top-3 codes |
|---|---|---|
| yhyjmnbvc | ytmbc yhmbc htmc | yhmbc ytmbc yjmbc |
| yhyhmbc | ytmbc htmc yhmbc | yhmbc ynmbc ytmbc |
| yuyjmnbc | ytmbc yujbc yjmbc | yujbc ytmbc yjmbc |
| yhmbc | yhmbc ynmbc yjmbc | yhmbc ynmbc yjmbc |
| yhjmnbvc | yhmbc yjmbc ynmbc | yhmbc yjmbc ymmbc |
| yhmnbvc | yhmbc ynmbc yjmbc | yhmbc ynmbc yjmbc |

## Words (243k words + chars; mixed continuous / dwell / lift boundaries; top-1 / top-5 %)

| profile | backtrack rate | before | after |
|---|---|---|---|
| mouse | 0.00 | 95.9 / 99.9 | 95.6 / 99.9 |
| mouse | 0.15 | 75.8 / 84.6 | 80.8 / 88.3 |
| mouse | 0.40 | 52.6 / 65.0 | 62.7 / 71.9 |
| finger | 0.00 | 76.6 / 91.1 | 75.8 / 92.9 |
| finger | 0.15 | 57.5 / 75.3 | 63.5 / 81.3 |
| finger | 0.40 | 41.6 / 57.1 | 47.4 / 64.1 |

## Latency (pure Python, one core, mean / p95 ms)

| decoder | before | after |
|---|---|---|
| single character | 7.1 / 14.1 | 10.6 / 17.7 |
| word (243k) | 11.8 / 18.6 | 21.5 / 31.8 |
