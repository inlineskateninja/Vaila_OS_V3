from __future__ import annotations

import json
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from System_Services.envelope_service import EnvelopeService
from System_Services.logging_service import LoggingService
from System_Services.orchestration_service import OrchestrationResponse, OrchestrationService
from System_Services.router_service import RouterService

PERSONAS = ["Auto", "Proto Jane", "Serren", "Maelith", "Vecht", "Riven"]


class VailaDesktopClient:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Vaila OS V3")
        self.root.geometry("1080x760")
        self.root.minsize(900, 620)

        self.logger = LoggingService(project_root=PROJECT_ROOT)
        self.envelope_service = EnvelopeService(project_root=PROJECT_ROOT)
        self.router = RouterService(project_root=PROJECT_ROOT)
        self.orchestrator = OrchestrationService(project_root=PROJECT_ROOT, logger=self.logger)

        self.persona_var = tk.StringVar(value="Auto")
        self.status_var = tk.StringVar(value="Ready.")
        self.route_var = tk.StringVar(value="Route: waiting")
        self.gateway_var = tk.StringVar(value="Gateway: not checked")
        self.busy = False

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
        ttk.Button(top, text="Clear", command=self.clear).grid(row=0, column=5, padx=(12, 0))

        body = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)

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
        self.response = tk.Text(response_frame, height=18, wrap=tk.WORD)
        self.response.grid(row=1, column=0, sticky="nsew")
        self._add_scrollbar(response_frame, self.response, row=1, column=1)

        body.add(prompt_frame, weight=1)
        body.add(response_frame, weight=4)

        bottom = ttk.Frame(self.root, padding=(12, 6, 12, 12))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.columnconfigure(2, weight=1)
        ttk.Label(bottom, textvariable=self.status_var, anchor=tk.W).grid(row=0, column=0, sticky="ew")
        ttk.Label(bottom, textvariable=self.route_var, anchor=tk.W).grid(row=0, column=1, sticky="ew", padx=10)
        ttk.Label(bottom, textvariable=self.gateway_var, anchor=tk.W).grid(row=0, column=2, sticky="ew")

        self.prompt.bind("<Control-Return>", lambda _event: self.send())

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
            envelope = self.envelope_service.create(user_text=self._apply_persona(raw_text), source="desktop_client")
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
            self._after(lambda: self._show_result(result))
        except Exception as exc:
            self._after(lambda error=exc: self._show_error(error))

    def _apply_persona(self, raw_text: str) -> str:
        persona = self.persona_var.get()
        return raw_text if persona == "Auto" else f"{persona}, {raw_text}"

    def _show_route(self, route: dict[str, Any], status: str) -> None:
        self.status_var.set(status)
        self.route_var.set(
            f"Route: {route.get('task_type')} / {route.get('persona')} / confidence {route.get('confidence')}"
        )

    def _show_result(self, result: OrchestrationResponse) -> None:
        self.response.delete("1.0", tk.END)
        self.response.insert(tk.END, result.visible_text)

        llm = result.meta.get("llm", {})
        model = llm.get("model", "(unknown)")
        error = llm.get("error", "")
        self.gateway_var.set(f"Gateway: {model}" if not error else "Gateway: fallback used")
        self.status_var.set("Complete." if not error else "Complete with gateway fallback.")
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

        self.response.delete("1.0", tk.END)
        self.response.insert(tk.END, json.dumps(diagnostics, indent=2))
        self._set_busy(False)

    def clear(self) -> None:
        self.prompt.delete("1.0", tk.END)
        self.response.delete("1.0", tk.END)
        self.status_var.set("Ready.")
        self.route_var.set("Route: waiting")

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
