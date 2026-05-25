from __future__ import annotations

import json
import os
import sys
import re
import shutil
import threading
from datetime import datetime, timezone
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
from typing import Any, Callable
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from System_Services.envelope_service import EnvelopeService, PromptEnvelope
from System_Services.logging_service import LoggingService
from System_Services.orchestration_service import OrchestrationResponse, OrchestrationService
from System_Services.router_service import RouterService
from System_Services.connected_service_manager import ConnectedServiceManager

# -------------------------------------------------------------
# CYBERPUNK DARK THEME COLOR PALETTE (Codex & Antigravity Style)
# -------------------------------------------------------------
BG_COLOR = "#08090D"          # High-contrast deep dark blue-grey
PANEL_BG = "#121620"          # Elevate panel background
HEADER_BG = "#1A1F2C"         # Active header background
TEXT_COLOR = "#9EADBF"        # Clean cool gray for normal text
TEXT_LIGHT = "#F1F5F9"        # High-contrast white-blue for titles & highlighted text
ACCENT_CYAN = "#00FFCC"       # Bright neon cyan for routing, prompts, and success states
ACCENT_PURPLE = "#A855F7"     # Deep glowing violet for model, personas, and inspect mode
ACCENT_GOLD = "#F59E0B"       # Warm gold for warnings, pending status, and memory reviews
ACCENT_RED = "#EF4444"        # Cyberpunk neon red for failed tasks and error logs
BORDER_COLOR = "#222C3E"      # Panel border lines
SELECT_BG = "#2E3B52"         # Selection highlighting background

PERSONAS = {
    "Proto Jane": "proto_jane",
    "Serren": "serren",
    "Maelith": "maelith",
    "Vecht": "vecht",
    "Riven": "riven",
}

class ClientTask:
    def __init__(self, task_id: str, prompt: str, persona: str, model: str, task_type: str = "general_chat") -> None:
        self.task_id = task_id
        self.prompt = prompt
        self.persona = persona
        self.model = model
        self.task_type = task_type
        self.timestamp = datetime.now().strftime("%H:%M:%S")
        self.status = "PENDING"  # PENDING, ROUTING, EXECUTING, COMPLETED, FAILED
        self.response = ""
        self.route_details: dict[str, Any] = {}
        self.memory_candidates: list[dict[str, Any]] = []
        self.memories_used: list[dict[str, Any]] = []
        self.artifacts_created: list[str] = []
        self.error_message = ""

