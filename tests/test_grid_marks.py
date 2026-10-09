"""Annotations and comments in a grid (owner 2026-10-09, note nu6e6cs2 on «grid is a table»: «Эта механика же и к Annotations (comments)
применяется, верно?»). A drawing or a pin sits on the thing under it as a share of its box, so when the grid reflows (a member dragged to
another cell) the drawing goes with its picture, not with the cell; a mark on a table's title cell (a heading) belongs to that heading
and moves with it. Chromium, dark, a temporary library.

  nice -n 10 python3 -m pytest -q tests/test_grid_marks.py
"""
import pytest

from test_annotations_ui import board, box, get, open_board, wait

playwright = pytest.importorskip("playwright.sync_api")


def test_a_drawing_rides_with_its_picture_through_a_grid_reflow_and_a_heading_holds_its_marks(tmp_path):
    servers, port = board(tmp_path, "en")
    try:
        with playwright.sync_playwright() as p:
            browser, page, errors = open_board(p, port)
            page.evaluate("""() => { const before = HY.snap();
              board.items.t1 = { type: 'text', text: 'Light', x: 0, y: -160, w: 300, h: 60, fs: 48, size: 1 };
              hyGrid.make(board, ['i0', 'i1', 'i2'], 3, false, HY.uid); HY.commit(before, 'grid'); }""")
            page.keyboard.press("p")
            page.wait_for_selector("#dock .ann-bar [data-tool=pen].on")
            r = box(page, '.it[data-id="i1"]')
            page.mouse.move(r["x"] + 40, r["y"] + 80); page.mouse.down()
            for i in range(12): page.mouse.move(r["x"] + 40 + i * 14, r["y"] + 80 + (i % 3) * 12)
            page.mouse.up()
            a = wait(lambda: get(port, "/api/annotations?name=main")["items"], "the stroke was not saved")[0]
            assert a["anchor"]["obj"] == "i1"
            page.keyboard.press("Escape"); page.wait_for_timeout(200)
            # a heading under a pin or a drawing: it is the anchor (a table's title cell)
            hd = page.evaluate("() => { const q = rectOf('t1'); return hyAnnot.anchorAt({ x: q.x + q.w / 2, y: q.y + q.h / 2, w: 0, h: 0 }).anchor; }")
            assert hd and hd["obj"] == "t1" and hd["kind"] == "heading", hd
            on_pic = page.evaluate("() => { const q = rectOf('i2'); return hyAnnot.anchorAt({ x: q.x + 10, y: q.y + 10, w: 0, h: 0 }).anchor.obj; }")
            assert on_pic == "i2"   # a picture still wins where there is one
            # the grid reflows: i1 dragged onto i0's cell, i0 slides into i1's
            g0, p0 = box(page, f'#annsvg g[data-a="{a["id"]}"]'), box(page, '.it[data-id="i1"]')
            q0 = box(page, '.it[data-id="i0"]')
            page.mouse.move(p0["x"] + p0["w"] / 2, p0["y"] + 20); page.mouse.down()
            for i in range(1, 13): page.mouse.move(p0["x"] + p0["w"] / 2 + (q0["x"] - p0["x"]) * i / 12, p0["y"] + 20, steps=1)
            page.mouse.up(); page.wait_for_timeout(600)
            assert page.evaluate("() => board.grids && Object.values(board.grids)[0].members.slice(0, 2).join()") == "i1,i0"
            g1, p1 = box(page, f'#annsvg g[data-a="{a["id"]}"]'), box(page, '.it[data-id="i1"]')
            assert abs((g1["x"] - g0["x"]) - (p1["x"] - p0["x"])) < 2 and abs(p1["x"] - p0["x"]) > 100, (g0, g1, p0, p1)
            # the heading moves (its table's group moved): a drawing on it goes along
            page.evaluate("""() => { hyAnnot.state.items.set('ah', { id: 'ah', kind: 'rect', color: 'yellow', w: 0.01, page: BOARD,
              pts: [[0.1, 0.1], [0.9, 0.9]], anchor: { obj: 't1', kind: 'heading', file: '', r: [0, -160, 300, 60] } }); hyAnnot.draw(); }""")
            h0 = box(page, '#annsvg g[data-a="ah"]')
            page.evaluate("() => { board.items.t1.x += 200; render(); }")
            h1 = box(page, '#annsvg g[data-a="ah"]')
            assert abs(h1["x"] - h0["x"] - 200) < 2, (h0, h1)
            assert not errors, errors
            browser.close()
    finally:
        servers.close()
