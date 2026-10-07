"""The runtime design audit (owner 2026-10-06: «делай юнит тесты, тесты ui, валидаторы, консистентный design валидатор»; what he kept
finding by eye: sliders and dropdowns with different radii, a focus ring around a slider, card marks of different sizes overlapping on
small cards, the selection bar under the library, the filter window climbing over the library's top, key hints over button labels).

Every page of the app on a temporary library (pictures, a video, a PDF, a PSD, a glb, an html page; a liked, a cropped, a copied, a graded
and a noted card, a group, a note) with the three plugins mounted from the sibling repositories: the board, the library beside it and
wide, Home, the image studio, the 3D studio and Dev studio; dark and light, round and pro, 1000 and 1600 px wide. design/audit.js
measures the real elements against design/contract.json ("runtime"); the board's card marks at three zooms.

What is known lives in design/baseline.json ("runtime": page, check and key; no coordinates), so the suite is green today and fails on a
NEW finding. HY_AUDIT_UPDATE=1 writes what this run found as the known ones (run the whole file for that). HY_AUDIT_QUICK=1 runs one
look (dark, round, 1600) per page. HY_AUDIT_REPORT=<file> writes every finding of the run as JSON.

  python3 -m pytest tests/test_design_audit.py
"""
import hashlib, json, os, shutil, socket, struct, subprocess, sys, time, urllib.request, uuid
from collections import defaultdict
from pathlib import Path

import pytest

from test_media_files import psd
from test_pdf import COLORS, make_pdf, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
REPOS = ROOT.parent
CONTRACT = json.loads((ROOT / "design/contract.json").read_text(encoding="utf-8"))
BASELINE = ROOT / "design/baseline.json"
AUDIT_JS = (ROOT / "design/audit.js").read_text(encoding="utf-8")
HOME = (ROOT / "review/home.html").as_uri()
FFMPEG = shutil.which("ffmpeg")
QUICK = os.environ.get("HY_AUDIT_QUICK") == "1"
LOOKS = [("dark", "round", 1600)] if QUICK else [(t, s, w) for t in ("dark", "light") for s in ("round", "pro") for w in (1000, 1600)]
PLUGINS = {"frames": "hyimg-frames", "3d": "hyimg-3d-studio", "dev": "hyimg-dev-studio"}
FOUND = defaultdict(set)   # (page, check, key) -> the looks it was seen in
MSG = {}
W = 240


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


def glb(path):
    """a glTF binary of one box (the 3D plugin's test helper, shortened)"""
    pos, idx = [], []
    for ax, a, b in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
        for sgn in (-1, 1):
            k = len(pos)
            for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                pt = [0.0] * 3; pt[ax] = sgn * 0.05; pt[a] = u * 0.05; pt[b] = v * 0.05; pos.append(pt)
            idx += [k, k + 1, k + 2, k, k + 2, k + 3]
    pb = b"".join(struct.pack("<3f", *p) for p in pos); ib = b"".join(struct.pack("<H", i) for i in idx); ib += b"\0" * (-len(ib) % 4)
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "box"}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": len(pos), "type": "VEC3", "min": [-.05] * 3, "max": [.05] * 3},
                         {"bufferView": 1, "componentType": 5123, "count": len(idx), "type": "SCALAR"}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pb)}, {"buffer": 0, "byteOffset": len(pb), "byteLength": len(ib)}],
           "buffers": [{"byteLength": len(pb) + len(ib)}]}
    js = json.dumps(doc).encode(); js += b" " * (-len(js) % 4); blob = pb + ib
    Path(path).write_bytes(struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(blob)) + struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(blob), 0x004E4942) + blob)


PAGE = "<!doctype html><html><head><title>Site</title><style>body{font:16px system-ui;margin:0;background:#2a6fdb;color:#fff}h1{margin:40px}</style></head><body><h1>A page</h1><p>text</p></body></html>"


