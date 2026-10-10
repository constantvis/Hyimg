"""⌘Z right after making a note or a heading takes it away (owner 2026-10-08: «когда я добавил нотификейшн и нажал cmd + z то значит, я хочу
его удалить, и то же самое с текстом. Если я, предположим, там заголовок сделал, нажал cmd Z, и значит его нужно просто убрать»).

- a new note (N with a picture selected: its arrow; the dock's button; N on a selected note: a reply) and a new heading (a double click on
  the board): ⌘Z while its field is still open removes it at once, one press, with its arrow or reply link; ⇧⌘Z brings it back with its
  text and links; the board step made before it stays
- ⌘Z after the note was finished (⌘↵) removes it the same way
- an empty new heading: ⌘Z takes it away and undoes nothing else
- a new group (G, whose g is not typed into the name any more): ⌘Z in its name field takes the group away, ⇧⌘Z brings it back with the
  name typed; a name applied with Enter is part of the group's step, so one ⌘Z still takes the group away (as a note finished with ⌘↵);
  a new timeline (L) with its first label open goes the same way
- the note files (server.py sync_notes): written when a note comes back with ⇧⌘Z and the board is saved, gone after the next ⌘Z
- an existing note or heading: ⌘Z first undoes the typing inside the field, as before; once the field is back as it was, the next ⌘Z
  leaves the field and undoes the board step before (as in Figma)
Chromium, dark theme, a temporary library. HY_SHOTS=<folder> keeps screenshots."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png
from test_note_replies import note, shot

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
OLD = ["E", "H", "p", "q"]


def board():
    return {"schema": 1, "revision": 1, "removed": {}, "groups": {}, "items": {
        "p": {"path": "a/0.png", "x": 0, "y": 0, "w": 300, "ar": 1.5, "crop": None},
        "q": {"path": "a/1.png", "x": 400, "y": 0, "w": 300, "ar": 1.5, "crop": None},
        "E": note(-400, 0, "Existing note"),
        "H": {"type": "text", "text": "Old title", "x": 0, "y": -200, "fs": 40, "size": 1, "w": 0, "h": 0},
    }}


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    for d in (lib / "a", state / "boards"): d.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png(60, 40)); (lib / "a/1.png").write_bytes(png(60, 40))
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, lib
    finally:
        proc.terminate(); proc.wait(5); log.close()


STATE = """() => ({ ids: Object.keys(board.items).sort(), groups: Object.keys(board.groups), qx: board.items.q.x, past: past.length,
  editing: !!document.querySelector('.note textarea, .tx textarea, .gt textarea, .tl textarea') })"""
STEP = "() => { const b = snap(); board.items.q.x += 50; commit(b); return board.items.q.x; }"   # a board step made before
SCREEN = "([x, y]) => { const r = stageBox(); return [r.left + (x - cam.x) * cam.z, r.top + (y - cam.y) * cam.z]; }"
CENTRE = "s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }"
FIELD = ".note textarea, .tx textarea, .gt textarea"
SAVED = "() => !dirty && !saveT && !saveFlight"


def refs(lib):
    """the note references in the first picture's json (server.py sync_notes); the json goes when they were all it held"""
    f = lib / "a/0.json"
    return [r["note"] for r in json.loads(f.read_text()).get("related_notes", [])] if f.exists() else []


