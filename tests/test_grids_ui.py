"""Arrange makes a grid (owner 2026-10-08: «добавить в нашу систему Arrange: пользователю нативно и удобно, он даже не поймет, что таблицей
что-то разложил, а для агента структура — win-win»), on the board in Chromium, dark, on a temporary library only.

- ⌥A on six pictures lays them out as a block and records board.grids (3 × 2, reading order); a member selected shows «Grid 3 × 2»
- a member dragged onto another cell takes it, the others reflow; one ⌘Z puts order and places back
- a member dragged far away leaves the grid and the gap closes; a picture dropped on the grid goes into the cell under the pointer
- ⌘D puts the copy right after its original; a member deleted reflows; «Arrange › Remove grid» drops the record and moves nothing
- the page is saved with its grid, and hy.py map and md show it as a table
Screenshots (dark) go to $HY_SHOTS when it is set."""
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
SHOTS = os.environ.get("HY_SHOTS")


def board():
    pic = lambda k, x, y: {"path": f"a/{k}.png", "x": x, "y": y, "w": 300, "ar": 1.5, "crop": None}
    items = {k: pic(k, x, y) for k, x, y in [("a", 0, 0), ("b", 380, 30), ("c", 700, -20), ("d", 20, 300), ("e", 360, 330), ("f", 760, 280)]}
    items["z"] = pic("z", 0, 900)
    items["n"] = {"type": "note", "text": "Свет мягкий", "x": -420, "y": 0, "w": 300, "fs": 20, "color": "blue", "to": ["a"]}
    return {"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    for k in "abcdefz": (lib / f"a/{k}.png").write_bytes(png(60, 40))
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HY_TEST_ONLY_PLUGINS="1", PYTHONDONTWRITEBYTECODE="1",
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


def api(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r: return json.load(r)


def hy(port, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("HYIMG_")}
    env.update(HYIMG_PORT=str(port), HYIMG_AGENT="test")
    return subprocess.run([sys.executable, str(ROOT / "review/hy.py"), *args, "--page", "main"], env=env, capture_output=True, text=True, timeout=60)


GRID = "() => { const g = Object.values(board.grids || {}); return g.map(x => ({ members: x.members, cols: x.cols, rows: x.rows })); }"
POS = "ids => ids.map(i => [Math.round(board.items[i].x), Math.round(board.items[i].y)])"
CENTRE = "id => { const r = EL.get(id).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }"


def drag(page, frm, to, alt=False, mid=None):
    page.mouse.move(*frm)
    if alt: page.keyboard.down("Alt")
    page.mouse.down()
    for k in range(1, 13):
        page.mouse.move(frm[0] + (to[0] - frm[0]) * k / 12, frm[1] + (to[1] - frm[1]) * k / 12); page.wait_for_timeout(16)
    if mid: page.wait_for_timeout(350); mid()
    page.mouse.up()
    if alt: page.keyboard.up("Alt")
    page.wait_for_timeout(120)


def shot(page, name):
    if SHOTS: Path(SHOTS).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def test_arrange_makes_a_grid_that_behaves(server):
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');"
                      " localStorage.setItem('cv.cam.main', JSON.stringify({ x: -560, y: -160, z: .62 })); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && window.hyGrid && EL.get('a') && EL.get('f')", timeout=30000)
        page.mouse.click(1380, 880)
        # ⌥A: a block, and the block is a grid (reading order, 3 columns)
        page.evaluate("() => { sel = new Set(['a', 'b', 'c', 'd', 'e', 'f']); render(); }")
        page.mouse.move(1380, 880); page.keyboard.press("Alt+KeyA")
        assert page.evaluate(GRID) == [{"members": ["a", "b", "c", "d", "e", "f"], "cols": 3, "rows": 2}]
        order = page.evaluate(GRID)[0]["members"]
        cells = page.evaluate(POS, order)
        assert cells == [[0, -20], [324, -20], [648, -20], [0, 204], [324, 204], [648, 204]], cells
        page.evaluate(f"() => {{ sel = new Set(['{order[4]}']); render(); }}")
        hint = page.locator("#handles .gridhint b")
        assert hint.inner_text() == "Grid 3 × 2"
        shot(page, "1-arrange-grid-selected")
        # a member dragged onto the third cell takes it; the others reflow; one ⌘Z undoes it
        a0 = order[0]
        drag(page, page.evaluate(CENTRE, a0), page.evaluate(CENTRE, order[2]))
        now = page.evaluate(GRID)[0]["members"]
        assert now == [order[1], order[2], a0] + order[3:], now
        assert page.evaluate(POS, now) == cells
        shot(page, "2-drag-within-reorders")
        page.keyboard.press("Control+z")
        assert page.evaluate(GRID)[0]["members"] == order and page.evaluate(POS, order) == cells
        # dragged far away: it leaves the grid, the gap closes
        last = order[5]
        drag(page, page.evaluate(CENTRE, last), (1250, 820))
        g = page.evaluate(GRID)[0]
        assert last not in g["members"] and len(g["members"]) == 5 and g["rows"] == 2
        # the picture z dropped on the first cell goes in first
        def slot():   # mid-drag: the cell it would take is shown, the members already moved over
            assert page.locator("#handles .gridslot").count() == 1 and page.locator("#handles .gridhint.on").count() == 1
            shot(page, "3a-drag-into-shows-the-cell")
        drag(page, page.evaluate(CENTRE, "z"), page.evaluate(CENTRE, order[0]), mid=slot)
        g = page.evaluate(GRID)[0]
        assert g["members"][0] == "z" and len(g["members"]) == 6, g
        assert page.evaluate(POS, ["z"]) == [[0, -20]]
        shot(page, "3-drop-into-grid")
        # ⌘D: the copy right after its original
        page.evaluate(f"() => {{ sel = new Set(['{order[1]}']); render(); }}")
        page.keyboard.press("Control+d")
        g = page.evaluate(GRID)[0]; k = g["members"].index(order[1])
        assert len(g["members"]) == 7 and g["members"][k + 1] not in order + ["z"], g
        copy = g["members"][k + 1]
        # a member deleted: the grid reflows from its top left
        page.evaluate(f"() => {{ sel = new Set(['{copy}']); render(); }}")
        page.keyboard.press("Backspace")
        g = page.evaluate(GRID)[0]
        assert copy not in g["members"] and len(g["members"]) == 6
        assert page.evaluate(POS, g["members"]) == cells
        # saved with its grid; hy.py map and md show the table
        page.wait_for_function("() => !dirty && !saveT && !saveFlight", timeout=10000)
        saved = api(server, "/api/board?name=main")
        assert list(saved["grids"].values())[0]["members"] == g["members"]
        m = hy(server, "map")
        assert m.returncode == 0, m.stderr
        assert "▦ сетка 3 × 2" in m.stdout and "| 1 | z.png [z] |" in m.stdout, m.stdout
        md = hy(server, "md")
        assert md.returncode == 0, md.stderr
        assert "▦ сетка 3 × 2" in md.stdout and "| z.png [z] |" in md.stdout and "> Свет мягкий [n]" in md.stdout, md.stdout
        # right click › Arrange › Remove grid: the record goes, nothing moves
        before = page.evaluate(POS, g["members"])
        page.mouse.click(*page.evaluate(CENTRE, "z"), button="right")
        page.locator('#ctx [data-sub="arrange"]').hover()
        page.wait_for_selector('[data-act="garr"][data-how="remove"]')
        shot(page, "4-arrange-submenu")
        page.locator('[data-act="garr"][data-how="remove"]').click()
        assert page.evaluate(GRID) == [] and page.evaluate(POS, g["members"]) == before
        page.keyboard.press("Control+z")
        assert len(page.evaluate(GRID)) == 1
        assert not errors, errors
        browser.close()
