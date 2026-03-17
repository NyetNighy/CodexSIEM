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
    Path("application.py"),
    Path("auth.py"),
    Path("secret_utils.py"),
    Path("siem_core.py"),
    Path("startup_checks.py"),
]

FORBIDDEN_STARTUP_SNIPPETS = [
    "Template startup self-check found failures but strict mode is disabled",
    "Template syntax error during startup check",
]

ENTRYPOINT_MAX_LINES = 20


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

    app_source_issues: list[str] = []

    entrypoint_source = Path("app.py").read_text()
    if "from application import *" not in entrypoint_source:
        app_source_issues.append("app.py must import and re-export from application.py")
    if len(entrypoint_source.splitlines()) > ENTRYPOINT_MAX_LINES:
        app_source_issues.append("app.py entrypoint wrapper is too large; keep it thin to avoid merge indentation regressions")
    for snippet in FORBIDDEN_STARTUP_SNIPPETS:
        if snippet in entrypoint_source:
            app_source_issues.append(f"app.py contains forbidden startup-check implementation snippet: {snippet}")

    app_impl_source = Path("application.py").read_text()
    for snippet in FORBIDDEN_STARTUP_SNIPPETS:
        if snippet in app_impl_source:
            app_source_issues.append(f"application.py contains forbidden startup-check implementation snippet: {snippet}")

    if not missing and not syntax_errors and not app_source_issues:
        print("Runtime dependency and syntax check passed.")
        return 0

    if missing:
        print("Missing modules:", ", ".join(missing))
        print("Run: pip install -r requirements.txt")

    if syntax_errors:
        print("Syntax/compile errors detected:")
        for err in syntax_errors:
            print(f" - {err}")

    if app_source_issues:
        print("App source guard errors detected:")
        for issue in app_source_issues:
            print(f" - {issue}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
