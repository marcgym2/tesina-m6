"""The generated numbers and tables of chapter 7 are in sync with results/."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build", ROOT / "scripts" / "build_thesis_results.py")
build = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = build
spec.loader.exec_module(build)


def test_generated_files_match_results(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "OUT_VARS", tmp_path / "_variables.yml")
    monkeypatch.setattr(build, "OUT_TABLES", tmp_path / "_generated")
    build.main()
    committed = ROOT / "thesis"
    assert build.OUT_VARS.read_text() == (committed / "_variables.yml").read_text()
    for path in sorted((committed / "_generated").glob("*.md")):
        assert (build.OUT_TABLES / path.name).read_text() == path.read_text()
