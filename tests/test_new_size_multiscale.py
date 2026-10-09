"""A new note's size follows the zoom, and several selected things scale together (owner 2026-10-07).

- N and the dock's note button: a new note is a quarter of the board's visible height on screen (ui/newsize.js NOTE_VIEW_SHARE), at
  most as big as a picture on the board (the size every note had before), its type the same share of its width; a new heading and a
  new timeline are no bigger on screen than at 100 %
- 2 and more selected: one box with corner squares and side strips; a corner scales the selection about the opposite corner, positions
  on both axes, sizes by one factor (pictures keep their proportions), ⇧ keeps the box's proportions, a side strip scales by its axis,
  a selected group scales as one thing, its frame and members by the same factor; one undo step brings everything back
Chromium, dark theme, temporary libraries only. HY_SHOTS=<folder> keeps the screenshots."""
import json
import os
from pathlib import Path

import pytest

from test_shortcuts import run_server

playwright = pytest.importorskip("playwright.sync_api")
W, H = 1400, 900
jsround = lambda v: int(v + 0.5)   # Math.round, not Python's round half to even


@pytest.fixture
def server(tmp_path):
    for port in run_server(tmp_path):
        (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
        yield port


def open_board(p, port):
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": W, "height": H}, color_scheme="dark")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url)
    page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }")
    page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 6 && EL.get('i0')", timeout=20000)
    errors.clear()
    return browser, page, errors


def shot(page, name):
    d = os.environ.get("HY_SHOTS")
    if d: Path(d).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(d) / name))


def cam(page, x, y, z):
    page.evaluate(f"() => {{ cam.x = {x}; cam.y = {y}; cam.z = {z}; sel = new Set(); renderCam(); render(); }}")


NEWEST = "t => { const ids = Object.keys(board.items).filter(i => board.items[i].type === t); return board.items[ids[ids.length - 1]]; }"


def test_new_note_follows_zoom(server):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, server)
        vh = page.evaluate("() => stage.getBoundingClientRect().height")
        share = page.evaluate("() => [hyNewSize.NOTE_VIEW_SHARE, hyNewSize.NOTE_MIN_PX]")
        assert share == [0.25, 160]
        target = max(160, vh * 0.25)

        def note_by_n(z):
            cam(page, -3000, -3000, z)
            page.mouse.move(700, 450); page.keyboard.press("n")
            n = page.evaluate(NEWEST, "note")
            page.keyboard.type("a"); page.keyboard.press("Escape")
            return n

        n = note_by_n(1)   # 100 %: a quarter of the visible height, under the picture's 320
        assert n["w"] == jsround(min(320, target)) and abs(n["fs"] / n["w"] - 1 / 18) < 1e-9
        n = note_by_n(4)   # zoomed in: the same size on screen, a quarter as many board units
        assert n["w"] == jsround(target / 4) and abs(n["fs"] / n["w"] - 1 / 18) < 1e-9
        assert abs(page.evaluate("() => { const e = [...document.querySelectorAll('.note')].pop(); return e.getBoundingClientRect().width; }") - target) < 3
        shot(page, "new-note-zoom-400.png")
        n = note_by_n(0.25)   # far out: never bigger than a picture
        assert n["w"] == 320
        # the dock's button takes the same size
        cam(page, -3000, -3000, 2)
        page.click("#bnote"); n = page.evaluate(NEWEST, "note"); page.keyboard.type("b"); page.keyboard.press("Escape")
        assert n["w"] == jsround(target / 2)
        # a heading (double click on the empty board) and a timeline (L): no bigger on screen than at 100 %
        cam(page, 8000, 8000, 4)
        page.mouse.dblclick(700, 450); t = page.evaluate(NEWEST, "text"); page.keyboard.type("Title"); page.keyboard.press("Escape")
        assert t["fs"] == 10
        cam(page, 12000, 12000, 1)
        page.mouse.dblclick(700, 450); t = page.evaluate(NEWEST, "text"); page.keyboard.type("Title"); page.keyboard.press("Escape")
        assert t["fs"] == 40
        cam(page, 20000, 20000, 2)
        page.mouse.move(700, 450); page.keyboard.press("l"); tl = page.evaluate(NEWEST, "timeline"); page.keyboard.press("Escape")
        assert tl["fs"] == 36 and tl["len"] == 1296
        assert not errors, errors
        browser.close()


XYWH = "ids => ids.map(i => { const o = board.items[i] || board.groups[i]; return [Math.round(o.x), Math.round(o.y), Math.round(o.w)]; })"


