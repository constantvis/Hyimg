"""A note's dot on every kind of card, and none on the card a Studio edits (owner 2026-10-08, the «UI» page at 75 %: a yellow note lay
on the HTML card «11 Hints», the card showed no dot: «И почему у HTML точки не появляется сверху? Естественно, она должна пропадать,
когда мы нажимаем и входим в режим студии, и линия должна тоже пропадать ... А так точка нужна слева»).

- a note on a picture, a Dev Studio HTML card, an HTML frame and a 3D card (lying on it, or its zone) shows its dot in the card's top
  left corner, on screen, at 50, 75 and 100 %, selected or not. The Dev card big enough on screen runs its live page, and that page's
  iframe had the class of Dev Studio's panels (.dvp, z-index 60): it lay over the card's marks, the dot among them
- one dot per note: an arrow from another note ends at that note's own dot, in the card's row beside the first (2026-10-09)
- in a Studio (Dev Studio on the HTML card, Image Studio on the picture) the card's dots and the arrows that end at it are hidden, the
  other cards' arrows stay; they come back on leaving
- in a Studio the card lies over everything of the board on it (owner 2026-10-08: «Заметка поверх карточки в Studio — да, конечно,
  заметка должна ложиться под карточки, когда мы открываем студию»): a note, a heading, another note's arrow across it and a comment pin
  of the board under the card, seen on a screenshot and by the pointer; the card's own comment pin stays over it. All of it comes back
  after Esc, and the note is typed into again
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
from test_note_replies import note

playwright = pytest.importorskip("playwright.sync_api")
Image = pytest.importorskip("PIL.Image")
ROOT = Path(__file__).resolve().parents[1]
PLUGINS = {"frames": "hyimg-image-studio", "dev": "hyimg-dev-studio", "3d": "hyimg-3d-studio"}
PAGE = "<!doctype html><html><head><title>{t}</title></head><body style='margin:0;background:#fff'><h1>{t}</h1></body></html>"
CARDS = ("p", "d", "hf", "m")


def board():
    return {"schema": 1, "revision": 1, "groups": {}, "removed": {}, "items": {
        "p": {"path": "a/0.png", "x": 0, "y": 0, "w": 480, "ar": 1.6, "crop": None},
        "d": {"type": "html", "src": "html/r11/hints.html", "vw": 1440, "ar": 1.6, "pics": ["html/r11/hints.html"], "x": 560, "y": 0, "w": 480, "h": 300},
        "hf": {"type": "htmlframe", "src": "html/x/index.html", "vw": 1440, "x": 560, "y": 400, "w": 480, "h": 300},
        "m": {"type": "model3d", "empty": True, "x": 0, "y": 400, "w": 480, "h": 300},
        "Np": note(300, 120, "on the picture"),
        "Nd": note(860, 120, "on the page"),
        "Zh": note(1100, 500, "the frame, by a zone", "pink", reach={"l": 560, "t": 0, "r": 0, "b": 0}),
        "Nm": note(300, 520, "on the scene", "green"),
    }}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in (lib / "a", lib / "html/x", lib / "html/r11", state / "boards", plugins): d.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png(64, 40))
    for rel, t in (("html/x/index.html", "Frame"), ("html/r11/hints.html", "11 Hints")):
        (lib / rel).write_text(PAGE.format(t=t))
    for name, repo in PLUGINS.items():   # each plugin as its repository's last commit (other agents may be changing the working copies)
        src = ROOT.parent / repo
        if not (src / "manifest.json").is_file(): pytest.skip(f"the plugin {repo} is not beside this repository")
        raw = subprocess.run(["git", "-C", str(src), "archive", "HEAD"], capture_output=True, check=True).stdout
        (plugins / name).mkdir(); tarfile.open(fileobj=io.BytesIO(raw)).extractall(plugins / name, filter="data")
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
        yield port
    finally:
        proc.terminate(); proc.wait(5); log.close()


def shot(page, name):
    d = os.environ.get("HY_SHOTS")
    if d: Path(d).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(d) / name))


# the card's row of note dots: each dot's note, centre on screen and colour, and whether the row is shown
DOTS = """id => { const s = EL.get(id).querySelector(':scope > .mk-note'); if (!s) return null; const cs = getComputedStyle(s), e = EL.get(id).getBoundingClientRect();
  return { shown: cs.display !== 'none' && cs.visibility === 'visible' && +cs.opacity > .9, card: [e.x, e.y, e.width, e.height],
    dots: [...s.querySelectorAll('i')].map(i => { const r = i.getBoundingClientRect(); return { nd: i.dataset.nd, x: r.x + r.width / 2, y: r.y + r.height / 2,
      w: r.width, c: getComputedStyle(i).backgroundColor.match(/\\d+/g).slice(0, 3).map(Number) }; }) }; }"""
ARROW = "k => { const a = document.querySelector(`#links .arw[data-k='${k}']`); return a ? getComputedStyle(a).visibility : null; }"


def seen_on_screen(page, d):   # the dot's own colour in the middle of it on a screenshot: nothing of the card lies over it
    im = Image.open(io.BytesIO(page.screenshot(clip={"x": d["x"] - 1.5, "y": d["y"] - 1.5, "width": 3, "height": 3}))).convert("RGB")
    px = im.getpixel((im.width // 2, im.height // 2))
    return max(abs(a - b) for a, b in zip(px, d["c"])) <= 24, px


def check_dots(page, where, look=CARDS, n=None):   # look: the cards whose dots must be seen on the screenshot too; n: card -> its notes
    for id in CARDS:
        r = page.evaluate(DOTS, id)
        assert r and r["shown"] and len(r["dots"]) == (n or {}).get(id, 1), (where, id, r)   # one dot per note, never two
        for d in r["dots"]:
            x, y, w, _ = r["card"]
            assert x < d["x"] < x + w * .12 and y < d["y"] < y + w * .12, (where, id, d, r["card"])   # in the top left corner
            if id not in look: continue
            ok, px = seen_on_screen(page, d)
            assert ok, (where, id, "the dot is covered", px, d)


def enter(page, id, mode, at=(.3, .6)):
    x, y, w, h = page.evaluate(DOTS, id)["card"]
    page.mouse.dblclick(x + w * at[0], y + h * at[1])
    page.wait_for_function("m => document.documentElement.dataset.hyEdit === m", arg=mode, timeout=15000); page.wait_for_timeout(600)


def leave(page):
    for _ in range(3):
        if not page.evaluate("() => !!document.documentElement.dataset.hyEdit"): break
        page.keyboard.press("Escape"); page.wait_for_timeout(700)
    page.wait_for_function("() => !document.documentElement.dataset.hyEdit", timeout=5000)


def open_board(p, port):   # the board at 75 %, Chromium, the dark theme
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url)
    page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
      localStorage.setItem('cv.cam.main', JSON.stringify({ x: -40, y: -140, z: .75 })); }""")
    page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && PLG.html && PLG.htmlframe && PLG.model3d && ['p', 'd', 'hf', 'm'].every(i => EL.get(i))",
                           timeout=30000)
    assert page.evaluate("() => document.documentElement.dataset.theme") != "light"
    return browser, page, errors


