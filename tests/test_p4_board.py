"""The board's П4 logic audit of 2026-10-10, its Критично and Высокий findings (docs/process.md §4, §5): one regression test each, every
one failing on the code before the fix. Chromium, dark theme, our own temporary servers and folders, never the ports 4180–4184.

  B-01, B-02  ⌘D and ⌥-drag copy a timeline's dots, a note's zone and arrows: the copy is its own, the original and its file stay
  B-03, B-04  Esc, a press on the board, another pin, the dock's button keep an annotation's unsent words as a draft on its pin
  B-05        ⌘C on one board, ⌘V on another (another project, another library) brings the things and their pictures
  B-06        an agent's write keeps the undo history: ⌘Z still undoes the last nudge, a step the agent overrode is skipped and said
  B-07        ⌘Z in a Studio never undoes the board's annotation
  B-08        the video player and the PDF page take every key: C and ⌘Z do nothing on the board under them
  B-09        Space pans with the Annotation tool on
  B-10        Move to page carries the connectors between the things that go, counts the dropped one, ⌘Z brings all back
  B-11        Esc after Edit gives back the reply written before, the edited words never become a reply
  B-12        the 8 s refresh closes the mention list, a hidden one never takes the next ↵
  B-13        \\ in the app never brings back the old library inside the board
  B-14        ⌘F with the library's viewer open leaves the search alone"""
import contextlib
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request
import uuid
import zlib
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
ME, OTHER = str(uuid.uuid4()), str(uuid.uuid4())

# a Studio that holds the dock and every key, its ⌘Z counted (as hyimg-3d-studio and hyimg-image-studio do)
FAKE = r"""
let open = null; window.__studioUndo = 0;
export function register(HY) {
  HY.register("fake", {
    render(el) { if (!el.firstChild) el.innerHTML = '<div style="position:absolute;inset:0;background:#2a6"></div>'; },
    dblclick(id) { open = id; HY.dock(Object.assign(document.createElement("span"), { innerHTML: '<button data-a="done">Done</button>', onclick: () => leave() })); HY.modeChanged(); },
    onKey(e) { if (!open) return false; if ((e.metaKey || e.ctrlKey) && e.key === "z") { e.preventDefault(); __studioUndo++; } if (e.key === "Escape") leave(); return true; },
  });
  const leave = () => { open = null; HY.dock(null); HY.modeChanged(); };
  HY.mode("fake", { fit: false, label: "Fake", order: 5, icon: "<svg width=16 height=16></svg>", title: "Fake", hint: "Select a fake card", isOpen: () => !!open,
    target: ids => ids.length === 1 && HY.board.items[ids[0]] && HY.board.items[ids[0]].type === "fake" ? ids[0] : null, enter: id => PLG.fake.dblclick(id), leave });
}
"""


def png(rgb=(255, 255, 255), w=40, h=60):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def free_port():
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]
        if not 4180 <= p <= 4184: return p


def pic(n, x, y=0):
    return {"path": f"a/{n}.png", "x": x, "y": y, "w": 320, "ar": 2 / 3, "crop": None}


