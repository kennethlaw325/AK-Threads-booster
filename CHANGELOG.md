# Changelog

What changed in AK體, in plain language.

---

## 2026-05-07 - AK-Threads-Booster 2.0 正式版

AK體 2.0 把系統從「Threads 發文 skill」升級成更完整的個人內容決策作業系統：低 token compiled memory、Next Move Engine、本地面板、Voice Fingerprint、`/draft` 作戰包、安全 `/update`，以及全 agent 通用安裝入口都放進正式版。

這版的重點不是把輸出變長，而是讓日常使用更省 token、更穩、更像用戶本人，也更容易交給任何支援 repo instructions / skill directory 的 agent 使用。

### 全 agent 通用入口

- `AGENTS.md` 是低 token agent router。
- `SKILL.md` 保留給會讀 skill metadata 的 agent。
- 移除特定 agent 平台專屬的 plugin metadata 與安裝說明。
- GitHub / GitLab README 會分別使用對應平台的安裝 URL。

### `/voice` 升級成創作基因蒸餾

`/voice` 從「讀完整 tracker 後直接分析文風」升級成兩段式蒸餾：本地腳本先做確定性統計，AI 再負責認知層、張力、禁區與 `/draft` 可用化。目的不是產出更長的 Brand Voice，而是讓 `/draft` 更像用戶本人會想、會切、會寫。

### 新增 `/update`：安全檢查新版與選擇性自動更新

AK體新增 `/update` 模組，可以檢查 GitHub 上的 AK-Threads-Booster 是否有新版，也可以在用戶明確同意後安裝每週自動檢查更新。

更新邏輯走 `scripts/check_skill_update.py`：

- 只允許 clean repo 的 fast-forward 更新。
- 如果有本地修改、未追蹤檔案、local-only commits 或衝突，會停下回報。
- 不會自動 reset、rebase、stash 或覆蓋本地檔案。
- 每次檢查或更新後，會主動問用戶要不要開啟每週自動檢查，但不會預設開啟。
- 即使用戶沒有主動輸入 `/update`，在第一次 `/setup`、安裝說明或 skill 維護情境中，AK體也會主動告知這個選項並詢問是否開啟。

### 新增 Voice Fingerprint

新增 `scripts/build_voice_distillation.py`，會從 `threads_daily_tracker.json` 產生：

- `compiled/voice_fingerprint.md`
- `compiled/voice_fingerprint.json`

它會先算出高互動貼文、開頭 / 結尾模式、段落節奏、常用轉折詞、標點、英文混用、留言回覆語氣、候選信念句、反 voice 候選與校準錨點。這些是 runtime cache，不取代 tracker。

`scripts/build_compiled_memory.py` 現在也會一起重建 voice fingerprint，所以更新 compiled memory 時不會漏掉 `/voice` 的新底稿。

### `/voice` 新增認知層

`/voice` 現在會把分析從 14 維擴成 15 維，新增：

- 核心信念
- 判斷框架
- 觀點張力
- 信念邊界

每個重要結論都要標注它是高互動 pattern、近期穩定 pattern、歷史 pattern，還是薄弱證據。這可以避免把很久以前的寫法硬塞進現在的 `/draft`。

### Brand Voice 變成 `/draft` 可執行作戰包

`brand_voice.md` 模板新增：

- `Cognitive Core`
- `Voice Fingerprint`
- `Anti-Voice / Forbidden Zone`
- `/draft Quick-Reference Pack`
- `Calibration Pairs`

這些 section 讓 `/draft` 不只是模仿句型，而是先對齊用戶的立場、判斷方式、開頭/結尾習慣，以及哪些寫法一碰就不像本人。

### `/draft` 讀取優先級更新

`/draft` 現在會優先讀：

1. Manual Refinements
2. Cognitive Core
3. `/draft Quick-Reference Pack`
4. Anti-Voice / Forbidden Zone
5. Voice Fingerprint

如果舊版 `brand_voice.md` 還沒有這些 section，`/draft` 會提醒重新跑 `/voice`，而不是假裝 voice baseline 已經夠精準。

### 新增 `/optimize`：把 compound log 嘅 misses 變成可審核嘅 sub-skill rule edits

`/optimize` 之前係 compound log 形式（2026-04-25 引入），AK體 2.0 將佢正式升級成獨立 sub-skill：

