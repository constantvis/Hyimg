# A folder's colour in the library's tree (owner 2026-10-06): the right-click menu starts with the note colours, a colour tints the
# folder and every folder under it that has none of its own, it stays with the project after a reload, «no colour» takes it off.
import json, pathlib, sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_shortcuts import png, run_server


def more(lib):
    for k, d in enumerate(("r/x", "r/y", "s")):
        (lib / d).mkdir(parents=True, exist_ok=True)
        for n in range(2):
            (lib / d / f"{n}.png").write_bytes(png(60 + k * 4 + n, 70))   # all different: equal files collapse into one place


@pytest.fixture
def server(tmp_path):
    yield from run_server(tmp_path, more=more)


def fcol(page, path):
    return page.evaluate("p => { const r = document.querySelector(`.frow[data-f=\"${p}\"]`); return r && r.classList.contains('col') ? getComputedStyle(r.querySelector('.fi')).color : ''; }", path)


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_folder_colour_from_its_menu_inherits_and_stays(server, tmp_path, engine):
    with sync_playwright() as p:
        b = getattr(p, engine).launch(); page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/?view=lib"); page.wait_for_selector("#list .card")
        if not page.locator('.frow[data-f="r"]').is_visible(): page.click("[data-ftree]")
        page.locator('.frow[data-f="r"] [data-tog]').click()   # open r: x and y show
        page.wait_for_selector('.frow[data-f="r/x"]')
        page.locator('.frow[data-f="r"]').click(button="right")
        menu = page.locator("#lctx")
        assert menu.locator(".msw button").count() == 9 and menu.locator(".msw button.none.on").count() == 1   # «no colour» + 8, none chosen
        assert menu.locator("button[data-a=reveal]").count() == 1
        menu.locator('.msw [data-color="blue"]').click()
        assert not menu.evaluate("m => m.classList.contains('open')")
        blue = fcol(page, "r"); assert blue and fcol(page, "r/x") == blue and fcol(page, "r/y") == blue and fcol(page, "s") == ""
        # a folder under it with its own colour keeps it
        page.locator('.frow[data-f="r/y"]').click(button="right"); menu.locator('.msw [data-color="pink"]').click()
        page.wait_for_timeout(300)
        pink = fcol(page, "r/y"); assert pink and pink != blue and fcol(page, "r/x") == blue
        saved = json.loads((tmp_path / "state" / "folders.json").read_text())["colors"]
        assert saved == {"r": "blue", "r/y": "pink"}
        # after a reload the colours are there, the menu marks the current one; «no colour» takes it off
        page.reload(); page.wait_for_selector("#list .card")
        if not page.locator('.frow[data-f="r"]').is_visible(): page.click("[data-ftree]")
        page.wait_for_function("() => document.querySelector('.frow[data-f=\"r\"]').classList.contains('col')")
        page.locator('.frow[data-f="r"]').click(button="right")
        assert menu.locator('.msw [data-color="blue"].on').count() == 1
        menu.locator(".msw button.none").click(); page.wait_for_timeout(300)
        assert fcol(page, "r") == ""
        assert json.loads((tmp_path / "state" / "folders.json").read_text())["colors"] == {"r/y": "pink"}
        assert not errors, errors
        b.close()
