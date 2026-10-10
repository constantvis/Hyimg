"""One dock for the board and the three Studios (owner 2026-10-10 on round 18, Concepts r18-dock.html, every question ★ yes, with the
owner's changes): ui/dock.js, ui/boarddock.js, ui/palette.js and the plugins beside this repository (../hyimg-image-studio,
../hyimg-3d-studio, ../hyimg-dev-studio). Chromium, the dark theme, our own temporary server and library, never the ports 4180–4184.

  ONE DOCK    every icon button of the four docks 36 × 34 with no plate; the groups between hairlines in one order: create | tools |
              Undo, Redo | view % | the Studio's own | the switch of Studios
  «+»         the board's create buttons under one «+» (owner: «Вот эта иконка мне вообще не нравится» of the timeline's): Note, Text,
              Timeline (the icon of a line with phases), the plugins' 3D scene; Text makes a text on the board with its field open
  G           G alone groups no more on the board, ⌘G does; the «?» panel says ⌘G only
  ⌘K          Actions in 3D Studio and Dev Studio, as in Image Studio: a search over the Studio's commands, ↵ runs one
  STEP NAME   over Undo or Redo under the pointer a plate names the step, and after ⌘Z for 2 s; the dock never gets wider (owner: «Я бы вот
              эти элементы делал по наведению, то есть чтобы оно изначально не расширяло этот элемент. У всех доков»)

  nice -n 10 python3 -m pytest -q tests/test_dock_r18.py
"""
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from test_p4_medium import COMBOS  # noqa: E402   the «?» panel's rows as key combos
from test_p4_studio_keys import Dev, Image, Studio3D, blur, board, serve  # noqa: E402

# the dock's groups in the order they stand, each a list of its parts; the hairlines split them
GROUPS = """() => {
  const d = document.getElementById('dock'), seen = el => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  const skip = el => el.closest('#modes > *, .ifcol > *, button > *') || el.matches('#tlib, #bpage');   // the library's own button: a browser only
  const els = [...d.querySelectorAll('button, .sep, .msep, #status, .ifcol, #modes')].filter(e => seen(e) && !skip(e))
    .sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
  const name = e => e.matches('.sep, .msep') ? '|' : e.id === 'modes' ? 'switch' : e.matches('.ifcol') ? 'colors' : e.matches('.ifg') ? 'tool'
    : e.matches('.ifann, [data-ann]') ? 'ann' : e.matches('.dkacts, #ifActs') ? 'acts' : (e.id || e.dataset.a || e.dataset.tool || (e.matches('[data-plus]') ? 'plus' : e.className));
  const out = [[]]; for (const e of els) { const n = name(e); if (n === '|') { if (out[out.length - 1].length) out.push([]); } else out[out.length - 1].push(n); }
  return out.filter(g => g.length);
}"""
# every icon button of the dock: its size and its ground (none: transparent), the one in hand aside
ICONS = """() => [...document.querySelectorAll('#dock :is(button.ic, button.hy-dkb, button.ifg, button.ifann)')].filter(b => b.getClientRects().length)
  .filter(b => !b.matches('.on, [aria-pressed=true]')).map(b => { const r = b.getBoundingClientRect(); return [b.id || b.dataset.a || b.dataset.tool || b.className,
    Math.round(r.width), Math.round(r.height), getComputedStyle(b).backgroundColor]; })"""
# the dock's width without the board's save status, whose words change with every save («saving…», «✓ 21:04»)
WIDTH = """() => { const s = document.getElementById('status'), w = s && s.getClientRects().length ? s.getBoundingClientRect().width : 0;
  return Math.round((document.getElementById('dock').getBoundingClientRect().width - w) * 10) / 10; }"""
PLATE = "() => { const p = document.getElementById('hydkstep'); return p && p.classList.contains('on') ? p.textContent : ''; }"
BOARD = [["bplus"], ["bann"], ["bundo", "bredo"], ["bfit", "status"], ["switch"]]
IMAGE = [["tool"] * 6 + ["ann"], ["colors"], ["undo", "redo"], ["ifZoom"], ["acts"], ["switch"]]
D3 = [["plus"], ["select", "translate", "rotate", "scale", "smart", "ann"], ["undo", "redo", "reset"], ["bfit"], ["shot", "acts"], ["switch"]]
DEV = [["pick", "comment"], ["undo", "redo"], ["bfit"], ["acts"], ["switch"]]


def icons_ok(page, where):
    bad = [x for x in page.evaluate(ICONS) if x[1:3] != [36, 34] or x[3] != "rgba(0, 0, 0, 0)"]
    assert not bad, (where, bad)


