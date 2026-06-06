# 使用官方 Python 3.10 輕量版
FROM python:3.10-slim

# 設定工作目錄
WORKDIR /app

# 設定環境變數，確保 Python 輸出即時刷新，並設定預設綁定 IP 與連接埠
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    AGENT_WORKSPACE=/app/agent_workspace

# 安裝基本系統依賴
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴清單並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案程式碼
COPY agent ./agent
COPY gateway ./gateway
COPY skills ./skills
COPY web ./web
COPY main.py .

# 建立安全工作區目錄
RUN mkdir -p /app/agent_workspace

# 曝露 FastAPI 連接埠
EXPOSE 8000

# 啟動 Uvicorn 伺服器
CMD ["python", "main.py"]
