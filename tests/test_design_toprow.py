"""The top row is one row in every mode (owner 2026-10-07: «breadcrumb area тоже разношерстная», with two crops: in the image studio the
library button, the crumb and the tool's hint under them crossed the ruler at the window's left edge and the group's title after the crumb
was shorter and another shade; in the 3D studio the scene's path after the crumb was shorter and another look). design/audit.js «top-row»
reads the row across the window's frames (the library page, the board in it, the image studio in that) and measures it against
design/contract.json runtime.top_row: one top, height, gutter and gap, one glass, shadow and corner, one text size, the mode's hint plate and
the side panels under it, nothing on the image studio's rulers. The board (with a long group's title stuck after the crumb), the library
beside it, the image studio, the 3D studio, Dev studio and Home; dark and light, round and pro, Russian and English; the board and the
image studio also as the Mac app's window, with the window buttons' capsule first in the row. Strict: no baseline, a finding fails.

  python3 -m pytest tests/test_design_toprow.py
  HY_AUDIT_QUICK=1          one look (dark, round) in both languages
  HY_TOPROW_SHOTS=<dir>     the row of every look as a picture (the top 170 px of the window)
"""
import json, os
from pathlib import Path

import pytest

from test_design_audit import (AUDIT_JS, CONTRACT, HOME, REPOS, board_doc, canvas_frame, library_closed, new_page, pick, reset_board,  # noqa: F401
                               world)

QUICK = os.environ.get("HY_AUDIT_QUICK") == "1"
LOOKS = [(t, s, l) for t in (("dark",) if QUICK else ("dark", "light")) for s in (("round",) if QUICK else ("round", "pro")) for l in ("ru", "en")]
SHOTS = os.environ.get("HY_TOPROW_SHOTS")
WIDTH = 1440
# the Mac app's window (not full screen): the pages see the app's bridge and a screen larger than the window
APP = ("window.webkit = { messageHandlers: { hyimg: { postMessage: m => {} } } };"
       " Object.defineProperty(screen, 'width', { get: () => 3000 }); Object.defineProperty(screen, 'height', { get: () => 2000 });")
# until nothing in the window's frames moves (an entrance, a plate gliding along the crumb): a plate on its way is not its place
STILL = """() => { const fr = [window]; for (let i = 0; i < fr.length; i++) for (const f of fr[i].document.querySelectorAll('iframe'))
  { try { if (f.contentWindow.document) fr.push(f.contentWindow); } catch {} }
  return fr.every(w => !w.document.getAnimations().some(a => a.playState === 'running' && isFinite(a.effect.getComputedTiming().endTime))); }"""


def look(world, theme, shape, lang):
    world["settings"].write_text(json.dumps({"cv.lang": lang, "cv.theme": theme, "cv.shape": shape, "cv.lod": "0", "cv.nolib": "0"}))


def top_row(page):
    """the check twice, 500 ms apart, once nothing moves: a plate on its way (the title gliding along a crumb that grows) is not a finding"""
    try: page.wait_for_function(STILL, timeout=8000)
    except Exception: pass
    page.evaluate(AUDIT_JS)
    run = lambda: page.evaluate("([c]) => hyAudit.run(c, { only: ['top-row'] })", [CONTRACT["runtime"]])
    page.wait_for_timeout(300); a = run(); page.wait_for_timeout(500); b = {v["key"] for v in run()}
    return [v for v in a if v["key"] in b]


def open_app(world, view, app=False):
    page = new_page(world, WIDTH)
    if app: page.add_init_script(APP)
    page.goto(f"http://127.0.0.1:{world['port']}/?view={view}", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_function("() => document.body.classList.contains('cv-on') && !document.documentElement.classList.contains('lib-wait')", timeout=90000)
    frame = canvas_frame(page)
    frame.wait_for_function(f"() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === {len(board_doc()['items'])}"
                            " && typeof PLGST !== 'undefined' && PLGST.length >= 1 && PLGST.every(p => p.ok !== undefined)", timeout=90000)
    page.wait_for_timeout(1800)   # the entrance, the crumb growing in
    return page, frame


NOTE = "() => window.hyToast && hyToast('3D: scene saved to 3d/scenes/261007-002901/scene.json', 'info', { sticky: true })"


def check(page, name):
    page.evaluate(NOTE)   # a note at the top of the window: it stands under the row, never on a plate of it
    found = top_row(page)
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / f"{name}.png"), clip={"x": 0, "y": 0, "width": WIDTH, "height": 170})
    assert not page.errors, page.errors
    assert not found, f"{len(found)} findings in the top row of {name}:\n" + "\n".join(f"  {v['msg']}" for v in found)


