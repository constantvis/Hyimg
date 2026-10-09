"""The shared pieces every editor mode gets from the board (owner 2026-10-08), with a fake plugin in a temp folder (the real modes have their
tests in hyimg-dev-studio/tests/test_mode_lift.py), Chromium, the dark theme:

- ui/editlift.js through ui/modes.js: entering a mode hides the board's selection around its card (outline, corner squares) and lifts it
  (a shadow that fades in, the setting «Тени» off as it is by default); leaving sets it down and the selection comes back
- ui/framezoom.js: a pinch (⌃ with the wheel) over a live page of the library's origin zooms the board, not the page; a click in the page
  gives it the zoom (nothing drawn on the card), a click outside gives it back; ⌥ sends one pinch to the page

  nice -n 10 python3 -m pytest tests/test_edit_lift.py
"""
import json, os, subprocess, sys, time, urllib.request, uuid
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from test_modes import free_port, png

ROOT = Path(__file__).resolve().parents[1]
FAKE = r"""
const TYPE = "fake";
let open = null, Z = null;
export function register(HY) {
  HY.register(TYPE, {
    render(el, it) {
      if (el.querySelector("iframe")) return;
      el.innerHTML = `<iframe src="/lib/a/page.html" style="position:absolute;left:0;top:0;width:640px;height:400px;border:0;transform-origin:0 0"></iframe>`;
      el.firstChild.style.transform = `scale(${it.w / 640})`;
    },
    dblclick(id) {
      open = id; const el = document.querySelector(`.plg[data-id="${id}"]`);
      Z = hyFrameZoom.attach(el.querySelector("iframe"), { card: el, local: true });
      HY.dock(Object.assign(document.createElement("span"), { innerHTML: '<button class="wide pri" data-a="done">Done</button>', onclick: () => leave() }));
      HY.modeChanged();
    },
  });
  const leave = () => { open = null; if (Z) Z.detach(); Z = null; HY.dock(null); HY.modeChanged(); };
  HY.mode("fake", { label: "Fake", order: 5, icon: "<svg width=16 height=16></svg>", title: "Fake", hint: "Select a fake card",
    isOpen: () => !!open, target: ids => ids.length === 1 && HY.board.items[ids[0]] && HY.board.items[ids[0]].type === TYPE ? ids[0] : null,
    enter: id => PLG[TYPE].dblclick(id), leave });
}
"""
PAGE = """<!doctype html><html><body style="margin:0;background:#2a6;height:3000px"><h1>Page</h1>
<script>window.__n = 0; addEventListener('wheel', e => { if (e.ctrlKey) { __n++; e.preventDefault(); } }, { passive: false });</script></body></html>"""


