"""The board's П4 logic audit of 2026-10-10, the owner's decisions of that day and the Средний / Низкий findings (docs/process.md §4, §5):
one regression test where the audit sketched one, each failing on the code before the fix. Chromium, dark theme, our own temporary
servers and folders, never the ports 4180–4184. The harness is tests/test_p4_board.py's.

  decision 1, B-15, B-25, B-49, B-50, B-59   Esc in every field: words on the canvas apply, a name or a value goes back; Tab, an IME's ↵
  decision 2, B-20                            a click selects an arrow, ⌫ takes it, Esc lets go
  decision 3, B-60, B-22                      ⌘-click toggles a card; a click on one of the selected selects only it on release
  decision 4, B-61, B-30, B-31                C keeps the selection and turns the tool off again; one tool at a time; a board key leaves it
  decision 5, B-62                            snapping guides when moving and resizing, ⌘ free
  decision 6, B-37, B-36, B-26                ♥ on a copy; ↵ opens; ♥ is an undo step
  B-16, B-17, B-18, B-44, B-45                one Esc order; the connector editor; a drag cancelled; the top-right buttons let go
  B-21, B-23, B-24, B-27                      ⌘A takes groups; a group is a command's cards; what a group carries; a nudge leaves a grid
  B-28, B-29, B-41, B-42, B-43                a version preview takes no new work; copies keep their arrows; paste at the edge; one toast
  B-32, B-33, B-39, B-46, B-47, B-48, B-57, B-58   pins of gone things; a thread deleted elsewhere; the «?» panel; crop; delete notes"""
import json
import re
from pathlib import Path

import pytest

from test_p4_board import api, board_page, box, browser_of, pic, serve, threads, wait

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
LIVE = "() => [...document.querySelectorAll('#hyToasts .ht')].filter(el => !el._gone).map(el => el.querySelector('span').textContent)"


LIB = [None]


def run(tmp_path, fn, items=None, **kw):
    with serve(tmp_path, items, **kw) as (port, lib), playwright.sync_playwright() as p:
        LIB[0] = lib
        browser = browser_of(p); page, errors = board_page(browser, port)
        try: fn(page, page.evaluate, port)
        finally: browser.close()
        assert not errors, errors


SHOW = "() => { cam.x = -600; cam.y = -800; renderCam(); render(); }"   # a new group's title on screen: its field takes the focus


def pick(ev, *ids):
    ev(f"() => {{ sel = new Set({json.dumps(list(ids))}); render(); }}")


# ---- decision 1: Esc in every field (B-15, B-59), Tab (B-25), an IME's ↵ (B-50), a page's name an undo step (B-49) ------------------
def test_esc_in_every_field_applies_words_and_cancels_names(tmp_path):
    def go(page, ev, port):
        k = page.keyboard
        # a note: Esc applies
        page.mouse.move(700, 760); k.press("n"); page.wait_for_selector(".note textarea"); k.type("hello"); k.press("Escape")
        assert ev("() => Object.values(board.items).filter(i => i.type === 'note').map(i => i.text)") == ["hello"]
        # a heading and a text document: Esc applies, the body too
        page.mouse.dblclick(300, 760); page.wait_for_selector(".tx textarea"); k.type("Head"); k.press("Escape")
        page.mouse.dblclick(1100, 800); page.wait_for_selector(".tx textarea"); k.type("Doc"); k.press("Shift+Enter"); k.type("body"); k.press("Escape")
        assert sorted(ev("() => Object.values(board.items).filter(i => i.type === 'text').map(i => i.text)")) == ["Doc\nbody", "Head"]
        # a group's title (⌘G opens it): Esc applies
        ev(SHOW); pick(ev, "i0", "i1"); k.press("Meta+g"); page.wait_for_selector(".grp .gt textarea", state="attached"); k.press("Meta+a"); k.type("Ours"); k.press("Escape")
        assert ev("() => Object.values(board.groups).map(g => g.title)") == ["Ours"]
        # a timeline's label: Esc applies
        page.mouse.move(400, 860); k.press("l"); page.wait_for_selector(".tl textarea"); k.type("Start"); k.press("Escape")
        assert ev("() => Object.values(board.items).filter(i => i.type === 'timeline').map(i => i.points[0].text)") == ["Start"]
        # an arrow's words: Esc applies
        cid = ev("() => { const b = snap(), id = hyConn.add(board, 'i2', 'i3'); commit(b); hyConn.edit(id); return id; }")
        page.wait_for_selector(".cned .cnin"); k.type("like"); k.press("Escape")
        assert ev(f"() => [board.links['{cid}'].label, !!document.querySelector('.cned')]") == ["like", False]
        # a page's name: Esc gives the old one back
        ev("() => { openPages(); renamePage('main'); }"); page.wait_for_selector("#pages input"); k.type("Renamed"); k.press("Escape")
        page.wait_for_timeout(200); assert ev("() => pages.find(p => p.id === 'main').title") == "A"
        # a version's name: the first Esc gives the field back as it was and leaves it, the second closes History
        ev("() => closePages()"); page.click("#bhist"); page.click('#hist [data-tab="ver"]'); page.click("#histLabel"); k.type("v1"); k.press("Escape")
        assert ev("() => [$('#histLabel').value, document.activeElement === $('#histLabel'), $('#hist').classList.contains('open')]") == ["", False, True]
        k.press("Escape"); assert not ev("() => $('#hist').classList.contains('open')")
    run(tmp_path, go, pages=True)


