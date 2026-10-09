"""Settings › Notifications (review/ui/macnotif.js, owner 2026-10-08): the Mac's banners for what comes to the bell. One section after the
shared rows, the same on a board and on Home: «Mac notifications» and under it one switch per event and «Only when Hyimg is in the
background», all on (that one off) by default; off, the rows under it are grey and cannot be changed. A board writes the app's settings
file (cv.mac, cv.mac.<type>, cv.mac.bg), Home sends them to the app. Chromium, dark theme, English and Russian."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "review/home.html").as_uri()
BRIDGE = "window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };"
OUT = os.environ.get("HY_SHOTS")   # a folder for the section's pictures, to look at
ROWS = """() => [...document.querySelectorAll('#hyMacNotif .mn-row')].map(r => { const s = r.querySelector('hy-switch');
  return [r.dataset.mn, r.querySelector('.mn-l').textContent, s.hasAttribute('checked'), s.hasAttribute('disabled')]; })"""
TYPES = ["mac.agent", "mac.comment", "mac.reply", "mac.mention", "mac.note"]


@pytest.fixture(scope="module")
def board(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("macnotif")
    lib, state = tmp / "lib", tmp / "state"
    lib.mkdir(); (state / "boards").mkdir(parents=True)
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    settings = tmp / "settings.json"; settings.write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    (tmp / "home").mkdir()
    env.update(HOME=str(tmp / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(settings),
               HYIMG_PLUGINS=str(tmp / "noplugins"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    try:
        yield port, settings
    finally:
        proc.terminate(); proc.wait(5); log.close()


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try: br = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        yield br
        br.close()


def opened(page):
    page.click("#bset"); page.wait_for_selector("#sets.open"); page.wait_for_selector("#hyMacNotif .mn-row", state="attached")
    page.evaluate("s => hySetPanel.go(s)", "notifications"); page.wait_for_selector("#hyMacNotif .mn-row"); page.wait_for_timeout(300)   # its section of the window
    return page


def open_board(browser, port):
    page = browser.new_page(viewport={"width": 1300, "height": 1100}, color_scheme="dark"); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(BRIDGE)
    page.goto(f"http://127.0.0.1:{port}/canvas.html")
    page.wait_for_function("() => typeof board !== 'undefined' && customElements.get('hy-switch')", timeout=20000)
    return opened(page), errors


def open_home(browser, lang="en", settings=None):
    page = browser.new_page(viewport={"width": 1300, "height": 1100}, color_scheme="dark"); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(BRIDGE); page.add_init_script(f"window.HY_LANG = '{lang}';")
    page.goto(HOME)
    page.evaluate("s => hyimgHome({ projects: [], settings: s, home: { folders: [] }, cef: true, engine: 'webkit' })",
                  {"cv.lang": lang, "cv.theme": "dark", **(settings or {})})
    return opened(page), errors


def wait_file(settings, test):
    for _ in range(50):
        f = json.loads(settings.read_text())
        if test(f): return f
        time.sleep(0.1)
    return json.loads(settings.read_text())


def test_the_section_on_a_board(browser, board):
    port, settings = board
    page, errors = open_board(browser, port)
    rows = page.evaluate(ROWS)
    assert rows == [["mac", "Mac notifications", True, False], ["mac.agent", "An agent placed something on a board", True, False],
                    ["mac.comment", "An annotation on a board", True, False], ["mac.reply", "A reply to me", True, False],
                    ["mac.mention", "I or my agent was @mentioned", True, False], ["mac.note", "A reply to my note", True, False],
                    ["mac.bg", "Only when Hyimg is in the background", False, False]], rows
    # its own section of the settings (ui/settings-win.js): at a board's side under its header «Notifications»
    assert page.evaluate("() => document.querySelector('#hyMacNotif .sh').textContent") == "Notifications"
    assert page.evaluate("""() => { const sp = document.querySelector('#sets .sw-body > .sp'), m = document.getElementById('hyMacNotif');
      return m.parentElement.classList.contains('sw-body') && !sp.contains(m) && m.dataset.sec === 'notifications' && m.classList.contains('sw-on'); }""")
    assert page.inner_text("#sets .sw-sl[data-for=notifications] .sw-st") == "Notifications"
    if OUT: page.locator("#hyMacNotif").screenshot(path=os.path.join(OUT, "macnotif-board-on.png"))
    # one type off, then on again: "0", then the setting taken away (on is the default)
    page.click("#hyMacNotif [data-mn='mac.reply'] .mn-l")
    assert page.evaluate("() => localStorage.getItem('cv.mac.reply')") == "0"
    assert wait_file(settings, lambda f: f.get("cv.mac.reply") == "0").get("cv.mac.reply") == "0"
    page.click("#hyMacNotif [data-mn='mac.reply'] hy-switch")
    assert page.evaluate("() => localStorage.getItem('cv.mac.reply')") is None
    assert "cv.mac.reply" not in wait_file(settings, lambda f: "cv.mac.reply" not in f)
    # only in the background: "1"
    page.click("#hyMacNotif [data-mn='mac.bg'] hy-switch")
    assert wait_file(settings, lambda f: f.get("cv.mac.bg") == "1").get("cv.mac.bg") == "1"
    # the master switch off: everything under it grey and fixed
    page.click("#hyMacNotif [data-mn='mac'] hy-switch")
    assert wait_file(settings, lambda f: f.get("cv.mac") == "0").get("cv.mac") == "0"
    rows = page.evaluate(ROWS)
    assert rows[0][2] is False and all(r[3] for r in rows[1:]) and rows[6][2] is True, rows
    assert page.evaluate("() => getComputedStyle(document.querySelector('#hyMacNotif .mn-sub')).opacity") == "0.45"
    if OUT: page.locator("#hyMacNotif").screenshot(path=os.path.join(OUT, "macnotif-board-off.png"))
    page.click("#hyMacNotif [data-mn='mac.agent'] .mn-l", force=True)
    assert page.evaluate("() => localStorage.getItem('cv.mac.agent')") is None   # a grey row does not change
    # by the keyboard: the master switch on again with Space, its rows come back
    page.focus("#hyMacNotif [data-mn='mac'] input"); page.keyboard.press("Space")
    assert "cv.mac" not in wait_file(settings, lambda f: "cv.mac" not in f)
    assert not any(r[3] for r in page.evaluate(ROWS))
    page.click("#hyMacNotif [data-mn='mac.bg'] hy-switch")
    assert "cv.mac.bg" not in wait_file(settings, lambda f: "cv.mac.bg" not in f)
    assert not errors, errors
    page.close()


def test_the_section_on_home_in_russian(browser):
    page, errors = open_home(browser, "ru", {"cv.mac.note": "0"})
    rows = page.evaluate(ROWS)
    assert page.evaluate("() => document.querySelector('#hyMacNotif .sh').textContent") == "Уведомления"
    assert [r[1] for r in rows] == ["Уведомления Mac", "Агент что-то положил на доску", "Аннотация на доске", "Ответ мне",
                                    "Упомянули меня или моего агента", "Ответ на мою заметку", "Только когда Hyimg в фоне"], rows
    assert [r[2] for r in rows] == [True, True, True, True, True, False, False]   # the file's cv.mac.note "0"
    if OUT: page.locator("#hyMacNotif").screenshot(path=os.path.join(OUT, "macnotif-home-ru.png"))
    sent = lambda: [m.get("change") for m in page.evaluate("window.__sent || []") if m.get("action") == "settings"]
    page.click("#hyMacNotif [data-mn='mac.mention'] .mn-l")
    assert {"cv.mac.mention": "0"} in sent()
    page.click("#hyMacNotif [data-mn='mac.note'] hy-switch")
    assert {"cv.mac.note": None} in sent()
    page.click("#hyMacNotif [data-mn='mac'] hy-switch")
    assert {"cv.mac": "0"} in sent() and all(r[3] for r in page.evaluate(ROWS)[1:])
    # the panel is wide enough for the Russian rows: nothing is cut, each name beside its switch
    assert page.evaluate("""() => [...document.querySelectorAll('#hyMacNotif .mn-row')].every(r => {
      const l = r.querySelector('.mn-l').getBoundingClientRect(), s = r.querySelector('hy-switch').getBoundingClientRect();
      const b = r.getBoundingClientRect(); return l.right <= s.left + 0.5 && s.right <= b.right + 0.5 && l.height < 24; })""")
    assert not errors, errors
    page.close()
