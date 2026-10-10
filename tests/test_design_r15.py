"""Round 15's Library and Tips in the real app (owner 2026-10-09, ♥ on Concepts/html/editors-concepts/r15/r15-library.html and r15-tips.html:
«accept as drawn»), measured against the drawings on the design audit's temporary library (tests/test_design_audit.py world). Chromium, dark.

The Library beside the board (ui/libpanel.css, ui/libpanel.js, v2.html):
- the board's dark side panel, as History (canvas.html #hist): 12 px from the left, under the top row, 12 px over the bottom, 18 px corners
- the header «Library 16», 52 px; the search 32 px under it, 11 px in from the panel's sides, ⌘F and one Filter button at its end
- by width (owner: «compact width folds the folders into the crumb row with a control to unfold them»): from 480 px the folders are a column;
  from 280 px a section «Folders» over the pictures, its fold button puts them into the path; under 280 px the folders are folded into
  the path, whose folder button unfolds them under it in a well; tree rows 28 px
- the Filter button as r15 draws it (closed); a click opens the app's filter window under the search, filters on show as the app showed
  them (the ink plate, the count). Only round 15 is followed (owner 2026-10-10), older rounds' filter states are not
- no Pages block in the library («Pages выбирается сверху, отдельного Pages блока не делаем»)

The ? panel, Tips (ui/keyspanel.css, ui/keyspanel.js): 340 px as History (it was up to 1000 px wide with uneven columns), the tabs Tips and
All keys in r15's 58 px header (a pill of 30 px tabs), «Here · Board» tips and «Keys here» rows: each row the action's icon, its words and its keys, one cap per key, at the right end.

  python3 -m pytest tests/test_design_r15.py
"""
import json
import re

from test_design_audit import board_doc, canvas_frame, new_page, reset_board, world  # noqa: F401

WIDTH = 1440
GEO = """(q) => { const e = document.querySelector(q); if (!e || !e.getClientRects().length) return null; const r = e.getBoundingClientRect();
  return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }"""
SKIN = """(q) => { const e = document.querySelector(q), s = getComputedStyle(e);
  return { bg: s.backgroundColor, r: s.borderTopLeftRadius, b: s.borderTopWidth + ' ' + s.borderTopStyle, blur: s.backdropFilter }; }"""


def settle(page, ms=450):
    page.wait_for_timeout(ms)


