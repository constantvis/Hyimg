"""The performance log on a board (owner 2026-10-08: «лог, который пишется, только когда падает частота кадров, с тем, что было на
экране ... выключатель в Настройках, размер в Хранилище с «Очистить»»). Chromium, dark theme, a throwaway board with pictures, headings,
a note on a picture, a group and comment threads. Frames are made slow on purpose (a busy loop in a few animation frames while the wheel
pans): with the log off nothing is written; switched on in Settings › Diagnostics, one entry comes with what was on screen; Settings ›
Storage shows its size and «Clear» empties it."""
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

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_canvas_pages import free_port  # noqa: E402

ME = str(uuid.uuid4())
PICS = 12


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "a").mkdir(parents=True); (lib / "comments").mkdir(); (state / "boards").mkdir(parents=True)
    for n in range(PICS): Image.new("RGB", (300, 200), (40 + n * 15, 90, 150)).save(lib / "a" / f"{n}.png")
    items = {f"i{n}": {"path": f"a/{n}.png", "x": n % 4 * 340, "y": n // 4 * 240, "w": 300, "ar": 1.5, "crop": None} for n in range(PICS)}
    items["t1"] = {"type": "text", "text": "Round 3", "x": 0, "y": -140, "fs": 64, "size": 4, "w": 400, "h": 74}
    items["n1"] = {"type": "note", "text": "Softer light", "color": "yellow", "x": 1400, "y": 0, "w": 220, "h": 160, "to": ["i0"]}
    groups = {"g": {"title": "Figma", "x": -40, "y": -60, "w": 1400, "h": 800, "members": [f"i{n}" for n in range(PICS)]}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": groups, "removed": {}}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.theme": "dark", "cv.lang": "en"}))
    (tmp_path / "profile.json").write_text(json.dumps({"id": ME, "name": "Robin", "color": "blue", "created": ""}))
    t0 = time.strftime("%Y-%m-%dT%H:%M:%S")
    for k in range(3):
        th = {"id": f"c{k}", "page": "main", "anchor": None, "at": [200 + 300 * k, 650], "by": {"person": ME, "via": "app"}, "created": t0, "updated": t0,
              "resolved": None, "objects": [], "messages": [{"id": f"m{k}", "by": {"person": ME, "via": "app"}, "text": "look", "mentions": [], "created": t0}]}
        (lib / "comments" / f"main__c{k}.json").write_text(json.dumps(th))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"),
               HYIMG_PROFILE_DIR=str(tmp_path), HYIMG_CACHE_ROOT=str(tmp_path / "cache"), PYTHONDONTWRITEBYTECODE="1")
    port = free_port(); log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, tmp_path
    finally:
        process.terminate(); process.wait(5); log.close()


def get(port, path):
    return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10).read())


# six slow frames (90 ms of work each) while the wheel pans the board: an episode of frame drops
SLOW = """() => new Promise(done => { let k = 0;
  const burn = () => { const t = performance.now(); while (performance.now() - t < 90) {} if (++k < 6) requestAnimationFrame(burn); else done(); };
  requestAnimationFrame(burn); })"""


def jank(page):
    page.mouse.move(700, 450)
    page.mouse.wheel(0, 40)   # the board pans: the log watches its frames
    page.evaluate(SLOW)
    for _ in range(3): page.mouse.wheel(0, 20); page.wait_for_timeout(60)
    page.wait_for_timeout(1500)   # the episode ends half a second after the last slow frame


