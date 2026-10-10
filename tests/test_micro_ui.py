"""Round 15's micro UI (owner 2026-10-09 on Concepts/html/editors-concepts/r15/r15-micro.html: «Все топ, все делай, кроме номера пять»), in
Chromium, dark. The primitives on their showcase (review/ui/hy/showcase.html, family micro) at the sheet's sizes, their keyboard and ARIA:
the mini toggle is a switch, the micro segments a radiogroup, the stepper a spinbutton, the count a toggle button, the LED an image with
its name; then the board's places: Home's open board and Settings › Plugins wear the green LED (ring when off), «Arrange › Columns» is the
tiny stepper and reflows the grid in one undo step. The letter scrubber (control 5) waits for its examples.
"""
import os
from pathlib import Path

import pytest

from test_arrange_ui import CENTRE, close, server  # noqa: F401  (server is the fixture)
from test_home import HOME
from test_plugins_ui import board as plug_board, hy, switch  # noqa: F401  (hy is the fixture)
from test_primitives import serve

playwright = pytest.importorskip("playwright.sync_api")
LOOK = '.sc-fam[data-fam="micro"] .sc-look[data-hy-theme="dark"][data-hy-shape="round"] '
BOX = "e => { const r = e.getBoundingClientRect(); return [Math.round(r.width * 2) / 2, Math.round(r.height * 2) / 2]; }"
PSEUDO = "([e, ps]) => { const s = getComputedStyle(e, ps); return [parseFloat(s.width), parseFloat(s.height), s.backgroundColor]; }"
PROBE = """([v, prop]) => { const p = document.createElement('i'); p.style.setProperty(prop, v); document.body.append(p);
  const c = getComputedStyle(p).getPropertyValue(prop); p.remove(); return c; }"""


@pytest.fixture(scope="module")
def showcase(tmp_path_factory):
    proc, log, port = serve(tmp_path_factory.mktemp("hymicro"), "en")
    yield port
    proc.terminate(); proc.wait(5); log.close()


@pytest.fixture(scope="module")
def pw():
    with playwright.sync_playwright() as p:
        yield p


@pytest.fixture(scope="module")
def chromium(pw):
    try: b = pw.chromium.launch()
    except Exception as e: pytest.skip(f"chromium: {e}")
    yield b
    b.close()


def open_showcase(chromium, port):
    page = chromium.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="dark")
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{port}/lib/html/hy/index.html")
    page.wait_for_selector("html.sc-ready", timeout=15000); page.wait_for_timeout(400)
    page.errors = errors
    return page