def test_note_dots_on_every_card_and_not_in_a_studio(server):
    port = server
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, port)

        # 75 %, the owner's zoom: the HTML card is 360 px on screen and runs its live page; every card shows its note's dot
        page.wait_for_function("() => EL.get('d').classList.contains('pv')", timeout=20000); page.wait_for_timeout(600)
        check_dots(page, "75 %")
        shot(page, "dots-75.png")
        page.evaluate("() => { sel = new Set(['d']); render(); }"); page.wait_for_timeout(500)
        check_dots(page, "75 %, the HTML card selected")
        shot(page, "dots-75-selected.png")
        for z in (.5, 1):
            page.evaluate("z => { sel = new Set(); cam = { x: -40, y: -140, z }; render(); }", z); page.wait_for_timeout(1500)
            check_dots(page, f"{z * 100:.0f} %")
        page.evaluate("() => { cam = { x: -40, y: -140, z: .75 }; render(); }")
        page.wait_for_function("() => EL.get('d').classList.contains('pv')", timeout=20000); page.wait_for_timeout(600)

        # arrows to the HTML card and to the picture: each ends at its note's own dot, one more in the card's row (2026-10-09: the arrow
        # drew a dot of its own on the arrows' layer, of another size, over the row's first one)
        page.evaluate("""() => { board.items.Ad = { type: 'note', text: 'arrow to the page', x: 1100, y: 40, w: 140, fs: 140 / 18, size: 2, h: 0, color: 'blue', reach: null, to: ['d'] };
          board.items.Ap = { type: 'note', text: 'arrow to the picture', x: -300, y: 40, w: 140, fs: 140 / 18, size: 2, h: 0, color: 'blue', reach: null, to: ['p'] };
          render(); }""")
        page.wait_for_function("() => document.querySelector(\"#links .arw[data-k='Ad|d'].ad\") && document.querySelector(\"#links .arw[data-k='Ap|p'].ad\")")
        page.wait_for_timeout(400)
        check_dots(page, "with arrows", n={"p": 2, "d": 2})
        assert [i["nd"] for i in page.evaluate(DOTS, "d")["dots"]] == ["Nd", "Ad"] and not page.locator("#links circle[data-nd]").count()
        assert page.evaluate(ARROW, "Ad|d") == "visible" and page.evaluate(ARROW, "Ap|p") == "visible"

        # Dev Studio on the HTML card: its dot and the arrow to it gone, the picture's arrow stays; back on leaving
        enter(page, "d", "dev")
        r = page.evaluate(DOTS, "d")
        assert not r["shown"] and page.evaluate(ARROW, "Ad|d") == "hidden", r
        assert page.evaluate(ARROW, "Ap|p") == "visible"
        shot(page, "dots-dev-studio.png")
        leave(page)
        assert page.evaluate(ARROW, "Ad|d") == "visible" and page.evaluate(DOTS, "d")["shown"]

        # Image Studio on the picture: the same
        page.evaluate("() => { sel = new Set(); cam = { x: -40, y: -140, z: .75 }; render(); }"); page.wait_for_timeout(500)
        enter(page, "p", "image")
        r = page.evaluate(DOTS, "p")
        assert not r["shown"] and page.evaluate(ARROW, "Ap|p") == "hidden", r
        assert page.evaluate(ARROW, "Ad|d") == "visible"
        shot(page, "dots-image-studio.png")
        leave(page)
        assert page.evaluate(ARROW, "Ap|p") == "visible" and page.evaluate(DOTS, "p")["shown"]

        # without the arrows every card has its one dot again, the HTML card's live page too
        page.evaluate("() => { sel = new Set(); delete board.items.Ad; delete board.items.Ap; cam = { x: -40, y: -140, z: .75 }; render(); }")
        page.wait_for_function("() => EL.get('d').classList.contains('pv')", timeout=20000); page.wait_for_timeout(800)
        check_dots(page, "after the studios")
        shot(page, "dots-after.png")
        assert not errors, errors
        browser.close()


