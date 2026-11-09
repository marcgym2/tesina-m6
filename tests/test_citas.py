"""scripts/citas.py: the resolver replaces a marker only when all its works have keys."""

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "citas.py"
spec = importlib.util.spec_from_file_location("citas", SCRIPT)
citas = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = citas
spec.loader.exec_module(citas)

BIB = """\
@article{fama1970,
  title = {Efficient Capital Markets: A Review of Theory and Empirical Work},
  doi = {10.2307/2325486},
}
@article{brown1992survivorship,
  title = {Survivorship Bias in Performance Studies},
  doi = {10.1093/rfs/5.4.553},
}
@book{lopezdeprado2018,
  title = {Advances in Financial Machine Learning},
  isbn = {978-1-119-48208-6},
}
@article{holm1979,
  title = {A Simple Sequentially Rejective Multiple Test Procedure},
}
"""

CHAPTER = """\
Uno [CITA PENDIENTE: Fama (1970), hipótesis de mercados eficientes].
Dos [CITA PENDIENTE: Brown, Goetzmann, Ibbotson y Ross (1992); Elton, Gruber y Blake (1996)].
Tres [CITA PENDIENTE: Holm (1979)].
"""


def test_every_marker_in_the_thesis_maps_to_a_known_work():
    refs = citas.references()
    ids = [r["id"] for r in refs]
    assert len(ids) == len(set(ids))
    unmatched = [d for _, _, _, d in citas.markers() if not citas.works_for(d, refs)]
    assert unmatched == []


def test_resolver_replaces_only_fully_resolved_markers(tmp_path, monkeypatch):
    bib, chapter = tmp_path / "references.bib", tmp_path / "01.qmd"
    bib.write_text(BIB, encoding="utf-8")
    chapter.write_text(CHAPTER, encoding="utf-8")
    monkeypatch.setattr(citas, "BIB", bib)
    monkeypatch.setattr(citas, "CHAPTERS", [chapter])
    monkeypatch.setattr(citas, "ROOT", tmp_path)
    citas.resolver(write=False)
    assert chapter.read_text(encoding="utf-8") == CHAPTER  # dry run changes nothing
    citas.resolver(write=True)
    text = chapter.read_text(encoding="utf-8").splitlines()
    assert text[0] == "Uno [@fama1970]."
    assert "CITA PENDIENTE" in text[1]  # Elton et al. (1996) has no key yet
    assert text[2] == "Tres [@holm1979]."  # matched by title (manual entry)


def test_isbn_matches_with_hyphens():
    entries = citas.bib_entries(BIB)
    ref = {"id": "lopezdeprado2018", "tipo": "isbn", "identificador": "9781119482086"}
    assert citas.key_for(ref, entries) == "lopezdeprado2018"


def test_provisional_keys_are_not_used():
    bib = "@book{2006,\n  title = {An Introduction to Copulas},\n"
    bib += "  doi = {10.1007/0-387-28678-0},\n}\n"
    entries = citas.bib_entries(bib)
    ref = {"id": "nelsen2006", "tipo": "doi", "identificador": "10.1007/0-387-28678-0"}
    assert citas.key_for(ref, entries) is None
