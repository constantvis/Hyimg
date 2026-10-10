"""Two keys as in Figma (owner 2026-10-06): ⌘M opens and closes the media library (it was ⌘., and ⌘M was the Mac's Minimize), ⌘. hides all
the interface around the canvas and brings it back as it was, the library only if it was open. The key works wherever the focus is:
in the review page around the canvas and in the canvas's own frame. Run in the page of the library over the canvas (v2.html)."""
import json
import os
import re
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
SHOTS = Path(os.environ.get("HYIMG_TEST_SHOTS", ""))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    yield from run_server(tmp_path)


def run_server(tmp_path, more=None, empty=False):
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    for n in range(6):
        (lib / "a" / f"{n}.png").write_bytes(png())
    if more: more(lib)
    items = {} if empty else {f"i{n}": {"path": f"a/{n}.png", "x": n * 340, "y": 0, "w": 320, "ar": 2 / 3, "crop": None} for n in range(6)}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "ru" if os.environ.get("HYIMG_TEST_RU") else "en"}))
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


def open_app(p, port, view="panel"):
    try:
        browser = p.chromium.launch()
    except Exception as error:
        pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/?view={view}"
    page.goto(url)
    page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.lod', '0'); }")
    page.goto(url)
    page.wait_for_function("() => document.body.classList.contains('cv-on') && !document.documentElement.classList.contains('lib-wait')", timeout=20000)
    frame = next(f for f in page.frames if f.url.endswith("embed=1") or "embed=1" in f.url)
    frame.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 6", timeout=20000)
    page.wait_for_timeout(1200)   # the entrance
    return browser, page, frame, errors


STATE = """() => { const b = document.body, r = document.documentElement;
  return { lib: b.classList.contains('cv-on') && !b.classList.contains('cv-only'), hid: r.classList.contains('hy-hideui'), btn: document.getElementById('tlibR').getAttribute('aria-pressed'), view: localStorage.getItem('view') }; }"""
CV = """() => { const op = id => { const e = document.querySelector(id); return e ? getComputedStyle(e).opacity : null; };
  return { hid: document.documentElement.classList.contains('hy-hideui'), crumb: op('#crumb'), dock: op('#dock'), bset: op('#bset'), cam: [cam.x, cam.y, cam.z] }; }"""


def settle(page, ms=900):
    page.wait_for_timeout(ms)


@pytest.mark.parametrize("focus", ["page", "canvas"])
def test_cmd_m_toggles_the_library(server, focus):
    with playwright.sync_playwright() as p:
        browser, page, frame, errors = open_app(p, server)
        assert page.evaluate(STATE)["lib"] is True
        if focus == "canvas":
            frame.evaluate("() => { document.body.tabIndex = -1; document.body.focus(); }"); page.locator("#cvFrame").click(position={"x": 900, "y": 600})
        page.keyboard.press("Meta+m"); settle(page)
        assert page.evaluate(STATE)["lib"] is False
        page.keyboard.press("Meta+m"); settle(page)
        s = page.evaluate(STATE); assert s["lib"] is True and s["btn"] == "true", s
        page.keyboard.press("Control+m"); settle(page)   # Ctrl too, as the old key
        assert page.evaluate(STATE)["lib"] is False
        page.keyboard.press("Meta+.")                    # the old key hides the interface now, not the library
        settle(page); assert page.evaluate(STATE)["hid"] is True
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("focus", ["page", "canvas"])
@pytest.mark.parametrize("lib_open", [True, False])
def test_cmd_dot_hides_all_the_interface_and_brings_it_back(server, focus, lib_open):
    with playwright.sync_playwright() as p:
        browser, page, frame, errors = open_app(p, server, "panel" if lib_open else "canvas")
        before = page.evaluate(STATE); assert before["lib"] is lib_open
        c0 = frame.evaluate(CV)
        assert c0["crumb"] == "1" and c0["dock"] == "1" and c0["bset"] == "1" and not c0["hid"]
        if focus == "canvas":
            page.locator("#cvFrame").click(position={"x": 900, "y": 700})
        page.keyboard.press("Meta+."); settle(page)
        s = page.evaluate(STATE); c = frame.evaluate(CV)
        assert s["hid"] and c["hid"] and s["lib"] is False, (s, c)
        assert c["crumb"] == "0" and c["dock"] == "0" and c["bset"] == "0" and c["cam"] == c0["cam"], c   # the camera does not move
        assert page.evaluate("() => getComputedStyle(document.querySelector('#tlibR')).opacity") == "0"
        # the one-time toast says how to bring it back, and it stays
        assert "Interface hidden · ⌘. to show" in page.inner_text("#hyToasts")   # the canvas sends its notes up to the page
        if SHOTS.name:
            page.screenshot(path=str(SHOTS / f"ui-hidden-{'lib-was-open' if lib_open else 'lib-was-closed'}-{focus}.png"))
        page.keyboard.press("Meta+."); settle(page, 1200)
        s = page.evaluate(STATE); c = frame.evaluate(CV)
        assert not s["hid"] and not c["hid"] and s["lib"] is lib_open, (s, c)   # the library returns only if it was open
        assert c["crumb"] == "1" and c["dock"] == "1" and c["bset"] == "1" and c["cam"] == c0["cam"], c
        assert page.evaluate("() => getComputedStyle(document.querySelector('#tlibR')).opacity") == "1"
        # the toast is said once: hiding again says nothing new
        page.evaluate("() => { document.querySelectorAll('#hyToasts .ht').forEach(e => e.remove()); }")
        page.keyboard.press("Meta+."); settle(page, 500)
        assert "Interface hidden" not in page.inner_text("#hyToasts")
        page.keyboard.press("Meta+."); settle(page, 800)
        assert not errors, errors
        browser.close()