def test_the_micro_primitives_render_at_the_sheets_sizes(chromium, showcase):
    page = open_showcase(chromium, showcase)
    sel = page.evaluate(PROBE, ["var(--hy-sel)", "background-color"])
    # 1 · mini toggle: 22 px, a 20 × 11 track and an 8 px knob, on in the selection's colour; bare it is 28 wide; a 24 px checkbox over it
    mt = page.locator(LOOK + "hy-minitoggle[checked]").first
    assert mt.evaluate(BOX)[1] == 22
    assert page.evaluate(PSEUDO, [mt.element_handle(), "::before"]) == [20, 11, sel]
    assert page.evaluate(PSEUDO, [mt.element_handle(), "::after"])[:2] == [8, 8]
    assert page.locator(LOOK + "hy-minitoggle[bare]").first.evaluate(BOX) == [28, 22]
    assert mt.evaluate("m => Math.round(m.input.getBoundingClientRect().height)") == 24
    # 2 · the count: an 18 px button «22 / 87»; all reads «87 / 87»
    sc = page.locator(LOOK + "hy-scope").first
    assert sc.locator("button").evaluate(BOX)[1] == 18 and sc.text_content() == "22/87"
    assert page.locator(LOOK + "hy-scope[all]").text_content() == "87/87"
    # 3 · micro segments: a 22 px well, 18 px options, an icon option 26 wide
    ms = page.locator(LOOK + 'hy-segmented[variant="micro"]')
    assert ms.first.evaluate(BOX)[1] == 22 and ms.first.locator("button").first.evaluate(BOX)[1] == 18
    assert ms.nth(2).locator("button").first.evaluate(BOX) == [26, 18]
    # 4 · the LED: 6 px, flat; on in the selection's colour, ok green, off a ring, busy blinking
    leds = page.locator(LOOK + "hy-led")
    got = leds.evaluate_all("ls => ls.map(l => { const s = getComputedStyle(l), r = l.getBoundingClientRect(); return [l.getAttribute('state') || 'on', r.width, r.height, "
                            "s.backgroundColor, s.boxShadow === 'none', s.animationName]; })")
    green = page.evaluate(PROBE, ["var(--hy-st-open)", "background-color"])
    assert got == [["on", 6, 6, sel, True, "none"], ["ok", 6, 6, green, True, "none"], ["off", 6, 6, "rgba(0, 0, 0, 0)", False, "none"],
                   ["busy", 6, 6, sel, True, "hy-led-busy"]], got
    # 6 · the stepper: one 22 px well, − and + 20 px, the number at least 26
    st = page.locator(LOOK + "hy-stepper").first
    assert st.evaluate(BOX)[1] == 22 and st.locator(".hy-stp-b").first.evaluate(BOX) == [20, 22] and st.locator(".hy-stp-n").evaluate(BOX)[0] >= 26
    # 7 · the change dot 5 px in the selection's colour, a chip's colour dot 6 px in its own colour, the chip 22 px
    assert page.locator(LOOK + ".sc-row > figure .hy-dot").first.evaluate("d => [d.getBoundingClientRect().width, getComputedStyle(d).backgroundColor]") == [5, sel]
    tag = page.locator(LOOK + ".hy-tag").first
    assert tag.evaluate(BOX)[1] == 22 and tag.locator(".hy-dot").evaluate(BOX) == [6, 6]
    # 8 · icons on hover: out until the row is hovered, a set one stays
    row = page.locator(LOOK + ".hy-hovrow")
    page.mouse.move(5, 5); page.wait_for_timeout(300)
    assert row.locator(".hy-ri").evaluate_all("bs => bs.map(b => [b.getBoundingClientRect().width, +getComputedStyle(b).opacity])") == [[20, 0], [20, 1]]
    row.hover(); page.wait_for_timeout(300)
    assert row.locator(".hy-ri").evaluate_all("bs => bs.map(b => +getComputedStyle(b).opacity)") == [1, 1]
    assert page.errors == [] and page.evaluate("() => window.__tMiss || []") == []
    page.close()