def api(port, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST", headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=10))


def wait(fn, what, t=10):
    end = time.time() + t
    while time.time() < end:
        v = fn()
        if v: return v
        time.sleep(0.1)
    raise AssertionError(what)


@contextlib.contextmanager
def serve(home, items=None, colour=(255, 255, 255), plugin=False, settings=None, links=None, pages=False):
    """a board's server on a temporary library; settings: the folder of the app's settings (two servers share it, as two boards of one app)"""
    lib, state = home / "lib", home / "state"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    for n in range(6): (lib / "a" / f"{n}.png").write_bytes(png(tuple((c + 20 * n) % 256 for c in colour)))
    items = items if items is not None else {f"i{n}": pic(n, n * 340) for n in range(6)}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}, **({"links": links} if links else {})}))
    if pages: (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "A"}, {"id": "p2", "title": "B"}]}))
    sdir = settings or home
    sdir.mkdir(parents=True, exist_ok=True)
    if not (sdir / "settings.json").exists():
        (sdir / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
        (sdir / "profile.json").write_text(json.dumps({"id": ME, "name": "Ann Lee", "color": "green", "created": ""}))
        (sdir / "people.json").write_text(json.dumps({OTHER: {"name": "Bob", "color": "orange", "agents": {"codex": time.time() - 60}}}))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(sdir / "settings.json"),
               HYIMG_CACHE_ROOT=str(home / "cache"), PYTHONDONTWRITEBYTECODE="1", HY_TEST_ONLY_PLUGINS="1")
    if plugin:
        (home / "plugins/fake").mkdir(parents=True)
        (home / "plugins/fake/manifest.json").write_text(json.dumps({"title": "Fake", "canvas": "canvas.js"})); (home / "plugins/fake/canvas.js").write_text(FAKE)
        env["HYIMG_PLUGINS"] = str(home / "plugins")
    port = free_port()
    log = open(home / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(150):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, lib
    finally:
        proc.terminate(); proc.wait(5); log.close()


def browser_of(p):
    try: return p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")


def board_page(browser, port):
    page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url); page.evaluate("() => { localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }"); page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && window.hyAnnot && document.getElementById('bann') && window.hyComments && window.hyPeople && hyPeople.me()",
                           timeout=20000)
    page.evaluate("() => { cam.x = -60; cam.y = -120; cam.z = 1; renderCam(); render(); window.TL = []; const o = window.hyToast;"
                  " window.hyToast = (t, k, x) => { TL.push(t); return o(t, k, x); }; }")
    page.wait_for_timeout(300)
    return page, errors


def app_page(browser, port):
    page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/?view=panel"
    page.goto(url); page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.lod', '0'); }"); page.goto(url)
    page.wait_for_function("() => document.body.classList.contains('cv-on') && !document.documentElement.classList.contains('lib-wait')", timeout=20000)
    frame = next(f for f in page.frames if "embed=1" in f.url)
    frame.wait_for_function("() => typeof BOARD !== 'undefined' && board && Object.keys(board.items).length === 6", timeout=20000)
    page.wait_for_timeout(800)
    return page, frame, errors


def box(page, sel):
    return page.evaluate("s => { const r = document.querySelector(s).getBoundingClientRect();"
                         " return { x: r.x, y: r.y, w: r.width, h: r.height, cx: r.x + r.width / 2, cy: r.y + r.height / 2 }; }", sel)


def saved(port):
    return api(port, "/api/board?name=main")


def settle(page, port):   # nothing waits to be saved
    page.wait_for_function("() => !dirty && !saveT && !saveFlight", timeout=10000)


# ---- B-01, B-02 -------------------------------------------------------------------------------------------------------------------
NOTE = {"type": "note", "text": "zone", "x": 800, "y": 100, "w": 200, "fs": 14, "size": 2, "h": 0, "color": "yellow", "reach": {"l": 20, "r": 20, "t": 20, "b": 20},
        "to": ["i0"]}


def test_b01_a_copied_timeline_has_its_own_dots(tmp_path):
    with serve(tmp_path, {"i0": pic(0, 0)}) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        # a timeline by L, its first dot named; ⌘D; the copy's first dot renamed: the original and its file keep their name
        page.mouse.move(900, 600); page.keyboard.press("l"); page.wait_for_timeout(200); page.keyboard.type("Start"); page.keyboard.press("Enter")
        tl = ev("() => [...sel][0]")
        page.keyboard.press("Meta+d"); tl2 = ev("() => [...sel][0]")
        assert tl2 != tl
        ev(f"() => editTlLabel('{tl2}', board.items['{tl2}'].points[0].id)"); page.wait_for_timeout(150)
        page.keyboard.press("Meta+a"); page.keyboard.type("Changed"); page.keyboard.press("Enter"); page.wait_for_timeout(200)
        assert ev(f"() => [board.items['{tl}'].points[0].text, board.items['{tl2}'].points[0].text]") == ["Start", "Changed"]
        settle(page, port)
        f = saved(port)["items"]
        assert f[tl]["points"][0]["text"] == "Start" and f[tl2]["points"][0]["text"] == "Changed"
        assert not errors, errors
        browser.close()


