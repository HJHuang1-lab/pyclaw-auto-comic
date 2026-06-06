import httpx
from bs4 import BeautifulSoup
from skills.registry import skill
import urllib.parse

@skill(name="search", category="web")
def search(query: str) -> str:
    """
    透過 DuckDuckGo 搜尋引擎，在網路上搜尋關鍵字，並返回前幾個搜尋結果。
    query: 搜尋關鍵字
    """
    return web_search(query)

@skill(name="web_search", category="web")
def web_search(query: str) -> str:
    """
    透過 DuckDuckGo 搜尋引擎，在網路上搜尋關鍵字，並返回前幾個搜尋結果。
    query: 搜尋關鍵字
    """
    try:
        # 使用 DuckDuckGo HTML 版 (免 API 金鑰且易於解析)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        encoded_query = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code != 200:
                return f"網路搜尋失敗：伺服器回應狀態碼 {response.status_code}"
                
            soup = BeautifulSoup(response.text, "html.parser")
            results = soup.find_all("a", class_="result__snippet")
            titles = soup.find_all("a", class_="result__url")
            
            if not results:
                return "搜尋完成，但沒有找到相關的網頁結果。"
                
            output = [f"『{query}』的搜尋結果：\n"]
            count = 0
            for title_tag, snippet_tag in zip(titles, results):
                if count >= 4: # 只回傳前 4 筆結果
                    break
                title = title_tag.get_text().strip()
                link = title_tag.get("href", "").strip()
                # 處理 DDG 內部導向連結
                if link.startswith("//duckduckgo.com/y.js"):
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                    link = parsed.get("uddg", [link])[0]
                    
                snippet = snippet_tag.get_text().strip()
                output.append(f"{count+1}. **{title}**\n   連結: {link}\n   簡介: {snippet}\n")
                count += 1
                
            return "\n".join(output)
    except Exception as e:
        return f"搜尋發生錯誤: {str(e)}。建議您手動檢查您的網際網路連線。"

@skill(name="fetch_webpage", category="web")
def fetch_webpage(url: str) -> str:
    """
    讀取指定網址 (URL) 的網頁內容，並提取網頁中的純文字訊息。
    url: 要抓取的網頁網址，必須以 http:// 或 https:// 開頭
    """
    if not url.startswith(("http://", "https://")):
        return "錯誤：網址必須以 http:// 或 https:// 開頭"
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            if response.status_code != 200:
                return f"讀取網頁失敗：HTTP 狀態碼 {response.status_code}"
                
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 移除 script, style 和 iframe 標籤避免雜訊
            for script in soup(["script", "style", "iframe", "noscript"]):
                script.decompose()
                
            # 提取網頁文字
            text = soup.get_text(separator="\n")
            
            # 清理多餘的空白字元與空行
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = "\n".join(chunk for chunk in chunks if chunk)
            
            # 限制返回長度以防 Token 爆炸
            max_chars = 4000
            if len(clean_text) > max_chars:
                return f"[內容過長，已截斷前 {max_chars} 字元]\n\n" + clean_text[:max_chars]
            return clean_text
    except Exception as e:
        return f"網頁讀取失敗: {str(e)}"
