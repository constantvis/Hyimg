"""The Text tool and a text's box, as Figma's text (owner 2026-10-11, a pasted text ran as one endless line across the board: «во-первых
я хочу иметь выбор text tool по кнопке "T". А во-вторых хочу ... выбрать ширину и высоту блока, то есть нажать мышку и тянуть ... а также
редактировать ширину и высоту, если нужно, и иметь настройку сбросить фиксирование ... фиксированность появляется, когда я тянуть начинаю»).

- T: a text cursor; a click makes an Auto width text, a drag a Fixed size box of exactly the dragged size whose words wrap; the tool is
  done after one text; Esc leaves it; T typed in a note's field is a «t» there; the dock's «+» › Text wears T
- the strips of a selected text: a side makes it Auto height at the new width, the bottom Fixed size; each drag one undo step,
  «Text box size»
- the text bar: Auto width, Auto height, Fixed size and Reset switch the box, each one undo step named by the box; the bar keeps its
  place and its width while the pointer is on it, whatever is clicked (the size's name included)
- a pasted single long line comes in Auto height at a document's width, not as one endless line
- hy.py: `text … w= h=` makes a Fixed box, `set … mode=w` resets it, `md` marks the box
Chromium, dark theme, our own server (tests/test_p4_board.py's harness), the mouse for every click."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_p4_board import box, board_page, browser_of, serve, settle

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
PLATE = "() => { const p = document.getElementById('hydkstep'); return p && p.classList.contains('on') ? p.textContent : ''; }"
TEXT = "() => { const k = Object.keys(board.items).find(k => board.items[k].type === 'text'); return k ? { id: k, ...board.items[k] } : null; }"
LINES = "id => { const r = document.createRange(); r.selectNodeContents(document.querySelector(`.tx[data-id='${id}']`)); return new Set([...r.getClientRects()].map(q => Math.round(q.top))).size; }"
BAR = "() => { const r = document.querySelector('#handles .tidy.tsz').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width)]; }"
HEAD = {"type": "text", "text": "Strips and boxes", "x": 100, "y": 300, "fs": 40, "size": 1, "w": 0, "h": 0}


def run(tmp_path, fn, items=None):
    with serve(tmp_path, items if items is not None else {}) as (port, lib), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port)
        try: fn(page, page.evaluate, port)
        finally: browser.close()
        assert not errors, errors


def plate(page, sel="#bundo"):   # the step's name over Undo, as the pointer rests on it
    page.mouse.move(5, 5); b = box(page, sel); page.mouse.move(b["cx"], b["cy"])
    page.wait_for_function(f"() => ({PLATE})()", timeout=4000)
    return page.evaluate(PLATE)


def drag(page, x0, y0, x1, y1):
    page.mouse.move(x0, y0); page.mouse.down(); page.mouse.move((x0 + x1) / 2, (y0 + y1) / 2, steps=4); page.mouse.move(x1, y1, steps=4); page.mouse.up()


def test_t_clicks_a_text_and_drags_a_box(tmp_path):
    def go(page, ev, port):
        # T, then a click on the empty board: a text there in Auto width, the tool done
        page.mouse.move(400, 520); page.keyboard.press("t")
        assert ev("() => [stage.classList.contains('ttool'), getComputedStyle(document.elementFromPoint(400, 520)).cursor]") == [True, "text"]
        page.mouse.click(400, 520); page.wait_for_selector(".tx.editing textarea"); page.keyboard.type("Hello"); page.keyboard.press("Escape")
        t = ev(TEXT); assert [t["text"], t.get("tm"), t.get("tw"), ev("() => stage.classList.contains('ttool')")] == ["Hello", None, None, False]
        p = ev("([x, y]) => toWorld(x, y)", [400, 520]); assert abs(t["x"] - p["x"]) < 2
        # T, then a drag of 300 × 120 at 100 %: a Fixed size box of that size, its field open; the words wrap inside its width
        page.keyboard.press("t"); drag(page, 600, 300, 900, 420)
        page.wait_for_selector(".tx.editing textarea"); page.keyboard.type("A box of its own width and height where a long line wraps")
        page.keyboard.press("Escape")
        b = ev("() => { const k = Object.keys(board.items).find(k => board.items[k].text && board.items[k].text.startsWith('A box')), it = board.items[k],"
               " r = document.querySelector(`.tx[data-id='${k}']`).getBoundingClientRect(), w = toWorld(600, 300);"
               " return { id: k, tm: it.tm, tw: it.tw, th: it.th, dx: Math.round(it.x - w.x), dy: Math.round(it.y - w.y), w: Math.round(r.width), h: Math.round(r.height) }; }")
        assert {k: b[k] for k in ("tm", "tw", "th", "dx", "dy", "w", "h")} == {"tm": "f", "tw": 300, "th": 120, "dx": 0, "dy": 0, "w": 300, "h": 120}, b
        assert ev(LINES, b["id"]) >= 2, "the words wrap inside the box"
        assert not ev("() => stage.classList.contains('ttool')")
        # Esc leaves the tool without making anything
        n = ev("() => Object.keys(board.items).length")
        page.keyboard.press("t"); page.keyboard.press("Escape"); page.mouse.click(300, 700)
        assert ev("() => [stage.classList.contains('ttool'), Object.keys(board.items).length]") == [False, n]
        # T typed in a note's field is a letter there, the tool stays off
        page.mouse.move(1000, 650); page.keyboard.press("n"); page.wait_for_selector(".note textarea"); page.keyboard.type("Tt"); page.keyboard.press("Escape")
        assert ev("() => [Object.values(board.items).find(i => i.type === 'note').text, stage.classList.contains('ttool')]") == ["Tt", False]
        # the dock's «+» › Text wears its key
        page.locator("#bplus").click(); page.wait_for_selector("#bplusm [data-mk=text]")
        assert ev("() => [...document.querySelectorAll('#bplusm [data-mk=text] kbd, #bplusm [data-mk=text] hy-kbd')].map(k => k.textContent).join('')") == "T"
        page.keyboard.press("Escape")
        settle(page, port)
    run(tmp_path, go)


def test_strips_and_the_bar_set_the_box(tmp_path):
    def go(page, ev, port):
        h = box(page, ".tx[data-id=t1]"); page.mouse.click(h["cx"], h["cy"]); page.wait_for_selector("#handles .he[data-rc=e]")
        w0 = ev("() => board.items.t1.w")
        # the right strip: Auto height at the new width, one step «Text box size»
        e = box(page, "#handles .he[data-rc=e]"); drag(page, e["cx"], e["cy"], e["cx"] - 120, e["cy"])
        t = ev("() => board.items.t1"); assert t["tm"] == "h" and abs(t["tw"] - (w0 - 120)) <= 2 and "th" not in t, t
        assert ev(LINES, "t1") >= 2, "a narrower heading wraps"
        assert plate(page) == "Undo ·Text box size⌘Z"
        # the bottom strip: Fixed size, the height dragged
        h0 = ev("() => board.items.t1.h"); s = box(page, "#handles .he[data-rc=s]"); drag(page, s["cx"], s["cy"], s["cx"], s["cy"] + 90)
        t = ev("() => board.items.t1"); assert t["tm"] == "f" and abs(t["th"] - (h0 + 90)) <= 2 and abs(t["tw"] - (w0 - 120)) <= 2, t
        assert round(ev("() => document.querySelector('.tx[data-id=t1]').getBoundingClientRect().height")) == round(t["th"])
        assert plate(page) == "Undo ·Text box size⌘Z"
        # the bar: the box shown is Fixed; the pointer on the bar, every click leaves it where it is and as wide as it was
        page.wait_for_selector("#handles .tsz hy-segmented.tbox.seg")
        assert ev("() => document.querySelector('#handles .tsz hy-segmented.tbox').value") == "f"
        a = box(page, "#handles .tsz [data-tmode=w]"); page.mouse.move(a["cx"], a["cy"]); page.wait_for_timeout(100); bar = ev(BAR)
        page.mouse.click(a["cx"], a["cy"]); page.wait_for_function("() => !board.items.t1.tm")
        assert ev("() => ['tw', 'th', 'tm'].filter(k => k in board.items.t1)") == [] and ev(LINES, "t1") == 1, "Auto width: one line"
        assert ev(BAR) == bar
        for m, want in (("h", "h"), ("f", "f")):
            b = box(page, f"#handles .tsz [data-tmode={m}]"); page.mouse.click(b["cx"], b["cy"])
            page.wait_for_function(f"() => board.items.t1.tm === '{want}'"); assert ev(BAR) == bar, m
        assert ev("() => document.querySelector('#handles .tsz hy-segmented.tbox').value") == "f"
        r = box(page, "#handles .tsz [data-tmode=reset]"); page.mouse.click(r["cx"], r["cy"]); page.wait_for_function("() => !board.items.t1.tm")
        assert ev(BAR) == bar and ev("() => document.querySelector('#handles .tsz [data-tmode=reset]').disabled")
        # the sizes: H1, A−, A− change the size's name at the bar's end, the bar keeps its width
        for q in ("[data-tsize='4']", ".fz", ".fz"):
            b = box(page, f"#handles .tsz {q}"); page.mouse.click(b["cx"], b["cy"]); page.wait_for_timeout(200)
            assert ev(BAR) == bar, q
        assert ev("() => hyTextSize.cur(board.items.t1)") == 2
        # one step each, named by the box it gave; ⌘Z walks them back to the Fixed box
        assert plate(page) == "Undo ·Size⌘Z"
        for _ in range(3): page.keyboard.press("Meta+z")
        assert plate(page) == "Undo ·Auto width⌘Z"
        page.keyboard.press("Meta+z"); assert plate(page) == "Undo ·Fixed size⌘Z"
        page.keyboard.press("Meta+z"); assert plate(page) == "Undo ·Auto height⌘Z"
        page.keyboard.press("Meta+z"); assert ev("() => 'tm' in board.items.t1") is False and plate(page) == "Undo ·Auto width⌘Z"
        page.keyboard.press("Meta+z"); assert ev("() => board.items.t1.tm") == "f" and plate(page) == "Undo ·Text box size⌘Z"
        settle(page, port)
    run(tmp_path, go, {"t1": HEAD})


def test_a_long_pasted_line_wraps_and_hy_py_knows_the_box(tmp_path):
    def go(page, ev, port):
        line = "A single pasted paragraph that goes on and on " * 6
        ev("""t => { lastPt = { x: 0, y: 600 }; const dt = new DataTransfer(); dt.setData('text/plain', t);
          document.body.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }""", line.strip())
        page.wait_for_function("() => Object.values(board.items).some(i => i.type === 'text')")
        t = ev(TEXT); assert [t.get("tm"), t.get("tw")] == ["h", 560], t
        assert round(ev("id => document.querySelector(`.tx[data-id='${id}']`).getBoundingClientRect().width", t["id"])) == 560
        assert ev(LINES, t["id"]) >= 3
        settle(page, port)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
        env.update(HYIMG_PORT=str(port), HYIMG_LIBRARY_ROOT=str(tmp_path / "lib"), HYIMG_STATE_ROOT=str(tmp_path / "state"), PYTHONDONTWRITEBYTECODE="1")
        hy = lambda *a: subprocess.run([sys.executable, str(ROOT / "review/hy.py"), *a], env=env, capture_output=True, text=True, timeout=60)
        r = hy("do", 'text "Boxed title" x=0 y=1400 w=300 h=120')
        assert r.returncode == 0, r.stdout + r.stderr
        b = json.loads(subprocess.run([sys.executable, "-c", f"import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:{port}/api/board?name=main').read().decode())"],
                                      capture_output=True, text=True).stdout)
        k, it = next((k, i) for k, i in b["items"].items() if i.get("text") == "Boxed title")
        assert [it.get("tm"), it.get("tw"), it.get("th"), it.get("w"), it.get("h")] == ["f", 300, 120, 300, 120], it
        md = hy("md").stdout; assert f"Boxed title [{k}] ▭300×120" in md, md
        r = hy("do", f"set {k} mode=w"); assert r.returncode == 0, r.stdout + r.stderr
        b = json.loads(subprocess.run([sys.executable, "-c", f"import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:{port}/api/board?name=main').read().decode())"],
                                      capture_output=True, text=True).stdout)
        assert [x for x in ("tm", "tw", "th", "mode") if x in b["items"][k]] == [], b["items"][k]
    run(tmp_path, go)
