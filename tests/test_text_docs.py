"""A text on the board is a small Markdown document, as a note in Apple Notes (owner 2026-10-09: «нужно, чтобы мы могли не только title
писать, а как в Notes Apple: когда сверху пишешь — это title, далее обычный текст. И чтобы это была Markdown-структура»).

- a heading with nothing under it is drawn exactly as before: its text as it is, its size's weight, auto width, no tw
- a document: the title at the item's size and bold, the body half of it and wrapping at tw, with headings, lists, a checklist, a quote,
  a rule, bold, italic, code and a link rendered
- a click on a checklist's box ticks it (one undo step) and neither selects nor moves the text
- writing: ↵ in the title finishes, as a heading's always did; ⇧↵ goes on into the body, where ↵ is a new line and lists go on;
  ⌘↵ applies; a double click on a body line opens the body there; ⌫ at the body's start joins its first line to the title
- ⌘Z right after making a document takes it away, one step
- a side strip sets a document's width; text pasted on the board becomes a text whose first line is its title
- hy.py: `text "Title\\nbody"` makes a document, `md` prints its body under its title, `find` names it by its title
Chromium, dark theme, a temporary library and server. HY_SHOTS=<folder> keeps screenshots."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png
from test_note_replies import shot

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
DOC = ("Plan\n## Steps\n- [ ] one\n- [x] two\n1. first\n2. second\n> a quote\n---\n**bold** *italic* `code` [link](https://example.com)\n"
       "A long line of plain body text that wraps inside the document's width rather than running on across the board.")


def board():
    return {"schema": 1, "revision": 1, "removed": {}, "groups": {}, "items": {
        "p": {"path": "a/0.png", "x": 0, "y": 0, "w": 300, "ar": 1.5, "crop": None},
        "H": {"type": "text", "text": "Old title", "x": 0, "y": -260, "fs": 128, "size": 3, "w": 0, "h": 0},
        "D": {"type": "text", "text": DOC, "x": 420, "y": 0, "fs": 40, "size": 1, "tw": 560, "w": 0, "h": 0},
    }}


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    for d in (lib / "a", state / "boards"): d.mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png(60, 40))
    (state / "boards/main.json").write_text(json.dumps(board()))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    (tmp_path / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, env
    finally:
        proc.terminate(); proc.wait(5); log.close()


def open_board(p, port):
    try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url)
    page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
      localStorage.setItem('cv.keyhint', 'always'); localStorage.setItem('cv.cam.main', JSON.stringify({ x: -300, y: -420, z: .9 })); }""")
    page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && document.querySelector('.tx[data-id=H]') && document.querySelector('.tx[data-id=D] .td-b')",
                           timeout=30000)
    page.wait_for_timeout(300)
    errors.clear()
    return browser, page, errors


SCREEN = "([x, y]) => { const r = stageBox(); return [r.left + (x - cam.x) * cam.z, r.top + (y - cam.y) * cam.z]; }"
CENTRE = "s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }"
NEW = "() => Object.keys(board.items).find(k => !['p', 'H', 'D'].includes(k)) || null"


