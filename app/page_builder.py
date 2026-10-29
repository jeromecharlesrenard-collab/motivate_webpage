"""Page builder logic: render, insert, load, and edit MOTIVATE pages.

No UI here. The browser form (site/builder.html) talks to the local server
(app/server.py), which calls load_page() / write_preview() / insert_page() / update_page().

Line text is stored as typed, with a few inline tags and entities kept as HTML:
<strong> <b> <em> <i> <u> <br> <a href="NN_page.html"> and entities such as &nbsp; &bull;.
Everything else is escaped.
"""

from __future__ import annotations

import html
import json
import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

EDT = ZoneInfo("America/New_York")
MAX_LINES = 20
MAX_TEXT = 500
PREVIEW_FILE = "_preview.html"

FONTS: dict[str, str] = {
    "Arial": "sans-serif",
    "Arial Black": "sans-serif",
    "Calibri": "sans-serif",
    "Segoe UI": "sans-serif",
    "Tahoma": "sans-serif",
    "Verdana": "sans-serif",
    "Georgia": "serif",
    "Times New Roman": "serif",
    "Courier New": "monospace",
}
FONT_TYPES: dict[str, tuple[str, str]] = {   # name -> (font-weight, font-style)
    "Normal": ("normal", "normal"),
    "Bold": ("bold", "normal"),
    "Italic": ("normal", "italic"),
    "Bold Italic": ("bold", "italic"),
}
H_ALIGNS: dict[str, tuple[str, str]] = {     # name -> (flex alignment, text-align)
    "Center": ("center", "center"),
    "Left": ("flex-start", "left"),
    "Right": ("flex-end", "right"),
}
V_ALIGNS: dict[str, str] = {"Middle": "center", "Top": "flex-start", "Bottom": "flex-end"}

FAVICON = (
    "<link rel=\"icon\" type=\"image/svg+xml\" href=\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
    "viewBox='0 0 24 24' fill='none' stroke='%2300b050' stroke-width='2' stroke-linecap='round' "
    "stroke-linejoin='round'><circle cx='12' cy='12' r='10'/><path d='M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8'/>"
    "<path d='M12 18V6'/></svg>\">"
)
PAGES_BLOCK = re.compile(r"(// PAGES-BEGIN\n)(.*?)(\n\s*// PAGES-END)", re.S)
HREF = re.compile(r'href="([^"#?]+\.html)')
PLACEHOLDER = "<!-- placeholder -->"

INLINE_TAG = re.compile(
    r"<(/?)(strong|b|em|i|u)>|<br\s*/?>|</a>"
    r'|<a((?:\s+(?:class|title)="[^"<>]*"|\s+href="[\w.-]+\.html")+)\s*>',
    re.I,
)
ENTITY = re.compile(r"&(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9a-fA-F]+);")
STYLE_BLOCK = re.compile(r"<style>(.*?)</style>", re.S)
CLASS_RULE = re.compile(r"\.page\s+\.([\w-]+)\s*\{([^}]*)\}")
PAGE_RULE = re.compile(r"\.page\s*\{([^}]*)\}")
MAIN_BLOCK = re.compile(r'<main class="page">(.*?)</main>', re.S)
SUB_SECTION = re.compile(r'<div class="sub-section"(?:\s+style="([^"]*)")?\s*>')
LINE_DIV = re.compile(r'<div class="([\w-]+)">(.*?)</div>', re.S)


# ---------------------------------------------------------- line text ----

def _escape(text: str) -> str:
    """Escape < > & but keep valid entities (&nbsp; &bull; ...) as typed."""
    out, pos = [], 0
    for m in ENTITY.finditer(text):
        out += [html.escape(text[pos:m.start()], quote=False), m.group(0)]
        pos = m.end()
    out.append(html.escape(text[pos:], quote=False))
    return "".join(out)


def clean_text(text: str) -> str:
    """Line text -> safe HTML: allowed inline tags kept (and balanced), the rest escaped."""
    out: list[str] = []
    stack: list[str] = []
    pos = 0
    for m in INLINE_TAG.finditer(text):
        out.append(_escape(text[pos:m.start()]))
        pos = m.end()
        tag = m.group(0)
        if tag.lower().startswith("<br"):
            out.append("<br>")
        elif m.group(2):                                # strong / b / em / i / u
            name = m.group(2).lower()
            if not m.group(1):
                stack.append(name)
                out.append(f"<{name}>")
            elif stack and stack[-1] == name:
                stack.pop()
                out.append(f"</{name}>")
        elif m.group(3) is not None:                    # <a ...>
            stack.append("a")
            out.append(tag)
        elif stack and stack[-1] == "a":                # </a>
            stack.pop()
            out.append("</a>")
    out.append(_escape(text[pos:]))
    out += [f"</{name}>" for name in reversed(stack)]
    return "".join(out)


