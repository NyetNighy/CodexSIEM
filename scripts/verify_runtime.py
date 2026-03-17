"""Simple runtime dependency and syntax check for CodexSIEM."""

import ast
import importlib
import sys
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    Path("main.py"),
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


def _validate_dashboard_signature(source: str) -> tuple[list[str], str]:
    issues: list[str] = []
    detected_signature = "<unavailable>"
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"application.py AST parse failed: {exc}"], detected_signature

    dashboard_nodes = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "dashboard"]
    if not dashboard_nodes:
        return ["dashboard() function not found in application.py"], detected_signature

    node = dashboard_nodes[0]
    arg_names = [a.arg for a in node.args.args]
    defaults = ["<no-default>"] * (len(arg_names) - len(node.args.defaults)) + [ast.unparse(d) if hasattr(ast, "unparse") else "<default>" for d in node.args.defaults]
    detected_signature = "dashboard(" + ", ".join(f"{n}={d}" for n, d in zip(arg_names, defaults)) + ")"

    if "info" not in arg_names:
        issues.append("dashboard() is missing expected 'info' parameter; this matches the stale signature seen in startup tracebacks.")
    return issues, detected_signature


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
    import_errors: list[str] = []

    entrypoint_source = Path("app.py").read_text()
    if "from application import *" not in entrypoint_source:
        app_source_issues.append("app.py must import and re-export from application.py")
    if len(entrypoint_source.splitlines()) > ENTRYPOINT_MAX_LINES:
        app_source_issues.append("app.py entrypoint wrapper is too large; keep it thin to avoid merge indentation regressions")
    for snippet in FORBIDDEN_STARTUP_SNIPPETS:
        if snippet in entrypoint_source:
            app_source_issues.append(f"app.py contains forbidden startup-check implementation snippet: {snippet}")

    app_impl_source = Path("application.py").read_text()
    dashboard_issues, dashboard_signature = _validate_dashboard_signature(app_impl_source)
    app_source_issues.extend(dashboard_issues)
    for snippet in FORBIDDEN_STARTUP_SNIPPETS:
        if snippet in app_impl_source:
            app_source_issues.append(f"application.py contains forbidden startup-check implementation snippet: {snippet}")

    for module in ("application", "main"):
        try:
            imported = importlib.import_module(module)
            print(f"Imported {module} from: {getattr(imported, '__file__', '<unknown>')}")
        except Exception as exc:
            import_errors.append(f"{module}: {exc}")

    if not missing and not syntax_errors and not app_source_issues and not import_errors:
        print(f"Detected dashboard signature: {dashboard_signature}")
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
        print(f" - Detected dashboard signature: {dashboard_signature}")
        for issue in app_source_issues:
            print(f" - {issue}")
        print(" - Remediation: ensure your deployed checkout includes dashboard(request, q, error, info) and rerun this check.")

    if import_errors:
        print("Import errors detected:")
        for issue in import_errors:
            print(f" - {issue}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
