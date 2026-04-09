"""Alternative ASGI entrypoint wrapper with safe fallback mode."""

import importlib

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse


def _fallback_startup_app(exc: Exception) -> FastAPI:
    fallback = FastAPI(title="CodexSIEM Startup Error")

    @fallback.get("/", response_class=PlainTextResponse)
    async def startup_error() -> str:
        return (
            "CodexSIEM failed to import application.py at startup.\n"
            f"Error: {exc}\n"
            "Recovery: run `python run_server.py --auto-recover --host 0.0.0.0 --port 8000`.\n"
        )

    return fallback


def _load_app() -> FastAPI:
    try:
        module = importlib.import_module("application")
        return module.app
    except Exception as exc:  # noqa: BLE001
        return _fallback_startup_app(exc)


app = _load_app()
"""Alternative stable ASGI entrypoint wrapper.

Use `uvicorn main:app` for operational startup to avoid accidental local
merge-conflict breakage in `app.py`.
"""

from application import *  # noqa: F401,F403
