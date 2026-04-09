"""CodexSIEM startup launcher helpers.

Contains the implementation behind the thin `run_server.py` wrappers so the
operator-facing entrypoint stays minimal and less prone to merge/edit damage.
"""

from __future__ import annotations

import argparse
import importlib
import py_compile
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _compile_target(path: Path) -> bool:
    try:
        py_compile.compile(str(path), doraise=True)
        return True
    except py_compile.PyCompileError as exc:
        print(f"Preflight compile check failed for {path}: {exc.msg}", file=sys.stderr)
        print("Remediation: sync your checkout and rerun startup.", file=sys.stderr)
        return False


def _compile_required_targets(auto_recover: bool = False) -> int:
    failed_files: list[str] = []
    for filename in ("app.py", "application.py", "main.py"):
        path = ROOT / filename
        if not _compile_target(path):
            failed_files.append(filename)

    if not failed_files:
        return 0

    if auto_recover:
        recover_cmd = ("git", "checkout", "--", *failed_files)
        print(f"Attempting automatic recovery: {' '.join(recover_cmd)}", file=sys.stderr)
        result = subprocess.run(recover_cmd, cwd=ROOT)
        if result.returncode == 0:
            print("Auto-recovery succeeded; re-running compile preflight.", file=sys.stderr)
            return _compile_required_targets(auto_recover=False)
        print("Auto-recovery failed; falling back to manual recovery instructions.", file=sys.stderr)

    if len(failed_files) == 1:
        print(f"Suggested recovery: git checkout -- {failed_files[0]}", file=sys.stderr)
    else:
        joined = " ".join(failed_files)
        print(f"Suggested recovery: git checkout -- {joined}", file=sys.stderr)
    print("Alternative recovery: python scripts/repair_entrypoints.py --include-application", file=sys.stderr)
    print("If you have local edits, back them up before running the command above.", file=sys.stderr)
    return 1


def _validate_entrypoint_wrappers() -> int:
    targets = (("app.py", "app.py"), ("main.py", "main.py"))
    for filename, label in targets:
        source = (ROOT / filename).read_text()
        if "importlib.import_module(\"application\")" not in source:
            print(
                f"Preflight wrapper check failed: {label} must load application.py via importlib.",
                file=sys.stderr,
            )
            return 1
        if len(source.splitlines()) > 80:
            print(
                f"Preflight wrapper check failed: {label} is too large; expected thin wrapper.",
                file=sys.stderr,
            )
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
    parser.add_argument("--auto-recover", action="store_true", help="Attempt git checkout auto-recovery for broken app/main wrappers.")
    args = parser.parse_args()

    if _compile_required_targets(auto_recover=args.auto_recover) != 0:
        return 1
    if _validate_entrypoint_wrappers() != 0:
        return 1

    if _verify_runtime_script_is_usable():
        verify_cmd = (sys.executable, str(ROOT / "scripts" / "verify_runtime.py"))
        verify = subprocess.run(verify_cmd, cwd=ROOT)
        if verify.returncode != 0:
            print("Preflight failed. Fix the issues above before starting uvicorn.", file=sys.stderr)
            return verify.returncode
    elif _minimal_import_preflight() != 0:
        return 1

    uvicorn_cmd = (
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

    try:
        return subprocess.call(uvicorn_cmd, cwd=ROOT)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
