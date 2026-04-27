"""Stable ASGI entrypoint wrapper with safe fallback mode."""

from __future__ import annotations

import importlib
from types import ModuleType

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


def _export_module_symbols(module: ModuleType) -> None:
    exported = getattr(module, "__all__", None)
    if exported is None:
        exported = [name for name in module.__dict__ if not name.startswith("_")]
    for name in exported:
        if name == "app":
            continue
        globals()[name] = getattr(module, name)


def _load_app() -> FastAPI:
    try:
        module = importlib.import_module("application")
        _export_module_symbols(module)
        return module.app
    except Exception as exc:  # noqa: BLE001
        return _fallback_startup_app(exc)


app = _load_app()