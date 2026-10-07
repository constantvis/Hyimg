"""One slider for the whole app (owner 2026-10-06: «why are the sliders everywhere not the same as in 3D»): ui/slider.js + slider.css is the
3D editor's look, and the board's selection bar (opacity), the canvas settings (dots visibility), the library's card size (in its panel
and inline in the path bar) and Home's settings (dots visibility) use it. Measured here in Chromium and WebKit: the thin line sits on the
fill's end within 1 px at several values, a drag and the arrow keys change the value as they did, and the page's own code (opacity on the
frames, the card size, the stored setting) still gets its `input` events. Pictures are distinct: equal ones count once."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
ENGINES = ["chromium", "webkit"]
SHOTS = os.environ.get("HYIMG_TEST_SHOTS", "")
HOME = (ROOT / "review/home.html").as_uri()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    for n in range(6):
        (lib / "a" / f"{n}.png").write_bytes(png(40 + n * 3, 60))
    items = {f"i{n}": {"path": f"a/{n}.png", "x": n * 340, "y": 0, "w": 320, "ar": (60) / (40 + n * 3), "crop": None} for n in range(6)}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        yield port
    finally:
        process.terminate(); process.wait(5); log.close()


def launch(p, engine, **kw):
    try:
        return getattr(p, engine).launch(**kw)
    except Exception as error:
        pytest.skip(f"no {engine} for Playwright: {error}")


def shot(page, name, theme, engine):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(SHOTS) / f"slider-{name}-{theme}-{engine}.png"))


GEOM = """sel => { const w = document.querySelector(sel); const f = w.querySelector('.hy-slider-f').getBoundingClientRect(), t = w.querySelector('.hy-slider-t').getBoundingClientRect(),
  r = w.getBoundingClientRect(), i = w.querySelector('input[type=range]'); return { fill: f.right, line: (t.left + t.right) / 2, left: r.left, right: r.right, v: +i.value, min: +i.min, max: +i.max, p: getComputedStyle(w).getPropertyValue('--p'),
  end: w.classList.contains('sm') ? 1 : r.height * .1 + 1 }; }"""   # the line's clamp: inside the round ends (slider.css --hy-sl-end)


def check_geometry(ctx, sel, label):
    """the line stands on the fill's end within 1 px (clamped inside the track's round ends, --hy-sl-end) at the ends and at three values between"""
    lo, hi = ctx.evaluate("s => { const i = document.querySelector(s + ' input[type=range]'); return [+i.min, +i.max]; }", sel)
    for frac in (0, 0.25, 0.5, 0.9, 1):
        v = lo + (hi - lo) * frac
        ctx.evaluate("([s, v]) => { const i = document.querySelector(s + ' input[type=range]'); i.value = v; i.dispatchEvent(new Event('input', { bubbles: true })); }", [sel, v])
        g = ctx.evaluate(GEOM, sel)
        want = min(max(g["fill"], g["left"] + g["end"]), g["right"] - g["end"])
        assert abs(g["line"] - want) <= 1, (label, frac, g)
        assert abs(g["fill"] - (g["left"] + (g["right"] - g["left"]) * frac)) <= 1, (label, "fill is where the value is", frac, g)


def drag_and_keys(page, ctx, sel, origin=(0, 0), changed=None):
    """a click puts the value under the pointer, a drag moves it, the arrow keys move it by a step; `changed` is the page's own read-out"""
    box = ctx.evaluate("s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }", sel)
    x0, y, w = origin[0] + box[0], origin[1] + box[1] + box[3] / 2, box[2]
    lo, hi, v0 = ctx.evaluate("s => { const i = document.querySelector(s + ' input[type=range]'); return [+i.min, +i.max, +i.value]; }", sel)
    val = lambda: ctx.evaluate("s => +document.querySelector(s + ' input[type=range]').value", sel)
    page.mouse.move(x0 + w * 0.3, y); page.mouse.down(); page.mouse.up()
    assert abs(val() - (lo + (hi - lo) * 0.3)) <= (hi - lo) * 0.04, ("click", val())
    page.wait_for_timeout(450)   # a bar the page draws again after the click (the opacity's) settles before it is measured again
    box = ctx.evaluate("s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }", sel)
    x0, y, w = origin[0] + box[0], origin[1] + box[1] + box[3] / 2, box[2]
    page.mouse.move(x0 + w * 0.3, y); page.mouse.down(); page.mouse.move(x0 + w * 0.5, y, steps=6); page.mouse.move(x0 + w * 0.8, y, steps=6); page.mouse.up()
    assert abs(val() - (lo + (hi - lo) * 0.8)) <= (hi - lo) * 0.04, ("drag", val())
    check = ctx.evaluate(GEOM, sel); assert abs(check["line"] - min(max(check["fill"], check["left"] + check["end"]), check["right"] - check["end"])) <= 1, ("after the drag", check)
    before = val()
    focus = lambda: ctx.evaluate("s => document.querySelector(s + ' input[type=range]').focus()", sel)   # the opacity's bar is drawn again after each change: the key goes to the new one
    focus(); page.keyboard.press("ArrowLeft"); page.wait_for_timeout(120); after = val()
    assert after < before, ("ArrowLeft", before, after)
    focus(); page.keyboard.press("ArrowRight"); page.wait_for_timeout(120); focus(); page.keyboard.press("ArrowRight"); page.wait_for_timeout(120)
    assert val() > after, "ArrowRight"
    if changed: changed(page, val())
    check = ctx.evaluate(GEOM, sel); assert abs(check["line"] - min(max(check["fill"], check["left"] + check["end"]), check["right"] - check["end"])) <= 1, ("after the keys", check)


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("engine", ENGINES)
def test_board_selection_bar_opacity_and_settings_dots(server, engine, theme):
    with playwright.sync_playwright() as p:
        browser = launch(p, engine)
        page = browser.new_page(viewport={"width": 1300, "height": 800}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)) if "ResizeObserver loop" not in str(e) else None)   # WebKit's harmless note when a grid resizes with the card size
        url = f"http://127.0.0.1:{server}/canvas.html?board=main"
        page.goto(url)
        page.evaluate("t => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.theme', t); localStorage.setItem('cv.cam.main', JSON.stringify({x: -20, y: -60, z: 1})); }", theme)
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 6 && document.querySelectorAll('#items .it').length >= 3")
        page.evaluate("t => { document.documentElement.dataset.theme = t; }", theme)
        # opacity of the selection, the compact slider
        page.mouse.click(*page.evaluate("() => { const r = EL.get('i1').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }"))
        page.wait_for_selector(".tidy .op .hy-slider.sm")
        assert page.evaluate("() => !!document.querySelector('.tidy .op input[data-op]') && document.querySelector('.tidy .op input[data-op]').closest('.hy-slider')._hy !== undefined")
        check_geometry(page, ".tidy .op .hy-slider", "opacity")
        shot(page, "opacity", theme, engine)
        def opacity_read(pg, v):
            assert abs(pg.evaluate("() => board.items.i1.opacity ?? 1") - round(v) / 100) < 0.011, (v, pg.evaluate("() => board.items.i1.opacity"))
            assert pg.inner_text(".tidy .op b") == f"{round(v)}%"
        drag_and_keys(page, page, ".tidy .op .hy-slider", changed=opacity_read)
        # the settings panel: dots visibility, the labelled slider (the number is the slider's own, in %)
        page.click("#bset"); page.wait_for_selector("#sets.open")
        assert page.evaluate("() => !!document.querySelector('#sets #dotsVis').closest('.hy-slider') && !document.querySelector('#dotsVal')")
        check_geometry(page, "#sets .hy-slider", "dots")
        page.evaluate("() => { const i = document.getElementById('dotsVis'); i.value = 150; i.dispatchEvent(new Event('input', { bubbles: true })); }")
        assert page.inner_text("#sets .hy-slider-v") == "150%" and page.evaluate("() => localStorage.getItem('cv.dotsv')") == "150"
        shot(page, "settings", theme, engine)
        drag_and_keys(page, page, "#sets .hy-slider", changed=lambda pg, v: None)
        assert page.evaluate("() => localStorage.getItem('cv.dotsv')") == str(int(page.evaluate("() => +document.getElementById('dotsVis').value")))
        # one row radius (owner 2026-10-06: «одни круглые другие квадратные»): the slider and the rows beside it in the panel, round and pro
        RAD = "() => ['#sets .hy-slider', '#sets .seg', '#sets .paper label', '#sets .paper button'].map(s => getComputedStyle(document.querySelector(s)).borderTopLeftRadius)"
        assert set(page.evaluate(RAD)) == {"999px"}, page.evaluate(RAD)
        # the line never crosses the words: over the label it fades out, past it it shows (owner 2026-10-06: «Power, W» crossed near 0)
        UNDER = """v => { const r = document.querySelector('#sets .hy-slider'); hySlider.mount(r).set(v); return new Promise(ok => requestAnimationFrame(() => requestAnimationFrame(() => {
          const t = r.querySelector('.hy-slider-t').getBoundingClientRect(), l = r.querySelector('.hy-slider-l').getBoundingClientRect(), x = (t.left + t.right) / 2;
          ok({ over: x >= l.left - 4 && x <= l.right + 4, under: r.classList.contains('hy-under') }); }))); }"""
        for v in (5, 25, 45, 150):
            u = page.evaluate(UNDER, v); assert u["over"] == u["under"], (v, u)
        assert page.evaluate(UNDER, 25)["under"], "a value whose line falls on the label"
        page.wait_for_timeout(300)
        assert page.evaluate("() => getComputedStyle(document.querySelector('#sets .hy-slider .hy-slider-t')).opacity") == "0"
        # pro corners: the same slider, squarer, the same 8 px as its neighbours
        page.evaluate("() => { document.documentElement.dataset.shape = 'pro'; }")
        assert set(page.evaluate(RAD)) == {"8px"}, page.evaluate(RAD)
        check_geometry(page, "#sets .hy-slider", "dots, pro")
        shot(page, "settings-pro", theme, engine)
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("engine", ENGINES)
def test_library_card_size_in_its_panel_and_in_the_path_bar(server, engine, theme):
    with playwright.sync_playwright() as p:
        browser = launch(p, engine)
        page = browser.new_page(viewport={"width": 1700, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)) if "ResizeObserver loop" not in str(e) else None)   # WebKit's harmless note when a grid resizes with the card size
        page.goto(f"http://127.0.0.1:{server}/?view=panel")
        page.evaluate("t => { localStorage.clear(); localStorage.setItem('cv.theme', t); }", theme)
        page.goto(f"http://127.0.0.1:{server}/?view=panel"); page.wait_for_selector("#list .card")
        page.evaluate("t => { document.documentElement.dataset.theme = t; }", theme)
        # the library's normal width has no room in the path bar for it: the panel under its button
        page.wait_for_timeout(600); assert page.evaluate("() => !document.getElementById('lview').classList.contains('inl')")
        page.click("#lviewBtn"); page.wait_for_function("() => document.getElementById('lview').classList.contains('open')"); page.wait_for_timeout(400)
        assert page.evaluate("() => !!document.querySelector('#lview .hy-slider') && !document.querySelector('#lview .hy-slider').classList.contains('sm')")
        check_geometry(page, "#lview .hy-slider", "card size")
        assert page.inner_text("#lview .hy-slider-l") == "Size"
        shot(page, "card-size-panel", theme, engine)
        def size_read(pg, v):
            assert pg.evaluate("() => getComputedStyle(document.body).getPropertyValue('--ls').trim()") == f"{round(v)}px", (v, pg.evaluate("() => document.body.style.getPropertyValue('--ls')"))
        drag_and_keys(page, page, "#lview .hy-slider", changed=size_read)
        page.wait_for_timeout(400)
        assert page.evaluate("() => localStorage.getItem('lsize')") == str(int(page.evaluate("() => +document.getElementById('lsize').value")))
        # with room in the path bar it sits there as the compact slider, no words
        page.keyboard.press("Escape"); page.click("#lwide")   # the library at full width: room in the path bar
        page.wait_for_function("() => document.getElementById('lview').classList.contains('inl')", timeout=10000)
        page.wait_for_timeout(2500)   # the library's widening and the bar's own entrance end before the slider is measured
        assert page.evaluate("() => document.querySelector('#lview .hy-slider').classList.contains('sm')")
        assert page.evaluate("() => getComputedStyle(document.querySelector('#lview .hy-slider-l')).display") == "none"
        assert abs(page.evaluate("() => document.querySelector('#lview .hy-slider').getBoundingClientRect().width") - 96) <= 1
        check_geometry(page, "#lview .hy-slider", "card size inline")
        shot(page, "card-size-inline", theme, engine)
        drag_and_keys(page, page, "#lview .hy-slider")
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("engine", ENGINES)
def test_home_settings_dots(engine, theme):
    with playwright.sync_playwright() as p:
        browser = launch(p, engine)
        page = browser.new_page(viewport={"width": 1300, "height": 800}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)) if "ResizeObserver loop" not in str(e) else None)   # WebKit's harmless note when a grid resizes with the card size
        page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };")
        page.add_init_script("window.HY_LANG = 'en';")
        page.goto(HOME)
        page.evaluate("t => hyimgHome({ projects: [], settings: { 'cv.theme': t, 'cv.dotsv': '120' }, home: { folders: [] } })", theme)
        page.evaluate("() => document.getElementById('sets').classList.add('open')")
        assert page.inner_text("#sets .hy-slider-v") == "120%"
        check_geometry(page, "#sets .hy-slider", "home dots")
        shot(page, "home-settings", theme, engine)
        drag_and_keys(page, page, "#sets .hy-slider")
        page.wait_for_timeout(400)
        sent = [m for m in page.evaluate("window.__sent") if "cv.dotsv" in json.dumps(m)]
        assert sent, "the setting is still sent to the app"
        assert not errors, errors
        browser.close()
