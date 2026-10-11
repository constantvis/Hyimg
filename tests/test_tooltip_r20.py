"""The one tooltip of the app (owner 2026-10-11 on round 20, question 11, ♥ A «Одна своя подсказка»: «идеально!!! и возможность их отключить
в Tips and shortcuts и в настройках тоже, при этом у нас 2 вида»): review/ui/hy/tooltip.js, <hy-tooltip id=hytip>. Chromium, the dark
theme, our own temporary server and library with the plugins beside this repository, never the ports 4180–4184.

  LOOK      glass (a blur under it), 30 px, the round look's capsule, the words and the keys as caps («Undo ⌘ Z»)
  TIMING    the first after a rest of about 400 ms, the next button at once; a press hides it
  NATIVE    the system's tooltip never shows: the title rests in data-hy-title while the pointer is on it, VoiceOver keeps aria-label
  WHERE     the board's dock, the library (v2.html), Home (a file page, a classic script), Image Studio (its data-tip and data-key)
  SWITCHES  Settings › Interface › Tooltips and the «?» panel's «Tooltips» are one setting (cv.tooltips); the «?» panel's «Key hints» is
            Settings' Key hints (cv.keyhint): off there, no Hint bar, no nudge

  nice -n 10 python3 -m pytest -q tests/test_tooltip_r20.py
"""
import json
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from test_p4_studio_keys import Image, board, serve  # noqa: E402

HOME = (Path(__file__).resolve().parents[1] / "review/home.html").as_uri()
TIP = """() => { const t = document.getElementById('hytip'); if (!t || !t.hasAttribute('shown')) return null; const s = getComputedStyle(t), r = t.getBoundingClientRect();
  return { text: t.textContent, words: (t.querySelector('.tt-t') || {}).textContent || '', sub: (t.querySelector('.tt-s') || {}).textContent || '',
    caps: [...t.querySelectorAll('hy-kbd')].map(k => k.textContent), h: Math.round(r.height), blur: s.backdropFilter || s.webkitBackdropFilter || '',
    radius: s.borderTopLeftRadius, top: r.top, bottom: r.bottom }; }"""
# the time from the pointer's arrival to the tooltip showing these words, measured in the page: window.__tt (ms, -1 never)
CLOCK = """(words) => { window.__tt = null; const t0 = performance.now(); const tick = () => {
  const t = document.getElementById('hytip'); if (t && t.hasAttribute('shown') && t.textContent.startsWith(words)) { window.__tt = performance.now() - t0; return; }
  if (performance.now() - t0 > 3000) { window.__tt = -1; return; } requestAnimationFrame(tick); }; tick(); }"""


def mid(page, sel, frame=None):
    b = (frame or page).locator(sel).first.bounding_box()
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


def hover_clock(page, sel, words, ev=None):
    """the pointer onto sel; how long until the tooltip says words (ms, -1 never)"""
    x, y = mid(page, sel)
    ev = ev or page
    ev.evaluate(CLOCK, words); page.mouse.move(x, y)
    ev.wait_for_function("() => window.__tt !== null", timeout=5000)
    return ev.evaluate("window.__tt")


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    with serve(tmp_path_factory.mktemp("tooltip")) as s: yield s


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try: b = p.chromium.launch()
        except Exception as e: pytest.skip(f"no Chromium for Playwright: {e}")
        yield b; b.close()


