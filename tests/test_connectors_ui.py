"""Arrows between anything on the board (owner 2026-10-09 on «Agent layouts» › 4 Structures and the «Board structure» card «Arrows
between anything»: «реализуй это»; st6 «A, then C»: arrows from any object, the notes' soft curve, labels and dashes).

- board.links draws: a heading → a picture, a note → a picture, a picture → a picture (dashed), a group → a picture (blue), a picture
  → a group; a soft curve with a head on the target's edge, a dot where it starts, its words on a pill in the middle
- hover: 3 px and the × under the pointer (notelink.js rides it along); a click takes the arrow off, «Arrow removed», ⌘Z brings it back
- a drag from the handle of one selected thing to another thing (or a group) makes an arrow, one undo step; a note keeps its own handle
- a click on the words opens the editor: words, line, colour; Enter applies, one undo step for all of it; an arrow with no words shows
  «+ Label» while an end is selected
- a moved thing takes its arrows along; a deleted one takes them off (and ⌘Z brings both back); Copy as › Mermaid
- the merge of the page keeps arrows made on both sides (ui/merge.js); a choice grid shows its numbers (ui/gridnum.js)
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
from test_note_replies import note, shot

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


def board():
    pic = lambda p, x, y: {"path": p, "x": x, "y": y, "w": 300, "ar": 1.5, "crop": None}
    return {"schema": 1, "revision": 1, "removed": {}, "items": {
        "p": pic("a/0.png", 0, 0), "q": pic("a/1.png", 700, 0), "r": pic("a/2.png", 1300, 500),
        "g1": pic("a/3.png", 60, 560), "g2": pic("a/4.png", 400, 560),
        "t": {"type": "text", "text": "Atlas · Studio", "x": 0, "y": -360, "fs": 80, "size": 3, "w": 600, "h": 92},
        "n": note(700, -380, "Brief", "yellow", w=200),
    }, "groups": {"g": {"title": "Studio series", "x": 20, "y": 500, "w": 720, "h": 320, "members": ["g1", "g2"]}},
        "grids": {"gx": {"members": ["g1", "g2"], "cols": 2, "rows": 1, "gap": 40, "cell": "fit", "num": "seq"}},
        "links": {"c1": {"from": "t", "to": "p", "label": "contains"}, "c2": {"from": "n", "to": "q", "label": "brief for"},
                  "c3": {"from": "p", "to": "q", "style": "dashed", "label": "same light"}, "c4": {"from": "g", "to": "r", "color": "blue"},
                  "c5": {"from": "q", "to": "r", "style": "dotted"}}}


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    for d in (lib / "a", state / "boards"): d.mkdir(parents=True)
    for k in range(5): (lib / f"a/{k}.png").write_bytes(png(60 + k, 40))
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HYIMG_PLUGINS=str(tmp_path / "none"), PYTHONDONTWRITEBYTECODE="1",
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


BOX = "s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2, r.width, r.height]; }"
AT = """([c, f]) => { const p = document.querySelector(`.cnx[data-c='${c}'] .ln`), q = p.getPointAtLength(p.getTotalLength() * f), m = p.getScreenCTM();
  return [q.x * m.a + m.e, q.y * m.d + m.f]; }"""
CARD = "id => { const e = EL.get(id) || GEL.get(id); const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }"
D = "c => document.querySelector(`.cnx[data-c='${c}'] .ln`).getAttribute('d')"
TOASTS = "() => [...document.querySelectorAll('#hyToasts .ht')].map(t => t.textContent).join('|')"


def seen(page, s, on):
    page.wait_for_function(f"s => {{ const e = document.querySelector(s); const o = e ? +getComputedStyle(e).opacity : 0; return {'o > .99' if on else 'o < .01'}; }}", arg=s, timeout=10000)


def open_board(p, port):
    try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url)
    page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
      localStorage.setItem('cv.cam.main', JSON.stringify({ x: -260, y: -520, z: .62 })); }""")
    page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && EL.get('p') && document.querySelector(\".cnx[data-c='c1'] .ln\")", timeout=30000)
    page.evaluate("() => render()")
    return browser, page, errors


