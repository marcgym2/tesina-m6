"""Derive the Quarto/Pandoc reference document from the official UANL template.

    uv run python scripts/build_reference_docx.py

Reads ``thesis/templates/uanl_original.docx`` and writes
``thesis/templates/reference.docx``. The reference document keeps the
template's page size, margins, theme and page-number footer, drops its body,
and defines the paragraph styles Pandoc emits (Body Text, Heading 1-5,
captions, bibliography, TOC levels, ...) so they reproduce the template's
manual formatting. It also adds the custom styles used by
``scripts/postprocess_docx.py`` (chapter label, front-matter heading).

Formatting values come from the template (see comments); where the template
gives no rule (captions, footnotes, block quotes) a neutral choice is made.
"""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = REPO_ROOT / "thesis" / "templates"
DEFAULT_SRC = TEMPLATES / "uanl_original.docx"
DEFAULT_DST = TEMPLATES / "reference.docx"

FONT = "Arial"
LANG = "es-MX"
# Letter page, left margin 2268 and right 1418 twips (template sectPr) -> text width.
TEXT_WIDTH = 12240 - 2268 - 1418
# Three empty double-spaced 11 pt lines (~25 pt each) precede every chapter and
# front-matter heading in the template; one empty 1.15-spaced line is ~14.5 pt. In twips:
TOP_OF_PAGE_SPACE = 1500
ONE_LINE = 290


def _el(tag: str, **attrs: str) -> OxmlElement:
    el = OxmlElement(tag)
    for key, value in attrs.items():
        el.set(qn(f"w:{key}"), str(value))
    return el


def _replace(parent, child) -> None:
    """Insert ``child`` into ``parent`` replacing any existing element with the same tag."""
    for old in parent.findall(child.tag):
        parent.remove(old)
    parent.append(child)


def _sort_ppr(ppr) -> None:
    """Order pPr children as required by the OOXML schema."""
    order = [
        "pStyle", "keepNext", "keepLines", "pageBreakBefore", "widowControl", "numPr",
        "pBdr", "shd", "tabs", "suppressAutoHyphens", "spacing", "ind", "contextualSpacing",
        "jc", "outlineLvl", "rPr",
    ]  # fmt: skip
    rank = {qn(f"w:{name}"): i for i, name in enumerate(order)}
    children = sorted(ppr, key=lambda c: rank.get(c.tag, len(order)))
    for child in children:
        ppr.append(child)


def _sort_rpr(rpr) -> None:
    order = ["rFonts", "b", "bCs", "i", "iCs", "caps", "color", "sz", "szCs", "u", "lang"]
    rank = {qn(f"w:{name}"): i for i, name in enumerate(order)}
    for child in sorted(rpr, key=lambda c: rank.get(c.tag, len(order))):
        rpr.append(child)


def get_style(doc, style_id: str, name: str, based_on: str | None = "Normal"):
    """Return the paragraph style ``style_id`` (created if missing), reset to a clean state."""
    styles = doc.styles.element
    el = styles.find(f"w:style[@w:styleId='{style_id}']", styles.nsmap)
    if el is None:
        el = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH).element
        el.set(qn("w:styleId"), style_id)
    for tag in ("w:pPr", "w:rPr", "w:basedOn", "w:next", "w:link"):
        for old in el.findall(qn(tag)):
            el.remove(old)
    name_el = el.find(qn("w:name"))
    name_el.set(qn("w:val"), name)
    if based_on:
        name_el.addnext(_el("w:basedOn", val=based_on))
    el.append(_el("w:pPr"))
    el.append(_el("w:rPr"))
    return el


