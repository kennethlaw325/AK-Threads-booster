[中文](README.md) | [English](README.en.md)

# AK體 2.0 - 基於 Threads 演算法的創作決策 skill

AK-Threads-Booster 是這個 skill 的內部代號與安裝 id。

AK-Threads-Booster 是一套給 Threads 創作者用的 AI skill 系統。

它不是要幫你亂寫一堆貼文，而是幫你把「選題、起草、分析、預測、復盤」變成一套有資料依據的工作流，讓你更容易發出值得被分享、收藏、討論的內容。

如果你平常的痛點是這些：

- 不知道下一篇到底該寫什麼
- 有很多題目，但分不出哪個更值得先發
- 文章不是寫不好，只是常常撞題、老梗、沒新鮮度
- 想讓內容更像自己，不想一看就很 AI
- 發完之後沒有把結果整理回來，下一篇又從零猜

這套 skill 就是為這些問題設計的。

它不保證爆文。

它做的是讓你用自己的歷史資料，提高每一次發文決策的品質，讓「更有擴散機會」這件事變得比較可複製。

---

## 2.0 新增什麼

2.0 的重點是把 AK體從單次發文輔助，升級成更完整的 Threads content operating system。

- **低 token compiled memory**：把 tracker 編譯成帳號 wiki、貼文特徵索引、主題 cluster、下一步行列和 voice fingerprint，日常分析先讀快取，省 token、速度更快。
- **Next Move Engine**：不只推薦題目，而是先判斷帳號下一篇應該補哪個成長瓶頸，例如人格判斷、討論密度、收藏價值、題材新鮮度或反 AI 感。
- **Voice + Cognitive + Draft Operating Pack**：新版 `/voice` 先用本地腳本建立聲音指紋，再蒸餾核心信念、判斷張力、反 voice 禁區和 `/draft` 可直接使用的作戰包。
- **本地 visual panel**：用零 token 查看帳號狀態、最近趨勢、最強貼文、主題分布、compiled memory 和下一步建議。
- **安全 `/update`**：可以檢查新版，也可以在用戶同意後開啟每週自動檢查；只做 clean repo fast-forward，不覆蓋本地修改。
- **全 agent 通用包裝**：移除特定 agent 平台專屬安裝入口，改用 `AGENTS.md` / `SKILL.md` / `agents/openai.yaml`。

---

## 這套 skill 會幫你做什麼

### 1. 幫你選出更值得發的題

`/topics` 不是單純丟熱門題給你。

它會一起看：

- 你的歷史貼文表現
- 留言裡反覆出現的問題
- 你自己曾經回過哪些問題
- 最近有沒有撞到同一個 semantic cluster
- 外部話題現在是不是已經過熱

也就是說，它不只是找「熱門」，而是找「對你這個帳號來說，現在更值得發」的題目。

### 2. 幫你起草，但盡量像你

`/draft` 會根據：

- `brand_voice.md`
- `style_guide.md`
- 歷史貼文
- concept library

來起草一篇比較接近你語感的內容。

而且它不是拿到題目就直接寫：

- 先做 freshness gate，避免你花時間寫一個已經被寫爛的角度
- 做 fact-check，但**不會動你自己說過的個人事實與事件順序**（你的貼文是 source of truth）
- research 時會主動丟「你可能沒想到的 2-3 個角度」給你選，幫貼文變更豐富
- 寫完以後會回問 3-5 個針對這篇的改進問題，不是罐頭提問

這些對話功能都是開關式的——第一次會問你要不要開，也可以設成 always on / always off，存在 `threads_booster_config.json`。想要快就快，想要深就深。

### 3. 幫你在發文前做最後判斷

`/analyze` 是這套 skill 的 decision layer。

它會看：

- 有沒有演算法紅線
- 這篇最大的上升空間在哪
- 主要卡點在哪
- 比較像 follower-fit 還是 stranger-fit
- 有沒有 AI 味太重

這樣你在按下發送前，不是只靠感覺。

### 4. 幫你建立比較合理的預期

