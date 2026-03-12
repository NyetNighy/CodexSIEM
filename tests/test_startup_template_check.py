import logging

import pytest

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
            app.startup_template_self_check()

    assert "Template compilation failed during startup for broken.html" in caplog.text


def test_startup_template_self_check_passes(monkeypatch, caplog):
    monkeypatch.setattr(app.templates.env, "list_templates", lambda: ["dashboard.html", "login.html"])
    monkeypatch.setattr(app.templates.env, "get_template", lambda _: object())

    with caplog.at_level(logging.INFO):
        app.startup_template_self_check()

    assert "Template startup self-check passed for 2 HTML templates" in caplog.text
