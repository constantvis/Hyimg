"""A note links any object on the board as it links a picture (owner 2026-10-07: «Почему я не могу HTML указать: ноут добавить, и чтобы
он так же, как на картинку, ссылался? Что 3D, что картинка, неважно что, это объект»).

- a note lying on an HTML frame, a note whose area holds a 3D card and an arrow drawn with the mouse to a Dev HTML card: each links it,
  the Info names it by its kind («linked: 1 HTML page · the AI reads it with them»), the card shows as the selected note's target
- while the arrow is drawn the card under the pointer is the target (.linktarget), letting go adds it to the note's arrows
- the card's own Info lists the board's notes about it, as a picture's does
- saved: the note files list the cards by id ("objects"), the board's notes index maps item id -> notes, hy.py find prints the note
  under the card; the user's .html files are not written
- a picture keeps "related_notes" in its json and its Info line as before
Chromium, dark theme, temporary libraries only (the plugins from their repositories' last commits). HY_SHOTS=<folder> keeps screenshots."""
import io
import json
import os
import subprocess
import sys
import tarfile
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
PLUGINS = {"frames": "hyimg-frames", "3d": "hyimg-3d-studio", "dev": "hyimg-dev-studio"}
PAGE = "<!doctype html><html><head><title>Site</title></head><body><h1>A page</h1></body></html>"


def note(x, y, text, w=120, **kw):
    return {"type": "note", "text": text, "x": x, "y": y, "w": w, "fs": w / 18, "size": 2, "h": 0, "color": "yellow", "reach": None, "to": [], **kw}


def board():
    return {"schema": 1, "revision": 1, "groups": {}, "removed": {}, "items": {
        "p": {"path": "a/0.png", "x": 0, "y": 0, "w": 300, "ar": 1.5, "crop": None},
        "hf": {"type": "htmlframe", "src": "html/x/index.html", "vw": 1280, "x": 400, "y": 0, "w": 400, "h": 250},
        "m": {"type": "model3d", "empty": True, "x": 0, "y": 400, "w": 400, "h": 300},
        "d": {"type": "html", "src": "site/index.html", "vw": 1280, "ar": 1.6, "x": 600, "y": 400, "w": 400, "h": 250, "pics": ["site/index.html"]},
        "n1": note(650, 150, "About the frame"),
        "n2": note(-300, 400, "About the scene", reach={"l": 20, "t": 20, "r": 750, "b": 300}),
        "n3": note(-300, -60, "Arrow to dev"),
        "n4": note(100, 50, "About the picture", w=100),
    }}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in (lib / "a", lib / "html/x", lib / "site", state / "boards", plugins): d.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png(60, 40)); (lib / "html/x/index.html").write_text(PAGE); (lib / "site/index.html").write_text(PAGE)
    have = []
    for name, repo in PLUGINS.items():   # each plugin as its repository's last commit (other agents may be changing the working copies)
        src = ROOT.parent / repo
        if not (src / "manifest.json").is_file(): continue
        raw = subprocess.run(["git", "-C", str(src), "archive", "HEAD"], capture_output=True, check=True).stdout
        (plugins / name).mkdir(); tarfile.open(fileobj=io.BytesIO(raw)).extractall(plugins / name, filter="data"); have.append(name)
    if len(have) < 3: pytest.skip("the frames, 3D and Dev plugins' repositories are not beside this one")
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HYIMG_PLUGINS=str(plugins), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, lib, state, env
    finally:
        proc.terminate(); proc.wait(5); log.close()


def api(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r: return json.load(r)


def shot(page, name):
    d = os.environ.get("HY_SHOTS")
    if d: Path(d).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(d) / name))


INFO = "id => { sel = new Set([id]); render(); return [$('#iM').textContent, $('#iP').textContent]; }"
CENTRE = "s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }"


