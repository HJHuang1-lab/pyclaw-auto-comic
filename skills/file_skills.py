import os
from pathlib import Path
from skills.registry import skill
from dotenv import load_dotenv

load_dotenv()

# 獲取安全工作區目錄，預設為當前目錄下的 agent_workspace
WORKSPACE_DIR = os.getenv("AGENT_WORKSPACE", "./agent_workspace")
WORKSPACE_PATH = Path(WORKSPACE_DIR).resolve()

# 確保安全工作區目錄存在
WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)

def _safe_path(relative_path: str) -> Path:
    """
    安全路徑檢查：防範目錄穿越攻擊 (Directory Traversal)。
    將相對路徑解析並限制在 WORKSPACE_PATH 之下。
    """
    # 去除首部的斜線，確保是相對於工作區的路徑
    clean_path = relative_path.lstrip("/").lstrip("\\")
    target_path = (WORKSPACE_PATH / clean_path).resolve()
    
    # 檢查目標路徑是否在工作區路徑下
    if not str(target_path).startswith(str(WORKSPACE_PATH)):
        raise PermissionError("拒絕存取：操作路徑超出安全工作區範圍。")
    return target_path

@skill(name="read_file", category="file")
def read_file(path: str) -> str:
    """
    讀取安全工作區內指定檔案的內容。
    path: 檔案的相對路徑 (例如 'notes.txt' 或 'data/config.json')
    """
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"錯誤：找不到檔案 '{path}'"
        if not target.is_file():
            return f"錯誤：'{path}' 不是一個檔案"
            
        with open(target, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"讀取失敗: {str(e)}"

@skill(name="write_file", category="file")
def write_file(path: str, content: str) -> str:
    """
    寫入內容到安全工作區內指定路徑的檔案。如果檔案不存在會自動建立，如果存在則會覆寫。
    path: 檔案的相對路徑
    content: 要寫入的文字內容
    """
    try:
        target = _safe_path(path)
        # 確保父資料夾存在
        target.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"成功：檔案 '{path}' 寫入完成 (共 {len(content)} 個字元)。"
    except Exception as e:
        return f"寫入失敗: {str(e)}"

@skill(name="list_dir", category="file")
def list_dir(path: str = ".") -> str:
    """
    列出安全工作區內指定目錄下的所有檔案與資料夾。
    path: 目錄的相對路徑，預設 '.' 代表工作區根目錄
    """
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"錯誤：找不到目錄 '{path}'"
        if not target.is_dir():
            return f"錯誤：'{path}' 不是一個目錄"
            
        items = os.listdir(target)
        if not items:
            return f"目錄 '{path}' 是空的。"
            
        result = []
        for item in items:
            item_path = target / item
            item_type = "[資料夾]" if item_path.is_dir() else "[檔案]"
            size_str = "" if item_path.is_dir() else f" ({item_path.stat().st_size} bytes)"
            result.append(f"- {item_type} {item}{size_str}")
            
        return f"目錄 '{path}' 內容：\n" + "\n".join(result)
    except Exception as e:
        return f"列出目錄失敗: {str(e)}"
