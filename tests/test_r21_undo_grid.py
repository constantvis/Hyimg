"""Round 21 on the board (owner 2026-10-11). Chromium, dark theme, our own temporary server (tests/test_p4_board.py's harness).

  r21/undo-config.html   every step's note: white words, the kind in the dot (blue, green, yellow), the step's pictures as tiles and Undo;
                         a refusal is yellow; ♥ has Undo; ⌘D, a crop and ⌥A name their step by the command (round 20 B-12); the
                         step's name over the dock's Undo with its pictures
  r21/grid-b.html ♥      ⌥A keeps the grid where the selection was, what it covers moves down, one undo step, a note says it
  r21/tl-star.html       the timeline's one icon, two dots, a line, an arrow: «+» and the «?» panel show the same"""
import pytest

from test_p4_board import board_page, browser_of, serve, wait

playwright = pytest.importorskip("playwright.sync_api")
LAST = """() => { const el = [...document.querySelectorAll('#hyToasts .ht')].filter(e => !e._gone).pop(); if (!el) return null;
  const cs = e => getComputedStyle(e);
  return { words: el.querySelector('span').textContent, kind: el.className, ink: cs(el.querySelector('span')).color, dot: cs(el.querySelector('i')).backgroundColor,
           buttons: [...el.querySelectorAll('.ab')].map(b => b.textContent), tiles: el.querySelectorAll('.th b').length,
           more: (el.querySelector('.th em') || {}).textContent || '', tile: (el.querySelector('.th b') || { style: {} }).style.backgroundImage || '' }; }"""
INK = "() => getComputedStyle(document.documentElement).getPropertyValue('--ink').trim()"
STEP = "() => hyBoardDock.stepName('undo')"


def sq(n, x, y, w=100, ar=1.0):
    return {"path": f"a/{n}.png", "x": x, "y": y, "w": w, "ar": ar, "crop": None}


def rgb(page, css):   # a CSS colour as the page computes it
    return page.evaluate("c => { const e = document.createElement('i'); e.style.color = c; document.body.append(e); const v = getComputedStyle(e).color; e.remove(); return v; }", css)


def run(tmp_path, items, fn):
    with serve(tmp_path, items) as (port, lib), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port)
        try: fn(page, page.evaluate)
        finally: browser.close()
        assert not errors, errors


def pick(ev, *ids):
    ev(f"() => {{ sel = new Set({list(ids)!r}); render(); }}")


def last(page):
    return page.evaluate(LAST)


def test_alt_a_keeps_the_grid_in_place_and_moves_the_covered_neighbours_down_in_one_step(tmp_path):
    items = {f"s{k}": sq(k, k * 120, 0) for k in range(6)} | {"n0": sq(0, 0, 150, 200, 2.0), "n2": sq(1, 900, 150)}

    def go(page, ev):
        pick(ev, *[f"s{k}" for k in range(6)]); n = ev("() => past.length")
        page.keyboard.press("Alt+a")
        wait(lambda: ev("() => board.items.n0.y") != 150, "the neighbour under the second row did not move")
        assert ev("() => [board.items.s3.x, board.items.s3.y, board.items.s5.x]") == [0, 124, 248]   # the grid from the selection's top left
        assert ev("() => board.items.n0.y") == 248 and ev("() => board.items.n2.y") == 150   # just below the grid; the one apart stays
        t = wait(lambda: last(page), "no note")
        assert t["words"].startswith("Moved down to make room") and t["buttons"] == ["Undo"], t
        assert t["tiles"] == 3 and t["more"] == "+3" and "/thumb?" in t["tile"], t   # the step's six pictures: three tiles and «+3»
        assert t["ink"] == rgb(page, ev(INK)) and t["dot"] == rgb(page, "#0a84ff"), t   # white words, the blue dot of «what happened»
        assert ev(STEP) == "Arrange as a grid" and ev("() => past.length") == n + 1   # one step, named by the command
        # the step's name over Undo comes with its pictures (r21/undo-config.html: «Имя шага над Undo с вещами (как в undo-b)»)
        r = page.locator("#bundo").bounding_box(); page.mouse.move(r["x"] + r["width"] / 2, r["y"] + r["height"] / 2)
        tip = wait(lambda: ev("""() => { const p = document.getElementById('hytip'); return p && p.hasAttribute('shown') && {
          t: p.querySelector('.tt-t').textContent, sub: p.querySelector('.tt-s').textContent, tiles: p.querySelectorAll('.tt-th b').length,
          more: (p.querySelector('.tt-th em') || {}).textContent, above: p.getBoundingClientRect().bottom <= document.getElementById('bundo').getBoundingClientRect().top }; }"""),
                   "no tooltip over Undo")
        assert tip == {"t": "Undo", "sub": "Arrange as a grid", "tiles": 3, "more": "+3", "above": True}, tip
        page.mouse.move(700, 450)
        page.click("#hyToasts .ht:last-child .ab")   # its Undo, with the mouse
        wait(lambda: ev("() => board.items.n0.y === 150 && board.items.s3.x === 360 && board.items.s3.y === 0"), "Undo did not take the whole step")
    run(tmp_path, items, go)


