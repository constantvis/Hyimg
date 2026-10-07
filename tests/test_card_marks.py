"""The marks on a board card, one system (owner 2026-10-06: «inconsistencies in item badges across the board, padding rules, sizing,
disappearing rules»; «с логикой педингов и размера такая беда что они тут аж пересекаются эти элементы»), with the numbers the owner set
in a lab the same day, and «Open in <App>» on a card's right-click menu («maybe you can also see what's the default app to be opened in
so you can right away write it there»).

- every mark (the kind pills ▶ 0:07, PSD, ‹ 1 / 3 ›, the ♥, the colour grade, crop and copy marks) is one .mk: a 26 px plate at most and
  14 at least, k = the card's short side × .25 / 26, its icon 66% of the plate, 11 px type and 8.5 px inset times k; the note is a plain
  12 px dot with a 1.5 px ring, not scaled
- each in its corner (owner: «top right is the heart; bottom right the file type or play; bottom left the duplicate; top right after the
  heart: colour grading and trim/crop»): note top left; ♥, grade, crop from the top right corner; copy bottom left; kind bottom right
- marks never overlap and never leave their card, selected or not, on any card size: they shrink, then leave one by one
- a mark that leaves scales down to 0 around its corner in .32 s and only then is display:none; one that comes scales up from 0
- the corner squares are 30 px with 7 px corners from 62 px wide; the selection bar is 44 px high
- the far view draws the same geometry as the elements
- the kind pills have an icon before their letters (layers for PSD, a page for PDF, ▶ for video)
- the menu item names the app macOS opens the file with (here HYIMG_DEFAULT_APP stands in for LaunchServices) and `open`s the file
Runs in Chromium and WebKit where Playwright has them, on temporary libraries only."""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_media_files import psd
from test_pdf import make_pdf, COLORS, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
ENGINES = ["chromium", "webkit"]
FFMPEG = shutil.which("ffmpeg")
APP = {"name": "Test Viewer 2026", "path": "/Applications/Test Viewer 2026.app"}
W = 260


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def board():
    items = {
        "p": {"path": "a/layers.psd", "x": 0, "y": 0, "w": W, "ar": 4 / 3, "crop": None},
        "d": {"path": "a/doc.pdf", "x": 300, "y": 0, "w": W, "ar": 0.75, "crop": None},
        "l": {"path": "a/liked.png", "x": 600, "y": 0, "w": W, "ar": 0.75, "crop": [0, 0, 1, 0.9]},
        "l2": {"path": "a/liked.png", "x": 900, "y": 0, "w": W, "ar": 0.75, "crop": None},   # a copy: the copy mark
        "n1": {"type": "note", "text": "a note", "x": 1000, "y": 200, "w": 120, "fs": 12, "color": "blue"},   # lies on l2: the note mark
    }
    if FFMPEG:
        items["v"] = {"path": "a/clip.mp4", "x": 0, "y": 400, "w": W, "ar": 640 / 360, "crop": None}
    return {"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("marks")
    lib, state = tmp / "lib", tmp / "state"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    (lib / "a/layers.psd").write_bytes(psd(64, 48, (230, 160, 40)))
    (lib / "a/doc.pdf").write_bytes(make_pdf(COLORS))
    (lib / "a/liked.png").write_bytes(png((90, 120, 200)))
    (lib / "a/liked.json").write_text(json.dumps({"feedback": {"fav": True, "updated": "2099-01-01 00:00"}}))
    if FFMPEG:
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-t", "7", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(lib / "a/clip.mp4")],
                       check=True, timeout=120)
    (state / "boards/main.json").write_text(json.dumps(board()))
    rec = tmp / "opened.txt"
    opener = tmp / "open"
    opener.write_text(f'#!/bin/sh\nfor a in "$@"; do printf "%s\\t" "$a" >> "{rec}"; done\necho >> "{rec}"\n'); opener.chmod(0o755)
    (tmp / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp / "settings.json"),
               HYIMG_VIDEO_CACHE=str(tmp / "vcache"), HYIMG_DEFAULT_APP=json.dumps(APP), HYIMG_REVEAL_CMD=str(opener), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        yield {"port": port, "opened": rec, "lib": lib}
    finally:
        process.terminate(); process.wait(5); log.close()


