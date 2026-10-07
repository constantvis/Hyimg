"""Submenus in the app's one menu and «Move to page ›» on the board (owner 2026-10-06, showing Figma's right-click menu with «Move to
page ›»: «move to page is also a good feature»).

- an item with the chevron opens its panel beside it: on hover after a short delay, at once on a click, with → (← closes, ↑ ↓ move,
  Enter runs, Esc closes one level); a diagonal move towards the panel over the items between keeps it open (the safe triangle), a
  pointer that stays on another item closes it; no room on the right: it opens on the left, inside the window
- «Move to page ›» lists the other pages (not the open one) and «New page…»; the selection goes there with what a drag carries (a group's
  members and the groups inside its frame, a note's zone pictures), plugin cards too; the layout among them is kept; they stand where they
  stood when that room is free on the other page, else right of its content; arrows between moved things stay, the others are dropped
- versions before and after on both pages; a note with «Open» (that page, the moved things selected) and «Undo»; ⌘Z on the page they
  left brings them back on both pages, ⇧⌘Z moves them again
- hy.py do 'topage PAGE REF...' does the same for agents
Runs in Chromium and WebKit where Playwright has them, on temporary libraries only (the frames plugin from its repository's last commit)."""
import json
import os
import shutil
import subprocess
import sys
import tarfile
import io
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT.parent / "hyimg-frames"
ENGINES = ["chromium", "webkit"]


def pic(n, x, y, w=200):
    return {"path": f"a/{n}.png", "x": x, "y": y, "w": w, "ar": 2 / 3, "crop": None}


def main_board():
    items = {f"i{n}": pic(n, n * 240, 0) for n in range(3)}            # a row on top: i0 i1 i2
    # a group with two pictures and a note whose zone holds a third picture, and a smaller group inside its frame
    items.update({
        "g_a": pic(3, 0, 1000), "g_b": pic(4, 240, 1000),
        "nz": {"type": "note", "text": "zone", "x": 0, "y": 1400, "w": 200, "fs": 12, "color": "blue", "to": ["g_a", "i0"],
               "reach": {"l": 0, "t": 0, "r": 300, "b": 60}},
        "z_p": pic(5, 260, 1420),                                        # its centre is in nz's zone: goes with the note
        "in_p": pic(6, 700, 1100),                                       # in the nested group
        "stay_n": {"type": "note", "text": "stays", "x": 2000, "y": 0, "w": 200, "fs": 12, "color": "yellow", "to": ["g_b"]},
    })
    groups = {"G": {"title": "Big", "x": -100, "y": 900, "w": 1200, "h": 1000, "members": ["g_a", "g_b", "nz"]},
              "Gin": {"title": "Inner", "x": 650, "y": 1050, "w": 300, "h": 450, "members": ["in_p"]}}
    return {"schema": 1, "revision": 1, "items": items, "groups": groups, "removed": {}}


def b_board():   # B: one picture far away, so the top row's room is free; and one right where the group stands
    return {"schema": 1, "revision": 1, "items": {"b0": pic(7, 5000, 5000), "b1": pic(8, 100, 1200)}, "groups": {}, "removed": {}}


