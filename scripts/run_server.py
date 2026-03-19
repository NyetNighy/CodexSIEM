"""Backward-compatible thin wrapper for CodexSIEM startup."""

"""Preflight launcher for CodexSIEM.

Intentionally avoids square-bracket syntax to reduce merge/edit corruption risk.
Runs runtime verification first, then starts uvicorn only if checks pass.
Use this in deployments to surface syntax/import issues before ASGI boot.
"""

from __future__ import annotations

import argparse
import importlib
import py_compile
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from startup_launcher import main


def _compile_target(path: Path) -> bool:
    try:
        py_compile.compile(str(path), doraise=True)
        return True
    except py_compile.PyCompileError as exc:
        print(f"Preflight compile check failed for {path}: {exc.msg}", file=sys.stderr)
        print("Remediation: sync your checkout and rerun startup.", file=sys.stderr)
        return False


def _compile_required_targets() -> int:
    ok = True
    ok = _compile_target(ROOT / "application.py") and ok
    ok = _compile_target(ROOT / "main.py") and ok
    return 0 if ok else 1
ROOT = Path(__file__).resolve().parents[1]


def _compile_required_targets() -> int:
    targets = [
def _compile_preflight_targets() -> int:
    targets = [
        ROOT / "scripts" / "verify_runtime.py",
        ROOT / "application.py",
        ROOT / "main.py",
    ]
    for target in targets:
        try:
            py_compile.compile(str(target), doraise=True)
        except py_compile.PyCompileError as exc:
            print(f"Preflight compile check failed for {target}: {exc.msg}", file=sys.stderr)
            print("Remediation: sync your checkout and rerun startup.", file=sys.stderr)
            return 1
    return 0


def _verify_runtime_script_is_usable() -> bool:
    target = ROOT / "scripts" / "verify_runtime.py"
    try:
        py_compile.compile(str(target), doraise=True)
        return True
    except py_compile.PyCompileError as exc:
        print(f"Warning: skipping scripts/verify_runtime.py because it is not parseable: {exc.msg}", file=sys.stderr)
        print("Continuing with built-in minimal preflight checks for this startup.", file=sys.stderr)
        return False


def _minimal_import_preflight() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    for module in ("application", "main"):
        try:
            imported = importlib.import_module(module)
            print(f"Imported {module} from: {getattr(imported, '__file__', '<unknown>')}")
        except Exception as exc:  # noqa: BLE001
            print(f"Preflight import check failed for {module}: {exc}", file=sys.stderr)
            return 1
    print("Minimal preflight checks passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CodexSIEM with preflight runtime checks.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default="8000")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    if _compile_required_targets() != 0:
        return 1

    if _verify_runtime_script_is_usable():
        verify_cmd = (sys.executable, str(ROOT / "scripts" / "verify_runtime.py"))
    compile_status = _compile_required_targets()
    if compile_status != 0:
        return compile_status

    if _verify_runtime_script_is_usable():
        verify_cmd = [sys.executable, str(ROOT / "scripts" / "verify_runtime.py")]
        verify = subprocess.run(verify_cmd, cwd=ROOT)
        if verify.returncode != 0:
            print("Preflight failed. Fix the issues above before starting uvicorn.", file=sys.stderr)
            return verify.returncode
    elif _minimal_import_preflight() != 0:
        return 1

    uvicorn_cmd = (
    else:
        minimal_status = _minimal_import_preflight()
        if minimal_status != 0:
            return minimal_status
    compile_status = _compile_preflight_targets()
    if compile_status != 0:
        return compile_status

    verify_cmd = [sys.executable, str(ROOT / "scripts" / "verify_runtime.py")]
    verify = subprocess.run(verify_cmd, cwd=ROOT)
    if verify.returncode != 0:
        print("Preflight failed. Fix the issues above before starting uvicorn.", file=sys.stderr)
        print("Tip: if you saw SyntaxError in scripts/verify_runtime.py, your local checkout is stale/corrupted; refresh repository files.", file=sys.stderr)
        return verify.returncode

    uvicorn_cmd = [
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
        uvicorn_cmd = uvicorn_cmd + ("--reload",)
    ]
    if args.reload:
        uvicorn_cmd.append("--reload")

    try:
        return subprocess.call(uvicorn_cmd, cwd=ROOT)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
