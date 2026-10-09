"""Two rows that can each carry a background never touch (owner 2026-10-09, on the board's name menu: «Open boards», the open board's row
lit and the sleeping board's row under the pointer, the two plates one block: «опять проблема с расстоянием. Эти блоки, если я делаю hover,
у меня нулевое расстояние. Посмотри, нет ли у нас где-то еще этой проблемы: в менюшках, в наших сайдбарах. Это все нужно поправить»).

Between what two neighbouring rows paint stands --hy-gap-row (ui/tokens.css, 2 px; DESIGN.md «Меню и настройки»). Every list whose rows
light up is opened here, one row is put in its chosen, current or open state and the next is under the pointer, and the gap between the
two painted backgrounds is measured (the row's box less what its background-clip leaves out): menus and submenus, the board's name menu,
the pages, the bell, the history, the notes in Info, the library's folders and its card menu, Home's menu, sidebar, list and settings rail,
Image Studio's Layers, History and Channels, the 3D outliner, Dev Studio's element tree. A list with too few rows gets copies of its own
row. Chromium, dark (owner 2026-10-07), a temporary library with the three plugins from the sibling repositories.

  python3 -m pytest tests/test_design_rowgap.py
  HY_ROWGAP_REPORT=1 (with -s)   every list measured: its rows and the gaps between them
"""
import json, os

import pytest

from test_design_audit import (HOME, REPOS, library_closed, look, new_page, open_app, pick, reset_board,  # noqa: F401
                               world)

# the painted boxes of a list's rows, the gap between each two that follow each other in one parent and overlap across, the token
PAINT = """(sel) => {
  const vis = e => { if (!e.getClientRects().length) return false;
    for (let x = e; x && x.nodeType === 1; x = x.parentElement) { const s = getComputedStyle(x); if (s.display === 'none' || s.visibility === 'hidden') return false; }
    return true; };
  const box = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); let t = r.top, b = r.bottom;
    if (s.backgroundClip !== 'border-box') { t += parseFloat(s.borderTopWidth); b -= parseFloat(s.borderBottomWidth); }
    if (s.backgroundClip === 'content-box') { t += parseFloat(s.paddingTop); b -= parseFloat(s.paddingBottom); }
    return { t, b, l: r.left, r: r.right }; };
  const lit = el => { const m = getComputedStyle(el).backgroundColor.match(/[\\d.]+/g); return !!m && (m.length < 4 || +m[3] > 0); };
  const name = el => (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 24) || el.className;
  const rows = [...document.querySelectorAll(sel)].filter(vis), pairs = [];
  for (let i = 0; i + 1 < rows.length; i++) {
    if (rows[i].nextElementSibling !== rows[i + 1]) continue;
    const a = box(rows[i]), b = box(rows[i + 1]); if (Math.min(a.r, b.r) - Math.max(a.l, b.l) < 8) continue;
    pairs.push({ i, a: name(rows[i]), b: name(rows[i + 1]), gap: Math.round((b.t - a.b) * 10) / 10, lit: [lit(rows[i]), lit(rows[i + 1])] });
  }
  return { n: rows.length, token: parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--hy-gap-row')) || 2, pairs }; }"""
# a list with too few rows: copies of its last row after it, up to n
GROW = """([sel, n]) => { const rows = [...document.querySelectorAll(sel)]; const last = rows[rows.length - 1]; if (!last) return 0;
  for (let k = rows.length; k < n; k++) { const c = last.cloneNode(true); c.classList.remove('first', 'last', 'sel', 'on', 'cur', 'viewing', 'now');
    c.removeAttribute('aria-current'); c.removeAttribute('id'); last.after(c); }
  return document.querySelectorAll(sel).length; }"""
# the first two rows that follow each other; the first one put in its state (".sel" a class, "aria-current=true" an attribute)
MARK = """([sel, mark]) => { const vis = e => e.getClientRects().length > 0;
  const rows = [...document.querySelectorAll(sel)].filter(vis); const i = rows.findIndex((r, k) => rows[k + 1] && r.nextElementSibling === rows[k + 1]);
  if (i < 0) return -1;
  if (mark) { const r = rows[i]; if (mark[0] === '.') r.classList.add(mark.slice(1)); else { const [k, v] = mark.split('='); r.setAttribute(k, v); } }
  rows[i + 1].setAttribute('data-rowgap-next', ''); return i; }"""

FOUND = []


