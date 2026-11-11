# 倉頡 Sweep Pad / Cangjie Sweep Pad

以滑鼠拖過螢幕上的 ANSI QWERTY 字母鍵盤，在放開時辨識倉頡碼，按候選按鈕把該碼的**字母按鍵**送進原本的應用程式。先在目標程式啟用 Rime（小狼毫／鼠鬚管／ibus-rime）；容錯、組字及選字窗仍由 Rime 處理。例：顏的碼是 `yhmbc`，手勢可能經過 `y h y j m n b v c`。單鍵點擊直接送出該字母。觸控板及以滑鼠事件運作的觸控螢幕也可使用。

Drag the mouse over the drawn ANSI QWERTY keyboard, release to decode, then click a candidate to send its **code letter keystrokes** to the target application. Enable your Rime IME in that application first. Rime owns composition, fuzzy matching, and its candidate window. A single-key click sends that letter. Touchpads and touchscreens that produce mouse events can also work.

隨附的是 **27 筆示範碼表**（字根與「顏」），不是完整倉頡字典；輸入其他字需以 `--table` 指定您有權使用的完整 TSV。完整研究碼表因授權來源未釐清而未隨附，見 `data/README.md`。

The bundled **27-entry demo lexicon** contains radicals and 顏, not a complete dictionary. For other characters, supply a full TSV you are entitled to use through `--table`. The research table is excluded because its redistribution provenance is unresolved; see `data/README.md`.

## 執行 / Run

Python 3.8+，僅使用標準函式庫；圖形介面需要 tkinter。部分 Linux 發行版需另外安裝 `python3-tk`。不需要 pip 套件。原始碼使用相鄰的 `sweep/` 與 `core/`；發行 zip 已包含它們，解壓後可在任意目錄執行。

Python 3.8+ with the standard library only; the GUI requires tkinter (often `python3-tk` on Linux). No pip packages. A source checkout uses the neighboring `sweep/` and `core/` packages; the release zip includes both and runs after extraction independently of the checkout.

```sh
python3 sweep-pad/cangjie_sweep_pad.py
# In an extracted release / 解壓後：
python3 cangjie_sweep_pad.py
```

拖曳後最多顯示五個候選，按候選送字母；碼欄可檢視辨識結果。預設不送空白或 Enter，因此不會自動提交 Rime 的組字。使用目標程式本身的鍵盤操作選字／提交。

After a drag, up to five candidate buttons show decoded characters and codes. Click one to send its letters; inspect the recognized code in the code box. No Space or Enter is appended: choose and commit through your normal Rime controls.

## 選項與設定 / Options and settings

```sh
python3 sweep-pad/cangjie_sweep_pad.py --strictness 1 --top-k 5 --keysize 48 --window-size 640x300
python3 sweep-pad/cangjie_sweep_pad.py --mode keys --always-on-top --save-config
python3 sweep-pad/cangjie_sweep_pad.py --no-always-on-top
python3 sweep-pad/cangjie_sweep_pad.py --config /path/to/config.json --table /path/to/cangjie3.tsv
```

`--strictness` 控制幾何比對的嚴格程度（正數，預設 1），`--top-k` 控制解碼回傳數量，介面最多顯示五個。`--keysize` 是像素鍵寬，`--window-size` 是視窗尺寸。`--mode keys` 是預設；Windows 可選 `--mode commit`，直接送候選字的 Unicode，繞過 Rime 組字。其他平台不支援 commit。

`--strictness` scales geometric matching strictness (positive, default 1); `--top-k` controls decoded result count, while the GUI shows at most five. `--keysize` sets pixel key width and `--window-size` sets window geometry. `keys` is the default mode. Windows also supports `--mode commit`, which sends the selected character as Unicode directly and bypasses Rime composition. Commit mode is unavailable elsewhere.

設定 JSON 支援 `strictness`、`top_k`、`mode`、`window_size`、`keysize`、`always_on_top`。命令列優先於設定檔；`--save-config` 儲存設定。預設位置為 Windows `%APPDATA%/cangjie-sweep-pad/config.json`、macOS `~/Library/Application Support/cangjie-sweep-pad/config.json`、Linux `$XDG_CONFIG_HOME/cangjie-sweep-pad/config.json`（未設定時用 `~/.config`）。

JSON settings accept `strictness`, `top_k`, `mode`, `window_size`, `keysize`, and `always_on_top`. CLI options override the file; `--save-config` persists settings. Default locations: Windows `%APPDATA%/cangjie-sweep-pad/config.json`; macOS `~/Library/Application Support/cangjie-sweep-pad/config.json`; Linux `$XDG_CONFIG_HOME/cangjie-sweep-pad/config.json`, falling back to `~/.config`.

## 各平台 / Platforms