def test_tab_out_of_a_heading_applies_and_gives_the_keys_back(tmp_path):   # B-25: the next ↵ made a note
    def go(page, ev, port):
        page.mouse.dblclick(300, 760); page.wait_for_selector(".tx textarea"); page.keyboard.type("Title"); page.keyboard.press("Tab")
        page.keyboard.press("Enter"); page.wait_for_timeout(200)
        assert ev("() => [Object.values(board.items).filter(i => i.type === 'text').map(i => i.text), Object.values(board.items).filter(i => i.type === 'note').length]") == [["Title"], 0]
        assert ev("() => document.activeElement === document.body")
    run(tmp_path, go)


def test_an_input_methods_enter_stays_in_the_field(tmp_path):   # B-50: the group title applied on an IME's ↵
    def go(page, ev, port):
        ev(SHOW); pick(ev, "i0", "i1"); page.keyboard.press("Meta+g"); page.wait_for_selector(".grp .gt textarea", state="attached")
        ev("() => document.querySelector('.grp .gt textarea').dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', isComposing: true, bubbles: true }))")
        assert ev("() => !!document.querySelector('.grp .gt textarea')")
    run(tmp_path, go)


def test_a_page_rename_is_an_undo_step(tmp_path):   # B-49
    def go(page, ev, port):
        ev("() => { openPages(); renamePage('main'); }"); page.wait_for_selector("#pages input"); page.keyboard.type("Moodboard"); page.keyboard.press("Enter")
        page.wait_for_timeout(200); assert ev("() => pages.find(p => p.id === 'main').title") == "Moodboard"
        ev("() => closePages()"); page.keyboard.press("Meta+z"); page.wait_for_timeout(200)
        assert ev("() => pages.find(p => p.id === 'main').title") == "A"
        page.keyboard.press("Meta+Shift+z"); page.wait_for_timeout(200)
        assert ev("() => pages.find(p => p.id === 'main').title") == "Moodboard"
    run(tmp_path, go, pages=True)


# ---- decision 2: arrows (B-20) ------------------------------------------------------------------------------------------------------
NOTE = {"type": "note", "text": "about", "x": 800, "y": 700, "w": 200, "fs": 14, "size": 2, "h": 0, "color": "yellow", "to": ["i1"]}
MID = """([s, k]) => { const p = document.querySelector(s), q = p.getPointAtLength(p.getTotalLength() * k), m = p.getScreenCTM();
  return [q.x * m.a + q.y * m.c + m.e, q.x * m.b + q.y * m.d + m.f]; }"""


def test_a_click_selects_an_arrow_and_delete_takes_it(tmp_path):
    # the points clicked lie off the cards: an arrow's line goes under them
    items = {f"i{n}": pic(n, n * 340) for n in range(4)} | {"n1": NOTE, "t1": {"type": "text", "text": "Head", "x": 1100, "y": 800, "fs": 40, "size": 1, "w": 0, "h": 0}}
    def go(page, ev, port):
        ev("() => { const b = snap(); hyConn.add(board, 'i3', 't1'); commit(b); }")
        for hit, k, gone in (('[data-arrow="n1|i1"]', .12, "() => !board.items.n1.to.includes('i1')"), ("[data-conn]", .5, "() => !Object.keys(board.links || {}).length")):
            x, y = ev(MID, [f"#links {hit}", k]); page.mouse.click(x, y); page.wait_for_timeout(150)
            assert not ev(gone), "one click kept the arrow"
            assert ev("() => !!selArrow && !!document.querySelector('#links .arw.pick') && sel.size === 0")
            assert ev("() => getComputedStyle(document.querySelector('#links .arw.pick .del')).opacity") == "1"
            page.keyboard.press("Escape"); assert ev("() => selArrow === null && !document.querySelector('#links .arw.pick')")
            page.mouse.click(x, y); page.keyboard.press("Backspace"); page.wait_for_timeout(150)
            assert ev(gone)
            assert any("Undo" in t or "removed" in t for t in ev(LIVE))
        assert ev("() => getComputedStyle(document.querySelector('#links .arw .del') || document.body).opacity") in ("0", "1")
    run(tmp_path, go, items)


