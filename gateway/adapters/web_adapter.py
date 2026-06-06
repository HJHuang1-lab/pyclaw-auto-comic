import json
from typing import Dict, List, Any
from fastapi import WebSocket

class WebConnectionManager:
    def __init__(self):
        # 儲存 session_id -> List[WebSocket] 的映射，支援同一 Session 多開分頁
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_to_session(self, session_id: str, message: Dict[str, Any]):
        """
        傳送 JSON 訊息給指定 Session 的所有 WebSocket 連線。
        """
        if session_id in self.active_connections:
            # 拷貝一份連線列表，防範非同步廣播時列表發生變化
            connections = self.active_connections[session_id][:]
            for connection in connections:
                try:
                    await connection.send_text(json.dumps(message, ensure_ascii=False))
                except Exception:
                    # 如果連線斷開，安全移除
                    self.disconnect(session_id, connection)

# 全域 Web 連線管理器
web_manager = WebConnectionManager()
