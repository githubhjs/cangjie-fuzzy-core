# cangjie-fuzzy-core

倉頡「鄰鍵容錯」輸入的共用核心：契約、鄰接資料、規則產生器、可安裝的 Rime 方案、測試集與驗收腳本。
Adjacent-key typo tolerance for Cangjie input (Rime): contract, neighbour maps, rule generator, installable schemas, test corpora and acceptance scripts.

打碼時只錯**一個鍵、而且錯成鄰近的鍵**，仍然出正確的字：`yhmbc` 是「顏」，打成 `yhmbv`（c 與 v 相鄰）也要能出「顏」；兩個位置都錯（`yhnbv`）或錯成非鄰鍵（`yhmbp`）則不出。

- 規格與已驗證的結果：[SPEC.md](SPEC.md)
- **核心：** `core/layout.py`（用鍵位幾何動態判斷鄰鍵：PC 是 QWERTY 實體鍵盤，Android 是螢幕鍵盤實際繪出的按鍵矩形，誤差值 θ 可設）與 `core/matcher.py`（動態比對器，每次查詢 8 微秒）；測試：`python3 tests/test_layout_matcher.py -v`
- 這是核心與驗收標準；各平台的安裝包另外做。目前可以用的是 `packages/pc/`（Rime 方案；在 Linux 的 Rime 引擎驗證過，還沒有在小狼毫、鼠鬚管的圖形介面實際打字驗證）。

## 使用（PC 實體鍵盤，Rime：小狼毫 / 鼠鬚管 / ibus-rime / fcitx5-rime）

