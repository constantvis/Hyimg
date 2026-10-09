"""The settings, one component on Home and on a board (owner 2026-10-07: «настройки причесать, переключатели странные ... и настройки
на доске отличаются от настроек тут»): ui/setpanel.js draws the same sections and rows in the same order on both, every choice is a
<hy-segmented variant=tint>, an on/off a <hy-switch>, each control changes its setting (a board: localStorage and the app's settings
file; Home: a message to the app), Reset puts the paper's colours back. Since 2026-10-08 they stand in a window inside the page
(ui/settings-win.js, owner: «изначально ты нажимаешь, у тебя прям настройки открываются широко, красиво, а не в углу»): large and in the
middle, a rail of sections, a search across them, resized by its edges up to the whole window, its size remembered, closed by Esc, a
click on the veil and the settings button. Since round 11 (owner 2026-10-08: «В обеих вроде все нравится») a board opens them at its
side by default: a panel docked at the right under the top row, every section under its folding header, the board working beside it,
its width the viewer's; «Open as a window» and «Dock to the side» switch, kept in the app's settings (cv.setsdock). Home keeps the
window. Every control lies in a dark well, the chosen thing on a grey plate (ui/hy variant=well). Chromium, dark theme."""
import io
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
from PIL import Image

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "review/home.html").as_uri()
BRIDGE = "window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };"
# the rows' outline: each group's section (and heading) and its rows in order, each row with its name and its options
OUTLINE = """() => [...document.querySelectorAll('#sets .sp .sp-g, #sets .sp .sh, #sets .sp .sp-row')].map(e => e.matches('.sp-g') ? '@ ' + e.dataset.sec
  : e.matches('.sh') ? '# ' + e.textContent
  : [e.dataset.row, (e.querySelector('.sp-l') || {}).textContent || '', [...e.querySelectorAll('hy-segmented > button')].map(b => b.value).join('|'), e.hidden ? 'hidden' : ''].join(' '))"""
CHOSEN = """k => { const s = document.querySelector(`#sets hy-segmented[data-set=${k}]`); if (!s) return document.querySelector(`#sets hy-switch[data-set-sw=${k}]`)
  .hasAttribute('checked') ? '1' : '0'; const b = s.querySelector(':scope > button.on'); return b && b.value; }"""
# the section of the window each setting stands in (ui/setpanel.js ROWS)
SEC = {"lang": "appearance", "theme": "appearance", "shape": "appearance", "shadow": "appearance", "glass": "appearance", "paper": "board", "grain": "board",
       "dotsv": "board", "sleep": "board", "applinks": "board", "hideui": "interface", "keyhint": "interface", "engine": "performance", "lod": "performance",
       "dotsgl": "performance", "perflog": "performance"}
BOX = "() => { const r = document.querySelector('#sets .sw-box').getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map(Math.round); }"


def go(page, k):
    """shows the section of a setting (or a section by its name): the window's rail, or at the side unfolded at the top"""
    page.evaluate("s => hySetPanel.go(s)", SEC.get(k, k))


SIDE = "() => document.querySelector('#sets').classList.contains('sw-side')"


def mode(page, want):
    """the settings at the side ("side") or as a window ("window"), by the key in their header"""
    if page.evaluate(SIDE) != (want == "side"):
        page.click("#sets [data-sw-act=mode]"); page.wait_for_timeout(500)
    assert page.evaluate(SIDE) == (want == "side")


