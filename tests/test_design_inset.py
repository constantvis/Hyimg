"""No text or icon touches the rounded edge that holds it (owner 2026-10-06, with two crops: «Presets ⌄» flush against its capsule's left
edge, «Colo…» cut into an icon: «посмотри, где еще вот такие проблемы есть, где нет пэддинга по сторонам, чтобы пофиксить вот эти все
вещи»; then the 3D studio's «Off | On», its chosen thumb touching the track top and bottom). design/audit.js «inset» measures every
capsule, chip, button, select, field and tag of every page: the board with its selection bar, right-click menu and Raw Editor (its
presets open), the library with its filter window, Home with its settings, the image studio, the 3D studio and Dev studio; dark and light,
round and pro, Russian and English (the Russian words are longer). Strict: no baseline, a finding fails.

  python3 -m pytest tests/test_design_inset.py
  HY_AUDIT_QUICK=1   one look (dark, round) in both languages
  HY_INSET_REPORT=<file>   every finding as JSON
"""
import json, os
from pathlib import Path

import pytest

from test_design_audit import (AUDIT_JS, CONTRACT, HOME, REPOS, audit_once, canvas_frame, library_closed, new_page, pick, reset_board, settle,  # noqa: F401
                               world, board_doc)

QUICK = os.environ.get("HY_AUDIT_QUICK") == "1"
LOOKS = [(t, s, l) for t in (("dark",) if QUICK else ("dark", "light")) for s in (("round",) if QUICK else ("round", "pro")) for l in ("ru", "en")]
FOUND = []


def look(world, theme, shape, lang):
    world["settings"].write_text(json.dumps({"cv.lang": lang, "cv.theme": theme, "cv.shape": shape, "cv.lod": "0", "cv.nolib": "0"}))


def inset(target, where):
    """the inset check, twice 400 ms apart: a control on its way somewhere is not a finding"""
    settle(target); a = audit_once(target, ["inset"]); target.wait_for_timeout(400); settle(target)
    b = {v["key"] for v in audit_once(target, ["inset"])}
    return [dict(v, where=where) for v in a if v["key"] in b]


