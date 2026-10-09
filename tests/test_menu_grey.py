"""The board's right-click menu by kind (owner 2026-10-07: «show only items that relate to the KIND of thing clicked; within those,
unavailable-right-now items stay grey with their reason; items that make no sense for that kind are hidden»; it refines 2026-10-06's «if
some options are not available in the right-click menu, they must simply be grey»).

- a picture, a PDF, a note, a group and the empty board each get their own list, in one fixed order: no «Split into pages» but on a PDF, no
  file items on a note, «Ungroup» only for a group, the frame editor's items only for a frame; «Copy as ›» holds the links, the image and
  the path; what applies to the kind but not now is grey with its reason, a click on it does nothing, the arrow keys pass over it
- the plugins' items follow (the frames plugin: make frame, frame each, the mask's two for pictures)
- «Copy properties ›», «Paste properties ›» and the «Custom…» window list the kinds the object can have, what it has not grey with why
- a page's own menu keeps «Delete page» grey on the only page; the library's card menu keeps «Show on board» grey for a frame on no board
Runs in Chromium where Playwright has it, dark, on temporary libraries only (the frames plugin from its repository's last commit)."""
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
ENGINES = ["chromium"]   # the board's tests run in Chromium, dark (owner 2026-10-07)


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
    page = browser.new_page(viewport={"width": 1400, "height": 1000}, color_scheme="dark")
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
    page.wait_for_selector("#ctx.open [role=menuitem]")
    return page.evaluate(ROWS, "#ctx")


def on(page, id, dy=40):
    it = page.evaluate(f"() => board.items['{id}'] || board.groups['{id}']")
    return screen(page, it["x"] + 40, it["y"] + dy)


def rows(page):
    return {r[0]: r[1] for r in page.evaluate(ROWS, "#ctx") if r != "—"}


LABELS = lambda rows: [r if r == "—" else r[0] for r in rows]


@pytest.mark.parametrize("engine", ENGINES)
def test_each_kind_its_own_list_grey_within(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"], server["frames"])
        fr = server["frames"]
        pic = menu(page, on(page, "p"))
        plugin = ["Make frame", "Frame each", "Mask from alpha", "Clear mask", "—"] if fr else []
        assert LABELS(pic) == ["Open in default app", "—", "Cut", "Copy", "Paste", "Duplicate", "—", *plugin, "Group", "Move to page", "Order", "Arrange", "—",
                               "Copy properties", "Paste properties", "Clear properties", "—", "Copy as", "Show in Finder", "—", "Remove from the board"], LABELS(pic)
        r = rows(page)
        assert r["Paste"] == "The clipboard is empty" and r["Paste properties"] == "The clipboard is empty" and r["Clear properties"] == "Nothing to clear"
        if fr: assert r["Make frame"] == "" and r["Frame each"] == "Only for 2 images or more" and r["Mask from alpha"] == "" and r["Clear mask"] == "No mask here"
        # «Copy as ›»: the links, the image, the path
        page.locator("#ctx [data-sub=copyas]").hover()
        page.wait_for_function("() => document.querySelectorAll('#ctx .hy-sub [role=menuitem]').length === 6")
        assert [x[0] for x in page.evaluate(SUB)] == ["App link", "Browser link", "App link to this view", "Browser link to this view", "Image", "File path"]
        # a click on a grey item does nothing and the menu stays; the arrow keys pass over the grey ones
        page.mouse.move(1390, 990)
        page.locator("#ctx [data-act=paste]").click(force=True)
        assert page.evaluate("() => $('#ctx').classList.contains('open') && Object.keys(board.items).length === 4")
        page.evaluate("() => document.querySelector('#ctx [data-act=copy]').focus()")
        page.keyboard.press("ArrowDown")
        assert page.evaluate("() => document.activeElement.dataset.act") == "dup"   # Paste is skipped
        page.keyboard.press("Escape"); page.keyboard.press("Escape")
        # a PDF: its page items
        r = {x[0]: x[1] for x in menu(page, on(page, "d")) if x != "—"}
        assert r.get("Split into pages (3)") == "" and "Ungroup" not in r, json.dumps(r)
        page.keyboard.press("Escape")
        # a note: no file items, no frames, no picture kinds
        nt = menu(page, on(page, "n"))
        assert LABELS(nt) == ["Cut", "Copy", "Paste", "Duplicate", "—", "Group", "Move to page", "Order", "—", "Copy properties", "Paste properties", "—",
                              "Copy as", "—", "Remove from the board"], LABELS(nt)
        page.locator("#ctx [data-sub=copyas]").hover()
        page.wait_for_function("() => document.querySelectorAll('#ctx .hy-sub [role=menuitem]').length === 4")
        assert [x[0] for x in page.evaluate(SUB)] == ["App link", "Browser link", "App link to this view", "Browser link to this view"]
        page.keyboard.press("Escape"); page.keyboard.press("Escape")
        # a group: «Ungroup», no «Group», no «Duplicate», the properties of its pictures
        gr = menu(page, on(page, "G", dy=-10))
        assert LABELS(gr) == ["Cut", "Copy", "Paste", "—", *(["Make frame", "Frame each", "—"] if fr else []), "Ungroup", "Move to page", "Order", "Arrange", "—",
                              "Paste properties", "Clear properties", "—", "Copy as", "—", "Remove from the board"], LABELS(gr)
        page.keyboard.press("Escape")
        # the empty board: only its own
        assert LABELS(menu(page, [1300, 900])) == ["Paste here", "—", "Hide annotations", "—", "Copy app link to this view", "Copy browser link to this view"]
        assert not errors, errors
        browser.close()


SUB = """() => [...document.querySelectorAll('#ctx .hy-sub > [role=menuitem]')].map(b => [(b.querySelector('.ml') || b).textContent.trim(),
  b.getAttribute('aria-disabled') === 'true' ? b.title : ''])"""


@pytest.mark.parametrize("engine", ENGINES)
def test_properties_list_the_kinds_of_the_object(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"], server["frames"])
        fr = server["frames"]
        menu(page, on(page, "p"))
        page.locator("#ctx [data-sub=props-copy]").hover()
        page.wait_for_function("() => document.querySelectorAll('#ctx .hy-sub [role=menuitem]').length > 3")
        got = page.evaluate(SUB)
        kinds = ([["Raw Editor", "Raw Editor isn't applied"], ["Mask", "This picture has no mask"]] if fr else []) + [
            ["Crop", "This picture isn't cropped"], ["Size", ""], ["Opacity", "This object is fully opaque"]]   # no Time (videos), no PDF page
        assert got == [["Custom…", ""], *kinds, ["Save as preset…", ""]], got
        # the size, the one it has: copied; a note's paste submenu lists the kinds a note can have: the size
        page.locator("#ctx .hy-sub [role=menuitem]", has_text="Size").click()
        menu(page, on(page, "n"))
        assert rows(page)["Paste properties"] == ""
        page.locator("#ctx [data-sub=props-paste]").hover()
        page.wait_for_function("() => document.querySelectorAll('#ctx .hy-sub [role=menuitem]').length >= 2")
        got = dict(page.evaluate(SUB))
        assert list(got) == ["Size", "Presets"] and got["Size"] == "" and got["Presets"].startswith("No presets yet"), got
        page.keyboard.press("Escape"); page.keyboard.press("Escape")
        # the Custom… window: the picture's kinds, what it has not unticked and disabled, its reason on the row
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
