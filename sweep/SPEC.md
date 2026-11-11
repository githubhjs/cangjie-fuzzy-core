# Sweep：倉頡三代「滑行輸入」解碼器規格 / Sweep decoder for Cangjie 3

## 摘要 / Summary

**中文（繁體）**

- 使用者在鍵盤上滑過字母鍵（手機用手指，電腦用**滑鼠拖曳**畫出來的螢幕鍵盤；觸控板、觸控螢幕視為滑鼠的變體），**一次滑行 = 一個字**。解碼器輸入是一串 `(x, y, t_ms)`，輸出是依分數排序的候選字。
- 做法是 SHARK2（Kristensson & Zhai 2004）的模板比對，改成適合倉頡的封閉碼表：每個碼（2–5 碼，約 1.9 萬個不同的連續字母去重後模板）是「穿過各鍵中心的折線」；輸入與模板都重取樣成 N 點；**形狀通道 + 位置通道 + 起訖點**合成高斯對數似然，再加碼表字頻的對數先驗；先用「起點鍵、終點鍵」的索引砍掉大部分候選。
- **連續重複的字母（`hh`、`aa`）在路徑上看不出來**，所以用**停留（dwell）**判斷：在某個鍵上幾乎不動超過約 250 ms = 該鍵重複。滑鼠與觸控板靜止時不會送事件，所以停留以「下一個事件的時間戳」計算。
- **全部數字都是合成軌跡（simulate.py）的結果，不是真人資料。** 雜訊參數是假設，沒有實測。真人手指、滑鼠資料的驗證**還沒做**。
- **整詞滑行**（一筆跨 2-4 字，可連續、或在字界停留／抬起）：詞模板 = 各字主碼串成一條折線，不假設字界；見第 10 節。「顏值」「頻率」兩個例子都排第一。
- 合成軌跡上的結果（測試集 = 沒用來調參的字）：滑鼠中等雜訊單字 top-1 81.5% / top-5 99.2%（上限 91.4% / 100%），手指中等雜訊 42.0% / 75.9%；整詞（24.3 萬詞）滑鼠 95.9% / 99.9%、手指 76.6% / 91.1%。純 Python 單字一次解碼平均 7 ms、整詞平均 11 ms；Kotlin 移植依此規格與 `vectors/vectors.json` 對照。

**English**

- A sweep is one finger or mouse stroke over the letter keys = one character. Input `(x, y, t_ms)` samples in key-width units (platform neutral: finger on a phone, **mouse drag on a drawn on-screen keyboard on desktop**; touchpad and touch screen behave as mouse variants). Output: ranked characters.
- Method: SHARK2-style template matching (Kristensson & Zhai, UIST 2004) specialised to a closed lexicon of short codes: template = polyline through the key centres of the code with repeats collapsed; both resampled to N points; shape channel + location channel + start/end term combined as Gaussian log-likelihoods plus a log-weight prior; candidates pre-filtered by a (first key, last key) index.
- Headline numbers on synthetic strokes (held-out characters): single character, mouse mid noise top-1 81.5 / top-5 99.2 (ceiling 91.4 / 100), finger mid 42.0 / 75.9; words (243k) mouse mid 95.9 / 99.9, finger mid 76.6 / 91.1. Pure Python: 7 ms per character, 11 ms per word (mean).
- **Word-level sweeps** (one stroke over 2-4 characters, continuous or with a dwell/lift at the boundaries): the word template is the concatenated main codes; no boundary is assumed; section 10. Both owner cases (顏值, 頻率) rank first.
- Repeated letters (`hh`) are invisible in a path; they are decided by **dwell** (nearly still on a key for ~250 ms). Mouse and touchpad send no events while still, so dwell is measured from the next event's timestamp.
- **All numbers below come from synthetic strokes. The noise levels are assumptions, not measurements. Real finger and mouse data have NOT been used.**

---

## 1. 介面契約 / Interface contract (platform neutral)

```
decode(points, lexicon, layout, config) -> [(char, code, score)]   best first, one row per character
points : list of (x, y, t_ms), time order, >= 1 sample, from pointer-down to pointer-up of ONE sweep
         x, y in KEY-WIDTH units of `layout` (default: core.layout.qwerty_pc(), ANSI QWERTY, row pitch 1.0)
lexicon: entries (code, char, weight) with len(code) >= 2   (single-letter codes are taps, not sweeps)
```

- Pixels to key widths: `layout_from_rects(rects)` gives the key centres in key widths and the key width in pixels (median rectangle width); divide pixel coordinates by it (`to_key_units`). The same parameters then mean the same on every screen size and keyboard.
- One sweep = pointer down ... pointer up. Lifting ends the sweep. The caller supplies the layout; there is no hidden state.
- The decoder is deterministic: same input gives the same output. Ties: score, then code, then char (ascending).
- Time is used **only** for dwell. Everything else is arc-length based, so uneven or low sampling rates are fine, provided the stream contains the true start and end points.

## 2. 演算法（精確）/ Algorithm (exact; reference = `decoder.py`)

**Offline, once per lexicon and layout**

1. `collapse(code)`: drop consecutive duplicate letters (`aab -> ab`, `hh -> h`). Entries with the same collapsed code share one template.
2. Template vertices `V = [center(k) for k in collapsed]`; `T = resample(V, N)`; template centroid `(cx, cy)`; `size = max(bbox width, bbox height)` of `T`; `nseg = len(collapsed) - 1`; first/last key.
3. Per entry: `R = repeat_positions(code)` = set of indices into the collapsed code whose letter is repeated in `code` (`abb -> {1}`, `aabb -> {0, 1}`; counts beyond 2 are not distinguished).
4. Bucket index: `(first_key, last_key) -> [templates]`.

**Resample(P, N)** (used for both input and templates): cumulative arc length `c_i`; target `d_i = i * total / (N-1)`; linear interpolation on the segment containing `d_i`; zero total length (or a single point) gives N copies of the first point.

**Online, per sweep**

