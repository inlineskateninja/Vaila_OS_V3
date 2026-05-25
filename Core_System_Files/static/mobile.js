document.addEventListener("DOMContentLoaded", () => {
    const authStorageKey = "vaila_web_auth_token";
    const state = {
        activeView: "chat",
        personas: [],
        activePersona: "proto_jane",
        busy: false,
        toastTimer: null
    };

    const viewTitles = {
        chat: "Chat",
        memory: "Memory",
        files: "Files",
        system: "System"
    };

    const elements = {
        viewTitle: document.getElementById("mobile-view-title"),
        refreshBtn: document.getElementById("refresh-btn"),
        tokenBtn: document.getElementById("token-btn"),
        connectionDot: document.getElementById("connection-dot"),
        navButtons: Array.from(document.querySelectorAll(".nav-button")),
        quickActions: Array.from(document.querySelectorAll(".quick-actions button")),
        views: Array.from(document.querySelectorAll(".mobile-view")),
        gatewayStatus: document.getElementById("gateway-status"),
        activePersonaLabel: document.getElementById("active-persona-label"),
        personaChips: document.getElementById("persona-chips"),
        chatFeed: document.getElementById("chat-feed"),
        chatForm: document.getElementById("chat-form"),
        promptInput: document.getElementById("prompt-input"),
        sendBtn: document.getElementById("send-btn"),
        memoryList: document.getElementById("memory-list"),
        memoryCount: document.getElementById("memory-count"),
        fileInput: document.getElementById("file-input"),
        filesList: document.getElementById("files-list"),
        filesCount: document.getElementById("files-count"),
        systemList: document.getElementById("system-list"),
        healthCount: document.getElementById("health-count"),
        toast: document.getElementById("toast"),
        dialog: document.getElementById("detail-dialog"),
        dialogTitle: document.getElementById("dialog-title"),
        dialogContent: document.getElementById("dialog-content"),
        dialogClose: document.getElementById("dialog-close")
    };

    function getStoredAuthToken() {
        return localStorage.getItem(authStorageKey) || "";
    }

    function setStoredAuthToken(token) {
        if (token) {
            localStorage.setItem(authStorageKey, token);
        } else {
            localStorage.removeItem(authStorageKey);
        }
    }

    function requestAuthToken() {
        const token = window.prompt("Enter your Vaila remote access token:");
        if (!token || !token.trim()) return "";
        setStoredAuthToken(token.trim());
        toast("Token saved on this device.");
        return token.trim();
    }

    async function apiFetch(resource, options = {}, allowRetry = true) {
        const mergedOptions = { ...options };
        const headers = new Headers(mergedOptions.headers || {});
        const token = getStoredAuthToken();
        if (token) {
            headers.set("Authorization", `Bearer ${token}`);
        }
        mergedOptions.headers = headers;

        const response = await window.fetch(resource, mergedOptions);
        if (response.status !== 401 || !allowRetry) {
            return response;
        }

        setStoredAuthToken("");
        const freshToken = requestAuthToken();
        if (!freshToken) {
            return response;
        }

        const retryHeaders = new Headers(mergedOptions.headers || {});
        retryHeaders.set("Authorization", `Bearer ${freshToken}`);
        return window.fetch(resource, { ...mergedOptions, headers: retryHeaders });
    }

    function escapeHtml(text) {
        return String(text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function toast(message) {
        window.clearTimeout(state.toastTimer);
        elements.toast.textContent = message;
        elements.toast.classList.add("show");
        state.toastTimer = window.setTimeout(() => {
            elements.toast.classList.remove("show");
        }, 2800);
    }

    function setConnection(status) {
        elements.connectionDot.classList.remove("online", "offline");
        if (status) {
            elements.connectionDot.classList.add(status);
        }
    }

    function showEmpty(target, text) {
        target.innerHTML = `<div class="empty-state">${escapeHtml(text)}</div>`;
    }

    function showError(target, text) {
        target.innerHTML = `<div class="error-state">${escapeHtml(text)}</div>`;
    }

    function openDialog(title, content) {
        elements.dialogTitle.textContent = title;
        elements.dialogContent.textContent = content || "";
        if (typeof elements.dialog.showModal === "function") {
            elements.dialog.showModal();
        } else {
            window.alert(`${title}\n\n${content}`);
        }
    }

    function copyText(text) {
        if (!text) return;
        navigator.clipboard.writeText(text).then(
            () => toast("Copied."),
            () => toast("Copy failed.")
        );
    }

    function addMessage(type, label, text) {
        const article = document.createElement("article");
        article.className = `message ${type}`;
        article.innerHTML = `
            <span class="message-label">${escapeHtml(label)}</span>
            <div class="message-body">${escapeHtml(text)}</div>
            ${type === "assistant" ? `<div class="message-actions"><button class="mini-button" type="button">Copy</button></div>` : ""}
        `;
        if (type === "assistant") {
            article.querySelector("button").addEventListener("click", () => copyText(text));
        }
        elements.chatFeed.appendChild(article);
        elements.chatFeed.scrollTop = elements.chatFeed.scrollHeight;
    }

    function setBusy(isBusy) {
        state.busy = isBusy;
        elements.sendBtn.disabled = isBusy;
        elements.sendBtn.textContent = isBusy ? "..." : "Send";
    }

    function resizeComposer() {
        elements.promptInput.style.height = "auto";
        elements.promptInput.style.height = `${Math.min(elements.promptInput.scrollHeight, 150)}px`;
    }

    function switchView(viewName) {
        state.activeView = viewName;
        elements.viewTitle.textContent = viewTitles[viewName] || "Vaila";

        elements.views.forEach((view) => {
            view.classList.toggle("active", view.id === `view-${viewName}`);
        });
        elements.navButtons.forEach((button) => {
            button.classList.toggle("active", button.dataset.view === viewName);
        });

        refreshActiveView();
    }

    function renderPersonas() {
        elements.personaChips.innerHTML = "";
        state.personas.forEach((persona) => {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "persona-chip";
            chip.textContent = persona.name;
            chip.classList.toggle("active", persona.id === state.activePersona);
            chip.addEventListener("click", () => {
                state.activePersona = persona.id;
                elements.activePersonaLabel.textContent = persona.name;
                renderPersonas();
                toast(`Lens set to ${persona.name}.`);
            });
            elements.personaChips.appendChild(chip);
        });
    }

    async function loadPersonas() {
        try {
            const res = await apiFetch("/api/personas");
            if (!res.ok) throw new Error(`Status ${res.status}`);
            state.personas = await res.json();
            const active = state.personas.find((persona) => persona.id === state.activePersona);
            elements.activePersonaLabel.textContent = active ? active.name : "Proto Jane";
            renderPersonas();
            setConnection("online");
        } catch (err) {
            setConnection("offline");
            elements.personaChips.innerHTML = "";
            addMessage("system", "Connection", `Could not load personas: ${err.message}`);
        }
    }

    async function checkGateway() {
        try {
            const res = await apiFetch("/api/diagnostics");
            if (!res.ok) throw new Error(`Status ${res.status}`);
            const data = await res.json();
            elements.gatewayStatus.textContent = data.server_reachable ? "Online" : "Offline";
            setConnection("online");
        } catch (err) {
            elements.gatewayStatus.textContent = "Unknown";
            setConnection("offline");
        }
    }

    async function sendPrompt(event) {
        event.preventDefault();
        const text = elements.promptInput.value.trim();
        if (!text || state.busy) return;

        elements.promptInput.value = "";
        resizeComposer();
        addMessage("user", "You", text);
        setBusy(true);

        try {
            const res = await apiFetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text,
                    persona: state.activePersona,
                    source: "mobile_web",
                    session_id: "mobile_session"
                })
            });
            if (!res.ok) throw new Error(`Status ${res.status}`);
            const data = await res.json();
            addMessage("assistant", "Vaila", data.text || "(No visible response)");
        } catch (err) {
            addMessage("system", "Error", `Chat request failed: ${err.message}`);
        } finally {
            setBusy(false);
        }
    }

    async function updateMemoryCandidate(candidate, status) {
        try {
            const res = await apiFetch(`/api/memory/candidates/${candidate.candidate_id}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status })
            });
            if (!res.ok) throw new Error(`Status ${res.status}`);
            toast(status === "rejected" ? "Candidate rejected." : "Candidate updated.");
            await loadMemory();
        } catch (err) {
            toast(`Memory update failed: ${err.message}`);
        }
    }

    async function loadMemory() {
        showEmpty(elements.memoryList, "Loading memory candidates...");
        try {
            const res = await apiFetch("/api/memory/candidates");
            if (!res.ok) throw new Error(`Status ${res.status}`);
            const candidates = await res.json();
            elements.memoryCount.textContent = candidates.length;
            if (!candidates.length) {
                showEmpty(elements.memoryList, "No memory candidates are waiting.");
                return;
            }

            elements.memoryList.innerHTML = "";
            candidates.slice(0, 30).forEach((candidate) => {
                const text = candidate.payload?.text || candidate.text || "(empty candidate)";
                const status = candidate.status || "candidate";
                const card = document.createElement("article");
                card.className = "item-card";
                card.innerHTML = `
                    <span class="item-kicker">${escapeHtml(status)}</span>
                    <h3>${escapeHtml(candidate.candidate_id || "Memory Candidate")}</h3>
                    <p>${escapeHtml(text).slice(0, 280)}</p>
                    <div class="meta">
                        <span class="pill warn">Review</span>
                    </div>
                    <div class="card-actions">
                        <button type="button" data-action="details">Details</button>
                        <button type="button" data-action="reject" class="danger">Reject</button>
                    </div>
                `;
                card.querySelector('[data-action="details"]').addEventListener("click", () => {
                    openDialog(candidate.candidate_id || "Memory Candidate", text);
                });
                card.querySelector('[data-action="reject"]').addEventListener("click", () => {
                    updateMemoryCandidate(candidate, "rejected");
                });
                elements.memoryList.appendChild(card);
            });
        } catch (err) {
            elements.memoryCount.textContent = "0";
            showError(elements.memoryList, `Memory load failed: ${err.message}`);
        }
    }

    async function loadFiles() {
        showEmpty(elements.filesList, "Loading workspace files...");
        try {
            const res = await apiFetch("/api/files");
            if (!res.ok) throw new Error(`Status ${res.status}`);
            const files = await res.json();
            elements.filesCount.textContent = files.length;
            if (!files.length) {
                showEmpty(elements.filesList, "No imported files yet.");
                return;
            }

            elements.filesList.innerHTML = "";
            files.slice(0, 35).forEach((file) => {
                const card = document.createElement("article");
                card.className = "item-card";
                card.innerHTML = `
                    <span class="item-kicker">Imported File</span>
                    <h3>${escapeHtml(file.name)}</h3>
                    <div class="meta">
                        <span class="pill">${escapeHtml(file.size_kb)}</span>
                        <span class="pill">${escapeHtml(file.mtime)}</span>
                    </div>
                `;
                elements.filesList.appendChild(card);
            });
        } catch (err) {
            elements.filesCount.textContent = "0";
            showError(elements.filesList, `File list failed: ${err.message}`);
        }
    }

    async function uploadFile() {
        const file = elements.fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);
        showEmpty(elements.filesList, `Uploading ${file.name}...`);

        try {
            const res = await apiFetch("/api/files/upload", {
                method: "POST",
                body: formData
            });
            if (!res.ok) throw new Error(`Status ${res.status}`);
            toast("File uploaded.");
            await loadFiles();
        } catch (err) {
            showError(elements.filesList, `Upload failed: ${err.message}`);
        } finally {
            elements.fileInput.value = "";
        }
    }

    async function loadSystem() {
        showEmpty(elements.systemList, "Checking system health...");
        try {
            const res = await apiFetch("/api/system/health");
            if (!res.ok) throw new Error(`Status ${res.status}`);
            const health = await res.json();
            const rows = [
                ["LM Studio", health.lm_studio, health.lm_studio_endpoint || ""],
                ["Memory DB", health.memory_db, health.memory_db_mode || ""],
                ["Text to Speech", health.tts, ""]
            ];
            const serviceNames = Object.keys(health.registries || {});
            serviceNames.forEach((name) => {
                rows.push([name, Boolean(health.registries[name]), "Registered service"]);
            });

            elements.healthCount.textContent = rows.length;
            elements.systemList.innerHTML = "";
            rows.forEach(([name, ok, detail]) => {
                const card = document.createElement("article");
                card.className = "item-card";
                card.innerHTML = `
                    <span class="item-kicker">Health Check</span>
                    <h3>${escapeHtml(name)}</h3>
                    <p>${escapeHtml(detail || (ok ? "Available" : "Unavailable"))}</p>
                    <div class="meta">
                        <span class="pill ${ok ? "good" : "bad"}">${ok ? "Online" : "Offline"}</span>
                    </div>
                `;
                elements.systemList.appendChild(card);
            });
        } catch (err) {
            elements.healthCount.textContent = "0";
            showError(elements.systemList, `System check failed: ${err.message}`);
        }
    }

    function refreshActiveView() {
        if (state.activeView === "chat") {
            checkGateway();
        } else if (state.activeView === "memory") {
            loadMemory();
        } else if (state.activeView === "files") {
            loadFiles();
        } else if (state.activeView === "system") {
            loadSystem();
        }
    }

    function setupEvents() {
        elements.navButtons.forEach((button) => {
            button.addEventListener("click", () => switchView(button.dataset.view));
        });
        elements.quickActions.forEach((button) => {
            button.addEventListener("click", () => {
                elements.promptInput.value = button.dataset.prompt || "";
                resizeComposer();
                elements.promptInput.focus();
            });
        });
        elements.refreshBtn.addEventListener("click", () => {
            refreshActiveView();
            toast("Refreshed.");
        });
        elements.tokenBtn.addEventListener("click", requestAuthToken);
        elements.chatForm.addEventListener("submit", sendPrompt);
        elements.promptInput.addEventListener("input", resizeComposer);
        elements.fileInput.addEventListener("change", uploadFile);
        elements.dialogClose.addEventListener("click", () => elements.dialog.close());
        elements.gatewayStatus.closest("button").addEventListener("click", checkGateway);
        elements.activePersonaLabel.closest("button").addEventListener("click", () => {
            elements.personaChips.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "start" });
        });
    }

    async function init() {
        setupEvents();
        resizeComposer();
        await loadPersonas();
        await checkGateway();
    }

    init();
});
