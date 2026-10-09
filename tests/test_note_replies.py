"""A reply arrow from a note to another note, and a dot for every note on a thing (owner 2026-10-08: «Почему я не могу привязывать
стрелочку от моей заметки к другой заметке, как ответ на заметку?»; a video under two notes showed one blue dot).

- an arrow drawn with the mouse from note R's dot to note A: A is the target while it is drawn (.linktarget), letting go makes R a reply;
  R's Info says «Reply to: “…”», A's lists «Replies · 1», A selected outlines its thread; hy.py find prints the thread, the note files
  carry reply_to and replies
- the arrow back from A to R would close a circle: refused with a toast, nothing changes
- a picture under two notes has two dots in those notes' colours (the reply adds none), an HTML frame under three a row of three,
  each the same size on screen at two zooms; hovering a dot outlines its note, a click on it selects that note
Chromium, dark theme, a temporary library. HY_SHOTS=<folder> keeps screenshots."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


def note(x, y, text, color="yellow", w=140, **kw):
    return {"type": "note", "text": text, "x": x, "y": y, "w": w, "fs": w / 18, "size": 2, "h": 0, "color": color, "reach": None, "to": [], **kw}


Z = {"l": 400, "t": 0, "r": 400, "b": 400}


def board():
    return {"schema": 1, "revision": 1, "groups": {}, "removed": {}, "items": {
        "p": {"path": "a/0.png", "x": 0, "y": 0, "w": 300, "ar": 1.5, "crop": None},
        "hf": {"type": "htmlframe", "src": "html/x/index.html", "vw": 1280, "x": 700, "y": 0, "w": 400, "h": 250},
        # on the things by their zones (an arrow straight to a thing ends at its own dot instead, tests/test_note_arrows.py)
        "A": note(-260, -230, "# Warmer tone?\nthe first row", "blue", reach={"l": 0, "t": 0, "r": 500, "b": 400}),
        "B": note(-200, 120, "Not our style at all", reach={"l": 0, "t": 100, "r": 500, "b": 300}),
        "R": note(-250, 420, "Yes, by 10 percent", "green"),
        "H1": note(560, -200, "One", "pink", reach=Z), "H2": note(760, -200, "Two", "purple", reach=Z), "H3": note(960, -200, "Three", reach=Z),
    }}


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    for d in (lib / "a", lib / "html/x", state / "boards"): d.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png(60, 40)); (lib / "html/x/index.html").write_text("<!doctype html><h1>A page</h1>")
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, lib, state, env
    finally:
        proc.terminate(); proc.wait(5); log.close()


def api(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r: return json.load(r)


def shot(page, name):
    d = os.environ.get("HY_SHOTS")
    if d: Path(d).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(d) / name))


CENTRE = "s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }"
DOTS = """id => [...EL.get(id).querySelectorAll(':scope > .mk-note i')].map(i => { const r = i.getBoundingClientRect();
  return [i.dataset.nd, getComputedStyle(i).backgroundColor, Math.round(r.width), Math.round(r.left), getComputedStyle(i).display]; })"""


def drag(page, a, b):
    x0, y0 = page.evaluate(CENTRE, a); x1, y1 = page.evaluate(CENTRE, b)
    page.mouse.move(x0, y0); page.mouse.down()
    for k in range(1, 11): page.mouse.move(x0 + (x1 - x0) * k / 10, y0 + (y1 - y0) * k / 10)


def test_a_reply_arrow_and_a_dot_per_note(server):
    port, lib, state, env = server
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{port}/canvas.html"
        page.goto(url)
        page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
          localStorage.setItem('cv.cam.main', JSON.stringify({ x: -500, y: -320, z: .8 })); }""")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && PLG.htmlframe && EL.get('hf') && EL.get('R') && EL.get('p')", timeout=30000)
        errors.clear()
        page.wait_for_timeout(500)   # the marks grow in (.32 s)

        # a dot per note: the picture under A (blue) and B (yellow), the HTML frame under three notes
        page.wait_for_function("() => EL.get('p').querySelector('.mk-note i').getBoundingClientRect().width > 11", timeout=5000)   # grown in
        d = page.evaluate(DOTS, "p")
        assert [x[0] for x in d] == ["A", "B"] and d[0][1] == "rgb(125, 187, 245)" and d[1][1] == "rgb(244, 196, 48)"
        assert d[0][2] == d[1][2] and abs((d[1][3] - d[0][3]) - d[0][2] - 3.5) <= 1.5   # side by side, 3.5 px apart (2026-10-09)
        h = page.evaluate(DOTS, "hf")
        assert [x[0] for x in h] == ["H1", "H2", "H3"] and page.evaluate("() => EL.get('hf').classList.contains('noted')")
        assert h[0][1] == "rgb(240, 140, 196)" and h[1][1] == "rgb(183, 156, 242)"
        size = d[0][2]
        page.evaluate("() => { cam.z = 1.6; render(); }"); page.wait_for_timeout(400)
        assert page.evaluate(DOTS, "p")[0][2] == size   # the same size on screen at another zoom
        page.evaluate("() => { cam.z = .8; render(); }"); page.wait_for_timeout(400)
        shot(page, "dots-two-notes-and-a-stack.png")
        if os.environ.get("HY_SHOTS"):   # the two stacks up close
            for k, s in (("p", ".it[data-id=p]"), ("hf", ".plg[data-id=hf]")):
                r = page.evaluate("s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.x, r.y]; }", s)
                page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / f"dots-{k}-close.png"), clip={"x": r[0] - 10, "y": r[1] - 10, "width": 120, "height": 60})
        # hover a dot: its note is outlined; a click selects that note
        x, y = page.evaluate(CENTRE, ".plg[data-id=hf] .mk-note i[data-nd=H2]")
        page.mouse.move(x, y)
        page.wait_for_function("() => EL.get('H2').classList.contains('ndhot')", timeout=3000)   # the pointer's events come with a frame
        assert page.evaluate("() => EL.get('H2').classList.contains('ndhot') && !EL.get('H1').classList.contains('ndhot')")
        shot(page, "dot-hover-outlines-its-note.png")
        page.mouse.down(); page.mouse.up()
        assert page.evaluate("() => [...sel]") == ["H2"]

        # the arrow from R to A: A is the target while drawn, R answers A when let go
        page.evaluate("() => { sel = new Set(['R']); render(); }")
        drag(page, ".cn[data-connect=R]", ".note[data-id=A]")
        assert page.evaluate("() => [...document.querySelectorAll('.linktarget')].map(e => e.dataset.id)") == ["A"]
        shot(page, "reply-arrow-drawing.png")
        page.mouse.up()
        assert page.evaluate("() => board.items.R.to") == ["A"]
        page.evaluate("() => { sel = new Set(['R']); render(); }")
        assert page.evaluate("() => [...document.querySelectorAll('#iNotes .inote .t')].map(e => e.textContent)") == ["Reply to: “Warmer tone?”"]
        assert page.evaluate("() => $('#iM').textContent").startswith("linked: 1 frame")   # what A is about, R is about too
        assert [x[0] for x in page.evaluate(DOTS, "p")] == ["A", "B"]   # but the reply adds no dot to A's picture
        shot(page, "reply-info.png")
        page.evaluate("() => { sel = new Set(['A']); render(); }")
        assert page.evaluate("() => [...document.querySelectorAll('#iNotes .sh')].map(e => e.textContent)") == ["Replies · 1"]
        assert page.evaluate("() => document.querySelectorAll('#links rect.lkc').length") >= 1   # the thread outlined
        shot(page, "replied-note-info-and-thread.png")

        # the arrow back from A to R would be a circle: refused with its reason
        page.evaluate("() => { sel = new Set(['A']); render(); }")
        drag(page, ".cn[data-connect=A]", ".note[data-id=R]")
        page.mouse.up()
        assert page.evaluate("() => board.items.A.to") == []
        page.wait_for_function("() => ($('#hyToasts') || document.body).innerText.includes(\"Can't reply in a circle\")", timeout=5000)
        page.wait_for_timeout(700)   # the toast rises to the front of the stack
        shot(page, "circle-refused.png")

        # saved: the files and hy.py tell the thread
        for _ in range(60):
            if api(port, "/api/board?name=main")["items"]["R"]["to"] == ["A"]: break
            time.sleep(0.25)
        for _ in range(40):
            if (lib / "notes/main__R.json").exists(): break
            time.sleep(0.25)
        assert json.loads((lib / "notes/main__R.json").read_text())["reply_to"] == "main/A"
        assert json.loads((lib / "notes/main__A.json").read_text())["replies"] == ["main/R"]
        hy = lambda *a: subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "--page", "main", *a], env={**env, "HYIMG_PORT": str(port)},
                                       capture_output=True, text=True, timeout=60).stdout
        out = hy("find", "Warmer")
        assert "↳ «Yes, by 10 percent»" in out and "[R]" in out, out
        assert "↑ ответ на «Warmer tone?»" in hy("find", "Yes, by")
        assert "заметка «Yes, by 10 percent» (ответ на заметку о нем) [R]" in hy("find", "a/0.png")
        assert errors == []
        browser.close()