def rows(target, where, sel, mark=None, grow=0, lit=True):
    """one list: its first two neighbours, the first in `mark`'s state, the second under the pointer; every pair's painted gap"""
    if grow: target.evaluate(GROW, [sel, grow])
    i = target.evaluate(MARK, [sel, mark])
    assert i >= 0, f"{where}: no two rows of {sel} next to each other"
    target.locator("[data-rowgap-next]").first.hover(force=True); target.wait_for_timeout(250)
    got = target.evaluate(PAINT, sel)
    pair = next(p for p in got["pairs"] if p["i"] == i)
    if mark and lit:
        assert all(pair["lit"]), f"{where}: the chosen row and the one under the pointer must both be lit to be measured: {pair}"
    bad = [p for p in got["pairs"] if p["gap"] < got["token"] - 0.05]
    if os.environ.get("HY_ROWGAP_REPORT"): print(f"\n{where}: {got['n']} rows, gaps {sorted({p['gap'] for p in got['pairs']})}")
    FOUND.extend(f"{where} ({sel}): «{p['a']}» / «{p['b']}» {p['gap']} px apart, the rule is {got['token']} px" for p in bad)
    target.evaluate("() => document.querySelectorAll('[data-rowgap-next]').forEach(e => e.removeAttribute('data-rowgap-next'))")
    (target.page if hasattr(target, "parent_frame") else target).mouse.move(2, 2)
    return got


def done():
    found = FOUND[:]; FOUND.clear()
    assert not found, f"{len(found)} pairs of rows whose backgrounds touch:\n  " + "\n  ".join(found)


def test_board_menus_and_panels(world):
    look(world, "dark", "round"); reset_board(world)
    (world["state"] / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "A"}, {"id": "p2", "title": "B"}, {"id": "p3", "title": "C"}]}))
    try:
        board_menus_and_panels(world)
    finally:
        (world["state"] / "boards/pages.json").unlink()


def board_menus_and_panels(world):
    page, frame = open_app(world, 1600, "canvas")
    library_closed(page)
    # the board's name menu, the owner's case: the open board current, the one under it under the pointer
    boards = [{"id": "a", "name": "Atlas studio workroom", "state": "open", "ago": 0, "covers": []},
              {"id": "b", "name": "Hyimg App", "state": "sleeping", "ago": 60, "covers": []}, {"id": "c", "name": "Atlas", "state": "warm", "ago": 90, "covers": []}]
    page.evaluate("(c) => hyimgBoards(c)", boards)
    frame.click("#cProj"); frame.wait_for_selector("#ctx.open .hysw-row")
    rows(frame, "board name menu", "#ctx > button.hysw-row", "aria-current=true")
    page.keyboard.press("Escape"); frame.wait_for_timeout(200)
    # the right click: a submenu's opener stays lit while the pointer is on the item under it; then the submenu's own rows
    frame.click("#items [data-id=p4]", button="right"); frame.wait_for_selector("#ctx.open")
    rows(frame, "right-click menu", "#ctx > button", "aria-expanded=true")
    frame.locator("#ctx [data-sub=order]").hover(); frame.wait_for_selector("#ctx .hy-sub button")
    rows(frame, "right-click submenu", "#ctx .hy-sub > button")
    page.keyboard.press("Escape"); frame.wait_for_timeout(200)
    # the pages
    frame.evaluate("() => openPages()"); frame.wait_for_selector("#pages.open .row")
    rows(frame, "pages menu", "#pages .row:not(.dv)", ".drag")
    frame.evaluate("() => closePages()")
    # the bell: unread rows are tinted, one under the pointer
    frame.click("#bntf"); frame.wait_for_selector("#ntf", state="visible")
    frame.evaluate("() => { const n = document.getElementById('ntf'); n.querySelectorAll('.none').forEach(e => e.remove());"
                   " n.insertAdjacentHTML('beforeend', [1, 2, 3].map(k => hyBellRow({ id: 'n' + k, title: 'Agent ' + k, text: 'moved 2 pictures', read: k > 1 })).join('')); }")
    rows(frame, "bell", "#ntf .nt", ".new")
    frame.click("#bntf"); frame.wait_for_timeout(200)
    # the history: its events, then its versions, the one being viewed lit (a fresh board has neither: rows of the panel's own markup)
    frame.click("#bhist"); frame.wait_for_selector("#hist", state="visible"); frame.wait_for_timeout(300)
    row = "'<div class=\"' + c + ' who-owner' + (k ? '' : ' first') + (k === 2 ? ' last' : '') + '\"><span class=\"dot\"></span><div><b>Moved ' + k + '</b></div></div>'"
    fill = f"(c) => {{ const L = document.getElementById(c === 'hv' ? 'histList' : 'evList'); L.innerHTML = [0, 1, 2].map(k => {row}).join(''); }}"
    frame.evaluate(fill, "ev")
    rows(frame, "history events", "#evList .ev")
    frame.evaluate("() => document.getElementById('hist').classList.add('ver')"); frame.evaluate(fill, "hv")
    rows(frame, "history versions", "#histList .hv", ".viewing")
    timeline = frame.evaluate("() => { const r = [...document.querySelectorAll('#histList .hv')].map(e => [e.getBoundingClientRect(), getComputedStyle(e, '::before')]);"
                              " return [0, 1].map(k => { const a = r[k][0], s = r[k][1], b = r[k + 1][0], t = r[k + 1][1];"
                              " return (a.bottom - parseFloat(getComputedStyle(document.querySelectorAll('#histList .hv')[k]).borderBottomWidth) - parseFloat(s.bottom))"
                              " >= (b.top + parseFloat(getComputedStyle(document.querySelectorAll('#histList .hv')[k + 1]).borderTopWidth) + parseFloat(t.top)); }); }")
    assert timeline == [True, True], "the history's timeline runs on through the gap between two versions"
    frame.evaluate("() => document.getElementById('hist').classList.remove('ver')")
    frame.click("#bhist"); frame.wait_for_timeout(200)
    # the notes of a picture in Info
    pick(frame, ["p4"]); frame.wait_for_timeout(500)
    if frame.locator("#iNotes .inote").count():
        rows(frame, "Info notes", "#iNotes .inote", grow=3)
    assert not page.errors, page.errors
    page.close(); done()