def test_the_log_writes_only_when_on_and_says_what_was_on_screen(server):
    port, tmp = server
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark"); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/canvas.html")
        page.wait_for_function("() => typeof board !== 'undefined' && Object.keys(board.items).length > 10 && document.querySelectorAll('.cmpin').length === 3", timeout=20000)
        assert page.evaluate("() => document.documentElement.dataset.theme") == "dark"
        # on by default (owner 2026-10-08); turned off in Settings › Diagnostics: frames drop, nothing is written
        # the settings' window opens on the section it showed last (ui/settings-win.js): Performance, the switch one click away, as before
        page.evaluate("() => hySetPanel.go('performance')")
        page.click("#bset"); page.wait_for_selector("#sets.open")
        page.click("#sets hy-switch[data-set-sw=perflog]")   # on: off
        page.click("#bset"); page.wait_for_selector("#sets:not(.open)", state="attached")
        jank(page)
        g = get(port, "/api/perflog?last=10")
        assert g["on"] is False and g["entries"] == [] and g["bytes"] == 0, g
        assert not (tmp / "cache" / "perf").exists()
        # on, from Settings › Diagnostics: it goes into the app's settings file
        page.click("#bset"); page.wait_for_selector("#sets.open"); page.evaluate("s => hySetPanel.go(s)", "performance")
        page.click("#sets hy-switch[data-set-sw=perflog]")   # off: on
        for _ in range(50):
            if json.loads((tmp / "settings.json").read_text()).get("cv.perflog") == "1": break
            time.sleep(0.1)
        assert json.loads((tmp / "settings.json").read_text()).get("cv.perflog") == "1"
        page.click("#bset"); page.wait_for_selector("#sets:not(.open)", state="attached")
        jank(page)
        g = get(port, "/api/perflog?last=10")
        assert g["on"] is True and len(g["entries"]) == 1, g
        e = g["entries"][0]
        assert e["page"] == "main" and e["action"] == "pan" and e["engine"] == "chrome", e
        assert e["counts"]["items"] == {"pic": PICS, "text": 1, "note": 1}, e["counts"]
        assert e["counts"]["visible"].get("pic", 0) + e["counts"]["visible"].get("pic (canvas)", 0) > 0, e["counts"]
        assert e["counts"]["pins"] == 3 and e["counts"]["groups"] == 1 and e["counts"]["dots"] >= 1, e["counts"]
        assert e["counts"]["liveFrames"] == 0 and e["panels"]["bell"] is False and isinstance(e["heapMB"], int), e
        assert e["frames"]["slow"] >= 3 and e["frames"]["worst"][0] >= 85, e["frames"]
        assert 0 < e["zoom"] and e["lod"]["mode"] in ("standard", "canvas", "webgl"), e
        files = list((tmp / "cache" / "perf").glob("perf-*.jsonl"))
        assert len(files) == 1 and len(files[0].read_text().splitlines()) == 1
        # a second drop within 5 s: held back, counted in the next entry
        jank(page)
        assert len(get(port, "/api/perflog?last=10")["entries"]) == 1
        # the agent's summary: hy.py perf through the board's server
        out = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "perf", "--last", "5", "--port", str(port)], capture_output=True, text=True, timeout=60)
        assert out.returncode == 0 and "Эпизодов: 1" in out.stdout and "pan" in out.stdout and "пинов 3" in out.stdout, out.stdout + out.stderr
        # Settings › Storage: the log's size, and «Clear» (asked first) empties it
        page.click("#bset"); page.wait_for_selector("#sets.open"); page.evaluate("s => hySetPanel.go(s)", "storage")
        row = page.locator("#hyStore .hs-row", has_text="Performance log")
        page.wait_for_function("() => [...document.querySelectorAll('#hyStore .hs-row')].some(r => /Performance log/.test(r.textContent) && /[1-9][\\d.,]* KB/.test(r.textContent))",
                               timeout=20000)   # the size as the panel measured it on opening
        row.locator("hy-button[data-hs=perflog]").click()
        page.wait_for_selector("#hyConfirm.on")
        assert "Clear the performance log" in page.locator("#hyConfirm").inner_text()
        page.locator("#hyConfirm [data-a=ok]").click()
        page.wait_for_function("() => [...document.querySelectorAll('#hyStore .hs-row')].some(r => /Performance log/.test(r.textContent) && /\\b0 KB/.test(r.textContent))", timeout=10000)
        assert get(port, "/api/perflog")["bytes"] == 0 and not list((tmp / "cache" / "perf").glob("perf-*.jsonl"))
        shots = os.environ.get("HYIMG_SHOTS")
        if shots: page.locator("#sets").screenshot(path=os.path.join(shots, "perflog-settings-dark.png"))
        assert not errors, errors
        browser.close()