def test_the_micro_primitives_keyboard_and_aria(chromium, showcase):
    page = open_showcase(chromium, showcase)
    page.evaluate("() => { window.__ev = []; document.addEventListener('hy-change', e => __ev.push([e.target.localName, e.detail])); }")
    # the mini toggle is a switch: Space and Enter turn it, hy-change says so
    mt = page.locator(LOOK + "hy-minitoggle").first   # «All nodes», off
    inp = mt.locator("input")
    assert inp.evaluate("i => [i.type, i.getAttribute('role'), i.getAttribute('aria-label')]") == ["checkbox", "switch", "All nodes"]
    inp.focus(); page.keyboard.press("Space")
    assert mt.evaluate("m => [m.hasAttribute('checked'), m.input.checked]") == [True, True]
    page.keyboard.press("Enter")
    assert not mt.evaluate("m => m.hasAttribute('checked')")
    assert page.locator(LOOK + "hy-minitoggle[disabled] input").evaluate("i => i.disabled")
    # the micro segments are a radiogroup: radios, the chosen one in the Tab order, the arrows choose
    ms = page.locator(LOOK + 'hy-segmented[variant="micro"]').nth(1)
    assert ms.evaluate("s => [s.getAttribute('role'), s.getAttribute('aria-label'), "
                       "[...s.querySelectorAll('button')].map(b => [b.getAttribute('role'), b.getAttribute('aria-checked'), b.tabIndex])]") \
        == ["radiogroup", "Units", [["radio", "true", 0], ["radio", "false", -1], ["radio", "false", -1]]]
    ms.locator("button.on").focus(); page.keyboard.press("ArrowRight")
    assert ms.evaluate("s => s.value") == "m"
    page.keyboard.press("End")
    assert ms.evaluate("s => [s.value, document.activeElement.value]") == ["in", "in"]
    # the stepper's number is a spinbutton: ↑ ↓ step, ⇧ ten, Home and End the ends; − and + by pointer, out of the Tab order
    st = page.locator(LOOK + "hy-stepper").first
    n = st.locator(".hy-stp-n")
    assert n.evaluate("n => [n.getAttribute('role'), n.getAttribute('aria-valuenow'), n.getAttribute('aria-valuemin'), n.getAttribute('aria-valuemax'), n.getAttribute('aria-label'), n.tabIndex]") \
        == ["spinbutton", "3", "1", "12", "Columns", 0]
    assert st.locator(".hy-stp-b").evaluate_all("bs => bs.map(b => [b.tabIndex, b.getAttribute('aria-label')])") == [[-1, "Less"], [-1, "More"]]
    n.focus(); page.keyboard.press("ArrowUp")
    assert st.evaluate("s => s.value") == 4
    page.keyboard.press("Shift+ArrowUp")
    assert st.evaluate("s => s.value") == 12   # held at max
    assert st.locator(".hy-stp-b").nth(1).is_disabled()
    page.keyboard.press("Home")
    assert st.evaluate("s => s.value") == 1 and st.locator(".hy-stp-b").first.is_disabled()
    st.locator(".hy-stp-b").nth(1).click()
    assert n.get_attribute("aria-valuenow") == "2"
    # the count is a toggle button: aria-pressed and its words say both numbers
    sc = page.locator(LOOK + "hy-scope").first   # 22 / 87, the part
    b = sc.locator("button")
    assert b.evaluate("b => [b.getAttribute('aria-pressed'), b.getAttribute('aria-label')]") == ["false", "22 of 87 shown · show all"]
    b.click()
    assert b.evaluate("b => [b.getAttribute('aria-pressed'), b.getAttribute('aria-label'), b.textContent.replace(/\\s/g, '')]") == ["true", "All 87 shown · show only 22", "87/87"]
    # the LED is an image with its name
    assert page.locator(LOOK + "hy-led").evaluate_all("ls => ls.map(l => [l.getAttribute('role'), l.getAttribute('aria-label')])") \
        == [["img", "The current camera"], ["img", "Running"], ["img", "Not found"], ["img", "Working"]]
    ev = page.evaluate("() => __ev")
    assert ["hy-minitoggle", {"checked": True}] in ev and ["hy-segmented", {"value": "m"}] in ev and ["hy-stepper", {"value": 4}] in ev \
        and ["hy-scope", {"all": True}] in ev, ev
    assert page.errors == []
    page.close()


def test_home_marks_an_open_board_with_the_green_led(chromium):
    page = chromium.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => {} } } };")
    page.goto(HOME)
    page.evaluate("""() => hyimgHome({ projects: [{ id: "a", name: "Open board", path: "/x", available: true, updated: 1791100000, covers: [], open: true },
      { id: "b", name: "Closed board", path: "/y", available: true, updated: 1791000000, covers: [] }],
      home: { folders: [], favs: ["a", "b"] } })""")
    page.wait_for_selector("aside .nav[data-open=a]")
    assert page.locator("aside .dot").count() == 0
    led = page.locator("aside .nav[data-open=a] hy-led")
    green = page.evaluate(PROBE, ["var(--hy-st-open)", "background-color"])
    assert led.evaluate("l => { const r = l.getBoundingClientRect(); return [l.getAttribute('state'), r.width, r.height, getComputedStyle(l).backgroundColor, "
                        "l.getAttribute('role'), l.getAttribute('aria-label')]; }") \
        == ["ok", 6, 6, green, "img", "Open"]
    assert page.locator("aside .nav[data-open=b] hy-led").count() == 0
    page.close()


