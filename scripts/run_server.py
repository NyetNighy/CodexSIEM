"""Preflight launcher for CodexSIEM.

Runs runtime verification first, then starts uvicorn only if checks pass.
Use this in deployments to surface syntax/import issues before ASGI boot.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CodexSIEM with preflight runtime checks.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default="8000")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    verify_cmd = [sys.executable, str(ROOT / "scripts" / "verify_runtime.py")]
    verify = subprocess.run(verify_cmd, cwd=ROOT)
    if verify.returncode != 0:
        print("Preflight failed. Fix the issues above before starting uvicorn.", file=sys.stderr)
        return verify.returncode

    uvicorn_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        uvicorn_cmd.append("--reload")

    try:
        return subprocess.call(uvicorn_cmd, cwd=ROOT)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
