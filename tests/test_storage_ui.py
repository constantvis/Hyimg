"""Settings › Storage on Home and on a board (owner 2026-10-07: «show in Settings the cache size and how much each project takes,
also on Home, and how much RAM the app uses right now»). Home is a file page with a fake app bridge (the app answers
window.hyimgStorage); a board's page asks its own server, on a disposable library, and its memory comes from the app the same way."""
import json
import os
from pathlib import Path

import pytest

from test_storage import cache_tree, env, library, serve  # noqa: F401  (env is a fixture)

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "review/home.html").as_uri()
SHOTS = os.environ.get("HY_SHOTS")   # a folder: the tests leave their screenshots there
P = [{"id": "a", "name": "Studio North", "path": "/x", "available": True, "updated": 1791100000, "covers": []},
     {"id": "b", "name": "Lookbook FW27", "path": "/y", "available": True, "updated": 1791000000, "covers": []},
     {"id": "c", "name": "Hyimg App", "path": "/z", "available": True, "updated": 0, "covers": []}]
GB = 10 ** 9
SUMMARY = {"t": 0, "boards": [{"id": "A", "name": "Studio North", "total": {"bytes": 34 * GB, "disk": 34.3 * GB}},
                              {"id": "b", "name": "Lookbook FW27", "total": {"bytes": 30.5 * GB, "disk": 30.5 * GB}},
                              {"id": "c", "name": "Hyimg App", "total": {"bytes": 0.19 * GB, "disk": 0.19 * GB}}],
           "global": {"backups": [{"name": f"Hyimg.backup.2026100{i}-120000.app", "disk": 0.33 * GB} for i in range(5)]},
           "totals": {"boards": {"disk": 65 * GB}, "made": {"disk": 4.3 * GB}, "cache": {"disk": 3 * GB}, "clearable": {"disk": 0.58 * GB},
                      "backups": {"disk": 1.65 * GB}, "dups": 1.2 * GB}}
RAM = {"op": "ram", "total": 6.9 * GB, "kinds": {"gpu": 4.3 * GB, "pages": 1.7 * GB, "servers": 0.55 * GB, "app": 0.18 * GB}}


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    with playwright.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as error:
            pytest.skip(f"no {request.param} for Playwright: {error}")
        yield b
        b.close()


def shot(page, name):
    if SHOTS:
        try: page.screenshot(path=os.path.join(SHOTS, name + ".png"), timeout=8000)
        except Exception: pass   # WebKit waits for the web font, which may never come offline


def home(browser, lang="en", theme="dark"):
    page = browser.new_page(viewport={"width": 1440, "height": 900}); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };")
    page.add_init_script(f"window.HY_LANG = '{lang}';")
    page.goto(HOME, wait_until="domcontentloaded")   # the web font may take its time; the page does not wait for it
    page.evaluate(f"hyimgHome({json.dumps({'projects': P, 'settings': {'cv.theme': theme}, 'home': {'folders': [], 'view': 'list'}})})")
    page.wait_for_function("() => (window.__sent || []).some(m => m.action === 'storage' && m.op === 'summary')")   # sizes without opening the panel
    page.evaluate(f"hyimgStorage({json.dumps({'op': 'summary', 'summary': SUMMARY, 'age': 120, 'scanning': False})})")
    return page, errors


def sent(page, **kv):
    return [m for m in page.evaluate("window.__sent || []") if all(m.get(k) == v for k, v in kv.items())]


def test_home_shows_each_boards_size_and_sorts_by_it(browser):
    page, errors = home(browser)
    page.locator("[data-tab=all]").click()
    assert page.locator(".list .card[data-id=a] .c4").inner_text() == "34 GB"
    assert page.locator(".list .card[data-id=c] .c4").inner_text() == "190 MB"
    names = lambda: page.locator(".list .card .n").all_inner_texts()
    assert names() == ["Hyimg App", "Lookbook FW27", "Studio North"]   # by name, as before
    page.locator(".list .lh .hs-th").click()
    assert names() == ["Studio North", "Lookbook FW27", "Hyimg App"] and page.locator(".hs-th").get_attribute("aria-pressed") == "true"
    assert sent(page, action="homeSave")[-1]["home"]["sort"] == "size"
    shot(page, f"home-list-{browser.browser_type.name}")
    page.locator(".list .lh .hs-th").click()
    assert names() == ["Hyimg App", "Lookbook FW27", "Studio North"]
    page.locator(".head [data-view=grid]").click()
    assert "34 GB" in page.locator(".grid .card[data-id=a] .meta .s").inner_text()
    assert not errors


