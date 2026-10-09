"""A board that wakes behind another and comes in through ⌃Tab or the crumb's list (owner 2026-10-08, a screenshot of «Hyimg App» at 23 %
right after the switch: «вот такой баг при переключении»). The board's loading list «Library: 222 frames, drawing the board» stayed over the
board with its ring turning, large parts of the board were still empty and the HTML cards showed only their «HTML» plates, and the bar of a
selection far off screen floated at the top with nothing selected in view.

The page plays the app (native/Switcher.swift, BoardSleep.swift) the way app.log showed it: the page loads behind with no stars, says it is
drawn (canvasReady), the app asks it to say when what is on its screen is drawn (hyimgSwitchWait, its answer «switchShown»), gives the
selection back (hyimgSwitchRestore) and brings it in (hyimgSwitchIn prep, play). Not automation for the page (navigator.webdriver false),
so it has its loading steps as in the app. ~700 pictures at 23 % (the far view, WebGL in Chromium) and a plugin card with a picture of its
own. Chromium, dark, a temporary library.

  nice -n 10 python3 -m pytest tests/test_switch_wake.py
"""
import json, os, re, struct, subprocess, sys, tempfile, time, urllib.request, uuid, zlib
from contextlib import contextmanager
from pathlib import Path

import pytest

from test_canvas_pages import free_port

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
SHOTS = Path(os.environ.get("HY_SHOTS") or Path(tempfile.gettempdir()) / "hyimg-shots")   # screenshots never go into the repository
COLS, N = 35, 700
# the app: not automation (the loading steps show), its message bridge, the page's saved camera at 23 % over the board's top left
APP = """Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => false });
if (window === window.top) window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(JSON.parse(JSON.stringify(m))); } } } };
try { localStorage.setItem('cv.page', 'main'); localStorage.setItem('cv.cam.main', JSON.stringify({ x: -200, y: -200, z: 0.23 })); } catch {}"""
# a plugin card with a picture of its own, as an HTML card has its still
FAKE = r"""
export function register(HY) {
  HY.register("pic", { render(el) {
    if (!el.querySelector("img")) el.innerHTML = `<img alt="" src="/thumb?p=a%2F1.png&s=320&card=1" style="position:absolute;inset:0;width:100%;height:100%">`;
  } });
}
"""


