"""«Arrange» for every card on the board (owner 2026-10-07, three 3D cards selected, their bar with only Raw Editor and opacity: «и как насчет
arrange, оно должно быть у всех items на канвасе: 3d, image, dev, video»).

- the bar over a selection of 2 or more cards shows the three arrange buttons (⌥A block, ⌥S row, ⌥D tidy) for 3D cards alone and for a mix
  of a picture, a video, a Dev HTML card and a 3D card
- ⌥A lays 3D cards out as a block, ⌥S puts the mix in one row aligned at the top, a gap of 24 between; one undo step; saved
Runs in Chromium and WebKit where Playwright has them, on temporary libraries only (the plugins from their repositories' last commits)."""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
ENGINES = ["chromium", "webkit"]
FFMPEG = shutil.which("ffmpeg")
PLUGINS = {"3d": "hyimg-3d-studio", "dev": "hyimg-dev-studio"}
PAGE = "<!doctype html><html><head><title>Site</title></head><body><h1>A page</h1></body></html>"


def board():
    items = {
        "m1": {"type": "model3d", "empty": True, "x": 0, "y": 0, "w": 400, "h": 300},
        "m2": {"type": "model3d", "empty": True, "x": 700, "y": 50, "w": 400, "h": 300},
        "m3": {"type": "model3d", "empty": True, "x": 100, "y": 600, "w": 300, "h": 200},
        "p": {"path": "a/0.png", "x": 0, "y": 1200, "w": 300, "ar": 1.5, "crop": None},
        "h": {"type": "html", "src": "site/index.html", "vw": 1280, "x": 900, "y": 1300, "w": 400, "h": 250, "pics": ["site/index.html"]},
        "m4": {"type": "model3d", "empty": True, "x": 450, "y": 1250, "w": 400, "h": 300},
    }
    if FFMPEG: items["v"] = {"path": "a/clip.mp4", "x": 1400, "y": 1220, "w": 320, "ar": 16 / 9, "crop": None}
    return {"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    (lib / "a").mkdir(parents=True); (lib / "site").mkdir(); (state / "boards").mkdir(parents=True); plugins.mkdir()
    (lib / "a/0.png").write_bytes(png(60, 40)); (lib / "site/index.html").write_text(PAGE)
    if FFMPEG:
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(lib / "a/clip.mp4")],
                       check=True, timeout=120)
    have = []
    for name, repo in PLUGINS.items():   # each plugin as its repository's last commit (other agents may be changing the working copies)
        src = ROOT.parent / repo
        if not (src / "manifest.json").is_file(): continue
        raw = subprocess.run(["git", "-C", str(src), "archive", "HEAD"], capture_output=True, check=True).stdout
        (plugins / name).mkdir(); tarfile.open(fileobj=io.BytesIO(raw)).extractall(plugins / name, filter="data"); have.append(name)
    if len(have) < 2: pytest.skip("the 3D and Dev plugins' repositories are not beside this one")
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HYIMG_PLUGINS=str(plugins), HYIMG_VIDEO_CACHE=str(tmp_path / "vcache"), PYTHONDONTWRITEBYTECODE="1",
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


BOX = "ids => ids.map(i => { const r = rectOf(i); return [Math.round(r.x), Math.round(r.y), Math.round(r.w), Math.round(r.h)]; })"


@pytest.mark.parametrize("engine", ENGINES)
def test_arrange_every_kind(server, engine):
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]) if engine == "chromium" else p.webkit.launch()
        except Exception as error: pytest.skip(f"no {engine} for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); localStorage.setItem('cv.cam.main', JSON.stringify({ x: -200, y: -200, z: .4 })); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && PLG.model3d && PLG.html && EL.get('m1') && EL.get('h')", timeout=30000)
        errors.clear()   # WebKit reports the first load's requests, cancelled by the reload, as errors
        page.mouse.click(1380, 880)
        # three 3D cards: the bar has the arrange buttons; ⌥A lays them out as a block (2 columns), one undo step
        page.evaluate("() => { sel = new Set(['m1', 'm2', 'm3']); render(); }")
        page.wait_for_selector("#handles .tidy [data-tidy=grid]")
        assert page.evaluate("() => document.querySelectorAll('#handles .tidy [data-tidy]').length") == 3
        before = page.evaluate(BOX, ["m1", "m2", "m3"])
        page.locator("#handles .tidy [data-tidy=grid]").click()
        assert page.evaluate(BOX, ["m1", "m2", "m3"]) == [[0, 0, 400, 300], [424, 0, 400, 300], [0, 324, 300, 200]]
        page.keyboard.press("Control+z"); assert page.evaluate(BOX, ["m1", "m2", "m3"]) == before
        # a picture, a video, a Dev HTML card and a 3D card: the buttons too; ⌥S puts them in a row aligned at the top
        mix = ["p", "m4", "h"] + (["v"] if "v" in page.evaluate("() => Object.keys(board.items)") else [])
        page.evaluate(f"() => {{ sel = new Set({json.dumps(mix)}); render(); }}")
        page.wait_for_selector("#handles .tidy [data-tidy=row]")
        page.mouse.move(1380, 880)
        page.keyboard.press("Alt+KeyS")
        got = page.evaluate(BOX, mix)
        assert {g[1] for g in got} == {1200}, got   # the top of the selection
        row = sorted(got)
        for a, b in zip(row, row[1:]): assert b[0] == a[0] + a[2] + 24, row
        assert row[0][0] == 0
        page.wait_for_function("() => !dirty && !saveT && !saveFlight", timeout=10000)
        saved = api(server, "/api/board?name=main")["items"]
        assert saved["h"]["y"] == 1200 and saved["m4"]["y"] == 1200
        assert not errors, errors
        browser.close()
