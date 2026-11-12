# 倉頡 Sweep Pad / Cangjie Sweep Pad

一筆滑行可輸入 2–4 字詞，也可輸入單字。以滑鼠拖過螢幕上的 ANSI QWERTY 字母鍵盤，候選清單會依詞解碼器的分數混排詞語與單字，每個候選下方顯示倉頡碼。先在目標程式啟用 Rime；按候選後送出的是**碼的字母按鍵**，由 Rime 組字及選字。單鍵點擊直接送出該字母。

One sweep can cover a 2–4 character word or a single character. Drag over the drawn ANSI QWERTY keyboard; words and characters share the decoder's ranked candidate list, with codes below each candidate. Enable Rime in the target application first. Choosing a candidate sends its **code letter keystrokes**; Rime handles composition and selection. A single-key click sends that letter.

範例：`yhmnbvc ojhbnm → 顏值`、`yhjmnbvc yuiokjhj → 頻率`（空格標示字界，不是必須按的鍵）。連續滑行即可辨識；在滑行途中放開後 **250 ms 內重新按下**，會接續同一手勢並傳入抬起字界提示。超過等待時間即解碼。按住停留的時間戳由解碼器處理，可作為字界或重複字根提示。

Examples: `yhmnbvc ojhbnm → 顏值` and `yhjmnbvc yuiokjhj → 頻率` (the space labels a character boundary). Continuous strokes work. Releasing and pressing again **within 250 ms** continues the gesture and supplies a lift boundary; otherwise the pad decodes after that interval. Held pauses retain timestamps so the decoder can recognize dwell boundaries and repeated letters.

啟動時會顯示 loading，背景執行緒建立詞典，不阻塞介面；完成後處理等待中的手勢。詞典使用 `essay.txt` 詞頻 ≥1000、長度 2–4 的詞，並保留碼表中的單字；只有全部字元都有碼的詞才可用。建立後以資料檔雜湊作鍵，在使用者快取目錄存成 JSON；沒有二進位物件序列化。一般位置：Linux `$XDG_CACHE_HOME/cangjie-sweep-pad`（預設 `~/.cache`）、macOS `~/Library/Caches/cangjie-sweep-pad`、Windows `%LOCALAPPDATA%/cangjie-sweep-pad`。

Startup shows loading while a background thread builds the lexicon and keeps the UI responsive; queued gestures decode when ready. The lexicon uses 2–4 character essay words with frequency ≥1000, plus table characters. A word is available only when every character has a code. The built lexicon is cached as JSON, keyed by data-file hashes, in the user cache directory; no binary object serialization is used. Typical locations are Linux `$XDG_CACHE_HOME/cangjie-sweep-pad` (default `~/.cache`), macOS `~/Library/Caches/cangjie-sweep-pad`, and Windows `%LOCALAPPDATA%/cangjie-sweep-pad`.

隨附完整倉頡三代碼表（22,174 列，與 cangjie-fluency 相同）與完整 `essay.txt`。程式碼為 MIT；**碼表與 essay.txt 資料為 LGPL-3.0**，授權全文及來源見 `data/LICENSE-essay.txt`、`data/README.md`。不包含 GPL 程式碼。可用 `--table` 換成自己的碼表。

The bundle includes the full Cangjie 3 table (22,174 rows, same as cangjie-fluency) and the full `essay.txt`. Code is MIT; **the table and essay.txt data are LGPL-3.0**, with license and provenance in `data/LICENSE-essay.txt` and `data/README.md`. No GPL code is bundled. Use `--table` to substitute your own table.

## 執行 / Run

Python 3.8+，僅使用標準函式庫；圖形介面需要 tkinter。部分 Linux 發行版需另外安裝 `python3-tk`。不需要 pip 套件。原始碼使用相鄰的 `sweep/` 與 `core/`；發行 zip 已包含它們，解壓後可在任意目錄執行。

Python 3.8+ with the standard library only; the GUI requires tkinter (often `python3-tk` on Linux). No pip packages. A source checkout uses the neighboring `sweep/` and `core/` packages; the release zip includes both and runs after extraction independently of the checkout.

```sh
python3 sweep-pad/cangjie_sweep_pad.py
# In an extracted release / 解壓後：
python3 cangjie_sweep_pad.py
```

