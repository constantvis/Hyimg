"""A double click is never swallowed by the info panel the first click opens (owner 2026-10-07, via the coordinator: a picture that lay where
the panel comes up did not enter the Image mode, its second click landed on the panel). The panel shows at once on a click; for a double
click's time (0.5 s) after it comes up, or turns to another selection, it lets the pointer through to the card under it. Every kind of card
lies where the panel opens, under the pointer: a picture (Image, a stand-in mode), a video (crop and trim), a PDF (crop), a sticky note
(its text), a plugin card (its own double click: the 3D studio, an HTML page, an image frame). Chromium and WebKit."""
import json, os, shutil, socket, subprocess, sys, time, urllib.request, uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_pdf import COLORS, make_pdf, png   # noqa: E402

FFMPEG = shutil.which("ffmpeg")
FAKE = r"""
let open = null;
export function register(HY) {
  HY.register("fake", { render(el, it) { el.textContent = "fake"; }, dblclick(id) { window.PLG_DBL = (window.PLG_DBL || []).concat(id); },
    info: () => ({ name: "Fake card", meta: "a plugin card" }) });
  HY.mode("image", { label: "Image", order: 10, icon: "<svg width=16 height=16></svg>", title: "Image studio", hint: "Select one image",
    isOpen: () => !!open, target: ids => ids.length === 1 && HY.isPic(HY.board.items[ids[0]]) ? ids[0] : null,
    enter: id => { open = id; window.ENTERED = (window.ENTERED || []).concat(id); HY.dock(document.createElement("span")); },
    leave: () => { open = null; HY.dock(null); } });
}
"""
W = 300   # every card 300 wide, laid out far apart; each in turn is brought under the spot where the panel opens
ITEMS = {"i0": {"path": "a/one.png", "x": 0, "y": 0, "w": W, "ar": 1.5, "crop": None},
         "p0": {"path": "a/doc.pdf", "x": 1000, "y": 0, "w": W, "ar": 0.75, "crop": None},
         "n0": {"type": "note", "text": "note", "x": 2000, "y": 0, "w": W, "fs": 24, "size": 2, "h": 0, "color": "yellow", "reach": None, "to": []},
         "f0": {"type": "fake", "x": 3000, "y": 0, "w": W, "h": 200}}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in (lib / "a", state / "boards", plugins / "fake"): d.mkdir(parents=True)
    (lib / "a/one.png").write_bytes(png()); (lib / "a/doc.pdf").write_bytes(make_pdf(COLORS[:1]))
    items = dict(ITEMS)
    if FFMPEG:
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(lib / "a/clip.mp4")], check=True, timeout=120)
        items["v0"] = {"path": "a/clip.mp4", "x": 4000, "y": 0, "w": W, "ar": 16 / 9, "crop": None}
    (plugins / "fake/manifest.json").write_text(json.dumps({"title": "Fake", "canvas": "canvas.js"})); (plugins / "fake/canvas.js").write_text(FAKE)
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"})); (tmp_path / "home").mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_PLUGINS=str(plugins), HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    port = free_port(); log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    try:   # the server goes even when the test fails or is interrupted
        yield port, sorted(items)
    finally:
        proc.terminate(); proc.wait(5); log.close()


# what each kind's double click does, checked on the page
DONE = {"i0": "(window.ENTERED || []).includes('i0')", "p0": "cropState && cropState.id === 'p0'",
        "n0": "!!document.querySelector('.note[data-id=n0] textarea')", "f0": "(window.PLG_DBL || []).includes('f0')",
        "v0": "cropState && cropState.id === 'v0' && cropState.vid"}
# the spot inside the panel's place (right: 12, top: 60, 300 wide), on the card's left part, clear of its corner marks and a video's pill
SPOT = (1300 - 12 - 300 + 60, 100)


def reset(page):
    page.keyboard.press("Escape"); page.keyboard.press("Escape")
    page.evaluate("() => { if (MODES && MODES.open !== 'board') MODES.enter('board'); if (cropState) endCrop(); sel = new Set(); render(); }")
    page.wait_for_timeout(700)   # the panel is gone and no longer fresh


def under_spot(page, id):
    """the card's left part at SPOT: its top left 20 px left of and 60 px above it"""
    page.evaluate(f"""() => {{ const it = board.items['{id}']; cam.z = 1; cam.x = it.x - ({SPOT[0]} - 20); cam.y = it.y - ({SPOT[1]} - 60); renderCam(); render();
      const r = document.querySelector('[data-id={id}]').getBoundingClientRect(); cam.x += r.left - ({SPOT[0]} - 20); cam.y += r.top - ({SPOT[1]} - 60); renderCam(); render(); }}""")   # the stage's own offset
    page.wait_for_timeout(300)


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_the_panel_never_takes_the_second_click(server, engine):
    port, ids = server
    with playwright.sync_playwright() as p:
        try: browser = getattr(p, engine).launch()
        except Exception as error: pytest.skip(f"no {engine} for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1300, "height": 850}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/canvas.html")
        page.wait_for_function("() => typeof PLGST !== 'undefined' && PLGST.length === 1 && PLGST[0].ok && byPath.has('a/doc.pdf')", timeout=20000)
        if "v0" in ids: page.wait_for_function("() => (byPath.get('a/clip.mp4') || {}).kind === 'video'", timeout=30000)
        for id in ids:
            reset(page); under_spot(page, id)
            # what the pointer meets there: the panel first, or the card (a plugin card lets its events through to the board, which looks under it)
            hit = f"() => {{ const L = document.elementsFromPoint({SPOT[0]}, {SPOT[1]}), e = L[0]; return e && e.closest('#info') ? 'panel' : L.some(x => x.closest && x.closest('[data-id={id}]')) && !L.slice(0, L.findIndex(x => x.closest && x.closest('[data-id={id}]'))).some(x => x.closest('#info, #handles, #dock, #crumb')) ? 'card' : (e ? e.tagName + '.' + e.className : null); }}"
            assert page.evaluate(hit) == "card", (id, page.evaluate(hit), page.evaluate(f"() => {{ const e = document.querySelector('[data-id={id}]'); return e && [e.className, JSON.stringify(e.getBoundingClientRect()), getComputedStyle(e).display, getComputedStyle(e).visibility]; }}"))
            # a single click: the panel is there at once, over the very spot, and lets the pointer through for now
            page.mouse.click(*SPOT)
            assert page.evaluate("() => getComputedStyle(document.getElementById('info')).display") == "block", id
            box = page.locator("#info").bounding_box()
            assert box["x"] <= SPOT[0] <= box["x"] + box["width"] and box["y"] <= SPOT[1] <= box["y"] + box["height"], (id, box)
            assert page.evaluate(hit) == "card", id
            # after a double click's time it takes clicks again
            page.wait_for_timeout(650)
            assert page.evaluate(hit) == "panel", id
            # a double click from nothing selected: the panel comes up after the first click, the second still reaches the card
            reset(page); under_spot(page, id)
            page.mouse.dblclick(*SPOT)
            try: page.wait_for_function(f"() => {DONE[id]}", timeout=8000)
            except Exception: raise AssertionError((id, page.evaluate("() => [[...sel], !!cropState, window.ENTERED, window.PLG_DBL, document.getElementById('info').className]")))
        assert not errors, errors
        browser.close()