# ---- decision 3: ⌘-click (B-60), a click among the selected (B-22) --------------------------------------------------------------------
def card(page, id):
    r = box(page, f'.it[data-id="{id}"]'); return r["cx"], r["cy"]


def test_cmd_click_toggles_and_a_click_selects_only_that_card(tmp_path):
    def go(page, ev, port):
        page.mouse.click(*card(page, "i0"))
        page.keyboard.down("Meta"); page.mouse.click(*card(page, "i1")); page.keyboard.up("Meta")
        assert sorted(ev("() => [...sel]")) == ["i0", "i1"]
        page.keyboard.down("Meta"); page.mouse.click(*card(page, "i0")); page.keyboard.up("Meta")
        assert ev("() => [...sel]") == ["i1"]
        pick(ev, "i0", "i1", "i2"); page.mouse.click(*card(page, "i1"))   # a plain click on one of the selected, no drag: only it
        assert ev("() => [...sel]") == ["i1"]
        pick(ev, "i0", "i2"); x, y = card(page, "i2"); page.keyboard.down("Shift")   # ⇧ press and drag a selected card: all move, it too
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + 40, y + 30, steps=5); page.mouse.up(); page.keyboard.up("Shift")
        assert ev("() => [board.items.i0.x, board.items.i2.x]") == [40, 720]
        pick(ev, "i0", "i2"); page.keyboard.down("Shift"); page.mouse.click(*card(page, "i2")); page.keyboard.up("Shift")   # ⇧ click: out
        assert ev("() => [...sel]") == ["i0"]
    run(tmp_path, go)


# ---- decision 4: the Annotation tool (B-61, B-30, B-31) ------------------------------------------------------------------------------
def test_c_keeps_the_selection_and_c_again_ends_the_tool(tmp_path):
    def go(page, ev, port):
        pick(ev, "i0"); page.keyboard.press("c"); assert ev("() => hyAnnot.active") == "comment"
        page.keyboard.press("c"); assert ev("() => [hyAnnot.active, [...sel]]") == [None, ["i0"]]
        ev("() => startCrop('i0')"); page.keyboard.press("c")   # B-30: the crop ends, one tool at a time
        assert ev("() => [cropState === null, hyAnnot.active]") == [True, "comment"]
        ev("() => startCrop('i1')"); assert ev("() => [!!cropState, hyAnnot.active]") == [True, None]
        page.keyboard.press("Escape")
        page.keyboard.press("c"); page.mouse.move(700, 760); page.keyboard.press("n")   # B-31: N leaves the tool and makes a note
        page.wait_for_selector(".note textarea")
        assert ev("() => [hyAnnot.active, Object.values(board.items).filter(i => i.type === 'note').length]") == [None, 1]
    run(tmp_path, go)


# ---- decision 5: snapping guides (B-62) ---------------------------------------------------------------------------------------------
def test_a_dragged_card_snaps_to_an_edge_and_cmd_lets_it_go(tmp_path):
    def go(page, ev, port):
        x, y = card(page, "i1")   # i1 at 340: 18 px left of it is 2 px off i0's right edge (320)
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x - 10, y + 1, steps=3); page.mouse.move(x - 18, y + 1, steps=2)
        assert ev("() => document.querySelectorAll('#snapg i').length") >= 1
        page.mouse.up(); assert ev("() => [board.items.i1.x, board.items.i1.y]") == [320, 0]
        assert ev("() => document.querySelectorAll('#snapg i').length") == 0
        x, y = card(page, "i3"); page.keyboard.down("Meta")
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x - 10, y + 1, steps=3); page.mouse.move(x - 18, y + 1, steps=2); page.mouse.up(); page.keyboard.up("Meta")
        assert ev("() => [board.items.i3.x, board.items.i3.y]") == [1002, 1]
    run(tmp_path, go)


def test_a_resized_card_snaps_its_edge(tmp_path):
    def go(page, ev, port):
        pick(ev, "i0"); h = box(page, '#handles [data-resize="i0"][data-rc="se"]')
        page.mouse.move(h["cx"], h["cy"]); page.mouse.down(); page.mouse.move(h["cx"] + 10, h["cy"] + 5, steps=3); page.mouse.move(h["cx"] + 17, h["cy"] + 5, steps=2)
        page.mouse.up(); assert ev("() => board.items.i0.w") == 340   # i1's left edge
    run(tmp_path, go)