# what the pointer finds at a point: the board thing (a card, a note, a heading: its id), an arrow, a comment pin
HIT = """([x, y]) => { const e = document.elementFromPoint(x, y); if (!e) return null;
  if (e.closest('#links')) return 'arrow'; if (e.closest('#cmpins')) return 'pin';
  const t = e.closest('#items > [data-id]'); return t ? t.dataset.id : (e.closest('.ifed') ? 'image studio' : e.tagName); }"""
MID = "id => { const r = EL.get(id).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }"
# a point of the arrow Ax|p on the card d, away from the card's edges and from the note on it
ON_D = """() => { const ln = document.querySelector("#links .arw[data-k='Ax|p'] .ln"), d = EL.get('d').getBoundingClientRect(), n = EL.get('Nd').getBoundingClientRect();
  const m = ln.getScreenCTM(), L = ln.getTotalLength();
  for (let i = 1; i < 200; i++) { const q = ln.getPointAtLength(L * i / 200), x = m.a * q.x + m.c * q.y + m.e, y = m.b * q.x + m.d * q.y + m.f;
    if (x > d.x + 40 && x < d.right - 40 && y > d.y + 30 && y < d.bottom - 30 && !(x > n.x - 20 && x < n.right + 20 && y > n.y - 20 && y < n.bottom + 20)) return [x, y]; }
  return null; }"""
PINS = """() => Object.fromEntries([...document.querySelectorAll('#cmpins .cmpin')].map(b => [hyComments.threads().find(t => t.id === b.dataset.c).messages[0].text,
  getComputedStyle(b).visibility]))"""