def test_the_boards_dock_shows_the_one_tooltip_after_a_rest_and_the_next_at_once(srv, browser):
    port, _ = srv
    page, errors = board(browser, port)
    page.mouse.move(700, 500); page.wait_for_timeout(300)
    ms = hover_clock(page, "#bundo", "Undo")
    assert 330 <= ms <= 1200, f"the first tooltip came after {ms} ms, not about 400"
    t = page.evaluate(TIP)
    assert t["words"] == "Undo" and t["caps"] == ["⌘", "Z"], t
    assert t["h"] == 30 and "blur" in t["blur"] and t["radius"] in ("999px", "15px"), t
    assert t["bottom"] <= mid(page, "#bundo")[1], "the dock's tooltip stands over the dock"
    ms2 = hover_clock(page, "#bredo", "Redo")
    assert 0 <= ms2 < 200, f"the next button's tooltip took {ms2} ms"
    assert page.evaluate(TIP)["caps"] == ["⇧", "⌘", "Z"]
    # a title of the board's own: words and keys from «Create: a note, a text, a timeline…», no system tooltip while it shows
    page.mouse.move(700, 500); page.wait_for_function("() => !document.querySelector('#hytip[shown]')")
    page.wait_for_timeout(500)
    assert hover_clock(page, "#bplus", "Create") > 0
    assert page.evaluate("() => { const b = document.getElementById('bplus'); return [b.getAttribute('title'), b.dataset.hyTitle, b.getAttribute('aria-label')]; }") \
        == [None, "Create: a note, a text, a timeline…", "Create"]
    page.mouse.move(700, 500); page.wait_for_function("() => !document.querySelector('#hytip[shown]')")
    assert page.evaluate("document.getElementById('bplus').getAttribute('title')") == "Create: a note, a text, a timeline…", "the title came back for VoiceOver"
    # a press hides it and it does not come back while the pointer stays on that button
    page.wait_for_timeout(600); hover_clock(page, "#bredo", "Redo"); page.mouse.down(); page.mouse.up()
    page.wait_for_timeout(700); assert page.evaluate(TIP) is None
    assert not errors, errors
    page.close()


def test_the_mode_switch_and_the_steps_use_it_too(srv, browser):
    port, _ = srv
    page, errors = board(browser, port)
    page.mouse.move(700, 500); page.wait_for_timeout(300)
    assert hover_clock(page, "#modes button[data-mode=board]", "Board") > 0
    assert page.evaluate(TIP)["words"] == "Board" and page.evaluate("() => !document.getElementById('modetip')")
    assert page.evaluate("() => !document.getElementById('hydkstep')"), "the dock's own plate is gone"
    assert not errors, errors
    page.close()


def test_the_library_has_the_same_tooltip(srv, browser):
    port, _ = srv
    page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    page.goto(f"http://127.0.0.1:{port}/?view=lib"); page.wait_for_selector("#tfBtn")
    page.wait_for_function("() => !!window.hyTooltip"); page.mouse.move(700, 600); page.wait_for_timeout(300)
    ms = hover_clock(page, "#tfBtn", "Filters")
    assert 330 <= ms <= 1200, ms
    assert page.evaluate("document.getElementById('tfBtn').getAttribute('title')") is None
    page.close()


def test_home_a_file_page_has_it_and_its_switch(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };")
    page.goto(HOME)
    page.evaluate(f"hyimgHome({json.dumps({'projects': [], 'settings': {'cv.theme': 'dark'}, 'home': {'folders': []}})})")
    page.wait_for_function("() => !!window.hyTooltip"); page.mouse.move(700, 600); page.wait_for_timeout(300)
    assert hover_clock(page, "#bset", "App settings") > 0
    page.mouse.move(700, 600); page.wait_for_timeout(600)
    page.evaluate(f"hyimgHome({json.dumps({'projects': [], 'settings': {'cv.theme': 'dark', 'cv.tooltips': '0'}, 'home': {'folders': []}})})")
    x, y = mid(page, "#bset"); page.mouse.move(x, y); page.wait_for_timeout(1000)
    assert page.evaluate(TIP) is None, "Tooltips off in the app's settings: none on Home"
    page.close()


def test_image_studio_takes_the_one_tooltip(srv, browser):
    port, _ = srv
    page, errors = board(browser, port)
    im = Image(page).open(); fr = im.fr
    assert fr.evaluate("() => !document.getElementById('tip') && !!window.hyTooltip")
    # a button of the page with its words and keys in data-tip and data-key, in sight (the first of them)
    want = fr.evaluate("""() => { const b = [...document.querySelectorAll('[data-tip][data-key]')].find(e => { const r = e.getBoundingClientRect();
      return r.width > 8 && r.left > 0 && document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)?.closest('[data-tip]') === e; });
      b.setAttribute('data-probe', ''); return [b.dataset.tip, b.dataset.key]; }""")
    page.mouse.move(700, 500); page.wait_for_timeout(600)
    b = fr.locator("[data-probe]").bounding_box(); fr.evaluate("() => { window.__t0 = performance.now(); }")
    page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    fr.wait_for_function("() => !!document.querySelector('#hytip[shown]')", timeout=3000)
    ms = fr.evaluate("() => performance.now() - __t0"); t = fr.evaluate(TIP)
    assert ms >= 300, ms
    assert t["words"] == want[0] and "".join(t["caps"]) == want[1].replace(" ", "") and len(t["caps"]) >= len(want[1].split(" ")), (t, want)   # a cap a key
    assert t["h"] == 30 and "blur" in t["blur"], t
    im.close()
    assert not errors, errors
    page.close()


