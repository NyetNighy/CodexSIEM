from pathlib import Path


def test_app_does_not_inline_startup_template_check_logic():
    app_source = Path("app.py").read_text()

    assert "Template startup self-check found failures but strict mode is disabled" not in app_source
    assert "Template syntax error during startup check" not in app_source
    assert "def startup_template_self_check" in app_source
    assert "run_startup_template_self_check" in app_source
