"""«Order ›» on the board's right click and its keys, as in Figma (owner 2026-10-06: «добавь на правой кнопке мыши move on top, move
bottom… Как в Figma: слои вверх-вниз или на полный верх, на полный низ. Только в рамках той же группы. И комбинация клавиш, как в Figma»).

- Bring to front ⌥⌘], Bring forward ⌘], Send backward ⌘[, Send to back ⌥⌘[ change what is drawn on top where cards overlap
- only among the siblings: a group's members (or the page's top level), in their layer; a card outside the group stays where it was
- several selected keep their order among themselves
- grey with the reason when nothing would move: «Already on top», «Already at the bottom», «No neighbours in the group»
- one undo step; saved (the order of the board file's items), so a reload keeps it; hy.py do 'front REF' does the same
Runs in Chromium and WebKit where Playwright has them, on temporary libraries only (the frames plugin from its repository's last commit)."""
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
from test_move_to_page import frames_plugin, screen

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
ENGINES = ["chromium", "webkit"]


def board():
    pic = lambda n, x, y: {"path": f"a/{n}.png", "x": x, "y": y, "w": 300, "ar": 1, "crop": None}
    items = {
        "a": pic(0, 0, 0), "b": pic(1, 100, 100),                      # in the group, overlapping around (250, 250)
        "f": {"type": "imgframe", "x": 200, "y": 200, "w": 300, "h": 300, "name": "F1", "doc": "frames/t1/frame.1.json", "render": "frames/t1/render.1.png",
              "v": 1, "size": [60, 60], "pics": ["a/3.png"]},             # a plugin card in the same group, over both
        "n": {"type": "note", "text": "in the group", "x": 600, "y": 0, "w": 200, "fs": 12, "color": "yellow"},
        "o": pic(2, -250, -250),                                        # not in the group, the last of all: over a at (-50, -50)… (25, 25)
    }
    groups = {"G": {"title": "G", "x": -100, "y": -100, "w": 1000, "h": 800, "members": ["a", "b", "f", "n"]}}
    items["o"]["x"], items["o"]["y"] = -200, -200
    return {"schema": 1, "revision": 1, "items": items, "groups": groups, "removed": {}}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True); plugins.mkdir()
    for n in range(4):
        (lib / "a" / f"{n}.png").write_bytes(png(40 + n, 40))
    (lib / "frames/t1").mkdir(parents=True)
    (lib / "frames/t1/render.1.png").write_bytes(png(60, 60))
    (lib / "frames/t1/frame.1.json").write_text(json.dumps({"version": 1, "v": 1, "name": "F1", "size": [60, 60], "background": "#ffffff", "order": "bottom-to-top",
                                                             "layers": [], "render": "frames/t1/render.1.png"}))
    frames = frames_plugin(plugins / "frames")
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HYIMG_PLUGINS=str(plugins), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield {"port": port, "frames": frames}
    finally:
        proc.terminate(); proc.wait(5); log.close()


def api(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r: return json.load(r)


def open_board(p, engine, port, frames):
    try: browser = getattr(p, engine).launch()
    except Exception as error: pytest.skip(f"no {engine} for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url)
    page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); localStorage.setItem('cv.cam.main', JSON.stringify({ x: -400, y: -300, z: .8 })); }")
    page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && board.items.a && EL.get('a') && EL.get('o')", timeout=20000)
    if frames: page.wait_for_function("() => PLG.imgframe && EL.get('f') && EL.get('f').classList.contains('plg')", timeout=15000)
    errors.clear()   # WebKit reports the first load's requests, cancelled by the reload, as errors
    page.wait_for_timeout(300)
    return browser, page, errors


TOP = "([x, y]) => { const [sx, sy] = (({ x: X, y: Y }) => { const r = stage.getBoundingClientRect(); return [(X - cam.x) * cam.z + r.left, (Y - cam.y) * cam.z + r.top]; })({ x, y });" \
      " const e = document.elementsFromPoint(sx, sy).map(e => e.closest('#items [data-id]')).find(Boolean); return e ? e.dataset.id : null; }"
P, Q = [250, 250], [50, 50]   # P: a, b and f overlap; Q: a and o (o outside the group)
ORDER = "() => Object.keys(board.items).join(',')"


def pick(page, *ids):
    page.evaluate(f"() => {{ sel = new Set({json.dumps(list(ids))}); render(); }}")


def wait_saved(page):
    page.wait_for_function("() => !dirty && !saveT && !saveFlight", timeout=10000)


ROWS = """() => [...document.querySelectorAll('#ctx .hy-sub [role=menuitem]')].map(b => [b.querySelector('.ml').textContent.trim(), b.getAttribute('aria-disabled') === 'true' ? b.title : ''])"""