`/predict` 會用相似歷史貼文幫你估 24 小時的可能區間，讓你不要因為單篇波動就誤判。

### 5. 幫你把發文結果變成下一次的優勢

`/review` 會把實際表現、預測偏差、風格訊號再寫回 tracker。

這點很重要，因為很多工具只會給你建議，不會讓系統越用越準。這套 skill 的重點就是把學到的東西留下來。

### 6. 幫你更新 tracker，不用每次手動整理

`/refresh` 可以更新 `threads_daily_tracker.json`：

- 有 Threads API token 就走 API
- 沒有 API 就走已登入的瀏覽器自動化環境抓自己的 Threads profile

你不用每次都自己慢慢補資料。

### 7. 幫你蒸餾更像本人的 Brand Voice

`/voice` 會把歷史貼文變成更可執行的 Brand Voice：

- 先算高互動貼文、開頭/結尾模式、段落節奏、常用轉折、標點和中英混用
- 再提取你的核心信念、判斷框架和觀點張力
- 標出哪些寫法是穩定聲音、哪些只是舊風格或薄弱證據
- 產出 `/draft` 可以直接用的 Quick-Reference Pack 和 Forbidden Zone

這讓 `/draft` 不只模仿句型，而是更接近你的內容基因。

### 8. 幫你用零 token 看帳號狀態

`/panel` 會開啟本地 visual panel，讓你不用翻 JSON 也能看：

- 帳號總覽和最近趨勢
- 最強貼文和主題分布
- 貼文搜尋與篩選
- compiled memory 和 next move queue

面板本身不會呼叫 AI。你可以先看資料，再決定要不要把某篇交給 agent 分析。

### 9. 幫你安全更新 skill

`/update` 可以檢查 GitHub 上是否有新版。

它只會在本地 repo 乾淨、可以 fast-forward 時更新；如果你有本地修改、local-only commits 或衝突，它會停下回報，不會自動覆蓋。

---

## 最適合誰

這套 skill 特別適合：

- 已經有固定在經營 Threads 的人
- 想把發文從「靈感型」變成「決策型」的人
- 想更穩定找到下一篇題目的人
- 想知道自己什麼內容比較有機會擴散的人
- 想把歷史貼文真的變成可用資產的人

如果你現在還完全沒有歷史資料，它也可以用，但前期的判斷會比較弱。這套系統的價值，會隨著你的資料累積而變強。

---

## 第一次使用你會得到什麼

跑完 `/setup` 之後，工作目錄通常會有：

- `threads_daily_tracker.json`
- `style_guide.md`
- `concept_library.md`
- `brand_voice.md`（如果有跑 `/voice`）
- `compiled/account_wiki.md`
- `compiled/account_state.md`
- `compiled/next_move_queue.md`
- `compiled/post_feature_index.jsonl`
- `compiled/voice_fingerprint.md` / `.json`（如果有重建 compiled memory 或跑新版 `/voice`）
- `posts_by_date.md`
- `posts_by_topic.md`
- `comments.md`

其中最重要的是 `threads_daily_tracker.json`。

其他檔案都是圍繞這份 tracker 產生的 companion 或 runtime cache。tracker 永遠是 source of truth，compiled memory 可以重建，不需要手動改。

---

## 建議使用流程

### 第一次使用

```text
/setup
/voice
```

先把歷史資料整理好，再把 Brand Voice 建起來。新版 `/voice` 會先用本地腳本做 voice fingerprint，再讓 AI 蒸餾認知層、反 voice 禁區和 `/draft` 作戰包。

`/voice` 產出的 `brand_voice.md` 是**參考初稿**，不是定稿。LLM 從外部看你的貼文一定會漏東西。建議：

- 直接改檔案裡任何覺得不對的地方
- 最下面的 **Manual Refinements** 區塊用來補分析漏掉的、你自己知道的細節（禁用詞、必做事項、「這不是我」的例子）
- 重跑 `/voice` 會保留你改過的內容，不會覆蓋掉