def png(n):   # a picture of its own colour, so a drawn one and an empty place tell apart in the screenshots
    rgb = bytes(((n * 37) % 180 + 60, (n * 91) % 180 + 60, (n * 53) % 180 + 60))
    raw = b"".join(b"\x00" + rgb * 30 for _ in range(45))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 30, 45, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("switchwake")
    lib, state, plugins = tmp / "lib", tmp / "state", tmp / "plugins"
    for p in (lib / "a", state / "boards", plugins / "pic", tmp / "home"): p.mkdir(parents=True)
    (plugins / "pic/manifest.json").write_text(json.dumps({"title": "Pic", "canvas": "canvas.js"}))
    (plugins / "pic/canvas.js").write_text(FAKE)
    items = {}
    for n in range(N):
        (lib / "a" / f"{n}.png").write_bytes(png(n))
        items[f"i{n}"] = {"path": f"a/{n}.png", "x": n % COLS * 340, "y": n // COLS * 520, "w": 320, "ar": 2 / 3, "crop": None}
    items["c1"] = {"type": "pic", "x": 1360, "y": 1300, "w": 640, "h": 400}   # on screen at the saved camera, over two pictures' place
    for k in ("i74", "i75", "i109", "i110"): items.pop(k)
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    settings = tmp / "settings.json"; settings.write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(settings),
               HYIMG_PLUGINS=str(plugins), HYIMG_CACHE_ROOT=str(tmp / "cache"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    try:
        yield port
    finally:
        proc.terminate(); proc.wait(5); log.close()


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try: br = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        yield br
        br.close()


class Held:
    """the thumbnails held back while `on`: the pictures of a board still coming"""
    def __init__(self, page):
        self.on, self.waiting = True, []
        page.route("**/thumb?**", self.route)

    def route(self, route):
        if self.on: self.waiting.append(route)
        else: route.continue_()

    def release(self):
        self.on = False
        for r in self.waiting: r.continue_()
        self.waiting = []

    def close(self, page):   # nothing left waiting when the page goes; a request on its way when the page closes is no error
        self.on = False; self.waiting = []; page.unroute_all(behavior="ignoreErrors")


@contextmanager
def woken(browser, port, hold=False, no_plugins=False):
    """the page as the app loads a board behind the one in front, until it says it is drawn; it goes at the end, whatever happened.
    no_plugins: the board's server does not give the list of plugins"""
    ctx = browser.new_context(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    ctx.add_init_script(APP)
    page = ctx.new_page(); page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    if no_plugins: page.route(re.compile(r".*/api/plugins$"), lambda r: r.abort())
    held = Held(page) if hold else None
    try:
        page.goto(f"http://127.0.0.1:{port}/?view=canvas", wait_until="domcontentloaded")   # «load» waits for the pictures held back
        page.wait_for_function("() => (window.__sent || []).some(m => m.action === 'canvasReady')", timeout=60000)
        yield page, held
    finally:
        if held: held.close(page)
        ctx.close()


def sent(page, action):
    return [m for m in page.evaluate("() => window.__sent || []") if m.get("action") == action]


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"switch-wake-{name}.png"))


IN_FRAME = "(fn) => { const w = document.getElementById('cvFrame').contentWindow; return w.eval('(' + fn + ')()'); }"
# what is on the board's screen and not drawn yet: pictures of the far view without their cell, a card's picture still coming
MISSING = """() => { const r = stage.getBoundingClientRect(), x0 = cam.x, y0 = cam.y, x1 = cam.x + r.width / cam.z, y1 = cam.y + r.height / cam.z, out = [];
  const gl = document.getElementById('world').classList.contains('gl');
  for (const id in board.items) { const it = board.items[id]; if (it.x > x1 || it.x + it.w < x0 || it.y > y1 || it.y + itemH(it) < y0) continue;
    if (!it.type) { const s = gl ? GL.slot.get(pgKey(it)) : [96, 320].map(k => LOD.bm.get(k + ':' + pgKey(it))).find(Boolean); if (!s) out.push(id); }
    else { const el = EL.get(id), img = el && el.querySelector('img'); if (!img || !img.complete || !img.naturalWidth) out.push(id); } }
  return { far: LOD.on, gl, missing: out }; }"""


def come_in(page, sel=None):
    """the app brings the board in: its selection back, under the veil and smaller, in front, scaling up into place"""
    if sel: page.evaluate("(s) => hyimgSwitchRestore({ page: 'main', sel: s })", sel)
    page.evaluate("() => hyimgSwitchIn('prep')")
    page.wait_for_timeout(80)
    page.evaluate("() => hyimgSwitchIn('play')")


def test_the_board_switched_to_ends_its_loading_steps(browser, server):
    """the loading list goes once the board is in, as the entrance ends it; the board's controls are in"""
    with woken(browser, server) as (page, _):
        steps = page.evaluate(IN_FRAME, "() => [...document.querySelectorAll('#csteps li')].map(li => li.textContent)")
        assert steps and steps[0] == "Reading the board's pages", steps   # the list the owner saw, on its way to «drawing the board»
        come_in(page)
        page.wait_for_timeout(1300)   # the list's way out is 0.95 s
        st = page.evaluate(IN_FRAME, "() => ({ steps: !!document.getElementById('csteps'), root: document.documentElement.className })")
        shot(page, "in")
        assert not st["steps"], "the loading list stayed over the board after the switch"
        assert "preintro" not in st["root"].split() and "hy-open" not in st["root"].split(), st
        assert not {"cv-wait", "lib-wait"} & set(page.evaluate("() => document.documentElement.className").split())
        assert page.evaluate(IN_FRAME, "() => +getComputedStyle(document.getElementById('dock')).opacity") > .99   # its controls are there
        assert not page.errors, page.errors


def test_the_switch_waits_for_what_is_on_screen(browser, server):
    """the board in front keeps its place until the switched-to board has drawn what will be on screen: no half-empty board comes in"""
    with woken(browser, server, hold=True) as (page, held):
        assert page.evaluate("() => typeof hyimgSwitchWait") == "function"
        page.evaluate("() => hyimgSwitchWait(30000, 1)")   # the app gives it 5 s; here the held pictures take their time to be let go
        page.wait_for_timeout(1500)
        m = page.evaluate(IN_FRAME, MISSING)
        assert m["far"] and m["gl"] and len(m["missing"]) > 20, m   # 23 %: the far view, its pictures held back
        assert not sent(page, "switchShown"), "it said it was drawn with its pictures still coming"
        held.release()
        page.wait_for_function("() => (window.__sent || []).some(m => m.action === 'switchShown')", timeout=30000)
        assert sent(page, "switchShown") == [{"action": "switchShown", "drawn": True, "token": 1}]
        m = page.evaluate(IN_FRAME, MISSING)
        assert m["missing"] == [], m   # everything on screen drawn when it says so: every picture in its cell, the card's own picture
        come_in(page)
        page.wait_for_timeout(1300)
        shot(page, "drawn")
        assert not page.errors, page.errors


def test_the_switch_does_not_wait_for_ever(browser, server):
    """pictures that do not come hold the switch back at most a few seconds"""
    with woken(browser, server, hold=True) as (page, held):
        t0 = time.time()
        page.evaluate("() => hyimgSwitchWait(5000, 1)")
        page.wait_for_function("() => (window.__sent || []).some(m => m.action === 'switchShown')", timeout=15000)
        took = time.time() - t0
        assert 4 < took < 8 and sent(page, "switchShown") == [{"action": "switchShown", "drawn": False, "token": 1}], took
        held.release()


def test_each_wait_answers_with_its_own_token(browser, server):
    """⌃Tab to a board, Esc while it waits, ⌃Tab to it again: the app asks again (its page is there now, but maybe not drawn where it
    looks), and the answers say which wait they end, so a wait left over from the switch given up cannot bring the board in early
    (native/Switcher.swift takes only the latest, SwitchWait in BoardSleep.swift)"""
    with woken(browser, server, hold=True) as (page, held):
        page.evaluate("() => hyimgSwitchWait(30000, 1)")
        page.wait_for_timeout(400)
        page.evaluate("() => hyimgSwitchWait(30000, 2)")
        page.wait_for_timeout(400)
        assert not sent(page, "switchShown")   # neither says drawn with the pictures still held
        held.release()
        page.wait_for_function("() => (window.__sent || []).filter(m => m.action === 'switchShown').length === 2", timeout=30000)
        assert sorted(m["token"] for m in sent(page, "switchShown")) == [1, 2] and all(m["drawn"] for m in sent(page, "switchShown"))
        assert page.evaluate(IN_FRAME, MISSING)["missing"] == []


def test_a_board_without_its_plugin_list_still_says_drawn(browser, server):
    """the list of plugins did not come (the board's server failed it): the board is drawn without them, its plugin cards as plates, and
    says so; it waited the whole 5 s and the app logged it «not drawn» on every switch to it"""
    with woken(browser, server, no_plugins=True) as (page, _):
        page.wait_for_timeout(300)
        t0 = time.time()
        page.evaluate("() => hyimgSwitchWait(5000, 1)")
        page.wait_for_function("() => (window.__sent || []).some(m => m.action === 'switchShown')", timeout=15000)
        took = time.time() - t0
        assert sent(page, "switchShown") == [{"action": "switchShown", "drawn": True, "token": 1}] and took < 3, took
        assert page.evaluate(IN_FRAME, "() => !!document.querySelector('.plg[data-id=c1]')")   # the card is there, as a plate
        come_in(page)
        page.wait_for_timeout(1300)
        shot(page, "no-plugins")


def test_the_bar_of_a_selection_off_screen_goes_with_it(browser, server):
    """a woken board takes its selection back where the owner left it; its bar stands over it, not alone at the top of the board"""
    with woken(browser, server) as (page, _):
        come_in(page, sel=["i3"])
        page.wait_for_timeout(600)
        bar = "() => { const t = document.querySelector('#handles .tidy'); if (!t) return null; const r = t.getBoundingClientRect();" \
              " return { vis: getComputedStyle(t).visibility, top: Math.round(r.top), left: Math.round(r.left) }; }"
        info = "() => { const b = document.getElementById('info'); return getComputedStyle(b).display !== 'none' && getComputedStyle(b).visibility === 'visible'; }"
        near = page.evaluate(IN_FRAME, bar)
        assert near and near["vis"] == "visible", near   # i3 is on screen at the top left: its opacity bar over it
        assert page.evaluate(IN_FRAME, info) is True   # and its Info card
        # centred on it once the switch's motion is over (laid while the world was smaller, it stood 16 px off until the camera moved)
        mid = page.evaluate(IN_FRAME, "() => { const it = board.items.i3, t = document.querySelector('#handles .tidy').getBoundingClientRect();"
                                      " return [(it.x + it.w / 2 - cam.x) * cam.z + stage.getBoundingClientRect().left, t.left + t.width / 2]; }")
        assert abs(mid[0] - mid[1]) < 2, mid
        page.evaluate(IN_FRAME, "() => HY.camera(cam.x, cam.y + 8000, cam.z)")   # the selection far above the screen now
        page.wait_for_timeout(300)
        far = page.evaluate(IN_FRAME, bar)
        shot(page, "sel-off")
        assert far is None or far["vis"] == "hidden", far   # no bar floating at the top with nothing selected in view
        assert page.evaluate(IN_FRAME, info) is False   # nor its Info card (the owner's screenshot: «image-raw.html · HTML · 1440×900»)
        page.evaluate(IN_FRAME, "() => HY.camera(cam.x, cam.y - 8000, cam.z)")
        page.wait_for_timeout(300)
        back = page.evaluate(IN_FRAME, bar)
        assert back and back["vis"] == "visible" and abs(back["top"] - near["top"]) < 2 and abs(back["left"] - near["left"]) < 2, (near, back)
        assert page.evaluate(IN_FRAME, info) is True   # the Info card back with it
        assert not page.errors, page.errors