def open_board(p, engine, port):
    try:
        browser = getattr(p, engine).launch()
    except Exception as error:
        pytest.skip(f"no {engine} for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html?board=main"
    page.goto(url)
    page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }")
    page.goto(url)
    n = len(board()["items"])
    page.wait_for_function(f"() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === {n} && byPath.size >= 3"
                           " && EL.get('p') && EL.get('p').querySelector('.kd .kt') && EL.get('d').querySelector('.kd .kt') && EL.get('l2').classList.contains('noted')", timeout=20000)
    return browser, page, errors


def cam(page, z, x=-40, y=-40):
    page.evaluate(f"() => {{ cam.x = {x}; cam.y = {y}; cam.z = {z}; renderCam(); render(); }}")
    page.wait_for_timeout(500)


# every shown mark of a card: its box on screen, the card's box, and the computed look
MARKS = """id => { const el = EL.get(id), c = el.getBoundingClientRect();
  return [...el.querySelectorAll('.mk')].filter(m => getComputedStyle(m).display !== 'none').map(m => { const r = m.getBoundingClientRect(), s = getComputedStyle(m);
    return { cls: m.className, n: [...m.classList].find(c => /^mk-/.test(c) && !/^mk-(tl|tr|bl|br|on)$/.test(c)), l: r.left - c.left, t: r.top - c.top, r: c.right - r.right, b: c.bottom - r.bottom,
      w: r.width, h: r.height, rad: s.borderTopLeftRadius, font: s.fontSize, weight: s.fontWeight, bg: s.backgroundColor, ring: s.boxShadow, scale: s.scale,
      icon: (() => { const i = m.querySelector('.kp svg, :scope > svg'); if (!i) return 0; const b = i.getBoundingClientRect(); return Math.round(b.height * 100) / 100; })() }; }); }"""

# a stand-in for the frames plugin's colour grade mark (hyimg-frames grade.js: the same class and the same rule that shows it), so the
# core's law is tested with a full top row without the plugin; the plugin's own tests check the real one
GRADE = """ids => { if (!document.getElementById('grst')) { const st = document.createElement('style'); st.id = 'grst';
    st.textContent = ':is(.it, .plg).graded:not(.mkoff):not([data-mkx~=grade]) > .mk.mk-grade { display: flex; scale: 1; opacity: 1; }'
      + '@starting-style { :is(.it, .plg).graded:not(.mkoff):not([data-mkx~=grade]) > .mk.mk-grade { scale: 0; opacity: 0; } }';
    document.head.appendChild(st); }
  for (const id of ids) { const el = EL.get(id); if (!el.querySelector('.mk-grade')) { const b = document.createElement('button'); b.className = 'mk mk-tr mk-grade'; b.innerHTML = hyGradeIcon(true, 0, 2.2); el.appendChild(b); } el.classList.add('graded'); }
  render(); }"""


def law(w, h):   # the owner's law: k from the short side, 14/26 to 1, floored to .01
    import math
    return max(14 / 26, math.floor(min(1, min(w, h) * .25 / 26) * 100) / 100)


