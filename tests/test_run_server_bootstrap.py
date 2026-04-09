import run_server


def test_ensure_repair_script_usable_rewrites_corrupted_script(monkeypatch, tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    repair_path = scripts_dir / "repair_entrypoints.py"
    repair_path.write_text("def broken(:\n", encoding="utf-8")

    monkeypatch.setattr(run_server, "ROOT", tmp_path)

    assert run_server._ensure_repair_script_usable() is True
    repaired = repair_path.read_text(encoding="utf-8")
    assert "Bootstrap repair for CodexSIEM startup wrappers" in repaired
