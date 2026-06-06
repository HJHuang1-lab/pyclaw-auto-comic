# 🎨 PyClaw AI 漫畫家自動化系統 (PyClaw AI Manga Artist Automation System)

PyClaw 是一個基於 ReAct (Reasoning and Acting) 框架的 AI 自動化網關系統。它能自動搜集當日科技趨勢與迷因，並由一個名為 **PyClaw** 的「熱血日系漫畫家 Agent」進行劇本構思、分鏡規劃，再調用 Imagen 生成精美的四格手繪黑白網點風格漫畫，隨後自動備份至 Google Drive 並以 HTML 電子郵件形式寄送給您。

---

## 🚀 核心功能與特色

1. **熱門科技話題自動搜集**：調用網路搜尋技能（`web_search`）搜集當日最新的 AI、半導體或網路迷因素材。
2. **AI 四格分鏡繪製 (Imagen 3/4)**：Agent 會自動將故事設計成四格漫畫，並呼叫圖片生成服務產出四張分鏡手稿（`panel_1.png` 到 `panel_4.png`）。
3. **高品質日系手繪網點 (Manga Screentone)**：產出的漫畫網頁採用日系黑白網點（Screentone）、手繪風粗邊框及速度集中線（Speed Lines）等經典單行本風格排版，並保證對話框與人物臉部不重疊。
4. **Google Drive 雲端自動備份**：採用 **OAuth 2.0 用戶端憑證與 Token 快取機制**。首次在本地授權後，系統會快取 `google_drive_token.json`，後續每日排程將完全在背景靜默上傳備份至雲端 `pyclaw/` 資料夾中，無需彈出瀏覽器。
5. **MIME CID 行內嵌入式電子郵件**：發送的 HTML 通知信中，圖片皆自動打包成 **CID (Content-ID) 資源** 嵌入郵件。這確保圖片不需要任何公網 URL，在任何郵件客戶端（如手機 Gmail app）中都能 100% 直接顯示，並附上線上預覽連結。
6. **AI 推理軌跡即時儀表板**：提供 FastAPI + WebSocket 即時前端，您可以即時看見 PyClaw 的內心思考軌跡 (Thought) 與工具呼叫情況。

---

## 📂 專案目錄結構

```text
Create AI agent workflow/
├── agent/                  # Agent 核心邏輯
│   ├── memory.py           # SQLite 記憶與對話歷程管理 (pyclaw.db)
│   └── runtime.py          # ReAct 推理循環主程序與系統提示詞
├── gateway/                # FastAPI 網關與 WebSocket 伺服器
│   ├── server.py           # 路由、定時排程 API 端點 (/api/cron/generate-comic)
│   └── adapters/           # WebSocket 廣播連接管理
├── skills/                 # Agent 可調用的工具技能
│   ├── registry.py         # 技能註冊器
│   ├── google_drive_skills.py  # Google 雲端硬碟 OAuth 上傳技能
│   └── mail_skills.py      # SMTP 電子郵件發送與 CID 圖片嵌入邏輯
├── web/                    # 儀表板前端靜態網頁
├── agent_workspace/        # Agent 工作目錄 (產生的圖片、HTML 漫畫與 Markdown 腳本均存放於此)
├── main.py                 # 伺服器啟動入口檔案
├── pyclaw.db               # 本地 SQLite 資料庫 (儲存日誌與歷史對話)
├── google_drive_credentials.json # Google Drive 憑證 (用戶端下載)
├── google_drive_token.json # Google Drive 授權快取 Token (自動產生)
├── .env                    # 系統環境變數設定
└── requirements.txt        # Python 依賴庫
```

---

## 🛠️ 環境配置與準備

### 1. 安裝套件
請確保您的 Python 版本為 3.10+，並在專案根目錄下安裝依賴：
```bash
pip install -r requirements.txt
```

