"""A double click on a picture enters the dock's Image mode instead of the crop (owner 2026-10-07: «давай при двойном нажатии на картинку
мы будем в режим картинки переходить, а не trim, trim добавим в меню сверху, которое появляется»). The core asks the mode switch to enter
"image" for the picture (ui/modes.js enter); a fake plugin stands in for the frames plugin, which has its own test of the studio
(hyimg-frames tests/test_picture_dblclick.py). With no Image mode that takes the picture the crop opens, as before; a PDF keeps its crop.
The crop of a picture is «Crop» on the bar over it. The video's double click (crop and trim) is in test_video.py. Chromium and WebKit."""
import json, os, socket, subprocess, sys, time, urllib.request, uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_pdf import COLORS, make_pdf, png   # noqa: E402

FAKE = r"""
let open = null;
export function register(HY) {
  HY.mode("image", { label: "Image", order: 10, icon: "<svg width=16 height=16></svg>", title: "Image studio", hint: "Select one image",
    isOpen: () => !!open,
    target: ids => !window.NO_IMAGE && ids.length === 1 && HY.isPic(HY.board.items[ids[0]]) ? ids[0] : null,
    enter: id => { open = id; window.ENTERED = (window.ENTERED || []).concat(id); HY.dock(document.createElement("span")); },
    leave: () => { open = null; HY.dock(null); } });
}
"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in (lib / "a", state / "boards", plugins / "fake"): d.mkdir(parents=True)
    (lib / "a/one.png").write_bytes(png()); (lib / "a/doc.pdf").write_bytes(make_pdf(COLORS[:1]))
    (plugins / "fake/manifest.json").write_text(json.dumps({"title": "Fake", "canvas": "canvas.js"})); (plugins / "fake/canvas.js").write_text(FAKE)
    items = {"i0": {"path": "a/one.png", "x": 0, "y": 0, "w": 300, "ar": 1.5, "crop": None},
             "p0": {"path": "a/doc.pdf", "x": 400, "y": 0, "w": 200, "ar": 0.75, "crop": None}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    (tmp_path / "home").mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_PLUGINS=str(plugins), HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    port = free_port(); log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    try:   # the server goes even when the test fails or is interrupted
        yield port
    finally:
        proc.terminate(); proc.wait(5); log.close()


def center(page, id):
    return page.evaluate("id => { const r = document.querySelector(`.it[data-id=${id}]`).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", id)


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_double_click_on_a_picture_enters_image_and_the_crop_is_on_the_bar(server, engine):
    with playwright.sync_playwright() as p:
        try: browser = getattr(p, engine).launch()
        except Exception as error: pytest.skip(f"no {engine} for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1300, "height": 850}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof PLGST !== 'undefined' && PLGST.length === 1 && PLGST[0].ok && byPath.has('a/doc.pdf')", timeout=20000)
        page.evaluate("() => { cam.x = -100; cam.y = -100; cam.z = 1; renderCam(); render(); }"); page.wait_for_timeout(300)
        pressed = lambda: page.evaluate("() => [...document.querySelectorAll('#modes > button')].filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.mode)")
        # the picture: Image, for it, with it selected; no crop
        page.mouse.dblclick(*center(page, "i0"))
        page.wait_for_function("() => (window.ENTERED || []).join() === 'i0'")
        assert page.evaluate("() => !cropState && [...sel].join()") == "i0" and pressed() == ["image"]
        page.click("#modes [data-mode=board]"); page.wait_for_function("() => !document.getElementById('dock').classList.contains('plg-mode')")
        # a PDF keeps its double click: the crop
        page.mouse.dblclick(*center(page, "p0"))
        page.wait_for_function("() => cropState && cropState.id === 'p0'")
        assert page.evaluate("() => (window.ENTERED || []).join()") == "i0" and pressed() == ["board"]
        page.keyboard.press("Escape"); page.wait_for_function("() => !cropState")
        # no Image mode that takes the picture (no frames plugin): the crop, as before
        page.evaluate("() => { window.NO_IMAGE = true; sel = new Set(); render(); }")
        page.mouse.dblclick(*center(page, "i0"))
        page.wait_for_function("() => cropState && cropState.id === 'i0'")
        page.keyboard.press("Escape"); page.wait_for_function("() => !cropState")
        # «Crop» on the bar over the selected picture, its key in the tooltip and on the button, enters the crop
        page.evaluate("() => { sel = new Set(['i0']); render(); }"); page.wait_for_timeout(350)
        b = page.locator(".tidy > button[data-crop]")
        assert b.count() == 1 and b.get_attribute("title") == "Crop · C" and b.locator("> kbd").inner_text() == "C"
        b.click(); page.wait_for_function("() => cropState && cropState.id === 'i0' && !cropState.vid")
        page.keyboard.press("Escape")
        # the shortcuts panel tells the double click and C apart
        keys = page.evaluate("() => document.getElementById('keys').textContent.replace(/\\s+/g, ' ')")
        assert "double-click an image: the Image mode; a video: crop and trim" in keys and "C crop; a video: crop and trim" in keys, keys
        assert not errors, errors
        browser.close()
