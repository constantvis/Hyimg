"""Switching pages on the canvas in a real browser (owner 2026-10-01: after a page switch the frames showed as empty boxes).

The far-view canvases (#lodc, #glc, #lodd) live inside #items; clearing #items on a page switch took them out of the page, the next
far-view draw threw on a missing canvas and nothing was painted. Runs only where Playwright and its Chromium are installed.
"""
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
def png(w=40, h=60):   # a plain white picture
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * w for _ in range(h))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def board(folder, count, first):
    items = {f"i{first + n}": {"path": f"{folder}/{n}.png", "x": n % 6 * 340, "y": n // 6 * 520, "w": 320, "ar": 2 / 3, "crop": None}
             for n in range(count)}
    return {"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    for folder in ("a", "b"):
        (lib / folder).mkdir(parents=True)
        for n in range(12):
            (lib / folder / f"{n}.png").write_bytes(png())
    (state / "boards").mkdir(parents=True)
    (state / "boards/main.json").write_text(json.dumps(board("a", 12, 0)))
    (state / "boards/p2.json").write_text(json.dumps(board("b", 12, 100)))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "A"}, {"id": "p2", "title": "B"}]}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        yield port
    finally:
        process.terminate()
        process.wait(5)
        log.close()


PROBE = """() => {
  const c = document.querySelector('#lodc'); let lit = 0;
  if (c && c.width) { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    for (let i = 0; i < d.length; i += 4 * 31) if (d[i + 3] && d[i] + d[i + 1] + d[i + 2] > 300) lit++; }
  return { page: BOARD, far: LOD.on, canvases: ['#lodc', '#glc', '#lodd'].filter(s => document.querySelector(s)).length,
           frames: document.querySelectorAll('#items .it').length, lit };
}"""


@pytest.mark.parametrize("zoom", [0.1, 1.0])   # far view (pictures drawn into one canvas) and close view (picture elements)
def test_pictures_show_after_switching_pages(server, zoom):
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:   # Playwright installed without its browser
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate(f"() => {{ localStorage.clear(); localStorage.setItem('cv.lod', '1'); localStorage.setItem('cv.cam.main', JSON.stringify({{x: -40, y: -40, z: {zoom}}})); localStorage.setItem('cv.cam.p2', JSON.stringify({{x: -40, y: -40, z: {zoom}}})); }}")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        for target in ("p2", "main"):
            page.evaluate(f"() => switchPage('{target}')")
            page.wait_for_function(f"() => BOARD === '{target}' && Object.keys(board.items).length === 12")
            if zoom < 0.3:   # far view: wait until the thumbnails are painted (a fixed pause failed on a busy machine)
                page.wait_for_function(f"() => ({PROBE.strip()})().lit > 0", timeout=15000)
            else:
                page.wait_for_timeout(500)
            state = page.evaluate(PROBE)
            assert state["canvases"] == 3, state
            assert state["frames"] == 12, state
            assert state["far"] == (zoom < 0.3), state
            if state["far"]:
                assert state["lit"] > 0, state   # the white test pictures are painted into the far canvas
        assert not errors, errors
        browser.close()



GROUP = "() => { board.groups.g1 = { title: 'Пары', x: -1300, y: -1300, w: 3440, h: 3420, members: Object.keys(board.items) }; sel = new Set(); render(); }"
# zoomed out: the group's left side 300 px right of the library panel, its top off screen, the other edges on screen; zoomed in: it covers the screen
CAM = "z => { cam.x = z < 0.5 ? -1300 - (INSET + 300) / z : -1000; cam.y = -400; cam.z = z; renderCam(); }"
SCREEN = "([x, y]) => { const r = stage.getBoundingClientRect(); return [(x - cam.x) * cam.z + r.left, (y - cam.y) * cam.z + r.top]; }"


def drag(page, a, b):   # press at board point a, let go at board point b
    (x0, y0), (x1, y1) = page.evaluate(SCREEN, a), page.evaluate(SCREEN, b)
    assert page.evaluate("([x, y]) => document.elementFromPoint(x, y).closest('#stage') !== null", [x0, y0])
    page.mouse.move(x0, y0); page.mouse.down(); page.mouse.move((x0 + x1) / 2, (y0 + y1) / 2, steps=5); page.mouse.move(x1, y1, steps=5); page.mouse.up()
STATE = """() => ({ sel: [...sel].map(id => board.groups[id] ? id : [board.items[id].x, board.items[id].y]), x: Math.round(board.groups.g1.x),
  paused: document.querySelector('.grp[data-id=g1]').classList.contains('paused'), handles: document.querySelectorAll('#handles [data-resize]').length })"""


