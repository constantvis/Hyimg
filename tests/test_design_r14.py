"""Round 14's settled decisions in the real app (owner 2026-10-09 on Concepts/html/editors-concepts/r14, «большинство уже можно
реализовать»), on the design audit's temporary library with the three plugins (tests/test_design_audit.py world). Chromium, dark.

- Block tabs at the standard size everywhere: 24 px, words 12.5 / 500 (ui/hy/block.css .hy-bh-tab); no bigger tab on any panel
  (note ntfghcp4 on round 13: «я бы все равно склонялся к стандартному размеру оставить»). The annotations list's Open | Resolved were
  28 px on a blue tint.
- No line where a block's header meets its content (the same note: «Разделительную линию нужно точно убирать сверху»); the hairlines
  between sections stay. Settings at the side had one under its header.
- In a Studio the top row's right end is the Studio's own: the board's round buttons (bell, ?, history, settings) and Image Studio's gear
  are away, the session actions stand at the row's gutter (owner on r14 final-3d: «В режиме студии мы вот эти все элементы убираем»).
- The ? panel: a row of an action shows that action's icon before its key caps, as the menus do (owner on r14 final-tips: «Почему здесь у
  нас нет иконок этих кнопок?»).

  python3 -m pytest tests/test_design_r14.py
"""
import json

import pytest

from test_design_audit import REPOS, board_doc, canvas_frame, library_closed, new_page, pick, reset_board, world  # noqa: F401

WIDTH = 1440
# every visible tab of a block header or a panel's tab row: [where, height, font size, weight]
TABS = r"""() => { const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0; };
  return [...document.querySelectorAll('.hy-bh .hy-bh-tab, .hy-bh hy-segmented[variant=tabs] > button, .cm-tabs > button, [role=tablist] > [role=tab]')]
    .filter(vis).map(t => { const s = getComputedStyle(t);
      return [(t.closest('[id]') || t).id + ' ' + t.textContent.trim().slice(0, 20), Math.round(t.getBoundingClientRect().height), s.fontSize, s.fontWeight,
        !!t.closest('hy-segmented[variant=pill]')]; }); }"""
# a line where a block's header meets its content: the header's own bottom border or inset shadow, or a border of anything in its block
# within 10 px under it that runs across most of the header (the tabs' own plates are not lines)
RULES = r"""() => { const out = [], vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0; };
  const line = (w, st) => parseFloat(w) > 0 && st !== 'none' && st !== 'hidden';
  for (const h of [...document.querySelectorAll('.hy-bh, #sets.sw-side .sw-hd')].filter(vis)) {
    const hb = h.getBoundingClientRect(), hs = getComputedStyle(h), who = (h.closest('[id]') || h).id + ' .' + h.className.toString().split(' ')[0];
    if (line(hs.borderBottomWidth, hs.borderBottomStyle)) out.push(who + ': its bottom border');
    if (/inset[^,]*-1px|0px -1px 0px[^,]*inset/.test(hs.boxShadow)) out.push(who + ': an inset line at its bottom');
    const blk = h.parentElement;
    for (const e of blk.querySelectorAll('*')) { if (h.contains(e) || !vis(e)) continue;
      const r = e.getBoundingClientRect(), s = getComputedStyle(e), across = Math.min(r.right, hb.right) - Math.max(r.left, hb.left) > hb.width * .5;
      if (!across) continue;
      if (line(s.borderTopWidth, s.borderTopStyle) && r.top >= hb.bottom - 1 && r.top <= hb.bottom + 10) out.push(who + ': the top border of ' + e.tagName + '.' + e.className);
      if (line(s.borderBottomWidth, s.borderBottomStyle) && Math.abs(r.bottom - hb.bottom) <= 1) out.push(who + ': the bottom border of ' + e.tagName + '.' + e.className); } }
  return out; }"""
ROUND = """() => ['#bntf', '#bkeys', '#bhist', '#bset'].filter(q => { const e = document.querySelector(q);
  return e && e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden'; })"""
ACTS = "(q) => { const a = document.querySelector(q), r = a.getBoundingClientRect(); return [Math.round(r.top), Math.round(innerWidth - r.right)]; }"
STUDIOS = [("image", "p2", "() => window.__frames && __frames.ED && __frames.ED.win", "hyimg-image-studio"),
           ("3d", "m1", "() => document.body.classList.contains('m3edit') && document.querySelector('.m3title')", "hyimg-3d-studio"),
           ("dev", "h1", "() => window.__dev && __dev.D && __dev.D.tree", "hyimg-dev-studio")]


