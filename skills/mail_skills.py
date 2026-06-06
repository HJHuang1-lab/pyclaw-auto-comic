import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from skills.registry import skill
from dotenv import load_dotenv

load_dotenv()

@skill(name="send_email", category="general")
def send_email(subject: str, body_content: str, is_html: bool = True) -> str:
    """
    發送電子郵件通知給總編輯/編劇大人（預設寄送至 a5170171@gmail.com）。
    subject: 郵件主旨
    body_content: 郵件內容（可為 HTML 或是純文字，亦可為安全工作區內的可讀檔案路徑如 'comic.html' 以防範內容過長限制）
    is_html: 是否以 HTML 格式寄出，預設為 True
    """
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER", "a5170171@gmail.com")
    smtp_password = os.getenv("SMTP_PASSWORD")
    receiver = os.getenv("NOTIFICATION_RECEIVER", "a5170171@gmail.com")
    
    # 支援傳入安全工作區內的檔案路徑來讀取內文，防範 LLM 複製貼上大量 HTML 導致 Recitation 限制
    workspace_dir = os.getenv("AGENT_WORKSPACE", "./agent_workspace")
    from pathlib import Path
    is_file_body = False
    clean_filename = ""
    try:
        trimmed_content = body_content.strip()
        if "\n" not in trimmed_content and len(trimmed_content) < 260 and trimmed_content.lower().endswith(('.html', '.htm', '.md', '.txt')):
            clean_path = trimmed_content.lstrip("/").lstrip("\\")
            target_path = (Path(workspace_dir) / clean_path).resolve()
            if str(target_path).startswith(str(Path(workspace_dir).resolve())) and target_path.exists() and target_path.is_file():
                with open(target_path, 'r', encoding='utf-8') as f:
                    body_content = f.read()
                is_file_body = True
                clean_filename = target_path.name
    except Exception:
        pass
    
    if not smtp_password:
        return "發送失敗：未在環境變數或 .env 中設定 SMTP_PASSWORD（如 Gmail 應用程式密碼）。"
        
    try:
        # 建立多用途郵件結構
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = receiver
        msg["Subject"] = subject
        
        # 如果是從 HTML 檔案載入的，自動附上線上預覽連結
        if is_file_body and is_html:
            host = os.getenv("HOST", "127.0.0.1")
            port = os.getenv("PORT", "8000")
            base_url = os.getenv("BASE_URL", f"http://{host}:{port}")
            # 如果是 GitHub Pages URL，路徑為 /agent_workspace/，否則為本地 /workspace/
            if "github.io" in base_url.lower():
                preview_url = f"{base_url.rstrip('/')}/agent_workspace/{clean_filename}"
            else:
                preview_url = f"{base_url.rstrip('/')}/workspace/{clean_filename}"
            preview_link_html = f"""
            <hr style="border: 1px dashed #ccc; margin-top: 30px; margin-bottom: 20px;">
            <p style="text-align: center; font-size: 0.95em; color: #555; font-family: '微軟正黑體', sans-serif; margin-bottom: 10px;">
                🌐 <b>線上觀看：</b> <a href="{preview_url}" target="_blank" style="color: #007bff; text-decoration: none; font-weight: bold; border-bottom: 1px solid #007bff;">在瀏覽器中開啟線上預覽連結</a>
            </p>
            """
            if "</body>" in body_content:
                body_content = body_content.replace("</body>", f"{preview_link_html}</body>")
            else:
                body_content += preview_link_html
                
        # 解析 HTML 尋找 <img> 標籤並嵌入圖片為 inline cid
        if is_html:
            try:
                from bs4 import BeautifulSoup
                from email.mime.image import MIMEImage
                soup = BeautifulSoup(body_content, "html.parser")
                img_tags = soup.find_all("img")
                attached_cids = {}
                
                for idx, img in enumerate(img_tags):
                    src = img.get("src", "")
                    if not src:
                        continue
                        
                    # 獲取檔名 (例如 panel_1.png)
                    filename = src.split("/")[-1]
                    if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        continue
                        
                    # 尋找本機實體檔案路徑
                    local_img_path = Path(workspace_dir) / filename
                    if not local_img_path.exists():
                        # 去除開頭斜線
                        clean_src = src.lstrip("/").lstrip("\\")
                        if clean_src.startswith("workspace"):
                            clean_src = clean_src.replace("workspace", "", 1).lstrip("/").lstrip("\\")
                        local_img_path = Path(workspace_dir) / clean_src
                        
                    if local_img_path.exists() and local_img_path.is_file():
                        cid = f"img_{idx}_{filename}"
                        img["src"] = f"cid:{cid}"
                        
                        # 附加圖片至郵件
                        if cid not in attached_cids:
                            with open(local_img_path, 'rb') as f_img:
                                mime_img = MIMEImage(f_img.read())
                                mime_img.add_header('Content-ID', f'<{cid}>')
                                mime_img.add_header('Content-Disposition', 'inline', filename=filename)
                                msg.attach(mime_img)
                                attached_cids[cid] = True
                                
                body_content = str(soup)
            except Exception:
                pass
        
        # 附加內文（支援 HTML 或純文字）
        mime_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body_content, mime_type, "utf-8"))
        
        # 根據連接埠選用連線協議
        if smtp_port == 465:
            # SSL 連線 (常用於 465 端口)
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            # STARTTLS 連線 (常用於 587 端口)
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            
        # 登入並發送
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, receiver, msg.as_string())
        server.quit()
        
        return f"成功：郵件已成功寄送至 {receiver}，主旨為 '{subject}'。"
    except Exception as e:
        return f"發送失敗：{str(e)}"
