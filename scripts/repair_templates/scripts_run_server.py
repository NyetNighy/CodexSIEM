"""Backward-compatible thin wrapper for CodexSIEM startup."""

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    runpy.run_path(str(root / "run_server.py"), run_name="__main__")
