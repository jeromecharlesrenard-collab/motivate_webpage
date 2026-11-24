"""Info page: build site/info.html from the Word master copy assets/MOTIVATE_info_page.docx.

The .docx is read directly (a zip of XML), no extra package. Mapping:
- bold paragraph, 14 pt or larger -> section title (the first one is the page title)
- bold paragraph, smaller         -> sub-title
- bullet / numbered list item     -> <ul> / <ol> item
- other paragraph                 -> <p>; empty paragraphs only end a list
- bold / italic / underline runs  -> <strong> / <em> / <u>; text is escaped, so "<br>" shows as typed
Page look (fonts, width, closing) comes from app/info_template.html.
"""

from __future__ import annotations

import html
import logging
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

log = logging.getLogger(__name__)

DOCX_NAME = "MOTIVATE_info_page.docx"          # in assets/
PAGE_NAME = "info.html"                        # in site/
TEMPLATE = Path(__file__).with_name("info_template.html")
BODY_MARK = "<!-- INFO-BODY -->"
TITLE_SIZE = 28                                # half-points: 14 pt

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ORDERED = {"decimal", "decimalZero", "lowerLetter", "upperLetter", "lowerRoman", "upperRoman"}


def _on(el: ET.Element | None) -> bool:
    """True for a w:b / w:i / w:u style toggle that is switched on."""
    if el is None:
        return False
    val = el.get(W + "val", "true")
    return val not in ("0", "false", "none")


def _list_kinds(z: zipfile.ZipFile) -> tuple[dict[str, str], dict[str, str]]:
    """(numId -> 'ul'/'ol', list styleId -> numId) from numbering.xml and styles.xml."""
    kinds: dict[str, str] = {}
    if "word/numbering.xml" in z.namelist():
        root = ET.fromstring(z.read("word/numbering.xml"))
        abstract = {}
        for a in root.iter(W + "abstractNum"):
            fmt = a.find(f"{W}lvl/{W}numFmt")
            abstract[a.get(W + "abstractNumId")] = fmt.get(W + "val") if fmt is not None else "bullet"
        for n in root.iter(W + "num"):
            ref = n.find(W + "abstractNumId")
            fmt = abstract.get(ref.get(W + "val") if ref is not None else "", "bullet")
            kinds[n.get(W + "numId")] = "ol" if fmt in ORDERED else "ul"
    style_num: dict[str, str] = {}
    if "word/styles.xml" in z.namelist():
        for st in ET.fromstring(z.read("word/styles.xml")).iter(W + "style"):
            num = st.find(f"{W}pPr/{W}numPr/{W}numId")
            if num is not None:
                style_num[st.get(W + "styleId")] = num.get(W + "val")
    return kinds, style_num


def _runs(p: ET.Element) -> list[tuple[str, bool, bool, bool, int]]:
    """(text, bold, italic, underline, size in half-points) for every run with text."""
    out = []
    for r in p.iter(W + "r"):
        rpr = r.find(W + "rPr")
        bold = italic = under = False
        size = 24
        if rpr is not None:
            bold, italic, under = _on(rpr.find(W + "b")), _on(rpr.find(W + "i")), _on(rpr.find(W + "u"))
            sz = rpr.find(W + "sz")
            if sz is not None and sz.get(W + "val", "").isdigit():
                size = int(sz.get(W + "val"))
        parts = []
        for child in r:
            if child.tag == W + "t":
                parts.append(html.escape(child.text or "", quote=False))
            elif child.tag == W + "tab":
                parts.append(" ")
            elif child.tag in (W + "br", W + "cr"):
                parts.append("<br>")
        text = "".join(parts)
        if text:
            out.append((text, bold, italic, under, size))
    return out


def docx_to_html(docx: Path) -> str:
    """HTML body (titles, paragraphs, lists) for the info page."""
    with zipfile.ZipFile(docx) as z:
        kinds, style_num = _list_kinds(z)
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
    lines: list[str] = []
    open_list = None
    have_title = False

    def close_list() -> None:
        nonlocal open_list
        if open_list:
            lines.append(f"        </{open_list}>")
            open_list = None

    for p in body.iter(W + "p"):
        runs = _runs(p)
        if not "".join(t for t, *_ in runs).strip():
            close_list()
            continue
        ppr = p.find(W + "pPr")
        num = ppr.find(f"{W}numPr/{W}numId") if ppr is not None else None
        style = ppr.find(W + "pStyle") if ppr is not None else None
        num_id = num.get(W + "val") if num is not None else style_num.get(style.get(W + "val")) if style is not None else None
        kind = kinds.get(num_id, "ul") if num_id not in (None, "0") else None

        visible = [r for r in runs if r[0].strip()]
        if kind is None and all(b for _, b, *_ in visible):
            close_list()
            text = "".join(t for t, *_ in runs).strip()
            if max(size for *_, size in visible) >= TITLE_SIZE:
                tag = "h2" if have_title else "h1"
                have_title = True
            else:
                tag = "h3"
            lines.append(f"        <{tag}>{text}</{tag}>")
            continue

        inner = ""
        for text, bold, italic, under, _ in runs:
            if under:
                text = f"<u>{text}</u>"
            if italic:
                text = f"<em>{text}</em>"
            if bold:
                text = f"<strong>{text}</strong>"
            inner += text
        inner = inner.replace("</strong><strong>", "").strip()
        if kind:
            if open_list != kind:
                close_list()
                lines.append(f"        <{kind}>")
                open_list = kind
            lines.append(f"            <li>{inner}</li>")
        else:
            close_list()
            lines.append(f"        <p>{inner}</p>")
    close_list()
    return "\n".join(lines)


def build(docx: Path, page: Path) -> None:
    """Write the info page from the docx and the template."""
    page.write_text(TEMPLATE.read_text(encoding="utf-8").replace(BODY_MARK, docx_to_html(docx)), encoding="utf-8")


def refresh(project_dir: Path) -> bool:
    """Rebuild site/info.html if the docx (or the template) is newer; True if it was rebuilt."""
    docx = project_dir / "assets" / DOCX_NAME
    page = project_dir / "site" / PAGE_NAME
    if not docx.exists():
        log.warning("Info page source missing: %s", docx)
        return False
    if page.exists() and page.stat().st_mtime >= max(docx.stat().st_mtime, TEMPLATE.stat().st_mtime):
        return False
    try:
        build(docx, page)
    except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        log.error("Info page not rebuilt from %s: %s", docx.name, exc)
        return False
    log.info("Info page rebuilt from %s", docx.name)
    return True