@pytest.mark.parametrize("engine", ENGINES)
def test_every_mark_has_the_owners_size_inset_icon_and_type(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"])
        page.mouse.move(5, 5)
        page.evaluate(GRADE, ["l"])
        for z in (1, 0.6, 0.3):   # 260, 156 and 78 px wide cards
            cam(page, z)
            page.wait_for_timeout(500)
            ids = page.evaluate("() => Object.keys(board.items).filter(i => !board.items[i].type)")
            seen = set()
            for id in ids:
                box = page.evaluate("id => { const r = EL.get(id).getBoundingClientRect(); return [r.width, r.height]; }", id)
                k = page.evaluate("id => +getComputedStyle(EL.get(id)).getPropertyValue('--vbs')", id)
                assert abs(k - law(*box)) < 0.011, (z, id, box, k)   # the card's own law; these cards have room for all their marks
                for m in page.evaluate(MARKS, id):
                    seen.add(m["n"])
                    if m["n"] == "mk-note":   # the plain dot: 12 px (35% of a narrow card), a 1.5 px dark ring, 8.5 px × k in
                        assert abs(m["w"] - min(12, box[0] * .35)) < 0.3 and abs(m["h"] - m["w"]) < 0.3, (z, m)
                        assert abs(float(m["ring"].split()[-1][:-2]) * z - 1.5) < 0.05, (z, m)   # the ring's spread, in board px
                        assert abs(m["l"] - 8.5 * k) < 0.6 and abs(m["t"] - 8.5 * k) < 0.6, (z, k, m)
                        continue
                    assert abs(m["h"] - 26 * k) < 0.6, (z, k, m)   # one plate, by the card's one factor
                    assert abs(m["icon"] - 26 * .66 * k) < 0.6, (z, k, m)   # the icon 66% of it, ▶ too
                    assert m["rad"] == "999px", (z, m)   # round
                    assert m["bg"].replace(" ", "") == "rgba(20,20,22,0.72)", (z, m)
                    if m["n"] == "mk-kind":
                        assert abs(float(m["font"][:-2]) * z * k - 11 * k) < 0.3, (z, m)   # 11 px × k type on screen
                        assert m["weight"] in ("700", "bold"), m
                    corner = m["cls"].split()[1]
                    for side in {"mk-tl": "lt", "mk-tr": "t", "mk-br": "rb", "mk-bl": "b"}[corner]:
                        assert abs(m[side] - 8.5 * k) < 0.6, (z, side, k, m)   # 8.5 px × k from the card's edge
                pills = [m for m in page.evaluate(MARKS, id) if m["n"] == "mk-kind"]
                for m in pills:
                    if box[0] >= 104:   # open: wide, with its icon and letters, 6 px × k on each side
                        assert m["w"] > m["h"] * 1.5, (z, m)
                    else:   # under 104 px wide: folded into a circle the plate's size
                        assert abs(m["w"] - m["h"]) < 0.6, (z, m)
            assert {"mk-kind", "mk-fav", "mk-crop", "mk-dup", "mk-note", "mk-grade"} <= seen, (z, seen)
        # the ring is the 1.5 px the owner set, the plates' gap 3.5 px: the top right row of l, ♥ grade crop from the corner
        cam(page, 1); page.wait_for_timeout(500)
        top = sorted([m for m in page.evaluate(MARKS, "l") if m["cls"].split()[1] == "mk-tr"], key=lambda m: m["r"])
        assert [m["n"] for m in top] == ["mk-fav", "mk-grade", "mk-crop"], top
        for a, b in zip(top, top[1:]):
            assert abs(b["r"] - (a["r"] + a["w"] + 3.5)) < 0.6, (a, b)
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_marks_never_overlap_and_keep_their_corners_selected_or_not(server, engine):
    """(owner 2026-10-06, a small selected liked card: the copy mark lay over the ♥; «why did you move the duplicate up, it must stay
    bottom left») every size from 20 to 400 px, selected or not: no two marks of a card touch (the colour grade too), none leaves the
    card, each is in its corner: the note top left, ♥ grade crop from the top right corner, copy bottom left, the kind bottom right"""
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"])
        page.mouse.move(5, 5)
        # the copy l2 cropped and graded too: note, ♥, grade, crop on top; copy and nothing else below; the PSD and PDF for the kind pills
        page.evaluate("() => { board.items.l2.crop = [0, 0, 1, .95]; board.items.p.crop = [0, 0, 1, .95]; render(); }")
        page.evaluate(GRADE, ["l2", "p"])
        bad = page.evaluate("""async () => {
          const out = [], frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
          document.querySelectorAll('.mk').forEach(m => m.style.transition = 'none');
          for (const id of ['l2', 'p', 'd']) for (const seld of [false, true]) for (const w of [20, 30, 40, 52, 64, 80, 90, 100, 104, 120, 140, 180, 260, 400]) {
            const it = board.items[id]; it.w = w; sel = new Set(seld ? [id] : []); cam.x = it.x - 40; cam.y = it.y - 40; cam.z = 1; renderCam(); render(); await frame();
            const el = EL.get(id), c = el.getBoundingClientRect();
            const ms = [...el.querySelectorAll('.mk')].filter(m => getComputedStyle(m).display !== 'none').map(m => [[...m.classList].find(c => /^mk-/.test(c) && !/^mk-(tl|tr|bl|br|on)$/.test(c)), m.getBoundingClientRect()]);
            for (const [n, r] of ms) if (r.left < c.left - .5 || r.top < c.top - .5 || r.right > c.right + .5 || r.bottom > c.bottom + .5) out.push([id, seld, w, n, 'outside']);
            for (let i = 0; i < ms.length; i++) for (let j = i + 1; j < ms.length; j++) { const a = ms[i][1], b = ms[j][1];
              if (a.left < b.right + 3 && b.left < a.right + 3 && a.top < b.bottom + 3 && b.top < a.bottom + 3) out.push([id, seld, w, ms[i][0], ms[j][0], 'closer than the 3.5 px gap']); }
            const at = n => (ms.find(m => m[0] === n) || [])[1], cy = c.top + c.height / 2, cx = c.left + c.width / 2;
            // the row (top or bottom half) and the side it hangs from (the one nearer to it: the top right row runs inwards past the middle)
            for (const [n, top, right] of [['mk-note', 1, 0], ['mk-fav', 1, 1], ['mk-grade', 1, null], ['mk-crop', 1, null], ['mk-dup', 0, 0], ['mk-kind', 0, 1]]) {
              const r = at(n); if (!r) continue;
              if ((r.top + r.bottom) / 2 < cy !== !!top || (right !== null && (c.right - r.right < r.left - c.left) !== !!right)) out.push([id, seld, w, n, 'wrong corner']); }
            const fv = at('mk-fav'), gr = at('mk-grade'), cr = at('mk-crop');
            if (fv && gr && !(gr.right < fv.left)) out.push([id, seld, w, 'order ♥ grade']);
            if (gr && cr && !(cr.right < gr.left)) out.push([id, seld, w, 'order grade crop']);
            if (fv && cr && !(cr.right < fv.left)) out.push([id, seld, w, 'order ♥ crop']);
          }
          return out; }""")
        assert not bad, bad
        # the owner's case: a selected liked copy about 140 x 100 on screen shows its marks apart
        page.evaluate("() => { board.items.l2.w = 140; board.items.l2.ar = 1.4; board.items.l2.crop = null; sel = new Set(['l2']); cam.x = 860; cam.y = -40; cam.z = 1; renderCam(); render(); }")
        page.wait_for_timeout(500)
        ms = page.evaluate(MARKS, "l2")
        assert {m["n"] for m in ms} >= {"mk-fav", "mk-dup", "mk-grade"}, ms
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_marks_leave_in_the_owners_order(server, engine):
    """grade, copy, crop, note, ♥, then the kind: on a card too small for all, the least needed go first"""
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"])
        f = {"grade": True, "dup": True, "crop": True, "note": True, "fav": True, "kind": True}
        order = page.evaluate("""f => { const seen = []; for (let w = 200; w >= 24; w -= 1) { const x = mkFit(w, w * .75 < 24 ? 24 : w * .75, f).x.split(' ').filter(Boolean);
          x.forEach(n => { if (!seen.includes(n)) seen.push(n); }); } return seen; }""", f)
        assert order == ["grade", "dup", "crop", "note", "fav"][:len(order)] and len(order) >= 4, order
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_mark_leaves_by_scaling_to_zero_in_320_ms_then_display_none_and_comes_back_from_zero(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"])
        page.mouse.move(5, 5)
        cam(page, 1)
        dur = page.evaluate("() => { const s = getComputedStyle(EL.get('p').querySelector('.mk-kind')); return [s.transitionProperty, s.transitionDuration]; }")
        props, durs = [x.strip() for x in dur[0].split(",")], [x.strip() for x in dur[1].split(",")]
        for want in ("scale", "opacity", "display"):
            assert durs[props.index(want)] == "0.32s", dur   # the owner's 320 ms
        trace = """([id, w]) => new Promise(done => { const m = EL.get(id).querySelector('.mk-kind'), out = [], t0 = performance.now();
          board.items[id].w = w; render();
          const step = () => { const s = getComputedStyle(m), t = performance.now() - t0; out.push([s.display, parseFloat(s.scale === 'none' ? 1 : s.scale), parseFloat(s.opacity), t]);
            t < 700 ? requestAnimationFrame(step) : done(out); }; requestAnimationFrame(step); })"""
        out = page.evaluate(trace, ["p", 20])   # under 24 px: every mark goes
        mids = [s for d, s, o, t in out if d != "none" and 0.02 < s < 0.98]
        assert len(mids) >= 3, out   # through in-between sizes
        assert any(d != "none" and t > 250 for d, s, o, t in out), out   # still on its way out after 250 ms: it takes 320
        assert out[-1][0] == "none", out   # then not displayed at all
        assert all(d != "none" for d, s, o, t in out[:3]), out   # not hidden at once
        back = page.evaluate(trace, ["p", W])
        ups = [s for d, s, o, t in back if d != "none" and 0.02 < s < 0.98]
        assert len(ups) >= 3 and back[0][1] < 0.5, back   # grows from 0
        assert back[-1][0] != "none" and back[-1][1] == 1, back
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_corner_squares_are_30_px_from_62_px_wide_and_the_bar_is_44_high(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"])
        page.mouse.move(5, 5)
        for w, want in ((61, 0), (62, 4), (104, 4), (260, 4)):
            page.evaluate(f"() => {{ board.items.l2.w = {w}; sel = new Set(['l2']); cam.x = 860; cam.y = -100; cam.z = 1; renderCam(); render(); }}")
            page.wait_for_timeout(300)
            hs = page.evaluate("() => [...document.querySelectorAll('#handles .h')].map(h => { const r = h.getBoundingClientRect(), s = getComputedStyle(h); return [r.width, r.height, s.borderTopLeftRadius]; })")
            assert len(hs) == want, (w, hs)
            for hw, hh, rad in hs:
                assert abs(hw - 30) < 0.6 and abs(hh - 30) < 0.6 and rad == "7px", (w, hs)   # always 30 with 7 px corners
            assert page.evaluate("() => EL.get('l2').classList.contains('mkh')") == bool(want)   # the marks keep 16 px × k from the squares
            bar = page.evaluate("() => document.querySelector('#handles .tidy').getBoundingClientRect().height")
            assert abs(bar - 44) < 0.6, (w, bar)   # the selection bar, always shown, 44 px
        assert not errors, errors
        browser.close()


# the canvas's pixel at a point of the stage (px), and the marks of a card as the element shows them, relative to the stage
PX = """([x, y]) => { const c = document.getElementById('lodd'), d = c.width / stage.getBoundingClientRect().width; return Array.from(c.getContext('2d').getImageData(Math.round(x * d), Math.round(y * d), 1, 1).data); }"""
ELMARKS = """id => { const st = stage.getBoundingClientRect(); return [...EL.get(id).querySelectorAll('.mk')].filter(m => getComputedStyle(m).display !== 'none')
  .map(m => { const r = m.getBoundingClientRect(); return { n: [...m.classList].find(c => /^mk-/.test(c) && !/^mk-(tl|tr|bl|br|on)$/.test(c)), l: r.left - st.left, t: r.top - st.top, r: r.right - st.left, b: r.bottom - st.top }; }); }"""


@pytest.mark.parametrize("engine", ENGINES)
def test_kind_pills_have_their_icon_and_the_far_view_draws_the_same_geometry(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"])
        cam(page, 1)
        # the pill draws the registry's glyph (ui/icons.js, owner 2026-10-07: one icon per meaning), the far view the same glyph as one path
        icon = """([id, k]) => { const s = EL.get(id).querySelector('.mk-kind .kp svg'), r = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          r.innerHTML = HY_TOOL_IC[k]; return !!s && s.innerHTML === r.innerHTML && MKI[k] === hyIconPath(k); }"""
        assert page.evaluate(icon, ["p", "layers"])
        assert page.evaluate(icon, ["d", "doc"])
        assert page.inner_text("#items [data-id=p] .kd").strip() == "PSD"
        if FFMPEG:
            page.wait_for_function("() => EL.get('v').querySelector('.kd .kt')")
            assert page.evaluate("() => !!EL.get('v').querySelector('.mk-kind .kp .pl')")
        # the element's marks and the far view's drawing of the same card at the same camera: every plate where the element has it
        page.evaluate("() => { board.items.l2.crop = [0, 0, 1, .95]; board.items.p.crop = [0, 0, 1, .95]; render(); }")
        page.evaluate(GRADE, ["l2"])
        for z, wide in ((1, 260), (0.45, 260), (1, 90), (1, 150)):
            page.evaluate(f"() => {{ board.items.l2.w = {wide}; board.items.p.w = {wide}; board.items.p.x = 300; board.items.l2.x = 900; board.items.l2.y = 0; cam.x = -40; cam.y = -40; cam.z = {z}; renderCam(); render(); }}")
            page.mouse.move(5, 890); page.wait_for_timeout(600)
            page.evaluate("() => { LOD.mkK = null; LOD.mka = new Map(); lodDots(); }")
            for id in ("l2", "p"):
                ms = page.evaluate(ELMARKS, id)
                assert len(ms) >= (4 if id == "l2" else 2), (z, wide, id, ms)   # note, ♥, grade, crop, copy; crop, kind
                for m in ms:
                    if m["n"] == "mk-fav" and id == "p":
                        continue   # a ♥ shown under the pointer only: the far view draws a liked one
                    cx, cy = (m["l"] + m["r"]) / 2, (m["t"] + m["b"]) / 2
                    inside = page.evaluate(PX, [cx, cy])
                    assert inside[3] > 150, (z, wide, id, m, inside)   # drawn where the element is
                    e = 1.6 + (1.5 if m["n"] == "mk-note" else 0)   # the note's ring lies around its box
                    for x, y in ((m["l"] - e, cy), (m["r"] + e, cy), (cx, m["t"] - e), (cx, m["b"] + e)):
                        out = page.evaluate(PX, [x, y])
                        assert out[3] < 60, (z, wide, id, m, (x, y), out)   # and not beyond it
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_right_click_opens_the_file_in_its_default_app(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server["port"])
        cam(page, 1)
        r = page.evaluate("() => { const r = EL.get('p').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
        page.mouse.click(*r, button="right")
        page.wait_for_function("() => { const b = document.querySelector('#ctx [data-act=open] .ml'); return b && b.textContent === 'Open in Test Viewer 2026'; }")
        first = page.evaluate("() => document.querySelector('#ctx button').dataset.act")
        assert first == "open"   # the menu's default action, first
        before = server["opened"].read_text() if server["opened"].exists() else ""
        page.click("#ctx [data-act=open]")
        for _ in range(50):
            now = server["opened"].read_text() if server["opened"].exists() else ""
            if now != before: break
            time.sleep(0.1)
        assert now[len(before):].strip().endswith("a/layers.psd"), now
        assert not errors, errors
        browser.close()


def test_library_card_menu_has_open_in_the_app(server):
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"http://127.0.0.1:{server['port']}/?view=lib")
        page.wait_for_function("() => [...document.querySelectorAll('.card[data-i]')].some(c => (view[+c.dataset.i] || {}).path === 'a/layers.psd')")
        card = page.evaluate_handle("() => [...document.querySelectorAll('.card[data-i]')].find(c => view[+c.dataset.i].path === 'a/layers.psd')")
        card.as_element().click(button="right")
        page.wait_for_function("() => { const b = document.querySelector('#lctx [data-a=open] .ml'); return b && b.textContent === 'Open in Test Viewer 2026'; }")
        assert page.evaluate("() => document.querySelector('#lctx button').dataset.a") == "open"
        browser.close()


def test_default_app_endpoints_stay_inside_the_library(server):
    port = server["port"]

    def call(path, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "Host": f"127.0.0.1:{port}", "Origin": f"http://127.0.0.1:{port}"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    st, body = call("/api/defaultapp?p=a/layers.psd")
    assert st == 200 and json.loads(body) == APP
    for bad in ("../state/settings.json", "/etc/hosts", "~/x.psd"):
        assert call(f"/api/defaultapp?p={urllib.parse.quote(bad)}")[0] == 404, bad
        assert call("/api/openfile", {"path": bad})[0] == 403, bad
    assert call("/api/openfile", {"path": "a/none.psd"})[0] == 404
    assert call("/api/appicon?app=/System/Applications/Calculator.app")[0] == 404   # only an app the server itself named
