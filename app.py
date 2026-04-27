from __future__ import annotations
import importlib; from types import ModuleType
from fastapi import FastAPI; from fastapi.responses import PlainTextResponse

def _fallback_startup_app(exc: Exception) -> FastAPI:
    f = FastAPI(title="CodexSIEM Startup Error")
    @f.get("/", response_class=PlainTextResponse)
    async def startup_error() -> str:
        return f"CodexSIEM failed to import application.py at startup.\nError: {exc}\nRecovery: run `python run_server.py --auto-recover --host 0.0.0.0 --port 8000`."
    return f

def _export_module_symbols(module: ModuleType) -> None:
    for name in getattr(module, "__all__", [n for n in module.__dict__ if not n.startswith("_")]):
        if name != "app": globals()[name] = getattr(module, name)

def _load_app() -> FastAPI:
    try:
        module = importlib.import_module("application")
        _export_module_symbols(module)
        return module.app
    except Exception as exc:  # noqa: BLE001
        return _fallback_startup_app(exc)

app = _load_app()
from application import *  # noqa: F401,F403