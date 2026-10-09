"""Arrows between anything stay as light as the notes' arrows on a big page (owner 2026-10-09, «реализуй это» on «Agent layouts» › 4
Structures; the big page of test_perf_big_board.py: «что-то тормозит, очень сильно, просто ужасно лагает»). The page's scale: 2600
pictures in 40 groups, 420 notes with zones and 400 arrows, each from a picture of one group across a row of pictures of the next (so
its line is cut under the cards it crosses), half of them with words. Two pages of one board: «main» with 400 connectors, «notes»
with the same 400 arrows as notes' arrows (the drawing a69dc0b and 0cf175e measured and the owner works with). Measured on each, in the
same browser one after the other: one renderLinks pass with every arrow's markup written again, and a live zoom step (zLive, as a pinch
writes it) with its style and layout. The connectors may cost at most a quarter more than the notes' arrows: absolute times swing with
the Mac's load (a step of 24-110 ms here, load average 20)."""
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
from test_perf_big_board import GPU  # noqa: E402

RATIO = 1.25


def pages():
    items, groups, links = {}, {}, {}
    for n in range(2600):
        g, k = divmod(n, 65)
        items[f"p{n}"] = {"path": f"r/{n}.png", "x": (g % 4) * 5000 + (k % 13) * 360, "y": (g // 4) * 2400 + (k // 13) * 440, "w": 320, "ar": .8}
    for g in range(40):
        gx, gy = (g % 4) * 5000, (g // 4) * 2400
        groups[f"g{g}"] = {"title": f"r{g} · studio", "x": gx - 400, "y": gy - 80, "w": 5100, "h": 2300, "members": [f"p{n}" for n in range(g * 65, g * 65 + 65)]}
        for k in range(10 if g < 38 else 11):
            items[f"n{g}_{k}"] = {"type": "note", "text": f"# r{g} · {k}\nlight tent", "color": "blue", "x": gx - 368 - k // 5 * 20, "y": gy + k % 5 * 440,
                                  "w": 320, "h": 180, "fs": 17.8, "size": 2, "to": [], "reach": {"l": 0, "t": 0, "r": 4800, "b": 220}}
    for c in range(400):   # from a picture of one group to one across the row of the next group: over the pictures between
        g, k = divmod(c, 10); a, z = g * 65 + k, ((g + 1) % 40) * 65 + 12 - k
        links[f"c{c}"] = {"from": f"p{a}", "to": f"p{z}", **({"label": f"step {c}"} if c % 2 else {}), **({"style": "dashed"} if c % 3 == 0 else {})}
    main = {"schema": 1, "revision": 1, "items": items, "groups": groups, "removed": {}, "links": links}
    notes = json.loads(json.dumps({**main, "links": {}}))
    for c, (nid, l) in enumerate(zip([k for k in items if k.startswith("n")], links.values())): notes["items"][nid]["to"] = [l["to"]]
    return main, notes


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("bigarrows"); lib, state = tmp / "lib", tmp / "lib/_review"
    (lib / "r").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    for n in range(2600): Image.new("RGB", (8, 10), (n * 7 % 200 + 30, n * 13 % 200 + 30, 90)).save(lib / "r" / f"{n}.png")
    main, notes = pages()
    (state / "boards/main.json").write_text(json.dumps(main)); (state / "boards/notes.json").write_text(json.dumps(notes))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "Connectors"}, {"id": "notes", "title": "Notes"}]}))
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


DRAW = """() => { const t = []; for (let i = 0; i < 9; i++) { document.getElementById('links')._h = ''; const t0 = performance.now(); renderLinks();
  t.push(performance.now() - t0); } t.sort((a, b) => a - b); return t[4]; }"""
STEP = """() => { const t = []; for (let i = 0; i < 25; i++) { const q = (0.06 + 0.01 * (i % 12)).toFixed(4), t0 = performance.now(); zLive(q);
  document.getElementById('links').getBoundingClientRect(); document.body.offsetHeight; t.push(performance.now() - t0); } zLive(null);
  t.sort((a, b) => a - b); return t[12]; }"""


async def measure(ctx, port, page_id):
    page = await ctx.new_page(); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.goto(f"http://127.0.0.1:{port}/canvas.html?page={page_id}")
    await page.wait_for_function("() => typeof board !== 'undefined' && Object.keys(board.items).length >= 3000 && EL.size >= 3000", timeout=60000)
    await page.evaluate("() => { cam = { x: -500, y: -300, z: 0.06 }; render(); }")
    await page.wait_for_timeout(2500)
    arrows = await page.evaluate("() => document.querySelectorAll('#links .arw').length")
    cuts = await page.evaluate("() => document.querySelectorAll('#linkcuts clipPath').length")
    out = {"arrows": arrows, "cuts": cuts, "draw": [], "step": []}
    for _ in range(3):   # alternating rounds smooth the Mac's load out
        out["draw"].append(await page.evaluate(DRAW)); out["step"].append(await page.evaluate(STEP))
    assert not errors, errors
    await page.close()
    return out


def test_400_connectors_cost_as_400_note_arrows(server):
    asyncio.run(run(server))


async def run(port):
    async with playwright.async_playwright() as p:
        try: browser = await p.chromium.launch(args=GPU)
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        ctx = await browser.new_context(viewport={"width": 1680, "height": 1000}, device_scale_factor=2, color_scheme="dark")
        c, n = await measure(ctx, port, "main"), await measure(ctx, port, "notes")
        c2, n2 = await measure(ctx, port, "main"), await measure(ctx, port, "notes")
        med = lambda xs: sorted(xs)[len(xs) // 2]
        cd, nd = med(c["draw"] + c2["draw"]), med(n["draw"] + n2["draw"]); cs, ns = med(c["step"] + c2["step"]), med(n["step"] + n2["step"])
        print(f"400 arrows: renderLinks {cd:.1f} ms connectors / {nd:.1f} ms notes; a zoom step {cs:.1f} / {ns:.1f} ms; clip paths {c['cuts']} / {n['cuts']}")
        assert c["arrows"] == n["arrows"] == 400
        assert c["cuts"] >= 300, "the connectors' lines go under the pictures they cross"
        assert cd <= nd * RATIO + 2, f"renderLinks {cd:.1f} ms with connectors, {nd:.1f} ms with notes' arrows"
        assert cs <= ns * RATIO + 2, f"a zoom step {cs:.1f} ms with connectors, {ns:.1f} ms with notes' arrows"
        await browser.close()
