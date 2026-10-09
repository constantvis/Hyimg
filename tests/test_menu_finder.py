"""«Show in Finder» and «Copy as › File path» for every card that stands for a file on disk (owner 2026-10-09, on an HTML card's menu:
«reveal in Finder всё равно не вижу»; he wanted the .html file to send it to a friend).

- an HTML card (Dev Studio, `src`), an HTML frame (the frames plugin, `src`) and a 3D scene card (`scene`) get both items, enabled;
  Show in Finder posts that file's path to /api/reveal, File path copies it
- several cards selected: one reveal with all their files, the picture's among them; a picture's menu stays as it was
Runs in Chromium, dark, on a temporary library with no plugins: the cards are drawn by the board's stand-in. /api/reveal is intercepted,
Finder never opens."""
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
from test_move_to_page import screen

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
FILES = {"h": "html/demo/index.html", "f": "html/frame/index.html", "m": "3d/scenes/s/scene.json"}


def board():
    items = {
        "p": {"path": "a/0.png", "x": 0, "y": 0, "w": 300, "ar": 2 / 3, "crop": None},
        "h": {"type": "html", "src": FILES["h"], "vw": 1440, "x": 400, "y": 0, "w": 300, "h": 200},
        "f": {"type": "htmlframe", "src": FILES["f"], "vw": 1440, "x": 800, "y": 0, "w": 300, "h": 200},
        "m": {"type": "model3d", "scene": FILES["m"], "camera": "c", "x": 1200, "y": 0, "w": 300, "h": 300},
    }
    return {"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True); plugins.mkdir()
    (lib / "a/0.png").write_bytes(png(40, 60))
    for p in FILES.values():
        (lib / p).parent.mkdir(parents=True, exist_ok=True); (lib / p).write_text("{}" if p.endswith(".json") else "<!doctype html><p>hi")
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HYIMG_PLUGINS=str(plugins), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port
    finally:
        proc.terminate(); proc.wait(5); log.close()


ROWS = """() => [...document.querySelectorAll('#ctx > [role=menuitem]')].map(e => [(e.querySelector('.ml') || e).textContent.trim(),
  e.getAttribute('aria-disabled') === 'true'])"""
SUB = """() => [...document.querySelectorAll('#ctx .hy-sub > [role=menuitem]')].map(b => [(b.querySelector('.ml') || b).textContent.trim(),
  b.getAttribute('aria-disabled') === 'true'])"""


def test_file_cards_show_in_finder(server):
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 1000}, color_scheme="dark")
        errors, reveals = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/api/reveal", lambda route: (reveals.append(json.loads(route.request.post_data)["paths"]),
                                                    route.fulfill(status=200, content_type="application/json", body="{}")))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && ['p', 'h', 'f', 'm'].every(i => EL.get(i) || document.querySelector(`.plg[data-id=${i}]`))",
                               timeout=20000)
        page.evaluate("() => { cam.x = -100; cam.y = -100; cam.z = .6; renderCam(); render(); window.__copied = []; copyText = (t) => __copied.push(t); }")
        page.wait_for_timeout(300)

        def menu(id):
            it = page.evaluate(f"() => board.items['{id}']")
            page.mouse.click(1390, 990); page.keyboard.press("Escape")
            x, y = screen(page, it["x"] + 40, it["y"] + 40)
            page.mouse.click(x, y, button="right")
            page.wait_for_selector("#ctx.open [role=menuitem]")
            return dict(page.evaluate(ROWS))

        for id in ("h", "f", "m", "p"):
            rows = menu(id)
            assert rows.get("Show in Finder") is False, (id, rows)   # present and enabled
            page.locator("#ctx [data-sub=copyas]").hover()
            page.wait_for_selector("#ctx .hy-sub [role=menuitem]")
            sub = dict(page.evaluate(SUB))
            assert sub.get("File path") is False, (id, sub)
            page.locator("#ctx .hy-sub [data-act=path]").click()
            menu(id)
            page.locator("#ctx [data-act=reveal]").click()
            page.wait_for_timeout(200)
        files = [FILES["h"], FILES["f"], FILES["m"], "a/0.png"]
        assert page.evaluate("() => __copied") == files
        assert reveals == [[f] for f in files], reveals
        # several selected: one reveal of all their files
        page.evaluate("() => { sel = new Set(['p', 'h', 'f', 'm']); render(); }")
        it = page.evaluate("() => board.items.h")
        x, y = screen(page, it["x"] + 40, it["y"] + 40)
        page.mouse.click(x, y, button="right")
        page.wait_for_selector("#ctx.open [role=menuitem]")
        assert dict(page.evaluate(ROWS)).get("Show in Finder") is False
        page.locator("#ctx [data-act=reveal]").click()
        page.wait_for_timeout(300)
        assert sorted(reveals[-1]) == sorted(files), reveals[-1]
        assert not errors, errors
        browser.close()
