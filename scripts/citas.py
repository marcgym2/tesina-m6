"""Help with the pending citations (issues #29, #30): export for Zotero, then resolve.

    uv run python scripts/citas.py exportar
    uv run python scripts/citas.py resolver            # dry run: what would change
    uv run python scripts/citas.py resolver --escribir # apply to thesis/chapters/*.qmd

``docs/citas/referencias.csv`` lists every work the thesis needs. Each row has an id,
a short citation, how Zotero can fetch it (``doi``, ``arxiv``, ``isbn``; ``manual`` =
import ``docs/citas/manuales.bib``; ``zotero`` = already in Zotero) and a regular
expression that matches the ``[CITA PENDIENTE: ...]`` markers it resolves. The DOIs,
arXiv ids and ISBNs were checked against Crossref, arXiv and Open Library.

``exportar`` writes:
- ``docs/citas/identificadores.txt``: one identifier per line, to paste in Zotero's
  "Add Item by Identifier" (magic wand), which fetches the metadata itself;
- ``docs/citas/verificacion.md``: every pending marker with the sentence it supports
  and the work(s) it maps to, to check each claim against the PDF before citing it.

``resolver`` reads ``thesis/references.bib`` (maintained by Marco with Zotero; this
script never edits it), finds each work's citation key by DOI, arXiv id, ISBN, URL or
title, and replaces a marker by ``[@key1; @key2]`` only when every work it maps to has a
key. Markers it cannot resolve are left as they are and listed.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "docs" / "citas" / "referencias.csv"
MANUAL = ROOT / "docs" / "citas" / "manuales.bib"
CHAPTERS = sorted((ROOT / "thesis" / "chapters").glob("*.qmd"))
BIB = ROOT / "thesis" / "references.bib"
MARKER = re.compile(r"\[CITA PENDIENTE:\s*(?P<desc>[^\]]*)\]")

# Titles of the manual entries, used to find their keys in the exported bib.
MANUAL_TITLES = {
    "ke2017": "lightgbm",
    "riskmetrics1996": "riskmetrics",
    "timesfm3": "timesfm 3",
    "politis1992": "circular block-resampling",
    "holm1979": "sequentially rejective multiple test",
    "sec2024": "artificial intelligence (ai) and investment fraud",
    "m6methods": "m6-methods",
    "sebrad": "sebrad",
    "woundignite": "wound-ignite",
    "finqboost": "finqboost",
    "schneider2024": "benchmarking m6 competitors",
    "vilmarest2024": "adaptive volatility method for probabilistic forecasting",
}


def references() -> list[dict]:
    with open(TABLE, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def markers():
    """Yield ``(path, line_number, line, description)`` for every pending marker."""
    for path in CHAPTERS:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in MARKER.finditer(line):
                yield path, n, line, m.group("desc")


def works_for(desc: str, refs: list[dict]) -> list[dict]:
    return [r for r in refs if r["patron"] and re.search(r["patron"], desc)]


def identifier(r: dict) -> str | None:
    kind, value = r["tipo"], r["identificador"]
    if kind == "doi":
        return value
    if kind == "arxiv":
        return f"arXiv:{value}"
    if kind == "isbn":
        return value
    return None


def sentence(path: Path, n: int) -> str:
    """The paragraph around a line, without markers, trimmed for the checklist."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = n - 1
    while start > 0 and lines[start - 1].strip() and not lines[start - 1].startswith("#"):
        start -= 1
    end = n - 1
    while end + 1 < len(lines) and lines[end + 1].strip():
        end += 1
    text = " ".join(line.strip() for line in lines[start : end + 1])
    text = MARKER.sub("[*]", text)
    return text if len(text) < 600 else text[:600] + "…"


