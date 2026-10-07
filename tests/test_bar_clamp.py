# The selection bar stays inside the board's visible part (owner 2026-10-06): centred over a card near the library it went under the
# library and its buttons could not be pressed; it slides sideways instead, 8 px from the edge, at any zoom.
import pathlib, sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_shortcuts import run_server


@pytest.fixture
def server(tmp_path):
    yield from run_server(tmp_path)


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_the_selection_bar_stays_inside_the_board(server, engine):
    with sync_playwright() as p:
        b = getattr(p, engine).launch(); page = b.new_page(viewport={"width": 1200, "height": 800})
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/canvas.html?board=main")
        page.wait_for_function("() => typeof board !== 'undefined' && board.items && board.items.i0 && EL.get('i0')")
        page.evaluate("() => postMessage({ type: 'inset', left: 300, row: 12, ms: 0 }, location.origin)"); page.wait_for_timeout(100)
        for z in (1, 0.5, 2):
            # the card's middle sits 40 px right of the library's edge: the bar centred over it would start far under the library
            page.evaluate("z => { const it = board.items.i0, st = stage.getBoundingClientRect(); cam.z = z; cam.x = it.x + it.w / 2 - (300 + 40) / z; cam.y = it.y - 260 / z; renderCam(); sel.clear(); sel.add('i0'); render(); }", z)
            page.wait_for_timeout(150)
            r = page.evaluate("() => { const t = document.querySelector('#handles .tidy').getBoundingClientRect(), st = stage.getBoundingClientRect(); return [t.left - st.left, st.right - t.right]; }")
            assert r[0] >= 300 + 8 - 1 and r[1] >= 8 - 1, (z, r)
        # far from the edges the bar is where it always was: centred over the card (a wide window, the bar has room on both sides)
        page.set_viewport_size({"width": 2400, "height": 800}); page.wait_for_timeout(200)
        page.evaluate("() => { const it = board.items.i0; cam.z = 1; cam.x = it.x + it.w / 2 - 1350; renderCam(); render(); }"); page.wait_for_timeout(150)
        c = page.evaluate("() => { const t = document.querySelector('#handles .tidy').getBoundingClientRect(), e = EL.get('i0').getBoundingClientRect(); return Math.abs((t.left + t.right) / 2 - (e.left + e.right) / 2); }")
        assert c < 2, c
        assert not errors, errors
        b.close()
