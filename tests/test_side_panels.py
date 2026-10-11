"""The side panels, one anatomy (owner 2026-10-11, round 20's configurator Concepts/html/editors-concepts/r20/panels-config.html, his choice:
«Ширина 340 · Угол 18 · Фон стекло 97 % · Высота по содержимому · Шапка 52, вкладки в шапке · Вкладки капсула 30 · без крестика (как
Библиотека, Esc) · Кнопки шапки квадрат 24 · Поиск поле 32 · Выбранное и новое синяя заливка и рамка (как дерево и версии) · Подвал сноска
у всех · Пустой список по центру 14»; DESIGN.md «Боковая панель»). Chromium, a temporary board, dark and light.

One table over every side panel: the bell, «?», History, Settings at the side, the annotations' list, Info, the Library beside the board
and Home's bell. Each is measured as a person sees it: its box (340 wide, 18 corners, glass 97 % of the panel colour, under the top row,
12 px from the right), its header (52 px, the tabs a pill of 30 px tabs, its buttons square 24), no × anywhere in it, the search 32, the
footnote at its foot, an empty list in the middle at 14 px, the chosen and the new row the selection's fill and line, Esc closes it (Settings
too while the board has the keyboard), the top row's button opens and closes it. Info keeps its file header and no close (it goes with the
selection), its footnote says what ↵ does with the card; the Library keeps its own width and its height to the bottom (DESIGN.md says why).

  nice -n 10 python3 -m pytest -q tests/test_side_panels.py      (HY_SHOTS=<folder> keeps a picture of each panel)
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_canvas_pages import free_port  # noqa: E402
from test_pdf import png  # noqa: E402

HOME = (ROOT / "review/home.html").as_uri()
W, H = 1440, 900
# a panel as seen: its box, corner, ground, header, the tabs in it, its buttons, any ×, its search, its footnote
LOOK = """([q, head]) => {
  const e = document.querySelector(q); if (!e || !e.getClientRects().length) return null;
  const r = e.getBoundingClientRect(), s = getComputedStyle(e), vis = x => x && x.getClientRects().length && getComputedStyle(x).visibility !== 'hidden';
  const probe = v => { const d = document.createElement('div'); d.style.cssText = 'position:fixed;left:-99px;top:0;width:9px;height:9px;' + v; document.body.append(d);
    const c = getComputedStyle(d), o = [c.backgroundColor, c.boxShadow]; d.remove(); return o; };
  const hd = head ? document.querySelector(head) : null, hr = hd && hd.getBoundingClientRect();
  const seg = hd && hd.querySelector('hy-segmented');
  const btns = hd ? [...hd.querySelectorAll('hy-icon-button, #lwide, #lviewBtn')].filter(vis).map(b => { const x = b.getBoundingClientRect();
    return [Math.round(x.width), Math.round(x.height), getComputedStyle(b).borderTopLeftRadius]; }) : [];
  const shut = [...e.querySelectorAll('button, hy-icon-button, [role=button]')].filter(vis).filter(b => {
    const w = (b.getAttribute('aria-label') || b.getAttribute('label') || b.title || '') + ' ' + (b.getAttribute('icon') || '') + ' ' + (b.dataset.swAct || '');
    return /^close\\b|\\bclose$|×/i.test(w.trim()) || /\\bclose\\b/.test(b.getAttribute('icon') || '') || b.dataset.swAct === 'close'; }).length;
  const qs = [...e.querySelectorAll('input[type=search]')].filter(vis).map(i => [Math.round(i.getBoundingClientRect().height), getComputedStyle(i).borderTopLeftRadius]);
  const ft = [...e.querySelectorAll('.hy-side-ft')].find(vis), fr = ft && ft.getBoundingClientRect();
  return { box: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], right: Math.round(innerWidth - r.right),
    bottom: Math.round(innerHeight - r.bottom), r: s.borderTopLeftRadius, bg: s.backgroundColor, glass: probe('background: color-mix(in srgb, var(--panel) 97%, transparent)')[0],
    head: hr ? Math.round(hr.height) : null, tabs: seg ? [seg.getAttribute('variant'), ...[...seg.querySelectorAll(':scope > button')].map(b => Math.round(b.getBoundingClientRect().height))] : null,
    btns, shut, qs, foot: ft ? [getComputedStyle(ft).fontSize, Math.round(r.bottom - fr.bottom), ft.textContent.trim()] : null,
    on: probe('background: var(--hy-side-on); box-shadow: var(--hy-side-ring)') };
}"""
# an empty list: its words, size and where they stand against the panel's middle
NONE = """([q, p]) => { const e = [...document.querySelectorAll(q)].find(x => x.getClientRects().length); if (!e) return null;
  const r = e.getBoundingClientRect(), b = document.querySelector(p).getBoundingClientRect(), s = getComputedStyle(e);
  const t = document.createRange(); t.selectNodeContents(e); const tr = t.getBoundingClientRect();
  return [e.textContent.trim(), s.fontSize, Math.round(Math.abs((tr.left + tr.right) / 2 - (b.left + b.right) / 2))]; }"""
ROW = "q => { const e = document.querySelector(q); if (!e) return null; const s = getComputedStyle(e); return [s.backgroundColor, s.boxShadow]; }"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("side")
    lib, state = tmp / "lib", tmp / "state"
    for p in (lib / "a", lib / "b", state / "boards"): p.mkdir(parents=True)
    for n, c in (("a/p1", (200, 90, 80)), ("a/p2", (90, 120, 200)), ("b/p3", (120, 160, 90))): (lib / f"{n}.png").write_bytes(png(c))
    items = {f"p{i}": {"path": p, "w": 240, "ar": 0.75, "x": i * 300, "y": 0} for i, p in ((1, "a/p1.png"), (2, "a/p2.png"))}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    settings = tmp / "settings.json"; settings.write_text(json.dumps({"cv.lang": "en"}))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(settings),
               HYIMG_CACHE_ROOT=str(tmp / "cache"), HYIMG_PLUGINS=str(tmp / "noplugins"), PYTHONDONTWRITEBYTECODE="1")
    port = free_port(); log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(150):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        with playwright.sync_playwright() as p:
            try: browser = p.chromium.launch()
            except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
            yield {"port": port, "settings": settings, "browser": browser}
            browser.close()
    finally:
        proc.terminate(); proc.wait(5); log.close()


def news(world, theme):
    """two unread rows of agents: new in the bell, no comments"""
    port = world["port"]
    for title in ("Placed 2 pictures", "Rendered the scene"):
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/notifications", method="POST",
                                     data=json.dumps({"action": "add", "title": f"{title} ({theme})", "text": "", "who": "Claude", "page": "main"}).encode(),
                                     headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}", "X-Hyimg-Agent": "Claude"})
        urllib.request.urlopen(req, timeout=20).read()


def shot(page, name):
    if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / f"{name}.png"))


def open_board(world, theme, view="canvas"):
    world["settings"].write_text(json.dumps({"cv.lang": "en", "cv.theme": theme, "cv.shape": "round", "cv.lod": "0", "cv.nolib": "0"}))
    page = world["browser"].new_page(viewport={"width": W, "height": H}, color_scheme=theme)
    page.errors = []; page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{world['port']}/?view={view}", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_function("() => document.body.classList.contains('cv-on') && !document.documentElement.classList.contains('lib-wait')", timeout=90000)
    frame = None
    for _ in range(100):
        frame = next((f for f in page.frames if "/canvas" in f.url), None)
        if frame: break
        page.wait_for_timeout(100)
    frame.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 2 && window.hyKeysPanel && hyKeysPanel.parts", timeout=90000)
    frame.wait_for_function(f"() => document.documentElement.dataset.theme === '{theme}'", timeout=20000)
    page.wait_for_timeout(1200)
    return page, frame


def shown(target, q):
    return target.evaluate("q => { const e = document.querySelector(q); return !!e && !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden'; }", q)


def wait_shown(target, q, on=True):
    target.wait_for_function("""([q, on]) => { const e = document.querySelector(q);
      return (!!e && !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden') === on; }""", arg=[q, on], timeout=10000)
    target.wait_for_timeout(450)   # the side's slide (Settings) ends


def anatomy(look, name, *, head=True, tabs=False, btns=0, search=False, foot=True, width=340, full=False):
    """the chosen values (round 20), the same in both themes"""
    assert look, f"{name}: not shown"
    l, t, w, h = look["box"]
    assert w == width, f"{name}: {w} px wide, not {width}"
    assert look["r"] == "18px", f"{name}: corners {look['r']}"
    assert look["bg"] == look["glass"], f"{name}: ground {look['bg']}, not the glass 97 % {look['glass']}"
    assert t == 58 and (look["right"] == 12 or width != 340), f"{name}: at {look['box']}, right {look['right']}"
    assert look["bottom"] >= 12, f"{name}: past 12 px over the bottom"
    if full: assert look["bottom"] == 12, f"{name}: down to 12 px over the bottom"
    assert look["shut"] == 0, f"{name}: a × in it"
    if head: assert look["head"] == 52, f"{name}: header {look['head']}"
    if tabs: assert look["tabs"] and look["tabs"][0] == "pill" and all(x == 30 for x in look["tabs"][1:]), f"{name}: tabs {look['tabs']}"
    assert len(look["btns"]) == btns and all(b == [24, 24, "6px"] for b in look["btns"]), f"{name}: header buttons {look['btns']}"
    if search: assert look["qs"] and look["qs"][0] == [32, "9px"], f"{name}: search {look['qs']}"
    if foot: assert look["foot"] and look["foot"][0] == "11px" and look["foot"][1] <= 2, f"{name}: footnote {look['foot']}"


def empty(target, q, panel, words):
    got = target.evaluate(NONE, [q, panel])
    assert got and got[0].startswith(words) and got[1] == "14px" and got[2] <= 2, f"{panel}: the empty list {got}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_boards_side_panels_are_one_panel(world, theme):
    news(world, theme)
    page, f = open_board(world, theme)
    esc = lambda: page.keyboard.press("Escape")
    # the bell: two new rows of agents, the tabs in its header, Comments empty
    f.click("#bntf"); wait_shown(f, "#ntf")
    look = f.evaluate(LOOK, ["#ntf", "#ntf .hy-side-hd"]); shot(page, f"{theme}-bell")
    anatomy(look, "bell", tabs=True)
    assert look["box"][3] < H - 58 - 12 - 100, f"bell: as tall as its rows, {look['box']}"
    assert f.evaluate(ROW, "#ntf .nt.new") == look["on"], "a new row: the selection's fill and line"
    f.click("#ntf hy-segmented > button[value=com]"); f.wait_for_timeout(300)
    empty(f, "#ntf .hy-side-none", "#ntf", "Nothing yet")
    f.click("#ntf hy-segmented > button[value=all]"); f.wait_for_timeout(200)
    esc(); wait_shown(f, "#ntf", False)
    f.click("#bntf"); wait_shown(f, "#ntf"); f.click("#bntf"); wait_shown(f, "#ntf", False)
    # «?»: the search, «Nothing found» in the middle
    f.click("#bkeys"); wait_shown(f, "#keys")
    anatomy(f.evaluate(LOOK, ["#keys", "#keys .hy-side-hd"]), "?", tabs=True, search=True); shot(page, f"{theme}-keys")
    f.click("#keys input[type=search]"); page.keyboard.type("zzzz"); f.wait_for_timeout(200)
    empty(f, "#keys .hy-side-none", "#keys", "Nothing found")
    f.click("#keys .hy-side-hd"); esc(); wait_shown(f, "#keys", False)
    f.click("#bkeys"); wait_shown(f, "#keys"); f.click("#bkeys"); wait_shown(f, "#keys", False)
    # History: Activity empty, a version saved and looked at is the chosen row
    f.click("#bhist"); wait_shown(f, "#hist")
    f.click("#hist hy-segmented > button[value=ev]"); f.wait_for_timeout(400)
    look = f.evaluate(LOOK, ["#hist", "#hist .hy-side-hd"]); shot(page, f"{theme}-history")
    anatomy(look, "History", tabs=True)
    assert look["box"][3] < H - 58 - 12 - 100, f"History: as tall as what it shows, {look['box']}"
    empty(f, "#evList .hy-side-none", "#hist", "No changes yet")
    f.click("#hist hy-segmented > button[value=ver]"); f.wait_for_timeout(400)
    f.click("#histLabel"); page.keyboard.type("First"); f.click("#histSave")
    f.wait_for_selector("#histList .hv.named", timeout=10000); f.click("#histList .hv.named"); f.wait_for_selector("#histList .hv.viewing", timeout=10000)
    assert f.evaluate(ROW, "#histList .hv.viewing") == look["on"], "the version looked at: the selection's fill and line"
    f.click("#pvBack"); f.wait_for_timeout(300)
    esc(); wait_shown(f, "#hist", False)
    # Settings at the side: the title, «Open as a window» square 24, the search 32, the footnote; Esc from the board closes it
    f.click("#bset"); wait_shown(f, "#sets .sw-box")
    anatomy(f.evaluate(LOOK, ["#sets .sw-box", "#sets .sw-hd"]), "Settings", btns=1, search=True); shot(page, f"{theme}-settings")
    page.mouse.click(700, 600); f.wait_for_timeout(200)
    assert shown(f, "#sets .sw-box"), "a click on the board leaves Settings open (round 11)"
    esc(); wait_shown(f, "#sets .sw-box", False)
    f.click("#bset"); wait_shown(f, "#sets .sw-box"); f.click("#bset"); wait_shown(f, "#sets .sw-box", False)
    # the annotations' list: Open | Resolved in the header, none open in the middle
    page.mouse.click(1300, 820, button="right"); f.locator("#ctx").get_by_text("Annotations on this page").click(); wait_shown(f, "#cmlist")
    anatomy(f.evaluate(LOOK, ["#cmlist", "#cmlist .hy-side-hd"]), "annotations", tabs=True); shot(page, f"{theme}-annotations")
    empty(f, "#cmlist .hy-side-none", "#cmlist", "No open annotations")
    esc(); wait_shown(f, "#cmlist", False)
    # Info: the side panels' width, corner, glass and place; its own header, no close: Esc lets the picture go and Info with it
    box = f.locator('.it[data-id="p1"]').bounding_box(); page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    wait_shown(f, "#info")
    look = f.evaluate(LOOK, ["#info", None]); shot(page, f"{theme}-info")
    anatomy(look, "Info", head=False)   # its own header (the file); the footnote as every panel's: what ↵ does here, Esc lets it go
    main = f.evaluate("() => document.getElementById('iOpen').title.replace(/ · ↵$/, '')")   # Open's main row: View here (no plugins), Image Studio with them
    assert main and look["foot"][2] == f"↵ {main} · Esc lets it go", (main, look["foot"])
    esc(); wait_shown(f, "#info", False)
    assert not page.errors, page.errors
    page.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_library_beside_the_board_wears_the_same_parts(world, theme):
    page, f = open_board(world, theme, "panel")
    page.wait_for_function("() => window.hyLibPanel && hyLibPanel.ready && !document.body.classList.contains('cv-only')", timeout=30000)
    page.evaluate("() => { document.documentElement.style.setProperty('--lw', '560px'); renderFolders(); }"); page.wait_for_timeout(500)
    look = page.evaluate(LOOK, ["main", "header.hy-dock"]); shot(page, f"{theme}-library")
    head = page.evaluate("() => Math.round(document.querySelector('header.hy-dock .lph').getBoundingClientRect().height)")
    # its own width (the board's column, 560 by default, dragged) and its height to the bottom; the rest as every side panel
    anatomy(look, "Library", head=False, foot=False, width=560, full=True)
    ft = page.evaluate("""() => { const f = document.querySelector('.lpft'), m = document.querySelector('main').getBoundingClientRect(); if (!f || !f.getClientRects().length) return null;
      const r = f.getBoundingClientRect(); return [getComputedStyle(f).fontSize, Math.round(m.bottom - r.bottom), Math.round(r.left - m.left), Math.round(m.right - r.right), f.textContent]; }""")
    assert ft and ft[0] == "11px" and ft[1:4] == [1, 1, 1], f"Library: the footnote at its foot {ft}"
    q = page.evaluate("() => { const i = document.getElementById('q'); return [Math.round(i.getBoundingClientRect().height), getComputedStyle(i).borderTopLeftRadius]; }")
    assert q == [32, "9px"], f"Library: search {q}"
    hb = page.evaluate(LOOK, ["main", "body"])["btns"]   # the expand and view buttons stand over the header as layers of the page
    assert hb == [[24, 24, "6px"], [24, 24, "6px"]], f"Library: header buttons {hb}"
    assert page.evaluate("() => getComputedStyle(document.body).getPropertyValue('--lp-head').trim()") == "52px" and head <= 52, head
    ff = page.evaluate("() => { const i = document.getElementById('ffilt'); const r = i.getBoundingClientRect(); return [Math.round(r.height), getComputedStyle(i).borderTopLeftRadius]; }")
    assert ff == [32, "9px"], f"«Find folder»: the side panels' field, {ff}"
    page.click("#fnav .frow >> nth=1"); page.wait_for_timeout(400)
    assert page.evaluate(ROW, "#fnav .frow.on") == look["on"], "the chosen folder: the selection's fill and line"
    page.click("#q"); page.keyboard.type("zzzz"); page.wait_for_timeout(600)
    empty(page, "#list .hy-side-none", "#list .hy-side-none", "Nothing matches")   # in the middle of the pictures' room (the folders stand left of it)
    # Esc: the search's words, then the keys go to the board; in the library with nothing to take it, Esc closes it; its button opens it
    page.keyboard.press("Escape"); page.wait_for_timeout(300)
    page.click("header.hy-dock .lph"); page.keyboard.press("Escape")
    page.wait_for_function("() => document.body.classList.contains('cv-only')", timeout=10000)
    page.click("#tlibR"); page.wait_for_function("() => !document.body.classList.contains('cv-only')", timeout=10000)
    assert not page.errors, page.errors
    page.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_homes_bell_is_the_same_panel(world, theme):
    page = world["browser"].new_page(viewport={"width": W, "height": H}, color_scheme=theme)
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => {} } } };")
    page.goto(HOME)
    page.evaluate(f"hyimgHome({json.dumps({'projects': [], 'settings': {'cv.theme': theme}, 'home': {'folders': [], 'favs': [], 'view': 'grid'}})})")
    page.wait_for_function(f"() => document.documentElement.dataset.theme === '{theme}'", timeout=10000)
    page.click("#hbell"); wait_shown(page, "#ntf")
    look = page.evaluate(LOOK, ["#ntf", "#ntf .hy-side-hd"]); shot(page, f"{theme}-home-bell")
    anatomy(look, "Home's bell")
    assert page.evaluate("() => document.querySelector('#ntf .hy-side-t').textContent") == "Notifications"
    empty(page, "#ntf .hy-side-none", "#ntf", "Nothing new on the boards")
    page.keyboard.press("Escape"); wait_shown(page, "#ntf", False)
    page.click("#hbell"); wait_shown(page, "#ntf"); page.click("#hbell"); wait_shown(page, "#ntf", False)
    assert not errors, errors
    page.close()