def frames_plugin(dest):
    """the frames plugin as its repository's last commit has it (another agent may be changing its working copy)"""
    if os.environ.get("HY_TEST_FRAMES_DIR"):   # a prepared copy (the plugin's last commit plus a change about to be committed with this one)
        shutil.copytree(os.environ["HY_TEST_FRAMES_DIR"], dest); return True
    if not (FRAMES / "manifest.json").is_file():
        return False
    raw = subprocess.run(["git", "-C", str(FRAMES), "archive", "HEAD"], capture_output=True, check=True).stdout
    dest.mkdir(parents=True)
    tarfile.open(fileobj=io.BytesIO(raw)).extractall(dest, filter="data")
    return True


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True); plugins.mkdir()
    for n in range(10):
        (lib / "a" / f"{n}.png").write_bytes(png())
    have_frames = frames_plugin(plugins / "frames")
    (lib / "frames/t1").mkdir(parents=True)
    (lib / "frames/t1/render.1.png").write_bytes(png(60, 40))
    (lib / "frames/t1/frame.1.json").write_text(json.dumps({"version": 1, "v": 1, "name": "F1", "size": [60, 40], "background": "#ffffff", "order": "bottom-to-top",
                                                             "layers": [], "render": "frames/t1/render.1.png"}))
    b = main_board()
    b["items"]["fr"] = {"type": "imgframe", "x": 1200, "y": 0, "w": 300, "h": 200, "name": "F1", "doc": "frames/t1/frame.1.json", "render": "frames/t1/render.1.png",
                        "v": 1, "size": [60, 40], "pics": ["a/9.png"]}
    (state / "boards/main.json").write_text(json.dumps(b))
    (state / "boards/p2.json").write_text(json.dumps(b_board()))
    (state / "boards/p3.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "A"}, {"id": "dv", "title": "---"}, {"id": "p2", "title": "B"}, {"id": "p3", "title": "C"}]}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HYIMG_PLUGINS=str(plugins), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError:
                time.sleep(0.1)
        yield {"port": port, "state": state, "frames": have_frames, "tmp": tmp_path}
    finally:
        process.terminate(); process.wait(5); log.close()


def api(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r:
        return json.load(r)


def open_board(p, engine, port, w=1400, h=900):
    try:
        browser = getattr(p, engine).launch()
    except Exception as error:
        pytest.skip(f"no {engine} for Playwright: {error}")
    page = browser.new_page(viewport={"width": w, "height": h})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url)
    page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); localStorage.setItem('cv.page', 'main'); }")
    page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && BOARD === 'main' && board.items.i0 && pages.length === 4", timeout=20000)
    errors.clear()   # WebKit reports the first load's requests, cancelled by the reload, as errors («… due to access control checks»)
    page.evaluate("() => { cam.x = -100; cam.y = -200; cam.z = .35; renderCam(); render(); }")
    page.wait_for_timeout(300)
    return browser, page, errors


def screen(page, x, y):   # a board point on the screen
    return page.evaluate(f"() => {{ const r = stage.getBoundingClientRect(); return [({x} - cam.x) * cam.z + r.left, ({y} - cam.y) * cam.z + r.top]; }}")


def menu_on(page, id, at=None):
    """right click on the card id (at: a screen point instead); returns the opener's box"""
    if at is None:
        it = page.evaluate(f"() => board.items['{id}']")
        at = screen(page, it["x"] + it["w"] / 2, it["y"] + 40)
    page.mouse.click(at[0], at[1])
    page.mouse.click(at[0], at[1], button="right")
    page.wait_for_selector("#ctx.open [data-sub=topage]")
    return page.locator("#ctx [data-sub=topage]").bounding_box()


SUB = "() => { const s = document.querySelector('#ctx .hy-sub'); if (!s || !s.getClientRects().length) return null; const r = s.getBoundingClientRect();" \
      " return { x: r.left, y: r.top, r: r.right, b: r.bottom, side: s.dataset.side, items: [...s.querySelectorAll('[role=menuitem]')].map(b => b.textContent.trim())," \
      " focus: document.activeElement && document.activeElement.textContent.trim(), W: innerWidth, H: innerHeight }; }"


def wait_saved(page):
    page.wait_for_function("() => !dirty && !saveT && !saveFlight && !moveBusy", timeout=10000)