def set_para(
    style,
    *,
    jc: str | None = None,
    before: int = 0,
    after: int = 0,
    line: int = 276,
    first_line: int | None = None,
    left: int | None = None,
    hanging: int | None = None,
    keep_next: bool = False,
    page_break_before: bool = False,
    outline: int | None = None,
    bottom_border: bool = False,
    tabs: list[tuple[str, int, str | None]] | None = None,
) -> None:
    ppr = style.find(qn("w:pPr"))
    if keep_next:
        ppr.append(_el("w:keepNext"))
        ppr.append(_el("w:keepLines"))
    if page_break_before:
        ppr.append(_el("w:pageBreakBefore"))
    if bottom_border:
        bdr = _el("w:pBdr")
        bdr.append(_el("w:bottom", val="single", sz="12", space="1", color="000000"))
        ppr.append(bdr)
    if tabs:
        tabs_el = _el("w:tabs")
        for kind, pos, leader in tabs:
            tab = _el("w:tab", val=kind, pos=str(pos))
            if leader:
                tab.set(qn("w:leader"), leader)
            tabs_el.append(tab)
        ppr.append(tabs_el)
    ppr.append(_el("w:spacing", before=before, after=after, line=line, lineRule="auto"))
    ind = {}
    if first_line is not None:
        ind["firstLine"] = first_line
    if left is not None:
        ind["left"] = left
    if hanging is not None:
        ind["hanging"] = hanging
    # Explicit zero indent so styles never inherit a first-line indent by accident.
    ppr.append(_el("w:ind", **{k: str(v) for k, v in (ind or {"firstLine": 0}).items()}))
    if jc:
        ppr.append(_el("w:jc", val=jc))
    if outline is not None:
        ppr.append(_el("w:outlineLvl", val=outline))
    _sort_ppr(ppr)


def set_run(
    style,
    *,
    size: float = 11,
    bold: bool = False,
    italic: bool = False,
    caps: bool = False,
    font: str | None = FONT,
) -> None:
    rpr = style.find(qn("w:rPr"))
    if font:
        rpr.append(_el("w:rFonts", ascii=font, hAnsi=font, eastAsia=font, cs=font))
    if bold:
        rpr.append(_el("w:b"))
        rpr.append(_el("w:bCs"))
    if italic:
        rpr.append(_el("w:i"))
        rpr.append(_el("w:iCs"))
    if caps:
        rpr.append(_el("w:caps"))
    rpr.append(_el("w:color", val="000000"))
    rpr.append(_el("w:sz", val=int(size * 2)))
    rpr.append(_el("w:szCs", val=int(size * 2)))
    _sort_rpr(rpr)


