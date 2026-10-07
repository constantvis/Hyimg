# The bar over a selection stays put on it (owner 2026-10-07, a video: «настройки сверху не должны ездить, это как-то очень странно»):
# with the card wholly in view the bar is centred on it at any zoom and pan, the info panel at the top right narrowing the board only at
# its own height, and while the board pans the bar keeps the same offset to the card on every frame (no easing, no slide); it is pushed
# only when it would leave the board's free part, and then only as far as it must. And ⌘. twice shows the interface without playing the
# entrance again (owner: «при нажатии ⌘. интерфейс заново анимируется как при старте»): only the hide and the show run.
import pathlib, sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_shortcuts import run_server


@pytest.fixture
def server(tmp_path):
    yield from run_server(tmp_path)


M = """() => { const t = document.querySelector('#handles .tidy').getBoundingClientRect(), e = EL.get('i0').getBoundingClientRect(),
  i = document.querySelector('#info').getBoundingClientRect(), f = hyBars.free(stage, INSET);
  return { bar: (t.left + t.right) / 2, card: (e.left + e.right) / 2, l: t.left, r: t.right, top: t.top, bottom: t.bottom, info: [i.left, i.top, i.bottom], free: f }; }"""
# the card at (x, y) on screen at zoom z, selected
PUT = """([x, y, z]) => { const it = board.items.i0, st = stage.getBoundingClientRect(); cam.z = z; cam.x = it.x - (x - st.left) / z;
  cam.y = it.y - (y - st.top) / z; renderCam(); sel.clear(); sel.add('i0'); render(); }"""


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_the_bar_is_centred_on_a_card_in_view_and_moves_with_it(server, engine):
    with sync_playwright() as p:
        b = getattr(p, engine).launch(); page = b.new_page(viewport={"width": 1300, "height": 900})
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/canvas.html?board=main")
        page.wait_for_function("() => typeof board !== 'undefined' && board.items && board.items.i0 && EL.get('i0')")
        page.evaluate(PUT, [600, 400, 1]); page.wait_for_timeout(300)
        info = page.evaluate(M)["info"]
        assert info[2] > info[1] + 20, "the info panel shows for the selected picture"
        # the card wholly in view, its right part under the info panel's x but well below it: the bar stays centred on the card
        for z in (0.8, 1, 1.4):
            for x in (420, 560, 700):
                page.evaluate(PUT, [x, info[2] + 140, z]); page.wait_for_timeout(120)
                m = page.evaluate(M)
                assert abs(m["bar"] - m["card"]) <= 1, ("centred on the card", z, x, m)
        # bars carry no transition: they follow the board on the frame it moves
        assert page.evaluate("() => { const s = getComputedStyle(document.querySelector('#handles .tidy')); return [s.transitionDuration, s.transitionProperty]; }")[0] in ("0s", "0s, 0s")
        # a pan, frame by frame: the bar's offset to the card the same on every frame
        page.evaluate(PUT, [500, info[2] + 140, 1]); page.wait_for_timeout(120)
        offs = page.evaluate("""() => new Promise(done => { const out = []; let n = 0;
          const step = () => { cam.x -= 3; renderCam(); const t = document.querySelector('#handles .tidy').getBoundingClientRect(), e = EL.get('i0').getBoundingClientRect();
            out.push((t.left + t.right) / 2 - (e.left + e.right) / 2); if (++n < 40) requestAnimationFrame(step); else done(out); };
          requestAnimationFrame(step); })""")
        assert max(offs) - min(offs) <= 0.5 and abs(offs[0]) <= 1, offs
        # near the left edge (the library's inset) the bar is pushed only as far as it must: its left 8 px from the edge
        page.evaluate("() => postMessage({ type: 'inset', left: 300, row: 12, ms: 0 }, location.origin)"); page.wait_for_timeout(100)
        page.evaluate(PUT, [260, info[2] + 140, 1]); page.wait_for_timeout(150)
        m = page.evaluate(M)
        assert abs(m["l"] - m["free"]["l"]) <= 1 and m["bar"] > m["card"], ("pushed to the free part's edge, no further", m)
        assert not errors, errors
        b.close()


ANIMS = "() => document.getAnimations().map(a => a.animationName).filter(Boolean)"


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_hiding_and_showing_the_interface_does_not_replay_the_entrance(server, engine):
    with sync_playwright() as p:
        b = getattr(p, engine).launch(); page = b.new_page(viewport={"width": 1300, "height": 900})
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/canvas.html?board=main&intro=1")   # the entrance runs (automation skips it without intro=1)
        page.wait_for_function("() => typeof board !== 'undefined' && board.items && board.items.i0")
        page.wait_for_function("() => !document.documentElement.classList.contains('preintro') && !document.documentElement.classList.contains('intro')", timeout=20000)
        page.wait_for_timeout(1500)
        assert page.evaluate(ANIMS) == [], "the entrance is over"
        mod = "Meta" if engine == "webkit" else "Control"
        for k in (mod, "Meta"):   # ⌘ on a Mac; Ctrl counts too (isCmd)
            page.keyboard.press(f"{k}+Period"); page.wait_for_timeout(500)
            if page.evaluate("() => window.hyUiHidden()"): break
        assert page.evaluate("() => window.hyUiHidden()"), "hidden"
        page.keyboard.press(f"{k}+Period"); page.wait_for_timeout(120)
        seen = set()
        for _ in range(12):   # the show (0.2 s) and well after it: only the show's animation runs
            seen |= set(page.evaluate(ANIMS)); page.wait_for_timeout(60)
        assert not page.evaluate("() => window.hyUiHidden()")
        assert seen <= {"hyUiBack"}, ("only the show runs, not the entrance", seen)
        assert not errors, errors
        b.close()