@pytest.fixture(scope="module")
def board(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("setpanel")
    lib, state = tmp / "lib", tmp / "state"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    b = io.BytesIO(); Image.new("RGB", (40, 60), (90, 90, 90)).save(b, "PNG"); (lib / "a/0.png").write_bytes(b.getvalue())
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {"i0": {"path": "a/0.png", "x": 0, "y": 0, "w": 200, "ar": 2 / 3}},
                                                        "groups": {}, "removed": {}}))
    settings = tmp / "settings.json"; settings.write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    (tmp / "home").mkdir()
    env.update(HOME=str(tmp / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(settings),
               HYIMG_PLUGINS=str(tmp / "noplugins"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    try:
        yield port, settings
    finally:
        proc.terminate(); proc.wait(5); log.close()


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try: br = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        yield br
        br.close()


def open_board(browser, port, how="side"):
    page = browser.new_page(viewport={"width": 1300, "height": 1000}, color_scheme="dark"); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(BRIDGE)   # as in the Mac app: the Engine row shows, the switch goes to the app
    page.goto(f"http://127.0.0.1:{port}/canvas.html")
    page.wait_for_function("() => typeof board !== 'undefined' && Object.keys(board.items).length && customElements.get('hy-segmented')", timeout=20000)
    page.click("#bset"); page.wait_for_selector("#sets.open"); page.wait_for_timeout(300)
    mode(page, how)
    return page, errors


def open_home(browser):
    page = browser.new_page(viewport={"width": 1300, "height": 1000}, color_scheme="dark"); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(BRIDGE); page.add_init_script("window.HY_LANG = 'en';")
    page.goto(HOME)
    page.evaluate("hyimgHome({ projects: [], settings: { 'cv.lang': 'en', 'cv.theme': 'dark' }, home: { folders: [] }, cef: true, engine: 'webkit' })")
    page.click("#bset"); page.wait_for_selector("#sets.open"); page.wait_for_timeout(300)
    return page, errors


def test_the_same_panel_on_home_and_on_a_board(browser, board):
    port, _ = board
    bp, berr = open_board(browser, port, "window")
    hp, herr = open_home(browser)
    b, h = bp.evaluate(OUTLINE), hp.evaluate(OUTLINE)
    assert b == h, (b, h)
    assert [x for x in b if x[0] in "@#"] == ["@ appearance", "@ board", "@ board", "@ interface", "@ performance", "@ performance", "# Diagnostics"]
    assert [x.split(" ")[0] for x in b if x[0] not in "@#"] == ["lang", "theme", "shape", "shadow", "glass", "paper", "grain", "dotsv", "sleep", "applinks",
                                                                "hideui", "keyhint", "engine", "lod", "dotsgl", "perflog"]
    # the rail: the same sections on both, in E1's order; the modules' sections stand in the window too
    RAIL = "() => [...document.querySelectorAll('#sets .sw-rail [data-go]')].map(b => b.dataset.go)"
    assert bp.evaluate(RAIL) == hp.evaluate(RAIL) == ["profile", "team", "appearance", "board", "notifications", "plugins", "storage", "interface", "performance"]
    for pg in (bp, hp):
        pg.wait_for_function("() => ['hyMacNotif', 'hyPlugSet', 'hyStore'].every(id => document.getElementById(id) && document.getElementById(id).closest('.sw-body'))", timeout=10000)
        assert pg.evaluate("() => [...document.querySelectorAll('#hyPeopleSet [data-sec]')].map(e => e.dataset.sec)") == ["profile", "team"]
        assert pg.evaluate("() => ['hyMacNotif', 'hyPlugSet', 'hyStore'].map(id => document.getElementById(id).dataset.sec)") == ["notifications", "plugins", "storage"]
    # the visual choices are pictures of the app in that look (owner 2026-10-08, the concepts' previews), each option one
    PV = "() => [...document.querySelectorAll('#sets hy-segmented.sp-pvs')].map(s => s.dataset.set + ':' + s.querySelectorAll(':scope > button .sp-pvi .sp-mini').length)"
    assert bp.evaluate(PV) == hp.evaluate(PV) == ["theme:4", "shape:2", "shadow:3", "glass:2", "grain:4"], bp.evaluate(PV)
    assert bp.evaluate(CHOSEN, "perflog") == hp.evaluate(CHOSEN, "perflog") == "1"   # the performance log starts on (owner 2026-10-08)
    assert bp.evaluate(CHOSEN, "sleep") == hp.evaluate(CHOSEN, "sleep") == "10"   # boards behind sleep after 10 minutes (owner 2026-10-08)
    assert bp.evaluate(CHOSEN, "applinks") == hp.evaluate(CHOSEN, "applinks") == "0"   # «Open board links in the app» starts off (owner 2026-10-07)
    assert bp.evaluate(CHOSEN, "keyhint") == hp.evaluate(CHOSEN, "keyhint") == "learn"   # key hints until learned (owner 2026-10-08)
    for pg in (bp, hp):
        # every choice is the primitive in its well variant (round 11): a dark well, the chosen option on a grey plate in the panel's ink
        # (the selection's blue ring is the owner's open question: grey until he says)
        assert pg.evaluate("() => [...document.querySelectorAll('#sets .sp hy-segmented')].every(s => s.getAttribute('variant') === 'well' && s.classList.contains('has-st'))")
        go(pg, "hideui")
        look = pg.evaluate("""() => { const s = document.querySelector('#sets hy-segmented[data-set=hideui]'), on = s.querySelector('button.on'), off = s.querySelector('button:not(.on)');
          const tok = n => { const i = document.createElement('i'); i.style.background = `var(${n})`; s.appendChild(i); const c = getComputedStyle(i).backgroundColor; i.remove(); return c; };
          return { track: getComputedStyle(s).backgroundColor, ink: getComputedStyle(on).color, other: getComputedStyle(off).color,
                   thumb: getComputedStyle(s.querySelector('.st')).backgroundColor, well: tok('--hy-well'), plate: tok('--hy-thumb'), panel: tok('--ink') }; }""")
        assert look["track"] == look["well"] != "rgba(0, 0, 0, 0)" and look["thumb"] == look["plate"] != look["track"], look
        assert look["ink"] == "rgb(250, 250, 250)" and look["other"] != look["ink"], look
        # a visual choice: its chosen picture on the same grey plate, the choice's thumb
        assert pg.evaluate("""() => [...document.querySelectorAll('#sets hy-segmented.sp-pvs')].every(s => { const t = s.querySelector(':scope > .st'), b = s.querySelector('button.on');
          return t && getComputedStyle(t).backgroundColor === getComputedStyle(document.querySelector('#sets hy-segmented[data-set=hideui] > .st')).backgroundColor; })""")
        # an on/off is the app's switch in the same well; Reset is a plain hy-button
        assert pg.evaluate("() => [...document.querySelectorAll('#sets .sp hy-switch')].map(s => s.dataset.setSw + ':' + s.getAttribute('variant'))") == ["applinks:well", "perflog:well"]
        assert pg.evaluate("() => document.querySelector('#sets [data-paper-reset]').localName") == "hy-button"
    assert hp.evaluate(BOX) == bp.evaluate(BOX)   # the same window on both
    # Home keeps the window: no key to dock it; a board has it
    assert hp.locator("#sets [data-sw-act=mode]").count() == 0 and hp.locator("#sets [data-sw-act=close]").count() == 1
    assert bp.get_attribute("#sets [data-sw-act=mode]", "label") == "Dock to the side"
    assert not berr and not herr, (berr, herr)
    bp.close(); hp.close()


def test_each_control_on_a_board(browser, board):
    port, settings = board
    page, errors = open_board(browser, port)
    de = lambda k: page.evaluate(f"() => document.documentElement.dataset.{k}")
    ls = lambda k: page.evaluate(f"() => localStorage.getItem('cv.{k}')")
    for k, v in [("theme", "light"), ("theme", "dark"), ("shape", "pro"), ("shadow", "panels"), ("glass", "0"), ("grain", "3"), ("lod", "0"), ("dotsgl", "1"), ("hideui", "slide"),
                 ("applinks", "1"), ("sleep", "30")]:
        go(page, k)
        page.click(f"#sets hy-switch[data-set-sw={k}]" if k == "applinks" else f"#sets hy-segmented[data-set={k}] > button[value='{v}']")
        assert ls(k) == v and page.evaluate(CHOSEN, k) == v, (k, v)
        if k == "theme": assert de("theme") == v
        if k == "shape": assert de("shape") == "pro"
        if k == "shadow": assert de("shadow") == "panels"
        if k == "glass": assert not page.evaluate("() => stage.classList.contains('glass')")
    # the words under a row's name follow the choice; a switch's too
    assert page.inner_text("#sets [data-tip=applinks]") == "A board link opened in a browser goes straight to Hyimg"
    # by the keyboard: the arrows move the choice (the element's own keys, its hy-change)
    go(page, "hideui"); page.focus("#sets hy-segmented[data-set=hideui] > button.on"); page.keyboard.press("ArrowLeft")
    assert ls("hideui") == "zoom" and page.evaluate(CHOSEN, "hideui") == "zoom"
    assert page.inner_text("#sets [data-tip=hideui]") == "Everything around the board grows a little and fades out"
    # the performance log: its switch, by a click on its row's name too (the row is the switch's label)
    go(page, "perflog"); page.click("#sets [data-row=perflog] .sp-l")
    assert ls("perflog") == "0" and page.evaluate(CHOSEN, "perflog") == "0"
    page.click("#sets hy-switch[data-set-sw=perflog]"); assert ls("perflog") == "1"
    # the app's settings file gets them, «Hide interface» too (it reaches every board and Home)
    for _ in range(40):
        f = json.loads(settings.read_text())
        if f.get("cv.hideui") == "zoom" and f.get("cv.shape") == "pro": break
        time.sleep(0.1)
    assert f.get("cv.hideui") == "zoom" and f.get("cv.shape") == "pro" and f.get("cv.grain") == "3" and f.get("cv.applinks") == "1", f
    assert f.get("cv.sleep") == "30", f   # the app reads it there (native/BoardSleep.swift)
    # the engine goes to the app
    go(page, "engine"); page.click("#sets hy-segmented[data-set=engine] > button[value=chromium]")
    assert {"action": "engine", "engine": "chromium"} in page.evaluate("window.__sent")
    # the paper: a colour, then Reset puts both back
    go(page, "paper")
    page.evaluate("() => { const i = document.querySelector('#sets [data-paper=paperDark]'); i.value = '#203040'; i.dispatchEvent(new Event('input', { bubbles: true })); }")
    assert ls("paperDark") == "#203040" and page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--paper-d').trim()") == "#203040"
    page.click("#sets [data-paper-reset]")
    assert ls("paperDark") is None and page.evaluate("() => document.querySelector('#sets [data-paper=paperDark]').value") == "#17171a"
    page.evaluate("() => { const i = document.getElementById('dotsVis'); i.value = 60; i.dispatchEvent(new Event('input', { bubbles: true })); }")
    assert ls("dotsv") == "60"
    assert not errors, errors
    page.close()


def test_each_control_on_home(browser):
    page, errors = open_home(browser)
    sent = lambda: [m.get("change") for m in page.evaluate("window.__sent || []") if m.get("action") == "settings"]
    for k, v in [("theme", "light"), ("theme", "dark"), ("shape", "pro"), ("shadow", "panels"), ("glass", "0"), ("grain", "1"), ("lod", "2"), ("dotsgl", "1"), ("hideui", "slide"),
                 ("applinks", "1"), ("sleep", "0")]:
        go(page, k)
        page.click(f"#sets hy-switch[data-set-sw={k}] input" if k == "applinks" else f"#sets hy-segmented[data-set={k}] > button[value='{v}']")
        assert {f"cv.{k}": v} in sent() and page.evaluate(CHOSEN, k) == v, (k, v, sent()[-3:])
        if k in ("theme", "shape", "shadow"): assert page.evaluate(f"() => document.documentElement.dataset.{k}") == ("pro" if k == "shape" else v)
    # Home's choices are not upgraded elements (a file page): its own arrow keys
    go(page, "hideui"); page.focus("#sets hy-segmented[data-set=hideui] > button.on"); page.keyboard.press("ArrowLeft")
    assert {"cv.hideui": "zoom"} in sent() and page.evaluate(CHOSEN, "hideui") == "zoom"
    go(page, "engine"); page.click("#sets hy-segmented[data-set=engine] > button[value=chromium]")
    assert {"action": "engine", "engine": "chromium"} in page.evaluate("window.__sent")
    go(page, "paper")
    page.evaluate("() => { const i = document.querySelector('#sets [data-paper=paperLight]'); i.value = '#ffeedd'; i.dispatchEvent(new Event('input', { bubbles: true })); }")
    page.wait_for_timeout(400)
    assert {"cv.paperLight": "#ffeedd"} in sent()
    page.focus("#sets [data-paper-reset]"); page.keyboard.press("Enter")   # the un-upgraded hy-button is a button for the keyboard too
    assert {"cv.paperLight": None} in sent() and {"cv.paperDark": None} in sent()
    assert page.evaluate("() => document.querySelector('#sets [data-paper=paperLight]').value") == "#ebe6dc"
    assert not errors, errors
    page.close()


# «Тени» (owner 2026-10-08: «добавь среднюю: для панелей тень, а для верхнего и нижнего блока тени нет»): which of a plate of the top row,
# a round key of it, the dock and a side panel lie flat (no shadow, or only a transparent one)
SHADE = """() => { const flat = s => { const v = getComputedStyle(document.querySelector(s)).boxShadow;
  return v === 'none' || !v.replace(/rgba\\(0, 0, 0, 0\\) 0px 0px 0px 0px(, )?/g, ''); };
  return { row: flat('#crumb'), keys: flat('#bset'), dock: flat('#dock'), panel: flat('#sets .sw-box') }; }"""
FLAT = {"1": dict(row=False, keys=False, dock=False, panel=False), "panels": dict(row=True, keys=True, dock=True, panel=False),
        "0": dict(row=True, keys=True, dock=True, panel=True)}


def test_shadows_three_choices_none_by_default(browser, board):
    port, settings = board
    f = json.loads(settings.read_text()); f.pop("cv.shadow", None); settings.write_text(json.dumps(f))
    page, errors = open_board(browser, port)
    assert page.evaluate("() => document.documentElement.dataset.shadow") == "0" and page.evaluate(CHOSEN, "shadow") == "0"   # none by default
    go(page, "shadow")
    opts = page.evaluate("() => [...document.querySelectorAll('#sets hy-segmented[data-set=shadow] > button')].map(b => b.value + ' ' + b.textContent)")
    assert opts == ["1 With shadows", "panels Panels only", "0 No shadows"], opts
    for v in ("1", "panels", "0"):
        page.click(f"#sets hy-segmented[data-set=shadow] > button[value='{v}']"); page.wait_for_timeout(100)
        assert page.evaluate("() => document.documentElement.dataset.shadow") == v and page.evaluate(SHADE) == FLAT[v], (v, page.evaluate(SHADE))
    # the board's choice reaches the app's file, and Home takes it from there
    page.click("#sets hy-segmented[data-set=shadow] > button[value='panels']")
    for _ in range(40):
        if json.loads(settings.read_text()).get("cv.shadow") == "panels": break
        time.sleep(0.1)
    assert json.loads(settings.read_text()).get("cv.shadow") == "panels"
    hp = browser.new_page(viewport={"width": 1300, "height": 1000}, color_scheme="dark"); herr = []
    hp.on("pageerror", lambda e: herr.append(str(e)))
    hp.add_init_script(BRIDGE); hp.add_init_script("window.HY_LANG = 'en';")
    hp.goto(HOME)
    hp.evaluate("s => hyimgHome({ projects: [], settings: s, home: { folders: [] }, cef: true, engine: 'webkit' })", json.loads(settings.read_text()))
    hp.click("#bset"); hp.wait_for_selector("#sets.open"); go(hp, "shadow")
    assert hp.evaluate("() => document.documentElement.dataset.shadow") == "panels" and hp.evaluate(CHOSEN, "shadow") == "panels"
    # Home's choice goes to the app, the app writes the file, the board takes it when it comes to the front
    hp.click("#sets hy-segmented[data-set=shadow] > button[value='1']")
    assert {"cv.shadow": "1"} in [m.get("change") for m in hp.evaluate("window.__sent || []") if m.get("action") == "settings"]
    f = json.loads(settings.read_text()); f["cv.shadow"] = "1"; settings.write_text(json.dumps(f))
    page.evaluate("() => hyimgSettingsPull()")
    page.wait_for_function("() => document.documentElement.dataset.shadow === '1'", timeout=5000)
    assert page.evaluate(CHOSEN, "shadow") == "1" and page.evaluate(SHADE) == FLAT["1"]
    assert not errors and not herr, (errors, herr)
    page.close(); hp.close()


# The window (owner 2026-10-08, E1 «Rail popover» of Concepts/html/settings-concepts: «его можно растягивать на всю ширину, высоту ...
# изначально ты нажимаешь, у тебя прям настройки открываются широко, красиво, а не в углу»)
def test_the_window_opens_wide_in_the_middle_and_resizes(browser, board):
    port, _ = board
    page, errors = open_board(browser, port, "window")
    page.wait_for_timeout(400)   # the choice of the window reached the app's settings: the board opens it so after a reload
    page.evaluate("() => { localStorage.removeItem('hy.sets.size'); localStorage.removeItem('hy.sets.sec'); }")
    page.reload(); page.wait_for_function("() => typeof board !== 'undefined' && Object.keys(board.items).length", timeout=20000)
    page.click("#bset"); page.wait_for_selector("#sets.open"); page.wait_for_timeout(600)
    # min(1100, 90 %) by min(760, 85 %) of a 1300 × 1000 window, in its middle, over a veil; Appearance first, the search has the keys
    assert page.evaluate(BOX) == [100, 120, 1100, 760], page.evaluate(BOX)
    assert page.evaluate("() => document.querySelector('#sets .sw-rail .on').dataset.go") == "appearance"
    assert page.evaluate("() => document.activeElement === document.querySelector('#sets .sw-q input')")
    assert page.evaluate("() => document.elementFromPoint(20, 500).classList.contains('sw-veil')")
    # an edge follows the pointer and the other one moves as much the other way: the window stays in the middle
    def drag(handle, to):
        x, y = page.evaluate(f"() => {{ const r = document.querySelector('#sets .sw-rz[data-rz={handle}]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }}")
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(*to, steps=6); page.mouse.up(); page.wait_for_timeout(100)
    drag("e", (1250, 500))
    assert page.evaluate(BOX) == [50, 120, 1200, 760], page.evaluate(BOX)
    drag("n", (650, 200))
    assert page.evaluate(BOX) == [50, 200, 1200, 600], page.evaluate(BOX)
    assert json.loads(page.evaluate("localStorage.getItem('hy.sets.size')")) == {"w": 1200, "h": 600}
    # the corner past the window: the whole window, no corners; a double click on the title gives the size before back
    drag("se", (1400, 1100))
    assert page.evaluate(BOX) == [0, 0, 1300, 1000] and page.evaluate("() => document.querySelector('#sets .sw-box').classList.contains('sw-full')")
    page.dblclick("#sets .sw-hd"); page.wait_for_timeout(600)
    assert page.evaluate(BOX) == [50, 200, 1200, 600], page.evaluate(BOX)
    page.dblclick("#sets .sw-hd"); page.wait_for_timeout(600)
    assert page.evaluate(BOX) == [0, 0, 1300, 1000]
    # the size and the section are the viewer's: the same after a reload
    go(page, "storage")
    page.reload(); page.wait_for_function("() => typeof board !== 'undefined' && Object.keys(board.items).length", timeout=20000)
    page.click("#bset"); page.wait_for_selector("#sets.open"); page.wait_for_timeout(600)
    assert page.evaluate(BOX) == [0, 0, 1300, 1000] and page.evaluate("() => document.querySelector('#sets .sw-rail .on').dataset.go") == "storage"
    page.dblclick("#sets .sw-hd"); page.wait_for_timeout(600)
    assert not errors, errors
    page.close()


def test_the_window_closes_by_esc_the_veil_and_the_button(browser, board):
    port, _ = board
    page, errors = open_board(browser, port, "window")
    shown = "() => getComputedStyle(document.querySelector('#sets')).visibility !== 'hidden'"   # closed, it stays laid out and is not drawn
    page.keyboard.press("Escape"); page.wait_for_timeout(500)
    assert not page.evaluate(shown) and page.get_attribute("#bset", "aria-expanded") == "false"
    page.click("#bset"); page.wait_for_selector("#sets.open"); page.wait_for_timeout(400)
    page.mouse.click(20, 500); page.wait_for_timeout(500)   # the veil
    assert not page.evaluate("() => document.querySelector('#sets').classList.contains('open')") and not page.evaluate(shown)
    page.click("#bset"); page.wait_for_selector("#sets.open"); page.wait_for_timeout(400)
    page.click("#bset"); page.wait_for_timeout(500)   # the button stands over the veil
    assert not page.evaluate(shown)
    # a key typed in the window is not the board's (N would make a note under it)
    page.click("#bset"); page.wait_for_selector("#sets.open"); page.wait_for_timeout(400)
    n = page.evaluate("() => Object.keys(board.items).length")
    page.keyboard.type("n"); page.keyboard.press("Escape")   # the first Esc clears the search, the window stays
    assert page.evaluate("() => document.querySelector('#sets').classList.contains('open') && !document.querySelector('#sets .sw-q input').value")
    assert page.evaluate("() => Object.keys(board.items).length") == n
    assert not errors, errors
    page.close()


def test_the_search_finds_rows_in_every_section(browser, board):
    port, _ = board
    page, errors = open_board(browser, port, "window")
    page.wait_for_selector("#hyMacNotif .mn-row", state="attached")
    # the groups shown, in the order they stand on screen (the rail's: CSS order), each with its rows shown
    found = """() => [...document.querySelectorAll('#sets .sw-body [data-sec].sw-on')].sort((a, b) => getComputedStyle(a).order - getComputedStyle(b).order).map(g => g.dataset.sec + ':'
      + [...g.querySelectorAll('.sp-row, .mn-row, .hpl-row, .hs-row')].filter(r => r.offsetParent).map(r => r.dataset.row || r.dataset.mn || '').join(','))"""
    page.fill("#sets .sw-q input", "log")   # the performance log: its switch in Performance › Diagnostics, its size in Storage
    page.wait_for_timeout(200)
    got = page.evaluate(found)
    assert got == ["storage:", "performance:perflog"], got
    assert page.evaluate("() => [...document.querySelectorAll('#sets .sw-sl.sw-on')].map(l => l.dataset.for)") == [g.split(":")[0] for g in dict.fromkeys(got)]
    assert page.inner_text("#sets .sw-hd h2") == "Search" and page.inner_text("#sets .sw-cnt").endswith("found")
    # the rail counts them, the sections without any grow pale; the words found are marked (the CSS highlight API)
    assert page.evaluate("() => document.querySelector('#sets [data-go=performance] .sw-n').textContent") == "1"
    assert page.evaluate("() => document.querySelector('#sets [data-go=appearance]').classList.contains('dim')")
    assert page.evaluate("() => CSS.highlights.get('hy-set-q').size") >= 2
    # an option's words find their row: «Glass» is an option of Notes, «WebGL» of two rows; the macOS events by their words
    page.fill("#sets .sw-q input", "straight to hyimg"); page.wait_for_timeout(200)   # a switch's words when on
    assert page.evaluate(found) == ["board:applinks"]
    page.fill("#sets .sw-q input", "webgl"); page.wait_for_timeout(200)
    assert page.evaluate(found) == ["performance:lod,dotsgl"]
    page.fill("#sets .sw-q input", "mentioned"); page.wait_for_timeout(200)
    assert page.evaluate(found) == ["notifications:mac.mention"]
    page.fill("#sets .sw-q input", "zzzz"); page.wait_for_timeout(200)
    assert page.evaluate(found) == [] and page.inner_text("#sets .sw-cnt") == "Nothing found"
    # a section's button ends the search and shows that section whole
    go(page, "notifications"); page.wait_for_timeout(200)
    assert page.evaluate("() => document.querySelector('#sets .sw-q input').value") == ""
    assert page.evaluate(found) == ["notifications:mac,mac.agent,mac.comment,mac.reply,mac.mention,mac.note,mac.bg"]
    assert page.inner_text("#sets .sw-hd h2") == "Notifications"
    assert not errors, errors
    page.close()


# At the side (owner 2026-10-08, round 11 settings-side.html; his comment c43bcc5daff on the strip of the sections' icons under the search:
# «Так вот этот элемент можно убрать. Он тут лишний»)
SIDEBOX = "() => { const r = document.querySelector('#sets .sw-box').getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map(Math.round); }"
HEADS = """() => [...document.querySelectorAll('#sets .sw-body > .sw-sl')].filter(l => l.offsetParent).sort((a, b) => a.style.order - b.style.order)
  .map(l => l.dataset.for + (l.classList.contains('sw-shut') ? ' folded' : ''))"""


def test_a_board_opens_them_at_its_side(browser, board):
    port, settings = board
    page, errors = open_board(browser, port, "side")
    page.wait_for_function("() => ['hyMacNotif', 'hyPlugSet', 'hyStore', 'hyPeopleSet'].every(id => document.getElementById(id))", timeout=10000)
    page.wait_for_timeout(300)
    # docked at the right edge under the top row, 412 px wide, down to 12 px above the bottom; no veil, the page under it takes the pointer
    assert page.evaluate(SIDEBOX) == [1300 - 12 - 412, 58, 412, 1000 - 58 - 12], page.evaluate(SIDEBOX)
    assert page.evaluate("() => getComputedStyle(document.querySelector('#sets .sw-veil')).display") == "none"
    assert page.evaluate("() => document.documentElement.classList.contains('hy-sets-dock') && getComputedStyle(document.querySelector('#sets')).pointerEvents === 'none'")
    # its header with «Open as a window» and close, the search, the sections, the footnote: no strip of the sections' icons between
    assert page.evaluate("() => [...document.querySelector('#sets .sw-pane').children].map(e => e.className)") == ["sw-hd", "hy-search sw-q", "sw-body", "hy-hint sw-foot"]
    assert page.locator("#sets [role=tablist], #sets .snav").count() == 0 and not page.evaluate("() => !!document.querySelector('#sets .sw-rail').offsetParent")
    assert page.inner_text("#sets .sw-hd h2") == "Settings" and page.get_attribute("#sets [data-sw-act=mode]", "label") == "Open as a window"
    # every section under its header, in the rail's order; Profile and Team folded at first; the words at a header's end say what is chosen
    assert page.evaluate(HEADS) == ["profile folded", "team folded", "appearance", "board", "notifications", "plugins", "storage", "interface", "performance"]
    words = page.evaluate("() => ['theme', 'shape', 'shadow'].map(k => document.querySelector(`#sets hy-segmented[data-set=${k}] > button.on .sp-pvl`).textContent).join(' · ')")
    assert page.inner_text("#sets .sw-sl[data-for=appearance] .sw-sum") == words, words
    assert page.inner_text("#sets .sw-sl[data-for=notifications] .sw-sum") == "5 of 5 on"
    # a header folds its section and unfolds it again; the viewer's
    page.click("#sets .sw-sl[data-for=appearance]")
    assert page.evaluate("() => !document.querySelector('#sets [data-row=theme]').offsetParent") and "appearance" in json.loads(page.evaluate("localStorage.getItem('hy.sets.shut')"))
    page.click("#sets .sw-sl[data-for=appearance]")
    assert page.evaluate("() => !!document.querySelector('#sets [data-row=theme]').offsetParent")
    # a change shows on the board beside it at once, and the summary follows
    go(page, "shadow"); page.click("#sets hy-segmented[data-set=shadow] > button[value=panels]")
    assert page.evaluate("() => document.documentElement.dataset.shadow") == "panels"
    page.wait_for_timeout(100); assert page.inner_text("#sets .sw-sl[data-for=appearance] .sw-sum").endswith("Panels only")
    # the board keeps working beside it: a click selects a picture and the settings stay; Esc there is the board's
    xy = page.evaluate("() => { const r = EL.get('i0').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
    assert xy[0] < 1300 - 12 - 412
    page.mouse.click(*xy); page.wait_for_timeout(200)
    assert page.evaluate("() => sel.has('i0')") and page.evaluate("() => document.querySelector('#sets').classList.contains('open')")
    page.keyboard.press("Escape"); page.wait_for_timeout(200)
    assert page.evaluate("() => document.querySelector('#sets').classList.contains('open')")
    # its left edge sets its width, kept for the viewer
    x, y = page.evaluate("() => { const r = document.querySelector('#sets .sw-rz[data-rz=w]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
    page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x - 100, y, steps=6); page.mouse.up(); page.wait_for_timeout(100)
    w = page.evaluate(SIDEBOX)[2]
    assert abs(w - 512) <= 1 and page.evaluate("localStorage.getItem('hy.sets.side')") == str(w), w
    page.mouse.move(x - 100, y); page.mouse.down(); page.mouse.move(x - 2000, y, steps=4); page.mouse.up()   # never most of the window
    assert page.evaluate(SIDEBOX)[2] == 760
    page.mouse.move(*page.evaluate("() => { const r = document.querySelector('#sets .sw-rz[data-rz=w]').getBoundingClientRect(); return [r.left + 4, r.top + 300]; }"))
    page.mouse.down(); page.mouse.move(1290, 300, steps=4); page.mouse.up()
    assert page.evaluate(SIDEBOX)[2] == 320   # nor less than 320
    page.evaluate("() => localStorage.removeItem('hy.sets.side')")
    # the settings' own Esc: with the keyboard in the panel it closes it
    page.click("#sets .sw-q input"); page.keyboard.press("Escape"); page.wait_for_timeout(500)
    assert not page.evaluate("() => document.querySelector('#sets').classList.contains('open')") and not page.evaluate("() => document.documentElement.classList.contains('hy-sets-dock')")
    assert page.get_attribute("#bset", "aria-expanded") == "false"
    # «Open as a window»: the window over its veil, kept in the app's settings for every board; «Dock to the side» takes it back
    page.click("#bset"); page.wait_for_selector("#sets.open"); page.wait_for_timeout(400)
    page.click("#sets [data-sw-act=mode]"); page.wait_for_timeout(600)
    assert not page.evaluate(SIDE) and page.evaluate("() => getComputedStyle(document.querySelector('#sets .sw-veil')).opacity") == "1"
    assert page.get_attribute("#sets [data-sw-act=mode]", "label") == "Dock to the side"
    for _ in range(40):
        if json.loads(settings.read_text()).get("cv.setsdock") == "window": break
        time.sleep(0.1)
    assert json.loads(settings.read_text()).get("cv.setsdock") == "window"
    page.click("#sets [data-sw-act=mode]"); page.wait_for_timeout(600)
    assert page.evaluate(SIDE)
    for _ in range(40):
        if "cv.setsdock" not in json.loads(settings.read_text()): break
        time.sleep(0.1)
    assert "cv.setsdock" not in json.loads(settings.read_text())
    # the close key
    page.click("#sets [data-sw-act=close]"); page.wait_for_timeout(500)
    assert not page.evaluate("() => document.querySelector('#sets').classList.contains('open')")
    assert not errors, errors
    page.close()


def test_the_search_at_the_side(browser, board):
    port, _ = board
    page, errors = open_board(browser, port, "side")
    page.wait_for_selector("#hyMacNotif .mn-row", state="attached")
    found = """() => [...document.querySelectorAll('#sets .sw-body [data-sec].sw-on')].filter(g => g.getClientRects().length).sort((a, b) => a.style.order - b.style.order)
      .map(g => g.dataset.sec + ':' + [...g.querySelectorAll('.sp-row, .mn-row, .hpl-row, .hs-row')].filter(r => r.offsetParent).map(r => r.dataset.row || r.dataset.mn || '').join(','))"""
    page.fill("#sets .sw-q input", "webgl"); page.wait_for_timeout(200)
    assert page.evaluate(found) == ["performance:lod,dotsgl"] and page.evaluate(HEADS) == ["performance"]
    assert page.inner_text("#sets .sw-qn") == "2" and page.evaluate("() => CSS.highlights.get('hy-set-q').size") >= 2
    # a folded section opens while it has rows found: Profile's folders
    page.fill("#sets .sw-q input", "private folder"); page.wait_for_timeout(200)
    assert page.evaluate(HEADS) == ["profile"] and page.evaluate("() => !!document.querySelector('#sets .hp-prof').offsetParent")
    page.fill("#sets .sw-q input", "zzzz"); page.wait_for_timeout(200)
    assert page.evaluate(found) == [] and page.evaluate(HEADS) == [] and page.inner_text("#sets .sw-qn") == "0"
    # the first Esc clears it, every section is back (Profile folded again), the second closes
    page.keyboard.press("Escape"); page.wait_for_timeout(200)
    assert page.evaluate("() => document.querySelector('#sets').classList.contains('open') && !document.querySelector('#sets .sw-q input').value")
    assert page.evaluate(HEADS)[0] == "profile folded" and len(page.evaluate(HEADS)) == 9
    page.keyboard.press("Escape"); page.wait_for_timeout(500)
    assert not page.evaluate("() => document.querySelector('#sets').classList.contains('open')")
    assert not errors, errors
    page.close()


def test_the_window_in_russian_and_without_motion(browser):
    page = browser.new_page(viewport={"width": 1300, "height": 1000}, color_scheme="dark", reduced_motion="reduce"); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(BRIDGE); page.add_init_script("window.HY_LANG = 'ru';")
    page.goto(HOME)
    page.evaluate("hyimgHome({ projects: [], settings: { 'cv.lang': 'ru', 'cv.theme': 'dark' }, home: { folders: [] }, cef: true, engine: 'webkit' })")
    page.click("#bset"); page.wait_for_selector("#sets.open")
    # with «Reduce motion» it is there at once
    assert page.evaluate("() => getComputedStyle(document.querySelector('#sets .sw-box')).opacity") == "1"
    rail = page.evaluate("() => [...document.querySelectorAll('#sets .sw-rail [data-go] .sw-nt')].map(e => e.textContent)")
    assert rail == ["Команда и агенты", "Вид", "Доска", "Уведомления", "Плагины", "Хранилище", "Интерфейс", "Производительность"], rail
    assert page.get_attribute("#sets .sw-q input", "placeholder") == "Поиск"
    page.keyboard.press("Escape"); page.wait_for_timeout(50)
    assert page.evaluate("() => getComputedStyle(document.querySelector('#sets')).visibility") == "hidden"
    assert not errors, errors
    page.close()


# One definition for Home and every board (owner 2026-10-08, looking at Home's old panel beside a board's new window: «Почему настройки не
# синхронизированы? Оно должно быть одинаково, это же единое приложение»): both pages load the same two modules and draw the same window,
# the same sections with the same rows in the same order, the modules' sections included
SECTIONS = """() => [...document.querySelectorAll('#sets .sw-body [data-sec]')].sort((a, b) => getComputedStyle(a).order - getComputedStyle(b).order)
  .map(g => g.dataset.sec + ': ' + [...g.querySelectorAll('.sp-row[data-row], .mn-row, .hp-mine')].map(r => r.dataset.row || r.dataset.mn || r.dataset.agent).join(' '))"""


def test_one_definition_for_home_and_boards(browser, board):
    port, _ = board
    bp, berr = open_board(browser, port, "window")
    hp, herr = open_home(browser)
    for pg in (bp, hp):
        pg.wait_for_function("() => document.querySelector('#hyMacNotif .mn-row') && document.querySelector('#hyPeopleSet .hp-mine')", timeout=10000)
        assert pg.evaluate("() => [...document.scripts].filter(s => /ui\\/(setpanel|settings-win)\\.js$/.test(s.src)).length") == 2
        assert pg.evaluate("() => !!window.hySetWin && hySetPanel.body() === document.querySelector('#sets .sw-body')")
    b, h = bp.evaluate(SECTIONS), hp.evaluate(SECTIONS)
    assert b == h, (b, h)
    assert [x.split(":")[0] for x in dict.fromkeys(b)] == ["profile", "team", "appearance", "board", "board", "notifications", "plugins", "storage",
                                                           "interface", "performance", "performance"], b
    # the same window: the same rail, header, the knob on the settings button
    RAIL = "() => [document.querySelector('#sets .sw-rail').innerText, document.querySelector('#bset svg').innerHTML]"
    assert bp.evaluate(RAIL) == hp.evaluate(RAIL)
    assert not berr and not herr, (berr, herr)
    bp.close(); hp.close()
