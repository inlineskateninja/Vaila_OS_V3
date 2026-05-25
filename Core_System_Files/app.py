from __future__ import annotations

import sys
import os
import time
import socket
import threading
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def find_free_port(start_port: int) -> int:
    """Finds a free TCP port starting from start_port."""
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Connect_ex returns 0 if connection succeeds (port in use)
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
        port += 1
    return start_port


def launch_web_gui() -> None:
    import uvicorn

    server_host = os.getenv("VAILA_SERVER_HOST", "127.0.0.1").strip() or "127.0.0.1"
    display_host = "127.0.0.1" if server_host == "0.0.0.0" else server_host
    start_port = int(os.getenv("VAILA_SERVER_PORT", "8765"))
    port = find_free_port(start_port)

    if port != start_port:
        print(f"\n[Vaila OS] Port {start_port} is already in use by another process.")
        print(f"[Vaila OS] Redirecting automatically to free port: {port}")
    else:
        print(f"\n[Vaila OS] Port {port} is free and ready.")

    print("\n[Vaila OS] Launching Web GUI...")
    print(f"Local Server Address: http://{display_host}:{port}")
    
    # Background thread to open default web browser after uvicorn initializes
    def browser_trigger() -> None:
        time.sleep(1.5)
        print(f"[Vaila OS] Auto-opening web browser to http://{display_host}:{port}...")
        webbrowser.open(f"http://{display_host}:{port}")
        
    threading.Thread(target=browser_trigger, daemon=True).start()

    # Start FastAPI server on the resolved free port
    uvicorn.run(
        "Core_System_Files.local_api:app",
        host=server_host,
        port=port,
        log_level="info",
        reload=False
    )


def main() -> None:
    print("\n=======================================================")
    print("               VAILA OS V3 // STARTUP MENU             ")
    print("=======================================================")
    print("  [1] CLI Mode (Interactive Text Terminal)")
    print("  [2] Web GUI Mode (FastAPI Cyberpunk Interface) [RECOMMENDED]")
    print("  [3] Desktop Client Mode (Legacy Tkinter Interface)")
    print("  [4] Exit")
    print("=======================================================")

    while True:
        try:
            choice = input("Select interface mode (1-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nShutdown requested.")
            sys.exit(0)

        if choice == "1":
            print("\n[Vaila OS] Booting CLI mode...\n")
            from Core_System_Files.cli import run_cli
            run_cli(project_root=PROJECT_ROOT)
            break
        elif choice == "2":
            launch_web_gui()
            break
        elif choice == "3":
            print("\n[Vaila OS] Booting Tkinter Desktop client...\n")
            from Core_System_Files.desktop_client import main as run_desktop
            run_desktop()
            break
        elif choice == "4" or choice.lower() in {"exit", "quit"}:
            print("\nShutting down. Farewell.")
            sys.exit(0)
        else:
            print("Invalid selection. Please enter 1, 2, 3, or 4.")


if __name__ == "__main__":
    main()
