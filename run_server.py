"""Startup wrapper for CodexSIEM.

Runs `startup_launcher.py` when parseable; otherwise falls back to direct
`uvicorn main:app` startup so launcher-file corruption does not fully block
service boot.
"""

from __future__ import annotations

import argparse
import py_compile
import runpy
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _fallback_start() -> int:
    parser = argparse.ArgumentParser(description="Fallback starter for CodexSIEM.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default="8000")
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--auto-recover", action="store_true")
    args = parser.parse_args()

    if args.auto_recover:
        repair_cmd = (
            sys.executable,
            str(ROOT / "scripts" / "repair_entrypoints.py"),
            "--include-application",
        )
        repair = subprocess.call(repair_cmd, cwd=ROOT)
        if repair == 0:
            launcher_path = ROOT / "startup_launcher.py"
            try:
                py_compile.compile(str(launcher_path), doraise=True)
                runpy.run_path(str(launcher_path), run_name="__main__")
                return 0
            except py_compile.PyCompileError as exc:
                print(f"Auto-recover could not repair startup_launcher.py: {exc.msg}", file=sys.stderr)
        else:
            print("Auto-recover command failed before startup.", file=sys.stderr)

    cmd = (
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    )
    if args.reload:
        cmd = cmd + ("--reload",)
    try:
        return subprocess.call(cmd, cwd=ROOT)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    launcher_path = ROOT / "startup_launcher.py"
    try:
        py_compile.compile(str(launcher_path), doraise=True)
        runpy.run_path(str(launcher_path), run_name="__main__")
    except py_compile.PyCompileError as exc:
        print(f"Warning: startup_launcher.py is not parseable: {exc.msg}", file=sys.stderr)
        print("Falling back to direct uvicorn startup path.", file=sys.stderr)
        raise SystemExit(_fallback_start())