def test_n_on_a_selected_note_makes_a_reply_beside_it(server):
    """owner 2026-10-08: N with one note selected made an area over the whole group; now the new note answers it, beside it"""
    port, lib, state, env = server
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{port}/canvas.html"
        page.goto(url)
        page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
          localStorage.setItem('cv.cam.main', JSON.stringify({ x: -500, y: -320, z: .8 })); }""")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && EL.get('B') && EL.get('p')", timeout=30000)
        errors.clear()
        made = "before => Object.keys(board.items).filter(k => !before.includes(k))"
        # one note selected, N: a reply to it, to its right, no area, covering nothing
        before = page.evaluate("() => { sel = new Set(['B']); render(); return Object.keys(board.items); }")
        x, y = page.evaluate(CENTRE, "#stage"); page.mouse.move(x, y + 300)
        page.keyboard.press("n")
        [nid] = page.evaluate(made, before)
        n = page.evaluate("id => board.items[id]", nid)
        assert n["to"] == ["B"] and not n["reach"] and n["x"] > -200 + 140 and n["y"] == 120
        assert page.evaluate("id => Object.keys(board.items).filter(k => k !== id && board.items[k].type !== 'text').every(k => { const a = rectOf(id), b = rectOf(k);"
                             " return !(a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y); })", nid)
        page.keyboard.type("Agreed"); page.keyboard.press("Escape")
        page.evaluate("id => { sel = new Set([id]); render(); }", nid)
        assert page.evaluate("() => [...document.querySelectorAll('#iNotes .inote .t')].map(e => e.textContent)") == ["Reply to: “Not our style at all”"]
        shot(page, "n-on-a-note-makes-a-reply.png")
        # a picture selected, N: as before, the note above it with an arrow to it
        before = page.evaluate("() => { sel = new Set(['p']); render(); return Object.keys(board.items); }")
        page.keyboard.press("n")
        [pid] = page.evaluate(made, before)
        assert page.evaluate("id => [board.items[id].to, board.items[id].reach]", pid) == [["p"], None]
        page.keyboard.press("Escape")
        # a picture and a note: linked to the picture as before and an answer to the note
        before = page.evaluate("() => { sel = new Set(['p', 'A']); render(); return Object.keys(board.items); }")
        page.evaluate("() => newNote(false)")   # the dock's button
        [mid] = page.evaluate(made, before)
        m = page.evaluate("id => board.items[id]", mid)
        assert m["to"] == ["p", "A"] and not m["reach"]   # the picture as when it is alone (an arrow), and the reply
        assert errors == []
        browser.close()