def open_lib(world, lw=320):
    world["settings"].write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark", "cv.shape": "round", "cv.lod": "0", "cv.nolib": "0"}))
    reset_board(world)
    page = new_page(world, WIDTH)
    page.goto(f"http://127.0.0.1:{world['port']}/?view=panel", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_function("() => document.body.classList.contains('cv-on') && !document.body.classList.contains('cv-only')"
                           " && !document.documentElement.classList.contains('lib-wait') && window.hyLibPanel && hyLibPanel.ready", timeout=90000)
    frame = canvas_frame(page)
    frame.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length > 0", timeout=90000)
    page.evaluate("() => { localStorage.setItem('cv.ftree', '1'); treeShown = true; DRAWER = false; }")
    width(page, lw)
    return page, frame


def width(page, w):
    page.evaluate("w => { document.documentElement.style.setProperty('--lw', w + 'px'); renderFolders(); }", w)
    settle(page)


def form(page):
    return page.evaluate("() => hyLibPanel.form()")


# ---------------------------------------------------------------- the Library
def test_library_panel_is_the_dark_side_panel(world):
    page, frame = open_lib(world, 320)
    assert page.evaluate(GEO, "main") == [12, 58, 320, 830], "the panel: 12 px from the left, under the top row, 12 px over the bottom"
    lib = page.evaluate(SKIN, "main")
    frame.click("#bhist"); settle(frame, 600)
    hist = frame.evaluate(SKIN, "#hist")
    assert lib == hist, f"the library wears History's skin: {lib} vs {hist}"
    assert lib["r"] == "18px" and "blur(24px)" in lib["blur"]
    # the header: «Library 16», 600 15 px, in the panel's first 52 px; the expand button round, 9 px from the edge
    head = page.evaluate("() => { const h = document.querySelector('header.hy-dock .lph'), r = h.getBoundingClientRect(), s = getComputedStyle(h);"
                         " return { text: h.textContent, mid: (r.top + r.bottom) / 2, font: s.fontWeight + ' ' + s.fontSize }; }")
    assert re.fullmatch(r"Library\d+", head["text"]) and head["font"] == "600 15px", head
    assert 59 + 26 - 3 <= head["mid"] <= 59 + 26 + 3, head
    x = page.evaluate(GEO, "#lwide")
    assert x[2:] == [30, 30] and 12 + 320 - (x[0] + 30) == 9 and x[1] == 59 + 11, x
    # the search: 32 px under the header, 11 px in from the panel's sides; ⌘F and the Filter button at its end
    q = page.evaluate(GEO, "#q")
    assert q == [23, 111, 298, 32], q
    assert page.evaluate("() => getComputedStyle(document.querySelector('#q')).borderTopLeftRadius") == "9px"
    assert page.get_attribute("#q", "placeholder") == f"Search {page.evaluate('() => document.querySelector(\".lph em\").textContent')} items"
    f = page.evaluate(GEO, "#lfbtn")
    plate = page.evaluate("() => { const b = document.querySelector('#lfbtn'); return b.clientHeight; }")   # the drawn plate, inside a 24 px target
    assert f[3] == 24 and plate == 22 and q[0] + q[2] - (f[0] + f[2]) <= 6 and q[1] < f[1] < q[1] + q[3] - f[3], (f, plate)
    assert page.locator(".lpk").inner_text() == "⌘F"
    # no Pages block: the library has no tab or block of pages
    assert page.evaluate("""() => [...document.querySelectorAll('header.hy-dock *, .fbar *, .fdrawer *, main > :not(section)')]
      .filter(e => e.getClientRects().length && /^\\s*Pages\\b/.test(e.textContent) && e.children.length === 0).length""") == 0
    assert not page.errors, page.errors
    page.close()


def test_library_forms_by_width(world):
    page, _ = open_lib(world, 560)
    assert form(page) == "wide" and page.evaluate("() => document.body.classList.contains('fdock')")
    # regular: «Folders» a section over the pictures, round 15's rows
    width(page, 320)
    assert form(page) == "regular"
    sec = page.evaluate(GEO, ".lfh")
    assert sec and sec[3] == 30 and sec[1] == 58 + 1 + 52 + 32 + 6, sec
    assert page.evaluate("() => /^Folders\\s*\\d+$/i.test(document.querySelector('.lfh').innerText.replace(/\\n/g, ' '))")
    rows = page.evaluate("""() => [...document.querySelectorAll('#fnav .frow')].map(r => { const b = r.getBoundingClientRect();
      return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)]; })""")
    assert len(rows) >= 3 and all(r[3] == 28 and r[0] == 19 and r[2] == 306 for r in rows), rows
    assert [b[1] - a[1] for a, b in zip(rows, rows[1:])] == [28] * (len(rows) - 1)
    lab, grid = page.evaluate(GEO, ".fbar"), page.evaluate("() => Math.round(document.querySelector('#list .card').getBoundingClientRect().top)")
    assert lab[3] == 30 and lab[1] >= rows[-1][1] + 28 and grid >= lab[1] + lab[3], (lab, grid)
    on = page.evaluate("() => getComputedStyle(document.querySelector('#fnav .frow.on')).backgroundColor")
    assert on.startswith("color(srgb 0.23") or "59, 130, 246" in on, f"the chosen folder in the selection's blue: {on}"
    # the threshold: 280 px keeps the section, 279 folds the folders into the path
    width(page, 280); assert form(page) == "regular"
    width(page, 279); assert form(page) == "compact"
    # compact: the path with its folder button, no tree until it is pressed
    width(page, 248)
    bar, btn = page.evaluate(GEO, ".fbar"), page.evaluate(GEO, ".fbar .fticon")
    assert bar[3] == 34 and bar[0] == 19 and bar[2] == 234 and bar[1] == 58 + 1 + 52 + 32 + 6, bar
    assert btn and btn[3] == 26 and btn[0] == 21, btn
    assert page.evaluate(GEO, "#fdrawer") is None
    first = page.evaluate("() => Math.round(document.querySelector('#list .card').getBoundingClientRect().top)")
    page.click(".fbar .fticon"); settle(page)
    tree, after = page.evaluate(GEO, "#fdrawer"), page.evaluate("() => Math.round(document.querySelector('#list .card').getBoundingClientRect().top)")
    assert tree and tree[0] == 19 and tree[2] == 234 and tree[1] >= bar[1] + bar[3], tree
    assert after >= tree[1] + tree[3] and after > first, "the unfolded tree pushes the pictures down, under it"
    well, panel = page.evaluate("() => [getComputedStyle(document.querySelector('#fdrawer')).backgroundColor, getComputedStyle(document.querySelector('header.hy-dock')).backgroundColor]")
    assert well != panel, "the unfolded tree lies in a well"
    assert page.get_attribute(".fbar .fticon", "aria-pressed") == "true"
    page.click(".fbar .fticon"); settle(page)
    assert page.evaluate(GEO, "#fdrawer") is None
    assert not page.errors, page.errors
    page.close()


def test_library_fold_into_the_path(world):
    page, _ = open_lib(world, 320)
    page.click(".lfh [data-lpfold]"); settle(page)
    assert form(page) == "folded" and page.evaluate(GEO, ".fbar .fticon") and page.evaluate(GEO, "#fdrawer") is None
    page.click(".fbar .fticon"); settle(page)
    assert form(page) == "regular" and page.evaluate(GEO, ".lfh")
    assert not page.errors, page.errors
    page.close()


def test_library_filter_states(world):
    page, _ = open_lib(world, 320)
    st = lambda: page.evaluate("() => { const b = document.querySelector('#lfbtn'), g = b.querySelector('hy-badge'); return { act: b.classList.contains('act'),"
                               " open: b.classList.contains('open'), n: g.getAttribute('count'), badge: getComputedStyle(g).display, bg: getComputedStyle(b).backgroundColor,"
                               " ink: getComputedStyle(document.body).getPropertyValue('--ink').trim(), all: !document.querySelector('#tfPanel').hidden }; }")
    s = st(); assert not s["act"] and not s["open"] and s["badge"] == "none" and not s["all"] and s["bg"] == "rgba(0, 0, 0, 0)", s
    assert page.locator("#lfbtn").inner_text().strip() == "Filter"
    # a click opens the app's filter window, under the search, inside the panel's width
    q = page.evaluate(GEO, "#q")
    page.click("#lfbtn"); settle(page, 600)
    s = st(); assert s["open"] and s["all"], s
    tf = page.evaluate(GEO, "#tfPanel")
    assert tf[1] >= q[1] + q[3] and tf[0] >= 12 and tf[0] + tf[2] <= 12 + 320, (tf, q)
    # one on: the count, the app's ink plate; the window closes on its button
    page.click('#tfGroups .fchip[data-id="none"] .fl'); settle(page, 300)
    page.click("#lfbtn"); settle(page)
    s = st(); assert s["act"] and not s["all"] and s["n"] == "1" and s["badge"] != "none" and s["bg"] != "rgba(0, 0, 0, 0)", s
    # the window's own Reset clears it
    page.click("#lfbtn"); settle(page, 600); page.click("#tfClear"); settle(page, 300)
    s = st(); assert not s["act"] and s["n"] == "0", s
    assert not page.errors, page.errors
    page.close()


def test_library_keeps_its_work(world):
    """the library's own functions in the new panel: ⌘F finds, a card picks, a folder and a card drag to the board"""
    page, _ = open_lib(world, 320)
    page.evaluate("() => document.activeElement && document.activeElement.blur()")
    page.keyboard.press("Meta+f"); settle(page, 200)
    assert page.evaluate("() => document.activeElement && document.activeElement.id") == "q"
    page.keyboard.type("liked"); settle(page, 500)
    assert page.locator("#list .card").count() >= 1
    page.fill("#q", ""); page.dispatch_event("#q", "input"); settle(page, 400)
    page.hover("#list .card >> nth=0"); page.click("#list .card >> nth=0 >> .pick"); settle(page, 300)
    assert page.locator("#pickinfo").is_visible()
    assert page.evaluate("() => document.querySelector('#fnav .frow[data-f=\"a\"]').draggable") is True
    assert page.evaluate("() => document.querySelector('#list .card').getAttribute('draggable')") == "true"
    assert not page.errors, page.errors
    page.close()


# ---------------------------------------------------------------- Tips
def open_tips(world):
    world["settings"].write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark", "cv.shape": "round", "cv.lod": "0", "cv.nolib": "0"}))
    reset_board(world)
    page = new_page(world, WIDTH)
    page.goto(f"http://127.0.0.1:{world['port']}/?view=canvas", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_function("() => document.body.classList.contains('cv-on') && !document.documentElement.classList.contains('lib-wait')", timeout=90000)
    frame = canvas_frame(page)
    frame.wait_for_function("() => typeof BOARD !== 'undefined' && window.hyKeysPanel && hyKeysPanel.parts", timeout=90000)
    settle(page, 1500)
    frame.click("#bkeys"); settle(frame, 600)
    return page, frame


ROWS = """(sel) => [...document.querySelectorAll(sel)].filter(r => r.getClientRects().length).map(r => { const b = r.getBoundingClientRect(), i = r.querySelector('.kpi'), k = r.querySelector('.k');
  return { h: Math.round(b.height), top: Math.round(b.top), ix: i ? Math.round(i.getBoundingClientRect().left) : null, svg: !!(i && i.querySelector('svg')) || !!(k && k.querySelector('svg')),
    caps: [...r.querySelectorAll('hy-kbd, kbd')].map(x => x.textContent.trim()), right: k ? Math.round(k.getBoundingClientRect().right) : null,
    words: (r.querySelector('.t') || r).textContent.trim() }; })"""


def test_tips_panel_as_drawn(world):
    page, frame = open_tips(world)
    # the button wears the bulb of the tips, as the board's other round buttons wear their icons (owner 2026-10-10: «у нас была иконка
    # лайтболб, нужно ее заменить тут», the «?» it had)
    btn = frame.evaluate("""() => { const b = document.querySelector('#bkeys'), s = b.querySelector('svg');
      return { text: b.textContent.trim(), ic: s && s.dataset.ic, paths: s ? s.querySelectorAll('path').length : 0,
        w: s ? Math.round(s.getBoundingClientRect().width) : 0, bell: Math.round(document.querySelector('#bntf svg').getBoundingClientRect().width) }; }""")
    assert btn["text"] == "" and btn["ic"] == "tip" and btn["paths"] >= 3 and btn["w"] == btn["bell"], btn
    assert frame.evaluate(GEO, "#keys") == [1088, 58, 340, 830], "History's place and size (it was up to 1000 px wide)"
    assert frame.evaluate(SKIN, "#keys") == frame.evaluate("() => { const h = document.querySelector('#hist'); h.classList.add('open');"
                                                          " const s = getComputedStyle(h), o = { bg: s.backgroundColor, r: s.borderTopLeftRadius,"
                                                          " b: s.borderTopWidth + ' ' + s.borderTopStyle, blur: s.backdropFilter }; h.classList.remove('open'); return o; }")
    assert frame.evaluate(GEO, "#keys .kp-bh") == [1089, 59, 338, 58], "r15's 58 px header"
    tabs = frame.evaluate("""() => [...document.querySelectorAll('#keys .kp-tab')].map(t => [t.textContent.trim(), t.getAttribute('aria-selected'),
      Math.round(t.getBoundingClientRect().height), getComputedStyle(t).fontSize, !!t.querySelector('svg')])""")
    assert tabs[0][0] == "Tips" and tabs[1][0].startswith("All keys") and tabs[0][1] == "true", tabs
    assert all(t[2] == 30 and t[3] == "13.5px" and not t[4] for t in tabs), tabs
    assert frame.evaluate(GEO, "#keys .kp-x")[2:] == [30, 30]
    s = frame.evaluate(GEO, "#keys .kp-s input")
    assert s == [1099, 117, 318, 32], s
    labels = frame.evaluate("() => [...document.querySelectorAll('#keys .kp-body > section:not([hidden]) .kp-lb')].map(l => l.innerText.replace(/\\s+/g, ' ').trim())")
    assert re.match(r"(?i)here · board 5", labels[0]) and re.match(r"(?i)keys here 9 All \d+", labels[1]), labels
    lb, tip = frame.evaluate(GEO, "#keys .kp-lb"), frame.evaluate(GEO, "#keys .kp-tip")
    assert lb[1] == 155 and lb[3] == 30 and tip[0] == 1099 and tip[2] == 318, (lb, tip)
    # the tips: each its icon and its keys or main words
    tips = frame.evaluate(ROWS, "#keys .kp-tip")
    assert len(tips) == 5 and all(t["svg"] for t in tips) and all(t["caps"] or "Double click" in t["words"] or "Drag a folder" in t["words"] for t in tips), tips
    assert tips[3]["caps"] == ["⌥", "A"], "one cap per key"
    # the keys here: 32 px rows, the icon in one column, the caps one per key at the right end
    keys = frame.evaluate(ROWS, "#keys .kp-main .kp-row")
    assert len(keys) == 9 and all(k["h"] == 32 for k in keys), keys
    assert [b["top"] - a["top"] for a, b in zip(keys, keys[1:])] == [32] * 8
    assert all(k["svg"] for k in keys) and len({k["ix"] for k in keys}) == 1 and keys[0]["ix"] == 1088 + 11 + 6, keys
    assert {k["words"]: k["caps"] for k in keys}["Redo"] == ["⇧", "⌘", "Z"] and {k["words"]: k["caps"] for k in keys}["Library"] == ["⌘", "M"]
    assert len({k["right"] for k in keys}) == 1 and 1088 + 340 - keys[0]["right"] <= 20, keys
    assert not page.errors, page.errors
    page.close()


def test_tips_all_keys_and_search(world):
    page, frame = open_tips(world)
    frame.click("#keys .kp-tab[data-kt=all]"); settle(frame, 300)
    rows = frame.evaluate(ROWS, "#keys .kp-all .kp-row")
    assert len(rows) >= 45 and all(r["svg"] for r in rows), [r["words"] for r in rows if not r["svg"]]
    assert len({r["ix"] for r in rows}) == 1, "the icons stand in one column"
    caps = [r for r in rows if r["caps"]]
    wide = [c for r in caps for c in r["caps"] if len(c) > 1 and c not in ("Space", "Esc", "1.")]   # a key's name, «1.» typed at a line's start
    assert not wide, f"one cap per key: {wide}"
    n = frame.evaluate("() => document.querySelector('#keys .kp-tab[data-kt=all] em').textContent")
    assert int(n) == len(rows)
    frame.fill("#keys .kp-s input", "group"); settle(frame, 200)
    hits = frame.evaluate(ROWS, "#keys .kp-all .kp-row")
    assert hits
    assert frame.evaluate("() => [...document.querySelectorAll('#keys .kp-all .kp-row')].filter(r => !r.hidden).every(r => r.textContent.toLowerCase().includes('group'))")
    assert len(hits) < len(rows)
    frame.click("#keys .kp-x"); settle(frame, 300)
    assert frame.evaluate("() => document.getElementById('keys').style.display") == "none"
    assert not page.errors, page.errors
    page.close()