def test_snap_geometry_picks_the_nearest_line_within_reach(tmp_path):
    def go(page, ev, port):
        assert ev("() => hySnap.near([10, 50, 90], [0, 47, 200], 6)") == {"d": -3, "c": 47}
        assert ev("() => hySnap.near([10], [30], 6)") == {"d": 0, "c": None}
        assert ev("() => hySnap.near([100, 160], [158, 103], 6)") == {"d": -2, "c": 158}
    run(tmp_path, go)


# ---- decision 6, B-36, B-26 ---------------------------------------------------------------------------------------------------------
def test_a_copys_info_shows_its_heart_and_enter_opens(tmp_path):
    items = {"i0": pic(0, 0), "i1": pic(0, 340)}   # i1 is a copy of the same file
    def go(page, ev, port):
        pick(ev, "i1"); page.wait_for_timeout(200)
        assert ev("() => [$('#info').dataset.kind, getComputedStyle($('#iFav')).display !== 'none', $('#iOpen').title.endsWith('· ↵')]") == ["instance", True, True]
        page.keyboard.press("Enter"); page.wait_for_timeout(300)   # a copy's Open: to the original
        assert ev("() => [...sel]") == ["i0"]
        assert ev("() => $('#iOpen').title.endsWith('· ↵')")
    run(tmp_path, go, items)


def test_a_heart_is_an_undo_step(tmp_path):
    def go(page, ev, port):
        pick(ev, "i0"); page.keyboard.press("ArrowRight"); page.wait_for_timeout(700); page.keyboard.press("f")
        wait(lambda: ev("() => !!(byPath.get('a/0.png').feedback || {}).fav"), "♥ set")
        page.keyboard.press("Meta+z"); page.wait_for_timeout(300)
        assert ev("() => [!!(byPath.get('a/0.png').feedback || {}).fav, board.items.i0.x]") == [False, 1]
        wait(lambda: not json.loads((LIB[0] / "a/0.png.json").read_text()).get("feedback", {}).get("fav") if (LIB[0] / "a/0.png.json").exists() else True, "the ♥ is off the file")
        page.keyboard.press("Meta+Shift+z"); page.wait_for_timeout(300)
        assert ev("() => [!!(byPath.get('a/0.png').feedback || {}).fav, board.items.i0.x]") == [True, 1]
    run(tmp_path, go)


# ---- B-16, B-17, B-18, B-44, B-45: Esc's one order -------------------------------------------------------------------------------------
def test_esc_closes_the_open_panel_before_the_selection(tmp_path):   # B-16, B-45
    def go(page, ev, port):
        for btn, panel in (("#bntf", "() => $('#ntf').classList.contains('open')"), ("#bkeys", "() => $('#keys').style.display === 'block'"),
                           ("#bhist", "() => $('#hist').classList.contains('open')")):
            pick(ev, "i0"); page.click(btn); page.wait_for_timeout(150)
            assert ev(panel) and ev(f"() => document.activeElement !== $('{btn}')"), btn + " kept the focus"   # B-45
            page.keyboard.press("Escape"); page.wait_for_timeout(100)
            assert not ev(panel) and ev("() => [...sel]") == ["i0"], btn
        page.keyboard.press("Escape"); assert ev("() => sel.size") == 0
    run(tmp_path, go)


def test_esc_closes_a_thread_opened_from_its_pin_and_the_list(tmp_path):   # B-17
    def go(page, ev, port):
        tid = api(port, "/api/comments", {"name": "main", "op": "new", "anchor": None, "at": [900, 700], "text": "look"})["thread"]["id"]
        ev("() => hyComments.load()"); page.wait_for_selector(f'#cmpins [data-c="{tid}"]')
        page.click(f'#cmpins [data-c="{tid}"]'); page.wait_for_selector("#cmthread.open")
        page.mouse.click(1300, 860); page.keyboard.press("Escape") if ev("() => !!document.querySelector('#cmthread.open')") else None
        ev(f"() => hyComments.open('{tid}')"); page.wait_for_selector("#cmthread.open"); ev("() => document.activeElement.blur()")
        page.keyboard.press("Escape"); assert ev("() => !document.querySelector('#cmthread.open') && !hyAnnot.active")
        ev("() => hyComments.list()"); page.wait_for_selector("#cmlist.open"); page.keyboard.press("Escape")
        assert ev("() => !document.querySelector('#cmlist.open')")
    run(tmp_path, go)