def test_cmd_m_while_the_interface_is_hidden_brings_it_back_with_the_library(server):
    with playwright.sync_playwright() as p:
        browser, page, frame, errors = open_app(p, server, "canvas")
        page.keyboard.press("Meta+."); settle(page)
        assert page.evaluate(STATE)["hid"] is True
        page.keyboard.press("Meta+m"); settle(page, 1200)
        s = page.evaluate(STATE); assert not s["hid"] and s["lib"] is True and not frame.evaluate(CV)["hid"], s
        assert not errors, errors
        browser.close()


def test_the_apps_view_menu_calls_reach_the_page(server):
    """native: View › Media Library and Hide Interface run window.hyimgMenu on the board's page"""
    with playwright.sync_playwright() as p:
        browser, page, frame, errors = open_app(p, server, "panel")
        page.evaluate("() => hyimgMenu('hideui')"); settle(page)
        assert page.evaluate(STATE)["hid"] is True and frame.evaluate(CV)["hid"]
        page.evaluate("() => hyimgMenu('hideui')"); settle(page, 1200)
        assert page.evaluate(STATE)["lib"] is True
        page.evaluate("() => hyimgMenu('library')"); settle(page)
        assert page.evaluate(STATE)["lib"] is False
        assert not errors, errors
        browser.close()


def test_the_keys_help_and_the_app_menu_name_them(server):
    with playwright.sync_playwright() as p:
        browser, page, frame, errors = open_app(p, server, "canvas")
        text = frame.inner_text("#keys")
        assert re.search(r"⌘\s*M\s*the media library", text) and re.search(r"⌘\s*\.\s*hide all the interface", text), text
        assert "Library · ⌘M" == page.get_attribute("#tlibR", "title")
        browser.close()
    main = (ROOT / "native/main.swift").read_text()
    assert 'item(L("Minimize"), #selector(NSWindow.miniaturize(_:)), "")' in main            # ⌘M is free for the page
    assert 'item(L("Media Library"), #selector(menuLibrary), "m")' in main and 'item(L("Hide Interface"), #selector(menuHideUI), ".")' in main
    ru = (ROOT / "native/ProjectRegistry.swift").read_text()
    assert '"Media Library": "' in ru and '"Hide Interface": "' in ru


def test_library_view_and_size_sit_in_the_path_bar_when_there_is_room(server):
    """(owner 2026-10-06: «if there is room, why do you hide these settings in a panel»): a wide library shows the view switch and the
    size slider right in its path bar, a narrow one keeps them behind the button"""
    with playwright.sync_playwright() as p:
        browser, page, frame, errors = open_app(p, server, "panel")
        state = "() => ({ inl: document.getElementById('lview').classList.contains('inl'), btn: getComputedStyle(document.getElementById('lviewBtn')).display, inBar: !!document.querySelector('#fbar #lview') })"
        page.evaluate("() => document.documentElement.style.setProperty('--lw', '480px')"); page.wait_for_timeout(200)   # round 15: the bar's buttons moved up
        assert page.evaluate(state) == {"inl": False, "btn": "grid", "inBar": False}
        page.evaluate("() => document.documentElement.style.setProperty('--lw', '1000px')")
        page.wait_for_function("() => document.getElementById('lview').classList.contains('inl')")
        assert page.evaluate(state) == {"inl": True, "btn": "none", "inBar": True}
        # it works there: the size slider resizes the cards
        page.locator("#fbar #lsize").fill("200")
        page.wait_for_function("() => document.body.style.getPropertyValue('--ls') === '200px'")
        # the bar is rebuilt (another folder): it stays in it
        page.evaluate("() => renderFolders()")
        assert page.evaluate(state)["inBar"]
        page.evaluate("() => document.documentElement.style.setProperty('--lw', '480px')")
        page.wait_for_function("() => !document.getElementById('lview').classList.contains('inl')")
        assert page.evaluate(state) == {"inl": False, "btn": "grid", "inBar": False}
        assert not errors, errors
        browser.close()



