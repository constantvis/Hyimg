"""Key hints beside what is being done (owner 2026-10-08, writing a note: «должна быть подсказка внизу справа ... полупрозрачная:
Shift+Enter — готово»): ui/hy/keyhint.js, the board's contexts in ui/boardhints.js.

- writing a note shows, after a moment, the cap ↵ alone, bare on the note at its bottom right, and it never learns away (owner 2026-10-08)
- ↵ finishes the note, ⇧↵ is a new line and goes on with a list, ⌘↵ and Esc finish too, an IME's ↵ never does (owner 2026-10-09:
  «please change for notes the apply button from cmd+enter to just enter»); the hint goes with the editing
- learning: an item used 3 times is quieter, used 5 times it is not shown; when every item is learned no hint comes; the counts are an app
  setting (cv.keyhintUsed), one for the Mac
- Settings › Interface › Key hints: Always shows learned keys again, Off shows none
- on a surface the hint is the ↵ alone, bare, in its ink, no word and no cap plate (owner 2026-10-09 on round 12: «просто Enter символа
  достаточно, писать Send не нужно, а Line убери», «даже без подложки»): a heading's right after its words, a comment's in its field's
  corner, a typed number's just before it; a slider's drag shows none
- the glass capsule stays for a drag and a resize («да, отличные вот эти»); an annotation tool's keys are the Hint bar, top centre in the
  board's free part under the top row, gone once one of them is used
- a hint is drawn over what it is about, a typed number's in the settings window too (a slider's lay under the window from bbbf923 on)
Chromium, dark theme, a temporary library. HY_SHOTS=<folder> keeps screenshots."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


def board():
    note = {"type": "note", "text": "First idea", "x": 0, "y": 0, "w": 720, "fs": 40, "size": 2, "h": 720, "color": "yellow", "reach": None, "to": []}
    head = {"type": "text", "text": "A heading", "x": 0, "y": -400, "fs": 96}
    return {"schema": 1, "revision": 1, "removed": {}, "items": {"n": note, "h": head}, "groups": {}}


@pytest.fixture
def server(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    for d in (lib, state / "boards", tmp_path / "plugins", tmp_path / "home"): d.mkdir(parents=True)
    (state / "boards/main.json").write_text(json.dumps(board()))
    settings = tmp_path / "settings.json"; settings.write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(settings), HYIMG_PLUGINS=str(tmp_path / "plugins"), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, settings
    finally:
        proc.terminate(); proc.wait(5); log.close()


def shot(page, name):
    d = os.environ.get("HY_SHOTS")
    if d: Path(d).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(Path(d) / name))


# the hint now: shown, its items (caps, word, quiet), where it stands against the anchor
HINT = """sel => { const h = document.querySelector('hy-keyhint'); if (!h) return null; const r = h.getBoundingClientRect();
  const a = sel && document.querySelector(sel), ar = a && a.getBoundingClientRect();
  return { shown: h.hasAttribute('shown'), opacity: +getComputedStyle(h).opacity, ctx: h.dataset.ctx,
    items: [...h.querySelectorAll('.kh-i')].map(i => ({ id: i.dataset.id, caps: [...i.querySelectorAll('hy-kbd')].map(k => k.textContent),
      word: (i.querySelector('.kh-t') || {}).textContent || '', quiet: i.hasAttribute('quiet') })), bare: h.hasAttribute('bare'), bg: getComputedStyle(h).backgroundColor,
    capBg: (() => { const k = h.querySelector('hy-kbd'); return k ? getComputedStyle(k).backgroundColor : null; })(), place: h.getAttribute('place'),
    box: [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)], aBox: ar ? [Math.round(ar.left), Math.round(ar.top), Math.round(ar.right), Math.round(ar.bottom)] : null,
    inside: ar ? r.left >= ar.left && r.right <= ar.right + 1 && r.top >= ar.top && r.bottom <= ar.bottom + 1 : null,
    right: ar ? Math.round(ar.right - r.right) : null, bottom: ar ? Math.round(ar.bottom - r.bottom) : null,
    // drawn over what is around it: the hint is what is hit at its own centre (its pointer events on for that moment, it never takes them)
    top: (() => { h.style.pointerEvents = 'auto'; const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      h.style.pointerEvents = ''; return !!e && h.contains(e); })() }; }"""


def open_board(b, port):
    pg = b.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"http://127.0.0.1:{port}/canvas.html")
    pg.wait_for_function("typeof EL !== 'undefined' && EL.size >= 2 && window.hyKeyHint && window.hyHint && !!customElements.get('hy-kbd')", timeout=20000)
    pg.evaluate("() => { sel = new Set(['n']); render(); if (typeof fitAll === 'function') fitAll(); }")
    pg.wait_for_timeout(500)
    return pg, errors


def edit_note(pg):
    pg.evaluate("() => editNote('n')")
    pg.wait_for_selector(".note textarea")
    pg.wait_for_timeout(450)   # the hint comes after 300 ms and fades in


def edit_heading(pg):
    pg.evaluate("() => editText('h')")
    pg.wait_for_selector(".tx textarea")
    pg.wait_for_timeout(450)


def test_note_hint_lists_the_real_keys_and_enter_finishes(server):
    port, settings = server
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg, errors = open_board(b, port)
            pg.evaluate("() => editNote('n')")
            pg.wait_for_selector(".note textarea")
            h = pg.evaluate(HINT, ".note.editing")
            assert h and not h["shown"], h   # not at once: after a moment of writing
            pg.wait_for_timeout(450)
            h = pg.evaluate(HINT, ".note.editing")
            shot(pg, "note-hint.png")
            assert h["shown"] and h["ctx"] == "note" and h["opacity"] > 0.5 and h["top"], h
            assert [(i["id"], i["caps"], i["word"]) for i in h["items"]] == [("done", ["↵"], "")], h
            assert h["bare"] and h["bg"] == "rgba(0, 0, 0, 0)" and h["capBg"] == "rgba(0, 0, 0, 0)", h   # no plate, not even the cap's: the note's ink
            assert h["inside"] and 0 <= h["right"] <= 12 and 0 <= h["bottom"] <= 10, h   # the note's bottom right corner
            # ⇧↵ is a new line, ↵ finishes and keeps the text
            pg.keyboard.press("End"); pg.keyboard.type(" more"); pg.keyboard.press("Shift+Enter"); pg.keyboard.type("second line")
            assert pg.evaluate("() => !!document.querySelector('.note textarea')")
            pg.keyboard.press("Enter")
            pg.wait_for_function("() => !document.querySelector('.note textarea')", timeout=3000)
            assert pg.evaluate("() => board.items.n.text") == "First idea more\nsecond line"
            pg.wait_for_function("() => !document.querySelector('hy-keyhint')", timeout=2000)   # gone with the editing
            assert pg.evaluate("() => JSON.parse(localStorage.getItem('cv.keyhintUsed') || '{}')") == {"note.done": 1}
            # the heading: the ↵ alone, bare in its ink, right after its words (the field is as wide as they are), on their line
            pg.evaluate("() => editText('h')"); pg.wait_for_selector(".tx textarea"); pg.wait_for_timeout(450)
            h = pg.evaluate(HINT, ".tx.editing textarea")
            shot(pg, "heading-hint.png")
            assert [(i["caps"], i["word"]) for i in h["items"]] == [(["↵"], "")] and h["bare"] and h["capBg"] == "rgba(0, 0, 0, 0)", h
            assert 4 <= h["box"][0] - h["aBox"][2] <= 20 and h["aBox"][1] <= h["box"][1] and h["box"][3] <= h["aBox"][3] + 1, h
            pg.keyboard.press("Escape")
            assert not errors, errors
        finally:
            b.close()
        # the count reached the app's settings file: one for every project of this Mac
        for _ in range(30):
            if "note.done" in json.loads(settings.read_text()).get("cv.keyhintUsed", "{}"): break
            time.sleep(0.1)
        assert json.loads(json.loads(settings.read_text())["cv.keyhintUsed"]) == {"note.done": 1}


def test_note_enter_finishes_shift_enter_lists_ime_stays(server):
    """Owner 2026-10-09: «please change for notes the apply button from cmd+enter to just enter». ⇧↵ takes over the new line and the
    list («- » goes on, an empty item ends the list); the ↵ with which an IME picks its candidate stays in the note, in Chromium
    (isComposing) and as WebKit sends it (keyCode 229 without isComposing)."""
    port, _ = server
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg, errors = open_board(b, port)
            edit_note(pg)
            pg.keyboard.press("End")
            for k in ("Shift+Enter", "- one", "Shift+Enter", "two", "Shift+Enter", "Shift+Enter", "after"):
                pg.keyboard.press(k) if k == "Shift+Enter" else pg.keyboard.type(k)
            assert pg.evaluate("() => document.querySelector('.note textarea').value") == "First idea\n- one\n- two\nafter"
            # an IME: Chromium's own composition, its ↵ (keyCode 229, isComposing) picks the candidate, the note stays open
            cdp = pg.context.new_cdp_session(pg)
            cdp.send("Input.imeSetComposition", {"text": "にほん", "selectionStart": 3, "selectionEnd": 3})
            cdp.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 229,
                                                "nativeVirtualKeyCode": 229})
            cdp.send("Input.insertText", {"text": "日本"})
            pg.wait_for_timeout(100)
            assert pg.evaluate("() => !!document.querySelector('.note textarea')"), "an IME's Enter finished the note"
            # WebKit: the Enter that confirms the candidate comes as key Enter, keyCode 229, isComposing false
            kept = pg.evaluate("""() => { const ta = document.querySelector('.note textarea');
              const e = new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true, cancelable: true });
              Object.defineProperty(e, 'keyCode', { get: () => 229 }); ta.dispatchEvent(e);
              const c = new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', isComposing: true, bubbles: true, cancelable: true });
              ta.dispatchEvent(c); return !!document.querySelector('.note textarea') && !e.defaultPrevented && !c.defaultPrevented; }""")
            assert kept, "a composing Enter finished the note"
            assert pg.evaluate("() => document.querySelector('.note textarea').value").endswith("after日本")
            pg.keyboard.press("Enter")   # a plain ↵ applies, as a heading's does
            pg.wait_for_function("() => !document.querySelector('.note textarea')", timeout=3000)
            assert pg.evaluate("() => board.items.n.text") == "First idea\n- one\n- two\nafter日本"
            # ⌘↵ and Esc still finish
            for key in ("Meta+Enter", "Escape"):
                edit_note(pg); pg.keyboard.press("End"); pg.keyboard.type("!")
                pg.keyboard.press(key); pg.wait_for_function("() => !document.querySelector('.note textarea')", timeout=3000)
            assert pg.evaluate("() => board.items.n.text").endswith("after日本!!")
            assert not errors, errors
        finally:
            b.close()


def test_learning_quiets_then_hides_and_the_setting(server):
    port, _ = server
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg, errors = open_board(b, port)
            for n in range(1, 6):   # five headings finished with ↵
                edit_heading(pg)
                h = pg.evaluate(HINT, ".tx.editing")
                done = next((i for i in h["items"] if i["id"] == "done"), None)
                assert done and done["quiet"] == (n > 3), (n, h)   # used 3 times: quieter
                if n == 4: shot(pg, "heading-hint-quiet.png")
                pg.keyboard.press("Enter"); pg.wait_for_function("() => !document.querySelector('.tx textarea')")
            edit_heading(pg)
            assert pg.evaluate(HINT, ".tx.editing") is None   # used 5 times: learned, and a hint with nothing left does not come
            pg.keyboard.press("Escape")
            for n in range(1, 7):   # a note's ↵ stays however often it is used, never quieter (owner 2026-10-08: «куда-то пропала»)
                edit_note(pg)
                h = pg.evaluate(HINT, ".note.editing")
                assert h and [(i["id"], i["quiet"]) for i in h["items"]] == [("done", False)], (n, h)
                pg.keyboard.press("Enter" if n % 2 else "Meta+Enter"); pg.wait_for_function("() => !document.querySelector('.note textarea')")
            edit_note(pg)
            assert pg.evaluate(HINT, ".note.editing")["items"][0]["caps"] == ["↵"]
            pg.keyboard.press("Escape")
            # Settings › Interface › Key hints: Always shows them all again, Off none anywhere. The settings window shows one section at a
            # time since ff727fd (Appearance first), so the row is there once Interface is chosen on its rail
            pg.click("#bset"); pg.evaluate("s => hySetPanel.go(s)", "interface"); pg.wait_for_timeout(400)
            row = pg.locator("hy-segmented[data-set=keyhint]")
            assert row.get_attribute("value") == "learn"
            row.locator("button[value=always]").click()
            assert pg.evaluate("() => localStorage.getItem('cv.keyhint')") == "always"
            pg.click("#bset"); pg.wait_for_timeout(300)
            edit_note(pg)
            h = pg.evaluate(HINT, ".note.editing")
            assert [i["id"] for i in h["items"]] == ["done"] and not any(i["quiet"] for i in h["items"]), h
            pg.keyboard.press("Escape")
            pg.click("#bset"); pg.evaluate("s => hySetPanel.go(s)", "interface"); pg.wait_for_timeout(400)
            shot(pg, "settings-key-hints.png")
            row.locator("button[value=off]").click()
            assert pg.evaluate("() => localStorage.getItem('cv.keyhint')") == "off"
            pg.click("#bset"); pg.wait_for_timeout(300)
            edit_note(pg)
            assert pg.evaluate(HINT, ".note.editing") is None
            pg.keyboard.press("Escape")
            pg.evaluate("() => editText('h')"); pg.wait_for_selector(".tx textarea"); pg.wait_for_timeout(450)
            assert pg.evaluate(HINT, ".tx.editing") is None
            pg.keyboard.press("Escape")
            assert not errors, errors
        finally:
            b.close()


def test_other_board_contexts(server):
    """a drag, an annotation tool, the comment box, a slider: each its real keys, where they are needed, gone when it ends"""
    port, _ = server
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg, errors = open_board(b, port)
            words = lambda: [(i["caps"], i["word"]) for i in (pg.evaluate(HINT, None) or {"items": []})["items"]]
            drawn = lambda: (pg.evaluate(HINT, None) or {}).get("top")   # seen, not covered by what it is about
            # dragging the selected note: ⇧ keeps it on one axis, under the selection; gone with the release
            box = pg.evaluate("() => { const r = EL.get('n').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }")
            pg.mouse.move(*box); pg.mouse.down(); pg.mouse.move(box[0] + 40, box[1] + 10, steps=4); pg.wait_for_timeout(450)
            shot(pg, "move-hint.png")
            assert words() == [(["⇧"], "One axis")] and drawn()
            pg.mouse.up(); pg.wait_for_function("() => !document.querySelector('hy-keyhint')", timeout=2000)
            # an annotation tool: its ⇧ and Esc in the Hint bar, top centre of the board's free part on the line under the top row
            pg.evaluate("() => hyAnnot.tool('arrow')"); pg.wait_for_timeout(450)
            h = pg.evaluate(HINT, "#dock")
            shot(pg, "annotate-arrow-hint.png")
            assert words() == [(["⇧"], "45°"), (["Esc"], "Done")] and h["top"] and h["place"] == "top" and not h["bare"], h
            free = pg.evaluate("() => { const f = hyBars.free(stage, INSET, { t: 58, b: 84 }); return [f.l, f.r]; }")
            assert h["box"][1] == 58 and abs((h["box"][0] + h["box"][2]) / 2 - sum(free) / 2) <= 1, (h, free)
            pg.evaluate("() => hyAnnot.tool('rect')"); pg.wait_for_timeout(450)
            assert words() == [(["⇧"], "Square"), (["Esc"], "Done")]
            # the bar has done its job once one of its keys is used: it goes, and comes back with the next tool
            pg.keyboard.press("Shift")
            pg.wait_for_function("() => !document.querySelector('hy-keyhint[shown]')", timeout=2000)
            pg.evaluate("() => hyAnnot.tool('ellipse')"); pg.wait_for_timeout(450)
            assert words() == [(["⇧"], "Circle"), (["Esc"], "Done")]
            pg.evaluate("() => hyAnnot.exit()"); pg.wait_for_function("() => !document.querySelector('hy-keyhint')", timeout=2000)
            # the comment box: the ↵ alone in its field's corner, bare in the field's ink (⇧↵ and @ work, not shown)
            pg.evaluate("() => hyComments.newAt({ x: 900, y: 300 })"); pg.wait_for_selector("#cmthread textarea"); pg.wait_for_timeout(450)
            shot(pg, "comment-hint.png")
            h = pg.evaluate(HINT, "#cmthread textarea")
            assert words() == [(["↵"], "")] and h["bare"] and h["inside"] and 0 <= h["right"] <= 16 and drawn(), h
            pg.evaluate("() => hyComments.close()"); pg.wait_for_function("() => !document.querySelector('hy-keyhint')", timeout=2000)
            # a slider of the settings: a drag shows nothing; a typed number its ↵ just before it, over the settings window (z 62), not
            # under it at the hint's own z 50 (bbbf923). The dots' slider is in Settings › Board (one section at a time, ff727fd)
            pg.click("#bset"); pg.evaluate("s => hySetPanel.go(s)", "board"); pg.wait_for_timeout(400)
            s = pg.evaluate("() => { const r = document.querySelector('[data-row=dotsv] .hy-slider').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }")
            pg.mouse.move(*s); pg.mouse.down(); pg.mouse.move(s[0] + 30, s[1], steps=4); pg.wait_for_timeout(450)
            assert pg.evaluate(HINT, None) is None
            pg.mouse.up()
            pg.evaluate("() => document.querySelector('[data-row=dotsv] .hy-slider-v').click()"); pg.wait_for_timeout(450)
            h = pg.evaluate(HINT, "[data-row=dotsv] .hy-slider-ed")
            shot(pg, "number-hint.png")
            assert words() == [(["↵"], "")] and h["bare"] and drawn() and 0 <= h["aBox"][0] - h["box"][2] <= 8, h
            pg.keyboard.press("Escape"); pg.wait_for_function("() => !document.querySelector('hy-keyhint')", timeout=2000)
            assert not errors, errors
        finally:
            b.close()