def test_every_steps_note_has_undo_the_refusal_is_yellow_and_the_steps_are_named_by_their_command(tmp_path):
    items = {f"i{n}": sq(n, n * 340, 0, 320, 2 / 3) for n in range(3)}

    def go(page, ev):
        # ♥: green, with Undo (round 20 B-12: it had none, though ⌘Z takes it), the picture as its tile
        pick(ev, "i0"); page.keyboard.press("f")
        wait(lambda: ev("() => !!(byPath.get('a/0.png').feedback || {}).fav"), "♥ set")
        t = last(page); assert t["words"] == "♥ set" and t["buttons"] == ["Undo"] and t["tiles"] == 1, t
        assert t["dot"] == rgb(page, "#30d158") and t["ink"] == rgb(page, ev(INK)), t
        page.click("#hyToasts .ht:last-child .ab")
        wait(lambda: ev("() => !(byPath.get('a/0.png').feedback || {}).fav"), "Undo on the note did not take the ♥ off")
        # a refusal says why in yellow
        pick(ev, "i0", "i1"); page.keyboard.press("Shift+c")
        t = wait(lambda: (lambda x: x if x and "at a time" in x["words"] else None)(last(page)), "no refusal")
        assert "warn" in t["kind"] and t["dot"] == rgb(page, "#fbbf24") and t["buttons"] == [], t
        # ⌘D and a crop: the dock's Undo says the command, not «New card» and «Size»
        pick(ev, "i0"); page.keyboard.press("Meta+d"); wait(lambda: ev("() => Object.keys(board.items).length") == 4, "⌘D")
        assert ev(STEP) == "Duplicate"
        ev("() => { startCrop('i1'); cropState.c = [0.1, 0.1, 0.9, 0.9]; applyCrop(); }")
        assert ev(STEP) == "Crop"
    run(tmp_path, items, go)


def test_the_timeline_wears_one_icon_in_plus_and_in_the_keys_panel(tmp_path):
    def go(page, ev):
        want = ev("() => document.createRange().createContextualFragment(hyIcon('timeline', 16, 1.85)).firstElementChild.innerHTML")
        assert 'cx="4.5"' in want and "m17.5 8.5 3.5 3.5-3.5 3.5" in want   # two dots, a line, an arrow (r21/tl-star.html)
        page.locator("#bplus").click(); page.wait_for_selector("#bplusm.open")
        assert ev("() => document.querySelector('#bplusm [data-mk=timeline] svg').innerHTML") == want
        page.keyboard.press("Escape")
        page.click("#bkeys"); page.wait_for_selector("#keys .kp-tab[data-kt=all]"); page.click("#keys .kp-tab[data-kt=all]")
        row = wait(lambda: ev("""() => { const r = [...document.querySelectorAll('#keys .kp-all > .kp-row')].find(r =>
          [...r.querySelectorAll('.k kbd')].map(k => k.textContent.trim()).join('') === 'L'); return r && r.querySelector(':scope > .kpi').innerHTML; }"""),
                   "no L row in the «?» panel")
        assert row == ev("() => Object.assign(document.createElement('i'), { innerHTML: HY_IC.timeline }).innerHTML"), row
    run(tmp_path, None, go)
