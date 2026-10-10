"""No shortcut fires while someone types (owner 2026-10-10, an Annotation thread open over an HTML card, a reply being written: «когда я
в аннотациях пишу что-то, у меня триггерится F кнопка, возможно и другие тоже, когда я тупо пишу сообщение»).

The cause: the thread's refresh every 8 s (ui/comments.js load) drew the open thread anew, its field too, and the focus fell to the page;
the next letters were the board's keys: F ♥ the selected cards, N a new note, G a group, digits the opacity. The rule since then is one
(ui/typing.js, hyTyping): a field that takes text (an input, a textarea, an editable element, [role=textbox]) takes every key, and the
redrawn thread keeps its field's focus and caret.

Each case types a message with every single-letter key of the board (F C V N L G T I P A, ⇧ of them, the digits, the space, ⌫, ! and the
Russian letters of the same keys) and checks that nothing of the board happened (no ♥, no new object, the selection and the opacity
as they were, no tool, no crop) and that the field holds the text as typed:
- a reply in an annotation thread on a live HTML card and on a picture, the thread's refresh in the middle of it
- the note editor, a page's name, the settings' search, an editable element and a [role=textbox] of the board's page

Chromium, dark theme, a temporary library (the plugins from their repositories' last commits). HY_SHOTS=<folder> keeps screenshots."""
import io
import json
import os
import subprocess
import sys
import tarfile
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
PLUGINS = {"frames": "hyimg-image-studio", "dev": "hyimg-dev-studio"}
PAGE = "<!doctype html><html><head><title>Bell</title></head><body><div>a</div><div>b</div><div>c</div><div style='height:600px'>four</div></body></html>"
# every single-letter key of the board and its Russian twin, ⇧ of them, the digits (opacity), the space (the hand), ! (fit)
TEXT = "fcvnlgtipa FCVNLGTIPA 0123456789 ! афсмтдпше zxyz"
# the board's actions a key can start: none of them may run while a field is typed in
WATCH = ["toggleFav", "makeGroup", "ungroup", "newNote", "newTimeline", "setOpacity", "removeSel", "removeArrow", "startCropSel", "fit",
         "toggleLib", "tidy", "tidyRow", "smartTidy", "duplicate", "copySel", "cutSel", "nudge", "undo", "redo", "vidSpace", "closePages"]
SPY = """names => { window.__hits = [];
  for (const n of names) { const f = window[n]; if (typeof f !== 'function' || f.__spy) continue;
    const g = function (...a) { __hits.push(n); return f.apply(this, a); }; g.__spy = true; window[n] = g; } }"""
STATE = """() => ({ items: Object.keys(board.items).sort(), groups: Object.keys(board.groups || {}).sort(), sel: [...sel].sort(),
  op: Object.fromEntries(Object.entries(board.items).map(([k, v]) => [k, v.op ?? null])),
  faved: [...document.querySelectorAll('.faved')].map(e => e.dataset.id).sort(), tool: (window.hyAnnot && hyAnnot.active) || null,
  crop: !!cropState, space: !!space, hits: window.__hits })"""


@pytest.fixture
def server(tmp_path):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in (lib / "a", lib / "html/bell", state / "boards", plugins): d.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png(64, 40)); (lib / "html/bell/index.html").write_text(PAGE)
    have = []
    for name, repo in PLUGINS.items():   # each plugin as its repository's last commit (other agents may be changing the working copies)
        src = ROOT.parent / repo
        if not (src / "manifest.json").is_file(): continue
        raw = subprocess.run(["git", "-C", str(src), "archive", "HEAD"], capture_output=True, check=True).stdout
        (plugins / name).mkdir(); tarfile.open(fileobj=io.BytesIO(raw)).extractall(plugins / name, filter="data"); have.append(name)
    if len(have) < 2: pytest.skip("the frames and Dev plugins' repositories are not beside this one")
    items = {"p": {"path": "a/0.png", "x": 0, "y": 0, "w": 480, "ar": 1.6, "crop": None},
             "d": {"type": "html", "src": "html/bell/index.html", "vw": 1440, "ar": 1.6, "pics": ["html/bell/index.html"], "x": 560, "y": 0, "w": 480, "h": 300}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "groups": {}, "removed": {}, "items": items}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    (tmp_path / "profile.json").write_text(json.dumps({"id": str(uuid.uuid4()), "name": "Ann Lee", "color": "green", "created": ""}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HYIMG_PLUGINS=str(plugins), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, lib
    finally:
        proc.terminate(); proc.wait(5); log.close()


def shot(page, name):
    d = os.environ.get("HY_SHOTS")
    if d: Path(d).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(d) / name))