def open_canvas(world):
    world["settings"].write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark", "cv.shape": "round", "cv.lod": "0", "cv.nolib": "0"}))
    reset_board(world)
    page = new_page(world, WIDTH)
    page.goto(f"http://127.0.0.1:{world['port']}/?view=canvas", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_function("() => document.body.classList.contains('cv-on') && !document.documentElement.classList.contains('lib-wait')", timeout=90000)
    frame = canvas_frame(page)
    frame.wait_for_function(f"() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === {len(board_doc()['items'])}"
                            " && typeof PLGST !== 'undefined' && PLGST.length >= 1 && PLGST.every(p => p.ok !== undefined)", timeout=90000)
    page.wait_for_timeout(1800)
    library_closed(page)
    return page, frame


def studio(world, key):
    _, card, ready, repo = next(s for s in STUDIOS if s[0] == key)
    if not (REPOS / repo / "manifest.json").is_file(): pytest.skip(f"no {repo} beside hyimg")
    page, frame = open_canvas(world)
    pick(frame, [card])
    frame.click(f"#modes [data-mode=\"{key}\"]")
    frame.wait_for_function(ready, timeout=90000)
    frame.wait_for_timeout(1800)
    if frame.locator(".m3pause [data-go]").count(): frame.click(".m3pause [data-go]"); frame.wait_for_timeout(600)
    editor = next((f for f in page.frames if "/editor/" in f.url), None)
    return page, frame, editor


def board_panel(world, which):
    page, frame = open_canvas(world)
    if which == "annotations": frame.evaluate("() => hyComments.list()")
    else: frame.click({"history": "#bhist", "notifications": "#bntf", "settings": "#bset"}[which])
    frame.wait_for_timeout(900)
    return page, frame


def check_blocks(target, name):
    tabs, rules = target.evaluate(TABS), target.evaluate(RULES)
    # the bell's All | Notifications | Comments are the «?» panel's pill of 30 px tabs, 13.5 / 500 (owner 2026-10-10 on round 18, question 9:
    # «Почему ты не можешь сделать нотификации точно так же, как здесь?»); every other tab stays at the standard size
    wrong = [t for t in tabs if t[1:4] != ([30, "13.5px", "500"] if t[4] else [24, "12.5px", "500"])]
    assert tabs and not wrong, f"{name}: tabs not at the standard 24 px, 12.5 / 500: {wrong} (all: {tabs})"
    assert not rules, f"{name}: a line where a block's header meets its content: {rules}"


@pytest.mark.parametrize("which", ["history", "notifications", "annotations", "settings"])
def test_board_panels(world, which):
    page, frame = board_panel(world, which)
    if which == "settings":   # its header has no tabs: only the line is checked, and the search still comes right under it
        assert frame.evaluate(RULES) == [], frame.evaluate(RULES)
        assert frame.evaluate("() => document.querySelector('#sets').classList.contains('sw-side')")
    else:
        check_blocks(frame, which)
    assert not page.errors, page.errors
    page.close()


@pytest.mark.parametrize("key", [s[0] for s in STUDIOS])
def test_studio_blocks(world, key):
    page, frame, editor = studio(world, key)
    check_blocks(editor or frame, key)
    assert not page.errors, page.errors
    page.close()


@pytest.mark.parametrize("key", [s[0] for s in STUDIOS])
def test_studio_top_row_is_its_own(world, key):
    page, frame, editor = studio(world, key)
    assert frame.evaluate(ROUND) == [], f"{key}: the board's round buttons show in the Studio: {frame.evaluate(ROUND)}"
    assert frame.evaluate("() => document.documentElement.hasAttribute('data-in-studio')")
    if editor:   # Image Studio's page: its own gear is away too, its Cancel and Save at the gutter
        assert editor.evaluate(ROUND) == [], "Image Studio's gear shows"
        frame.wait_for_timeout(500); assert editor.evaluate(ACTS, "#topr") == [12, 12]
    else:
        frame.wait_for_timeout(500); assert frame.evaluate(ACTS, "hy-studio-actions") == [12, 12]
    # back on the board, the round buttons are there again
    frame.click("#modes [data-mode=board]")
    frame.wait_for_function("() => !document.documentElement.hasAttribute('data-in-studio')", timeout=20000)
    frame.wait_for_function("() => ['#bntf', '#bkeys', '#bhist', '#bset'].every(q => document.querySelector(q).getClientRects().length)", timeout=20000)
    assert not page.errors, page.errors
    page.close()


def test_keys_panel_icons(world):
    """round 14's icons in the ? panel, now its All keys tab (round 15's Tips, tests/test_design_r15.py): every row its action's icon"""
    page, frame = open_canvas(world)
    frame.click("#bkeys"); frame.wait_for_timeout(600)
    frame.click("#keys .kp-tab[data-kt=all]"); frame.wait_for_timeout(300)
    rows = frame.evaluate("""() => [...document.querySelectorAll('#keys .kp-all > .kp-row')].map(r => {
      const i = r.querySelector(':scope > .kpi'), keys = [...r.querySelectorAll('.k kbd')].map(k => k.textContent.trim()).join('');
      const app = n => Object.assign(document.createElement('i'), { innerHTML: HY_IC[n] }).innerHTML;   // the menus' icon, as the page parses it
      return { keys, icon: i ? i.dataset.icon || '' : null, svg: i ? i.innerHTML : '', want: i && i.dataset.icon ? app(i.dataset.icon) : '',
               x: i ? Math.round(i.getBoundingClientRect().left) : null, first: r.firstElementChild === i, own: !!r.querySelector('.k svg') }; })""")
    assert rows and all(r["icon"] is not None and r["first"] for r in rows), [r for r in rows if r["icon"] is None or not r["first"]]
    assert len({r["x"] for r in rows}) == 1, "the icons do not stand in one column"
    got = {r["keys"]: r["icon"] for r in rows}
    for keys, icon in {"N": "note", "C": "comment", "⌘GG": "group", "⇧⌘G⇧G": "ungroup", "⌘Z⇧⌘Z": "undo", "⇧1": "fit", "⇧C": "crop", "⌘M": "library",
                       "⌘D": "duplicate", "⌥A": "tidyBlock"}.items():
        assert got.get(keys) == icon, (keys, got.get(keys))
    assert all(r["svg"] == r["want"] and "<svg" in r["svg"] for r in rows if r["icon"]), "an icon is not the app's (HY_IC)"
    assert all(r["icon"] or r["own"] for r in rows), "a row without its icon"   # round 15: a gesture's row has one too (a drag: the library)
    assert frame.evaluate("() => document.querySelectorAll('#keys kbd').length") > 40   # the keys stay the app's key caps
    assert not page.errors, page.errors
    page.close()