def test_library(world):
    look(world, "dark", "round"); reset_board(world)
    page, _ = open_app(world, 1600, "panel")
    page.wait_for_selector(".frow")
    rows(page, "library folders", ".frow", ".on", grow=3)
    page.locator(".card").first.click(button="right"); page.wait_for_selector("#lctx.open")
    rows(page, "library card menu", "#lctx > button")
    assert not page.errors, page.errors
    page.close(); done()


def test_home(world):
    page = new_page(world, 1440)
    page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => {} } } }; window.HY_LANG = 'en';")
    page.goto(HOME)
    projects = [{"id": i, "name": n, "path": "/x" + i, "available": True, "updated": 1791100000 - k * 1000, "covers": []}
                for k, (i, n) in enumerate([("a", "Atlas"), ("b", "Studio North"), ("c", "Hyimg App")])]
    home = {"folders": [{"id": "f1", "name": "Studio", "projects": ["a"]}, {"id": "f2", "name": "North", "projects": []}], "favs": ["a"], "view": "list"}
    page.evaluate(f"hyimgHome({json.dumps({'projects': projects, 'settings': {'cv.theme': 'dark', 'cv.lang': 'en'}, 'home': home})})")
    page.wait_for_timeout(800)
    rows(page, "Home sidebar", "aside .nav", "aria-current=true")
    rows(page, "Home list", ".list .card", ".drop", lit=False)
    page.locator(".card").first.click(button="right"); page.wait_for_selector(".menu.open button")
    rows(page, "Home menu", ".menu.open > button")
    page.keyboard.press("Escape")
    page.locator("#bset").click(); page.wait_for_selector(".sw-nv")
    rows(page, "Settings rail", ".sw-nv", ".on")
    assert not page.errors, page.errors
    page.close(); done()


def studio(world, card, mode, ready):
    look(world, "dark", "round"); reset_board(world)
    page, frame = open_app(world, 1600, "canvas")
    library_closed(page)
    pick(frame, [card])
    frame.click(f"#modes [data-mode=\"{mode}\"]")
    frame.wait_for_function(ready, timeout=40000)
    frame.wait_for_timeout(1500)
    if frame.locator(".m3pause [data-go]").count(): frame.click(".m3pause [data-go]")
    return page, frame


def test_image_studio(world):
    if not (REPOS / "hyimg-image-studio/manifest.json").is_file(): pytest.skip("no hyimg-image-studio beside hyimg")
    page, _ = studio(world, "p2", "image", "() => window.__frames && __frames.ED && __frames.ED.win")
    ed = next(f for f in page.frames if "/editor/" in f.url)
    ed.wait_for_selector("#rows .lr")
    rows(ed, "Image Studio Layers", "#rows > .lr", ".sel", grow=3, lit=False)   # a copied row takes no pointer
    for tab, sel, mark in (("hist", "#phist .hrow", ".cur"), ("chan", "#pchan .chr", ".cur")):
        ed.evaluate(f"() => __ed.showPanel('{tab}')"); ed.wait_for_timeout(500)
        if ed.locator(sel).count(): rows(ed, f"Image Studio {tab}", sel, mark, grow=3, lit=False)
    assert not page.errors, page.errors
    page.close(); done()


def test_3d_outliner(world):
    if not (REPOS / "hyimg-3d-studio/manifest.json").is_file(): pytest.skip("no hyimg-3d-studio beside hyimg")
    page, frame = studio(world, "m1", "3d", "() => document.body.classList.contains('m3edit') && document.querySelector('.m3l .row')")
    rows(frame, "3D outliner", ".m3l .row", ".sel", grow=3)
    assert not page.errors, page.errors
    page.close(); done()


def test_dev_element_tree(world):
    if not (REPOS / "hyimg-dev-studio/manifest.json").is_file(): pytest.skip("no hyimg-dev-studio beside hyimg")
    page, frame = studio(world, "h1", "dev", "() => window.__dev && __dev.D && __dev.D.tree && document.querySelector('.dvt .row')")
    rows(frame, "Dev Studio element tree", ".dvt .row", ".sel", grow=3)
    assert not page.errors, page.errors
    page.close(); done()