`/draft` 會把 Manual Refinements 當硬約束讀，優先級高於其他章節；接著讀 Cognitive Core、Quick-Reference Pack、Anti-Voice 和 Voice Fingerprint。

### 平常發文前

```text
/topics
/draft
/analyze
```

這是最實用的一組流程：

- `/topics` 找題
- `/draft` 起草
- `/analyze` 發文前檢查

### 發完之後

```text
/predict
/review
```

這樣系統會慢慢知道：

- 你估得準不準
- 哪些題真的會跑
- 哪些風格只是你以為有效

### 想先看帳號狀態

```text
/panel
```

或在本機執行：

```bash
python scripts/panel_server.py --open
```

面板適合在寫文前先掃 30 秒，決定這次要不要進入 `/topics` 或 `/analyze`。

---

## 資料可以怎麼進來

你可以用這些方式建立資料：

- Threads Developer API token
- Meta 官方匯出 zip
- 既有 JSON / Markdown / CSV
- 已登入 Threads 的瀏覽器自動化環境
- 舊版 tracker migration

API 不是必須，但如果你有 API，更新會輕鬆很多。

---

## 產品定位

AK-Threads-Booster 是一套以你的 Threads 歷史資料為核心的內容決策系統。

它的重點不是自動亂生文，而是幫你：

- 找出更值得發的題目
- 起草更接近你自己的內容
- 避開明顯的重複與紅線
- 把每次發文結果累積成下一次判斷的依據

---

## 安裝與使用

把這個 GitHub repo 給你的 agent：

```text
https://github.com/akseolabs-seo/AK-Threads-booster
```

支援 skill / repo instructions 的 agent 可以直接讀 `AGENTS.md` 或 `SKILL.md`，再依你的指令進入 `/setup`、`/voice`、`/topics`、`/draft`、`/analyze` 等模組。

支援 OpenAI/Codex-style discovery 的環境也可以讀 `agents/openai.yaml` 作為 UI metadata。

也可以手動 clone：

```bash
git clone https://github.com/akseolabs-seo/AK-Threads-booster.git
```

再依你使用的工具，把這個 repo 放到對應的 skill / agent instructions 目錄即可。

### 更新與自動更新

安裝後可以用 `/update` 檢查 AK-Threads-Booster 有沒有新版。

`/update` 會主動問你要不要開啟每週自動檢查更新。開啟後只有在本地 repo 乾淨、可以 fast-forward 時才會更新；如果你有本地修改、local commits 或衝突，它會停下回報，不會覆蓋你的東西。

---

## 目錄結構

```text
AK-Threads-booster/
|- SKILL.md
|- AGENTS.md
|- agents/
|  |- openai.yaml
|- skills/
|  |- setup/SKILL.md
|  |- refresh/SKILL.md
|  |- analyze/SKILL.md
|  |- draft/SKILL.md
|  |- predict/SKILL.md
|  |- review/SKILL.md
|  |- topics/SKILL.md
|  |- voice/SKILL.md
|  |- panel/SKILL.md
|  |- update/SKILL.md
|  |- optimize/SKILL.md
|- knowledge/
|  |- _shared/
|  |- psychology.md
|  |- algorithm.md
|  |- ai-detection.md
|  |- data-confidence.md
|  |- chrome-selectors.md
|- scripts/
|  |- fetch_threads.py
|  |- parse_export.py
|  |- build_compiled_memory.py
|  |- build_voice_distillation.py
|  |- check_skill_update.py
|  |- panel_server.py
|  |- update_snapshots.py
|  |- update_topic_freshness.py
|  |- render_companions.py
|- panel/
|- templates/
|- examples/


```
## Star History

<a href="https://www.star-history.com/?repos=akseolabs-seo%2FAK-Threads-booster&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=akseolabs-seo/AK-Threads-booster&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=akseolabs-seo/AK-Threads-booster&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=akseolabs-seo/AK-Threads-booster&type=date&legend=top-left" />
 </picture>
</a>

---

## License

MIT License. See [LICENSE](./LICENSE).