1. `u = resample(points, N)`. `(sx, sy) = u[0]`, `(ex, ey) = u[N-1]`. `usize = max(bbox width, bbox height)` of `u`; `uc` = `u` minus its centroid.
2. Candidate templates: those whose first key centre is within `prune_radius` of `(sx, sy)` and last key centre within `prune_radius` of `(ex, ey)` (index lookup over key pairs). If none, retry with `2 * prune_radius`, then with all templates. (Absolute positions, not SHARK2's normalized ones: a closed lexicon on a fixed keyboard makes absolute start/end keys the most reliable evidence.)
3. Dwell events (only if `repeat_mode = "dwell"` and more than 2 samples): scan `i`; extend `j` while the sample is within `dwell_radius` of sample `i`; duration = `t[j]` (first sample after the run, or `t[j-1]` if the path ends in the run) `- t[i]`; if `>= dwell_ms` it is a dwell at the run's mean position, and scanning resumes at `j`, else at `i+1`.
4. For each candidate template `t` (with `x_*` all in key widths squared):
   - location: `x_L = sum_i alpha_i * |u_i - T_i|^2`, `alpha_i` proportional to `1 + (end_alpha - 1) * |2i/(N-1) - 1|`, normalised to sum 1 (lowest in the middle, `end_alpha` times heavier at both ends; the SHARK2 location channel, simplified: point-to-point, squared). With `loc_tolerance > 0`, use `max(0, |u_i - T_i| - tol)^2`.
   - start/end: `x_E = ( |u_0 - T_0|^2 + |u_{N-1} - T_{N-1}|^2 ) / 2`.
   - shape (only if `nseg >= 1` and both sizes > 1e-9): `s = t.size / usize`; `x_S = mean_i | s * uc_i - (T_i - T_centroid) |^2` (translation free, input rescaled to the template's size so the distance is in key widths; SHARK2 proportional matching). Weight `shape_weight`, times `shape_short_scale` if `nseg == 1`; for `nseg == 0` the weight is `shape_weight * shape_single_scale` (default 0).
   - cover (optional): `x_C = mean over template vertices v of ( min_i |u_i - v|^2 )`.
   - base score `= -(w_S x_S + w_L x_L + w_E x_E + w_C x_C)`.
   - dwell set `D`: for each dwell, the index of the nearest template vertex within `dwell_assign_radius` (ties go to the later vertex); unassigned dwells are ignored.
5. For each entry `(code, char, weight)` of the template: `score = base + prior_weight * ln(weight + prior_floor) - repeat_miss_penalty * |R \ D| - dwell_extra_penalty * |D \ R|`. (Second and third terms: a repeated letter without a dwell, and a dwell on a key that is not repeated.)
6. Per character keep the best score (tie: smaller code). Sort by `(-score, code, char)`; return `top_k`.

Why not SHARK2 as published: its channels' distances are converted to Gaussian probabilities and multiplied (eq. 7-9); here the same Gaussian assumption is used directly in the log domain with per-channel weights (= 1/(2 sigma^2)), which is what the tuner sets. SHARK2's "tunnel" location distance and its speed-dependent channel weighting are not implemented (the tunnel is approximated by `loc_tolerance` and `cover_weight`; speed weighting is not used because sweeps here are short and mostly visually guided).

## 2b. 迴旋／折返容錯 / Spur and backtrack tolerance (key-sequence alignment rerank)

**Problem (owner example).** The slip path `y h y j m n b v c` for 顏 (`yhmbc`) went to a wrong code first (`ytmbc` 顱) because the extra `y h y` out-and-back lengthens the path and shifts the equidistant resampling, so the location channel prefers a code whose shape happens to fit the shifted points. Paths without the backtrack were fine.

**Stage (after the normal scoring, applied to the best `align_top` candidates; `align_weight` = 0 switches it off):**

1. `hits` = keys the path touches, in order, repeats collapsed: walk the path in steps of at most 0.15 key widths (linear interpolation between samples, so fast sparse strokes do not skip keys); a point touches the nearest key if within `hit_radius` of its centre.
2. `alignCost(codeKeys, hits)` = edit distance with no substitution: `D[i][j] = min(D[i-1][j] + miss, D[i][j-1] + ins, D[i-1][j-1] if codeKeys[i-1] == hits[j-1])`, `D[0][j] = j * ins`, `D[i][0] = i * miss`. A code key that is never touched costs `align_miss` (1.0); a touched key the code does not need costs `align_ins` (0.40): extra touches, spurs and backtracks are cheap, missing keys are expensive.
3. `excess = max(0, alignCost(code, hits) - alignCost(code, hitsOfIdealPath(code)))`, where `hitsOfIdealPath` = `hits` of the polyline through the code's key centres (cached per code): a perfect straight sweep also touches the keys in between and must score 0, so a clean sweep is unchanged.
4. `revisits = len(hits) - len(distinct keys in hits)` (a key touched again after leaving it: backtrack evidence); a property of the PATH, not of the candidate.
5. For each reranked candidate: `geo` = the geometry part of its score (`-(shape + location + start/end + cover terms)`, i.e. the score without prior and dwell terms); `score' = score - geo + geo / (1 + align_gate * revisits) - align_weight * excess`. Geometry is trusted less when the path doubled back, and a candidate whose keys the path really touched in order is preferred. Candidates below `align_top` keep their order after the reranked ones. Words: same, with the template's key string and `align_top` 25.

Defaults (tuned on train characters by `tune_align.py`: mouse and finger at backtrack rates 0 / 0.15 / 0.4, clean scenarios counted double; the same values are used for characters, words and all profiles): `align_weight` 2.34, `align_gate` 0.66, `align_ins` 0.40, `align_miss` 1.0 (fixed), `hit_radius` 0.58, `align_top` 40 (chars) / 25 (words).

**Evidence (synthetic; `results/SPUR.md`; held-out characters and words, level mid; top-1 / top-5 %, before -> after):**

| | rate 0 | rate 0.15 | rate 0.4 |
|---|---|---|---|
| char, mouse | 81.3 / 99.2 -> 81.1 / 99.2 | 70.4 / 89.9 -> 73.4 / 93.3 | 54.0 / 75.6 -> 61.1 / 84.1 |
| char, finger | 50.0 / 82.0 -> 52.7 / 83.8 | 43.4 / 74.3 -> 47.8 / 78.1 | 33.5 / 61.5 -> 39.9 / 69.0 |
| word, mouse | 95.9 / 99.9 -> 95.6 / 99.9 | 75.8 / 84.6 -> 80.8 / 88.3 | 52.6 / 65.0 -> 62.7 / 71.9 |
| word, finger | 76.6 / 91.1 -> 75.8 / 92.9 | 57.5 / 75.3 -> 63.5 / 81.3 | 41.6 / 57.1 -> 47.4 / 64.1 |

The owner example, noiseless polylines, top-3 codes before -> after: `yhyjmnbvc` ytmbc yhmbc htmc -> **yhmbc** ytmbc yjmbc; `yhyhmbc` ytmbc htmc yhmbc -> **yhmbc** ynmbc ytmbc; `yhmbc`, `yhjmnbvc`, `yhmnbvc` unchanged (yhmbc first). `yuyjmnbc` stays ambiguous by construction: `yujbc` and `yjmbc` both are subsequences of the touched keys at the same alignment cost (before: ytmbc first). The owner word cases (顏值, 頻率) stay top-1 in all six boundary modes, and `yhyjmnbvc ojhbnm` (the slip inside a word) decodes to 顏值.

**Costs and limits.** Frequency-weighted top-1 on CLEAN mouse sweeps drops 91.3 -> 88.3 (unweighted unchanged, 81.3 -> 81.1): the rerank sometimes promotes a rarer character whose keys are all touched; finger clean improves. Latency (pure Python): single character 7.1 -> 10.6 ms mean (p95 14.1 -> 17.7); word (243k) 11.8 -> 21.5 ms mean (p95 18.6 -> 31.8), mostly `hit_sequence` and warming the per-code ideal-hit cache; a port with flat arrays and a warm cache should be a small fraction of that. The noise class is MY model of a backtrack (go back 70-100% toward the previous key, then on); real spurs, loops and corrections may look different. Not handled: a spur that skips a code key entirely (that key is then "missing").

**Kotlin port notes.** Implement `hit_sequence`, `align_cost`, `excess` (with a per-code cache of the ideal-path cost), the `revisits` count and the rerank formula exactly as above, `align_top` 40 / 25. Reference vectors: `vectors/vectors.json` now includes `spur-yhyjmnbvc` and `spur-yhyhmbc` (the top CODE must be `yhmbc`; every case has `expected_codes`) and `spur-yuyjmnbc-ambiguous` (order recorded, not meaningful); the word vectors were regenerated. Deliberate vector change: all expected scores moved because the default config now includes the alignment stage; the top-1 of every older case is unchanged except the owner slip example (顱 first before, 頻 first now); lower ranks of 15 of the 27 older cases moved (the mini lexicon was also rebuilt).

## 3. 參數與預設值 / Parameters and defaults

`SweepConfig` (decoder.py). Defaults = tuned **mouse** profile. Per-profile files: `results/defaults_<mouse|touchpad|finger|touchscreen>.json`. Tuned by random search + local refinement on the train split (25% of characters by hash). Objective: mean over levels low/mid/high/vhigh of `0.5*(top1 + w1) + 0.25*(top5 + w5)` where `w` = frequency-weighted (unweighted metrics cannot see the prior; weighted ones can). `prior_weight` is searched only in 0.05-0.4 (an unbounded search let the prior drown clean paths: oracle top-1 54% for one profile, kept in `results/round2/`). `n` = 24, `prune_radius` = 1.2 and `dwell_ms` = 250 are fixed, not tuned: larger n / radius (n 48, radius 2.8 in round 1) gave the same accuracy at up to 7x the latency, and a tuned `dwell_ms` was seen to exploit the simulator's assumed hold time (406 ms for finger).

| parameter | meaning | mouse | touchpad | finger | touchscreen |
|---|---|---|---|---|---|
| `n` | resample points N | 24 | 24 | 24 | 24 |
| `shape_weight` | shape channel weight | 6.807 | 6.583 | 0.0 | 1.277 |
| `loc_weight` | location channel weight | 17.552 | 17.552 | 2.826 | 17.21 |
| `end_weight` | start/end term weight | 10.655 | 6.663 | 2.086 | 13.748 |
| `cover_weight` | cover weight | 2.806 | 2.806 | 3.269 | 0.0 |
| `end_alpha` | end weight of location points | 1.746 | 1.686 | 1.343 | 2.046 |
| `loc_tolerance` | location slack (key widths) | 0.0 | 0.0 | 0.0 | 0.073 |
| `shape_short_scale` | shape multiplier for 2-key templates | 0.357 | 0.48 | 0.0 | 0.469 |
| `prior_weight` | prior weight (ln weight) | 0.101 | 0.101 | 0.197 | 0.095 |
| `prune_radius` | start/end pruning radius (key widths) | 1.2 | 1.2 | 1.2 | 1.2 |
| `dwell_ms` | dwell threshold (ms) | 250.0 | 250.0 | 250.0 | 250.0 |
| `dwell_radius` | still radius (key widths) | 0.35 | 0.35 | 0.35 | 0.35 |
| `repeat_miss_penalty` | repeat without dwell | 2.332 | 1.59 | 0.593 | 1.384 |
| `dwell_extra_penalty` | dwell without repeat | 2.165 | 1.374 | 4.268 | 0.84 |

The mouse column is the code default (`SweepConfig()`). `dwell_ms` is fixed at 250 for all profiles, not tuned (a tuned value was seen to exploit the simulator's assumed hold time: 406 ms for finger). The touchpad search found nothing better than the mouse values; touchscreen differs little; the finger search chose a softer location channel and a larger prior. `results/round1/` and `results/round2/` keep the earlier tuning rounds (round 1 optimised unweighted accuracy only and under a harsher corner-cutting model; round 2 let the prior grow so large that clean paths failed); they are kept as logs, not as results.

Notes: the tuned numbers are one search's result with noisy objective (1,000 train entries, one seed); treat differences between profiles of a few percent in any single parameter as noise. Large weights mean the channels are sharp: `loc_weight` 15-22 corresponds to sigma about 0.15-0.18 key widths for a point's error.

## 4. 桌面輸入的差異 / Desktop input differences

Primary desktop device is the **mouse dragging across a drawn on-screen keyboard**; touchpad and touch screen then behave as a mouse (the OS delivers them as pointer events).

| | mouse drag | precision touchpad | touch screen on a PC | finger on a phone |
|---|---|---|---|---|
| position | absolute: cursor on the drawn keys | absolute cursor, but the hand moves RELATIVELY (indirect, clutching at pad edge) | absolute finger position | absolute |
| sampling | event per movement, display-synced in browsers (typically 60-144 Hz; hardware 125-1000 Hz); NO event while still | like mouse; fewer, coarser events at low speed | 60-120 Hz, events while touching | 60-120 Hz |
| pressure | none (button held = sweep) | none (button held or tap-drag = sweep) | none/inconsistent | none exposed to the decoder |
| pointer acceleration | OS ballistics map hand speed to cursor distance; irrelevant to the decoder because only the on-screen position is used, but it makes the hand-to-cursor gain vary during a sweep, which adds overshoot at fast speeds | strongest effect (small gestures, high gain, plus edge clutching) | none | none |
| end of sweep | button up (capture the pointer so releasing outside the keyboard still ends the sweep; clamp the position to the keyboard rectangle) | button up or end of tap-drag (drag lock off) | finger lift | finger lift |
| repeated letter | pointer **dwell** on the key: easy and precise (no hand tremor), but no events are sent | dwell: pointer still; finger micro-motion usually small | dwell with finger jitter | dwell with finger jitter |
| occlusion | none (cursor visible) | none | hand covers keys | finger covers keys |

Consequences implemented in `simulate.py` and the decoder:

- **mouse** profile (primary): smallest jitter, smooth (spline) path, 8-16 ms samples, `event_driven` (no samples while still), most users dwell on repeats (`p_dwell` 0.9). **touchpad**: larger endpoint and overshoot errors, still event-driven. **touchscreen**: finger-like but with bigger keys in cm (smaller error in key widths), continuous samples. **finger**: largest errors.
- Dwell must be derived from timestamps, not from sample counts. A port must pass the true pointer-up time as the last sample, and should not drop duplicate-position events (a repeated position with a later timestamp is how a mouse reports a stop). If the platform emits nothing while still, the first event after the stop carries the time that ends the dwell; the decoder handles both timer-driven and event-driven streams.
- UI contract (not built here): show the current key under the pointer and a visible dwell confirmation (for example a pulse after about 250 ms) so that users learn the dwell.

Profiles (all ASSUMED; `simulate.py: PROFILES`, level mid = x1). Spatial values in key widths:

| profile | position error / key | bias | start+end extra | corner cut (max) | overshoot p x amount | detour p | spline | samples | dwell prob | event-driven |
|---|---|---|---|---|---|---|---|---|---|---|
| mouse (primary) | 0.14 | 0.03 | 0.12 / 0.14 | 0.30 | 0.3 x 0.2 | 0.05 | yes | 8-16 ms | 0.9 | yes |
| touchpad | 0.24 | 0.05 | 0.25 / 0.25 | 0.40 | 0.4 x 0.3 | 0.10 | yes | 8-16 ms | 0.8 | yes |
| touchscreen | 0.17 | 0.10 | 0.16 / 0.16 | 0.35 | 0.3 x 0.15 | 0.08 | no | 8-16 ms | 0.8 | no |
| finger | 0.22 | 0.15 | 0.20 / 0.20 | 0.45 | 0.3 x 0.2 | 0.12 | no | 8-16 ms | 0.8 | no |

## 5. 研究 / Research (what was read, what was not found)

Read in full or in part (text extracted):

- Kristensson & Zhai, **SHARK2**, UIST 2004: https://pokristensson.com/pubs/KristenssonZhaiUIST2004.pdf. Used: multi-channel recognizer (shape + location), template pruning by start-to-start / end-to-end distance of normalized patterns, proportional (linear) shape matching beating elastic matching in crowded template spaces, location channel with a one-key-width "tunnel" and end-weighted point weights, Gaussian conversion of distances with 2 sigma pruning and Bayes combination, dynamic channel weighting by speed, N-best list; reported 20,000 templates searched in 20-40 ms on an 800 MHz Pentium III; confusion analysis on a 20K lexicon (QWERTY: 1461 identical-shape pairs, 537 with the same shape and start and end keys). **The paper does not state the number of resample points N**; here N is a tuned parameter.
- Zhai & Kristensson, **The Word-Gesture Keyboard**, CACM 2012: https://research.google.com/pubs/archive/39190.pdf. Used: lexicon of 20k-100k words suffices for English; matching by dynamic time warping and template matching; indexing and aggressive pruning for real time; unigram frequencies alone "provide significant power"; text-entry error 1.1% in a study (a user-level rate, not decoder accuracy).
- Ouyang, Rybach, Beaufays, Riley (Google), **Mobile keyboard input decoding with finite-state transducers**, 2017: https://arxiv.org/abs/1704.03987. Used: the finger slides past many keys in transit (pit/pot/put share one canonical path on QWERTY); spatial model for gestures is typically a minimum-jerk model; gesture input is "easily 10 to 20% faster than tap input".
- Yin, Ouyang, Partridge, Zhai, **Making touchscreen keyboards adaptive to keys, hand postures, and individuals**, CHI 2013: https://research.google.com/pubs/archive/41930.pdf. Used: touch offsets depend on key, posture and user; key- and posture-specific spatial models cut character error by about 11.5-14.2%. It gives no offset numbers in key widths that I could extract.
- Kristensson, doctoral consortium paper (UIST 2004, short): https://pokristensson.com/pubs/KristenssonUIST2004.pdf (background only).

Found only as titles or snippets (not verified against the full text):

- Zhai & Kristensson, **Shorthand writing on stylus keyboard**, CHI 2003, DOI 10.1145/642611.642630 (https://research-portal.st-andrews.ac.uk/en/publications/shorthand-writing-on-stylus-keyboard/). Abstract only; **no recognition accuracy numbers retrieved**.
- Azenkot & Zhai, **Touch behavior with different postures on soft smartphone keyboards**, MobileHCI 2012, DOI 10.1145/2371574.2371612 (https://research.google/pubs/touch-behavior-with-different-postures-on-soft-smartphone-keyboards/). **Full text not retrieved**; I know only from Yin et al. that posture changes touch bias. I do not quote any offset number from it.
- Parhi, Karlson, Bederson, MobileHCI 2006, DOI 10.1145/1152215.1152260: thumb target-size recommendation of about 9.2 mm (discrete) and 9.6 mm (serial) according to a search-result summary; not read.
- Zhang, Meng, Zhao, **A smart sliding Chinese Pinyin input method editor on touchscreen**, arXiv 1909.01063 (listing only; the PDF could not be fetched): a sliding Pinyin IME, not a path decoder for a code-based system.

**Not found:** any published swipe decoder or accuracy figure for Cangjie, Wubi or other shape-code Chinese input; any measured top-1/top-5 of gesture typing as a function of lexicon size (only the SHARK2 confusion counts and patent statements that bigger lexicons reduce accuracy); any study of word-gesture typing with a **mouse**; the SHARK2 resample count; finger-touch error in key widths from the primary sources. The noise profiles below are therefore assumptions that bracket plausible behaviour; they are NOT grounded in a measurement.

## 6. 雜訊假設 / Noise profiles (ASSUMPTIONS)

Level multiplies spatial errors (and, capped, probabilities): low x0.5, **mid x1**, high x1.6, vhigh x2.5. `simulate.py` generates, in order: per-stroke bias; per-key position error; extra error on first and last key; absolute corner cutting toward the neighbours' chord (up to N key widths); overshoot along the travel direction; lateral detours between two keys (this produces slip paths like y-h-y-j-m-n-b-v-c); optional Catmull-Rom smoothing; Fitts-style segment times with lognormal speed variation and slower ends; per-sample tremor; deliberate dwell on repeated letters with probability `p_dwell` (about 330 +- 90 ms), unintended hesitation pauses (5%, about 130 ms) and a short linger at both ends.

Orders of magnitude: a mid finger error of 0.22 key widths is about 2 mm on a 9-10 mm phone key; Parhi et al. (secondary summary) recommend 9-10 mm keys because smaller ones, 3.8-5.8 mm, gave the most errors. A mid mouse error of 0.14 key widths is about 6 px on a 45 px key. These are guesses consistent in magnitude only. The correct next step is to record real strokes (sections 8 and 9).

## 7. 證據 / Evidence

Held-out test split (75% of characters by hash; 16,481 entries with code length >= 2; noise seeds 1-3; full tables in `results/REPORT.md`). Top-1 / top-5 % over all characters, each counted once. **Analytic ceiling** (exact code known, ties by weight): top-1 91.4, top-3 99.8, top-5 100.0.

| profile | oracle (noiseless) | low x0.5 | mid x1 | high x1.6 | vhigh x2.5 |
|---|---|---|---|---|---|
| mouse | 88.2 / 99.9 | 86.2 / 99.8 | 81.5 / 99.2 | 61.0 / 90.2 | 27.9 / 56.1 |
| touchpad | 88.3 / 99.9 | 83.1 / 99.5 | 55.6 / 86.6 | 22.6 / 47.5 | 6.0 / 16.1 |
| finger | 80.0 / 98.9 | 68.2 / 92.8 | 42.0 / 75.9 | 16.0 / 39.0 | 4.6 / 14.0 |
| touchscreen | 87.3 / 99.9 | 83.9 / 99.6 | 67.7 / 94.6 | 35.2 / 66.3 | 11.1 / 28.1 |

Frequency-weighted top-1 (what a user typing common characters sees), mid: mouse 91.9, touchpad 61.7, finger 71.9, touchscreen 79.2.
**What the numbers say (synthetic; read the limits first).**

- Oracle top-1 88 (mouse) is below the 91.4 analytic ceiling because collapsed repeats and 2-letter codes remain ambiguous even for a perfect path. Finger oracle is 80 with its tuned (soft) location channel.
- **Noise dominates.** Mouse mid: 81.5 / 99.2; high: 61.0 / 90.2; vhigh: 27.9 / 56.1. Finger mid: 42.0 / 75.9 (frequency-weighted top-1 71.9). The gap between profiles is entirely the assumed noise, which is not measured.
- **Ablations** (mid, 6,000 test entries, top-1 / top-5; frequency-weighted top-1 in brackets): full mouse 80.8 / 99.1 (91.9), finger 41.6 / 76.6 (64.7). **No location channel**: mouse 60.0 / 93.5, finger 8.6 / 33.2: the location channel does almost all the work. **No start/end term**: -2 (mouse), -6.5 (finger). **No dwell** (`repeat_mode=ignore`): -4.7 mouse top-1. **No prior**: unweighted top-1 does not change (ordering inside a group that shares a code cannot change how many entries are first), but frequency-weighted top-1 drops from 91.9 to 75.1 (mouse) and 64.7 to 35.0 (finger): the prior matters for what a user types. **No shape channel**: -0.1 (mouse), 0 (finger): the shape channel adds nothing in this simulation. It matters only under a large systematic offset: with a 0.4 key-width per-stroke bias, mouse top-1 goes 41.8 (no shape) -> 45.2 (tuned) -> 49.9 (shape weight x3); finger is unaffected because its tuned shape weight is 0.
- **N and pruning**: N = 16...64 changes top-1 by at most 1.1 points (finger; mouse 0.2); N = 24 is the default. Pruning radius 1.0 loses nothing for the mouse and finger at mid; 0.8 loses 2.5 points of frequency-weighted top-1 (and 5.7 of top-5) for the finger; radius 1.2 (default) keeps a margin; 2.5 is 7x slower for no gain.
- **Repeated letters (`hh`) and dwell** (repeat rows only, mid, mouse top-1 / top-5): user always dwells 79.8 / 98.9; dwells 80% of the time 71.2 / 96.7; never dwells 35.5 / 88.2, and if the decoder is told to ignore dwell then 56 / 97 (dwell-less users do better with `repeat_mode=ignore`: choose the mode from a user setting, or fall back to it when no dwell is ever observed).
- **Lexicon size** (random subsets of characters; mouse / finger mid, top-1): 2.2k entries 97.0 / 77.1; 5.5k 93.3 / 63.4; 11k 89.4 / 54.4; 22k 82.2 / 43.2. Accuracy falls steadily as the lexicon grows: the 22k-entry table is the hard case, and a restricted lexicon (for example frequent characters first) would help.
- **Transfer between profiles** (mid; top-1 / frequency-weighted top-1, %). Mouse config on mouse / touchpad / finger / touchscreen noise: 80.8 / 91.9, 54.6 / 50.8, 48.7 / 56.4, 67.5 / 77.0. Finger config: 65.6 / 90.0, 40.8 / 53.8, **41.6 / 64.7**, 55.9 / 85.4. Touchpad and touchscreen configs are within about 1 point of the mouse config everywhere. So the finger config trades 7 points of unweighted top-1 on finger noise (rare characters) for **+8.3 points frequency-weighted** (a stronger prior and a softer location channel), and it costs 15 points unweighted on mouse noise. **Recommendation: desktop (mouse, touchpad, touchscreen) = `SweepConfig()`; phone (finger) = `results/defaults_finger.json` if frequent characters matter most, the mouse config if every character must work from a clean path** (the finger config's noiseless oracle top-1 is 80.0 vs 88.2). This is a product choice the data cannot make for real users.
- **Layout**: with a phone-like layout (row pitch 1.3) mouse mid 82.9 / 99.4, finger 50.7 / 85.2: same behaviour.
- **Latency** (pure Python 3.12, one core, 300 mid mouse paths): default (N 24, radius 1.2) mean 7.0 ms, p50 6.8, p95 14.0, max 20.4; N 16: 5.0 ms; radius 1.0: 2.7 ms; N 48: 12.5; radius 2.5: 50.7. The bucket index saves only about 20% in Python (8.8 -> 7.0 ms) because the work is the per-template scoring, which the radius controls, not the enumeration; on a phone the radius and a flat float-array layout are what matter. Lexicon build 0.30 s.

## 8. 限制與未驗證 / Limitations and what is NOT validated

- Python 3.8 compatibility is by inspection only (no `match`, no builtin generics, dataclasses only); everything was run on Python 3.12.
- **No real finger, mouse, touchpad or touch-screen data.** All accuracies are on synthetic strokes whose noise I chose. Absolute numbers may be too optimistic or too pessimistic; the ordering between variants (ablations) is more trustworthy than the absolute level, and even that depends on the simulator.
- The tuner and the simulator share assumptions (for example the detour and overshoot model); tuned parameters can be over-fitted to them. Held-out characters and fresh noise seeds control for over-fitting to a sample, not for a wrong noise model.
- Language context is not used (one sweep = one character, rank by lexicon weight only). The weights are the table's weights, so rankings among characters that share a code are only as good as that table.
- Repeated letters rely on the user dwelling. Users who never dwell lose the repeat codes (see the dwell table). Run lengths above 2 (`aaa` vs `aa`) are not distinguished.
- 2-letter codes carry little shape information; accuracy there depends on the location channel.
- Very short or nearly motionless paths: the shape channel rescales by the input's size; a path shorter than about a quarter key width should be treated as a tap by the caller.
- **Independent per-sample jitter cliff.** Characters degrade gracefully (mouse, mid-noise paths plus iid per-sample jitter of 0.05 / 0.1 / 0.2 key widths: top-1 77 / 69 / 60%). Words do not when the jitter is comparable to the sample spacing: the literal owner path (97 samples over 18.6 key widths, 0.19 spacing) with iid jitter 0.1 still gives 顏值 100% but 頻率 about 1%, and at 0.2 both are 0%, because the jitter doubles the measured arc length (39.5 vs 18.6) and the length window `len_lo..len_hi` then removes the right template and the arc-length resampling stops tracking progress. Slow hand wobble (SPEC section 10.6) is fine. A minimum-step debounce (drop samples closer than 0.08 key widths) was tried and does NOT fix it (it helps at 0.25 for 頻率 at jitter 0.1 only) and cost 0.5-1.5 points on the main tables, so it was removed; a low-pass filter of the pointer in the platform layer (or a wider length window) is the open fix. Real touch and mouse sensor noise is far smaller than 0.1 key widths per sample, but this was not measured.
- Cangjie 3 only; Cangjie 5 or other tables change the confusion structure. Only ANSI QWERTY (and one phone-like check) was simulated. Non-QWERTY layouts untested.
- No latency measurement on a phone or in a browser; Python numbers only.
- Not implemented: speed-dependent channel weighting, user adaptation, spatial model personalisation, any neural decoder.

## 9. 移植指引 / Porting notes (Kotlin, JS/TS)

- Reference vectors: `sweep/vectors/vectors.json` (format `cangjie-sweep-vectors-1`): key centres, config, an embedded mini lexicon (a few hundred REAL rows of the Cangjie 3 table that the cases need, plus SYNTHETIC filler rows with private-use characters; the repository does not contain the table), about 26 cases (each code length, a repeat code with and without dwell, the 2-letter case, the 顏 example, the slip path) with expected ranked characters and scores (compare scores to 1e-6; the ranked characters must match exactly). `vectors/word_vectors.json` (`cangjie-sweep-word-vectors-1`) does the same for the word decoder: the two owner paths (continuous, lift, dwell) plus 12 simulated word sweeps, embedded mini chars + words lexicon, `lifts` per case. Each case also has `expected_full` against the full table (table sha256 in the file). `python3 sweep/tests/test_sweep.py` checks them against the Python decoder; regenerate with `python3 -m sweep.make_vectors`.
- Use IEEE doubles. The score formula sums in a fixed order (index order) and uses `ln`; scores can differ by a few ulps between languages, hence the 1e-6 tolerance. Cases whose top-k margin is below 1e-6 were dropped from the vectors.
- Latency design: build templates and the `(first, last)` bucket index once at start-up (Python: about 0.3 s for 19k templates; memory about 19k x N x 2 doubles = 7 MB at N 24 as doubles, half as floats). Per decode: resample the input once, iterate only the buckets whose first key is near the start point and last key near the end point (`prune_radius` 1.2 key widths = roughly 5-8 first keys x 5-8 last keys of 26, so a few hundred templates are scored). Measured Python numbers are in the evidence section; a JIT-compiled port should be well under that.
- Do not skip the dwell logic for event-driven pointers; pass the pointer-up timestamp as a final sample.

## 10. 整詞滑行 / Word-level sweep (one stroke = a word of 1-4 characters)

**中文摘要**：一次滑行可以跨越整個詞（2-4 字，手指不離開、或在字與字之間短暫停留／抬起）。詞的模板 = 各字「主碼」（最短碼，同長取權重高者）直接串接成**一條**折線；**不假設字界在路徑的哪裡**，整條路徑對整條模板比對（與單字相同的位置、起訖通道），所以不需要先切分。停留與抬起只是「字界提示」，會加分。排序 = 路徑分數 + 詞頻對數（essay.txt 的 `詞<TAB>次數`）；單字與詞放在同一個候選清單，用 `char_offset` 與兩個先驗權重校準。另有一個慢速的「逐字切分」備選（DP，沒有詞庫），準確度低，見下。**全部仍是合成軌跡的結果。**

**English.** Implemented in `words.py` (`WordLexicon`, `WordDecoder`, `CharSegmenter`), evaluated by `evaluate_words.py`, tuned by `tune_words.py`, reported in `results/WORDS.md`, vectors in `vectors/word_vectors.json`, tests in `tests/test_words.py`.

### 10.1 Interface

```
WordDecoder.decode(points, lifts=(), top_k) -> [(text, kind, score)]    kind = "word" | "char"
points : (x, y, t_ms) in key widths, time order, the whole gesture (one stroke, or several strokes concatenated)
lifts  : indices i where the finger/button was released between points[i] and points[i+1]   (explicit boundary hints)
```

A lift is simply a hint: the samples of the next stroke are appended to the same list. Nothing else changes: the jump between the strokes is part of the path just like a continuous transition would be. A dwell needs no argument (it is detected from timestamps, per stroke, so the pause caused by a lift is not mistaken for a dwell). Stroke-level dwell semantics are exactly those of section 2.

### 10.2 Lexicon and templates

- Entries: **words** = `word<TAB>freq` lines of essay.txt with 2-4 characters, every character having a Cangjie 3 code; **chars** = every `(code, char)` with `len(code) >= 2` (a character with several codes gives several templates; they compete under one text, best score wins). Single-letter codes are not sweeps and are excluded as candidates; a word may still contain such a character (its code is one key).
- Main code of a character (used inside words) = the shortest code, ties: higher weight, then smaller code.
- Template = `concat_template(codes)`: the codes concatenated, consecutive equal letters collapsed into one vertex (`yhmbc` + `ojbm` -> `yhmbcojbm`; a boundary between two characters that start/end with the same key is a single vertex). Per entry it also gives `bounds` = `[(end vertex of char i, start vertex of char i+1)]` and `repeats` (letters repeated inside one character's code).
- Stored prior is the raw `ln(freq + 1)` (words) or `ln(weight + 1)` (chars); the weights `word_prior_weight`, `char_prior_weight`, `char_offset` live in the config, so they can change without rebuilding.
- Templates are grouped by their collapsed key string; each keeps its arc length, an 8-point coarse resampling (flat float array) and the vertex list. Index: `(first key, last key) -> templates sorted by arc length`.

### 10.3 Decoding

1. Resample the input to `m = 8` (coarse) and `n = 40` (fine) points; `Lp` = total path length (lift jumps included); start = first point, end = last point.
2. Candidates: for each first key within `prune_radius` (1.2 key widths) of the start and last key within `prune_radius` of the end, the bucket's templates whose arc length `Lt` satisfies `len_lo <= Lp / Lt <= len_hi` (0.7 .. 1.6; two binary searches on the sorted lengths). If fewer than `min_candidates` (30): radius x 1.6 and window x (0.7, 1.4); if still fewer: radius x 2.5 and no window. This is the "pruning by start key, end key and total path length"; no assumption about where characters end.
3. Coarse pass: `-(loc_weight * s) * sum_k beta_k |c_k - t_k|^2 + best prior of the template` over the 8 points (end points weight 2), `s = ((nv - 1) / 4) ** evidence_power` with `nv` = vertices. Keep the best `keep` = 150 templates.
4. Fine pass for each kept template: as section 2 with `n = 40`: `x_L` (location, end-weighted), `x_E` (start/end), `x_C` (cover), optional shape; `base = -s * (w_L x_L + w_E x_E + w_C x_C + w_S x_S)`. The factor `s` scales the evidence with the path size because a long path carries more evidence than a short one; the tuner chose a small exponent (0.06).
5. Per entry: `score = base + prior + dwell terms + lift terms`.
   - prior: words `word_prior_weight * ln(freq + 1)`; chars `char_prior_weight * ln(weight + 1) + char_offset`.
   - dwell: as section 2 but a dwell on a character-boundary vertex is not "extra" and earns `boundary_dwell_bonus`; repeated letters inside a character still need their dwell (`repeat_miss_penalty`).
   - lift (per lift hint): `- lift_weight / 2 * min over the candidate's boundaries of ( |end of stroke - boundary end vertex|^2 + |landing point - boundary start vertex|^2 )`; if there are more lifts than boundaries, `- lift_extra_penalty` per extra lift (a candidate with no boundary, i.e. a single character, is penalised for every lift).
6. Per text keep the best score; sort by `(-score, text)`; return `top_k`.

Why no explicit segmentation: the whole path is matched against the whole concatenated template with absolute positions, so character boundaries are implied by the candidate, not searched. Segmentation is therefore only needed for the optional alternative below.

### 10.4 Per-character segmentation alternative (no word lexicon)

`CharSegmenter(single_char_decoder).segment(points, lifts)` returns `(text, score, [(start_idx, end_idx, char, code)])`. Split candidates = the 14 most significant turning points of the path (Douglas-Peucker importance) plus lift points; dynamic programming picks 2-4 consecutive segments, each scored by the single-character decoder (`score`), minus `seg_penalty` (3.0) per character, plus `lift_bonus` (3.0) for a segment that starts after a lift; a segment never crosses a lift and must be at least 0.8 key widths long. It costs tens of single-character decodes (about 0.2-0.9 s in Python), so call it only when the alternative is wanted (for example when no word matches well). **Its accuracy is low without lifts** (see 10.6); it is a fallback, not a replacement for the word decoder.

### 10.5 Defaults (`results/defaults_words.json`)

Tuned on train words/characters (hash split by word / by character) by `tune_words.py`: random search + local refinement of 9 parameters, objective = mean over (mouse, finger) x (mid, high) of 0.5 x (word top-1 + 0.5 top-5) + 0.5 x (single-character-sweep top-1 + 0.5 top-5), because both kinds of sweep are decoded by the same candidate list. (A first tuning on word sweeps alone made words dominate so strongly that single-character sweeps were almost never decoded: 0.2% top-1; the joint objective fixed it.)

| parameter | default | meaning |
|---|---|---|
| `n`, `m`, `keep` | 40, 8, 150 | fine points, coarse points, survivors of the coarse pass (fixed, not tuned) |
| `loc_weight`, `end_weight`, `cover_weight`, `end_alpha`, `shape_weight` | 22.41, 22.456, 2.769, 1.93, 0 | channel weights (shape off) |
| `evidence_power` | 0.065 | exponent of the path-size scaling of the evidence |
| `word_prior_weight`, `char_prior_weight`, `char_offset` | 0.093, 0.1, 0.949 | prior calibration between words and characters |
| `prune_radius`, `len_lo`, `len_hi`, `min_candidates` | 1.2, 0.7, 1.6, 30 | start/end and length pruning |
| `boundary_dwell_bonus`, `lift_weight`, `lift_extra_penalty` | 0.19, 2.495, 4.0 | boundary hints |
| dwell parameters | as `SweepConfig` mouse defaults | |

The word prior ended up small (0.09): the path carries most of the information when the lexicon is a closed set of whole words. Whether it stays small on real data (where paths are sloppier) is untested.

### 10.6 Evidence (synthetic; `results/WORDS.md`)

Test words: 900 (stratified: length 2/3/4 x frequency band 1k-3k, 3k-10k, >=10k, 100 per cell) disjoint from the tuning words; candidate list = 243k essay words (freq >= 100) + all 22k single characters; boundary mode mixed 50% continuous / 25% dwell / 25% lift. Top-1 / top-5 % (full tables in `results/WORDS.md`):

| profile | low | mid | high | continuous only (mid) | lift (mid) | dwell (mid) |
|---|---|---|---|---|---|---|
| mouse | 97.8 / 100.0 | **95.9 / 99.9** | 86.0 / 96.4 | 93.8 | 99.0 | 97.3 |
| touchpad | 97.2 / 100.0 | 84.2 / 95.4 | 47.5 / 66.9 | 81.3 | 90.9 | 83.9 |
| finger | 95.8 / 100.0 | 76.6 / 91.1 | 37.3 / 55.4 | 72.4 | 86.8 | 75.9 |
| touchscreen | 97.2 / 100.0 | 89.2 / 97.7 | 64.2 / 81.2 | 87.1 | 95.4 | 87.9 |

- **Characters vs words.** Single-character sweeps (mid): mouse 82.1 / 98.9, finger 49.9 / 78.8 with a characters-only list; word sweeps (mid): mouse 95.9 / 99.9, finger 76.6 / 91.1. A word is much easier to decode than a character because the path is longer and the candidate set around it is much sparser relative to the path information. Putting words and characters in ONE list costs little: word sweeps 97.0 -> 95.9 (mouse mid) and single-character sweeps 82.1 -> 81.0 (mouse mid); for finger 49.9 -> 46.1 for single characters.
- **Boundary hints.** A lift is the strongest hint (top-1 +5 points for mouse mid, +14 for finger mid, vs continuous). A dwell gives about +3.5 for both. Continuous strokes are still decoded: 93.8% for the mouse at mid.
- **Lexicon size** (same test words, all with freq >= 1000; mouse mid top-1 / finger mid top-1): 9.9k words 98.6 / 90.1; 31.6k 97.5 / 85.6; 191k 96.1 / 78.5; 243k 95.9 / 76.6; 290k 95.8 / 75.2. Accuracy falls with the lexicon, most for the sloppy finger. Words-only vs words+chars: -1 point for word sweeps, above.
- **Owner cases.** Exact literal paths `yhmnbvc ojhbnm` and `yhjmnbvc yuiokjhj` (continuous, lift at the space, dwell at the space): **顏值 and 頻率 are top-1 in all six** (top-2 is 20+ score points lower). The two words share the code of the first character (yhmbc); the second character's path decides, not the word frequency (頻率 12176 vs 顏值 11796). 1000 simulated variants each, generated from the intended codes: 顏值 mouse mid 100% top-1 in all three modes, mouse high 96.7-97.8%, finger mid 90.5-94.0%; 頻率 mouse mid 99.2-100%, mouse high 88.0-96.2%, finger mid 84.1-90.6%. The literal slip path of 頻率 (`o k j h j` after `y u i`) with a slow hand wobble: 100% top-1 at wobble 0.1 with dwell, 80.6% continuous; at wobble 0.4 key widths 48-74% (top-5 71-92%). 頻率 is the harder case because its second character takes a long detour (`o -> k -> j -> h -> j`).
- **Latency** (pure Python, one core): 6.6 ms mean for 31.6k words, 11.4 ms mean / 18 ms p95 / 26 ms max for 243k words (+ chars); lexicon build 2.4 s; the Python process peaks at 373 MB (object overhead; a float-array Kotlin port needs about 16 MB for templates).
- **Per-character segmentation alternative** (no word lexicon): exact text match with a lift: mouse mid 61%, finger mid 21%; **without a lift: under 1%**, with only a dwell: 0%; right number of characters 58-84%. It is weak without lifts; treat it as a display fallback. Possible improvements not done: use dwell hints inside the DP, a bigram/word-length prior, a coarse-to-fine split search.

### 10.7 Porting plan (Kotlin / desktop)

- Build once: parse essay.txt (about 243k words at freq >= 100: build 2.4 s in Python), group by collapsed key string (257k templates), store per template `coarse[16]` floats, arc length, vertex key bytes, entry list; per-bucket arrays sorted by arc length. About 257k x 16 floats = 16 MB (floats) plus entries. A frequency threshold (1000: 31.6k words) cuts memory 8x and costs little accuracy (WORDS.md, lexicon-size table).
- Per decode: resample once to 8 and 40 points; enumerate buckets of the first/last keys within 1.2 key widths (about 8-10 keys each); two binary searches by arc length; score the coarse pass on a few thousand templates (8 points each); partial sort for the best 150; fine pass on 150 templates only. Python needs 11 ms mean / 18 ms p95 for 243k words (7 ms for 31k); a JIT port should be far lower. If the platform needs it, shrink `keep` to 60 and the radius to 1.0.
- Low-pass the pointer in the platform layer: independent per-sample jitter comparable to the sample spacing breaks the word decoder's length window (section 8, "jitter cliff"); a minimum-step debounce did not fix it. Real sensor noise is expected to be far below that, but that is not measured.
- Desktop (mouse): lifts are button-up/button-down pairs inside one gesture (for example a gesture that continues while a modifier is held); a dwell is a pause with the button held. Both hints are optional; the continuous path works alone.

## 11. 檔案 / Files

`keyboard.py` geometry (imports `core/layout.py`), `decoder.py` single-character decoder, `words.py` word-level decoder and segmentation alternative, `simulate.py` synthetic strokes and profiles (`generate`, `generate_word`), `evaluate.py` / `evaluate_words.py` harnesses (train/test split by character / word hash), `tune.py` / `tune_words.py` search, `report.py` / `report_words.py` final evaluations, `make_vectors.py` / `make_word_vectors.py`, `tests/test_sweep.py`, `tests/test_words.py`, `results/` (`REPORT.md`, `WORDS.md`, `final.json`, `words.json`, tuning logs, `defaults_*.json`, `round1/`, `round2/` older rounds kept as logs), `vectors/vectors.json`, `vectors/word_vectors.json`.

Reproduce (paths of the Cangjie 3 table and essay.txt are arguments; neither is in this repository):
`python3 -m sweep.tune --profile mouse --trials 40 --refine 40 --sample 1000 --out sweep/results/tune_mouse.json`; `python3 -m sweep.report --table cangjie3.tsv`; `python3 -m sweep.tune_words --table cangjie3.tsv --essay essay.txt --out sweep/results/tune_words.json`; `python3 -m sweep.report_words --table cangjie3.tsv --essay essay.txt`; tests: `python3 sweep/tests/test_sweep.py`, `python3 sweep/tests/test_words.py` (the tests that need the real table or essay.txt are skipped when they are missing; the vector tests are self-contained).
