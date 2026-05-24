from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from app.api_client import VailaApiClient, VailaApiError
from app.paths import find_project_root


DEFAULT_BASE_URL = "http://127.0.0.1:8765"
RESPONSE_TYPE_OPTIONS = {
    "Short Text": "short_text",
    "Long Text": "long_text",
    "Short Voice": "short_voice",
    "Long Voice": "long_voice",
    "Text with Debug Info": "text_debug",
    "Voice with Debug Info": "voice_debug",
}
PERSONA_OPTIONS = {
    "Proto Jane": "proto_jane",
    "Serren": "serren",
    "Vecht": "vecht",
    "Maelith": "maelith",
    "Riven": "riven",
    "Council": "council",
}


class VailaDesktopClient(tk.Tk):
    """Tkinter desktop control panel for the local Vaila API service."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Vaila Persona Core Control Panel")
        self.geometry("1120x760")
        self.minsize(980, 680)

        self.base_url_var = tk.StringVar(value=DEFAULT_BASE_URL)
        self.status_var = tk.StringVar(value="Service not checked yet.")
        self.processing_status_var = tk.StringVar(value="Ready")
        self.processing_detail_var = tk.StringVar(value="No request is running.")
        self.include_context_var = tk.BooleanVar(value=False)
        self.chat_persona_var = tk.StringVar(value="Proto Jane")
        self.response_type_var = tk.StringVar(value="Short Text")
        self.import_path_var = tk.StringVar(value="")
        self.analysis_path_var = tk.StringVar(value="")
        self.import_tags_var = tk.StringVar(value="project_vaila")
        self.import_scope_var = tk.StringVar(value="all")
        self.memory_query_var = tk.StringVar(value="")
        self.memory_persona_var = tk.StringVar(value="proto_jane")
        self.memory_tags_var = tk.StringVar(value="")
        self.candidate_status_var = tk.StringVar(value="pending")
        self.reject_note_var = tk.StringVar(value="")
        self.candidate_rows: list[dict[str, Any]] = []
        self.service_process: subprocess.Popen | None = None
        self.processing_after_id: str | None = None
        self.processing_step_index = 0

        self._build_layout()

    def api(self) -> VailaApiClient:
        return VailaApiClient(self.base_url_var.get().strip() or DEFAULT_BASE_URL)

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_top_bar()

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.chat_tab = ttk.Frame(notebook)
        self.memory_tab = ttk.Frame(notebook)
        self.analysis_tab = ttk.Frame(notebook)
        self.import_tab = ttk.Frame(notebook)
        self.candidates_tab = ttk.Frame(notebook)
        self.review_tab = ttk.Frame(notebook)
        self.models_tab = ttk.Frame(notebook)

        notebook.add(self.chat_tab, text="Chat")
        notebook.add(self.memory_tab, text="Memory Search")
        notebook.add(self.analysis_tab, text="File Analysis")
        notebook.add(self.import_tab, text="Document Import")
        notebook.add(self.candidates_tab, text="Candidate Review")
        notebook.add(self.review_tab, text="Project Review")
        notebook.add(self.models_tab, text="Models / State")

        self._build_chat_tab()
        self._build_memory_tab()
        self._build_analysis_tab()
        self._build_import_tab()
        self._build_candidates_tab()
        self._build_review_tab()
        self._build_models_tab()
        self._build_processing_bar()

    def _build_top_bar(self) -> None:
        frame = ttk.Frame(self)
        frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="API URL").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(frame, textvariable=self.base_url_var).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(frame, text="Check", command=self.check_health).grid(row=0, column=2, padx=3)
        ttk.Button(frame, text="Reload", command=self.reload_state).grid(row=0, column=3, padx=3)
        ttk.Button(frame, text="Resolve Models", command=self.resolve_models).grid(row=0, column=4, padx=3)
        ttk.Label(frame, textvariable=self.status_var).grid(row=1, column=0, columnspan=5, sticky="w", pady=(6, 0))

    def _build_processing_bar(self) -> None:
        frame = ttk.Frame(self)
        frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Processing").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(frame, textvariable=self.processing_status_var).grid(row=0, column=1, sticky="w")
        self.processing_progress = ttk.Progressbar(frame, mode="indeterminate", length=170)
        self.processing_progress.grid(row=0, column=2, sticky="e", padx=(8, 0))
        ttk.Label(frame, textvariable=self.processing_detail_var).grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 0))

    def _build_chat_tab(self) -> None:
        self.chat_tab.columnconfigure(0, weight=1)
        self.chat_tab.rowconfigure(1, weight=1)

        input_frame = ttk.Frame(self.chat_tab)
        input_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        input_frame.columnconfigure(0, weight=1)

        self.chat_input = tk.Text(input_frame, height=5, wrap="word")
        self.chat_input.grid(row=0, column=0, sticky="ew", columnspan=8)

        ttk.Checkbutton(
            input_frame,
            text="Include context packet",
            variable=self.include_context_var,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(input_frame, text="Persona").grid(row=1, column=1, sticky="e", padx=(8, 4), pady=(8, 0))
        persona_box = ttk.Combobox(
            input_frame,
            textvariable=self.chat_persona_var,
            values=list(PERSONA_OPTIONS.keys()),
            width=14,
            state="readonly",
        )
        persona_box.grid(row=1, column=2, sticky="e", padx=4, pady=(8, 0))
        ttk.Label(input_frame, text="Response type").grid(row=1, column=3, sticky="e", padx=(8, 4), pady=(8, 0))
        response_box = ttk.Combobox(
            input_frame,
            textvariable=self.response_type_var,
            values=list(RESPONSE_TYPE_OPTIONS.keys()),
            width=16,
            state="readonly",
        )
        response_box.grid(row=1, column=4, sticky="e", padx=4, pady=(8, 0))
        ttk.Button(input_frame, text="Send", command=self.send_chat).grid(row=1, column=6, sticky="e", padx=4, pady=(8, 0))
        ttk.Button(input_frame, text="Clear Output", command=lambda: self.clear_text(self.chat_output)).grid(
            row=1, column=7, sticky="e", pady=(8, 0)
        )

        self.chat_output = tk.Text(self.chat_tab, wrap="word")
        self.chat_output.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._add_scrollbar(self.chat_tab, self.chat_output, row=1, column=1)

    def _build_memory_tab(self) -> None:
        self.memory_tab.columnconfigure(0, weight=1)
        self.memory_tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(self.memory_tab)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(5, weight=1)

        ttk.Label(controls, text="Query").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.memory_query_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(controls, text="Persona").grid(row=0, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.memory_persona_var, width=18).grid(row=0, column=3, padx=6)
        ttk.Label(controls, text="Tags").grid(row=0, column=4, sticky="w")
        ttk.Entry(controls, textvariable=self.memory_tags_var).grid(row=0, column=5, sticky="ew", padx=6)
        ttk.Button(controls, text="Search", command=self.search_memory).grid(row=0, column=6)

        self.memory_output = tk.Text(self.memory_tab, wrap="word")
        self.memory_output.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._add_scrollbar(self.memory_tab, self.memory_output, row=1, column=1)

    def _build_analysis_tab(self) -> None:
        self.analysis_tab.columnconfigure(0, weight=1)
        self.analysis_tab.rowconfigure(2, weight=1)

        controls = ttk.Frame(self.analysis_tab)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="File").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.analysis_path_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(controls, text="Browse", command=self.browse_analysis_file).grid(row=0, column=2, padx=3)
        ttk.Button(controls, text="Analyze", command=self.analyze_file).grid(row=0, column=3, padx=3)
        ttk.Button(controls, text="Clear Output", command=lambda: self.clear_text(self.analysis_output)).grid(row=0, column=4, padx=3)

        hint = (
            "Supported files: .md, .txt, .json, .yaml, .yml, .py, .log. "
            "Analysis is read-only and does not create memory candidates."
        )
        ttk.Label(self.analysis_tab, text=hint).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))

        self.analysis_output = tk.Text(self.analysis_tab, wrap="word")
        self.analysis_output.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._add_scrollbar(self.analysis_tab, self.analysis_output, row=2, column=1)

    def _build_import_tab(self) -> None:
        self.import_tab.columnconfigure(0, weight=1)
        self.import_tab.rowconfigure(2, weight=1)

        controls = ttk.Frame(self.import_tab)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="File").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.import_path_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(controls, text="Browse", command=self.browse_import_file).grid(row=0, column=2)

        ttk.Label(controls, text="Tags").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(controls, textvariable=self.import_tags_var).grid(row=1, column=1, sticky="ew", padx=6, pady=(8, 0))

        ttk.Label(controls, text="Persona scope").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(controls, textvariable=self.import_scope_var).grid(row=2, column=1, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(controls, text="Import as Candidates", command=self.import_document).grid(row=2, column=2, pady=(8, 0))

        hint = (
            "Supported files: .md, .txt, .json, .yaml, .yml, .py, .log. "
            "Imported documents create pending candidates. Approval still happens separately."
        )
        ttk.Label(self.import_tab, text=hint).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))

        self.import_output = tk.Text(self.import_tab, wrap="word")
        self.import_output.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._add_scrollbar(self.import_tab, self.import_output, row=2, column=1)

    def _build_candidates_tab(self) -> None:
        self.candidates_tab.columnconfigure(0, weight=1)
        self.candidates_tab.columnconfigure(1, weight=2)
        self.candidates_tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(self.candidates_tab)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        controls.columnconfigure(5, weight=1)

        ttk.Label(controls, text="Status").grid(row=0, column=0, sticky="w")
        status_box = ttk.Combobox(
            controls,
            textvariable=self.candidate_status_var,
            values=["pending", "all", "approved", "rejected"],
            width=12,
            state="readonly",
        )
        status_box.grid(row=0, column=1, padx=6)
        ttk.Button(controls, text="Refresh", command=self.refresh_candidates).grid(row=0, column=2, padx=3)
        ttk.Button(controls, text="Approve Selected", command=self.approve_selected_candidate).grid(row=0, column=3, padx=3)
        ttk.Label(controls, text="Reject note").grid(row=0, column=4, padx=(10, 3))
        ttk.Entry(controls, textvariable=self.reject_note_var).grid(row=0, column=5, sticky="ew", padx=3)
        ttk.Button(controls, text="Reject Selected", command=self.reject_selected_candidate).grid(row=0, column=6, padx=3)

        self.candidate_list = tk.Listbox(self.candidates_tab, exportselection=False)
        self.candidate_list.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))
        self.candidate_list.bind("<<ListboxSelect>>", self.show_selected_candidate)

        self.candidate_detail = tk.Text(self.candidates_tab, wrap="word")
        self.candidate_detail.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))
        self._add_scrollbar(self.candidates_tab, self.candidate_detail, row=1, column=2)

    def _build_review_tab(self) -> None:
        self.review_tab.columnconfigure(0, weight=1)
        self.review_tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(self.review_tab)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ttk.Button(controls, text="Generate Project Review", command=self.generate_project_review).grid(row=0, column=0, padx=3)
        ttk.Button(controls, text="Show Recent Activity", command=self.show_recent_activity).grid(row=0, column=1, padx=3)
        ttk.Button(controls, text="Clear Output", command=lambda: self.clear_text(self.review_output)).grid(row=0, column=2, padx=3)

        self.review_output = tk.Text(self.review_tab, wrap="word")
        self.review_output.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._add_scrollbar(self.review_tab, self.review_output, row=1, column=1)

    def _build_models_tab(self) -> None:
        self.models_tab.columnconfigure(0, weight=1)
        self.models_tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(self.models_tab)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ttk.Button(controls, text="Health", command=self.check_health).grid(row=0, column=0, padx=3)
        ttk.Button(controls, text="Resolve Models", command=self.resolve_models).grid(row=0, column=1, padx=3)
        ttk.Button(controls, text="Show Models", command=self.show_models).grid(row=0, column=2, padx=3)
        ttk.Button(controls, text="Clear Output", command=lambda: self.clear_text(self.models_output)).grid(row=0, column=3, padx=3)

        self.models_output = tk.Text(self.models_tab, wrap="word")
        self.models_output.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._add_scrollbar(self.models_tab, self.models_output, row=1, column=1)

    def _add_scrollbar(self, parent: ttk.Frame, widget: tk.Text, row: int, column: int) -> None:
        scrollbar = ttk.Scrollbar(parent, command=widget.yview)
        scrollbar.grid(row=row, column=column, sticky="ns", pady=(0, 10), padx=(0, 10))
        widget.configure(yscrollcommand=scrollbar.set)

    def run_api_call(
        self,
        task: Callable[[], dict[str, Any]],
        on_success: Callable[[dict[str, Any]], None],
        busy_message: str = "Working...",
        processing_steps: list[str] | None = None,
    ) -> None:
        self.status_var.set(busy_message)
        self.start_processing(busy_message, processing_steps or ["Preparing request", "Waiting for local API", "Processing response"])

        def worker() -> None:
            try:
                result = task()
            except VailaApiError:
                if self._can_start_local_service():
                    self.after(0, lambda: self.processing_detail_var.set("Starting the local Vaila API service..."))
                    self._start_local_service()
                    try:
                        result = task()
                    except Exception as error:
                        self.after(0, lambda: self.show_error(error))
                        return
                else:
                    self.after(0, lambda: self.show_error(VailaApiError("Could not reach the configured Vaila API service.")))
                    return
            except Exception as error:
                self.after(0, lambda: self.show_error(error))
                return
            self.after(0, lambda: self.finish_api_call(on_success, result))

        threading.Thread(target=worker, daemon=True).start()

    def finish_api_call(self, on_success: Callable[[dict[str, Any]], None], result: dict[str, Any]) -> None:
        self.stop_processing(reset=False)
        self.processing_status_var.set("Complete" if result.get("ok", True) else "Failed")
        on_success(result)

    def start_processing(self, label: str, steps: list[str]) -> None:
        self.stop_processing(reset=False)
        self.processing_step_index = 0
        self.processing_status_var.set(label)
        self.processing_progress.start(12)
        self._advance_processing_steps(steps)

    def _advance_processing_steps(self, steps: list[str]) -> None:
        if not steps:
            return
        step = steps[min(self.processing_step_index, len(steps) - 1)]
        self.processing_detail_var.set(step)
        if self.processing_step_index < len(steps) - 1:
            self.processing_step_index += 1
        self.processing_after_id = self.after(900, lambda: self._advance_processing_steps(steps))

    def stop_processing(self, reset: bool = True) -> None:
        if self.processing_after_id:
            self.after_cancel(self.processing_after_id)
            self.processing_after_id = None
        if hasattr(self, "processing_progress"):
            self.processing_progress.stop()
        if reset:
            self.processing_status_var.set("Ready")

    def _can_start_local_service(self) -> bool:
        return self.base_url_var.get().strip().rstrip("/") == DEFAULT_BASE_URL

    def _start_local_service(self) -> None:
        if self.service_process and self.service_process.poll() is None:
            time.sleep(1)
            return

        project_root = find_project_root(__file__)
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.service_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.service:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
            ],
            cwd=project_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        time.sleep(2)

    def show_error(self, error: Exception) -> None:
        self.stop_processing(reset=False)
        self.status_var.set("Error. Check output or popup.")
        self.processing_status_var.set("Error")
        self.processing_detail_var.set(str(error))
        messagebox.showerror("Vaila API Error", str(error))

    def check_health(self) -> None:
        self.run_api_call(self.api().health, self._display_health, "Checking service...")

    def reload_state(self) -> None:
        self.run_api_call(self.api().reload, self._display_reload, "Reloading local state...")

    def resolve_models(self) -> None:
        self.run_api_call(self.api().resolve_models, self._display_models, "Resolving models...")

    def show_models(self) -> None:
        self.run_api_call(self.api().models, self._display_models, "Loading model status...")

    def generate_project_review(self) -> None:
        self.run_api_call(
            lambda: self.api().project_review(limit=50),
            self._display_project_review,
            "Generating project review...",
        )

    def show_recent_activity(self) -> None:
        self.run_api_call(
            lambda: self.api().recent_activity(limit=50),
            self._display_recent_activity,
            "Loading recent activity...",
        )

    def send_chat(self) -> None:
        message = self.chat_input.get("1.0", "end").strip()
        if not message:
            messagebox.showinfo("No message", "Type a message before sending.")
            return
        selected_response = self.response_type_var.get().strip()
        if selected_response not in RESPONSE_TYPE_OPTIONS:
            messagebox.showinfo("Response type required", "Choose a response type before sending.")
            return
        selected_persona = self.chat_persona_var.get().strip()
        if selected_persona not in PERSONA_OPTIONS:
            messagebox.showinfo("Persona required", "Choose which persona you want to speak to before sending.")
            return

        self.append_text(self.chat_output, f"\nUser [{selected_persona}] > {message}\n")
        self.run_api_call(
            lambda: self.api().chat(
                message,
                include_context=self.include_context_var.get(),
                response_type=RESPONSE_TYPE_OPTIONS[selected_response],
                persona_id=PERSONA_OPTIONS[selected_persona],
            ),
            self._display_chat_result,
            "Sending chat request...",
            [
                "Preserving request envelope",
                "Routing persona and context",
                "Planning task and tool needs",
                "Running tools or model response",
                "Formatting final persona response",
            ],
        )

    def search_memory(self) -> None:
        query = self.memory_query_var.get().strip()
        if not query:
            messagebox.showinfo("No query", "Type a memory search query first.")
            return

        tags = parse_csv(self.memory_tags_var.get())
        persona = self.memory_persona_var.get().strip() or "proto_jane"
        self.run_api_call(
            lambda: self.api().search_memory(query=query, persona=persona, tags=tags, limit=12),
            self._display_memory_results,
            "Searching memory...",
        )

    def browse_import_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a document to import",
            filetypes=[
                ("Supported documents", "*.md *.txt *.json *.yaml *.yml *.py *.log"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.import_path_var.set(path)

    def browse_analysis_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a file to analyze",
            filetypes=[
                ("Supported files", "*.md *.txt *.json *.yaml *.yml *.py *.log"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.analysis_path_var.set(path)

    def analyze_file(self) -> None:
        path = self.analysis_path_var.get().strip()
        if not path:
            messagebox.showinfo("No file", "Choose a file to analyze first.")
            return
        if not Path(path).exists():
            messagebox.showerror("File not found", f"The selected file does not exist:\n{path}")
            return

        self.run_api_call(
            lambda: self.api().analyze_file(path),
            self._display_file_analysis,
            "Analyzing file...",
        )

    def import_document(self) -> None:
        path = self.import_path_var.get().strip()
        if not path:
            messagebox.showinfo("No file", "Choose a file to import first.")
            return
        if not Path(path).exists():
            messagebox.showerror("File not found", f"The selected file does not exist:\n{path}")
            return

        tags = parse_csv(self.import_tags_var.get())
        persona_scope = parse_csv(self.import_scope_var.get()) or ["all"]
        self.run_api_call(
            lambda: self.api().import_document(path=path, tags=tags, persona_scope=persona_scope),
            self._display_import_result,
            "Importing document...",
        )

    def refresh_candidates(self) -> None:
        status = self.candidate_status_var.get() or "pending"
        self.run_api_call(
            lambda: self.api().list_candidates(status=status),
            self._display_candidate_list,
            "Loading candidates...",
        )

    def show_selected_candidate(self, event: tk.Event | None = None) -> None:
        selected = self.candidate_list.curselection()
        if not selected:
            return
        index = selected[0]
        if index >= len(self.candidate_rows):
            return
        candidate_id = self.candidate_rows[index]["id"]
        self.run_api_call(
            lambda: self.api().get_candidate(candidate_id),
            self._display_candidate_detail,
            "Loading candidate...",
        )

    def approve_selected_candidate(self) -> None:
        candidate = self._selected_candidate_row()
        if not candidate:
            return
        if candidate.get("status") != "pending":
            messagebox.showinfo("Not pending", "Only pending candidates can be approved.")
            return

        candidate_id = candidate["id"]
        self.run_api_call(
            lambda: self.api().approve_candidate(candidate_id),
            self._after_candidate_review,
            "Approving candidate...",
        )

    def reject_selected_candidate(self) -> None:
        candidate = self._selected_candidate_row()
        if not candidate:
            return
        if candidate.get("status") != "pending":
            messagebox.showinfo("Not pending", "Only pending candidates can be rejected.")
            return

        candidate_id = candidate["id"]
        note = self.reject_note_var.get().strip()
        self.run_api_call(
            lambda: self.api().reject_candidate(candidate_id, note=note),
            self._after_candidate_review,
            "Rejecting candidate...",
        )

    def _selected_candidate_row(self) -> dict[str, Any] | None:
        selected = self.candidate_list.curselection()
        if not selected:
            messagebox.showinfo("No candidate selected", "Select a candidate first.")
            return None
        index = selected[0]
        if index >= len(self.candidate_rows):
            messagebox.showerror("Selection error", "Selected candidate index is invalid.")
            return None
        return self.candidate_rows[index]

    def _display_project_review(self, result: dict[str, Any]) -> None:
        self.status_var.set("Project review generated.")
        self.write_text(self.review_output, format_project_review(result))

    def _display_recent_activity(self, result: dict[str, Any]) -> None:
        events = result.get("events", [])
        self.status_var.set(f"Loaded {len(events)} activity event(s).")
        if not events:
            self.write_text(self.review_output, "No activity logged yet.")
            return
        self.write_text(self.review_output, "\n\n".join(format_activity_event(event) for event in events))

    def _display_health(self, result: dict[str, Any]) -> None:
        state = result.get("state", {})
        self.status_var.set(
            f"Service online. Memory: {state.get('memory_records', 0)}. "
            f"Pending candidates: {state.get('pending_candidates', 0)}."
        )
        self.write_text(self.models_output, pretty_json(result))

    def _display_reload(self, result: dict[str, Any]) -> None:
        state = result.get("state", {})
        self.status_var.set(
            f"Reloaded. Memory: {state.get('memory_records', 0)}. "
            f"Pending candidates: {state.get('pending_candidates', 0)}."
        )
        self.write_text(self.models_output, pretty_json(result))

    def _display_models(self, result: dict[str, Any]) -> None:
        self.status_var.set(result.get("message", "Model status loaded."))
        self.write_text(self.models_output, pretty_json(result))

    def _display_chat_result(self, result: dict[str, Any]) -> None:
        self.status_var.set("Chat complete." if result.get("ok") else "Chat failed. See output.")

        envelope = result.get("request_envelope", {})
        envelope_metadata = envelope.get("metadata", {})
        interpretation = result.get("prompt_interpretation", {})
        comparison = result.get("routing_comparison", {})
        persona_continuity = result.get("persona_continuity", {})
        task_plan = result.get("task_plan", {})
        route = result.get("route_plan", {})
        response_route = result.get("response_route", {})
        tool_calls = result.get("tool_calls", [])
        tool_names = ", ".join(call.get("tool_name", "") for call in tool_calls) or "None"
        self.processing_status_var.set("Chat complete" if result.get("ok") else "Chat failed")
        self.processing_detail_var.set(
            f"Persona: {route.get('persona', 'unknown')} | "
            f"Task: {route.get('task_type', 'unknown')} | "
            f"Plan: {task_plan.get('mode', 'direct_response')} | "
            f"Tools: {tool_names} | "
            f"Profile: {result.get('selected_profile')}"
        )
        if route:
            self.append_text(
                self.chat_output,
                "\nRoute\n"
                f"Request UTC: {result.get('request_timestamp', '')}\n"
                f"Response UTC: {result.get('response_timestamp', '')}\n"
                f"Task: {route.get('task_type')}\n"
                f"Persona: {route.get('persona')}\n"
                f"Persona continuity: {persona_continuity.get('display_name', route.get('persona', ''))} "
                f"({persona_continuity.get('active_persona', route.get('persona', ''))})\n"
                f"Model profile: {route.get('model_profile')}\n"
                f"Fallback: {route.get('fallback_profile')}\n"
                f"Response type: {response_route.get('response_type', 'text')}\n"
                f"Output channel: {response_route.get('output_channel', 'text')}\n"
                f"TTS engine: {response_route.get('tts_engine', 'kokoro')}\n"
                f"Request envelope: {envelope.get('id', '')}\n"
                f"Persona source: {envelope_metadata.get('persona_source', 'detect_persona')}\n"
                f"Selected persona: {envelope_metadata.get('selected_persona', '') or 'None'}\n"
                f"Interpreter: {interpretation.get('source', 'not_run')} | "
                f"Advised task: {interpretation.get('advised_task_type', '')} | "
                f"Advised persona: {interpretation.get('advised_persona', '')}\n"
                f"Task plan: {task_plan.get('mode', 'direct_response')} | "
                f"Needs synthesis: {task_plan.get('requires_synthesis', False)} | "
                f"Tools: {tool_names}\n"
                f"Route comparison: {comparison.get('status', '')} | "
                f"Disagreements: {', '.join(comparison.get('disagreements', []) or ['None'])}\n"
                f"Reasons: {', '.join(route.get('reasons', []))}\n",
            )

        if result.get("ok"):
            self.append_text(
                self.chat_output,
                "\nVaila > "
                f"[Profile: {result.get('selected_profile')} | Model: {result.get('model')} | "
                f"{result.get('elapsed_seconds')}s]\n{result.get('response', '')}\n",
            )
        else:
            self.append_text(self.chat_output, f"\nModel response failed:\n{result.get('error', '')}\n")

        if result.get("context_packet"):
            self.append_text(self.chat_output, f"\nFull context audit packet\n{result['context_packet']}\n")
        if result.get("llm_context_packet"):
            self.append_text(self.chat_output, f"\nCompact LLM packet\n{result['llm_context_packet']}\n")

    def _display_memory_results(self, result: dict[str, Any]) -> None:
        records = result.get("records", [])
        self.status_var.set(f"Memory search complete. {len(records)} record(s) found.")
        if not records:
            self.write_text(self.memory_output, "No memory records matched.")
            return
        self.write_text(self.memory_output, "\n\n".join(format_memory(record) for record in records))

    def _display_file_analysis(self, result: dict[str, Any]) -> None:
        analysis = result.get("analysis", {})
        self.status_var.set(f"File analyzed: {analysis.get('title', 'selected file')}")
        self.write_text(self.analysis_output, format_file_analysis(analysis))

    def _display_import_result(self, result: dict[str, Any]) -> None:
        report = result.get("report", {})
        document = report.get("document", {})
        text = [
            f"Imported: {document.get('title')}",
            f"Document ID: {document.get('id')}",
            f"File type: {document.get('file_type')}",
            f"Characters: {document.get('char_count')}",
            f"Chunks: {document.get('chunk_count')}",
            f"Candidates created: {report.get('candidates_created')}",
            f"Saved new pending candidates: {result.get('added_count')}",
            f"Skipped duplicates: {result.get('skipped_duplicate_count')}",
            "",
            "Candidate IDs:",
        ]
        for candidate_id in report.get("candidate_ids", []):
            text.append(f"  - {candidate_id}")
        warnings = report.get("warnings", [])
        text.append("")
        text.append("Warnings:")
        if warnings:
            text.extend(f"  - {warning}" for warning in warnings)
        else:
            text.append("  - None")
        text.append("")
        text.append("Review candidates in the Candidate Review tab before approving memory writes.")

        self.status_var.set("Document imported as memory candidates.")
        self.write_text(self.import_output, "\n".join(text))
        self.refresh_candidates()

    def _display_candidate_list(self, result: dict[str, Any]) -> None:
        self.candidate_rows = result.get("candidates", [])
        self.candidate_list.delete(0, "end")
        for candidate in self.candidate_rows:
            label = f"{candidate.get('status', '').upper()} | {candidate.get('id')} | {candidate.get('question', '')[:72]}"
            self.candidate_list.insert("end", label)
        self.status_var.set(f"Loaded {len(self.candidate_rows)} candidate(s).")
        if not self.candidate_rows:
            self.write_text(self.candidate_detail, "No candidates for this status.")

    def _display_candidate_detail(self, result: dict[str, Any]) -> None:
        candidate = result.get("candidate", {})
        self.status_var.set(f"Loaded candidate {candidate.get('id')}")
        self.write_text(self.candidate_detail, format_candidate(candidate))

    def _after_candidate_review(self, result: dict[str, Any]) -> None:
        candidate = result.get("candidate", {})
        self.status_var.set(f"Candidate reviewed: {candidate.get('id')} is now {candidate.get('status')}")
        self.write_text(self.candidate_detail, format_candidate(candidate))
        self.refresh_candidates()

    @staticmethod
    def write_text(widget: tk.Text, text: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("end", text)
        widget.see("end")

    @staticmethod
    def append_text(widget: tk.Text, text: str) -> None:
        widget.insert("end", text)
        widget.see("end")

    @staticmethod
    def clear_text(widget: tk.Text) -> None:
        widget.delete("1.0", "end")


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def format_memory(record: dict[str, Any]) -> str:
    source = f"\nSource: {record.get('source_path')}" if record.get("source_path") else ""
    return (
        f"[Memory: {record.get('id')}]\n"
        f"Question: {record.get('question')}\n"
        f"Answer: {record.get('answer')}\n"
        f"Tags: {', '.join(record.get('tags', []))}"
        f"{source}"
    )


def format_file_analysis(analysis: dict[str, Any]) -> str:
    def block(title: str, items: list[str]) -> list[str]:
        lines = [title]
        if items:
            lines.extend(f"  - {item}" for item in items)
        else:
            lines.append("  - None")
        return lines

    lines = [
        "File Analysis",
        f"File: {analysis.get('path')}",
        f"Type: {analysis.get('file_type')}",
        f"Size: {analysis.get('size_bytes')} bytes",
        f"Lines: {analysis.get('line_count')}",
        f"Words: {analysis.get('word_count')}",
        f"SHA-256: {analysis.get('sha256')}",
        "",
        "Summary",
        analysis.get("summary", ""),
        "",
    ]
    lines.extend(block("Headings / Structure", analysis.get("headings", [])))
    lines.append("")
    lines.extend(block("Key Lines", analysis.get("key_lines", [])))
    lines.append("")
    lines.extend(block("Action Items", analysis.get("action_items", [])))
    lines.append("")
    lines.extend(block("Structural Notes", analysis.get("structural_notes", [])))
    lines.append("")
    lines.extend(block("Warnings", analysis.get("warnings", [])))
    return "\n".join(lines)


def format_candidate(candidate: dict[str, Any]) -> str:
    return (
        f"[{candidate.get('status', '').upper()}] {candidate.get('id')}\n"
        f"Source: {candidate.get('source_title') or candidate.get('source_path')}\n"
        f"Question: {candidate.get('question')}\n"
        f"Answer: {candidate.get('answer')}\n"
        f"Tags: {', '.join(candidate.get('tags', []))}\n"
        f"Persona scope: {', '.join(candidate.get('persona_scope', []))}\n"
        f"Confidence: {candidate.get('confidence')}\n"
        f"Source document ID: {candidate.get('source_document_id')}\n"
        f"Chunk IDs: {', '.join(candidate.get('chunk_ids', []))}\n"
        f"Created: {candidate.get('created_at')}\n"
        f"Reviewed: {candidate.get('reviewed_at')}\n"
        f"Review note: {candidate.get('review_note')}"
    )


def format_activity_event(event: dict[str, Any]) -> str:
    details = event.get("details", {})
    detail_lines = []
    for key, value in details.items():
        if value in (None, "", [], {}):
            continue
        detail_lines.append(f"  {key}: {value}")
    detail_text = "\n".join(detail_lines) if detail_lines else "  No details."
    return (
        f"[{event.get('created_at')}] {event.get('event_type')}\n"
        f"{event.get('summary')}\n"
        f"Details:\n{detail_text}"
    )


def format_project_review(review: dict[str, Any]) -> str:
    state = review.get("state", {})
    lines = [
        "Project Review",
        f"Generated: {review.get('generated_at')}",
        f"Phase: {review.get('phase')}",
        "",
        "Summary",
        review.get("summary", ""),
        "",
        "Phase Fit",
        review.get("phase_fit", ""),
        "",
        "State",
        f"  Memory records: {state.get('memory_records')}",
        f"  Pending candidates: {state.get('pending_candidates')}",
        f"  Approved candidates: {state.get('approved_candidates')}",
        f"  Rejected candidates: {state.get('rejected_candidates')}",
        f"  Activity events: {state.get('activity_events')}",
        f"  Activity counts: {state.get('activity_counts')}",
        "",
        "Risks",
    ]
    lines.extend(f"  - {item}" for item in review.get("risks", []))
    lines.append("")
    lines.append("Recommended Next Steps")
    lines.extend(f"  - {item}" for item in review.get("recommended_next_steps", []))
    lines.append("")
    lines.append("Suggested Tests")
    lines.extend(f"  - {item}" for item in review.get("suggested_tests", []))
    lines.append("")
    lines.append("Recent Activity")
    for event in review.get("recent_activity", [])[:10]:
        lines.append(f"  - [{event.get('created_at')}] {event.get('event_type')}: {event.get('summary')}")
    return "\n".join(lines)

def main() -> None:
    app = VailaDesktopClient()
    app.mainloop()


if __name__ == "__main__":
    main()
