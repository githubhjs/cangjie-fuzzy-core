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
- 倉庫裡**沒有任何碼表、詞表或語言模型**；那些在 cangjie-fluency 倉庫。
- 沒有在 Windows、macOS 的圖形介面實際打字驗證過。

## 授權

MIT（見 `LICENSE`）。本倉庫只含程式與設定，不含第三方資料。

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
| Android | 私有、之後收費 / private, to be sold | （建置與測試進行中 / build and tests in progress） |

預設方案是普通倉頡的版本：[cangjie-fluency](https://github.com/githubhjs/cangjie-fluency)（Windows）、[-macos](https://github.com/githubhjs/cangjie-fluency-macos)、[-linux](https://github.com/githubhjs/cangjie-fluency-linux)，容錯方案隨附但排第二。
The versions whose default is plain Cangjie are cangjie-fluency (Windows), -macos and -linux; the typo-tolerant schema is included there too, listed second.
