"""Simple runtime dependency check for CodexSIEM."""

import importlib
import sys

REQUIRED = [
    "fastapi",
    "uvicorn",
    "httpx",
    "jinja2",
    "multipart",
    "itsdangerous",
]


def main() -> int:
    missing: list[str] = []
    for module in REQUIRED:
        try:
            importlib.import_module(module)
        except Exception:
            missing.append(module)

    if not missing:
        print("Runtime dependency check passed.")
        return 0

    print("Missing modules:", ", ".join(missing))
    print("Run: pip install -r requirements.txt")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
