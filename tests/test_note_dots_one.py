"""One kind of note dot on every card (owner 2026-10-09 on an HTML card of the Atlas board: a big blue dot and a small yellow one
over each other in its top left corner, «что за бардак с точками? Разберись. Почему тут синяя большая, желтая маленькая, какая-то
ерунда»).

The yellow one was the end of a yellow note's arrow, drawn on the arrows' layer by its own law (a radius of 7 px, far out at most 4.5 %
of the card, its centre 8.5 % of the card inside the corner); the blue one the card's row of dots for a blue note lying on the card
(12 px, 8.5 px inside the corner). Two sizes, two places, two slot counters that both began at the corner. Now every note that links
a card has its dot in that card's row, an arrow's note too, the dots side by side instead of overlapping like avatars, and the
arrow's line goes under the card towards its note's dot.

- a picture, a Dev Studio HTML card and an HTML frame, each with a note lying on it and notes whose arrows end at it: one dot per
  note, all the same size, in one row along the top edge in the notes' order, 3.5 px apart (none over another), its own colour seen
  on a screenshot at its centre, at 25, 50, 100 and 200 %
- an arrow's line ends inside the card's top left corner, the arrows to one card in the order of their dots; hovering an arrow's dot
  shows that arrow's × under the dot, touching it and covering no other dot; a click on the × takes the arrow off and its dot leaves
  the row with it
- the handles of a selected card (corner squares, the round handle to draw an arrow) are not where the dots are
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
from test_note_dots_cards import PAGE
from test_note_replies import note

playwright = pytest.importorskip("playwright.sync_api")
Image = pytest.importorskip("PIL.Image")
ROOT = Path(__file__).resolve().parents[1]
PLUGINS = {"frames": "hyimg-image-studio", "dev": "hyimg-dev-studio"}
# each card: the notes that link it, in board order (the row's order); the arrows' notes come from outside the card
LINKED = {"p": ["Yp", "Bp"], "d": ["Yd", "Bd", "Pd"], "hf": ["Ah", "Gh"]}


def board():
    return {"schema": 1, "revision": 1, "groups": {}, "removed": {}, "items": {
        "p": {"path": "a/0.png", "x": 0, "y": 0, "w": 480, "ar": 1.6, "crop": None},
        "d": {"type": "html", "src": "html/r6/rose.html", "vw": 1440, "ar": 1.6, "pics": ["html/r6/rose.html"], "x": 640, "y": 0, "w": 480, "h": 300},
        "hf": {"type": "htmlframe", "src": "html/x/index.html", "vw": 1440, "x": 640, "y": 460, "w": 480, "h": 300},
        "Yp": note(300, 160, "lies on the picture"),
        "Bp": note(-300, 360, "an agent's note, by an arrow", "blue", to=["p"]),
        "Yd": note(940, 160, "lies on the page"),
        "Bd": note(1240, -260, "the agent's arrow", "blue", to=["d"]),
        "Pd": note(1240, 120, "another arrow", "pink", to=["d"]),
        "Ah": note(1240, 520, "an arrow to the frame", "green", to=["hf"]),
        "Gh": note(940, 620, "lies on the frame", "purple"),
    }}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in (lib / "a", lib / "html/x", lib / "html/r6", state / "boards", plugins): d.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png(64, 40))
    for rel, t in (("html/x/index.html", "Frame"), ("html/r6/rose.html", "6 Rose")):
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


# every round thing in a card's corner that stands for a note, wherever it is drawn: the card's row (.mk-note i) and any circle on the
# arrows' layer at an arrow that ends at the card (the arrow's own end dot until 2026-10-09). Each: note, centre, diameter, colour
DOTS = """id => { const out = [], rgb = c => (c.match(/[\\d.]+/g) || []).slice(0, 3).map(Number);
  const row = EL.get(id).querySelector(':scope > .mk-note'), shown = row && getComputedStyle(row).display !== 'none' && +getComputedStyle(row).opacity > .9;
  if (shown) for (const i of row.querySelectorAll('i:not(.more)')) { const r = i.getBoundingClientRect();
    out.push({ nd: i.dataset.nd, x: r.x + r.width / 2, y: r.y + r.height / 2, d: r.width, c: rgb(getComputedStyle(i).backgroundColor), at: 'row' }); }
  for (const c of document.querySelectorAll(`#links .arw[data-k$='|${id}'] circle[data-nd]`)) { if (getComputedStyle(c).visibility !== 'visible') continue;
    const r = c.getBoundingClientRect(); out.push({ nd: c.dataset.nd, x: r.x + r.width / 2, y: r.y + r.height / 2, d: r.width, c: rgb(getComputedStyle(c).fill), at: 'arrow' }); }
  const e = EL.get(id).getBoundingClientRect(); return { dots: out, card: [e.x, e.y, e.width, e.height] }; }"""
COL = "id => NCOL[board.items[id].color][0]"
# an arrow's end on screen (the last point of its line)
END = """k => { const p = document.querySelector(`#links .arw[data-k='${k}'] .ln`); if (!p) return null; const q = p.getPointAtLength(p.getTotalLength()), m = p.getScreenCTM();
  return [m.a * q.x + m.c * q.y + m.e, m.b * q.x + m.d * q.y + m.f]; }"""
BOX = "s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2, r.width]; }"


def hexrgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def pixel(page, x, y):
    im = Image.open(io.BytesIO(page.screenshot(clip={"x": x - 1, "y": y - 1, "width": 3, "height": 3}))).convert("RGB")
    return im.getpixel((im.width // 2, im.height // 2))


# the camera with a card's top left corner at (300, 200) on screen: clear of the page's chrome, the card on screen at any zoom
LOOK = "([id, z]) => { const it = board.items[id]; sel = new Set(); cam = { x: it.x - 300 / z, y: it.y - 200 / z, z }; render(); }"


def check(page, where, z=1, cards=LINKED):
    for id in cards:
        notes = LINKED[id]
        page.evaluate(LOOK, [id, z]); page.wait_for_timeout(500)
        r = page.evaluate(DOTS, id); D, (x, y, w, h) = r["dots"], r["card"]
        assert sorted(d["nd"] for d in D) == sorted(notes), (where, id, "one dot per note", D)   # none twice, none missing
        assert {d["at"] for d in D} == {"row"}, (where, id, "every dot in the card's row", D)
        size = D[0]["d"]
        assert all(abs(d["d"] - size) <= .5 for d in D), (where, id, "one size", [(d["nd"], d["d"]) for d in D])
        assert abs(size - min(12, w * .35)) <= .6, (where, id, size, w)   # 12 px on screen, at most 35 % of the card's width
        D.sort(key=lambda d: d["x"])
        assert [d["nd"] for d in D] == notes, (where, id, "in the notes' order", [d["nd"] for d in D])
        assert all(abs(d["y"] - D[0]["y"]) <= .5 for d in D), (where, id, "one row", D)
        for a, b in zip(D, D[1:]): assert abs(b["x"] - a["x"] - size - 3.5) <= .6, (where, id, "side by side, 3.5 px apart", a, b)
        assert x < D[0]["x"] - size / 2 and D[0]["x"] < x + 30 and y < D[0]["y"] < y + 30, (where, id, "in the top left corner", D[0], r["card"])
        for d in D:
            assert d["c"] == hexrgb(page.evaluate(COL, d["nd"])), (where, id, d)   # its note's colour
            px = pixel(page, d["x"], d["y"])
            assert max(abs(a - b) for a, b in zip(px, d["c"])) <= 30, (where, id, d["nd"], "covered", px, d["c"])
        # each arrow's line ends inside the card's top left corner, the arrows in the order of their dots
        ends = [(n, page.evaluate(END, f"{n}|{id}")) for n in notes if id in (page.evaluate("n => board.items[n].to", n) or [])]
        for n, e in ends: assert e and x < e[0] < x + w * .5 and y < e[1] < y + h * .5, (where, id, n, e, r["card"])
        assert [n for n, e in sorted(ends, key=lambda t: t[1][0])] == [n for n in notes if n in dict(ends)], (where, id, ends)


def test_one_kind_of_note_dot(server):
    port = server
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{port}/canvas.html"
        page.goto(url)
        page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
          localStorage.setItem('cv.cam.main', JSON.stringify({ x: -60, y: -40, z: 1 })); }""")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && PLG.html && PLG.htmlframe && ['p', 'd', 'hf'].every(i => EL.get(i))"
                               " && document.querySelector(\"#links .arw[data-k='Bd|d']\")", timeout=30000)
        assert page.evaluate("() => document.documentElement.dataset.theme") != "light"
        page.mouse.move(5, 5)
        for z in (.25, .5, 1, 2):
            check(page, f"{z * 100:.0f} %", z)
            shot(page, f"dots-{z}.png")

        # hovering an arrow's dot: that arrow's × touching the dot; a click on it takes the arrow off, its dot leaves the row
        page.evaluate(LOOK, ["d", 1]); page.wait_for_timeout(600)
        dot = page.evaluate(BOX, ".plg[data-id=d] .mk-note i[data-nd=Pd]")
        page.mouse.move(dot[0], dot[1])
        page.wait_for_function("() => +getComputedStyle(document.querySelector(\"#links .arw[data-k='Pd|d'] .del.e\")).opacity > .99", timeout=3000)
        assert page.evaluate("() => EL.get('Pd').classList.contains('ndhot')")   # the dot's note outlined, as before
        xe = page.evaluate(BOX, "#links .arw[data-k='Pd|d'] .del.e circle")
        gap = ((xe[0] - dot[0]) ** 2 + (xe[1] - dot[1]) ** 2) ** .5
        assert gap <= (dot[2] + xe[2]) / 2 + 2 and xe[1] > dot[1] + dot[2] / 2, ("the × touches its dot, under it", dot, xe)
        for o in page.evaluate(DOTS, "d")["dots"]:   # and covers none of the row's other dots
            if o["nd"] != "Pd": assert ((xe[0] - o["x"]) ** 2 + (xe[1] - o["y"]) ** 2) ** .5 >= (xe[2] + o["d"]) / 2 - .5, (o, xe)
        assert page.evaluate("() => +getComputedStyle(document.querySelector(\"#links .arw[data-k='Bd|d'] .del.e\")).opacity") < .01
        shot(page, "dot-hover.png")
        page.mouse.move(xe[0], xe[1]); page.wait_for_timeout(200)
        page.mouse.down(); page.mouse.up()
        assert page.evaluate("() => board.items.Pd.to") == []
        page.wait_for_timeout(300)
        assert [d["nd"] for d in sorted(page.evaluate(DOTS, "d")["dots"], key=lambda d: d["x"])] == ["Yd", "Bd"]
        page.keyboard.press("Meta+z")
        page.wait_for_function("() => (board.items.Pd.to || []).join() === 'd'")
        page.mouse.move(5, 5); page.wait_for_timeout(300)
        check(page, "after ⌘Z", 1, ["d"])

        # a click on an arrow's dot selects its note
        page.evaluate(LOOK, ["p", 1]); page.wait_for_timeout(500)
        dot = page.evaluate(BOX, ".it[data-id=p] .mk-note i[data-nd=Bp]")
        page.mouse.move(dot[0], dot[1]); page.mouse.down(); page.mouse.up()
        assert page.evaluate("() => [...sel]") == ["Bp"]

        # one card selected: its corner squares and its round arrow handle are away from its dots
        page.evaluate(LOOK, ["d", 1]); page.evaluate("() => { sel = new Set(['d']); render(); }"); page.wait_for_timeout(500)
        D = page.evaluate(DOTS, "d")["dots"]
        assert len(D) == 3, D
        for s in ("#stage .cn.cc", "#handles .h"):
            for hb in page.evaluate("s => [...document.querySelectorAll(s)].map(e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.right, r.bottom]; })", s):
                for d in D: assert not (hb[0] - 1 < d["x"] < hb[2] + 1 and hb[1] - 1 < d["y"] < hb[3] + 1), (s, hb, d)
        shot(page, "dots-selected.png")
        assert not errors, errors
        browser.close()
