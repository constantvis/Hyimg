"""Zoom far out stays light (owner 2026-10-08, a screen recording of the «UI» board: zoom in and out between 8 and 20 % lagged and parts of
the board went blank). Measured on a read-only copy of that page (499 things: 117 pictures, 228 headings, 103 HTML cards, 34 HTML frames,
17 notes, 12 groups, 47 comment pins) in Chromium with dpr 2 and the CPU 4× slower (the owner renders 3D beside it): every zoom frame wrote
--z into the whole board layer, a restyle and a new layout of every card on screen, and restarted the transitions that depend on it
(comment areas, note arrows): 46 % of the zoom frames took over 50 ms, the median 41 ms; with --z on steps of 5 % (canvas.html zStep) and
those transitions off while the zoom moves, 17 % and 20 ms.

This board copies the page's structure with throwaway files (pictures, headings, notes linked to pictures, comment pins, groups, and HTML
frames with their stills when the frames plugin is beside this repository) and zooms it with the trackpad's pinch (⌃ wheel) between 7
and 25 %. It checks the cause (--z is written on its steps, not on every frame), the main thread's work per frame and the frame times
against budgets set from that measurement. Chromium, dark theme."""
import json
import math
import os
import random
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest
from PIL import Image

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT.parent / "hyimg-image-studio"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_canvas_pages import free_port  # noqa: E402

