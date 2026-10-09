"""⌃Tab's cards, the switch's motion and the crumb's list of boards, the page's side (owner 2026-10-08, «Вкладки со сном»: «Главное, чтобы
таб еще с анимацией был: blur + scale down, и scale, когда released. При этом верхнюю панель можно сохранить ... так мы всегда будем в
доступе к кнопкам Home, Settings и все равно иметь возможность переключаться, даже если другая страница грузится»).

review/ui/switcher.js on the board's page in the app (the app's message bridge stubbed): the cards and their states, the veil under the top
row and the world a little smaller, the crumb while a board loads behind with Home and Settings still working, the board coming in
(prep, play), the crumb's list of boards and its click, a woken board's selection, what keeps a board awake, the Settings row.
Chromium, dark (owner 2026-10-07), a temporary library."""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
PID = str(uuid.uuid4())
SHOTS = Path(os.environ.get("HY_SHOTS") or Path(tempfile.gettempdir()) / "hyimg-shots")   # screenshots never go into the repository
BRIDGE = "window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.top.__sent = window.top.__sent || []).push(m); } } } };"
A, B, C = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
CARDS = [{"id": A, "name": "Board A", "state": "open", "ago": 0, "covers": []},
         {"id": B, "name": "Field Kit", "state": "warm", "ago": 130, "covers": []},
         {"id": C, "name": "Lookbook FW27", "state": "sleeping", "ago": 1500, "covers": []},
         {"id": "home", "name": "", "state": "home"}]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("switcher")
    lib, state = tmp / "lib", tmp / "state"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    for n in range(3): (lib / "a" / f"{n}.png").write_bytes(png(40 + n, 60))
    item = lambda path, x: {"path": path, "x": x, "y": 0, "w": 300, "ar": 2 / 3, "crop": None}
    items = {"p": item("a/0.png", 0), "q": item("a/1.png", 340), "r": item("a/2.png", 680)}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    settings = tmp / "settings.json"; settings.write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    (tmp / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=PID, HYIMG_SETTINGS=str(settings),
               HYIMG_PLUGINS=str(tmp / "noplugins"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    try:
        yield {"port": port}
    finally:
        proc.terminate(); proc.wait(5); log.close()


@pytest.fixture(scope="module")
def page(server, browser):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    ctx.add_init_script(BRIDGE)
    pg = ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"http://127.0.0.1:{server['port']}/?view=canvas")
    pg.wait_for_function("() => { const f = document.getElementById('cvFrame'); const w = f && f.contentWindow;"
                         " return w && w.hyimgSleepState && w.document.getElementById('stage') && w.eval(`typeof EL !== 'undefined' && !!EL.get('p')`) && window.hyimgSwitcher; }", timeout=30000)
    pg.wait_for_timeout(400)
    pg.errors = errors
    yield pg
    ctx.close()


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try: br = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        yield br
        br.close()


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"switcher-{name}.png"))


IN_FRAME = "(fn) => { const w = document.getElementById('cvFrame').contentWindow; return w.eval('(' + fn + ')()'); }"
VEIL = "() => { const d = document.getElementById('cvFrame').contentDocument, v = d.querySelector('.hysw-veil');" \
       " return v ? { on: v.classList.contains('on'), opacity: +getComputedStyle(v).opacity, parent: v.parentNode.id } : null; }"
SCALE = "() => { const d = document.getElementById('cvFrame').contentDocument, s = getComputedStyle(d.getElementById('world')).scale; return s === 'none' ? 1 : +s; }"
# what is under a point of the window, through the board's frame
AT = "([x, y]) => { const d = document.getElementById('cvFrame').contentDocument, e = d.elementFromPoint(x, y); return e ? (e.closest('[id]') || e).id : null; }"
CENTRE = "(sel) => { const d = document.getElementById('cvFrame').contentDocument, r = d.querySelector(sel).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }"


def sent(page, action):
    return [m for m in page.evaluate("() => window.__sent || []") if m.get("action") == action]


