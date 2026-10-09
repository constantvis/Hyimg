"""Pages switch fast (owner 2026-10-08, «Board structure» › «Pages switch fast»: «pages stay asleep in the background, coming back is
instant») and glass notes in the «Luminous edge» look (2026-10-09, «Glass notes», Concepts/html/notes-glass/g3-edge.html).

The page left falls asleep with its elements (ui/pagesleep.js); coming back shows them at once, before the server answers (its answer is
held back here), with the same <img> elements, and then brings them up to date with what changed on the server meanwhile: a moved
picture moves, a removed one goes, a new note comes. Chromium, dark, a temporary library.

  nice -n 10 python3 -m pytest -q tests/test_page_sleep.py
"""
import json
import time
import urllib.request

import pytest

from test_canvas_pages import board, free_port, png  # noqa: F401  (the same temporary pages)

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def server(tmp_path):
    import os, subprocess, sys, uuid
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    lib, state = tmp_path / "lib", tmp_path / "state"
    for folder in ("a", "b"):
        (lib / folder).mkdir(parents=True)
        for n in range(30): (lib / folder / f"{n}.png").write_bytes(png())
    (state / "boards").mkdir(parents=True)
    a = board("a", 30, 0)
    a["items"]["n1"] = {"type": "note", "text": "Keep this blue", "x": 40, "y": 60, "w": 320, "fs": 24, "size": 2, "h": 0, "color": "yellow", "to": []}
    (state / "boards/main.json").write_text(json.dumps(a))
    (state / "boards/p2.json").write_text(json.dumps(board("b", 30, 100)))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "A"}, {"id": "p2", "title": "B"}]}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(root / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port
    finally:
        proc.terminate(); proc.wait(5); log.close()


def api(port, path, body=None):
    rq = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(rq))


def test_a_page_sleeps_and_wakes_at_once_up_to_date(server):
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1200, "height": 800}, color_scheme="dark")
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.cam.main', JSON.stringify({x: -40, y: -40, z: 0.6})); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 31 && EL.size === 31")
        # the camera at 60 %, near view (the first load's fitted camera may be saved late over the one set before the reload)
        page.evaluate("() => { cam = { x: -40, y: -40, z: 0.6 }; renderCam(); render(); saveCam(); }")
        page.wait_for_function("() => !document.querySelector('#world').classList.contains('lod')")
        # glass notes: «Luminous edge»
        g = page.evaluate("""() => { const s = getComputedStyle(document.querySelector('.note[data-id=n1]'));
          return { glass: stage.classList.contains('glass'), bf: s.backdropFilter || s.webkitBackdropFilter, sh: s.boxShadow, bg: s.backgroundColor }; }""")
        assert g["glass"] and "saturate(2.3)" in g["bf"] and "brightness(1.2)" in g["bf"], g
        assert "inset" in g["sh"] and g["sh"].count("rgb") >= 3, g   # the rim inside, the coloured ring and glow outside
        page.evaluate("() => { EL.get('i0').__probe = 7; EL.get('i0').querySelector('img').__probe = 8; }")
        page.evaluate("() => switchPage('p2')")
        page.wait_for_function("() => BOARD === 'p2' && Object.keys(board.items).length === 30")
        assert page.evaluate("() => hyPageSleep.has('main') && !document.querySelector('#items [data-id=i0]') && !EL.has('i0')")
        b = api(server, "/api/board?name=main")   # meanwhile an agent moves a picture, removes one and adds a note on the sleeping page
        b["items"]["i0"]["x"] += 2000; b["items"].pop("i1")
        b["items"]["n2"] = {"type": "note", "text": "new", "x": 700, "y": 60, "w": 320, "fs": 24, "size": 2, "h": 0, "color": "blue", "to": []}
        api(server, "/api/board?name=main", b)
        # the server's answer comes 1.5 s late (held in the page, so the browser goes on); the wake is timed in the page, each frame
        page.evaluate("""() => { const of = window.fetch; window.fetch = (u, o) => String(u).includes('/api/board?name=main') && !(o && o.method)
            ? new Promise(r => setTimeout(r, 1500)).then(() => of(u, o)) : of(u, o);
          window.__t0 = performance.now(); window.__w = null; switchPage('main');
          const f = () => { if (BOARD === 'main' && EL.has('i0')) window.__w = { dt: performance.now() - __t0, fresh: !!board.items.n2, z: cam.z,
            same: EL.get('i0').__probe === 7 && EL.get('i0').querySelector('img').__probe === 8, shown: !!document.querySelector('#items [data-id=i0]') };
            else requestAnimationFrame(f); }; f(); }""")
        page.wait_for_function("() => window.__w", timeout=5000)
        early = page.evaluate("() => window.__w")
        assert early["same"] and early["shown"] and not early["fresh"] and early["dt"] < 900 and abs(early["z"] - 0.6) < 1e-6, early
        page.wait_for_function("() => !!document.querySelector('.note[data-id=n2]') && !document.querySelector('#items [data-id=i1]')", timeout=10000)
        late = page.evaluate("""() => ({ same: EL.get('i0').__probe === 7, x: parseFloat(EL.get('i0').style.left), gone: !document.querySelector('#items [data-id=i1]'),
          n2: !!document.querySelector('.note[data-id=n2]'), count: EL.size, asleep: hyPageSleep.pages })""")
        assert late["same"] and late["x"] == 2000 and late["gone"] and late["n2"] and late["count"] == 31, late
        assert late["asleep"] == ["p2"], late
        assert not errors, errors
        browser.close()
