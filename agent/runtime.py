import os
import json
import logging
import datetime
from typing import Callable, List, Dict, Any
import google.generativeai as genai
import google.generativeai.protos as protos
from dotenv import load_dotenv

from agent.memory import AgentMemory
from skills.registry import registry

# 載入環境變數
load_dotenv()

class AgentRuntime:
    def __init__(self, db_path: str = "pyclaw.db"):
        self.memory = AgentMemory(db_path=db_path)
        self._configure_gemini()

    def _configure_gemini(self):
        """配置 Gemini API"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your_gemini_api_key_here":
            logging.warning("警告：GEMINI_API_KEY 未設定，請在工作區的 .env 檔案中填入金鑰！")
            self.api_key_set = False
        else:
            genai.configure(api_key=api_key)
            self.api_key_set = True
            
        # 獲取模型名稱，預設為 gemini-1.5-flash
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    async def run(self, session_id: str, user_message: str, callback: Callable[[Dict[str, Any]], Any] = None):
        """
        執行 Agent ReAct 推理循環。
        session_id: 會話 ID
        user_message: 使用者輸入的指令
        callback: 用於即時廣播狀態的非同步回呼函式，接受一個日誌 dict
        """
        # 1. 寫入使用者訊息到資料庫
        self.memory.add_message(session_id, "user", user_message)
        
        # 2. 如果沒有設定 API 金鑰，提示使用者設定
        if not self.api_key_set:
            error_msg = "系統偵測到未設定 GEMINI_API_KEY！請在專案根目錄的 `.env` 檔案中填寫正確的 Google AI Studio API 金鑰，然後重試。"
            self.memory.add_message(session_id, "assistant", error_msg)
            if callback:
                await callback({
                    "session_id": session_id,
                    "type": "error",
                    "title": "API 金鑰未設定",
                    "content": error_msg
                })
            return error_msg

        # 3. 獲取當前啟用的技能工具
        active_skills = registry.get_enabled_skills()
        tools = [s["func"] for s in active_skills] if active_skills else []
        
        # 4. 載入歷史紀錄並建立 Gemini 對話結構
        # 系統提示詞 (System Instruction)，賦予智能體角色與行為準則
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        receiver = os.getenv("NOTIFICATION_RECEIVER", "a5170171@gmail.com")
        base_url = os.getenv("BASE_URL", "http://127.0.0.1:8000")
        system_instruction = (
            f"你是一個名為 PyClaw 的專業日系風格漫畫家（Manga Artist）。\n"
            f"你對動漫創作充滿無限熱忱，說話口吻親切、熱血且帶有日系職人精神，稱呼使用者為「助手」或「編劇/編輯大人」。\n"
            f"你被部署在一個安全的沙盒環境中，擁有一系列實用的技能（Python 函式），能操作檔案和搜尋網路。\n"
            f"今天的日期是：{current_date}。\n"
            f"你的核心任務與行為準則：\n"
            f"1. 每天持續精進自己的畫工與創意，積極主動地調用工具（例如搜尋最新畫技、整理分鏡靈感、管理手稿檔案等）來克服創作難關。\n"
            f"2. 在每次與使用者對話或開啟任務時，若使用者沒有給予具體主題，請積極找使用者討論「今天的製作主題」或「漫畫劇本構想」，共同激盪創作火花。\n"
            f"3. 【自動化出漫畫流程與超高品質要求】：當編劇/編輯大人要求你自動化出漫畫時，你必須確實執行以下「自動化漫畫創作鏈」並達到「日系頂級大作級別」的畫風與版面：\n"
            f"   - 【第一步：搜集靈感】：使用 `web_search` 搜尋與主題相關的最新八卦、迷因或科技趨勢，作為素材。\n"
            f"   - 【第二步：編劇分鏡】：將素材轉化為具備「人設、四格分鏡、趣味對白與日式幽默」的漫畫大綱。\n"
            f"   - 【第三步：實體繪製高品質 HTML/CSS 漫畫（重要：拒絕粗糙廉價的拼湊！）】：你必須為每一格漫畫（四格漫畫共 4 格，從第一格到第四格）都呼叫 `generate_image` 技能生成對應的圖片（檔名分別為 `panel_1.png`、`panel_2.png`、`panel_3.png`、`panel_4.png`）。所有圖片生成完畢後，呼叫 `write_file` 寫入一個極其華麗的可視化漫畫 HTML。你必須嚴格遵守以下美學準則：\n"
            f"     * ①【純正日系黑白網點風格 (Manga Screentone)】：拒絕使用大面積花綠的亮彩色背景！整體採用經典的「日系黑白手繪網點風」，以白色、淡灰色、黑色為主，利用 CSS 漸變 (Linear Gradient) 或 SVG `<pattern>` 做出「波點/網點效果 (Screentone Pattern)」，並加上黑色粗斜線手繪風邊框、效果集中線 (Speed Lines/Action Lines) 來呈現戲劇張力。\n"
            f"     * ②【絕對無遮擋對話泡泡 (No Text Overlap)】：對話框絕對不能擋到人物的臉或圖形！每個漫畫格（Panel）必須有清晰的物理分區。你可以用 Flexbox 橫向排版：人物偏右側/對話框在左側（對話框背景為不透明白色 `rgba(255,255,255,0.95)` 搭配黑邊，且有尖角指向人物嘴巴），或是將對話框固定在格子最上方，人物放在格子底部，雙方保持安全邊距 (Margin/Padding)，文字要適度換行、排版工整！\n"
            f"     * ③【高畫質 Imagen 3 實體圖片與 SVG 雙重繪圖機制 (重要)】：優先嘗試呼叫 `generate_image` 技能來生成精美的 Imagen 3 漫畫分鏡圖片，並在 HTML 中以 `<img src=\"/workspace/檔名.png\">` 引用。若呼叫 `generate_image` 失敗（例如額度不足或 404），你必須靈活無縫地降級改用『經典日系黑白手繪 Q 版 SVG 角色』繪製模式（即利用多個 `<path>`、`<ellipse>`、`<circle>` 疊加繪製出特鮮明的阿宅與機器人小聰），作為高可用的備用方案！\n"
            f"       - 若降級使用 SVG 繪圖，請畫出特徵鮮明的角色：「阿宅 (Otaku)」戴黑色粗圓眼鏡，有著無奈的漫畫眼神與刺蝟頭呆毛；「小聰 (Smarty Robot)」有貓耳科幻耳機與螺旋天線，身上有機械線條結構。禁止使用極簡單線火柴人！\n"
            f"     * ④【動態格線與版面設計】：使用 `transform: rotate(-1deg)` 或不同寬高的網格版面，讓漫畫格有手寫漫畫單行本的躍動感與斜切視覺效果，並確保對話泡泡與人物之間邊距安全無覆蓋。\n"
            f"     * ⑤【重要：圖片中禁止包含任何文字】：由於 AI 繪圖模型（Imagen）極難正確繪製中文字元，在呼叫 `generate_image` 的 prompt 時，**絕對不要**要求模型在圖片內繪製任何文字、英文字母、對白或對話泡泡（請在 prompt 中加入 'no text', 'text-free' 或 'without any text' 等關鍵字，確保生成的圖畫是純淨的插圖）。所有的漫畫對白與角色台詞，必須**完全且確實地使用 HTML/CSS 的對白框元素**來在網頁與郵件中呈現，以保證繁體中文（zh-TW）對白 100% 正確且無錯字。所有網頁與信件中顯示的中文字，都必須是正確無誤的繁體中文。\n"
            f"   - 【第四步：備份腳本】：同時呼叫 `write_file` 將漫畫劇本備份為一個 Markdown 檔案（例如 `comic_script.md`）。\n"
            f"   - 【第五步：備份至雲端硬碟】：呼叫 `upload_to_google_drive` 技能，將生成的 4 張漫畫圖片（`panel_1.png`、`panel_2.png`、`panel_3.png`、`panel_4.png`）、產生的華麗 HTML 漫畫檔案（例如 `comic_semiconductor_xxxx.html`）以及 Markdown 劇本（`comic_script.md`）一併上傳備份至 Google Drive 的 `pyclaw` 資料夾下。\n"
            f"   - 【第六步：呈上大作與郵件通知】：在上述所有步驟確實完成後，最後一步呼叫 `send_email` 技能。為了避免複製貼上大量重複 HTML 觸發 Recitation (重複文字限制) 錯誤，**請直接將您在前述步驟中產生的 HTML 漫畫檔案路徑（例如：'comic_semiconductor_xxxx.html'）作為 `body_content` 參數傳入**，系統會自動在後台讀取檔案內容寄出！收件人為 {receiver}。【重要：您寫入檔案的 HTML 內容本身必須遵守以下郵件客戶端相容性要求】：\n"
            f"     * ①【禁止使用 CSS Grid/Flexbox/絕對定位】：郵件客戶端不支援這些現代佈局，請改用傳統的 HTML `<table>` 進行 2x2 排版（分成兩行 `<tr>`，每行兩個 `<td>` 單元格，每個單元格寬度 50%）。\n"
            f"     * ②【必須使用行內樣式 (Inline Styles)】：請直接將 CSS 寫在每個標籤的 `style` 屬性中，例如 `<table style=\"border: 3px solid black; ...\">`，不要依賴 `<style>` 區塊或 `@import`。\n"
            f"     * ③【對話框實體化】：在每個單元格 `<td>` 內，在圖片的「上方或下方」放置一個獨立的對話框 `<div>`（例如：`<div style=\"border: 2px solid black; border-radius: 10px; padding: 8px; background: #ffffff; font-weight: bold; margin-bottom: 8px;\">對話內容</div>`），絕對不能使用 CSS 絕對定位覆蓋在圖片上，且確實把對白文字寫出來，不能為空！\n"
            f"     * ④【圖片絕對路徑】：圖片的 `<img>` 標籤 src 屬性必須使用絕對 URL：`{base_url}/workspace/圖檔檔名`（例如 `{base_url}/workspace/panel_1.png`），寬度設為 `100%` 或固定寬度以適應單元格。郵件主旨格式為：【PyClaw 每日漫畫排程 (10點)】今日主題：xxxx。內文末尾同時也附上網頁的線上預覽連結。\n"
            f"4. 每當你呼叫工具前，請在心中明確想清楚你的 Thought (思考過程) 以及你預期該工具如何能幫你解決問題。\n"
            f"5. 你的回答必須極具日系動漫風格與創作激情，使用溫慢熱血的繁體中文 (zh-TW) 與使用者交談。"
        )

        # 組合歷史對話做為 Gemini 的 contents
        history_messages = self.memory.get_messages(session_id, limit=20)
        
        # 將歷史轉換成 Gemini API 接受的格式 (統一使用 protos.Content 物件，避免與後續 Tool 呼叫物件混用造成序列化錯誤)
        contents = []
        for msg in history_messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(protos.Content(
                role=role,
                parts=[protos.Part(text=msg["content"])]
            ))
            
        # 5. 啟動 Gemini 模型
        # 我們使用 GenerativeModel，並啟用 manual tools
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction
        )
        
        # 初始化循環變數
        max_turns = 10 # 限制單次任務工具呼叫次數防範無限死循環
        current_turn = 0
        final_answer = ""
        
        # 通知前端：開始思考
        if callback:
            await callback({
                "session_id": session_id,
                "type": "thought",
                "title": "PyClaw 正在啟動...",
                "content": "正在接收指令並分析可用的工具資源..."
            })
            
        while current_turn < max_turns:
            current_turn += 1
            
            try:
                # 呼叫 Gemini 產生內容
                # 如果沒有可用 tools，我們就不傳入 tools 參數以防出錯
                if tools:
                    response = model.generate_content(contents, tools=tools)
                else:
                    response = model.generate_content(contents)
                
                # 安全解析候選內容
                if not response.candidates:
                    raise ValueError("Gemini 回應內容為空：沒有 candidates。")
                    
                candidate = response.candidates[0]
                if not candidate.content or not candidate.content.parts:
                    finish_reason = getattr(candidate, "finish_reason", "unknown")
                    safety_ratings = getattr(candidate, "safety_ratings", [])
                    raise ValueError(
                        f"Gemini 回應內容為空。Finish reason: {finish_reason}. "
                        f"Safety ratings: {safety_ratings}. Prompt feedback: {getattr(response, 'prompt_feedback', 'None')}"
                    )
                    
                model_content = candidate.content
                parts = model_content.parts

                # 檢查是否有 function call (工具調用)
                function_calls = [p.function_call for p in parts if p.function_call]
                
                # 如果有文字內容，視為 AI 的思考過程 (Thought)
                text_parts = [p.text for p in parts if p.text]
                if text_parts:
                    thought_text = "\n".join(text_parts).strip()
                    if thought_text:
                        # 儲存到 SQLite
                        log_data = self.memory.add_execution_log(
                            session_id, "thought", f"思考軌跡 (步驟 {current_turn})", thought_text
                        )
                        # 即時廣播
                        if callback:
                            await callback(log_data)
                            
                # 將 Model 的回應重新包裝為乾淨的 protos.Content 物件，避免與後續的 protos.Content 混用產生序列化錯誤
                clean_parts = []
                for part in model_content.parts:
                    if part.text:
                        clean_parts.append(protos.Part(text=part.text))
                    elif part.function_call:
                        clean_parts.append(protos.Part(
                            function_call=protos.FunctionCall(
                                name=part.function_call.name,
                                args=dict(part.function_call.args)
                            )
                        ))
                contents.append(protos.Content(role=model_content.role, parts=clean_parts))
                
                # 如果沒有 function call，代表推理結束，這就是最終回答
                if not function_calls:
                    final_answer = response.text
                    break
                    
                # 處理第一個 function call (一般來說一次處理一個，Gemini 也支援平行調用，這裡處理主調用)
                fn_call = function_calls[0]
                tool_name = fn_call.name
                
                # 遞迴將 Protobuf 物件轉為原生 Python 型態，避免 json.dumps 序列化失敗 (例如 RepeatedComposite)
                def to_native_type(obj):
                    if hasattr(obj, "items"):
                        return {k: to_native_type(v) for k, v in obj.items()}
                    elif isinstance(obj, (list, tuple)):
                        return [to_native_type(x) for x in obj]
                    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
                        return [to_native_type(x) for x in obj]
                    else:
                        return obj
                
                tool_args = to_native_type(fn_call.args)
                
                # 1. 紀錄工具調用日誌
                tool_call_info = {
                    "tool": tool_name,
                    "arguments": tool_args
                }
                log_data = self.memory.add_execution_log(
                    session_id, 
                    "tool_call", 
                    f"呼叫技能：{tool_name}", 
                    tool_call_info
                )
                if callback:
                    await callback(log_data)
                
                # 2. 執行工具
                observation = registry.execute(tool_name, **tool_args)
                
                # 3. 紀錄執行結果 (Observation)
                log_data = self.memory.add_execution_log(
                    session_id, 
                    "observation", 
                    f"執行結果：{tool_name}", 
                    str(observation)
                )
                if callback:
                    await callback(log_data)
                    
                # 4. 將執行結果以 "function" 角色回傳給 Gemini
                # 我們需要建立一個 protos.Part 包含 function_response 結構
                response_part = protos.Part(
                    function_response=protos.FunctionResponse(
                        name=tool_name,
                        response={"result": str(observation)}
                    )
                )
                
                # 加入到對話 contents 中
                contents.append(protos.Content(
                    role="function",
                    parts=[response_part]
                ))
                
            except Exception as e:
                error_msg = f"ReAct 循環發生錯誤 (步驟 {current_turn}): {str(e)}"
                log_data = self.memory.add_execution_log(session_id, "error", "執行中斷", error_msg)
                if callback:
                    await callback(log_data)
                final_answer = f"抱歉，我在執行過程中遇到了一些技術性問題：{str(e)}"
                break
                
        # 超出最大步驟
        if current_turn >= max_turns and not final_answer:
            final_answer = "抱歉，我的推理步驟已達上限，為防範無限循環，我必須先暫停。請嘗試簡化您的指令。"
            
        # 6. 保存最終回答到 SQLite 聊天歷史
        self.memory.add_message(session_id, "assistant", final_answer)
        
        # 7. 通知前端完成
        if callback:
            await callback({
                "session_id": session_id,
                "type": "final_answer",
                "title": "完成任務",
                "content": final_answer
            })
            
        return final_answer