def order_menu(page, id, at):
    page.mouse.click(*screen(page, *at), button="right")
    page.wait_for_selector("#ctx.open [data-sub=order]")
    op = page.locator("#ctx [data-sub=order]")
    title = op.get_attribute("title") if op.get_attribute("aria-disabled") == "true" else ""
    if not title:
        op.hover(); page.wait_for_function("() => document.querySelectorAll('#ctx .hy-sub [role=menuitem]').length === 4")
    return title, (page.evaluate(ROWS) if not title else None)


@pytest.mark.parametrize("engine", ENGINES)
def test_menu_moves_within_the_group(server, engine):
    if not server["frames"]: pytest.skip("no hyimg-frames repository beside this one")
    port = server["port"]
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, port, True)
        assert page.evaluate(TOP, P) == "f" and page.evaluate(TOP, Q) == "o"
        pick(page, "a")
        _, rows = order_menu(page, "a", [250, 30])
        assert rows == [["Bring to front", ""], ["Bring forward", ""], ["Send backward", "Already at the bottom"], ["Send to back", "Already at the bottom"]], rows
        page.locator("#ctx .hy-sub [role=menuitem]", has_text="Bring to front").click()
        assert page.evaluate(TOP, P) == "a" and page.evaluate(TOP, Q) == "o"   # over its group's cards, still under the one outside
        assert page.evaluate(ORDER) == "b,f,a,n,o"
        # a plugin card: one step down, then to the bottom
        pick(page, "f")
        _, rows = order_menu(page, "f", [450, 450])
        assert rows[0] == ["Bring to front", ""] and rows[3] == ["Send to back", ""], rows
        page.locator("#ctx .hy-sub [role=menuitem]", has_text="Send backward").click()
        assert page.evaluate(ORDER) == "f,b,a,n,o"
        page.keyboard.press("Control+z"); assert page.evaluate(ORDER) == "b,f,a,n,o"   # one step each
        page.keyboard.press("Control+z"); assert page.evaluate(ORDER) == "a,b,f,n,o" and page.evaluate(TOP, P) == "f"
        # the note is alone in its layer of the group: grey with why; the group alone on the page: «Order» itself grey
        pick(page, "n")
        title, rows = order_menu(page, "n", [700, 50])
        assert title == "No neighbours in the group", (title, rows)
        page.keyboard.press("Escape")
        page.mouse.click(1300, 850)
        title, _ = order_menu(page, "G", [850, 600])
        assert title == "Nothing else on this level", title
        page.keyboard.press("Escape")
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_keys_several_undo_and_reload(server, engine):
    port = server["port"]
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, port, server["frames"])
        pick(page, "a", "b")
        page.mouse.move(1300, 850)
        page.keyboard.press("Control+Alt+BracketRight")    # both to the front of their group, their order kept
        assert page.evaluate(ORDER) == "f,a,b,n,o"
        page.keyboard.press("Control+Alt+BracketLeft")     # both to the back
        assert page.evaluate(ORDER) == "a,b,f,n,o"
        pick(page, "a")
        page.keyboard.press("Control+BracketRight"); assert page.evaluate(ORDER) == "b,a,f,n,o"
        page.keyboard.press("Control+BracketRight"); assert page.evaluate(ORDER) == "b,f,a,n,o"
        page.keyboard.press("Control+BracketRight"); assert page.evaluate(ORDER) == "b,f,a,n,o"   # already on top: nothing, o is outside the group
        page.keyboard.press("Control+BracketLeft"); assert page.evaluate(ORDER) == "b,a,f,n,o"
        assert page.evaluate("() => location.href").endswith("canvas.html")   # the browser's ⌘[ (back) did not run
        page.keyboard.press("Control+z"); assert page.evaluate(ORDER) == "b,f,a,n,o"
        wait_saved(page)
        assert ",".join(api(port, "/api/board?name=main")["items"]) == "b,f,a,n,o"
        page.reload()
        page.wait_for_function("() => typeof BOARD !== 'undefined' && EL.get('a')", timeout=20000)
        assert page.evaluate(ORDER) == "b,f,a,n,o"
        if server["frames"]:
            page.wait_for_function("() => EL.get('f') && EL.get('f').classList.contains('plg')", timeout=15000); page.wait_for_timeout(300)
            assert page.evaluate(TOP, P) == "a"
        assert not errors, errors
        browser.close()


def test_hy_order(server):
    port = server["port"]
    run = lambda script: subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "--port", str(port), "--page", "main", "do", script, "--quiet"],
                                        capture_output=True, text=True, timeout=60)
    r = run("front a"); assert r.returncode == 0, r.stdout + r.stderr
    assert ",".join(api(port, "/api/board?name=main")["items"]) == "b,f,a,n,o"
    r = run("back @a; forward b"); assert r.returncode == 0, r.stdout + r.stderr
    assert ",".join(api(port, "/api/board?name=main")["items"]) == "a,f,b,n,o"
    r = run("backward a"); assert r.returncode == 0 and "ничего не сдвинулось" in r.stdout, r.stdout + r.stderr