@pytest.mark.parametrize("engine", ENGINES)
def test_submenu_hover_diagonal_click_keys(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"])
        op = menu_on(page, "i1")
        # hover: opens after the intent delay, lists the other pages (not A, not the divider) and «New page…»
        page.mouse.move(op["x"] + 20, op["y"] + op["height"] / 2)
        page.wait_for_function(SUB.replace("return null;", "return null;") + "", timeout=3000)
        page.wait_for_function(f"() => ({SUB})() !== null")
        s = page.evaluate(SUB)
        assert s["items"] == ["B", "C", "New page…"], s
        assert s["side"] == "right" and s["x"] >= op["x"] + op["width"] - 8, s
        assert page.evaluate("() => document.querySelector('#ctx [data-sub=topage]').getAttribute('aria-expanded')") == "true"
        # a diagonal move towards the panel's lower part crosses the items under the opener: the panel stays
        x0, y0 = op["x"] + op["width"] - 30, op["y"] + op["height"] / 2
        tx, ty = s["x"] + 30, s["b"] - 12
        for k in range(1, 13):
            page.mouse.move(x0 + (tx - x0) * k / 12, y0 + (ty - y0) * k / 12)
            page.wait_for_timeout(12)
            assert page.evaluate(SUB) is not None, f"closed on the way at step {k}"
        page.wait_for_timeout(300)
        assert page.evaluate(SUB) is not None
        # back on the opener, then up onto the item above («Group») and resting there: the panel closes
        page.mouse.move(op["x"] + 20, op["y"] + op["height"] / 2); page.wait_for_timeout(200)
        page.mouse.move(op["x"] + 20, op["y"] - op["height"] * .6, steps=2)
        page.wait_for_function(f"() => ({SUB})() === null", timeout=3000)
        # a click opens it at once
        page.mouse.click(op["x"] + 20, op["y"] + op["height"] / 2)
        assert page.evaluate(SUB) is not None
        assert page.evaluate("() => $('#ctx').classList.contains('open')")
        # keys: Esc closes one level (the menu stays), → opens and goes in, ↓ moves, ← comes back, Enter opens, Esc twice closes all
        page.mouse.move(5, 5)
        page.keyboard.press("Escape")
        assert page.evaluate(SUB) is None and page.evaluate("() => $('#ctx').classList.contains('open')")
        page.evaluate("() => document.querySelector('#ctx [data-sub=topage]').focus()")
        page.keyboard.press("ArrowRight")
        s = page.evaluate(SUB); assert s and s["focus"] == "B", s
        page.keyboard.press("ArrowDown"); assert page.evaluate(SUB)["focus"] == "C"
        page.keyboard.press("ArrowDown"); assert page.evaluate(SUB)["focus"] == "New page…"
        page.keyboard.press("ArrowDown"); assert page.evaluate(SUB)["focus"] == "B"   # round
        page.keyboard.press("ArrowLeft")
        assert page.evaluate(SUB) is None
        assert page.evaluate("() => document.activeElement.dataset.sub") == "topage"
        page.keyboard.press("ArrowDown")
        assert page.evaluate("() => document.activeElement.dataset.sub") != "topage"   # ↓ moves in the menu, the board's arrows wait
        page.keyboard.press("ArrowUp")
        page.keyboard.press("Enter")
        s = page.evaluate(SUB); assert s and s["focus"] == "B", s
        page.keyboard.press("Escape"); page.keyboard.press("Escape")
        assert not page.evaluate("() => $('#ctx').classList.contains('open')")
        assert page.evaluate("() => board.items.i1.x") == 240   # the arrows moved nothing on the board
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_submenu_flips_at_the_right_edge(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"], w=900, h=520)
        # i1 at the window's right edge, low: the menu is pushed in from the corner, its submenu has no room on the right
        page.evaluate("() => { const r = stage.getBoundingClientRect(), it = board.items.i1; cam.z = .35; cam.x = it.x + 100 - (880 - r.left) / cam.z; cam.y = it.y + 40 - (500 - r.top) / cam.z; renderCam(); render(); }")
        page.wait_for_timeout(200)
        op = menu_on(page, "i1", at=[880, 500])
        page.mouse.click(op["x"] + 20, op["y"] + op["height"] / 2)
        s = page.evaluate(SUB)
        m = page.evaluate("() => { const r = $('#ctx').getBoundingClientRect(); return { x: r.left, r: r.right }; }")
        assert s["side"] == "left" and s["r"] <= m["x"] + 8, (s, m)
        assert 8 <= s["x"] and s["r"] <= s["W"] - 8 and 8 <= s["y"] and s["b"] <= s["H"] - 8, s
        assert not errors, errors
        browser.close()


def move_via_menu(page, id, target):
    op = menu_on(page, id)
    page.mouse.click(op["x"] + 20, op["y"] + op["height"] / 2)
    page.locator("#ctx .hy-sub [role=menuitem]", has_text=target).click()
    page.wait_for_function("() => !moveBusy && document.querySelector('#hyToasts .ht.act')", timeout=10000)
    wait_saved(page)
    return page.evaluate("() => [...document.querySelectorAll('#hyToasts .ht.act')].pop().querySelector('span').textContent")


@pytest.mark.parametrize("engine", ENGINES)
def test_move_a_picture_versions_and_open(server, engine):
    port = server["port"]
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, port)
        text = move_via_menu(page, "i0", "B")
        assert text == "Moved to “B”: 1 object · arrows dropped: 1", text   # nz pointed at i0
        a, b = api(port, "/api/board?name=main"), api(port, "/api/board?name=p2")
        assert "i0" not in a["items"] and a["items"]["nz"]["to"] == ["g_a"]
        assert b["items"]["i0"]["x"] == 0 and b["items"]["i0"]["y"] == 0   # its room on B was free: where it stood
        assert "a/0.png" not in a.get("removed", {})                        # it is on B, not gone to the archive
        for name, word in (("main", "to"), ("p2", "from")):
            labels = [e["label"] for e in api(port, f"/api/history?name={name}")]
            assert f"Before: moved {word} “{'B' if word == 'to' else 'A'}”" in labels and f"After: moved {word} “{'B' if word == 'to' else 'A'}”" in labels, (name, labels)
        page.locator("#hyToasts .ht.act .ab", has_text="Open").click()
        page.wait_for_function("() => BOARD === 'p2' && sel.has('i0')", timeout=10000)
        assert page.evaluate("() => $('#cPageName').textContent") == "B"
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_move_a_group_keeps_layout_lands_in_free_room_and_drops_outer_arrows(server, engine):
    port = server["port"]
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, port)
        before = page.evaluate("() => JSON.parse(JSON.stringify(board))")
        page.evaluate("() => { sel = new Set(['G']); render(); }")
        page.evaluate("() => moveToPage('p2')")
        page.wait_for_function("() => !moveBusy && document.querySelector('#hyToasts .ht.act')", timeout=10000); wait_saved(page)
        text = page.evaluate("() => [...document.querySelectorAll('#hyToasts .ht.act')].pop().querySelector('span').textContent")
        moved = ["g_a", "g_b", "nz", "z_p", "in_p"]
        assert text == "Moved to “B”: 7 objects · arrows dropped: 2", text   # 5 items, 2 groups; nz→i0 and stay_n→g_b
        a, b = api(port, "/api/board?name=main"), api(port, "/api/board?name=p2")
        assert not set(moved) & set(a["items"]) and "G" not in a["groups"] and "Gin" not in a["groups"]
        assert a["items"]["stay_n"]["to"] == []
        assert set(moved) <= set(b["items"]) and {"G", "Gin"} <= set(b["groups"])
        assert b["items"]["nz"]["to"] == ["g_a"] and b["groups"]["G"]["members"] == ["g_a", "g_b", "nz"] and b["groups"]["Gin"]["members"] == ["in_p"]
        # B had a picture where the group stood: the group goes right of B's content, at its top, the layout among them kept
        dx, dy = b["groups"]["G"]["x"] - before["groups"]["G"]["x"], b["groups"]["G"]["y"] - before["groups"]["G"]["y"]
        assert (b["groups"]["G"]["x"], b["groups"]["G"]["y"]) == (5200 + 300, 1200)   # B's right edge + a group's air (1.5 × 200), B's top
        for k in moved:
            assert (b["items"][k]["x"] - before["items"][k]["x"], b["items"][k]["y"] - before["items"][k]["y"]) == (dx, dy), k
        assert (b["groups"]["Gin"]["x"] - before["groups"]["Gin"]["x"], b["groups"]["Gin"]["y"] - before["groups"]["Gin"]["y"]) == (dx, dy)
        # ⌘Z here brings them back on both pages; ⇧⌘Z moves them again
        page.mouse.click(5, 300); page.keyboard.press("Control+z")
        page.wait_for_function("() => board.groups.G && board.items.z_p", timeout=5000); wait_saved(page)
        for _ in range(50):
            b = api(port, "/api/board?name=p2")
            if "G" not in b["groups"]: break
            time.sleep(0.1)
        assert "G" not in b["groups"] and not set(moved) & set(b["items"]) and set(b["items"]) == {"b0", "b1"}
        a = api(port, "/api/board?name=main")
        assert set(moved) <= set(a["items"]) and a["items"]["stay_n"]["to"] == ["g_b"] and a["items"]["nz"]["to"] == ["g_a", "i0"]
        page.keyboard.press("Control+Shift+z")
        page.wait_for_function("() => !board.groups.G", timeout=5000); wait_saved(page)
        for _ in range(50):
            b = api(port, "/api/board?name=p2")
            if "G" in b["groups"]: break
            time.sleep(0.1)
        assert set(moved) <= set(b["items"]) and "G" in b["groups"]
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_new_page_and_the_notes_undo_after_other_edits(server, engine):
    port = server["port"]
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, port)
        text = move_via_menu(page, "i2", "New page…")
        assert text == "Moved to “Page 5”: 1 object", text   # named as the pages menu names a new page
        pg = api(port, "/api/pages")["pages"]
        new = next(x for x in pg if x["title"] == "Page 5")
        assert "a/2.png" in new["on"] and api(port, f"/api/board?name={new['id']}")["items"]["i2"]["x"] == 480
        # another edit here first: the note's «Undo» still takes it back from the new page and puts it here as it was
        page.evaluate("() => { const b = snap(); board.items.i1.x += 10; commit(b); }"); wait_saved(page)
        page.locator("#hyToasts .ht.act .ab", has_text="Undo").click()
        page.wait_for_function("() => board.items.i2 && board.items.i2.x === 480", timeout=10000); wait_saved(page)
        assert "i2" not in api(port, f"/api/board?name={new['id']}")["items"]
        assert api(port, "/api/board?name=main")["items"]["i1"]["x"] == 250   # the other edit stays
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_move_a_plugin_card(server, engine):
    if not server["frames"]:
        pytest.skip("no hyimg-frames repository beside this one")
    port = server["port"]
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, port)
        page.wait_for_function("() => PLG.imgframe && EL.get('fr')", timeout=15000)
        text = move_via_menu(page, "fr", "C")
        assert text == "Moved to “C”: 1 object", text
        c = api(port, "/api/board?name=p3")
        assert c["items"]["fr"]["type"] == "imgframe" and c["items"]["fr"]["x"] == 1200 and c["items"]["fr"]["pics"] == ["a/9.png"]
        assert "fr" not in api(port, "/api/board?name=main")["items"]
        page.locator("#hyToasts .ht.act .ab", has_text="Open").click()
        page.wait_for_function("() => BOARD === 'p3' && EL.get('fr') && sel.has('fr')", timeout=10000)
        assert not errors, errors
        browser.close()


def hy(port, *args):
    r = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "--port", str(port), *args], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def test_hy_topage(server):
    port = server["port"]
    out = hy(port, "--page", "main", "do", "topage B Big i1", "--quiet")
    a, b = api(port, "/api/board?name=main"), api(port, "/api/board?name=p2")
    assert "G" not in a["groups"] and "i1" not in a["items"] and {"g_a", "g_b", "nz", "z_p", "in_p", "i1"} <= set(b["items"]) and {"G", "Gin"} <= set(b["groups"])
    assert a["items"]["stay_n"]["to"] == [] and b["items"]["nz"]["to"] == ["g_a"]
    assert b["items"]["i1"]["x"] - b["groups"]["G"]["x"] == 240 - (-100) and b["items"]["i1"]["y"] - b["groups"]["G"]["y"] == 0 - 900   # the layout among them
    assert "стрелок убрано: 2" in out, out
    for name in ("main", "p2"):
        labels = [e["label"] for e in api(port, f"/api/history?name={name}")]
        assert any(l.startswith("до: ") for l in labels) and any(l.startswith("после: ") for l in labels), (name, labels)