def test_a_note_links_html_frames_3d_and_dev_cards(server):
    port, lib, state, env = server
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{port}/canvas.html"
        page.goto(url)
        page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
          localStorage.setItem('cv.cam.main', JSON.stringify({ x: -400, y: -150, z: .75 })); }""")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && PLG.htmlframe && PLG.model3d && PLG.html && EL.get('hf') && EL.get('m') && EL.get('d') && EL.get('n3')", timeout=30000)
        errors.clear()
        assert page.evaluate("() => document.documentElement.dataset.theme || getComputedStyle(document.body).colorScheme") != "light"

        # the old way still holds for a picture: its line and its outline as before
        assert page.evaluate(INFO, "n4") == ["linked: 1 frame · goes into these frames' json", "0"]
        # a note on an HTML frame, a note whose area holds a 3D card
        m1, l1 = page.evaluate(INFO, "n1")
        assert m1 == "linked: 1 HTML page · the AI reads it with them" and "html/x/index.html" in l1
        assert page.evaluate("() => EL.get('hf').classList.contains('linked') && !EL.get('d').classList.contains('linked')")
        shot(page, "note-on-html-frame.png")
        m2, l2 = page.evaluate(INFO, "n2")
        assert m2 == "linked: 1 3D scene · the AI reads it with them" and page.evaluate("() => EL.get('m').classList.contains('linked')")
        shot(page, "note-area-3d.png")

        # an arrow drawn with the mouse from the note's dot to the Dev HTML card
        page.evaluate("() => { sel = new Set(['n3']); render(); }")
        assert "not linked" in page.evaluate(INFO, "n3")[0]
        x0, y0 = page.evaluate(CENTRE, ".cn[data-connect=n3]")
        x1, y1 = page.evaluate(CENTRE, ".plg[data-id=d]")
        page.mouse.move(x0, y0); page.mouse.down()
        for k in range(1, 11): page.mouse.move(x0 + (x1 - x0) * k / 10, y0 + (y1 - y0) * k / 10)
        assert page.evaluate("() => [...document.querySelectorAll('.linktarget')].map(e => e.dataset.id)") == ["d"]
        shot(page, "arrow-to-dev-card-drawing.png")
        page.mouse.up()
        assert page.evaluate("() => board.items.n3.to") == ["d"]
        assert page.evaluate(INFO, "n3")[0] == "linked: 1 HTML page · the AI reads it with them"
        assert page.evaluate("() => EL.get('d').classList.contains('linked')")
        shot(page, "arrow-to-dev-card.png")

        # the card's Info lists the note, as a picture's does
        page.evaluate("() => { sel = new Set(['d']); render(); }")
        notes = page.evaluate("() => [...document.querySelectorAll('#iNotes .inote')].map(b => b.textContent)")
        assert len(notes) == 1 and "Arrow to dev" in notes[0] and "by an arrow" in notes[0]
        shot(page, "dev-card-info-notes.png")

        # saved: the files say it by id, the agent sees it
        for _ in range(60):
            if api(port, "/api/board?name=main")["items"]["n3"]["to"] == ["d"]: break
            time.sleep(0.25)
        assert api(port, "/api/board?name=main")["items"]["n3"]["to"] == ["d"]
        for _ in range(40):
            if (lib / "notes/main__n3.json").exists(): break
            time.sleep(0.25)
        objs = lambda n: {o["id"]: (o["kind"], o["via"]) for o in json.loads((lib / f"notes/main__{n}.json").read_text())["objects"]}
        assert objs("n1") == {"hf": ("html", ["overlap"])} and objs("n2") == {"m": ("3d", ["zone"])} and objs("n3") == {"d": ("html", ["arrow"])}
        idx = json.loads((state / "boards/main.notes-index.json").read_text())
        assert idx["items"]["d"] == [{"note": "main/n3", "via": ["arrow"]}] and idx["items"]["m"] == [{"note": "main/n2", "via": ["zone"]}]
        assert json.loads((lib / "a/0.json").read_text())["related_notes"] == [{"note": "main/n4", "via": ["overlap"]}]
        assert (lib / "site/index.html").read_text() == PAGE and (lib / "html/x/index.html").read_text() == PAGE
        assert sorted(os.listdir(lib / "site")) == ["index.html"]
        assert api(port, "/api/notes?name=main")["n3"]["objects"][0]["file"] == "site/index.html"
        hy = lambda *a: subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "--page", "main", *a], env={**env, "HYIMG_PORT": str(port)},
                                       capture_output=True, text=True, timeout=60).stdout
        assert "заметка «Arrow to dev» (стрелка) [n3]" in hy("find", "site/index.html")
        assert "заметка «About the frame» (лежит на нем) [n1]" in hy("find", "html/x")
        assert "→ HTML 1" in hy("map", "n3")
        assert errors == []
        browser.close()