def test_big_group_selection_pauses(server):
    """Owner 2026-10-02: zoomed into a selected group and tried to move a picture, the whole group moved. While the group covers the
    whole screen its selection pauses: it stays selected but a press on its empty inside draws a selection frame, Delete leaves it,
    and with an edge back on screen it is an ordinary selected group again. Taller than the screen with the other edges visible is
    not enough, but an edge within 150 px of the screen side counts as outside (owner, same day)."""
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 2000, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.lod', '0'); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        page.evaluate("() => Object.values(board.items).forEach((it, n) => { it.x = n % 6 * 340; it.y = Math.floor(n / 6) * 520; it.w = 320; it.ar = 2 / 3; })")
        page.evaluate(GROUP)
        page.evaluate(CAM, 0.3)
        page.evaluate("() => { sel = new Set(['g1']); render(); }")
        state = page.evaluate(STATE)
        assert state["sel"] == ["g1"] and not state["paused"] and state["handles"] > 0, state   # top off screen, the other edges visible
        # zoomed in until the group covers the screen: still selected, paused, no handles, Delete does nothing
        page.evaluate(CAM, 1)
        state = page.evaluate(STATE)
        assert state["sel"] == ["g1"] and state["paused"] and state["handles"] == 0, state
        page.keyboard.press("Delete")
        assert page.evaluate("() => !!board.groups.g1 && Object.keys(board.items).length === 12")
        # edges 100 px inside the screen still pause it, 200 px inside do not
        def edges_in(px):
            page.evaluate("px => { const r = stage.getBoundingClientRect(), g = board.groups.g1; cam.z = 1; cam.x = g.x - INSET - px; cam.y = g.y - px; renderCam(); }", px)
            return page.evaluate(STATE)["paused"]
        assert edges_in(100) and not edges_in(200)
        # zoomed back out the selection works again
        page.evaluate(CAM, 0.3)
        state = page.evaluate(STATE)
        assert state["sel"] == ["g1"] and not state["paused"] and state["handles"] > 0, state
        # paused, its empty inside (board point -150, 300) draws a selection frame, the group stays where it was
        page.evaluate(CAM, 1)
        drag(page, [-150, 300], [100, 390])
        state = page.evaluate(STATE)
        assert state["sel"] == [[0, 0]] and state["x"] == -1300, state   # the picture top left, the frame touched it
        # with edges on screen it picks up from its inside and moves, as before
        page.evaluate(CAM, 0.3)
        drag(page, [-150, 300], [180, 300])
        state = page.evaluate(STATE)
        assert state["sel"] == ["g1"] and state["x"] == -970, state
        assert not errors, errors
        browser.close()


RATIO = """() => { const s = cropState, c = s.c; return { r: (c[2] - c[0]) * s.full.w / ((c[3] - c[1]) * s.full.h), on: [...document.querySelectorAll('#crop .cratio button.on')].map(b => b.textContent),
  labels: [...document.querySelectorAll('#crop .cratio button[data-ratio]')].map(b => b.textContent).filter(Boolean), c }; }"""


def test_crop_ratios_lock_the_frame(server):
    """Owner 2026-10-02: in crop mode a bar of standard proportions over the frame (1:1, 3:4 turned to 4:3 and others), free by
    default; with a ratio picked the frame resizes only in that ratio."""
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.lod', '0'); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        page.evaluate("() => { const id = Object.keys(board.items).find(k => board.items[k].x === 340 && board.items[k].y === 0); cam.x = 100; cam.y = -300; cam.z = 1; renderCam(); startCrop(id); }")
        st = page.evaluate(RATIO)
        assert st["on"] == ["Свободно"] and st["labels"] == ["Свободно", "1:1", "4:5", "3:4", "2:3", "9:16"], st
        click = lambda label: page.locator("#crop .cratio button", has_text=label).first.click()
        def corner(c, dx, dy):
            box = page.locator(f"#crop .h[data-c={c}]").bounding_box(); x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + dx / 2, y + dy / 2, steps=4); page.mouse.move(x + dx, y + dy, steps=4); page.mouse.up()
        click("1:1")
        st = page.evaluate(RATIO); assert abs(st["r"] - 1) < 1e-6 and st["on"] == ["1:1"], st
        corner("se", -120, -20)                      # mostly sideways: still square
        st = page.evaluate(RATIO); assert abs(st["r"] - 1) < 1e-6 and st["c"][2] - st["c"][0] < 0.9, st
        click("3:4")
        assert abs(page.evaluate(RATIO)["r"] - 0.75) < 1e-6
        page.keyboard.press("x")                     # turned: 4:3, the labels follow
        st = page.evaluate(RATIO); assert abs(st["r"] - 4 / 3) < 1e-6 and st["on"] == ["4:3"] and "16:9" in st["labels"], st
        corner("nw", 40, 70)
        assert abs(page.evaluate(RATIO)["r"] - 4 / 3) < 1e-6
        page.keyboard.press("r")                     # the whole frame in the ratio: the biggest 4:3 piece
        st = page.evaluate(RATIO); assert abs(st["r"] - 4 / 3) < 1e-6 and abs(st["c"][2] - st["c"][0] - 1) < 1e-6, st
        click("Свободно")
        corner("se", -100, 10)                       # free again: the proportion changes
        st = page.evaluate(RATIO); assert abs(st["r"] - 4 / 3) > 0.05 and st["on"] == ["Свободно"], st
        page.keyboard.press("Enter")
        assert page.evaluate("() => cropState") is None
        assert not errors, errors
        browser.close()


