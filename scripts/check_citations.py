"""Verify that every citation key used in the thesis exists in the bibliography.

Scans the ``.qmd`` files under ``thesis/`` for Pandoc citations (``@key``,
``[@key, p. 3]``, ``[-@key]``, ``@{key}``) and checks each key against
``thesis/references.bib``. Quarto cross-references (``@fig-...``, ``@tbl-...``,
etc.), e-mail addresses, code, YAML front matter and HTML comments are ignored.

It also lists every ``[CITA PENDIENTE: ...]`` placeholder. Placeholders do not
fail the check unless ``--strict`` is given (useful for the final pass).

Exit code: 0 if every key exists, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_THESIS_DIR = REPO_ROOT / "thesis"
DEFAULT_BIB = DEFAULT_THESIS_DIR / "references.bib"

# Directories under thesis/ that never contain sources to check.
EXCLUDED_DIRS = {"_output", ".quarto", "legacy", "templates"}

# Quarto cross-reference prefixes (https://quarto.org/docs/authoring/cross-references.html).
CROSSREF_PREFIXES = (
    "fig",
    "tbl",
    "sec",
    "eq",
    "lst",
    "thm",
    "lem",
    "cor",
    "prp",
    "cnj",
    "def",
    "exm",
    "exr",
    "sol",
    "rem",
    "alg",
)
CROSSREF_RE = re.compile(rf"^(?:{'|'.join(CROSSREF_PREFIXES)})-")

# Pandoc citation key: starts with a word character; may contain internal
# punctuation :.#$%&-+?<>~/ but cannot end with it. `@` must not follow a word
# character (e-mails) or a backslash (escaped). Braced form: @{key}.
CITATION_RE = re.compile(
    r"(?<![\w\\])-?@(?:\{(?P<braced>[^}\s]+)\}|(?P<bare>\w(?:[\w:.#$%&\-+?<>~/]*\w)?))"
)
PENDING_RE = re.compile(r"\[CITA PENDIENTE:?\s*(?P<desc>[^\]]*)\]")

# Bib entries: @type{key, ... — skipping @comment, @string and @preamble.
BIB_ENTRY_RE = re.compile(r"^\s*@(?P<type>\w+)\s*[{(]\s*(?P<key>[^,\s]+)\s*,", re.MULTILINE)
BIB_NON_ENTRIES = {"comment", "string", "preamble"}

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class Occurrence:
    path: Path
    line: int
    text: str


def _blank(match: re.Match[str]) -> str:
    """Replace a match with spaces, keeping newlines so line numbers survive."""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_non_prose(text: str) -> str:
    """Blank out YAML front matter, fenced code, inline code and HTML comments."""
    text = HTML_COMMENT_RE.sub(_blank, text)
    lines = text.split("\n")

    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() in ("---", "..."):
                for i in range(end + 1):
                    lines[i] = ""
                break

    fence: str | None = None
    for i, line in enumerate(lines):
        match = FENCE_RE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)
                lines[i] = ""
        else:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
            lines[i] = ""

    return "\n".join(INLINE_CODE_RE.sub(_blank, line) for line in lines)


def find_citations(text: str, path: Path) -> list[Occurrence]:
    found = []
    for lineno, line in enumerate(strip_non_prose(text).split("\n"), start=1):
        for match in CITATION_RE.finditer(line):
            key = match.group("braced") or match.group("bare")
            if not CROSSREF_RE.match(key):
                found.append(Occurrence(path, lineno, key))
    return found


def find_pending(text: str, path: Path) -> list[Occurrence]:
    found = []
    for lineno, line in enumerate(strip_non_prose(text).split("\n"), start=1):
        for match in PENDING_RE.finditer(line):
            found.append(Occurrence(path, lineno, match.group("desc").strip()))
    return found


def read_bib_keys(bib_path: Path) -> set[str]:
    text = bib_path.read_text(encoding="utf-8")
    return {
        m.group("key")
        for m in BIB_ENTRY_RE.finditer(text)
        if m.group("type").lower() not in BIB_NON_ENTRIES
    }


def iter_sources(thesis_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in thesis_dir.rglob("*.qmd")
        if not EXCLUDED_DIRS.intersection(p.relative_to(thesis_dir).parts)
    )


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def check(thesis_dir: Path, bib_path: Path, strict: bool = False) -> int:
    citations: list[Occurrence] = []
    pending: list[Occurrence] = []
    for source in iter_sources(thesis_dir):
        text = source.read_text(encoding="utf-8")
        citations += find_citations(text, source)
        pending += find_pending(text, source)

    if bib_path.exists():
        keys = read_bib_keys(bib_path)
    else:
        keys = set()
        if citations:
            print(f"error: bibliography not found: {_display(bib_path)}", file=sys.stderr)

    unknown = [c for c in citations if c.text not in keys]
    for c in unknown:
        print(f"{_display(c.path)}:{c.line}: unknown citation key @{c.text}", file=sys.stderr)

    if pending:
        print(f"{len(pending)} [CITA PENDIENTE]:")
        for p in pending:
            print(f"  {_display(p.path)}:{p.line}: {p.text}")

    used = {c.text for c in citations}
    print(
        f"{len(citations)} citations ({len(used)} distinct keys), "
        f"{len(unknown)} unknown, {len(pending)} pending."
    )

    if unknown:
        return 1
    if strict and pending:
        print("error: --strict and there are [CITA PENDIENTE] placeholders.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--thesis-dir", type=Path, default=DEFAULT_THESIS_DIR)
    parser.add_argument("--bib", type=Path, default=DEFAULT_BIB)
    parser.add_argument(
        "--strict", action="store_true", help="also fail if there are [CITA PENDIENTE] placeholders"
    )
    args = parser.parse_args(argv)
    return check(args.thesis_dir, args.bib, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