def test_b02_a_copied_note_has_its_own_zone_and_arrows(tmp_path):
    with serve(tmp_path, {"i0": pic(0, 0), "i1": pic(1, 340), "n1": NOTE}) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        r = box(page, '.note[data-id="n1"]')   # ⌥-drag, then ⌘D: two copies
        page.keyboard.down("Alt"); page.mouse.move(r["cx"], r["cy"]); page.mouse.down(); page.mouse.move(r["cx"] + 260, r["cy"] + 40, steps=6); page.mouse.up(); page.keyboard.up("Alt")
        n3 = ev("() => [...sel][0]")
        ev("() => { sel = new Set(['n1']); render(); }"); page.keyboard.press("Meta+d"); n2 = ev("() => [...sel][0]")
        assert len({"n1", n2, n3}) == 3
        for n in (n2, n3):   # a copy's zone pulled wider and an arrow added, as the zone's handles and the arrow's drag do it, in place
            ev(f"() => {{ const b = snap(); board.items['{n}'].reach.l = 400; board.items['{n}'].to.push('i1'); commit(b); }}")
        assert ev("() => [board.items.n1.reach.l, board.items.n1.to]") == [20, ["i0"]]
        settle(page, port)
        f = saved(port)["items"]
        assert f["n1"]["reach"]["l"] == 20 and f["n1"]["to"] == ["i0"] and f[n2]["reach"]["l"] == 400 and f[n3]["to"] == ["i0", "i1"]
        assert not errors, errors
        browser.close()


# ---- B-03, B-04, B-11, B-12 ---------------------------------------------------------------------------------------------------------
FIELD = "() => (document.querySelector('#cmthread.open textarea') || {}).value"


def threads(port):
    return api(port, "/api/comments?name=main").get("items", [])


def annotate(page, port, on="i1", text="first words"):   # C, a click on a picture, words, ↵: one thread, left open
    page.keyboard.press("c"); r = box(page, f'.it[data-id="{on}"]'); page.mouse.click(r["x"] + 80, r["y"] + 90)
    page.wait_for_selector("#cmthread.open textarea"); page.keyboard.type(text); page.keyboard.press("Enter")
    wait(lambda: len(threads(port)) == 1, "the annotation was sent")
    page.wait_for_selector("#cmthread.open .cm-m [data-cm=edit]")
    return threads(port)[0]["id"]


def test_b03_esc_keeps_the_words_as_a_draft(tmp_path):
    with serve(tmp_path) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        # a new annotation, typed, Esc: nothing is sent, the pin stays with its draft dot, a press on it brings the words back
        page.keyboard.press("c"); r = box(page, '.it[data-id="i2"]'); page.mouse.click(r["x"] + 80, r["y"] + 90)
        page.wait_for_selector("#cmthread.open textarea"); page.keyboard.type("keep me")
        page.keyboard.press("Escape")
        page.wait_for_function("() => !document.querySelector('#cmthread.open')")
        assert threads(port) == []
        pin = page.wait_for_selector("#cmpins .cmpin .cmp-d", timeout=3000).evaluate("d => d.parentElement.dataset.c")
        page.click(f'#cmpins .cmpin[data-c="{pin}"]')
        page.wait_for_selector("#cmthread.open textarea"); assert ev(FIELD) == "keep me"
        page.keyboard.press("Enter"); wait(lambda: len(threads(port)) == 1, "the annotation was sent")   # sent from there: the draft pin goes
        page.wait_for_function("() => !document.querySelector('#cmpins .cmp-d')")
        tid = threads(port)[0]["id"]
        # a reply typed, Esc: the words stay with the thread, its pin wears the dot, opening it brings them back
        page.click("#cmthread.open textarea"); page.keyboard.type("half a reply")
        page.keyboard.press("Escape"); page.wait_for_function("() => !document.querySelector('#cmthread.open')")
        page.wait_for_selector(f'#cmpins .cmpin[data-c="{tid}"] .cmp-d')
        page.click(f'#cmpins .cmpin[data-c="{tid}"]'); page.wait_for_selector("#cmthread.open textarea")
        assert ev(FIELD) == "half a reply" and len(threads(port)[0]["messages"]) == 1
        assert not errors, errors
        browser.close()


