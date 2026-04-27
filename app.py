from application import *  # noqa: F401,F403
import importlib
from types import ModuleType
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

def _fallback_startup_app(exc: Exception) -> FastAPI:
    f = FastAPI(title="CodexSIEM Startup Error")
    @f.get("/", response_class=PlainTextResponse)
    async def startup_error() -> str:
        return f"CodexSIEM startup failed: {exc}"
    return f

def _export(module: ModuleType) -> None:
    for n in getattr(module, "__all__", [x for x in module.__dict__ if not x.startswith("_")]):
        if n != "app": globals()[n] = getattr(module, n)

def _load_app() -> FastAPI:
    try:
        m = importlib.import_module("application")
        _export(m)
        return m.app
    except Exception as exc:  # noqa: BLE001
        return _fallback_startup_app(exc)

app = _load_app()