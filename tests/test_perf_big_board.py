"""A zoom on a big page stays light (owner 2026-10-08: «что-то тормозит, очень сильно, просто ужасно лагает», the performance log: the
«Renderings» page of Studio North, 2675 pictures, 422 notes with zones, 41 groups, 48 600 elements, 589 ms frames). Measured on a copy of
that page in Chromium on the Mac's GPU, dpr 2, a trackpad-like pinch from 5 % in and back: the live zoom wrote --z on the board layer,
so each 5 % step restyled every card of the page, the 3107 hidden ones too (34 ms a step, 130 ms with the CPU 4× slower). --z now goes
on the board's layers and on the cards on screen only (canvas.html zLive). Frames: median 50-66 → 16.7 ms, over 50 ms 37-63 → 2 of
95-282; restyle 4.2-5.5 → 0.7 s; with the CPU 4× slower median 217 → 66 ms, restyle 8.6-10.9 → 1.2-1.5 s.

This board has the page's scale with throwaway pictures: 2600 pictures in 40 groups, 402 notes, each with a zone over a row of its
group's pictures (a dot on each). It zooms with the trackpad's pinch (⌃ wheel) and checks the cause, the settle and a budget."""
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest
from PIL import Image

playwright = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_canvas_pages import free_port  # noqa: E402

