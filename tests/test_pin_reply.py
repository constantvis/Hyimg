"""A click on an annotation's pin puts the cursor in the reply at once (owner 2026-10-10, round 18 question 20, r18-small.html, version A:
«Да, все окей, давай так»). The thread opens and its reply field has the focus: the next letters are the reply, not the board's keys
(F would ♥ the selected picture). The same for a thread opened from the bell and from the page's list of annotations: they all go
through ui/comments.js hyComments.open, the one rule the Studios use too (their own tests: hyimg-image-studio, hyimg-3d-studio,
hyimg-dev-studio test_pin_reply.py).

Chromium, dark theme, a temporary board, the mouse."""
import pytest

from test_annotations_ui import ME, OTHER, board, get, open_board, wait, write_thread

playwright = pytest.importorskip("playwright.sync_api")
FOCUS = "() => !!(document.activeElement && document.activeElement.matches('#cmthread.open textarea'))"


def typed(page, text):
    """types into what has the focus; returns the reply field's text and the pictures ♥ meanwhile"""
    page.keyboard.type(text)
    return page.evaluate("() => [document.querySelector('#cmthread textarea').value, document.querySelectorAll('.faved').length]")


def test_a_click_on_a_pin_the_bell_or_the_list_puts_the_cursor_in_the_reply(tmp_path):
    servers, port = board(tmp_path, "en")
    try:
        write_thread(tmp_path, "cbob00001", {"person": OTHER, "via": "app"}, "@Ann Lee have a look", [{"person": ME, "label": "Ann Lee"}])
        with playwright.sync_playwright() as p:
            browser, page, errors = open_board(p, port)
            page.wait_for_selector('#cmpins [data-c="cbob00001"]', timeout=15000)
            page.evaluate("() => { sel = new Set(['i3']); render(); }")
            # the pin on the board: a click, and the reply field is the one typed in
            page.locator('#cmpins [data-c="cbob00001"]').click()
            page.wait_for_selector('#cmthread.open[data-c="cbob00001"] textarea')
            page.wait_for_function(FOCUS, timeout=3000)
            assert typed(page, "fine") == ["fine", 0]
            page.keyboard.press("Escape"); page.wait_for_function("() => !document.querySelector('#cmthread.open')")
            page.mouse.click(700, 820); page.wait_for_timeout(200)
            # the bell: its row opens the thread with the cursor in the reply, the words kept on the pin come back with it
            page.evaluate("() => pollNtf()"); page.wait_for_selector("#bntf.dot", timeout=10000)
            page.locator("#bntf").click(); page.wait_for_selector("#ntf.open")
            page.locator('#ntf .nt[data-n^="c:cbob00001"]').click()
            page.wait_for_selector('#cmthread.open[data-c="cbob00001"] textarea')
            page.wait_for_function(FOCUS, timeout=3000)
            assert typed(page, " good") == ["fine good", 0]
            page.keyboard.press("Escape"); page.wait_for_function("() => !document.querySelector('#cmthread.open')")
            # the page's list of annotations: a row goes to the pin, the cursor in the reply
            page.evaluate("() => hyComments.list()"); page.wait_for_selector('#cmlist.open [data-go="cbob00001"]')
            page.locator('#cmlist [data-go="cbob00001"]').click()
            page.wait_for_selector('#cmthread.open[data-c="cbob00001"] textarea')
            page.wait_for_function(FOCUS, timeout=3000)
            page.keyboard.press("Enter")   # ↵ sends what was typed: a reply, written
            wait(lambda: len(get(port, "/api/comments?name=main")["items"][0]["messages"]) == 2, "no reply")
            assert get(port, "/api/comments?name=main")["items"][0]["messages"][1]["text"] == "fine good"
            assert not errors, errors
            browser.close()
    finally:
        servers.close()
