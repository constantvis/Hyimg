"""The board's mode switch and the generic pieces plugins build on (owner 2026-10-06: «in the bottom menu a toggle like in Figma: Board,
Image, Dev, 3D»; «dev studio and html are a plugin too»): ui/modes.js with HY.mode, HY.placeAs for a library file a plugin makes its
own card of, the view hook, a plugin's file kinds in the library and the sandboxed page route. A fake plugin in a temp folder stands in
for the real ones (they have their own tests); nothing of the owner's is touched."""
import io, json, os, socket, subprocess, sys, time, urllib.error, urllib.request, uuid
from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FAKE = r"""
const TYPE = "fake";
let open = null;
export function register(HY) {
  HY.register(TYPE, {
    render(el, it) { el.textContent = it.src; },
    view(id, el, px, moving) { el.dataset.px = Math.round(px); el.dataset.moving = moving ? "1" : "0"; },
    dblclick(id) { open = id; HY.dock(Object.assign(document.createElement("span"), { innerHTML: '<button class="wide pri" data-a="done">Done</button>', onclick: () => { open = null; HY.dock(null); } })); },
  });
  HY.placeAs(p => /\.fake$/.test(p) ? { type: TYPE, src: p, ar: 2 } : null);
  HY.mode("fake", { label: "Fake", order: 5, icon: "<svg width=16 height=16></svg>", title: "Fake for the card", hint: "Select a fake card",
    isOpen: () => !!open, target: ids => ids.length === 1 && HY.board.items[ids[0]] && HY.board.items[ids[0]].type === TYPE ? ids[0] : null,
    enter: id => PLG_FAKE_ENTER(id), leave: () => { open = null; HY.dock(null); } });
  window.PLG_FAKE_ENTER = id => PLG[TYPE].dblclick(id);
}
"""


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def png():
    b = io.BytesIO(); Image.new("RGB", (40, 60), (90, 90, 90)).save(b, "PNG"); return b.getvalue()


@pytest.fixture
def srv(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for p in (lib / "a", state / "boards", plugins / "fake"): p.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png()); (lib / "a/x.fake").write_text("<p>fake</p>"); (lib / "a/page.html").write_text("<html><head><title>T</title></head><body>hi</body></html>")
    (tmp_path / "outside.txt").write_text("secret")
    (plugins / "fake/manifest.json").write_text(json.dumps({"title": "Fake", "canvas": "canvas.js", "kinds": {"fake": [".fake"], "image": [".html"], "video2": [".png"]}, "pageScript": "page.js"}))
    (plugins / "fake/canvas.js").write_text(FAKE); (plugins / "fake/page.js").write_text("window.FAKE_PAGE = 1;")
    items = {"i0": {"path": "a/0.png", "x": 0, "y": 0, "w": 200, "ar": 2 / 3, "crop": None},
             "f1": {"type": "fake", "src": "a/x.fake", "x": 300, "y": 0, "w": 300, "h": 150}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    (tmp_path / "home").mkdir()   # a home of its own: the plugins in the real ~/Library/Application Support/Hyimg/plugins stay out
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_PLUGINS=str(plugins),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    try:   # the server goes even when the test fails or is interrupted
        yield port, lib
    finally:
        proc.terminate(); proc.wait(5); log.close()


def get(port, path, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {})) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_plugin_kinds_and_sandboxed_pages(srv):
    port, lib = srv
    kinds = {i["path"]: i.get("kind") for i in json.loads(get(port, "/api/items")[2])}
    # its own kind is listed; a kind may not take over the app's names or extensions (image, .png), nor an extension nobody claims (.html)
    assert kinds == {"a/0.png": None, "a/x.fake": "fake"}
    assert get(port, "/thumb?p=a/x.fake&s=320")[0] == 200   # no preview of its own: Quick Look's or the grey card
    base = json.loads(get(port, "/api/sandbox")[2])["base"]
    st, h, body = get(port, base + "a/page.html?hyp=fake")
    assert st == 200 and h["Content-Security-Policy"] == "sandbox allow-scripts" and body.startswith(b"<html><head><script src=\"" + base.encode() + b"~hyp/fake\"></script><title>")
    assert get(port, base + "~hyp/fake")[2] == b"window.FAKE_PAGE = 1;"
    for bad in ("../outside.txt", "%2e%2e/outside.txt", "a/%2e%2e/%2e%2e/outside.txt", "/etc/hosts", "~/x", "~hyp/missing", "a/page.html%00.png"):
        assert get(port, base + bad)[0] == 404, bad
    assert get(port, "/sandbox/x/a/page.html")[0] == 404
    assert get(port, base + "a/page.html", {"Origin": "http://example.com"})[0] == 403
    st, h, _ = get(port, base + "a/page.html", {"Origin": "null"})
    assert st == 200 and h["Access-Control-Allow-Origin"] == "null"
    assert get(port, "/api/sandbox", {"Origin": "null"})[0] == 403 and get(port, "/lib/a/page.html", {"Origin": "null"})[0] == 403
    assert (lib / "a/page.html").read_text().startswith("<html><head><title>")


