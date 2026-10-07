"""What does not apply stays in the menu, grey, with its reason (owner 2026-10-06: «if some options are not available in the right-click
menu, they must simply be grey — I want users to know what functions exist»).

- the board's right-click menu has one fixed list for any selection (a picture, a PDF, a note, a group): the items that do not apply keep
  their place, grey (aria-disabled), their reason in the tooltip; a click on one does nothing, the arrow keys pass over them
- the plugins' items follow (the frames plugin: open, unframe, make frame, frame each, the mask's two)
- «Copy properties ›» and the «Custom…» window list every registered kind, what the object has not grey with why; «Paste properties ›»
  every kind, «Not in the clipboard» grey; an empty clipboard and no presets: the item itself is grey, «The clipboard is empty»
- a page's own menu keeps «Delete page» grey on the only page; the library's card menu keeps «Show on board» grey for a frame on no board
Runs in Chromium and WebKit where Playwright has them, on temporary libraries only (the frames plugin from its repository's last commit)."""
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
from test_move_to_page import frames_plugin, screen
from test_pdf import make_pdf, COLORS

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
ENGINES = ["chromium", "webkit"]


def board():
    items = {
        "p": {"path": "a/0.png", "x": 0, "y": 0, "w": 300, "ar": 2 / 3, "crop": None},
        "d": {"path": "a/doc.pdf", "x": 400, "y": 0, "w": 300, "ar": 0.75, "crop": None},
        "n": {"type": "note", "text": "a note", "x": 800, "y": 0, "w": 300, "fs": 18, "color": "yellow"},
        "g1": {"path": "a/1.png", "x": 100, "y": 1000, "w": 300, "ar": 2 / 3, "crop": None},
    }
    groups = {"G": {"title": "Group one", "x": 0, "y": 800, "w": 600, "h": 800, "members": ["g1"]}}
    return {"schema": 1, "revision": 1, "items": items, "groups": groups, "removed": {}}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True); plugins.mkdir()
    for n in range(3):
        (lib / "a" / f"{n}.png").write_bytes(png(40 + n, 60))   # three different files: the library folds byte-identical copies into one
    (lib / "a/doc.pdf").write_bytes(make_pdf(COLORS))
    frames = frames_plugin(plugins / "frames")
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HYIMG_PLUGINS=str(plugins), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield {"port": port, "frames": frames}
    finally:
        proc.terminate(); proc.wait(5); log.close()


def open_board(p, engine, port, frames=False):
    try: browser = getattr(p, engine).launch()
    except Exception as error: pytest.skip(f"no {engine} for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url)
    page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }")
    page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && board.items.p && EL.get('p') && byPath.size >= 4", timeout=20000)
    page.wait_for_function("() => pdfPages('a/doc.pdf') >= 2", timeout=15000)
    if frames: page.wait_for_function("() => PLGST.some(x => x.name === 'frames' && x.ok) && HY.props.list().some(d => d.id === 'mask')", timeout=15000)
    errors.clear()   # WebKit reports the first load's requests, cancelled by the reload, as errors
    page.evaluate("() => { cam.x = -100; cam.y = -100; cam.z = .45; renderCam(); render(); }")
    page.wait_for_timeout(300)
    return browser, page, errors


# [label, reason or ""] of each item of a panel, in order; separators as "—"
# «Open in <App>» is named by macOS as soon as the server has asked: one name here
ROWS = """sel => [...document.querySelector(sel).children].filter(e => e.matches('[role=menuitem], .sep')).map(e => e.classList.contains('sep') ? '—'
  : [(e.querySelector('.ml') || e).textContent.trim().replace(/^Open in (?!default app).+$/, 'Open in default app'), e.getAttribute('aria-disabled') === 'true' ? e.title : ''])"""


def menu(page, at):
    page.mouse.click(at[0], at[1], button="right")
    page.wait_for_selector("#ctx.open [data-act=view]")
    return page.evaluate(ROWS, "#ctx")


