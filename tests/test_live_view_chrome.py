"""An HTML frame's live view keeps the board's chrome away, as a Studio does (owner 2026-10-11 on the Info card over the live page: «пж
убери в live preview вот это справа — это пиздец как мешает»; ui/modes.js data-in-studio), and the crop's ratio bar never shows unless a
crop is open on the board (the same screenshot: the bar stood over the live page; ui/cropframe.js). The frames plugin alone, beside this
repository (../hyimg-image-studio). Chromium, the dark theme, our own temporary server.

  nice -n 10 python3 -m pytest -q tests/test_live_view_chrome.py
"""
import pytest

import test_p4_studio_keys as K

playwright = pytest.importorskip("playwright.sync_api")

SEEN = """q => [...document.querySelectorAll(q)].some(e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05; })"""
CHROME = ["#info", "#bntf", "#bkeys", "#bhist", "#bset"]


def test_the_live_view_hides_info_and_never_shows_a_crop_bar(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "PLUGINS", {"frames": K.PLUGINS["frames"]})
    monkeypatch.setattr(K, "ITEMS", {"a1": K.ITEMS["a1"],
                                     "h1": {"type": "htmlframe", "src": "site/keys.html", "vw": 1280, "x": 800, "y": 0, "w": 640, "h": 400}})
    with K.serve(tmp_path) as (port, lib), playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 950}, color_scheme="dark")
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{port}/canvas.html"
        page.goto(url); page.evaluate("() => localStorage.setItem('cv.nolib', '1')"); page.goto(url)
        page.wait_for_function("() => typeof PLGST !== 'undefined' && PLGST.some(p => p.name === 'frames' && p.ok)", timeout=30000)
        page.evaluate("() => { cam.x = -100; cam.y = -100; cam.z = 0.6; renderCam(); render(); }"); page.wait_for_timeout(600)
        page.click(".plg[data-id=h1]"); page.wait_for_function(SEEN, arg="#info", timeout=5000)   # the card's Info, before
        page.dblclick(".plg[data-id=h1]"); page.wait_for_selector(".plg[data-id=h1].plg-live iframe.hfl", timeout=10000)
        page.wait_for_selector("body > hy-studio-actions", timeout=5000)
        page.wait_for_function(f"() => !{CHROME!r}.some(q => ({SEEN})(q))", timeout=5000)
        # a crop asked for while the live page is open (a key, a menu): no ratio bar over the page
        page.evaluate("() => startCrop('a1')"); page.wait_for_timeout(400)
        assert not page.evaluate(SEEN, "#crop .cratio"), "the crop's ratio bar shows over the live page"
        page.keyboard.press("Escape"); page.wait_for_selector(".plg[data-id=h1].plg-live", state="detached", timeout=5000)
        page.click(".plg[data-id=h1]"); page.wait_for_function(SEEN, arg="#info", timeout=5000)   # Info is back with the board
        # the board's own crop still opens and shows its bar
        page.click(".it[data-id=a1]"); page.keyboard.press("Shift+c"); page.wait_for_function(SEEN, arg="#crop .cratio", timeout=5000)
        page.keyboard.press("Escape")
        assert not errors, errors
        browser.close()