NOTE = """() => { const n = Object.values(board.items).find(i => i.type === 'note'); return n && { to: n.to, reach: n.reach, x: n.x, y: n.y, w: n.w }; }"""


def test_n_on_one_picture_puts_a_note_above_with_an_arrow(server):
    """Owner 2026-10-02: one picture selected, N gives a note above it with an arrow to it, not a zone; several still get a zone."""
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.lod', '0'); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        pic = page.evaluate("() => { const id = Object.keys(board.items).find(k => board.items[k].x === 340 && board.items[k].y === 520); sel = new Set([id]); render(); return [id, board.items[id]]; }")
        page.keyboard.press("n"); page.keyboard.type("про этот кадр"); page.keyboard.press("Escape")
        n = page.evaluate(NOTE)
        assert n["to"] == [pic[0]] and n["reach"] is None, n
        assert n["y"] + n["w"] < pic[1]["y"] and abs(n["x"] + n["w"] / 2 - (pic[1]["x"] + pic[1]["w"] / 2)) <= 1, n   # above, centred
        page.evaluate("() => { Object.keys(board.items).filter(k => board.items[k].type === 'note').forEach(k => delete board.items[k]); sel = new Set(Object.keys(board.items).slice(0, 2)); render(); }")
        page.keyboard.press("n"); page.keyboard.type("про оба"); page.keyboard.press("Escape")
        n = page.evaluate(NOTE)
        assert n["reach"] and not n["to"], n
        assert not errors, errors
        browser.close()