| 平台 / OS | 需求與限制 / Requirements and limits |
|---|---|
| Windows | 無額外套件。用 SendInput，視窗套用 `WS_EX_NOACTIVATE` 與 `WS_EX_TOOLWINDOW`。一般權限程式不能向較高權限的目標注入。No extra package; SendInput and non-activating window styles. Injection into elevated applications from a lower-privilege pad may fail. |
| macOS | 在「系統設定 → 隱私權與安全性 → 輔助使用」允許啟動 Python 的終端機／應用程式，授權後可能需重啟。以 ctypes 呼叫 ApplicationServices。Tk 無法保證不取得焦點，會嘗試恢復先前應用程式；原生桌面仍需驗證。Grant Accessibility permission to the terminal/application launching Python, then restart if needed. Uses ApplicationServices via ctypes. Tk cannot guarantee a non-activating window; the fallback attempts to restore the previous application. Native desktop verification remains required. |
| Linux X11 | 注入需安裝 `xdotool`；視窗焦點處理不使用 xdotool，而使用 Tk dock/utility 類型與 X11 提示。視窗管理員可能不遵守。Install `xdotool` for injection. Focus handling uses Tk window types and X11 hints independently of xdotool; window managers may ignore hints. |
| Linux Wayland | 需 `ydotool`、運作中的 ydotoold 及 uinput 權限。套件本身只呼叫工具，不包含其程式碼。不保證視窗不取得焦點；啟動會明確提示。Requires `ydotool`, a running ydotoold, and uinput access. The package invokes external tools and does not redistribute them. Non-activation cannot be guaranteed; startup prints this limitation. |

## 無介面指令 / Headless commands

```sh
python3 sweep-pad/cangjie_sweep_pad.py --print-layout
python3 sweep-pad/cangjie_sweep_pad.py --decode-file path.json --top-k 5
python3 sweep-pad/cangjie_sweep_pad.py --decode-file pixels.json --keysize 48
python3 sweep-pad/cangjie_sweep_pad.py --self-check
python3 sweep-pad/cangjie_sweep_pad.py --inject-test yhmbc --delay 5
```

`path.json` 是 `[[x,y,t_ms], ...]`，座標預設為 `sweep.keyboard.default_layout()` 的鍵寬單位；明確指定 `--keysize` 時視為像素並除以該值。`--print-layout` 可查看座標。`--decode-file` 輸出排名 JSON。`--inject-test` 會在倒數後實際送字母，倒數期間切到目標程式。`--self-check` 不注入按鍵，回傳 0（基本需求可用）或 1（有缺項），不代表實際輸入／IME 整合已驗證。

`path.json` contains `[[x,y,t_ms], ...]` in key-width units from `sweep.keyboard.default_layout()`. An explicit `--keysize` treats coordinates as pixels and divides by that value. `--print-layout` exposes the geometry; `--decode-file` prints ranked JSON. `--inject-test` actually types after the countdown: focus the target application during it. `--self-check` sends no keys and returns 0 for available prerequisites or 1 for missing prerequisites. Passing it does not prove real injection or IME integration.

## 測試與發行 / Tests and release

```sh
python3 -m unittest discover -s sweep-pad/tests
./sweep-pad/make-release.sh 0.1.0
```

產物位於 `sweep-pad/dist/cangjie-sweep-pad-0.1.0.zip` 與 `.zip.sha256`。建置只讀取相鄰解碼器原始碼，不修改 `sweep/`、不連線、不上傳 GitHub。驗證雜湊可在 dist 目錄執行 `sha256sum -c cangjie-sweep-pad-0.1.0.zip.sha256`。

Artifacts are written under `sweep-pad/dist/` as a zip plus `.zip.sha256`. The builder reads neighboring decoder sources without modifying `sweep/`, contacting the network, or publishing to GitHub. Verify the checksum with `sha256sum -c` inside dist.

## 已驗證／尚未驗證 / Verified / not verified

- 已在 Linux GX10 驗證發行 zip 的 SHA-256，並將 zip 解壓至獨立目錄，確認 26 鍵配置及 `yhmbc → 顏` 解碼正常。Verified on Linux GX10: archive SHA-256, independent extraction, 26-key layout, and `yhmbc → 顏` decoding.
- 已有可執行的 unittest：鍵盤幾何、路徑映射、解碼、設定與模擬注入；實際執行結果見本次交付報告。Executable unit tests cover geometry, path mapping, decoding, configuration, and mocked injection; actual run results are recorded in the delivery report.
- 本次 Linux GX10 執行 26 個測試：25 通過，1 因上游向量檔尚未提供而跳過。`--self-check` 回傳 1：tkinter 8.6 與示範碼表可用，但沒有 `xdotool`、`DISPLAY` 或 Wayland 桌面（session 為 `tty`）。On this Linux GX10 run: 26 tests, 25 passed and one skipped because upstream vectors were absent. Self-check exited 1: tkinter 8.6 and demo data are available, but xdotool and a desktop display are absent (`tty` session).
- 尚未驗證真實 Windows/macOS SendInput/CGEvent、Rime 組字、原生視窗焦點；需 Windows 11 與 MacBook Air 測試機。Real Windows/macOS injection, Rime composition, and native window focus require those test rigs.
- 尚未驗證真實 Linux 目標應用程式的按鍵注入、所有視窗管理員、Wayland compositor、ydotoold/uinput 權限、觸控螢幕與長時間使用。Real Linux target injection, all window managers, Wayland compositors, uinput permissions, touchscreen operation, and prolonged use remain unverified.
- 手勢解碼候選可能誤判；同碼字、重複字根停留與手勢品質會影響排序。Candidate ranking can be wrong; shared codes, repeated-letter dwells, and path quality affect results.

程式碼為 MIT，見 `LICENSE`；資料來源及限制見 `data/README.md`。Code is MIT; see `LICENSE`. Data provenance and limitations are documented in `data/README.md`.