def test_arrows_draw_hover_remove_make_edit(server):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, server)

        # drawn: a curve each, a head on the target's edge, a start dot; the words; dashed, dotted, blue
        for c in ("c1", "c2", "c3", "c4", "c5"):
            assert page.evaluate(D, c).count("C") == 1, c
            assert page.locator(f".cnx[data-c='{c}'] .hh").count() == 1 and page.locator(f".cnx[data-c='{c}'] .c0").count() == 1
        assert page.locator(".cnx[data-c='c3'] .arw.ds").count() == 1 and page.locator(".cnx[data-c='c5'] .arw.dt").count() == 1
        assert page.evaluate("() => getComputedStyle(document.querySelector(\".cnx[data-c='c4'] .ln\")).stroke") == \
            page.evaluate("() => getComputedStyle(document.querySelector(\".cnx[data-c='c4'] .hh\")).fill")
        assert "contains" in page.locator(".cnx[data-c='c1'] .clab text").text_content()
        assert not page.locator(".cnx[data-c='c4'] .clab.empty").is_visible()   # no words and no end selected: no pill
        head, card = page.evaluate(BOX, ".cnx[data-c='c1'] .hh"), page.evaluate(CARD, "p")
        assert abs(head[1] + head[3] / 2 - card[1]) < 4 and card[0] < head[0] < card[0] + card[2], (head, card)   # on p's top edge
        # the label pill keeps 12 px words on screen
        assert 9 <= page.evaluate(BOX, ".cnx[data-c='c1'] .clab text")[3] <= 17
        shot(page, "connectors-rest.png")

        # hover the line: 3 px, the × under the pointer; a click takes it off, ⌘Z brings it back
        x, y = page.evaluate(AT, ["c3", .3])
        page.mouse.move(x, y); seen(page, ".cnx[data-c='c3'] .del.m", True)
        m = page.evaluate(BOX, ".cnx[data-c='c3'] .del.m circle")
        assert ((m[0] - x) ** 2 + (m[1] - y) ** 2) ** .5 <= 3, (m, x, y)
        w = page.evaluate("() => parseFloat(getComputedStyle(document.querySelector(\".cnx[data-c='c3'] .ln\")).strokeWidth) * cam.z")
        assert abs(w - 3) < .3, w
        shot(page, "connectors-hover.png")
        page.mouse.down(); page.mouse.up()
        assert page.evaluate("() => !(board.links || {}).c3") and "Arrow removed" in page.evaluate(TOASTS)
        page.mouse.move(5, 300)
        page.keyboard.press("Meta+z")
        page.wait_for_function("() => (board.links || {}).c3 && document.querySelector(\".cnx[data-c='c3']\")")

        # a drag from the handle of the selected picture to the group: a new arrow, one undo step; a note shows only its own handle
        page.evaluate("() => { sel = new Set(['n']); render(); }")
        assert page.locator(".cn.cc").count() == 0 and page.locator(".cn[data-connect=n]").count() == 1
        page.evaluate("() => { sel = new Set(['r']); render(); }")
        h = page.evaluate(BOX, ".cn.cc")
        assert h, "no handle on the selected picture"
        gx, gy = page.evaluate("() => { const r = GEL.get('g').getBoundingClientRect(); return [r.x + r.width - 30, r.y + r.height - 20]; }")
        page.mouse.move(h[0], h[1]); page.mouse.down(); page.mouse.move((h[0] + gx) / 2, (h[1] + gy) / 2, steps=4); page.mouse.move(gx, gy, steps=4)
        assert page.evaluate("() => GEL.get('g').classList.contains('linktarget')")
        shot(page, "connectors-pull.png")
        page.mouse.up()
        made = page.evaluate("() => Object.entries(board.links).filter(([k, c]) => c.from === 'r' && c.to === 'g').map(([k]) => k)")
        assert len(made) == 1 and not page.evaluate("() => GEL.get('g').classList.contains('linktarget')")
        page.keyboard.press("Meta+z")
        page.wait_for_function("() => !Object.values(board.links).some(c => c.from === 'r' && c.to === 'g')")
        page.keyboard.press("Meta+Shift+z")
        page.wait_for_function("() => Object.values(board.links).some(c => c.from === 'r' && c.to === 'g')")
        page.keyboard.press("Meta+z")   # off again: its pill would lie over c4's, the same two ends the other way
        page.wait_for_function("() => !Object.values(board.links).some(c => c.from === 'r' && c.to === 'g')")

        # «+ Label» while an end is selected; a click opens the editor; words, dashed, blue; Enter; one ⌘Z takes all three back
        page.evaluate("() => { sel = new Set(['g']); render(); }")
        assert page.locator(".cnx[data-c='c4'] .clab.empty").is_visible()
        lab = page.evaluate(BOX, ".cnx[data-c='c4'] .clab rect")
        page.mouse.click(lab[0], lab[1])
        page.wait_for_selector(".cned .cnin")
        page.keyboard.type("uses")
        page.locator(".cned .cnst button[value=dashed]").click()
        page.wait_for_timeout(300); shot(page, "connectors-edit.png")
        assert page.evaluate("() => document.querySelector('.cned .cnst').value") == "dashed"
        page.locator(".cned .cnin").press("Enter")
        assert page.evaluate("() => board.links.c4") == {"from": "g", "to": "r", "color": "blue", "label": "uses", "style": "dashed"}
        assert not page.locator(".cned").count()
        page.mouse.click(5, 300)
        page.keyboard.press("Meta+z")
        page.wait_for_function("() => !board.links.c4.label && !board.links.c4.style && board.links.c4.color === 'blue'")

        # a moved thing takes its arrows; a deleted one takes them off, ⌘Z brings it back with them
        d0 = page.evaluate(D, "c1")
        page.evaluate("() => { const b = snap(); board.items.p.x += 200; commit(b); }")
        page.wait_for_function("d => document.querySelector(\".cnx[data-c='c1'] .ln\").getAttribute('d') !== d", arg=d0)
        page.evaluate("() => { sel = new Set(['q']); render(); }")
        page.mouse.click(5, 300)
        page.evaluate("() => { sel = new Set(['q']); removeSel(); }")
        assert page.evaluate("() => ['c2', 'c3', 'c5'].every(k => !board.links[k]) && !!board.links.c1")
        page.keyboard.press("Meta+z")
        page.wait_for_function("() => ['c2', 'c3', 'c5'].every(k => board.links[k]) && board.items.q")

        # Copy as › Mermaid: the selection's arrows as a flowchart with the board ids
        mm = page.evaluate("() => hyConn.mermaid(board, ['p', 'q', 't'])")
        assert mm.startswith("flowchart LR") and '-- "contains" -->' in mm and '-.->|"same light"|' in mm and "%% hyimg:" in mm and "brief" not in mm
        page.evaluate("() => { sel = new Set(['p']); render(); }")
        cp = page.evaluate(CARD, "p"); page.mouse.click(cp[0] + cp[2] / 2, cp[1] + cp[3] / 2, button="right")
        page.locator("#ctx [data-sub=copyas]").click()
        page.wait_for_selector("#ctx [data-act=mermaid]")
        shot(page, "connectors-copy-as.png")
        page.keyboard.press("Escape"); page.keyboard.press("Escape")

        # a choice grid's numbers on its cells
        assert page.evaluate("() => [EL.get('g1'), EL.get('g2')].map(e => e.querySelector(':scope > .mk-num').textContent)") == ["1", "2"]
        assert page.locator(".it[data-id=g1] > .mk-num").is_visible()

        # saved: the server has the arrows as the page has them
        page.wait_for_function("async () => { const b = await (await fetch('/api/board?name=main')).json(); return JSON.stringify(b.links) === JSON.stringify(board.links); }", timeout=8000)
        assert not errors, errors
        browser.close()


def test_merge_keeps_arrows_made_on_both_sides(server):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, server)
        out = page.evaluate("""() => { const base = JSON.parse(JSON.stringify(board)), mine = JSON.parse(JSON.stringify(board)), theirs = JSON.parse(JSON.stringify(board));
          mine.links.m1 = { from: 'p', to: 'r' }; theirs.links.t1 = { from: 'r', to: 'p', label: 'back' }; delete theirs.items.q;
          theirs.links.c1.label = 'holds'; const m = hyMerge.merge3(base, mine, theirs); return m.links; }""")
        assert out["m1"] == {"from": "p", "to": "r"} and out["t1"]["label"] == "back" and out["c1"]["label"] == "holds"
        assert not any(c["from"] == "q" or c["to"] == "q" for c in out.values())   # theirs deleted q: its arrows go too
        assert not errors, errors
        browser.close()
