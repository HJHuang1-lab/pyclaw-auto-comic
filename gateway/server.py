import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List

from skills.registry import registry
from agent.runtime import AgentRuntime
from gateway.adapters.web_adapter import web_manager

app = FastAPI(title="PyClaw Gateway Server")

# 允許跨域請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 Agent 執行核心與資料庫記憶
runtime = AgentRuntime()

# 技能開關請求結構
class ToggleSkillRequest(BaseModel):
    name: str
    enabled: bool

# 接收 REST 傳送訊息結構
class MessageRequest(BaseModel):
    session_id: str
    message: str

# --- REST APIs ---

@app.get("/api/skills")
def get_skills():
    """獲取系統中所有已安裝技能及啟用狀態"""
    skills = []
    for s in registry.get_all_skills():
        skills.append({
            "name": s["name"],
            "description": s["schema"]["description"],
            "category": s["category"],
            "enabled": s["enabled"],
            "doc": s["doc"]
        })
    return {"skills": skills}

@app.post("/api/skills/toggle")
def toggle_skill(req: ToggleSkillRequest):
    """開啟或關閉指定技能"""
    if req.name not in registry.skills:
        raise HTTPException(status_code=404, detail=f"找不到技能: {req.name}")
    registry.skills[req.name]["enabled"] = req.enabled
    state = "啟用" if req.enabled else "停用"
    return {"status": "success", "message": f"技能 '{req.name}' 已被{state}。"}

@app.get("/api/history/{session_id}")
def get_history(session_id: str):
    """獲取對話歷史紀錄"""
    messages = runtime.memory.get_messages(session_id)
    return {"session_id": session_id, "messages": messages}

@app.get("/api/canvas/{session_id}")
def get_canvas(session_id: str):
    """獲取該對話 session 的 AI 思考與工具執行日誌 (即時畫布)"""
    logs = runtime.memory.get_execution_logs(session_id)
    return {"session_id": session_id, "logs": logs}

@app.post("/api/clear/{session_id}")
def clear_session(session_id: str):
    """清空會話歷史"""
    runtime.memory.clear_session_data(session_id)
    return {"status": "success", "message": "對話紀錄與畫布日誌已成功清除。"}

@app.post("/api/chat")
async def chat_endpoint(req: MessageRequest):
    """
    透過 HTTP 傳送指令的非同步 REST 接口。
    會將執行日誌透過 WebSocket 廣播，並返回最終回答。
    """
    async def ws_callback(log_entry: Dict[str, Any]):
        await web_manager.send_to_session(req.session_id, {
            "event": "log",
            "data": log_entry
        })
        
    final_answer = await runtime.run(req.session_id, req.message, callback=ws_callback)
    return {"status": "success", "response": final_answer}

# --- WebSocket 即時通訊端點 ---

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await web_manager.connect(session_id, websocket)
    
    # 發送連接成功信號，並傳送當前狀態
    await websocket.send_json({
        "event": "system",
        "data": {
            "status": "connected",
            "message": f"已成功連接到 PyClaw WebSocket。Session: {session_id}"
        }
    })
    
    try:
        while True:
            # 接收前端發送的指令文字
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
                user_msg = message_data.get("message", "").strip()
            except Exception:
                user_msg = data.strip()
                
            if not user_msg:
                continue
                
            # 定義 callback 用於向 WebSocket 客戶端即時廣播思考、工具調用和結果
            async def ws_callback(log_entry: Dict[str, Any]):
                await web_manager.send_to_session(session_id, {
                    "event": "log",
                    "data": log_entry
                })
                
            # 在背景非同步執行 Agent Runtime，防範阻塞接收其他訊息
            # 這裡直接 await 執行，因為對話通常是序列的。如果需要，也可以創建成 background task。
            await runtime.run(session_id, user_msg, callback=ws_callback)
            
    except WebSocketDisconnect:
        web_manager.disconnect(session_id, websocket)
    except Exception as e:
        web_manager.disconnect(session_id, websocket)

# --- 定時自動化排程 API 與背景處理任務 ---

