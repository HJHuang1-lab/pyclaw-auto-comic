import os
import json
import asyncio
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

def setup_gdrive_secrets():
    """從環境變數中讀取 Google Drive 憑證 JSON 並寫入為實體檔案"""
    creds_json = os.getenv("GOOGLE_DRIVE_CREDENTIALS_JSON")
    token_json = os.getenv("GOOGLE_DRIVE_TOKEN_JSON")
    
    # 寫入 Credentials
    if creds_json:
        try:
            # 驗證是否為合法 JSON
            json_data = json.loads(creds_json)
            with open("google_drive_credentials.json", "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            print("Successfully restored google_drive_credentials.json from env var.")
        except Exception as e:
            print(f"Error parsing GOOGLE_DRIVE_CREDENTIALS_JSON: {e}")
            # 退而求其次直接寫入字串
            with open("google_drive_credentials.json", "w", encoding="utf-8") as f:
                f.write(creds_json)
    else:
        print("Warning: GOOGLE_DRIVE_CREDENTIALS_JSON env var is not set.")

    # 寫入 Token
    if token_json:
        try:
            # 驗證是否為合法 JSON
            json_data = json.loads(token_json)
            with open("google_drive_token.json", "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            print("Successfully restored google_drive_token.json from env var.")
        except Exception as e:
            print(f"Error parsing GOOGLE_DRIVE_TOKEN_JSON: {e}")
            # 退而求其次直接寫入字串
            with open("google_drive_token.json", "w", encoding="utf-8") as f:
                f.write(token_json)
    else:
        print("Warning: GOOGLE_DRIVE_TOKEN_JSON env var is not set.")

async def main():
    setup_gdrive_secrets()
    
    # 動態匯入 gateway.server 中的執行邏輯，確保在此之前 credentials 檔案已就緒
    from gateway.server import execute_automated_comic_generation
    
    print("Starting automated comic generation task...")
    await execute_automated_comic_generation()
    print("Automated comic generation task finished.")

if __name__ == "__main__":
    asyncio.run(main())
