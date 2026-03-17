import logging

import pytest
from jinja2 import TemplateSyntaxError

import app


def test_startup_template_self_check_logs_and_raises(monkeypatch, caplog):
    monkeypatch.setattr(app.templates.env, "list_templates", lambda: ["dashboard.html", "broken.html"])

    def _get_template(name: str):
        if name == "broken.html":
            raise RuntimeError("synthetic compile failure")
        return object()

    monkeypatch.setattr(app.templates.env, "get_template", _get_template)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="Template startup self-check failed"):
            app.startup_template_self_check(strict=True)

    assert "Template compilation failed during startup for broken.html" in caplog.text


def test_startup_template_self_check_passes(monkeypatch, caplog):
    monkeypatch.setattr(app.templates.env, "list_templates", lambda: ["dashboard.html", "login.html"])
    monkeypatch.setattr(app.templates.env, "get_template", lambda _: object())

    with caplog.at_level(logging.INFO):
        app.startup_template_self_check(strict=True)

    assert "Template startup self-check passed for 2 HTML templates" in caplog.text


def test_startup_template_self_check_reports_template_syntax_line(monkeypatch, caplog):
    monkeypatch.setattr(app.templates.env, "list_templates", lambda: ["dashboard.html"])

    def _get_template(_: str):
        raise TemplateSyntaxError("unexpected endfor", 102, name="dashboard.html", filename="templates/dashboard.html")

    monkeypatch.setattr(app.templates.env, "get_template", _get_template)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="dashboard.html:102"):
            app.startup_template_self_check(strict=True)

    assert "Template syntax error during startup check for dashboard.html" in caplog.text
    assert "line=102" in caplog.text


def test_startup_template_self_check_non_strict_logs_but_does_not_raise(monkeypatch, caplog):
    monkeypatch.setattr(app.templates.env, "list_templates", lambda: ["dashboard.html"])

    def _get_template(_: str):
        raise TemplateSyntaxError("unexpected endfor", 102, name="dashboard.html", filename="templates/dashboard.html")

    monkeypatch.setattr(app.templates.env, "get_template", _get_template)

    with caplog.at_level(logging.ERROR):
        failures = app.startup_template_self_check(strict=False)

    assert failures == ["dashboard.html:102"]
    assert "strict mode is disabled" in caplog.text