class VailaDesktopClient:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("VAILA // AI COMMAND SURFACE V3.0")
        self.root.geometry("1350x880")
        self.root.minsize(1024, 720)
        self.root.configure(bg=BG_COLOR)

        # Core Services
        self.logger = LoggingService(project_root=PROJECT_ROOT)
        self.envelope_service = EnvelopeService(project_root=PROJECT_ROOT)
        self.router = RouterService(project_root=PROJECT_ROOT)
        self.orchestrator = OrchestrationService(project_root=PROJECT_ROOT, logger=self.logger)
        self.service_manager = ConnectedServiceManager(project_root=PROJECT_ROOT)

        # Intercept Logger to stream events to bottom console in real-time
        self._setup_logger_hooks()

        # UI state variables
        self.persona_var = tk.StringVar(value="Proto Jane")
        self.status_var = tk.StringVar(value="STATUS: READY")
        self.route_var = tk.StringVar(value="ROUTE: IDLE")
        self.gateway_var = tk.StringVar(value="GATEWAY: UNCHECKED")
        
        self.busy = False
        self.tasks: list[ClientTask] = []
        self.selected_task: ClientTask | None = None
        self.task_counter = 0
        self.current_view = "chat"  # chat, memory, system, artifacts, council, files, n8n

        # Initialize directories
        (PROJECT_ROOT / "data" / "artifacts").mkdir(parents=True, exist_ok=True)
        (PROJECT_ROOT / "Sandbox" / "Imported_Documents").mkdir(parents=True, exist_ok=True)

        self._build_ui()
        self._refresh_sidebar_buttons()
        self.switch_view("chat")
        
        # Bind keyboard shortcuts
        self.root.bind("<Control-p>", self._toggle_command_palette)
        self.root.bind("<Control-P>", self._toggle_command_palette)

    def _setup_logger_hooks(self) -> None:
        old_log_session = self.logger.log_session_event
        old_log_error = self.logger.log_error
        old_log_router = self.logger.log_router_event

        def log_session_event_hook(event: dict[str, Any]) -> None:
            old_log_session(event)
            self._dispatch_system_log("session", event)

        def log_error_hook(event: dict[str, Any]) -> None:
            old_log_error(event)
            self._dispatch_system_log("error", event)

        def log_router_event_hook(event: dict[str, Any]) -> None:
            old_log_router(event)
            self._dispatch_system_log("router", event)

        self.logger.log_session_event = log_session_event_hook
        self.logger.log_error = log_error_hook
        self.logger.log_router_event = log_router_event_hook

    def _dispatch_system_log(self, category: str, event: dict[str, Any]) -> None:
        # Avoid thread safety issues by scheduling on the main Tkinter thread
        if hasattr(self, 'root'):
            self.root.after(0, self._process_system_log, category, event)

    def _process_system_log(self, category: str, event: dict[str, Any]) -> None:
        if not hasattr(self, 'event_console'):
            return

        stamp = datetime.now().strftime("%H:%M:%S")
        event_type = event.get("event_type", "EVENT")
        
        if category == "error":
            msg = f"[{stamp}] [ERROR] {event.get('error', 'Critical operational issue')}"
            color = ACCENT_RED
        elif category == "router":
            msg = f"[{stamp}] [ROUTER] {event_type} // Task: {event.get('route', {}).get('task_type', 'unknown')}"
            color = ACCENT_CYAN
        else:
            if event_type == "memory_candidate_detected":
                msg = f"[{stamp}] [MEMORY] Candidate captured! Queue populated."
                color = ACCENT_GOLD
                # Auto-refresh memory review queue if visible
                if self.current_view == "memory":
                    self.switch_view("memory")
            elif event_type == "desktop_interaction_complete":
                msg = f"[{stamp}] [SYSTEM] Pipeline interaction finalized."
                color = ACCENT_CYAN
            elif event_type == "artifact_created":
                msg = f"[{stamp}] [ARTIFACT] Generated: {event.get('filename')}"
                color = ACCENT_PURPLE
                if self.current_view == "artifacts":
                    self.switch_view("artifacts")
            else:
                msg = f"[{stamp}] [INFO] {event_type}"
                color = TEXT_COLOR

        self.event_console.configure(state=tk.NORMAL)
        self.event_console.insert(tk.END, msg + "\n", event_type)
        self.event_console.tag_config(event_type, foreground=color)
        self.event_console.see(tk.END)
        self.event_console.configure(state=tk.DISABLED)

    # -------------------------------------------------------------
    # LAYOUT AND INTERFACE ASSEMBLY
    # -------------------------------------------------------------
    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)  # Status Bar
        self.root.rowconfigure(1, weight=1)  # Core Workspace Panel
        self.root.rowconfigure(2, weight=0)  # Bottom Event Console

        # 1. Top Status Bar
        top_bar = tk.Frame(self.root, bg=PANEL_BG, height=45, bd=1, relief=tk.SOLID, highlightbackground=BORDER_COLOR, highlightthickness=1)
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        top_bar.pack_propagate(False)

        logo_lbl = tk.Label(top_bar, text="VAILA // OS V3.0", bg=PANEL_BG, fg=ACCENT_CYAN, font=("Consolas", 12, "bold"))
        logo_lbl.pack(side=tk.LEFT, padx=15)

        # Status displays
        status_lbl = tk.Label(top_bar, textvariable=self.status_var, bg=PANEL_BG, fg=TEXT_LIGHT, font=("Consolas", 9, "bold"))
        status_lbl.pack(side=tk.LEFT, padx=20)

        route_lbl = tk.Label(top_bar, textvariable=self.route_var, bg=PANEL_BG, fg=ACCENT_GOLD, font=("Consolas", 9))
        route_lbl.pack(side=tk.LEFT, padx=20)

        gateway_lbl = tk.Label(top_bar, textvariable=self.gateway_var, bg=PANEL_BG, fg=ACCENT_PURPLE, font=("Consolas", 9))
        gateway_lbl.pack(side=tk.LEFT, padx=20)

        # Actions & Persona select
        persona_frame = tk.Frame(top_bar, bg=PANEL_BG)
        persona_frame.pack(side=tk.RIGHT, padx=10)
        
        lbl = tk.Label(persona_frame, text="Active Lens:", bg=PANEL_BG, fg=TEXT_COLOR, font=("Segoe UI", 9))
        lbl.pack(side=tk.LEFT, padx=5)
        
        persona_menu = ttk.OptionMenu(persona_frame, self.persona_var, self.persona_var.get(), *PERSONAS, command=self._on_persona_changed)
        persona_menu.pack(side=tk.LEFT, padx=5)

        check_btn = tk.Button(top_bar, text="Ping Gateway", bg=BG_COLOR, fg=ACCENT_CYAN, activebackground=PANEL_BG, activeforeground=ACCENT_CYAN, bd=1, relief=tk.SOLID, font=("Segoe UI", 9), command=self.check_model, padx=10)
        check_btn.pack(side=tk.RIGHT, padx=10)

        palette_btn = tk.Button(top_bar, text="Palette (Ctrl+P)", bg=BG_COLOR, fg=TEXT_LIGHT, activebackground=PANEL_BG, activeforeground=TEXT_LIGHT, bd=1, relief=tk.SOLID, font=("Segoe UI", 9), command=lambda: self._toggle_command_palette(None), padx=10)
        palette_btn.pack(side=tk.RIGHT, padx=10)

        # 2. Main Area (Sidebar + Center Viewport + Inspector)
        main_workspace = tk.Frame(self.root, bg=BG_COLOR)
        main_workspace.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        main_workspace.rowconfigure(0, weight=1)
        main_workspace.columnconfigure(0, weight=0)  # Left Sidebar
        main_workspace.columnconfigure(1, weight=1)  # Center Viewport
        main_workspace.columnconfigure(2, weight=0)  # Right Inspector

        # Sidebar Assembly
        sidebar_outer, sidebar_content = self._create_panel(main_workspace, "Navigation", BORDER_COLOR)
        sidebar_outer.grid(row=0, column=0, sticky="ns", padx=(0, 5))
        sidebar_outer.configure(width=190)
        sidebar_outer.grid_propagate(False)

        self.sidebar_btns: dict[str, tk.Button] = {}
        views_metadata = [
            ("chat", "Task Chat console"),
            ("memory", "Memory review queue"),
            ("artifacts", "Artifact vault"),
            ("system", "System health map"),
            ("council", "Council reasoning"),
            ("files", "Workspace vault"),
            ("n8n", "n8n Workflows"),
        ]
        
        for view_id, label in views_metadata:
            btn = tk.Button(
                sidebar_content,
                text=label.upper(),
                bg=BG_COLOR,
                fg=TEXT_COLOR,
                activebackground=PANEL_BG,
                activeforeground=ACCENT_CYAN,
                bd=0,
                font=("Consolas", 9, "bold"),
                anchor="w",
                padx=12,
                pady=10,
                command=lambda vid=view_id: self._on_sidebar_click(vid)
            )
            btn.pack(fill=tk.X, pady=2)
            self.sidebar_btns[view_id] = btn

        # Center Viewport Assembly
        self.center_viewport = tk.Frame(main_workspace, bg=BG_COLOR)
        self.center_viewport.grid(row=0, column=1, sticky="nsew", padx=5)

        # Right Inspector Assembly
        self.inspector_outer, self.inspector_content = self._create_panel(main_workspace, "Inspector Panel", ACCENT_PURPLE)
        self.inspector_outer.grid(row=0, column=2, sticky="ns", padx=(5, 0))
        self.inspector_outer.configure(width=340)
        self.inspector_outer.grid_propagate(False)

        self._build_inspector_ui()

        # 3. Bottom Event Console
        console_outer, console_content = self._create_panel(self.root, "Live System Event Log", ACCENT_GOLD)
        console_outer.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        console_outer.configure(height=140)
        console_outer.grid_propagate(False)

        self.event_console = tk.Text(
            console_content,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            relief=tk.FLAT,
            font=("Consolas", 9),
            insertbackground=TEXT_LIGHT,
            state=tk.DISABLED
        )
        self.event_console.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(console_content, self.event_console, side=tk.RIGHT)

        # 4. Floating Command Palette Overlay (initially hidden)
        self.palette_frame = tk.Frame(self.root, bg=PANEL_BG, bd=1, relief=tk.SOLID, highlightbackground=ACCENT_CYAN, highlightthickness=1)
        self.palette_frame.place(relx=0.5, rely=0.08, anchor="n", width=550, height=50)
        self.palette_frame.lower()  # Hide initially
        
        self.palette_lbl = tk.Label(self.palette_frame, text=">", bg=PANEL_BG, fg=ACCENT_CYAN, font=("Consolas", 12, "bold"))
        self.palette_lbl.pack(side=tk.LEFT, padx=(10, 5))
        
        self.palette_entry = tk.Entry(
            self.palette_frame,
            bg=BG_COLOR,
            fg=TEXT_LIGHT,
            insertbackground=TEXT_LIGHT,
            relief=tk.FLAT,
            font=("Consolas", 11)
        )
        self.palette_entry.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=5, pady=8)
        self.palette_entry.bind("<Return>", self._execute_palette_command)
        self.palette_entry.bind("<Escape>", lambda e: self._hide_command_palette())

    def _create_panel(self, parent: tk.Widget, title: str, accent_color: str = BORDER_COLOR) -> tuple[tk.Frame, tk.Frame]:
        outer = tk.Frame(parent, bg=BG_COLOR, bd=1, relief=tk.SOLID, highlightbackground=BORDER_COLOR, highlightthickness=1)
        
        title_bar = tk.Frame(outer, bg=PANEL_BG, height=28)
        title_bar.pack(fill=tk.X, side=tk.TOP)
        title_bar.pack_propagate(False)
        
        title_lbl = tk.Label(title_bar, text=f"[ {title.upper()} ]", bg=PANEL_BG, fg=accent_color, font=("Consolas", 9, "bold"), anchor="w", padx=10)
        title_lbl.pack(fill=tk.BOTH, expand=True)
        
        content = tk.Frame(outer, bg=BG_COLOR)
        content.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        return outer, content

    def _add_scrollbar(self, parent: tk.Widget, widget: tk.Text | tk.Listbox, side: str = tk.RIGHT) -> None:
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=widget.yview)
        scrollbar.pack(side=side, fill=tk.Y)
        widget.configure(yscrollcommand=scrollbar.set)

    def _on_persona_changed(self, choice: str) -> None:
        p_id = PERSONAS.get(choice, "proto_jane")
        self.route_var.set(f"ROUTE: FORCE {p_id.upper()}")
        self._log_event(f"System Lens configured to: {choice}")

    def _on_sidebar_click(self, view_name: str) -> None:
        if self.busy and view_name in {"council", "files", "n8n"}:
            messagebox.showwarning("System Busy", "The orchestration service is currently active. Please await task finalization.")
            return
        self.current_view = view_name
        self._refresh_sidebar_buttons()
        self.switch_view(view_name)

    def _refresh_sidebar_buttons(self) -> None:
        for view_id, btn in self.sidebar_btns.items():
            if view_id == self.current_view:
                btn.configure(bg=ACCENT_CYAN, fg=BG_COLOR, activebackground=ACCENT_CYAN, activeforeground=BG_COLOR)
            else:
                btn.configure(bg=BG_COLOR, fg=TEXT_COLOR, activebackground=PANEL_BG, activeforeground=ACCENT_CYAN)

    def switch_view(self, view_name: str) -> None:
        # Clear Center viewport children
        for child in self.center_viewport.winfo_children():
            child.destroy()

        if view_name == "chat":
            self._render_chat_view(self.center_viewport)
        elif view_name == "memory":
            self._render_memory_view(self.center_viewport)
        elif view_name == "system":
            self._render_system_view(self.center_viewport)
        elif view_name == "artifacts":
            self._render_artifacts_view(self.center_viewport)
        elif view_name == "council":
            self._render_council_view(self.center_viewport)
        elif view_name == "files":
            self._render_files_view(self.center_viewport)
        elif view_name == "n8n":
            self._render_n8n_view(self.center_viewport)

    # -------------------------------------------------------------
    # PHASE 1 & 2: TASK CHAT WORKSPACE
    # -------------------------------------------------------------
    def _render_chat_view(self, parent: tk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=0)
        parent.columnconfigure(0, weight=1)

        chat_outer, chat_content = self._create_panel(parent, "Task & Prompt Command Console", ACCENT_CYAN)
        chat_outer.grid(row=0, column=0, sticky="nsew", pady=(0, 5))

        # Main scrollable chat log
        self.chat_txt = tk.Text(
            chat_content,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            relief=tk.FLAT,
            font=("Consolas", 10),
            insertbackground=TEXT_LIGHT,
            selectbackground=SELECT_BG,
            state=tk.DISABLED
        )
        self.chat_txt.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(chat_content, self.chat_txt, side=tk.RIGHT)

        # Style tags
        self.chat_txt.tag_config("task_header", foreground=ACCENT_PURPLE, font=("Consolas", 10, "bold"))
        self.chat_txt.tag_config("prompt_tag", foreground=ACCENT_CYAN, font=("Consolas", 10, "bold"))
        self.chat_txt.tag_config("prompt_text", foreground=TEXT_LIGHT, font=("Consolas", 10))
        self.chat_txt.tag_config("response_text", foreground=TEXT_COLOR, font=("Consolas", 10))
        self.chat_txt.tag_config("system_status", foreground=ACCENT_GOLD, font=("Consolas", 10, "italic"))
        self.chat_txt.tag_config("metadata_status", foreground=ACCENT_GOLD, font=("Consolas", 10, "bold"))
        self.chat_txt.tag_config("error_status", foreground=ACCENT_RED, font=("Consolas", 10, "bold"))

        # Re-render existing tasks
        self._reload_chat_log()

        # Input Frame
        input_outer, input_content = self._create_panel(parent, "Operator Entry Pane", BORDER_COLOR)
        input_outer.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        input_outer.configure(height=120)
        input_outer.grid_propagate(False)

        self.prompt_entry = tk.Text(
            input_content,
            bg=BG_COLOR,
            fg=TEXT_LIGHT,
            relief=tk.FLAT,
            font=("Consolas", 10),
            insertbackground=TEXT_LIGHT,
            selectbackground=SELECT_BG,
            height=3
        )
        self.prompt_entry.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 10))
        self.prompt_entry.bind("<Control-Return>", lambda e: self.send_task())
        self.prompt_entry.focus_set()

        btn_frame = tk.Frame(input_content, bg=BG_COLOR)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.send_btn = tk.Button(
            btn_frame,
            text="EXECUTE TASK",
            bg=PANEL_BG,
            fg=ACCENT_CYAN,
            activebackground=ACCENT_CYAN,
            activeforeground=BG_COLOR,
            bd=1,
            relief=tk.SOLID,
            font=("Consolas", 9, "bold"),
            width=15,
            command=self.send_task
        )
        self.send_btn.pack(fill=tk.X, pady=2, expand=True)

        clear_btn = tk.Button(
            btn_frame,
            text="CLEAR CHAT",
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            activebackground=PANEL_BG,
            activeforeground=ACCENT_CYAN,
            bd=1,
            relief=tk.SOLID,
            font=("Consolas", 9, "bold"),
            width=15,
            command=self.clear_chat
        )
        clear_btn.pack(fill=tk.X, pady=2, expand=True)

    def _reload_chat_log(self) -> None:
        self.chat_txt.configure(state=tk.NORMAL)
        self.chat_txt.delete("1.0", tk.END)
        self.chat_txt.configure(state=tk.DISABLED)
        
        for t in self.tasks:
            self._append_task_to_chat(t)

    def _append_task_to_chat(self, task: ClientTask) -> None:
        self.chat_txt.configure(state=tk.NORMAL)
        
        header = f"\n┌── [ {task.task_id} ] ─────────────────────────────────────────────\n"
        header += f"│ TYPE: {task.task_type.upper()}  •  PERSONA: {task.persona.upper()}  •  MODEL: {task.model}\n"
        header += f"│ STATUS: {task.status}  •  TIME: {task.timestamp}\n"
        header += "└─────────────────────────────────────────────────────────────\n"
        
        self.chat_txt.insert(tk.END, header, "task_header")
        self.chat_txt.insert(tk.END, "malik@vaila:~$ ", "prompt_tag")
        self.chat_txt.insert(tk.END, task.prompt + "\n\n", "prompt_text")
        
        if task.status in {"PENDING", "ROUTING", "EXECUTING"}:
            self.chat_txt.insert(tk.END, f"[SYSTEM] Routing and executing autonomous task pipeline...\n", "system_status")
        elif task.status == "FAILED":
            self.chat_txt.insert(tk.END, f"[FATAL] Connection or gateway failure:\n{task.error_message}\n", "error_status")
        elif task.status == "COMPLETED":
            self.chat_txt.insert(tk.END, task.response + "\n", "response_text")
            if task.artifacts_created:
                self.chat_txt.insert(tk.END, f"\n[PERSISTENCE] Artifact saved: {', '.join(task.artifacts_created)}\n", "metadata_status")
            if task.memory_candidates:
                self.chat_txt.insert(tk.END, f"[MEMORY] Saved {len(task.memory_candidates)} candidates to Memory Vault.\n", "metadata_status")

        self.chat_txt.see(tk.END)
        self.chat_txt.configure(state=tk.DISABLED)

    def send_task(self, custom_prompt: str | None = None) -> None:
        if self.busy:
            messagebox.showwarning("Pipeline Active", "The Command Surface is executing a previous directive.")
            return

        raw_text = custom_prompt if custom_prompt else self.prompt_entry.get("1.0", tk.END).strip()
        if not raw_text:
            self.status_var.set("STATUS: EMPTY DIRECTIVE")
            return

        if not custom_prompt:
            self.prompt_entry.delete("1.0", tk.END)

        self.task_counter += 1
        t_id = f"TSK-{self.task_counter:03d}"
        
        task = ClientTask(
            task_id=t_id,
            prompt=raw_text,
            persona=self.persona_var.get(),
            model="local-model"
        )
        self.tasks.append(task)
        self.selected_task = task
        self.busy = True

        self._set_ui_busy(True, f"ORCHESTRATING {t_id}...")
        
        if self.current_view == "chat":
            self._append_task_to_chat(task)
        self._refresh_inspector()

        # Execute in background thread
        threading.Thread(target=self._task_worker, args=(task,), daemon=True).start()

    def _task_worker(self, task: ClientTask) -> None:
        self._log_event(f"Task {task.task_id} initiated.")
        try:
            task.status = "ROUTING"
            self._on_task_progress(task)

            # Create Prompt Envelope
            metadata = {
                "interface": "desktop_client",
                "selected_persona": PERSONAS.get(task.persona, "proto_jane"),
                "prompt_interpreter_enabled": False,
                "session_id": "desktop_session",
            }
            envelope = self.envelope_service.create(
                user_text=task.prompt,
                source="desktop_client",
                metadata=metadata,
            )

            # Route
            route = self.router.route(envelope)
            task.route_details = route
            task.task_type = route.get("task_type", "general_chat")
            
            task.status = "EXECUTING"
            self._on_task_progress(task)

            # Handle with Orchestrator
            result = self.orchestrator.handle(envelope=envelope, route=route)
            
            task.response = result.visible_text
            task.status = "COMPLETED"

            # Parse diagnostic stats
            llm_info = result.meta.get("llm", {})
            model = llm_info.get("model", "auto")
            error = llm_info.get("error", "")
            
            self.gateway_var.set(f"GATEWAY: {model.upper()}")
            
            # Check for memory candidates generated during this turn
            # We delay slightly to allow background task completion
            import time
            time.sleep(0.5)
            task.memory_candidates = self._find_candidates_by_request_id(envelope.request_id)
            
            # Add to artifacts system if completed successfully
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"task_{task.task_id}_{timestamp_str}.md"
            art_content = (
                f"# VAILA OS V3 - AUTO REPORT: {task.task_id}\n\n"
                f"- **Prompt**: {task.prompt}\n"
                f"- **Persona**: {task.persona}\n"
                f"- **Model**: {model}\n"
                f"- **Timestamp**: {task.timestamp}\n\n"
                f"## Analysis Response\n\n{task.response}\n\n"
                f"## Routing Log\n"
                f"```json\n{json.dumps(route, indent=2)}\n```\n"
            )
            self._save_artifact(filename, art_content, "route_reports")
            task.artifacts_created.append(filename)

            self._log_event(f"Task {task.task_id} completed successfully.")
        except Exception as exc:
            task.status = "FAILED"
            task.error_message = str(exc)
            self.logger.log_error({
                "event_type": "desktop_client_task_failed",
                "task_id": task.task_id,
                "error": str(exc)
            })
            self._log_event(f"Task {task.task_id} aborted: {exc}")
        finally:
            self.busy = False
            self._on_task_finished(task)

    def _find_candidates_by_request_id(self, request_id: str) -> list[dict[str, Any]]:
        cands = self._load_memory_candidates()
        matches = []
        for c in cands:
            payload = c.get("payload", {})
            if payload.get("request_id") == request_id:
                matches.append(c)
        return matches

    def _on_task_progress(self, task: ClientTask) -> None:
        self.root.after(0, self._process_task_progress, task)

    def _process_task_progress(self, task: ClientTask) -> None:
        self.status_var.set(f"STATUS: {task.status}")
        self.route_var.set(f"ROUTE: {task.task_type.upper()}")
        if self.current_view == "chat":
            self._reload_chat_log()
        self._refresh_inspector()

    def _on_task_finished(self, task: ClientTask) -> None:
        self.root.after(0, self._process_task_finished, task)

    def _process_task_finished(self, task: ClientTask) -> None:
        self._set_ui_busy(False, "STATUS: COMPLETE" if task.status == "COMPLETED" else "STATUS: FAILED")
        if self.current_view == "chat":
            self._reload_chat_log()
        self._refresh_inspector()

    def clear_chat(self) -> None:
        self.orchestrator.clear_history("desktop_session")
        self.tasks.clear()
        self.selected_task = None
        self.status_var.set("STATUS: READY")
        self.route_var.set("ROUTE: IDLE")
        if self.current_view == "chat":
            self._reload_chat_log()
        self._refresh_inspector()

    # -------------------------------------------------------------
    # PHASE 3: ROUTE & TASK INSPECTOR (RIGHT PANEL)
    # -------------------------------------------------------------
    def _build_inspector_ui(self) -> None:
        self.inspector_content.columnconfigure(0, weight=1)
        self.inspector_content.rowconfigure(0, weight=1)

        self.inspect_txt = tk.Text(
            self.inspector_content,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            relief=tk.FLAT,
            font=("Consolas", 9),
            insertbackground=TEXT_LIGHT,
            selectbackground=SELECT_BG,
            state=tk.DISABLED
        )
        self.inspect_txt.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(self.inspector_content, self.inspect_txt, side=tk.RIGHT)

        # Inspector Tags
        self.inspect_txt.tag_config("section", foreground=ACCENT_PURPLE, font=("Consolas", 10, "bold"))
        self.inspect_txt.tag_config("lbl", foreground=ACCENT_CYAN, font=("Consolas", 9, "bold"))
        self.inspect_txt.tag_config("val", foreground=TEXT_LIGHT, font=("Consolas", 9))
        self.inspect_txt.tag_config("alert", foreground=ACCENT_GOLD, font=("Consolas", 9, "bold"))

        self._refresh_inspector()

    def _refresh_inspector(self) -> None:
        self.inspect_txt.configure(state=tk.NORMAL)
        self.inspect_txt.delete("1.0", tk.END)

        task = self.selected_task
        if not task:
            self.inspect_txt.insert(tk.END, "=== ORCHESTRATION PIPELINE ===\n\nNo task active or selected.\nSubmit a directive to see real-time routing analysis.", "val")
            self.inspect_txt.configure(state=tk.DISABLED)
            return

        self.inspect_txt.insert(tk.END, f"=== INSPECTING: {task.task_id} ===\n\n", "section")
        
        self.inspect_txt.insert(tk.END, "PIPELINE STATE:\n", "section")
        self.inspect_txt.insert(tk.END, "  Status: ", "lbl")
        self.inspect_txt.insert(tk.END, f"{task.status}\n", "alert" if task.status != "COMPLETED" else "val")
        self.inspect_txt.insert(tk.END, "  Timestamp: ", "lbl")
        self.inspect_txt.insert(tk.END, f"{task.timestamp}\n\n", "val")

        self.inspect_txt.insert(tk.END, "ROUTING ENGINE:\n", "section")
        route = task.route_details
        self.inspect_txt.insert(tk.END, "  Detected Task: ", "lbl")
        self.inspect_txt.insert(tk.END, f"{task.task_type}\n", "val")
        self.inspect_txt.insert(tk.END, "  Target Lens: ", "lbl")
        self.inspect_txt.insert(tk.END, f"{route.get('persona', task.persona)}\n", "val")
        self.inspect_txt.insert(tk.END, "  Confidence: ", "lbl")
        self.inspect_txt.insert(tk.END, f"{route.get('confidence', 'N/A')}\n", "val")
        self.inspect_txt.insert(tk.END, "  Interpreter Audited: ", "lbl")
        self.inspect_txt.insert(tk.END, f"{'TRUE' if route.get('needs_prompt_interpreter') else 'FALSE'}\n\n", "val")

        self.inspect_txt.insert(tk.END, "GATEWAY CONFIG:\n", "section")
        self.inspect_txt.insert(tk.END, "  Selected Model: ", "lbl")
        self.inspect_txt.insert(tk.END, f"{task.model}\n", "val")
        self.inspect_txt.insert(tk.END, "  Resolved Server: ", "lbl")
        self.inspect_txt.insert(tk.END, f"{self.orchestrator.llm.base_url}\n\n", "val")

        self.inspect_txt.insert(tk.END, "MEMORY AUDIT:\n", "section")
        # Load local memory count
        durables = self._load_durable_memories()
        self.inspect_txt.insert(tk.END, f"  Durable memories injected: {len(durables)}\n", "val")
        self.inspect_txt.insert(tk.END, "  Auto-captured candidates: ", "lbl")
        self.inspect_txt.insert(tk.END, f"{len(task.memory_candidates)}\n\n", "val")

        self.inspect_txt.insert(tk.END, "WORKSPACE DELIVERABLES:\n", "section")
        for f in task.artifacts_created:
            self.inspect_txt.insert(tk.END, f"  📁 {f}\n", "val")
        if not task.artifacts_created:
            self.inspect_txt.insert(tk.END, "  No artifacts captured.\n", "val")

        self.inspect_txt.configure(state=tk.DISABLED)

    # -------------------------------------------------------------
    # PHASE 6: MEMORY CENTER VIEW
    # -------------------------------------------------------------
    def _render_memory_view(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # Left Column: Candidate List
        list_outer, list_content = self._create_panel(parent, "Memory Candidate Queue", ACCENT_GOLD)
        list_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.mem_listbox = tk.Listbox(
            list_content,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            selectbackground=SELECT_BG,
            selectforeground=ACCENT_CYAN,
            bd=0,
            font=("Consolas", 9),
            highlightthickness=0
        )
        self.mem_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(list_content, self.mem_listbox, side=tk.RIGHT)
        self.mem_listbox.bind("<<ListboxSelect>>", self._on_memory_candidate_selected)

        # Right Column: Editor / Form
        form_outer, form_content = self._create_panel(parent, "Candidate Analysis & Review", BORDER_COLOR)
        form_outer.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        form_content.columnconfigure(0, weight=0)
        form_content.columnconfigure(1, weight=1)

        # ID
        tk.Label(form_content, text="CANDIDATE ID:", bg=BG_COLOR, fg=ACCENT_CYAN, font=("Consolas", 9, "bold")).grid(row=0, column=0, sticky="w", pady=5)
        self.mem_id_lbl = tk.Label(form_content, text="NONE", bg=BG_COLOR, fg=TEXT_LIGHT, font=("Consolas", 9))
        self.mem_id_lbl.grid(row=0, column=1, sticky="w", pady=5)

        # Text
        tk.Label(form_content, text="MEMORY TEXT:", bg=BG_COLOR, fg=ACCENT_CYAN, font=("Consolas", 9, "bold")).grid(row=1, column=0, sticky="nw", pady=5)
        self.mem_text_entry = tk.Text(form_content, bg=PANEL_BG, fg=TEXT_LIGHT, insertbackground=TEXT_LIGHT, relief=tk.SOLID, bd=1, highlightthickness=0, font=("Segoe UI", 9), height=10)
        self.mem_text_entry.grid(row=1, column=1, sticky="nsew", pady=5)

        # Category
        tk.Label(form_content, text="CATEGORY:", bg=BG_COLOR, fg=ACCENT_CYAN, font=("Consolas", 9, "bold")).grid(row=2, column=0, sticky="w", pady=5)
        self.mem_cat_var = tk.StringVar(value="general")
        categories = ["general", "user_preference", "system_rule", "project_architecture"]
        self.mem_cat_menu = ttk.OptionMenu(form_content, self.mem_cat_var, self.mem_cat_var.get(), *categories)
        self.mem_cat_menu.grid(row=2, column=1, sticky="w", pady=5)

        # Project-Only
        self.mem_proj_var = tk.BooleanVar(value=True)
        self.mem_proj_check = tk.Checkbutton(
            form_content,
            text="PROJECT-ONLY RETRIEVAL ACTIVE",
            variable=self.mem_proj_var,
            bg=BG_COLOR,
            fg=TEXT_LIGHT,
            selectcolor=BG_COLOR,
            activebackground=BG_COLOR,
            activeforeground=TEXT_LIGHT,
            font=("Consolas", 9)
        )
        self.mem_proj_check.grid(row=3, column=1, sticky="w", pady=10)

        # Controls
        ctrl_frame = tk.Frame(form_content, bg=BG_COLOR)
        ctrl_frame.grid(row=4, column=1, sticky="ew", pady=15)

        approve_btn = tk.Button(ctrl_frame, text="APPROVE MEMORY", bg=PANEL_BG, fg=ACCENT_CYAN, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, width=16, command=self._approve_selected_memory)
        approve_btn.pack(side=tk.LEFT, padx=5)

        reject_btn = tk.Button(ctrl_frame, text="REJECT MEMORY", bg=PANEL_BG, fg=ACCENT_RED, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, width=16, command=self._reject_selected_memory)
        reject_btn.pack(side=tk.LEFT, padx=5)

        self._load_candidates_into_listbox()

    def _load_candidates_into_listbox(self) -> None:
        self.mem_listbox.delete(0, tk.END)
        self.active_candidates = self._load_memory_candidates()
        
        # Only show candidates needing review
        self.filtered_candidates = [c for c in self.active_candidates if c.get("status") in {"needs_user_review", "candidate_logged"}]
        
        for cand in self.filtered_candidates:
            payload = cand.get("payload", {})
            text = payload.get("text", "Empty Memory Fragment")
            snippet = text[:40] + "..." if len(text) > 40 else text
            self.mem_listbox.insert(tk.END, f"[{cand.get('candidate_id')[:8]}] {snippet}")

    def _on_memory_candidate_selected(self, event: Any) -> None:
        selections = self.mem_listbox.curselection()
        if not selections:
            return
            
        index = selections[0]
        cand = self.filtered_candidates[index]
        payload = cand.get("payload", {})
        
        self.mem_id_lbl.configure(text=cand.get("candidate_id", "UNKNOWN"))
        self.mem_text_entry.delete("1.0", tk.END)
        self.mem_text_entry.insert(tk.END, payload.get("text", ""))
        self.mem_cat_var.set(payload.get("route", {}).get("task_type", "general"))
        self.mem_proj_var.set(True)

    def _approve_selected_memory(self) -> None:
        c_id = self.mem_id_lbl.cget("text")
        if c_id == "NONE":
            messagebox.showwarning("Warning", "No memory candidate selected.")
            return

        edited_text = self.mem_text_entry.get("1.0", tk.END).strip()
        if not edited_text:
            messagebox.showwarning("Warning", "Memory text cannot be empty.")
            return

        # Add to durable memories store
        record = {
            "memory_id": f"dur_{uuid4().hex}",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "text": edited_text,
            "category": self.mem_cat_var.get(),
            "project_only": self.mem_proj_var.get(),
            "original_candidate": c_id
        }
        self._write_durable_memory(record)

        # Update candidate status in openbrain candidate queue
        self._update_candidate_status(c_id, "approved")
        self._log_event(f"Approved memory {c_id[:8]} into durable store.")
        messagebox.showinfo("Success", "Memory candidate promoted to durable store!")
        
        # Refresh UI
        self._load_candidates_into_listbox()
        self._clear_memory_form()
        self._refresh_inspector()

    def _reject_selected_memory(self) -> None:
        c_id = self.mem_id_lbl.cget("text")
        if c_id == "NONE":
            messagebox.showwarning("Warning", "No memory candidate selected.")
            return

        self._update_candidate_status(c_id, "rejected")
        self._log_event(f"Rejected memory candidate: {c_id[:8]}")
        messagebox.showinfo("Rejected", "Memory candidate deleted from active queue.")
        
        # Refresh UI
        self._load_candidates_into_listbox()
        self._clear_memory_form()

    def _clear_memory_form(self) -> None:
        self.mem_id_lbl.configure(text="NONE")
        self.mem_text_entry.delete("1.0", tk.END)
        self.mem_cat_var.set("general")
        self.mem_proj_var.set(True)

    def _load_memory_candidates(self) -> list[dict[str, Any]]:
        candidates_file = PROJECT_ROOT / "data" / "openbrain_memory_candidates.jsonl"
        if not candidates_file.exists():
            return []
        
        candidates = []
        try:
            lines = candidates_file.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        candidates.append(item)
                except json.JSONDecodeError:
                    continue
        except Exception as exc:
            self.logger.log_error({"event_type": "gui_load_candidates_failed", "error": str(exc)})
        return candidates

    def _update_candidate_status(self, candidate_id: str, new_status: str) -> None:
        candidates_file = PROJECT_ROOT / "data" / "openbrain_memory_candidates.jsonl"
        if not candidates_file.exists():
            return
        
        updated_records = []
        try:
            lines = candidates_file.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if record.get("candidate_id") == candidate_id:
                        record["status"] = new_status
                    updated_records.append(record)
                except json.JSONDecodeError:
                    continue
            
            with candidates_file.open("w", encoding="utf-8") as f:
                for r in updated_records:
                    f.write(json.dumps(r) + "\n")
        except Exception as exc:
            self.logger.log_error({"event_type": "gui_update_candidate_failed", "error": str(exc)})

    def _write_durable_memory(self, record: dict[str, Any]) -> None:
        durable_file = PROJECT_ROOT / "data" / "openbrain_durable_memories.jsonl"
        try:
            with durable_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as exc:
            self.logger.log_error({"event_type": "gui_write_durable_failed", "error": str(exc)})

    def _load_durable_memories(self) -> list[dict[str, Any]]:
        durable_file = PROJECT_ROOT / "data" / "openbrain_durable_memories.jsonl"
        if not durable_file.exists():
            return []
        
        memories = []
        try:
            for line in durable_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        memories.append(item)
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        return memories

    # -------------------------------------------------------------
    # PHASE 7: SYSTEM SELF-PERCEPTION MAP VIEW
    # -------------------------------------------------------------
    def _render_system_view(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # Left Column: Service Health nodes
        health_outer, health_content = self._create_panel(parent, "Core Service Health Registry", ACCENT_CYAN)
        health_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.health_txt = tk.Text(health_content, bg=BG_COLOR, fg=TEXT_COLOR, relief=tk.FLAT, font=("Consolas", 10), state=tk.DISABLED)
        self.health_txt.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(health_content, self.health_txt, side=tk.RIGHT)

        self.health_txt.tag_config("online", foreground=ACCENT_CYAN, font=("Consolas", 10, "bold"))
        self.health_txt.tag_config("offline", foreground=ACCENT_RED, font=("Consolas", 10, "bold"))
        self.health_txt.tag_config("header", foreground=ACCENT_PURPLE, font=("Consolas", 10, "bold"))

        # Right Column: Files Scanner & Map
        scan_outer, scan_content = self._create_panel(parent, "Project Health Scanner & Missing Files", BORDER_COLOR)
        scan_outer.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.scan_txt = tk.Text(scan_content, bg=BG_COLOR, fg=TEXT_COLOR, relief=tk.FLAT, font=("Consolas", 9), state=tk.DISABLED)
        self.scan_txt.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(scan_content, self.scan_txt, side=tk.RIGHT)

        self.scan_txt.tag_config("missing", foreground=ACCENT_RED, font=("Consolas", 9, "bold"))
        self.scan_txt.tag_config("ok", foreground=ACCENT_CYAN, font=("Consolas", 9, "bold"))

        # Trigger background checks
        self._refresh_system_map()

    def _refresh_system_map(self) -> None:
        self._log_event("Performing system integrity assessment scan...")
        self.health_txt.configure(state=tk.NORMAL)
        self.health_txt.delete("1.0", tk.END)
        self.health_txt.insert(tk.END, "Pinging network registry and health checks...\n\n", "header")
        self.health_txt.configure(state=tk.DISABLED)

        self.scan_txt.configure(state=tk.NORMAL)
        self.scan_txt.delete("1.0", tk.END)
        self.scan_txt.insert(tk.END, "Parsing project directories recursive structures...\n\n")
        self.scan_txt.configure(state=tk.DISABLED)

        # Multi-thread checks to avoid GUI freeze
        threading.Thread(target=self._system_map_worker, daemon=True).start()

    def _system_map_worker(self) -> None:
        # Service diagnostics
        diagnostics = self.orchestrator.llm.diagnostics()
        lm_studio_online = diagnostics.get("server_reachable", False)
        
        # Check OpenBrain Connectivity
        ob_online = self.orchestrator.memory.openbrain.is_configured()
        
        # Check n8n Connectivity
        n8n_online = False
        if self.orchestrator.n8n.enabled:
            try:
                n8n_online = self.orchestrator.n8n.list_workflows().get("ok", False)
            except Exception:
                pass

        # Check TTS engine stub
        tts_online = False
        try:
            import pyttsx3
            tts_online = True
        except ImportError:
            pass

        # Parse connected registries
        registries = self.service_manager.service_statuses()

        # Scanner
        file_count = 0
        total_size = 0
        directory_lines = []
        
        # Expected files check
        expected_files = {
            ".env": PROJECT_ROOT / ".env",
            "requirements.txt": PROJECT_ROOT / "requirements.txt",
            "Core_System_Files/desktop_client.py": PROJECT_ROOT / "Core_System_Files" / "desktop_client.py",
            "System_Services/openbrain_service.py": PROJECT_ROOT / "System_Services" / "openbrain_service.py",
            "Persona_Files/Proto_Jane/identity.md": PROJECT_ROOT / "Persona_Files" / "Proto_Jane" / "identity.md",
            "Persona_Files/Vecht/identity.md": PROJECT_ROOT / "Persona_Files" / "Vecht" / "identity.md",
        }
        
        try:
            # Walk and record files
            for p in PROJECT_ROOT.glob("*"):
                if p.name.startswith(".") or p.name == "__pycache__":
                    continue
                if p.is_dir():
                    directory_lines.append(f" 📂 {p.name}/")
                    children = list(p.glob("*"))
                    for c in children[:4]:
                        if c.name.startswith(".") or c.name == "__pycache__":
                            continue
                        suffix = "/" if c.is_dir() else ""
                        directory_lines.append(f"    📄 {c.name}{suffix}")
                    if len(children) > 4:
                        directory_lines.append(f"    ... and {len(children)-4} more files")
                else:
                    directory_lines.append(f" 📄 {p.name} ({p.stat().st_size/1024:.1f} KB)")

            # Total files count
            for p in PROJECT_ROOT.rglob("*"):
                if p.is_file() and not p.name.startswith(".") and "__pycache__" not in str(p):
                    file_count += 1
                    total_size += p.stat().st_size
        except Exception as exc:
            directory_lines.append(f"[SCAN FAILURE] {exc}")

        # Update GUI on main thread
        self.root.after(0, self._render_health_data, lm_studio_online, ob_online, tts_online, n8n_online, registries, file_count, total_size, directory_lines, expected_files)

    def _render_health_data(self, lm_studio: bool, ob: bool, tts: bool, n8n: bool, registries: dict, file_count: int, size: float, dir_lines: list, expected: dict) -> None:
        self.health_txt.configure(state=tk.NORMAL)
        self.health_txt.delete("1.0", tk.END)

        self.health_txt.insert(tk.END, "=== SERVICE HEALTH NODES ===\n\n", "header")
        
        # LM Studio
        self.health_txt.insert(tk.END, "  [●] LM Studio: ")
        self.health_txt.insert(tk.END, "ONLINE\n" if lm_studio else "OFFLINE\n", "online" if lm_studio else "offline")
        self.health_txt.insert(tk.END, f"      Endpoint: {self.orchestrator.llm.base_url}\n\n")

        # OpenBrain
        self.health_txt.insert(tk.END, "  [●] Memory DB (OpenBrain): ")
        self.health_txt.insert(tk.END, "ONLINE\n" if ob else "OFFLINE\n", "online" if ob else "offline")
        self.health_txt.insert(tk.END, f"      Mode: {self.orchestrator.memory.openbrain.mode}\n\n")

        # n8n
        self.health_txt.insert(tk.END, "  [●] n8n Workflows: ")
        self.health_txt.insert(tk.END, "ONLINE\n" if n8n else "OFFLINE\n", "online" if n8n else "offline")
        self.health_txt.insert(tk.END, f"      Endpoint: {self.orchestrator.n8n.base_url}\n\n")

        # TTS
        self.health_txt.insert(tk.END, "  [●] Text-to-Speech: ")
        self.health_txt.insert(tk.END, "ONLINE\n" if tts else "OFFLINE\n", "online" if tts else "offline")
        self.health_txt.insert(tk.END, "      Status: Native speech stubs loaded.\n\n")

        # Registries
        self.health_txt.insert(tk.END, "=== REGISTERED ADAPTERS ===\n\n", "header")
        for s_id, data in registries.items():
            en = data.get("enabled", False)
            self.health_txt.insert(tk.END, f"  [●] {s_id.upper()}: ")
            self.health_txt.insert(tk.END, "ENABLED\n" if en else "DISABLED\n", "online" if en else "offline")
            self.health_txt.insert(tk.END, f"      Adapter: {data.get('adapter', 'default')}\n")
            self.health_txt.insert(tk.END, f"      Phase: {data.get('phase', '1')}\n")

        self.health_txt.configure(state=tk.DISABLED)

        # Render scanner details
        self.scan_txt.configure(state=tk.NORMAL)
        self.scan_txt.delete("1.0", tk.END)

        self.scan_txt.insert(tk.END, "=== DIRECTORY STRUCTURE SCAN ===\n\n")
        self.scan_txt.insert(tk.END, f"Total File Count: {file_count}\n")
        self.scan_txt.insert(tk.END, f"Accumulated Size: {size / (1024*1024):.2f} MB\n\n")

        self.scan_txt.insert(tk.END, "=== FILE SYSTEM ALERTS ===\n")
        for name, path in expected.items():
            ex = path.exists()
            self.scan_txt.insert(tk.END, f"  [{'✓' if ex else '✗'}] {name}: ")
            self.scan_txt.insert(tk.END, "FOUND\n" if ex else "MISSING\n", "ok" if ex else "missing")
        self.scan_txt.insert(tk.END, "\n=== DISK TREE ===\n")
        self.scan_txt.insert(tk.END, "\n".join(dir_lines))

        self.scan_txt.configure(state=tk.DISABLED)

    # -------------------------------------------------------------
    # PHASE 5: ARTIFACT BROWSER
    # -------------------------------------------------------------
    def _render_artifacts_view(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=0)

        # Left Column: Artifacts list
        list_outer, list_content = self._create_panel(parent, "Artifact Archive Browser", ACCENT_PURPLE)
        list_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.art_listbox = tk.Listbox(
            list_content,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            selectbackground=SELECT_BG,
            selectforeground=ACCENT_CYAN,
            bd=0,
            font=("Consolas", 9),
            highlightthickness=0
        )
        self.art_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(list_content, self.art_listbox, side=tk.RIGHT)
        self.art_listbox.bind("<<ListboxSelect>>", self._on_artifact_selected)

        # Right Column: Previewer
        preview_outer, preview_content = self._create_panel(parent, "Structured Previewer", BORDER_COLOR)
        preview_outer.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.art_preview = tk.Text(
            preview_content,
            bg=BG_COLOR,
            fg=TEXT_LIGHT,
            relief=tk.FLAT,
            font=("Consolas", 9),
            insertbackground=TEXT_LIGHT,
            selectbackground=SELECT_BG,
            state=tk.DISABLED
        )
        self.art_preview.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(preview_content, self.art_preview, side=tk.RIGHT)

        # Controls panel at bottom of parent frame
        ctrl_outer, ctrl_content = self._create_panel(parent, "Vault Control Interface", BORDER_COLOR)
        ctrl_outer.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        export_btn = tk.Button(ctrl_content, text="EXPORT TO FILESYSTEM", bg=PANEL_BG, fg=ACCENT_CYAN, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, command=self._export_selected_artifact)
        export_btn.pack(side=tk.LEFT, padx=10, pady=2)

        copy_btn = tk.Button(ctrl_content, text="COPY TO CLIPBOARD", bg=PANEL_BG, fg=TEXT_LIGHT, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, command=self._copy_artifact_to_clipboard)
        copy_btn.pack(side=tk.LEFT, padx=10, pady=2)

        self._load_artifacts_list()

    def _load_artifacts_list(self) -> None:
        self.art_listbox.delete(0, tk.END)
        self.active_artifacts = []
        
        art_dir = PROJECT_ROOT / "data" / "artifacts"
        if art_dir.exists():
            for p in sorted(art_dir.glob("*.md"), key=os.path.getmtime, reverse=True):
                self.art_listbox.insert(tk.END, f"📄 {p.name}")
                self.active_artifacts.append(p)

    def _on_artifact_selected(self, event: Any) -> None:
        selections = self.art_listbox.curselection()
        if not selections:
            return
            
        index = selections[0]
        file_path = self.active_artifacts[index]
        
        try:
            content = file_path.read_text(encoding="utf-8")
            self.art_preview.configure(state=tk.NORMAL)
            self.art_preview.delete("1.0", tk.END)
            self.art_preview.insert(tk.END, content)
            self.art_preview.configure(state=tk.DISABLED)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not load artifact: {exc}")

    def _export_selected_artifact(self) -> None:
        selections = self.art_listbox.curselection()
        if not selections:
            messagebox.showwarning("Warning", "No artifact selected.")
            return

        index = selections[0]
        source_path = self.active_artifacts[index]
        
        dest_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            initialfile=source_path.name
        )
        if dest_path:
            try:
                shutil.copy2(source_path, dest_path)
                messagebox.showinfo("Export Successful", f"Saved artifact safely to: {dest_path}")
            except Exception as exc:
                messagebox.showerror("Export Failed", str(exc))

    def _copy_artifact_to_clipboard(self) -> None:
        selections = self.art_listbox.curselection()
        if not selections:
            messagebox.showwarning("Warning", "No artifact selected.")
            return

        index = selections[0]
        file_path = self.active_artifacts[index]
        try:
            content = file_path.read_text(encoding="utf-8")
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("Success", "Artifact content copied to clipboard.")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _save_artifact(self, filename: str, content: str, artifact_type: str) -> Path:
        art_dir = PROJECT_ROOT / "data" / "artifacts"
        art_dir.mkdir(parents=True, exist_ok=True)
        file_path = art_dir / filename
        file_path.write_text(content, encoding="utf-8")
        
        self.logger.log_session_event({
            "event_type": "artifact_created",
            "artifact_type": artifact_type,
            "filename": filename,
            "path": str(file_path)
        })
        return file_path

    # -------------------------------------------------------------
    # PHASE 8: FILE WORKSPACE SESSION
    # -------------------------------------------------------------
    def _render_files_view(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        # Left Column: Files list
        list_outer, list_content = self._create_panel(parent, "Imported Documents Vault", ACCENT_CYAN)
        list_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.files_listbox = tk.Listbox(
            list_content,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            selectbackground=SELECT_BG,
            selectforeground=ACCENT_CYAN,
            bd=0,
            font=("Consolas", 9),
            highlightthickness=0
        )
        self.files_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(list_content, self.files_listbox, side=tk.RIGHT)
        self.files_listbox.bind("<<ListboxSelect>>", self._on_imported_file_selected)

        # Right Column: Workspace controls & details
        form_outer, form_content = self._create_panel(parent, "Workspace Session Controls", BORDER_COLOR)
        form_outer.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        # Import button
        import_btn = tk.Button(form_content, text="IMPORT DOCUMENT PATH", bg=PANEL_BG, fg=ACCENT_CYAN, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, height=2, command=self._import_document_path)
        import_btn.pack(fill=tk.X, pady=10)

        # Analysis details
        self.file_details_lbl = tk.Label(form_content, text="SELECT AN IMPORTED FILE FOR DIAGNOSTICS", bg=BG_COLOR, fg=ACCENT_GOLD, font=("Consolas", 10, "bold"), anchor="w")
        self.file_details_lbl.pack(fill=tk.X, pady=5)

        self.file_preview = tk.Text(
            form_content,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            relief=tk.SOLID,
            bd=1,
            height=12,
            font=("Segoe UI", 9),
            state=tk.DISABLED
        )
        self.file_preview.pack(fill=tk.BOTH, expand=True, pady=5)

        # Pipeline actions
        actions_frame = tk.Frame(form_content, bg=BG_COLOR)
        actions_frame.pack(fill=tk.X, pady=10)

        self.file_analyze_btn = tk.Button(actions_frame, text="ANALYZE FILE", bg=PANEL_BG, fg=TEXT_LIGHT, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, width=18, state=tk.DISABLED, command=self._analyze_selected_file)
        self.file_analyze_btn.pack(side=tk.LEFT, padx=5)

        self.file_memory_btn = tk.Button(actions_frame, text="EXTRACT TO MEMORY", bg=PANEL_BG, fg=ACCENT_CYAN, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, width=18, state=tk.DISABLED, command=self._extract_selected_file_to_memory)
        self.file_memory_btn.pack(side=tk.LEFT, padx=5)

        self._load_imported_files_list()

    def _load_imported_files_list(self) -> None:
        self.files_listbox.delete(0, tk.END)
        self.imported_files = []
        
        imp_dir = PROJECT_ROOT / "Sandbox" / "Imported_Documents"
        if imp_dir.exists():
            for p in sorted(imp_dir.glob("*"), key=os.path.getmtime, reverse=True):
                if p.is_file():
                    self.files_listbox.insert(tk.END, f"📄 {p.name}")
                    self.imported_files.append(p)

    def _on_imported_file_selected(self, event: Any) -> None:
        selections = self.files_listbox.curselection()
        if not selections:
            return
            
        index = selections[0]
        file_path = self.imported_files[index]
        
        self.file_details_lbl.configure(text=f"SELECTED: {file_path.name}")
        self.file_analyze_btn.configure(state=tk.NORMAL)
        self.file_memory_btn.configure(state=tk.NORMAL)

        # Simple file reading preview
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            self.file_preview.configure(state=tk.NORMAL)
            self.file_preview.delete("1.0", tk.END)
            self.file_preview.insert(tk.END, content[:2000])
            if len(content) > 2000:
                self.file_preview.insert(tk.END, "\n... [Context truncated for GUI preview]")
            self.file_preview.configure(state=tk.DISABLED)
        except Exception as exc:
            self.file_preview.configure(state=tk.NORMAL)
            self.file_preview.delete("1.0", tk.END)
            self.file_preview.insert(tk.END, f"[Cannot read content]: {exc}")
            self.file_preview.configure(state=tk.DISABLED)

    def _import_document_path(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Import Workspace Document",
            filetypes=[("Text/Markdown/JSON", "*.txt;*.md;*.json"), ("PDF documents", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self._log_event(f"Importing document: {file_path}")
            dest_dir = PROJECT_ROOT / "Sandbox" / "Imported_Documents"
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            src = Path(file_path)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = dest_dir / f"{stamp}_{src.name}"
            
            try:
                shutil.copy2(src, destination)
                self._log_event(f"Successfully cached document in sandbox.")
                messagebox.showinfo("Import Successful", f"Document copied to Workspace: {destination.name}")
                self._load_imported_files_list()
            except Exception as exc:
                messagebox.showerror("Error", f"Failed to import file: {exc}")

    def _analyze_selected_file(self) -> None:
        selections = self.files_listbox.curselection()
        if not selections:
            return
        index = selections[0]
        file_path = self.imported_files[index]

        # Trigger analysis
        self._log_event(f"Analyzing file: {file_path.name}")
        self._set_ui_busy(True, "ANALYZING DOCUMENT...")
        
        def run_analysis() -> None:
            try:
                analysis = self.orchestrator.file_analyzer.analyze_file(str(file_path))
                
                # Show results in preview and save as artifact
                self.root.after(0, lambda: self._show_file_analysis_results(file_path.name, analysis))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("Analysis Error", str(exc)))
            finally:
                self.root.after(0, lambda: self._set_ui_busy(False, "STATUS: COMPLETE"))

        threading.Thread(target=run_analysis, daemon=True).start()

    def _show_file_analysis_results(self, name: str, analysis: str) -> None:
        self.file_preview.configure(state=tk.NORMAL)
        self.file_preview.delete("1.0", tk.END)
        self.file_preview.insert(tk.END, analysis)
        self.file_preview.configure(state=tk.DISABLED)
        
        # Save as artifact
        art_filename = f"scan_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        art_content = f"# File Analysis: {name}\n\n{analysis}\n"
        self._save_artifact(art_filename, art_content, "system_scans")
        self._log_event(f"Analysis saved as artifact: {art_filename}")

    def _extract_selected_file_to_memory(self) -> None:
        selections = self.files_listbox.curselection()
        if not selections:
            return
        index = selections[0]
        file_path = self.imported_files[index]
        
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            drafted_count = 0
            
            for line in lines:
                line_clean = line.strip()
                if len(line_clean) < 15:
                    continue
                
                # Simple memory detection rule
                should_extract = any(
                    k in line_clean.lower()
                    for k in ["prefer", "always", "never", "remember", "must", "should", "like", "favorite"]
                )
                
                if should_extract:
                    cand = {
                        "event_type": "memory_candidate_detected",
                        "request_id": f"file_import_{datetime.now().strftime('%H%M%S')}",
                        "source": f"workspace_vault:{file_path.name}",
                        "text": line_clean,
                        "route": {"task_type": "file_import"},
                        "status": "needs_user_review"
                    }
                    
                    # Store memory candidate directly in OpenBrain queue
                    candidates_file = PROJECT_ROOT / "data" / "openbrain_memory_candidates.jsonl"
                    candidates_file.parent.mkdir(parents=True, exist_ok=True)
                    with candidates_file.open("a", encoding="utf-8") as f:
                        record = {
                            "candidate_id": f"ob_{uuid4().hex}",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "service_id": "openbrain",
                            "mode": "local",
                            "status": "candidate_logged",
                            "payload": cand
                        }
                        f.write(json.dumps(record) + "\n")
                    drafted_count += 1
            
            self._log_event(f"Extracted {drafted_count} memory candidates from {file_path.name}")
            messagebox.showinfo("Extraction Complete", f"Successfully drafted {drafted_count} memory candidates into the Memory review queue!")
        except Exception as exc:
            messagebox.showerror("Extraction Failed", str(exc))

    # -------------------------------------------------------------
    # PHASE 9: COUNCIL MODE VIEW (MULTI-PERSONA REASONING)
    # -------------------------------------------------------------
    def _render_council_view(self, parent: tk.Frame) -> None:
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=0)
        parent.columnconfigure(0, weight=1)

        # Top Control Panel
        top_outer, top_content = self._create_panel(parent, "Council Mode Settings & Prompt", ACCENT_PURPLE)
        top_outer.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        # Checkboxes for personas
        chk_frame = tk.Frame(top_content, bg=BG_COLOR)
        chk_frame.pack(fill=tk.X, pady=5)
        
        self.council_vars: dict[str, tk.BooleanVar] = {}
        for p_name in PERSONAS:
            var = tk.BooleanVar(value=(p_name in {"Proto Jane", "Serren", "Vecht"}))
            chk = tk.Checkbutton(
                chk_frame,
                text=p_name.upper(),
                variable=var,
                bg=BG_COLOR,
                fg=TEXT_LIGHT,
                selectcolor=BG_COLOR,
                activebackground=BG_COLOR,
                activeforeground=ACCENT_CYAN,
                font=("Consolas", 9, "bold")
            )
            chk.pack(side=tk.LEFT, padx=15)
            self.council_vars[p_name] = var

        # Council Prompt Entry
        prompt_frame = tk.Frame(top_content, bg=BG_COLOR)
        prompt_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(prompt_frame, text="CONSENSUS DIRECTIVE:", bg=BG_COLOR, fg=ACCENT_CYAN, font=("Consolas", 9, "bold")).pack(anchor="w")
        
        self.council_prompt_entry = tk.Entry(
            prompt_frame,
            bg=PANEL_BG,
            fg=TEXT_LIGHT,
            insertbackground=TEXT_LIGHT,
            relief=tk.SOLID,
            bd=1,
            font=("Segoe UI", 9)
        )
        self.council_prompt_entry.pack(fill=tk.X, pady=5, side=tk.LEFT, expand=True)
        self.council_prompt_entry.insert(0, "Assess system integration strategy for Vaila OS V3.")

        exec_btn = tk.Button(
            prompt_frame,
            text="EXECUTE COUNCIL",
            bg=PANEL_BG,
            fg=ACCENT_PURPLE,
            activebackground=ACCENT_PURPLE,
            activeforeground=BG_COLOR,
            bd=1,
            relief=tk.SOLID,
            font=("Consolas", 9, "bold"),
            width=16,
            command=self._execute_council_mode
        )
        exec_btn.pack(side=tk.RIGHT, padx=(10, 0))

        # Center Split Console View
        mid_outer, mid_content = self._create_panel(parent, "Council Dialogue Arenas", BORDER_COLOR)
        mid_outer.grid(row=1, column=0, sticky="nsew", pady=5)

        self.council_txt = tk.Text(
            mid_content,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            relief=tk.FLAT,
            font=("Consolas", 9),
            insertbackground=TEXT_LIGHT,
            state=tk.DISABLED
        )
        self.council_txt.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(mid_content, self.council_txt, side=tk.RIGHT)

        self.council_txt.tag_config("title", foreground=ACCENT_PURPLE, font=("Consolas", 10, "bold"))
        self.council_txt.tag_config("status", foreground=ACCENT_GOLD, font=("Consolas", 9, "italic"))
        self.council_txt.tag_config("response", foreground=TEXT_LIGHT, font=("Segoe UI", 9))
        self.council_txt.tag_config("drift", foreground=ACCENT_CYAN, font=("Consolas", 9))

        # Bottom synthesis actions
        synth_outer, synth_content = self._create_panel(parent, "Council Consensus Synthesis Workspace", BORDER_COLOR)
        synth_outer.grid(row=2, column=0, sticky="ew", pady=(5, 0))

        synth_btn = tk.Button(synth_content, text="SYNTHESIZE CONSENSUS", bg=PANEL_BG, fg=ACCENT_CYAN, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, command=self._synthesize_council_consensus)
        synth_btn.pack(side=tk.LEFT, padx=10, pady=2)

        drift_btn = tk.Button(synth_content, text="TONE DRIFT INSPECTION", bg=PANEL_BG, fg=TEXT_LIGHT, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, command=self._inspect_persona_drift)
        drift_btn.pack(side=tk.LEFT, padx=10, pady=2)

    def _execute_council_mode(self) -> None:
        prompt = self.council_prompt_entry.get().strip()
        if not prompt:
            messagebox.showwarning("Warning", "Prompt cannot be empty.")
            return

        selected_personas = [p for p, var in self.council_vars.items() if var.get()]
        if not selected_personas:
            messagebox.showwarning("Warning", "At least one persona must be selected.")
            return

        self._log_event(f"Activating Council Mode with: {', '.join(selected_personas)}")
        self._set_ui_busy(True, "COUNCIL ASSEMBLY ACTIVE...")

        self.council_txt.configure(state=tk.NORMAL)
        self.council_txt.delete("1.0", tk.END)
        self.council_txt.insert(tk.END, "=== ASSEMBLING COUNCIL ===\n\n")
        self.council_txt.configure(state=tk.DISABLED)

        self.council_responses = {}
        self.council_status = {}

        # Spin up parallel threads
        for p_name in selected_personas:
            p_id = PERSONAS[p_name]
            self.council_status[p_name] = "Routing prompt..."
            self._update_council_text()
            
            t = threading.Thread(target=self._council_worker, args=(prompt, p_name, p_id), daemon=True)
            t.start()

    def _council_worker(self, prompt: str, p_name: str, p_id: str) -> None:
        start_time = datetime.now()
        try:
            self.logger.log_router_event({
                "event_type": "council_thread_started",
                "persona": p_name,
                "prompt": prompt
            })

            # Mock Envelope
            envelope = self.envelope_service.create(
                user_text=prompt,
                source="council_mode",
                metadata={"interface": "council_mode", "selected_persona": p_id}
            )
            route = {
                "task_type": "general_chat",
                "persona": p_id,
                "confidence": 1.0,
                "needs_prompt_interpreter": False
            }

            self.council_status[p_name] = "Executing response generation..."
            self.root.after(0, self._update_council_text)

            res = self.orchestrator.handle(envelope=envelope, route=route)
            elapsed = (datetime.now() - start_time).total_seconds()
            
            self.council_responses[p_name] = res.visible_text
            self.council_status[p_name] = f"Completed in {elapsed:.2f}s"
        except Exception as exc:
            self.council_status[p_name] = f"Failed: {exc}"
            self.council_responses[p_name] = f"Pipeline execution failed: {exc}"

        self.root.after(0, self._update_council_text)

    def _update_council_text(self) -> None:
        self.council_txt.configure(state=tk.NORMAL)
        self.council_txt.delete("1.0", tk.END)

        self.council_txt.insert(tk.END, "=== COUNCIL MODE DIALOGUE ARENA ===\n\n", "title")
        
        # Display completion statuses
        self.council_txt.insert(tk.END, "COUNCIL PIPELINE STATES:\n", "title")
        all_done = True
        for name in PERSONAS:
            if name not in self.council_vars or not self.council_vars[name].get():
                continue
            status = self.council_status.get(name, "Queued.")
            self.council_txt.insert(tk.END, f"  [✓] {name}: ")
            self.council_txt.insert(tk.END, f"{status}\n", "status")
            if "Completed" not in status and "Failed" not in status:
                all_done = False

        self.council_txt.insert(tk.END, "\n=== LENS DIALOGUES ===\n\n", "title")
        for name, response in self.council_responses.items():
            self.council_txt.insert(tk.END, f"--- RESPONSIBILITY SPECTRUM: {name.upper()} ---\n", "title")
            self.council_txt.insert(tk.END, f"{response}\n\n", "response")

        self.council_txt.configure(state=tk.DISABLED)
        
        if all_done and self.busy:
            self.busy = False
            self._set_ui_busy(False, "STATUS: COMPLETE")
            self._log_event("Parallel Council dialogues compiled.")

    def _synthesize_council_consensus(self) -> None:
        if not hasattr(self, 'council_responses') or not self.council_responses:
            messagebox.showwarning("Warning", "Run the council mode first to obtain responses.")
            return

        self._log_event("Synthesizing joint council consensus response...")
        self._set_ui_busy(True, "SYNTHESIZING CONSENSUS...")

        def synth_worker() -> None:
            try:
                directive = "You are the Council Synthesizer. Synthesize a singular, highly cohesive decision report combining the analysis of the council personas:\n\n"
                for name, resp in self.council_responses.items():
                    directive += f"### PERSONA: {name.upper()}\n{resp}\n\n"
                
                directive += "Draft a consolidated and highly strategic system integration recommendation."

                envelope = self.envelope_service.create(
                    user_text=directive,
                    source="council_mode",
                    metadata={"interface": "council_mode"}
                )
                route = {"task_type": "general_chat", "persona": "proto_jane", "confidence": 1.0}
                res = self.orchestrator.handle(envelope=envelope, route=route)
                
                # Show results in a dialog box & save as artifact
                self.root.after(0, lambda: self._show_council_synthesis(res.visible_text))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("Synthesis Failure", str(exc)))
            finally:
                self.root.after(0, lambda: self._set_ui_busy(False, "STATUS: COMPLETE"))

        threading.Thread(target=synth_worker, daemon=True).start()

    def _show_council_synthesis(self, synthesis: str) -> None:
        # Save synthesis as artifact
        art_filename = f"council_synthesis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        self._save_artifact(art_filename, synthesis, "persona_comparisons")
        
        # Display synthesis preview to user
        dialog = tk.Toplevel(self.root)
        dialog.title("COUNCIL CONSENSUS SYNTHESIS")
        dialog.geometry("800x600")
        dialog.configure(bg=BG_COLOR)

        frame = tk.Frame(dialog, bg=BG_COLOR, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text=f"SYNTHESIZED REPORT: {art_filename}", bg=BG_COLOR, fg=ACCENT_CYAN, font=("Consolas", 10, "bold")).pack(anchor="w", pady=(0, 5))
        
        txt = tk.Text(frame, bg=PANEL_BG, fg=TEXT_LIGHT, relief=tk.SOLID, bd=1, font=("Segoe UI", 10))
        txt.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(frame, txt, side=tk.RIGHT)
        txt.insert(tk.END, synthesis)
        txt.configure(state=tk.DISABLED)

    def _inspect_persona_drift(self) -> None:
        if not hasattr(self, 'council_responses') or not self.council_responses:
            messagebox.showwarning("Warning", "Dialogue responses not populated yet.")
            return

        drift_report = "=== LENS DRIFT & LEXICAL METRICS ===\n\n"
        for name, resp in self.council_responses.items():
            words = resp.split()
            unique_words = set(w.lower() for w in words)
            density = len(unique_words) / len(words) if words else 0
            
            # Simple tone heuristic checks
            has_cyberpunk = "vaila" in resp.lower() or "os" in resp.lower() or "quantum" in resp.lower()
            drift_metric = "STABLE" if density > 0.45 else "SLIGHT DRIFT"
            
            drift_report += f"LENS: {name.upper()}\n"
            drift_report += f"  Word Count: {len(words)}\n"
            drift_report += f"  Lexical Diversity: {density:.2%}\n"
            drift_report += f"  Cyberpunk Lexicon Alignment: {'MATCHED' if has_cyberpunk else 'STANDARDIZED'}\n"
            drift_report += f"  Tone Integrity Index: {drift_metric}\n\n"

        self.council_txt.configure(state=tk.NORMAL)
        self.council_txt.insert(tk.END, "\n" + drift_report, "drift")
        self.council_txt.configure(state=tk.DISABLED)

    # -------------------------------------------------------------
    # PHASE 10: OVERLAY COMMAND PALETTE (CTRL+P)
    # -------------------------------------------------------------
    def _toggle_command_palette(self, event: Any) -> None:
        if self.palette_frame.winfo_y() < 0:
            self._show_command_palette()
        else:
            self._hide_command_palette()

    def _show_command_palette(self) -> None:
        self.palette_frame.tkraise()
        self.palette_frame.place(relx=0.5, rely=0.08, anchor="n", width=550, height=50)
        self.palette_entry.delete(0, tk.END)
        self.palette_entry.focus_set()
        self._log_event("Command Palette overlay loaded.")

    def _hide_command_palette(self) -> None:
        self.palette_frame.place(relx=0.5, rely=-1.0, anchor="n")
        self._log_event("Command Palette overlay hidden.")

    def _execute_palette_command(self, event: Any) -> None:
        raw_cmd = self.palette_entry.get().strip()
        self._hide_command_palette()
        
        if not raw_cmd.startswith("/"):
            # Treat as quick chat task
            self.switch_view("chat")
            self.send_task(raw_cmd)
            return

        cmd_parts = raw_cmd.split(maxsplit=1)
        base_cmd = cmd_parts[0].lower()
        args = cmd_parts[1] if len(cmd_parts) > 1 else ""

        self._log_event(f"Executing palette command: {base_cmd}")

        if base_cmd == "/scan":
            self.switch_view("system")
        elif base_cmd == "/clear":
            self.clear_chat()
        elif base_cmd == "/memory-queue":
            self.switch_view("memory")
        elif base_cmd == "/council":
            self.switch_view("council")
            if args:
                self.council_prompt_entry.delete(0, tk.END)
                self.council_prompt_entry.insert(0, args)
                self._execute_council_mode()
        elif base_cmd == "/self-assess":
            self.switch_view("chat")
            self.send_task("run self assessment tool diagnostics")
        elif base_cmd == "/import":
            self.switch_view("files")
            self._import_document_path()
        elif base_cmd == "/n8n":
            self.switch_view("n8n")
        else:
            messagebox.showwarning("Command Failure", f"Unrecognized terminal command: {base_cmd}\nSupported: /scan, /clear, /memory-queue, /council <prompt>, /self-assess, /import, /n8n")

    # -------------------------------------------------------------
    # AUXILIARY UTILITIES
    # -------------------------------------------------------------
    def check_model(self) -> None:
        if self.busy:
            return

        self._set_ui_busy(True, "PINGING GATEWAY MODEL...")
        threading.Thread(target=self._check_model_worker, daemon=True).start()

    def _check_model_worker(self) -> None:
        diagnostics = self.orchestrator.llm.diagnostics()
        self.root.after(0, self._show_diagnostics, diagnostics)

    def _show_diagnostics(self, diagnostics: dict[str, Any]) -> None:
        server_ok = diagnostics.get("server_reachable", False)
        resolved = diagnostics.get("resolved_model") or "AUTO"
        
        self.gateway_var.set(f"GATEWAY: {resolved.upper()}" if server_ok else "GATEWAY: UNREACHABLE")
        self.status_var.set("STATUS: COMPLETE" if server_ok else "STATUS: SERVICE CHECK FAILED")
        
        self._set_ui_busy(False)
        self._refresh_inspector()
        self._log_event(f"Gateway Diagnostics - Reachable: {server_ok}, Resolved Model: {resolved}")
        
        if not server_ok:
            messagebox.showerror("Gateway Error", "Local LLM Server (LM Studio) is not reachable.\nPlease boot LM Studio and confirm configured base URL.")

    def _log_event(self, message: str) -> None:
        # Mock internal log dispatch
        self.logger.log_session_event({
            "event_type": "desktop_client_action",
            "message": message
        })

    def _set_ui_busy(self, busy: bool, status_msg: str | None = None) -> None:
        self.busy = busy
        if status_msg:
            self.status_var.set(status_msg)
        
        if hasattr(self, 'send_btn'):
            self.send_btn.configure(state=tk.DISABLED if busy else tk.NORMAL)

    # -------------------------------------------------------------
    # PHASE 11: N8N ACTIVE WORKFLOWS BROWSER & COMPILER
    # -------------------------------------------------------------
    def _render_n8n_view(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.columnconfigure(2, weight=1)
        parent.rowconfigure(0, weight=1)

        # Left Column: Workflows List
        list_outer, list_content = self._create_panel(parent, "n8n Container Workflows", ACCENT_CYAN)
        list_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.n8n_listbox = tk.Listbox(
            list_content,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            selectbackground=SELECT_BG,
            selectforeground=ACCENT_CYAN,
            bd=0,
            font=("Consolas", 9),
            highlightthickness=0
        )
        self.n8n_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(list_content, self.n8n_listbox, side=tk.RIGHT)
        self.n8n_listbox.bind("<<ListboxSelect>>", self._on_n8n_workflow_selected)

        # Bottom Left: Refresh button
        refresh_btn = tk.Button(list_content, text="REFRESH WORKFLOWS", bg=PANEL_BG, fg=TEXT_LIGHT, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, command=self._load_n8n_workflows_list)
        refresh_btn.pack(fill=tk.X, pady=(5, 0))

        # Right Column: Workflow Details & Compiler Workspace
        detail_outer, detail_content = self._create_panel(parent, "Workflow Details & Compiler", BORDER_COLOR)
        detail_outer.grid(row=0, column=1, sticky="nsew", padx=5)

        detail_content.columnconfigure(0, weight=0)
        detail_content.columnconfigure(1, weight=1)

        # Active Workflow title & ID
        tk.Label(detail_content, text="SELECTED WORKFLOW:", bg=BG_COLOR, fg=ACCENT_CYAN, font=("Consolas", 9, "bold")).grid(row=0, column=0, sticky="w", pady=2)
        self.n8n_wf_name_lbl = tk.Label(detail_content, text="NONE", bg=BG_COLOR, fg=TEXT_LIGHT, font=("Consolas", 9, "bold"))
        self.n8n_wf_name_lbl.grid(row=0, column=1, sticky="w", pady=2)

        tk.Label(detail_content, text="WORKFLOW ID:", bg=BG_COLOR, fg=ACCENT_CYAN, font=("Consolas", 9, "bold")).grid(row=1, column=0, sticky="w", pady=2)
        self.n8n_wf_id_lbl = tk.Label(detail_content, text="NONE", bg=BG_COLOR, fg=TEXT_LIGHT, font=("Consolas", 9))
        self.n8n_wf_id_lbl.grid(row=1, column=1, sticky="w", pady=2)

        # Action Buttons: Toggle and Delete
        action_frame = tk.Frame(detail_content, bg=BG_COLOR)
        action_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)

        self.n8n_toggle_btn = tk.Button(action_frame, text="ACTIVATE WORKFLOW", bg=PANEL_BG, fg=ACCENT_CYAN, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, state=tk.DISABLED, width=20, command=self._toggle_n8n_workflow)
        self.n8n_toggle_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.n8n_delete_btn = tk.Button(action_frame, text="DELETE WORKFLOW", bg=PANEL_BG, fg=ACCENT_RED, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, state=tk.DISABLED, width=20, command=self._delete_n8n_workflow)
        self.n8n_delete_btn.pack(side=tk.LEFT)

        # Schema JSON Preview
        tk.Label(detail_content, text="NODES SCHEMA:", bg=BG_COLOR, fg=ACCENT_CYAN, font=("Consolas", 9, "bold")).grid(row=3, column=0, sticky="nw", pady=2)
        
        self.n8n_preview_txt = tk.Text(detail_content, bg=PANEL_BG, fg=TEXT_COLOR, insertbackground=TEXT_LIGHT, relief=tk.SOLID, bd=1, font=("Consolas", 9), height=10, state=tk.DISABLED)
        self.n8n_preview_txt.grid(row=3, column=1, sticky="nsew", pady=5)
        
        # Compiler Header
        tk.Label(detail_content, text="DRAFT NEW AUTOMATION TEMPLATE:", bg=BG_COLOR, fg=ACCENT_PURPLE, font=("Consolas", 9, "bold")).grid(row=4, column=0, columnspan=2, sticky="w", pady=(15, 5))

        # Compiler forms:
        # Name
        tk.Label(detail_content, text="WORKFLOW NAME:", bg=BG_COLOR, fg=TEXT_COLOR, font=("Consolas", 9)).grid(row=5, column=0, sticky="w", pady=2)
        self.n8n_compiler_name = tk.Entry(detail_content, bg=PANEL_BG, fg=TEXT_LIGHT, relief=tk.SOLID, bd=1, font=("Segoe UI", 9))
        self.n8n_compiler_name.grid(row=5, column=1, sticky="ew", pady=2)
        self.n8n_compiler_name.insert(0, "Vaila Webhook Automation")

        # Path
        tk.Label(detail_content, text="WEBHOOK PATH:", bg=BG_COLOR, fg=TEXT_COLOR, font=("Consolas", 9)).grid(row=6, column=0, sticky="w", pady=2)
        self.n8n_compiler_path = tk.Entry(detail_content, bg=PANEL_BG, fg=TEXT_LIGHT, relief=tk.SOLID, bd=1, font=("Segoe UI", 9))
        self.n8n_compiler_path.grid(row=6, column=1, sticky="ew", pady=2)
        self.n8n_compiler_path.insert(0, "vaila-webhook")

        # Endpoint Callback URL
        tk.Label(detail_content, text="CALLBACK URL:", bg=BG_COLOR, fg=TEXT_COLOR, font=("Consolas", 9)).grid(row=7, column=0, sticky="w", pady=2)
        self.n8n_compiler_url = tk.Entry(detail_content, bg=PANEL_BG, fg=TEXT_LIGHT, relief=tk.SOLID, bd=1, font=("Segoe UI", 9))
        self.n8n_compiler_url.grid(row=7, column=1, sticky="ew", pady=2)
        self.n8n_compiler_url.insert(0, "http://localhost:8000/api/n8n/hook")

        # Compile Button
        compile_btn = tk.Button(detail_content, text="COMPILE & DEPLOY TEMPLATE", bg=PANEL_BG, fg=ACCENT_CYAN, font=("Consolas", 9, "bold"), bd=1, relief=tk.SOLID, height=2, command=self._deploy_n8n_template)
        compile_btn.grid(row=8, column=1, sticky="ew", pady=15)

        detail_content.rowconfigure(3, weight=1)

        # Rightmost Column: AI Suggestions Lab
        sugg_outer, sugg_content = self._create_panel(parent, "AI Suggestion Lab", ACCENT_PURPLE)
        sugg_outer.grid(row=0, column=2, sticky="nsew", padx=(5, 0))

        # Consult Council Button
        consult_btn = tk.Button(
            sugg_content,
            text="CONSULT THE COUNCIL",
            bg=PANEL_BG,
            fg=ACCENT_PURPLE,
            activebackground=ACCENT_PURPLE,
            activeforeground=BG_COLOR,
            bd=1,
            relief=tk.SOLID,
            font=("Consolas", 9, "bold"),
            command=self._consult_council_for_n8n_suggestions
        )
        consult_btn.pack(fill=tk.X, pady=(0, 10))

        self.n8n_sugg_listbox = tk.Listbox(
            sugg_content,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            selectbackground=SELECT_BG,
            selectforeground=ACCENT_CYAN,
            bd=0,
            font=("Consolas", 9),
            highlightthickness=0
        )
        self.n8n_sugg_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._add_scrollbar(sugg_content, self.n8n_sugg_listbox, side=tk.RIGHT)
        self.n8n_sugg_listbox.bind("<<ListboxSelect>>", self._on_n8n_suggestion_selected)

        # Load workflows
        self._load_n8n_workflows_list()
        
        # Load suggestions
        self._load_default_n8n_suggestions()

    def _load_n8n_workflows_list(self) -> None:
        self.n8n_listbox.delete(0, tk.END)
        self.n8n_listbox.insert(tk.END, "Syncing container workflows...")
        
        self.n8n_workflows = []
        self.n8n_selected_wf = None
        
        # Clear fields
        self.n8n_wf_name_lbl.configure(text="NONE")
        self.n8n_wf_id_lbl.configure(text="NONE")
        self.n8n_toggle_btn.configure(state=tk.DISABLED, text="ACTIVATE WORKFLOW", fg=ACCENT_CYAN)
        self.n8n_delete_btn.configure(state=tk.DISABLED)
        self.n8n_preview_txt.configure(state=tk.NORMAL)
        self.n8n_preview_txt.delete("1.0", tk.END)
        self.n8n_preview_txt.configure(state=tk.DISABLED)

        def fetch_n8n() -> None:
            try:
                res = self.orchestrator.n8n.list_workflows()
                self.root.after(0, self._render_n8n_workflows, res)
            except Exception as exc:
                self.root.after(0, lambda: self._on_n8n_fetch_failed(str(exc)))

        threading.Thread(target=fetch_n8n, daemon=True).start()

    def _on_n8n_fetch_failed(self, error: str) -> None:
        self.n8n_listbox.delete(0, tk.END)
        self.n8n_listbox.insert(tk.END, "Sync Failure: Could not connect to container.")
        self.n8n_listbox.insert(tk.END, f"  {error}")
        self._log_event(f"n8n sync failed: {error}")

    def _render_n8n_workflows(self, res: dict[str, Any]) -> None:
        self.n8n_listbox.delete(0, tk.END)
        if not res.get("ok", False):
            self.n8n_listbox.insert(tk.END, f"Docker Sync Failure:")
            self.n8n_listbox.insert(tk.END, f"  {res.get('error', 'Unknown error')}")
            return

        self.n8n_workflows = res.get("workflows", [])
        if not self.n8n_workflows:
            self.n8n_listbox.insert(tk.END, "No workflows found in container.")
            return

        for wf in self.n8n_workflows:
            status_indicator = "[●] " if wf.get("active") else "[○] "
            self.n8n_listbox.insert(tk.END, f"{status_indicator}{wf.get('name')} ({wf.get('id')})")

    def _on_n8n_workflow_selected(self, event: Any) -> None:
        selections = self.n8n_listbox.curselection()
        if not selections:
            return
            
        index = selections[0]
        if index >= len(self.n8n_workflows):
            return

        wf = self.n8n_workflows[index]
        self.n8n_selected_wf = wf

        self.n8n_wf_name_lbl.configure(text=wf.get("name", "Unnamed").upper())
        self.n8n_wf_id_lbl.configure(text=wf.get("id", "UNKNOWN"))

        # Configure Toggle action
        is_active = wf.get("active", False)
        self.n8n_toggle_btn.configure(
            state=tk.NORMAL,
            text="DEACTIVATE WORKFLOW" if is_active else "ACTIVATE WORKFLOW",
            fg=ACCENT_RED if is_active else ACCENT_CYAN
        )
        self.n8n_delete_btn.configure(state=tk.NORMAL)

        # Pretty print JSON preview of the nodes
        nodes = wf.get("nodes", [])
        connections = wf.get("connections", {})
        
        self.n8n_preview_txt.configure(state=tk.NORMAL)
        self.n8n_preview_txt.delete("1.0", tk.END)
        self.n8n_preview_txt.insert(tk.END, json.dumps({"nodes": nodes, "connections": connections}, indent=2))
        self.n8n_preview_txt.configure(state=tk.DISABLED)

    def _toggle_n8n_workflow(self) -> None:
        if not self.n8n_selected_wf:
            return

        wf = self.n8n_selected_wf
        wf_id = wf.get("id")
        target_state = not wf.get("active", False)

        action_msg = "Activating" if target_state else "Deactivating"
        self._set_ui_busy(True, f"{action_msg.upper()} WORKFLOW...")

        def toggle_worker() -> None:
            try:
                res = self.orchestrator.n8n.toggle_workflow(wf_id, target_state)
                if res.get("ok", False):
                    self._log_event(f"Successfully toggled n8n workflow {wf_id} to active={target_state}")
                    self.root.after(0, self._load_n8n_workflows_list)
                else:
                    error = res.get("error", "Unknown error")
                    self.root.after(0, lambda: messagebox.showerror("Toggle Failed", f"Failed to toggle workflow:\n{error}"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("Error", str(exc)))
            finally:
                self.root.after(0, lambda: self._set_ui_busy(False, "STATUS: COMPLETE"))

        threading.Thread(target=toggle_worker, daemon=True).start()

    def _delete_n8n_workflow(self) -> None:
        if not self.n8n_selected_wf:
            return

        wf = self.n8n_selected_wf
        wf_id = wf.get("id")
        name = wf.get("name")

        if not messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete workflow '{name}' ({wf_id})?"):
            return

        self._set_ui_busy(True, "DELETING WORKFLOW...")

        def delete_worker() -> None:
            try:
                res = self.orchestrator.n8n.delete_workflow(wf_id)
                if res.get("ok", False):
                    self._log_event(f"Deleted workflow '{name}' ({wf_id}) successfully.")
                    self.root.after(0, self._load_n8n_workflows_list)
                else:
                    error = res.get("error", "Unknown error")
                    self.root.after(0, lambda: messagebox.showerror("Delete Failed", f"Failed to delete workflow:\n{error}"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("Error", str(exc)))
            finally:
                self.root.after(0, lambda: self._set_ui_busy(False, "STATUS: COMPLETE"))

        threading.Thread(target=delete_worker, daemon=True).start()

    def _deploy_n8n_template(self) -> None:
        name = self.n8n_compiler_name.get().strip()
        path = self.n8n_compiler_path.get().strip()
        url = self.n8n_compiler_url.get().strip()

        if not name or not path or not url:
            messagebox.showwarning("Validation Warning", "Please fill in all template fields before compiling.")
            return

        self._set_ui_busy(True, "COMPILING AND DEPLOYING TEMPLATE...")

        def deploy_worker() -> None:
            try:
                secret_token = self.orchestrator.n8n.webhook_secret
                nodes, connections = self.orchestrator.n8n_manager.compile_webhook_trigger_workflow(
                    name=name,
                    webhook_path=path,
                    action_url=url,
                    secret_token=secret_token
                )
                res = self.orchestrator.n8n.create_workflow(name=name, nodes=nodes, connections=connections)
                if res.get("ok", False):
                    new_wf = res.get("workflow", {})
                    self._log_event(f"Successfully compiled and deployed n8n workflow '{name}' (ID: {new_wf.get('id')})")
                    self.root.after(0, lambda: messagebox.showinfo("Success", f"Workflow '{name}' compiled & deployed!\nID: {new_wf.get('id')}"))
                    self.root.after(0, self._load_n8n_workflows_list)
                else:
                    error = res.get("error", "Unknown error")
                    self.root.after(0, lambda: messagebox.showerror("Deployment Failed", f"Failed to deploy workflow:\n{error}"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("Error", str(exc)))
            finally:
                self.root.after(0, lambda: self._set_ui_busy(False, "STATUS: COMPLETE"))

        threading.Thread(target=deploy_worker, daemon=True).start()

    def _load_default_n8n_suggestions(self) -> None:
        self.n8n_sugg_listbox.delete(0, tk.END)
        self.n8n_suggestions_data = [
            {
                "name": "Discord Alert Gateway",
                "path": "discord-notifier",
                "action_url": "https://discord.com/api/webhooks/dummy_id/dummy_token",
                "description": "Webhook Trigger -> Verify Token -> HTTP POST alerts to Discord Channels."
            },
            {
                "name": "Vaila Log Streamer",
                "path": "vaila-logs",
                "action_url": "http://localhost:8000/api/logs",
                "description": "Webhook Trigger -> Verify Secret -> Stream logs to Sandbox central server."
            },
            {
                "name": "OpenBrain Sync Webhook",
                "path": "openbrain-sync",
                "action_url": "http://localhost:8000/api/openbrain/sync",
                "description": "Webhook Trigger -> Extract memory candidates automatically to durable store."
            }
        ]
        for s in self.n8n_suggestions_data:
            self.n8n_sugg_listbox.insert(tk.END, f"🔮 {s['name'].upper()}")

    def _on_n8n_suggestion_selected(self, event: Any) -> None:
        selections = self.n8n_sugg_listbox.curselection()
        if not selections:
            return
        index = selections[0]
        if index >= len(self.n8n_suggestions_data):
            return
        
        s = self.n8n_suggestions_data[index]
        self.n8n_compiler_name.delete(0, tk.END)
        self.n8n_compiler_name.insert(0, s["name"])
        
        self.n8n_compiler_path.delete(0, tk.END)
        self.n8n_compiler_path.insert(0, s["path"])
        
        self.n8n_compiler_url.delete(0, tk.END)
        self.n8n_compiler_url.insert(0, s["action_url"])
        
        self._log_event(f"Auto-populated template compiler inputs from: {s['name']}")

    def _consult_council_for_n8n_suggestions(self) -> None:
        self._set_ui_busy(True, "CONSULTING THE COUNCIL...")
        self._log_event("Consulting multi-persona Council for custom workflow suggestions...")
        
        def consult_worker() -> None:
            try:
                prompt = (
                    "You are the Vaila OS Council. Suggest three highly strategic automation workflows "
                    "that integrate Vaila OS with third-party or local services via n8n webhook nodes. "
                    "Return a JSON array containing three objects, each with the following exact keys: "
                    "\"name\", \"path\", \"action_url\", \"description\". "
                    "Return ONLY the raw JSON block without markdown formatting or introductory text."
                )
                envelope = self.envelope_service.create(user_text=prompt, source="system_agent")
                route = {"task_type": "general_chat", "persona": "proto_jane", "confidence": 1.0}
                res = self.orchestrator.handle(envelope=envelope, route=route)
                
                raw_text = res.visible_text.strip()
                if raw_text.startswith("```"):
                    lines = raw_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw_text = "\n".join(lines).strip()
                suggestions = json.loads(raw_text)
                
                self.root.after(0, lambda: self._render_custom_n8n_suggestions(suggestions))
            except Exception as exc:
                self.root.after(0, lambda: self._log_event(f"Council suggestions failed: {exc}. Loading presets."))
                self.root.after(0, self._load_default_n8n_suggestions)
                self.root.after(0, lambda: messagebox.showinfo("Council Status", "Model Gateway offline. Predefined system suggestions loaded."))
            finally:
                self.root.after(0, lambda: self._set_ui_busy(False, "STATUS: COMPLETE"))

        threading.Thread(target=consult_worker, daemon=True).start()

    def _render_custom_n8n_suggestions(self, suggestions: list[dict[str, Any]]) -> None:
        self.n8n_sugg_listbox.delete(0, tk.END)
        self.n8n_suggestions_data = suggestions
        for s in self.n8n_suggestions_data:
            self.n8n_sugg_listbox.insert(tk.END, f"🔮 {s.get('name', 'Unnamed').upper()}")
        self._log_event("Custom Council recommendations successfully compiled.")
        messagebox.showinfo("Council Consultation Complete", "The Council has drafted 3 custom automation ideas! Click on any suggestion in the rightmost panel to populate the editor form.")

def main() -> None:
    root = tk.Tk()
    VailaDesktopClient(root)
    root.mainloop()

if __name__ == "__main__":
    main()
