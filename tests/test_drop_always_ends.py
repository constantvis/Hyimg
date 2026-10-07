"""Letting go always ends a drag (owner 2026-10-07: «когда отпускаю, оно не опускается»). A redraw that threw (a card's element of
another kind, before 0dc7b0e) stopped the board's pointerup before the drag was over: the card kept following the pointer with the button
up and the move was never committed. Here a redraw is made to throw while a picture is dragged and when it is let go, in Chromium and
WebKit: the drag ends, the picture stays where it was let go, the move is one undo step and saved, and the error shows as a note.
"""
import json, os, time
from pathlib import Path

import pytest

from test_canvas_pages import server, png, free_port   # noqa: F401  (the fixture)

playwright = pytest.importorskip("playwright.sync_api")
WEBKIT = any(Path(os.path.expanduser("~/Library/Caches/ms-playwright")).glob("webkit-*"))


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_a_throwing_redraw_does_not_keep_the_drag(server, tmp_path, engine):
    if engine == "webkit" and not WEBKIT: pytest.skip("no Playwright WebKit")
    with playwright.sync_playwright() as p:
        browser = p.webkit.launch() if engine == "webkit" else p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        page.evaluate("() => { cam.x = -40; cam.y = -40; cam.z = 1; renderCam(); render(); }")
        page.wait_for_timeout(300)
        # every redraw throws once the picture has moved: the moves during the drag and the one the release makes
        page.evaluate("""() => { window.__notes = []; const t0 = window.hyToast; window.hyToast = (t, k, o) => { __notes.push([t, k]); return t0 && t0(t, k, o); };
          const r0 = render; render = function () { if (window.__boom && drag && drag.moved) throw new Error('boom'); return r0.apply(this, arguments); }; }""")
        x0, n0 = page.evaluate("() => [board.items.i1.x, past.length]")
        b = page.locator('#items [data-id="i1"]').bounding_box()
        x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + 20, y + 10, steps=3)
        page.evaluate("() => { window.__boom = true; }")
        page.mouse.move(x + 100, y + 40, steps=5); page.mouse.up(); page.wait_for_timeout(100)
        page.evaluate("() => { window.__boom = false; }")
        s = page.evaluate("() => ({ drag: !!drag, x: board.items.i1.x, steps: past.length, notes: __notes })")
        assert not s["drag"], "the drag ends when the button is let go"
        assert abs(s["x"] - (x0 + 100)) < 2, s
        assert s["steps"] == n0 + 1, s
        assert any(k == "error" and "boom" in t for t, k in s["notes"]), s
        page.mouse.move(700, 600, steps=4); page.wait_for_timeout(100)
        assert page.evaluate("() => board.items.i1.x") == s["x"], "the picture stays down, it does not follow the pointer"
        page.wait_for_function("() => !dirty", timeout=10000)
        saved = lambda: json.loads((tmp_path / "state/boards/main.json").read_text())["items"]["i1"]["x"]
        for _ in range(50):
            if abs(saved() - s["x"]) < 0.01: break
            time.sleep(0.1)
        assert abs(saved() - s["x"]) < 0.01, "the move is saved"
        page.keyboard.press("Meta+z")
        page.wait_for_function("x => board.items.i1.x === x", arg=x0)
        browser.close()
