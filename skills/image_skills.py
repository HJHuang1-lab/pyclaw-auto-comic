import os
import httpx
import base64
from pathlib import Path
from skills.registry import skill
from dotenv import load_dotenv

load_dotenv()

# 獲取安全工作區目錄，預設為當前目錄下的 agent_workspace
WORKSPACE_DIR = os.getenv("AGENT_WORKSPACE", "./agent_workspace")

@skill(name="generate_image", category="general")
def generate_image(prompt: str, filename: str) -> str:
    """
    使用 Google Imagen 圖像生成模型，根據 prompt 描述生成一張圖片並存檔。
    本技能支援級聯降級：優先使用 env 設定的模型 (預設為 Imagen 3)，若失敗則自動嘗試 Imagen 4.0，若仍失敗則回報錯誤以觸發系統的 SVG 繪製機制。
    prompt: 圖片的詳細視覺描述（如 'A cartoon robot waving hello'）
    filename: 存檔檔名（例如 'panel_1.png'），會自動儲存在安全工作區
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "生成失敗：未設定 GEMINI_API_KEY 環境變數。"

    # 決定嘗試的模型列表
    config_model = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
    models_to_try = [config_model]
    
    # 如果設定的模型不是 4.0，將 4.0 作為備用模型
    if config_model != "imagen-4.0-generate-001":
        models_to_try.append("imagen-4.0-generate-001")
        
    last_error = ""
    
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={api_key}"
        payload = {
            "instances": [
                {"prompt": prompt}
            ],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": "1:1",
                "outputMimeType": "image/png"
            }
        }
        
        try:
            # 圖像生成可能耗時較長，設定 60 秒 Timeout
            r = httpx.post(url, json=payload, timeout=60.0)
            
            if r.status_code == 200:
                response_json = r.json()
                # 解析返回的 base64 影像資料
                if "predictions" in response_json:
                    img_b64 = response_json["predictions"][0]["bytesBase64Encoded"]
                elif "generatedImages" in response_json:
                    img_b64 = response_json["generatedImages"][0]["image"]["imageBytes"]
                else:
                    last_error = f"模型 {model} 回應格式異常，未找到影像欄位。"
                    continue
                    
                # 解碼並寫入檔案
                img_bytes = base64.b64decode(img_b64)
                
                # 安全路徑處理，確保在工作區內
                clean_filename = filename.lstrip("/").lstrip("\\")
                target_path = (Path(WORKSPACE_DIR) / clean_filename).resolve()
                
                # 檢查是否目錄穿越
                workspace_path = Path(WORKSPACE_DIR).resolve()
                if not str(target_path).startswith(str(workspace_path)):
                    return "生成失敗：操作路徑超出安全工作區範圍。"
                    
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(target_path, "wb") as f:
                    f.write(img_bytes)
                    
                return f"成功：使用 {model} 圖片已成功生成並儲存至工作區，路徑為 '{clean_filename}'。"
                
            elif r.status_code == 429:
                last_error = (
                    f"模型 {model} 生成失敗：API 傳回 429 額度限制。這是因為您的 Google AI Studio 帳戶"
                    "尚未啟用付費 (Billing) 功能，或者當前的圖像生成額度已耗盡。請確認帳戶狀態。"
                )
            else:
                last_error = f"模型 {model} 生成失敗：伺服器傳回錯誤代碼 {r.status_code} - {r.text}"
                
        except Exception as e:
            last_error = f"模型 {model} 呼叫異常：{str(e)}"
            
    # 如果所有模型都嘗試失敗
    return f"生成失敗：所有嘗試的模型都無法生成圖像。最後錯誤訊息為：{last_error}"