def test_the_cards_and_the_board_behind_them(page):
    page.evaluate("(c) => hyimgSwitcher({ open: true, boards: c, pick: 1 })", CARDS)
    page.wait_for_timeout(450)
    cards = page.evaluate("() => [...document.querySelectorAll('.hysw-card')].map(c => [c.className, c.querySelector('.hysw-n').textContent.trim(), c.querySelector('.hysw-s').textContent.trim()])")
    assert [c[1] for c in cards] == ["Board A", "Field Kit", "Lookbook FW27", "Home"], cards
    assert [c[2] for c in cards] == ["Open", "Warm · 2 min", "Asleep · 25 min", "All boards"], cards
    assert "on" in cards[1][0].split() and "st-sleeping" in cards[2][0], cards
    assert page.evaluate("() => !!document.querySelector('.hysw-card.st-sleeping .hysw-moon svg')")   # the moon, from the icons
    assert page.evaluate("() => document.querySelector('.hysw').classList.contains('on') && +getComputedStyle(document.querySelector('.hysw')).opacity > .99")
    v = page.evaluate(VEIL)
    assert v == {"on": True, "opacity": 1, "parent": "stage"}, v
    assert abs(page.evaluate(SCALE) - .96) < .002   # the board a little smaller behind the cards
    # the top row stays over the veil: the crumb, Home and Settings are what is under their centres
    for sel, want in [("#cHome", "cHome"), ("#bset", "bset"), ("#cProj", "cProj"), ("#bntf", "bntf")]:
        assert page.evaluate(AT, page.evaluate(CENTRE, sel)) == want, sel
    shot(page, "cards")
    page.evaluate("() => hyimgSwitcher({ pick: 2 })")
    assert page.evaluate("() => [...document.querySelectorAll('.hysw-card')].findIndex(c => c.classList.contains('on'))") == 2
    # the pointer picks a card and a click opens it: the app hears both
    page.locator(".hysw-card >> nth=3").hover(); page.wait_for_timeout(100)
    assert sent(page, "switchPick")[-1] == {"action": "switchPick", "i": 3}
    page.locator(".hysw-card >> nth=1").click()
    assert sent(page, "switchTo")[-1] == {"action": "switchTo", "to": B}
    # closed with no switch: the veil goes and the board is its size again
    page.evaluate("() => hyimgSwitcher({ open: false, keep: false })"); page.wait_for_timeout(500)
    assert page.evaluate(VEIL)["opacity"] == 0 and page.evaluate(SCALE) == 1
    assert not page.evaluate("() => document.querySelector('.hysw').classList.contains('on')")
    assert not page.errors, page.errors


def test_the_row_while_a_board_loads_behind(page):
    page.evaluate("() => hyimgSwitchOut({ name: 'Lookbook FW27', state: 'sleeping' })"); page.wait_for_timeout(700)
    crumb = page.evaluate(IN_FRAME, "() => ({ name: document.getElementById('cProjName').textContent, pend: document.getElementById('crumb').classList.contains('hysw-pend'),"
                                    " spin: !!document.querySelector('#cProj .hysw-spin'), page: getComputedStyle(document.getElementById('cPage')).display,"
                                    " wake: document.querySelector('.hysw-wake').textContent, wakeOn: +getComputedStyle(document.querySelector('.hysw-wake')).opacity })")
    assert crumb["name"] == "Lookbook FW27" and crumb["pend"] and crumb["spin"] and crumb["page"] == "none", crumb
    assert crumb["wake"] == "Waking “Lookbook FW27”" and crumb["wakeOn"] > .99, crumb
    assert page.evaluate(VEIL)["on"] and abs(page.evaluate(SCALE) - .96) < .002
    shot(page, "loading")
    # Home and Settings work meanwhile: Settings opens its panel, Home asks the app
    page.mouse.click(*page.evaluate(CENTRE, "#bset")); page.wait_for_timeout(400)
    assert page.evaluate(IN_FRAME, "() => document.getElementById('sets').classList.contains('open')")
    page.mouse.click(*page.evaluate(CENTRE, "#bset")); page.wait_for_timeout(300)
    page.mouse.click(*page.evaluate(CENTRE, "#cHome")); page.wait_for_timeout(200)
    assert sent(page, "home"), "Home answered while the board loads"
    # the press on the veil does not reach the board under it
    page.mouse.click(700, 500); page.wait_for_timeout(150)
    assert page.evaluate(IN_FRAME, "() => sel.size") == 0
    # back as it was (Esc in the app, or the board in front picked again)
    page.evaluate("() => hyimgSwitchOut(null)"); page.wait_for_timeout(500)
    back = page.evaluate(IN_FRAME, "() => [document.getElementById('cProjName').textContent, document.getElementById('crumb').classList.contains('hysw-pend'),"
                                   " !!document.querySelector('#cProj .hysw-spin')]")
    assert back[1:] == [False, False] and back[0] != "Lookbook FW27", back
    assert page.evaluate(VEIL)["opacity"] == 0 and page.evaluate(SCALE) == 1
    assert not page.errors, page.errors


def test_the_board_coming_in(page):
    page.evaluate("() => hyimgSwitchIn('prep')")
    assert page.evaluate(VEIL) == {"on": True, "opacity": 1, "parent": "stage"}   # at once, before the app brings it in front
    assert abs(page.evaluate(SCALE) - .96) < .002
    page.evaluate("() => hyimgSwitchIn('play')"); page.wait_for_timeout(120)
    mid = page.evaluate(SCALE)
    assert .96 < mid < 1, mid   # scaling up into place
    page.wait_for_timeout(450)
    assert page.evaluate(SCALE) == 1 and page.evaluate(VEIL)["opacity"] == 0
    # a woken board takes its selection back
    page.evaluate("() => hyimgSwitchRestore({ page: 'main', sel: ['q', 'gone'] })")
    assert page.evaluate(IN_FRAME, "() => [...sel]") == ["q"]
    page.evaluate(IN_FRAME, "() => { sel = new Set(); render(); }")
    assert not page.errors, page.errors