前提：已經裝了 [cangjie-fluency](https://github.com/githubhjs/cangjie-fluency)（它提供 `cangjie3_fluency` 方案、碼表、詞表與語言模型）。

1. 把 `packages/pc/cangjie3_fuzzy.schema.yaml` 和 `packages/pc/cangjie3_fuzzy_prism.schema.yaml` 兩個檔案複製到 Rime 使用者資料夾（Windows：`%APPDATA%\Rime`）。
2. 在 `default.custom.yaml` 的 `schema_list` 加上 `- schema: cangjie3_fuzzy`（只要列這一個，容錯索引會依 `dependencies` 自動建好）。
3. 重新部署（第一次約 12 秒，多產生約 10.7 MB 的索引），選擇「倉頡三代整句（鄰鍵容錯）」。

`packages/phone/` 是以手機觸控鍵盤的鄰接資料產生的版本，**鄰接是理想化的幾何假設，不是實機量測值**，僅供手機版開發驗收用。

## 結果摘要（真實 Rime 引擎，librime 1.10；細節見 SPEC.md）

| 方案 | 精確句首選 | 一鍵鄰鍵打錯的整句出現在前 5 個候選 |
|---|---|---|
| 無容錯 | 88/91 | 0/273 |
| 單流（容錯與精確同一條流） | 81/91（退步） | 230/273 |
| **兩條流（本專案）** | **88/91（無退步）** | **230/273（84%）** |

- 精確輸入的**首選**完全不變（100 組抽樣 0 組改變），但前 5 個候選的清單會多出容錯候選，少數情況容錯字會取代第 2 位的精確字。
- 單字母碼預設不容錯。誤差預算是「每個字碼 1 次」。

## 重現與限制（請先讀）

- `tests/eval_driver.py` 等腳本是在作者的環境跑的（GX10 ARM64、自己編的 librime 與 `rime_deployer`），**路徑寫死在 `/home/hjs/...`**，在別的機器上要改路徑；它們是驗收標準的參考實作，還沒做成一鍵重現。
- 倉庫裡**沒有任何碼表、詞表或語言模型**；那些在 cangjie-fluency 倉庫。（例外：`sweep/vectors/` 的移植對照向量內含幾百列真實碼表／詞表列，見授權一節。）
- 沒有在 Windows、macOS 的圖形介面實際打字驗證過。

## Sweep（滑行輸入）/ Sweep (swipe) decoder

`sweep/`：倉頡三代**滑行輸入**解碼器的設計、模擬與調參；手機手指、電腦**滑鼠拖曳**（觸控板、觸控螢幕為變體）共用同一個與平台無關的解碼器：輸入 `(x, y, t_ms)` 加鍵位，輸出排序後的字。一次滑行可以是**一個字**，也可以是**整個詞（2-4 字）**，字界可以不標（連續）、停留、或抬起。規格見 [sweep/SPEC.md](sweep/SPEC.md)（含摘要、演算法、參數、證據、限制、Kotlin／桌面移植指引），結果見 [sweep/results/REPORT.md](sweep/results/REPORT.md)（單字）與 [sweep/results/WORDS.md](sweep/results/WORDS.md)（整詞），移植對照用的參考向量在 `sweep/vectors/`。純 Python 3.8+ 標準庫，測試：`python3 sweep/tests/test_sweep.py`、`python3 sweep/tests/test_words.py`。

**所有數字都來自合成軌跡（不是真人的手指或滑鼠資料），雜訊參數是假設；真人資料驗證還沒做。**

A path decoder for Cangjie 3 sweeps, platform neutral (finger on a phone, **mouse drag on a drawn keyboard** on desktop; touchpad and touch screen as variants): input `(x, y, t_ms)` + key geometry, output ranked characters. One sweep = one character, or a whole word of 2-4 characters (continuous, or with a dwell or lift at the boundaries). Spec: [sweep/SPEC.md](sweep/SPEC.md); results: [sweep/results/REPORT.md](sweep/results/REPORT.md) (characters), [sweep/results/WORDS.md](sweep/results/WORDS.md) (words); reference vectors for ports: `sweep/vectors/`. Pure Python 3.8+ standard library.

| synthetic, held-out | top-1 / top-5 |
|---|---|
| one character, mouse, mid noise (ceiling 91.4 / 100) | 81.5 / 99.2 |
| one character, finger, mid noise | 42.0 / 75.9 |
| word (243k words), mouse, mid noise | 95.9 / 99.9 |
| word, finger, mid noise | 76.6 / 91.1 |
| latency, pure Python, one core | 7 ms per character, 11 ms per word (mean) |

**Not validated:** real finger and mouse data, real users' dwell behaviour, any phone or browser latency. The Cangjie 3 table and the word list (essay.txt) are not in this repository.

## 授權

MIT（見 `LICENSE`）。本倉庫只含程式與設定，不含第三方資料；唯一例外是 `sweep/vectors/*.json`：移植對照用的參考向量，內含幾百列真實的倉頡三代碼表／essay.txt 列（只有各案例需要的字與其排名靠前的競爭者），其餘為合成填充列（隨機碼、私用區字元）。

## 預設值與可調整的旋鈕 / Defaults and configurable knobs

範圍、每碼容錯、每句容錯三個旋鈕的預設值與研究依據見 [DEFAULTS.md](DEFAULTS.md)（模擬結果：`results/range_study.md`）。跨平台無介面引擎測試：`tests/headless/cj_headless.py`（Linux、macOS、Windows 同一份）。
The three tolerance knobs, their defaults and the evidence behind them: [DEFAULTS.md](DEFAULTS.md). Cross-platform headless engine test: `tests/headless/cj_headless.py`.

## 各平台安裝（容錯為預設方案）/ Install per platform (typo-tolerant is the default schema)

每個平台是獨立倉庫，內含完整的 cj*fluency，有一行安裝指令與 release 離線包 / Each platform is its own repository containing the full cj*fluency, with a one-line install and an offline release bundle:

| 平台 / Platform | 倉庫 / Repository | 一行安裝 / One-liner |
|---|---|---|
| Windows 11 (Weasel) | [cangjie-fuzzy-windows](https://github.com/githubhjs/cangjie-fuzzy-windows) | `irm https://raw.githubusercontent.com/githubhjs/cangjie-fuzzy-windows/main/install.ps1 \| iex` |
| macOS (Squirrel) | [cangjie-fuzzy-macos](https://github.com/githubhjs/cangjie-fuzzy-macos) | `curl -fsSL https://raw.githubusercontent.com/githubhjs/cangjie-fuzzy-macos/main/install.sh \| bash` |
| Linux (ibus-rime, fcitx5-rime) | [cangjie-fuzzy-linux](https://github.com/githubhjs/cangjie-fuzzy-linux) | `curl -fsSL https://raw.githubusercontent.com/githubhjs/cangjie-fuzzy-linux/main/install.sh \| bash` |
| Android | 私有、之後收費 / private, to be sold | v0.1.0 已發布於私有倉庫（模擬器端到端測試通過；實機未驗證）/ v0.1.0 released in a private repository (emulator end-to-end test passes; real phones not verified) |

預設方案是普通倉頡的版本：[cangjie-fluency](https://github.com/githubhjs/cangjie-fluency)（Windows）、[-macos](https://github.com/githubhjs/cangjie-fluency-macos)、[-linux](https://github.com/githubhjs/cangjie-fluency-linux)，容錯方案隨附但排第二。
The versions whose default is plain Cangjie are cangjie-fluency (Windows), -macos and -linux; the typo-tolerant schema is included there too, listed second.
