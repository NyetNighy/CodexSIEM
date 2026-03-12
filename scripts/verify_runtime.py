"""Simple runtime dependency and syntax check for CodexSIEM."""

import importlib
import py_compile
from pathlib import Path

REQUIRED = [
    "fastapi",
    "uvicorn",
    "httpx",
    "jinja2",
    "multipart",
    "itsdangerous",
]

PYTHON_SOURCES = [
    Path("app.py"),
    Path("auth.py"),
    Path("secret_utils.py"),
    Path("siem_core.py"),
]


def main() -> int:
    missing: list[str] = []
    for module in REQUIRED:
        try:
            importlib.import_module(module)
        except Exception:
            missing.append(module)

    syntax_errors: list[str] = []
    for source in PYTHON_SOURCES:
        try:
            py_compile.compile(str(source), doraise=True)
        except py_compile.PyCompileError as exc:
            syntax_errors.append(f"{source}: {exc.msg}")

    if not missing and not syntax_errors:
        print("Runtime dependency and syntax check passed.")
        return 0

    if missing:
        print("Missing modules:", ", ".join(missing))
        print("Run: pip install -r requirements.txt")

    if syntax_errors:
        print("Syntax/compile errors detected:")
        for err in syntax_errors:
            print(f" - {err}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