def board_doc():
    at = lambda i: {"x": (i % 6) * (W + 30), "y": (i // 6) * 320}
    items = {
        "p1": {"path": "a/p1.png", "w": W, "ar": 0.75, "crop": [0, 0, 1, 0.9], **at(0)},
        "p2": {"path": "a/liked.png", "w": W, "ar": 0.75, "crop": None, **at(1)},
        "p3": {"path": "a/liked.png", "w": W, "ar": 0.75, "crop": [0.1, 0, 1, 1], **at(2)},   # a copy, cropped, liked: three marks on one card
        # graded (the frames plugin's mark top left), cropped and copied (top right), with a note on it (top left too): «the grade mark is not
        # counted in the board's fit (mkFit), on narrow cards it can touch the top row» (the card-marks session, 2026-10-06)
        "p4": {"path": "a/graded.png", "w": W, "ar": 0.75, "crop": [0, 0.1, 1, 1], "grade": {"exposure": 0.4, "contrast": 20}, **at(3)},
        "p5": {"path": "a/graded.png", "w": W, "ar": 0.75, "crop": None, **at(8)},
        "n2": {"type": "note", "text": "on the graded one", "x": 3 * (W + 30) + 140, "y": 40, "w": 110, "fs": 12, "color": "yellow"},
        "d": {"path": "a/doc.pdf", "w": W, "ar": 0.75, "crop": None, **at(4)},
        "s": {"path": "a/layers.psd", "w": W, "ar": 4 / 3, "crop": None, **at(5)},
        "h1": {"type": "html", "src": "site/index.html", "vw": 1280, "w": 400, "h": 250, "pics": ["site/index.html"], **at(7)},
        "m1": {"type": "model3d", "empty": True, "w": 400, "h": 300, **at(9)},
        "n1": {"type": "note", "text": "a note", "x": 2 * (W + 30) + 120, "y": 200, "w": 120, "fs": 12, "color": "blue"},
    }
    if FFMPEG:
        items["v"] = {"path": "a/clip.mp4", "w": W, "ar": 16 / 9, "crop": None, **at(6)}
    groups = {"g1": {"title": "Group", "x": -40, "y": -60, "w": 2 * (W + 30) + 50, "h": 320, "members": ["p1", "p2"]}}
    return {"schema": 1, "revision": 1, "items": items, "groups": groups, "removed": {}}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("audit")
    lib, state, plugins, home = tmp / "lib", tmp / "state", tmp / "plugins", tmp / "home"
    for p in (lib / "a", lib / "models", lib / "site", state / "boards", plugins, home): p.mkdir(parents=True)
    for n, c in (("p1", (200, 90, 80)), ("liked", (90, 120, 200)), ("graded", (120, 160, 90)), ("x1", (60, 60, 70)), ("x2", (220, 200, 160))):
        (lib / "a" / f"{n}.png").write_bytes(png(c))
    (lib / "a/liked.json").write_text(json.dumps({"feedback": {"fav": True, "updated": "2099-01-01 00:00"}}))
    (lib / "a/layers.psd").write_bytes(psd(64, 48, (230, 160, 40)))
    (lib / "a/doc.pdf").write_bytes(make_pdf(COLORS))
    glb(lib / "models/box.glb")
    (lib / "site/index.html").write_text(PAGE)
    if FFMPEG:
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(lib / "a/clip.mp4")], check=True, timeout=120)
    (state / "boards/main.json").write_text(json.dumps(board_doc()))
    for n, repo in PLUGINS.items():
        if (REPOS / repo / "manifest.json").is_file(): (plugins / n).symlink_to(REPOS / repo)
    settings = tmp / "settings.json"; settings.write_text(json.dumps({"cv.lang": "en"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(home), PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_PLUGINS=str(plugins),
               HYIMG_SETTINGS=str(settings), HYIMG_VIDEO_CACHE=str(tmp / "vcache"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(150):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        with playwright.sync_playwright() as p:
            try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
            yield {"port": port, "settings": settings, "state": state, "browser": browser, "p": p}
            browser.close()
    finally:
        proc.terminate(); proc.wait(5); log.close()
    _finish()


# ---------------------------------------------------------------- driving the pages
def look(world, theme, shape):
    world["settings"].write_text(json.dumps({"cv.lang": "en", "cv.theme": theme, "cv.shape": shape, "cv.lod": "0", "cv.nolib": "0"}))


def new_page(world, width):
    page = world["browser"].new_page(viewport={"width": width, "height": 900})
    page.errors = []; page.on("pageerror", lambda e: page.errors.append(str(e)))
    return page


def reset_board(world):
    (world["state"] / "boards/main.json").write_text(json.dumps(board_doc()))


def canvas_frame(page):
    for _ in range(200):
        f = next((f for f in page.frames if "/canvas" in f.url), None)
        if f: return f
        page.wait_for_timeout(100)
    raise AssertionError("no canvas frame")


def open_app(world, width, view):
    page = new_page(world, width)
    page.goto(f"http://127.0.0.1:{world['port']}/?view={view}")
    page.wait_for_function("() => document.body.classList.contains('cv-on') && !document.documentElement.classList.contains('lib-wait')", timeout=30000)
    frame = canvas_frame(page)
    frame.wait_for_function(f"() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === {len(board_doc()['items'])}"
                            " && typeof PLGST !== 'undefined' && PLGST.length >= 1 && PLGST.every(p => p.ok !== undefined)", timeout=30000)
    page.wait_for_timeout(1800)   # the entrance, and an empty board's library opening by itself
    return page, frame


def audit_once(target, only=None):
    target.evaluate(AUDIT_JS)
    return target.evaluate("([c, o]) => hyAudit.run(c, o)", [CONTRACT["runtime"], {"only": only} if only else {}])


def focus_rings(target):
    """every control of the chrome focused as the keyboard focuses it (focusVisible): what ring shows"""
    target.evaluate(AUDIT_JS)
    return target.evaluate("""(C) => { const out = [];
      const els = [...document.querySelectorAll(C.chrome.join(','))].filter(hyAudit.vis).flatMap(p => [...p.querySelectorAll('button, select, input:not([type=hidden]), [tabindex]')])
        .filter((e, i, a) => a.indexOf(e) === i && hyAudit.vis(e.closest('.hy-slider') || e)).slice(0, 60);
      for (const e of els) { const before = getComputedStyle(e).boxShadow; try { e.focus({ focusVisible: true, preventScroll: true }); } catch { continue; }
        if (document.activeElement !== e) continue;
        const s = getComputedStyle(e), host = e.closest('.hy-slider'), hs = host ? getComputedStyle(host) : null;
        const ring = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) ? 'outline ' + s.outlineWidth
          : (hs && hs.outlineStyle !== 'none' && parseFloat(hs.outlineWidth) > 0) ? 'outline on the slider'
          : (s.boxShadow !== before && /0px 0px 0px [2-9]/.test(s.boxShadow) && !/inset/.test(s.boxShadow)) ? 'box-shadow ring' : null;
        if (ring) out.push({ check: 'focus', key: hyAudit.path(host || e), msg: `${hyAudit.path(host || e)} shows a focus ring (${ring})` });
        e.blur(); }
      return out; }""", CONTRACT["runtime"])


def record(page_id, theme, shape, width, items):
    for v in items:
        k = (page_id, v["check"], v["key"]); FOUND[k].add(f"{theme}/{shape}/{width}"); MSG[k] = v["msg"]
    return [v for v in items]


def fp(page_id, check, key):
    return hashlib.sha1(f"{page_id}|{check}|{key}".encode()).hexdigest()[:12]


def known():
    try: return json.loads(BASELINE.read_text(encoding="utf-8")).get("runtime", {}).get("where", {})
    except (OSError, ValueError): return {}


def assert_known(page_id, items):
    if os.environ.get("HY_AUDIT_UPDATE") == "1": return
    base = known()
    new = [v for v in items if fp(page_id, v["check"], v["key"]) not in base]
    assert not new, f"{len(new)} new design findings on {page_id}:\n" + "\n".join(f"  [{v['check']}] {v['msg']}" for v in new)


def _finish():
    rows = [{"page": k[0], "check": k[1], "key": k[2], "msg": MSG[k], "looks": sorted(v)} for k, v in sorted(FOUND.items())]
    if os.environ.get("HY_AUDIT_REPORT"):
        Path(os.environ["HY_AUDIT_REPORT"]).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    if os.environ.get("HY_AUDIT_UPDATE") == "1" and rows:
        try: data = json.loads(BASELINE.read_text(encoding="utf-8"))
        except (OSError, ValueError): data = {}
        where = {fp(r["page"], r["check"], r["key"]): {"page": r["page"], "check": r["check"], "key": r["key"], "msg": r["msg"][:200], "looks": r["looks"]} for r in rows}
        by = defaultdict(int)
        for r in rows: by[r["check"]] += 1
        data["runtime"] = {"note": "known runtime findings of tests/test_design_audit.py: page, check and key; a new key fails the audit",
                           "updated": time.strftime("%Y-%m-%d"), "by_check": dict(sorted(by.items())), "where": dict(sorted(where.items()))}
        BASELINE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def settle(target, ms=3000):
    """until no transition or animation of the cards' marks and the bars runs (a mark measured mid-way is not its geometry)"""
    try:
        target.wait_for_function("() => !document.getAnimations().some(a => a.playState === 'running' && a.effect && a.effect.target"
                                 " && a.effect.target.closest && a.effect.target.closest('.mk, .tidy, #handles') && isFinite(a.effect.getComputedTiming().endTime))", timeout=ms)
    except Exception:
        pass


def cam(frame, z, x=-60, y=-80):
    frame.evaluate(f"() => {{ cam.x = {x}; cam.y = {y}; cam.z = {z}; renderCam(); render(); }}")
    frame.wait_for_timeout(700); settle(frame)


def audit(target, only=None):
    """findings seen twice, 500 ms apart: a state on its way somewhere is not a finding"""
    settle(target); a = audit_once(target, only); target.wait_for_timeout(500); settle(target)
    b = {(v["check"], v["key"]) for v in audit_once(target, only)}
    return [v for v in a if (v["check"], v["key"]) in b]


def pick(frame, ids):
    frame.evaluate(f"() => {{ sel = new Set({json.dumps(ids)}); render(); }}"); frame.wait_for_timeout(400); settle(frame)


def library_closed(page):
    if page.evaluate("() => !document.body.classList.contains('cv-only')"):
        page.keyboard.press("Control+m"); page.wait_for_function("() => document.body.classList.contains('cv-only')", timeout=5000); page.wait_for_timeout(900)


# ---------------------------------------------------------------- the pages
@pytest.mark.parametrize("theme,shape,width", LOOKS)
def test_board(world, theme, shape, width):
    look(world, theme, shape); reset_board(world)
    page, frame = open_app(world, width, "canvas")
    library_closed(page)
    page.mouse.move(5, 450)
    found = audit(frame) + audit(page) + focus_rings(frame)
    for z in (1, 0.6, 0.3):   # the marks' law: full, shrunk, folded
        cam(frame, z); found += [v for v in audit(frame, ["marks"]) if v["check"] == "marks"]
    # a selection: its bar over the cards (the bar must be inside the board and not under anything)
    cam(frame, 0.8); pick(frame, ["p1", "p2"]); found += audit(frame, ["covered", "viewport", "bar-height", "hint", "target"])
    record("board", theme, shape, width, found)
    assert not page.errors, page.errors
    assert_known("board", found)
    page.close()


@pytest.mark.parametrize("theme,shape,width", LOOKS)
def test_library(world, theme, shape, width):
    look(world, theme, shape); reset_board(world)
    page, frame = open_app(world, width, "panel")
    page.wait_for_timeout(600)
    found = audit(page) + audit(frame) + focus_rings(page)
    # the board beside the library with a selection: «the selection bar went under the library and its buttons could not be pressed»
    pick(frame, ["p1", "p2", "p3", "p4"]); found += audit(frame, ["covered", "viewport"])
    # the filter window over its dock
    btn = page.locator("#vf button").first
    if btn.count() and btn.is_visible():
        btn.click(); page.wait_for_timeout(700)
        found += audit(page, ["row-radius", "viewport", "covered", "hint", "target"])
        r = page.evaluate("""() => { const p = document.querySelector('.tfpanel'), d = document.querySelector('header.hy-dock #vf') || document.querySelector('#vf'), m = document.querySelector('main#list') || document.querySelector('main');
          if (!p || !hyAudit.vis(p) || !d) return null; const a = p.getBoundingClientRect(), b = d.getBoundingClientRect(), c = m ? m.getBoundingClientRect() : null;
          return { pl: a.left, pr: a.right, pt: a.top, dl: b.left, dr: b.right, mt: c ? c.top : 0 }; }""")
        if r:
            if r["pt"] < r["mt"] - 1: found.append({"check": "viewport", "key": ".tfpanel above the library", "msg": f"the filter window climbs {round(r['mt'] - r['pt'])} px over the library's top"})
            if r["pl"] > r["dl"] + 1 or r["pr"] < r["dr"] - 1: found.append({"check": "viewport", "key": ".tfpanel not over its dock", "msg": "the filter window is not aligned over its dock capsule"})
        btn.click(); page.wait_for_timeout(500)   # the filter button closes its window
        if page.evaluate("() => hyAudit.vis(document.querySelector('.tfpanel'))"):
            found.append({"check": "covered", "key": ".tfpanel stays open", "msg": "the filter window did not close on its own button"}); page.keyboard.press("Escape"); page.wait_for_timeout(400)
    # the wide library
    wide = page.locator("#lwide")
    if wide.count() and wide.is_visible() and not page.evaluate("() => hyAudit.vis(document.querySelector('.tfpanel'))"):
        wide.click(); page.wait_for_timeout(1200)
        found += [dict(v, key="wide " + v["key"]) for v in audit(page)]
    # the library card's kind pills against the board's marks
    found += audit(page, ["lib-pill"])
    record("library", theme, shape, width, found)
    assert not page.errors, page.errors
    assert_known("library", found)
    page.close()


@pytest.mark.parametrize("theme,shape,width", LOOKS)
def test_home(world, theme, shape, width):
    page = new_page(world, width)
    page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => {} } } }; window.HY_LANG = 'en';")
    page.goto(HOME)
    projects = [{"id": i, "name": n, "path": "/x" + i, "available": True, "updated": 1791100000 - k * 1000, "covers": []} for k, (i, n) in enumerate([("a", "Atlas"), ("b", "Studio North"), ("c", "Hyimg App")])]
    page.evaluate(f"hyimgHome({json.dumps({'projects': projects, 'settings': {'cv.theme': theme, 'cv.shape': shape, 'cv.lang': 'en'}, 'home': {'folders': [{'id': 'f1', 'name': 'Studio', 'projects': ['a']}], 'favs': ['a']}})})")
    page.wait_for_timeout(1200)
    found = audit(page) + focus_rings(page)
    page.locator("#bset").click(); page.wait_for_timeout(600)
    found += [dict(v, key="settings " + v["key"]) for v in audit(page)]
    page.locator("#bset").click(); page.wait_for_timeout(300)
    card = page.locator(".card[data-id=a]")
    if card.count():
        card.click(button="right"); page.wait_for_timeout(400)
        found += [dict(v, key="menu " + v["key"]) for v in audit(page, ["viewport", "covered", "target", "hint", "font"])]
        page.keyboard.press("Escape")
    record("home", theme, shape, width, found)
    assert not page.errors, page.errors
    assert_known("home", found)
    page.close()


def editor(world, theme, shape, width, card, mode, ready):
    look(world, theme, shape); reset_board(world)
    page, frame = open_app(world, width, "canvas")
    library_closed(page)
    pick(frame, [card])
    frame.click(f"#modes [data-mode=\"{mode}\"]")
    frame.wait_for_function(ready, timeout=40000)
    frame.wait_for_timeout(1500)
    if frame.locator(".m3pause [data-go]").count(): frame.click(".m3pause [data-go]")
    return page, frame


@pytest.mark.parametrize("theme,shape,width", LOOKS)
def test_image_studio(world, theme, shape, width):
    if not (REPOS / "hyimg-frames/manifest.json").is_file(): pytest.skip("no hyimg-frames beside hyimg")
    page, frame = editor(world, theme, shape, width, "p2", "image", "() => window.__frames && __frames.ED && __frames.ED.win")
    ed = next((f for f in page.frames if "/editor/" in f.url or "plugin/frames" in f.url and f is not frame), None)
    found = audit(frame)
    if ed:
        ed.wait_for_timeout(1200)
        found += [dict(v, key="editor " + v["key"]) for v in audit(ed) + focus_rings(ed)]
    record("image", theme, shape, width, found)
    assert not page.errors, page.errors
    assert_known("image", found)
    page.close()


@pytest.mark.parametrize("theme,shape,width", LOOKS)
def test_3d_studio(world, theme, shape, width):
    if not (REPOS / "hyimg-3d-studio/manifest.json").is_file(): pytest.skip("no hyimg-3d-studio beside hyimg")
    page, frame = editor(world, theme, shape, width, "m1", "3d", "() => document.body.classList.contains('m3edit') && document.querySelector('.m3r .hy-slider')")
    found = audit(frame) + focus_rings(frame)
    record("3d", theme, shape, width, found)
    assert not page.errors, page.errors
    assert_known("3d", found)
    page.close()


@pytest.mark.parametrize("theme,shape,width", LOOKS)
def test_dev_studio(world, theme, shape, width):
    if not (REPOS / "hyimg-dev-studio/manifest.json").is_file(): pytest.skip("no hyimg-dev-studio beside hyimg")
    page, frame = editor(world, theme, shape, width, "h1", "dev", "() => window.__dev && __dev.D && __dev.D.tree")
    found = audit(frame) + focus_rings(frame)
    record("dev", theme, shape, width, found)
    assert not page.errors, page.errors
    assert_known("dev", found)
    page.close()