@pytest.mark.parametrize("browser", ["chromium", "webkit"])
def test_mode_switch(srv, browser):
    port, lib = srv
    with sync_playwright() as p:
        br = getattr(p, browser).launch(); page = br.new_page(viewport={"width": 1400, "height": 900})
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/canvas.html")
        page.wait_for_function("() => typeof PLGST !== 'undefined' && PLGST.length === 1 && PLGST[0].ok", timeout=20000)
        state = lambda: page.evaluate("[...document.querySelectorAll('#modes > button')].map(b => b.dataset.mode + ':' + b.getAttribute('aria-pressed') + ':' + b.getAttribute('aria-disabled') + ':' + b.dataset.tip)")
        # Board first and chosen; the plugin's mode after it, dimmed, its tooltip says what enables it
        assert state() == ["board:true:false:Board", "fake:false:true:Select a fake card"]
        assert page.evaluate("getComputedStyle(document.querySelector('#modes [data-mode=fake]')).opacity") == "0.38"
        page.evaluate("(() => { sel = new Set(['f1']); render(); })()"); page.wait_for_timeout(100)
        assert state()[1] == "fake:false:false:Fake"
        assert page.get_attribute("#modes [data-mode=fake]", "aria-description") == "Fake for the card"
        # the segment enters; the editor's dock takes over, the switch stays and shows it; Board leaves it
        page.click("#modes [data-mode=fake]"); page.wait_for_timeout(100)
        assert state()[0].startswith("board:false") and state()[1].startswith("fake:true")
        assert page.evaluate("document.getElementById('dock').classList.contains('plg-mode')") and page.is_visible("#modes") and not page.is_visible("#bundo")
        page.click("#modes [data-mode=board]"); page.wait_for_timeout(100)
        assert state()[0].startswith("board:true") and not page.evaluate("document.getElementById('dock').classList.contains('plg-mode')")
        # opened and closed by other means (a double click, its own Done): the switch follows
        page.dblclick(".plg[data-id=f1]"); page.wait_for_timeout(100)
        assert state()[1].startswith("fake:true")
        page.click("#dock .plgdock [data-a=done]"); page.wait_for_timeout(100)
        assert state()[0].startswith("board:true")
        # the view hook: the card's width on screen, 0 off it, and whether the board moves
        page.evaluate("(() => { sel = new Set(); render(); HY.camera(0, 0, 2, false); })()"); page.wait_for_timeout(100)
        assert page.get_attribute(".plg[data-id=f1]", "data-px") == "600"
        page.evaluate("HY.camera(100000, 0, 1, false)"); page.wait_for_timeout(100)
        assert page.get_attribute(".plg[data-id=f1]", "data-px") == "0"
        # a dropped library file of the plugin's becomes its card (placeAs), placed like a picture with the plugin's shape
        page.evaluate("HY.camera(0, 0, 1, false)")
        page.evaluate("""(() => { const dt = new DataTransfer(); dt.setData('text/x-frame', 'a/x.fake'); const r = stage.getBoundingClientRect();
          stage.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, clientX: r.left + 500, clientY: r.top + 500, bubbles: true, cancelable: true })); })()""")
        page.wait_for_function("() => Object.values(board.items).filter(it => it.src === 'a/x.fake').length === 2")
        it = page.evaluate("Object.values(board.items).filter(it => it.src === 'a/x.fake').pop()")
        assert it["type"] == "fake" and it["w"] == 320 and it["h"] == 160 and "ar" not in it and "path" not in it
        assert not errors, errors
        br.close()


