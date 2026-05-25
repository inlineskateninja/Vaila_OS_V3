/* VAILA OS V3 // FRONTEND CONTROLLER (OFFLINE-FIRST)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // STATE MANAGEMENT
    const state = {
        personas: [],
        activePersona: "proto_jane",
        systemInfo: {},
        activeConsoleTab: "session",
        inspectorOpen: true,
        busy: false
    };

    // Initialize Session ID
    if (!sessionStorage.getItem("vaila_session_id")) {
        sessionStorage.setItem("vaila_session_id", "session_" + Math.random().toString(36).substring(2, 15));
    }
    const sessionId = sessionStorage.getItem("vaila_session_id");

    // DOM ELEMENTS
    const elements = {
        personaList: document.getElementById("persona-list"),
        gatewayStatus: document.getElementById("gateway-status"),
        activeLensIndicator: document.getElementById("active-lens-indicator"),
        activeLensName: document.getElementById("active-lens-name"),
        activeLensTagline: document.getElementById("active-lens-tagline"),
        latencyTag: document.getElementById("latency-tag"),
        chatFeed: document.getElementById("chat-feed"),
        promptInput: document.getElementById("prompt-input"),
        sendBtn: document.getElementById("send-prompt-btn"),
        charCount: document.getElementById("character-count"),
        
        // Operations
        runAssessmentBtn: document.getElementById("run-assessment-btn"),
        runSummarizeBtn: document.getElementById("run-summarize-btn"),
        runDiagnosticsBtn: document.getElementById("run-diagnostics-btn"),
        clearChatBtn: document.getElementById("clear-chat-btn"),
        
        // Inspector
        toggleInspectorBtn: document.getElementById("toggle-inspector-btn"),
        inspectorPanel: document.getElementById("inspector-panel"),
        closeInspectorX: document.getElementById("close-inspector-x"),
        routeConfidence: document.getElementById("route-confidence"),
        confidenceBar: document.getElementById("confidence-bar-inner"),
        routeTaskType: document.getElementById("route-task-type"),
        routePersona: document.getElementById("route-persona"),
        routingReasons: document.getElementById("routing-reasons"),
        consoleTabSession: document.getElementById("console-tab-session"),
        consoleTabErrors: document.getElementById("console-tab-errors"),
        consoleOutput: document.getElementById("console-output"),
        metadataViewer: document.getElementById("metadata-viewer"),
        
        // Modal Overlay
        loadingOverlay: document.getElementById("loading-overlay"),
        loadingMessage: document.getElementById("loading-message")
    };

    // INITIALIZATION
    async function init() {
        setupEventListeners();
        await loadPersonas();
        await loadSystemInfo();
        await checkGateway();
        await startConsolePolling();
    }

    // EVENT LISTENERS SETUP
    function setupEventListeners() {
        // Send prompt click & enter keys
        elements.sendBtn.addEventListener("click", handleSend);
        elements.promptInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && e.ctrlKey) {
                e.preventDefault();
                handleSend();
            }
        });
        
        // Input character count track
        elements.promptInput.addEventListener("input", () => {
            const len = elements.promptInput.value.length;
            elements.charCount.innerText = `${len} chars`;
        });

        // Toggle Inspector Panel
        elements.toggleInspectorBtn.addEventListener("click", toggleInspector);
        elements.closeInspectorX.addEventListener("click", toggleInspector);

        // Operations
        elements.runAssessmentBtn.addEventListener("click", runSelfAssessment);
        elements.runSummarizeBtn.addEventListener("click", runLogSummary);
        elements.runDiagnosticsBtn.addEventListener("click", () => {
            checkGateway(true);
        });
        elements.clearChatBtn.addEventListener("click", clearChat);

        // Console tabs switching
        elements.consoleTabSession.addEventListener("click", () => switchConsoleTab("session"));
        elements.consoleTabErrors.addEventListener("click", () => switchConsoleTab("errors"));
    }

    // CORE TELEMETRY LOADS
    async function loadPersonas() {
        try {
            const res = await fetch("/api/personas");
            if (!res.ok) throw new Error("Failed to load personas");
            state.personas = await res.json();
            renderPersonas();
        } catch (err) {
            logConsole(`[error] error loading intelligence cores: ${err.message}`, "error");
            elements.personaList.innerHTML = `<p class="text-muted">Failed to load personas. Ensure backend local_api is active.</p>`;
        }
    }

    async function loadSystemInfo() {
        try {
            const res = await fetch("/api/system_info");
            if (res.ok) {
                state.systemInfo = await res.json();
                logConsole(`[system] system variables resolved. root: ${state.systemInfo.project_root}`, "success");
            }
        } catch (err) {
            logConsole(`[error] failed to resolve system info: ${err.message}`, "error");
        }
    }

    async function checkGateway(manual = false) {
        if (manual) showLoading("Interrogating model gateway...");
        try {
            const res = await fetch("/api/diagnostics");
            if (!res.ok) throw new Error("Server diagnostics returned non-200");
            const diagnostics = await res.json();
            
            const reachable = diagnostics.server_reachable;
            const model = diagnostics.resolved_model || diagnostics.configured_model || "(auto)";
            
            if (reachable) {
                elements.gatewayStatus.innerText = model;
                elements.gatewayStatus.className = "status-val text-cyan";
                logConsole(`[gateway] LLM model gateway reachable. active model: ${model}`, "success");
            } else {
                elements.gatewayStatus.innerText = "unreachable";
                elements.gatewayStatus.className = "status-val text-red";
                logConsole(`[warn] LLM model gateway unreachable. Check local LM Studio or Ollama server status.`, "warn");
            }
        } catch (err) {
            elements.gatewayStatus.innerText = "check failed";
            elements.gatewayStatus.className = "status-val text-red";
            logConsole(`[error] model gateway check error: ${err.message}`, "error");
        } finally {
            if (manual) hideLoading();
        }
    }

    // RENDERING ELEMENTS
    function renderPersonas() {
        elements.personaList.innerHTML = "";
        state.personas.forEach(p => {
            const card = document.createElement("div");
            card.className = `persona-card ${p.color} ${state.activePersona === p.id ? 'active' : ''}`;
            card.innerHTML = `
                <div class="card-header-meta">
                    <h3>${p.name}</h3>
                    <span class="lens-glow-dot ${p.color}"></span>
                </div>
                <div class="tagline">${p.tagline}</div>
                <div class="desc">${p.description}</div>
            `;
            card.addEventListener("click", () => selectPersona(p.id));
            elements.personaList.appendChild(card);
        });
    }

    function selectPersona(personaId) {
        state.activePersona = personaId;
        
        // Update active class on card elements
        document.querySelectorAll(".persona-card").forEach((card, idx) => {
            const p = state.personas[idx];
            if (p && p.id === personaId) {
                card.classList.add("active");
            } else {
                card.classList.remove("active");
            }
        });

        // Update active details in chat header
        const persona = state.personas.find(p => p.id === personaId);
        if (persona) {
            elements.activeLensName.innerText = persona.name;
            elements.activeLensTagline.innerText = persona.tagline;
            elements.activeLensIndicator.className = `lens-glow-dot ${persona.color}`;
            logConsole(`[lens] aligned cognitive context to: ${persona.name}`, "info");
        }
    }

    // CHAT ENGINE
    async function handleSend() {
        if (state.busy) return;
        const text = elements.promptInput.value.trim();
        if (!text) return;

        state.busy = true;
        elements.promptInput.value = "";
        elements.charCount.innerText = "0 chars";
        
        // Append user message
        appendMessage("user", text);
        
        // Append Vaila placeholder typing message
        const typingEl = appendMessage("vaila", "...", true);
        
        const startTime = performance.now();
        logConsole(`[routing] dispatching prompt to deterministic regex router...`, "info");
        
        try {
            const res = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: text,
                    persona: state.activePersona,
                    source: "web_client",
                    session_id: sessionId
                })
            });

            if (!res.ok) throw new Error(`HTTP status code ${res.status}`);
            const data = await res.json();
            
            const endTime = performance.now();
            const latency = ((endTime - startTime) / 1000).toFixed(1);
            
            // Show latency tag
            elements.latencyTag.innerText = `${latency}s`;
            elements.latencyTag.classList.remove("hidden");
            
            // Remove typing bubble and render text
            typingEl.remove();
            appendMessage("vaila", data.text);
            
            // Populate Inspector metrics
            updateInspector(data.route, data.meta);
            
            logConsole(`[orchestrator] received orchestration response in ${latency}s`, "success");
        } catch (err) {
            typingEl.remove();
            appendMessage("vaila", `**System Error:** Could not contact local Vaila API.\n\nDetails:\n\`\`\`\n${err.message}\n\`\`\``);
            logConsole(`[error] communication breakdown: ${err.message}`, "error");
        } finally {
            state.busy = false;
        }
    }

    function appendMessage(sender, text, isTyping = false) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${sender === "user" ? "user-msg" : "vaila-msg"}`;
        
        const senderName = sender === "user" ? "User" : (state.personas.find(p => p.id === state.activePersona)?.name || "Vaila");
        
        msgDiv.innerHTML = `
            <div class="msg-sender">${senderName}</div>
            <div class="msg-content">
                ${isTyping ? '<div class="typing-placeholder">. . .</div>' : parseMarkdown(text)}
            </div>
        `;
        
        elements.chatFeed.appendChild(msgDiv);
        elements.chatFeed.scrollTop = elements.chatFeed.scrollHeight;
        return msgDiv;
    }

    async function clearChat() {
        try {
            await fetch("/chat/clear", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ session_id: sessionId })
            });
            logConsole("[system] session history cleared on server", "success");
        } catch (err) {
            logConsole(`[error] failed to clear session history on server: ${err.message}`, "error");
        }

        elements.chatFeed.innerHTML = `
            <div class="message system-msg">
                <div class="msg-sender">SYSTEM BOOT</div>
                <div class="msg-content">
                    <p><strong>Vaila OS V3 Session Reset.</strong> View cleared, gateway and routes fully operational.</p>
                </div>
            </div>
        `;
        elements.latencyTag.classList.add("hidden");
        logConsole("[system] session view reset", "info");
    }

    // OPERATIONAL TASKS
    async function runSelfAssessment() {
        showLoading("Running sandboxed self-assessment...");
        logConsole("[task] dispatching SelfAssessmentTool execution...", "info");
        try {
            const res = await fetch("/api/reports/self_assessment", { method: "POST" });
            if (!res.ok) throw new Error("Assessment returned status error");
            const data = await res.json();
            appendMessage("vaila", data.report);
            logConsole("[task] self-assessment complete. proposed patches exported to Sandbox.", "success");
        } catch (err) {
            appendMessage("vaila", `**Self-Assessment Failure:**\n\n\`\`\`\n${err.message}\n\`\`\``);
            logConsole(`[error] self-assessment aborted: ${err.message}`, "error");
        } finally {
            hideLoading();
        }
    }

    async function runLogSummary() {
        showLoading("Compiling daily JSONL logs...");
        logConsole("[task] dispatching LogSummarizer tool...", "info");
        try {
            const res = await fetch("/api/reports/summarize", { method: "POST" });
            if (!res.ok) throw new Error("Summarizer returned status error");
            const data = await res.json();
            appendMessage("vaila", data.summary);
            logConsole("[task] log summarization complete.", "success");
        } catch (err) {
            appendMessage("vaila", `**Log Summarization Failure:**\n\n\`\`\`\n${err.message}\n\`\`\``);
            logConsole(`[error] log summary aborted: ${err.message}`, "error");
        } finally {
            hideLoading();
        }
    }

    // INSPECTOR LAYOUT & OPERATIONS
    function toggleInspector() {
        state.inspectorOpen = !state.inspectorOpen;
        if (state.inspectorOpen) {
            elements.inspectorPanel.classList.remove("collapsed");
            elements.toggleInspectorBtn.innerHTML = '<span class="icon">&#9656;</span> INSPECTOR';
        } else {
            elements.inspectorPanel.classList.add("collapsed");
            elements.toggleInspectorBtn.innerHTML = '<span class="icon">&#9666;</span> INSPECTOR';
        }
    }

    function updateInspector(route, meta) {
        // 1. Confidence Meter
        const conf = route.confidence || 1;
        elements.routeConfidence.innerText = `Level ${conf}`;
        if (conf === 3) {
            elements.routeConfidence.className = "value badge badge-green";
            elements.confidenceBar.style.width = "100%";
            elements.confidenceBar.style.background = "linear-gradient(90deg, #10b981, #059669)";
        } else {
            elements.routeConfidence.className = "value badge badge-yellow";
            elements.confidenceBar.style.width = "33%";
            elements.confidenceBar.style.background = "linear-gradient(90deg, #ffb300, #d97706)";
        }

        // 2. Classification Tags
        elements.routeTaskType.innerText = route.task_type || "general_chat";
        elements.routePersona.innerText = route.persona || "proto_jane";
        
        // Update tag coloring if persona color matches
        const activeColor = state.personas.find(p => p.id === route.persona)?.color || "cyan";
        elements.routePersona.className = `value badge text-${activeColor}`;

        // 3. Routing Reasons
        elements.routingReasons.innerHTML = "";
        const reasons = route.reasons || [];
        if (reasons.length === 0) {
            elements.routingReasons.innerHTML = '<li class="text-muted">No reasons returned.</li>';
        } else {
            reasons.forEach(r => {
                const li = document.createElement("li");
                li.innerText = r;
                elements.routingReasons.appendChild(li);
            });
        }

        // 4. Metadata JSON viewer
        const payload = { route, meta };
        elements.metadataViewer.innerText = JSON.stringify(payload, null, 2);
    }

    // MICRO-TERMINAL LOGS CONSOLE
    async function startConsolePolling() {
        // Poll every 3 seconds for log updates
        pollConsoleLogs();
        setInterval(pollConsoleLogs, 3000);
    }

    async function pollConsoleLogs() {
        try {
            const apiPath = state.activeConsoleTab === "session" ? "/api/logs/session" : "/api/logs/errors";
            const res = await fetch(apiPath + "?limit=40");
            if (!res.ok) return;
            const logs = await res.json();
            renderConsoleLogs(logs);
        } catch (err) {
            // Ignore background polling errors to keep UI quiet
        }
    }

    function renderConsoleLogs(logs) {
        if (!logs || logs.length === 0) {
            elements.consoleOutput.innerHTML = `<div class="terminal-line text-muted">[system] console waiting for entries...</div>`;
            return;
        }

        elements.consoleOutput.innerHTML = "";
        // Render in chronological order (logs are returned in reverse from API, let's reverse them again to scroll down)
        const ordered = [...logs].reverse();
        
        ordered.forEach(item => {
            const line = document.createElement("div");
            
            const timestamp = item.logged_utc 
                ? `<span class="timestamp">[${new Date(item.logged_utc).toLocaleTimeString()}]</span>` 
                : '<span class="timestamp">[utc]</span>';
            
            let content = "";
            let typeClass = "";
            
            if (item.event_type) {
                content = `${item.event_type.toUpperCase()}`;
                if (item.route) {
                    content += ` | route: ${item.route.task_type || 'chat'} | model: ${item.response_meta?.llm?.model || 'auto'}`;
                } else if (item.error) {
                    content += ` | error: ${item.error}`;
                    typeClass = "error";
                }
                typeClass = typeClass || "info";
            } else if (item.raw) {
                content = item.raw;
                typeClass = "warn";
            } else {
                content = JSON.stringify(item);
                typeClass = "success";
            }
            
            line.className = `terminal-line ${typeClass}`;
            line.innerHTML = `${timestamp} ${content}`;
            elements.consoleOutput.appendChild(line);
        });
        
        // Scroll terminal to bottom
        elements.consoleOutput.scrollTop = elements.consoleOutput.scrollHeight;
    }

    function switchConsoleTab(tab) {
        state.activeConsoleTab = tab;
        if (tab === "session") {
            elements.consoleTabSession.classList.add("active");
            elements.consoleTabErrors.classList.remove("active");
        } else {
            elements.consoleTabSession.classList.remove("active");
            elements.consoleTabErrors.classList.add("active");
        }
        pollConsoleLogs();
    }

    function logConsole(msg, type = "info") {
        const line = document.createElement("div");
        line.className = `terminal-line ${type}`;
        
        const timestamp = `<span class="timestamp">[${new Date().toLocaleTimeString()}]</span>`;
        line.innerHTML = `${timestamp} ${msg}`;
        elements.consoleOutput.appendChild(line);
        elements.consoleOutput.scrollTop = elements.consoleOutput.scrollHeight;
    }

    // MODAL UTILITIES
    function showLoading(msg) {
        elements.loadingMessage.innerText = msg;
        elements.loadingOverlay.classList.remove("hidden");
    }

    function hideLoading() {
        elements.loadingOverlay.classList.add("hidden");
    }

    // CUSTOM OFFLINE MARKDOWN PARSER (LINE-BY-LINE AND INLINE REGEXES)
    function parseMarkdown(text) {
        if (!text) return "";
        
        // HTML Escape to prevent XSS
        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
            
        // Process code blocks first
        const codeBlockRegex = /```([\s\S]*?)```/gm;
        let codeBlocks = [];
        html = html.replace(codeBlockRegex, (match, codeContent) => {
            const lines = codeContent.split('\n');
            let lang = "";
            let code = codeContent;
            if (lines[0] && lines[0].trim().length < 15 && !lines[0].includes(' ') && !lines[0].includes('\n')) {
                lang = lines[0].trim();
                code = lines.slice(1).join('\n');
            }
            
            code = code.trim();
            const idx = codeBlocks.length;
            codeBlocks.push({ lang, code });
            return `__CODE_BLOCK_PLACEHOLDER_${idx}__`;
        });
        
        const lines = html.split('\n');
        let inList = false;
        let listType = ""; // "ul" or "ol"
        let parsedLines = [];
        
        for (let i = 0; i < lines.length; i++) {
            let line = lines[i];
            const trimmed = line.trim();
            
            const isBullet = trimmed.startsWith("- ") || trimmed.startsWith("* ");
            const isNum = /^\d+\.\s+/.test(trimmed);
            
            if (inList && !isBullet && !isNum && trimmed !== "") {
                parsedLines.push(`</${listType}>`);
                inList = false;
            }
            
            if (isBullet) {
                if (!inList) {
                    inList = true;
                    listType = "ul";
                    parsedLines.push(`<ul>`);
                } else if (listType !== "ul") {
                    parsedLines.push(`</ol><ul>`);
                    listType = "ul";
                }
                const content = trimmed.replace(/^[\-\*]\s+/, "");
                parsedLines.push(`<li>${parseInlineMarkdown(content)}</li>`);
            } else if (isNum) {
                if (!inList) {
                    inList = true;
                    listType = "ol";
                    parsedLines.push(`<ol>`);
                } else if (listType !== "ol") {
                    parsedLines.push(`</ul><ol>`);
                    listType = "ol";
                }
                const content = trimmed.replace(/^\d+\.\s+/, "");
                parsedLines.push(`<li>${parseInlineMarkdown(content)}</li>`);
            } else if (trimmed.startsWith("&gt; ")) {
                const content = trimmed.replace(/^&gt;\s+/, "");
                parsedLines.push(`<blockquote>${parseInlineMarkdown(content)}</blockquote>`);
            } else if (trimmed === "") {
                if (inList) {
                    parsedLines.push(`</${listType}>`);
                    inList = false;
                }
                parsedLines.push("<br>");
            } else {
                parsedLines.push(`<p>${parseInlineMarkdown(line)}</p>`);
            }
        }
        
        if (inList) {
            parsedLines.push(`</${listType}>`);
        }
        
        let result = parsedLines.join('\n');
        
        // Restore code blocks with premium layout and Copy utilities
        codeBlocks.forEach((block, idx) => {
            const langLabel = block.lang ? `<span class="code-lang-label">${block.lang.toUpperCase()}</span>` : "";
            const replacement = `
                <pre>${langLabel}<code>${block.code}</code><button class="code-copy-btn" onclick="navigator.clipboard.writeText(this.previousSibling.innerText); this.innerText='Copied!'; setTimeout(()=>this.innerText='Copy', 2000)">Copy</button></pre>
            `;
            result = result.replace(`__CODE_BLOCK_PLACEHOLDER_${idx}__`, replacement);
        });
        
        // Clean redundant paragraphs and empty wraps
        result = result.replace(/<p><br><\/p>/g, "<br>");
        result = result.replace(/<p>__CODE_BLOCK_PLACEHOLDER_\d+__<\/p>/g, (m) => m.replace(/<\/?p>/g, ""));
        
        return result;
    }

    function parseInlineMarkdown(text) {
        let res = text;
        // Inline raw Code elements
        res = res.replace(/`([^`]+)`/g, "<code>$1</code>");
        // Strong Emphasis
        res = res.replace(/\*\*([^*]+)\*\?/g, "<strong>$1</strong>");
        res = res.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        // Emphasis
        res = res.replace(/\*([^*]+)\*/g, "<em>$1</em>");
        res = res.replace(/_([^_]+)_/g, "<em>$1</em>");
        // Clickable file or hyperlink URLs
        res = res.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
        return res;
    }

    // RUN THE COGNITIVE MACHINE
    init();
});