### 2. 環境變數設定 (`.env`)
複製 `.env.template` 並命名為 `.env`，填寫以下設定：
```env
# Google AI Studio Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# 使用的模型
GEMINI_MODEL=gemini-2.5-pro
IMAGEN_MODEL=imagen-4.0-generate-001

# 伺服器預設 URL (用於產生圖片的絕對 URL 連結)
BASE_URL=http://127.0.0.1:8000

# SMTP 郵件發送設定 (以 Gmail 應用程式密碼為例)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your_gmail@gmail.com
SMTP_PASSWORD=your_gmail_app_password
NOTIFICATION_RECEIVER=receiver_email@gmail.com

# 排程觸發安全金鑰
CRON_SECRET_KEY=pyclaw_secure_cron_trigger_key_2026

# Google Drive 認證檔案路徑
GOOGLE_DRIVE_CREDENTIALS_PATH=google_drive_credentials.json
GOOGLE_DRIVE_TOKEN_PATH=google_drive_token.json
```

### 3. Google Drive OAuth 2.0 金鑰配置
由於 Google Cloud Organization 政策可能限制建立「服務帳戶金鑰 (Service Account Key)」，本專案已改用 **OAuth 2.0 用戶端憑證** 架構：
1. 前往 [Google Cloud Console](https://console.cloud.google.com/)。
2. 建立新專案，並啟用 **Google Drive API**。
3. 前往 **「OAuth 同意畫面 (OAuth consent screen)」**，設定為 **External** (外部)，並在測試使用者 (Test users) 中加入您要備份的 Gmail 帳戶。
4. 前往 **「憑證 (Credentials)」** ➡️ **「建立憑證 (Create Credentials)」** ➡️ 選擇 **「OAuth 用戶端 ID (OAuth client ID)」**。
5. 應用程式類型選擇 **「桌面應用程式 (Desktop App)」**，完成建立後下載其 JSON 檔案。
6. 將該 JSON 檔案改名為 `google_drive_credentials.json` 並放入本專案根目錄。

*(註：第一次執行時會彈出瀏覽器要求您登入 Gmail 授權，成功後會自動建立 `google_drive_token.json`。此後背景執行均會靜默認證，不再需要任何彈窗或人工干預。)*

---

## 🚀 啟動與測試

### 1. 啟動伺服器
執行 `main.py` 啟動 FastAPI 服務：
```bash
python main.py
```
啟動後您可以訪問前台儀表板：`http://127.0.0.1:8000`

### 2. 手動觸發測試
伺服器運行中時，您可以手動向排程端點發送 POST 請求，觸發一次完整的「靈感搜集 ➡️ 四格繪圖 ➡️ 備份雲端 ➡️ 信件通知」流程：

- **Windows PowerShell (推薦)**:
  ```powershell
  Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/cron/generate-comic?key=pyclaw_secure_cron_trigger_key_2026"
  ```
- **命令提示字元 (cmd.exe / Linux Terminal)**:
  ```bash
  curl.exe -X POST "http://127.0.0.1:8000/api/cron/generate-comic?key=pyclaw_secure_cron_trigger_key_2026"
  ```

---

## 📅 設定每日早上 10 點自動排程

為了讓系統在每天早上 10:00 自動定時生成漫畫並寄出，您可以設定 **Windows 工作排程器 (Task Scheduler)** 或 Linux 的 **Cron Job**：

### Windows 工作排程器配置步驟
1. 開啟 **「工作排程器」**，在右側點擊 **「建立基本工作」**。
2. 輸入名稱，例如：`PyClaw Daily Comic Trigger`。
3. 觸發程序選擇 **「每天」**，並設定開始時間為早上 **`10:00:00`**。
4. 動作選擇 **「啟動程式」**。
5. 在「程式或指令碼」欄位中填入：
   `powershell`
6. 在「新增引數 (選用)」欄位中填入：
   `-Command "Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/cron/generate-comic?key=pyclaw_secure_cron_trigger_key_2026'"`
7. 點選完成。
8. **重要提示**：此排程會向您的本地伺服器發送 POST 請求，因此請確保 `python main.py` 伺服器在早上 10:00 時是處於啟動狀態的。
