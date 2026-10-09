"""⇧⌘C and right click › Copy as › Image for every card that is a picture (owner 2026-10-09: «Я хочу любой объект скопировать по нажатию
⌘⇧C. Именно имею в виду video, photo, HTML — в виде картинки, или PDF в виде картинки»). Before, only a picture file could be copied.

- a picture: the file at full size with its crop
- a video: the frame at the video's own size (2560 × 1440 here; the poster the old code copied is at most 2048 px)
- a PDF: the page the card shows (page 2, green; the old code copied page 1, red)
- an HTML page, Dev Studio's card and the frames plugin's HTML frame: the page at the card's viewport at 2× (the old code copied nothing)
- the menu's «Image» row is there and enabled for each; a note has none, and ⇧⌘C on it says why

The PNG is read back from the system clipboard of Playwright's Chromium (clipboard permissions granted). Dark, Chromium only, temporary
libraries; the plugins as their repositories' last commits when they are beside this one."""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png
from test_pdf import make_pdf, COLORS, MAC

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
FFMPEG = shutil.which("ffmpeg")
PLUGINS = {"frames": "hyimg-image-studio", "dev": "hyimg-dev-studio"}
pytestmark = [pytest.mark.skipif(not FFMPEG, reason="no ffmpeg to make the test video"), pytest.mark.skipif(not MAC, reason="PDF pages are drawn by PDFKit")]
PAGE = "<!doctype html><html><head><style>html,body{margin:0;height:100%;background:rgb(20,200,40)}</style></head><body></body></html>"