- 讀 `threads_skill_learnings.log` 入面 ≥ 2 條同 `(sub_skill, category)` cluster 嘅 entry。
- 對每個 cluster 草擬一個 sub-skill rule edit 提案，附 user_signal 引文做依據。
- 用戶逐個 approve / reject，唔會自動改 SKILL.md。
- Reject 嘅提案 log 入 `skills/optimize/references/rejected-proposals.md` 做 dedupe signal，避免下次重複建議。

### 新增 `evals/` 評估層

獨立 fixture-based 評估層保護 sub-skill 行為唔靜默回退：

- `evals/rubric.md` — canonical scoring rubric。
- `evals/fixtures/` — 7 個 minimal reproducible test case。
- `evals/runbook.md` — 點樣手動或用 evaluator agent 跑 eval pass。

### 版本

- Main `SKILL.md`：`2.0.0`
- 全部 sub-skill：`2.0.0`
- Runtime budget policy：`2.0.0`
- Compiled memory schema：`2.0.0`

---

## 2026-04-26 - 新增本地視覺面板：把帳號狀態變成可以看的儀表板

AK體多了一個本地視覺面板。你不需要再打開 tracker JSON、也不用翻 markdown 檔，就能在一頁看到帳號全貌、最近趨勢、最強主題、留言訊號跟 compiled memory。面板本身完全本地、零 token — 看數據不花用量，AI 動作要按下按鈕才觸發。

### 為什麼會想要這個面板

- **寫貼文前先掃一眼，比直接叫 `/analyze` 省 token**。30 秒掃完帳號狀態，再決定要不要花 token 進 AI 流程。
- **不用切到 IDE 就能看 compiled memory**。下一步行列、帳號診斷直接呈現在畫面上。
- **Demo 給合作對象看更直覺**。不需要解釋 tracker JSON 是什麼，直接秀畫面。
- **非技術用戶也能用**。匯入 tracker JSON 就跑，不需要 Python，不需要懂指令列。

### 一頁看完整個帳號

- **帳號總覽**：貼文數、總觀看、互動率三張指標卡，每張都帶「過去 14 天 vs 再前 14 天」的趨勢晶片，紅綠箭頭一眼看出最近狀態走升還是走跌。
- **觀看曲線 + 中位數基準線**：最近 14 天的觀看曲線會疊一條虛線基準，落在線上是「比平常好」、線下是「比平常差」，不需要心算。
- **重點窗口**：最佳貼文、最強主題、最近一篇拉到最上面，不用往下捲。
- **下一步行列 + 帳號訊號**：自動讀取 compiled memory，演算法 / 心理 / 反 AI 三軸診斷直接顯示。
- **可讀檔案**：歷史貼文（按時間 / 按主題）、留言記錄全部 markdown 排版渲染，標題、清單、粗體都正確呈現，不再是 raw text。
- **貼文檢視**：可以搜尋、按主題 / 類型 / 時間過濾，點任一篇就能看完整內文跟所有指標。

### 啟動方式

```
python scripts/panel_server.py --open
```

會自動找 tracker、companion 檔、compiled memory。如果資料在另一個資料夾，加 `--data-root <path>`。沒有 Python 也能直接用瀏覽器打開 `panel/index.html`，匯入 tracker JSON 即可。

也可以在 Skill 裡用 `/panel` 觸發。

### 零 token 預設

面板本身不會發出任何 AI 請求：

- 圖表、排序、過濾、搜尋都在瀏覽器本地計算。
- **分析 / 預測 / 檢查** 三顆按鈕會把選中的貼文打包成 prompt，放在面板下方的文字框，要送出時才複製給 AI。
- **重建 compiled memory** 在本地執行 `scripts/build_compiled_memory.py`，產生新的低 token 記憶檔，下次叫 Skill 直接用。

### 介面設計

- **編輯級配色**：單一 indigo 強調色 + 中性紙白底，沒有粉彩漸層或裝飾色塊。
- **Light / Dark 自動切換**：跟著作業系統設定走，不需要手動。
- **中英雙語**：一鍵切換，整個面板（含 i18n label）都會跟著翻譯。
- **真 SVG 圖示**：topbar 五顆按鈕（語言、資料夾、Tracker、範例、重建）改用 inline SVG，沒有外部依賴、沒有字型 CDN。
- **Markdown 渲染**：compiled memory 跟 companion 檔內的 H1~H4、有序/無序清單、粗體、斜體、行內程式碼、程式區塊全部正確排版。
- **資料密度優化**：1440px 寬之下，hero → 重點窗口 → command center 變成清楚的「概覽 → 重點 → 操作」垂直節奏。

