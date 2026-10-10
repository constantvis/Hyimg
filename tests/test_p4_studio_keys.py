"""The Studios' keys as one table (owner decisions 2026-10-10, П4 S-25…S-29, S-61; docs/process.md §7 «Таблица поведения как данные»):
«place × key → action» for Image Studio, 3D Studio and Dev Studio, read by one test that presses each key in each Studio, the real plugins
beside this repository (../hyimg-image-studio, ../hyimg-3d-studio, ../hyimg-dev-studio). Chromium, the dark theme, our own temporary
server and library, never the ports 4180–4184.

  FIELDS  Esc in a field: a name or a value goes back («back»), what is written on the canvas stays («kept»); ↵ applies; ⌘↵ applies and
          is the Studio's primary action («primary»: Save, or Done in Dev Studio)
  LEAVE   with a change made: the last Esc and the Board segment keep the work, only Cancel asks, with Hyimg's one question
  HINTS   the Hint bar as a Studio opens: V Select, C Annotation, Esc / ⌘↵ with the primary action's word
  CAMERA  every Studio flies its card between its own panels

  nice -n 10 python3 -m pytest -q tests/test_p4_studio_keys.py
"""
import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
PIL = pytest.importorskip("PIL.Image")

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = {"frames": ROOT.parent / "hyimg-image-studio", "3d": ROOT.parent / "hyimg-3d-studio", "dev": ROOT.parent / "hyimg-dev-studio"}

#   studio, place,         key,          what happens to the typed words
FIELDS = [
    ("image", "layer name", "Escape", "back"), ("image", "layer name", "Enter", "kept"), ("image", "layer name", "Meta+Enter", "primary"),
    ("image", "number", "Escape", "back"), ("image", "number", "Enter", "kept"),
    ("3d", "object name", "Escape", "back"), ("3d", "object name", "Enter", "kept"), ("3d", "prompt", "Escape", "kept"),
    ("3d", "object name", "Meta+Enter", "primary"),
    ("dev", "tree text", "Escape", "kept"), ("dev", "tree tag", "Escape", "back"), ("dev", "attribute", "Escape", "back"),
    ("dev", "number", "Escape", "back"), ("dev", "tree text", "Meta+Enter", "primary"),
]
#   studio, the way out, what happens to a change made
LEAVE = [("image", "esc", "kept"), ("image", "board", "kept"), ("image", "cancel", "asks"),
         ("3d", "esc", "kept"), ("3d", "board", "kept"), ("3d", "cancel", "asks"),
         ("dev", "esc", "kept"), ("dev", "board", "kept")]
PRIMARY = {"image": "Save", "3d": "Save", "dev": "Done"}

