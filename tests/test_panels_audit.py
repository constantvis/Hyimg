"""Panels audit 2026-10-11. Chromium, dark, a throwaway board.

  P-19  a bell row whose tile has no picture (a 3D card without its still: /feedthumb answers 404) shows no tile at all, not an empty
        grey 144 × 96 plate
  P-20  the settings window's rail draws one hairline between two groups of sections, never two in a row (Home and a board)

  nice -n 10 python3 -m pytest -q tests/test_panels_audit.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_canvas_pages import free_port  # noqa: E402
from test_setpanel import BRIDGE, HOME  # noqa: E402

# the rail's children as the person sees them, top to bottom: a hairline «|», a section's name, nothing for what is hidden
RAIL = """() => [...document.querySelectorAll('#sets .sw-rail > *')].filter(e => e.getClientRects().length && getComputedStyle(e).display !== 'none')
  .map(e => e.classList.contains('sw-sep') ? '|' : e.dataset.go || e.className)"""


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    lib.mkdir(); (state / "boards").mkdir(parents=True)
    items = {"m1": {"type": "model3d", "scene": "3d/scenes/a/scene.json", "x": 0, "y": 0, "w": 400, "h": 300}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.theme": "dark", "cv.lang": "en"}))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"),
               HYIMG_CACHE_ROOT=str(tmp_path / "cache"), HYIMG_PLUGINS=str(tmp_path / "noplugins"), PYTHONDONTWRITEBYTECODE="1")
    port = free_port(); log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port
    finally:
        process.terminate(); process.wait(5); log.close()


def test_a_tile_without_its_picture_goes_whole(server):
    port = server
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/notifications", method="POST",
                                 data=json.dumps({"action": "add", "title": "Scene ready", "text": "", "who": "Claude", "page": "main", "ids": ["m1"]}).encode(),
                                 headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}", "X-Hyimg-Agent": "Claude"})
    urllib.request.urlopen(req, timeout=20).read()
    items = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/notifications", timeout=20).read())["items"]
    n = next(x for x in items if x["title"] == "Scene ready")
    assert n.get("pv"), "the server offers a tile for the card (its still), which it does not have"
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark"); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/canvas.html")
        page.wait_for_function("() => typeof NTF !== 'undefined' && NTF.items.length >= 1", timeout=15000)
        page.click("#bntf"); row = f"#ntf.open .nt[data-n='{n['id']}']"
        page.wait_for_selector(row)
        # the tile's picture has answered (404): wait until nothing of it is loading any more
        page.wait_for_function("q => [...document.querySelectorAll(q + ' .bt img')].every(i => i.complete)", arg=row, timeout=15000)
        page.wait_for_timeout(200)
        got = page.evaluate("""q => { const r = document.querySelector(q);
          return { tiles: [...r.querySelectorAll('.bt')].map(b => [b.offsetWidth, b.offsetHeight]), strip: !!r.querySelector('.pv'), h: r.offsetHeight }; }""", row)
        assert got["tiles"] == [] and not got["strip"], got
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("where", ["home", "board"])
def test_one_hairline_between_two_groups(server, where):
    port = server
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1300, "height": 1000}, color_scheme="dark"); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        if where == "home":
            page.add_init_script(BRIDGE); page.goto(HOME)
            page.evaluate("hyimgHome({ projects: [], settings: { 'cv.lang': 'en', 'cv.theme': 'dark' }, home: { folders: [] }, cef: true, engine: 'webkit' })")
        else:
            page.goto(f"http://127.0.0.1:{port}/canvas.html")
            page.evaluate("() => localStorage.setItem('cv.setsdock', 'window')"); page.goto(f"http://127.0.0.1:{port}/canvas.html")
            page.wait_for_function("() => typeof BOARD !== 'undefined'", timeout=15000)
        page.click("#bset"); page.wait_for_selector("#sets.open .sw-rail")
        rail = page.evaluate(RAIL)
        twice = [i for i in range(1, len(rail)) if rail[i] == "|" and rail[i - 1] == "|"]
        assert not twice and rail[0] != "|" and rail[-1] != "|", rail
        assert rail.count("|") >= 2, rail
        assert not errors, errors
        browser.close()