def open_app(world, view):
    page = new_page(world, 1440)
    page.goto(f"http://127.0.0.1:{world['port']}/?view={view}", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_function("() => document.body.classList.contains('cv-on') && !document.documentElement.classList.contains('lib-wait')", timeout=30000)
    frame = canvas_frame(page)
    frame.wait_for_function(f"() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === {len(board_doc()['items'])}"
                            " && typeof PLGST !== 'undefined' && PLGST.length >= 1 && PLGST.every(p => p.ok !== undefined)", timeout=30000)
    page.wait_for_timeout(1500)
    return page, frame


def done(name, items, page):
    FOUND.extend(dict(v, page=name) for v in items)
    if os.environ.get("HY_INSET_REPORT"):
        Path(os.environ["HY_INSET_REPORT"]).write_text(json.dumps(FOUND, ensure_ascii=False, indent=1), encoding="utf-8")
    assert not page.errors, page.errors
    assert not items, f"{len(items)} controls with too little inset on {name}:\n" + "\n".join(f"  [{v['where']}] {v['msg']}" for v in items)


@pytest.mark.parametrize("theme,shape,lang", LOOKS)
def test_board_and_raw_editor(world, theme, shape, lang):
    look(world, theme, shape, lang); reset_board(world)
    page, frame = open_app(world, "canvas")
    library_closed(page)
    found = inset(frame, "board") + inset(page, "board page")
    pick(frame, ["p1", "p2"]); found += inset(frame, "selection bar")
    pick(frame, ["p4"]); frame.wait_for_timeout(300)
    # the right click and its properties submenu
    frame.click("#items [data-id=p4]", button="right"); frame.wait_for_timeout(400)
    found += inset(frame, "right click")
    sub = frame.locator("#ctx [data-sub=props-copy]")
    if sub.count(): sub.hover(); frame.wait_for_timeout(500); found += inset(frame, "properties")
    page.keyboard.press("Escape"); frame.wait_for_timeout(300)
    # the notes at the top (ui/toasts.js): a plain one, one with a button, a sticky one with its ×, the dot and the words off the round ends
    frame.evaluate("""() => { hyToast('Raw Editor'); hyToast('Moved 2 objects to page 2', 'success', { actions: [{ label: 'Undo', fn: () => {} }] }); hyToast('Not saved: the server did not answer', 'error', { sticky: true }); }""")
    frame.wait_for_timeout(700)
    found += inset(page, "toasts") + inset(frame, "toasts")
    # Raw Editor (the frames plugin), its presets open
    btn = frame.locator(".tidy button.ic[data-plgbar]").first
    if btn.count():
        btn.click(); frame.wait_for_selector("#hcgp.in .hcg", timeout=10000); frame.wait_for_timeout(500)
        frame.evaluate("() => document.querySelectorAll('#hcgp .hcg-sec').forEach(s => s.classList.add('open'))"); frame.wait_for_timeout(500)
        found += inset(frame, "raw editor")
        for top in range(0, 4000, 500):   # its sections further down
            if not frame.evaluate(f"() => {{ const s = document.querySelector('#hcgp .hcg-scroll'); s.scrollTop = {top}; return s.scrollTop >= {top} - 1; }}"): break
            frame.wait_for_timeout(150); found += inset(frame, f"raw editor at {top}")
        frame.evaluate("() => document.querySelector('#hcgp .hcg-pbtn').click()"); frame.wait_for_timeout(400)
        found += inset(frame, "raw editor presets")
    done("board", found, page); page.close()


@pytest.mark.parametrize("theme,shape,lang", LOOKS)
def test_library(world, theme, shape, lang):
    look(world, theme, shape, lang); reset_board(world)
    page, frame = open_app(world, "panel")
    found = inset(page, "library")
    btn = page.locator("#vf button").first
    if btn.count() and btn.is_visible():
        btn.click(); page.wait_for_timeout(700); found += inset(page, "filters"); btn.click(); page.wait_for_timeout(400)
    done("library", found, page); page.close()


@pytest.mark.parametrize("theme,shape,lang", LOOKS)
def test_home(world, theme, shape, lang):
    page = new_page(world, 1440)
    page.add_init_script(f"window.webkit = {{ messageHandlers: {{ hyimg: {{ postMessage: m => {{}} }} }} }}; window.HY_LANG = '{lang}';")
    page.goto(HOME)
    projects = [{"id": i, "name": n, "path": "/x" + i, "available": True, "updated": 1791100000 - k * 1000, "covers": [], "news": 3 if k == 0 else 0} for k, (i, n) in enumerate([("a", "Atlas"), ("b", "Studio North"), ("c", "Hyimg App")])]
    page.evaluate(f"hyimgHome({json.dumps({'projects': projects, 'settings': {'cv.theme': theme, 'cv.shape': shape, 'cv.lang': lang}, 'home': {'folders': [{'id': 'f1', 'name': 'Studio', 'projects': ['a']}], 'favs': ['a']}})})")
    page.wait_for_timeout(1200)
    found = inset(page, "home")
    page.locator("#bset").click(); page.wait_for_timeout(600); found += inset(page, "home settings"); page.locator("#bset").click()
    done("home", found, page); page.close()


def studio(world, theme, shape, lang, card, mode, ready):
    look(world, theme, shape, lang); reset_board(world)
    page, frame = open_app(world, "canvas")
    library_closed(page)
    pick(frame, [card])
    frame.click(f"#modes [data-mode=\"{mode}\"]")
    frame.wait_for_function(ready, timeout=40000)
    frame.wait_for_timeout(1500)
    if frame.locator(".m3pause [data-go]").count(): frame.click(".m3pause [data-go]")
    return page, frame


@pytest.mark.parametrize("theme,shape,lang", LOOKS)
def test_image_studio(world, theme, shape, lang):
    if not (REPOS / "hyimg-image-studio/manifest.json").is_file(): pytest.skip("no hyimg-image-studio beside hyimg")
    page, frame = studio(world, theme, shape, lang, "p2", "image", "() => window.__frames && __frames.ED && __frames.ED.win")
    found = inset(frame, "image studio board")
    ed = next((f for f in page.frames if "/editor/" in f.url), None)
    if ed:
        ed.wait_for_timeout(1200); found += inset(ed, "image studio")
        for tab in ("adj", "mask"):   # the Adjustments tab (Raw Editor layers) and the mask's panel
            try: ed.evaluate(f"() => __ed.showPanel && __ed.showPanel('{tab}')"); ed.wait_for_timeout(500); found += inset(ed, f"image studio {tab}")
            except Exception: pass
    done("image", found, page); page.close()


@pytest.mark.parametrize("theme,shape,lang", LOOKS)
def test_3d_studio(world, theme, shape, lang):
    if not (REPOS / "hyimg-3d-studio/manifest.json").is_file(): pytest.skip("no hyimg-3d-studio beside hyimg")
    page, frame = studio(world, theme, shape, lang, "m1", "3d", "() => document.body.classList.contains('m3edit') && document.querySelector('.m3r .hy-slider')")
    found = inset(frame, "3d studio")
    done("3d", found, page); page.close()


@pytest.mark.parametrize("theme,shape,lang", LOOKS)
def test_dev_studio(world, theme, shape, lang):
    if not (REPOS / "hyimg-dev-studio/manifest.json").is_file(): pytest.skip("no hyimg-dev-studio beside hyimg")
    page, frame = studio(world, theme, shape, lang, "h1", "dev", "() => window.__dev && __dev.D && __dev.D.tree")
    found = inset(frame, "dev studio")
    done("dev", found, page); page.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_slider_line_stays_inside_its_round_ends(world, theme):
    """the app's slider at 0 and at its end (owner 2026-10-06: at 0 a thin crescent «(» stuck out of the 3D panel's row, the line cut by
    the curve): Raw Editor's sliders at 0, one at its maximum; with the old 1 px clamp the check finds the cut line"""
    look(world, theme, "round", "en"); reset_board(world)
    page, frame = open_app(world, "canvas")
    library_closed(page)
    pick(frame, ["p2"])
    frame.locator(".tidy button.ic[data-plgbar]").first.click(); frame.wait_for_selector("#hcgp.in .hcg", timeout=10000); frame.wait_for_timeout(500)
    frame.evaluate("""() => { const i = document.querySelector("#hcgp input[aria-label='Clarity']"); i.value = i.max; i.dispatchEvent(new Event('input', { bubbles: true })); }""")
    frame.wait_for_timeout(400)
    lines = lambda: [v for v in inset(frame, "raw editor sliders") if v["key"].startswith("slider-line")]
    assert not lines(), lines()
    frame.evaluate("() => { const s = document.createElement('style'); s.id = 'oldclamp'; s.textContent = '.hy-slider { --hy-sl-end: 1px !important; }'; document.head.appendChild(s); }")
    frame.wait_for_timeout(300)
    assert lines(), "the check must find a line cut by the round end"
    page.close()
