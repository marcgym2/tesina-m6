import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_citations.py"
spec = importlib.util.spec_from_file_location("check_citations", SCRIPT)
check_citations = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_citations
spec.loader.exec_module(check_citations)

BIB = """\
@comment{jabref-meta: ignored,}
@string{jan = "January"}
@article{makridakis2024m6,
  title = {The M6 forecasting competition},
}
@misc{bbt:Key-With.Punct_2023,
  title = {Better BibTeX style key},
}
"""


@pytest.fixture
def project(tmp_path):
    thesis = tmp_path / "thesis"
    (thesis / "chapters").mkdir(parents=True)
    (thesis / "references.bib").write_text(BIB, encoding="utf-8")

    def write(text, name="chapters/01.qmd"):
        (thesis / name).write_text(text, encoding="utf-8")
        return check_citations.check(thesis, thesis / "references.bib")

    return write


def keys(text):
    return [o.text for o in check_citations.find_citations(text, Path("x.qmd"))]


def test_passes_with_valid_keys(project):
    assert project("Según @makridakis2024m6, el M6 [@makridakis2024m6, p. 3].\n") == 0


def test_fails_with_unknown_key(project, capsys):
    assert project("Texto.\n\nComo dice [@nonexistent2020].\n") == 1
    assert "chapters/01.qmd:3: unknown citation key @nonexistent2020" in capsys.readouterr().err


def test_fails_when_bib_missing_and_citations_exist(tmp_path):
    thesis = tmp_path / "thesis"
    thesis.mkdir()
    (thesis / "a.qmd").write_text("[@makridakis2024m6]\n", encoding="utf-8")
    assert check_citations.check(thesis, thesis / "references.bib") == 1


def test_passes_when_bib_missing_and_no_citations(tmp_path):
    thesis = tmp_path / "thesis"
    thesis.mkdir()
    (thesis / "a.qmd").write_text("# Introducción\n", encoding="utf-8")
    assert check_citations.check(thesis, thesis / "references.bib") == 0


def test_citation_syntax_variants():
    text = "[@a1; @b2, pp. 3-4], -@c3 y @{d4:x}. Final @e5.\n"
    assert keys(text) == ["a1", "b2", "c3", "d4:x", "e5"]


def test_key_with_internal_punctuation(project):
    assert keys("Ver @bbt:Key-With.Punct_2023.") == ["bbt:Key-With.Punct_2023"]
    assert project("Ver @bbt:Key-With.Punct_2023.\n") == 0


def test_ignores_crossrefs_emails_and_escapes():
    text = "Ver @fig-cascade, @tbl-rps y @sec-intro. Correo marco@uanl.mx. Literal \\@no.\n"
    assert keys(text) == []


def test_ignores_code_front_matter_and_comments():
    text = """\
---
title: "Capítulo @fake1"
author: x@y.com
---

```{python}
df["@fake2"] = 1
```

~~~~
@fake3
~~~~

Inline `@fake4` y <!-- @fake5
@fake6 --> pero @real.
"""
    assert keys(text) == ["real"]
    occ = check_citations.find_citations(text, Path("x.qmd"))
    assert occ[0].line == 15


def test_bib_parser_skips_non_entries(tmp_path):
    bib = tmp_path / "r.bib"
    bib.write_text(BIB, encoding="utf-8")
    assert check_citations.read_bib_keys(bib) == {"makridakis2024m6", "bbt:Key-With.Punct_2023"}


def test_lists_pending_without_failing(project, capsys):
    text = "Algo [CITA PENDIENTE: paper original de RPS] y más.\n"
    assert project(text) == 0
    out = capsys.readouterr().out
    assert "1 [CITA PENDIENTE]" in out
    assert "chapters/01.qmd:1: paper original de RPS" in out


def test_strict_fails_on_pending(tmp_path):
    thesis = tmp_path / "thesis"
    thesis.mkdir()
    (thesis / "a.qmd").write_text("[CITA PENDIENTE: x]\n", encoding="utf-8")
    assert check_citations.check(thesis, thesis / "references.bib", strict=True) == 1


def test_skips_excluded_dirs(tmp_path):
    thesis = tmp_path / "thesis"
    (thesis / "_output").mkdir(parents=True)
    (thesis / "_output" / "a.qmd").write_text("[@missing]\n", encoding="utf-8")
    assert check_citations.check(thesis, thesis / "references.bib") == 0
