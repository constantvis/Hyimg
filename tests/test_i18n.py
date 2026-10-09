"""The interface in English or Russian (owner 2026-10-06: «translate the whole interface to English», then «make 2 versions, Russian
and English, switchable in settings»; «translate the interface entirely, not just some parts»).

English is the default: with no cv.lang in the app's settings no Russian word may show anywhere on the board or the library, in any
state a person can reach (the panels, the menus, the info card, the bars over a selection, the crop hint, the notifications). Only the
owner's own data may be Russian; here it is Latin, so any Cyrillic is a leak. The one Russian word allowed is «Русский», the language's
own name in the switch (marked lang="ru"). In Russian every key the pages ask for has its Russian (window.__tMiss stays empty), and a
switch in the board's settings reloads the open pages in the other language.
Runs only where Playwright and its Chromium are installed.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]

# every visible Cyrillic text node, and every title / aria-label / placeholder / alt, on the page and in its same-origin frames;
# the agent's note (agent-facing, hidden) and the language's own name (lang="ru") are not the interface
CRAWL = r"""() => {
  const CY = /[\u0400-\u04FF]/, RAW = /\w::\w|\{[a-z]+\}/, out = [];   // RAW: a dictionary key shown as it is (a context key, an unfilled {var})
  const skip = el => el.closest('.agentnote, [lang="ru"]:not(html), head');
  const shown = el => { if (el.tagName === 'OPTION') return true; const s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden' && el.getClientRects().length > 0; };
  const walk = doc => {
    if (!doc || !doc.body) return;
    const w = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) { const n = w.currentNode, p = n.parentElement;
      if (!p || /^(SCRIPT|STYLE)$/.test(p.tagName) || skip(p)) continue;
      if (CY.test(n.nodeValue) && shown(p)) out.push('text: ' + n.nodeValue.trim().slice(0, 90));
      if (RAW.test(n.nodeValue) && shown(p)) out.push('raw key: ' + n.nodeValue.trim().slice(0, 90)); }
    doc.querySelectorAll('[title],[aria-label],[placeholder],[alt]').forEach(el => { if (skip(el) || (el.tagName !== 'OPTION' && !el.closest('svg') && !shown(el) && !el.closest('[role=menu],[role=dialog],#keys,#sets,#hist,#ntf,#info'))) return;
      for (const a of ['title', 'aria-label', 'placeholder', 'alt']) { const v = el.getAttribute(a); if (v && (CY.test(v) || RAW.test(v))) out.push(a + ': ' + v.slice(0, 90)); } });
    doc.querySelectorAll('.note:empty, .tl .lbl:empty, #cPageName:empty, .it.missing').forEach(el => { const c = getComputedStyle(el, '::before').content; if (CY.test(c)) out.push('css: ' + c); });
    if (CY.test(doc.title)) out.push('document title: ' + doc.title);
    doc.querySelectorAll('iframe').forEach(f => { try { walk(f.contentDocument); } catch (e) {} });
  };
  walk(document);
  return [...new Set(out)];
}"""
MISS = "() => { const f = document.querySelector('#cvFrame'); let m = [...(window.__tMiss || [])]; try { if (f) m = m.concat(f.contentWindow.__tMiss || []); } catch (e) {} return m; }"


def board_json():
    items = {f"i{n}": {"path": f"a/{n}.png", "x": n % 4 * 340, "y": n // 4 * 520, "w": 320, "ar": 2 / 3, "crop": None} for n in range(6)}
    items["n1"] = {"type": "note", "text": "a note", "x": 1400, "y": 0, "w": 320, "fs": 18, "color": "yellow"}
    items["t1"] = {"type": "text", "text": "Heading A", "x": 0, "y": -300, "w": 600, "fs": 72, "size": 2}
    items["t2"] = {"type": "text", "text": "Heading B", "x": 700, "y": -300, "w": 600, "fs": 128, "size": 3}
    items["m1"] = {"path": "a/gone.png", "x": 1400, "y": 600, "w": 320, "ar": 2 / 3, "crop": None}   # a file no longer on disk
    groups = {"g1": {"title": "Group one", "x": -40, "y": -40, "w": 720, "h": 600, "members": ["i0", "i1"]}}
    return {"schema": 1, "revision": 1, "items": items, "groups": groups, "removed": {}}


def start(tmp_path, lang):
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "a").mkdir(parents=True)
    for n in range(6):
        (lib / "a" / f"{n}.png").write_bytes(png())
        (lib / "a" / f"{n}.json").write_text(json.dumps({"prompt": "a quiet test prompt", "model": "test-model"}))
    # a frame rated on the old tag page: the json keeps the app's own Russian words (verdict, «Годится для», good and bad tags), the
    # card on the right shows them in the interface's language
    (lib / "a/0.json").write_text(json.dumps({"prompt": "a quiet test prompt", "model": "test-model", "feedback": {"verdict": "take", "fav": True,
        "use": ["Реклама", "Анимация"], "good": ["Идея", "Чехол точный"], "bad": ["Кич"], "comment": "ok", "updated": "2026-10-06 10:00"}}))
    (state / "boards").mkdir(parents=True)
    (state / "boards/main.json").write_text(json.dumps(board_json()))
    (state / "boards/p2.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (state / "boards/d1.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "Alpha"}, {"id": "d1", "title": "---"}, {"id": "p2", "title": "Beta"}]}))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"cv.lang": lang} if lang else {}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(settings),
               HYIMG_PLUGINS=str(tmp_path / "no-plugins"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    return port, process, log, settings


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as error:   # Playwright installed without its browser
            pytest.skip(f"no Chromium for Playwright: {error}")
        yield b
        b.close()


def board_states(page, frame):
    """walks the board through the states a person reaches; yields (name, frame) after each"""
    ev = frame.evaluate
    ev("() => { cam.x = -60; cam.y = -400; cam.z = .6; renderCam ? renderCam() : render(); }")
    yield "first screen"
    for button, name in (("#bset", "settings"), ("#bkeys", "keys"), ("#bntf", "notifications"), ("#bhist", "history")):
        frame.click(button); frame.wait_for_timeout(250); yield name
        if button == "#bset":   # the settings' window lies over the page: its button closes it before the next one
            for sec in ("team", "board", "notifications", "plugins", "storage", "interface", "performance", "profile"):
                frame.evaluate("s => hySetPanel.go(s)", sec); frame.wait_for_timeout(120); yield f"settings: {sec}"
            frame.evaluate("s => hySetPanel.go(s)", "appearance"); frame.click("#bset"); frame.wait_for_timeout(450)
    frame.click('#hist [data-tab="ev"]'); frame.wait_for_timeout(300); yield "history: activity"
    frame.click('#hist [data-tab="ver"]'); frame.wait_for_timeout(300); yield "history: versions"
    frame.fill("#histLabel", "v one"); frame.click("#histSave"); frame.wait_for_timeout(500); yield "version saved toast"
    frame.click("#histClose"); frame.wait_for_timeout(150)
    frame.click("#cPage"); frame.wait_for_timeout(250); yield "pages list"
    ev("""() => { const r = document.querySelector('#pages .row'); r && r.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, clientX: 300, clientY: 300 })); }""")
    frame.wait_for_timeout(200); yield "page menu"
    page.keyboard.press("Escape"); ev("() => document.body.click()"); frame.wait_for_timeout(150)
    frame.click("#cPage"); frame.wait_for_timeout(250)
    ev("""() => { const r = document.querySelector('#pages .row.dv'); r && r.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, clientX: 300, clientY: 300 })); }""")
    frame.wait_for_timeout(200); yield "divider menu"
    page.keyboard.press("Escape"); ev("() => document.body.click()"); frame.wait_for_timeout(150)
    if ev("() => !!document.querySelector('#cProj') && getComputedStyle(document.querySelector('#cProj')).display !== 'none'"):
        frame.click("#cProj"); frame.wait_for_timeout(200); yield "board name menu"
        page.keyboard.press("Escape")
    for ids, name in ((["i2"], "a frame selected"), (["i2", "i3"], "two frames selected"), (["n1"], "a note selected"), (["t1"], "a heading selected"), (["t1", "t2"], "two headings selected"),
                      (["g1"], "a group selected"), (["i0"], "a rated frame selected"), (["m1"], "a missing file selected")):
        ev(f"() => {{ sel = new Set({json.dumps(ids)}); render(); if (typeof renderInfo === 'function') renderInfo(); }}")
        frame.wait_for_timeout(250); yield name
        ev(f"""() => {{ const id = {json.dumps(ids[0])}, el = document.querySelector(`[data-id="${{id}}"]`) || document.querySelector('#stage');
            const r = el.getBoundingClientRect(); el.dispatchEvent(new MouseEvent('contextmenu', {{ bubbles: true, clientX: r.left + 10, clientY: r.top + 10 }})); }}""")
        frame.wait_for_timeout(200); yield name + ": context menu"
        page.keyboard.press("Escape"); frame.wait_for_timeout(100)
    ev("() => { sel = new Set(); render(); const s = document.querySelector('#stage'); s.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, clientX: 600, clientY: 700 })); }")
    frame.wait_for_timeout(200); yield "empty canvas: context menu"
    frame.click('#ctx [data-act="view"]'); frame.wait_for_timeout(300); yield "link copied toast"
    ev("() => { sel = new Set(['i4']); render(); }"); page.keyboard.press("c"); frame.wait_for_timeout(300); yield "crop"
    page.keyboard.press("Escape"); frame.wait_for_timeout(150)
    ev("() => newTimeline(false)"); frame.wait_for_timeout(300); yield "a new timeline"
    page.keyboard.press("Escape")
    ev("() => newNote(false)"); frame.wait_for_timeout(300); yield "a new note"
    page.keyboard.press("Escape"); frame.wait_for_timeout(150)
    ev("() => toggleFav(['i5'])"); frame.wait_for_timeout(300); yield "like toast"


def open_board(browser, port, where):
    page = browser.new_page(viewport={"width": 1400, "height": 900}, permissions=[])
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{port}/{where}")
    if where.startswith("canvas"):
        frame = page.main_frame
    else:
        frame = page.wait_for_selector("#cvFrame").content_frame()
    frame.wait_for_function("() => typeof board !== 'undefined' && Object.keys(board.items).length >= 8", timeout=20000)
    page.wait_for_timeout(600)
    return page, frame, errors


@pytest.mark.parametrize("where", ["canvas.html", ""])   # the board alone, and the library with the board in it
def test_english_by_default_shows_no_russian(tmp_path, browser, where):
    port, process, log, _ = start(tmp_path, None)
    try:
        page, frame, errors = open_board(browser, port, where)
        assert page.evaluate("document.documentElement.lang") == "en"
        leaks = {}
        for name in board_states(page, frame):
            found = page.evaluate(CRAWL)
            if found: leaks[name] = found
        assert not leaks, json.dumps(leaks, ensure_ascii=False, indent=1)
        assert not errors, errors
    finally:
        process.terminate(); process.wait(5); log.close()


def test_russian_has_every_word(tmp_path, browser):
    port, process, log, _ = start(tmp_path, "ru")
    try:
        page, frame, errors = open_board(browser, port, "")
        assert page.evaluate("document.documentElement.lang") == "ru"
        assert "Библиотека" in frame.inner_text("#tlib")
        for _ in board_states(page, frame):
            pass
        assert page.evaluate(MISS) == []
        assert not errors, errors
    finally:
        process.terminate(); process.wait(5); log.close()


def test_switching_language_reloads_open_pages(tmp_path, browser):
    """The switch is the first thing in the board's settings; the page reloads in the chosen language with the settings open again,
    the app's settings file keeps it, and another open page takes it when the settings sync arrives."""
    port, process, log, settings = start(tmp_path, None)
    try:
        page, frame, _ = open_board(browser, port, "")
        other = browser.new_page(viewport={"width": 1200, "height": 800})
        other.goto(f"http://127.0.0.1:{port}/canvas.html")
        other.wait_for_function("() => typeof board !== 'undefined' && Object.keys(board.items).length >= 8", timeout=20000)
        assert other.evaluate("T.lang") == "en"
        frame.click("#bset"); frame.evaluate("s => hySetPanel.go(s)", "appearance")
        assert frame.inner_text("#sets .sp .sp-l") == "Language"   # the first row (ui/setpanel.js)
        with page.expect_navigation():
            frame.click('#sets [data-set=lang] [data-v="ru"]')
        page.wait_for_function("() => document.documentElement.lang === 'ru'")
        for _ in range(50):
            if json.loads(settings.read_text()).get("cv.lang") == "ru": break
            time.sleep(0.1)
        assert json.loads(settings.read_text())["cv.lang"] == "ru"
        frame = page.frames[-1]
        frame.wait_for_function("() => typeof board !== 'undefined' && document.querySelector('#sets').classList.contains('open')", timeout=20000)
        assert frame.evaluate("document.querySelector('#sets [data-set=lang] [data-v=ru]').getAttribute('aria-checked')") == "true"
        assert re.search(r"[Ѐ-ӿ]", frame.inner_text("#tlib"))
        # the other page: its settings sync (on focus, or the app's call) brings the change and it reloads in Russian
        with other.expect_navigation():
            other.evaluate("window.hyimgSettingsPull()")
        other.wait_for_function("() => typeof T !== 'undefined' && T.lang === 'ru'", timeout=20000)
        # and back to English
        frame.click("#bset") if not frame.evaluate("document.querySelector('#sets').classList.contains('open')") else None
        with page.expect_navigation():
            frame.click('#sets [data-set=lang] [data-v="en"]')
        page.wait_for_function("() => document.documentElement.lang === 'en'")
    finally:
        process.terminate(); process.wait(5); log.close()


