"""Every row of the bell shows what it is about (owner 2026-10-08: «Расстраивает, что нет картинок ... показать либо пространство,
либо прям этот объект, который выделен»): a comment on an area its crop with the area outlined in its author's colour, a free pin the
board around it, a group's news its members, an old notification with ids its pictures on read. Chromium, dark theme, a throwaway
board; the panel's screenshot goes to HYIMG_SHOTS when set."""
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

ME, ANN = str(uuid.uuid4()), str(uuid.uuid4())


def thread(tid, anchor, at, area, msgs):
    t0 = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 600))
    return {"id": tid, "page": "main", "anchor": anchor, "at": at, **({"area": area} if area else {}), "by": msgs[0][0], "created": t0, "updated": t0,
            "resolved": None, "objects": [anchor["obj"]] if anchor else [],
            "messages": [{"id": f"m{tid}{k}", "by": by, "text": text, "mentions": [],
                          "created": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 500 + k * 60))} for k, (by, text) in enumerate(msgs)]}


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "a").mkdir(parents=True); (lib / "comments").mkdir(); (state / "boards").mkdir(parents=True)
    colors = [(200, 60, 50), (60, 120, 200), (230, 180, 40), (70, 160, 90), (150, 90, 200), (230, 120, 60)]
    for n, c in enumerate(colors):
        im = Image.new("RGB", (600, 400), c); im.paste((245, 245, 245), (330, 80, 540, 300)); im.save(lib / "a" / f"{n}.png")
    items = {f"i{n}": {"path": f"a/{n}.png", "x": n % 3 * 640, "y": n // 3 * 440, "w": 600, "ar": 1.5, "crop": None} for n in range(6)}
    items["nt"] = {"type": "note", "text": "Свет мягче", "color": "yellow", "x": 2000, "y": 0, "w": 260, "h": 200}
    groups = {"g": {"title": "Референсы", "x": -40, "y": -60, "w": 1960, "h": 960, "members": [f"i{n}" for n in range(5)]}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": groups, "removed": {}}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.theme": "dark", "cv.lang": "ru"}))
    (tmp_path / "profile.json").write_text(json.dumps({"id": ME, "name": "Robin", "color": "blue", "created": ""}))
    (tmp_path / "people.json").write_text(json.dumps({ANN: {"name": "Ann", "color": "green", "seen": 1}}))
    me_claude, ann = {"person": ME, "via": "claude"}, {"person": ANN, "via": "app"}
    for t in (thread("carea1", {"obj": "i1", "kind": "picture", "file": "a/1.png"}, [.9, .2], [.55, .2, .35, .55],
                     [(ann, "Блик слишком яркий"), (me_claude, "Убрал блик, смотри новый вариант")]),
              thread("cfree1", None, [2130, 100], None, [(ann, "Сюда положить варианты")])):
        (lib / "comments" / f"main__{t['id']}.json").write_text(json.dumps(t, ensure_ascii=False))
    old = [{"id": "201008000000-ab12", "t": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 3600)), "read": False,
            "title": "На доске новое: 2 объекта", "text": "", "who": "Claude", "page": "main", "ids": ["i5", "nt"], "previews": []}]
    (state / "notifications.json").write_text(json.dumps(old, ensure_ascii=False))
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


def call(port, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}", "X-Hyimg-Agent": "Claude"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def test_every_bell_row_shows_what_it_is_about(server):
    port, tmp = server
    call(port, "/api/notifications", {"action": "add", "title": "На доске новое: 1 группа", "text": "Собрал референсы", "who": "Claude",
                                      "page": "main", "ids": ["g"]})
    items = {n["id"]: n for n in call(port, "/api/notifications")["items"]}
    group = next(n for n in items.values() if n["title"].endswith("1 группа"))
    stored = json.loads((tmp / "state" / "notifications.json").read_text())
    assert len(stored[-1]["pv"]) == 4 and stored[-1]["pvn"] == 5, "written when it was made (notifplace.tiles)"
    assert "pv" not in stored[0], "an old one stays as it was on disk"
    old = items["201008000000-ab12"]
    assert old["pvn"] == 2 and old["pv"][0]["k"] == "pic", "an old one gets its pictures on read"
    reply = next(n for n in items.values() if n["id"].startswith("c:carea1:") and n["title"] in ("Reply in a thread", "Ответ в обсуждении"))
    assert reply["pv"][0]["k"] == "crop" and "r" in reply["pv"][0]["mark"] and reply["pv"][0]["who"] == ANN
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 1000}, color_scheme="dark", device_scale_factor=2); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && BOARD === 'main'", timeout=15000)
        assert page.evaluate("() => document.documentElement.dataset.theme") == "dark"
        page.wait_for_function("() => NTF.items.length >= 5", timeout=15000)
        page.click("#bntf"); page.wait_for_selector("#ntf.open .nt .pv")
        # the space is there before the pictures: every tile has its size from the start
        sizes = page.evaluate("() => [...document.querySelectorAll('#ntf .bt')].map(e => [e.dataset.k, e.offsetWidth, e.offsetHeight])")
        assert sizes and all(s[1:] in ([48, 48], [72, 48], [144, 96]) for s in sizes), sizes
        page.wait_for_function("() => [...document.querySelectorAll('#ntf .bt img')].every(i => i.complete && i.naturalWidth > 0)", timeout=30000)
        row = lambda nid: f"#ntf .nt[data-n='{nid}']"
        # the reply on an area: one large crop, the area outlined in Ann's colour (green), the picture's own light patch inside it
        r = page.evaluate("""q => { const b = document.querySelector(q + ' .bt'), m = b.querySelector('.ma'), i = b.querySelector('img');
            return { cls: b.className, color: getComputedStyle(m).borderTopColor, w: m.offsetWidth, h: m.offsetHeight,
                     nat: i.naturalWidth }; }""", row(reply["id"]))
        assert r["cls"] == "bt l" and r["color"] == "rgb(127, 212, 155)" and r["w"] > 30 and r["h"] > 30 and r["nat"] == 360, r
        # the free pin: the board around it (the note lies there), the dot in the middle
        free = next(n for n in items.values() if n["id"].startswith("c:cfree1:"))
        f = page.evaluate("q => { const b = document.querySelector(q + ' .bt'); return [b.dataset.k, !!b.querySelector('.mp')]; }", row(free["id"]))
        assert f == ["region", True], f
        # the group: four of its five pictures, then +1; the old one: the picture and the note's place
        g = page.evaluate("q => [document.querySelectorAll(q + ' .bt').length, (document.querySelector(q + ' .bmore') || {}).textContent]", row(group["id"]))
        assert g == [4, "+1"], g
        o = page.evaluate("q => [...document.querySelectorAll(q + ' .bt')].map(b => b.dataset.k)", row(old["id"]))
        assert o == ["pic", "region"], o
        shots = os.environ.get("HYIMG_SHOTS")
        if shots: page.locator("#ntf").screenshot(path=os.path.join(shots, "bell-thumbs-dark.png"))
        assert not errors, errors
        browser.close()