def drag_handle(page, rc, dx, dy, mods=()):
    js = "rc => { const r = document.querySelector(`#handles [data-mresize=${rc}]`).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }"
    box = page.evaluate(js, rc)
    for m in mods: page.keyboard.down(m)
    page.mouse.move(*box); page.mouse.down()
    page.mouse.move(box[0] + dx / 2, box[1] + dy / 2); page.mouse.move(box[0] + dx, box[1] + dy)
    page.mouse.up()
    for m in mods: page.keyboard.up(m)


def test_several_scale_together(server):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, server)
        cam(page, -200, -200, 0.5)
        page.evaluate("() => { sel = new Set(['i0', 'i1', 'i2']); render(); }")
        # one box, four corners and four sides
        count = "s => s.map(q => document.querySelectorAll('#handles ' + q).length)"
        assert page.evaluate(count, [".mbox", ".h[data-mresize]", ".he[data-mresize]"]) == [1, 4, 4]
        shot(page, "multi-select-box.png")
        n0 = page.evaluate("() => past.length")
        # the bottom right corner 250 px to the right at 50 %: the box 1000 → 1500 wide, the pictures 1.5 times, the top left stays
        drag_handle(page, "se", 250, 0)
        assert page.evaluate(XYWH, ["i0", "i1", "i2"]) == [[0, 0, 480], [510, 0, 480], [1020, 0, 480]]
        assert page.evaluate("() => past.length") == n0 + 1
        shot(page, "multi-select-scaled.png")
        page.keyboard.press("Control+z")
        assert page.evaluate(XYWH, ["i0", "i1", "i2"]) == [[0, 0, 320], [340, 0, 320], [680, 0, 320]]
        # ⇧ on the top left corner with a note and a heading in the selection: everything at half the size about the bottom right corner
        page.evaluate("""() => { board.items.n1 = { type: 'note', text: 'hi', x: 0, y: 520, w: 200, fs: 200 / 18, size: 2, h: 0, color: 'yellow',
            reach: null, to: [] };
          board.items.t1 = { type: 'text', text: 'Head', x: 400, y: 560, fs: 40, size: 1, w: 0, h: 0 }; sel = new Set(['i0', 'i1', 'n1', 't1']); render(); }""")
        b0 = page.evaluate("() => bbox(['i0', 'i1', 'n1', 't1'])")
        shot(page, "multi-select-mixed.png")
        drag_handle(page, "nw", b0["w"] / 4, b0["h"] / 4, ["Shift"])   # 1/4 of the box on screen at 50 % = half of it in board units
        b1 = page.evaluate("() => bbox(['i0', 'i1', 'n1', 't1'])")
        assert abs(b1["w"] - b0["w"] / 2) < 3 and abs(b1["x"] + b1["w"] - (b0["x"] + b0["w"])) < 3 and abs(b1["y"] + b1["h"] - (b0["y"] + b0["h"])) < 3
        n1, t1 = page.evaluate("() => [board.items.n1, board.items.t1]")
        assert abs(n1["w"] - 100) < 1 and abs(n1["fs"] / n1["w"] - 1 / 18) < 1e-6 and abs(t1["fs"] - 20) < .5
        page.keyboard.press("Control+z")
        assert page.evaluate(XYWH, ["i0", "i1", "n1"]) == [[0, 0, 320], [340, 0, 320], [0, 520, 200]]
        # a group and a picture, the right side 1.5 times: the group as one thing, the picture keeps its place beside it
        page.evaluate("""() => { delete board.items.n1; delete board.items.t1;
          board.groups.G = { title: 'G', x: 1000, y: -40, w: 700, h: 560, members: ['i3', 'i4'] }; sel = new Set(['G', 'i5']); render(); }""")
        b0 = page.evaluate("() => bbox(['G', 'i5'])")
        drag_handle(page, "e", b0["w"] / 2 * 0.5, 0)   # 50 % wider
        g = page.evaluate("() => board.groups.G")
        shot(page, "multi-select-group-scaled.png")
        assert [round(g["x"]), round(g["y"]), round(g["w"]), round(g["h"])] == [1000, -180, 1050, 840]   # the group is one thing: 1.5 times
        assert page.evaluate(XYWH, ["i3", "i4", "i5"]) == [[1030, -120, 480], [1540, -120, 480], [2050, -120, 480]]
        assert page.evaluate("() => board.groups.G.members") == ["i3", "i4"]
        page.keyboard.press("Control+z")
        assert page.evaluate(XYWH, ["G", "i3", "i4", "i5"]) == [[1000, -40, 700], [1020, 0, 320], [1360, 0, 320], [1700, 0, 320]]
        # one thing selected: its own corners as before, no box
        page.evaluate("() => { sel = new Set(['i0']); render(); }")
        assert page.evaluate(count, [".mbox", ".h[data-resize]"]) == [0, 4]
        assert not errors, errors
        browser.close()
