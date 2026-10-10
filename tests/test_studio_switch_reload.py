"""The Studio switch's tooltips, ⌘R and leaving a page with a Studio's work (owner decisions 2026-10-10). ui/modes.js with two fake Studios,
Chromium, the dark theme, a temporary board; each fails on the code before:

- a greyed Studio segment says why and what to do: on the Board what to select (hint), inside another Studio what to open (hintStudio)
- ⌘R is never the board's or a Studio's (owner 2026-10-10): in the app View › Reload Page has no key, in a browser the tab reloads
- a browser asks before it unloads a Studio's unsaved work, not the board's own (it saves as it goes)
- a page switch (leaveFirst) waits for a Studio's work still being written and stays when the write was refused

  nice -n 10 python3 -m pytest tests/test_studio_switch_reload.py
"""
from playwright.sync_api import sync_playwright

from test_modes import srv  # noqa: F401  (the fixture: a board with a fake plugin «fake» and its card f1)

APP_UA = "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 HyimgCEF"
# a second Studio for no card on this board, with the words for both places, and hooks the test sets
TWO = """() => { window.__pend = null; window.__unsaved = false;
  HY.mode("two", { fit: false, label: "Two", name: "Two Studio", order: 7, icon: "<svg width=16 height=16></svg>", title: "Two for its card",
    hint: "Select a two card to use Two Studio", hintStudio: "Open a two card to use Two Studio",
    isOpen: () => false, target: () => null, enter() {}, leave() {}, pending: () => window.__pend, unsaved: () => window.__unsaved }); }"""


def open_board(p, port, ua=None):
    br = p.chromium.launch(); ctx = br.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark", **({"user_agent": ua} if ua else {}))
    page = ctx.new_page(); errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{port}/canvas.html")
    page.wait_for_function("() => typeof MODES !== 'undefined' && MODES && document.querySelector('#modes button[data-mode=fake]')", timeout=20000)
    page.evaluate(TWO); page.wait_for_selector("#modes button[data-mode=two]")
    return br, page, errors


def tip(page, key):
    page.mouse.move(5, 5); page.wait_for_timeout(500)
    page.hover(f"#modes button[data-mode={key}]"); page.wait_for_function("() => document.getElementById('modetip').classList.contains('on')", timeout=3000)
    return page.locator("#modetip").inner_text()


def test_greyed_segments_say_what_to_do(srv):
    port, lib = srv
    with sync_playwright() as p:
        br, page, errors = open_board(p, port)
        page.evaluate("() => { sel = new Set(); render(); }"); page.wait_for_timeout(200)
        assert page.get_attribute("#modes button[data-mode=two]", "aria-disabled") == "true"
        t = tip(page, "two")
        assert "Two Studio" in t and "Select a two card to use Two Studio" in t, t
        # inside a Studio nothing can be selected: the tooltip says what to open instead
        page.evaluate("() => MODES.enter('fake', ['f1'])"); page.wait_for_function("() => MODES.open === 'fake'")
        t = tip(page, "two")
        assert "Open a two card to use Two Studio" in t and "Select" not in t, t
        assert page.get_attribute("#modes button[data-mode=two]", "aria-description") == "Open a two card to use Two Studio"
        assert not errors, errors
        br.close()


CMD_R = """() => { const e = new KeyboardEvent('keydown', { key: 'r', code: 'KeyR', metaKey: true, cancelable: true, bubbles: true });
  dispatchEvent(e); return e.defaultPrevented; }"""


def test_cmd_r_is_never_ours(srv):
    """⌘R is never taken by the board or a Studio: in the app the menu's Reload Page has no key (nothing happens), in a browser it reloads"""
    port, lib = srv
    with sync_playwright() as p:
        for ua in (APP_UA, None):
            br, page, errors = open_board(p, port, ua)
            assert page.evaluate("() => hyLink.inApp") == bool(ua)
            assert page.evaluate(CMD_R) is False, "the board took ⌘R"
            page.evaluate("() => MODES.enter('fake', ['f1'])"); page.wait_for_function("() => MODES.open === 'fake'")
            assert page.evaluate(CMD_R) is False, "a Studio without a reload of its own took ⌘R"
            assert not errors, errors
            br.close()


def test_unload_question_and_a_page_switch_waits(srv):
    port, lib = srv
    with sync_playwright() as p:
        br, page, errors = open_board(p, port)
        ask = "() => { const e = new Event('beforeunload', { cancelable: true }); dispatchEvent(e); return e.defaultPrevented; }"
        page.wait_for_timeout(1500)   # the board saved what it loaded
        assert page.evaluate(ask) is False, "the board asked with nothing to lose"
        page.evaluate("() => { window.__unsaved = true; }")
        assert page.evaluate(ask) is True, "a Studio's unsaved work: no question"
        page.evaluate("() => { window.__unsaved = false; }")
        # a write still running: leaveFirst waits for it; refused, the page stays
        got = page.evaluate("""() => { let done; window.__pend = new Promise(ok => { done = ok; }); const t0 = performance.now();
          setTimeout(() => done(true), 400); return MODES.leaveFirst().then(ok => [ok, performance.now() - t0 >= 380]); }""")
        assert got == [True, True], got
        assert page.evaluate("() => { window.__pend = Promise.resolve(false); return MODES.leaveFirst(); }") is False
        page.evaluate("() => { window.__pend = null; }")
        assert page.evaluate("() => MODES.leaveFirst()") is True
        assert not errors, errors
        br.close()