def test_settings_plugins_wear_the_led(hy, pw):  # noqa: F811
    port, _plugins, _tmp = hy
    br, page, errors = plug_board(pw, port)
    leds = "() => [...document.querySelectorAll('#hyPlugSet .hpl-row')].map(r => { const l = r.querySelector('.hpl-top > hy-led'); " \
           "return [r.dataset.pl, l && l.getAttribute('state'), l && Math.round(l.getBoundingClientRect().width), l && l.getAttribute('aria-label')]; })"
    page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "plugins"); page.wait_for_selector("#hyPlugSet .hpl-row >> nth=2")
    page.locator("#hyPlugSet").scroll_into_view_if_needed(); page.wait_for_timeout(400)
    if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / "micro-settings-plugins.png"))
    assert page.evaluate(leds) == [["3d", "ok", 6, "Running"], ["dev", "ok", 6, "Running"], ["frames", "ok", 6, "Running"]]
    switch(page, "dev")
    page.wait_for_function("() => typeof PLGST !== 'undefined' && PLGST.length === 2", timeout=30000)
    page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "plugins"); page.wait_for_selector("#hyPlugSet .hpl-row >> nth=2")
    assert page.evaluate(leds)[1] == ["dev", "off", 6, "Off"]
    assert errors == [], errors
    br.close()


def test_arrange_columns_is_the_tiny_stepper(server, chromium):  # noqa: F811
    port = server
    page = chromium.new_page(viewport={"width": 1600, "height": 1000}, color_scheme="dark")
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{port}/canvas.html")
    page.wait_for_function("() => typeof hyArrange !== 'undefined' && EL.get('a3')", timeout=20000)
    page.evaluate("() => { cam.x = 0; cam.y = 0; cam.z = 0.5; renderCam(); render(); }")
    ids = ["a0", "a1", "a2", "a3"]

    def arrange():
        close(page)
        page.evaluate("ids => { sel = new Set(ids); render(); }", ids)
        x, y = page.evaluate(CENTRE, ids[0]); page.mouse.click(x, y, button="right"); page.wait_for_selector("#ctx.open")
        page.locator('#ctx [data-sub="arrange"]').last.click(); page.wait_for_selector('#ctx [data-sub="arrange"][aria-expanded="true"]')

    arrange()
    assert page.locator("#ctx .hy-sub hy-stepper").count() == 0   # no grid yet: no columns
    page.locator('#ctx .hy-sub [data-how="make"]').last.click(); page.wait_for_function("() => board.grids && Object.keys(board.grids).length === 1")
    gid, cols = page.evaluate("() => { const [k, g] = Object.entries(board.grids)[0]; return [k, g.cols]; }")
    assert cols == 4
    arrange()
    st = page.locator(f'#ctx .hy-sub .hy-mstp hy-stepper[data-gcols="{gid}"]')
    assert st.count() == 1 and st.evaluate("s => [s.value, s.getAttribute('min'), s.getAttribute('max')]") == [4, "1", "4"]
    if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / "micro-arrange-columns.png"))
    assert page.locator("#ctx .hy-sub .hy-mstp .ml").inner_text() == "Columns"   # not in the capitals of a block's .hy-sub label
    assert st.evaluate("s => s.offsetHeight") == 22   # the panel may still be scaling in
    y0 = page.evaluate("() => board.items.a3.y")
    steps = page.evaluate("() => HY.steps")
    st.locator(".hy-stp-b").first.click(); page.wait_for_timeout(300)
    assert page.evaluate(f"() => board.grids['{gid}'].cols") == 3
    assert page.evaluate("() => board.items.a3.y") > y0   # the fourth went to a second row
    assert page.locator("#ctx.open").count() == 1   # the menu stays while − and + reflow the grid
    assert page.evaluate("() => HY.steps") == steps + 1
    page.keyboard.press("Escape"); close(page)
    page.keyboard.press("Meta+KeyZ"); page.wait_for_timeout(300)
    assert page.evaluate(f"() => [board.grids['{gid}'].cols, board.items.a3.y]") == [4, y0]
    assert errors == [], errors
    page.close()