def define_styles(doc) -> None:
    styles = doc.styles.element

    # Document defaults: Arial 11 (template docDefaults), Spanish (Mexico).
    rpr_default = styles.find("w:docDefaults/w:rPrDefault/w:rPr", styles.nsmap)
    _replace(rpr_default, _el("w:lang", val=LANG, eastAsia=LANG, bidi="ar-SA"))

    normal = get_style(doc, "Normal", "Normal", based_on=None)
    set_para(normal, line=276)
    set_run(normal)

    # Body: justified, 1.5 spacing, 0.5" first-line indent (template chapter 4 body paragraphs).
    body = get_style(doc, "BodyText", "Body Text")
    set_para(body, jc="both", after=115, line=360, first_line=720)
    set_run(body)
    first = get_style(doc, "FirstParagraph", "First Paragraph", based_on="BodyText")
    set_para(first, jc="both", after=115, line=360, first_line=720)
    compact = get_style(doc, "Compact", "Compact", based_on="BodyText")
    set_para(compact, line=240)
    block = get_style(doc, "BlockText", "Block Text", based_on="BodyText")
    set_para(block, jc="both", after=115, line=360, left=720, first_line=0)

    # Chapter title: bold, centered, uppercase, bottom rule (template "INTRODUCCIÓN").
    # When the chapter label is inserted, postprocess_docx.py removes the page break
    # and space before from the heading and puts them on the label.
    h1 = get_style(doc, "Heading1", "heading 1")
    set_para(
        h1,
        jc="center",
        before=TOP_OF_PAGE_SPACE,
        after=2 * ONE_LINE,
        keep_next=True,
        page_break_before=True,
        bottom_border=True,
        outline=0,
    )
    set_run(h1, bold=True, caps=True)

    # Level 2: numbered, bold, centered, 12 pt (template "1.1 (Subtítulo)").
    h2 = get_style(doc, "Heading2", "heading 2")
    set_para(h2, jc="center", before=240, after=240, keep_next=True, outline=1)
    set_run(h2, size=12, bold=True)

    # Levels 3-5: plain text, left aligned; 4-5 indented (template "1.1.1 (Subtítulo).").
    h3 = get_style(doc, "Heading3", "heading 3")
    set_para(h3, jc="left", before=240, after=120, keep_next=True, outline=2)
    set_run(h3)
    for level in (4, 5):
        h = get_style(doc, f"Heading{level}", f"heading {level}")
        set_para(h, jc="left", before=240, after=120, left=360, keep_next=True, outline=level - 1)
        set_run(h)

    # Custom styles used by postprocess_docx.py.
    label = get_style(doc, "UANLChapterLabel", "UANL Chapter Label")
    set_para(
        label,
        jc="center",
        before=TOP_OF_PAGE_SPACE,
        after=ONE_LINE,
        keep_next=True,
        page_break_before=True,
    )
    set_run(label, bold=True, caps=True)
    front = get_style(doc, "UANLFrontHeading", "UANL Front Heading")
    set_para(
        front,
        jc="center",
        before=TOP_OF_PAGE_SPACE,
        after=2 * ONE_LINE,
        keep_next=True,
        page_break_before=True,
        bottom_border=True,
    )
    set_run(front, bold=True, caps=True)
    index_header = get_style(doc, "UANLIndexHeader", "UANL Index Header")
    set_para(index_header, after=240, tabs=[("right", TEXT_WIDTH, None)])
    set_run(index_header, bold=True)

    # Title block (used by short documents such as thesis/propuesta.qmd, not by the
    # thesis, whose cover comes from the template). Same look as the cover: black Arial.
    title = get_style(doc, "Title", "Title")
    set_para(title, jc="center", after=120, line=240, keep_next=True)
    set_run(title, size=13, bold=True)
    subtitle = get_style(doc, "Subtitle", "Subtitle", based_on="Title")
    set_para(subtitle, jc="center", after=120, line=240, keep_next=True)
    set_run(subtitle, size=11, italic=True)
    for style_id, name in (("Author", "Author"), ("Date", "Date")):
        style = get_style(doc, style_id, name)
        set_para(style, jc="center", after=60, line=240, keep_next=True)
        set_run(style)

    # Captions: no rule in the template; APA-like, table caption above (keep with table).
    caption = get_style(doc, "Caption", "caption")
    set_para(caption, jc="center", before=120, after=240, line=240)
    set_run(caption, size=10)
    table_caption = get_style(doc, "TableCaption", "Table Caption", based_on="Caption")
    set_para(table_caption, jc="center", before=240, after=120, line=240, keep_next=True)
    image_caption = get_style(doc, "ImageCaption", "Image Caption", based_on="Caption")
    set_para(image_caption, jc="center", before=120, after=240, line=240)
    figure = get_style(doc, "CaptionedFigure", "Captioned Figure")
    set_para(figure, jc="center", before=240, line=240, keep_next=True)
    figure = get_style(doc, "Figure", "Figure")
    set_para(figure, jc="center", before=240, line=240, keep_next=True)

    # References: left aligned with hanging indent (template "REFERENCIAS" note).
    bib = get_style(doc, "Bibliography", "Bibliography")
    set_para(bib, jc="left", after=115, line=360, left=720, hanging=720)
    set_run(bib)

    footnote = get_style(doc, "FootnoteText", "footnote text")
    set_para(footnote, jc="both", line=240)
    set_run(footnote, size=9)

    # Table of contents / figures / tables: dotted leader to the right margin.
    for level in (1, 2, 3):
        toc = get_style(doc, f"TOC{level}", f"toc {level}")
        set_para(
            toc,
            before=0,
            after=120,
            left=(level - 1) * 440,
            tabs=[("right", TEXT_WIDTH, "dot")],
        )
        set_run(toc)


def strip_body(doc) -> None:
    """Remove the template body, keeping one empty paragraph and a single final section.

    The template's page-number footer is referenced only from its first section, so the
    references are moved to the final section, which is what Pandoc copies.
    """
    body = doc.element.body
    sect_prs = body.findall(".//" + qn("w:sectPr"))
    first_sect, final_sect = sect_prs[0], sect_prs[-1]
    footer_refs = [copy.deepcopy(r) for r in first_sect.findall(qn("w:footerReference"))]
    for child in list(body):
        if child is not final_sect:
            body.remove(child)
    for old in final_sect.findall(qn("w:footerReference")) + final_sect.findall(qn("w:titlePg")):
        final_sect.remove(old)
    for ref in reversed(footer_refs):
        if ref.get(qn("w:type")) == "default":
            final_sect.insert(0, ref)
    body.insert(0, _el("w:p"))


def build(src: Path, dst: Path) -> None:
    doc = Document(src)
    strip_body(doc)
    define_styles(doc)
    doc.core_properties.title = "UANL reference document"
    doc.core_properties.author = ""
    doc.save(dst)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--dst", type=Path, default=DEFAULT_DST)
    args = parser.parse_args(argv)
    build(args.src, args.dst)
    print(f"wrote {args.dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