def on(page, id, dy=40):
    it = page.evaluate(f"() => board.items['{id}'] || board.groups['{id}']")
    return screen(page, it["x"] + 40, it["y"] + dy)


def rows(page):
    return {r[0]: r[1] for r in page.evaluate(ROWS, "#ctx") if r != "—"}


@pytest.mark.parametrize("engine", ENGINES)
def test_one_list_grey_with_reasons(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"], server["frames"])
        fr = server["frames"]
        pic = menu(page, on(page, "p"))
        labels = [r if r == "—" else r[0] for r in pic]
        plugin = ["Open frame editor", "Unframe", "Make frame", "Frame each", "Mask from alpha", "Clear mask", "—"] if fr else []
        assert labels == ["Open in default app", "—", "Cut", "Copy", "Paste", "Duplicate", "—", *plugin, "Group", "Ungroup", "Move to page", "Order", "—", "Copy properties", "Paste properties", "—",
                          "Copy link to the frame", "Split into pages", "Copy image", "Copy file path", "Show in Finder", "—", "Copy link to this view", "—", "Remove from the board"], labels
        r = rows(page)
        assert r["Group"] == "" and r["Ungroup"] == "No group selected" and r["Split into pages"] == "Only for a PDF" and r["Copy image"] == ""
        assert r["Paste properties"] == "The clipboard is empty" and r["Copy properties"] == ""
        if fr:
            assert r["Open frame editor"] == "Only for a frame" and r["Unframe"] == "Only for a frame" and r["Make frame"] == ""
            assert r["Frame each"] == "Only for 2 images or more" and r["Mask from alpha"] == "" and r["Clear mask"] == "No mask here"
        # a click on a grey item does nothing and the menu stays; the arrow keys pass over the grey ones
        page.locator("#ctx [data-act=ungroup]").click(force=True)
        assert page.evaluate("() => $('#ctx').classList.contains('open') && Object.keys(board.groups).length === 1")
        page.evaluate("() => document.querySelector('#ctx [data-act=group]').focus()")
        page.keyboard.press("ArrowDown")
        assert page.evaluate("() => document.activeElement.dataset.sub") == "topage"   # Ungroup is skipped
        page.keyboard.press("Escape")
        # the same places for a PDF, a note and a group, other items grey
        page.keyboard.press("Escape")
        menu(page, on(page, "d")); r = rows(page)
        assert r.get("Split into pages (3)") == "" and r["Ungroup"] == "No group selected", json.dumps(r)
        page.keyboard.press("Escape")
        nt = menu(page, on(page, "n")); r = rows(page)
        assert [x if x == "—" else x[0] for x in nt][:1] == ["Open in default app"] and len(nt) == len(pic) and "Copy link to the note" in r
        assert r["Open in default app"] == "Only for a file" and r["Copy image"] == "Only for a file" and r["Show in Finder"] == "No file in the selection"
        assert r["Split into pages"] == "Only for a PDF"
        if fr: assert r["Make frame"] == "Only images go into a frame" and r["Mask from alpha"] == "A mask only on images and frames"
        page.keyboard.press("Escape")
        gr = menu(page, on(page, "G", dy=-10)); r = rows(page)
        assert "Copy link to the group" in r and len(gr) == len(pic)
        assert r["Group"] == "Groups are not grouped: select the objects" and r["Ungroup"] == "" and r["Open in default app"] == "Only for a file"
        page.keyboard.press("Escape")
        # the empty board: only its own
        assert [x if x == "—" else x[0] for x in menu(page, [1300, 900])] == ["Paste here", "—", "Copy link to this view"]
        assert not errors, errors
        browser.close()


SUB = """() => [...document.querySelectorAll('#ctx .hy-sub > [role=menuitem]')].map(b => [(b.querySelector('.ml') || b).textContent.trim(),
  b.getAttribute('aria-disabled') === 'true' ? b.title : ''])"""


@pytest.mark.parametrize("engine", ENGINES)
def test_properties_list_every_kind(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"], server["frames"])
        fr = server["frames"]
        menu(page, on(page, "p"))
        page.locator("#ctx [data-sub=props-copy]").hover()
        page.wait_for_function("() => document.querySelectorAll('#ctx .hy-sub [role=menuitem]').length > 3")
        got = page.evaluate(SUB)
        kinds = ([["Raw Editor", "Raw Editor isn't applied"], ["Mask", "This picture has no mask"]] if fr else []) + [
            ["Crop", "This picture isn't cropped"], ["Time", "Time only on videos"], ["Size", ""], ["Opacity", "This object is fully opaque"],
            ["PDF page", "A page only on a PDF that is not split"]]
        assert got == [["Custom…", ""], *kinds, ["Save as preset…", ""]], got
        # the size, the one it has: copied; then the paste submenu lists every kind, the others «Not in the clipboard»
        page.locator("#ctx .hy-sub [role=menuitem]", has_text="Size").click()
        menu(page, on(page, "n"))
        assert rows(page)["Paste properties"] == ""
        page.locator("#ctx [data-sub=props-paste]").hover()
        page.wait_for_function("() => document.querySelectorAll('#ctx .hy-sub [role=menuitem]').length > 3")
        got = dict(page.evaluate(SUB))
        assert got["Size"] == "" and got["Crop"] == "Not in the clipboard" and got["Presets"].startswith("No presets yet")
        assert list(got)[:len(kinds)] == [k for k, _ in kinds]
        page.keyboard.press("Escape"); page.keyboard.press("Escape")
        # the Custom… window: every kind, what the object has not unticked and disabled, its reason on the row
        page.evaluate("() => { sel = new Set(['p']); render(); }")
        page.keyboard.press("Control+Alt+Shift+KeyC"); page.wait_for_selector("#propsDlg")
        box = page.evaluate("() => [...document.querySelectorAll('#propsDlg label')].map(l => [l.textContent.trim(), l.querySelector('input').disabled, l.querySelector('input').checked, l.title])")
        assert [b[0] for b in box] == [k for k, _ in kinds]
        assert all(b[1] == (b[3] != "") and (b[2] or b[1]) for b in box) and [b for b in box if not b[1]] == [["Size", False, True, ""]], box
        page.keyboard.press("Escape")
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_page_and_library_menus_grey(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"], server["frames"])
        page.locator("#cPage").click()
        page.locator("#pages .row").first.click(button="right")
        page.wait_for_selector("#ctx.open [data-act=del]")
        assert page.evaluate("() => document.querySelector('#ctx [data-act=del]').title") == "This is the only page, it can't be deleted"
        page.locator("#ctx [data-act=del]").click(force=True)
        assert page.evaluate("() => pages.length") == 1
        page.keyboard.press("Escape")
        # the library: a frame on no board keeps «Show on board», grey
        lib = browser.new_page(viewport={"width": 1400, "height": 900})
        lib.goto(f"http://127.0.0.1:{server['port']}/?view=lib")
        lib.wait_for_function("() => [...document.querySelectorAll('#list .card')].some(c => (view[+c.dataset.i] || {}).path === 'a/2.png')", timeout=20000)
        free = lib.evaluate("() => [...document.querySelectorAll('#list .card')].findIndex(c => (view[+c.dataset.i] || {}).path === 'a/2.png')")
        lib.locator("#list .card").nth(free).click(button="right")
        lib.wait_for_selector("#lctx.open [data-a=show]")
        assert lib.evaluate("() => { const b = document.querySelector('#lctx [data-a=show]'); return [b.textContent.trim(), b.getAttribute('aria-disabled'), b.title]; }") == [
            "Show on board", "true", "This frame is on no board"]
        assert not errors, errors
        browser.close()
