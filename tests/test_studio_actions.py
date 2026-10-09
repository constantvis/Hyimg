"""A Studio's session actions (owner 2026-10-09 on Dev Studio's dock: «кнопки Done у нас всегда стандартизированы справа вверху, а не внизу
... чтобы они везде были идентичны»; «Что такое Open? Может быть, Open in browser тогда нужно написать. И также добавить логотип ... кнопку
со стрелочкой, чтобы выбрать браузер»): ui/hy/actions.js and ui/hy/openin.js on a temporary board, no plugin. The element stands in the top
row just left of the round buttons, the row's gap apart, at the row's line and height; the secondary actions in the order given, the one
primary last, filled with the colour of where it stands and white words, its key in the tooltip and as the key cap. «Open in <Browser>»
without the Mac app is «Open in browser» with no icon and no chevron and opens a new tab; with the app (a stand-in for native/Browsers.swift
through hyBrowsers.via) it names the default browser with its icon, its chevron lists the browsers with their icons and the default marked,
a choice opens the page there and becomes the main part's browser, Esc closes the menu and nothing else. Chromium, dark."""
import json, os, socket, subprocess, sys, time, urllib.request, uuid
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
# two tiny PNGs as the app sends them (data URLs), told apart by their size
ICON_S = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
ICON_F = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFklEQVR42mP8z8DwnwEJMDGgAQYGBgB2WgP9t2vXVQAAAABJRU5ErkJggg=="
LIST = {"op": "list", "default": "com.apple.Safari", "last": "",
        "browsers": [{"id": "org.mozilla.firefox", "name": "Firefox", "icon": ICON_F}, {"id": "com.apple.Safari", "name": "Safari", "icon": ICON_S},
                     {"id": "bad", "name": "Bad icon", "icon": "javascript:alert(1)"}]}
# the stand-in for the app: it records what the page sends and answers a list the way native/Browsers.swift does (window.hyimgBrowsers)
STUB = """(list) => { window.SENT = []; hyBrowsers.via(m => { SENT.push(m);
  if (m.op === 'list') setTimeout(() => hyimgBrowsers(list)); else if (m.op === 'open') setTimeout(() => hyimgBrowsers({ op: 'open', app: m.app, ok: true }));
  return true; }); }"""
MOUNT = """(acts) => { const w = document.createElement('div'); w.id = 'wrap'; w.style.setProperty('--sel', 'rgb(47, 174, 106)'); document.body.append(w);
  window.RAN = []; const a = document.createElement('hy-studio-actions'); w.append(a);
  a.actions = acts.map(x => x.open ? { ...x, open: () => '/lib/a/page.html' } : { ...x, run: () => RAN.push(x.id) }); }"""
ACTS = [{"id": "done", "label": "Done", "tip": "Done", "key": "Esc", "primary": True}, {"id": "reload", "label": "Reload", "tip": "Reload the page"},
        {"id": "open", "open": True, "tip": "Open the page alone in a new tab"}]
BOX = "(s) => { const r = document.querySelector(s).getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.height)]; }"
GO = """() => { const g = document.querySelector('hy-open-in .oi-go'), i = g.querySelector('img');
  return [g.textContent, i ? i.getAttribute('src') : null, document.querySelector('hy-open-in .oi-more').hidden]; }"""
