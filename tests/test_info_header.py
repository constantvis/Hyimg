"""The Info card's header (owner 2026-10-09 on round 15's «Info · the header», ♥ with one comment: on the group's «для групп я бы не
делал»; round 14: «лайк справа сверху, и там же кнопка Открыть ... и какая-то информация: размер, разрешение, формат, если видео — то его
данные», «этот блок абсолютно бессмысленный, картинку мы уже выделили и видим — нужно компактно упаковать»).

- one selected picture, video, 3D scene, HTML page or copy (an instance of a picture) has the compact header: its name, one line of facts
  read from the file (picture: size in px, format, bytes, ratio; video: size, length, fps, codec, sound, bytes; a plugin's card: its info),
  ♥, Open and «…» at the top right; a video has its trim bar under it
- ♥ likes the file, Open opens it (the viewer for a picture, the Studio for a card), a copy's button goes to its original, «…» opens the
  thing's own menu; the body's File section no longer repeats the facts
- a group has no Info at all, as when nothing is selected (owner 2026-10-10 on round 16: «да не, вообще picker for group не нужен»)
Chromium, dark theme, a temporary library, the plugins from their repositories' last commits. HY_SHOTS=<folder> keeps screenshots."""
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
from contextlib import contextmanager
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
PLUGINS = {"frames": "hyimg-image-studio", "3d": "hyimg-3d-studio", "dev": "hyimg-dev-studio"}
FFMPEG = shutil.which("ffmpeg")
PAGE = "<!doctype html><html><head><title>Site</title></head><body><h1>A page</h1></body></html>"
CAM = {"lens": 50, "sensor": 36, "sensor_h": 24, "fit": "AUTO", "shift": [0, 0], "clip": [0.01, 100], "loc": [0.3, -0.5, 0.2], "rot": [1, 0, 0, 0]}


def board():
    items = {
        "p": {"path": "a/form.png", "x": 0, "y": 0, "w": 240, "ar": 1122 / 1402, "crop": None},
        "c": {"path": "a/form.png", "x": 280, "y": 0, "w": 240, "ar": 1122 / 1402, "crop": None},   # a copy of p: an instance
        "s": {"type": "model3d", "scene": "3d/scenes/s1/scene.json", "camera": "c1", "x": 0, "y": 400, "w": 400, "h": 300},
        "h": {"type": "html", "src": "site/index.html", "vw": 1440, "ar": 1.6, "pics": ["site/index.html"], "x": 440, "y": 400, "w": 400, "h": 250},
        "q": {"path": "a/x.png", "x": 0, "y": 800, "w": 200, "ar": 1, "crop": None},
    }
    if FFMPEG: items["v"] = {"path": "a/clip.mp4", "x": 560, "y": 0, "w": 320, "ar": 16 / 9, "crop": None, "trim": [0.5, 2]}
    groups = {"g": {"title": "Series", "x": -20, "y": 780, "w": 260, "h": 260, "members": ["q"]}}
    return {"schema": 1, "revision": 1, "items": items, "groups": groups, "removed": {}}


@contextmanager
def world(tmp):
    """a temporary library and its server: (port, lib)"""
    lib, state, plugins = tmp / "lib", tmp / "state", tmp / "plugins"
    for d in (lib / "a", lib / "site", lib / "3d/scenes/s1", state / "boards", plugins, tmp / "home"): d.mkdir(parents=True)
    (lib / "a/form.png").write_bytes(png(1122, 1402)); (lib / "a/x.png").write_bytes(png(64, 64))
    (lib / "a/form.json").write_text(json.dumps({"model": "Test model", "prompt": "a chrome form"}))
    (lib / "site/index.html").write_text(PAGE)
    (lib / "3d/scenes/s1/scene.json").write_text(json.dumps({"format": "hyimg-scene/1", "rev": 1, "objects": [], "lights": [],
                                                            "cameras": [dict(CAM, id="c1", name="Front"), dict(CAM, id="c2", name="Side")], "active_camera": "c1"}))
    if FFMPEG:
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24", "-f", "lavfi", "-i", "sine=frequency=440",
                        "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(lib / "a/clip.mp4")], check=True, timeout=120)
    for name, repo in PLUGINS.items():   # each plugin as its repository's last commit (other agents may be changing the working copies)
        src = ROOT.parent / repo
        if not (src / "manifest.json").is_file(): pytest.skip(f"{repo} is not beside this repository")
        raw = subprocess.run(["git", "-C", str(src), "archive", "HEAD"], capture_output=True, check=True).stdout
        (plugins / name).mkdir(); tarfile.open(fileobj=io.BytesIO(raw)).extractall(plugins / name, filter="data")
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp / "settings.json"), HYIMG_PLUGINS=str(plugins), HYIMG_VIDEO_CACHE=str(tmp / "vcache"), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(150):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, lib
    finally:
        proc.terminate(); proc.wait(5); log.close()


