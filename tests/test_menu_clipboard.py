"""Cut, copy, paste, duplicate and delete on the board's right click, as in Figma (owner 2026-10-07: «по правой кнопке отсутствует удаление
или вырезать/вставить»): the board's own ⌘X ⌘C ⌘V ⌘D ⌫, the same functions, the same keys shown.

- a card's menu: Cut ⌘X, Copy ⌘C, Paste ⌘V, Duplicate ⌘D after «Open…», «Remove from the board» ⌫ last and red; the empty board: «Paste here»
- an empty clipboard greys Paste («The clipboard is empty»); a group alone greys Duplicate with why
- each is one undo step; a paste from the menu lands where the menu was opened; removing a picture from its only page marks it for the
  archive (board.removed), the file stays
Runs in Chromium and WebKit where Playwright has them, on temporary libraries only."""
import json
import urllib.request

import pytest

from test_shortcuts import run_server

playwright = pytest.importorskip("playwright.sync_api")
ENGINES = ["chromium"]   # the board's tests run in Chromium, dark (owner 2026-10-07)


@pytest.fixture
def server(tmp_path):
    yield from run_server(tmp_path)


SCREEN = "([x, y]) => { const r = stage.getBoundingClientRect(); return [(x - cam.x) * cam.z + r.left, (y - cam.y) * cam.z + r.top]; }"
WORLD = "([x, y]) => toWorld(x, y)"
ROWS = """() => [...document.querySelectorAll('#ctx > [role=menuitem]')].map(b => [(b.querySelector('.ml') || b).textContent.trim(),
  b.getAttribute('aria-disabled') === 'true' ? b.title : '', [...b.querySelectorAll('.mk kbd')].map(k => k.textContent).join(''), b.classList.contains('danger')])"""


def menu(page, at):
    page.mouse.click(at[0], at[1], button="right")
    page.wait_for_selector("#ctx.open [role=menuitem]")
    return {r[0]: r[1:] for r in page.evaluate(ROWS)}


def act(page, name):
    page.locator(f"#ctx [data-act={name}]").click()
    page.wait_for_function("() => !$('#ctx').classList.contains('open')")


@pytest.mark.parametrize("engine", ENGINES)
def test_clipboard_and_delete_on_the_menu(server, engine):
    with playwright.sync_playwright() as p:
        try: browser = getattr(p, engine).launch()
        except Exception as error: pytest.skip(f"no {engine} for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); localStorage.setItem('cv.cam.main', JSON.stringify({ x: -100, y: -100, z: .5 })); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 6 && EL.get('i0')", timeout=20000)
        errors.clear()
        on = lambda id: page.evaluate(SCREEN, page.evaluate(f"() => {{ const it = board.items['{id}']; return [it.x + 100, it.y + 300]; }}"))   # under the toasts
        n = lambda: page.evaluate("() => Object.keys(board.items).length")
        # a card's menu: the four after «Open…», the shortcuts shown, Paste grey while the clipboard is empty, «Remove from the board» last and red
        r = menu(page, on("i1"))
        assert r["Cut"] == ["", "⌘X", False] and r["Copy"] == ["", "⌘C", False] and r["Duplicate"] == ["", "⌘D", False]
        assert r["Paste"] == ["The clipboard is empty", "⌘V", False] and r["Remove from the board"] == ["", "⌫", True]
        assert list(r)[1:5] == ["Cut", "Copy", "Paste", "Duplicate"] and list(r)[-1] == "Remove from the board"
        # Duplicate: one more card, one undo step
        act(page, "dup"); assert n() == 7
        page.keyboard.press("Control+z"); assert n() == 6
        # Copy, then «Paste here» on the empty board: the copy lands centred where the menu was opened
        menu(page, on("i1")); act(page, "copy")
        spot = [1150, 700]
        r = menu(page, spot)
        assert list(r) == ["Paste here", "Hide annotations", "Annotations on this page", "Copy app link to this view", "Copy browser link to this view"]
        assert r["Paste here"][0] == ""
        at = page.evaluate(WORLD, spot)
        act(page, "paste"); assert n() == 7
        new = page.evaluate("() => [...sel].map(id => board.items[id]).filter(Boolean).map(it => [it.x + it.w / 2, it.y + itemH(it) / 2])")
        assert len(new) == 1 and abs(new[0][0] - at["x"]) < 1 and abs(new[0][1] - at["y"]) < 1, (new, at)
        page.keyboard.press("Control+z"); assert n() == 6
        # Cut: gone, on the clipboard, one step back
        menu(page, on("i2")); act(page, "cut")
        assert n() == 5 and "i2" not in page.evaluate("() => Object.keys(board.items)")
        assert page.evaluate("() => JSON.parse(localStorage.getItem('cv.clip')).items[0].path") == "a/2.png"
        page.keyboard.press("Control+z"); assert n() == 6
        # Remove from the board: off the page, marked for the archive (the file stays), one step back
        menu(page, on("i3")); act(page, "del")
        assert n() == 5 and page.evaluate("() => 'a/3.png' in board.removed")
        page.keyboard.press("Control+z"); assert n() == 6 and not page.evaluate("() => 'a/3.png' in board.removed")
        # a group alone: no Duplicate (a group is duplicated by its cards; the menu by kind, owner 2026-10-07)
        page.evaluate("() => { board.groups.G = { title: 'G', x: 1650, y: -60, w: 400, h: 800, members: ['i5'] }; sel = new Set(); render(); }")
        r = menu(page, page.evaluate(SCREEN, [1680, 650]))   # the group's empty inside, under the toasts
        assert "Duplicate" not in r and "Ungroup" in r, r
        page.keyboard.press("Escape")
        assert not errors, errors
        browser.close()
