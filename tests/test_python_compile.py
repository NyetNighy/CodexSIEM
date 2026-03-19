import py_compile
from pathlib import Path


def test_core_python_files_compile_without_syntax_errors():
    for source in [Path("app.py"), Path("main.py"), Path("run_server.py"), Path("startup_launcher.py"), Path("application.py"), Path("auth.py"), Path("secret_utils.py"), Path("siem_core.py"), Path("startup_checks.py"), Path("scripts/verify_runtime.py"), Path("scripts/run_server.py")]:
    for source in [Path("app.py"), Path("main.py"), Path("application.py"), Path("auth.py"), Path("secret_utils.py"), Path("siem_core.py"), Path("startup_checks.py"), Path("scripts/verify_runtime.py"), Path("scripts/run_server.py")]:
    for source in [Path("app.py"), Path("main.py"), Path("application.py"), Path("auth.py"), Path("secret_utils.py"), Path("siem_core.py"), Path("startup_checks.py")]:
        py_compile.compile(str(source), doraise=True)



def test_main_module_imports_without_errors():
    __import__("main")



def test_application_module_imports_without_errors():
    __import__("application")
    for source in [Path("app.py"), Path("application.py"), Path("auth.py"), Path("secret_utils.py"), Path("siem_core.py"), Path("startup_checks.py")]:
    for source in [Path("app.py"), Path("auth.py"), Path("secret_utils.py"), Path("siem_core.py"), Path("startup_checks.py")]:
    for source in [Path("app.py"), Path("auth.py"), Path("secret_utils.py"), Path("siem_core.py")]:
        py_compile.compile(str(source), doraise=True)
