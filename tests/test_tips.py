"""The tip (ui/hy/tip.js), round 12's version 9 (owner 2026-10-09 on r12/docs-tips.html: «9 версия идеальна — делай»):

- an empty page shows one tip under «Drag frames from the library on the left», still; the next visit shows the next one
- a click shows the next, × closes the place's tips and leaves the bulb at half strength, a click on the bulb brings them back; closed
  stays closed after a reload (the place's state is kept beside the key hints' counts, cv.keyhintUsed, an app setting)
- a tip whose keys are pressed is learned and not shown again; Settings › Interface › Key hints: Always shows learned ones, Off shows none
- the library's header shows one in its free part after the folder's path, cut with an ellipsis, and none without room
- filtering the long way (a tag clicked twice to exclude it) shows the quick way (⌥-click) once; ⌥-click itself teaches it
Chromium, dark theme, a temporary library. HY_SHOTS=<folder> keeps screenshots."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
TIP = """() => { const t = document.querySelector('hy-tip'); if (!t) return null; const r = t.getBoundingClientRect(), s = t.querySelector('svg');
  return { ctx: t.dataset.ctx, id: t.dataset.id, text: t.querySelector('.tip-t').textContent, title: t.title, off: t.hasAttribute('off'),
    w: Math.round(r.width), x: Math.round(r.x), bulb: +getComputedStyle(s).opacity,
    line: getComputedStyle(t.querySelector('.tip-t')).display !== 'none' && t.querySelector('.tip-t').getBoundingClientRect().width > 0 }; }"""
COUNTS = "() => JSON.parse(localStorage.getItem('cv.keyhintUsed') || '{}')"


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    for d in (lib / "a", state / "boards", tmp_path / "home"): d.mkdir(parents=True)
    (lib / "a/one.png").write_bytes(png())
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "removed": {}, "items": {}, "groups": {}}))
    settings = tmp_path / "settings.json"; settings.write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(settings), HYIMG_PLUGINS=str(tmp_path / "plugins"), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port
    finally:
        proc.terminate(); proc.wait(5); log.close()


def shot(page, name):
    d = os.environ.get("HY_SHOTS")
    if d: Path(d).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(d) / name))


def board(pg, port):
    pg.goto(f"http://127.0.0.1:{port}/canvas.html")
    pg.wait_for_function("typeof EL !== 'undefined' && !!customElements.get('hy-tip') && !!document.querySelector('#empty hy-tip')", timeout=20000)
    return pg.evaluate(TIP)


def test_empty_page_tip_one_per_visit_click_close_learn_and_the_setting(server):
    port = server
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg = b.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
            errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
            t = board(pg, port)
            shot(pg, "tip-empty-page.png")
            assert t["ctx"] == "board" and t["id"] == "note" and t["text"] == "N puts a note here" and t["title"] == t["text"] and t["line"], t
            # under the empty page's line, centred with it
            pos = pg.evaluate("""() => { const e = document.querySelector('#empty'), t = document.querySelector('#empty hy-tip').getBoundingClientRect();
              const r = document.createRange(); r.selectNodeContents(e.firstChild); const l = r.getBoundingClientRect();
              return [Math.round(t.top - l.bottom), Math.round((t.left + t.right) / 2 - (l.left + l.right) / 2)]; }""")
            assert 0 <= pos[0] <= 24 and abs(pos[1]) <= 2, pos
            # still: the same tip a while later; the next visit (a reload) shows the next one
            pg.wait_for_timeout(1500); assert pg.evaluate(TIP)["id"] == "note"
            assert board(pg, port)["id"] == "paste"
            # a click: the next, the old line fades and lifts first
            pg.click("#empty hy-tip .tip-t"); pg.wait_for_timeout(100)
            assert pg.evaluate("() => document.querySelector('#empty hy-tip').hasAttribute('out')")
            pg.wait_for_timeout(400); assert pg.evaluate(TIP)["id"] == "folder"
            # × on hover closes this place's tips: the bulb alone at half strength, and so after a reload
            pg.hover("#empty hy-tip .tip-t"); pg.click("#empty hy-tip .tip-x")
            t = pg.evaluate(TIP); shot(pg, "tip-closed.png")
            assert t["off"] and not t["line"] and t["bulb"] == 0.5 and "click the bulb" in t["title"], t
            t = board(pg, port); assert t["off"] and not t["line"], t
            pg.click("#empty hy-tip svg"); t = pg.evaluate(TIP)
            assert not t["off"] and t["line"] and pg.evaluate(COUNTS).get("tip.board@off") is None, t
            # its keys pressed: learned (the next visit leaves it out); the key does its own work on the board too (N makes a note)
            pg.evaluate("() => document.activeElement && document.activeElement.blur()"); pg.mouse.click(1000, 300)
            pg.keyboard.press("Escape"); pg.keyboard.press("Meta+v")
            assert pg.evaluate(COUNTS).get("tip.board.paste") == 1
            ids = {board(pg, port)["id"] for _ in range(3)}
            assert ids == {"note", "folder"}, ids
            # Settings › Interface › Key hints: Always brings learned tips back, Off shows none
            pg.evaluate("() => localStorage.setItem('cv.keyhint', 'always')")
            assert "paste" in {board(pg, port)["id"] for _ in range(3)}
            pg.evaluate("() => localStorage.setItem('cv.keyhint', 'off')")
            pg.goto(f"http://127.0.0.1:{port}/canvas.html"); pg.wait_for_function("typeof EL !== 'undefined'", timeout=20000); pg.wait_for_timeout(1200)
            assert pg.evaluate("() => document.querySelectorAll('hy-tip').length") == 0
            assert not errors, errors
        finally:
            b.close()


def test_library_header_tip_takes_the_free_part_and_the_quick_way_once(server):
    port = server
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg = b.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
            errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(f"http://127.0.0.1:{port}/"); pg.wait_for_function("!!document.querySelector('#fbar hy-tip')", timeout=20000)
            tip = lambda: pg.evaluate("""() => { const t = document.querySelector('#fbar hy-tip'), r = t.getBoundingClientRect();
              return [t.dataset.id, Math.round(r.width), t.querySelector('.tip-t').textContent]; }""")
            room = """() => { const bar = document.getElementById('fbar'), p = bar.querySelector('.fpath'), w = bar.querySelector('.libtip').getBoundingClientRect();
              const end = Math.max(...[...p.children].map(c => c.getBoundingClientRect().right)), more = bar.querySelector('.fsMore').getBoundingClientRect();
              return [Math.round(w.left - end), Math.round(more.left - w.right)]; }"""
            # a wide library: the whole line after the path, clear of the path's words and of the next control
            pg.evaluate("() => document.documentElement.style.setProperty('--lw', '1000px')"); pg.wait_for_timeout(500)
            t = tip(); gaps = pg.evaluate(room); shot(pg, "tip-library.png")
            assert t[0] == "altx" and t[1] > 150 and t[2] == "⌥-click a filter excludes it at once" and gaps[0] >= 8 and gaps[1] >= 8, (t, gaps)
            # narrower: the free part only, the line cut with an ellipsis (its title keeps it whole); with no room it is not there
            pg.evaluate("() => document.documentElement.style.setProperty('--lw', '680px')"); pg.wait_for_timeout(500)   # round 15: no buttons at the bar's end
            t = tip(); assert 60 <= t[1] <= 130 and pg.evaluate("() => document.querySelector('#fbar hy-tip').title") == t[2], t
            pg.evaluate("() => document.documentElement.style.setProperty('--lw', '320px')"); pg.wait_for_timeout(500)
            assert tip()[1] == 0
            pg.evaluate("() => document.documentElement.style.setProperty('--lw', '1000px')"); pg.wait_for_timeout(500)
            # the long way: a tag shown, then excluded by a second click; the place shows the quick way, once
            pg.evaluate("() => document.querySelector('#fbar hy-tip').click()"); pg.wait_for_timeout(450)
            assert tip()[0] == "folder"
            pg.evaluate("() => { fcycle('tag:red', false); fcycle('tag:red', false); }"); pg.wait_for_timeout(450)
            assert tip()[0] == "altx" and pg.evaluate(COUNTS).get("tip.library.altx@told") == 1
            pg.evaluate("() => document.querySelector('#fbar hy-tip').click()"); pg.wait_for_timeout(450)
            pg.evaluate("() => { fcycle('tag:red', false); fcycle('tag:red', false); fcycle('tag:red', false); }"); pg.wait_for_timeout(450)
            assert tip()[0] != "altx"   # told once only
            # ⌥-click is the quick way: learned; a folder dragged out of the library teaches the folder tips here and on the board
            pg.evaluate("() => fcycle('tag:blue', true)")
            pg.evaluate("() => document.querySelector('.frow[data-f]').dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: new DataTransfer() }))")
            c = pg.evaluate(COUNTS)
            assert c.get("tip.library.altx") == 1 and c.get("tip.library.folder") == 1 and c.get("tip.board.folder") == 1, c
            assert not errors, errors
        finally:
            b.close()