拖曳後最多顯示五個候選。詞的送出碼 = 各字主碼串接，預設 `word_separator=""`，例如顏值送出 `yhmbcojbm`。不擅自加入空白，因為 Rime 的空白常用於選字或提交，實際分詞方式取決於啟用的 schema；若 schema 需要分隔，請設定 `word_separator`（空字串、空格或單引號）。Linux ibus-rime + `cangjie3_fluency` 實測（見下方「已驗證」）：空字串（預設）與空格結果相同，Rime 會把 `yhmbcojbm` 切成兩個字碼；**單引號不可用**，Rime 會把它當標點（‘），後面的碼變成未轉換的英文字母。pad 只送碼，不送你點的是哪個候選：同碼的字（頻／顏）以及詞的首選由 Rime 自己的排序決定，你可能要在 Rime 裡再選一次。

Up to five candidates are shown. A word sends its characters' main codes joined together, with `word_separator=""` by default: 顏值 sends `yhmbcojbm`. Rime commonly uses Space for selection or commit, so the pad does not insert it automatically. Configure `word_separator` (empty, Space, or apostrophe) if your schema requires a delimiter. Measured on Linux ibus-rime with `cangjie3_fluency` (see Verified below): empty (the default) and Space behave the same, and Rime splits `yhmbcojbm` into two character codes. **Do not use the apostrophe**: Rime treats it as punctuation (‘) and the following code stays as raw ASCII letters. The pad sends only the code, not which candidate you clicked. Rime's own ranking decides between characters that share a code (頻/顏) and which word comes first, so you may have to pick again in Rime.

## 選項與設定 / Options and settings

```sh
python3 sweep-pad/cangjie_sweep_pad.py --strictness 1 --top-k 5 --keysize 48 --window-size 640x300
python3 sweep-pad/cangjie_sweep_pad.py --mode keys --always-on-top --save-config
python3 sweep-pad/cangjie_sweep_pad.py --profile touchpad --lift-ms 250 --word-separator ""
python3 sweep-pad/cangjie_sweep_pad.py --no-always-on-top
python3 sweep-pad/cangjie_sweep_pad.py --config /path/to/config.json --table /path/to/cangjie3.tsv
```

`--strictness` 控制幾何比對的嚴格程度（正數，預設 1），`--top-k` 控制解碼回傳數量，介面最多顯示五個。`--keysize` 是像素鍵寬，`--window-size` 是視窗尺寸。`--mode keys` 是預設；Windows 可選 `--mode commit`，直接送候選字的 Unicode，繞過 Rime 組字。其他平台不支援 commit。

`--strictness` scales geometric matching strictness (positive, default 1); `--top-k` controls decoded result count, while the GUI shows at most five. `--keysize` sets pixel key width and `--window-size` sets window geometry. `keys` is the default mode. Windows also supports `--mode commit`, which sends the selected character as Unicode directly and bypasses Rime composition. Commit mode is unavailable elsewhere.

設定 JSON 支援 `strictness`、`top_k`、`mode`、`window_size`、`keysize`、`always_on_top`、`profile`、`word_separator`、`lift_ms`。命令列優先於設定檔；`--save-config` 儲存設定。預設位置為 Windows `%APPDATA%/cangjie-sweep-pad/config.json`、macOS `~/Library/Application Support/cangjie-sweep-pad/config.json`、Linux `$XDG_CONFIG_HOME/cangjie-sweep-pad/config.json`（未設定時用 `~/.config`）。

JSON settings accept `strictness`, `top_k`, `mode`, `window_size`, `keysize`, `always_on_top`, `profile`, `word_separator`, and `lift_ms`. CLI options override the file; `--save-config` persists settings. Default locations: Windows `%APPDATA%/cangjie-sweep-pad/config.json`; macOS `~/Library/Application Support/cangjie-sweep-pad/config.json`; Linux `$XDG_CONFIG_HOME/cangjie-sweep-pad/config.json`, falling back to `~/.config`.

`profile` 可選 `mouse`（預設）、`touchpad`、`touchscreen`，可保存為設定。目前三者都載入 `sweep/results/defaults_words.json` 的滑鼠整詞預設值；上游沒有另外調整的觸控板／觸控螢幕整詞設定，這項選擇不代表有裝置專屬的實測校準。`lift_ms` 預設 250 ms。

`profile` accepts `mouse` (default), `touchpad`, or `touchscreen` and persists in settings. All currently use the tuned mouse word defaults from `sweep/results/defaults_words.json`; upstream has no separately tuned touchpad/touchscreen word configuration. The choice does not imply measured device-specific calibration. `lift_ms` defaults to 250 ms.

## 各平台 / Platforms