def test_folders_sort_by_name(tmp_path):
    """(owner 2026-10-06: «A–Z by default, no other orders»): the library's folders are in name order, numbers counted as numbers;
    by the batch's start date (before) the order looked random. c/ is the newest batch, 10/ sorts after 2/."""
    day, now = 86400, time.time()
    def more(lib):
        for rel, age in [("c/1.png", 0), ("b/1.png", 3), ("10/1.png", 1), ("2/1.png", 2)]:
            f = lib / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(png(50 + 10 * age, 60))   # distinct: equal pictures count once
            os.utime(f, (now - age * day, now - age * day))
    gen = run_server(tmp_path, more); port = next(gen)
    try:
        with playwright.sync_playwright() as p:
            browser, page, frame, errors = open_app(p, port, "panel")
            page.evaluate("() => { DRAWER = true; renderFolders(); }")
            page.wait_for_selector(".ftree .frow[data-f='b']")
            order = "() => [...document.querySelectorAll('.ftree .frow[data-f]')].map(r => r.dataset.f).filter(f => f && !f.includes('/'))"
            assert page.evaluate(order) == ["2", "10", "a", "b", "c"]
            assert page.locator(".fsort").count() == 0   # no switch
            assert not errors, errors
            browser.close()
    finally:
        gen.close()


def test_library_keeps_the_picture_in_view_when_its_width_changes(tmp_path):
    """(owner 2026-10-06: «I make it wider or narrower and the picture at the top flies away; Apple's gallery keeps you where you
    look»): the card at the top left of the view stays at the same height on screen when the library gets wider or narrower"""
    def more(lib):
        (lib / "many").mkdir()
        for n in range(160):
            (lib / "many" / f"{n:03}.png").write_bytes(png(40 + n, 60))   # distinct: equal pictures count once
    gen = run_server(tmp_path, more); port = next(gen)
    try:
        with playwright.sync_playwright() as p:
            browser, page, frame, errors = open_app(p, port, "panel")
            page.wait_for_function("() => document.querySelectorAll('#list .card[data-i]').length > 100")
            page.evaluate("() => document.documentElement.style.setProperty('--lw', '560px')"); page.wait_for_timeout(400)
            box = page.locator("main").bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            for _ in range(12): page.mouse.wheel(0, 220); page.wait_for_timeout(40)
            page.wait_for_timeout(300)
            a = page.evaluate("() => hyLibAnchor.anchor")
            assert a and a["path"], a
            where = "p => { const k = view.findIndex(i => i.path === p), c = document.querySelector(`#list .card[data-i='${k}']`); return c.getBoundingClientRect().top - document.querySelector('main').getBoundingClientRect().top; }"
            y0 = page.evaluate(where, a["path"])
            for lw in ("900px", "420px", "700px"):
                page.evaluate("w => document.documentElement.style.setProperty('--lw', w)", lw); page.wait_for_timeout(700)
                assert abs(page.evaluate(where, a["path"]) - y0) <= 2, (lw, y0, page.evaluate(where, a["path"]))
            assert not errors, errors
            browser.close()
    finally:
        gen.close()