def test_b04_every_way_out_keeps_the_words(tmp_path):
    with serve(tmp_path, pages=True) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        tid = annotate(page, port)
        pin = f'#cmpins .cmpin[data-c="{tid}"]'
        # a reply typed; with the tool on, a press on a picture closes the thread: its words stay, the pin wears the dot
        page.click("#cmthread.open textarea"); page.keyboard.type("half a reply"); ev("() => hyAnnot.active || hyAnnot.tool('comment')")
        r = box(page, '.it[data-id="i3"]'); page.mouse.click(r["x"] + 60, r["y"] + 60)
        page.wait_for_function("() => !document.querySelector('#cmthread.open')")
        page.wait_for_selector(pin + " .cmp-d", timeout=3000)
        # the next press starts a new one; typed, then a press on the thread's pin: the thread has its words back
        page.mouse.click(r["x"] + 60, r["y"] + 60); page.wait_for_selector('#cmthread.open[data-c="draft"] textarea'); page.keyboard.type("second")
        page.click(pin); page.wait_for_selector(f'#cmthread.open[data-c="{tid}"] textarea')
        assert ev(FIELD) == "half a reply"
        # one more new one, then the dock's Annotation button
        page.mouse.click(r["x"] + 60, r["y"] + 160); page.wait_for_function("() => !document.querySelector('#cmthread.open')")
        page.mouse.click(r["x"] + 60, r["y"] + 160); page.wait_for_selector('#cmthread.open[data-c="draft"] textarea'); page.keyboard.type("third")
        page.click("#bann"); page.wait_for_function("() => !hyAnnot.active && !document.querySelector('#cmthread.open')")
        # each new one waits on a pin of its own with the dot; a press on it brings its words back
        kept = page.eval_on_selector_all("#cmpins .cmpin", f"bs => bs.filter(b => b.querySelector('.cmp-d') && b.dataset.c !== '{tid}').map(b => b.dataset.c)")
        words = []
        for k in kept:
            page.click(f'#cmpins .cmpin[data-c="{k}"]'); page.wait_for_selector('#cmthread.open[data-c="draft"] textarea')
            words.append(ev(FIELD)); page.keyboard.press("Escape"); page.wait_for_function("() => !document.querySelector('#cmthread.open')")
        assert sorted(words) == ["second", "third"], words
        # a page switch with a reply typed: back on the page, the words are there
        page.click(pin); page.wait_for_selector(f'#cmthread.open[data-c="{tid}"] textarea')
        page.click("#cmthread.open textarea"); page.keyboard.press("Meta+a"); page.keyboard.type("before the switch")
        ev("() => switchPage('p2')"); page.wait_for_function("() => BOARD === 'p2'"); ev("() => switchPage('main')")
        page.wait_for_function("() => BOARD === 'main'"); page.wait_for_selector(pin + " .cmp-d")
        page.click(pin); page.wait_for_selector(f'#cmthread.open[data-c="{tid}"] textarea')
        assert ev(FIELD) == "before the switch"
        assert len(threads(port)) == 1 and len(threads(port)[0]["messages"]) == 1   # leaving never sent anything
        assert not errors, errors
        browser.close()


