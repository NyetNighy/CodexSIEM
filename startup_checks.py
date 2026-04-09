import os
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, TemplateSyntaxError


def run_startup_template_self_check(
    env: Environment,
    logger,
    templates_dir: Path,
    strict: Optional[bool] = None,
) -> List[str]:
    strict_mode = (
        strict
        if strict is not None
        else os.getenv("SIEM_STRICT_TEMPLATE_CHECK", "false").lower() == "true"
    )
    logger.info("Using template directory: %s", templates_dir)
    template_names = [name for name in env.list_templates() if name.endswith(".html")]
    failed_templates: list[str] = []

    for template_name in template_names:
        try:
            env.get_template(template_name)
        except TemplateSyntaxError as exc:
            failure = f"{template_name}:{exc.lineno}"
            failed_templates.append(failure)
            logger.exception(
                "Template syntax error during startup check for %s (file=%s, line=%s): %s",
                template_name,
                exc.filename or template_name,
                exc.lineno,
                exc.message,
            )
        except Exception:  # noqa: BLE001
            failed_templates.append(template_name)
            logger.exception("Template compilation failed during startup for %s", template_name)

    if failed_templates:
        failures = ", ".join(sorted(failed_templates))
        if strict_mode:
            raise RuntimeError(f"Template startup self-check failed for: {failures}")
        logger.error("Template startup self-check found failures but strict mode is disabled: %s", failures)
    else:
        logger.info("Template startup self-check passed for %d HTML templates", len(template_names))

    return failed_templates
