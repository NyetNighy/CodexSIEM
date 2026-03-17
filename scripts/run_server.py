"""Preflight launcher for CodexSIEM.

Runs runtime verification first, then starts uvicorn only if checks pass.
Use this in deployments to surface syntax/import issues before ASGI boot.
"""

from __future__ import annotations

import argparse
import py_compile
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CodexSIEM with preflight runtime checks.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default="8000")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

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
    ]
    if args.reload:
        uvicorn_cmd.append("--reload")

    try:
        return subprocess.call(uvicorn_cmd, cwd=ROOT)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
