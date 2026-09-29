import json

import pytest

from tesina import experiment


def test_prepare_run_records_config_and_commit(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "RESULTS", tmp_path)
    config = tmp_path / "config.toml"
    config.write_text('[data]\nsnapshot = "2026-09-28"\n')
    out = experiment.prepare_run("demo", config)
    assert (out / "config.toml").read_text() == config.read_text()
    info = json.loads((out / "run_info.json").read_text())
    assert len(info["commit"]) == 40
    assert out.name.split("_")[1].startswith(info["commit"][:7])
    with pytest.raises(FileExistsError):
        experiment.prepare_run("demo", config)
