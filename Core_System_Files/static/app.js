/* VAILA OS V3 // FRONTEND CONTROLLER (ACTIVE N8N INTEGRATIONS)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // STATE MANAGEMENT
    const state = {
        personas: [],
        activePersona: "proto_jane",
        systemInfo: {},
        activeConsoleTab: "session",
        inspectorOpen: true,
        busy: false,
        
        // Upgraded state hooks
        currentView: "chat",
        activeCandidates: [],
        durableMemories: [],
        selectedCandidate: null,
        activeFiles: [],
        selectedFile: null,
        activeArtifacts: [],
        selectedArtifact: null,
        councilResponses: {},
        
        // n8n Active integration state
        activeWorkflows: [],
        selectedWorkflow: null,
        
        // User Profile state
        activeProfileModules: [],
        selectedProfileModule: null
    };

    // Initialize Session ID
    if (!sessionStorage.getItem("vaila_session_id")) {
        sessionStorage.setItem("vaila_session_id", "session_" + Math.random().toString(36).substring(2, 15));
    }
    const sessionId = sessionStorage.getItem("vaila_session_id");
    const authStorageKey = "vaila_web_auth_token";

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
        const token = window.prompt("Enter the Vaila remote access token for this device:");
        if (token && token.trim()) {
            setStoredAuthToken(token.trim());
            return token.trim();
        }
        return "";
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
        const refreshedToken = requestAuthToken();
        if (!refreshedToken) {
            return response;
        }

        const retryHeaders = new Headers(mergedOptions.headers || {});
        retryHeaders.set("Authorization", `Bearer ${refreshedToken}`);
        return window.fetch(resource, { ...mergedOptions, headers: retryHeaders });
    }

    // DOM ELEMENTS INDEX
    const elements = {
        // Top status
        gatewayStatus: document.getElementById("gateway-status"),
        toggleInspectorBtn: document.getElementById("toggle-inspector-btn"),
        loadingOverlay: document.getElementById("loading-overlay"),
        loadingMessage: document.getElementById("loading-message"),

        // Sidebar cores & tabs
        personaList: document.getElementById("persona-list"),
        runAssessmentBtn: document.getElementById("run-assessment-btn"),
        runSummarizeBtn: document.getElementById("run-summarize-btn"),
        runDiagnosticsBtn: document.getElementById("run-diagnostics-btn"),
        clearChatBtn: document.getElementById("clear-chat-btn"),

        // Workspace tab selectors
        navBtnChat: document.getElementById("nav-btn-chat"),
        navBtnCouncil: document.getElementById("nav-btn-council"),
        navBtnMemory: document.getElementById("nav-btn-memory"),
        navBtnFiles: document.getElementById("nav-btn-files"),
        navBtnArtifacts: document.getElementById("nav-btn-artifacts"),
        navBtnSystem: document.getElementById("nav-btn-system"),
        navBtnN8n: document.getElementById("nav-btn-n8n"),
        navBtnProfile: document.getElementById("nav-btn-profile"),

        // Workspace view containers
        viewChat: document.getElementById("view-chat"),
        viewCouncil: document.getElementById("view-council"),
        viewMemory: document.getElementById("view-memory"),
        viewFiles: document.getElementById("view-files"),
        viewArtifacts: document.getElementById("view-artifacts"),
        viewSystem: document.getElementById("view-system"),
        viewN8n: document.getElementById("view-n8n"),
        viewProfile: document.getElementById("view-profile"),

        // Chat View components
        activeLensIndicator: document.getElementById("active-lens-indicator"),
        activeLensName: document.getElementById("active-lens-name"),
        activeLensTagline: document.getElementById("active-lens-tagline"),
        latencyTag: document.getElementById("latency-tag"),
        chatFeed: document.getElementById("chat-feed"),
        promptInput: document.getElementById("prompt-input"),
        sendBtn: document.getElementById("send-prompt-btn"),
        charCount: document.getElementById("character-count"),

        // Inspector panel
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

        // Council view components
        execCouncilBtn: document.getElementById("exec-council-btn"),
        councilPromptInput: document.getElementById("council-prompt-input"),
        councilFeed: document.getElementById("council-feed"),
        councilSynthBtn: document.getElementById("council-synth-btn"),
        councilDriftBtn: document.getElementById("council-drift-btn"),
        consensusModal: document.getElementById("consensus-modal"),
        closeConsensusBtn: document.getElementById("close-consensus-btn"),
        consensusReportViewer: document.getElementById("consensus-report-viewer"),

        // Memory center components
        memoryCandidatesList: document.getElementById("memory-candidates-list"),
        durableMemoriesList: document.getElementById("durable-memories-list"),
        durableMemoryCount: document.getElementById("durable-memory-count"),
        memCandId: document.getElementById("mem-cand-id"),
        memCandText: document.getElementById("mem-cand-text"),
        memCandCategory: document.getElementById("mem-cand-category"),
        memCandProject: document.getElementById("mem-cand-project"),
        memApproveBtn: document.getElementById("mem-approve-btn"),
        memRejectBtn: document.getElementById("mem-reject-btn"),

        // File vault components
        fileUploader: document.getElementById("file-uploader"),
        triggerUploadBtn: document.getElementById("trigger-upload-btn"),
        sandboxFilesList: document.getElementById("sandbox-files-list"),
        workspaceFilename: document.getElementById("workspace-filename"),
        workspaceFilePreview: document.getElementById("workspace-file-preview"),
        fileDiagnoseBtn: document.getElementById("file-diagnose-btn"),
        fileExtractBtn: document.getElementById("file-extract-btn"),

        // Artifact browser components
        artifactsList: document.getElementById("artifacts-list"),
        artifactTitle: document.getElementById("artifact-title"),
        artifactContentPre: document.getElementById("artifact-content-pre"),
        artifactCopyBtn: document.getElementById("artifact-copy-btn"),
        artifactDownloadBtn: document.getElementById("artifact-download-btn"),

        // System perception components
        systemHealthFeed: document.getElementById("system-health-feed"),
        systemScannerPre: document.getElementById("system-scanner-pre"),
        refreshSystemMapBtn: document.getElementById("refresh-system-map-btn"),
        
        // n8n workflows elements
        n8nWorkflowsList: document.getElementById("n8n-workflows-list"),
        n8nWorkflowTitle: document.getElementById("n8n-workflow-title"),
        n8nWorkflowNodesPreview: document.getElementById("n8n-workflow-nodes-preview"),
        n8nToggleActiveBtn: document.getElementById("n8n-toggle-active-btn"),
        n8nDeleteBtn: document.getElementById("n8n-delete-btn"),
        n8nTemplateName: document.getElementById("n8n-template-name"),
        n8nTemplatePath: document.getElementById("n8n-template-path"),
        n8nTemplateUrl: document.getElementById("n8n-template-url"),
        n8nDeployTemplateBtn: document.getElementById("n8n-deploy-template-btn"),
        n8nCouncilSuggestionsBtn: document.getElementById("n8n-council-suggestions-btn"),
        n8nSuggestionsList: document.getElementById("n8n-suggestions-list"),
        
        // User profile elements
        profileZipPath: document.getElementById("profile-zip-path"),
        profileImportPathBtn: document.getElementById("profile-import-path-btn"),
        profileZipUploader: document.getElementById("profile-zip-uploader"),
        profileTriggerUploadBtn: document.getElementById("profile-trigger-upload-btn"),
        profileModulesList: document.getElementById("profile-modules-list"),
        profileModuleFilename: document.getElementById("profile-module-filename"),
        profileModuleContent: document.getElementById("profile-module-content"),
        profileSaveModuleBtn: document.getElementById("profile-save-module-btn"),
        profileSimPromptInput: document.getElementById("profile-sim-prompt-input"),
        profileRunSimBtn: document.getElementById("profile-run-sim-btn"),
        profileSimResults: document.getElementById("profile-sim-results")
    };

    // INITIALIZATION
    async function init() {
        setupEventListeners();
        await loadAuthStatus();
        await loadPersonas();
        await loadSystemInfo();
        await checkGateway();
        await startConsolePolling();
    }

    function escapeHtml(text) {
        return String(text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    async function loadAuthStatus() {
        try {
            const res = await window.fetch("/api/auth/status");
            if (!res.ok) return;
            const status = await res.json();
            if (status.auth_required) {
                logConsole("[security] remote token protection is active for API requests.", "success");
            } else {
                logConsole("[security] local development mode: API token protection is inactive.", "info");
            }
        } catch (err) {
            logConsole(`[security] auth status unavailable: ${err.message}`, "error");
        }
    }

    // EVENT LISTENERS SETUP
    function setupEventListeners() {
        // Tab switching
        elements.navBtnChat.addEventListener("click", () => switchView("chat"));
        elements.navBtnCouncil.addEventListener("click", () => switchView("council"));
        elements.navBtnMemory.addEventListener("click", () => switchView("memory"));
        elements.navBtnFiles.addEventListener("click", () => switchView("files"));
        elements.navBtnArtifacts.addEventListener("click", () => switchView("artifacts"));
        elements.navBtnSystem.addEventListener("click", () => switchView("system"));
        elements.navBtnN8n.addEventListener("click", () => switchView("n8n"));
        elements.navBtnProfile.addEventListener("click", () => switchView("profile"));

        // Chat send prompt
        elements.sendBtn.addEventListener("click", handleSend);
        elements.promptInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && e.ctrlKey) {
                e.preventDefault();
                handleSend();
            }
        });
        elements.promptInput.addEventListener("input", () => {
            elements.charCount.innerText = `${elements.promptInput.value.length} chars`;
        });

        // COLLAPSE INSPECTOR
        elements.toggleInspectorBtn.addEventListener("click", toggleInspector);
        elements.closeInspectorX.addEventListener("click", toggleInspector);

        // Sidebar assessments & logs
        elements.runAssessmentBtn.addEventListener("click", runSelfAssessment);
        elements.runSummarizeBtn.addEventListener("click", runLogSummary);
        elements.runDiagnosticsBtn.addEventListener("click", () => checkGateway(true));
        elements.clearChatBtn.addEventListener("click", clearChat);

        // Console tabs
        elements.consoleTabSession.addEventListener("click", () => switchConsoleTab("session"));
        elements.consoleTabErrors.addEventListener("click", () => switchConsoleTab("errors"));

        // Upgraded panel actions
        // Council Mode
        elements.execCouncilBtn.addEventListener("click", executeCouncil);
        elements.councilSynthBtn.addEventListener("click", synthesizeCouncilConsensus);
        elements.councilDriftBtn.addEventListener("click", inspectCouncilDrift);
        elements.closeConsensusBtn.addEventListener("click", () => elements.consensusModal.classList.add("hidden"));

        // Memory reviews
        elements.memApproveBtn.addEventListener("click", approveMemoryCandidate);
        elements.memRejectBtn.addEventListener("click", rejectMemoryCandidate);

        // Vault imports & analyzer
        elements.triggerUploadBtn.addEventListener("click", () => elements.fileUploader.click());
        elements.fileUploader.addEventListener("change", handleFileUpload);
        elements.fileDiagnoseBtn.addEventListener("click", analyzeSandboxFile);
        elements.fileExtractBtn.addEventListener("click", extractFileMemories);

        // Artifact controls
        elements.artifactCopyBtn.addEventListener("click", copyArtifactToClipboard);
        elements.artifactDownloadBtn.addEventListener("click", downloadSelectedArtifact);
        elements.refreshSystemMapBtn.addEventListener("click", loadSystemMap);
        
        // n8n active management events
        elements.n8nToggleActiveBtn.addEventListener("click", toggleN8NWorkflow);
        elements.n8nDeleteBtn.addEventListener("click", deleteN8NWorkflow);
        elements.n8nDeployTemplateBtn.addEventListener("click", deployN8NTemplate);
        elements.n8nCouncilSuggestionsBtn.addEventListener("click", consultCouncilForSuggestions);

        // Profile Panel Events
        elements.profileImportPathBtn.addEventListener("click", importProfileFromPath);
        elements.profileTriggerUploadBtn.addEventListener("click", () => elements.profileZipUploader.click());
        elements.profileZipUploader.addEventListener("change", handleProfileZipUpload);
        elements.profileSaveModuleBtn.addEventListener("click", saveProfileModuleContent);
        elements.profileRunSimBtn.addEventListener("click", runProfileRoutingSimulation);
    }

    // VIEW ENGINE NAVIGATION
    function switchView(viewName) {
        if (state.busy && viewName !== "chat") {
            alert("The model pipeline is active. Await directive completion.");
            return;
        }

        state.currentView = viewName;

        // Toggle active nav tab
        const navs = [elements.navBtnChat, elements.navBtnCouncil, elements.navBtnMemory, elements.navBtnFiles, elements.navBtnArtifacts, elements.navBtnSystem, elements.navBtnN8n, elements.navBtnProfile];
        navs.forEach(btn => {
            if (btn.id === `nav-btn-${viewName}`) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });

        // Toggle visibility of panels
        const containers = [elements.viewChat, elements.viewCouncil, elements.viewMemory, elements.viewFiles, elements.viewArtifacts, elements.viewSystem, elements.viewN8n, elements.viewProfile];
        containers.forEach(div => {
            if (div.id === `view-${viewName}`) {
                div.classList.remove("hidden");
            } else {
                div.classList.add("hidden");
            }
        });

        // Load data specific to the view
        if (viewName === "memory") {
            loadMemoryCenter();
        } else if (viewName === "files") {
            loadSandboxFiles();
        } else if (viewName === "artifacts") {
            loadArtifacts();
        } else if (viewName === "system") {
            loadSystemMap();
        } else if (viewName === "n8n") {
            loadN8NWorkflows();
        } else if (viewName === "profile") {
            loadProfileInfo();
        }
        
        logConsole(`[view] navigated to: ${viewName.toUpperCase()}`, "info");
    }

    // -------------------------------------------------------------
    // CHAT DIRECTIVES PIPELINE
    // -------------------------------------------------------------
    async function loadPersonas() {
        try {
            const res = await apiFetch("/api/personas");
            if (!res.ok) throw new Error("Status code " + res.status);
            state.personas = await res.json();
            renderPersonas();
        } catch (err) {
            logConsole(`[error] error loading intelligence cores: ${err.message}`, "error");
            elements.personaList.innerHTML = `<p class="text-muted">Failed to load personas.</p>`;
        }
    }

    async function loadSystemInfo() {
        try {
            const res = await apiFetch("/api/system_info");
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
            const res = await apiFetch("/api/diagnostics");
            if (!res.ok) throw new Error("Reachable test returned non-200");
            const diagnostics = await res.json();
            
            const reachable = diagnostics.server_reachable;
            const model = diagnostics.resolved_model || diagnostics.configured_model || "(auto)";
            
            if (reachable) {
                elements.gatewayStatus.innerText = model.toUpperCase();
                elements.gatewayStatus.className = "status-val text-cyan";
                logConsole(`[gateway] LLM model gateway reachable. active model: ${model}`, "success");
            } else {
                elements.gatewayStatus.innerText = "UNREACHABLE";
                elements.gatewayStatus.className = "status-val text-red";
                logConsole(`[warn] LLM model gateway unreachable. Boot LM Studio.`, "warn");
            }
        } catch (err) {
            elements.gatewayStatus.innerText = "CHECK FAILED";
            elements.gatewayStatus.className = "status-val text-red";
            logConsole(`[error] model gateway check error: ${err.message}`, "error");
        } finally {
            if (manual) hideLoading();
        }
    }

    function renderPersonas() {
        elements.personaList.innerHTML = "";
        state.personas.forEach(p => {
            const card = document.createElement("div");
            card.className = `persona-card ${p.color} ${state.activePersona === p.id ? 'active' : ''}`;
            card.innerHTML = `
                <div class="card-header-meta">
                    <h3>${p.name.toUpperCase()}</h3>
                    <span class="lens-glow-dot ${p.color}"></span>
                </div>
                <div class="tagline">${p.tagline.toUpperCase()}</div>
                <div class="desc">${p.description}</div>
            `;
            card.addEventListener("click", () => selectPersona(p.id));
            elements.personaList.appendChild(card);
        });
    }

    function selectPersona(personaId) {
        state.activePersona = personaId;
        
        document.querySelectorAll(".persona-card").forEach((card, idx) => {
            const p = state.personas[idx];
            if (p && p.id === personaId) {
                card.classList.add("active");
            } else {
                card.classList.remove("active");
            }
        });

        const persona = state.personas.find(p => p.id === personaId);
        if (persona) {
            elements.activeLensName.innerText = persona.name;
            elements.activeLensTagline.innerText = persona.tagline;
            elements.activeLensIndicator.className = `lens-glow-dot ${persona.color}`;
            logConsole(`[lens] aligned cognitive context to: ${persona.name}`, "info");
        }
    }

    async function handleSend() {
        if (state.busy) return;
        const text = elements.promptInput.value.trim();
        if (!text) return;

        state.busy = true;
        elements.promptInput.value = "";
        elements.charCount.innerText = "0 chars";
        
        appendMessage("user", text);
        const typingEl = appendMessage("vaila", "...", true);
        
        const startTime = performance.now();
        logConsole(`[routing] dispatching prompt to deterministic regex router...`, "info");
        
        try {
            const res = await apiFetch("/chat", {
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
            
            elements.latencyTag.innerText = `${latency}s`;
            elements.latencyTag.classList.remove("hidden");
            
            typingEl.remove();
            appendMessage("vaila", data.text);
            
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
            <div class="msg-sender">${senderName.toUpperCase()}</div>
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
            await apiFetch("/chat/clear", {
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

    // -------------------------------------------------------------
    // MULTI-PERSONA COUNCIL ASSEMBLY
    // -------------------------------------------------------------
    async function executeCouncil() {
        const prompt = elements.councilPromptInput.value.trim();
        if (!prompt) {
            alert("Please enter a directive prompt.");
            return;
        }

        const selected = [];
        const personaIds = ["proto_jane", "serren", "maelith", "vecht", "riven"];
        personaIds.forEach(id => {
            const cb = document.getElementById(`council-cb-${id}`);
            if (cb && cb.checked) {
                selected.push(id);
            }
        });

        if (selected.length === 0) {
            alert("Select at least one active council core.");
            return;
        }

        state.busy = true;
        showLoading("Assembling Parallel Council...");
        elements.councilFeed.innerHTML = "";
        logConsole(`[council] starting parallel council execution with cores: ${selected.join(', ')}`, "info");

        try {
            const res = await apiFetch("/api/council", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt, personas: selected })
            });

            if (!res.ok) throw new Error("Council thread execution failed");
            const data = await res.json();
            
            state.councilResponses = data.results;
            
            let feedHtml = "<h3>COUNCIL ASSEMBLY DIALOGUES</h3><br>";
            feedHtml += "<strong>COUNCIL STATUS MATRIX:</strong><br>";
            for (let p in data.status) {
                const name = state.personas.find(pr => pr.id === p)?.name || p;
                feedHtml += `  [âœ“] ${name.toUpperCase()}: <span class="text-cyan">${data.status[p]}</span><br>`;
            }
            feedHtml += "<br><hr><br>";

            for (let p in data.results) {
                const name = state.personas.find(pr => pr.id === p)?.name || p;
                feedHtml += `<h4>--- RESPONSIBILITY LENS: ${name.toUpperCase()} ---</h4>`;
                feedHtml += `<p class="padding-10">${parseMarkdown(data.results[p])}</p><br><br>`;
            }

            elements.councilFeed.innerHTML = feedHtml;
            logConsole(`[council] compiled parallel responses. ready for consensus compilation.`, "success");
        } catch (err) {
            elements.councilFeed.innerHTML = `<div class="text-red">Council failure: ${err.message}</div>`;
            logConsole(`[error] council execution aborted: ${err.message}`, "error");
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    async function synthesizeCouncilConsensus() {
        if (Object.keys(state.councilResponses).length === 0) {
            alert("Execute the council first to gather dialogues.");
            return;
        }

        state.busy = true;
        showLoading("Compiling consensus synthesis directive...");
        logConsole(`[council] starting consensus synthesis worker thread...`, "info");

        try {
            const res = await apiFetch("/api/council/synthesize", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ responses: state.councilResponses })
            });

            if (!res.ok) throw new Error("Consensus synthesis endpoint error");
            const data = await res.json();

            elements.consensusReportViewer.innerHTML = parseMarkdown(data.synthesis);
            elements.consensusModal.classList.remove("hidden");
            logConsole(`[council] synthesis report created and archived as artifact: ${data.filename}`, "success");
        } catch (err) {
            alert("Consensus synthesis aborted: " + err.message);
            logConsole(`[error] synthesis failure: ${err.message}`, "error");
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    async function inspectCouncilDrift() {
        if (Object.keys(state.councilResponses).length === 0) {
            alert("Awaiting council dialogue execution outputs.");
            return;
        }

        try {
            const res = await apiFetch("/api/council/drift", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ responses: state.councilResponses })
            });

            if (!res.ok) throw new Error("Drift check returned non-200");
            const data = await res.json();

            let driftHtml = "<br><hr><br><h3>COUNCIL DRIFT INTEGRITY LEDGER</h3><br>";
            for (let p in data.drift) {
                const name = state.personas.find(pr => pr.id === p)?.name || p;
                const m = data.drift[p];
                driftHtml += `<strong>LENS: ${name.toUpperCase()}</strong><br>`;
                driftHtml += `  Lexical Density: ${m.density} (Word count: ${m.words_count})<br>`;
                driftHtml += `  Alignment Index: ${m.alignment}<br>`;
                driftHtml += `  Drift Integrity: <span class="text-cyan">${m.drift_index}</span><br><br>`;
            }

            elements.councilFeed.innerHTML += driftHtml;
            elements.councilFeed.scrollTop = elements.councilFeed.scrollHeight;
            logConsole(`[council] lens drift and complexity assessment completed.`, "success");
        } catch (err) {
            alert("Drift analysis failure: " + err.message);
        }
    }

    // -------------------------------------------------------------
    // MEMORY CENTER QUEUE REVIEW
    // -------------------------------------------------------------
    async function loadMemoryCenter() {
        await Promise.all([
            loadMemoryCandidates(),
            loadDurableMemories()
        ]);
    }

    async function loadMemoryCandidates() {
        elements.memoryCandidatesList.innerHTML = `<div class="text-muted padding-20">Syncing candidate reviews queue...</div>`;
        try {
            const res = await apiFetch("/api/memory/candidates");
            if (!res.ok) throw new Error("Database returned status code: " + res.status);
            state.activeCandidates = await res.json();
            renderCandidatesList();
        } catch (err) {
            elements.memoryCandidatesList.innerHTML = `<div class="text-red padding-20">Sync failure: ${err.message}</div>`;
        }
    }

    async function loadDurableMemories() {
        if (!elements.durableMemoriesList) return;
        elements.durableMemoriesList.innerHTML = `<div class="text-muted padding-20">Loading durable memories...</div>`;
        try {
            const res = await apiFetch("/api/memory/durable");
            if (!res.ok) throw new Error("Durable memory endpoint returned status code: " + res.status);
            state.durableMemories = await res.json();
            renderDurableMemoriesList();
        } catch (err) {
            elements.durableMemoryCount.innerText = "0";
            elements.durableMemoriesList.innerHTML = `<div class="text-red padding-20">Load failure: ${escapeHtml(err.message)}</div>`;
        }
    }

    function renderCandidatesList() {
        elements.memoryCandidatesList.innerHTML = "";
        if (state.activeCandidates.length === 0) {
            elements.memoryCandidatesList.innerHTML = `<div class="text-muted padding-20">Queue empty or fully promoted.</div>`;
            return;
        }

        state.activeCandidates.forEach(c => {
            const payload = c.payload || {};
            const text = payload.text || "Empty Memory Segment";
            const snippet = text.length > 55 ? text.substring(0, 55) + "..." : text;
            
            const card = document.createElement("div");
            card.className = "vault-item-card";
            card.innerHTML = `
                <div class="vault-item-header">
                    <span>${escapeHtml(c.candidate_id.substring(0, 10).toUpperCase())}</span>
                    <span class="text-muted">${escapeHtml(payload.source || 'agent')}</span>
                </div>
                <div class="vault-item-snippet">${escapeHtml(snippet)}</div>
            `;
            
            card.addEventListener("click", () => selectCandidate(c));
            elements.memoryCandidatesList.appendChild(card);
        });
    }

    function renderDurableMemoriesList() {
        elements.durableMemoriesList.innerHTML = "";
        elements.durableMemoryCount.innerText = String(state.durableMemories.length);

        if (state.durableMemories.length === 0) {
            elements.durableMemoriesList.innerHTML = `<div class="text-muted padding-20">No durable memories saved yet.</div>`;
            return;
        }

        state.durableMemories.forEach(memory => {
            const text = memory.text || "(empty memory)";
            const snippet = text.length > 120 ? text.substring(0, 120) + "..." : text;
            const card = document.createElement("div");
            card.className = "vault-item-card";
            card.innerHTML = `
                <div class="vault-item-header">
                    <span>${escapeHtml((memory.memory_id || "memory").substring(0, 14).toUpperCase())}</span>
                    <span class="text-muted">${escapeHtml(memory.category || "general")}</span>
                </div>
                <div class="vault-item-snippet">${escapeHtml(snippet)}</div>
                <div class="node-meta-details">Project only: ${memory.project_only ? "yes" : "no"} // ${escapeHtml(memory.approved_at || "unknown time")}</div>
            `;
            card.addEventListener("click", () => {
                elements.memCandId.innerText = memory.memory_id || "DURABLE MEMORY";
                elements.memCandText.value = text;
                elements.memCandCategory.value = memory.category || "general";
                elements.memCandProject.checked = Boolean(memory.project_only);
                elements.memApproveBtn.disabled = true;
                elements.memRejectBtn.disabled = true;
                document.querySelectorAll("#durable-memories-list .vault-item-card").forEach(node => node.classList.remove("active"));
                card.classList.add("active");
                document.querySelectorAll("#memory-candidates-list .vault-item-card").forEach(node => node.classList.remove("active"));
            });
            elements.durableMemoriesList.appendChild(card);
        });
    }

    function selectCandidate(candidate) {
        state.selectedCandidate = candidate;
        
        document.querySelectorAll("#memory-candidates-list .vault-item-card").forEach((card, idx) => {
            const c = state.activeCandidates[idx];
            if (c && c.candidate_id === candidate.candidate_id) {
                card.classList.add("active");
            } else {
                card.classList.remove("active");
            }
        });

        const payload = candidate.payload || {};
        elements.memCandId.innerText = candidate.candidate_id;
        elements.memCandText.value = payload.text || "";
        elements.memCandCategory.value = payload.route?.task_type || "general";
        elements.memCandProject.checked = true;
        elements.memApproveBtn.disabled = false;
        elements.memRejectBtn.disabled = false;
        document.querySelectorAll("#durable-memories-list .vault-item-card").forEach(node => node.classList.remove("active"));
    }

    async function approveMemoryCandidate() {
        const c_id = elements.memCandId.innerText;
        if (c_id === "NONE SELECTED") {
            alert("Select a candidate to approve.");
            return;
        }

        const text = elements.memCandText.value.trim();
        if (!text) {
            alert("Memory content cannot be empty.");
            return;
        }

        state.busy = true;
        showLoading("Promoting candidate to durable database...");

        try {
            const resDur = await apiFetch("/api/memory/durable", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: text,
                    category: elements.memCandCategory.value,
                    project_only: elements.memCandProject.checked,
                    original_candidate: c_id
                })
            });

            if (!resDur.ok) throw new Error("Failed to write to durable store");

            const resUp = await apiFetch(`/api/memory/candidates/${c_id}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: "approved", text: text })
            });

            if (!resUp.ok) throw new Error("Failed to update queue candidate status");

            logConsole(`[memory] Promoted candidate ${c_id.substring(0,8)} to durable database.`, "success");
            alert("Memory candidate approved and synchronized successfully!");
            
            clearMemoryForm();
            await loadMemoryCenter();
        } catch (err) {
            alert("Approval failure: " + err.message);
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    async function rejectMemoryCandidate() {
        const c_id = elements.memCandId.innerText;
        if (c_id === "NONE SELECTED") {
            alert("Select a candidate to reject.");
            return;
        }

        if (!confirm("Are you sure you want to reject this memory fragment?")) return;

        state.busy = true;
        showLoading("Rejecting memory candidate...");

        try {
            const res = await apiFetch(`/api/memory/candidates/${c_id}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: "rejected" })
            });

            if (!res.ok) throw new Error("Failed to update candidate status");

            logConsole(`[memory] Candidate ${c_id.substring(0,8)} rejected and cleared.`, "warn");
            
            clearMemoryForm();
            await loadMemoryCandidates();
        } catch (err) {
            alert("Rejection failure: " + err.message);
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    function clearMemoryForm() {
        elements.memCandId.innerText = "NONE SELECTED";
        elements.memCandText.value = "";
        elements.memCandCategory.value = "general";
        elements.memCandProject.checked = true;
        elements.memApproveBtn.disabled = false;
        elements.memRejectBtn.disabled = false;
        state.selectedCandidate = null;
    }

    // -------------------------------------------------------------
    // FILES WORKSPACE VAULT
    // -------------------------------------------------------------
    async function loadSandboxFiles() {
        elements.sandboxFilesList.innerHTML = `<div class="text-muted padding-20">Listing vault cache...</div>`;
        try {
            const res = await apiFetch("/api/files");
            if (!res.ok) throw new Error("Cannot list directory files");
            state.activeFiles = await res.json();
            renderFilesList();
        } catch (err) {
            elements.sandboxFilesList.innerHTML = `<div class="text-red padding-20">List error: ${err.message}</div>`;
        }
    }

    function renderFilesList() {
        elements.sandboxFilesList.innerHTML = "";
        if (state.activeFiles.length === 0) {
            elements.sandboxFilesList.innerHTML = `<div class="text-muted padding-20">Vault empty. Import documents above.</div>`;
            return;
        }

        state.activeFiles.forEach(f => {
            const card = document.createElement("div");
            card.className = "vault-item-card";
            card.innerHTML = `
                <div class="vault-item-header">
                    <span>${f.name}</span>
                    <span class="text-muted">${f.size_kb}</span>
                </div>
                <div class="vault-item-snippet">Imported at: ${f.mtime}</div>
            `;
            
            card.addEventListener("click", () => selectFile(f));
            elements.sandboxFilesList.appendChild(card);
        });
    }

    function selectFile(file) {
        state.selectedFile = file;

        document.querySelectorAll("#sandbox-files-list .vault-item-card").forEach((card, idx) => {
            const f = state.activeFiles[idx];
            if (f && f.name === file.name) {
                card.classList.add("active");
            } else {
                card.classList.remove("active");
            }
        });

        elements.workspaceFilename.innerText = file.name;
        elements.fileDiagnoseBtn.disabled = false;
        elements.fileExtractBtn.disabled = false;
        
        elements.workspaceFilePreview.innerText = "Loading document context stream preview...";

        try {
            apiFetch(`/static/../../Sandbox/Imported_Documents/${file.name}`)
                .then(res => {
                    if (!res.ok) return `[Binary file preview not supported or file not read directly]. Size: ${file.size_kb}`;
                    return res.text();
                })
                .then(txt => {
                    elements.workspaceFilePreview.innerText = txt.substring(0, 1500) + (txt.length > 1500 ? "\n\n... [Content clipped for GUI viewer]" : "");
                })
                .catch(err => {
                    elements.workspaceFilePreview.innerText = `Preview unavailable: ${err.message}`;
                });
        } catch (err) {
            elements.workspaceFilePreview.innerText = `Diagnostic Preview unavailable.`;
        }
    }

    async function handleFileUpload() {
        const file = elements.fileUploader.files[0];
        if (!file) return;

        state.busy = true;
        showLoading("Importing file to sandbox...");
        logConsole(`[vault] Uploading workspace document: ${file.name}`, "info");

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await apiFetch("/api/files/upload", {
                method: "POST",
                body: formData
            });

            if (!res.ok) throw new Error("Upload handler returned status error");
            const data = await res.json();

            logConsole(`[vault] Upload complete. Saved as sandboxed file: ${data.filename}`, "success");
            alert("Document imported to Sandbox successfully!");
            
            await loadSandboxFiles();
            elements.fileUploader.value = "";
        } catch (err) {
            alert("Upload failed: " + err.message);
            logConsole(`[error] sandbox write failed: ${err.message}`, "error");
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    async function analyzeSandboxFile() {
        const filename = elements.workspaceFilename.innerText;
        if (filename === "SELECT A VAULT FILE") return;

        state.busy = true;
        showLoading("Executing document diagnostics...");
        logConsole(`[task] analyzing sandbox file dependencies: ${filename}`, "info");

        try {
            const res = await apiFetch("/api/files/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ filename })
            });

            if (!res.ok) throw new Error("Analysis failed");
            const data = await res.json();

            elements.workspaceFilePreview.innerText = data.analysis;
            logConsole(`[task] analysis complete. archived as artifact: ${data.filename}`, "success");
            alert("Analysis completed! Diagnostic report generated successfully.");
        } catch (err) {
            alert("Analysis failure: " + err.message);
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    async function extractFileMemories() {
        const filename = elements.workspaceFilename.innerText;
        if (filename === "SELECT A VAULT FILE") return;

        state.busy = true;
        showLoading("Extracting memory rules...");
        logConsole(`[task] running memory heuristics extraction on file: ${filename}`, "info");

        try {
            const res = await apiFetch("/api/files/extract", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ filename })
            });

            if (!res.ok) throw new Error("Memory extraction endpoint error");
            const data = await res.json();

            logConsole(`[task] extraction completed. Drafted ${data.extracted_count} memory candidates into queue.`, "success");
            alert(`Extraction completed successfully! Drafted ${data.extracted_count} memory candidates into the Memory review queue.`);
        } catch (err) {
            alert("Extraction failure: " + err.message);
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    // -------------------------------------------------------------
    // ARTIFACTS ARCHIVE VAULT
    // -------------------------------------------------------------
    async function loadArtifacts() {
        elements.artifactsList.innerHTML = `<div class="text-muted padding-20">Reading artifact database...</div>`;
        try {
            const res = await apiFetch("/api/artifacts");
            if (!res.ok) throw new Error("Failed to scan directory");
            state.activeArtifacts = await res.json();
            renderArtifactsList();
        } catch (err) {
            elements.artifactsList.innerHTML = `<div class="text-red padding-20">Scan error: ${err.message}</div>`;
        }
    }

    function renderArtifactsList() {
        elements.artifactsList.innerHTML = "";
        if (state.activeArtifacts.length === 0) {
            elements.artifactsList.innerHTML = `<div class="text-muted padding-20">No archives generated yet.</div>`;
            return;
        }

        state.activeArtifacts.forEach(art => {
            const card = document.createElement("div");
            card.className = "vault-item-card";
            card.innerHTML = `
                <div class="vault-item-header">
                    <span>${art.name}</span>
                    <span class="text-muted">${art.size_kb}</span>
                </div>
                <div class="vault-item-snippet">Created: ${art.mtime}</div>
            `;
            
            card.addEventListener("click", () => selectArtifact(art));
            elements.artifactsList.appendChild(card);
        });
    }

    async function selectArtifact(art) {
        state.selectedArtifact = art;

        document.querySelectorAll("#artifacts-list .vault-item-card").forEach((card, idx) => {
            const a = state.activeArtifacts[idx];
            if (a && a.name === art.name) {
                card.classList.add("active");
            } else {
                card.classList.remove("active");
            }
        });

        elements.artifactTitle.innerText = art.name;
        elements.artifactCopyBtn.disabled = false;
        
        elements.artifactDownloadBtn.classList.remove("disabled");
        elements.artifactDownloadBtn.href = "#";

        try {
            const res = await apiFetch(`/api/artifacts/${art.name}`);
            if (!res.ok) throw new Error("File not found");
            const txt = await res.text();
            elements.artifactContentPre.innerText = txt;
        } catch (err) {
            elements.artifactContentPre.innerText = `Failed to preview: ${err.message}`;
        }
    }

    function copyArtifactToClipboard() {
        const text = elements.artifactContentPre.innerText;
        if (text === "Awaiting archive selection..." || !text) return;

        navigator.clipboard.writeText(text);
        alert("Artifact copied to clipboard!");
    }

    async function downloadSelectedArtifact(event) {
        event.preventDefault();
        const art = state.selectedArtifact;
        if (!art) return;

        try {
            const res = await apiFetch(`/api/artifacts/${art.name}`);
            if (!res.ok) throw new Error("Download unavailable");
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = art.name;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        } catch (err) {
            alert("Artifact download failed: " + err.message);
        }
    }

    // -------------------------------------------------------------
    // SYSTEM SELF-PERCEPTION MAP VIEW
    // -------------------------------------------------------------
    async function loadSystemMap() {
        elements.systemHealthFeed.innerHTML = `<div class="text-muted padding-20">Pinging node connectivity ledgers...</div>`;
        elements.systemScannerPre.innerText = "Analyzing file tree scanner...";

        try {
            const resH = await apiFetch("/api/system/health");
            if (!resH.ok) throw new Error("Failed to load health registry");
            const health = await resH.json();
            renderHealthNodes(health);

            const resS = await apiFetch("/api/system/map");
            if (!resS.ok) throw new Error("Disk tree scanner error");
            const scan = await resS.json();
            renderScannerTree(scan);
            
            logConsole("[system] diagnostic perception checks verified.", "success");
        } catch (err) {
            elements.systemHealthFeed.innerHTML = `<div class="text-red padding-20">Integrity scan failed: ${err.message}</div>`;
        }
    }

    function renderHealthNodes(health) {
        elements.systemHealthFeed.innerHTML = "";

        const lmCard = document.createElement("div");
        lmCard.className = "health-node-card";
        lmCard.innerHTML = `
            <div class="health-node-header">
                <span>LM STUDIO GATEWAY</span>
                <span class="node-status-badge ${health.lm_studio ? 'online' : 'offline'}">${health.lm_studio ? 'ONLINE' : 'OFFLINE'}</span>
            </div>
            <div class="node-meta-details">Endpoint: ${health.lm_studio_endpoint}</div>
        `;
        elements.systemHealthFeed.appendChild(lmCard);

        const memCard = document.createElement("div");
        memCard.className = "health-node-card";
        memCard.innerHTML = `
            <div class="health-node-header">
                <span>OPENBRAIN MEMORY DB</span>
                <span class="node-status-badge ${health.memory_db ? 'online' : 'offline'}">${health.memory_db ? 'ONLINE' : 'OFFLINE'}</span>
            </div>
            <div class="node-meta-details">Mode: ${health.memory_db_mode.toUpperCase()}</div>
        `;
        elements.systemHealthFeed.appendChild(memCard);

        const ttsCard = document.createElement("div");
        ttsCard.className = "health-node-card";
        ttsCard.innerHTML = `
            <div class="health-node-header">
                <span>SPEECH (TTS) ENGINE</span>
                <span class="node-status-badge ${health.tts ? 'online' : 'offline'}">${health.tts ? 'ONLINE' : 'OFFLINE'}</span>
            </div>
            <div class="node-meta-details">Stubs: Native drivers checked.</div>
        `;
        elements.systemHealthFeed.appendChild(ttsCard);

        const regTitle = document.createElement("h4");
        regTitle.className = "card-title mt-20";
        regTitle.innerText = "CONNECTED SERVICES";
        elements.systemHealthFeed.appendChild(regTitle);

        for (let name in health.registries) {
            const en = health.registries[name];
            const regCard = document.createElement("div");
            regCard.className = "health-node-card";
            regCard.innerHTML = `
                <div class="health-node-header">
                    <span>${name.toUpperCase()} ADAPTER</span>
                    <span class="node-status-badge ${en ? 'online' : 'offline'}">${en ? 'ENABLED' : 'DISABLED'}</span>
                </div>
            `;
            elements.systemHealthFeed.appendChild(regCard);
        }
    }

    function renderScannerTree(scan) {
        let txt = `=== ACTIVE DIRECTORY SCAN ===\n`;
        txt += `File count: ${scan.file_count}\n`;
        txt += `Workspace size: ${scan.total_size_mb}\n\n`;

        txt += `=== expected files check ===\n`;
        for (let path in scan.alerts) {
            const ex = scan.alerts[path];
            txt += `  [${ex ? 'âœ“' : 'âœ—'}] ${path}: ${ex ? 'FOUND' : 'MISSING'}\n`;
        }

        txt += `\n=== workspace tree maps ===\n`;
        txt += scan.tree.join('\n');

        elements.systemScannerPre.innerText = txt;
    }

    // -------------------------------------------------------------
    // N8N ACTIVE WORKFLOWS BROWSER
    // -------------------------------------------------------------
    async function loadN8NWorkflows() {
        elements.n8nWorkflowsList.innerHTML = `<div class="text-muted padding-20">Syncing container workflows...</div>`;
        try {
            const res = await apiFetch("/api/n8n/workflows");
            if (!res.ok) throw new Error("Docker REST API returned status code " + res.status);
            const data = await res.json();
            
            if (data.ok) {
                state.activeWorkflows = data.workflows;
                renderN8NWorkflowsList();
            } else {
                throw new Error(data.error);
            }
        } catch (err) {
            elements.n8nWorkflowsList.innerHTML = `<div class="text-red padding-20">Docker Sync Failure: ${err.message}</div>`;
            logConsole(`[error] n8n rest sync failed: ${err.message}`, "error");
        } finally {
            loadDefaultSuggestions();
        }
    }

    function renderN8NWorkflowsList() {
        elements.n8nWorkflowsList.innerHTML = "";
        if (state.activeWorkflows.length === 0) {
            elements.n8nWorkflowsList.innerHTML = `<div class="text-muted padding-20">No workflows found. Draft templates below.</div>`;
            return;
        }

        state.activeWorkflows.forEach(wf => {
            const card = document.createElement("div");
            card.className = "vault-item-card";
            card.innerHTML = `
                <div class="vault-item-header">
                    <span>${wf.name}</span>
                    <span class="node-status-badge ${wf.active ? 'online' : 'offline'}">${wf.active ? 'ACTIVE' : 'INACTIVE'}</span>
                </div>
                <div class="vault-item-snippet">ID: ${wf.id}</div>
            `;
            card.addEventListener("click", () => selectN8NWorkflow(wf));
            elements.n8nWorkflowsList.appendChild(card);
        });
    }

    function selectN8NWorkflow(wf) {
        state.selectedWorkflow = wf;

        // Highlight
        document.querySelectorAll("#n8n-workflows-list .vault-item-card").forEach((card, idx) => {
            const w = state.activeWorkflows[idx];
            if (w && w.id === wf.id) {
                card.classList.add("active");
            } else {
                card.classList.remove("active");
            }
        });

        elements.n8nWorkflowTitle.innerText = wf.name.toUpperCase();
        elements.n8nToggleActiveBtn.disabled = false;
        elements.n8nDeleteBtn.disabled = false;

        // Set action button labels
        elements.n8nToggleActiveBtn.innerText = wf.active ? "DEACTIVATE WORKFLOW" : "ACTIVATE WORKFLOW";
        if (wf.active) {
            elements.n8nToggleActiveBtn.className = "action-btn-red";
        } else {
            elements.n8nToggleActiveBtn.className = "action-btn-accent";
        }

        // Render node JSONs
        elements.n8nWorkflowNodesPreview.innerText = JSON.stringify({
            nodes: wf.nodes,
            connections: wf.connections
        }, null, 2);
    }

    async function toggleN8NWorkflow() {
        const wf = state.selectedWorkflow;
        if (!wf) return;

        state.busy = true;
        const targetActiveState = !wf.active;
        showLoading(targetActiveState ? "Activating n8n workflow..." : "Deactivating n8n workflow...");

        try {
            const res = await apiFetch(`/api/n8n/workflows/${wf.id}/toggle`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ active: targetActiveState })
            });

            if (!res.ok) throw new Error("Failed to toggle workflow status");
            
            logConsole(`[n8n] Toggled workflow ${wf.id} to state: ${targetActiveState}`, "success");
            alert(targetActiveState ? "Workflow successfully activated!" : "Workflow successfully deactivated!");
            
            // Reload & select again
            await loadN8NWorkflows();
            
            // Re-select
            const updated = state.activeWorkflows.find(w => w.id === wf.id);
            if (updated) selectN8NWorkflow(updated);
        } catch (err) {
            alert("Failed to toggle workflow state: " + err.message);
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    async function deleteN8NWorkflow() {
        const wf = state.selectedWorkflow;
        if (!wf) return;

        if (!confirm(`Are you sure you want to permanently delete n8n workflow: ${wf.name}?`)) return;

        state.busy = true;
        showLoading("Deleting n8n workflow...");

        try {
            const res = await apiFetch(`/api/n8n/workflows/${wf.id}`, {
                method: "DELETE"
            });

            if (!res.ok) throw new Error("Failed to delete workflow");
            
            logConsole(`[n8n] Workflow deleted successfully: ${wf.id}`, "warn");
            alert("Workflow deleted successfully!");
            
            // Clear details
            elements.n8nWorkflowTitle.innerText = "SELECT A WORKFLOW";
            elements.n8nWorkflowNodesPreview.innerText = "Select a workflow on the left to inspect node configurations...";
            elements.n8nToggleActiveBtn.disabled = true;
            elements.n8nDeleteBtn.disabled = true;
            
            await loadN8NWorkflows();
        } catch (err) {
            alert("Failed to delete workflow: " + err.message);
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    async function deployN8NTemplate() {
        const name = elements.n8nTemplateName.value.trim();
        const path = elements.n8nTemplatePath.value.trim();
        const url = elements.n8nTemplateUrl.value.trim();

        if (!name || !path || !url) {
            alert("All template fields must be completed.");
            return;
        }

        state.busy = true;
        showLoading("Drafting and deploying AI Template...");
        logConsole(`[n8n] Compiling trigger template: ${name} (path: /webhook/${path})`, "info");

        try {
            const res = await apiFetch("/api/n8n/workflows/template", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, path, action_url: url })
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                const errMsg = errData.detail || "Failed to deploy template";
                throw new Error(errMsg);
            }
            const data = await res.json();

            logConsole(`[n8n] Workflow successfully deployed. ID: ${data.workflow.id}`, "success");
            alert(`Workflow deployed successfully!\nID: ${data.workflow.id}\n\nNote: You can activate it from the active console controls above.`);
            
            // Reload
            await loadN8NWorkflows();
        } catch (err) {
            alert("Failed to deploy template: " + err.message);
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    // -------------------------------------------------------------
    // OPERATIONAL REPORTS DISPATCHERS
    // -------------------------------------------------------------
    async function runSelfAssessment() {
        showLoading("Interrogating system sandbox...");
        logConsole("[task] initiating SelfAssessmentTool script...", "info");
        try {
            const res = await apiFetch("/api/reports/self_assessment", { method: "POST" });
            if (!res.ok) throw new Error("Assessment returned status error");
            const data = await res.json();
            
            switchView("chat");
            appendMessage("vaila", data.report);
            logConsole(`[task] self-assessment completed. report generated: ${data.filename}`, "success");
        } catch (err) {
            switchView("chat");
            appendMessage("vaila", `**Self-Assessment Failure:**\n\n\`\`\`\n${err.message}\n\`\`\``);
            logConsole(`[error] self-assessment aborted: ${err.message}`, "error");
        } finally {
            hideLoading();
        }
    }

    async function runLogSummary() {
        showLoading("Collating daily operational logs...");
        logConsole("[task] launching LogSummarizer tool...", "info");
        try {
            const res = await apiFetch("/api/reports/summarize", { method: "POST" });
            if (!res.ok) throw new Error("Summarizer returned status error");
            const data = await res.json();
            
            switchView("chat");
            appendMessage("vaila", data.summary);
            logConsole(`[task] log summary completed. summary archived: ${data.filename}`, "success");
        } catch (err) {
            switchView("chat");
            appendMessage("vaila", `**Log Summarization Failure:**\n\n\`\`\`\n${err.message}\n\`\`\``);
            logConsole(`[error] log summary aborted: ${err.message}`, "error");
        } finally {
            hideLoading();
        }
    }

    // COLLAPSIBLE INSPECTOR BAR
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

        elements.routeTaskType.innerText = route.task_type || "general_chat";
        elements.routePersona.innerText = route.persona || "proto_jane";
        
        const activeColor = state.personas.find(p => p.id === route.persona)?.color || "cyan";
        elements.routePersona.className = `value badge text-${activeColor}`;

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

        const payload = { route, meta };
        elements.metadataViewer.innerText = JSON.stringify(payload, null, 2);
    }

    // CONSOLE POLLING LEDGER
    async function startConsolePolling() {
        pollConsoleLogs();
        setInterval(pollConsoleLogs, 3000);
    }

    async function pollConsoleLogs() {
        try {
            const apiPath = state.activeConsoleTab === "session" ? "/api/logs/session" : "/api/logs/errors";
            const res = await apiFetch(apiPath + "?limit=40");
            if (!res.ok) return;
            const logs = await res.json();
            renderConsoleLogs(logs);
        } catch (err) {
            // Quiet
        }
    }

    function renderConsoleLogs(logs) {
        if (!logs || logs.length === 0) {
            elements.consoleOutput.innerHTML = `<div class="terminal-line text-muted">[system] console waiting for entries...</div>`;
            return;
        }

        elements.consoleOutput.innerHTML = "";
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

    // MODALS OVERLAYS
    function showLoading(msg) {
        elements.loadingMessage.innerText = msg;
        elements.loadingOverlay.classList.remove("hidden");
    }

    function hideLoading() {
        elements.loadingOverlay.classList.add("hidden");
    }

    // CUSTOM OFFLINE MARKDOWN PARSER
    function parseMarkdown(text) {
        if (!text) return "";
        
        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
            
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
        let listType = "";
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
        
        codeBlocks.forEach((block, idx) => {
            const langLabel = block.lang ? `<span class="code-lang-label">${block.lang.toUpperCase()}</span>` : "";
            const replacement = `
                <pre>${langLabel}<code>${block.code}</code><button class="code-copy-btn" onclick="navigator.clipboard.writeText(this.previousSibling.innerText); this.innerText='Copied!'; setTimeout(()=>this.innerText='Copy', 2000)">Copy</button></pre>
            `;
            result = result.replace(`__CODE_BLOCK_PLACEHOLDER_${idx}__`, replacement);
        });
        
        result = result.replace(/<p><br><\/p>/g, "<br>");
        result = result.replace(/<p>__CODE_BLOCK_PLACEHOLDER_\d+__<\/p>/g, (m) => m.replace(/<\/?p>/g, ""));
        
        return result;
    }

    function parseInlineMarkdown(text) {
        let res = text;
        res = res.replace(/`([^`]+)`/g, "<code>$1</code>");
        res = res.replace(/\*\*([^*]+)\*\?/g, "<strong>$1</strong>");
        res = res.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        res = res.replace(/\*([^*]+)\*/g, "<em>$1</em>");
        res = res.replace(/_([^_]+)_/g, "<em>$1</em>");
        res = res.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
        return res;
    }

    // -------------------------------------------------------------
    // N8N AI SUGGESTIONS LAB
    // -------------------------------------------------------------
    const defaultN8NSuggestions = [
        {
            name: "Discord Alert Gateway",
            path: "discord-notifier",
            action_url: "https://discord.com/api/webhooks/dummy_id/dummy_token",
            description: "Webhook Trigger -> Verify Token -> HTTP POST alerts to Discord Channels."
        },
        {
            name: "Vaila Log Streamer",
            path: "vaila-logs",
            action_url: "http://localhost:8000/api/logs",
            description: "Webhook Trigger -> Verify Secret -> Stream logs to Sandbox central server."
        },
        {
            name: "OpenBrain Sync Webhook",
            path: "openbrain-sync",
            action_url: "http://localhost:8000/api/openbrain/sync",
            description: "Webhook Trigger -> Extract memory candidates automatically to durable store."
        }
    ];

    function loadDefaultSuggestions() {
        renderSuggestionsList(defaultN8NSuggestions);
    }

    function renderSuggestionsList(suggestions) {
        elements.n8nSuggestionsList.innerHTML = "";
        if (!suggestions || suggestions.length === 0) {
            elements.n8nSuggestionsList.innerHTML = `<div class="text-muted padding-20">No suggestions available.</div>`;
            return;
        }

        suggestions.forEach(sugg => {
            const card = document.createElement("div");
            card.className = "vault-item-card";
            card.style.borderLeft = "3px solid var(--accent-purple)";
            card.style.marginBottom = "8px";
            card.innerHTML = `
                <div style="font-weight: bold; color: var(--text-light); font-size: 13px;">${sugg.name.toUpperCase()}</div>
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 3px; font-family: monospace;">path: /webhook/${sugg.path}</div>
                <div style="font-size: 11px; color: var(--text-color); margin-top: 5px; line-height: 1.3;">${sugg.description}</div>
            `;
            card.addEventListener("click", () => populateTemplateForm(sugg));
            elements.n8nSuggestionsList.appendChild(card);
        });
    }

    function populateTemplateForm(sugg) {
        elements.n8nTemplateName.value = sugg.name;
        elements.n8nTemplatePath.value = sugg.path;
        elements.n8nTemplateUrl.value = sugg.action_url;
        logConsole(`[n8n] Auto-populated template inputs from: ${sugg.name}`, "info");
    }

    async function consultCouncilForSuggestions() {
        state.busy = true;
        showLoading("Consulting multi-persona Council...");
        logConsole("[n8n] Council Assembly active: drafting automation recommendations...", "info");
        try {
            const res = await apiFetch("/api/n8n/workflows/suggestions/council", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            if (!res.ok) throw new Error("Council generation endpoint failed.");
            const data = await res.json();
            
            if (data.ok) {
                renderSuggestionsList(data.suggestions);
                logConsole("[n8n] Council recommendations successfully compiled!", "success");
                alert("The Council has returned custom automation suggestions! Click any suggestion card on the right to auto-populate the deploy form.");
            } else {
                throw new Error(data.error || "Unknown response error");
            }
        } catch (err) {
            logConsole(`[error] Council consultation failed: ${err.message}. Loading defaults.`, "error");
            loadDefaultSuggestions();
            alert("Model Gateway offline. Pre-templated system suggestions loaded successfully.");
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    // -------------------------------------------------------------
    // USER PROFILE CONTROLLER WORKERS
    // -------------------------------------------------------------
    async function loadProfileInfo() {
        elements.profileModulesList.innerHTML = `<div class="text-muted padding-20">Syncing user profile modules...</div>`;
        try {
            const res = await apiFetch("/api/profile/info");
            if (!res.ok) throw new Error("Failed to load profile info");
            const data = await res.json();
            
            if (data.loaded) {
                state.activeProfileModules = data.modules;
                logConsole(`[profile] user profile loaded: ${data.profile_name} (v${data.version})`, "success");
                renderProfileModulesList();
            } else {
                state.activeProfileModules = [];
                elements.profileModulesList.innerHTML = `<div class="text-muted padding-20">${data.message}</div>`;
                clearProfileEditor();
                logConsole(`[warn] no active user profile loaded. Please import a zip file.`, "warn");
            }
        } catch (err) {
            elements.profileModulesList.innerHTML = `<div class="text-red padding-20">Load error: ${err.message}</div>`;
        }
    }

    function renderProfileModulesList() {
        elements.profileModulesList.innerHTML = "";
        if (state.activeProfileModules.length === 0) {
            elements.profileModulesList.innerHTML = `<div class="text-muted padding-20">No profile modules.</div>`;
            return;
        }

        state.activeProfileModules.forEach(mod => {
            const card = document.createElement("div");
            card.className = "vault-item-card";
            card.innerHTML = `
                <div class="vault-item-header">
                    <span>${mod.title}</span>
                    <span class="text-muted" style="font-family:monospace; font-size:9px;">${mod.file}</span>
                </div>
                <div class="vault-item-snippet" style="font-size:10px; color: var(--text-muted);">Dynamic matching module</div>
            `;
            card.addEventListener("click", () => selectProfileModule(mod));
            elements.profileModulesList.appendChild(card);
        });
    }

    async function selectProfileModule(mod) {
        state.selectedProfileModule = mod;

        document.querySelectorAll("#profile-modules-list .vault-item-card").forEach((card, idx) => {
            const m = state.activeProfileModules[idx];
            if (m && m.file === mod.file) {
                card.classList.add("active");
            } else {
                card.classList.remove("active");
            }
        });

        elements.profileModuleFilename.innerText = mod.title.toUpperCase();
        elements.profileModuleContent.value = "Loading module content rules...";
        elements.profileSaveModuleBtn.disabled = true;

        try {
            const res = await apiFetch(`/api/profile/module/${mod.file}`);
            if (!res.ok) throw new Error("Failed to load module content");
            const text = await res.text();
            
            elements.profileModuleContent.value = text;
            elements.profileSaveModuleBtn.disabled = false;
            logConsole(`[profile] loaded module content: ${mod.file}`, "info");
        } catch (err) {
            elements.profileModuleContent.value = `Error loading module content: ${err.message}`;
            logConsole(`[error] failed to load module '${mod.file}': ${err.message}`, "error");
        }
    }

    function clearProfileEditor() {
        elements.profileModuleFilename.innerText = "SELECT A PROFILE MODULE";
        elements.profileModuleContent.value = "";
        elements.profileSaveModuleBtn.disabled = true;
        state.selectedProfileModule = null;
    }

    async function saveProfileModuleContent() {
        const mod = state.selectedProfileModule;
        if (!mod) {
            alert("No module selected to save.");
            return;
        }

        const text = elements.profileModuleContent.value;
        state.busy = true;
        showLoading(`Saving module ${mod.title}...`);
        logConsole(`[profile] saving updates to module: ${mod.file}`, "info");

        try {
            const res = await apiFetch(`/api/profile/module/${mod.file}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content: text })
            });

            if (!res.ok) throw new Error("Server failed to save module");
            
            logConsole(`[profile] module ${mod.file} saved successfully!`, "success");
            alert(`Module content for '${mod.title}' saved successfully!`);
        } catch (err) {
            alert("Failed to save module: " + err.message);
            logConsole(`[error] save aborted: ${err.message}`, "error");
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    async function importProfileFromPath() {
        const path = elements.profileZipPath.value.trim();
        if (!path) {
            alert("Enter a valid local ZIP absolute path.");
            return;
        }

        state.busy = true;
        showLoading("Importing user profile zip archive...");
        logConsole(`[profile] importing local zip path: ${path}`, "info");

        try {
            const res = await apiFetch("/api/profile/import", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ zip_path: path })
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "ZIP extraction failed.");
            }
            const data = await res.json();
            
            logConsole(`[profile] ZIP imported successfully. Extracted to: ${data.extracted_to}`, "success");
            alert("User profile ZIP imported and extracted successfully!");
            await loadProfileInfo();
        } catch (err) {
            alert("Import aborted: " + err.message);
            logConsole(`[error] import failed: ${err.message}`, "error");
        } finally {
            state.busy = false;
            hideLoading();
        }
    }

    async function handleProfileZipUpload(e) {
        const file = e.target.files[0];
        if (!file) return;

        state.busy = true;
        showLoading("Uploading & extracting profile ZIP...");
        logConsole(`[profile] uploading multipart ZIP archive: ${file.name}`, "info");

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await apiFetch("/api/profile/upload", {
                method: "POST",
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "ZIP upload extraction failed.");
            }
            const data = await res.json();

            logConsole(`[profile] Uploaded successfully. Extracted to: ${data.extracted_to}`, "success");
            alert("User profile ZIP uploaded and extracted successfully!");
            await loadProfileInfo();
        } catch (err) {
            alert("Upload failed: " + err.message);
            logConsole(`[error] upload failed: ${err.message}`, "error");
        } finally {
            state.busy = false;
            hideLoading();
            elements.profileZipUploader.value = "";
        }
    }

    async function runProfileRoutingSimulation() {
        const prompt = elements.profileSimPromptInput.value.trim();
        if (!prompt) {
            alert("Please enter a mock user prompt directive to test.");
            return;
        }

        elements.profileSimResults.innerHTML = `<span class="text-muted">Interrogating keyword router...</span>`;
        logConsole(`[profile] running context loading routing simulation for prompt`, "info");

        try {
            const res = await apiFetch("/api/profile/simulate_route", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: prompt })
            });

            if (!res.ok) throw new Error("Simulation endpoint failed");
            const data = await res.json();

            let resultsHtml = `<div style="font-weight: bold; margin-bottom: 10px; color: var(--accent-purple);">ROUTING DECISION SUMMARY</div>`;
            resultsHtml += `<div style="margin-bottom: 8px;"><strong>Context Size:</strong> <span class="text-cyan">${data.context_length_chars} characters</span></div>`;
            
            resultsHtml += `<div style="margin-bottom: 8px;"><strong>LOADED MODULES (${data.loaded_modules.length}):</strong></div>`;
            if (data.loaded_modules.length === 0) {
                resultsHtml += `<div class="text-muted" style="padding-left:10px;">- None (Trivial / Utility Prompt)</div>`;
            } else {
                data.loaded_modules.forEach(m => {
                    resultsHtml += `<div style="padding-left:10px; color: #fff;">ðŸ“„ ${m}</div>`;
                });
            }

            resultsHtml += `<div style="margin-top: 12px; margin-bottom: 8px;"><strong>MATCHED TRIGGERS:</strong></div>`;
            const matchedKeys = Object.keys(data.matched_keywords);
            if (matchedKeys.length === 0) {
                resultsHtml += `<div class="text-muted" style="padding-left:10px;">- No trigger keywords matched in prompt. (Loaded recommended default modules only)</div>`;
            } else {
                matchedKeys.forEach(cat => {
                    const words = data.matched_keywords[cat];
                    resultsHtml += `<div style="padding-left:10px;">`;
                    resultsHtml += `<strong class="text-cyan">${cat.toUpperCase()} Triggers matched:</strong> `;
                    resultsHtml += `<span style="background: rgba(168, 85, 247, 0.15); border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 4px; padding: 1px 5px; font-family: monospace;">`;
                    resultsHtml += `${words.join(", ")}`;
                    resultsHtml += `</span>`;
                    resultsHtml += `</div>`;
                });
            }

            elements.profileSimResults.innerHTML = resultsHtml;
            logConsole(`[profile] context loading simulation complete.`, "success");
        } catch (err) {
            elements.profileSimResults.innerHTML = `<span class="text-red">Simulation error: ${err.message}</span>`;
            logConsole(`[error] simulation failed: ${err.message}`, "error");
        }
    }

    // RUN THE FRONTEND CONTROLLER
    init();
});

