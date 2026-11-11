# Word-level sweep: results on SYNTHETIC sweeps

Table sha256 `eeffc957306b58c046ab13a16373e0d0c0999026f5700be50f5799e3942bff1d`. Words = essay.txt entries (word<TAB>freq) of 2-4 characters whose characters all have a Cangjie 3 code (main = shortest code). Test words (hash split disjoint from tuning), stratified by length (2/3/4) x frequency band (1k-3k, 3k-10k, >=10k), 100 per cell. Boundary modes mixed: 50% continuous (one stroke, nothing marks the boundary), 25% dwell on the boundary key, 25% finger lift. Candidates: words with freq >= 100 plus every single character (words+chars).

## 1. Word accuracy (tuned defaults, words + chars candidates)

| profile | level | words top-1 | top-3 | top-5 | chars right in top-1 (per position) | continuous | dwell | lift | len 2 | len 3 | len 4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mouse | low | 97.8 | 99.8 | 100.0 | 98.6 | 95.9 | 100.0 | 99.5 | 96.7 | 98.0 | 98.8 |
| mouse | mid | 95.9 | 99.5 | 99.9 | 97.4 | 93.8 | 97.3 | 99.0 | 93.3 | 96.7 | 98.0 |
| mouse | high | 86.0 | 94.6 | 96.4 | 90.4 | 82.0 | 86.6 | 93.9 | 76.3 | 88.7 | 94.1 |
| touchpad | low | 97.2 | 99.8 | 100.0 | 98.2 | 95.4 | 98.7 | 99.5 | 95.0 | 98.3 | 98.4 |
| touchpad | mid | 84.2 | 93.2 | 95.4 | 88.8 | 81.3 | 83.9 | 90.9 | 74.7 | 86.0 | 93.3 |
| touchpad | high | 47.5 | 62.0 | 66.9 | 55.2 | 43.1 | 49.1 | 55.3 | 33.0 | 53.3 | 57.6 |
| finger | low | 95.8 | 99.9 | 100.0 | 97.4 | 94.2 | 96.4 | 98.5 | 92.7 | 96.3 | 98.8 |
| finger | mid | 76.6 | 87.8 | 91.1 | 82.2 | 72.4 | 75.9 | 86.8 | 67.0 | 79.3 | 84.7 |
| finger | high | 37.3 | 49.5 | 55.4 | 46.0 | 34.6 | 32.6 | 48.7 | 23.0 | 43.3 | 47.1 |
| touchscreen | low | 97.2 | 100.0 | 100.0 | 98.3 | 94.7 | 100.0 | 99.5 | 95.3 | 97.7 | 98.8 |
| touchscreen | mid | 89.2 | 96.3 | 97.7 | 93.0 | 87.1 | 87.9 | 95.4 | 83.0 | 91.3 | 94.1 |
| touchscreen | high | 64.2 | 76.8 | 81.2 | 72.1 | 60.4 | 60.7 | 76.6 | 49.3 | 71.0 | 73.7 |

Frequency bands (top-1 / top-5, %), mouse and finger at mid:

| profile | 1k-3k | 3k-10k | >=10k |
|---|---|---|---|
| mouse | 94.0 / 100.0 | 97.0 / 100.0 | 96.9 / 99.6 |
| finger | 76.0 / 90.7 | 79.3 / 90.3 | 74.1 / 92.5 |

## 2. Characters vs words, and what adding words does to single-character sweeps

| candidates | word sweeps top-1 / top-5 (mouse mid) | word sweeps (finger mid) | single-character sweeps top-1 / top-5 (mouse mid) | (finger mid) |
|---|---|---|---|---|
| words only | 97.0 / 99.9 | 77.9 / 92.0 | n/a | n/a |
| chars only | n/a | n/a | 82.1 / 98.9 | 49.9 / 78.8 |
| words + chars | 95.9 / 99.9 | 76.6 / 91.1 | 81.0 / 98.6 | 46.1 / 73.9 |

## 3. Lexicon size (same test words, all with freq >= 1000; candidate words = essay words with freq >= threshold, plus chars)

| min freq | words in lexicon | mouse mid top-1 / top-5 | finger mid top-1 / top-5 | mouse high | finger high |
|---|---|---|---|---|---|
| 3000 | 9869 | 98.6 / 100.0 | 90.1 / 97.5 | 95.5 / 99.3 | 60.2 / 75.0 |
| 1000 | 31576 | 97.5 / 100.0 | 85.6 / 95.9 | 91.9 / 98.4 | 52.0 / 67.7 |
| 300 | 191283 | 96.1 / 99.9 | 78.5 / 91.8 | 86.8 / 96.8 | 39.8 / 57.1 |
| 100 | 242991 | 95.9 / 99.9 | 76.6 / 91.1 | 86.0 / 96.4 | 37.3 / 55.4 |
| 30 | 290439 | 95.8 / 99.9 | 75.2 / 90.8 | 85.4 / 96.1 | 35.7 / 53.3 |

