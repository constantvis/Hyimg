"""Open ▾ and the right click, round 20 question 13 B (owner 2026-10-11 on open-b.html: «да вот так лучше»; panels audit P-12, board
audit B-14 and B-18). One main row: the Info card's Open ▾, the right click and ↵ start with the same row, the one the Studio chip names
(«Image Studio ↵», «3D Studio ↵», «Dev Studio ↵»), a video's «View ↵»; Crop ⇧C second; Hyimg's viewer is «View» and the Mac's apps are one
«Open with ›», the default first, each opening the file with `open -a`; Open's tooltip is its main row's («View · ↵», a video's said
«Open the frame to view and rate it»). The key caps stay (2026-10-04). The empty board's right click makes what «+» makes, at the click.
Each test failed on the code before: the right click started with «Open in <app>», had no Studio and no Crop, the empty board could only
paste. Chromium, dark theme, a temporary library, the plugins from their repositories' last commits (test_info_header.py's world)."""
import json
import time

import pytest

from test_info_header import FFMPEG, open_board, until, world

playwright = pytest.importorskip("playwright.sync_api")

APPS = [{"name": "Test Viewer", "path": "/Applications/Test Viewer.app", "default": True}, {"name": "Another Editor", "path": "/Applications/Another Editor.app"}]
# the right click's rows: [words, keys] or "—"
CTX = """() => [...document.querySelectorAll('#ctx > button, #ctx > .sep')].map(b => b.classList.contains('sep') ? '—'
  : [(b.querySelector('.ml') || b).textContent.trim(), [...b.querySelectorAll('.mk kbd')].map(k => k.textContent).join('')])"""
SUB = "() => [...document.querySelectorAll('.hy-sub [data-openwith]')].map(b => b.textContent.trim())"


def right(page, at):
    if isinstance(at, str):
        at = page.evaluate("id => { const r = EL.get(id).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", at)
    page.keyboard.press("Escape"); page.mouse.click(*at, button="right"); page.wait_for_selector("#ctx.open [role=menuitem]")
    return page.evaluate(CTX)


def recorder(tmp):   # `open` as the server runs it: its arguments, a line a call
    rec, opener = tmp / "opened.txt", tmp / "open"
    opener.write_text(f'#!/bin/sh\nfor a in "$@"; do printf "%s\\t" "$a" >> "{rec}"; done\necho >> "{rec}"\n'); opener.chmod(0o755)
    return rec, opener


def opened(rec, before):
    for _ in range(80):
        now = rec.read_text() if rec.exists() else ""
        if now != before: return now[len(before):].strip().split("\t")
        time.sleep(0.1)
    return []


