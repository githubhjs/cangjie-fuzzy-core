# Phone-like layouts: raw vs per-axis normalised decoding (SYNTHETIC strokes)

Layout = `phone_qwerty(row_pitch=p)` (rows staggered 0 / 0.5 / 1.5 key widths like the emulator keyboard). Strokes are simulated on the raw layout with isotropic noise in key widths. 'raw' decodes with the raw layout (y in key widths); 'normalised' divides y by the pitch (pitch-1 layout), the rule in SPEC.md. Level mid, default configs. Characters: 3000 held-out entries; words: 360 (freq >= 1000 lexicon + chars; mixed boundaries). top-1 / top-5 %.

| profile | backtrack | pitch | chars raw | chars normalised | words raw | words normalised |
|---|---|---|---|---|---|---|
| finger | 0.0 | 1.0 | 47.7 / 81.6 | 47.7 / 81.6 | 75.0 / 91.7 | 75.0 / 91.7 |
| finger | 0.0 | 1.3 | 56.7 / 88.4 | 55.5 / 87.0 | 80.6 / 95.8 | 81.4 / 94.7 |
| finger | 0.0 | 1.5 | 60.4 / 90.8 | 58.5 / 89.1 | 83.3 / 96.4 | 83.1 / 94.7 |
| finger | 0.0 | 1.7 | 62.6 / 92.2 | 59.6 / 89.9 | 85.8 / 96.1 | 83.9 / 95.3 |
| finger | 0.4 | 1.0 | 38.7 / 68.0 | 38.7 / 68.0 | 58.6 / 78.3 | 58.6 / 78.3 |
| finger | 0.4 | 1.3 | 45.4 / 76.2 | 44.4 / 74.0 | 65.6 / 83.6 | 63.3 / 82.2 |
| finger | 0.4 | 1.5 | 48.9 / 79.2 | 46.4 / 75.7 | 70.6 / 86.7 | 63.3 / 81.9 |
| finger | 0.4 | 1.7 | 50.9 / 81.2 | 47.4 / 77.0 | 70.3 / 87.5 | 67.2 / 83.6 |
| touchscreen | 0.0 | 1.0 | 67.7 / 95.2 | 67.7 / 95.2 | 87.5 / 97.8 | 87.5 / 97.8 |
| touchscreen | 0.0 | 1.3 | 73.7 / 97.4 | 71.4 / 97.0 | 91.9 / 98.9 | 91.7 / 98.6 |
| touchscreen | 0.0 | 1.5 | 75.5 / 97.8 | 73.0 / 97.2 | 94.2 / 99.4 | 92.5 / 98.6 |
| touchscreen | 0.0 | 1.7 | 76.1 / 98.1 | 73.4 / 97.5 | 93.1 / 99.2 | 92.8 / 98.9 |
| touchscreen | 0.4 | 1.0 | 54.2 / 81.4 | 54.2 / 81.4 | 71.4 / 86.1 | 71.4 / 86.1 |
| touchscreen | 0.4 | 1.3 | 59.6 / 87.2 | 57.4 / 83.9 | 79.2 / 90.6 | 74.2 / 87.2 |
| touchscreen | 0.4 | 1.5 | 61.7 / 88.5 | 58.5 / 84.2 | 79.4 / 91.4 | 73.6 / 86.1 |
| touchscreen | 0.4 | 1.7 | 62.4 / 89.2 | 58.9 / 84.4 | 80.8 / 91.1 | 75.8 / 86.7 |