def faved(lib):
    out = []
    for rel in ("a/0.json", "html/bell/index.html.json"):
        f = lib / rel
        if f.is_file() and json.loads(f.read_text()).get("feedback", {}).get("fav"): out.append(rel)
    return out


def open_board(p, port):
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url)
    page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
      localStorage.setItem('cv.cam.main', JSON.stringify({ x: -60, y: -120, z: 1 })); }""")
    page.goto(url)
    page.wait_for_function("""() => typeof BOARD !== 'undefined' && PLG.html && EL.get('p') && EL.get('d') && window.hyAnnot && window.hyComments
      && document.getElementById('bann') && window.hyPeople && hyPeople.me()""", timeout=30000)
    page.wait_for_function("() => document.querySelector('.plg[data-id=d] iframe')", timeout=20000)   # big on screen: the live page
    assert page.evaluate("() => document.documentElement.dataset.theme") != "light"
    return browser, page, errors


def typed_nothing_fired(page, lib, before, field, text=TEXT):
    """after typing into `field` (a CSS selector of the board's page): the board as it was, the field holding the text"""
    after = page.evaluate(STATE)
    assert after["hits"] == [], f"board actions ran while typing: {after['hits']}"
    for k in ("items", "groups", "sel", "op", "faved", "tool", "crop", "space"):
        assert after[k] == before[k], (k, before[k], after[k])
    assert faved(lib) == []
    return page.evaluate(f"() => {{ const f = document.querySelector({json.dumps(field)}); return f.value ?? f.textContent; }}")


def thread_on(page, card):
    """an annotation on the card (C, a click on it, a first message), closed again; its id"""
    page.keyboard.press("c"); page.wait_for_selector("#stage.annot[data-ann-tool=comment]")
    r = page.evaluate(f"() => {{ const r = EL.get('{card}').getBoundingClientRect(); return [r.x + r.width * .3, r.y + r.height * .7]; }}")
    page.mouse.click(*r)
    page.wait_for_selector("#cmthread.open textarea"); page.keyboard.type("first"); page.keyboard.press("Enter")
    page.wait_for_function("() => document.querySelector('#cmthread.open') && document.querySelector('#cmthread').dataset.c !== 'draft'")
    tid = page.evaluate("() => document.querySelector('#cmthread').dataset.c")
    page.keyboard.press("Escape"); page.keyboard.press("Escape")
    page.wait_for_function("() => !document.querySelector('#cmthread.open') && !hyAnnot.active")
    return tid


@pytest.mark.parametrize("card", ["d", "p"])
def test_a_reply_in_an_annotation_thread_types_no_board_keys(server, card):
    """the owner's case: the thread of a live HTML card (and of a picture) open from its pin, the cards selected, a reply typed while the
    thread refreshes (its 8 s poll): the letters stay in the field, the board does nothing"""
    port, lib = server
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, port)
        tid = thread_on(page, card)
        page.evaluate("() => { sel = new Set(['p', 'd']); render(); }")
        page.locator(f'#cmpins [data-c="{tid}"]').click()
        page.wait_for_selector("#cmthread.open textarea"); page.locator("#cmthread textarea").click()
        page.evaluate(SPY, WATCH)
        before = page.evaluate(STATE)
        page.keyboard.type("я же сказал ")
        # the refresh draws the thread anew mid-sentence (what the 8 s poll does): the field keeps the focus and the caret at its end
        page.evaluate("() => hyComments.load()")
        page.wait_for_function("() => document.querySelector('#cmthread .cm-m:nth-child(1)')")
        page.keyboard.type(TEXT); page.keyboard.press("Space"); page.keyboard.press("Backspace")
        page.keyboard.press("Backspace")
        shot(page, f"typing-thread-{card}.png")
        assert typed_nothing_fired(page, lib, before, "#cmthread textarea") == "я же сказал " + TEXT[:-1]
        assert page.evaluate("() => document.activeElement && document.activeElement.matches('#cmthread textarea')"), "the refresh took the field's focus"
        # a caret moved back into the middle stays there over a refresh too
        page.evaluate("() => document.querySelector('#cmthread textarea').setSelectionRange(2, 2)")
        page.evaluate("() => hyComments.load()"); page.wait_for_timeout(300)
        page.keyboard.type("X")
        assert page.evaluate("() => document.querySelector('#cmthread textarea').value") == "я Xже сказал " + TEXT[:-1]
        assert not errors, errors
        browser.close()