| 平台 / OS | 需求與限制 / Requirements and limits |
|---|---|
| Windows | 無額外套件。用 SendInput，視窗套用 `WS_EX_NOACTIVATE` 與 `WS_EX_TOOLWINDOW`。一般權限程式不能向較高權限的目標注入。No extra package; SendInput and non-activating window styles. Injection into elevated applications from a lower-privilege pad may fail. |
| macOS | 在「系統設定 → 隱私權與安全性 → 輔助使用」允許啟動 Python 的終端機／應用程式，授權後可能需重啟。以 ctypes 呼叫 ApplicationServices。Tk 無法保證不取得焦點，會嘗試恢復先前應用程式；原生桌面仍需驗證。Grant Accessibility permission to the terminal/application launching Python, then restart if needed. Uses ApplicationServices via ctypes. Tk cannot guarantee a non-activating window; the fallback attempts to restore the previous application. Native desktop verification remains required. |
| Linux X11 | 注入需安裝 `xdotool`；視窗焦點處理不使用 xdotool，而使用 Tk dock/utility 類型與 X11 提示。視窗管理員可能不遵守。Install `xdotool` for injection. Focus handling uses Tk window types and X11 hints independently of xdotool; window managers may ignore hints. |
| Linux Wayland | 需 `ydotool`、運作中的 ydotoold 及 uinput 權限。套件本身只呼叫工具，不包含其程式碼。不保證視窗不取得焦點；啟動會明確提示。Requires `ydotool`, a running ydotoold, and uinput access. The package invokes external tools and does not redistribute them. Non-activation cannot be guaranteed; startup prints this limitation. |

## 無介面指令 / Headless commands

```sh
python3 sweep-pad/cangjie_sweep_pad.py --decode-string "yhmnbvc ojhbnm" --boundary continuous --expect 顏值
python3 sweep-pad/cangjie_sweep_pad.py --decode-string "yhjmnbvc yuiokjhj" --boundary lift --expect 頻率
python3 sweep-pad/cangjie_sweep_pad.py --decode-string yhyjmnbvc --expect-code yhmbc   # one character: the slip y h y j m n b v c
python3 sweep-pad/cangjie_sweep_pad.py --print-layout
python3 sweep-pad/cangjie_sweep_pad.py --decode-file path.json --top-k 5
python3 sweep-pad/cangjie_sweep_pad.py --decode-file pixels.json --keysize 48
python3 sweep-pad/cangjie_sweep_pad.py --self-check
python3 sweep-pad/cangjie_sweep_pad.py --inject-test yhmbc --delay 5
```

`path.json` 可用 `{"points":[[x,y,t_ms], ...],"lifts":[idx,...]}`；`lifts` 的索引 i 表示在 points[i] 與 points[i+1] 之間抬起。也接受原本的 `[[x,y,t_ms], ...]`。座標預設為 `sweep.keyboard.default_layout()` 的鍵寬單位；明確指定 `--keysize` 時視為像素並除以該值。`--print-layout` 可查看座標。`--decode-file` 輸出排名 JSON。`--inject-test` 會在倒數後實際送字母，倒數期間切到目標程式。`--self-check` 不注入按鍵，回傳 0（基本需求可用）或 1（有缺項），不代表實際輸入／IME 整合已驗證。

`path.json` accepts `{"points":[[x,y,t_ms], ...],"lifts":[idx,...]}`; index i marks a lift between points[i] and points[i+1]. The original point list is also accepted. Coordinates are in key-width units from `sweep.keyboard.default_layout()`. An explicit `--keysize` treats coordinates as pixels and divides by that value. `--print-layout` exposes the geometry; `--decode-file` prints ranked JSON. `--inject-test` actually types after the countdown: focus the target application during it. `--self-check` sends no keys and returns 0 for available prerequisites or 1 for missing prerequisites. Passing it does not prove real injection or IME integration.

`--decode-string` 使用上游 `sweep.report_words.literal`，`--boundary` 可選 `continuous`、`lift`、`dwell`。加上 `--expect` 時，只有第一候選符合預期才回傳 0；不符合回傳非零。

`--decode-string` reuses upstream `sweep.report_words.literal`; `--boundary` accepts `continuous`, `lift`, or `dwell`. With `--expect`, exit status is 0 only when the first candidate matches. A single key sequence (no space) is one character sweep; `--expect-code` checks the main code of the first candidate. Decoding uses `sweep/auto.py` `decode_auto` (single-character decoder + one-list word decoder, SPEC section 12).

