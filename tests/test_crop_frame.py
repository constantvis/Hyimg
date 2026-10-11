"""The crop on the board, the owner's complaint of 2026-10-10 about it («все прыгает, скачет», a screenshot of the crop with its ratio
pills) and the board audit of 2026-10-11 (B-01 … B-06, B-08). Each test failed on the code before the fix: the pills moved under the
pointer, a ratio shrank the frame step by step, a locked corner jumped, a drag inside a whole picture drew a dot, the bar went under the
dock, the dock's Undo took a board step under an open crop, three quarters of each handle were dead. Chromium, dark theme, our own
server and folders (tests/test_p4_board.py's harness), the mouse for every gesture."""
import pytest

from test_p4_board import board_page, box, browser_of, pic, serve

playwright = pytest.importorskip("playwright.sync_api")

# a landscape picture 720 × 480 on the board at 100 %, as in the audit, and a second one beside it
ITEMS = {"i0": {"path": "a/0.png", "x": 0, "y": 0, "w": 720, "ar": 1.5, "crop": None}, "i1": pic(1, 900)}
WIN = "() => { const r = document.querySelector('#crop .win').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }"
PILLS = "() => [...document.querySelectorAll('#crop .cratio button'), document.querySelector('#crop .cratio')].map(b => { const r = b.getBoundingClientRect(); return [r.left, r.width]; })"
BAR = "() => { const r = document.querySelector('#crop .cratio').getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom }; }"


def run(tmp_path, fn, items=ITEMS):
    with serve(tmp_path, items) as (port, lib), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port)
        try: fn(page, page.evaluate)
        finally: browser.close()
        assert not errors, errors


def crop(page, ev, id="i0"):   # a click on the picture, ⇧C
    r = page.evaluate(f"() => {{ const r = EL.get('{id}').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }}")
    page.mouse.click(*r); page.keyboard.press("Shift+C"); page.wait_for_function("() => !!cropState")
    page.wait_for_timeout(50)


def still(page):   # where the bar stands once it stopped (lesson 20): the same place in five frames running
    return page.evaluate(f"""() => new Promise(done => {{ let last = '', n = 0; const at = {BAR};
      const step = () => {{ const b = JSON.stringify(at()); n = b === last ? n + 1 : 0; last = b; if (n >= 5) done(JSON.parse(b)); else requestAnimationFrame(step); }}; step(); }})""")


def pill(page, k):   # a ratio by what it says (5:4, 16:9 on a landscape picture)
    page.click(f"#crop .cratio button[data-k='{k}']" if k not in ("free", "flip") else f"#crop .cratio button[data-ratio='{k}']")


def test_b01_the_pills_never_move_and_the_platform_shows_over_them(tmp_path):
    def go(page, ev):
        crop(page, ev); page.mouse.move(5, 890); page.wait_for_timeout(450)
        before = ev(PILLS)
        for k in ("1:1", "16:9", "4:3", "free"):
            b = box(page, f"#crop .cratio button[data-k='{k}']" if k != "free" else "#crop .cratio button[data-ratio='free']")
            page.mouse.move(b["cx"], b["cy"]); page.wait_for_timeout(450)   # the old widening took .38 s
            now = ev(PILLS)
            assert all(abs(a[0] - c[0]) < 0.5 and abs(a[1] - c[1]) < 0.5 for a, c in zip(before, now)), (k, "nothing in the bar moved", before, now)
            tip = ev("() => { const t = document.querySelector('#crop .cratio .rtip.on'); return t && getComputedStyle(t).opacity === '1' ? t.textContent : null; }")
            # every format has its name since round 20 (2026-10-11), 4:3 too; Free none
            assert tip == {"1:1": "Instagram post", "16:9": "YouTube", "4:3": "iPhone photo · iPad", "free": None}[k], (k, tip)
        # a click keeps the pointer on the same pill: the next one is where it was
        b = box(page, "#crop .cratio button[data-k='1:1']"); page.mouse.click(b["cx"], b["cy"]); page.wait_for_timeout(450)
        assert ev(PILLS) == before
    run(tmp_path, go)