@pytest.fixture
def srv(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for p in (lib / "a", state / "boards", plugins / "fake"): p.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png()); (lib / "a/page.html").write_text(PAGE)
    (plugins / "fake/manifest.json").write_text(json.dumps({"title": "Fake", "canvas": "canvas.js"}))
    (plugins / "fake/canvas.js").write_text(FAKE)
    items = {"i0": {"path": "a/0.png", "x": -300, "y": 0, "w": 200, "ar": 2 / 3, "crop": None},
             "f1": {"type": "fake", "x": 0, "y": 0, "w": 480, "h": 300}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    (tmp_path / "home").mkdir()
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_PLUGINS=str(plugins),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    try:
        yield port
    finally:
        proc.terminate(); proc.wait(5); log.close()


STATE = """() => { const el = document.querySelector('.plg[data-id=f1]'), cs = getComputedStyle(el), L = document.getElementById('hylift');
  return { outline: cs.outlineStyle, mode: document.documentElement.dataset.hyEdit || '', shadow: document.documentElement.dataset.shadow,
    on: !!L && L.classList.contains('on'), seen: !!L && getComputedStyle(L).visibility, far: L ? getComputedStyle(L.querySelector('.far')).opacity : '',
    corners: [...document.querySelectorAll('#handles > .h')].filter(h => getComputedStyle(h).opacity !== '0').length }; }"""


def test_mode_lifts_its_card_and_page_zoom_goes_to_the_board(srv):
    port = srv
    with sync_playwright() as p:
        br = p.chromium.launch(); page = br.new_page(viewport={"width": 1300, "height": 850}, color_scheme="dark")
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/canvas.html")
        page.wait_for_function("() => typeof PLGST !== 'undefined' && PLGST.length === 1 && PLGST[0].ok", timeout=20000)
        page.evaluate("HY.camera(-400, -200, 1, false)")
        page.evaluate("(() => { sel = new Set(['f1']); render(); })()"); page.wait_for_timeout(300)
        s = page.evaluate(STATE)
        assert s["outline"] == "solid" and s["corners"] == 4 and not s["on"] and s["mode"] == "" and s["shadow"] == "0", s
        # entering: no outline, no corner squares to see, the lift on after its 420 ms, «Тени» still off
        page.click("#modes [data-mode=fake]")
        page.wait_for_function("() => document.getElementById('hylift') && document.getElementById('hylift').classList.contains('on')")
        page.wait_for_timeout(600)
        s = page.evaluate(STATE)
        assert s["outline"] == "none" and s["corners"] == 0 and s["mode"] == "fake" and s["on"] and s["seen"] == "visible" and s["far"] == "1", s
        assert page.evaluate("document.getElementById('hylift').nextElementSibling.id") == "handles"
        r = page.evaluate("""(() => { const a = document.getElementById('hylift').getBoundingClientRect(), b = document.querySelector('.plg[data-id=f1]').getBoundingClientRect();
          return [a.x - b.x, a.y - b.y, a.width - b.width, a.height - b.height]; })()""")
        assert max(abs(v) for v in r) < 1, r
        # the page's zoom: a pinch over it zooms the board at the pointer, the page never sees it
        fr = next(f for f in page.frames if f.url.endswith("/lib/a/page.html")); fr.wait_for_function("() => typeof __n === 'number'")
        b = page.locator(".plg[data-id=f1] iframe").bounding_box(); mid = (b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        def pinch(dy, mods=("Control",)):
            page.mouse.move(*mid); [page.keyboard.down(m) for m in mods]; page.mouse.wheel(0, dy); page.wait_for_timeout(300); [page.keyboard.up(m) for m in reversed(mods)]
        z0 = page.evaluate("HY.cam.z"); pinch(-100)
        assert page.evaluate("HY.cam.z") > z0 * 1.05 and fr.evaluate("__n") == 0
        page.evaluate("HY.camera(-400, -200, 1, false)"); page.wait_for_timeout(200)
        pinch(-100, ("Alt", "Control")); assert page.evaluate("HY.cam.z") == 1 and fr.evaluate("__n") == 1   # ⌥: that one to the page
        page.mouse.click(*mid); page.wait_for_function("() => document.querySelector('.plg[data-id=f1]').classList.contains('hy-page-own')")
        page.wait_for_timeout(300)   # nothing drawn on the card for it (owner 2026-10-08: «обводка эта дурацкая вокруг»)
        assert page.evaluate("""(() => { const e = document.querySelector('.plg[data-id=f1]'), b = getComputedStyle(e, '::before'), c = getComputedStyle(e);
          return [c.outlineStyle, c.boxShadow, b.content === 'none' || b.boxShadow === 'none'] })()""") == ["none", "none", True]
        pinch(-100); assert page.evaluate("HY.cam.z") == 1 and fr.evaluate("__n") == 2   # entered: the page's own
        page.mouse.click(5, 300); page.wait_for_function("() => !document.querySelector('.plg[data-id=f1]').classList.contains('hy-page-own')")
        # leaving: set down, the selection around it again
        page.click("#dock .plgdock [data-a=done]")
        page.wait_for_function("() => !document.documentElement.dataset.hyEdit && getComputedStyle(document.getElementById('hylift')).visibility === 'hidden'", timeout=3000)
        page.evaluate("(() => { sel = new Set(['f1']); render(); })()"); page.wait_for_timeout(200)
        s = page.evaluate(STATE)
        assert s["outline"] == "solid" and s["corners"] == 4 and not s["on"], s
        assert not errors, errors
        br.close()