def test_headings_stay_documents_render(server):
    port, _ = server
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, port)
        # the heading: its text node alone, no width, its size's weight, one line as before
        h = page.evaluate("""() => { const el = document.querySelector('.tx[data-id=H]'), cs = getComputedStyle(el);
          return { kids: el.children.length, text: el.textContent, doc: el.classList.contains('doc'), width: el.style.width, ws: cs.whiteSpace,
                   wt: cs.fontWeight, fs: cs.fontSize, tw: 'tw' in board.items.H }; }""")
        assert h == {"kids": 0, "text": "Old title", "doc": False, "width": "", "ws": "pre", "wt": "700", "fs": "128px", "tw": False}, h
        # the document: title at the item's size and bold, body half of it, wrapping at tw
        d = page.evaluate("""() => { const el = document.querySelector('.tx[data-id=D]'), q = s => el.querySelector(s), cs = e => getComputedStyle(e);
          return { doc: el.classList.contains('doc'), w: el.offsetWidth, title: q('.td-t').textContent, tfs: cs(q('.td-t')).fontSize, twt: cs(q('.td-t')).fontWeight,
                   bfs: cs(q('.td-b')).fontSize, bwt: cs(q('.td-b')).fontWeight, h2: q('.td-h2') && q('.td-h2').textContent,
                   ck: [...el.querySelectorAll('.td-ck')].map(c => [c.textContent, c.classList.contains('td-on')]), ol: el.querySelectorAll('.td-li.td-ol').length,
                   quote: q('.td-q') && q('.td-q').textContent, hr: !!q('hr'), b: q('b') && q('b').textContent, i: q('i') && q('i').textContent,
                   code: q('code') && q('code').textContent, a: q('a') && [q('a').getAttribute('href'), q('a').textContent],
                   wraps: q('.td-p:last-child').getClientRects().length && q('.td-p:last-child').offsetHeight > parseFloat(cs(q('.td-b')).lineHeight) * 1.5,
                   bh: board.items.D.h > 0 && board.items.D.w === 560 }; }""")
        assert d == {"doc": True, "w": 560, "title": "Plan", "tfs": "40px", "twt": "700", "bfs": "20px", "bwt": "400", "h2": "Steps",
                     "ck": [["one", False], ["two", True]], "ol": 2, "quote": "a quote", "hr": True, "b": "bold", "i": "italic", "code": "code",
                     "a": ["https://example.com", "link"], "wraps": True, "bh": True}, d
        shot(page, "text-docs-view.png")
        # the checklist's box: a circle in the round shape, a rounded square in pro; light and dark from the board's tokens
        BX = "() => getComputedStyle(document.querySelector('.tx[data-id=D] .td-box')).borderRadius"
        assert page.evaluate(BX) == "50%"
        page.evaluate("() => { localStorage.setItem('cv.theme', 'light'); localStorage.setItem('cv.shape', 'pro'); }"); page.reload()
        page.wait_for_function("() => document.querySelector('.tx[data-id=D] .td-b') && document.documentElement.dataset.theme === 'light'", timeout=30000)
        page.wait_for_timeout(300); shot(page, "text-docs-view-light-pro.png")
        assert page.evaluate(BX) != "50%" and sum(map(int, page.evaluate("() => getComputedStyle(document.querySelector('.tx[data-id=D] .td-t')).color")[4:-1].split(","))) < 150
        page.evaluate("() => { localStorage.setItem('cv.theme', 'dark'); localStorage.setItem('cv.shape', 'round'); }"); page.reload()
        page.wait_for_function("() => document.querySelector('.tx[data-id=D] .td-b')", timeout=30000); page.wait_for_timeout(300)

        # a checklist's box: one click ticks it, one ⌘Z takes it back; the text is neither selected nor moved
        x0 = page.evaluate("() => board.items.D.x")
        page.evaluate("() => { sel = new Set(); render(); }")
        page.mouse.click(*page.evaluate(CENTRE, ".tx[data-id=D] .td-ck .td-box"))
        assert page.evaluate("() => board.items.D.text.split('\\n')[2]") == "- [x] one"
        assert page.evaluate("() => [sel.size, board.items.D.x]") == [0, x0]
        page.wait_for_function("() => document.querySelectorAll('.tx[data-id=D] .td-ck.td-on').length === 2")
        page.keyboard.press("Meta+z")
        assert page.evaluate("() => board.items.D.text") == DOC

        # the side strip: the document's width follows the drag
        page.evaluate("() => { sel = new Set(['D']); render(); }")
        page.wait_for_selector(".he[data-resize=D][data-rc=e]", state="attached")
        x, y = page.evaluate(CENTRE, ".he[data-resize=D][data-rc=e]")
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + 45, y, steps=4); page.mouse.move(x + 90, y, steps=4); page.mouse.up()
        tw, fs = page.evaluate("() => [board.items.D.tw, board.items.D.fs]")
        assert abs(tw - (560 + 90 / .9)) < 3 and fs == 40, (tw, fs)
        assert page.evaluate("() => document.querySelector('.tx[data-id=D]').offsetWidth") == round(tw)
        page.keyboard.press("Meta+z")
        assert page.evaluate("() => board.items.D.tw") == 560
        # the size buttons: the type and the width together, as the corner does
        page.click(".tidy [data-tsize='2']")
        assert page.evaluate("() => [board.items.D.fs, board.items.D.tw]") == [72, 1008]
        page.keyboard.press("Meta+z")

        # a link: a click opens it once the double click's time has passed; a double click on it opens the text for writing instead
        page.evaluate("() => { window.__open = []; window.open = (...a) => { window.__open.push(a[0]); }; sel = new Set(); render(); }")
        page.mouse.click(*page.evaluate(CENTRE, ".tx[data-id=D] a")); page.wait_for_timeout(450)
        assert page.evaluate("() => window.__open") == ["https://example.com"]
        page.mouse.dblclick(*page.evaluate(CENTRE, ".tx[data-id=D] a")); page.wait_for_timeout(450)
        assert page.evaluate("() => [window.__open.length, !!document.querySelector('.tx[data-id=D] textarea')]") == [1, True]
        page.keyboard.press("Escape")
        assert page.evaluate("() => board.items.D.text") == DOC
        assert errors == []
        browser.close()