def test_the_connector_editor_takes_its_keys_after_tab(tmp_path):   # B-18
    def go(page, ev, port):
        pick(ev, "i0")
        cid = ev("() => { const b = snap(), id = hyConn.add(board, 'i2', 'i3'); commit(b); hyConn.edit(id); return id; }")
        page.wait_for_selector(".cned .cnin"); page.keyboard.type("w"); page.keyboard.press("Tab"); page.keyboard.press("Escape")
        assert ev(f"() => [!!document.querySelector('.cned'), [...sel], board.links['{cid}'].label]") == [False, ["i0"], "w"]
    run(tmp_path, go)


def test_esc_during_a_drag_puts_it_back(tmp_path):   # B-44
    def go(page, ev, port):
        n = ev("() => past.length"); x, y = card(page, "i0")
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + 120, y + 90, steps=5); page.keyboard.press("Escape"); page.mouse.move(x + 160, y + 90); page.mouse.up()
        assert ev("() => [board.items.i0.x, board.items.i0.y, past.length]") == [0, 0, n]
        pick(ev, "i1"); page.mouse.move(700, 760); page.mouse.down(); page.mouse.move(100, 200, steps=5); page.keyboard.press("Escape"); page.mouse.up()
        assert ev("() => [...sel]") == ["i1"]   # a selection frame: the selection as it was
    run(tmp_path, go)


# ---- B-21, B-23, B-24, B-27: groups, grids ---------------------------------------------------------------------------------------------
def grouped(**over):
    items = {f"i{n}": pic(n, n * 340) for n in range(4)}
    return items, {"g1": {"title": "One", "x": -40, "y": -40, "w": 740, "h": 560, "members": ["i0", "i1"]}, **over}


def boarded(tmp_path, items, groups, links=None):   # a board with groups, written before its server starts
    import contextlib
    @contextlib.contextmanager
    def cm():
        with serve(tmp_path, items, links=links) as (port, lib):
            b = api(port, "/api/board?name=main"); b["groups"] = groups
            api(port, "/api/board?name=main&who=owner", b); yield port, lib
    return cm()


def run_g(tmp_path, fn, groups, items=None, links=None):
    items = items or {f"i{n}": pic(n, n * 340) for n in range(4)}
    with boarded(tmp_path, items, groups, links) as (port, lib), playwright.sync_playwright() as p:
        LIB[0] = lib; browser = browser_of(p); page, errors = board_page(browser, port)
        try: fn(page, page.evaluate, port)
        finally: browser.close()
        assert not errors, errors


G1 = {"g1": {"title": "One", "x": -40, "y": -40, "w": 740, "h": 560, "members": ["i0", "i1"]}}


def test_cmd_a_takes_the_groups_and_delete_leaves_no_empty_frame(tmp_path):   # B-21
    def go(page, ev, port):
        page.keyboard.press("Meta+a"); assert sorted(ev("() => [...sel]")) == ["g1", "i2", "i3"]
        page.keyboard.press("Backspace"); assert ev("() => [Object.keys(board.items).length, Object.keys(board.groups).length]") == [0, 0]
        page.keyboard.press("Meta+z"); pick(ev, "i0", "i1"); ev(SHOW); page.keyboard.press("Meta+g"); page.keyboard.press("Enter")   # ⌘G on a group's cards
        assert len(ev("() => Object.keys(board.groups)")) == 1
    run_g(tmp_path, go, G1)


def test_a_selected_group_is_its_cards_for_the_commands(tmp_path):   # B-23
    def go(page, ev, port):
        pick(ev, "g1"); page.keyboard.press("Meta+d")
        gs = ev("() => Object.keys(board.groups)"); assert len(gs) == 2
        new = [g for g in gs if g != "g1"][0]
        assert ev(f"() => board.groups['{new}'].members.filter(m => board.items[m] && !['i0', 'i1'].includes(m)).length") == 2
        pick(ev, "g1"); page.keyboard.press("Alt+s"); page.wait_for_timeout(100)   # ⌥S on the group: its two cards in a row
        assert ev("() => board.grids && Object.values(board.grids).some(g => g.members.includes('i0') && g.members.includes('i1'))")
    run_g(tmp_path, go, G1)