## 4. The two owner cases

Exact literal paths (key sequences from the brief, space = boundary), top-5 and score:

| target | boundary | top-5 |
|---|---|---|
| 顏值 (`yhmnbvc ojhbnm`) | continuous | 顏值 0.2, 逕直 -23.0, 炭疽 -23.3, 途徑 -25.6, 虧虛 -26.3 |
| 顏值 (`yhmnbvc ojhbnm`) | lift | 顏值 0.2, 炭疽 -26.8, 文學史上 -35.4, 遼寧 -37.6, 途徑 -37.8 |
| 顏值 (`yhmnbvc ojhbnm`) | dwell | 顏值 0.4, 逕直 -23.0, 炭疽 -23.3, 途徑 -25.6, 虧虛 -26.3 |
| 頻率 (`yhjmnbvc yuiokjhj`) | continuous | 頻率 -21.2, 卡榫 -25.1, 某品牌 -28.1, 肯幹 -29.2, 頻密 -29.5 |
| 頻率 (`yhjmnbvc yuiokjhj`) | lift | 頻率 -21.2, 頻密 -32.6, 某品牌 -34.7, 這步 -35.1, 鞍革 -35.8 |
| 頻率 (`yhjmnbvc yuiokjhj`) | dwell | 頻率 -21.1, 卡榫 -25.1, 某品牌 -28.1, 肯幹 -29.2, 頻密 -29.3 |

1000 noisy variants each (seeded). A: generated from the intended codes (yhmbc+ojbm, yhmbc+yioj) with the simulator; B: the owner's literal slip path with a slow hand wobble added (amplitude in key widths, per-sample noise 0.02). Top-1 / top-5 %.

| target | variant | profile / level | continuous | lift | dwell |
|---|---|---|---|---|---|
| 顏值 | A generated | mouse / mid | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| 顏值 | A generated | mouse / high | 96.7 / 99.6 | 97.8 / 99.7 | 97.0 / 99.6 |
| 顏值 | A generated | finger / mid | 91.4 / 98.4 | 94.0 / 99.1 | 90.5 / 98.0 |
| 顏值 | A generated | touchscreen / mid | 98.5 / 100.0 | 99.5 / 100.0 | 99.4 / 99.9 |
| 顏值 | B literal + wobble 0.1 key widths | - | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| 顏值 | B literal + wobble 0.2 key widths | - | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| 顏值 | B literal + wobble 0.4 key widths | - | 100.0 / 100.0 | 100.0 / 100.0 | 99.7 / 99.9 |
| 頻率 | A generated | mouse / mid | 99.2 / 100.0 | 100.0 / 100.0 | 99.5 / 100.0 |
| 頻率 | A generated | mouse / high | 88.0 / 97.1 | 96.2 / 99.2 | 90.0 / 97.3 |
| 頻率 | A generated | finger / mid | 84.2 / 95.4 | 90.6 / 96.8 | 84.1 / 93.7 |
| 頻率 | A generated | touchscreen / mid | 95.8 / 99.7 | 99.6 / 100.0 | 97.6 / 99.8 |
| 頻率 | B literal + wobble 0.1 key widths | - | 80.6 / 99.8 | 99.1 / 100.0 | 100.0 / 100.0 |
| 頻率 | B literal + wobble 0.2 key widths | - | 65.6 / 94.1 | 88.6 / 99.9 | 95.3 / 100.0 |
| 頻率 | B literal + wobble 0.4 key widths | - | 48.0 / 71.4 | 71.0 / 92.1 | 73.7 / 91.8 |

## 5. Latency, pure Python 3.12, one core (ms per decode; mid-noise mouse word sweeps)

| lexicon | mean | p50 | p95 | max |
|---|---|---|---|---|
| words >= 1000 (34576) | 6.6 | 6.6 | 8.4 | 9.2 |
| words >= 100 (242991) | 11.4 | 11.3 | 18.2 | 25.6 |

Build: 2.4 s, 257125 templates (242991 words); peak RSS of this process 373 MB (includes the table and lists; the Python object overhead is far larger than a Kotlin float array would be).

## 6. Best per-character segmentation (no word lexicon, DP over split points, single-character decoder)

| profile / level | boundary | exact text match | right number of characters | ms per call (mean) |
|---|---|---|---|---|
| mouse / mid | continuous | 0.8 | 59.3 | 566 |
| mouse / mid | lift | 61.0 | 76.4 | 201 |
| mouse / mid | dwell | 0.0 | 62.6 | 947 |
| finger / mid | continuous | 0.8 | 57.7 | 895 |
| finger / mid | lift | 21.1 | 83.7 | 319 |
| finger / mid | dwell | 0.0 | 57.7 | 908 |