def test_the_scrub_drags_the_letter_and_types_the_number(chromium, showcase):
    """round 16's scrub, version A (owner 2026-10-10 on r16-scrub.html: «отлично, беру»): drag the letter ← →, ⇧ ×10, ⌥ ×0.1, Esc while
    dragging puts the old value back, one hy-change a drag; a click on the number types it, Enter keeps it, ↑ ↓ step"""
    page = open_showcase(chromium, showcase)
    page.evaluate("() => { window.__ev = []; for (const t of ['hy-scrub-start', 'hy-input', 'hy-change', 'hy-cancel']) document.addEventListener(t, e => __ev.push(t)); }")
    f = page.locator(LOOK + 'hy-scrub[label="X"]')
    h = f.locator(".hy-scrub-h")
    assert f.evaluate(BOX)[1] == 24 and h.evaluate(BOX) == [22, 24]
    assert h.evaluate("h => getComputedStyle(h).cursor") == "ew-resize" and f.locator("input").evaluate("i => getComputedStyle(i).cursor") == "text"
    assert f.locator("input").evaluate("i => [i.value, i.inputMode, i.getAttribute('aria-label')]") == ["24", "decimal", "X"]
    assert f.locator(".hy-scrub-l").evaluate("l => getComputedStyle(l).color") == page.evaluate(PROBE, ["#ff5f6d", "color"])   # the X axis' red
    h.scroll_into_view_if_needed()
    x, y = h.evaluate("h => { const r = h.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")

    def drag(dx, key=None, esc=False):
        page.mouse.move(x, y); page.mouse.down()
        if key: page.keyboard.down(key)
        for i in range(1, 5): page.mouse.move(x + dx * i / 4, y)
        mid = page.evaluate("() => [document.documentElement.classList.contains('hy-scrub-drag'), getComputedStyle(document.body).cursor]")
        if esc: page.keyboard.press("Escape")
        if key: page.keyboard.up(key)
        page.mouse.up()
        return mid

    assert drag(20) == [True, "ew-resize"]   # the page keeps ew-resize for the whole drag
    assert f.evaluate("f => f.value") == 44 and not page.evaluate("() => document.documentElement.classList.contains('hy-scrub-drag')")
    ev = page.evaluate("() => __ev"); assert ev.count("hy-scrub-start") == 1 and ev.count("hy-change") == 1 and ev.count("hy-input") >= 3, ev
    drag(10, "Shift"); assert f.evaluate("f => f.value") == 144   # ⇧ ten times
    drag(-30, "Alt"); assert f.evaluate("f => f.value") == 141   # ⌥ a tenth
    page.evaluate("() => { __ev = []; }")
    drag(40, esc=True)
    assert f.evaluate("f => f.value") == 141 and "hy-cancel" in page.evaluate("() => __ev") and "hy-change" not in page.evaluate("() => __ev")
    # the minimum holds: W 160, min 16
    w = page.locator(LOOK + 'hy-scrub[label="W"]')
    wx, wy = w.locator(".hy-scrub-h").evaluate("h => { const r = h.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
    page.mouse.move(wx, wy); page.mouse.down(); page.keyboard.down("Shift"); page.mouse.move(wx - 100, wy, steps=4); page.keyboard.up("Shift"); page.mouse.up()
    assert w.evaluate("f => f.value") == 16
    # a click on the letter without moving types the number; Enter keeps it, ↑ steps, Esc puts the typed one back
    h.click(); assert page.evaluate("() => document.activeElement.classList.contains('hy-scrub-v')")
    page.keyboard.type("42"); page.keyboard.press("Enter")
    assert f.evaluate("f => [f.value, f.input.value]") == [42, "42"]
    f.locator("input").click(); page.keyboard.press("ArrowUp"); page.keyboard.press("Shift+ArrowUp")
    assert f.evaluate("f => f.value") == 53
    page.keyboard.type("7"); page.keyboard.press("Escape")
    assert f.evaluate("f => [f.value, f.input.value]") == [53, "53"]
    assert page.errors == []
    page.close()