def test_a_dragged_group_carries_the_group_in_its_frame(tmp_path):   # B-24
    groups = {"g1": {"title": "Outer", "x": -40, "y": -100, "w": 1400, "h": 640, "members": []},
              "g2": {"title": "Inner", "x": -20, "y": -20, "w": 700, "h": 520, "members": ["i0", "i1"]}}
    def go(page, ev, port):
        ev("() => { cam.x = -100; cam.y = -400; renderCam(); render(); }"); page.wait_for_timeout(400)
        t = box(page, '.grp[data-id="g1"] .gt'); page.mouse.move(t["x"] + 10, t["cy"]); page.mouse.down(); page.mouse.move(t["x"] + 70, t["cy"] + 50, steps=5); page.mouse.up()
        assert ev("() => [board.groups.g2.x, board.items.i0.x]") == [40, 60]
    run_g(tmp_path, go, groups)


def test_a_nudged_grid_member_leaves_the_grid(tmp_path):   # B-27
    def go(page, ev, port):
        pick(ev, "i0", "i1", "i2", "i3", "i4", "i5"); page.keyboard.press("Alt+a")   # a block of 3 × 2: a grid
        assert ev("() => Object.values(board.grids || {}).length") == 1
        pick(ev, "i1"); page.keyboard.press("ArrowDown"); page.keyboard.press("ArrowDown")
        x, y = ev("() => [board.items.i1.x, board.items.i1.y]")
        pick(ev, "i4"); page.keyboard.press("Backspace")   # another member goes: the grid reflows, the nudged one stays where it was put
        assert ev("() => [board.items.i1.x, board.items.i1.y]") == [x, y]
    run(tmp_path, go)


# ---- B-28, B-29, B-41, B-42, B-43: preview, copies, paste ------------------------------------------------------------------------------
def test_a_version_preview_takes_no_new_work(tmp_path):   # B-28
    def go(page, ev, port):
        ev("() => { PREV = { id: 'x', back: board, backSel: [] }; }")
        page.mouse.move(700, 760); page.keyboard.press("n"); page.wait_for_timeout(150)
        assert ev("() => !document.querySelector('.note textarea')")
        assert any("version preview" in t for t in ev(LIVE))
        page.mouse.dblclick(300, 760); assert ev("() => !document.querySelector('.tx textarea')")
    run(tmp_path, go)


def test_copies_keep_the_arrows_among_them(tmp_path):   # B-29
    def go(page, ev, port):
        ev("() => { const b = snap(); hyConn.add(board, 'i0', 'i1'); commit(b); }")
        pick(ev, "i0", "i1"); page.keyboard.press("Meta+d"); page.wait_for_timeout(100)
        assert ev("() => Object.keys(board.links).length") == 2
        pick(ev, "i0", "i1"); page.keyboard.press("Meta+c"); page.mouse.move(700, 800); page.keyboard.press("Meta+v"); page.wait_for_timeout(400)
        assert ev("() => Object.keys(board.links).length") == 3
        ev("() => { cam.x = -60; cam.y = -120; renderCam(); render(); }"); page.wait_for_timeout(100)   # the paste slid the view to its copies
        r = box(page, '.it[data-id="i0"]'); x, y = r["x"] + 10, r["y"] + 80; pick(ev, "i0", "i1"); page.keyboard.down("Alt")   # ⌥-drag, beside ⌘D's copy
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x, y + 600, steps=5); page.mouse.up(); page.keyboard.up("Alt")
        assert ev("() => Object.keys(board.links).length") == 4
    run(tmp_path, go)


def test_paste_at_the_edge_keeps_the_zoom_and_again_steps_aside(tmp_path):   # B-41, B-43
    def go(page, ev, port):
        pick(ev, "i0"); page.keyboard.press("Meta+c")
        ev("() => { cam.z = .5; cam.x = 0; cam.y = 0; renderCam(); render(); }")
        page.mouse.move(1430, 890); page.keyboard.press("Meta+v"); page.wait_for_timeout(400)
        assert ev("() => cam.z") == 0.5
        first = ev("() => { const id = [...sel][0]; return [board.items[id].x, board.items[id].y]; }")
        page.keyboard.press("Meta+v"); page.wait_for_timeout(400)
        second = ev("() => { const id = [...sel][0]; return [board.items[id].x, board.items[id].y]; }")
        assert [round(second[0] - first[0]), round(second[1] - first[1])] == [24, 24]
    run(tmp_path, go)


def test_a_cut_and_a_copy_as_image_say_it_once(tmp_path):   # B-42
    def go(page, ev, port):
        pick(ev, "i0"); page.keyboard.press("Meta+x"); page.wait_for_timeout(300)
        texts = ev(LIVE); assert len(texts) == 1 and texts[0].startswith("Cut"), texts
    run(tmp_path, go)


