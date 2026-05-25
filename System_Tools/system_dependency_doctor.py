from __future__ import annotations

import importlib
import os
import sys
import socket
from pathlib import Path
from typing import Any


class SystemDependencyDoctor:
    """
    Checks Python paths, missing packages, import health, .env sanity,
    service reachability, and startup readiness.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.requirements_path = project_root / "requirements.txt"
        self.env_path = project_root / ".env"
        self.env_example_path = project_root / ".env.example"

    def run_diagnostics(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "python_version": sys.version,
            "python_executable": sys.executable,
            "python_path": sys.path,
            "requirements_health": {},
            "env_health": {},
            "services_reachability": {},
            "readiness": True
        }

        # 1. Check requirements packages and test import health
        if self.requirements_path.exists():
            lines = self.requirements_path.read_text(encoding="utf-8").splitlines()
            reqs = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Split on comparison operators
                pkg = line.split(">")[0].split("<")[0].split("=")[0].strip()
                reqs.append(pkg)

            # Map package names to import names
            import_mapping = {
                "python-dotenv": "dotenv",
                "python-multipart": "multipart"
            }

            import_status = {}
            for req in reqs:
                import_name = import_mapping.get(req.lower(), req.replace("-", "_"))
                try:
                    importlib.import_module(import_name)
                    import_status[req] = {"installed": True, "importable": True, "error": None}
                except ImportError as exc:
                    import_status[req] = {"installed": False, "importable": False, "error": str(exc)}
                    report["readiness"] = False

            report["requirements_health"] = {
                "file_present": True,
                "status": import_status
            }
        else:
            report["requirements_health"] = {
                "file_present": False,
                "status": {}
            }
            report["readiness"] = False

        # 2. Check .env variables sanity
        env_vars = {}
        env_example_keys = []
        if self.env_example_path.exists():
            lines = self.env_example_path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key = line.split("=")[0].strip()
                env_example_keys.append(key)

        missing_keys = []
        configured_keys = {}
        for key in env_example_keys:
            val = os.getenv(key)
            if val is None:
                missing_keys.append(key)
                configured_keys[key] = "(missing)"
            else:
                configured_keys[key] = "(set)" if "key" in key.lower() or "secret" in key.lower() or "token" in key.lower() else val

        report["env_health"] = {
            "env_file_exists": self.env_path.exists(),
            "missing_keys": missing_keys,
            "configured_keys": configured_keys
        }
        if missing_keys:
            # We don't fail immediately for missing optional keys, but flag warning
            pass

        # 3. Check service reachability
        # Probe LLM Gateway (LM Studio default is usually localhost:1234 or configured)
        llm_base_url = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
        llm_host = "127.0.0.1"
        llm_port = 1234

        if "localhost" in llm_base_url or "127.0.0.1" in llm_base_url:
            # Try to parse port
            import re
            port_match = re.search(r":(\d+)", llm_base_url)
            if port_match:
                llm_port = int(port_match.group(1))

        # Check LLM socket
        llm_reachable = self._probe_port(llm_host, llm_port)
        
        # Check n8n workflow port (default 5678)
        n8n_reachable = self._probe_port("127.0.0.1", 5678)

        report["services_reachability"] = {
            "llm_gateway": {
                "configured_url": llm_base_url,
                "port_probed": llm_port,
                "reachable": llm_reachable
            },
            "n8n_service": {
                "port_probed": 5678,
                "reachable": n8n_reachable
            }
        }

        return report

    def render_report(self) -> str:
        rep = self.run_diagnostics()
        status_symbol = "🟢" if rep["readiness"] else "🔴"
        
        lines = [
            f"# Vaila OS Dependency Doctor {status_symbol}",
            "",
            "## Environment & Platform Info",
            f"- Python Executable: `{rep['python_executable']}`",
            f"- Python Version: `{rep['python_version'].splitlines()[0]}`",
            ""
        ]

        lines.append("## 📦 Package Import Integrity")
        req_health = rep["requirements_health"]
        if req_health["file_present"]:
            for pkg, stat in req_health["status"].items():
                icon = "✅" if stat["importable"] else "❌"
                err_info = f" (Error: {stat['error']})" if stat["error"] else ""
                lines.append(f"- {icon} **{pkg}**: Installed & Importable{err_info}")
        else:
            lines.append("- ❌ `requirements.txt` is missing from the workspace root.")
        lines.append("")

        lines.append("## 🔑 Environment Configuration (.env)")
        env_health = rep["env_health"]
        if env_health["env_file_exists"]:
            lines.append("- ✅ `.env` file detected.")
            if env_health["missing_keys"]:
                lines.append(f"- ⚠️ **Missing Keys (configured in .env.example but not in .env)**: {', '.join(env_health['missing_keys'])}")
            else:
                lines.append("- ✅ All keys from `.env.example` are present in `.env`.")
        else:
            lines.append("- ❌ `.env` file is missing. Please copy `.env.example` to `.env`.")
        lines.append("")

        lines.append("## 🌐 Service Reachability Probes")
        reach = rep["services_reachability"]
        llm = reach["llm_gateway"]
        lines.append(f"- {'✅' if llm['reachable'] else '⚠️'} **LLM Gateway** (URL: `{llm['configured_url']}`): {'REACHABLE' if llm['reachable'] else 'UNREACHABLE (check if LM Studio / Ollama is running)'}")
        
        n8n = reach["n8n_service"]
        lines.append(f"- {'✅' if n8n['reachable'] else '⚠️'} **n8n Workflow Service** (Port: `5678`): {'REACHABLE' if n8n['reachable'] else 'UNREACHABLE (check if n8n server is started)'}")

        lines.append("")
        lines.append("## 🚀 Startup Readiness Summary")
        if rep["readiness"]:
            lines.append("✅ **READY**: Vaila OS has all required packages importable and is ready to load.")
        else:
            lines.append("❌ **NOT READY**: One or more critical dependencies are missing or unimportable. Run `pip install -r requirements.txt` to fix.")

        return "\n".join(lines)

    def _probe_port(self, host: str, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.8)
                return s.connect_ex((host, port)) == 0
        except Exception:
            return False
