"""What a selected note links is outlined in that note's colour, and every card it links shows its dot (owner 2026-10-08: «почему я не
вижу, что синий тут влияет на эту группу: эти штуки желтым обведены, и нет точки сверху слева у объектов»).

- a blue note in a group with two HTML frames and two Dev HTML cards speaks for the whole group: selected, each card is outlined in
  blue (it was the theme's yellow: a plugin card had no --note of its own), and each shows a blue dot in its top left corner (an HTML
  frame has no other mark, the marks' law counted no note on a plugin card and switched all its marks off, .mkoff)
- a pink note with an arrow to one frame: that frame shows two dots, blue and pink; with the pink note selected only that frame is
  outlined, in pink
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

from test_canvas_pages import free_port

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
PLUGINS = {"frames": "hyimg-image-studio", "dev": "hyimg-dev-studio"}
PAGE = "<!doctype html><html><body style='background:#fff'><h1>A page</h1></body></html>"


def note(x, y, text, color, **kw):
    return {"type": "note", "text": text, "x": x, "y": y, "w": 720, "fs": 40, "size": 2, "h": 720, "color": color, "reach": None, "to": [], **kw}


def board():
    card = lambda t, src, x, y, **kw: {"type": t, "src": src, "vw": 1440, "x": x, "y": y, "w": 1440, "h": 900, **kw}
    return {"schema": 1, "revision": 1, "removed": {}, "items": {
        "n": note(-17, 0, "# Tabs with sleep · 3 variants\nwhich one", "blue"),
        "f1": card("htmlframe", "html/a/index.html", 1028, 0), "f2": card("htmlframe", "html/b/index.html", 2548, 0),
        "d1": card("html", "site/index.html", 1028, 1000, ar=1.6, pics=["site/index.html"]),
        "d2": card("html", "site2/index.html", 2548, 1000, ar=1.6, pics=["site2/index.html"]),
        "pk": note(1028, -1600, "Too dark", "pink", to=["f1"]),
    }, "groups": {"g": {"title": "Tabs", "x": -480, "y": -500, "w": 5580, "h": 3090, "members": ["f1", "f2", "d1", "d2", "n"]}}}


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in ("html/a", "html/b", "site", "site2"): (lib / d).mkdir(parents=True); (lib / d / "index.html").write_text(PAGE)
    for d in (state / "boards", plugins): d.mkdir(parents=True)
    for name, repo in PLUGINS.items():   # each plugin as its repository's last commit (other agents may be changing the working copies)
        src = ROOT.parent / repo
        if not (src / "manifest.json").is_file(): pytest.skip(f"{repo} is not beside this repository")
        raw = subprocess.run(["git", "-C", str(src), "archive", "HEAD"], capture_output=True, check=True).stdout
        (plugins / name).mkdir(); tarfile.open(fileobj=io.BytesIO(raw)).extractall(plugins / name, filter="data")
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
        yield port
    finally:
        proc.terminate(); proc.wait(5); log.close()


def shot(page, name):
    d = os.environ.get("HY_SHOTS")
    if d: Path(d).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(d) / name))


# each card: is it .linked, its outline colour, its dots (colour, width on screen, shown, the topmost element at the dot's centre)
STATE = """ids => { const rgb = c => { const d = document.createElement('i'); d.style.color = c; document.body.appendChild(d);
    const v = getComputedStyle(d).color; d.remove(); return v; };
  return { blue: rgb(noteCol(board.items.n)[0]), pink: rgb(noteCol(board.items.pk)[0]), cards: ids.map(id => { const el = EL.get(id), cs = getComputedStyle(el);
    return { id, linked: el.classList.contains('linked'), off: el.classList.contains('mkoff'), outline: cs.outlineColor, style: cs.outlineStyle,
      dots: [...el.querySelectorAll(':scope > .mk-note i')].map(i => { const r = i.getBoundingClientRect(), s = getComputedStyle(i.parentElement);
        const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
        return { c: getComputedStyle(i).backgroundColor, w: Math.round(r.width), shown: s.display !== 'none' && s.opacity === '1', top: top === i }; }) }; }) }; }"""
CARDS = ["f1", "f2", "d1", "d2"]


def test_selected_note_outlines_and_dots_in_its_colour(server):
    port = server
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg = b.new_page(viewport={"width": 1600, "height": 1000}, color_scheme="dark")
            pg.goto(f"http://127.0.0.1:{port}/canvas.html")
            pg.wait_for_function("typeof EL !== 'undefined' && EL.size >= 6 && [...EL.values()].filter(e => e.classList.contains('plg')).length === 4", timeout=20000)
            pg.evaluate("() => { sel = new Set(['n']); render(); if (typeof fitAll === 'function') fitAll(); }")
            pg.wait_for_timeout(1200)   # the marks grow in (.32 s)
            s = pg.evaluate(STATE, CARDS)
            shot(pg, "blue-note-selected.png")
            for c in s["cards"]:
                assert c["linked"], c
                assert c["outline"] == s["blue"] and c["style"] == "solid", c   # not the theme's yellow
                assert not c["off"], c
                blue = [d for d in c["dots"] if d["c"] == s["blue"]]
                assert len(blue) == 1 and blue[0]["shown"] and blue[0]["w"] >= 8 and blue[0]["top"], c
            f1 = next(c for c in s["cards"] if c["id"] == "f1")
            assert sorted(d["c"] for d in f1["dots"]) == sorted([s["blue"], s["pink"]]), f1   # a stack: the group's note and the arrow's
            assert all(len(c["dots"]) == 1 for c in s["cards"] if c["id"] != "f1")

            pg.evaluate("() => { sel = new Set(['pk']); render(); }")
            pg.wait_for_timeout(400)
            s = pg.evaluate(STATE, CARDS)
            shot(pg, "pink-note-selected.png")
            by = {c["id"]: c for c in s["cards"]}
            assert by["f1"]["linked"] and by["f1"]["outline"] == s["pink"], by["f1"]
            assert not any(by[k]["linked"] for k in ("f2", "d1", "d2"))
        finally:
            b.close()