SCENE = {"format": "hyimg-scene/1", "rev": 1, "render": {"x": 1600, "y": 1600}, "world": {"color": [0.18, 0.18, 0.18], "strength": 1},
         "objects": [{"id": "box1", "name": "Box", "src": {"type": "prim", "shape": "box", "size": [0.3, 0.3, 0.3]}, "loc": [0, 0, 0.15], "rot": [1, 0, 0, 0],
                      "scale": [1, 1, 1], "ai": "old prompt"}],
         "lights": [{"id": "l1", "name": "Key", "type": "area", "loc": [-0.5, -0.5, 0.6], "rot": [1, 0, 0, 0], "color": [1, 1, 1], "power": 20, "size": 0.5}],
         "cameras": [{"id": "cam1", "name": "Front", "loc": [0, -1.4, 0.4], "rot": [0.7071, 0.7071, 0, 0], "lens": 50, "sensor": 36, "fit": "AUTO", "clip": [0.01, 100]}],
         "active_camera": "cam1"}
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Keys</title>
<style>body { margin: 0; font: 16px system-ui; background: #fff; } h1 { margin: 24px; font-size: 32px; border-radius: 4px; }</style></head>
<body><header id="top"><h1 id="title">Hello world</h1></header><p>Text</p></body></html>
"""
ITEMS = {"a1": {"path": "pics/a.png", "x": 0, "y": 0, "w": 600, "ar": 1.5, "crop": None},
         "c": {"type": "model3d", "scene": "3d/scenes/a/scene.json", "camera": "cam1", "x": 0, "y": 700, "w": 500, "h": 500},
         "e1": {"type": "html", "src": "site/keys.html", "vw": 1280, "x": 800, "y": 0, "w": 640, "h": 400, "pics": ["site/keys.html"]}}


def free_port():
    with socket.socket() as s: s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


@contextlib.contextmanager
def serve(home):
    missing = [k for k, p in PLUGINS.items() if not (p / "manifest.json").is_file()]
    if missing: pytest.skip(f"the plugins beside this repository are missing: {missing}")
    lib, state, plugins = home / "lib", home / "state", home / "plugins"
    for d in (lib / "pics", lib / "site", lib / "3d/scenes/a", state / "boards", plugins): d.mkdir(parents=True)
    img = PIL.new("RGB", (600, 400), (200, 60, 40)); img.paste((40, 90, 200), (300, 0, 600, 400)); img.save(lib / "pics/a.png")
    (lib / "site/keys.html").write_text(PAGE); (lib / "3d/scenes/a/scene.json").write_text(json.dumps(SCENE))
    for k, p in PLUGINS.items(): (plugins / k).symlink_to(p)   # in pytest's own temporary folder, as the plugins' tests do
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": ITEMS, "groups": {}, "removed": {}}))
    (home / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(home / "settings.json"),
               HYIMG_CACHE_ROOT=str(home / "cache"), HYIMG_PLUGINS=str(plugins), PYTHONDONTWRITEBYTECODE="1", HY_TEST_ONLY_PLUGINS="1")
    port = free_port(); log = open(home / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(150):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, lib
    finally:
        proc.terminate(); proc.wait(5); log.close()


def board(browser, port):
    page = browser.new_page(viewport={"width": 1500, "height": 950}, color_scheme="dark")
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url); page.evaluate("() => { localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.keyhint', 'always'); }"); page.goto(url)
    page.wait_for_function("() => typeof PLGST !== 'undefined' && ['frames', '3d', 'dev'].every(n => PLGST.some(p => p.name === n && p.ok))", timeout=30000)
    page.evaluate("() => { cam.x = -100; cam.y = -100; cam.z = 0.6; renderCam(); render(); }"); page.wait_for_timeout(800)
    return page, errors


def blur(page): page.evaluate("document.activeElement && document.activeElement.blur(); window.focus()")


# ---- each Studio: open it, its fields, its state, close it without keeping anything ----------------------------------------------------
class Image:
    def __init__(self, page): self.page = page; self.fr = None

    def open(self):
        p = self.page; p.evaluate("() => { sel = new Set(['a1']); render(); }"); p.dblclick(".plg[data-id=a1], .it[data-id=a1]")
        p.wait_for_function("() => window.__frames && __frames.ED && __frames.ED.win && __frames.ED.win.__ed && __frames.ED.win.__ed.ready", timeout=30000)
        # the open studio's page: one that left and still writes its work (hyimg-image-studio awaywork.js, 2026-10-10) is hidden, .away
        self.fr = p.query_selector(".ifed.on:not(.away) iframe").content_frame(); self.fr.wait_for_timeout(900)
        self.v0 = p.evaluate("() => board.items.a1.v || 0"); return self

    def is_open(self): return self.page.evaluate("() => !!(window.__frames && __frames.ED)")

    def hint(self): return self.fr.evaluate("() => [...document.querySelectorAll('hy-keyhint')].map(h => h.textContent).join(' | ')")

    def change(self, tag): self.fr.evaluate("() => hyEdK.edit('Opacity Change', () => { const n = __ed.root.find(x => x.type === 'pixel'); n.opacity = n.opacity === 55 ? 56 : 55; })")

    def kept(self, tag): return self.page.evaluate("() => board.items.a1.v || 0") > self.v0   # saved: a new version of the frame

    def close(self):
        if not self.is_open(): return
        self.fr.evaluate("() => { __ed.S.savedVer = __ed.S.ver; __ed.S.savedTop = __ed.S.undo[__ed.S.undo.length - 1] || null; __ed.cancelFrame(); }")
        self.page.wait_for_function("() => !__frames.ED", timeout=10000); self.page.wait_for_timeout(500)

    def field(self, place, text):
        fr, p = self.fr, self.page
        if place == "layer name":   # a layer of its own (the picture's is its base, locked)
            lid = fr.evaluate("() => { hyEdK.newLayer(); return hyEdK.one().id; }"); fr.wait_for_timeout(300)
            b = fr.locator(f".lr[data-id='{lid}'] .nm").bounding_box()
            p.mouse.dblclick(b["x"] + 8, b["y"] + b["height"] / 2); fr.wait_for_selector(".lr .nm input", timeout=4000)
            self.read = lambda: fr.evaluate(f"() => __ed.byId('{lid}').name")
            was = self.read(); p.keyboard.press("Meta+a"); p.keyboard.type(text); return was
        if place == "number":   # a layer of its own, its first number in Properties (the picture's base layer is locked)
            fr.evaluate("() => { hyEdK.newLayer(); __ed.showPanel('props'); }"); fr.wait_for_timeout(300)
            inp = fr.locator("#pbody input[inputmode=decimal]").first; inp.focus(); fr.wait_for_timeout(100)
            self.read = lambda: fr.evaluate("() => document.querySelector('#pbody input[inputmode=decimal]').value")
            was = self.read(); p.keyboard.press("Meta+a"); p.keyboard.type("37"); return was
        raise KeyError(place)

    def leave(self, way):
        if way == "esc":
            for _ in range(4):
                if not self.is_open(): break
                self.fr.evaluate("() => { document.activeElement && document.activeElement.blur(); window.focus(); }"); self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(700)
        elif way == "board": self.page.click("#modes button[data-mode=board]")
        elif way == "cancel": self.fr.click("#topr [data-a=cancel]")

    def question(self):
        self.fr.wait_for_selector("#hyConfirm.on", timeout=5000)
        return self.fr.evaluate("() => [document.querySelector('#hyConfirm .hc-t').textContent, [...document.querySelectorAll('#hyConfirm button')].map(b => b.textContent.trim()),"
                                " document.activeElement && document.activeElement.textContent.trim()]")


class Studio3D:
    DOC = "() => import('/plugins/3d/engine.js').then(m => m.docOf('3d/scenes/a/scene.json'))"

    def __init__(self, page, lib): self.page = page; self.lib = lib

    def open(self):
        p = self.page; p.dblclick(".plg[data-id=c]", position={"x": 40, "y": 40})
        p.wait_for_selector(".m3r .hy-slider", timeout=60000); p.wait_for_timeout(1500)
        if p.locator(".m3pause [data-go]").count(): p.click(".m3pause [data-go]")
        return self

    def is_open(self): return self.page.evaluate("() => import('/plugins/3d/engine.js').then(m => m.isLive())")

    def hint(self): return self.page.evaluate("() => [...document.querySelectorAll('hy-keyhint')].map(h => h.textContent).join(' | ')")

    def pick(self):
        self.page.evaluate("() => import('/plugins/3d/engine.js').then(m => m.liveSelect(['box1']))")
        self.page.wait_for_selector(".dk .dialkit-text-input:not([inert])", timeout=5000); self.page.wait_for_timeout(300)

    def change(self, tag):
        self.pick(); f = self.page.locator(".dk .dialkit-text-input:not([inert])").first; f.click(); self.page.keyboard.press("Meta+a"); self.page.keyboard.type(tag)
        self.page.keyboard.press("Enter"); self.page.wait_for_timeout(500)

    def file(self): return json.loads((self.lib / "3d/scenes/a/scene.json").read_text())

    def kept(self, tag): return self.file()["objects"][0]["name"] == tag

    def close(self):
        if not self.is_open(): return
        if not self.page.locator("#hyConfirm.on").count():   # Cancel, and Discard when it asks
            blur(self.page); self.page.click("hy-studio-actions [data-a=cancel]"); self.page.wait_for_timeout(500)
        if self.page.locator("#hyConfirm.on").count(): self.page.click("#hyConfirm [data-a=ok]")
        self.page.wait_for_timeout(800)

    def field(self, place, text):
        p = self.page; self.pick()
        k = 0 if place == "object name" else -1   # the name first, the prompt (its words for a generation) last
        T = p.locator(".dk .dialkit-text-input:not([inert])"); f = T.nth(0) if k == 0 else T.last
        key = "name" if place == "object name" else "ai"
        self.read = lambda: p.evaluate(f"() => import('/plugins/3d/engine.js').then(m => m.docOf('3d/scenes/a/scene.json').objects[0].{key} || '')")
        was = self.read(); f.click(); p.keyboard.press("Meta+a"); p.keyboard.type(text); return was

    def leave(self, way):
        if way == "esc":
            for _ in range(4):
                if not self.is_open(): break
                blur(self.page); self.page.keyboard.press("Escape"); self.page.wait_for_timeout(800)
        elif way == "board": self.page.click("#modes button[data-mode=board]")
        elif way == "cancel": self.page.click(".m3ui hy-studio-actions [data-a=cancel], hy-studio-actions [data-a=cancel]")

    def question(self):
        self.page.wait_for_selector("#hyConfirm.on", timeout=5000)
        return self.page.evaluate("() => [document.querySelector('#hyConfirm .hc-t').textContent, [...document.querySelectorAll('#hyConfirm button')].map(b => b.textContent.trim()),"
                                  " document.activeElement && document.activeElement.textContent.trim()]")


class Dev:
    def __init__(self, page, lib): self.page = page; self.lib = lib; self.f = lib / "site/keys.html"

    def open(self):
        p = self.page; p.dblclick(".plg[data-id=e1]")
        p.wait_for_function("() => __dev.D && __dev.D.tree && __dev.D.rev", timeout=30000); p.wait_for_timeout(1200)
        return self

    def is_open(self): return self.page.evaluate("() => !!__dev.D")

    def hint(self): return self.page.evaluate("() => [...document.querySelectorAll('hy-keyhint')].map(h => h.textContent).join(' | ')")

    def h1(self):
        p = self.page
        p.evaluate("""() => { const path = n => n.t === 'h1' ? [n] : (n.k || []).map(k => { const r = path(k); return r && [n, ...r]; }).find(Boolean);
          const ps = path(__dev.D.tree.root); ps.slice(0, -1).forEach(n => __dev.D.open.add(n.i)); __dev.select(ps.at(-1).i, true); }""")
        p.wait_for_function("() => { const d = __dev.D.detail; return d && d.t === 'h1' && d.src && d.src.rev === __dev.D.rev; }", timeout=8000)

    def edit_mode(self):
        if not self.page.evaluate("__dev.D.edit"): self.page.evaluate("__dev.setEdit(true)"); self.page.wait_for_timeout(300)

    def change(self, tag):
        self.edit_mode(); self.h1(); self.page.dblclick(".dvt .row.sel .dtx"); self.page.wait_for_selector(".dvt .row .dvin")
        self.page.fill(".dvt .row .dvin", tag); self.page.press(".dvt .row .dvin", "Enter"); self.page.wait_for_timeout(1500)

    def kept(self, tag): return tag in self.f.read_text()

    def close(self):
        if self.is_open(): self.page.evaluate("() => __dev.closeDev()"); self.page.wait_for_timeout(800)

    def field(self, place, text):
        p = self.page; self.edit_mode(); self.h1()
        if place in ("tree text", "tree tag"):
            p.dblclick(".dvt .row.sel " + (".dtx" if place == "tree text" else ".dtg")); p.wait_for_selector(".dvt .row .dvin")
            self.read = lambda: self.f.read_text()
            was = self.read(); p.fill(".dvt .row .dvin", text if place == "tree text" else "section"); return was
        if place == "attribute":
            sel = ".dvr .dattr .dva[data-a=id] .dva-v"; p.wait_for_selector(sel)
            self.read = lambda: (self.f.read_text(), p.evaluate(f"() => document.querySelector('{sel}') ? document.querySelector('{sel}').value : ''"))
            was = self.read(); p.fill(sel, "headline"); return was
        if place == "number":
            sel = ".dvr input[data-n=border-radius]"; p.wait_for_selector(sel); p.click(sel)
            self.read = lambda: (self.f.read_text(), p.evaluate(f"() => document.querySelector('{sel}') ? document.querySelector('{sel}').value : ''"))
            was = self.read(); p.keyboard.press("ArrowUp"); p.keyboard.press("ArrowUp"); p.wait_for_timeout(700); return was
        raise KeyError(place)

    def leave(self, way):
        if way == "esc":
            for _ in range(5):
                if not self.is_open(): break
                blur(self.page); self.page.keyboard.press("Escape"); self.page.wait_for_timeout(600)
        elif way == "board": self.page.click("#modes button[data-mode=board]")


def studios(page, lib): return {"image": Image(page), "3d": Studio3D(page, lib), "dev": Dev(page, lib)}


def test_the_studios_keys_by_one_table(tmp_path):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page, errors = board(browser, port)
        S = studios(page, lib); bad = []
        # HINTS and CAMERA, as each Studio opens
        for k in ("3d", "dev", "image"):
            s = S[k].open(); page.wait_for_timeout(900); h = s.hint()
            for word in ("Select", "Annotation", "Esc", PRIMARY[k]):
                if word not in h: bad.append(f"{k}: the Hint bar has no «{word}»: {h!r}")
            if k != "image":
                card = page.evaluate("id => { const r = document.querySelector(`.plg[data-id=\"${id}\"]`).getBoundingClientRect(); return [r.left, r.right]; }", "c" if k == "3d" else "e1")
                panes = page.evaluate("q => [...document.querySelectorAll(q)].map(e => { const r = e.getBoundingClientRect(); return [r.left, r.right]; })",
                                      ".m3l, .m3r" if k == "3d" else ".dvl, .dvr")
                left, right = min(panes, key=lambda r: r[0]), max(panes, key=lambda r: r[0])
                if not (card[0] >= left[1] - 1 and card[1] <= right[0] + 1): bad.append(f"{k}: the card is not between the panels: {card} {panes}")
            s.close()
        # FIELDS
        for k, place, key, want in FIELDS:
            s = S[k].open(); was = s.field(place, "Typed words")
            page.keyboard.press(key); page.wait_for_timeout(1500)
            if want == "primary":
                for _ in range(30):
                    if not s.is_open(): break
                    page.wait_for_timeout(500)
                if s.is_open(): bad.append(f"{k} {place} {key}: the Studio stayed open, ⌘↵ is its {PRIMARY[k]}")
            else:
                now = s.read()
                if (now == was) != (want == "back"): bad.append(f"{k} {place} {key}: want {want}, was {str(was)[:80]!r}, now {str(now)[:80]!r}")
            s.close()
        # LEAVE
        for n, (k, way, want) in enumerate(LEAVE):
            tag = f"Kept {n}"; s = S[k].open(); s.change(tag); s.leave(way); page.wait_for_timeout(1500)
            if want == "kept":
                for _ in range(30):   # a Save writes for a while
                    if not s.is_open(): break
                    page.wait_for_timeout(500)
                page.wait_for_timeout(800)
                for _ in range(30):   # Image Studio writes after it closed (owner decision 2026-10-10, hyimg-image-studio awaywork.js)
                    if s.is_open() or s.kept(tag): break
                    page.wait_for_timeout(500)
                if s.is_open(): bad.append(f"{k} {way}: the Studio is still open")
                elif not s.kept(tag): bad.append(f"{k} {way}: the change was not kept")
            else:
                q = s.question()
                if not (q[0].startswith("Save changes to") and q[1] == ["Discard", "Keep editing", "Save"] and q[2] == "Keep editing"):
                    bad.append(f"{k} {way}: not Hyimg's one question: {q}")
                page.keyboard.press("Escape"); page.wait_for_timeout(400)
                if not s.is_open(): bad.append(f"{k} {way}: Esc in the question left the Studio")
            s.close()
        assert not bad, "\n".join(bad)
        assert not errors, errors
        browser.close()