def test_b11_esc_after_edit_gives_back_the_reply(tmp_path):
    with serve(tmp_path) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        annotate(page, port)
        # a reply half written, Edit, the message changed, Esc: the field has the reply again, ↵ sends only it
        page.click("#cmthread.open textarea"); page.keyboard.type("my reply")
        page.click("#cmthread.open .cm-m [data-cm=edit]"); assert ev(FIELD) == "first words"
        page.keyboard.type(" plus an edit"); page.keyboard.press("Escape")
        assert ev(FIELD) == "my reply" and ev("() => hyComments.state.edit") is None
        page.keyboard.press("Enter"); wait(lambda: len(threads(port)[0]["messages"]) == 2, "the reply was sent")
        msgs = [m["text"] for m in threads(port)[0]["messages"]]
        assert msgs == ["first words", "my reply"], msgs
        # Edit with nothing written before, Esc: the field is empty
        page.wait_for_function(FIELD + " === ''")
        page.click("#cmthread.open .cm-m [data-cm=edit]"); page.keyboard.type(" again"); page.keyboard.press("Escape")
        assert ev(FIELD) == ""
        assert not errors, errors
        browser.close()


def test_b12_a_refresh_closes_the_mention_list(tmp_path):
    with serve(tmp_path) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        annotate(page, port)
        # «@B» opens the mention list; the refresh every 8 s draws the thread anew and closes it; ↵ sends the words as typed
        page.click("#cmthread.open textarea"); page.keyboard.type("@B"); page.wait_for_selector("#cmat")
        page.wait_for_timeout(8600)   # the refresh itself (comments.js init: every 8 s)
        assert ev("() => !document.getElementById('cmat')") and ev(FIELD) == "@B"
        page.keyboard.press("Enter"); wait(lambda: len(threads(port)[0]["messages"]) == 2, "↵ sent the reply")
        assert threads(port)[0]["messages"][1]["text"] == "@B"
        assert not errors, errors
        browser.close()


# ---- B-05 ---------------------------------------------------------------------------------------------------------------------------
def test_b05_copy_on_one_board_paste_on_another(tmp_path):
    shared = tmp_path / "app"   # the app's settings folder: both boards are of one app
    with serve(tmp_path / "A", colour=(200, 40, 40), settings=shared) as (pa, la), serve(tmp_path / "B", settings=shared) as (pb, lb), \
            playwright.sync_playwright() as p:
        browser = browser_of(p)
        a, ea = board_page(browser, pa); b, eb = board_page(browser, pb)
        a.evaluate("() => { sel = new Set(['i1', 'i2']); render(); }"); a.bring_to_front(); a.keyboard.press("Meta+c")
        link = a.evaluate("() => linkTo({ obj: 'i1,i2' })")
        time.sleep(0.5)   # the copy reaches the app's clipboard
        b.bring_to_front(); b.mouse.move(700, 600); b.keyboard.press("Meta+v")
        b.wait_for_function("() => Object.keys(board.items).length === 8", timeout=10000)
        new = b.evaluate("() => [...sel].map(id => board.items[id].path)")
        assert len(new) == 2
        # A's pictures, byte for byte, in B's library (B's own a/1.png and a/2.png are other pictures)
        assert sorted((lb / rel).read_bytes() for rel in new) == sorted((la / "a" / f"{n}.png").read_bytes() for n in (1, 2))
        assert "Pasted" in " ".join(b.evaluate("() => TL"))
        # the link ⌘C put on the system clipboard, pasted as text on B: the things again, never a heading with the link
        n0 = b.evaluate("() => Object.keys(board.items).length")
        b.evaluate("t => { const d = new DataTransfer(); d.setData('text/plain', t); document.dispatchEvent(new ClipboardEvent('paste', { clipboardData: d })); }", link)
        b.wait_for_function(f"() => Object.keys(board.items).length === {n0 + 2}", timeout=10000)
        assert not b.evaluate("() => Object.values(board.items).some(i => i.type === 'text')")
        assert not ea and not eb, (ea, eb)
        browser.close()


