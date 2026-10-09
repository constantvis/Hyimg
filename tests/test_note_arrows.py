"""A note's arrow (owner 2026-10-08 on Concepts/html/notes-glass/a7-states.html «Arrow states»: «вот это очень круто, и по наведению на
линию или на точку можно было бы удалить»).

- a soft curve; on a picture or a card (an HTML card too: «почему-то здесь нет точки») it ends at the note's own dot inside the thing's
  top left corner, with no head, and the thing's row of dots has no second one for that note; at a group it ends on the side, with a head
- where it ends is board geometry: the same path at 10 % and at 100 % («если мы не двигаем элементы, линия не двигается»); its sizes on
  screen follow the zoom in CSS, live while the zoom moves («чтобы когда ты зумишь, оно плавно пересчитывалось»), and far out the dot
  and the head shrink with the thing instead of covering it («стрелочки какие-то огромные»)
- hovering the line makes it thicker and shows a × under the pointer, riding along the line with it («я хочу, чтобы я мог водить мышкой,
  и у меня был этот символ удалить связь»); hovering the end dot (the note's dot: its note outlined) shows a × beside the dot instead;
  a click on a × removes the arrow (the note stays), «Arrow removed» with Undo, ⌘Z brings it back; with the × under the pointer a click
  on the line is a click on the ×
- the line runs under the thing it ends on and under every other card it crosses (owner 2026-10-08, after a sketch of options: «я бы
  сделал как сейчас, но линия проходила бы под самим объектом»): there the pointer and the screen find the card; the end dot stays on
  top and takes a click, the × still rides the line's visible part; it goes under other notes too; a card the note lies on keeps the
  line over it
Chromium, dark theme, a temporary library. HY_SHOTS=<folder> keeps screenshots."""
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
from PIL import Image

from test_canvas_pages import free_port, png
from test_note_dots_cards import PAGE
from test_note_replies import note, shot

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


def board():
    return {"schema": 1, "revision": 1, "removed": {}, "items": {
        "p": {"path": "a/0.png", "x": 0, "y": 0, "w": 300, "ar": 1.5, "crop": None},
        "q": {"path": "a/1.png", "x": 0, "y": 500, "w": 300, "ar": 1.5, "crop": None},
        "A": note(-360, 40, "Warmer tone?", to=["p"]),
        "B": note(-360, 560, "This group", "blue", to=["g"]),
        "hf": {"type": "htmlframe", "src": "html/x/index.html", "vw": 1280, "x": 700, "y": 0, "w": 400, "h": 250},
        "D": note(500, 300, "The page", "pink", to=["hf"]),
    }, "groups": {"g": {"title": "Group", "x": -40, "y": 440, "w": 380, "h": 320, "members": ["q"]}}}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in (lib / "a", lib / "html/x", state / "boards", plugins): d.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png(60, 40)); (lib / "a/1.png").write_bytes(png(60, 40))
    (lib / "html/x/index.html").write_text(PAGE.format(t="Frame"))
    src = ROOT.parent / "hyimg-frames"   # the HTML frame's plugin as its last commit (other agents may be changing the working copy)
    if (src / "manifest.json").is_file():
        raw = subprocess.run(["git", "-C", str(src), "archive", "HEAD"], capture_output=True, check=True).stdout
        (plugins / "frames").mkdir(); tarfile.open(fileobj=io.BytesIO(raw)).extractall(plugins / "frames", filter="data")
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


BOX = "s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2, r.width]; }"
WIDTH = "k => parseFloat(getComputedStyle(document.querySelector(`.arw[data-k='${k}'] .ln`)).strokeWidth) * cam.z"   # screen px
AT = """([k, f]) => { const p = document.querySelector(`.arw[data-k='${k}'] .ln`), q = p.getPointAtLength(p.getTotalLength() * f), m = p.getScreenCTM();
  return [q.x * m.a + m.e, q.y * m.d + m.f]; }"""
CARD = "id => { const r = (EL.get(id) || {}).getBoundingClientRect ? EL.get(id).getBoundingClientRect() : null; return r && [r.x, r.y, r.width, r.height]; }"
ZOOM = "z => { cam = { x: -480, y: -80, z }; render(); }"


def seen(page, s, on):   # the × shown (opacity 1) or hidden (0), after its .12 s fade
    page.wait_for_function(f"s => {{ const o = +getComputedStyle(document.querySelector(s)).opacity; return {'o > .99' if on else 'o < .01'}; }}", arg=s, timeout=3000)