def test_home_settings_storage_section_and_clear_asks_the_app(browser):
    page, errors = home(browser)
    page.click("#bset")
    page.wait_for_function("() => (window.__sent || []).some(m => m.action === 'storage' && m.op === 'ram')")
    page.evaluate(f"hyimgStorage({json.dumps(RAM)})")
    sec = page.locator("#sets #hyStore")
    text = sec.text_content()   # the heading is upper case by CSS
    for words in ("Storage", "2 min ago", "Boards", "65 GB", "Studio North", "34 GB", "Made by Hyimg", "4.3 GB", "Cache", "3 GB",
                  "Clear 580 MB", "App copies · 5", "1.7 GB", "To the Trash", "Duplicates", "1.2 GB", "Memory now", "6.9 GB", "Graphics", "4.3 GB"):
        assert words in text, words
    page.locator("#hyStore [data-hs=clear] button").scroll_into_view_if_needed()
    shot(page, f"home-settings-{browser.browser_type.name}")
    page.locator("#hyStore [data-hs=clear] button").click()
    ask = sent(page, action="storage", op="clear")
    assert ask and ask[-1]["confirm"] is True and ask[-1]["title"] == "Clear the cache, 580 MB?"   # Home: the app asks with its dialog
    assert page.locator("#hyStore [data-hs=clear]").get_attribute("disabled") is not None   # busy until the answer
    page.evaluate("hyimgStorage({op: 'clear', freed: 581000000, removed: 12})")
    page.wait_for_selector("#hyToasts .ht")
    assert "Freed 581 MB" in page.locator("#hyToasts").inner_text()
    page.evaluate("hyimgStorage({op: 'backups', cancelled: true})")
    assert not errors


def test_home_storage_in_russian(browser):
    page, errors = home(browser, "ru", "light")
    page.click("#bset"); page.evaluate(f"hyimgStorage({json.dumps(RAM)})")
    text = page.locator("#hyStore").text_content()
    for words in ("Хранилище", "Доски", "65 ГБ", "Кэш", "Очистить 580 МБ", "Копии приложения · 5", "Память сейчас", "6,9 ГБ", "Графика"):
        assert words in text, words
    shot(page, f"home-settings-ru-{browser.browser_type.name}")
    assert page.evaluate("window.__tMiss") == [] and not errors


def test_board_settings_storage_from_its_server(browser, env):  # noqa: F811
    library(env["lib"]); cache_tree(env, env["pid"])
    port, proc = serve(env)
    try:
        page = browser.new_page(viewport={"width": 1440, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/canvas")
        page.wait_for_selector("#bset")
        page.click("#bset")
        page.wait_for_function("() => document.querySelector('#hyStore') && /Boards/.test(document.querySelector('#hyStore').innerText)", timeout=30000)
        text = page.locator("#hyStore").text_content()
        assert "Board" in text and "Server memory" in text and "Duplicates" in text   # a plain browser: no app, its server's memory
        clear = page.locator("#hyStore hy-button[data-hs=clear]")
        assert clear.locator("button").count() == 1   # the primitive's own button, not one written inside it
        shot(page, f"board-settings-{browser.browser_type.name}")
        clear.click()
        page.wait_for_selector("#hyConfirm.on")
        assert "Clear the cache" in page.locator("#hyConfirm").inner_text()
        page.locator("#hyConfirm [data-a=ok]").click()
        page.wait_for_selector("#hyToasts .ht")
        assert "Freed" in page.locator("#hyToasts").inner_text()
        assert not (env["cache"] / "video/old.webm").exists() and (env["cache"] / "video/new.webm").exists()
        assert (env["lib"] / "a/one.png").read_bytes() == b"P" * 5000
        assert not errors
    finally:
        proc.terminate(); proc.wait(5)


def test_home_lists_lost_processes_and_stop_asks_the_app(browser):
    """servers and Blender whose parent is gone (review/procs.py), with their memory; «Stop» goes through the app's question"""
    page, errors = home(browser)
    lost = [{"pid": 4242, "kind": "server", "port": "59674", "age": 54000, "bytes": 45 * 10 ** 6},
            {"pid": 4343, "kind": "blender", "port": "", "age": 600, "bytes": 300 * 10 ** 6}]
    page.evaluate(f"hyimgStorage({json.dumps({'op': 'summary', 'summary': SUMMARY, 'age': 5, 'scanning': False, 'lost': lost})})")
    page.click("#bset")
    text = page.locator("#hyStore").text_content()
    for words in ("Lost processes · 2", "345 MB", "Server 59674 · 15 h", "Blender · 10 min"):
        assert words in text, words
    page.locator("#hyStore [data-hs=stop][data-pid='4242'] button").click()
    ask = sent(page, action="storage", op="stop")
    assert ask[-1]["pid"] == 4242 and ask[-1]["confirm"] is True and ask[-1]["title"] == "Stop Server 59674 · 15 h?"
    page.evaluate("hyimgStorage({op: 'stop', stopped: 4242, freed: 45000000})")
    page.wait_for_selector("#hyToasts .ht")
    assert "Stopped, 45 MB freed" in page.locator("#hyToasts").inner_text()
    assert "Server 59674" not in page.locator("#hyStore").text_content()
    shot(page, f"home-lost-{browser.browser_type.name}")
    assert not errors


def test_home_sets_the_thumbnail_ceiling_through_the_app(browser):
    page, errors = home(browser)
    page.evaluate(f"hyimgStorage({json.dumps({'op': 'summary', 'summary': SUMMARY, 'age': 5, 'scanning': False, 'caps': {'board': 2, 'total': 8}})})")
    page.click("#bset")
    assert page.locator("#hyStore [data-hscap=board] [aria-pressed=true]").inner_text() == "2 GB"
    page.locator("#hyStore [data-hscap=board] [data-cap='5']").click()
    assert sent(page, action="storage", op="caps")[-1]["board"] == 5
    assert page.locator("#hyStore [data-hscap=board] [aria-pressed=true]").inner_text() == "5 GB"
    assert page.locator("#sets").evaluate("e => e.classList.contains('open')")   # the panel stays open
    shot(page, f"home-caps-{browser.browser_type.name}")
    assert not errors