# ---------------------------------------------------------------- spec ----

def _number(data: dict[str, Any], key: str, default: float, low: float, high: float, label: str) -> float:
    """Read a number from the form data and check its range."""
    raw = data.get(key, default)
    try:
        value = float(default if raw in ("", None) else raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number") from None
    if not low <= value <= high:
        raise ValueError(f"{label} must be between {low:g} and {high:g}")
    return value


def _choice(data: dict[str, Any], key: str, options: dict[str, Any], default: str, label: str) -> str:
    value = str(data.get(key) or default)
    if value not in options:
        raise ValueError(f"{label} must be one of: {', '.join(options)}")
    return value


@dataclass
class LineSpec:
    """One line of text on the page."""

    text: str
    font: str = "Arial Black"
    size: float = 3.0           # rem
    font_type: str = "Normal"
    color: str = "#083a5e"
    space_after: float = 0.5    # rem

    @classmethod
    def from_dict(cls, data: dict[str, Any], n: int) -> LineSpec:
        color = str(data.get("color") or "#083a5e")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError(f"Line {n}: color must look like #083a5e")
        text = str(data.get("text", "")).strip(" \t\r\n")   # keep non-breaking spaces
        if len(text) > MAX_TEXT:
            raise ValueError(f"Line {n}: {MAX_TEXT} characters max")
        return cls(
            text=text,
            font=_choice(data, "font", FONTS, "Arial Black", f"Line {n}: font"),
            size=_number(data, "size", 3.0, 0.5, 20, f"Line {n}: font size"),
            font_type=_choice(data, "font_type", FONT_TYPES, "Normal", f"Line {n}: font type"),
            color=color.lower(),
            space_after=_number(data, "space_after", 0.5, 0, 20, f"Line {n}: spacing after"),
        )


@dataclass
class PageSpec:
    """Everything the builder form collects for one page."""

    number: int
    name: str
    h_align: str = "Center"
    h_indent: float = 0.0       # rem
    v_align: str = "Middle"
    v_indent: float = 0.0       # rem
    lines: list[LineSpec] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PageSpec:
        try:
            number = int(data.get("number"))
        except (TypeError, ValueError):
            raise ValueError("Page number must be a whole number") from None
        name = " ".join(str(data.get("name", "")).split())
        if not name:
            raise ValueError("Page name is required")
        if len(name) > 40 or re.search(r"[<>\"\\]", name):
            raise ValueError('Page name: 40 characters max, without < > " \\')
        raw_lines = data.get("lines") or []
        if len(raw_lines) > MAX_LINES:
            raise ValueError(f"A page has at most {MAX_LINES} lines")
        lines = [LineSpec.from_dict(d, i + 1) for i, d in enumerate(raw_lines)]
        lines = [ln for ln in lines if ln.text]
        if not lines:
            raise ValueError("Enter text on at least one line")
        return cls(
            number=number,
            name=name,
            h_align=_choice(data, "h_align", H_ALIGNS, "Center", "Horizontal alignment"),
            h_indent=_number(data, "h_indent", 0, 0, 50, "Horizontal indent"),
            v_align=_choice(data, "v_align", V_ALIGNS, "Middle", "Vertical alignment"),
            v_indent=_number(data, "v_indent", 0, 0, 50, "Vertical indent"),
            lines=lines,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number, "name": self.name,
            "h_align": self.h_align, "h_indent": self.h_indent,
            "v_align": self.v_align, "v_indent": self.v_indent,
            "lines": [ln.__dict__ for ln in self.lines],
        }


# -------------------------------------------------------------- render ----

def slug(label: str) -> str:
    """File-name part for a page label: 'Key Points' -> 'key_points'."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:30] or "page"


def page_file(number: int, label: str) -> str:
    return f"{number:02d}_{slug(label)}.html"


def _css_font(font: str) -> str:
    return f"'{font}', {FONTS[font]}" if " " in font else f"{font}, {FONTS[font]}"


def render_page(spec: PageSpec, title: str, data_page: str | None = None) -> str:
    """Return the full HTML for a page, in the same structure as the other page files."""
    flex, text_align = H_ALIGNS[spec.h_align]
    page_rules = [f"align-items: {flex};", f"justify-content: {V_ALIGNS[spec.v_align]};", f"text-align: {text_align};"]
    if spec.h_align == "Left":
        page_rules.append(f"padding-left: calc(5vw + {spec.h_indent:g}rem);")
    elif spec.h_align == "Right":
        page_rules.append(f"padding-right: calc(5vw + {spec.h_indent:g}rem);")
    if spec.v_align == "Top":
        page_rules.append(f"padding-top: calc(2rem + {spec.v_indent:g}rem);")
    elif spec.v_align == "Bottom":
        page_rules.append(f"padding-bottom: calc(2rem + {spec.v_indent:g}rem);")

    styles = [
        f"        .page {{ {' '.join(page_rules)} }}",
        f"        .page .sub-section {{ align-items: {flex}; gap: 0; }}",
    ]
    body = []
    for i, ln in enumerate(spec.lines, 1):
        weight, style = FONT_TYPES[ln.font_type]
        styles.append(
            f"        .page .line-{i} {{ font-size: {ln.size:g}rem; font-family: {_css_font(ln.font)}; "
            f"color: {ln.color}; font-weight: {weight}; font-style: {style}; margin-bottom: {ln.space_after:g}rem; }}"
        )
        body.append(f'            <div class="line-{i}">{clean_text(ln.text)}</div>')

    number = data_page or str(spec.number)
    return "\n".join([
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1">',
        f"    {FAVICON}",
        f"    <title>{html.escape(title)}</title>",
        '    <link rel="stylesheet" href="css/motivate.css">',
        "    <style>",
        *styles,
        "    </style>",
        "</head>",
        f'<body data-page="{number}">',
        "",
        f"    <!-- ============================ PAGE {number} - {spec.name.upper()} ============================ -->",
        '    <main class="page">',
        '        <div class="sub-section">',
        *body,
        "        </div>",
        "    </main>",
        "",
        '    <script src="js/nav.js"></script>',
        "</body>",
        "</html>",
        "",
    ])


def write_preview(site_dir: Path, spec: PageSpec) -> Path:
    """Write site/_preview.html (not part of the page list) and return its path."""
    path = site_dir / PREVIEW_FILE
    path.write_text(render_page(spec, "PREVIEW", data_page="preview"), encoding="utf-8", newline="\n")
    log.info("Preview written for page %s %r", spec.number, spec.name)
    return path


# ---------------------------------------------------------------- load ----

def editable_text(inner_html: str) -> str:
    """Page HTML for one line -> text for the form (inverse of clean_text).

    &amp; &quot; &#39; become plain characters unless that would create an entity;
    tags and other entities (&nbsp; &bull; &lt;) stay as written.
    """
    text = " ".join(inner_html.split())
    text = re.sub(r"&amp;(?![a-zA-Z][a-zA-Z0-9]*;|#\d+;|#x[0-9a-fA-F]+;)", "&", text)
    return text.replace("&quot;", '"').replace("&#39;", "'")


def _decls(css: str) -> dict[str, str]:
    """'a: 1; b: 2' -> {'a': '1', 'b': '2'}."""
    pairs = (d.split(":", 1) for d in css.split(";") if ":" in d)
    return {k.strip().lower(): v.strip() for k, v in pairs}


def _rem(value: str | None, default: float = 0.0) -> float:
    """Last 'Nrem' in a CSS value ('3rem', 'calc(5vw + 2rem)') -> N."""
    found = re.findall(r"([\d.]+)rem", value or "")
    return float(found[-1]) if found else default


def _calc_rem(value: str | None) -> float:
    """Indent part of 'calc(5vw + 2rem)' -> 2; anything else -> 0."""
    m = re.search(r"\+\s*([\d.]+)rem", value or "")
    return float(m.group(1)) if m else 0.0


def _color(value: str | None) -> str:
    v = (value or "#000000").strip().lower()
    if re.fullmatch(r"#[0-9a-f]{3}", v):
        v = "#" + "".join(c * 2 for c in v[1:])
    return v if re.fullmatch(r"#[0-9a-f]{6}", v) else "#000000"


def _line_from_css(text: str, rule: dict[str, str], gap: float) -> LineSpec:
    family = rule.get("font-family", "Arial").split(",")[0].strip().strip("'\"")
    font = next((f for f in FONTS if f.lower() == family.lower()), "Arial")
    weight = rule.get("font-weight", "normal")
    bold = weight == "bold" or weight == "bolder" or (weight.isdigit() and int(weight) >= 600)
    italic = rule.get("font-style", "normal") == "italic"
    font_type = {(False, False): "Normal", (True, False): "Bold",
                 (False, True): "Italic", (True, True): "Bold Italic"}[(bold, italic)]
    return LineSpec(
        text=text,
        font=font,
        size=_rem(rule.get("font-size"), 1.0),
        font_type=font_type,
        color=_color(rule.get("color")),
        space_after=_rem(rule["margin-bottom"]) if "margin-bottom" in rule else gap,
    )


def page_spec_from_html(text: str, number: int, name: str) -> PageSpec:
    """Read a page file (original or builder-made) back into a PageSpec."""
    style = STYLE_BLOCK.search(text)
    css = style.group(1) if style else ""
    rules = {m.group(1): _decls(m.group(2)) for m in CLASS_RULE.finditer(css)}
    page_rule = PAGE_RULE.search(css)
    page = _decls(page_rule.group(1)) if page_rule else {}

    main = MAIN_BLOCK.search(text)
    body = main.group(1) if main else text
    sub = SUB_SECTION.search(body)
    sub_decls = rules.get("sub-section", {}) | _decls((sub.group(1) or "") if sub else "")
    if sub:
        body = body[sub.end():]
    gap = _rem(sub_decls.get("gap"))

    align = sub_decls.get("align-items") or page.get("align-items", "center")
    text_align = sub_decls.get("text-align") or page.get("text-align", "center")
    h_align = "Left" if "start" in align or text_align == "left" else (
        "Right" if "end" in align or text_align == "right" else "Center")
    justify = page.get("justify-content", "center")
    v_align = "Top" if "start" in justify else ("Bottom" if "end" in justify else "Middle")

    lines = [
        _line_from_css(editable_text(inner), rules.get(cls, {}), gap)
        for cls, inner in LINE_DIV.findall(body)
        if cls != "sub-section"
    ]
    return PageSpec(
        number=number,
        name=name,
        h_align=h_align,
        h_indent=_calc_rem(page.get(f"padding-{h_align.lower()}")) if h_align != "Center" else 0.0,
        v_align=v_align,
        v_indent=_calc_rem(page.get("padding-" + {"Top": "top", "Bottom": "bottom"}.get(v_align, ""))),
        lines=lines,
    )


def _content_page(pages: list[dict[str, str]], number: int) -> dict[str, str]:
    entry = next((p for p in pages[1:] if p["id"] == str(number)), None)
    if entry is None:
        raise ValueError(f"Page number must be between 1 and {len(pages) - 1}")
    return entry


def load_page(site_dir: Path, number: int) -> PageSpec:
    """Return the spec of existing page `number`, for editing."""
    entry = _content_page(read_pages(site_dir), number)
    text = (site_dir / entry["file"]).read_text(encoding="utf-8")
    return page_spec_from_html(text, number, entry["label"])


# ------------------------------------------------------------ page list ----

def read_pages(site_dir: Path) -> list[dict[str, str]]:
    """Return the PAGES list from site/js/nav.js (home page first)."""
    text = (site_dir / "js" / "nav.js").read_text(encoding="utf-8")
    block = PAGES_BLOCK.search(text)
    if not block:
        raise ValueError("nav.js: PAGES-BEGIN / PAGES-END markers not found")
    body = block.group(2)
    body = body[body.index("[") : body.rindex("]") + 1]
    return json.loads(body)


def write_pages(site_dir: Path, pages: list[dict[str, str]]) -> None:
    """Rewrite the PAGES block in site/js/nav.js, one page per line."""
    nav = site_dir / "js" / "nav.js"
    rows = ",\n".join("        " + json.dumps(p, ensure_ascii=False) for p in pages)
    new_block = f"    const PAGES = [\n{rows}\n    ];"
    text = PAGES_BLOCK.sub(lambda m: m.group(1) + new_block + m.group(3), nav.read_text(encoding="utf-8"))
    nav.write_text(text, encoding="utf-8", newline="\n")


def backup_site(site_dir: Path, backup_dir: Path) -> Path:
    """Zip the whole site folder before changing it; return the zip path."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(EDT).strftime("%y%m%d_%H%M%S")
    target = backup_dir / f"site_backup_{stamp}.zip"
    n = 1
    while target.exists():
        n += 1
        target = backup_dir / f"site_backup_{stamp}_{n}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in site_dir.rglob("*"):
            if f.is_file() and f.name != PREVIEW_FILE:
                zf.write(f, f.relative_to(site_dir))
    log.info("Site backed up to %s", target)
    return target


def _rewrite_links(site_dir: Path, renames: dict[str, str]) -> None:
    """Point every href="old.html" in every page at its new file name."""
    if not renames:
        return
    for path in site_dir.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        updated = HREF.sub(lambda m: 'href="' + renames.get(m.group(1), m.group(1)), text)
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")


# --------------------------------------------------------------- insert ----

def insert_page(site_dir: Path, spec: PageSpec, backup_dir: Path | None = None) -> Path:
    """Create page spec.number; pages at that number and above move up by one.

    Renames the shifted files, updates their data-page / title / placeholder text,
    rewrites links between pages in every HTML file, and rewrites the nav.js PAGES list.
    """
    pages = read_pages(site_dir)
    home, content = pages[0], pages[1:]
    k = spec.number
    if not 1 <= k <= len(content) + 1:
        raise ValueError(f"Page number must be between 1 and {len(content) + 1}")
    if backup_dir is not None:
        backup_site(site_dir, backup_dir)

    renames: dict[str, str] = {}
    shifted: list[tuple[dict[str, str], int, int]] = []
    new_list = [home]
    for p in content:
        old = int(p["id"])
        if old < k:
            new_list.append(p)
            continue
        new = old + 1
        q = dict(p, id=str(new))
        if re.fullmatch(rf"Page {old}", p["label"], re.I):
            q["label"] = f"Page {new}"
        if p["title"] == f"JR{old}":
            q["title"] = f"JR{new}"
        q["file"] = page_file(new, q["label"])
        renames[p["file"]] = q["file"]
        shifted.append((q, old, new))
        new_list.append(q)

    new_entry = {"id": str(k), "file": page_file(k, spec.name), "label": spec.name, "title": f"JR{k}"}
    new_list.insert(k, new_entry)

    # Two-phase rename so 05_x -> 06_y never overwrites a file not yet moved.
    temps = {}
    for old_file in renames:
        tmp = site_dir / f"~renumber_{old_file}"
        (site_dir / old_file).rename(tmp)
        temps[old_file] = tmp
    for old_file, tmp in temps.items():
        tmp.rename(site_dir / renames[old_file])

    for q, old, new in shifted:
        path = site_dir / q["file"]
        text = path.read_text(encoding="utf-8")
        text = text.replace(f'data-page="{old}"', f'data-page="{new}"', 1)
        text = re.sub(rf"(<!-- =+ PAGE ){old}( - )", rf"\g<1>{new}\g<2>", text, count=1)
        text = text.replace(f"<title>JR{old}</title>", f"<title>{html.escape(q['title'])}</title>", 1)
        if PLACEHOLDER in text:
            text = text.replace(f">PAGE {old}<", f">PAGE {new}<")
            text = re.sub(rf"(<!-- =+ PAGE {new} - )PAGE {old}\b", rf"\g<1>PAGE {new}", text, count=1)
        path.write_text(text, encoding="utf-8", newline="\n")

    _rewrite_links(site_dir, renames)

    target = site_dir / new_entry["file"]
    target.write_text(render_page(spec, new_entry["title"]), encoding="utf-8", newline="\n")
    write_pages(site_dir, new_list)
    log.info("Created page %s %r as %s; renumbered %d page(s)", k, spec.name, target.name, len(shifted))
    return target


# ----------------------------------------------------------------- edit ----

def update_page(site_dir: Path, spec: PageSpec, backup_dir: Path | None = None) -> Path:
    """Rewrite existing page spec.number from the spec (same number and tab title).

    A new page name renames the file (NN_new_name.html) and updates the menu and links.
    """
    pages = read_pages(site_dir)
    entry = _content_page(pages, spec.number)
    if backup_dir is not None:
        backup_site(site_dir, backup_dir)

    old_file = entry["file"]
    new_file = old_file if spec.name == entry["label"] else page_file(spec.number, spec.name)
    if new_file != old_file:
        if (site_dir / new_file).exists():
            raise ValueError(f"{new_file} already exists")
        (site_dir / old_file).rename(site_dir / new_file)
        entry["file"] = new_file
        _rewrite_links(site_dir, {old_file: new_file})
    entry["label"] = spec.name

    target = site_dir / new_file
    target.write_text(render_page(spec, entry["title"]), encoding="utf-8", newline="\n")
    write_pages(site_dir, pages)
    log.info("Edited page %s %r (%s)", spec.number, spec.name, target.name)
    return target


# --------------------------------------------------------- placeholders ----

def placeholder_spec(number: int) -> PageSpec:
    """Spec for an empty 'PAGE N' placeholder page."""
    return PageSpec(number=number, name=f"Page {number}", lines=[LineSpec(text=f"PAGE {number}", size=5)])


def add_placeholder(site_dir: Path, number: int, backup_dir: Path | None = None) -> Path:
    """Insert a 'PAGE N' placeholder page (marked so renumbering updates its text)."""
    path = insert_page(site_dir, placeholder_spec(number), backup_dir)
    text = path.read_text(encoding="utf-8")
    text = text.replace('    <main class="page">', f'    {PLACEHOLDER}\n    <main class="page">', 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path
