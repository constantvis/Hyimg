"""A thing made and named at once opens its name where a person sees it, and no board key fires while that name is pending (board audit
2026-10-11, B-09, B-11). ⌘G zoomed in: the new group's frame stands 1.5 picture widths off its pictures (owner 2026-09-29), its title
was above the screen and stuck to the top as a plate; the field went into the hidden title, the focus stayed on the page, and the typed
name ran the board's keys (F put ♥ on the pictures, N made a note). Chromium, dark theme, our own server (tests/test_p4_board.py)."""
import pytest

from test_p4_board import board_page, browser_of, serve

playwright = pytest.importorskip("playwright.sync_api")

# what the person sees of the field with the focus: in the window, not hidden
FOCUS = """() => { const a = document.activeElement; if (!a || a === document.body) return null; const r = a.getBoundingClientRect(),
  s = getComputedStyle(a), st = stage.getBoundingClientRect();
  return { tag: a.tagName, vis: s.visibility, in: r.width > 0 && r.left >= st.left - 1 && r.right <= st.right + 1 && r.top >= st.top - 1 && r.bottom <= st.bottom + 1 }; }"""
NOTES = "() => Object.values(board.items).filter(i => i.type === 'note').length"
FAVS = "() => Object.values(board.items).filter(i => i.path && ((byPath.get(i.path) || {}).feedback || {}).fav).length"


def run(tmp_path, fn):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port)
        try: fn(page, page.evaluate)
        finally: browser.close()
        assert not errors, errors


def test_cmd_g_zoomed_in_names_the_group_where_it_shows(tmp_path):
    def go(page, ev):
        # 90 %, three pictures filling the middle of the window: the new frame's title lies above the screen
        ev("() => { cam.z = 0.9; cam.x = -300; cam.y = -260; renderCam(); sel = new Set(['i0', 'i1', 'i2']); render(); }")
        page.mouse.move(720, 450); page.keyboard.press("Meta+g")
        page.wait_for_function("() => Object.keys(board.groups).length === 1")
        try: page.wait_for_function(f"() => {{ const f = ({FOCUS})(); return f && f.vis === 'visible' && f.in; }}", timeout=3000)   # a plate glides in
        except Exception: pass
        f = ev(FOCUS)
        assert f and f["vis"] == "visible" and f["in"], ("the name's field has the focus and shows", f)
        page.keyboard.type("Final look"); page.keyboard.press("Enter")
        assert ev("() => Object.values(board.groups).map(g => g.title)") == ["Final look"]
        assert ev(NOTES) == 0 and ev(FAVS) == 0, "no letter of the name ran a board key"
    run(tmp_path, go)


def test_no_board_key_fires_while_a_new_name_waits(tmp_path):
    def go(page, ev):
        # the focus never reaches the field (a hidden title, as B-09 was, or another window in front): the typed letters run no board key,
        # they go into the name
        ev("() => { sel = new Set(['i0', 'i1']); render(); window.F0 = HTMLElement.prototype.focus; HTMLElement.prototype.focus = function () {}; }")
        page.mouse.move(720, 450); page.keyboard.press("Meta+g")
        page.wait_for_function("() => Object.keys(board.groups).length === 1")
        ev("() => { HTMLElement.prototype.focus = window.F0; }")
        page.keyboard.type("fn")
        assert ev(NOTES) == 0 and ev(FAVS) == 0, "F and N wait while the group's name is open"
        # a click on the board ends the wait: the name is kept, the keys are the board's again
        page.mouse.click(720, 860)
        assert ev("() => Object.values(board.groups).map(g => g.title)") == ["fn"], "the letters went into the name, the first one too"; page.mouse.move(720, 450); page.keyboard.press("n")
        page.wait_for_function("() => Object.values(board.items).some(i => i.type === 'note')")
    run(tmp_path, go)


def test_a_new_timeline_fits_the_screen_and_its_label_shows(tmp_path):
    def go(page, ev):
        ev("() => { cam.z = 0.9; renderCam(); sel = new Set(); render(); }")
        page.mouse.move(720, 450); page.keyboard.press("l")
        page.wait_for_function("() => Object.values(board.items).some(i => i.type === 'timeline')")
        f = ev(FOCUS)
        assert f and f["vis"] == "visible" and f["in"], ("the first label's field shows", f)
        w = ev("() => { const it = Object.values(board.items).find(i => i.type === 'timeline'), st = stage.getBoundingClientRect();"
               " return [it.len * cam.z, hyBars.free(stage, INSET).r - hyBars.free(stage, INSET).l]; }")
        assert w[0] <= w[1] * 0.8 + 1, ("the new line is no wider than 80 % of the free board", w)
    run(tmp_path, go)


def test_a_new_page_and_a_note_name_where_they_show(tmp_path):
    def go(page, ev):
        ev("() => { cam.z = 2.5; renderCam(); render(); }")
        page.mouse.move(720, 450); page.keyboard.press("n"); page.wait_for_selector(".note textarea")
        f = ev(FOCUS); assert f and f["tag"] == "TEXTAREA" and f["vis"] == "visible", f
        page.keyboard.type("seen"); page.keyboard.press("Escape")
        assert ev("() => Object.values(board.items).filter(i => i.type === 'note').map(i => i.text)") == ["seen"]
        ev("() => openPages()"); page.click("#pgAdd"); page.wait_for_selector("#pages .row input")
        f = page.evaluate("() => { const a = document.activeElement; return a && a.tagName === 'INPUT' && a.closest('#pages') && getComputedStyle(a).visibility; }")
        assert f == "visible"
        page.keyboard.type("Ideas"); page.keyboard.press("Enter")
        page.wait_for_function("() => pages.some(p => p.title === 'Ideas')")
    run(tmp_path, go)