def start_library(tmp, lang):
    """a library with a rated frame, questions, marks, a reference, a pasted picture, a rejected one and folders"""
    lib, state = tmp / "lib", tmp / "state"
    for k, f in enumerate(["a/1.png", "a/2.png", "a/3.png", "ext/x.png", "added/261006/y.png", "_rejected/r.png", "loose.png", "deep/sub/z.png"]):
        (lib / f).parent.mkdir(parents=True, exist_ok=True); (lib / f).write_bytes(png(40 + k, 60))   # different pictures: the library folds copies
    (lib / "a/1.json").write_text(json.dumps({"prompt": "a red phone https://example.com", "model": "gpt-image",
        "feedback": {"verdict": "take", "fav": True, "scores": {"idea": 3, "casting": 1, "real": 3, "case": 3}, "comment": "c", "use": ["Реклама"], "good": ["Идея"], "bad": ["Кич"],
                     "notes": [{"kind": "box", "pts": [[.1, .1], [.4, .4]], "text": "x"}], "updated": "2026-10-06 10:00"},
        "questions": [{"id": "q1", "q": "What did you mean?", "a": ""}, {"id": "q2", "q": "And this?", "a": "yes", "answered": "2026-10-06 11:00"}],
        "qa": {"gate": {"status": "fail", "reasons": ["blur"], "warnings": ["soft"]}}}))
    (lib / "a/2.json").write_text(json.dumps({"feedback": {"verdict": "no", "updated": "2026-10-06 10:00"}, "model": "midjourney"}))
    (state / "boards").mkdir(parents=True, exist_ok=True)
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {"i1": {"path": "a/1.png", "x": 0, "y": 0, "w": 300, "ar": .66}},
        "groups": {}, "removed": {"a/2.png": 1}}))
    (tmp / "settings.json").write_text(json.dumps({"cv.lang": "ru"} if lang == "ru" else {}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp / "settings.json"),
               PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    return port, process, log


def library_states(page, port):
    """the library's states, its viewer, the folder-layout menu and dialog, the old tag page; yields a name after each"""
    page.goto(f"http://127.0.0.1:{port}/?view=lib"); page.wait_for_selector("#list .card"); page.wait_for_timeout(500); yield "list"
    page.locator("#list .card").first.click(button="right"); page.wait_for_selector("#lctx.open"); yield "card menu"
    page.keyboard.press("Escape")
    page.click("#tfBtn"); page.wait_for_selector("#tfPanel:not([hidden]) .fchip"); yield "filter window"
    page.locator('#tfGroups .fchip[data-id^="tag:"] .fl').first.click(); page.locator('#tfGroups .fchip[data-id^="tag:"] .fl').nth(1).click(modifiers=["Alt"]); yield "tag chips"
    page.locator('#tfGroups .fchip[data-id="take"] .pn').click(); page.locator('#tfGroups .fchip[data-id="fav"] .pn').click(); yield "pins changed"
    page.locator('#tfGroups .fchip[data-id="take"] .pn').click(); page.locator('#tfGroups .fchip[data-id="fav"] .pn').click()   # pinned back: the rating chips are pressed below
    page.click("#tgOpen"); yield "add a tag"
    page.click("#tgOpen"); page.click("#tfClear"); page.mouse.click(5, 400)
    page.locator(".fdrawer .frow").nth(1).click(modifiers=["Meta"]); yield "folder marks"
    page.click("[data-fclear]")
    page.locator(".fdrawer .frow").nth(1).click(); page.wait_for_timeout(200); yield "folder chosen"
    page.locator(".fsMore").first.click(); page.wait_for_timeout(200); yield "folder layout menu"
    page.locator('[data-fs="plan"]').first.click(); page.wait_for_selector("#fsDlg"); page.wait_for_timeout(600); yield "folder layout dialog"
    page.locator("#fsDlg [data-x]").first.click(); page.wait_for_timeout(200)
    page.click("#reset"); page.click("label.chk"); yield "rejects"
    page.click("label.chk")
    for f in ["none", "take", "ask", "score:real:3", "score:case:3"]:
        page.click(f'#vf button[data-f="{f}"]'); yield "filter " + f
    page.click('#vf button[data-f=""]')
    page.locator("#list .card .pick").first.click(); yield "picked"
    page.keyboard.press("Escape")
    page.fill("#q", "zzzz-nothing"); page.wait_for_timeout(100); yield "nothing found"
    page.fill("#q", "")
    page.locator('#list .card[aria-label="1"]').first.click(); page.wait_for_selector("#viewer.open"); page.wait_for_timeout(300); yield "viewer"
    page.click("#help"); yield "viewer help"
    page.locator("#det summary").click(); yield "viewer details"
    b = page.locator("#big").bounding_box()
    page.mouse.move(b["x"] + b["width"] * .6, b["y"] + b["height"] * .6); page.mouse.down(); page.mouse.move(b["x"] + b["width"] * .8, b["y"] + b["height"] * .8, steps=4); page.mouse.up()
    page.wait_for_selector("#pop:not([hidden])"); yield "mark on a frame"
    page.keyboard.press("Escape")
    page.click('#verdicts button[data-v="idea"]'); page.wait_for_timeout(400); yield "rating saved"
    page.click("#next"); page.wait_for_timeout(300); yield "next frame"
    page.keyboard.press("Escape")
    page.goto(f"http://127.0.0.1:{port}/?view=panel"); page.wait_for_selector("#list .card"); page.wait_for_timeout(1500)
    page.click("#lviewBtn"); yield "library over the canvas: view panel"
    page.keyboard.press("Escape")
    page.click("#lwide"); page.wait_for_timeout(700); yield "wide library"
    page.goto(f"http://127.0.0.1:{port}/v1"); page.wait_for_selector("#list .card"); yield "old tag page"
    page.locator('#list .card[aria-label="1"]').first.click(); page.wait_for_selector("#viewer.open"); page.locator("#det summary").click(); yield "old tag page viewer"


@pytest.mark.parametrize("lang", ["en", "ru"])
def test_library_in_each_language(tmp_path, browser, lang):
    port, process, log = start_library(tmp_path, lang)
    try:
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        leaks, miss = {}, set()
        for name in library_states(page, port):
            if lang == "en":
                found = page.evaluate(CRAWL)
                if found: leaks[name] = found
            miss.update(page.evaluate(MISS))
        assert not leaks, json.dumps(leaks, ensure_ascii=False, indent=1)
        assert not miss, miss
        assert not errors, errors
    finally:
        process.terminate(); process.wait(5); log.close()


def test_every_literal_key_has_its_russian():
    """T("...") with a literal key anywhere in the pages and the shared modules: its Russian is in the dictionaries (a missing one
    would show English in the Russian interface)"""
    import shutil
    if not shutil.which("node"): pytest.skip("no node")
    ui = ROOT / "review/ui"
    js = "const D = {};global.window = {};global.hyLang = d => { for (const l of Object.keys(d)) Object.assign(D[l] = D[l] || {}, d[l]); };" \
         + "".join(f"require({json.dumps(str(p))});" for p in sorted(ui.glob("lang-*.js")) + [ui / "i18n.js"] if p.name != "i18n.js") \
         + "console.log(JSON.stringify(Object.keys(D.ru || {})));"
    have = set(json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout))
    have |= {"just now", "{n} min ago", "{n} h ago", "{n} d ago"}   # i18n.js's own
    missing = {}
    for f in [*(ROOT / "review").glob("*.html"), *(p for p in ui.glob("*.js") if p.name != "i18n.js")]:   # i18n.js: its examples
        for k in re.findall(r'\bT\("((?:[^"\\]|\\.)*)"', f.read_text(encoding="utf-8")):
            k = json.loads(f'"{k}"')
            if k not in have: missing.setdefault(f.name, []).append(k)
    assert not missing, json.dumps(missing, ensure_ascii=False, indent=1)