def exportar() -> None:
    refs = references()
    ids = [identifier(r) for r in refs]
    out = ROOT / "docs" / "citas" / "identificadores.txt"
    out.write_text("\n".join(i for i in ids if i) + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {sum(1 for i in ids if i)} identifiers")

    rows, unmatched = [], []
    for path, n, _, desc in markers():
        works = works_for(desc, refs)
        if not works:
            unmatched.append((path, n, desc))
        cite = "; ".join(w["cita"] for w in works) or "**sin fuente asignada**"
        where = f"{path.relative_to(ROOT)}:{n}"
        rows.append(f"| [ ] | `{where}` | {cite} | {sentence(path, n).replace('|', '/')} |")
    doc = [
        "# Verificación de citas pendientes (#29)",
        "",
        "Generado por `scripts/citas.py exportar`. Por cada marca `[CITA PENDIENTE]`:",
        "la obra a la que se asigna y el párrafo que la usa (`[*]` indica dónde va la cita).",
        "Para cada fila, Marco verifica contra el PDF que la obra sostiene lo que dice el",
        "párrafo, y marca la casilla. Si no lo sostiene, se corrige el texto o la fuente.",
        "",
        "| ✓ | Dónde | Obra | Párrafo |",
        "|---|---|---|---|",
        *rows,
        "",
    ]
    if unmatched:
        doc += ["## Marcas sin fuente asignada", ""]
        doc += [f"- `{p.relative_to(ROOT)}:{n}`: {d}" for p, n, d in unmatched]
    out = ROOT / "docs" / "citas" / "verificacion.md"
    out.write_text("\n".join(doc).rstrip("\n") + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(rows)} markers, {len(unmatched)} without a source")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.:/ -]+", " ", text))


def bib_entries(text: str) -> list[dict]:
    """Minimal BibTeX reader: key and the lower-cased raw text of each entry."""
    entries = []
    for m in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,(.*?)(?=\n@|\Z)", text, re.S):
        entries.append({"key": m.group(1), "text": normalize(m.group(2))})
    return entries


def key_for(r: dict, entries: list[dict]) -> str | None:
    needles = []
    if r["identificador"]:
        needles.append(normalize(r["identificador"]))
    if r["id"] in MANUAL_TITLES:
        needles.append(normalize(MANUAL_TITLES[r["id"]]))
    for needle in needles:
        if r.get("tipo") == "isbn":  # exported ISBNs usually carry hyphens
            hits = [e["key"] for e in entries if needle in e["text"].replace("-", "")]
        else:
            hits = [e["key"] for e in entries if needle in e["text"]]
        if len(hits) == 1:
            return hits[0]
    return None


def resolver(write: bool) -> int:
    refs = references()
    entries = bib_entries(BIB.read_text(encoding="utf-8"))
    keys = {r["id"]: key_for(r, entries) for r in refs}
    changed, pending = 0, []
    for path in CHAPTERS:
        text = path.read_text(encoding="utf-8")

        def replace(m: re.Match, name: str = path.name) -> str:
            works = works_for(m.group("desc"), refs)
            found = [keys[w["id"]] for w in works]
            if not works or None in found:
                missing = [w["id"] for w, k in zip(works, found, strict=True) if k is None]
                pending.append((name, m.group("desc"), missing or ["sin fuente asignada"]))
                return m.group(0)
            return "[" + "; ".join(f"@{k}" for k in dict.fromkeys(found)) + "]"

        new = MARKER.sub(replace, text)
        n = len(MARKER.findall(text)) - len(MARKER.findall(new))
        if n:
            changed += n
            print(f"{path.relative_to(ROOT)}: {n} markers resolved")
            if write:
                path.write_text(new, encoding="utf-8")
    print(f"{changed} markers {'resolved' if write else 'would be resolved'}; {len(pending)} left")
    missing = sorted({i for _, _, ids in pending for i in ids})
    if missing:
        print("works without a key in references.bib:", ", ".join(missing))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("exportar")
    r = sub.add_parser("resolver")
    r.add_argument("--escribir", action="store_true", help="apply the replacements")
    args = parser.parse_args(argv)
    if args.command == "exportar":
        exportar()
        return 0
    return resolver(args.escribir)


if __name__ == "__main__":
    sys.exit(main())
