import os
import datetime
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv
from skills.registry import skill

load_dotenv()

# 獲取安全工作區目錄，預設為當前目錄下的 agent_workspace
WORKSPACE_DIR = os.getenv("AGENT_WORKSPACE", "./agent_workspace")
WORKSPACE_PATH = Path(WORKSPACE_DIR).resolve()

def get_drive_service():
    """
    載入金鑰並初始化 Google Drive 服務（使用 OAuth 2.0 桌面端授權流程與 Token 快取）。
    """
    creds_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH", "google_drive_credentials.json")
    token_path = os.getenv("GOOGLE_DRIVE_TOKEN_PATH", "google_drive_token.json")
    scopes = ['https://www.googleapis.com/auth/drive']
    creds = None

    # 如果 token.json 存在，則嘗試讀取它
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, scopes)
        except Exception:
            creds = None

    # 如果沒有憑證或憑證已失效，則進行登入/重新整理
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        # 如果重新整理失敗，或是沒有 refresh token，則執行新的登入流程
        if not creds or not creds.valid:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    f"找不到 Google Drive OAuth 用戶端金鑰檔案：'{creds_path}'。請確認您已下載並放置該 JSON 檔案，"
                    f"且已在 .env 中正確設定 GOOGLE_DRIVE_CREDENTIALS_PATH。"
                )
            
            # 使用本地伺服器進行 OAuth 瀏覽器登入授權
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, scopes)
            creds = flow.run_local_server(port=0)
            
            # 儲存憑證供下次使用
            with open(token_path, 'w', encoding='utf-8') as token_file:
                token_file.write(creds.to_json())
                
    service = build('drive', 'v3', credentials=creds)
    return service

def find_or_create_folder(service, folder_name: str, parent_id: str = None) -> str:
    """
    在雲端硬碟中尋找特定資料夾。如果找不到，則會自動建立它。
    """
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
        
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    
    if items:
        # 找到已存在的資料夾，回傳 ID
        return items[0]['id']
        
    # 未找到，建立資料夾
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_id:
        file_metadata['parents'] = [parent_id]
        
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')

@skill(name="upload_to_google_drive", category="google_drive")
def upload_to_google_drive(file_paths: list, folder_name: str = "pyclaw") -> str:
    """
    將安全工作區內的指定檔案（例如生成漫畫的圖片或 HTML 檔案）上傳至 Google 雲端硬碟的特定資料夾。
    本技能會自動在雲端硬碟主資料夾下，依照當天日期建立子資料夾（如 'YYYY-MM-DD'）來分類儲存每日漫畫。
    file_paths: 要上傳的本機檔案路徑列表（例如 ['panel_1.png', 'panel_2.png', 'comic.html']，必須在安全工作區內）
    folder_name: 雲端硬碟中的主資料夾名稱，預設為 'pyclaw'
    """
    # 規格化傳入的 file_paths，容錯處理字串格式
    if isinstance(file_paths, str):
        if file_paths.startswith("[") and file_paths.endswith("]"):
            try:
                import json
                file_paths = json.loads(file_paths)
            except Exception:
                file_paths = [file_paths]
        elif "," in file_paths:
            file_paths = [p.strip() for p in file_paths.split(",")]
        else:
            file_paths = [file_paths]

    if not file_paths:
        return "上傳失敗：上傳的檔案路徑列表為空。"

    try:
        service = get_drive_service()
    except Exception as e:
        return f"初始化 Google Drive 服務失敗: {str(e)}"

    # 1. 確保雲端主資料夾存在
    try:
        root_folder_id = find_or_create_folder(service, folder_name)
    except Exception as e:
        return f"在 Google Drive 中建立或尋找主資料夾 '{folder_name}' 失敗: {str(e)}"

    # 2. 確保當天日期的子資料夾存在 (例如 2026-06-06)
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    try:
        day_folder_id = find_or_create_folder(service, today_str, parent_id=root_folder_id)
    except Exception as e:
        return f"在 Google Drive 中建立或尋找今日日期子資料夾 '{today_str}' 失敗: {str(e)}"

    uploaded_files = []
    failed_files = []

    for path_str in file_paths:
        try:
            # 安全路徑處理，確保在安全工作區之內
            clean_path = path_str.lstrip("/").lstrip("\\")
            target_path = (WORKSPACE_PATH / clean_path).resolve()
            
            # 檢查是否超出工作區範圍
            if not str(target_path).startswith(str(WORKSPACE_PATH)):
                failed_files.append((path_str, "拒絕存取：操作路徑超出安全工作區範圍。"))
                continue
                
            if not target_path.exists():
                failed_files.append((path_str, "檔案不存在。"))
                continue
                
            if not target_path.is_file():
                failed_files.append((path_str, "此路徑不是一個檔案。"))
                continue

            file_name = target_path.name
            
            # 依附檔名判斷 mime_type
            mime_type = None
            if file_name.endswith('.png'):
                mime_type = 'image/png'
            elif file_name.endswith('.jpg') or file_name.endswith('.jpeg'):
                mime_type = 'image/jpeg'
            elif file_name.endswith('.html') or file_name.endswith('.htm'):
                mime_type = 'text/html'
            elif file_name.endswith('.md'):
                mime_type = 'text/markdown'
                
            file_metadata = {
                'name': file_name,
                'parents': [day_folder_id]
            }
            media = MediaFileUpload(str(target_path), mimetype=mime_type, resumable=True)
            
            # 檢查檔案是否已存在於該日期資料夾中，若存在則更新內容，若不存在則建立新檔案
            query = f"name = '{file_name}' and '{day_folder_id}' in parents and trashed = false"
            existing_results = service.files().list(q=query, spaces='drive', fields='files(id)').execute()
            existing_items = existing_results.get('files', [])
            
            if existing_items:
                # 更新現有檔案
                file_id = existing_items[0]['id']
                updated_file = service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
                uploaded_files.append(f"{file_name} (更新成功, ID: {file_id})")
            else:
                # 建立並上傳新檔案
                new_file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                uploaded_files.append(f"{file_name} (新增成功, ID: {new_file.get('id')})")
                
        except Exception as e:
            failed_files.append((path_str, str(e)))

    # 彙整結果回報
    result_lines = []
    if uploaded_files:
        result_lines.append(f"成功儲存至 Google 雲端硬碟 '{folder_name}/{today_str}/' 資料夾的檔案：")
        for f in uploaded_files:
            result_lines.append(f"  - {f}")
    if failed_files:
        if result_lines:
            result_lines.append("")
        result_lines.append("以下檔案上傳失敗：")
        for f, err in failed_files:
            result_lines.append(f"  - {f}: {err}")
            
    return "\n".join(result_lines)
