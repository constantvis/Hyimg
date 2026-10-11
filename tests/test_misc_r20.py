"""Round 20's small things (owner 2026-10-11 on misc-a.html and misc-b.html: «да давай всё по максимум делать»), each one rule in one place.
- B-17: the bar over a selection is put together one way (ui/selbar.js): the Studio | the kind's actions | ♥ | opacity, a hairline only
  between groups that have something; ♥ wherever it works (one picture and an HTML page had none, an HTML card had two hairlines in a row)
- B-22: every icon of the dock's «+» is 16 px, a plugin's too (3D Studio's was 18, its words 2 px further right)
- P-23 ★: a control reached by the keyboard (Tab) shows a 2 px ring of the selection's blue, a click never does (before: no ring at all)
- P-17: every pop-up is one surface (ui/tokens.css --hy-pop-*): the pages menu was glass 82 % and 16 px round beside the right click's
  92 % and 14, the library's view 94 % without saturation, its filters 20 px round; the card menu and the path's «…» kept a shadow under
  «No shadows»
Each test failed on the code before. Chromium, dark theme, a temporary library, the plugins from their repositories' last commits
(test_info_header.py's world)."""
import pytest

from test_info_header import open_board, until, world

playwright = pytest.importorskip("playwright.sync_api")

# the bar over the selection: its children in order, a hairline as "|", a button by its data attribute or its words
BAR = """() => { const t = document.querySelector('#handles .tidy:not(.plgedit)'); if (!t) return null;
  return [...t.children].map(c => c.classList.contains('sep') ? '|' : c.dataset.studiochip ? 'chip' : 'fav' in c.dataset ? '♥' : 'crop' in c.dataset ? 'crop'
    : c.querySelector && c.querySelector('[data-op]') ? 'opacity' : 'tidy' in c.dataset ? 'arrange' : 'plgbar' in c.dataset ? 'plugin' : c.tagName.toLowerCase()); }"""


def bar(page, *ids):
    page.evaluate("ids => { sel = new Set(ids); render(); }", list(ids)); page.wait_for_timeout(120)
    return page.evaluate(BAR)


def clean(b):   # no hairline first, last or twice in a row
    return b[0] != "|" and b[-1] != "|" and all(not (x == "|" and y == "|") for x, y in zip(b, b[1:]))


def test_b17_one_order_hairlines_only_between_groups_and_the_heart_wherever_it_works(tmp_path):
    with world(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        browser, page = open_board(p, port)
        one = bar(page, "p")
        assert one[:3] == ["chip", "|", "crop"] and "♥" in one and one[-1] == "opacity" and clean(one), one
        assert one.index("♥") < one.index("opacity"), one
        html = bar(page, "h")
        assert html[0] == "chip" and "♥" in html and clean(html), html   # it had «Dev Studio ↵ | | Opacity»
        three = bar(page, "s")
        assert three[0] == "chip" and "♥" not in three and clean(three), three   # a 3D scene takes no ♥
        two = bar(page, "p", "q")
        assert "chip" not in two and "♥" in two and two[-1] == "opacity" and clean(two), two
        # the ♥ of one picture likes it, as F does
        bar(page, "p"); page.click("#handles .tidy [data-fav]")
        until(page, "() => ((byPath.get('a/form.png') || {}).feedback || {}).fav === true")
        assert not page.errors, page.errors
        browser.close()


def test_b22_every_icon_of_plus_is_16_px_and_the_words_stand_in_one_column(tmp_path):
    with world(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        browser, page = open_board(p, port)
        page.click("#bplus"); page.wait_for_selector("#bplusm [role=menuitem]")
        rows = page.evaluate("""() => [...document.querySelectorAll('#bplusm [role=menuitem]')].map(b => { const i = b.querySelector('svg, img'), l = b.querySelector('.ml');
          return [l.textContent.trim(), Math.round(i.getBoundingClientRect().width), Math.round(l.getBoundingClientRect().left * 10) / 10]; })""")
        assert len(rows) >= 4 and "3D scene" in [r[0] for r in rows], rows   # the 3D plugin's item is there
        assert all(r[1] == 16 for r in rows), rows
        assert len({r[2] for r in rows}) == 1, rows
        assert not page.errors, page.errors
        browser.close()


def test_p23_the_keyboard_shows_where_the_focus_is_the_mouse_does_not(tmp_path):
    from test_p4_board import board_page, browser_of, serve
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port)
        RING = "() => { const e = document.activeElement, s = getComputedStyle(e); return [e.id || e.tagName, s.outlineStyle, s.outlineWidth]; }"
        page.click("#bhist"); page.wait_for_timeout(200)
        assert page.evaluate(RING)[1] == "none", ("a click shows no ring", page.evaluate(RING))
        page.click("#bhist"); page.mouse.click(700, 500)
        for _ in range(60):   # Tab until a button of the top row has the focus
            page.keyboard.press("Tab")
            if page.evaluate("() => ['bset', 'bkeys', 'bntf', 'bhist'].includes(document.activeElement.id)"): break
        got = page.evaluate(RING)
        assert got[0] in ("bset", "bkeys", "bntf", "bhist") and got[1] == "solid" and got[2] == "2px", got
        assert page.evaluate("() => getComputedStyle(document.activeElement).outlineColor") == page.evaluate(
            "() => { const d = document.createElement('i'); d.style.color = 'var(--hy-sel, var(--sel))'; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; }")
        browser.close()
        assert not errors, errors


SURF = """sel => { const e = document.querySelector(sel); if (!e) return null; const s = getComputedStyle(e);
  return { bg: s.backgroundColor, r: s.borderTopLeftRadius, blur: s.backdropFilter, line: s.borderTopWidth + ' ' + s.borderTopStyle, sh: s.boxShadow }; }"""


def test_p17_every_popup_is_one_surface(tmp_path):
    from test_p4_board import board_page, browser_of, serve
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port)
        ctx, pages = page.evaluate(SURF, "#ctx"), page.evaluate(SURF, "#pages")
        assert ctx["r"] == "14px" and "saturate(1.4)" in ctx["blur"] and pages == ctx, (ctx, pages)
        lp = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        lp.goto(f"http://127.0.0.1:{port}/?view=lib"); lp.wait_for_function("() => document.querySelector('#lview') && document.querySelector('#lctx')", timeout=20000)
        for sel in ("#lview", "#tfPanel", "#lctx"):
            got = lp.evaluate(SURF, sel)
            assert {k: got[k] for k in ("bg", "r", "blur", "line")} == {k: ctx[k] for k in ("bg", "r", "blur", "line")}, (sel, got, ctx)
        # «No shadows» (the setting cv.shadow 0) takes the pop-ups' shadow off, the library's card menu too
        lp.evaluate("() => { document.documentElement.dataset.shadow = '0'; }")
        sh = [lp.evaluate(SURF, s)["sh"] for s in ("#lview", "#tfPanel", "#lctx")]
        assert all(v == "none" or v == "rgba(0, 0, 0, 0) 0px 0px 0px 0px" for v in sh), sh
        browser.close()
        assert not errors, errors
