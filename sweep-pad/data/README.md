# 資料來源與授權 / Data provenance and licenses

`cangjie3.tsv` 是完整的倉頡三代碼表（22,174 列，`code<TAB>character<TAB>weight`），與 cangjie-fluency 各安裝程式、Android 輸入法使用的是同一份：由 cangjie-fluency 的 `tables/mscj3.cin`（微倉三）轉成，權重取自詞頻。**此碼表資料為 LGPL-3.0，不是 MIT**；來源與授權說明見 cangjie-fluency 的 `tables/README.md`。

`cangjie3.tsv` is the full Cangjie 3 table (22,174 rows, `code<TAB>character<TAB>weight`), the same file the cangjie-fluency installers and the Android IME use: converted from cangjie-fluency's `tables/mscj3.cin` with weights from word frequency. **This table data is LGPL-3.0, not MIT**; provenance and licence are described in cangjie-fluency's `tables/README.md`.

`essay.txt` 完整複製自本機 `~/projects/cangjie-fluency/data/essay.txt`，未修改。依該專案 `data/README.md` 的來源紀錄：上游為 [rime/rime-essay](https://github.com/rime/rime-essay)，commit `054920de4f54c9e5994276a96a4fc2a35cb51aa3`；5,887,319 bytes；SHA-256 `3e8512ebaa6657e35961b1f5762060717c647e3bf471d5e3b86e783b4e934ffb`。本次未連線驗證上游。

`essay.txt` is copied unchanged in full from local `~/projects/cangjie-fluency/data/essay.txt`. That project's `data/README.md` records upstream [rime/rime-essay](https://github.com/rime/rime-essay), commit `054920de4f54c9e5994276a96a4fc2a35cb51aa3`, 5,887,319 bytes, SHA-256 `3e8512ebaa6657e35961b1f5762060717c647e3bf471d5e3b86e783b4e934ffb`. Upstream was not contacted during this work.

**essay.txt 資料為 LGPL-3.0，不是 MIT。** 授權全文見 `LICENSE-essay.txt`（複製自 cangjie-fluency 的 LICENSE）。本發行保留此區別，未將詞表重新授權為 MIT；沒有包含 GPL 程式碼。Pad 僅讀取詞頻 ≥100 且長度 2–4 的詞，並排除示範碼表缺字的詞；檔案本身沒有刪減。

**essay.txt data is LGPL-3.0, not MIT.** See `LICENSE-essay.txt`, copied from cangjie-fluency's LICENSE. The data is not relicensed as MIT; no GPL code is included. The pad loads frequency ≥100 words of 2–4 characters and excludes words with missing character codes; the bundled data file itself is unabridged.

也可用 `--table /path/to/table.tsv` 換成自己的碼表。格式為 UTF-8 `code<TAB>character<TAB>weight`，小寫 ASCII 碼及非負權重，`#` 開頭為註解。自訂碼表保留原授權；換用發行資料時請更新授權與來源說明。建置腳本只讀取此目錄，不會自動複製研究碼表。

Supply your own table through `--table /path/to/table.tsv`: UTF-8 `code<TAB>character<TAB>weight`, lowercase ASCII codes and nonnegative weights, with `#` comments. Custom data retains its own license; update notices when substituting release data. The builder reads this directory and never automatically imports the research table.