async def execute_automated_comic_generation():
    import datetime
    # 使用包含時間戳記的唯一會話 ID，避免因為歷史紀錄累積而導致 Agent 的 ReAct 推理出現歷史混淆或提早中斷的問題
    session_id = f"cron-auto-{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8000")
    receiver = os.getenv("NOTIFICATION_RECEIVER", "a5170171@gmail.com")
    prompt = (
        f"今天是 {current_date}。請啟動『自動化漫畫創作鏈』做出一期全新的頂級大作！\n"
        f"1. 首先呼叫 `web_search` 搜尋今日最新、最熱門的科技新聞、AI 趨勢或網路科技迷因作為創作素材。\n"
        f"2. 編寫分鏡劇本。你必須依次呼叫 4 次 `generate_image` 技能來生成四格漫畫的 4 張圖片：第一步生成 `panel_1.png`，第二步生成 `panel_2.png`，第三步生成 `panel_3.png`，第四步生成 `panel_4.png`。請務必確保 4 張圖片都呼叫生成完畢，絕對不能只生成一張就跳到下一步！【重要：呼叫 `generate_image` 時，prompt 內絕對不能要求模型繪製任何文字、字元或對話泡泡，請在 prompt 中加入 'no text', 'text-free' 以確保產出純淨插畫，避免 AI 產生中文錯字與亂碼】。若某張圖片生成失敗，則該格改用經典 SVG 角色繪製模式。\n"
        f"3. 將漫畫實體繪製成一個 HTML 檔案寫入工作區（檔名格式如：comic_semiconductor_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html），並備份腳本為 Markdown 檔案（檔名如：comic_script.md）。所有的漫畫對白與台詞必須完全在 HTML 程式碼中以繁體中文 (zh-TW) 呈現，確保文字 100% 正確無錯字。\n"
        f"4. 確實呼叫 `upload_to_google_drive` 技能，將生成的 4 張漫畫圖片（`panel_1.png`、`panel_2.png`、`panel_3.png`、`panel_4.png`）、產生的 HTML 檔案與 Markdown 腳本檔案一併上傳備份至 Google Drive 的 `pyclaw` 資料夾中。\n"
        f"5. 確實呼叫 `send_email` 技能，為了防範複製貼上大量重複 HTML 觸發 Recitation (重複文字限制) 錯誤，請直接將前述步驟中產生的 HTML 漫畫檔案路徑（例如：'comic_semiconductor_xxxx.html'）作為 `body_content` 參數傳給 `send_email`。收件人為 {receiver}，郵件主旨格式為：【PyClaw 每日漫畫排程 (10點)】今日主題：xxxx。內文末尾請附上預覽網頁連結（`{base_url}/workspace/檔名.html`）。您產生的 HTML 漫畫檔案內容本身必須遵守以下相容性要求：① 禁止使用 CSS Grid/Flexbox/絕對定位，請使用傳統 HTML `<table>` 作為 2x2 格線排版佈局；② 必須使用 inline styles 寫在標籤的 style 屬性中；③ 對話框必須作為獨立的對白 `<div>` 實體元素放在圖片上方或下方，且確實寫出對白文字，不可為空；④ 圖片 `<img>` 的 src 必須為絕對網址 `{base_url}/workspace/panel_x.png`。"
    )
    
    print(f"[{current_date}] 啟動定時自動化漫畫生成流程...")
    try:
        final_answer = await runtime.run(session_id, prompt, callback=None)
        print(f"[{current_date}] 定時自動化任務完成！回答摘要：{final_answer[:100]}...")
    except Exception as e:
        print(f"[{current_date}] 定時自動化任務執行出錯：{str(e)}")

@app.post("/api/cron/generate-comic")
async def run_cron_comic(background_tasks: BackgroundTasks, key: str = None, sync: bool = True):
    """
    排程定時觸發端點。
    可傳入 key 參數進行安全驗證。
    """
    secret_key = os.getenv("CRON_SECRET_KEY")
    if secret_key and key != secret_key:
        raise HTTPException(status_code=403, detail="拒絕存取：安全金鑰無效")
        
    if sync:
        await execute_automated_comic_generation()
        return {
            "status": "success", 
            "message": "已成功完成全自動化漫畫生成任務與郵件寄送流程！"
        }
    else:
        background_tasks.add_task(execute_automated_comic_generation)
        return {
            "status": "success", 
            "message": "已成功於背景啟動全自動化漫畫生成任務與郵件寄送流程！"
        }

# --- 靜態檔案服務 (最後加載，防範路由覆蓋) ---
# 確保目錄存在
os.makedirs("./web", exist_ok=True)
os.makedirs("./agent_workspace", exist_ok=True)

# 掛載安全工作區，讓生成的可視化漫畫 HTML/SVG 可以直接在瀏覽器預覽
app.mount("/workspace", StaticFiles(directory="./agent_workspace", html=True), name="workspace")
app.mount("/", StaticFiles(directory="./web", html=True), name="web")

