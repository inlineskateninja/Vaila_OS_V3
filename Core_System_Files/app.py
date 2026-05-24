from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Core_System_Files.cli import run_cli


def main() -> None:
    print("Vaila OS V3 starting...")
    print(f"Project root: {PROJECT_ROOT}")
    run_cli(project_root=PROJECT_ROOT)


if __name__ == "__main__":
    main()