def test_b02_a_ratio_is_the_biggest_frame_of_it_and_never_shrinks(tmp_path):
    def go(page, ev):
        crop(page, ev)
        sizes = []
        for k in ("1:1", "16:9", "1:1", "3:2", "16:9"):
            pill(page, k); sizes.append(ev(WIN)[2:])
        assert sizes == [[480, 480], [720, 405], [480, 480], [720, 480], [720, 405]], sizes
        page.keyboard.press("x"); assert ev(WIN)[2:] == [270, 480]   # 9:16, the biggest that stands in the picture
        page.keyboard.press("x"); assert ev(WIN)[2:] == [720, 405]
        pill(page, "free"); page.keyboard.press("x"); page.keyboard.press("x"); assert ev(WIN)[2:] == [720, 405], "a free frame turned twice"
        # the frame moved to a side keeps its centre there, moved in where the bigger frame would leave the picture
        pill(page, "1:1"); w = ev(WIN); page.mouse.move(w[0] + 200, w[1] + 200); page.mouse.down(); page.mouse.move(w[0] + 80, w[1] + 200, steps=6); page.mouse.up()
        pill(page, "4:3"); assert ev(WIN)[2:] == [640, 480] and ev(WIN)[0] == ev("() => Math.round(EL.get('i0').getBoundingClientRect().left)")
        page.keyboard.press("r"); assert ev(WIN)[2:] == [640, 480], "R with a ratio: the biggest piece in it"
    run(tmp_path, go)


def test_b03_a_locked_corner_follows_the_pointer_smoothly(tmp_path):
    def go(page, ev):
        crop(page, ev); pill(page, "1:1")
        ev("() => { cropState.c = [0.3, 0.2, 0.7, 0.8]; drawCrop(); }")   # a frame 288 × 288 in the middle of the picture
        se = box(page, "#crop .h[data-c=se]"); x, y = se["cx"], se["cy"]
        page.mouse.move(x, y); page.mouse.down()
        ws = []
        for i in range(0, 41):   # up and right, the axis that moves further changes half way: (+40, -60) … (+60, -40)
            page.mouse.move(x + 40 + i * 0.5, y - 60 + i * 0.5); ws.append(ev(WIN)[2])
        page.mouse.up()
        steps = [abs(b - a) for a, b in zip(ws, ws[1:])]
        assert max(steps) <= 3, ("the frame's size changes smoothly", max(steps), ws)
        w = ev(WIN); assert abs(w[2] - w[3]) <= 1, "still square"
    run(tmp_path, go)


def test_b04_a_drag_inside_the_frame_moves_it_even_uncropped(tmp_path):
    def go(page, ev):
        crop(page, ev); w0 = ev(WIN)
        page.mouse.move(w0[0] + 300, w0[1] + 200); page.mouse.down(); page.mouse.move(w0[0] + 360, w0[1] + 240, steps=6); page.mouse.up()
        assert ev(WIN) == w0 and ev("() => cropState.c.join()") == "0,0,1,1", "the whole picture: nothing to move, nothing drawn"
        pill(page, "1:1"); w1 = ev(WIN)
        page.mouse.move(w1[0] + 240, w1[1] + 200); page.mouse.down(); page.mouse.move(w1[0] + 180, w1[1] + 205, steps=6); page.mouse.up()
        w2 = ev(WIN); assert w2[2:] == w1[2:] and w2[0] == w1[0] - 60, ("moved, the same size", w1, w2)
        # ⇧ draws a new frame
        page.keyboard.down("Shift"); page.mouse.move(w2[0] + 40, w2[1] + 40); page.mouse.down(); page.mouse.move(w2[0] + 140, w2[1] + 140, steps=6); page.mouse.up(); page.keyboard.up("Shift")
        assert ev(WIN)[2] == 100
    run(tmp_path, go)


