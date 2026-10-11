"""A bar over a selection does not move while the pointer is over it (board audit 2026-10-11, B-10; ui/bars.js). Before, a click on H1
moved the text's bar by the new width of the text (509 px on «Moodboard»), A− clicked twice in one place landed the second click on the
board and lost the selection, and «Area» lifted a note's bar 224 px over its new zone. Once the pointer leaves, the bar is placed again.
Chromium, dark theme, our own server (tests/test_p4_board.py's harness), the mouse for every click."""
import pytest

from test_p4_board import box, board_page, browser_of, serve

playwright = pytest.importorskip("playwright.sync_api")

BAR = "s => { const r = document.querySelector(s).getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)]; }"


def run(tmp_path, fn):
    with serve(tmp_path, {}) as (port, lib), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port)
        try: fn(page, page.evaluate)
        finally: browser.close()
        assert not errors, errors


def under(page, x, y, sel):   # what the pointer is over now is that button
    return page.evaluate("([x, y, s]) => { const e = document.elementFromPoint(x, y); return !!(e && e.closest(s)); }", [x, y, sel])


def test_the_text_bar_stays_under_the_pointer_through_clicks(tmp_path):
    def go(page, ev):
        page.mouse.dblclick(500, 600); page.wait_for_selector(".tx textarea"); page.keyboard.type("Moodboard"); page.keyboard.press("Escape")
        page.wait_for_selector("#handles .tidy.tsz"); page.wait_for_timeout(200)
        h1 = box(page, "#handles .tsz [data-tsize='4']"); page.mouse.move(h1["cx"], h1["cy"]); page.wait_for_timeout(100)
        bar = ev(BAR, "#handles .tidy.tsz")
        page.mouse.click(h1["cx"], h1["cy"]); page.wait_for_timeout(300)
        assert ev("() => hyTextSize.cur(Object.values(board.items).find(i => i.type === 'text'))") == 4
        assert ev(BAR, "#handles .tidy.tsz") == bar and under(page, h1["cx"], h1["cy"], "[data-tsize='4']"), "H1 is still under the pointer"
        a = box(page, "#handles .tsz .fz"); page.mouse.move(a["cx"], a["cy"]); page.wait_for_timeout(100)
        page.mouse.click(a["cx"], a["cy"]); page.wait_for_timeout(250); page.mouse.click(a["cx"], a["cy"]); page.wait_for_timeout(250)
        assert ev("() => [hyTextSize.cur(Object.values(board.items).find(i => i.type === 'text')), sel.size]") == [2, 1], "both clicks were A−"
        assert ev(BAR, "#handles .tidy.tsz") == bar
        # the pointer leaves: the bar is placed again over its text, centred unless the board's edge pushes it
        page.mouse.move(700, 880); page.wait_for_timeout(300)
        m = ev("""() => { const b = document.querySelector('#handles .tidy.tsz').getBoundingClientRect(), t = document.querySelector('.tx').getBoundingClientRect(),
          f = hyBars.free(stage, INSET); return [Math.abs((b.left + b.right) / 2 - (t.left + t.right) / 2) <= 1 || b.left <= f.l + 1 || b.right >= f.r - 1, b.left]; }""")
        assert m[0] and round(m[1]) != bar[0], m
    run(tmp_path, go)


def test_area_on_a_note_twice_in_one_place(tmp_path):
    def go(page, ev):
        page.mouse.move(700, 520); page.keyboard.press("n"); page.wait_for_selector(".note textarea"); page.keyboard.type("look"); page.keyboard.press("Escape")
        page.wait_for_selector("#handles [data-nzone]"); page.wait_for_timeout(200)
        a = box(page, "#handles [data-nzone]"); page.mouse.move(a["cx"], a["cy"]); page.wait_for_timeout(100)
        sel_bar = "#handles .tidy:has([data-nzone])"; bar = ev(BAR, sel_bar)
        page.mouse.click(a["cx"], a["cy"]); page.wait_for_timeout(300)
        assert ev("() => !!Object.values(board.items).find(i => i.type === 'note').reach")
        assert ev(BAR, sel_bar) == bar and under(page, a["cx"], a["cy"], "[data-nzone]"), "«Remove area» is where «Area» was"
        page.mouse.click(a["cx"], a["cy"]); page.wait_for_timeout(300)
        assert ev("() => [!!Object.values(board.items).find(i => i.type === 'note').reach, sel.size]") == [False, 1]
    run(tmp_path, go)
