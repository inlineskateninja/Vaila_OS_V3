from __future__ import annotations

import sys
from pathlib import Path

import uvicorn


BACKEND_ROOT = Path(__file__).resolve().parent / "system_services" / "python_backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.service import app


def main() -> None:
    uvicorn.run("app.service:app", host="127.0.0.1", port=8765, reload=True)


if __name__ == "__main__":
    main()