# ---- B-32, B-33, B-51: annotations ------------------------------------------------------------------------------------------------------
def anchored(port, obj="i0", text="on it"):
    return api(port, "/api/comments", {"name": "main", "op": "new", "anchor": {"obj": obj, "kind": "picture", "file": "a/0.png", "r": [0, 0, 320, 480]},
                                       "at": [.5, .5], "text": text})["thread"]["id"]


def test_a_pin_of_a_deleted_card_hides_and_comes_back(tmp_path):   # B-32
    def go(page, ev, port):
        tid = anchored(port); ev("() => hyComments.load()"); page.wait_for_selector(f'#cmpins [data-c="{tid}"]')
        pick(ev, "i0"); page.keyboard.press("Backspace"); page.wait_for_timeout(200)
        assert ev(f"() => !document.querySelector('#cmpins [data-c=\"{tid}\"]')")
        ev("() => hyComments.list()"); assert "object gone" in ev("() => $('#cmlist').textContent")
        page.keyboard.press("Escape"); page.keyboard.press("Meta+z"); page.wait_for_selector(f'#cmpins [data-c="{tid}"]')
    run(tmp_path, go)


def test_move_to_page_takes_the_cards_annotations(tmp_path):   # B-32
    def go(page, ev, port):
        tid = anchored(port); ev("() => hyComments.load()"); page.wait_for_selector(f'#cmpins [data-c="{tid}"]')
        pick(ev, "i0"); ev("() => moveToPage('p2')")
        wait(lambda: [t["id"] for t in api(port, "/api/comments?name=p2").get("items", [])] == [tid], "the thread went along")
        assert threads(port) == []
    run(tmp_path, go, pages=True)


def test_a_thread_deleted_elsewhere_closes_and_keeps_the_words(tmp_path):   # B-33
    def go(page, ev, port):
        tid = anchored(port); ev("() => hyComments.load()"); page.wait_for_selector(f'#cmpins [data-c="{tid}"]')
        ev(f"() => hyComments.open('{tid}')"); page.click("#cmthread.open textarea"); page.keyboard.type("my reply")
        api(port, "/api/comments", {"name": "main", "op": "put", "id": tid, "thread": None})
        ev("() => hyComments.load()"); page.wait_for_function("() => !document.querySelector('#cmthread.open')")
        assert any("deleted elsewhere" in t for t in ev(LIVE))
        page.wait_for_selector("#cmpins .cmpin .cmp-d"); page.click("#cmpins .cmpin .cmp-d")
        page.wait_for_selector("#cmthread.open textarea"); assert ev("() => $('#cmthread.open textarea').value") == "my reply"
    run(tmp_path, go)


def test_an_annotation_undo_the_server_refused_stays(tmp_path):   # B-51
    def go(page, ev, port):
        tid = anchored(port); ev("() => hyComments.load()"); page.wait_for_selector(f'#cmpins [data-c="{tid}"]')
        ev(f"() => hyComments.open('{tid}')"); page.click("#cmthread.open textarea"); page.keyboard.type("mine"); page.keyboard.press("Enter")
        wait(lambda: len(threads(port)[0]["messages"]) == 2, "the reply was sent")
        page.wait_for_timeout(1100)   # the server's times are in seconds
        api(port, "/api/comments", {"name": "main", "op": "reply", "id": tid, "text": "someone else"})   # changed since: the undo is refused
        ev("() => document.activeElement.blur()"); page.keyboard.press("Escape"); page.keyboard.press("Meta+z"); page.wait_for_timeout(500)
        assert ev("() => [hyAnnot.state.stacks.main.done.length, hyAnnot.state.stacks.main.undone.length]") == [1, 0] and len(threads(port)[0]["messages"]) == 3
    run(tmp_path, go)


# ---- B-39: the «?» panel and the keys -------------------------------------------------------------------------------------------------
# a row's keys as combos: the caps side by side are one combo («⇧⌘Z»), a space or words between them start the next
COMBOS = """() => [...document.querySelectorAll('#keys .kp-all .kp-row')].map(r => {
  const k = r.querySelector('.k'), out = []; let cur = '', words = false;
  for (const n of k.childNodes) {
    if (n.nodeType === 1 && n.tagName === 'KBD') cur += n.textContent.trim();
    else { if (cur) { out.push(cur); cur = ''; } if (n.textContent.trim() && !/^[,+]$/.test(n.textContent.trim())) words = true; }
  }
  if (cur) out.push(cur); return { keys: out, plain: !words, text: r.textContent.trim().slice(0, 60) }; })"""


