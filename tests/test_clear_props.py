"""«Clear properties ›» (owner 2026-10-07: «одним кликом убрать все, что применено к выбранной картинке»): Raw Editor, the master mask, crop,
time, opacity, a PDF's page, every kind of HY.props a card has, back to nothing applied; the files never change.

- the board's right click: «Clear properties ›» with «Clear all» first, then each kind the selection can have, grey with why when no
  selected card has it now; ⇧⌥⌘⌫ does «Clear all»; several cards at once; one undo step; a 3D card's opacity too
- the Raw Editor panel's menu has «Clear all», the same path (HY.props.clear)
- hy.py do 'clearprops REF [kind…]'
Runs in Chromium where Playwright has it, dark, on temporary libraries only (the plugins from their repositories' last commits)."""
import io
import json
import os
import subprocess
import sys
import tarfile
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png
from test_move_to_page import frames_plugin, screen

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
GRADE = {"basic": {"exposure": 0.6}}


def board():
    items = {
        "a": {"path": "a/0.png", "x": 0, "y": 0, "w": 300, "ar": 2 / 3, "crop": [0.1, 0.1, 0.9, 0.9], "opacity": 0.5, "grade": GRADE, "mask": {"file": "frames/board-masks/masks/m1.png"}},
        "b": {"path": "a/1.png", "x": 400, "y": 0, "w": 300, "ar": 2 / 3, "crop": [0, 0, 0.5, 1], "opacity": 0.7},
        "c": {"path": "a/2.png", "x": 800, "y": 0, "w": 300, "ar": 2 / 3, "crop": None},
        "m": {"type": "model3d", "empty": True, "x": 1200, "y": 0, "w": 400, "h": 300, "opacity": 0.4},
    }
    return {"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True); plugins.mkdir()
    for n in range(3): (lib / "a" / f"{n}.png").write_bytes(png(40 + n, 60))
    (lib / "frames/board-masks/masks").mkdir(parents=True); (lib / "frames/board-masks/masks/m1.png").write_bytes(png(20, 20))
    frames = frames_plugin(plugins / "frames")
    src = ROOT.parent / "hyimg-3d-studio"
    if (src / "manifest.json").is_file():
        raw = subprocess.run(["git", "-C", str(src), "archive", "HEAD"], capture_output=True, check=True).stdout
        (plugins / "3d").mkdir(); tarfile.open(fileobj=io.BytesIO(raw)).extractall(plugins / "3d", filter="data")
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
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
        yield {"port": port, "frames": frames, "lib": lib, "3d": (plugins / "3d").is_dir()}
    finally:
        proc.terminate(); proc.wait(5); log.close()


def api(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r: return json.load(r)


SUB = """() => [...document.querySelectorAll('#ctx .hy-sub > [role=menuitem]')].map(b => [(b.querySelector('.ml') || b).textContent.trim(),
  b.getAttribute('aria-disabled') === 'true' ? b.title : ''])"""
STATE = "ids => ids.map(i => { const it = board.items[i]; return [it.crop || null, it.opacity ?? 1, !!it.grade, !!it.mask]; })"


def test_clear_properties(server):
    if not server["frames"]: pytest.skip("no hyimg-frames repository beside this one")
    port = server["port"]
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{port}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');"
                      " localStorage.setItem('cv.cam.main', JSON.stringify({ x: -100, y: -100, z: .5 })); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && EL.get('a') && HY.props.list().some(d => d.id === 'mask') && HY.props.list().some(d => d.id === 'grade')", timeout=20000)
        errors.clear()
        st = lambda *ids: page.evaluate(STATE, list(ids))
        # the submenu on a: «Clear all», then the kinds a picture can have; Size is not cleared (the card is its size)
        at = screen(page, 150, 100)
        page.mouse.click(*at, button="right"); page.wait_for_selector("#ctx.open [data-sub=props-clear]")
        page.locator("#ctx [data-sub=props-clear]").hover()
        page.wait_for_function("() => document.querySelectorAll('#ctx .hy-sub [role=menuitem]').length > 3")
        assert page.evaluate(SUB) == [["Clear all", ""], ["Raw Editor", ""], ["Mask", ""], ["Crop", ""], ["Opacity", ""]], page.evaluate(SUB)
        # one kind: only the crop goes
        page.locator("#ctx .hy-sub [role=menuitem]", has_text="Crop").click()
        assert st("a") == [[None, 0.5, True, True]]
        page.keyboard.press("Control+z"); assert st("a")[0][0] == [0.1, 0.1, 0.9, 0.9]
        # a and b together, «Clear all» from the menu: everything applied on both, one undo step back
        page.evaluate("() => { sel = new Set(['a', 'b']); render(); }")
        page.mouse.click(*at, button="right"); page.wait_for_selector("#ctx.open [data-sub=props-clear]")
        page.locator("#ctx [data-sub=props-clear]").hover()
        page.wait_for_function("() => document.querySelectorAll('#ctx .hy-sub [role=menuitem]').length > 3")
        page.locator("#ctx .hy-sub [role=menuitem]", has_text="Clear all").click()
        assert st("a", "b") == [[None, 1, False, False], [None, 1, False, False]]
        page.keyboard.press("Control+z"); assert st("a", "b") == [[[0.1, 0.1, 0.9, 0.9], 0.5, True, True], [[0, 0, 0.5, 1], 0.7, False, False]]
        # c has nothing applied: the item itself is grey
        page.evaluate("() => { sel = new Set(['c']); render(); }")
        page.mouse.click(*screen(page, 950, 100), button="right"); page.wait_for_selector("#ctx.open [data-sub=props-clear]")
        assert page.evaluate("() => document.querySelector('#ctx [data-sub=props-clear]').title") == "Nothing to clear"
        page.keyboard.press("Escape")
        # ⇧⌥⌘⌫ on a 3D card: its opacity
        if server["3d"]:
            page.wait_for_function("() => PLG.model3d && EL.get('m')", timeout=20000)
            page.evaluate("() => { sel = new Set(['m']); render(); }"); page.mouse.move(1390, 890)
            page.keyboard.press("Control+Alt+Shift+Backspace")
            assert page.evaluate("() => board.items.m.opacity") is None
        # the Raw Editor panel's menu: «Clear all», the same path
        page.evaluate("() => { sel = new Set(['a']); render(); __grade.openPanel(['a']); }")
        page.wait_for_selector("#hcgp.in .hcg-pbtn")
        page.locator("#hcgp .hcg-pbtn").click()
        page.locator("#hcgp .hcg-mclear").click()
        assert st("a") == [[None, 1, False, False]]
        page.wait_for_function("() => !dirty && !saveT && !saveFlight", timeout=10000)
        saved = api(port, "/api/board?name=main")["items"]["a"]
        assert "grade" not in saved and "mask" not in saved and saved["crop"] is None and "opacity" not in saved
        assert (server["lib"] / "frames/board-masks/masks/m1.png").exists()   # the mask's file stays
        assert not errors, errors
        browser.close()


def test_hy_clearprops(server):
    port = server["port"]
    run = lambda script: subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "--port", str(port), "--page", "main", "do", script, "--quiet"],
                                        capture_output=True, text=True, timeout=60)
    r = run("clearprops a crop"); assert r.returncode == 0, r.stdout + r.stderr
    b = api(port, "/api/board?name=main")["items"]
    assert b["a"]["crop"] is None and b["a"]["opacity"] == 0.5 and b["a"]["grade"] == GRADE
    r = run("clearprops a b m"); assert r.returncode == 0, r.stdout + r.stderr
    b = api(port, "/api/board?name=main")["items"]
    assert all(k not in b["a"] for k in ("grade", "mask", "opacity")) and b["b"]["crop"] is None and "opacity" not in b["m"]
    assert "ничего не применено" in run("clearprops c").stdout
