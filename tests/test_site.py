"""Checks on the multi-page site and the launcher logic (no browser is opened)."""

import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app import launcher, page_builder

SITE = launcher.SITE_DIR
NAV_PAGES = [(p["id"], p["file"]) for p in page_builder.read_pages(SITE)]
EXTRA_FILES = {"builder.html"}          # in site/ but not in the page list
HTML_FILES = sorted(p for p in SITE.glob("*.html") if not p.name.startswith("_"))
VOID = {"meta", "link", "br", "img", "input", "hr"}


class TagBalance(HTMLParser):
    """Collect hrefs/srcs and verify every non-void tag is closed in order."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.refs: list[str] = []
        self.errors: list[str] = []
        self.body_page: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "body":
            self.body_page = a.get("data-page")
        for key in ("href", "src"):
            if a.get(key) and not a[key].startswith(("data:", "#", "http")):
                self.refs.append(a[key])
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack[-3:]})")
        else:
            self.stack.pop()


def parse(path: Path) -> TagBalance:
    parser = TagBalance()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def test_page_list_is_numbered_in_order() -> None:
    assert [i for i, _ in NAV_PAGES] == [str(n) for n in range(len(NAV_PAGES))]
    for _, file in NAV_PAGES:
        assert (SITE / file).exists(), file


def test_every_html_file_is_in_nav() -> None:
    assert {p.name for p in HTML_FILES} == {file for _, file in NAV_PAGES} | EXTRA_FILES


@pytest.mark.parametrize("path", HTML_FILES, ids=lambda p: p.name)
def test_page_markup(path: Path) -> None:
    parser = parse(path)
    assert not parser.errors and not parser.stack, (parser.errors, parser.stack)
    if path.name not in EXTRA_FILES:
        assert parser.body_page == dict((f, i) for i, f in NAV_PAGES)[path.name]
    for ref in parser.refs:
        assert (SITE / ref).exists(), f"{path.name} -> {ref}"
    assert "css/motivate.css" in parser.refs and "js/nav.js" in parser.refs


def test_marathon_links_to_patience() -> None:
    marathon = next(f for _, f in NAV_PAGES if f.endswith("_marathon.html"))
    patience = next(f for _, f in NAV_PAGES if f.endswith("_patience.html"))
    assert f'href="{patience}"' in (SITE / marathon).read_text(encoding="utf-8")


def test_load_config_creates_defaults(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    assert launcher.load_config(cfg) == launcher.DEFAULT_CONFIG
    assert json.loads(cfg.read_text(encoding="utf-8")) == launcher.DEFAULT_CONFIG


def test_start_page_falls_back_to_index() -> None:
    assert launcher.start_page_path({"start_page": "05_thinking.html"}).name == "05_thinking.html"
    assert launcher.start_page_path({"start_page": "missing.html"}).name == "index.html"
    assert launcher.start_page_path({"start_page": "../main.py"}).name == "index.html"


# ------------------------------------------------------------ page builder ----

def make_site(tmp_path: Path) -> Path:
    """A small copy of the site: home, 1 Alpha (links to 2), 2 Beta, 3 placeholder."""
    site = tmp_path / "site"
    (site / "js").mkdir(parents=True)
    (site / "js" / "nav.js").write_text(
        (SITE / "js" / "nav.js").read_text(encoding="utf-8"), encoding="utf-8"
    )
    page_builder.write_pages(site, [{"id": "0", "file": "index.html", "label": "Home", "title": "MOTIVATE HOME"}])
    (site / "index.html").write_text('<body data-page="0"></body>', encoding="utf-8")
    page_builder.insert_page(site, page_builder.PageSpec.from_dict(
        {"number": 1, "name": "Alpha", "lines": [{"text": "A"}]}))
    page_builder.insert_page(site, page_builder.PageSpec.from_dict(
        {"number": 2, "name": "Beta", "lines": [{"text": "B"}]}))
    page_builder.add_placeholder(site, 3)
    alpha = site / "01_alpha.html"
    alpha.write_text(alpha.read_text(encoding="utf-8").replace(
        '<div class="line-1">A</div>', '<div class="line-1"><a href="02_beta.html">A</a></div>'), encoding="utf-8")
    return site


def spec(**kw) -> page_builder.PageSpec:
    data = {"number": 2, "name": "New Page", "lines": [{"text": "HELLO <world>"}]} | kw
    return page_builder.PageSpec.from_dict(data)


def test_insert_renumbers_following_pages(tmp_path: Path) -> None:
    site = make_site(tmp_path)
    page_builder.insert_page(site, spec(), tmp_path / "backups")
    pages = page_builder.read_pages(site)
    assert [(p["id"], p["file"], p["title"]) for p in pages] == [
        ("0", "index.html", "MOTIVATE HOME"),
        ("1", "01_alpha.html", "JR1"),
        ("2", "02_new_page.html", "JR2"),
        ("3", "03_beta.html", "JR3"),
        ("4", "04_page_4.html", "JR4"),
    ]
    assert sorted(p.name for p in site.glob("*.html")) == [
        "01_alpha.html", "02_new_page.html", "03_beta.html", "04_page_4.html", "index.html"]
    beta = (site / "03_beta.html").read_text(encoding="utf-8")
    assert 'data-page="3"' in beta and "<title>JR3</title>" in beta
    assert 'href="03_beta.html"' in (site / "01_alpha.html").read_text(encoding="utf-8")
    placeholder = (site / "04_page_4.html").read_text(encoding="utf-8")
    assert ">PAGE 4<" in placeholder and "PAGE 4 - PAGE 4" in placeholder
    new = (site / "02_new_page.html").read_text(encoding="utf-8")
    assert "HELLO &lt;world&gt;" in new and 'data-page="2"' in new
    assert len(list((tmp_path / "backups").glob("site_backup_*.zip"))) == 1


def test_insert_at_end_renames_nothing(tmp_path: Path) -> None:
    site = make_site(tmp_path)
    page_builder.insert_page(site, spec(number=4))
    assert [p["file"] for p in page_builder.read_pages(site)][-1] == "04_new_page.html"
    assert (site / "03_page_3.html").exists()


def test_alignment_and_line_styles() -> None:
    html = page_builder.render_page(spec(
        h_align="Right", h_indent=2, v_align="Top", v_indent=1,
        lines=[{"text": "X", "font": "Times New Roman", "size": 2.5, "font_type": "Bold Italic",
                "color": "#FF0000", "space_after": 1}]), "JR2")
    assert "align-items: flex-end;" in html and "padding-right: calc(5vw + 2rem);" in html
    assert "justify-content: flex-start;" in html and "padding-top: calc(2rem + 1rem);" in html
    assert ("font-size: 2.5rem; font-family: 'Times New Roman', serif; color: #ff0000; "
            "font-weight: bold; font-style: italic; margin-bottom: 1rem;") in html


@pytest.mark.parametrize("bad, message", [
    ({"name": ""}, "name is required"),
    ({"lines": [{"text": ""}]}, "at least one line"),
    ({"lines": [{"text": "x", "color": "red"}]}, "color"),
    ({"lines": [{"text": "x", "font": "Comic Sans"}]}, "font must be"),
    ({"lines": [{"text": "x", "size": 99}]}, "font size"),
    ({"h_align": "Justify"}, "Horizontal alignment"),
])
def test_spec_validation(bad: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        spec(**bad)


@pytest.mark.parametrize("number", range(1, len(NAV_PAGES)))
def test_every_real_page_loads_and_round_trips(number: int) -> None:
    loaded = page_builder.load_page(SITE, number)
    assert loaded.lines and len(loaded.lines) <= page_builder.MAX_LINES
    again = page_builder.PageSpec.from_dict(loaded.to_dict())
    html = page_builder.render_page(again, "T")
    assert page_builder.page_spec_from_html(html, number, loaded.name) == loaded


def test_load_original_page_styles() -> None:
    key = page_builder.load_page(SITE, 1)
    first = key.lines[0]
    assert (first.text, first.font, first.size, first.color) == (
        "NO TRADE BEFORE 10:00am EDT", "Arial Black", 4.0, "#083a5e")
    assert key.lines[1].text == "&nbsp;" and key.lines[1].color == "#ffffff"
    assert any(ln.text == "SET & FORGET" for ln in key.lines)
    page8 = page_builder.load_page(SITE, 8)
    assert page8.h_align == "Left" and page8.lines[1].text.startswith("<strong>Alignment:</strong>")


@pytest.mark.parametrize("typed, html", [
    ("P&L", "P&amp;L"),
    ("A &nbsp; &bull; B", "A &nbsp; &bull; B"),
    ("<strong>Bold</strong> text<br>next", "<strong>Bold</strong> text<br>next"),
    ("<b>open", "<b>open</b>"),
    ("stray </em> close", "stray  close"),
    ("<script>x</script>", "&lt;script&gt;x&lt;/script&gt;"),
    ('<a href="javascript:x">y</a>', '&lt;a href="javascript:x"&gt;y'),
    ('<a class="text-link" href="13_patience.html">go</a>', '<a class="text-link" href="13_patience.html">go</a>'),
])
def test_clean_text(typed: str, html: str) -> None:
    assert page_builder.clean_text(typed) == html


def test_update_page_rewrites_lines_and_keeps_number(tmp_path: Path) -> None:
    site = make_site(tmp_path)
    loaded = page_builder.load_page(site, 2)
    data = loaded.to_dict()
    data["lines"] = [data["lines"][0] | {"text": "B edited", "color": "#ff0000"}, {"text": "added line"}]
    page_builder.update_page(site, page_builder.PageSpec.from_dict(data), tmp_path / "backups")
    edited = page_builder.load_page(site, 2)
    assert [ln.text for ln in edited.lines] == ["B edited", "added line"]
    assert edited.lines[0].color == "#ff0000"
    text = (site / "02_beta.html").read_text(encoding="utf-8")
    assert 'data-page="2"' in text and "<title>JR2</title>" in text
    assert len(list((tmp_path / "backups").glob("site_backup_*.zip"))) == 1


def test_update_page_rename_moves_file_and_links(tmp_path: Path) -> None:
    site = make_site(tmp_path)
    data = page_builder.load_page(site, 2).to_dict() | {"name": "Gamma"}
    page_builder.update_page(site, page_builder.PageSpec.from_dict(data))
    assert not (site / "02_beta.html").exists() and (site / "02_gamma.html").exists()
    assert page_builder.read_pages(site)[2] == {
        "id": "2", "file": "02_gamma.html", "label": "Gamma", "title": "JR2"}
    assert 'href="02_gamma.html"' in (site / "01_alpha.html").read_text(encoding="utf-8")


def test_update_placeholder_drops_marker(tmp_path: Path) -> None:
    site = make_site(tmp_path)
    data = page_builder.load_page(site, 3).to_dict() | {"lines": [{"text": "Real content"}]}
    page_builder.update_page(site, page_builder.PageSpec.from_dict(data))
    assert page_builder.PLACEHOLDER not in (site / "03_page_3.html").read_text(encoding="utf-8")


def test_update_rejects_unknown_page(tmp_path: Path) -> None:
    site = make_site(tmp_path)
    with pytest.raises(ValueError, match="between 1 and 3"):
        page_builder.update_page(site, spec(number=4))


def test_insert_rejects_out_of_range_number(tmp_path: Path) -> None:
    site = make_site(tmp_path)
    with pytest.raises(ValueError, match="between 1 and 4"):
        page_builder.insert_page(site, spec(number=9))