def open_board(p, port):
    try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url)
    page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
      localStorage.setItem('cv.cam.main', JSON.stringify({ x: -500, y: -320, z: .8 })); }""")
    page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && EL.get('p') && EL.get('E') && document.querySelector('.tx[data-id=H]')", timeout=30000)
    page.wait_for_timeout(300)
    errors.clear()
    return browser, page, errors


def new_id(page):
    return page.evaluate(f"() => Object.keys(board.items).find(k => !{json.dumps(OLD)}.includes(k)) || null")


def test_undo_takes_a_new_note_or_heading_away(server):
    port, lib = server
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, port)
        S = lambda: page.evaluate(STATE)

        # N with the picture selected: a note above it with an arrow to it; typing, then ⌘Z while typing removes it at once
        qx = page.evaluate(STEP)
        page.evaluate("() => { sel = new Set(['p']); render(); }")
        page.keyboard.press("n"); page.wait_for_selector(".note textarea")
        nid = new_id(page)
        assert page.evaluate("id => board.items[id].to", nid) == ["p"]
        page.keyboard.type("Hello")
        page.wait_for_function(f"() => document.querySelector('.note[data-id={nid}] textarea').value === 'Hello'")
        page.keyboard.press("Meta+z")
        s = S()
        assert s["ids"] == OLD and not s["editing"] and s["qx"] == qx, s   # gone at once, the step before stays
        assert not page.locator(f".arw[data-k='{nid}|p']").count() and not page.locator(f".note[data-id={nid}]").count()
        shot(page, "undo-new-note.png")
        # ⇧⌘Z: back with its text and its arrow; ⌘Z again: gone again, one step
        page.keyboard.press("Meta+Shift+z")
        assert page.evaluate("id => board.items[id] && [board.items[id].text, board.items[id].to]", nid) == ["Hello", ["p"]]
        page.wait_for_selector(f".arw[data-k='{nid}|p']", state="attached")
        assert not S()["editing"]
        # saved with the note back: its file and the picture's reference are written, so the check at the end has something to lose
        page.wait_for_function(SAVED, timeout=10000)
        assert json.loads((lib / f"notes/main__{nid}.json").read_text())["text"] == "Hello" and refs(lib) == [f"main/{nid}"]
        page.keyboard.press("Meta+z")
        assert S()["ids"] == OLD and S()["qx"] == qx

        # the dock's «+» › Note, nothing typed: ⌘Z removes the empty note, the step before stays
        qx = page.evaluate(STEP)
        page.evaluate("() => { sel = new Set(); render(); }")
        page.click("#bplus"); page.click("#bplusm [data-mk=note]"); page.wait_for_selector(".note textarea")
        assert new_id(page)
        page.keyboard.press("Meta+z")
        s = S(); assert s["ids"] == OLD and not s["editing"] and s["qx"] == qx, s

        # N on a selected note: a reply to it; ⌘Z removes the reply and its link, ⇧⌘Z brings both back
        page.evaluate("() => { sel = new Set(['E']); render(); }")
        page.keyboard.press("n"); page.wait_for_selector(".note textarea")
        rid = new_id(page)
        assert page.evaluate("id => board.items[id].to", rid) == ["E"]
        page.keyboard.type("Yes")
        page.keyboard.press("Meta+z")
        s = S(); assert s["ids"] == OLD and not s["editing"] and s["qx"] == qx, s
        assert page.evaluate("() => [board.items.E.text, board.items.E.to]") == ["Existing note", []]
        page.keyboard.press("Meta+Shift+z")
        assert page.evaluate("id => board.items[id] && [board.items[id].text, board.items[id].to]", rid) == ["Yes", ["E"]]
        page.wait_for_function(SAVED, timeout=10000)   # saved: the reply's file answers E, E's file lists the reply
        assert json.loads((lib / f"notes/main__{rid}.json").read_text()).get("reply_to") == "main/E"
        assert json.loads((lib / "notes/main__E.json").read_text()).get("replies") == [f"main/{rid}"]
        page.keyboard.press("Meta+z")
        assert S()["ids"] == OLD

        # a note finished with ⌘↵: ⌘Z removes it, one step
        page.evaluate("() => { sel = new Set(); render(); }")
        page.keyboard.press("n"); page.wait_for_selector(".note textarea")
        fid = new_id(page)
        page.keyboard.type("Done"); page.keyboard.press("Meta+Enter")
        assert not S()["editing"] and page.evaluate("id => board.items[id].text", fid) == "Done"
        page.keyboard.press("Meta+z")
        s = S(); assert s["ids"] == OLD and s["qx"] == qx, s
        page.keyboard.press("Meta+Shift+z")
        assert page.evaluate("id => board.items[id] && board.items[id].text", fid) == "Done"
        page.keyboard.press("Meta+z")
        assert S()["ids"] == OLD

        # a heading: a double click on the empty board, typing, ⌘Z while typing removes it; ⇧⌘Z brings it back with its text
        qx = page.evaluate(STEP)
        x, y = page.evaluate(SCREEN, [200, 420])
        page.mouse.dblclick(x, y); page.wait_for_selector(".tx textarea")
        tid = new_id(page)
        page.keyboard.type("Title")
        page.keyboard.press("Meta+z")
        s = S(); assert s["ids"] == OLD and not s["editing"] and s["qx"] == qx, s
        assert not page.locator(f".tx[data-id={tid}]").count()
        page.keyboard.press("Meta+Shift+z")
        assert page.evaluate("id => board.items[id] && board.items[id].text", tid) == "Title"
        page.keyboard.press("Meta+z")
        assert S()["ids"] == OLD and S()["qx"] == qx

        # an empty heading: ⌘Z takes it away and nothing else
        before = S()
        page.mouse.dblclick(x, y); page.wait_for_selector(".tx textarea")
        page.keyboard.press("Meta+z")
        s = S(); assert s["ids"] == OLD and not s["editing"] and s["qx"] == qx and s["past"] == before["past"], (s, before)

        # a new group: ⌘Z in its name field takes the group away, ⇧⌘Z brings it back with the name typed
        page.evaluate("() => { cam = { x: -900, y: -800, z: .4 }; sel = new Set(['p', 'q']); render(); }")   # the group's title on screen
        page.keyboard.press("Meta+g"); page.wait_for_selector(".gt textarea", state="attached")   # ⌘G only (G alone until 2026-10-10)
        assert page.evaluate("() => document.activeElement.matches('.gt textarea') && document.activeElement.value") == "Group 1"   # ⌘G types no g
        gid = page.evaluate("() => Object.keys(board.groups)[0]")
        page.keyboard.type("Shots")
        page.keyboard.press("Meta+z")
        s = S(); assert s["groups"] == [] and not s["editing"] and s["qx"] == qx, s
        page.keyboard.press("Meta+Shift+z")
        assert page.evaluate("id => board.groups[id] && board.groups[id].title", gid) == "Shots"
        page.keyboard.press("Meta+z")
        assert S()["groups"] == []
        # its name applied with Enter: still the group's own step, one ⌘Z takes the group away, not the name first
        page.evaluate("() => { sel = new Set(['p', 'q']); render(); }")
        page.keyboard.press("Meta+g"); page.wait_for_selector(".gt textarea", state="attached")
        gid = page.evaluate("() => Object.keys(board.groups)[0]")
        page.keyboard.type("Shots"); page.keyboard.press("Enter")
        assert not S()["editing"] and page.evaluate("id => board.groups[id].title", gid) == "Shots"
        page.keyboard.press("Meta+z")
        s = S(); assert s["groups"] == [] and s["qx"] == qx, s
        page.keyboard.press("Meta+Shift+z")
        assert page.evaluate("id => board.groups[id] && board.groups[id].title", gid) == "Shots"
        page.keyboard.press("Meta+z")
        assert S()["groups"] == [] and S()["qx"] == qx

        # a timeline (L) with its first label open: ⌘Z takes the line away, ⇧⌘Z brings it back with the label
        page.keyboard.press("l"); page.wait_for_selector(".tl textarea", state="attached")
        lid = new_id(page)
        page.keyboard.type("Start")
        page.keyboard.press("Meta+z")
        s = S(); assert s["ids"] == OLD and not s["editing"] and s["qx"] == qx, s
        page.keyboard.press("Meta+Shift+z")
        assert page.evaluate("id => board.items[id] && board.items[id].points[0].text", lid) == "Start"
        page.keyboard.press("Meta+z")
        assert S()["ids"] == OLD

        # saved as it looks: none of the new things on the saved board, the files of the note and the reply gone again
        page.wait_for_function(SAVED, timeout=10000)
        for _ in range(40):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/board?name=main", timeout=10) as r: saved = json.load(r)
            if sorted(saved["items"]) == OLD and not saved.get("groups"): break
            time.sleep(0.25)
        assert sorted(saved["items"]) == OLD and not saved.get("groups"), saved
        assert not list((lib / "notes").glob("main__*.json")) and refs(lib) == []
        assert errors == []
        browser.close()


def test_undo_in_an_existing_field_undoes_the_typing_first(server):
    port, _ = server
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, port)
        S = lambda: page.evaluate(STATE)
        for sel_, was in ((".note[data-id=E]", "Existing note"), (".tx[data-id=H]", "Old title")):
            qx = page.evaluate(STEP)
            x, y = page.evaluate(CENTRE, sel_)
            page.mouse.dblclick(x, y); page.wait_for_selector(FIELD)
            page.evaluate("s => { const t = document.querySelector(s); t.focus(); t.setSelectionRange(t.value.length, t.value.length); }", f"{sel_} textarea")
            page.keyboard.type(" more")
            value = lambda: page.evaluate("s => (document.querySelector(s) || {}).value", f"{sel_} textarea")
            assert value() == was + " more"
            # the field's own undo first: the field stays open and the board keeps its step
            for _ in range(6):
                page.keyboard.press("Meta+z")
                s = S(); assert s["editing"] and s["qx"] == qx, s
                if value() == was: break
            assert value() == was
            # the field is as it was: the next ⌘Z leaves it and undoes the step before
            page.keyboard.press("Meta+z")
            s = S(); assert not s["editing"] and s["qx"] == qx - 50, s
            assert page.evaluate("s => board.items[s].text", sel_.split("=")[1].rstrip("]")) == was
            assert s["ids"] == OLD
        assert errors == []
        browser.close()
