from pathlib import Path


def test_app_entrypoint_is_thin_wrapper():
    app_source = Path("app.py").read_text()

    assert "from application import *" in app_source
    assert "def startup_template_self_check" not in app_source
    assert "Template startup self-check found failures but strict mode is disabled" not in app_source
    assert "Template syntax error during startup check" not in app_source
    assert len(app_source.splitlines()) <= 20


def test_application_keeps_startup_check_logic_out_of_entrypoint():
    app_impl_source = Path("application.py").read_text()
    assert "Template startup self-check found failures but strict mode is disabled" not in app_impl_source
    assert "Template syntax error during startup check" not in app_impl_source
    assert "def startup_template_self_check" in app_impl_source
    assert "run_startup_template_self_check" in app_impl_source
