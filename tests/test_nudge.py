"""The arrows nudge the selection, as in Figma (owner 2026-10-07: «чтобы когда я двигал стрелочками вверх-вниз, вправо-влево, у меня на
канвасе передвигалось выделенное минимально. Если я зажимаю Shift, двигалось быстрее, так же как в Figma»).

- a press moves the selection one screen pixel at the zoom in use: max(1, round(1 / zoom)) board units; ⇧ ten of them
- several selected keep their places among themselves; a group carries its members
- a run of presses is one undo step; the board saves it, a reload keeps it
- with nothing selected, with the focus in a field, the arrows move nothing; after a menu was opened and closed they move again
Runs in Chromium and WebKit where Playwright has them, on temporary libraries only."""
import json
import urllib.request

import pytest

from test_shortcuts import run_server

playwright = pytest.importorskip("playwright.sync_api")
ENGINES = ["chromium", "webkit"]


@pytest.fixture
def server(tmp_path):
    yield from run_server(tmp_path)


def api(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r: return json.load(r)


XY = "ids => ids.map(i => { const o = board.items[i] || board.groups[i]; return [o.x, o.y]; })"


@pytest.mark.parametrize("engine", ENGINES)
def test_arrows_nudge(server, engine):
    with playwright.sync_playwright() as p:
        try: browser = getattr(p, engine).launch()
        except Exception as error: pytest.skip(f"no {engine} for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 6 && EL.get('i0')", timeout=20000)
        errors.clear()
        cam = lambda z: page.evaluate(f"() => {{ cam.x = -100; cam.y = -100; cam.z = {z}; renderCam(); render(); }}")
        xy = lambda *ids: page.evaluate(XY, list(ids))
        page.mouse.click(1350, 860)
        # nothing selected: nothing moves
        start = xy("i0", "i1", "i2", "i3")
        page.keyboard.press("ArrowRight"); assert xy("i0", "i1", "i2", "i3") == start
        # one screen pixel at the zoom in use; ⇧ ten
        cam(0.25)
        page.evaluate("() => { sel = new Set(['i1']); render(); }")
        page.keyboard.press("ArrowRight"); assert xy("i1") == [[344, 0]]
        page.keyboard.press("Shift+ArrowDown"); assert xy("i1") == [[344, 40]]
        cam(1)
        page.keyboard.press("ArrowLeft"); page.keyboard.press("ArrowUp"); assert xy("i1") == [[343, 39]]
        cam(3)
        page.keyboard.press("ArrowLeft"); assert xy("i1") == [[342, 39]]   # zoomed in: never less than one unit
        # that was one run: one undo step takes all of it back
        page.keyboard.press("Control+z"); assert xy("i1") == [[340, 0]]
        # several keep their places among themselves, a held key repeats
        cam(1)
        page.evaluate("() => { sel = new Set(['i2', 'i3']); render(); }")
        n0 = page.evaluate("() => past.length")
        for _ in range(12): page.keyboard.press("ArrowDown", delay=10)
        assert xy("i2", "i3") == [[680, 12], [1020, 12]]
        assert page.evaluate("() => past.length") == n0 + 1
        page.keyboard.press("Control+z"); assert xy("i2", "i3") == [[680, 0], [1020, 0]]
        page.keyboard.press("Control+Shift+z"); assert xy("i2", "i3") == [[680, 12], [1020, 12]]
        # a group carries its members
        page.evaluate("() => { board.groups.G = { title: 'G', x: -50, y: -50, w: 800, h: 600, members: ['i0', 'i1'] }; sel = new Set(['G']); render(); }")
        page.keyboard.press("Shift+ArrowRight"); assert xy("G", "i0", "i1") == [[-40, -50], [10, 0], [350, 0]]
        # the focus in a field: the field's, not the board's
        page.evaluate("() => { const i = document.createElement('input'); i.id = 'probe'; i.style.cssText = 'position:fixed;left:10px;top:120px;z-index:99'; document.body.appendChild(i); i.focus(); }")
        page.keyboard.press("ArrowLeft"); assert xy("G") == [[-40, -50]]
        page.evaluate("() => document.getElementById('probe').remove()")
        # a menu opened and closed: the arrows are the board's again, Enter runs nothing
        page.evaluate("() => { sel = new Set(['i4']); cam.x = 1000; renderCam(); render(); }")
        page.wait_for_function("() => EL.get('i4').getClientRects().length > 0")   # shown once the view's cull ran
        r = page.evaluate("() => { const it = board.items.i4, s = stage.getBoundingClientRect(); return [(it.x + 60 - cam.x) * cam.z + s.left, (it.y + 60 - cam.y) * cam.z + s.top]; }")
        page.mouse.click(*r, button="right"); page.wait_for_selector("#ctx.open")
        page.keyboard.press("Escape"); page.keyboard.press("Enter")
        page.keyboard.press("ArrowRight"); assert xy("i4") == [[1361, 0]]
        # saved after the run, and a reload keeps it
        page.wait_for_function("() => !dirty && !saveT && !saveFlight", timeout=10000)
        saved = api(server, "/api/board?name=main")["items"]
        assert [saved["i4"]["x"], saved["i2"]["y"]] == [1361, 12]
        page.reload()
        page.wait_for_function("() => typeof BOARD !== 'undefined' && board.items.i4", timeout=20000)
        assert xy("i4", "i2") == [[1361, 0], [680, 12]]
        assert not errors, errors
        browser.close()