def test_one_main_row_in_open_the_right_click_and_the_chip(tmp_path):
    rec, opener = recorder(tmp_path)
    with world(tmp_path, HYIMG_OPEN_APPS=json.dumps(APPS), HYIMG_REVEAL_CMD=str(opener)) as (port, lib), playwright.sync_playwright() as p:
        browser, page = open_board(p, port)
        page.evaluate("() => { window.ENT = []; MODES.enter = (k, ids) => { ENT.push(k + ':' + ids.join()); return true; }; }")   # the Studio stays shut
        # a picture: Open's tooltip and the right click's first rows are its Studio's, as the chip over it
        page.evaluate("() => { sel = new Set(['p']); render(); }"); until(page, "() => $('#iOpen').querySelector('.oi-more')")
        assert page.evaluate("() => $('#iOpen').title") == "Image Studio · ↵"
        assert page.evaluate("() => document.querySelector('#handles .tidy [data-studiochip]').textContent.trim()") == "Image Studio↵"
        rows = right(page, "p")
        assert rows[:4] == [["Image Studio", "↵"], ["Crop", "⇧C"], ["Open with", ""], "—"], rows
        assert page.locator("#ctx > [data-act=main] .oi-dot").count() == 1, "the Studio's dot where the icon stands"
        page.click("#ctx > [data-act=main]"); until(page, "() => ENT.join() === 'image:p'")
        right(page, "p"); page.click("#ctx > [data-act=crop]"); until(page, "() => cropState && cropState.id === 'p'")
        page.keyboard.press("Escape"); until(page, "() => !cropState")
        # «Open with ›»: the file's apps, the default first, then Other…; a row opens the file in that app
        right(page, "p"); page.locator("#ctx [data-sub=openwith]").hover(); until(page, "() => document.querySelectorAll('#ctx .hy-sub [data-openwith]').length === 3")
        assert page.evaluate(SUB) == ["Test Viewer default", "Another Editor", "Other…"]
        before = rec.read_text() if rec.exists() else ""
        page.click("#ctx .hy-sub [data-openwith='1']"); got = opened(rec, before)
        assert got[:2] == ["-a", "/Applications/Another Editor.app"] and got[2].endswith("a/form.png"), got
        assert page.evaluate("() => !$('#ctx').classList.contains('open')")
        # the same «Open with ›» in Open ▾, after View
        page.evaluate("() => { sel = new Set(['p']); render(); }"); page.click("#iOpen .oi-more"); page.wait_for_selector(".hy-oi-menu")
        assert page.evaluate("() => [...document.querySelectorAll('.hy-oi-menu > [role=menuitem]')].map(b => b.innerText.trim().split('\\n')[0]).slice(0, 3)") == [
            "Image Studio", "View", "Open with"]
        page.locator(".hy-oi-menu [data-sub]").hover(); until(page, "() => document.querySelectorAll('.hy-oi-menu .hy-sub [data-openwith]').length === 3")
        before = rec.read_text(); page.click(".hy-oi-menu .hy-sub [data-openwith='0']"); got = opened(rec, before)
        assert got[:2] == ["-a", "/Applications/Test Viewer.app"] and got[2].endswith("a/form.png"), got
        until(page, "() => !document.querySelector('.hy-oi-menu')")
        # a 3D scene and an HTML page: their Studio first, nothing to crop
        assert right(page, "s")[:2] == [["3D Studio", "↵"], "—"]
        assert right(page, "h")[:2] == [["Dev Studio", "↵"], "—"]
        # a copy goes to its original first, as its Open does
        assert right(page, "c")[:3] == [["To the original", "↵"], ["Crop", "⇧C"], ["Open with", ""]]
        if FFMPEG:   # a video has no Studio: View ↵, its Open says so (it said «Open the frame to view and rate it»)
            page.keyboard.press("Escape"); page.evaluate("() => { sel = new Set(['v']); render(); }"); until(page, "() => $('#iOpen').title === 'View · ↵'")
            assert right(page, "v")[:3] == [["View", "↵"], ["Crop & Trim", "⇧C"], ["Open with", ""]]
        assert not page.errors, page.errors
        browser.close()


def test_the_empty_boards_right_click_makes_things_at_the_click(tmp_path):
    with world(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        browser, page = open_board(p, port)
        page.evaluate("() => { sel = new Set(); render(); }")
        at = [1000, 700]
        assert page.evaluate("p => document.elementFromPoint(...p) === stage", at), "an empty place"
        rows = right(page, at)
        assert rows[:3] == [["Sticky note", "N"], ["Text", "T"], ["Timeline", "L"]], rows
        plus = page.evaluate("() => hyBoardDock.list().map(x => [x.label, (x.keys || []).join('')])")   # and what the plugins add to «+»
        assert rows[:len(plus) + 1] == [*plus, "—"], (rows, plus)
        w = page.evaluate("p => toWorld(...p)", at)
        n0 = set(page.evaluate("() => Object.keys(board.items)"))
        page.click("#ctx > [data-act='mk:note']"); until(page, "n => Object.keys(board.items).length > n", len(n0))
        nid = (set(page.evaluate("() => Object.keys(board.items)")) - n0).pop()
        it = page.evaluate("id => board.items[id]", nid)
        assert it["type"] == "note" and abs(it["x"] + it["w"] / 2 - w["x"]) <= 2 and abs(it["y"] + it["w"] / 2 - w["y"]) <= 2, (it, w)
        page.keyboard.press("Escape"); page.keyboard.press("Escape"); page.evaluate("() => { sel = new Set(); render(); document.activeElement.blur(); }")
        at = [1000, 300]; right(page, at); w = page.evaluate("p => toWorld(...p)", at)
        n0 = set(page.evaluate("() => Object.keys(board.items)"))
        page.click("#ctx > [data-act='mk:text']"); until(page, "n => Object.keys(board.items).length > n", len(n0))
        it = page.evaluate("id => board.items[id]", (set(page.evaluate("() => Object.keys(board.items)")) - n0).pop())
        assert it["type"] == "text" and abs(it["x"] - w["x"]) <= 2, (it, w)
        assert not page.errors, page.errors
        browser.close()