# ---- B-06 ---------------------------------------------------------------------------------------------------------------------------
def test_b06_an_agents_write_keeps_the_undo_history(tmp_path):
    with serve(tmp_path) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        y0 = ev("() => [1, 2, 3].map(i => board.items['i' + i].y)")
        for i in (1, 2, 3):   # three nudges, three steps
            ev(f"() => {{ sel = new Set(['i{i}']); render(); }}"); page.keyboard.press("Shift+ArrowDown"); page.wait_for_timeout(700)
        settle(page, port)
        assert ev("() => past.length") == 3
        # an agent adds a picture and moves i2 across
        b = saved(port); b["items"]["agent1"] = pic(0, 3000); b["items"]["i2"]["x"] += 500
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/board?name=main&who=ai", data=json.dumps(b).encode(), method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
        page.wait_for_function("() => !!board.items.agent1", timeout=10000)
        assert ev("() => past.length") == 3   # the history stays
        page.keyboard.press("Meta+z")
        assert ev("() => board.items.i3.y") == y0[2] and ev("() => !!board.items.agent1")   # the last nudge undone, the agent's picture stays
        # the next step moved i2, which the agent has moved since: skipped and said; the one before it is undone
        ev("() => TL.length = 0"); page.keyboard.press("Meta+z")
        assert ev("() => board.items.i1.y") == y0[0] and ev("() => board.items.i2.x") == 2 * 340 + 500
        assert any("skipped" in t for t in ev("() => TL")), ev("() => TL")
        assert ev("() => !!board.items.agent1") and ev("() => past.length") == 0
        page.keyboard.press("Meta+Shift+z")   # and back again
        assert ev("() => board.items.i1.y") != y0[0]
        assert not errors, errors
        browser.close()


# ---- B-07, B-08, B-09 -------------------------------------------------------------------------------------------------------------
def test_b07_cmd_z_in_a_studio_leaves_the_boards_annotation(tmp_path):
    items = {f"i{n}": pic(n, n * 340) for n in range(4)}
    items["f1"] = {"type": "fake", "x": 0, "y": 600, "w": 480, "h": 300}
    with serve(tmp_path, items, plugin=True) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        page.wait_for_function("() => window.MODES && document.querySelector('.plg[data-id=f1]')", timeout=10000)
        annotate(page, port, text="on the board")
        page.keyboard.press("Escape"); page.keyboard.press("Escape"); page.wait_for_function("() => !hyAnnot.active")
        f = box(page, ".plg[data-id=f1]"); page.mouse.dblclick(f["cx"], f["cy"])
        page.wait_for_function("() => document.getElementById('dock').classList.contains('plg-mode')")
        page.keyboard.press("Meta+z"); page.wait_for_timeout(600)
        assert ev("() => __studioUndo") == 1 and len(threads(port)) == 1   # the Studio's ⌘Z, the board's annotation stays
        page.keyboard.press("Escape"); page.wait_for_function("() => !document.getElementById('dock').classList.contains('plg-mode')")
        page.keyboard.press("Meta+z"); wait(lambda: not threads(port), "back on the board, ⌘Z undoes the annotation")
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("kind", ["vidOpen", "pdfOpen"])
def test_b08_the_viewers_take_every_key(tmp_path, kind):
    with serve(tmp_path) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        ev("() => { const b = snap(); board.items.i3.x += 10; commit(b); sel = new Set(['i0']); render(); }")
        n = ev("() => past.length")
        ev(f"() => {kind}('i0')"); page.wait_for_function("() => !!VBIG")
        for k in ("c", "Meta+z", "n", "Meta+d"):   # nothing of these reaches the board under the viewer
            page.keyboard.press(k); page.wait_for_timeout(200)
            assert ev("() => hyAnnot.active") is None, k
            assert ev("() => [past.length, Object.keys(board.items).length]") == [n, 6], k
        page.keyboard.press("Escape"); page.wait_for_function("() => !VBIG")   # its own Esc still closes it
        assert not errors, errors
        browser.close()


