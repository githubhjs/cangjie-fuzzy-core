# Product-level decode policy: one-list decoder alone vs decode_auto (SYNTHETIC sweeps)

One-list = word decoder over characters + 243k words (defaults_words.json). Auto = SPEC section 12: single-character decoder and the one-list decoder; if the one-list best guess is a word its list is returned, else the characters followed by the words. 'auto (profile cfg)' uses the profile's own character config (defaults_<profile>.json), 'auto (mouse cfg)' the mouse defaults for every profile. Level mid, held-out 3000 characters and 855 words (mixed continuous / dwell / lift). top-1 / top-5 %; 'w' = frequency-weighted top-1 over characters (word sweeps are not weighted).

| profile | backtrack | sweeps | one-list | auto (profile cfg) | auto (mouse cfg) |
|---|---|---|---|---|---|
| mouse | 0.0 | char | 80.2 / 98.8 (w 92.0) | 78.8 / 98.9 (w 92.2) | 78.8 / 98.9 (w 92.2) |
| mouse | 0.0 | word | 96.8 / 100.0 | 96.8 / 98.9 | 96.8 / 98.9 |
| mouse | 0.4 | char | 56.6 / 78.3 (w 80.5) | 55.8 / 79.9 (w 79.5) | 55.8 / 79.9 (w 79.5) |
| mouse | 0.4 | word | 63.5 / 72.7 | 63.5 / 71.8 | 63.5 / 71.8 |
| finger | 0.0 | char | 48.1 / 76.9 (w 42.3) | 36.8 / 71.7 (w 46.0) | 45.5 / 79.4 (w 40.5) |
| finger | 0.0 | word | 79.8 / 92.6 | 79.8 / 90.8 | 79.8 / 90.8 |
| finger | 0.4 | char | 31.8 / 55.6 (w 34.0) | 25.5 / 55.3 (w 28.7) | 31.4 / 59.5 (w 32.4) |
| finger | 0.4 | word | 49.6 / 64.0 | 49.6 / 62.8 | 49.6 / 62.8 |

Latency (pure Python, one core, mean / p95 ms): 

| sweep | one-list | auto |
|---|---|---|
| word | 21.7 / 32.0 | 26.2 / 36.7 |
| character | 8.7 / 14.1 | 16.7 / 26.0 |