def test_the_two_switches_in_settings_and_in_the_keys_panel(srv, browser):
    port, _ = srv
    page, errors = board(browser, port)
    page.evaluate("() => localStorage.setItem('cv.keyhint', 'learn')")
    # «?» › Tips › Show: Tooltips and Key hints, on
    page.click("#bkeys"); page.wait_for_selector("#keys.open .kp-show")
    rows = page.evaluate("""() => [...document.querySelectorAll('#keys .kp-show [data-kpset]')]
      .map(r => [r.dataset.kpset, r.textContent.trim(), r.querySelector('hy-minitoggle').hasAttribute('checked')])""")
    assert rows == [["tooltips", "Tooltips", True], ["keyhint", "Key hints", True]], rows
    page.locator('#keys .kp-show [data-kpset=tooltips] hy-minitoggle input').click()
    assert page.evaluate("localStorage.getItem('cv.tooltips')") == "0"
    page.click("#bkeys")
    page.mouse.move(700, 500); page.wait_for_timeout(300)
    x, y = mid(page, "#bundo"); page.mouse.move(x, y); page.wait_for_timeout(1000)
    assert page.evaluate(TIP) is None, "Tooltips off: no tooltip"
    # Settings › Interface shows the same setting, and turns it back on
    page.mouse.move(700, 500); page.click("#bset"); page.wait_for_selector("[data-row=tooltips]")
    assert page.evaluate("() => document.querySelector('[data-set-sw=tooltips]').hasAttribute('checked')") is False
    page.locator("[data-row=tooltips] hy-switch input").click()
    assert page.evaluate("localStorage.getItem('cv.tooltips')") == "1"
    page.keyboard.press("Escape"); page.mouse.move(700, 500); page.wait_for_timeout(300)
    assert hover_clock(page, "#bundo", "Undo") > 0
    # the hints' switch is Settings' Key hints: off, then the «?» panel shows it off
    page.mouse.move(700, 500); page.click("#bkeys"); page.wait_for_selector("#keys.open .kp-show")
    page.locator('#keys .kp-show [data-kpset=keyhint] hy-minitoggle input').click()
    assert page.evaluate("localStorage.getItem('cv.keyhint')") == "off"
    page.click("#bkeys"); page.click("#bset"); page.wait_for_selector("hy-segmented[data-set=keyhint]")
    assert page.evaluate("document.querySelector('hy-segmented[data-set=keyhint]').getAttribute('value')") == "off"
    assert not errors, errors
    page.close()


def test_the_crop_takes_the_one_hint_bar(srv, browser):
    """tips-a.html: «кадрирование берет общую строку подсказок под рядом» (board audit B-19: its own #hint line in the top row, all the time)"""
    port, _ = srv
    page, errors = board(browser, port)
    assert page.evaluate("() => !document.getElementById('hint')")
    page.evaluate("() => { sel = new Set(['a1']); render(); }"); page.mouse.move(700, 500); page.keyboard.press("Shift+C")
    page.wait_for_function("() => !!cropState && !!document.querySelector('hy-keyhint[place=top][data-ctx=crop][shown]')", timeout=4000)
    bar = page.evaluate("() => { const h = document.querySelector('hy-keyhint[data-ctx=crop]'), r = h.getBoundingClientRect();"
                        " return [[...h.querySelectorAll('.kh-i')].map(i => i.dataset.id), h.textContent, Math.round(r.top)]; }")
    assert bar[0] == ["ratio", "apply", "cancel"] and "X" in bar[1] and "↵" in bar[1] and "Esc" in bar[1] and 56 <= bar[2] <= 60, bar   # the line under the top row (--hy-row-under)
    page.keyboard.press("Escape"); page.wait_for_function("() => !cropState && !document.querySelector('hy-keyhint[data-ctx=crop][shown]')")
    assert not errors, errors
    page.close()