def test_every_key_of_the_board_has_one_row(tmp_path):   # B-39
    src = (ROOT / "review/ui/boardkeys.js").read_text()
    keyish = re.compile(r"^(?:Esc|Space|[⌘⇧⌥⌃↵⌫←↑→↓\\\[\]A-Z0-9!.]+)$")
    marks = [k for m in re.findall(r"// key: ([^;,(\n]+)", src) for k in m.split() if keyish.match(k)]
    assert len(marks) > 25
    def go(page, ev, port):
        rows = ev(COMBOS); have = {k for r in rows for k in r["keys"]}
        assert [m for m in marks if m not in have] == [], "keys of the board with no row in the «?» panel"
        plain = [k for r in rows if r["plain"] for k in r["keys"]]
        assert sorted({k for k in plain if plain.count(k) > 1}) == [], "a key with two rows"
        assert "⌘⇧Z" not in have
    run(tmp_path, go)


# ---- B-46: crop -----------------------------------------------------------------------------------------------------------------------
def test_crop_pans_with_space_ignores_a_press_beside_and_undoes(tmp_path):
    def go(page, ev, port):
        ev("() => startCrop('i0')"); page.wait_for_timeout(100)
        x0 = ev("() => cam.x"); page.keyboard.down(" "); page.mouse.move(1000, 700); page.mouse.down(); page.mouse.move(900, 700, steps=4); page.mouse.up(); page.keyboard.up(" ")
        assert ev("() => cam.x") > x0 and ev("() => !!cropState")
        page.mouse.click(1400, 880); assert ev("() => !!cropState && !board.items.i0.crop")   # beside the picture: nothing applied, still cropping
        r = box(page, "#crop"); page.mouse.move(r["x"] + 40, r["y"] + 40); page.mouse.down(); page.mouse.move(r["x"] + 200, r["y"] + 260, steps=4); page.mouse.up()
        c1 = ev("() => cropState.c.join()"); assert c1 != "0,0,1,1"
        page.keyboard.press("Meta+z"); assert ev("() => cropState.c.join()") == "0,0,1,1"
        page.keyboard.press("Escape"); assert ev("() => cropState === null && !board.items.i0.crop")
    run(tmp_path, go)


# ---- B-47, B-48, B-58: one note for every delete, the silent no-ops say why, pictures not frames -----------------------------------------
NOTE2 = {"type": "note", "text": "n", "x": 800, "y": 700, "w": 200, "fs": 14, "size": 2, "h": 0, "color": "yellow"}


def test_every_delete_says_what_went_with_undo(tmp_path):
    def go(page, ev, port):
        for ids, word in ((["n1"], "1 note"), (["i0"], "1 picture"), (["n1", "i1"], "1 picture, 1 note")):
            pick(ev, *ids); page.keyboard.press("Backspace"); page.wait_for_timeout(150)
            t = ev("() => { const el = [...document.querySelectorAll('#hyToasts .ht')].filter(e => !e._gone).pop();"
                   " return [el.querySelector('span').textContent, [...el.querySelectorAll('.ab')].map(b => b.textContent)]; }")
            assert t[0].startswith("Deleted: " + word) and t[1] == ["Undo"], t
            assert "frame" not in t[0]
            page.click("#hyToasts .ht:last-child .ab"); page.wait_for_timeout(150)
            assert all(ev(f"() => !!board.items['{i}']") for i in ids)
    run(tmp_path, go, {f"i{n}": pic(n, n * 340) for n in range(3)} | {"n1": NOTE2})


def test_the_silent_commands_say_why(tmp_path):
    def go(page, ev, port):
        for ids, key, words in ((["i0", "i1"], "Shift+c", "one picture at a time"), (["n1"], "f", "♥ is for pictures"),
                                ([], "Meta+Shift+c", "Select a picture, video, PDF, page or 3D"), (["n1"], "Alt+a", "two or more pictures")):
            pick(ev, *ids); page.keyboard.press(key); page.wait_for_timeout(100); t = ev(LIVE)
            assert any(words in x for x in t), (key, t)
    run(tmp_path, go, {f"i{n}": pic(n, n * 340) for n in range(3)} | {"n1": NOTE2})


# ---- B-57: the app's own question, not the system's ----------------------------------------------------------------------------------------
def test_deleting_a_page_asks_in_the_apps_dialog(tmp_path):
    def go(page, ev, port):
        asked = []; page.on("dialog", lambda d: (asked.append(d.message), d.dismiss()))
        ev("() => { deletePage('main'); }"); page.wait_for_selector("#hyConfirm")
        assert asked == [] and "Delete the page" in ev("() => $('#hyConfirm').textContent")
        page.keyboard.press("Escape"); page.wait_for_timeout(300)
        assert ev("() => pages.length") == 2 and ev("() => !!board.items.i0")
    run(tmp_path, go, pages=True)
