import os
import sys
import uvicorn
from dotenv import load_dotenv

# 解決 Windows 終端機下 (如 cp950 語系) 輸出 Unicode/Emoji 時產生的 UnicodeEncodeError 錯誤
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 載入 .env 檔案
load_dotenv()


def print_banner(host: str, port: int):
    """印出精美的啟動 Banner"""
    banner = f"""
=================================================================
 ██████╗ ██╗   ██╗ ██████╗██╗      █████╗ ██╗    ██╗
 ██╔══██╗╚██╗ ██╔╝██╔════╝██║     ██╔══██╗██║    ██║
 ██████╔╝ ╚████╔╝ ██║     ██║     ███████║██║ █╗ ██║
 ██╔═══╝   ╚██╔╝  ██║     ██║     ██╔══██║██║███╗██║
 ██║        ██║   ╚██████╗███████╗██║  ██║╚███╔███╔╝
 ╚═╝        ╚═╝    ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝ 
              ★  AI Agent 自動化網關系統  ★
=================================================================
 🚀 系統已成功啟動！
 🌐 前端儀表板網址: http://{host}:{port}
 🔗 WebSocket 端點: ws://{host}:{port}/ws/{{session_id}}
=================================================================
 💡 操作指引：
 1. 雙擊工作區的 `.env` 檔案，將 'your_gemini_api_key_here' 
    替換為您個人的 Google AI Studio Gemini API Key。
 2. 打開瀏覽器訪問上面的 前端儀表板網址。
 3. 在左下角直接輸入中文指令（如 "列出當前工作區所有檔案"），
    即可在右側即時看見 AI 的 Thought 思考軌跡與工具執行畫面！
=================================================================
"""
    print(banner)

if __name__ == "__main__":
    # 獲取配置，預設為 127.0.0.1:8000
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    
    # 確保安全工作區存在
    workspace_dir = os.getenv("AGENT_WORKSPACE", "./agent_workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    
    print_banner(host, port)
    
    # 啟動 Uvicorn 伺服器
    # 關閉 reload 以防範資料庫 (pyclaw.db) 與工作區檔案異動觸發伺服器無限制重啟循環
    uvicorn.run("gateway.server:app", host=host, port=port, reload=False)

