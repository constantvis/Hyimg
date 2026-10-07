"""The app's fonts come from its own files (owner 2026-10-07: the pages took 3-13 s to get Geist from Google Fonts, and the app is meant
to work offline). ui/fonts.css (imported by ui/tokens.css) names Geist and Geist Mono, the files are review/ui/fonts/*.woff2. Loaded here
in Chromium and WebKit with fonts.googleapis.com and fonts.gstatic.com blocked: the board, the library, Home (a file page, as the app
opens it), the primitives' showcase; the pages ask no font of Google and Geist (and Geist Mono) is the font the page draws with. The
image studio's own check is hyimg-frames/tests/test_fonts_local.py. Another page that loads a font from the net fails the static scan."""
import re
from pathlib import Path

import pytest

from test_sliders import ENGINES, HOME, ROOT, launch, playwright, server  # noqa: F401  (server is the fixture)

BLOCKED = re.compile(r"https?://fonts\.(googleapis|gstatic)\.com/")
# whether some text is set in the family and a face of it is loaded (fonts.load asks the browser to fetch what the text needs)
PROBE = """async fam => {
  await document.fonts.load(`500 13px "${fam}"`, 'Hyimg 12 Ag'); await document.fonts.ready;
  const faces = [...document.fonts].filter(f => f.family.replace(/["']/g, '') === fam && f.status === 'loaded');
  const used = [...document.querySelectorAll('body, body *')].some(e => getComputedStyle(e).fontFamily.includes(fam));
  return { used, check: document.fonts.check(`500 13px "${fam}"`, 'Hyimg 12 Ag'), loaded: faces.length };
}"""


def watch(page):
    """every request of the page and of its frames, and the ones to the font hosts failed on the spot"""
    seen = []
    page.on("request", lambda r: seen.append(r.url))
    page.route(BLOCKED, lambda route: route.abort())
    return seen


def assert_local(page, seen, fam="Geist"):
    r = page.evaluate(PROBE, fam)
    assert r["loaded"] >= 1 and r["check"], (fam, r)
    assert r["used"], r   # some text of the page is set in it
    assert not [u for u in seen if BLOCKED.match(u)], [u for u in seen if BLOCKED.match(u)]
    assert any(u.endswith(".woff2") and ("/ui/fonts/" in u or "/fonts/" in u) for u in seen), seen   # the file came from the app itself


@pytest.mark.parametrize("engine", ENGINES)
def test_pages_take_geist_from_the_apps_own_files(server, engine, tmp_path):
    import urllib.request
    # the primitives' showcase is copied into a library's html/ folder (its own docs)
    (tmp_path / "lib/html").mkdir(); (tmp_path / "lib/html/showcase.html").write_bytes((ROOT / "review/ui/hy/showcase.html").read_bytes())
    with playwright.sync_playwright() as p:
        browser = launch(p, engine)
        for url, mono in ((f"http://127.0.0.1:{server}/canvas.html", False), (f"http://127.0.0.1:{server}/", False),
                          (HOME, False), (f"http://127.0.0.1:{server}/lib/html/showcase.html", True)):
            page = browser.new_page(viewport={"width": 1440, "height": 900}); errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            if url == HOME: page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => {} } } };")
            seen = watch(page)
            page.goto(url); page.wait_for_load_state("load"); page.wait_for_timeout(600)
            assert_local(page, seen)
            if mono: assert_local(page, seen, "Geist Mono")
            assert not errors, (url, errors)
            page.close()
        browser.close()


def test_font_files_are_served_with_their_type_and_nothing_else_under_fonts(server):
    import urllib.error, urllib.request
    with urllib.request.urlopen(f"http://127.0.0.1:{server}/ui/fonts/geist-latin.woff2") as r:
        assert r.headers["Content-Type"] == "font/woff2" and r.read(4) == b"wOF2"
    with urllib.request.urlopen(f"http://127.0.0.1:{server}/ui/fonts.css") as r:
        assert b'"Geist Mono"' in r.read()
    for bad in ("fonts/OFL-Geist.txt", "fonts/nothing.woff2", "fonts/../server.py", "fonts/geist-latin.ttf"):
        with pytest.raises(urllib.error.HTTPError) as e: urllib.request.urlopen(f"http://127.0.0.1:{server}/ui/{bad}")
        assert e.value.code == 404, bad


def test_no_repository_page_asks_the_net_for_a_font():
    """the four repositories' pages and styles: no Google Fonts link, @import or url() (the license files and notes may name them)"""
    hits = []
    for repo in ("hyimg", "hyimg-frames", "hyimg-3d-studio", "hyimg-dev-studio"):
        base = ROOT.parent / repo
        if not base.is_dir(): continue
        for f in base.rglob("*"):
            if f.suffix not in (".html", ".css") or any(x in f.parts for x in ("node_modules", ".git", "_review", "dist")): continue
            if re.search(r"fonts\.(googleapis|gstatic)\.com", f.read_text(errors="ignore")): hits.append(str(f.relative_to(base.parent)))
    assert not hits, hits