def hover_plate(page, sel):
    """the plate over a dock button once the pointer rests on it"""
    page.mouse.move(5, 5); b = page.locator(sel).bounding_box(); page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    page.wait_for_function(f"() => ({PLATE})()", timeout=4000)
    return page.evaluate(PLATE)


def plate_after(page, w0, word):
    """after ⌘Z (or the dock's Undo) the step's name shows over Undo and the dock keeps its width; it goes after about 2 s"""
    page.wait_for_function(f"() => ({PLATE})().startsWith('{word}')", timeout=4000)
    text = page.evaluate(PLATE); assert page.evaluate(WIDTH) == w0, "the plate widened the dock"
    page.wait_for_function(f"() => !({PLATE})()", timeout=5000)
    return text


def test_one_dock_for_the_board_and_the_studios(tmp_path):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        br = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page, errors = board(br, port)
        assert page.evaluate(GROUPS) == BOARD; icons_ok(page, "board")
        st = Image(page).open(); page.wait_for_timeout(600)
        assert page.evaluate(GROUPS) == IMAGE; icons_ok(page, "image"); st.close()
        st = Studio3D(page, lib).open()
        assert page.evaluate(GROUPS) == D3; icons_ok(page, "3d"); st.close()
        st = Dev(page, lib).open()
        assert page.evaluate(GROUPS) == DEV; icons_ok(page, "dev"); st.close()
        assert page.evaluate(GROUPS) == BOARD
        assert not errors, errors
        br.close()


def test_plus_lists_what_the_board_makes_and_text_makes_a_text(tmp_path):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        br = p.chromium.launch(); page, errors = board(br, port)
        assert page.evaluate("() => !document.querySelector('#dock #bnote, #dock #btl')"), "the old create buttons are still in the dock"
        page.locator("#bplus").click()
        page.wait_for_selector("#bplusm.open")
        rows = page.evaluate("() => [...document.querySelectorAll('#bplusm [role=menuitem]')].map(b => [b.dataset.mk, b.querySelector('.ml').textContent])")
        assert [r[1] for r in rows] == ["Sticky note", "Text", "Timeline", "3D scene"], rows
        # the timeline wears the icon of a line with its phases (ui/icons.js layoutTimeline), not the dots on a line it had
        assert page.evaluate("() => document.querySelector('#bplusm [data-mk=timeline] svg').innerHTML === document.createRange()"
                             ".createContextualFragment(hyIcon('layoutTimeline', 16, 1.85)).firstElementChild.innerHTML")
        # the list stands over the dock, the dock keeps its width
        assert page.evaluate("() => document.getElementById('bplusm').getBoundingClientRect().bottom <= document.getElementById('dock').getBoundingClientRect().top")
        n0 = page.evaluate("() => Object.values(board.items).filter(i => i.type === 'text').length")
        page.locator("#bplusm [data-mk=text]").click()
        page.wait_for_selector(".tx textarea, .tx [contenteditable=true], .tx.editing", timeout=4000)
        page.keyboard.type("Brief"); page.keyboard.press("Escape")   # words on the canvas: Esc keeps them
        page.wait_for_function(f"() => Object.values(board.items).filter(i => i.type === 'text').length === {n0 + 1}", timeout=4000)
        assert page.evaluate("() => Object.values(board.items).some(i => i.type === 'text' && i.text === 'Brief')")
        assert not page.evaluate("() => document.getElementById('bplusm').classList.contains('open')")
        # Esc closes an open list and nothing else
        page.locator("#bplus").click(); page.wait_for_selector("#bplusm.open"); page.keyboard.press("Escape")
        page.wait_for_function("() => !document.getElementById('bplusm').classList.contains('open')")
        assert not errors, errors
        br.close()


def test_g_does_not_group_on_the_board_meta_g_does(tmp_path):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        br = p.chromium.launch(); page, errors = board(br, port)
        page.evaluate("() => { sel = new Set(['a1', 'e1']); render(); }"); blur(page)
        page.keyboard.press("g"); page.wait_for_timeout(400)
        assert page.evaluate("() => Object.keys(board.groups).length") == 0, "G grouped"
        page.keyboard.press("Shift+g"); page.wait_for_timeout(200)
        assert page.evaluate("() => Object.keys(board.groups).length") == 0
        page.keyboard.press("Meta+g"); page.wait_for_function("() => Object.keys(board.groups).length === 1", timeout=4000)
        # the «?» panel: ⌘G and ⇧⌘G, no plain G
        have = {k for r in page.evaluate(COMBOS) for k in r["keys"]}
        assert {"⌘G", "⇧⌘G"} <= have and not {"G", "⇧G"} & have, sorted(have)
        br.close()


