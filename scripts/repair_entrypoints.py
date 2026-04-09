"""Repair CodexSIEM startup entrypoints from known-good local templates."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = ROOT / "scripts" / "repair_templates"

TEMPLATES = {
    "app.py": "app.py",
    "main.py": "main.py",
    "run_server.py": "run_server.py",
    "startup_launcher.py": "startup_launcher.py",
    "scripts/run_server.py": "scripts_run_server.py",
}


def _load_template(template_name: str) -> str:
    template_path = TEMPLATE_ROOT / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Missing repair template: {template_path}")
    return template_path.read_text(encoding="utf-8")


def _restore_application_from_git() -> int:
    result = subprocess.run(("git", "checkout", "--", "application.py"), cwd=ROOT)
    if result.returncode == 0:
        print("Restored application.py from git checkout")
        return 0
    print("Failed to restore application.py from git. Please repair it manually.", flush=True)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair CodexSIEM startup wrappers.")
    parser.add_argument(
        "--include-application",
        action="store_true",
        help="Also restore application.py from git checkout.",
    )
    include_application = parser.parse_args().include_application

    for relative_path, template_name in TEMPLATES.items():
        path = ROOT / relative_path
        content = _load_template(template_name)
        path.write_text(content, encoding="utf-8")
        print(f"Repaired {relative_path}")

    if include_application:
        return _restore_application_from_git()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
