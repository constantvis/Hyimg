"""The ♥ on HTML cards, as on pictures (owner 2026-10-08, an HTML card of the concept rounds on the «UI» page: «И почему пропали лайки
справа в углу на HTML?»). The board's ♥ was built only into a picture's element; Dev Studio's html cards and the frames plugin's HTML
frames had none, so the rounds that came as HTML pages instead of pictures came without it (review/ui/cardfav.js).

- an HTML card has the picture's mark: hidden at rest, shown under the pointer in the same top right place as a picture's of that size
- a click on it likes the page (pink, it stays without the pointer), writes feedback.fav into the page's json and never the .html, and
  does not select the card; F likes the selected HTML frame, Info's ♥ says so
- a reload shows both again: a page outside the library is read with GET /api/fav, a page of the library comes with the list
- a second click takes it off; the picture's ♥ works as before
Chromium, dark theme, a temporary library (the plugins from their repositories' last commits). HY_SHOTS=<folder> keeps screenshots."""
import io
import json
import os
import subprocess
import sys
import tarfile
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
PLUGINS = {"frames": "hyimg-image-studio", "dev": "hyimg-dev-studio"}
PAGE = "<!doctype html><html><head><title>{t}</title></head><body><h1>{t}</h1></body></html>"
PINK = "rgb(251, 113, 133)"


def board():
    return {"schema": 1, "revision": 1, "groups": {}, "removed": {}, "items": {
        "p": {"path": "a/0.png", "x": 0, "y": 0, "w": 480, "ar": 1.6, "crop": None},
        "d": {"type": "html", "src": "html/r11/raw.html", "vw": 1440, "ar": 1.6, "pics": ["html/r11/raw.html"], "x": 560, "y": 0, "w": 480, "h": 300},
        "s": {"type": "html", "src": "site/index.html", "vw": 1440, "ar": 1.6, "pics": ["site/index.html"], "x": 0, "y": 400, "w": 480, "h": 300},
        "hf": {"type": "htmlframe", "src": "html/x/index.html", "vw": 1440, "x": 560, "y": 400, "w": 480, "h": 300},
    }}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in (lib / "a", lib / "html/x", lib / "html/r11", lib / "site", state / "boards", plugins): d.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png(64, 40))
    for rel, t in (("html/x/index.html", "Frame"), ("html/r11/raw.html", "Round eleven"), ("site/index.html", "Site page")):
        (lib / rel).write_text(PAGE.format(t=t))
    have = []
    for name, repo in PLUGINS.items():   # each plugin as its repository's last commit (other agents may be changing the working copies)
        src = ROOT.parent / repo
        if not (src / "manifest.json").is_file(): continue
        raw = subprocess.run(["git", "-C", str(src), "archive", "HEAD"], capture_output=True, check=True).stdout
        (plugins / name).mkdir(); tarfile.open(fileobj=io.BytesIO(raw)).extractall(plugins / name, filter="data"); have.append(name)
    if len(have) < 2: pytest.skip("the frames and Dev plugins' repositories are not beside this one")
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HYIMG_PLUGINS=str(plugins), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, lib
    finally:
        proc.terminate(); proc.wait(5); log.close()


def shot(page, name):
    d = os.environ.get("HY_SHOTS")
    if d: Path(d).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(d) / name))


def fav_of(lib, rel):
    f = lib / (rel + ".json") if not rel.endswith(".png") else lib / (rel[:-4] + ".json")
    return bool(json.loads(f.read_text()).get("feedback", {}).get("fav")) if f.is_file() else False


def until(fn, what, t=5.0):
    end = time.time() + t
    while time.time() < end:
        if fn(): return
        time.sleep(0.05)
    raise AssertionError(what)


# the heart of a card: shown or not, its colour, and its place from the card's top right corner on screen
HEART = """id => { const el = EL.get(id), h = el && el.querySelector(':scope > .mk-fav'); if (!h) return null;
  const cs = getComputedStyle(h), r = h.getBoundingClientRect(), e = el.getBoundingClientRect();
  return { shown: cs.display !== 'none' && +cs.opacity > .9, colour: cs.color, faved: el.classList.contains('faved'),
    right: Math.round(e.right - r.right), top: Math.round(r.top - e.top), size: Math.round(r.width), x: r.x + r.width / 2, y: r.y + r.height / 2 }; }"""
MID = "id => { const r = EL.get(id).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }"


