import scripts.repair_entrypoints as repair


def test_repair_main_uses_parsed_args_without_name_error(monkeypatch, tmp_path):
    monkeypatch.setattr(repair, "ROOT", tmp_path)
    monkeypatch.setattr(repair, "TEMPLATES", {"app.py": "app = 1\n"})

    called = {"restore": 0}

    def fake_restore() -> int:
        called["restore"] += 1
        return 0

    monkeypatch.setattr(repair, "_restore_application_from_git", fake_restore)
    monkeypatch.setattr("sys.argv", ["repair_entrypoints.py", "--include-application"])

    assert repair.main() == 0
    assert called["restore"] == 1
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "app = 1\n"
