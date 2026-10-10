"""The П4 audit's Средний / Низкий findings of 2026-10-10 in the library beside the board and on Home (docs/process.md §4, §5); the
board's own are tests/test_p4_medium.py. Chromium, dark theme, our own temporary servers, never the ports 4180–4184.

  B-19         the library's Filter window closes on Esc and on a click on the board
  B-34, B-55   ⌘M from the library's search, and a second Esc in it, give the keys to the board
  B-35         the library asks the one typing rule (ui/typing.js)
  B-38         Esc with the card menu open closes the menu only, the picked cards stay
  B-56         the card menu's items all act on the picked cards; ⌘-click picks a card (owner decision 2026-10-10, B-60)
  B-40, B-53   Home: a deleted project comes back with Undo; ⌘F in the Russian layout; a closed menu gives the focus back; ↵ on Open"""
import json
from pathlib import Path

import pytest

from test_p4_board import app_page, browser_of, serve

playwright = pytest.importorskip("playwright.sync_api")
HOME = (Path(__file__).resolve().parents[1] / "review/home.html").as_uri()


def run(tmp_path, fn):
    with serve(tmp_path) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, frame, errors = app_page(browser, port)
        try: fn(page, frame)
        finally: browser.close()
        assert not errors, errors


def test_the_filter_window_closes_on_esc_and_on_the_board(tmp_path):   # B-19
    def go(page, frame):
        page.evaluate("() => $('#tfBtn').click()"); page.wait_for_function("() => !$('#tfPanel').hidden")
        page.keyboard.press("Escape"); assert page.evaluate("() => $('#tfPanel').hidden")
        page.evaluate("() => $('#tfBtn').click()"); page.wait_for_function("() => !$('#tfPanel').hidden")
        frame.click("#stage", position={"x": 600, "y": 700}); page.wait_for_timeout(200)
        assert page.evaluate("() => $('#tfPanel').hidden")
    run(tmp_path, go)


def test_cmd_m_and_a_second_esc_give_the_keys_to_the_board(tmp_path):   # B-34, B-55, B-35
    def go(page, frame):
        assert page.evaluate("() => typeof hyTyping === 'function'")
        page.click("#q"); page.keyboard.type("zz"); page.keyboard.press("Escape")
        assert page.evaluate("() => [$('#q').value, document.activeElement === $('#q')]") == ["", True]
        page.keyboard.press("Escape"); page.wait_for_timeout(100)
        assert page.evaluate("() => document.activeElement === $('#cvFrame')")
        page.mouse.move(1100, 700); page.keyboard.press("n"); frame.wait_for_selector(".note textarea"); page.keyboard.press("Escape")
        n = frame.evaluate("() => Object.values(board.items).filter(i => i.type === 'note').length")
        page.click("#q"); page.keyboard.press("Meta+m"); page.wait_for_timeout(600)
        assert page.evaluate("() => document.activeElement === $('#cvFrame')")
        page.keyboard.press("n"); frame.wait_for_selector(".note textarea"); page.keyboard.press("Escape")
        assert frame.evaluate("() => Object.values(board.items).filter(i => i.type === 'note').length") == n + 1
    run(tmp_path, go)


def test_esc_closes_the_card_menu_only_and_the_menu_acts_on_the_picked(tmp_path):   # B-38, B-56, decision 3
    def go(page, frame):
        cards = page.locator("#list .card:not(.empty)")
        cards.nth(0).click(modifiers=["Meta"]); cards.nth(1).click(modifiers=["Meta"])   # ⌘-click picks, as in Finder
        assert page.evaluate("() => picked.size") == 2
        cards.nth(1).click(modifiers=["Meta"]); assert page.evaluate("() => picked.size") == 1
        cards.nth(1).click(modifiers=["Meta"])
        cards.nth(1).click(button="right"); page.wait_for_selector("#lctx.open")
        labels = page.locator("#lctx.open .ml").all_inner_texts()
        assert any(l.endswith("(2)") for l in labels if l.startswith("Show on board")) and any(l.endswith("(2)") for l in labels if l.startswith("Show in Finder"))
        assert any(l.endswith("(2)") for l in labels if l.startswith("Open")), labels
        page.keyboard.press("Escape")
        assert page.evaluate("() => [document.querySelector('#lctx.open') === null, picked.size]") == [True, 2]
    run(tmp_path, go)


# ---- Home ---------------------------------------------------------------------------------------------------------------------------
P = [{"id": "a", "name": "One", "path": "/x", "available": True, "updated": 1791100000, "covers": []},
     {"id": "b", "name": "Two", "path": "/y", "available": True, "updated": 1791000000, "covers": []}]


def home(p):
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark"); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };")
    page.goto(HOME)
    page.evaluate(f"hyimgHome({json.dumps({'projects': P, 'settings': {}, 'home': {'folders': [{'id': 'f1', 'name': 'Studio', 'projects': ['a']}]}})})")
    return browser, page, errors


def test_home_a_deleted_project_comes_back_and_the_keys(tmp_path):   # B-40, B-53
    with playwright.sync_playwright() as p:
        browser, page, errors = home(p)
        saves = lambda: [{**m["home"], "folders": [f for f in m["home"]["folders"] if f["id"] != "archive"]} for m in page.evaluate("window.__sent || []") if m["action"] == "homeSave"]
        page.locator("[data-folder=f1]").click(button="right"); page.locator("#menu [data-local=delfolder]").click()
        assert saves()[-1]["folders"] == []
        page.locator("#hyToasts .ab").click(); page.wait_for_timeout(100)
        assert [f["id"] for f in saves()[-1]["folders"]] == ["f1"] and saves()[-1]["folders"][0]["projects"] == ["a"]
        page.evaluate("() => document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'а', metaKey: true, bubbles: true, cancelable: true }))")   # ⌘F, Russian
        assert page.evaluate("() => document.activeElement.id") == "q"
        page.evaluate("() => document.activeElement.blur()")
        page.locator(".card[data-id=b]").hover(); page.locator(".card[data-id=b] [data-more]").click(); page.wait_for_selector("#menu.open")
        assert "↵" in page.locator("#menu [data-act=open]").inner_text()
        page.keyboard.press("Escape")
        assert page.evaluate("() => document.activeElement.matches('.card[data-id=b] [data-more]')")
        assert not errors, errors
        browser.close()