def test_the_crumbs_list_of_boards(page):
    page.evaluate("(c) => hyimgBoards(c)", CARDS)
    page.mouse.click(*page.evaluate(CENTRE, "#cProj")); page.wait_for_timeout(300)
    rows = page.evaluate(IN_FRAME, "() => [...document.querySelectorAll('#ctx .hysw-row')].map(b => [b.dataset.to, b.querySelector('.hysw-rn').textContent.trim(),"
                                   " b.querySelector('.hysw-rs').textContent.trim(), b.hasAttribute('aria-current')])")
    assert rows == [[A, "Board A", "Open", True], [B, "Field Kit", "Warm · 2 min", False], [C, "Lookbook FW27", "Asleep · 25 min", False]], rows
    assert page.evaluate(IN_FRAME, "() => document.querySelector('#ctx .hysw-mh').textContent") == "Open boards"
    assert page.evaluate(IN_FRAME, "() => !!document.querySelector('#ctx [data-act=copyRoot]')")   # its own items stay under the list
    shot(page, "crumb-list")
    page.evaluate(IN_FRAME, f"() => document.querySelector('#ctx [data-to=\"{C}\"]').click()")
    assert sent(page, "switchTo")[-1] == {"action": "switchTo", "to": C}
    assert not page.errors, page.errors


def test_what_keeps_a_board_awake(page):
    def ask():
        page.evaluate("() => hyimgSleepAsk('t1')")
        return [m for m in sent(page, "sleepState") if m["token"] == "t1"][-1]["state"]
    st = ask()
    assert st["unsaved"] is False and st["editing"] is False and st["studio"] == "" and st["busy"] == [] and st["video"] is False, st
    assert st["page"] == "main" and isinstance(st["sel"], list), st
    page.evaluate(IN_FRAME, "() => busy('upload', 'saving the image…')")
    assert ask()["busy"] == ["saving the image…"]
    page.evaluate(IN_FRAME, "() => busy('upload')")
    page.evaluate(IN_FRAME, "() => { dirty = true; }")
    assert ask()["unsaved"] is True
    page.evaluate(IN_FRAME, "() => { dirty = false; }")
    assert ask()["unsaved"] is False
    assert not page.errors, page.errors


def test_the_setting(page):
    page.mouse.click(*page.evaluate(CENTRE, "#bset")); page.wait_for_timeout(400)
    row = page.evaluate(IN_FRAME, "() => { const r = document.querySelector('#sets [data-row=sleep]'); return r && [r.querySelector('.sp-l').textContent,"
                                  " [...r.querySelectorAll('button')].map(b => b.textContent), r.querySelector('button.on').value]; }")
    assert row == ["Sleep background boards", ["5 min", "10 min", "30 min", "Never"], "10"], row
    page.mouse.click(*page.evaluate(CENTRE, "#bset")); page.wait_for_timeout(300)
    assert not page.errors, page.errors


def test_the_cards_over_home(browser):
    """Home in front: the cards over it, its columns blurred and smaller under them, its gear above; the switch to a board leaves the rest
    to Home's own way out, and the app puts Home back as it was when it comes back (hyimgSwitchOut(null, true))"""
    home = (ROOT / "review/home.html").as_uri()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    ctx.add_init_script(BRIDGE)
    pg = ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(home)
    pg.evaluate("(p) => hyimgHome({ projects: p, settings: { 'cv.theme': 'dark' }, home: { folders: [] } })",
                [{"id": c["id"], "name": c["name"], "path": "/x", "available": True, "updated": 0, "covers": []} for c in CARDS[:3]])
    home_first = [{"id": "home", "name": "", "state": "home"}] + [dict(c, state="warm") for c in CARDS[:3]]
    pg.evaluate("(c) => hyimgSwitcher({ open: true, boards: c, pick: 1 })", home_first); pg.wait_for_timeout(450)
    assert pg.evaluate("() => [...document.querySelectorAll('.hysw-card')].map(c => c.querySelector('.hysw-n').textContent.trim())") == ["Home", "Board A", "Field Kit", "Lookbook FW27"]
    veil = pg.evaluate("() => { const v = document.querySelector('body > .hysw-veil.home'); return v && [v.classList.contains('on'), +getComputedStyle(v).opacity]; }")
    assert veil == [True, 1], veil
    assert abs(pg.evaluate("() => +getComputedStyle(document.querySelector('body > .app')).scale") - .96) < .002
    gear = pg.evaluate("() => { const r = document.getElementById('bset').getBoundingClientRect();"
                       " return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2).closest('#bset') !== null; }")
    assert gear, "Home's gear stays over the veil"
    shot(pg, "home")
    pg.evaluate("() => hyimgSwitcher({ open: false, keep: true })"); pg.wait_for_timeout(300)
    pg.evaluate("() => hyimgSwitchOut(null, true)")
    assert pg.evaluate("() => { const v = document.querySelector('.hysw-veil'); return !v.classList.contains('on') && getComputedStyle(document.querySelector('body > .app')).scale === 'none'; }")
    assert not errors, errors
    ctx.close()