def test_arrow_states_and_hover_to_delete(server):
    port = server
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        cdp = page.context.new_cdp_session(page)
        url = f"http://127.0.0.1:{port}/canvas.html"
        page.goto(url)
        page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
          localStorage.setItem('cv.cam.main', JSON.stringify({ x: -480, y: -80, z: .8 })); }""")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && EL.get('p') && EL.get('A') && document.querySelector(\".arw[data-k='A|p'] .hd\")", timeout=30000)
        page.evaluate("() => render()")
        errors.clear()

        # at the picture: the curve ends at the note's dot inside its top left corner, no head; no second dot of A in the picture's row
        a = ".arw[data-k='A|p']"
        dot, card = page.evaluate(BOX, f"{a} .hd"), page.evaluate(CARD, "p")
        assert card[0] < dot[0] < card[0] + card[2] * .15 and card[1] < dot[1] < card[1] + card[2] * .15, (dot, card)
        assert abs(dot[2] - 2 * (7 + .75)) <= 1.5, dot   # 7 px and its ring, as the card's own dots
        assert not page.locator(".it[data-id=p] .mk-note i[data-nd=A]").count()
        assert not page.locator(f"{a} .hh").count() and page.locator(".arw[data-k='B|g'] .hh").count() == 1
        assert page.evaluate("() => document.querySelector(\".arw[data-k='A|p'] .ln\").getAttribute('d')").count("C") == 1   # a curve
        assert abs(page.evaluate(WIDTH, "A|p") - 2) < .2
        # an HTML card shows the note's dot at the end too (owner: «и плюс почему-то здесь нет точки»), selected or not
        assert page.locator(".arw[data-k='D|hf'] .hd").count() == 1 and not page.locator(".arw[data-k='D|hf'] .hh").count()
        page.evaluate("() => { sel = new Set(['p']); render(); }")
        assert page.evaluate(BOX, f"{a} .hd")[:2] == dot[:2]
        page.evaluate("() => { sel = new Set(); render(); }")
        shot(page, "arrows-rest.png")

        # the same path at 10 % and at 100 %; far out the dot and the head are a small share of what they end on
        page.evaluate(ZOOM, 1); page.wait_for_timeout(100)
        d1 = page.evaluate("() => [...document.querySelectorAll('#links .arw .ln')].map(e => e.getAttribute('d')).join('|')")
        page.evaluate(ZOOM, .1); page.wait_for_timeout(100)
        assert page.evaluate("() => [...document.querySelectorAll('#links .arw .ln')].map(e => e.getAttribute('d')).join('|')") == d1
        far, pc = page.evaluate(BOX, f"{a} .hd"), page.evaluate(CARD, "p")
        assert far[2] <= pc[2] * .1 + .5, (far, pc)   # was 15 px on a 30 px picture
        hh, gr = page.evaluate(BOX, ".arw[data-k='B|g'] .hh"), page.evaluate("() => { const r = GEL.get('g').getBoundingClientRect(); return [r.width, r.height]; }")
        assert hh[2] <= min(gr) * .31 + .5, (hh, gr)
        shot(page, "arrows-far.png")
        # a zoom moving: the line keeps its 2 px on screen without the arrows' markup written again
        page.evaluate(ZOOM, .8); page.wait_for_timeout(150)
        page.evaluate("() => { window.__h = document.getElementById('links')._h; window.__w = []; window.__on = true; const f = () => { if (!window.__on) return;"
                      " if (gesture) window.__w.push(parseFloat(getComputedStyle(document.querySelector(\".arw[data-k='A|p'] .ln\")).strokeWidth) * cam.z); requestAnimationFrame(f); };"
                      " requestAnimationFrame(f); }")
        for _ in range(30):
            cdp.send("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": 700, "y": 450, "deltaX": 0, "deltaY": -3, "modifiers": 2}); time.sleep(.016)
        page.wait_for_function("() => !gesture", timeout=5000)
        w = page.evaluate("() => { window.__on = false; return window.__w; }")
        assert len(w) > 5 and all(1.8 < v < 2.2 for v in w), w   # on the steps of 5 % (canvas.html zLive)
        assert page.evaluate("() => document.getElementById('links')._h === window.__h")
        page.evaluate(ZOOM, .8); page.wait_for_timeout(150)

        # hover the line: 3 px and the × under the pointer; along the line it rides with it; the dot's × stays hidden
        x, y = page.evaluate(AT, ["A|p", .3])
        page.mouse.move(x, y); seen(page, f"{a} .del.m", True); seen(page, f"{a} .del.e", False)
        assert abs(page.evaluate(WIDTH, "A|p") - 3) < .2
        m1 = page.evaluate(BOX, f"{a} .del.m circle")
        assert ((m1[0] - x) ** 2 + (m1[1] - y) ** 2) ** .5 <= 2, (m1, x, y)
        shot(page, "arrow-hover-line.png")
        x2, y2 = page.evaluate(AT, ["A|p", .7])
        page.mouse.move(x2, y2 + 5); page.wait_for_timeout(50)   # a little off the line: the × on the line's nearest point
        m2 = page.evaluate(BOX, f"{a} .del.m circle")
        assert ((m2[0] - x2) ** 2 + (m2[1] - y2) ** 2) ** .5 <= 4 and abs(m2[0] - m1[0]) > 20, (m1, m2, x2, y2)
        page.mouse.down(); page.mouse.up()   # a click on the line: the × under the pointer takes the arrow off
        assert page.evaluate("() => board.items.A.to") == [] and page.evaluate("() => !!board.items.A")
        assert "Arrow removed" in page.evaluate("() => [...document.querySelectorAll('#hyToasts .ht')].map(t => t.textContent).join('|')")
        page.keyboard.press("Meta+z")
        page.wait_for_function("() => (board.items.A.to || []).join() === 'p' && document.querySelector(\".arw[data-k='A|p']\")")

        # hover the end dot: the × beside it, touching it, not the middle one
        page.mouse.move(10, 10); page.wait_for_timeout(150)
        dot = page.evaluate(BOX, f"{a} .hd")
        page.mouse.move(dot[0], dot[1]); seen(page, f"{a} .del.e", True); seen(page, f"{a} .del.m", False)
        assert page.evaluate("() => EL.get('A').classList.contains('ndhot')")   # the note's dot: its note outlined
        xe = page.evaluate(BOX, f"{a} .del.e circle")
        assert ((xe[0] - dot[0]) ** 2 + (xe[1] - dot[1]) ** 2) ** .5 <= (dot[2] + xe[2]) / 2 + 2, (dot, xe)
        shot(page, "arrow-hover-dot.png")
        page.mouse.move(xe[0], xe[1]); page.wait_for_timeout(200); seen(page, f"{a} .del.e", True)   # moving onto it keeps it
        page.mouse.down(); page.mouse.up()
        assert page.evaluate("() => board.items.A.to") == [] and page.evaluate("() => !!board.items.A")
        assert not page.locator(a).count()
        assert "Arrow removed" in page.evaluate("() => [...document.querySelectorAll('#hyToasts .ht')].map(t => t.textContent).join('|')")
        page.keyboard.press("Meta+z")
        page.wait_for_function("() => (board.items.A.to || []).join() === 'p' && document.querySelector(\".arw[data-k='A|p']\")")

        assert not errors, errors
        browser.close()


# the line under the cards: E, F, G and H added on the page; E from below into the picture p, F from below into the HTML card hf,
# G from the right across hf to p, H lying on the picture q to hf across the note D (under D, over q)
UNDER = """() => {
  const n = (x, y, text, color, to) => ({ type: 'note', text, x, y, w: 140, fs: 140 / 18, size: 2, h: 0, color, reach: null, to });
  Object.assign(board.items, { E: n(80, 280, 'Below', 'yellow', ['p']), F: n(760, 340, 'Under the page', 'pink', ['hf']),
    G: n(1260, 90, 'Across', 'green', ['p']), H: n(110, 640, 'On q', 'blue', ['hf']) }); render(); }"""
# a point of the arrow k's line on screen inside thing id's box (m px from its sides) or outside every card (id null), away from notes
ON = """([k, id, m]) => { const ln = document.querySelector(`.arw[data-k='${k}'] .ln`), M = ln.getScreenCTM(), L = ln.getTotalLength();
  const box = i => EL.get(i).getBoundingClientRect(), cards = Object.keys(board.items).filter(i => hyNoteLink.caught(board.items[i]) && EL.get(i)).map(box);
  const notes = Object.keys(board.items).filter(i => board.items[i].type === 'note' && i !== id).map(box);
  const ins = (r, x, y, e) => x > r.x + e && x < r.right - e && y > r.y + e && y < r.bottom - e;
  for (let i = 4; i < 197; i++) { const q = ln.getPointAtLength(L * i / 200), x = M.a * q.x + M.e, y = M.d * q.y + M.f;
    if (notes.some(r => ins(r, x, y, -m)) || !(x > 8 && x < innerWidth - 8 && y > 8 && y < innerHeight - 8)) continue;
    if (id ? ins(box(id), x, y, m) : !cards.some(r => ins(r, x, y, -m))) return [x, y]; }
  return null; }"""
HIT = """([x, y]) => { const e = document.elementFromPoint(x, y); if (!e) return null; if (e.closest('#links')) return e.classList.contains('hd') ? 'dot' : 'arrow';
  const t = e.closest('#items > [data-id]'); return t ? t.dataset.id : e.tagName; }"""
COL = "k => getComputedStyle(document.querySelector(`.arw[data-k='${k}'] .ln`)).stroke"


def pixel(page, pt):
    im = Image.open(io.BytesIO(page.screenshot(clip={"x": pt[0] - 1, "y": pt[1] - 1, "width": 3, "height": 3}))).convert("RGB")
    return im.getpixel((im.width // 2, im.height // 2))


def rgb(css):
    return tuple(int(float(v)) for v in css[css.index("(") + 1:css.index(")")].split(",")[:3])


def close(a, b, tol=40):
    return max(abs(x - y) for x, y in zip(a, b)) <= tol


def test_the_line_runs_under_the_cards(server):
    port = server
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{port}/canvas.html"
        page.goto(url)
        page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
          localStorage.setItem('cv.cam.main', JSON.stringify({ x: -480, y: -80, z: 1 })); }""")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && EL.get('p') && EL.get('hf') && document.querySelector(\".arw[data-k='A|p'] .hd\")", timeout=30000)
        page.evaluate(UNDER)
        page.wait_for_function("() => ['E|p', 'F|hf', 'G|p', 'H|hf'].every(k => document.querySelector(`.arw[data-k='${k}'] .hd`)) && EL.get('H')")
        errors.clear()
        for z, m in ((1, 12), (.1, 3)):
            page.evaluate("z => { cam = { x: z === 1 ? -200 : -2600, y: z === 1 ? -60 : -1800, z }; render(); }", z); page.wait_for_timeout(300)
            shot(page, f"arrows-under-{z}.png")
            # under the thing it ends on and under a card it only crosses: the pointer and the screen find the card, not the line
            # (far out G's part in p and H's across the note D are a few px: at 100 % only)
            for k, card in (("E|p", "p"), ("F|hf", "hf"), ("G|p", "hf")) + ((("G|p", "p"), ("H|hf", "D")) if z == 1 else ()):
                pt = page.evaluate(ON, [k, card, m]); assert pt, (z, k, card)
                assert page.evaluate(HIT, pt) == card, (z, k, card, pt)
                px, line = pixel(page, pt), rgb(page.evaluate(COL, k))
                assert not close(px, line, 30), (z, k, card, px, line)
                if card == "p": assert close(px, (255, 255, 255)), (z, k, px)   # the white picture, not the line
            # its parts outside the cards and over the card the note lies on stay on top
            for k, card in (("E|p", None), ("G|p", None), ("H|hf", None), ("H|hf", "q")):
                pt = page.evaluate(ON, [k, card, m]); assert pt, (z, k, card)
                assert page.evaluate(HIT, pt) == "arrow", (z, k, card, pt)
            # the end dot over the card it ends on
            for k in ("E|p", "F|hf", "G|p"):
                dot = page.evaluate(BOX, f".arw[data-k='{k}'] .hd")
                assert page.evaluate(HIT, dot[:2]) == "dot", (z, k, dot)
        page.evaluate("() => { cam = { x: -200, y: -60, z: 1 }; render(); }"); page.wait_for_timeout(200)
        # at 100 %: the dot's colour on the picture and a click on it selects its note
        dot = page.evaluate(BOX, ".arw[data-k='E|p'] .hd")
        assert close(pixel(page, dot[:2]), rgb(page.evaluate(COL, "E|p"))), pixel(page, dot[:2])
        page.mouse.move(dot[0], dot[1]); page.mouse.down(); page.mouse.up()
        assert page.evaluate("() => [...sel]") == ["E"]
        page.evaluate("() => { sel = new Set(); render(); }")
        # hovering the visible part: the × under the pointer; moving on to the part under the picture: the picture's, the × goes
        page.mouse.move(5, 5); page.wait_for_timeout(150)
        vis, hid = page.evaluate(ON, ["E|p", None, 12]), page.evaluate(ON, ["E|p", "p", 12])
        page.mouse.move(*vis); seen(page, ".arw[data-k='E|p'] .del.m", True)
        xm = page.evaluate(BOX, ".arw[data-k='E|p'] .del.m circle")
        assert ((xm[0] - vis[0]) ** 2 + (xm[1] - vis[1]) ** 2) ** .5 <= 3, (xm, vis)
        shot(page, "arrows-under-hover.png")
        page.mouse.move(*hid); seen(page, ".arw[data-k='E|p'] .del.m", False)
        page.mouse.move(*vis); seen(page, ".arw[data-k='E|p'] .del.m", True)
        page.mouse.down(); page.mouse.up()   # the × on the visible part still takes the arrow off
        assert page.evaluate("() => board.items.E.to") == []
        assert not errors, errors
        browser.close()