# where the switch is and how it looks (owner 2026-10-06, a Figma screenshot: «look how Figma's switch is made, it's on the right and only
# the icon; active»): the dock's last thing after a hairline, an editor's buttons too; icons alone at every width, each as big as the
# dock's icon buttons; the chosen one a filled tile, its icon in the selection's blue; a tooltip with the name over the segment
GEO = """() => { const d = document.getElementById('dock').getBoundingClientRect(), w = document.getElementById('modesw'), m = document.getElementById('modes');
  const vis = [...document.getElementById('dock').querySelectorAll('button')].filter(b => b.offsetWidth && !m.contains(b));
  const last = Math.max(...vis.map(b => b.getBoundingClientRect().right)), mr = m.getBoundingClientRect(), sep = w.querySelector('.msep').getBoundingClientRect();
  const bs = [...m.querySelectorAll(':scope > button')].filter(b => b.offsetWidth), on = m.querySelector('[aria-pressed=true]'), ic = document.getElementById('bundo');
  return { right: d.right - mr.right, after: mr.left - last, sep: [sep.left > last, sep.right <= mr.left, sep.width], words: bs.map(b => b.innerText.trim()).join(''),
    sizes: bs.map(b => [Math.round(b.offsetWidth), Math.round(b.offsetHeight)]), gh: m.offsetHeight, ic: ic ? [ic.offsetWidth, ic.offsetHeight] : null,
    onColor: getComputedStyle(on).color, sel: getComputedStyle(document.documentElement).getPropertyValue('--sel').trim(),
    thumb: getComputedStyle(m.querySelector('.st')).backgroundColor, group: getComputedStyle(m).backgroundColor, rad: getComputedStyle(bs[0]).borderTopLeftRadius,
    thumbBox: (() => { const t = m.querySelector('.st').getBoundingClientRect(), o = on.getBoundingClientRect(); return Math.abs(t.left - o.left) + Math.abs(t.width - o.width); })() }; }"""


def rgb(c):   # "#3b82f6", "rgb(59, 130, 246)" or "color(srgb .23 .51 .96 / .5)" -> (r, g, b)
    from PIL import ImageColor
    if c.startswith("#"): return ImageColor.getrgb(c)[:3]
    inner = c[c.index("(") + 1:c.index(")")].split("/")[0]
    if c.startswith("color("): return tuple(round(float(x) * 255) for x in inner.split()[1:4])
    return tuple(int(float(x)) for x in inner.replace(",", " ").split()[:3])


@pytest.mark.parametrize("theme,shape", [("dark", "round"), ("light", "pro")])
def test_switch_is_icons_at_the_right_end_like_figmas(srv, theme, shape):
    port, lib = srv
    with sync_playwright() as p:
        br = p.chromium.launch()
        for w in (1400, 760):
            page = br.new_page(viewport={"width": w, "height": 800})
            errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{port}/canvas.html")
            page.evaluate(f"() => {{ localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.theme', '{theme}'); localStorage.setItem('cv.shape', '{shape}'); }}")
            page.goto(f"http://127.0.0.1:{port}/canvas.html")
            page.wait_for_function("() => typeof PLGST !== 'undefined' && PLGST.length === 1", timeout=20000); page.wait_for_timeout(500)
            g = page.evaluate(GEO)
            assert g["words"] == "", g   # no words at any width
            assert 0 < g["right"] < 12 and g["after"] > 0 and g["sep"][0] and g["sep"][1] and g["sep"][2] == 1, g   # last, after a hairline
            # the group as tall as the dock's icon buttons (34), its segments 3 px in on every side (the thumb inset, ui/look.css --hy-seg-pad):
            # 32 × 28 each (owner 2026-10-06: the chosen thumb touched the track's top and bottom)
            assert all(s == [32, 28] for s in g["sizes"]) and g["ic"][1] == 34 and g["group"] and g["gh"] == 34, g
            assert rgb(g["onColor"]) == rgb(g["sel"]), g   # the chosen icon in the selection's blue
            assert g["thumbBox"] < 1 and rgb(g["thumb"]) != rgb(g["group"]), g   # on a filled tile of its own colour
            assert g["rad"] == ("999px" if shape == "round" else "5px"), g   # round, or in «pro» the row radius less the thumb's 3 px inset (concentric)
            assert page.evaluate("document.getElementById('dock').offsetHeight") <= 50
            # the tooltip: the name over the segment; on a disabled one, also what enables it
            r = page.evaluate("() => { const r = document.querySelector('#modes [data-mode=fake]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, r.top]; }")
            page.mouse.move(r[0], r[1]); page.wait_for_function("() => document.getElementById('modetip').classList.contains('on')")
            page.wait_for_timeout(350)
            t = page.evaluate("() => { const t = document.getElementById('modetip'), b = t.getBoundingClientRect(); return [t.textContent, b.bottom, b.left + b.width / 2, getComputedStyle(t).opacity]; }")
            assert t[0] == "FakeSelect a fake card" and t[1] <= r[2] - 6 and t[3] == "1", t
            page.mouse.move(r[0] - 44, r[1]); page.wait_for_timeout(100)   # Board: at once (one was just shown), the name alone
            assert page.evaluate("document.getElementById('modetip').textContent") == "Board"
            page.mouse.move(700, 300); page.wait_for_timeout(300)
            assert page.evaluate("getComputedStyle(document.getElementById('modetip')).opacity") == "0"
            # an editor owns the dock: its buttons first, the switch still at the right end
            page.evaluate("(() => { sel = new Set(['f1']); render(); })()"); page.wait_for_timeout(100)
            page.click("#modes [data-mode=fake]"); page.wait_for_timeout(200)
            g = page.evaluate(GEO)
            assert page.is_visible("#dock .plgdock [data-a=done]") and 0 < g["right"] < 12 and g["after"] > 0, g
            assert not errors, errors
            page.close()
        br.close()