### 新增檔案

- `panel/`：靜態 HTML / CSS / JS，零外部依賴。
- `scripts/panel_server.py`：dependency-free 本地 server，可選 `--data-root` / `--open`。
- `skills/panel/SKILL.md`：`/panel` 指令模組。

---

## 2026-04-25 - AK體架構加固：更省 token、更穩、更會判斷下一篇

這次更新把 AK體從「會分析與寫文」升級成更完整的 Threads 經營判斷系統。核心改進是：日常使用更省 token，判斷更一致，下一篇內容不再從零猜，而是根據帳號狀態、演算法訊號、受眾心理與反 AI 風格一起判斷。

### 更省 token 的日常模式

AK體現在會把歷史資料整理成低 token 記憶檔，日常分析不需要每次重讀完整 tracker 和大型知識庫。

新增與強化的低 token 檔案包括：

- `compiled/account_wiki.md`：帳號基本狀態與歷史摘要。
- `compiled/account_state.md`：三軸帳號診斷。
- `compiled/personal_signal_memory.md`：這個帳號自己的演算法、心理、反 AI 訊號記憶。
- `compiled/next_move_queue.md`：下一篇可以考慮的方向。
- `compiled/post_feature_index.jsonl`、`cluster_wiki.json`、`recent_window.md`：用來快速比對歷史貼文、題材重複與近期狀態。

使用上會更快，也比較不容易因為一次分析就消耗大量 Agent 用量。

### 新增低 token / 高 token 選擇

當設定還沒固定時，Skill 會先問用戶這次要用哪種模式：

- **低 token 版**：比較快、省用量，適合日常檢查、一般選題、普通草稿。
- **高 token 版**：讀得更深，適合重要貼文、微妙風格判斷、演算法邊界問題，但比較慢也比較花用量。

用戶可以把偏好設成固定模式，也可以之後再改。

### 新增三軸帳號診斷

AK體現在會把帳號狀態拆成三個面向：

- **演算法狀態**：最近觸及、留言率、分享率、題材重複、紅線風險。
- **受眾心理狀態**：現在更需要信任、共鳴、具體經驗、可轉述觀點，還是高品質討論。
- **反 AI 狀態**：內容是否太完整、太工整、太像整理文，缺少人的判斷、限制感與現場感。

這些判斷都仍然以 `threads_daily_tracker.json` 為準。低 token 檔案只是整理後的快取，不會取代原始資料。

### 新增 Next Move Engine

AK體不再只問「下一篇要寫什麼」，而是先判斷「下一篇最該補哪個成長瓶頸」。

可能的方向包括：

- **補人格判斷**：資訊量夠，但人的立場、經驗、取捨不夠明顯。
- **澄清分歧**：需要提高討論密度，但避免變成吵架或釣留言。
- **擴散型實用觀點**：需要讓非粉也能一眼理解、收藏或轉發。

每個方向都必須先通過 AK體內建演算法規則：避開紅線，再確認要強化哪個正向訊號，最後才用心理學與反 AI 檢查調整表達方式。

這不是公式庫，也不是爆文模板。它的用途是讓用戶更清楚知道：下一篇為什麼該這樣寫。

### 演算法紅線更一致

`/analyze` 和 `/draft` 現在共用同一份紅線規則，不再各自維護一套判斷。

這代表同一段內容在分析與草稿階段，應該會得到一致的紅線判斷，例如：

- 互動誘導
- 標題黨
- 開頭與內文不一致
- 低原創性
- 連續同題材
- 低品質外部連結
- AI 內容標示與人格感問題

如果踩到明確紅線，AK體會直接提醒，因為這類問題可能影響分發。

### 輸出更像顧問，不像報告機

面向用戶的輸出會更精簡、更決策導向：