# style and layout per zoom frame, Playwright's headless Chromium on an M1's GPU (2026-10-08): 25-26 ms before (the --z of every card),
# 7.5-8 after
MAX_STYLE_LAYOUT_MS = 14
# the far view draws with WebGL: on a Mac on its GPU, as the app does (headless Chromium's default is a software GL, 5× slower frames)
GPU = ["--use-angle=metal", "--ignore-gpu-blocklist", "--enable-gpu"] if sys.platform == "darwin" else []


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("bigboard"); lib, state = tmp / "lib", tmp / "lib/_review"
    (lib / "r").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    items, groups = {}, {}
    for n in range(2600):   # 40 groups of 65 pictures, 13 a row, as the page's rows of renderings
        Image.new("RGB", (8, 10), (n * 7 % 200 + 30, n * 13 % 200 + 30, 90)).save(lib / "r" / f"{n}.png")
        g, k = divmod(n, 65)
        items[f"p{n}"] = {"path": f"r/{n}.png", "x": (g % 4) * 5000 + (k % 13) * 360, "y": (g // 4) * 2400 + (k // 13) * 440, "w": 320, "ar": .8}
    for g in range(40):
        gx, gy = (g % 4) * 5000, (g // 4) * 2400
        groups[f"g{g}"] = {"title": f"r{g} · studio", "x": gx - 400, "y": gy - 80, "w": 5100, "h": 2300, "members": [f"p{n}" for n in range(g * 65, g * 65 + 65)]}
        for k in range(10 if g < 38 else 11):   # 420 notes, each a zone over a row of its group's pictures: a dot on each picture
            items[f"n{g}_{k}"] = {"type": "note", "text": f"# r{g} · {k}\nlight tent, 480×600", "color": "blue", "x": gx - 368 - k // 5 * 20, "y": gy + k % 5 * 440,
                                  "w": 320, "h": 180, "fs": 17.8, "size": 2, "to": [], "reach": {"l": 0, "t": 0, "r": 4800, "b": 220}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": groups, "removed": {}}))
    (tmp / "settings.json").write_text(json.dumps({"cv.theme": "dark", "cv.lang": "en", "cv.glass": "1"}))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp / "settings.json"), HYIMG_PROFILE_DIR=str(tmp),
               HYIMG_CACHE_ROOT=str(tmp / "cache"), PYTHONDONTWRITEBYTECODE="1")
    port = free_port(); log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port
    finally:
        proc.terminate(); proc.wait(5); log.close()


# while the zoom runs: the frames, every --z the board layer and the root get (the root: when a zoom stops, also for a pause on a busy
# Mac), and the most cards with --z, on screen and hidden
REC = """() => { const R = window.__R = { world: 0, root: 0, on: true, n: 0, shown: 0, hidden: 0 };
  const f = () => { if (!R.on) return; R.n++; let s = 0, h = 0; for (const el of document.getElementById('items').children) if (el.style.getPropertyValue('--z')) el.hidden ? h++ : s++;
    R.shown = Math.max(R.shown, s); R.hidden = Math.max(R.hidden, h); requestAnimationFrame(f); }; requestAnimationFrame(f);
  const watch = (el, k) => { let z0 = el.style.getPropertyValue('--z'); const mo = new MutationObserver(() => { const z = el.style.getPropertyValue('--z');
    if (z !== z0 && R.on) R[k]++; z0 = z; }); mo.observe(el, { attributes: true, attributeFilter: ['style'] }); return mo; };
  R.mos = [watch(document.getElementById('world'), 'world'), watch(document.documentElement, 'root')]; }"""
STOP = """() => { const R = window.__R; R.on = false; R.mos.forEach(m => m.disconnect()); return { world: R.world, root: R.root, shown: R.shown, hidden: R.hidden, n: R.n }; }"""


def test_big_board_zoom_restyles_only_whats_on_screen(server):
    asyncio.run(zoom(server))


async def zoom(port):
    async with playwright.async_playwright() as p:
        try: browser = await p.chromium.launch(args=GPU)
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        ctx = await browser.new_context(viewport={"width": 1680, "height": 1000}, device_scale_factor=2, color_scheme="dark")
        page = await ctx.new_page(); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        cdp = await ctx.new_cdp_session(page); await cdp.send("Performance.enable")
        await page.goto(f"http://127.0.0.1:{port}/canvas.html")
        await page.wait_for_function("() => typeof board !== 'undefined' && Object.keys(board.items).length >= 3000 && EL.size >= 3000", timeout=60000)
        assert await page.evaluate("() => document.documentElement.dataset.theme") == "dark"
        await page.evaluate("() => { cam = { x: -500, y: -300, z: 0.06 }; render(); }")
        await page.wait_for_timeout(3000)
        assert await page.evaluate("() => document.querySelectorAll('.mk-note i').length") > 2000, "the notes' dots on the pictures, as on the page"

        async def work():
            d = {x["name"]: x["value"] for x in (await cdp.send("Performance.getMetrics"))["metrics"]}
            return d["RecalcStyleDuration"] + d["LayoutDuration"]
        await page.evaluate(REC); before = await work()
        sent = []
        for k in range(120):   # a pinch: ⌃ wheel events every 16 ms whatever the page is doing (the browser coalesces them), 6 → 50 % and back
            sent.append(asyncio.ensure_future(cdp.send("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": 840, "y": 500, "deltaX": 0,
                                                                                    "deltaY": -3.5 if k < 60 else 3.5, "modifiers": 2})))
            await asyncio.sleep(0.016)
        await asyncio.gather(*sent)
        await page.wait_for_function("() => !gesture", timeout=20000)   # the zoom settles: --z back on the root, off the cards
        r = await page.evaluate(STOP); spent = await work() - before
        after = await page.evaluate("() => [document.documentElement.style.getPropertyValue('--z'), "
                                    "[...document.getElementById('items').children].filter(e => e.style.getPropertyValue('--z')).length, gesture, cam.z]")
        per_frame = spent * 1000 / max(1, r["n"])
        print(f"big board zoom: {r['n']} frames, style+layout {per_frame:.2f} ms a frame, --z: world {r['world']}, root {r['root']}, cards on screen {r['shown']}")
        assert r["n"] > 20
        # the cause: the board layer never gets the live --z, the cards on screen do and the hidden ones don't
        assert r["world"] == 0, r
        assert 0 < r["shown"] + r["hidden"] < 1000, r
        assert after[1] == 0 and not after[2] and abs(float(after[0]) - after[3]) < 1e-9, after
        assert per_frame <= MAX_STYLE_LAYOUT_MS, f"style and layout {per_frame:.2f} ms a zoom frame"
        assert not errors, errors
        await browser.close()