ROWS = """() => [...document.querySelectorAll('.hy-oi-menu [data-b]')].map(b => { const i = b.querySelector('img');
  return [b.dataset.b, b.querySelector('.oi-n').textContent, i ? i.getAttribute('src') : null, b.getAttribute('aria-checked'), (b.querySelector('.oi-def') || {}).textContent || '']; })"""


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture
def srv(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    for p in (lib / "a", state / "boards"): p.mkdir(parents=True)
    (lib / "a/page.html").write_text("<html><head><title>Page</title></head><body>hi</body></html>")
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    (tmp_path / "home").mkdir()
    env.update(HOME=str(tmp_path / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    try:
        yield port
    finally:
        proc.terminate(); proc.wait(5); log.close()


def board(p, port):
    br = p.chromium.launch()
    ctx = br.new_context(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    page = ctx.new_page(); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{port}/canvas.html")
    page.wait_for_function("() => customElements.get('hy-studio-actions') && customElements.get('hy-open-in') && document.getElementById('bntf')", timeout=20000)
    return br, ctx, page, errors


def test_actions_top_right_in_order_primary_last(srv):
    with sync_playwright() as p:
        br, ctx, page, errors = board(p, srv)
        page.evaluate(MOUNT, ACTS); page.wait_for_timeout(300)
        # the secondary ones in the order given, the primary last, whatever its place in the list
        assert page.evaluate("() => [...document.querySelectorAll('hy-studio-actions > *')].map(b => b.localName + ':' + b.dataset.a)") == \
            ["hy-button:reload", "hy-open-in:open", "hy-button:done"]
        # in the top row: its line (12) and height (38), the row's gap (8) left of the bell, the leftmost of the round buttons
        acts, bell = page.evaluate(BOX, "hy-studio-actions"), page.evaluate(BOX, "#bntf")
        assert acts[1] == bell[1] == 12 and acts[3] == 38 and acts[2] == bell[0] - 8, (acts, bell)
        for s in ("hy-studio-actions [data-a=reload]", "hy-studio-actions [data-a=open]", "hy-studio-actions [data-a=done]"):
            assert page.evaluate(BOX, s)[1:4:2] == [12, 38], s
        # the primary: the colour of where it stands (the wrapper's --sel), white words, a check; the others on the row's glass
        done = page.evaluate("() => { const b = document.querySelector('hy-studio-actions [data-a=done]'), c = getComputedStyle(b); "
                             "return [b.getAttribute('variant'), c.backgroundColor, c.color, !!b.querySelector('svg'), b.title, b.querySelector('kbd').textContent]; }")
        assert done == ["accent", "rgb(47, 174, 106)", "rgb(255, 255, 255)", True, "Done · Esc", "Esc"], done
        reload = page.evaluate("() => { const b = document.querySelector('hy-studio-actions [data-a=reload]'); return [b.getAttribute('variant'), getComputedStyle(b).backgroundColor, b.title]; }")
        assert reload[0] is None and reload[1] != "rgb(47, 174, 106)" and reload[2] == "Reload the page", reload
        page.click("hy-studio-actions [data-a=reload]"); page.click("hy-studio-actions [data-a=done]")
        assert page.evaluate("RAN") == ["reload", "done"]
        # ⌘. hides the row and the actions with it
        assert page.evaluate("() => document.querySelector('hy-studio-actions').hasAttribute('data-hyui')")
        assert not errors, errors
        br.close()


def test_open_in_browser_without_the_app(srv):
    with sync_playwright() as p:
        br, ctx, page, errors = board(p, srv)
        page.evaluate(MOUNT, ACTS); page.wait_for_timeout(300)
        # no app to ask: the plain words, no icon, no chevron; its tooltip the studio's
        assert page.evaluate(GO) == ["Open in browser", None, True]
        assert page.evaluate("() => document.querySelector('hy-open-in .oi-go').title") == "Open the page alone in a new tab"
        with ctx.expect_page() as tab:
            page.click("hy-open-in .oi-go")
        new = tab.value; new.wait_for_load_state()
        assert new.url == f"http://127.0.0.1:{srv}/lib/a/page.html", new.url
        assert not errors, errors
        br.close()


def test_open_in_the_browsers_of_the_app(srv):
    with sync_playwright() as p:
        br, ctx, page, errors = board(p, srv)
        page.evaluate(STUB, LIST); page.evaluate(MOUNT, ACTS)
        page.wait_for_function("() => document.querySelector('hy-open-in .oi-go').textContent === 'Open in Safari'", timeout=5000)
        # the system's default with its own icon; the chevron is there; the page asked the app for its browsers
        assert page.evaluate(GO) == ["Open in Safari", ICON_S, False]
        assert {"action": "browsers", "op": "list"} in page.evaluate("SENT")
        # the menu: every browser with its icon, the default marked, the main part's one checked; a bad icon is dropped, its row stays
        page.click("hy-open-in .oi-more"); page.wait_for_selector(".hy-oi-menu")
        assert page.evaluate(ROWS) == [["org.mozilla.firefox", "Firefox", ICON_F, "false", ""], ["com.apple.Safari", "Safari", ICON_S, "true", "Default"],
                                       ["bad", "Bad icon", None, "false", ""]]
        menu, btn = page.evaluate(BOX, ".hy-oi-menu"), page.evaluate(BOX, "hy-open-in")
        assert menu[1] > btn[1] + btn[3] and menu[2] == btn[2], (menu, btn)   # under the button, its right edge on the button's
        # Esc closes the menu, and the press goes no further (a studio would leave on it)
        page.evaluate("() => { window.ESC = 0; addEventListener('keydown', e => { if (e.key === 'Escape') ESC++; }); }")
        page.keyboard.press("Escape")
        assert page.evaluate("() => [!!document.querySelector('.hy-oi-menu'), ESC, document.querySelector('hy-open-in .oi-more').getAttribute('aria-expanded')]") == [False, 0, "false"]
        # a choice opens the page in that browser, the whole address; it becomes the main part's
        page.click("hy-open-in .oi-more"); page.click(".hy-oi-menu [data-b='org.mozilla.firefox']")
        page.wait_for_function("() => document.querySelector('hy-open-in .oi-go').textContent === 'Open in Firefox'", timeout=5000)
        sent = [m for m in page.evaluate("SENT") if m["op"] == "open"]
        assert sent == [{"action": "browsers", "op": "open", "url": f"http://127.0.0.1:{srv}/lib/a/page.html", "app": "org.mozilla.firefox"}], sent
        assert not page.evaluate("() => !!document.querySelector('.hy-oi-menu')") and page.evaluate(GO)[1] == ICON_F
        # the main part opens there now, through the app, no tab of its own
        page.click("hy-open-in .oi-go")
        assert [m["app"] for m in page.evaluate("SENT") if m["op"] == "open"] == ["org.mozilla.firefox", "org.mozilla.firefox"]
        assert len(ctx.pages) == 1
        assert not errors, errors
        br.close()


def test_the_last_chosen_browser_comes_from_the_app(srv):
    with sync_playwright() as p:
        br, ctx, page, errors = board(p, srv)
        page.evaluate(STUB, dict(LIST, last="org.mozilla.firefox")); page.evaluate(MOUNT, ACTS)
        page.wait_for_function("() => document.querySelector('hy-open-in .oi-go').textContent === 'Open in Firefox'", timeout=5000)
        page.click("hy-open-in .oi-more"); page.wait_for_selector(".hy-oi-menu")
        assert [r[3] for r in page.evaluate(ROWS)] == ["true", "false", "false"] and page.evaluate(ROWS)[1][4] == "Default"
        # a last one the app no longer has: the default again
        page.keyboard.press("Escape"); page.evaluate(STUB, dict(LIST, last="gone.browser")); page.evaluate("() => hyBrowsers.ask()")
        page.wait_for_function("() => document.querySelector('hy-open-in .oi-go').textContent === 'Open in Safari'", timeout=5000)
        assert not errors, errors
        br.close()