def test_writing_a_document(server):
    port, _ = server
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, port)
        # a new text: ↵ in the title finishes it as a heading, nothing changes for a heading
        x, y = page.evaluate(SCREEN, [-250, 300])
        page.mouse.dblclick(x, y); page.wait_for_selector(".tx textarea.td-t")
        page.keyboard.type("Solo"); page.keyboard.press("Enter")
        sid = page.evaluate(NEW)
        assert page.evaluate("id => [board.items[id].text, 'tw' in board.items[id], document.querySelector(`.tx[data-id=${id}]`).classList.contains('doc')]", sid) \
            == ["Solo", False, False]
        page.evaluate("id => { delete board.items[id]; sel = new Set(); render(); }", sid)

        # ⇧↵ goes on into the body; ↵ is a new line there and a list goes on, an empty item ends it; ⌘↵ applies
        x, y = page.evaluate(SCREEN, [-250, 380])
        page.mouse.dblclick(x, y); page.wait_for_selector(".tx textarea.td-t")
        page.keyboard.type("Title"); page.keyboard.press("Shift+Enter")
        assert page.evaluate("() => document.activeElement.matches('.tx textarea.td-in')")
        page.keyboard.type("line one"); page.keyboard.press("Enter"); page.keyboard.type("- a"); page.keyboard.press("Enter")
        assert page.evaluate("() => document.activeElement.value") == "line one\n- a\n- "
        page.keyboard.type("b"); page.keyboard.press("Enter"); page.keyboard.press("Enter")
        page.keyboard.type("- [ ] task"); page.keyboard.press("Enter")
        assert page.evaluate("() => document.activeElement.value").endswith("- [ ] task\n- [ ] ")
        page.keyboard.type("**bold**")
        lit = page.evaluate("() => [document.querySelector('.tx .td-m .td-bd') && document.querySelector('.tx .td-m .td-bd').textContent, document.querySelectorAll('.tx .td-m .td-k').length > 3]")
        assert lit == ["bold", True], lit
        page.wait_for_timeout(450)   # the key hint shows after its delay; the title's goes
        hint = page.evaluate("() => [...document.querySelectorAll('hy-keyhint')].map(k => k.textContent.replace(/\\s+/g, '')).join('|')")
        shot(page, "text-docs-editing.png")
        assert hint and "⌘" in hint, hint
        page.keyboard.press("Meta+Enter")
        nid = page.evaluate(NEW)
        it = page.evaluate("id => board.items[id]", nid)
        assert it["text"] == "Title\nline one\n- a\n- b\n- [ ] task\n- [ ] **bold**", it["text"]
        assert it["tw"] > 0 and page.evaluate("id => document.querySelector(`.tx[data-id=${id}]`).classList.contains('doc')", nid)
        shot(page, "text-docs-new.png")
        # ⌘Z right after: the new document goes, one step
        page.keyboard.press("Meta+z")
        assert page.evaluate(NEW) is None

        # a double click on a body line opens the body there, the word under the pointer selected; ⌫ at the body's start joins the title
        page.mouse.dblclick(*page.evaluate(CENTRE, ".tx[data-id=D] .td-ck .td-lt"))
        page.wait_for_selector(".tx[data-id=D] textarea.td-in")
        sel = page.evaluate("() => { const t = document.activeElement; return [t.className, t.value.slice(t.selectionStart, t.selectionEnd)]; }")
        assert sel == ["td-in", "one"], sel
        page.wait_for_timeout(450); shot(page, "text-docs-editing-body.png")
        page.keyboard.type("uno"); page.keyboard.press("Escape")
        assert page.evaluate("() => board.items.D.text.split('\\n')[2]") == "- [ ] uno"
        page.evaluate("() => { board.items.D.text = 'Head\\nTail\\nrest'; render(); editText('D'); }")
        page.keyboard.press("End"); page.keyboard.press("ArrowDown")
        assert page.evaluate("() => document.activeElement.className") == "td-in"
        page.keyboard.press("Backspace")
        assert page.evaluate("() => [document.activeElement.className, document.activeElement.value, document.activeElement.selectionStart]") == ["td-t", "HeadTail", 4]
        page.keyboard.press("Enter")
        assert page.evaluate("() => board.items.D.text") == "HeadTail\nrest"
        assert errors == []
        browser.close()