# A board always comes in Board mode (owner 2026-10-07: «зашел на страницу, где мой wire, и там почему-то открылось 3D ... По дефолту он
# должен всегда заходить в board режим»). The Mac app keeps a board's page while Home is in front and brings it back with hyimgPrep and
# hyimgIntro (native/main.swift openSession): an editor left open closes then; a page loaded afresh opens none.
def test_a_board_comes_back_in_board_mode(srv):
    port, lib = srv
    with sync_playwright() as p:
        br = p.chromium.launch(); page = br.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/canvas.html")
        page.wait_for_function("() => typeof PLGST !== 'undefined' && PLGST.length === 1 && PLGST[0].ok", timeout=20000)
        enter = "() => { sel = new Set(['f1']); render(); return MODES.enter('fake'); }"
        assert page.evaluate(enter) and page.evaluate("MODES.open") == "fake" and page.is_visible("#dock .plgdock [data-a=done]")
        page.evaluate("() => { hyimgPrep(); hyimgIntro(); }")   # back from Home, as the app does it
        assert page.evaluate("MODES.open") == "board" and not page.is_visible("#dock .plgdock [data-a=done]")
        assert page.evaluate("document.querySelector('#modes [aria-pressed=true]').dataset.mode") == "board"
        assert page.evaluate(enter) and page.evaluate("MODES.open") == "fake"
        page.reload()
        page.wait_for_function("() => typeof PLGST !== 'undefined' && PLGST.length === 1 && PLGST[0].ok", timeout=20000); page.wait_for_timeout(300)
        assert page.evaluate("MODES.open") == "board" and not page.is_visible("#dock .plgdock [data-a=done]")
        assert not errors, errors
        br.close()


STUDIO3D = ROOT.parent / "hyimg-3d-studio"


@pytest.mark.skipif(not (STUDIO3D / "manifest.json").exists(), reason="no hyimg-3d-studio beside this repository")
def test_the_3d_studio_is_not_open_when_the_board_comes_back(tmp_path):
    """the owner's case: 3D entered on a card, Home, the board again (and a reload): Board mode, none of the studio's panels"""
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in (lib, state / "boards", plugins): d.mkdir(parents=True)
    (plugins / "3d").symlink_to(STUDIO3D)
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"})); (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_PLUGINS=str(plugins),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        with sync_playwright() as p:
            br = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            page = br.new_page(viewport={"width": 1500, "height": 950}, color_scheme="dark")
            errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
            ready = "() => typeof PLGST !== 'undefined' && PLGST.some(p => p.name === '3d' && p.ok)"
            page.goto(f"http://127.0.0.1:{port}/canvas.html"); page.wait_for_function(ready, timeout=30000)
            page.click("button[title^='3D scene']")   # the dock's «3D scene»
            page.wait_for_function("() => Object.values(board.items).some(i => i.type === 'model3d' && i.scene)", timeout=30000)
            cid = page.evaluate("() => Object.keys(board.items).find(k => board.items[k].type === 'model3d')")
            live = "() => MODES.open === '3d' && !!document.querySelector('.plg-live') && !!document.querySelector('.m3ui')"
            gone = "() => MODES.open === 'board' && !document.querySelector('.plg-live') && !document.querySelector('.m3ui')"
            assert page.evaluate(f"() => MODES.enter('3d', ['{cid}'])"); page.wait_for_function(live, timeout=60000)
            page.evaluate("() => { hyimgPrep(); hyimgIntro(); }")   # Home, then the board again: the app kept its page
            page.wait_for_function(gone, timeout=20000)
            assert page.evaluate("document.querySelector('#modes [aria-pressed=true]').dataset.mode") == "board"
            assert page.evaluate(f"() => MODES.enter('3d', ['{cid}'])"); page.wait_for_function(live, timeout=60000)
            page.reload(); page.wait_for_function(ready, timeout=30000); page.wait_for_timeout(1500)
            assert page.evaluate(gone), "a reload opens the board in Board mode"
            assert not errors, errors
            br.close()
    finally:
        proc.terminate(); proc.wait(5); log.close()
