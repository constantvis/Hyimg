"""⌃Tab back to Home while a board opens from it, Home's side (owner 2026-10-09 on the ⌃Tab cards: «почему-то не всегда переключается на
Home screen, особенно если мы открыли только одну вкладку. Я быстро переключаюсь назад — он меня не переключает»).

Home → board plays Home's leave (review/home.html hyimgOpen) and asks for the handoff (hyimgHandoff), which waits for the 750 ms leave. A quick
⌃Tab to Home meanwhile makes the app show Home again (native showProjects → hyimgBack). The handoff's wait then went on: its next tick read the
loading that Back had ended (a TypeError), and a board opened again in that time got a second handoff from the first wait. Here the app's
calls are played on Home with one board and with two: Home comes back, no handoff is sent for a board left, a board opened again gets one.
The app's side (which card ⌃Tab starts on while Home leaves, releasing on Home) is tests/test_native_sleep.swift. Chromium, dark."""
import json
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
HOME = (Path(__file__).resolve().parents[1] / "review/home.html").as_uri()
BRIDGE = "window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };"
ONE = [{"id": "a", "name": "Hyimg App", "path": "/x", "available": True, "updated": 1791100000, "covers": [], "open": True}]
TWO = ONE + [{"id": "b", "name": "Atlas studio workroom", "path": "/y", "available": True, "updated": 1791000000, "covers": [], "open": True}]


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try: br = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        yield br
        br.close()


def home(browser, projects):
    page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark"); page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.add_init_script(BRIDGE); page.add_init_script("window.HY_LANG = 'en';")
    page.goto(HOME)
    page.evaluate(f"hyimgHome({json.dumps({'projects': projects, 'settings': {'cv.theme': 'dark'}, 'home': {'folders': []}})})")
    page.wait_for_function("() => document.querySelectorAll('.card[data-id]').length > 0")
    return page


def handoffs(page, id):
    return [m for m in page.evaluate("window.__sent || []") if m.get("action") == "handoff" and m.get("id") == id]


def back_on_home(page):
    """Home is there again: not leaving, its loading plate gone, and nothing went wrong on the page"""
    assert "leave" not in (page.get_attribute("body", "class") or "")
    page.wait_for_function("() => getComputedStyle(document.querySelector('#load')).visibility === 'hidden'", timeout=3000)
    assert not page.errors, page.errors


@pytest.mark.parametrize("projects", [ONE, TWO], ids=["one board", "two boards"])
def test_ctrl_tab_to_home_while_a_board_opens(browser, projects):
    """board → Home → board → Home, each a quick ⌃Tab: the board is drawn, so Home leaves and asks for the handoff at once; Back comes
    200 ms later, within the 750 ms leave"""
    page = home(browser, projects)
    try:
        assert page.evaluate("hyimgOpen('a', 'Hyimg App') && hyimgHandoff('a')") is True
        page.wait_for_timeout(200)
        assert page.evaluate("hyimgBack()") is True
        page.wait_for_timeout(1300)   # past the leave and the handoff's ticks
        assert handoffs(page, "a") == [], "a board left for Home was handed over"
        back_on_home(page)
    finally:
        page.close()


def test_home_board_home_board_quickly_two_boards(browser):
    """Home → a → Home → b → Home, a quick ⌃Tab each, then a for good: one handoff, for the last open, after its own leave"""
    page = home(browser, TWO)
    try:
        for id in ("a", "b"):
            page.evaluate(f"hyimgOpen('{id}', 'x') && hyimgHandoff('{id}')"); page.wait_for_timeout(150)
            page.evaluate("hyimgBack()"); page.wait_for_timeout(100)
        back_on_home(page)
        page.evaluate("hyimgOpen('a', 'Hyimg App') && hyimgHandoff('a')")
        t0 = page.evaluate("performance.now()")
        page.wait_for_function("() => (window.__sent || []).some(m => m.action === 'handoff' && m.id === 'a')", timeout=4000)
        assert page.evaluate("performance.now()") - t0 > 600, "handed over before its own leave was over"
        page.wait_for_timeout(1000)
        assert len(handoffs(page, "a")) == 1 and handoffs(page, "b") == [], page.evaluate("window.__sent.filter(m => m.action === 'handoff')")
        assert not page.errors, page.errors
    finally:
        page.close()


def test_same_board_again_right_after_back(browser):
    """Home → a → Home → a within the first leave: a's handoff comes once, after the second leave, not from the first wait"""
    page = home(browser, ONE)
    try:
        page.evaluate("hyimgOpen('a', 'Hyimg App') && hyimgHandoff('a')"); page.wait_for_timeout(200)
        page.evaluate("hyimgBack()"); page.wait_for_timeout(100)
        page.evaluate("hyimgOpen('a', 'Hyimg App') && hyimgHandoff('a')")
        page.wait_for_function("() => (window.__sent || []).some(m => m.action === 'handoff' && m.id === 'a')", timeout=4000)
        page.wait_for_timeout(1000)
        assert len(handoffs(page, "a")) == 1, handoffs(page, "a")
        assert not page.errors, page.errors
    finally:
        page.close()