def studio(world, theme, shape, lang, card, mode, ready, app=False):
    look(world, theme, shape, lang); reset_board(world)
    page, frame = open_app(world, "canvas", app)
    library_closed(page)
    pick(frame, [card])
    frame.click(f"#modes [data-mode=\"{mode}\"]")
    frame.wait_for_function(ready, timeout=90000)
    frame.wait_for_timeout(1500)
    if frame.locator(".m3pause [data-go]").count(): frame.click(".m3pause [data-go]"); frame.wait_for_timeout(600)
    return page, frame


def stuck_title(frame):
    """a long group past the window's top: its title rides after the crumb (canvas.html stickTitles)"""
    frame.wait_for_function("""() => { cam.x = -60; cam.y = 140; cam.z = 1; renderCam(); render();
      const b = document.querySelector('#gsticky .gst'); return b && !b._out && Math.abs(b.getBoundingClientRect().top - 12) < 1; }""", polling=500, timeout=30000)


@pytest.mark.parametrize("theme,shape,lang", LOOKS)
def test_board(world, theme, shape, lang):
    look(world, theme, shape, lang); reset_board(world)
    page, frame = open_app(world, "canvas")
    library_closed(page); stuck_title(frame)
    check(page, f"board-{theme}-{shape}-{lang}"); page.close()


@pytest.mark.parametrize("theme,shape,lang", LOOKS)
def test_library(world, theme, shape, lang):
    look(world, theme, shape, lang); reset_board(world)
    page, frame = open_app(world, "panel")
    check(page, f"library-{theme}-{shape}-{lang}"); page.close()


@pytest.mark.parametrize("theme,shape,lang", LOOKS)
def test_image_studio(world, theme, shape, lang):
    if not (REPOS / "hyimg-image-studio/manifest.json").is_file(): pytest.skip("no hyimg-image-studio beside hyimg")
    page, frame = studio(world, theme, shape, lang, "p2", "image", "() => window.__frames && __frames.ED && __frames.ED.win")
    stuck_title(frame)
    # the tool's hint in the hint plate speaks the board's language (hyimg-image-studio lang.js, owner 2026-10-07)
    ed = next(f for f in page.frames if "/editor/" in f.url)
    hint = ed.evaluate("() => document.querySelector('#obar .hint2').textContent")
    assert hint.startswith("Клик выбирает слой" if lang == "ru" else "A click picks the layer"), hint
    check(page, f"image-{theme}-{shape}-{lang}"); page.close()


@pytest.mark.parametrize("theme,shape,lang", LOOKS)
def test_3d_studio(world, theme, shape, lang):
    if not (REPOS / "hyimg-3d-studio/manifest.json").is_file(): pytest.skip("no hyimg-3d-studio beside hyimg")
    page, frame = studio(world, theme, shape, lang, "m1", "3d", "() => document.body.classList.contains('m3edit') && document.querySelector('.m3title')")
    check(page, f"3d-{theme}-{shape}-{lang}"); page.close()


@pytest.mark.parametrize("theme,shape,lang", LOOKS)
def test_dev_studio(world, theme, shape, lang):
    if not (REPOS / "hyimg-dev-studio/manifest.json").is_file(): pytest.skip("no hyimg-dev-studio beside hyimg")
    page, frame = studio(world, theme, shape, lang, "h1", "dev", "() => window.__dev && __dev.D && __dev.D.tree")
    check(page, f"dev-{theme}-{shape}-{lang}"); page.close()


@pytest.mark.parametrize("theme,lang", [(t, l) for t in ("dark", "light") for l in ("ru", "en")])
def test_home(world, theme, lang):
    page = new_page(world, WIDTH)
    page.add_init_script(f"window.webkit = {{ messageHandlers: {{ hyimg: {{ postMessage: m => {{}} }} }} }}; window.HY_LANG = '{lang}';")
    page.goto(HOME)
    projects = [{"id": i, "name": n, "path": "/x" + i, "available": True, "updated": 1791100000 - k * 1000, "covers": [], "news": 0}
                for k, (i, n) in enumerate([("a", "Atlas"), ("b", "Studio North")])]
    data = {"projects": projects, "settings": {"cv.theme": theme, "cv.shape": "round", "cv.lang": lang}, "home": {"folders": [], "favs": []}}
    page.evaluate(f"hyimgHome({json.dumps(data)})")
    page.wait_for_timeout(1500)
    check(page, f"home-{theme}-{lang}"); page.close()


