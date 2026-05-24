from __future__ import annotations

import json
import sys
import threading
from datetime import datetime
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from System_Services.envelope_service import EnvelopeService, PromptEnvelope
from System_Services.logging_service import LoggingService
from System_Services.orchestration_service import OrchestrationResponse, OrchestrationService
from System_Services.router_service import RouterService

PERSONAS = {
    "Proto Jane": "proto_jane",
    "Serren": "serren",
    "Maelith": "maelith",
    "Vecht": "vecht",
    "Riven": "riven",
}


class VailaDesktopClient:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Vaila OS V3")
        self.root.geometry("1180x820")
        self.root.minsize(960, 660)

        self.logger = LoggingService(project_root=PROJECT_ROOT)
        self.envelope_service = EnvelopeService(project_root=PROJECT_ROOT)
        self.router = RouterService(project_root=PROJECT_ROOT)
        self.orchestrator = OrchestrationService(project_root=PROJECT_ROOT, logger=self.logger)

        self.persona_var = tk.StringVar(value="Proto Jane")
        self.status_var = tk.StringVar(value="Ready.")
        self.route_var = tk.StringVar(value="Route: waiting")
        self.gateway_var = tk.StringVar(value="Gateway: not checked")
        self.busy = False
        self.last_envelope: PromptEnvelope | None = None
        self.last_route: dict[str, Any] | None = None
        self.last_response: OrchestrationResponse | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=(12, 12, 12, 6))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(4, weight=1)

        ttk.Label(top, text="Persona").grid(row=0, column=0, sticky="w")
        persona_menu = ttk.OptionMenu(top, self.persona_var, self.persona_var.get(), *PERSONAS)
        persona_menu.grid(row=0, column=1, sticky="w", padx=(8, 12))

        self.send_button = ttk.Button(top, text="Send", command=self.send)
        self.send_button.grid(row=0, column=2, padx=4)
        ttk.Button(top, text="Check Model", command=self.check_model).grid(row=0, column=3, padx=4)
        ttk.Button(top, text="Clear Chat", command=self.clear_chat).grid(row=0, column=5, padx=(12, 0))

        notebook = ttk.Notebook(self.root)
        notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)

        self.chat_tab = ttk.Frame(notebook)
        self.system_tab = ttk.Frame(notebook)
        self.history_tab = ttk.Frame(notebook)
        self.metadata_tab = ttk.Frame(notebook)
        self.reports_tab = ttk.Frame(notebook)

        notebook.add(self.chat_tab, text="Chat")
        notebook.add(self.system_tab, text="System")
        notebook.add(self.history_tab, text="History")
        notebook.add(self.metadata_tab, text="Metadata")
        notebook.add(self.reports_tab, text="Reports")

        self._build_chat_tab()
        self._build_system_tab()
        self._build_history_tab()
        self._build_metadata_tab()
        self._build_reports_tab()

        bottom = ttk.Frame(self.root, padding=(12, 6, 12, 12))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.columnconfigure(2, weight=1)
        ttk.Label(bottom, textvariable=self.status_var, anchor=tk.W).grid(row=0, column=0, sticky="ew")
        ttk.Label(bottom, textvariable=self.route_var, anchor=tk.W).grid(row=0, column=1, sticky="ew", padx=10)
        ttk.Label(bottom, textvariable=self.gateway_var, anchor=tk.W).grid(row=0, column=2, sticky="ew")

    def _build_chat_tab(self) -> None:
        self.chat_tab.columnconfigure(0, weight=1)
        self.chat_tab.rowconfigure(0, weight=1)

        body = ttk.PanedWindow(self.chat_tab, orient=tk.VERTICAL)
        body.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        prompt_frame = ttk.Frame(body)
        prompt_frame.columnconfigure(0, weight=1)
        prompt_frame.rowconfigure(1, weight=1)
        ttk.Label(prompt_frame, text="Prompt").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.prompt = tk.Text(prompt_frame, height=8, wrap=tk.WORD, undo=True)
        self.prompt.grid(row=1, column=0, sticky="nsew")
        self._add_scrollbar(prompt_frame, self.prompt, row=1, column=1)

        response_frame = ttk.Frame(body)
        response_frame.columnconfigure(0, weight=1)
        response_frame.rowconfigure(1, weight=1)
        ttk.Label(response_frame, text="Response").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.response = tk.Text(response_frame, height=20, wrap=tk.WORD)
        self.response.grid(row=1, column=0, sticky="nsew")
        self._add_scrollbar(response_frame, self.response, row=1, column=1)

        body.add(prompt_frame, weight=1)
        body.add(response_frame, weight=4)
        self.prompt.bind("<Control-Return>", lambda _event: self.send())

    def _build_system_tab(self) -> None:
        self.system_tab.columnconfigure(0, weight=1)
        self.system_tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(self.system_tab)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ttk.Button(controls, text="Refresh System", command=self.refresh_system_info).grid(row=0, column=0, padx=3)
        ttk.Button(controls, text="Check Model", command=self.check_model).grid(row=0, column=1, padx=3)

        self.system_output = tk.Text(self.system_tab, wrap=tk.WORD)
        self.system_output.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._add_scrollbar(self.system_tab, self.system_output, row=1, column=1)

    def _build_history_tab(self) -> None:
        self.history_tab.columnconfigure(0, weight=1)
        self.history_tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(self.history_tab)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ttk.Button(controls, text="Refresh History", command=self.refresh_history).grid(row=0, column=0, padx=3)
        ttk.Button(controls, text="Recent Errors", command=self.refresh_errors).grid(row=0, column=1, padx=3)

        self.history_output = tk.Text(self.history_tab, wrap=tk.WORD)
        self.history_output.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._add_scrollbar(self.history_tab, self.history_output, row=1, column=1)

    def _build_metadata_tab(self) -> None:
        self.metadata_tab.columnconfigure(0, weight=1)
        self.metadata_tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(self.metadata_tab)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ttk.Button(controls, text="Show Last Exchange", command=self.refresh_metadata).grid(row=0, column=0, padx=3)

        self.metadata_output = tk.Text(self.metadata_tab, wrap=tk.WORD)
        self.metadata_output.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._add_scrollbar(self.metadata_tab, self.metadata_output, row=1, column=1)

    def _build_reports_tab(self) -> None:
        self.reports_tab.columnconfigure(0, weight=1)
        self.reports_tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(self.reports_tab)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ttk.Button(controls, text="Summarize Logs", command=self.summarize_logs).grid(row=0, column=0, padx=3)
        ttk.Button(controls, text="Self Assessment", command=self.run_self_assessment).grid(row=0, column=1, padx=3)

        self.reports_output = tk.Text(self.reports_tab, wrap=tk.WORD)
        self.reports_output.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._add_scrollbar(self.reports_tab, self.reports_output, row=1, column=1)

    def _add_scrollbar(self, parent: ttk.Frame, widget: tk.Text, row: int, column: int) -> None:
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=widget.yview)
        scrollbar.grid(row=row, column=column, sticky="ns")
        widget.configure(yscrollcommand=scrollbar.set)

    def send(self) -> None:
        if self.busy:
            return

        raw_text = self.prompt.get("1.0", tk.END).strip()
        if not raw_text:
            self.status_var.set("No prompt entered.")
            return

        self._set_busy(True, "Routing prompt...")
        threading.Thread(target=self._send_worker, args=(raw_text,), daemon=True).start()

    def _send_worker(self, raw_text: str) -> None:
        try:
            metadata = {
                "interface": "desktop_client",
                "selected_persona": self._selected_persona_id(),
                "prompt_interpreter_enabled": False,
            }
            envelope = self.envelope_service.create(
                user_text=raw_text,
                source="desktop_client",
                metadata=metadata,
            )
            route = self.router.route(envelope)
            self._after(lambda: self._show_route(route, "Calling local model..."))

            result = self.orchestrator.handle(envelope=envelope, route=route)
            self.logger.log_session_event(
                {
                    "event_type": "desktop_interaction_complete",
                    "envelope": envelope.to_dict(),
                    "route": route,
                    "response_meta": result.meta,
                }
            )
            self._after(lambda: self._show_result(envelope, route, result))
        except Exception as exc:
            self._after(lambda error=exc: self._show_error(error))

    def _selected_persona_id(self) -> str:
        return PERSONAS.get(self.persona_var.get(), "proto_jane")

    def _show_route(self, route: dict[str, Any], status: str) -> None:
        self.status_var.set(status)
        self.route_var.set(
            f"Route: {route.get('task_type')} / {route.get('persona')} / confidence {route.get('confidence')}"
        )

    def _show_result(
        self,
        envelope: PromptEnvelope,
        route: dict[str, Any],
        result: OrchestrationResponse,
    ) -> None:
        self.last_envelope = envelope
        self.last_route = route
        self.last_response = result

        self.response.delete("1.0", tk.END)
        self.response.insert(tk.END, result.visible_text)

        llm = result.meta.get("llm", {})
        model = llm.get("model", "(unknown)")
        error = llm.get("error", "")
        self.gateway_var.set(f"Gateway: {model}" if not error else "Gateway: fallback used")
        self.status_var.set("Complete." if not error else "Complete with gateway fallback.")
        self.refresh_metadata()
        self._set_busy(False)

    def _show_error(self, exc: Exception) -> None:
        self.response.delete("1.0", tk.END)
        self.response.insert(tk.END, f"Desktop client error:\n{exc}")
        self.status_var.set("Stopped on error.")
        self.gateway_var.set("Gateway: not completed")
        self._set_busy(False)

    def check_model(self) -> None:
        if self.busy:
            return

        self._set_busy(True, "Checking local model server...")
        threading.Thread(target=self._check_model_worker, daemon=True).start()

    def _check_model_worker(self) -> None:
        diagnostics = self.orchestrator.llm.diagnostics()
        self._after(lambda: self._show_diagnostics(diagnostics))

    def _show_diagnostics(self, diagnostics: dict[str, Any]) -> None:
        server_ok = diagnostics.get("server_reachable", False)
        resolved = diagnostics.get("resolved_model") or "(auto on first send)"
        self.gateway_var.set(f"Gateway: {resolved}" if server_ok else "Gateway: unreachable")
        self.status_var.set("Model server reachable." if server_ok else "Model server check failed.")
        self._write_text(self.system_output, json.dumps(diagnostics, indent=2))
        self._set_busy(False)

    def refresh_system_info(self) -> None:
        info = {
            "project_root": str(PROJECT_ROOT),
            "desktop_persona": self.persona_var.get(),
            "desktop_persona_id": self._selected_persona_id(),
            "prompt_interpreter": "reserved for future STT voice layer",
            "routing": "deterministic regex router",
            "gateway": {
                "base_url": self.orchestrator.llm.base_url,
                "configured_model": self.orchestrator.llm.model,
                "resolved_model": self.orchestrator.llm._resolved_model,
            },
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._write_text(self.system_output, json.dumps(info, indent=2))

    def refresh_history(self) -> None:
        self._write_text(self.history_output, self._read_recent_jsonl("Session_Logs", "session", limit=30))

    def refresh_errors(self) -> None:
        self._write_text(self.history_output, self._read_recent_jsonl("Error_Logs", "error", limit=30))

    def refresh_metadata(self) -> None:
        if not self.last_envelope or not self.last_route or not self.last_response:
            self._write_text(self.metadata_output, "No exchange has completed yet.")
            return

        payload = {
            "envelope": self.last_envelope.to_dict(),
            "route": self.last_route,
            "response_meta": self.last_response.meta,
        }
        self._write_text(self.metadata_output, json.dumps(payload, indent=2))

    def summarize_logs(self) -> None:
        self._write_text(self.reports_output, self.orchestrator.log_summarizer.summarize_recent_logs())

    def run_self_assessment(self) -> None:
        self._write_text(self.reports_output, self.orchestrator.self_assessment.run_self_assessment())

    def _read_recent_jsonl(self, folder_name: str, prefix: str, limit: int) -> str:
        folder = PROJECT_ROOT / "System_Logging" / folder_name
        files = sorted(folder.glob(f"{prefix}_*.jsonl"), reverse=True)
        if not files:
            return "No logs found."

        rows: list[str] = []
        for file_path in files[:5]:
            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError as exc:
                rows.append(f"{file_path.name}: {exc}")
                continue

            for line in lines[-limit:]:
                rows.append(line)
                if len(rows) >= limit:
                    return "\n".join(rows)

        return "\n".join(rows) if rows else "No logs found."

    def clear_chat(self) -> None:
        self.prompt.delete("1.0", tk.END)
        self.response.delete("1.0", tk.END)
        self.status_var.set("Ready.")
        self.route_var.set("Route: waiting")

    def _write_text(self, widget: tk.Text, text: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)

    def _set_busy(self, busy: bool, status: str | None = None) -> None:
        self.busy = busy
        self.send_button.configure(state=tk.DISABLED if busy else tk.NORMAL)
        if status:
            self.status_var.set(status)

    def _after(self, callback: Callable[[], None]) -> None:
        self.root.after(0, callback)


def main() -> None:
    root = tk.Tk()
    VailaDesktopClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()
