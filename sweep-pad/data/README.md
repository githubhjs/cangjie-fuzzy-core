# 示範碼表 / Demonstration lexicon

`cangjie3.tsv` 是本次撰寫的 27 筆小型示範資料：26 個倉頡字根與需求文件提供的「顏 = yhmbc」。所有權重均為 1，依本專案 MIT 授權。這不是完整字典，無法用來輸入任意中文字。它用來讓獨立發行包可驗證繪圖、解碼及候選操作。

`cangjie3.tsv` is an original 27-entry demonstration lexicon: the 26 Cangjie radicals and `顏 = yhmbc`, supplied in the product brief. Every weight is 1. It is released under this project's MIT license. It is not a complete dictionary and cannot support arbitrary Chinese text. It makes the standalone package usable for decoder and candidate demonstrations.

完整碼表未隨附：現有研究 TSV 由 `mscj3.cin` 與 `essay.txt` 詞頻產生。現有來源文件未提供 `mscj3.cin` 的明確逐檔著作權授權，且 essay 詞頻有 LGPL-3.0 條款；因此不將這些資料重新標示為 MIT 或複製進本發行包。

The full research table is not bundled. Local provenance records show it was generated from `mscj3.cin` and frequencies from `essay.txt`. The available records provide no explicit per-file copyright license for `mscj3.cin`, and identify the essay frequencies as LGPL-3.0. This package does not relabel those assets as MIT or copy them into the archive.

若您有權使用完整碼表，可用 `--table /path/to/table.tsv`。格式是 UTF-8，每行 `code<TAB>character<TAB>weight`，碼為小寫英文字母，權重為非負數。`#` 開頭是註解。自訂碼表的排序與權重會改變候選；請依原資料授權處理。為自己的發行包選用另一碼表時，先放到 `sweep-pad/data/cangjie3.tsv` 並更新本說明及應附授權，再執行建置；建置腳本不會從研究目錄自動取用資料。

If you have a table you are entitled to use, pass `--table /path/to/table.tsv`. Use UTF-8 rows of `code<TAB>character<TAB>weight`, lowercase ASCII codes and nonnegative numeric weights. Lines beginning with `#` are comments. Custom tables and weights change candidate ranking and retain their own license obligations. To make your own archive with a different table, replace `sweep-pad/data/cangjie3.tsv` and update this notice and required license texts before building. The builder never automatically imports research data.