def test_dragging_the_library_past_its_widest_makes_it_full_width(server):
    """(owner 2026-10-06: «if I drag the library to the maximum I go into full width»): the grip dragged past the widest normal width
    snaps the library to full width, dragged back in the same move it is normal again; let go there, full width is remembered"""
    with playwright.sync_playwright() as p:
        browser, page, frame, errors = open_app(p, server, "panel")
        page.evaluate("() => document.documentElement.style.setProperty('--lw', '560px')"); page.wait_for_timeout(300)
        g = page.locator("#lgrip").bounding_box(); x, y = g["x"] + g["width"] / 2, g["y"] + 200
        W = page.evaluate("() => innerWidth")
        wide = "() => document.body.classList.contains('lwide')"
        page.mouse.move(x, y); page.mouse.down()
        page.mouse.move(W - 140, y, steps=6); assert not page.evaluate(wide)   # still a normal width
        page.mouse.move(W - 20, y, steps=6); assert page.evaluate(wide)   # past the widest: full width
        page.mouse.move(W - 300, y, steps=6); assert not page.evaluate(wide)   # back in the same drag
        page.mouse.move(W - 10, y, steps=6); page.mouse.up()
        assert page.evaluate(wide) and page.evaluate("() => localStorage.getItem('lwide') || (window.pref && pref('lwide', ''))") in ("1", '"1"')
        assert page.evaluate("() => document.getElementById('lwide').getAttribute('aria-pressed')") == "true"
        assert not errors, errors
        browser.close()


def test_folder_arrows_walk_the_tree_and_show_the_folder(tmp_path):
    """(owner 2026-10-06: «switching with the arrows I see no highlight of the folders on the left; why is there no All on the left of
    the path»): ↑ ↓ go through the folders in the tree's order, the chosen one is highlighted on the left with its parents open, a
    folder the filters leave empty is skipped, and the path starts with All folders, one click back up"""
    def more(lib):
        for n, rel in enumerate(["b/k1.png", "c/x/k2.png", "c/y/z3.png"]):
            f = lib / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(png(70 + 10 * n, 60))   # distinct: equal pictures count once
    gen = run_server(tmp_path, more); port = next(gen)
    try:
        with playwright.sync_playwright() as p:
            browser, page, frame, errors = open_app(p, port, "panel")
            page.evaluate("() => { DRAWER = true; renderFolders(); }")
            page.wait_for_selector(".ftree .frow[data-f='b']")
            state = "() => ({ c: document.getElementById('coll').value, on: [...document.querySelectorAll('#fnav .frow.on')].map(r => r.dataset.f) })"
            seen = []
            step = lambda d: page.evaluate("d => stepCollection(d)", d)   # round 15 draws no ↑ ↓ buttons beside the board (ui/libpanel.css)
            for _ in range(5):
                step(1); seen.append(page.evaluate(state))
            assert [s["c"] for s in seen] == ["a", "b", "c/x", "c/y", "c/y"], seen   # A–Z, a parent's subfolders after it, stops at the end
            assert all(s["on"] == [s["c"]] for s in seen), seen   # highlighted on the left, its parents opened
            page.fill("#q", "k"); page.wait_for_timeout(300)
            step(-1); assert page.evaluate(state)["c"] == "c/x"
            step(1); assert page.evaluate(state)["c"] == "c/x"   # c/y has nothing with «k»: skipped
            page.fill("#q", "")
            crumbs = page.locator("#fbar .fcr")
            assert crumbs.first.inner_text() == "All folders" and crumbs.count() == 3, crumbs.all_inner_texts()
            crumbs.first.click(); assert page.evaluate(state)["c"] == ""
            assert not errors, errors
            browser.close()
    finally:
        gen.close()



def test_an_empty_board_opens_its_library_once_loaded(tmp_path):
    """(owner 2026-10-06: «when first opening an empty board, open the media library after the page is loaded, once its button is
    no longer disabled»); a board with pictures keeps the library closed"""
    for empty in (True, False):
        gen = run_server(tmp_path / ("e" if empty else "f"), empty=empty); port = next(gen)
        try:
            with playwright.sync_playwright() as p:
                browser = p.chromium.launch(); page = browser.new_page(viewport={"width": 1400, "height": 900})
                errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
                url = f"http://127.0.0.1:{port}/?view=canvas"; page.goto(url)
                page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.lod', '0'); }"); page.goto(url)
                frame = None
                for _ in range(100):
                    frame = next((f for f in page.frames if "embed=1" in f.url), None)
                    if frame: break
                    page.wait_for_timeout(100)
                frame.wait_for_function("() => typeof BOARD !== 'undefined' && typeof board !== 'undefined'", timeout=20000)
                lib = "() => document.body.classList.contains('cv-on') && !document.body.classList.contains('cv-only')"
                if empty: page.wait_for_function(lib, timeout=15000)
                else: page.wait_for_timeout(3000); assert not page.evaluate(lib)
                assert not errors, errors
                browser.close()
        finally:
            gen.close()