def test_paste_and_agent(server):
    port, env = server
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, port)
        # text pasted on the board: a text at the pointer, its first line the title, a document when it has more
        page.evaluate("""() => { lastPt = { x: 0, y: 900 }; const dt = new DataTransfer(); dt.setData('text/plain', 'Pasted title\\n- one\\n- two');
          document.body.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }""")
        nid = page.evaluate(NEW)
        assert nid and page.evaluate("id => [board.items[id].text, board.items[id].tw > 0, [...sel]]", nid) == ["Pasted title\n- one\n- two", True, [nid]]
        # a link to the board's own things pastes the copied things, as before (no text made)
        page.evaluate("""() => { delete board.items[Object.keys(board.items).find(k => !['p', 'H', 'D'].includes(k))]; sel = new Set(); render();
          const dt = new DataTransfer(); dt.setData('text/plain', location.origin + '/?view=canvas&page=main&obj=p');
          document.body.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }""")
        assert page.evaluate("() => Object.values(board.items).filter(i => i.type === 'text').length") == 2
        page.wait_for_function("() => !dirty && !saveT && !saveFlight", timeout=10000)
        browser.close()

    # hy.py: a document with \n, md prints its body under its title, find names it by its title
    hy = lambda *a: subprocess.run([sys.executable, str(ROOT / "review/hy.py"), *a], env={**env, "HYIMG_PORT": str(port)},
                                   capture_output=True, text=True, timeout=60)
    r = hy("do", 'text "Brief\\n## Goal\\n- [ ] ship it\\n**now**" x=0 y=1400')
    assert r.returncode == 0 and "Brief" in r.stdout, r.stdout + r.stderr
    b = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/board?name=main").read())
    t = next(i for i in b["items"].values() if i.get("type") == "text" and i["text"].startswith("Brief"))
    assert t["text"] == "Brief\n## Goal\n- [ ] ship it\n**now**" and t["size"] == 1 and t["fs"] == 40 and t["tw"] == 560
    md = hy("md").stdout
    assert "Brief [" in md and "- [ ] ship it" in md and "## Goal" not in md.split("Brief [")[1].split("\n")[2:3], md
    assert "Plan [" in md and "Old title [" in md, md
    f = hy("find", "Brief").stdout
    assert "Brief" in f and "ship it" not in f, f
