"""Stable ASGI entrypoint wrapper.

Keep this file intentionally tiny so `uvicorn app:app` stays resilient to
merge-conflict indentation regressions in the main implementation module.
"""

from application import *  # noqa: F401,F403