def pixel(page, pt):
    im = Image.open(io.BytesIO(page.screenshot(clip={"x": pt[0] - 1, "y": pt[1] - 1, "width": 3, "height": 3}))).convert("RGB")
    return im.getpixel((im.width // 2, im.height // 2))


def near(a, b, tol=24):
    return max(abs(x - y) for x, y in zip(a, b)) <= tol


def test_a_studio_lays_its_card_over_the_board(server):
    port = server
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, port)
        page.wait_for_function("() => EL.get('d').classList.contains('pv')", timeout=20000)
        # on the HTML card: the note Nd (the board's), a heading, an arrow from a note beside it to the picture, a comment of the board
        # itself and one of the card
        page.evaluate("""async () => {
          board.items.Hd = { type: 'text', text: 'A heading', x: 600, y: 200, w: 200, fs: 40, size: 2 };
          board.items.Ax = { type: 'note', text: 'arrow across', x: 1100, y: 200, w: 140, fs: 140 / 18, size: 2, h: 0, color: 'blue', reach: null, to: ['p'] };
          render();
          const api = b => hyAnnot.api('/api/comments', { name: BOARD, op: 'new', ...b });
          await api({ anchor: null, at: [700, 70], text: 'board pin' });
          await api({ anchor: hyAnnot.anchorAt({ x: 900, y: 40 }).anchor, at: [.7, .13], text: 'card pin' });
          await hyComments.load(); }""")
        page.wait_for_function("() => document.querySelector(\"#links .arw[data-k='Ax|p'] .ln\") && document.querySelectorAll('#cmpins .cmpin').length === 2")
        page.wait_for_timeout(600)
        nd, np_, hd, ax = page.evaluate(MID, "Nd"), page.evaluate(MID, "Np"), page.evaluate(MID, "Hd"), page.evaluate(ON_D)
        assert ax, "the arrow does not cross the HTML card"
        note_px, head_px = pixel(page, nd), pixel(page, hd)
        assert not near(note_px, (255, 255, 255)), note_px   # the note lies over the white page on the board
        assert [page.evaluate(HIT, q) for q in (nd, hd, ax)] == ["Nd", "Hd", "d"]   # an arrow's line goes under the cards it crosses
        assert page.evaluate(PINS) == {"board pin": "visible", "card pin": "visible"}
        assert page.evaluate("() => hyComments.threads().find(t => t.messages[0].text === 'card pin').anchor.obj") == "d"

        # Dev Studio on the HTML card: the page over the note, the heading, the arrow and the board's pin; the card's own pin over the page
        enter(page, "d", "dev", at=(.15, .85))
        page.wait_for_timeout(400)
        nd, hd, ax = page.evaluate(MID, "Nd"), page.evaluate(MID, "Hd"), page.evaluate(ON_D)
        shot(page, "studio-dev-over.png")
        assert [page.evaluate(HIT, q) for q in (nd, hd, ax)] == ["d", "d", "d"]
        for q in (nd, hd, ax):
            assert near(pixel(page, q), (255, 255, 255)), ("the page is not on top", q, pixel(page, q))
        assert page.evaluate(PINS) == {"board pin": "hidden", "card pin": "visible"}
        leave(page)
        page.wait_for_timeout(400)
        nd, hd, ax = page.evaluate(MID, "Nd"), page.evaluate(MID, "Hd"), page.evaluate(ON_D)
        assert [page.evaluate(HIT, q) for q in (nd, hd, ax)] == ["Nd", "Hd", "d"]
        assert near(pixel(page, nd), note_px), pixel(page, nd)
        assert page.evaluate(PINS) == {"board pin": "visible", "card pin": "visible"}
        assert page.evaluate("""() => [getComputedStyle(document.getElementById('links')).clipPath, getComputedStyle(EL.get('d')).zIndex,
          document.getElementById('gsticky').style.clipPath]""") == ["none", str(page.evaluate("() => EL.get('d')._n + 1")), ""]

        # Image Studio on the picture: the picture over its note, where the note lay too; the note back after Esc
        page.evaluate("() => { sel = new Set(); cam = { x: -40, y: -140, z: .75 }; render(); }"); page.wait_for_timeout(500)
        np_ = page.evaluate(MID, "Np"); np_px = pixel(page, np_)
        assert page.evaluate(HIT, np_) == "Np" and not near(np_px, (255, 255, 255)), np_px
        enter(page, "p", "image", at=(.15, .85))
        page.wait_for_timeout(600)
        np_ = page.evaluate(MID, "Np")
        x, y, w, h = page.evaluate("() => { const r = EL.get('p').getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }")
        shot(page, "studio-image-over.png")
        pic = pixel(page, (x + w * .1, y + h * .1))
        assert near(pixel(page, np_), pic) and not near(pic, np_px), ("the note is over the picture", pixel(page, np_), pic, np_px)
        assert page.evaluate(HIT, np_) != "Np"
        leave(page)
        page.wait_for_timeout(400)
        np_ = page.evaluate(MID, "Np")
        assert page.evaluate(HIT, np_) == "Np" and near(pixel(page, np_), np_px)

        # the note is typed into as before
        page.evaluate("() => { sel = new Set(); render(); }")
        page.mouse.dblclick(*np_)
        page.wait_for_selector(".note.editing textarea", timeout=5000)
        page.keyboard.press("End"); page.keyboard.type(" and more")
        page.keyboard.press("Escape"); page.wait_for_timeout(300)
        assert page.evaluate("() => board.items.Np.text") == "on the picture and more"
        shot(page, "studio-after.png")
        assert not errors, errors
        browser.close()