def test_the_board_s_other_fields_type_no_board_keys(server):
    """the note editor, a page's name, the settings' search, an editable element and a [role=textbox] on the board's page"""
    port, lib = server
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, port)
        page.evaluate("() => { sel = new Set(['p', 'd']); render(); }")
        page.evaluate(SPY, WATCH)

        # a page's name: the field in the pages' list
        page.evaluate("() => openPages()"); page.wait_for_function("() => document.querySelector(`#pages .row[data-pg='${BOARD}']`)")
        page.evaluate("() => renamePage(BOARD)"); page.wait_for_selector("#pages .row input")
        page.keyboard.press("ControlOrMeta+a"); before = page.evaluate(STATE)
        page.keyboard.type(TEXT)
        assert typed_nothing_fired(page, lib, before, "#pages .row input") == TEXT
        page.keyboard.press("Escape"); page.wait_for_timeout(200)
        page.evaluate("() => { if ($('#pages').classList.contains('open')) closePages(); sel = new Set(['p', 'd']); render(); __hits.length = 0; }")

        # the settings' search
        page.click("#bset"); page.wait_for_selector(".sw-q input")
        page.click(".sw-q input"); before = page.evaluate(STATE)
        page.keyboard.type(TEXT)
        assert typed_nothing_fired(page, lib, before, ".sw-q input") == TEXT
        page.keyboard.press("Escape"); page.keyboard.press("Escape"); page.wait_for_function("() => !document.querySelector('.sw-q input:focus')")
        page.evaluate("() => { document.activeElement.blur(); sel = new Set(['p', 'd']); render(); __hits.length = 0; }")

        # an editable element and a [role=textbox] (a plugin's or a primitive's field): the shared rule, not a list of tags
        page.evaluate("""() => { const a = document.createElement('div'); a.id = 'tyce'; a.contentEditable = 'plaintext-only';
          const b = document.createElement('div'); b.id = 'tyrole'; b.setAttribute('role', 'textbox'); b.tabIndex = 0;
          for (const x of [a, b]) { x.style.cssText = 'position:fixed;left:20px;top:200px;width:300px;height:40px;z-index:999;background:#222;color:#fff'; document.body.appendChild(x); }
          b.style.top = '260px'; }""")
        for fid in ("tyce", "tyrole"):
            page.evaluate(f"() => document.getElementById('{fid}').focus()"); before = page.evaluate(STATE)
            page.keyboard.type(TEXT)
            got = typed_nothing_fired(page, lib, before, f"#{fid}")
            if fid == "tyce": assert got == TEXT
        page.evaluate("() => { document.getElementById('tyce').remove(); document.getElementById('tyrole').remove(); }")

        # the note editor: N makes the note and its field takes the rest (the one new object)
        page.evaluate("() => { document.activeElement && document.activeElement.blur(); sel = new Set(['p', 'd']); render(); }")
        page.keyboard.press("n")
        page.wait_for_function("() => document.activeElement && document.activeElement.tagName === 'TEXTAREA'")
        page.evaluate("() => { __hits.length = 0; }"); before = page.evaluate(STATE)
        page.keyboard.type(TEXT)
        assert typed_nothing_fired(page, lib, before, "textarea:focus") == TEXT
        assert not errors, errors
        browser.close()
