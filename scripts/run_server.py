"""Backward-compatible thin wrapper for CodexSIEM startup."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from startup_launcher import main


if __name__ == "__main__":
    raise SystemExit(main())
