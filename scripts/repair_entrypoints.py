"""Rewrite entrypoint wrapper files to known-good templates."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

TEMPLATES = {
    "app.py": '''"""Stable ASGI entrypoint wrapper with safe fallback mode."""

import importlib

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse


def _fallback_startup_app(exc: Exception) -> FastAPI:
    fallback = FastAPI(title="CodexSIEM Startup Error")

    @fallback.get("/", response_class=PlainTextResponse)
    async def startup_error() -> str:
        return (
            "CodexSIEM failed to import application.py at startup.\\n"
            f"Error: {exc}\\n"
            "Recovery: run `python run_server.py --auto-recover --host 0.0.0.0 --port 8000`.\\n"
        )

    return fallback


def _load_app() -> FastAPI:
    try:
        module = importlib.import_module("application")
        return module.app
    except Exception as exc:  # noqa: BLE001
        return _fallback_startup_app(exc)


app = _load_app()
''',
    "main.py": '''"""Alternative ASGI entrypoint wrapper with safe fallback mode."""

import importlib

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse


def _fallback_startup_app(exc: Exception) -> FastAPI:
    fallback = FastAPI(title="CodexSIEM Startup Error")

    @fallback.get("/", response_class=PlainTextResponse)
    async def startup_error() -> str:
        return (
            "CodexSIEM failed to import application.py at startup.\\n"
            f"Error: {exc}\\n"
            "Recovery: run `python run_server.py --auto-recover --host 0.0.0.0 --port 8000`.\\n"
        )

    return fallback


def _load_app() -> FastAPI:
    try:
        module = importlib.import_module("application")
        return module.app
    except Exception as exc:  # noqa: BLE001
        return _fallback_startup_app(exc)


app = _load_app()
''',
    "run_server.py": '''"""Startup wrapper for CodexSIEM.

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
''',
    "scripts/run_server.py": '''"""Backward-compatible thin wrapper for CodexSIEM startup."""

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    runpy.run_path(str(root / "run_server.py"), run_name="__main__")
''',
}


def main() -> int:
    for relative_path, content in TEMPLATES.items():
        path = ROOT / relative_path
        path.write_text(content, encoding="utf-8")
        print(f"Repaired {relative_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