## 測試與發行 / Tests and release

```sh
python3 -m unittest discover -s sweep-pad/tests
./sweep-pad/make-release.sh 0.2.0
```

產物位於 `sweep-pad/dist/cangjie-sweep-pad-0.2.0.zip` 與 `.zip.sha256`。建置只讀取相鄰解碼器原始碼，不修改 `sweep/`、不連線、不上傳 GitHub。驗證雜湊可在 dist 目錄執行 `sha256sum -c cangjie-sweep-pad-0.2.0.zip.sha256`。

Artifacts are written under `sweep-pad/dist/` as a zip plus `.zip.sha256`. The builder reads neighboring decoder sources without modifying `sweep/`, contacting the network, or publishing to GitHub. Verify the checksum with `sha256sum -c` inside dist.

建置會將 zip 解壓至獨立暫存目錄，以空白快取、非原始碼工作目錄執行兩個 `--decode-string --expect` 與 `--self-check`，並印出結果。缺少桌面注入工具時，self-check 可回傳 1；建置會明確列出此限制，不宣稱實際注入已通過。

The builder extracts the archive into a temporary directory, uses an empty cache and foreign working directory, and runs both owner `--decode-string --expect` checks plus `--self-check`, printing their output. Missing desktop injection prerequisites may produce self-check status 1; the builder reports that limitation explicitly.

## 已驗證／尚未驗證 / Verified / not verified

- 自動驗證範圍：pad unittest、兩個上游 sweep 測試、兩個 literal owner 路徑，以及獨立 zip 解壓檢查；實際測試數與輸出見本次交付報告。Automated verification covers pad unittests, both upstream sweep tests, both literal owner paths, and extracted archive checks; see the delivery report for actual counts and output.
- 合成路徑測試不等於真人準確率；詞庫門檻與準確率數字見 `sweep/results/WORDS.md`。Synthetic paths do not establish human accuracy; lexicon threshold and accuracy numbers are in `sweep/results/WORDS.md`.
- 已驗證 GUI（2026-11-12，腳本在 `tests/gui/`，以合成的真實系統滑鼠事件操作，不是真人）：目標程式為一個取得焦點的 Tk Entry，不經 Rime。GUI verified on 2026-11-12 with scripted but real OS-level mouse events (scripts in `tests/gui/`; not a human), into a focused Tk Entry target without Rime:
  - Linux X11：Xvfb + openbox 3.6 + xdotool（XTEST）。滑過 `y h y j m n b v c` 後按第一個候選送出 `yhmbc`；單擊 K 鍵送出 `k`；`yhmnbvc ojhbnm` 連續滑動與抬筆兩種方式都出現 顏值 並送出 `yhmbcojbm`。整個過程 X 輸入焦點與 `_NET_ACTIVE_WINDOW` 未離開目標（約 30 ms 取樣，目標無 FocusOut）。Linux X11 (Xvfb, openbox 3.6, xdotool/XTEST): the `y h y j m n b v c` sweep plus first candidate sends `yhmbc`; a single K click sends `k`; `yhmnbvc ojhbnm` as one continuous sweep and as two strokes with a lift both offer 顏值 first and send `yhmbcojbm`. X input focus and `_NET_ACTIVE_WINDOW` stayed on the target throughout (sampled every ~30 ms, no FocusOut on the target).
  - Windows 11（已登入的主控台工作階段，透過排程工作執行，SendInput 滑鼠事件）：`--inject-test yhmbc` 送進目標；pad 視窗具 `WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW|WS_EX_TOPMOST`；開啟 pad、單擊 K、字與詞滑動加候選點擊後，前景視窗始終是目標，目標收到 `k`、`yhmbc`、`yhmbcojbm`。測試以系統管理員權限執行，因為當時前景是系統管理員終端機（UIPI 會無聲丟棄一般權限的注入）。Windows 11 (logged-on console session via a scheduled task, SendInput mouse events): `--inject-test yhmbc` reaches the target; the pad window has `WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW|WS_EX_TOPMOST`; showing the pad, clicking K, and the character and word sweeps with a candidate click never changed the foreground window, and the target received `k`, `yhmbc` and `yhmbcojbm`. The run was elevated because an elevated terminal was in the foreground (UIPI silently drops medium-integrity injection).
  - macOS 26（/usr/bin/python3 3.9、Tk 8.5，經 ssh）：只做啟動測試，pad 視窗出現並執行 10 秒無錯誤；`--self-check` 回報未取得輔助使用權限（`injector_available: false`）。macOS 26 (/usr/bin/python3 3.9, Tk 8.5, over ssh): startup smoke test only; the pad window appeared and ran 10 s without a traceback; `--self-check` reports Accessibility not granted (`injector_available: false`).
