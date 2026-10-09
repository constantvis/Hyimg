"""Every notification has a place on the board (owner 2026-10-08: one notification in the bell moved him nowhere: the agent wrote it
without ids). hy.py notify without --ids names what the agent put on the page from the page's events; a click on a notification that
still has no place opens its page and says so instead of doing nothing. Chromium, dark theme, a throwaway board."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_canvas_pages import board, free_port, png  # noqa: E402


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "b").mkdir(parents=True)
    for n in range(4): (lib / "b" / f"{n}.png").write_bytes(png())
    (state / "boards").mkdir(parents=True)
    (state / "boards/main.json").write_text(json.dumps(board("b", 1, 0)))
    (state / "boards/p2.json").write_text(json.dumps(board("b", 1, 100)))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "A"}, {"id": "p2", "title": "B"}]}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.theme": "dark"}))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"),
               PYTHONDONTWRITEBYTECODE="1")
    port = free_port(); log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, env
    finally:
        process.terminate(); process.wait(5); log.close()


def call(port, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}", "X-Hyimg-Agent": "Claude"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def test_notify_without_ids_finds_its_things_and_a_placeless_click_opens_the_page(server):
    port, env = server
    b = call(port, "/api/board?name=p2")   # the agent puts two pictures on page B, then tells the owner without naming them
    b["items"].update({"r1": {"path": "b/2.png", "x": 2000, "y": 0, "w": 320, "ar": 2 / 3, "crop": None},
                       "r2": {"path": "b/3.png", "x": 2400, "y": 0, "w": 320, "ar": 2 / 3, "crop": None}})
    call(port, "/api/board?name=p2&who=ai&agent=Claude", b)
    out = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "notify", "Положил референсы рядом с раскадровкой", "--page", "p2", "--port", str(port)],
                         env={**env, "HYIMG_AGENT": "Claude"}, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    told = call(port, "/api/notifications")["items"][0]
    assert told["ids"] == ["r1", "r2"] and told["area"]["x"] == 2000 and told["previews"] == ["b/2.png", "b/3.png"], told
    assert told["text"].startswith("На доске новое: 2 кадра"), (told["text"], out.stdout)
    assert "ВНИМАНИЕ" not in out.stdout
    # nothing new since: this one stays without a place, and hy.py says so
    out = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "notify", "Подумал о монтаже", "--page", "p2", "--port", str(port)],
                         env={**env, "HYIMG_AGENT": "Claude"}, capture_output=True, text=True, timeout=60)
    assert "ВНИМАНИЕ: уведомление без места" in out.stdout, out.stdout
    bare = call(port, "/api/notifications")["items"][0]
    assert bare["ids"] == [] and "area" not in bare
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark"); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && BOARD === 'main'", timeout=15000)
        assert page.evaluate("() => document.documentElement.dataset.theme") == "dark"
        page.click("#bntf"); page.wait_for_selector("#ntf.open .nt")
        page.click(f"#ntf .nt[data-n='{bare['id']}']")
        page.wait_for_function("() => BOARD === 'p2'", timeout=15000)
        page.wait_for_function("() => [...document.querySelectorAll('#hyToasts .ht')].some(e => /no place on the board/.test(e.textContent))", timeout=5000)
        page.click("#bntf"); page.wait_for_selector("#ntf.open .nt")
        page.click(f"#ntf .nt[data-n='{told['id']}']")   # the one with a place: its pictures, selected
        page.wait_for_function("() => sel.size === 2 && sel.has('r1') && sel.has('r2')", timeout=5000)
        assert not errors, errors
        browser.close()