ME = str(uuid.uuid4())
# budgets, from this board in Playwright's headless Chromium on an M1 (2026-10-08, two runs each): --z written 84 times in ~310 frames
# before (on every frame the zoom moved), 25-28 on steps; style and layout 2.0-2.1 ms a zoom frame before, 0.7-1.1 ms after; the median
# frame 16.7 ms and the 90th percentile 33-51 ms either way here (the CPU 4× slower, as on the owner's Mac, is where they part: above)
MAX_STYLE_LAYOUT_MS = 1.7
MAX_MEDIAN_MS = 34
MAX_P90_MS = 70


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("farzoom"); lib, state = tmp / "lib", tmp / "lib/_review"
    rnd = random.Random(8)
    (lib / "a").mkdir(parents=True); (lib / "comments").mkdir(); (state / "boards").mkdir(parents=True)
    items, groups = {}, {}
    for n in range(117):   # pictures 720 wide, as the page's (the far canvas takes them below 110 px on screen)
        Image.new("RGB", (160, 100), (rnd.randrange(40, 220), rnd.randrange(40, 220), rnd.randrange(40, 220))).save(lib / "a" / f"{n}.png")
        g = n // 10
        items[f"p{n}"] = {"path": f"a/{n}.png", "x": (n % 10) % 5 * 780, "y": g * 3600 + (n % 10) // 5 * 500, "w": 720, "ar": 1.6, "crop": None}
    for n in range(228):   # headings and captions
        items[f"t{n}"] = {"type": "text", "text": f"Caption {n}", "x": n % 6 * 900, "y": (n // 6) * 320 + 2400, "fs": 48 if n % 7 else 96, "size": 3, "w": 600, "h": 60}
    for n in range(17):   # notes, each linked to pictures: their dots on the pictures
        items[f"n{n}"] = {"type": "note", "text": f"Note {n}", "color": "yellow", "x": 4100, "y": n * 2100, "w": 260, "h": 200,
                          "to": [f"p{(n * 7 + k) % 117}" for k in range(7)]}
    if FRAMES.is_dir():   # HTML frames with their stills (the frames plugin), drawn as on the page
        for n in range(34):
            d = lib / "html" / f"f{n}" / ".stills"; d.mkdir(parents=True)
            (lib / "html" / f"f{n}" / "index.html").write_text("<!doctype html><p>frame</p>")
            Image.new("RGB", (1440, 900), (230, 230, 235)).save(d / "index-1440x900.png")
            items[f"h{n}"] = {"type": "htmlframe", "src": f"html/f{n}/index.html", "vw": 1440, "x": 4800 + n % 3 * 1500, "y": n // 3 * 1000, "w": 1440, "h": 900}
    for g in range(12):
        groups[f"g{g}"] = {"title": f"Figma · round {g}", "x": -100, "y": g * 3600 - 160, "w": 4000, "h": 1300, "members": [f"p{n}" for n in range(g * 10, min(117, g * 10 + 10))]}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": groups, "removed": {}}))
    t0 = time.strftime("%Y-%m-%dT%H:%M:%S")
    for k in range(47):   # comment pins with their author's face, on pictures and on the board
        an = {"obj": f"p{k * 2}", "kind": "picture", "file": f"a/{k * 2}.png"} if k % 2 else None
        th = {"id": f"c{k}", "page": "main", "anchor": an, "at": [.5, .3] if an else [k % 8 * 500, k // 8 * 3000 + 1400], "by": {"person": ME, "via": "app"},
              "created": t0, "updated": t0, "resolved": None, "objects": [an["obj"]] if an else [],
              "messages": [{"id": f"m{k}", "by": {"person": ME, "via": "app"}, "text": "look here", "mentions": [], "created": t0}]}
        (lib / "comments" / f"main__c{k}.json").write_text(json.dumps(th))
    (tmp / "settings.json").write_text(json.dumps({"cv.theme": "dark", "cv.lang": "en", "cv.glass": "1"}))
    (tmp / "profile.json").write_text(json.dumps({"id": ME, "name": "Robin", "color": "blue", "created": ""}))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp / "settings.json"), HYIMG_PROFILE_DIR=str(tmp),
               HYIMG_CACHE_ROOT=str(tmp / "cache"), PYTHONDONTWRITEBYTECODE="1")
    if FRAMES.is_dir():
        (tmp / "plugins").mkdir(); (tmp / "plugins" / "frames").symlink_to(FRAMES); env["HYIMG_PLUGINS"] = str(tmp / "plugins")
    port = free_port(); log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port
    finally:
        proc.terminate(); proc.wait(5); log.close()
# every frame's time while the zoom runs, and every value of --z the group layer gets (the live --z is on the layers and the cards on
# screen, canvas.html zLive, since 2026-10-08)

# every frame's time while the zoom runs, and every value of --z the board layer gets
REC = """() => { const R = window.__R = { t: [], z: [], cz: [], on: true, last: performance.now() };
  const tick = n => { if (!R.on) return; R.t.push(n - R.last); R.cz.push(cam.z); R.last = n; requestAnimationFrame(tick); }; requestAnimationFrame(tick);
  const w = document.getElementById('groups'); let z0 = w.style.getPropertyValue('--z');
  R.mo = new MutationObserver(() => { const z = w.style.getPropertyValue('--z'); if (z && z !== z0) R.z.push(+z); if (z) z0 = z; });   // a zoom resumed after a pause: no new value
  R.mo.observe(w, { attributes: true, attributeFilter: ['style'] }); }"""
STOP = "() => { const R = window.__R; R.on = false; R.mo.disconnect(); return { t: R.t.slice(2), z: R.z, cz: R.cz }; }"


def metrics(cdp):
    m = {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
    return m["RecalcStyleDuration"] + m["LayoutDuration"]


def test_far_zoom_writes_z_on_steps_and_stays_in_budget(server):
    port = server
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        ctx = browser.new_context(viewport={"width": 1680, "height": 1000}, device_scale_factor=2, color_scheme="dark")
        page = ctx.new_page(); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        cdp = ctx.new_cdp_session(page); cdp.send("Performance.enable")
        page.goto(f"http://127.0.0.1:{port}/canvas.html")
        page.wait_for_function("() => typeof board !== 'undefined' && Object.keys(board.items).length > 300 && document.querySelectorAll('.cmpin').length >= 40",
                               timeout=30000)
        assert page.evaluate("() => document.documentElement.dataset.theme") == "dark"
        page.evaluate("() => { cam = { x: -400, y: -300, z: 0.07 }; render(); }")
        page.wait_for_timeout(4000)   # thumbnails and stills in place
        assert page.evaluate("() => LOD.on"), "far out: the pictures in the far canvas"
        page.evaluate(REC); before = metrics(cdp)
        for dy, n in ((-3, 42), (3, 42)):   # in to about 25 % and back, a pinch's ⌃ wheel at 60 events a second
            for _ in range(n):
                cdp.send("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": 840, "y": 500, "deltaX": 0, "deltaY": dy, "modifiers": 2})
                time.sleep(0.016)
        page.wait_for_timeout(300)
        r = page.evaluate(STOP); work = metrics(cdp) - before
        t = sorted(r["t"]); frames = len(t)
        median, p90 = t[frames // 2], t[int(frames * .9)]
        per_frame = work * 1000 / max(1, frames)
        print(f"far zoom: {frames} frames, median {median:.1f} ms, 90% {p90:.1f} ms, --z written {len(r['z'])} times, style+layout {per_frame:.2f} ms a frame")
        assert frames > 40
        # the cause: --z changes when the zoom crosses a step of 5 %, not on every frame the zoom moves (each write restyles the board)
        g = [round(math.log(z) / .05) for z in r["cz"]]
        moved, crossed = sum(a != b for a, b in zip(r["cz"], r["cz"][1:])), sum(abs(a - b) for a, b in zip(g, g[1:]))
        assert len(r["z"]) <= crossed + 4 and len(r["z"]) < moved * .6, f"--z written {len(r['z'])} times, {crossed} steps crossed, the zoom moved on {moved} frames"
        assert all(abs(math.log(v) / .05 - round(math.log(v) / .05)) < 1e-6 for v in r["z"]), r["z"]   # on the 5 % grid
        assert per_frame <= MAX_STYLE_LAYOUT_MS, f"style and layout {per_frame:.2f} ms a zoom frame"
        assert median <= MAX_MEDIAN_MS and p90 <= MAX_P90_MS, (median, p90)
        assert not errors, errors
        browser.close()
