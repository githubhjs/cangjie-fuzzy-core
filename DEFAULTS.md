# 預設值的依據 / Why these defaults

三個旋鈕，預設值由模擬研究（`tests/range_study.py`，結果在 `results/range_study.md`）和已發表的打字錯誤數據決定。
Three knobs. The defaults come from a simulation study (`tests/range_study.py`, results in `results/range_study.md`) and published typing-error data.

| 旋鈕 / Knob | 預設 / Default | 意思 / Meaning | 怎麼改 / How to change |
|---|---|---|---|
| 範圍 `theta` / range | **1.3** | 兩個鍵的中心距離（以一個鍵寬為單位）不超過 θ 就算相鄰。1.0 = 只有左右；1.3 = 再加斜向；1.8 = 再多一圈。 / Keys are neighbours when their centres are within θ key widths. | 桌面 Rime：安裝時 `-FuzzyRange` / `--fuzzy-range narrow\|normal\|wide`（1.0／1.3／1.8），或 `generator/make_profiles.py --theta 1.5`。程式庫：`FuzzyConfig(theta=…)`。 |
| 每碼容錯 `per_code` / per code | **1** | 一個字的碼裡最多可以有幾個鍵打錯。 / Wrong keys tolerated inside one character's code. | 程式庫 `FuzzyConfig(per_code=…)`；Rime 產生器 `make_profiles.py --tolerance 2`（索引會變很大）。 |
| 每句容錯 `phrase` / per phrase | **碼數的 40%（無條件進位），至少 2** | 一個詞組裡最多可以有幾個碼被容錯修正，用百分比表示。 / Codes of one phrase that may be corrected, as a share of its length (rounded up), floor 2. | 程式庫 `FuzzyConfig(phrase_fraction=…, phrase_min=…)`（Python 與 Kotlin 相同）。**桌面 Rime 的詞組組句引擎沒有「每句上限」這個鉤子，所以桌面版只有每碼容錯；每句上限只在我們自己的比對器（Android、程式庫）生效。** |

## 研究結果摘要 / Study results (simulation, 6000 characters per cell)

Simulated user: each key press is wrong with probability p; a wrong key is a physical neighbour with probability 0.5, else a random key.

**範圍 θ（每碼容錯 1）/ Range θ (per code 1)** — 前五名內找回打錯的字 / intended character within the top 5:

| p（每鍵錯誤率） | 不容錯 | θ=1.0 | θ=1.3（預設） | θ=1.8 | θ=2.2 |
|---|---|---|---|---|---|
| 1% | 96.6% | 97.7% | 98.5% | 98.6% | 98.8% |
| 2% | 92.5% | 94.5% | 96.2% | 96.3% | 96.8% |
| 5% | 83.3% | 87.7% | 92.0% | 92.1% | 92.9% |

- θ=1.3 是拐點：從 1.0 到 1.3 補回約一半的差距；1.3 以上幾乎沒有增益（1.5 和 1.3 完全相同，因為鍵盤上這兩個距離之間沒有任何鍵）。
- 正確打字時多出來的候選：θ=1.0 平均 1.5 個；1.3 平均 3.3 個；2.2 平均 6.9 個。
- Knee at 1.3: from 1.0 to 1.3 recovers about half of the gap; beyond 1.3 almost nothing is gained while noise grows (extra candidates when typing correctly: 1.5 / 3.3 / 6.9 at θ 1.0 / 1.3 / 2.2).

**每碼容錯 / Per code** — 容錯 2 個鍵在 5% 錯誤率下只多找回 0.4 個百分點（92.0→92.4%），卻讓正確打字時多出的候選從 3.3 個變成 11.5 個，51% 的候選清單超過一頁。所以預設是 1。 / Two wrong keys per code add 0.4 points at 5% error but make 51% of candidate lists longer than one page, so the default is 1.

**每句 / Per phrase** — 一個詞組裡真正需要修正的碼很少：5 個字、每鍵錯誤率 5% 時，上限 2 找回 66.2%，不設上限 66.6%；8 個字、5%：上限 3 找回 50.3%，不設上限 50.6%。「碼數的 40%、至少 2」可保留不設上限時 99% 以上的還原率，同時限制雜訊。 / Cap at 40% of the codes (min 2) keeps ≥ 99% of the recovery of an unlimited setting.

## 已發表的數據 / Published data used to calibrate the model

- 實體鍵盤未更正的錯誤率平均 1.17%（Dhakal, Feit, Kristensson, Oulasvirta, CHI 2018, 136M keystrokes）；更正過的錯誤另計。我沒能確認該論文各錯誤類型百分比的分母，所以只引用 1.17% 這一個數字。
- 替換錯誤裡「相鄰鍵」的比例：新手 59% 為同排相鄰、另加 8% 為同欄上下；熟手 31%＋16%；Lessenberry 語料 43%＋15%（Grudin 1983, *Error Patterns in Novice and Skilled Transcription Typing*）。合計約 47%–67%，我的模擬用 50%。這個合計是我加總得到的，論文沒有直接給出。
- 觸控螢幕：6.6%–10.7% 的點擊落在目標鍵之外（Azenkot & Zhai, MobileHCI 2012）。
- 中文形碼輸入法（倉頡、五筆）每碼打錯幾個鍵的研究：**沒有找到**。所以模擬的錯誤率範圍（1%–5%）是假設，對實體鍵盤偏悲觀（相鄰鍵替換約只有 0.2%–0.4% 每鍵，是我用上面數字估算的），對觸控螢幕較貼切。
- Typing error rates and adjacency shares are from the papers above; no study of Cangjie/Wubi per-code error counts was found, so the simulated rates are assumptions.

## 限制 / Limits

模擬沒有模型：插入、漏打、對調（不在這個功能範圍）、真實使用者的錯誤分布是否均勻、語言模型對排序的影響。建議在你自己的打字紀錄上重跑 `tests/range_study.py`（它接受任何碼表）。
Not modelled: insertions, omissions, transpositions (outside this feature), non-uniform real-user error distributions, language-model re-ranking. Re-run `tests/range_study.py` on your own data.
