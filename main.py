"""Alternative stable ASGI entrypoint wrapper.

Use `uvicorn main:app` for operational startup to avoid accidental local
merge-conflict breakage in `app.py`.
"""

from application import *  # noqa: F401,F403