- 日常 `/analyze` 預設用 brief mode，只輸出真正重要的風險、機會與具體修改點。
- 不主動整篇重寫用戶已經寫好的貼文，只給「哪裡、為什麼、怎麼改」。
- 輸出會跟隨用戶使用的語言。用戶用中文，就少用不必要的英文術語；用戶用英文，就可以正常使用英文專業術語。`S2`、`R5` 這類 AK體內部代號第一次出現時仍會解釋。

### 更安全的資料更新

會寫入 tracker、style guide、concept library 或設定檔的流程，現在統一走備份與安全寫入規則：

- 寫入前先備份。
- 使用暫存檔再替換，降低寫壞檔案風險。
- 舊備份會自動控制數量。
- compiled memory 是快取，可以重建，不會當成唯一資料來源。

### 新增自我優化閉環

AK體現在可以把使用過程中確認的錯誤或漏判記錄下來，再透過 `/optimize` 轉成後續規則更新。

這個流程不會自動亂改。只有當用戶明確指出「這次判斷錯了」或「這裡漏掉了」，才會進入學習記錄。

### 新增維護與測試基準

新增 `evals/` 測試規則，讓後續維護可以檢查：

- `/analyze` 不應主動整篇改寫。
- `/draft` 不能跳過 freshness gate。
- 紅線判斷要一致。
- 寫入流程要有備份。
- Next Move 不能退化成公式庫。
- 用戶輸出要跟隨用戶語言；中文情境不堆英文術語，英文情境保留專業英文表達。

### 版本

- Main `SKILL.md`：`1.2.2`
- `setup`：`1.2.1`
- `analyze` / `draft` / `review`：`1.2.2`
- `topics` / `predict`：`1.1.2`
- Runtime budget policy：`1.1.0`
- Eval rubric：`1.2.2`

---

## 2026-04-22 - 第一版優化：寫稿前先對齊，品牌聲音不再當成死規則

這一版的重點，是讓 AK體不要太快直接產稿，而是先跟用戶對齊角度、事實與語氣。它讓寫稿流程更像合作，不像按一下就吐出一篇。

### `/draft` 寫稿前會先討論

研究與查證完成後，AK體不會直接開寫，而是會先問幾個跟這篇內容有關的問題，例如：

- 這個角度要不要採用？
- 這個說法是否有你的第一手經驗？
- 有沒有需要先避開的爭議或留言區反駁？
- 這篇要走更保守，還是更有立場？

這讓草稿比較不容易偏題，也比較不容易把用戶沒說過的事寫成確定事實。

### 討論模式可以開關

用戶可以決定 `/draft` 要不要每次都跟自己討論：

- **只這次**：這次討論，下次再問。
- **always on**：以後都先討論。
- **always off**：以後直接產稿，適合想要快一點的流程。

設定會存在 `threads_booster_config.json`，之後可以再改。

### 個人事實以用戶自己的內容為準

如果草稿涉及用戶自己的經歷、事件順序、做過的事，AK體會以用戶自己的貼文與手動補充為準。網路搜尋不能推翻用戶自己的歷史內容。

查不到或不確定的個人細節，會標成 `[confirm with user]`，不會自己猜。

### `/voice` 變成可修正的聲音初稿

`/voice` 產出的品牌聲音不再被當成不可更動的定稿，而是「可校正的初稿」。

新增重點：

- 會更細地分析用詞、開頭、收尾、標點、節奏、中英夾雜與論證習慣。
- 新增 `Manual Refinements` 區塊，讓用戶自己補「這裡不準」、「我不會這樣講」、「這句很像我」。
- 之後重跑 `/voice` 時，會保留用戶手動修改，不會直接覆蓋。

這讓 Brand Voice 更接近用戶自己認可的聲音，而不是 AI 單方面整理出來的印象。

### `/analyze` 和 `/review` 也能追問

分析或檢討完成後，AK體可以補問幾個針對該篇內容的問題，幫用戶決定要不要深入調整。這跟 `/draft` 使用同一組討論偏好。

### `/review` 會回看當初的寫稿決策

如果一篇文先經過 `/draft` 討論，後續 `/review` 可以回頭看當初採用或放棄了哪些角度，再對照實際表現。這讓每一次發文不只是單次結果，而是能累積成下次判斷的依據。

### 新增檔案

- `threads_booster_config.json`：保存討論模式、runtime 偏好等設定。
- `CHANGELOG.md`：記錄 AK體的產品更新。