@pytest.mark.parametrize("mode", ["board", "image"])
def test_in_the_app_window(world, mode):
    """the Mac app's window: the window buttons' capsule, then the library button and the crumb, the row's gap apart"""
    if mode == "image":
        if not (REPOS / "hyimg-image-studio/manifest.json").is_file(): pytest.skip("no hyimg-image-studio beside hyimg")
        page, frame = studio(world, "dark", "round", "en", "p2", "image", "() => window.__frames && __frames.ED && __frames.ED.win", app=True)
    else:
        look(world, "dark", "round", "en"); reset_board(world)
        page, frame = open_app(world, "canvas", app=True); library_closed(page)
    stuck_title(frame)
    assert page.evaluate("() => getComputedStyle(document.querySelector('#wl')).display !== 'none'"), "the window buttons' capsule shows in the app's window"
    check(page, f"app-{mode}"); page.close()


def test_the_image_studio_rulers_leave_the_row_alone(world):
    """the rulers are off until turned on, and the vertical one runs from the window's very top (owner 2026-10-09: «опять проблема с тем,
    что до самого верху должна идти линейка, и по дефолту выключена быть»; hyimg-image-studio had started it under the row): the row's plates
    float over its top. The tool's options ride over the dock on the board since round 11 D3 (hyimg-image-studio editor/dockwork.js) and lie on
    no ruler; the audit's edge band starts under the row's 58 px line, and it finds a hint plate laid on it"""
    if not (REPOS / "hyimg-image-studio/manifest.json").is_file(): pytest.skip("no hyimg-image-studio beside hyimg")
    page, frame = studio(world, "dark", "round", "en", "p2", "image", "() => window.__frames && __frames.ED && __frames.ED.win")
    ed = next(f for f in page.frames if "/editor/" in f.url)
    ed.wait_for_function("() => document.body.classList.contains('in')", timeout=10000); ed.wait_for_timeout(800)
    assert ed.evaluate("() => __ed.S.rulers || localStorage.getItem('hy-ed-rulers') === '1'") is False, "the rulers are off by default"
    ed.evaluate("() => __ed.toggleRulers()"); ed.wait_for_timeout(400)
    px = ed.evaluate("""() => { const c = document.getElementById('view'), g = c.getContext('2d'), k = c.width / innerWidth;
      const a = (x, y) => g.getImageData(Math.round(x * k), Math.round(y * k), 1, 1).data[3];
      const ob = document.getElementById('obar').getBoundingClientRect(), e = hyEdges();
      return { row: a(6, 31), ruler: a(6, innerHeight - 120), edgeTop: e[0].top, hTop: e[1].top, docked: document.getElementById('obar').classList.contains('indock'),
        hintLeft: ob.left, hintBottom: ob.bottom }; }""")
    assert px["ruler"] > 0, f"the ruler is drawn down the left edge: {px}"
    assert px["row"] > 0, f"the ruler runs on beside the row, to the window's top: {px}"
    assert px["docked"] and px["edgeTop"] == 58, px
    assert px["hintLeft"] > 18 and px["hintBottom"] <= px["hTop"], f"the options over the dock lie on neither ruler: {px}"
    # a hint plate moved onto the ruler is found (a copy of the options bar as it stands off the dock)
    ed.evaluate("""() => { const o = document.getElementById('obar'), c = o.cloneNode(true); c.classList.remove('indock');
      Object.assign(c.style, { transition: 'none', translate: 'none', opacity: '1', left: '4px', top: '200px', bottom: 'auto' }); o.after(c); }""")
    found = top_row(page)
    assert any(v["key"].startswith("hint edge") for v in found), found
    page.close()


def test_a_note_over_the_row_is_found(world):
    """the notes (ui/toasts.js) stand in the row at its centre, as tall as its plates (owner 2026-10-09: «на уровне breadcrumbs, поверх
    них, по центру экрана»); one moved over the crumb is a finding"""
    look(world, "dark", "round", "en"); reset_board(world)
    page, frame = open_app(world, "canvas"); library_closed(page)
    page.evaluate(NOTE)
    # the stack's line (the front card settles on it, translateY 0) and the card's height: the row's
    top = page.evaluate("() => document.querySelector('#hyToasts').getBoundingClientRect().top")
    assert abs(top - 12) <= 0.5, top
    h = page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('#hyToasts .ht')).minHeight)")
    assert abs(h - 38) <= 0.5, h
    assert not [v for v in top_row(page) if v["key"].startswith("toast")]
    page.evaluate("() => { const s = document.documentElement.style; s.setProperty('--toast-top', '14px'); s.setProperty('--toast-x', '300px'); }")
    found = top_row(page)
    assert any(v["key"].startswith("toast over") for v in found), found
    page.close()