- 已驗證真正的 Rime 組字（2026-11-12，Linux GX10 aarch64，Xvfb + openbox，獨立 HOME 與私有 ibus-daemon 1.5.29 + ibus-rime 1.5.0 / librime 1.10，cangjie-fluency-linux v0.4.3 安裝的 `cangjie3_fluency` 方案，pad v0.4.1，目標為使用 `GTK_IM_MODULE=ibus` 的 GTK3 Entry，腳本 `tests/gui/drive_pad_ime.py` 與記錄候選的 `tests/gui/log_panel.py`）：Real Rime composition verified on 2026-11-12 (Linux GX10 aarch64, Xvfb + openbox, throwaway HOME with a private ibus-daemon 1.5.29 + ibus-rime 1.5.0 / librime 1.10, `cangjie3_fluency` installed by cangjie-fluency-linux v0.4.3, pad v0.4.1, GTK3 Entry with `GTK_IM_MODULE=ibus`; scripts `tests/gui/drive_pad_ime.py` and the candidate-logging panel `tests/gui/log_panel.py`):
  - 點 pad 候選後 Entry 文字仍是空的，Rime 正在組字（preedit `卜竹一月金`），候選 `頻 顏 顪 顔`；按 `1` + Enter 得 頻，按 `2` + Enter 得 顏。After the candidate click the Entry text is still empty and Rime is composing (preedit `卜竹一月金`, candidates `頻 顏 顪 顔`); `1` + Enter gives 頻, `2` + Enter gives 顏.
  - 詞 `yhmnbvc ojhbnm`：pad 首選 顏值，送出 `yhmbcojbm`；Rime 在乾淨使用者詞典下切成 `卜竹一月金 人十月一`，首選是 **頻值**（不是 顏值），候選 `頻值 頻 顏 顪 顔`。選 顏值 要三鍵：`3`（顏）、`1`（值）、Enter。Rime 學到之後，同一滑動的首選變成 顏值（`1` + Enter）。五碼之後不會自動上屏。Word `yhmnbvc ojhbnm`: the pad's first candidate 顏值 sends `yhmbcojbm`; with a fresh user dictionary Rime segments it as `卜竹一月金 人十月一` and ranks **頻值** first (not 顏值), candidates `頻值 頻 顏 顪 顔`. Getting 顏值 takes three keys: `3` (顏), `1` (值), Enter. After Rime learns it, the same sweep ranks 顏值 first (`1` + Enter). Nothing is auto-committed after five codes.
  - `--word-separator " "` 與預設相同；`--word-separator "'"` 失敗（preedit 變成 `頻‘ojbm`）。全程 X 焦點與 `_NET_ACTIVE_WINDOW` 未離開 GTK 目標（740 次取樣，0 次偏離）。`--word-separator " "` behaves like the default; `--word-separator "'"` fails (preedit becomes `頻‘ojbm`). X focus and `_NET_ACTIVE_WINDOW` never left the GTK target (740 samples, 0 deviations).
- 尚未驗證：真人滑鼠／觸控板／觸控螢幕軌跡、長時間使用；真實桌面上的 ibus/fcitx5（GNOME、KDE）與 `cangjie3_fluency` 以外的 schema；Weasel、Squirrel 的連碼組詞；一般權限 pad 注入提升權限的程式（設計上會被 UIPI 擋下）；macOS 的實際 CGEvent 注入與焦點還原；openbox 以外的 X11 視窗管理員（GNOME/KDE 等）；Wayland compositor 與 ydotoold/uinput 權限。Not verified: human pointer traces, prolonged use; ibus/fcitx5 on a real desktop (GNOME, KDE) and schemas other than `cangjie3_fluency`; concatenated-code composition in Weasel and Squirrel; injecting from a normal-privilege pad into elevated Windows apps (blocked by UIPI by design); real CGEvent injection and focus restoration on macOS; X11 window managers other than openbox (GNOME, KDE, ...); Wayland compositors and ydotoold/uinput permissions.

程式碼為 MIT，見 `LICENSE`；LGPL-3.0 詞頻資料保留原授權，見 `data/README.md`。Code is MIT; see `LICENSE`. The LGPL-3.0 word-frequency data retains its own license; see `data/README.md`.