@pytest.mark.parametrize("z", [0.3, 1.0, 1.6])
def test_b05_the_bar_stays_in_the_free_board_and_still_while_the_frame_moves(tmp_path, z):
    def go(page, ev):
        # the picture's top 60 px under the window's top: the old bar went under the picture, at 160 % under the dock
        ev(f"() => {{ cam.z = {z}; const st = stage.getBoundingClientRect(); cam.x = -(st.width / 2 - 360 * {z}) / {z}; cam.y = -60 / {z}; renderCam(); render(); }}")
        crop(page, ev)
        inside = """() => { const b = document.querySelector('#crop .cratio').getBoundingClientRect(), f = hyBars.free(stage, INSET),
          d = document.querySelector('#dock').getBoundingClientRect(), under = b.bottom > d.top && b.top < d.bottom && b.right > d.left && b.left < d.right;
          return b.top >= f.t - 0.5 && b.bottom <= f.b + 0.5 && b.left >= f.l - 0.5 && b.right <= f.r + 0.5 && !under; }"""
        page.wait_for_function(inside, timeout=3000)
        bar = still(page); pill(page, "1:1"); w = ev(WIN)
        page.mouse.move(w[0] + w[2] / 2, w[1] + w[3] / 2); page.mouse.down(); page.mouse.move(w[0] + w[2] / 2 + 40, w[1] + w[3] / 2, steps=5); page.mouse.up()
        now = still(page); assert all(abs(now[k] - bar[k]) <= 1 for k in bar), ("the frame moved, the bar did not", bar, now)
        page.mouse.move(720, 450); page.mouse.wheel(0, 120); page.wait_for_timeout(200)   # a scroll up: the picture's top leaves the window
        page.wait_for_function(inside, timeout=3000)
    run(tmp_path, go)


def test_b06_the_docks_undo_and_redo_are_the_crops_steps(tmp_path):
    def go(page, ev):
        crop(page, ev); ev("() => { cropState.c = [0.5, 0.4, 1, 1]; drawCrop(); }"); page.keyboard.press("Enter")
        page.wait_for_function("() => !cropState && board.items.i0.crop")
        cropped = ev("() => board.items.i0.crop.join()")
        crop(page, ev); u = box(page, "#bundo")
        page.mouse.click(u["cx"], u["cy"]); page.wait_for_timeout(100)
        assert ev("() => [!!cropState, board.items.i0.crop && board.items.i0.crop.join()]") == [True, cropped], "no board step under the crop"
        c0 = ev("() => cropState.c.join()"); pill(page, "1:1"); c1 = ev("() => cropState.c.join()"); assert c1 != c0
        page.mouse.move(u["cx"], u["cy"])   # the step's name over Undo says it is the crop's
        page.wait_for_function("() => { const p = document.getElementById('hytip'); return p && p.hasAttribute('shown') && /Crop frame/.test(p.textContent); }")
        page.mouse.click(u["cx"], u["cy"]); assert ev("() => [cropState.c.join(), cropState.key]") == [c0, "free"]
        r = box(page, "#bredo"); page.mouse.click(r["cx"], r["cy"]); assert ev("() => [cropState.c.join(), cropState.key]") == [c1, "1:1"]
        page.keyboard.press("Meta+z"); assert ev("() => cropState.c.join()") == c0
        page.keyboard.press("Meta+Shift+z"); assert ev("() => cropState.c.join()") == c1
        page.keyboard.press("Escape"); assert ev("() => board.items.i0.crop.join()") == cropped
    run(tmp_path, go)


def test_b08_eight_whole_handles_and_no_second_box(tmp_path):
    def go(page, ev):
        crop(page, ev); pill(page, "1:1")
        hs = ev("""() => [...document.querySelectorAll('#crop .h')].map(h => { const r = h.getBoundingClientRect(), pts = [[r.left + 5, r.top + 5], [r.right - 5, r.top + 5],
          [r.left + 5, r.bottom - 5], [r.right - 5, r.bottom - 5]];   // the four corners of the square, inside its rounding
          return [h.dataset.c, pts.every(([x, y]) => { const e = document.elementFromPoint(x, y); return e === h && /resize/.test(getComputedStyle(e).cursor); })]; })""")
        assert sorted(c for c, _ in hs) == sorted(["nw", "n", "ne", "e", "se", "s", "sw", "w"]) and all(ok for _, ok in hs), hs
        assert ev("() => document.querySelectorAll('#handles .selbox').length") == 0, "no blue selection box beside the crop frame"
        # an edge moves only its side
        w0 = ev(WIN); pill(page, "free"); e = box(page, "#crop .h[data-c=n]")
        page.mouse.move(e["cx"], e["cy"]); page.mouse.down(); page.mouse.move(e["cx"] + 30, e["cy"] + 50, steps=5); page.mouse.up()
        w1 = ev(WIN); assert [w1[0], w1[1], w1[2], w1[3]] == [w0[0], w0[1] + 50, w0[2], w0[3] - 50], (w0, w1)
    run(tmp_path, go)
