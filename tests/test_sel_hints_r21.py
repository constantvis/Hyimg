"""What is picked, said two ways at once (owner 2026-10-11 on round 21, row 24: ♥ A «Совет под выделением», and on B «почему нужно выбирать
между одним и другим, когда тут можно сделать Б версию с общими командами и А версию с какими-то подсказками такими детальными»; round 20,
question 15 began it). review/ui/boardhints.js, ui/hy/nudge.js, ui/hy/keyhint.js. Chromium, the dark theme, our own temporary server and
library, never the ports 4180–4184.

  B         the Hint bar at the top: the selection's general keys (one picture ↵ Open, ⇧C Crop, ⇧2 Zoom to it; several ⌥A Grid, ⌘G Group,
            ⇧2 Zoom to them) every time, never learned away
  A         one tip under the selection, at its left edge, after 1 s: the first thing not yet learned, its keys as caps; its keys pressed
            once: learned and gone, the next selection says the next thing; 3 times the long way (the zoom's menu) or 30 days unused: back
  ×         closes the tips here; the «?» panel's Key hints switch brings them back
  OFF       Key hints off: neither

  nice -n 10 python3 -m pytest -q tests/test_sel_hints_r21.py
"""
import json

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from test_p4_studio_keys import board, serve  # noqa: E402

BAR = """() => { const h = document.querySelector('hy-keyhint[place=top][data-ctx=sel][shown]');
  return h ? [...h.querySelectorAll('.kh-i')].map(i => i.dataset.id) : null; }"""
TIP = """() => { const n = document.querySelector('hy-nudge[shown]'); if (!n) return null; const r = n.getBoundingClientRect(), b = document.querySelector('#handles .selbox');
  const s = b ? b.getBoundingClientRect() : null;
  return { id: n.dataset.id, caps: [...n.querySelectorAll('hy-kbd')].map(k => k.textContent).join(''), words: n.querySelector('.ng-t').textContent,
    under: !!s && r.top >= s.bottom - 1 && Math.abs(r.left - s.left) < 3, h: Math.round(r.height) }; }"""
COUNTS = "() => JSON.parse(localStorage.getItem('cv.keyhintUsed') || '{}')"


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    with serve(tmp_path_factory.mktemp("selhints")) as s: yield s


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try: b = p.chromium.launch()
        except Exception as e: pytest.skip(f"no Chromium for Playwright: {e}")
        yield b; b.close()


def pick(page, *ids):
    page.evaluate("(ids) => { sel = new Set(); render(); }", list(ids)); page.wait_for_timeout(400)
    page.evaluate("(ids) => { sel = new Set(ids); render(); }", list(ids))


def test_the_bar_and_the_tip_of_a_selection(srv, browser):
    port, _ = srv
    page, errors = board(browser, port)
    page.evaluate("() => { localStorage.setItem('cv.keyhint', 'learn'); localStorage.removeItem('cv.keyhintUsed'); localStorage.removeItem('cv.keyhintLast'); }")
    page.mouse.move(700, 120)
    page.evaluate("() => { window.__t0 = performance.now(); sel = new Set(['a1']); render(); }")
    page.wait_for_function(f"() => ({BAR})()", timeout=3000)
    assert page.evaluate(BAR) == ["open", "crop", "zoom"]
    page.wait_for_function(f"() => ({TIP})()", timeout=4000)
    assert page.evaluate("() => performance.now() - __t0") >= 900, "the tip waits for the selection to stand 1 s"
    t = page.evaluate(TIP)
    assert t["id"] == "zoom" and t["caps"] == "⇧2" and t["words"] == "zooms to it" and t["under"] and t["h"] == 28, t
    page.keyboard.press("Shift+Digit2")   # its keys: learned, the tip and the bar go
    page.wait_for_function(f"() => !({TIP})() && !({BAR})()", timeout=3000)
    assert page.evaluate(COUNTS)["nudge.sel.zoom"] == 1
    # the next selection says the next thing, the bar again as it was
    pick(page, "a1"); page.wait_for_function(f"() => ({TIP})()", timeout=4000)
    assert page.evaluate(TIP)["id"] == "crop" and page.evaluate(BAR) == ["open", "crop", "zoom"]
    # several: Grid, Group, Zoom to them in the bar, «lays them out as a grid» under them
    pick(page, "a1", "e1"); page.wait_for_function(f"() => ({TIP})()", timeout=4000)
    assert page.evaluate(BAR) == ["grid", "group", "zoom"] and page.evaluate(TIP)["id"] == "grid"
    assert not errors, errors
    page.close()


def test_the_long_way_forgetting_close_and_off(srv, browser):
    port, _ = srv
    page, errors = board(browser, port)
    page.evaluate("""() => { localStorage.setItem('cv.keyhint', 'learn'); localStorage.removeItem('cv.keyhintLast');
      localStorage.setItem('cv.keyhintUsed', JSON.stringify({ 'nudge.sel.zoom': 1 })); }""")
    page.mouse.move(700, 120)
    # three times through the zoom's menu (the long way): the tip of ⇧2 comes back
    for _ in range(3):
        page.evaluate("() => { sel = new Set(['a1']); render(); }"); page.click("#bfit"); page.locator('#bzoomm [data-zoom="sel"]').click()
    assert "nudge.sel.zoom" not in page.evaluate(COUNTS)
    pick(page, "a1"); page.wait_for_function(f"() => ({TIP})()", timeout=4000)
    assert page.evaluate(TIP)["id"] == "zoom"
    # forgotten: learned, but its last use more than a month ago
    page.evaluate(f"""() => {{ localStorage.setItem('cv.keyhintUsed', JSON.stringify({{ 'nudge.sel.zoom': 1 }}));
      localStorage.setItem('cv.keyhintLast', JSON.stringify({{ 'nudge.sel.zoom': Math.floor(Date.now() / 864e5) - 40 }})); }}""")
    pick(page, "a1"); page.wait_for_function(f"() => ({TIP})()", timeout=4000)
    assert page.evaluate(TIP)["id"] == "zoom"
    # × closes the tips here; the «?» panel's Key hints switch, off and on, brings them back
    page.locator("hy-nudge .ng-x").click()
    assert page.evaluate(COUNTS)["nudge.sel@off"] == 1
    pick(page, "a1"); page.wait_for_timeout(1600); assert page.evaluate(TIP) is None
    page.click("#bkeys"); page.wait_for_selector("#keys.open .kp-show")
    for _ in range(2): page.locator('#keys .kp-show [data-kpset=keyhint] hy-minitoggle input').click()
    assert page.evaluate("localStorage.getItem('cv.keyhint')") == "learn" and "nudge.sel@off" not in page.evaluate(COUNTS)
    page.click("#bkeys")
    pick(page, "a1"); page.wait_for_function(f"() => ({TIP})()", timeout=4000)
    # Key hints off: neither the bar nor the tip
    page.evaluate("() => localStorage.setItem('cv.keyhint', 'off')")
    pick(page, "e1"); page.wait_for_timeout(1600)
    assert page.evaluate(TIP) is None and page.evaluate(BAR) is None
    assert not errors, errors
    page.close()