def board():
    items = {
        "p": {"path": "a/0.png", "x": 0, "y": 0, "w": 300, "ar": 1.5, "crop": [0, 0, 0.5, 1]},
        "v": {"path": "a/clip.mp4", "x": 400, "y": 0, "w": 320, "ar": 16 / 9, "crop": None},
        "d": {"path": "a/doc.pdf", "x": 800, "y": 0, "w": 300, "ar": 0.75, "crop": None, "page": 2},
        "h": {"type": "html", "src": "site/index.html", "vw": 800, "x": 0, "y": 500, "w": 400, "h": 500, "pics": ["site/index.html"]},
        "f": {"type": "htmlframe", "src": "html/inv/index.html", "vw": 794, "x": 500, "y": 500, "w": 397, "h": 561.5},
        "n": {"type": "note", "text": "a note", "x": 1000, "y": 500, "w": 300, "fs": 18, "color": "yellow"},
    }
    return {"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in (lib / "a", lib / "site", lib / "html/inv", state / "boards", plugins): d.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png(60, 40)); (lib / "a/doc.pdf").write_bytes(make_pdf(COLORS))
    (lib / "site/index.html").write_text(PAGE); (lib / "html/inv/index.html").write_text(PAGE)
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=2560x1440:rate=5", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(lib / "a/clip.mp4")], check=True, timeout=120)
    for name, repo in PLUGINS.items():   # each as its repository's last commit (other agents may be changing the working copies)
        src = ROOT.parent / repo
        if not (src / "manifest.json").is_file(): continue
        raw = subprocess.run(["git", "-C", str(src), "archive", "HEAD"], capture_output=True, check=True).stdout
        (plugins / name).mkdir(); tarfile.open(fileobj=io.BytesIO(raw)).extractall(plugins / name, filter="data")
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
        yield {"port": port, "lib": lib}
    finally:
        proc.terminate(); proc.wait(5); log.close()


SCREEN = "([x, y]) => { const r = stage.getBoundingClientRect(); return [(x - cam.x) * cam.z + r.left, (y - cam.y) * cam.z + r.top]; }"
# the PNG on the system clipboard: [type, width, height, [r, g, b] at its centre], or null while there is none
CLIP = """async () => {
  let items; try { items = await navigator.clipboard.read(); } catch { return null; }
  const it = items.find(i => i.types.includes('image/png')); if (!it) return null;
  const b = await it.getType('image/png'), bm = await createImageBitmap(b), c = new OffscreenCanvas(bm.width, bm.height), g = c.getContext('2d');
  g.drawImage(bm, 0, 0); return [b.type, bm.width, bm.height, [...g.getImageData(bm.width >> 1, bm.height >> 1, 1, 1).data.slice(0, 3)]];
}"""


def clip(page, timeout=60):
    page.evaluate("() => navigator.clipboard.writeText('')")
    end = time.time() + timeout
    def got():
        while time.time() < end:
            r = page.evaluate(CLIP)
            if r: return r
            page.wait_for_timeout(150)
        return None
    return got


def select(page, id):
    page.evaluate(f"() => {{ sel = new Set(['{id}']); render(); }}")


@pytest.mark.parametrize("engine", ["chromium"])
def test_every_card_copies_as_a_png(server, engine):
    with playwright.sync_playwright() as p:
        try: browser = getattr(p, engine).launch()
        except Exception as error: pytest.skip(f"no {engine} for Playwright: {error}")
        ctx = browser.new_context(viewport={"width": 1400, "height": 1000}, color_scheme="dark", permissions=["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server['port']}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && EL.get('p') && EL.get('h') && EL.get('f') && byPath.size >= 3", timeout=20000)
        page.wait_for_function("() => pdfPages('a/doc.pdf') >= 2", timeout=15000)
        page.evaluate("() => { cam.x = -60; cam.y = -60; cam.z = .8; renderCam(); render(); }")
        page.wait_for_timeout(300)
        errors.clear()

        # the menu: «Copy as › Image» enabled on each of the five, none on the note
        for id in ["p", "v", "d", "h", "f"]:
            it = page.evaluate(f"() => board.items['{id}']")
            page.mouse.click(*page.evaluate(SCREEN, [it["x"] + 40, it["y"] + 60]), button="right")
            page.wait_for_selector("#ctx.open [data-sub=copyas]")
            page.locator("#ctx [data-sub=copyas]").hover()
            page.wait_for_selector("#ctx .hy-sub [data-act=image]")
            assert page.evaluate("() => document.querySelector('#ctx .hy-sub [data-act=image]').getAttribute('aria-disabled')") != "true", id
            page.keyboard.press("Escape"); page.keyboard.press("Escape")
        n = page.evaluate("() => board.items.n")
        page.mouse.click(*page.evaluate(SCREEN, [n["x"] + 40, n["y"] + 40]), button="right")
        page.wait_for_selector("#ctx.open [data-sub=copyas]"); page.locator("#ctx [data-sub=copyas]").hover()
        page.wait_for_function("() => document.querySelectorAll('#ctx .hy-sub [role=menuitem]').length >= 2")
        assert page.evaluate("() => !document.querySelector('#ctx .hy-sub [data-act=image]')")
        page.keyboard.press("Escape"); page.keyboard.press("Escape")

        def copied(id, key=True):
            got = clip(page)
            select(page, id)
            if key: page.keyboard.press("Control+Shift+KeyC")
            else:
                it = page.evaluate(f"() => board.items['{id}']")
                page.mouse.click(*page.evaluate(SCREEN, [it["x"] + 40, it["y"] + 60]), button="right")
                page.locator("#ctx [data-sub=copyas]").hover(); page.locator("#ctx .hy-sub [data-act=image]").click()
            r = got(); assert r, f"nothing on the clipboard for {id}"
            return r

        # a picture: its file, the crop applied (60 × 40, left half)
        assert copied("p")[:3] == ["image/png", 30, 40]
        # a video: its frame at the video's own size
        assert copied("v")[:3] == ["image/png", 2560, 1440]
        # a PDF: the card's page (2, green), from the menu
        t, w, h, rgb = copied("d", key=False)
        assert t == "image/png" and max(w, h) >= 1000 and abs(w / h - 0.75) < 0.02 and rgb[1] > 150 and rgb[0] < 90, (w, h, rgb)
        # Dev Studio's HTML card: the page at its viewport 800 × 1000 at 2×
        t, w, h, rgb = copied("h")
        assert [t, w, h] == ["image/png", 1600, 2000] and rgb[1] > 150 and rgb[0] < 60, (w, h, rgb)
        # the frames plugin's HTML frame: 794 × 1123 at 2×, nothing kept beside the page
        assert copied("f")[:3] == ["image/png", 1588, 2246]
        assert not (server["lib"] / "html/inv/.stills").exists() or not any("1588" in x.name for x in (server["lib"] / "html/inv/.stills").iterdir())
        # the note: ⇧⌘C says why, the clipboard stays as it was
        page.evaluate("() => navigator.clipboard.writeText('kept')")
        select(page, "n"); page.keyboard.press("Control+Shift+KeyC"); page.wait_for_timeout(300)
        assert page.evaluate("() => navigator.clipboard.readText()") == "kept"
        assert page.evaluate("() => hyCopyImage.why('n')") == "Only a picture, a video, a PDF, an HTML page or a 3D scene"
        assert not errors, errors
        browser.close()
    # the server's route: a time past the end gives the first frame, a picture file is not its business
    ask = lambda q: urllib.request.urlopen(f"http://127.0.0.1:{server['port']}/api/copyimage?{q}", timeout=60)
    with ask("p=a/clip.mp4&t=99") as r: assert r.headers["Content-Type"] == "image/png" and r.read()[:8] == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(urllib.error.HTTPError) as e: ask("p=a/0.png")
    assert e.value.code == 400
