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
    Path("startup_checks.py"),
]

FORBIDDEN_APP_SNIPPETS = [
    "Template startup self-check found failures but strict mode is disabled",
    "Template syntax error during startup check",
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

    app_source_issues: list[str] = []
    app_source = Path("app.py").read_text()
    for snippet in FORBIDDEN_APP_SNIPPETS:
        if snippet in app_source:
            app_source_issues.append(f"app.py contains forbidden startup-check implementation snippet: {snippet}")

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