def open_board(p, port):
    try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    page.errors = []; page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{port}/canvas.html")
    page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
      localStorage.setItem('cv.cam.main', JSON.stringify({ x: -60, y: -80, z: .5 })); }""")
    page.reload()
    page.wait_for_function("() => typeof BOARD !== 'undefined' && PLG.model3d && PLG.html && ['p', 's', 'h'].every(i => EL.get(i))", timeout=30000)
    page.wait_for_function("() => typeof byPath !== 'undefined' && byPath.get('a/form.png')", timeout=20000)
    page.wait_for_timeout(500)
    return browser, page


def shot(page, name):
    d = os.environ.get("HY_SHOTS")
    if d: Path(d).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(d) / name))


# what the Info card shows for one selected thing: its kind, the name, the facts, which buttons are shown, the header's height
READ = """async id => { sel = new Set([id]); render(); await new Promise(r => setTimeout(r, 50)); render();
  const b = $('#info'), h = b.querySelector('.ih'), vis = s => { const e = $(s); return !!e && getComputedStyle(e).display !== 'none' && e.offsetWidth > 0; };
  return { kind: b.dataset.kind || '', hx: b.classList.contains('hx'), name: $('#iN').textContent, facts: $('#iM').textContent,
    fav: vis('#iFav'), favOn: $('#iFav').classList.contains('on'), open: vis('#iOpen') ? $('#iOpen').textContent : '', more: vis('#iMore'),
    trim: vis('#iTrim') ? $('#iTrim').textContent : '', head: Math.round(h.getBoundingClientRect().height), media: h.querySelectorAll('img, video, canvas').length,
    file: [...document.querySelectorAll('#iNotes .isec')].map(s => s.textContent).find(t => t.startsWith('File')) || '' }; }"""


def size(n):   # the board's fmtSize
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{round(n / 1024)} KB"


def until(page, js, arg=None, t=15000):
    page.wait_for_function(js, arg=arg, timeout=t)


def test_info_header_for_each_kind(tmp_path):
    with world(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        browser, page = open_board(p, port)
        # a picture: name, «1122 × 1402 · PNG · 4 KB · 4:5», ♥ Open …; the facts once (not again in the body's File section)
        until(page, "() => { sel = new Set(['p']); render(); return /1122 × 1402/.test($('#iM').textContent); }")
        a = page.evaluate(READ, "p")
        assert a["kind"] == "image" and a["hx"] and a["name"] == "form.png", a
        assert a["facts"] == f"1122 × 1402 · PNG · {size((lib / 'a/form.png').stat().st_size)} · 4:5", a
        assert a["fav"] and a["open"] == "Open" and a["more"] and not a["trim"], a
        assert a["head"] <= 58 and a["media"] == 0, a   # compact, no preview: the picture is selected and seen
        assert "1122" not in a["file"] and "KB" not in a["file"] and "Test model" in a["file"], a["file"]
        shot(page, "1-image.png")
        # a copy of the picture: an instance, its original one click away
        until(page, "() => { sel = new Set(['c']); render(); return /1122 × 1402/.test($('#iM').textContent); }")
        c = page.evaluate(READ, "c")
        assert c["kind"] == "instance" and c["name"] == "form.png" and c["facts"] == "copy of “form.png” · 2 of 2 · 1122 × 1402", c
        assert c["open"] == "To the original" and c["fav"] and c["more"], c   # ♥ on a copy too, the same file (owner decision 2026-10-10, P4 B-37)
        shot(page, "2-instance.png")
        page.click("#iOpen"); until(page, "() => sel.size === 1 && sel.has('p')")
        # a video: its data from the server's probe and the trim bar
        if FFMPEG:
            until(page, "() => { sel = new Set(['v']); render(); return /fps/.test($('#iM').textContent); }")
            v = page.evaluate(READ, "v")
            assert v["kind"] == "video" and v["name"] == "clip.mp4", v
            assert v["facts"] == f"640 × 360 · 0:03 · 24 fps · H.264 · sound · {size((lib / 'a/clip.mp4').stat().st_size)}", v
            assert v["trim"] == "0:00 – 0:02 of 0:03" and v["fav"] and v["open"] == "Open" and v["more"], v
            shot(page, "3-video.png")
        # a 3D scene and an HTML page: the plugin's info in the same header, Open is their Studio
        until(page, "() => { sel = new Set(['s']); render(); return /cameras/.test($('#iM').textContent); }")
        s = page.evaluate(READ, "s")
        assert s["kind"] == "3d" and s["name"] == "3D scene" and s["facts"].startswith("0 objects, 0 lights, 2 cameras"), s
        assert s["open"] == "Open" and s["more"] and s["head"] <= 58, s
        shot(page, "4-3d.png")
        h = page.evaluate(READ, "h")
        assert h["kind"] == "html" and h["name"] == "index.html" and "1440×900" in h["facts"] and "site/index.html" in h["facts"], h
        assert h["fav"] and h["open"] == "Open" and h["more"], h
        shot(page, "5-html.png")
        # a group: no Info panel at all; a picture after it has its header again
        assert page.evaluate("() => { sel = new Set(['g']); render(); return getComputedStyle($('#info')).display; }") == "none"
        shot(page, "6-group.png")
        assert page.evaluate("() => { sel = new Set(['p']); render(); return getComputedStyle($('#info')).display; }") == "block"
        assert not page.errors, page.errors
        browser.close()


def test_info_header_buttons(tmp_path):
    with world(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        browser, page = open_board(p, port)
        page.evaluate("() => { window.__opened = []; window.open = u => { __opened.push(u); return null; }; }")
        # ♥ likes the picture: pink, written in its json; again takes it off
        page.evaluate("() => { sel = new Set(['p']); render(); }")
        page.click("#iFav")
        until(page, "() => $('#iFav').classList.contains('on')")
        for _ in range(100):
            if json.loads((lib / "a/form.json").read_text()).get("feedback", {}).get("fav"): break
            time.sleep(0.05)
        assert json.loads((lib / "a/form.json").read_text())["feedback"]["fav"] is True
        assert json.loads((lib / "a/form.json").read_text())["model"] == "Test model"   # the json keeps the rest
        page.click("#iFav"); until(page, "() => !$('#iFav').classList.contains('on')")
        # Open shows the picture
        page.click("#iOpen"); until(page, "() => __opened.length === 1")
        assert page.evaluate("() => __opened[0]") == "/img?p=a%2Fform.png"
        # «…» is the thing's own menu, under the button
        page.click("#iMore"); until(page, "() => $('#ctx').classList.contains('open')")
        assert "Show in Finder" in page.inner_text("#ctx")
        m, b = page.evaluate("() => [$('#ctx').getBoundingClientRect().top, $('#iMore').getBoundingClientRect().bottom]")
        assert m >= b - 1, (m, b)
        page.keyboard.press("Escape"); until(page, "() => !$('#ctx').classList.contains('open')")
        # Open on an HTML page and on a 3D scene: their Studio
        for card, studio in (("h", "dev"), ("s", "3d")):
            page.evaluate("id => { sel = new Set([id]); render(); }", card)
            page.click("#iOpen")
            until(page, "k => document.documentElement.dataset.studio === k", studio, t=20000)
            page.evaluate("() => MODES.enter('board')"); until(page, "() => !document.documentElement.dataset.studio", t=20000)   # Done
        assert not page.errors, page.errors
        browser.close()
