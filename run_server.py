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
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _try_compile(path: Path) -> bool:
    try:
        py_compile.compile(str(path), doraise=True)
        return True
    except py_compile.PyCompileError as exc:
        print(f"Warning: {path.name} is not parseable: {exc.msg}", file=sys.stderr)
        return False


def _run_repair(include_application: bool) -> int:
    repair_cmd = [sys.executable, str(ROOT / "scripts" / "repair_entrypoints.py")]
    if include_application:
        repair_cmd.append("--include-application")
    return subprocess.call(tuple(repair_cmd), cwd=ROOT)


def _run_emergency_error_app(host: str, port: str, reload_enabled: bool) -> int:
    with tempfile.TemporaryDirectory(prefix="codexsiem_emergency_") as tempdir:
        emergency_path = Path(tempdir) / "emergency_app.py"
        emergency_path.write_text(
            """from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
app = FastAPI(title='CodexSIEM Emergency Startup Fallback')
@app.get('/', response_class=PlainTextResponse)
async def root() -> str:
    return 'CodexSIEM startup wrappers are damaged. Run: python scripts/repair_entrypoints.py --include-application'
""",
            encoding="utf-8",
        )
        cmd = (
            sys.executable,
            "-m",
            "uvicorn",
            "emergency_app:app",
            "--app-dir",
            tempdir,
            "--host",
            host,
            "--port",
            str(port),
        )
        if reload_enabled:
            cmd = cmd + ("--reload",)
        try:
            return subprocess.call(cmd, cwd=ROOT)
        except KeyboardInterrupt:
            return 130


def _fallback_start() -> int:
    parser = argparse.ArgumentParser(description="Fallback starter for CodexSIEM.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default="8000")
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--auto-recover", action="store_true")
    args = parser.parse_args()

    if args.auto_recover:
        repair = _run_repair(include_application=True)
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

    if not _try_compile(ROOT / "main.py"):
        print("Attempting wrapper-only repair before fallback uvicorn startup.", file=sys.stderr)
        if _run_repair(include_application=False) == 0 and _try_compile(ROOT / "main.py"):
            print("Wrapper-only repair succeeded.", file=sys.stderr)
        else:
            print("Wrapper repair failed; starting emergency fallback app.", file=sys.stderr)
            return _run_emergency_error_app(args.host, str(args.port), args.reload)
    args = parser.parse_args()

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
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    launcher_path = ROOT / "startup_launcher.py"
    try:
        py_compile.compile(str(launcher_path), doraise=True)
        runpy.run_path(str(launcher_path), run_name="__main__")
    except py_compile.PyCompileError as exc:
        print(f"Warning: startup_launcher.py is not parseable: {exc.msg}", file=sys.stderr)
        print("Falling back to direct uvicorn startup path.", file=sys.stderr)
        raise SystemExit(_fallback_start())
"""Thin startup wrapper for CodexSIEM."""

from startup_launcher import main


if __name__ == "__main__":
    raise SystemExit(main())