def test_notes_lie_over_pictures_added_later(server):
    """Owner 2026-10-02: an agent added frames after a note and they covered it; notes, headings and timelines lie over pictures."""
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.lod', '0'); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        hit = page.evaluate("""() => {
          cam.x = -100; cam.y = -100; cam.z = 1; renderCam();
          board.items.nz = { type: 'note', text: 'заметка', x: 100, y: 100, w: 300, fs: 30, size: 2, h: 0, color: 'yellow', reach: null, to: [] };
          board.items.tz = { type: 'text', text: 'Заголовок', x: 100, y: 500, fs: 60 };
          board.items.later = { ...board.items[Object.keys(board.items)[0]], x: 0, y: 0, w: 900 };   // added last, covers both
          render();
          const r = stage.getBoundingClientRect(), at = (x, y) => document.elementFromPoint(r.left + (x - cam.x) * cam.z, r.top + (y - cam.y) * cam.z).closest('.it, .note, .tx');
          return [at(150, 150).dataset.id, at(130, 530).dataset.id];
        }""")
        assert hit == ["nz", "tz"], hit
        browser.close()


def test_space_hand_mode_ends_when_the_window_loses_focus(server):
    """Owner 2026-10-02: after space the board only panned, nothing could be moved, until space was pressed again: its keyup was
    lost while the window was elsewhere. Losing focus ends the hand mode."""
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        page.keyboard.down(" ")
        assert page.evaluate("() => space && stage.classList.contains('space')")
        page.evaluate("() => window.dispatchEvent(new Event('blur'))")   # the keyup goes to another window
        assert page.evaluate("() => !space && !stage.classList.contains('space')")
        browser.close()


def test_note_links_by_cells_match_and_arrow_line_clears(server):
    """Owner 2026-10-02: dragging a note lagged (every redraw tested every note against every frame) and the dashed line of a pulled
    arrow stayed after letting go. The cell index finds the same pictures; letting go of an arrow leaves no dashed line."""
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        same = page.evaluate("""() => {
          board.items.na = { type: 'note', text: 'а', x: 300, y: 300, w: 320, fs: 30, size: 2, h: 0, color: 'yellow', reach: { l: 400, t: 400, r: 2600, b: 600 }, to: [] };
          board.items.nb = { type: 'note', text: 'б', x: 1900, y: 900, w: 320, fs: 30, size: 2, h: 0, color: 'yellow', reach: null, to: [] };
          board.items.nc = { type: 'note', text: 'в', x: 9000, y: 9000, w: 320, fs: 30, size: 2, h: 0, color: 'yellow', reach: null, to: [] };
          render(); const near = picIndex(), flat = m => JSON.stringify([...m.entries()].map(([k, v]) => [k, [...v].sort()]).sort());
          return ['na', 'nb', 'nc'].map(n => [linksOf(n).size, flat(linksOf(n)) === flat(linksOf(n, near))]);
        }""")
        assert all(ok for _, ok in same) and same[0][0] > 0 and same[1][0] > 0 and same[2][0] == 0, same
        dashed = page.evaluate("""() => {
          const p = { x: 500, y: 500 }; sel = new Set(['nb']); render();
          drag = { mode: 'connect', id: 'nb', before: snap(), p, cur: { x: 2600, y: 2600 }, target: null }; renderLinks();
          const during = document.querySelectorAll('#links line[stroke-dasharray]').length;
          stage.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
          return [during, document.querySelectorAll('#links line[stroke-dasharray]').length];
        }""")
        assert dashed == [1, 0], dashed
        browser.close()


def test_hovered_arrow_shows_a_minus_that_removes_it(server):
    """Owner 2026-10-02: a round − on an arrow under the pointer, one click takes the arrow off, no select-then-Delete."""
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        page.evaluate("""() => {
          const pic = Object.keys(board.items).find(k => board.items[k].x === 1700 && board.items[k].y === 0);
          board.items.na = { type: 'note', text: 'а', x: 600, y: 700, w: 300, fs: 30, size: 2, h: 0, color: 'yellow', reach: null, to: [pic] };
          cam.x = -100; cam.y = -100; cam.z = 0.5; renderCam(); sel = new Set(); render(); renderLinks();
        }""")
        box = page.locator("#links .del").bounding_box()
        assert page.evaluate("() => getComputedStyle(document.querySelector('#links .del')).opacity") == "0"
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2); page.wait_for_timeout(250)
        assert page.evaluate("() => getComputedStyle(document.querySelector('#links .del')).opacity") == "1"
        page.mouse.down(); page.mouse.up()
        assert page.evaluate("() => board.items.na.to.length") == 0
        assert page.locator("#links .del").count() == 0
        browser.close()


def test_note_zone_lies_under_the_pictures(server):
    """Owner 2026-10-03: the dashed zone of a selected note tinted the frames yellow; it lies under them."""
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        page.evaluate("""() => {
          board.items.nz = { type: 'note', text: 'зона', x: -400, y: 0, w: 320, fs: 30, size: 2, h: 0, color: 'yellow', reach: { l: 200, t: 200, r: 1200, b: 400 }, to: [] };
          cam.x = -700; cam.y = -300; cam.z = 0.8; renderCam(); sel = new Set(); render(); renderLinks();
        }""")
        pt = page.evaluate("""() => { const id = Object.keys(board.items).find(k => board.items[k].x === 340 && board.items[k].y === 0), q = EL.get(id).getBoundingClientRect();
          return [q.x + q.width / 2, q.y + q.height / 2]; }""")
        page.wait_for_timeout(400)
        px = lambda: page.screenshot(clip={"x": pt[0], "y": pt[1], "width": 1, "height": 1})
        before = px()
        page.evaluate("() => { sel = new Set(['nz']); render(); renderLinks(); }"); page.wait_for_timeout(200)
        assert page.locator("#zones rect").count() == 1
        assert px() == before   # the picture looks the same with its note selected
        browser.close()


def test_copy_puts_a_link_and_paste_keeps_the_frames(server):
    """Owner 2026-10-03: ⌘C gives the link to what is selected (for the agent's chat), ⌘V on the canvas still pastes the frames with
    the same spacing; a pinch never zooms the page."""
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        ctx = browser.new_context(viewport={"width": 1400, "height": 900}); ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        ids = page.evaluate("() => { const ids = Object.keys(board.items).slice(0, 3); sel = new Set(ids); render(); return ids; }")
        page.keyboard.press("Meta+c"); page.wait_for_timeout(300)
        txt = page.evaluate("() => navigator.clipboard.readText()")
        assert "obj=" + ",".join(ids) in txt and txt.startswith(f"http://127.0.0.1:{server}/?view=canvas"), txt
        gaps = lambda keys: page.evaluate("ks => ks.map(k => [board.items[k].x - board.items[ks[0]].x, board.items[k].y - board.items[ks[0]].y])", keys)
        before = gaps(ids)
        page.evaluate("() => { lastPt = { x: 5000, y: 5000 }; }"); page.keyboard.press("Meta+v"); page.wait_for_timeout(400)
        new = page.evaluate(f"() => Object.keys(board.items).filter(k => !{json.dumps(ids)}.includes(k) && board.items[k].x > 4000)")
        assert len(new) == 3 and gaps(sorted(new, key=lambda k: page.evaluate(f"() => board.items['{k}'].x * 10000 + board.items['{k}'].y"))) == sorted(before), (new, before)
        prevented = page.evaluate("() => { const e = new WheelEvent('wheel', { ctrlKey: true, deltaY: -10, cancelable: true, bubbles: true }); document.querySelector('#info').dispatchEvent(e); return e.defaultPrevented; }")
        assert prevented   # ctrl + wheel (a pinch) outside the board is stopped too: the page does not zoom
        browser.close()


def test_opacity_slider_and_digit_keys(server):
    """Owner 2026-10-03: a slider over the selected picture sets its opacity, to lay one over another and compare; 1…9 and 0 as in Figma."""
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 12")
        pid = page.evaluate("() => { const id = Object.keys(board.items).find(k => board.items[k].x === 340 && board.items[k].y === 520); cam.x = 0; cam.y = 200; cam.z = 0.8; renderCam(); sel = new Set([id]); render(); return id; }")
        assert page.locator("#handles .tidy .op input").count() == 1
        page.keyboard.press("5"); page.wait_for_timeout(200)
        st = page.evaluate(f"() => [board.items['{pid}'].opacity, EL.get('{pid}').style.opacity, document.querySelector('.tidy .op b').textContent]")
        assert st == [0.5, "0.5", "50%"], st
        page.evaluate("() => { const r = document.querySelector('.tidy [data-op]'); r.value = 30; r.dispatchEvent(new Event('input', { bubbles: true })); r.dispatchEvent(new Event('change', { bubbles: true })); }")
        page.wait_for_timeout(200)
        assert page.evaluate(f"() => board.items['{pid}'].opacity") == 0.3
        page.keyboard.press("0"); page.wait_for_timeout(200)
        assert page.evaluate(f"() => 'opacity' in board.items['{pid}']") is False   # 100 % leaves no field behind
        page.keyboard.press("Meta+z"); page.wait_for_timeout(200)
        assert page.evaluate(f"() => board.items['{pid}'].opacity") == 0.3   # each step is one version
        browser.close()


def test_panels_over_the_board_keep_their_clicks(server):
    """Owner 2026-10-03: a double click on the open notifications started the crop of the frame under the panel. Buttons and panels
    over the board keep their double clicks, right clicks and wheel: the board under them does not crop, add a title, open its menu or move."""
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && BOARD === 'main'", timeout=15000)
        page.click("#bntf"); page.wait_for_selector("#ntf.open")
        before = page.evaluate("() => [Object.keys(board.items).length, JSON.stringify(cam)]")
        for q in ["#ntf", "#bntf", "#bhist", "#dock"]:
            b = page.locator(q).bounding_box(); x, y = b["x"] + b["width"] / 2, b["y"] + min(b["height"] / 2, 30)
            page.mouse.dblclick(x, y)
            page.mouse.move(x, y); page.mouse.wheel(0, 300)
            page.mouse.click(x, y, button="right")
            page.wait_for_timeout(150)
            assert page.evaluate("() => !cropState && !$('#ctx').classList.contains('open') && !document.querySelector('.tx textarea')"), q
            assert page.evaluate("() => [Object.keys(board.items).length, JSON.stringify(cam)]") == before, q
            if q != "#ntf" and not page.locator("#ntf.open").count(): page.click("#bntf")
        # the board itself still answers: a double click on empty paper starts a title
        page.keyboard.press("Escape"); page.mouse.dblclick(700, 800)
        page.wait_for_selector(".tx textarea")
        assert not errors, errors
        browser.close()


def test_library_right_click_shows_the_frame_on_the_board(server, tmp_path):
    """Owner 2026-10-03: a right click on a library card offers «Показать на доске» when the frame is on a board. The canvas opens
    (from the library alone too), switches to the page that has the frame, selects it and puts it in view."""
    (tmp_path / "lib/b/odd.png").write_bytes(png(50, 70))   # the test pictures are all the same and the library shows them once
    p2 = json.loads((tmp_path / "state/boards/p2.json").read_text())
    p2["items"]["i200"] = {"path": "b/odd.png", "x": 0, "y": 1200, "w": 320, "ar": 5 / 7, "crop": None}
    (tmp_path / "state/boards/p2.json").write_text(json.dumps(p2))
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/")
        page.evaluate("() => localStorage.setItem('view', 'lib')"); page.reload()
        page.wait_for_function("() => typeof view !== 'undefined' && view.some(i => i.path === 'b/odd.png') && ONBOARD.has('b/odd.png')", timeout=15000)
        card = lambda path: page.locator(f".card[data-i='{page.evaluate('p => view.findIndex(i => i.path === p)', path)}']")
        other = page.evaluate("() => view.find(i => i.path !== 'b/odd.png').path")
        page.evaluate("p => ONBOARD.delete(p)", other)   # as if this frame were on no page
        def right_click(path):   # the list draws again once the folders dock and draws its batches lazily: find, bring into view, retry
            for _ in range(5):
                try: card(path).scroll_into_view_if_needed(timeout=2000); card(path).click(button="right", timeout=3000); return
                except playwright.Error: page.wait_for_timeout(300)
            raise AssertionError(f"no card for {path}")
        right_click(other)
        assert page.locator("#lctx.open button:disabled").inner_text() == "Этого кадра нет на досках"
        page.keyboard.press("Escape"); assert not page.locator("#lctx.open").count()
        right_click("b/odd.png")
        page.click("#lctx.open >> text=Показать на доске")
        assert not page.locator("#lctx.open").count() and page.evaluate("() => document.body.classList.contains('cv-on')")
        frame = page.frame_locator("#cvFrame").locator("body")   # wait for the canvas inside the iframe
        frame.wait_for(state="attached")
        cv = next(f for f in page.frames if "/canvas" in f.url)
        cv.wait_for_function("() => BOARD === 'p2' && sel.size === 1 && sel.has('i200')", timeout=15000)
        assert not errors, errors
        browser.close()


def test_an_agent_on_any_page_reads_first_to_go_to_agent(server):
    """Owner 2026-10-03: an agent that opens the board in a browser first reads that its instructions are at /agent, that it starts
    there and changes the board with hy.py, not with the mouse. The page text and the accessibility tree (what agents read) both
    begin with that note; the owner does not see it and Tab does not land on it."""
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        for url in ["/?view=canvas&page=p2", "/canvas", "/v1"]:
            page.goto(f"http://127.0.0.1:{server}{url}")
            page.wait_for_function("() => document.querySelector('.agentnote a').textContent.endsWith('/agent')")
            text = page.evaluate("() => document.body.innerText").strip()
            assert text.startswith(f"ИИ-агенту: сначала открой инструкцию http://127.0.0.1:{server}/agent"), (url, text[:120])
            assert "а не мышью" in text.split("\n")[0], url
            first = page.locator("body").aria_snapshot().splitlines()[0]
            assert "Для ИИ-агента" in first, (url, first)
            box = page.locator(".agentnote").bounding_box(); assert box["width"] <= 1 and box["height"] <= 1, url
            page.keyboard.press("Tab"); assert not page.evaluate("() => !!document.activeElement.closest('.agentnote')"), url
        browser.close()
    guide = urllib.request.urlopen(f"http://127.0.0.1:{server}/agent").read().decode()
    assert "мышью не трогай" in guide and "hy.py map" in guide


def test_notes_stack_at_the_top_in_one_look(server):
    """Owner 2026-10-04: notes came at the bottom from the library and at the top from the canvas, in two looks. Now one stack at the top
    centre of the free part: the canvas inside the library sends its notes up to it; red for an error, blue for news, green for success;
    glass with blur; they leave one after another, the oldest first. Owner 2026-10-05: a stack as on the iPhone's lock screen, the newest in
    front, the older ones tucked behind it; the pointer on the stack fans them out into a list (newest on top) and holds them."""
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/?view=canvas")
        page.wait_for_function("() => typeof hyToast === 'function'")
        page.wait_for_selector("#cvFrame")
        cv = next(f for f in page.frames if "/canvas" in f.url)
        cv.wait_for_function("() => typeof BOARD !== 'undefined' && BOARD === 'main'", timeout=15000)
        cv.evaluate("() => toast('Не получилось скопировать картинку')"); page.wait_for_timeout(150)
        cv.evaluate("() => toast('Версия сохранена')"); page.wait_for_timeout(150)
        page.evaluate("() => libNote('В библиотеке новые кадры: 2')")
        page.wait_for_function("() => document.querySelectorAll('#hyToasts .ht').length === 3")
        page.wait_for_timeout(500)
        assert not cv.evaluate("() => !!document.querySelector('#hyToasts')"), "the canvas has no stack of its own inside the library"
        kinds = page.evaluate("() => [...document.querySelectorAll('#hyToasts .ht')].map(e => e.className.split(' ')[1])")
        assert kinds == ["error", "success", "info"], kinds
        front = page.evaluate("() => { const L = [...document.querySelectorAll('#hyToasts .ht')]; return L.reduce((a, e) => +e.style.zIndex > +a.style.zIndex ? e : a).className }")
        assert "info" in front, front   # the newest stands in front
        tops = page.evaluate("() => [...document.querySelectorAll('#hyToasts .ht')].map(e => Math.round(e.getBoundingClientRect().top))")
        assert max(tops) < 60, tops   # folded: all at the top, one behind the other
        box = page.evaluate("() => { const r = document.querySelector('#hyToasts').getBoundingClientRect(); return [r.left + r.width / 2, r.top + 10] }")
        page.mouse.move(*box); page.wait_for_timeout(600)
        fanned = page.evaluate("() => [...document.querySelectorAll('#hyToasts .ht')].map(e => Math.round(e.getBoundingClientRect().top))")
        assert fanned[2] < fanned[1] < fanned[0], fanned   # fanned out: the newest on top, a list under it
        page.mouse.move(5, 880)
        assert "blur" in page.evaluate("() => getComputedStyle(document.querySelector('#hyToasts .ht')).backdropFilter")
        cols = page.evaluate("() => [...document.querySelectorAll('#hyToasts .ht i')].map(e => getComputedStyle(e).backgroundColor)")
        assert len(set(cols)) == 3, cols
        page.evaluate("() => hyToast('Версия сохранена')")   # the same words again: no copy
        assert page.locator("#hyToasts .ht").count() == 3
        # after the pointer leaves they go one after the other, the oldest (the error) first, the newest last
        page.wait_for_function("() => document.querySelectorAll('#hyToasts .ht').length === 2", timeout=8000)
        assert "error" not in page.evaluate("() => [...document.querySelectorAll('#hyToasts .ht')].map(e => e.className).join()")
        page.wait_for_function("() => !document.querySelectorAll('#hyToasts .ht').length", timeout=8000)
        # a note to act on stays with a × (owner 2026-10-04), a passing one next to it still goes
        cv.evaluate("() => toast('Не сохранилось: сервер не отвечает', 'error', { sticky: true })"); cv.evaluate("() => toast('Скопировано 3', 'info')")
        page.wait_for_timeout(6500)
        assert page.locator("#hyToasts .ht").count() == 1 and page.locator("#hyToasts .ht.error .x").is_visible()
        page.click("#hyToasts .ht .x"); page.wait_for_function("() => !document.querySelectorAll('#hyToasts .ht').length", timeout=3000)
        assert not errors, errors
        browser.close()


def test_one_side_panel_at_a_time(server):
    """Owner 2026-10-04: the bell, keys, history and settings open on the right one at a time: pressing one closes the one before,
    nothing lies on top of the frame card, which hides while a panel is open and comes back after."""
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && BOARD === 'main' && Object.keys(board.items).length")
        page.evaluate("() => { sel = new Set([Object.keys(board.items)[0]]); render(); }")
        shown = lambda q: page.evaluate(f"() => {{ const e = document.querySelector('{q}'); return !!e && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0 }}")
        page.wait_for_function("() => getComputedStyle(document.querySelector('#info')).display !== 'none'")
        panels = {"#bntf": "#ntf", "#bkeys": "#keys", "#bhist": "#hist", "#bset": "#sets"}
        for b, q in panels.items():
            page.click(b); page.wait_for_timeout(150)
            open_now = [x for x in panels.values() if shown(x)]
            assert open_now == [q], (b, open_now)
            assert not shown("#info"), f"the frame card stays hidden while {q} is open"
        page.click("#bset"); page.wait_for_timeout(150)
        assert not [x for x in panels.values() if shown(x)] and shown("#info")
        # a click past the open panel closes it (owner 2026-10-04) ...
        page.click("#bset"); page.mouse.click(300, 700); page.wait_for_timeout(150)
        assert not shown("#sets")
        # ... but not while a saved version is looked at: the history stays with it
        page.click("#bhist"); page.evaluate("() => { PREV = { id: 'v', back: board, backSel: [] }; }")
        page.mouse.click(300, 700); page.wait_for_timeout(150)
        assert shown("#hist")
        page.evaluate("() => exitPreview()"); page.mouse.click(300, 700); page.wait_for_timeout(150)
        assert not shown("#hist")
        # in the library page, a click in the library closes the canvas's panel
        page.goto(f"http://127.0.0.1:{server}/?view=panel")
        cv = next(f for f in page.frames if "/canvas" in f.url)
        cv.wait_for_function("() => typeof BOARD !== 'undefined' && BOARD === 'main'", timeout=15000)
        cv.click("#bset"); cv.wait_for_selector("#sets.open")
        page.mouse.click(60, 400); page.wait_for_timeout(300)
        assert not cv.evaluate("() => document.querySelector('#sets').classList.contains('open')")
        assert not errors, errors
        browser.close()


def test_settings_are_one_for_the_whole_app(tmp_path):
    """Owner 2026-10-04: «the theme must not change with the project; the settings are one for the whole app, take the current ones of
    Studio North and make it work in a standard way»; and «one look is enough». Two projects share one settings file: a change made in
    one is what the other opens with, and takes when it comes to the front; what belongs to a project (its page) stays its own."""
    settings = tmp_path / "settings.json"; settings.write_text(json.dumps({"cv.theme": "light", "cv.grain": "0"}))
    ports, procs = [], []
    for name in ("a", "b"):
        lib, state = tmp_path / name / "lib", tmp_path / name / "state"
        (lib / "x").mkdir(parents=True); (lib / "x/0.png").write_bytes(png()); (state / "boards").mkdir(parents=True)
        port = free_port(); ports.append(port)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
        env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(settings), PYTHONDONTWRITEBYTECODE="1")
        procs.append(subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
    try:
        with playwright.sync_playwright() as p:
            try: browser = p.chromium.launch()
            except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
            ctx = browser.new_context(viewport={"width": 1400, "height": 900}); errors = []
            a, b = ctx.new_page(), ctx.new_page()
            for page, port in ((a, ports[0]), (b, ports[1])):
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.add_init_script("try { if (!sessionStorage.getItem('seeded')) { localStorage.setItem('cv.ui', 'studio'); localStorage.setItem('cv.theme', 'dark'); sessionStorage.setItem('seeded', '1'); } } catch {}")
                page.goto(f"http://127.0.0.1:{port}/canvas.html")
                page.wait_for_function("() => typeof BOARD !== 'undefined'", timeout=15000)
            for page in (a, b):   # the file decides, whatever the project kept before; one look
                assert page.evaluate("() => [document.documentElement.dataset.theme, document.documentElement.dataset.ui]") == ["light", "classic"]
                assert not page.locator("#sets [data-set=ui]").count()
            a.click("#bset"); a.click("#sets [data-set=theme] [data-v=dark]")
            for _ in range(50):
                if json.loads(settings.read_text()).get("cv.theme") == "dark": break
                time.sleep(0.1)
            assert json.loads(settings.read_text())["cv.theme"] == "dark" and "cv.page" not in json.loads(settings.read_text())
            b.evaluate("() => window.dispatchEvent(new Event('focus'))")
            b.wait_for_function("() => document.documentElement.dataset.theme === 'dark'", timeout=5000)
            b.reload(); b.wait_for_function("() => typeof BOARD !== 'undefined'", timeout=15000)
            assert b.evaluate("() => document.documentElement.dataset.theme") == "dark"
            assert not errors, errors
            browser.close()
    finally:
        for pr in procs: pr.terminate(); pr.wait(5)


def test_bell_shows_agent_news_and_jumps_there(server):
    """Owner 2026-10-03: the bell next to the history has a red dot while agents have news; the list shows the words and previews,
    a click opens that page and puts what was added in view, selected; opening the list reads the news."""
    req = urllib.request.Request(f"http://127.0.0.1:{server}/api/notifications", method="POST", headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{server}"},
                                 data=json.dumps({"action": "add", "title": "Собрал партию на второй странице", "text": "3 кадра", "who": "Codex", "page": "p2",
                                                  "ids": ["i103", "i104", "i105"], "previews": ["b/3.png", "b/4.png", "b/5.png"]}).encode())
    urllib.request.urlopen(req)
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && BOARD === 'main' && document.querySelector('#bntf.dot')", timeout=15000)
        page.click("#bntf")
        page.wait_for_selector("#ntf.open .nt")
        assert "Собрал партию на второй странице" in page.inner_text("#ntf") and "Codex" in page.inner_text("#ntf")
        assert page.locator("#ntf .nt .pv img").count() == 3
        assert not page.locator("#bntf.dot").count(), "opening the list reads the news"
        page.click("#ntf .nt")
        page.wait_for_function("() => BOARD === 'p2' && sel.size === 3 && ['i103', 'i104', 'i105'].every(i => sel.has(i))", timeout=15000)
        assert not page.locator("#ntf.open").count()
        assert json.loads(urllib.request.urlopen(f"http://127.0.0.1:{server}/api/notifications").read())["unread"] == 0
        assert not errors, errors
        browser.close()



def test_plate_home_project_page_and_the_pages_menu(server):
    """Owner 2026-10-04: «Home > File > Page» on a plate at the top left like the buttons on the right; the project's name cut at
    100 px and whole under the mouse; the page switched from there; no cross in the list, «Переименовать» and «Удалить» with icons on
    the right click. The house asks the Mac app for Home; in a browser there is no house."""
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/canvas.html")
        page.wait_for_function("() => typeof BOARD !== 'undefined' && BOARD === 'main'", timeout=15000)
        assert not page.locator("#cHome").is_visible() and page.locator("#cPageName").inner_text() == "A"
        page.wait_for_function("() => document.querySelector('#cProj').textContent === 'lib'")
        assert page.locator("#cProj").bounding_box()["width"] <= 100.5
        assert not page.locator("#bpage").is_visible(), "one switch of pages, at the top"
        page.click("#cPage"); page.wait_for_selector("#pages.open")
        assert page.locator("#pages").bounding_box()["y"] > page.locator("#crumb").bounding_box()["y"], "the list opens down from the plate"
        assert not page.locator("#pages .x, #pages [data-del]").count(), "no cross in the list"
        page.locator("#pages .row", has_text="B").click(button="right")
        assert page.locator("#ctx [data-act]").all_inner_texts() == ["Переименовать", "Удалить страницу"]
        assert page.locator("#ctx [data-act] svg").count() == 2
        page.locator("#ctx [data-act=ren]").click()
        page.locator("#pages input").fill("Бэ"); page.keyboard.press("Enter")
        page.wait_for_function("() => pages.some(p => p.id === 'p2' && p.title === 'Бэ')")
        page.locator("#pages .row", has_text="Бэ").click()
        page.wait_for_function("() => BOARD === 'p2' && document.querySelector('#cPageName').textContent === 'Бэ'", timeout=5000)
        if not page.locator("#pages.open").count(): page.click("#cPage")
        page.locator("#pages .row", has_text="A").click(button="right")
        page.once("dialog", lambda d: d.accept())
        page.locator("#ctx [data-act=del]").click()
        page.wait_for_function("() => pages.length === 1 && pages[0].id === 'p2'")
        assert not errors, errors
        # inside the app: the house is there, the plate starts past the window's buttons, the house asks for Home
        page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => { window.__sent = (window.__sent || []).concat([m]); } } } };")
        page.reload(); page.wait_for_function("() => typeof BOARD !== 'undefined'")
        assert page.locator("#crumb").bounding_box()["x"] >= 80
        page.wait_for_function("() => (window.__sent || []).some(m => m.action === 'canvasReady')")   # drawn: the app starts the entrance
        ready = [m for m in page.evaluate("window.__sent") if m["action"] == "canvasReady"]
        assert len(ready) == 1 and "кадр" in ready[0]["text"], ready
        page.click("#cHome"); assert [m for m in page.evaluate("window.__sent") if m["action"] not in ("canvasReady", "crumb", "log", "dragband")] == [{"action": "home"}]   # dragband: the window's drag zones, sent whenever the plates settle
        browser.close()