def open_board(p, port):
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url)
    page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
      localStorage.setItem('cv.cam.main', JSON.stringify({ x: -60, y: -80, z: .5 })); }""")
    return browser, page, errors, url


def wait_board(page):
    page.wait_for_function("() => typeof BOARD !== 'undefined' && PLG.html && PLG.htmlframe && ['p', 'd', 's', 'hf'].every(i => EL.get(i))", timeout=30000)
    page.wait_for_function("() => typeof byPath !== 'undefined' && byPath.get('a/0.png') && byPath.get('site/index.html')", timeout=20000)
    page.wait_for_timeout(400)


def hover(page, id):
    page.mouse.move(*page.evaluate(MID, id)); page.wait_for_timeout(450)


def test_html_cards_have_the_pictures_heart(server):
    port, lib = server
    raw = (lib / "html/r11/raw.html").read_text()
    with playwright.sync_playwright() as p:
        browser, page, errors, url = open_board(p, port)
        page.goto(url); wait_board(page)
        assert page.evaluate("() => document.documentElement.dataset.theme") != "light"

        # at rest: the mark is there and hidden, on the Dev page, the library's page and the HTML frame alike
        for i in ("d", "s", "hf"):
            h = page.evaluate(HEART, i)
            assert h and not h["shown"] and not h["faved"], (i, h)
        # under the pointer: shown in the picture's place (the same law: a 240 px card on screen, its inset and size)
        hover(page, "p"); pic = page.evaluate(HEART, "p"); assert pic["shown"], pic
        for i in ("d", "hf"):
            hover(page, i); h = page.evaluate(HEART, i)
            assert h["shown"] and (h["right"], h["top"], h["size"]) == (pic["right"], pic["top"], pic["size"]), (i, h, pic)
        shot(page, "heart-hover-html.png")

        # a click likes the page: pink, kept without the pointer, in the page's json; the .html is not written, the card not selected
        hover(page, "d"); h = page.evaluate(HEART, "d"); page.mouse.click(h["x"], h["y"])
        until(lambda: fav_of(lib, "html/r11/raw.html"), "the page's json got no ♥")
        page.mouse.move(700, 800); page.wait_for_timeout(450)
        h = page.evaluate(HEART, "d")
        assert h["shown"] and h["faved"] and h["colour"] == PINK, h
        assert page.evaluate("() => sel.size") == 0
        assert (lib / "html/r11/raw.html").read_text() == raw
        shot(page, "heart-liked-html.png")

        # F on a selected HTML frame; Info's ♥ says it is liked
        page.evaluate("() => { sel = new Set(['hf']); render(); }"); page.keyboard.press("f")
        until(lambda: fav_of(lib, "html/x/index.html"), "F gave the frame's page no ♥")
        page.wait_for_function("() => EL.get('hf').classList.contains('faved')")
        assert page.evaluate("() => { const b = $('#iFav'); return b.style.display !== 'none' && b.classList.contains('on'); }")
        # the library's page: a click on its card
        hover(page, "s"); h = page.evaluate(HEART, "s"); page.mouse.click(h["x"], h["y"])
        until(lambda: fav_of(lib, "site/index.html"), "the library page's json got no ♥")
        assert not errors, errors

        # a reload: all three liked again without the pointer (outside the library by GET /api/fav, the library page by its list)
        page.evaluate("() => { sel = new Set(); render(); }"); page.wait_for_timeout(1200)   # the board's save
        page.goto(url); wait_board(page); page.mouse.move(700, 800)
        page.wait_for_function("() => ['d', 's', 'hf'].every(i => EL.get(i).classList.contains('faved'))", timeout=10000)
        page.wait_for_timeout(450)
        for i in ("d", "s", "hf"):
            h = page.evaluate(HEART, i); assert h["shown"] and h["colour"] == PINK, (i, h)
        assert page.evaluate(HEART, "p")["shown"] is False
        shot(page, "heart-after-reload.png")

        # a second click takes it off
        h = page.evaluate(HEART, "d"); page.mouse.click(h["x"], h["y"])
        until(lambda: not fav_of(lib, "html/r11/raw.html"), "the second click left the ♥")
        page.mouse.move(700, 800); page.wait_for_timeout(450)
        assert not page.evaluate(HEART, "d")["shown"]

        # the picture as before: its ♥ by a click, pink, in its json
        hover(page, "p"); h = page.evaluate(HEART, "p"); page.mouse.click(h["x"], h["y"])
        until(lambda: fav_of(lib, "a/0.png"), "the picture's json got no ♥")
        page.mouse.move(700, 800); page.wait_for_timeout(450)
        h = page.evaluate(HEART, "p"); assert h["shown"] and h["colour"] == PINK and (h["right"], h["top"]) == (pic["right"], pic["top"]), h
        assert not errors, errors
        browser.close()