def test_actions_open_with_meta_k_in_3d_and_dev(tmp_path):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        br = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page, errors = board(br, port)
        st = Studio3D(page, lib).open(); blur(page)
        page.keyboard.press("Meta+k"); page.wait_for_selector(".hy-pal.on", timeout=4000)
        labels = page.evaluate("() => [...document.querySelectorAll('.hy-pal.on .pi')].map(b => b.querySelector('.pl > span').firstChild.textContent)")
        assert {"Snapshot", "Move", "Cube", "Save"} <= set(labels), labels
        page.keyboard.type("move"); page.keyboard.press("Enter")
        page.wait_for_function("() => !document.querySelector('.hy-pal.on')")
        assert page.evaluate("() => import('/plugins/3d/engine.js').then(m => m.liveInfo().tool)") == "translate"
        # the dock's Actions opens the same list, Esc closes it and the Studio stays
        page.locator("#dock .dkacts").click(); page.wait_for_selector(".hy-pal.on"); page.keyboard.press("Escape")
        page.wait_for_function("() => !document.querySelector('.hy-pal.on')"); assert st.is_open()
        st.close()
        st = Dev(page, lib).open(); blur(page)
        page.keyboard.press("Meta+k"); page.wait_for_selector(".hy-pal.on", timeout=4000)
        labels = page.evaluate("() => [...document.querySelectorAll('.hy-pal.on .pi')].map(b => b.querySelector('.pl > span').firstChild.textContent)")
        assert {"Select", "Annotation", "Edit HTML", "Done"} <= set(labels), labels
        was = page.evaluate("() => __dev.D.edit")
        page.keyboard.type("edit html"); page.keyboard.press("Enter")
        page.wait_for_function(f"() => __dev.D.edit === {str(not was).lower()}", timeout=4000)
        # ⌘K with the keyboard in the page itself (its own frame, agent.js hands the key over)
        page.evaluate("() => __dev.D.frame.focus()"); page.wait_for_timeout(200)
        page.keyboard.press("Meta+k"); page.wait_for_selector(".hy-pal.on", timeout=4000); page.keyboard.press("Escape")
        page.wait_for_function("() => !document.querySelector('.hy-pal.on')")
        st.close()
        assert not errors, errors
        br.close()


def test_the_step_name_over_undo_never_widens_a_dock(tmp_path):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        br = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page, errors = board(br, port)
        # the board: a card moved by the mouse is the step «Move»
        b = page.locator(".it[data-id=a1], .plg[data-id=a1]").first.bounding_box(); x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + 60, y + 30, steps=6); page.mouse.up()
        w0 = page.evaluate(WIDTH)
        assert hover_plate(page, "#bundo") == "Undo ·Move⌘Z", page.evaluate(PLATE)
        assert page.evaluate(WIDTH) == w0
        assert page.evaluate("() => !document.getElementById('bundo').title")   # no second, native tooltip
        page.mouse.move(5, 5); blur(page); page.keyboard.press("Meta+z")
        assert plate_after(page, w0, "Undo") == "Undo ·Move"
        assert hover_plate(page, "#bredo") == "Redo ·Move⇧⌘Z"
        page.mouse.move(5, 5)
        # Image Studio: a step of the studio, Undo in the dock
        st = Image(page).open(); st.change("x"); page.wait_for_timeout(300); w0 = page.evaluate(WIDTH)
        assert hover_plate(page, "#dock [data-a=undo]").startswith("Undo ·Opacity Change"), page.evaluate(PLATE)
        page.locator("#dock [data-a=undo]").click(); page.mouse.move(5, 5)
        assert plate_after(page, w0, "Undo") == "Undo ·Opacity Change"
        st.close()
        # 3D Studio: a renamed object, ⌘Z
        st = Studio3D(page, lib).open(); st.change("Crate"); page.wait_for_timeout(600); w0 = page.evaluate(WIDTH)
        text = hover_plate(page, "#dock [data-a=undo]"); assert text.startswith("Undo ·") and "Crate" in text, text
        page.mouse.move(5, 5); blur(page); page.keyboard.press("Meta+z")
        assert "Crate" in plate_after(page, w0, "Undo")
        st.close()
        # Dev Studio: a text typed in the tree, ⌘Z
        st = Dev(page, lib).open(); st.change("Hi there"); w0 = page.evaluate(WIDTH)
        text = hover_plate(page, "#dock [data-a=undo]"); assert text.startswith("Undo ·") and len(text) > len("Undo ·⌘Z"), text
        page.mouse.move(5, 5); blur(page); page.keyboard.press("Meta+z")
        assert len(plate_after(page, w0, "Undo")) > len("Undo ·")
        st.close()
        assert not errors, errors
        br.close()
