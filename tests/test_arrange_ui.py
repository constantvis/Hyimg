"""Arrange › for the owner (owner 2026-10-09: «Что у нас с нашим Arrange? Почему у меня нет кнопок для Arrange новых, которые мы
разработали ... сетка, таблица, вот это вот все. Где это все? Почему я не вижу этого?»), in Chromium, dark, on a temporary library.

- the right click's «Arrange ›» has Tidy (⌥A ⌥S ⌥D), Make grid, Make table, Remove grid and «Layout patterns ›» with the ten patterns;
  each row is grey with its reason when the selection cannot have it (one picture, no timeline, already a table)
- A / B, Timeline + batches (under a phase) and Make table on the selection give the page exactly what the agent's hy.py command (the
  one the answer names) gives on a copy of the same page; one ⌘Z puts the page back
- the bar over a selection has the button that opens the same menu, the shortcuts panel lists Arrange
Screenshots (dark) go to $HY_SHOTS when it is set."""
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
SHOTS = os.environ.get("HY_SHOTS")
PICS = [f"a{k}" for k in range(4)] + [f"b{k}" for k in range(4)]


def board():
    pic = lambda k, x, y: {"path": f"a/{k}.png", "x": x, "y": y, "w": 300, "ar": 1.5, "crop": None}
    items = {f"a{k}": pic(f"a{k}", k * 340, 0) for k in range(4)}
    items.update({f"b{k}": pic(f"b{k}", k * 340, 400) for k in range(4)})
    items["tl"] = {"type": "timeline", "dir": "h", "fs": 24, "len": 1200, "x": 0, "y": -700, "w": 1200, "h": 0,
                   "points": [{"id": "p1", "t": 0, "text": "P1"}, {"id": "p2", "t": 900, "text": "P2"}]}
    items["n1"] = {"type": "note", "text": "a note", "x": -900, "y": 0, "w": 300, "fs": 18, "color": "yellow", "to": []}
    return {"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    for k in PICS: (lib / f"a/{k}.png").write_bytes(png(60, 40))
    for name in ("main", "c-ab", "c-tl", "c-table"): (state / f"boards/{name}.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HY_TEST_ONLY_PLUGINS="1", PYTHONDONTWRITEBYTECODE="1",
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


def api(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r: return json.load(r)


def hy_do(port, page, cmd):
    """the command the board's answer names (hy.py do '…'), run by hy.py on another page"""
    words = shlex.split(cmd); assert words[:2] == ["hy.py", "do"], cmd
    env = {k: v for k, v in os.environ.items() if not k.startswith("HYIMG_")}
    env.update(HYIMG_PORT=str(port), HYIMG_AGENT="test")
    out = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "do", words[2], "--page", page, "--quiet"], env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr + out.stdout
    return api(port, f"/api/board?name={page}")


def shape(b, orig):
    """a page with its new things named by what they are and where (their ids are random), stamps left out: two pages laid out alike
    compare equal"""
    I, G = b.get("items") or {}, b.get("groups") or {}
    key = {k: k if k in orig else f"{it.get('type')}:{it.get('text')}:{round(it['x'])}:{round(it['y'])}" for k, it in I.items()}
    key.update({k: k if k in orig else f"group:{g.get('title')}:{round(g['x'])}:{round(g['y'])}" for k, g in G.items()})
    clean = lambda it: {f: v for f, v in it.items() if f not in ("by",)}
    return {"items": {key[k]: clean(it) for k, it in I.items()},
            "groups": {key[k]: {**clean(g), "members": sorted(key[m] for m in g.get("members", []))} for k, g in G.items()},
            "grids": sorted((json.dumps({**g, "members": [key[m] for m in g["members"]]}, sort_keys=True) for g in (b.get("grids") or {}).values())),
            "links": sorted((key[c["from"]], key[c["to"]], c.get("label") or "", c.get("style") or "", c.get("color") or "")
                            for c in (b.get("links") or {}).values())}


LIVE = "() => JSON.parse(JSON.stringify({ items: board.items, groups: board.groups, grids: board.grids || {}, links: board.links || {} }))"
SNAP = "() => { const o = JSON.parse(HY.snap()); delete o.sel; return o; }"
CENTRE = "id => { const r = EL.get(id).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }"


def close(page):
    page.evaluate("() => { window.hyMenuSubClose && hyMenuSubClose(); ctxClose(); }")


def menu(page, ids, *path):
    """select ids, right click the first, open Arrange › and the submenus on path; the last panel's rows: {how/op: reason or ''}"""
    close(page)
    page.evaluate("ids => { sel = new Set(ids); render(); }", ids)
    x, y = page.evaluate(CENTRE, ids[0])
    page.mouse.click(x, y, button="right")
    page.wait_for_selector("#ctx.open")
    for sub in ("arrange", *path):
        page.locator(f'#ctx [data-sub="{sub}"]').last.click()
        page.wait_for_selector(f'#ctx [data-sub="{sub}"][aria-expanded="true"]')
    return page.evaluate("""() => { const ps = [...document.querySelectorAll('#ctx .hy-sub')], p = ps[ps.length - 1];
      return Object.fromEntries([...p.querySelectorAll(':scope > [role=menuitem]')].map(b =>
        [b.dataset.ph !== undefined ? b.dataset.ph : b.dataset.op || b.dataset.how || b.dataset.sub, b.getAttribute('aria-disabled') === 'true' ? b.title : '']));
    }""")


def shot(page, name):
    if SHOTS: Path(SHOTS).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def seed(port, page, b):
    """the copy page starts from exactly what the board sent (as the board measured it)"""
    have = api(port, f"/api/board?name={page}")
    body = {**have, **{k: b[k] for k in ("items", "groups", "grids", "links", "removed") if k in b}}
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/board?name={page}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    assert urllib.request.urlopen(req, timeout=10).status == 200


def apply(page, port, ids, path, row, copy):
    """run one Arrange row on ids: the page the server laid out equals what the agent's hy.py command (the one the answer names) makes on
    a copy of the same page; the board took that page (grids, places); one ⌘Z puts it back"""
    before = page.evaluate(SNAP)
    seed(port, copy, before)
    page.evaluate("() => { hyArrange.last = null; }")
    menu(page, ids, *path)
    page.locator(f"#ctx .hy-sub {row}").last.click()
    page.wait_for_function("() => hyArrange.last", timeout=15000)
    last = page.evaluate("() => hyArrange.last")
    orig = set(before["items"]) | set(before["groups"])
    other = hy_do(port, copy, last["cmd"])
    A, B = shape(other, orig), shape(last["board"], orig)
    diff = {k: (A["items"].get(k), B["items"].get(k)) for k in set(A["items"]) | set(B["items"]) if A["items"].get(k) != B["items"].get(k)}
    assert not diff, (last["cmd"], json.dumps(diff, ensure_ascii=False)[:1500])
    assert A == B, last["cmd"]
    live = page.evaluate(LIVE); L = shape(live, orig)
    assert L["grids"] == B["grids"] and L["links"] == B["links"] and L["groups"] == B["groups"]
    assert {k: (it["x"], it["y"]) for k, it in L["items"].items()} == {k: (it["x"], it["y"]) for k, it in B["items"].items()}
    shot(page, f"3-{last['op']}-laid-out")
    page.keyboard.press("Control+z")
    assert page.evaluate(SNAP) == before, "one ⌘Z puts the page back"
    return last, live


def test_arrange_menu_and_layouts_match_the_agents(server):
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1500, "height": 950}, color_scheme="dark")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');"
                      " localStorage.setItem('cv.page', 'main'); localStorage.setItem('cv.cam.main', JSON.stringify({ x: -1000, y: -800, z: .5 })); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && window.hyArrange && window.hyGrid && EL.get('a0') && EL.get('b3')", timeout=30000)

        # one picture: the rows that need two are grey with the reason, the timeline row is there (it needs one), flow needs two things
        rows = menu(page, ["a0"])
        two = "Select two or more pictures or cards"
        assert rows == {"grid": two, "row": two, "smart": two, "make": two, "table": two, "remove": "Not in a grid", "layouts": ""}, rows
        rows = menu(page, ["a0"], "layouts")
        assert rows == {"variants": two, "ab": two, "phases": "", "directions": two, "docs": two, "before-after": two, "moodboard": two,
                        "review": two, "flow": "Select two or more things to join", "glossary": two}, rows
        # eight pictures: everything but «Remove grid»; the timeline's phases and a new one
        rows = menu(page, PICS)
        assert rows == {"grid": "", "row": "", "smart": "", "make": "", "table": "", "remove": "Not in a grid", "layouts": ""}, rows
        assert all(v == "" for v in menu(page, PICS, "layouts").values())
        shot(page, "1-arrange-layout-patterns")
        assert menu(page, PICS, "layouts", "phases") == {"p1": "", "p2": "", "": ""}
        close(page)

        # A / B: the two rows are A and B, a table under its title, numbered A1 B1 …; the agent's command makes the same page
        last, live = apply(page, server, PICS, ["layouts"], '[data-op="ab"]', "c-ab")
        assert "pattern ab" in last["cmd"] and "a0,a1,a2,a3" in last["cmd"] and "b0,b1,b2,b3" in last["cmd"], last["cmd"]
        g = next(iter(live["grids"].values()))
        assert g["cols"] == 2 and g["num"] == "rc" and g["head"] == {"row": True} and g["members"][2:] == ["a0", "b0", "a1", "b1", "a2", "b2", "a3", "b3"]
        assert [live["items"][m]["text"] for m in g["members"][:2]] == ["A", "B"]
        assert any(it.get("type") == "note" and it.get("pattern") == "ab" and it.get("color") == "yellow" for it in live["items"].values())

        # Timeline + batches: the batch goes under the phase P2, numbered 1 … 8
        last, live = apply(page, server, PICS, ["layouts", "phases"], '[data-ph="p2"]', "c-tl")
        assert "pattern timeline" in last["cmd"] and "phase=p2" in last["cmd"], last["cmd"]
        g = next(iter(live["grids"].values()))
        assert g["num"] == "seq" and sorted(g["members"]) == PICS
        tl = live["items"]["tl"]
        assert all(live["items"][m]["y"] > tl["y"] for m in PICS)

        # Make table: a heading row A B C D and a column 1 2, the title in the corner, the first picture where it was
        last, live = apply(page, server, PICS, [], '[data-how="table"]', "c-table")
        assert last["cmd"].startswith("hy.py do 'table"), last["cmd"]
        g = next(iter(live["grids"].values()))
        texts = [live["items"][m].get("text") for m in g["members"] if live["items"][m].get("type") == "text"]
        assert g["cols"] == 5 and g["head"] == {"row": True, "col": True} and texts == ["Table", "A", "B", "C", "D", "1", "2"], (g, texts)
        assert (live["items"]["a0"]["x"], live["items"]["a0"]["y"]) == (0, 0)

        # a table already: «Make table» is grey
        menu(page, PICS)
        page.locator('#ctx .hy-sub [data-how="table"]').last.click()
        page.wait_for_function("() => Object.keys(board.grids || {}).length === 1")
        assert menu(page, PICS)["table"] == "This is a table already"
        close(page); page.keyboard.press("Control+z")

        # the bar over a selection: the button after ⌥A ⌥S ⌥D opens the same menu
        page.evaluate("() => { sel = new Set(['a0', 'a1']); render(); }")
        btn = page.locator("#handles .tidy [data-arrange]")
        assert btn.count() == 1 and page.locator("#handles .tidy [data-tidy]").count() == 3
        btn.click()
        page.wait_for_selector('#ctx.open [data-how="table"]')
        assert page.locator('#ctx.open [data-sub="layouts"]').count() == 1
        shot(page, "2-bar-arrange-menu")
        close(page)

        # the shortcuts panel names Arrange's rows
        page.click("#bkeys"); page.click("#keys .kp-tab[data-kt=all]")   # round 15's Tips: the rows are in All keys
        assert page.locator("#keys [data-arrange-keys]").count() == 3
        assert "Layout patterns" in page.locator("#keys").inner_text()
        page.click("#bkeys")

        # no timeline on the page: its row says how to get one
        page.evaluate("() => { delete board.items.tl; render(); }")
        assert menu(page, PICS, "layouts")["timeline"] == "Put a timeline on the page first: L"
        close(page)
        assert not errors, errors
        browser.close()