def test_b09_space_pans_with_the_annotation_tool(tmp_path):
    with serve(tmp_path) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        page.keyboard.press("c"); page.wait_for_function("() => hyAnnot.active === 'comment'")
        c0 = ev("() => [cam.x, cam.y]")
        page.mouse.move(700, 500); page.keyboard.down(" "); page.mouse.down(); page.mouse.move(500, 400, steps=8); page.mouse.up(); page.keyboard.up(" ")
        assert ev("() => [cam.x, cam.y]") == [c0[0] + 200, c0[1] + 100]
        assert not ev("() => hyComments.state.draft") and ev("() => hyAnnot.active") == "comment"   # no pin was dropped, the tool stays
        assert not errors, errors
        browser.close()


# ---- B-10 ---------------------------------------------------------------------------------------------------------------------------
def test_b10_move_to_page_carries_the_connectors(tmp_path):
    links = {"c1": {"from": "i2", "to": "i3", "label": "is"}, "c2": {"from": "i1", "to": "i2"}}
    with serve(tmp_path, links=links) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        ev("() => { sel = new Set(['i2', 'i3']); render(); }")
        ev("() => moveToPage(null)")
        page.wait_for_function("() => TL.some(t => t.startsWith('Moved to'))", timeout=15000)
        note = next(t for t in ev("() => TL") if t.startswith("Moved to"))
        assert "arrows dropped: 1" in note, note
        dest = next(pg["id"] for pg in api(port, "/api/pages")["pages"] if pg["id"] != "main")
        there = api(port, f"/api/board?name={dest}")
        cs = list((there.get("links") or {}).values())
        assert [(c["from"], c["to"], c.get("label")) for c in cs] == [("i2", "i3", "is")], cs
        assert not ev("() => board.links && Object.keys(board.links).length")
        # ⌘Z: both connectors back here, the other page loses the things and their connector
        page.keyboard.press("Meta+z")
        page.wait_for_function("() => board.items.i2 && board.links && Object.keys(board.links).length === 2")
        wait(lambda: not (api(port, f"/api/board?name={dest}").get("links") or {}), "the other page lost the connector")
        assert not errors, errors
        browser.close()


# ---- B-13, B-14 ---------------------------------------------------------------------------------------------------------------------
def test_b13_backslash_in_the_app_never_brings_back_the_old_library(tmp_path):
    with serve(tmp_path) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, frame, errors = app_page(browser, port)
        hidden = "() => getComputedStyle(document.getElementById('lib')).display === 'none'"
        assert frame.evaluate(hidden)
        fr = page.evaluate("() => { const r = document.querySelector('#cvFrame').getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; }")
        page.mouse.click(fr["x"] + fr["w"] - 200, fr["y"] + fr["h"] - 150)   # the keyboard in the board's frame
        page.keyboard.press("\\"); page.wait_for_timeout(500)
        assert frame.evaluate(hidden), "the old built-in library came back inside the board"
        page.wait_for_function("() => document.body.classList.contains('cv-only')", timeout=5000)   # ⌘M's: the library page's library closed
        assert not errors, errors
        browser.close()


def test_b14_cmd_f_under_the_viewer_leaves_the_search_alone(tmp_path):
    with serve(tmp_path) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, frame, errors = app_page(browser, port)
        page.wait_for_selector("#list .card"); page.locator("#list .card").nth(0).click()
        page.wait_for_function("() => document.getElementById('viewer').classList.contains('open')")
        page.keyboard.press("Meta+f"); page.wait_for_timeout(500)
        assert page.evaluate("() => document.activeElement.id") != "q"
        page.keyboard.type("q"); page.wait_for_timeout(300)   # the viewer's own key: its verdict, not a letter in the search
        assert page.evaluate("() => document.getElementById('q').value") == ""
        assert page.evaluate("() => document.getElementById('viewer').classList.contains('open')")
        assert not errors, errors
        browser.close()
