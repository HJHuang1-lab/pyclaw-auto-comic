import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime

class AgentMemory:
    def __init__(self, db_path: str = "pyclaw.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        # 確保資料夾存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 建立會話表 (Sessions)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 2. 建立對話紀錄表 (Conversations)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
            )
            """)
            
            # 3. 建立 AI 思考與工具執行日誌表 (Execution Logs) - 用於即時畫布 (Live Canvas)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                type TEXT, -- 'thought', 'tool_call', 'observation', 'system', 'error'
                title TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
            )
            """)
            conn.commit()

    # --- Session 管理 ---
    def create_session(self, session_id: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)",
                (session_id,)
            )
            conn.commit()
            
    def list_sessions(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, created_at FROM sessions ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    # --- 對話歷史管理 (User 與 AI 的互動) ---
    def add_message(self, session_id: str, role: str, content: str):
        self.create_session(session_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content)
            )
            conn.commit()
            
    def get_messages(self, session_id: str, limit: int = 50):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
                (session_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    # --- 內部執行日誌管理 (AI 的 Thought, Tool Call, Observation) ---
    def add_execution_log(self, session_id: str, log_type: str, title: str, content: str or dict):
        self.create_session(session_id)
        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, ensure_ascii=False)
        else:
            content_str = str(content)
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO execution_logs (session_id, type, title, content) VALUES (?, ?, ?, ?)",
                (session_id, log_type, title, content_str)
            )
            conn.commit()
            
            # 獲取剛插入的日誌 ID 並返回完整日誌字典
            log_id = cursor.lastrowid
            return {
                "id": log_id,
                "session_id": session_id,
                "type": log_type,
                "title": title,
                "content": content_str,
                "timestamp": datetime.now().isoformat()
            }

    def get_execution_logs(self, session_id: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, type, title, content, timestamp FROM execution_logs WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            logs = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                # 嘗試將 JSON 字串解析回 dict/list
                try:
                    row_dict["content"] = json.loads(row_dict["content"])
                except Exception:
                    pass
                logs.append(row_dict)
            return logs

    def clear_session_data(self, session_id: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM execution_logs WHERE session_id = ?", (session_id,))
            conn.commit()
