import ast
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


def test_main_entrypoint_is_thin_wrapper():
    main_source = Path("main.py").read_text()

    assert "from application import *" in main_source
    assert len(main_source.splitlines()) <= 20


def test_run_server_entrypoint_is_thin_wrapper():
    run_server_source = Path("run_server.py").read_text()

    assert "from startup_launcher import main" in run_server_source
    assert len(run_server_source.splitlines()) <= 10


def test_scripts_run_server_entrypoint_is_thin_wrapper():
    run_server_source = Path("scripts/run_server.py").read_text()

    assert "runpy.run_path" in run_server_source
    assert "sys.path.insert(0, str(root))" in run_server_source
    assert 'run_server.py"), run_name="__main__"' in run_server_source
    assert len(run_server_source.splitlines()) <= 15


def test_dashboard_signature_guard():
    app_impl_source = Path("application.py").read_text()
    tree = ast.parse(app_impl_source)

    dashboard_nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "dashboard"
    ]
    assert len(dashboard_nodes) == 1

    arg_names = [arg.arg for arg in dashboard_nodes[0].args.args]
    assert arg_names == ["request", "q", "error", "info"]



def test_run_server_avoids_square_bracket_syntax():
    source = Path("scripts/run_server.py").read_text()
    assert "[" not in source
