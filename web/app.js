/* =================================================================
   PyClaw (OpenClaw-Lite) Frontend Client Logic
   ================================================================= */

document.addEventListener("DOMContentLoaded", () => {
    // --- UI 元素選擇器 ---
    const connectionDot = document.getElementById("connection-dot");
    const connectionText = document.getElementById("connection-text");
    const sessionIdInput = document.getElementById("session-id-input");
    const reconnectBtn = document.getElementById("reconnect-btn");
    const clearBtn = document.getElementById("clear-btn");
    const skillsList = document.getElementById("skills-list");
    const messagesArea = document.getElementById("messages-area");
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const canvasLogs = document.getElementById("canvas-logs");
    const stepCountBadge = document.getElementById("step-count");
    const executionTimer = document.getElementById("execution-timer");
    const exampleBtns = document.querySelectorAll(".example-btn");

    let socket = null;
    let sessionId = sessionIdInput.value.trim() || "default-session";
    let stepCount = 0;
    let timerInterval = null;
    let startTime = null;

    // --- Tabs & Preview UI elements ---
    const tabLogsBtn = document.getElementById("tab-logs-btn");
    const tabPreviewBtn = document.getElementById("tab-preview-btn");
    const canvasPreview = document.getElementById("canvas-preview");
    const previewIframe = document.getElementById("preview-iframe");
    const previewPlaceholder = document.getElementById("preview-placeholder");

    let lastWrittenHtml = null;
    
    // --- Tab Switching Logic ---
    function switchTab(tab) {
        if (tab === "logs") {
            if (tabLogsBtn) tabLogsBtn.classList.add("active");
            if (tabPreviewBtn) tabPreviewBtn.classList.remove("active");
            if (canvasLogs) canvasLogs.style.display = "flex";
            if (canvasPreview) canvasPreview.style.display = "none";
        } else if (tab === "preview") {
            if (tabLogsBtn) tabLogsBtn.classList.remove("active");
            if (tabPreviewBtn) tabPreviewBtn.classList.add("active");
            if (canvasLogs) canvasLogs.style.display = "none";
            if (canvasPreview) canvasPreview.style.display = "flex";
        }
    }

    if (tabLogsBtn && tabPreviewBtn) {
        tabLogsBtn.addEventListener("click", () => switchTab("logs"));
        tabPreviewBtn.addEventListener("click", () => switchTab("preview"));
    }

    function loadIframePreview(path) {
        if (!previewIframe || !previewPlaceholder) return;
        const previewUrl = `${httpProtocol}//${host}/workspace/${path}?t=${Date.now()}`;
        previewIframe.src = previewUrl;
        previewIframe.style.display = "block";
        previewPlaceholder.style.display = "none";
        switchTab("preview");
    }

    // --- 0. 執行計時器功能 ---
    function startExecutionTimer() {
        if (timerInterval) {
            clearInterval(timerInterval);
        }
        startTime = Date.now();
        if (executionTimer) {
            executionTimer.style.display = "inline-block";
            executionTimer.className = "badge badge-timer";
        }
        
        timerInterval = setInterval(() => {
            const elapsed = (Date.now() - startTime) / 1000;
            if (executionTimer) {
                executionTimer.innerHTML = `<i class="fa-solid fa-hourglass-half fa-spin"></i> 執行中 ${elapsed.toFixed(1)}s`;
            }
        }, 100);
    }

    function stopExecutionTimer() {
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
        if (startTime) {
            const elapsed = (Date.now() - startTime) / 1000;
            if (executionTimer) {
                executionTimer.className = "badge badge-timer completed";
                executionTimer.innerHTML = `<i class="fa-solid fa-circle-check"></i> 耗時 ${elapsed.toFixed(1)}s`;
            }
        }
    }



    // 取得當前伺服器主機與通訊協定
    const host = window.location.host;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const httpProtocol = window.location.protocol;

    // --- 1. 初始化與 WebSocket 連線 ---

    function initWebSocket() {
        if (socket) {
            socket.close();
        }

        sessionId = sessionIdInput.value.trim() || "default-session";
        const wsUrl = `${protocol}//${host}/ws/${sessionId}`;

        // 更新連線狀態 UI 為連接中
        connectionDot.className = "status-dot disconnected";
        connectionText.textContent = "連線中...";

        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            connectionDot.className = "status-dot connected";
            connectionText.textContent = "已連線";
            console.log("WebSocket 連線成功");
            
            // 載入資料庫中的歷史數據
            loadSessionData();
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleIncomingEvent(data);
        };

        socket.onclose = () => {
            connectionDot.className = "status-dot disconnected";
            connectionText.textContent = "未連線";
            console.log("WebSocket 連線已中斷，5秒後重試...");
            // 5 秒後自動重試
            setTimeout(initWebSocket, 5000);
        };

        socket.onerror = (error) => {
            console.error("WebSocket 發生錯誤:", error);
            connectionDot.className = "status-dot disconnected";
            connectionText.textContent = "錯誤";
        };
    }

    // --- 2. 接收即時事件處置 ---

    function handleIncomingEvent(payload) {
        const { event, data } = payload;

        if (event === "system") {
            console.log("系統消息:", data.message);
        } else if (event === "log") {
            renderLiveCanvasLog(data);
        }
    }

    // 將日誌渲染至 Live Canvas Panel
    function renderLiveCanvasLog(log) {
        // 如果是第一個執行日誌，先清除 empty 提示
        const emptyPrompt = canvasLogs.querySelector(".canvas-empty");
        if (emptyPrompt) {
            canvasLogs.innerHTML = "";
        }

        const logType = log.type; // 'thought', 'tool_call', 'observation', 'error', 'final_answer'
        const title = log.title || "執行步驟";
        const rawContent = log.content;
        const timestamp = log.timestamp ? formatTime(log.timestamp) : formatTime(new Date());

        // 偵測工具呼叫 write_file 的路徑
        if (logType === "tool_call" && rawContent && rawContent.tool === "write_file") {
            const path = rawContent.arguments.path;
            if (path && path.endsWith(".html")) {
                lastWrittenHtml = path;
                console.log("偵測到寫入 HTML 檔案:", lastWrittenHtml);
            }
        }

        // 偵測工具執行 write_file 成功的結果
        if (logType === "observation" && lastWrittenHtml) {
            if (title.includes("write_file") && typeof rawContent === "string" && !rawContent.includes("失敗") && !rawContent.includes("錯誤")) {
                loadIframePreview(lastWrittenHtml);
            }
        }

        // 增量計步器 (排除最後結果和錯誤)
        if (logType !== "final_answer" && logType !== "error" && logType !== "thought") {
            stepCount++;
            stepCountBadge.textContent = `${stepCount} 步驟`;
        }

        // 建立日誌卡片 DOM
        const logItem = document.createElement("div");
        logItem.className = `canvas-item ${logType}`;

        let iconHtml = "";
        if (logType === "thought") iconHtml = '<i class="fa-solid fa-brain"></i>';
        else if (logType === "tool_call") iconHtml = '<i class="fa-solid fa-gears"></i>';
        else if (logType === "observation") iconHtml = '<i class="fa-solid fa-code-compare"></i>';
        else if (logType === "error") iconHtml = '<i class="fa-solid fa-triangle-exclamation"></i>';
        else if (logType === "final_answer") iconHtml = '<i class="fa-solid fa-check"></i>';

        let contentHtml = "";
        if (typeof rawContent === "object") {
            // 工具調用的 arguments，轉成格式化 JSON 代碼塊
            contentHtml = `<pre class="canvas-item-code"><code>${JSON.stringify(rawContent, null, 2)}</code></pre>`;
        } else {
            // 如果是觀察結果，且內容很長，也使用代碼塊包起來
            if (logType === "observation" || logType === "error") {
                contentHtml = `<pre class="canvas-item-code"><code>${escapeHtml(rawContent)}</code></pre>`;
            } else {
                contentHtml = `<p class="canvas-item-content">${escapeHtml(rawContent)}</p>`;
            }
        }

        logItem.innerHTML = `
            <div class="canvas-item-icon">${iconHtml}</div>
            <div class="canvas-item-card">
                <div class="canvas-item-title">
                    <span>${escapeHtml(title)}</span>
                    <span class="canvas-item-time">${timestamp}</span>
                </div>
                ${contentHtml}
            </div>
        `;

        canvasLogs.appendChild(logItem);
        // 自動滾動到底部
        canvasLogs.scrollTop = canvasLogs.scrollHeight;

        // 如果是最終回答，同時將其渲染到 Chat Area 對話窗中
        if (logType === "final_answer") {
            appendChatMessage("assistant", rawContent);
            if (lastWrittenHtml) {
                loadIframePreview(lastWrittenHtml);
            }
        }

        // 當獲得最終結果或遭遇錯誤時，停止計時器
        if (logType === "final_answer" || logType === "error") {
            stopExecutionTimer();
        }
    }


    // --- 3. 聊天訊息渲染 ---

    function appendChatMessage(role, content) {
        // 清除歡迎頁面
        const welcome = messagesArea.querySelector(".system-welcome");
        if (welcome) {
            messagesArea.innerHTML = "";
        }

        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${role}`;

        const timestamp = formatTime(new Date());

        msgDiv.innerHTML = `
            <div class="message-bubble">
                ${formatMessageText(content)}
            </div>
            <span class="message-meta">${role === "user" ? "您" : "PyClaw"} • ${timestamp}</span>
        `;

        messagesArea.appendChild(msgDiv);
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }

    // 對文字進行格式化 (支持換行與簡單 Markdown 的代碼塊/粗體)
    function formatMessageText(text) {
        if (!text) return "";
        let escaped = escapeHtml(text);
        
        // 替換換行符號
        escaped = escaped.replace(/\n/g, "<br>");
        
        // 簡單替換 markdown 粗體 **text**
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        
        // 簡單替換行內代碼 `code`
        escaped = escaped.replace(/`(.*?)`/g, "<code class='inline-code'>$1</code>");
        
        return escaped;
    }

    // --- 4. REST APIs 介接 ---

    // 載入技能清單
    async function loadSkills() {
        try {
            const res = await fetch(`${httpProtocol}//${host}/api/skills`);
            const data = await res.json();
            
            skillsList.innerHTML = "";
            
            if (data.skills.length === 0) {
                skillsList.innerHTML = "<div class='loading-placeholder'>無已安裝技能。</div>";
                return;
            }
            
            data.skills.forEach(skill => {
                const card = document.createElement("div");
                card.className = "skill-card";
                
                const badgeClass = skill.category || "general";
                
                card.innerHTML = `
                    <div class="skill-info">
                        <div class="skill-name-row">
                            <span class="skill-name">${escapeHtml(skill.name)}</span>
                            <span class="skill-badge ${badgeClass}">${badgeClass}</span>
                        </div>
                        <div class="skill-desc" title="${escapeHtml(skill.doc || '')}">${escapeHtml(skill.description)}</div>
                    </div>
                    <label class="switch">
                        <input type="checkbox" class="skill-toggle-input" data-name="${skill.name}" ${skill.enabled ? 'checked' : ''}>
                        <span class="slider"></span>
                    </label>
                `;
                
                skillsList.appendChild(card);
            });
            
            // 綁定 Switch 切換事件
            document.querySelectorAll(".skill-toggle-input").forEach(checkbox => {
                checkbox.addEventListener("change", async (e) => {
                    const name = e.target.getAttribute("data-name");
                    const enabled = e.target.checked;
                    
                    try {
                        const toggleRes = await fetch(`${httpProtocol}//${host}/api/skills/toggle`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ name, enabled })
                        });
                        const result = await toggleRes.json();
                        console.log(result.message);
                    } catch (error) {
                        console.error("切換技能失敗:", error);
                        // 恢復原狀
                        e.target.checked = !enabled;
                    }
                });
            });
            
        } catch (error) {
            console.error("讀取技能清單錯誤:", error);
            skillsList.innerHTML = "<div class='loading-placeholder text-danger'>載入失敗，請確認伺服器狀態。</div>";
        }
    }

    // 載入當前 Session 的歷史對話與 Live Canvas 畫布日誌
    async function loadSessionData() {
        stepCount = 0;
        stepCountBadge.textContent = "0 步驟";
        if (executionTimer) {
            executionTimer.style.display = "none";
        }
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }

        // 重設預覽狀態
        lastWrittenHtml = null;
        if (previewIframe) previewIframe.src = "";
        if (previewIframe) previewIframe.style.display = "none";
        if (previewPlaceholder) previewPlaceholder.style.display = "block";
        switchTab("logs");


        
        try {
            // 1. 載入對話歷史
            const chatRes = await fetch(`${httpProtocol}//${host}/api/history/${sessionId}`);
            const chatData = await chatRes.json();
            
            messagesArea.innerHTML = "";
            if (chatData.messages && chatData.messages.length > 0) {
                chatData.messages.forEach(msg => {
                    appendChatMessage(msg.role, msg.content);
                });
            } else {
                // 恢復歡迎頁面
                messagesArea.innerHTML = `
                    <div class="system-welcome">
                        <div class="welcome-icon"><i class="fa-solid fa-robot"></i></div>
                        <h2>歡迎使用 PyClaw 自動化系統</h2>
                        <p>這是一個基於 ReAct (Reasoning + Action) 決策循環的 AI 智能體。你可以直接輸入指令要求他幫你處理任務，例如：</p>
                        <div class="example-grid">
                            <button class="example-btn">建立一個 todo.txt 並寫入今日任務</button>
                            <button class="example-btn">搜尋 2026 年最新的 AI 科技新聞並整理</button>
                            <button class="example-btn">列出當前工作區的所有檔案</button>
                        </div>
                    </div>
                `;
                // 重新綁定範例按鈕事件
                bindExampleButtons();
            }

            // 2. 載入執行日誌
            const canvasRes = await fetch(`${httpProtocol}//${host}/api/canvas/${sessionId}`);
            const canvasData = await canvasRes.json();
            
            canvasLogs.innerHTML = "";
            if (canvasData.logs && canvasData.logs.length > 0) {
                canvasData.logs.forEach(log => {
                    renderLiveCanvasLog(log);
                });
            } else {
                canvasLogs.innerHTML = `
                    <div class="canvas-empty">
                        <i class="fa-solid fa-diagram-project"></i>
                        <p>尚無執行日誌</p>
                        <span>當您送出指令時，這裡會以毫秒級的延遲即時呈現 AI 大腦的思考軌跡與工具呼叫過程。</span>
                    </div>
                `;
            }
            
        } catch (error) {
            console.error("載入會話歷史數據發生錯誤:", error);
        }
    }

    // --- 5. 事件監聽器與綁定 ---

    // 送出對話
    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text) return;

        // 1. 如果 WS 沒連線，提示無法傳送
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            alert("目前未連線至伺服器，請重新連線！");
            return;
        }

        // 2. 即時加入 User 訊息到 Chat Area
        appendChatMessage("user", text);
        
        // 3. 重設計步器，並在 Canvas Panel 顯示準備執行
        stepCount = 0;
        stepCountBadge.textContent = "0 步驟";
        
        // 重設預覽狀態為新任務準備
        lastWrittenHtml = null;
        if (previewIframe) previewIframe.src = "";
        if (previewIframe) previewIframe.style.display = "none";
        if (previewPlaceholder) previewPlaceholder.style.display = "block";
        switchTab("logs");

        // 啟動執行計時器
        startExecutionTimer();
        
        canvasLogs.innerHTML = `
            <div class="canvas-item thought">
                <div class="canvas-item-icon"><i class="fa-solid fa-brain"></i></div>
                <div class="canvas-item-card">
                    <div class="canvas-item-title">
                        <span>PyClaw 正在準備中...</span>
                        <span class="canvas-item-time">${formatTime(new Date())}</span>
                    </div>
                    <p class="canvas-item-content">正在解析您發送的指令，調用大腦進行思考...</p>
                </div>
            </div>
        `;

        // 4. 透過 WS 發送給 Gateway Server
        socket.send(JSON.stringify({ message: text }));

        // 5. 清空輸入框
        chatInput.value = "";
    });


    // 重新連線
    reconnectBtn.addEventListener("click", () => {
        initWebSocket();
    });

    // 清除對話與畫布
    clearBtn.addEventListener("click", async () => {
        if (!confirm("確定要完全清空此 Session 的所有對話紀錄與執行畫布嗎？此操作無法還原。")) {
            return;
        }
        
        try {
            const res = await fetch(`${httpProtocol}//${host}/api/clear/${sessionId}`, {
                method: "POST"
            });
            const data = await res.json();
            console.log(data.message);
            
            // 重新載入數據清空 UI
            loadSessionData();
        } catch (error) {
            console.error("清除歷史失敗:", error);
        }
    });

    // 範例按鈕點擊快捷鍵
    function bindExampleButtons() {
        const btns = document.querySelectorAll(".example-btn");
        btns.forEach(btn => {
            btn.addEventListener("click", () => {
                chatInput.value = btn.textContent.trim();
                chatInput.focus();
            });
        });
    }

    // --- 6. 工具函式 ---

    function formatTime(isoStringOrDate) {
        const date = new Date(isoStringOrDate);
        const hrs = String(date.getHours()).padStart(2, '0');
        const mins = String(date.getMinutes()).padStart(2, '0');
        const secs = String(date.getSeconds()).padStart(2, '0');
        return `${hrs}:${mins}:${secs}`;
    }

    function escapeHtml(text) {
        if (!text) return "";
        return text
            .toString()
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // --- 7. 啟動與引導 ---
    initWebSocket();
    loadSkills();
});
