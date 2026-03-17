import py_compile
from pathlib import Path


def test_core_python_files_compile_without_syntax_errors():
    for source in [Path("app.py"), Path("main.py"), Path("application.py"), Path("auth.py"), Path("secret_utils.py"), Path("siem_core.py"), Path("startup_checks.py")]:
        py_compile.compile(str(source), doraise=True)
