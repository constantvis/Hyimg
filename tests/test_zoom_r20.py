"""The board's zoom (owner 2026-10-11 on round 20, question 15, ♥ A «Меню зума у процента»: «идеально»): review/ui/boardzoom.js,
ui/boardkeys.js, ui/keyspanel.js. The hints on a selection the owner added there: tests/test_sel_hints_r21.py. Chromium, the dark theme,
our own temporary server and library, never the ports 4180–4184.

  KEYS      ⇧2 to the selection, ⇧0 100 %, ⌘= (⌘+) in, ⌘− out, ⇧1 everything, on the board
  MENU      a click on the view % opens the zoom's menu: its five rows with their icons and keys, 50 % and 200 %; to the selection is grey
            with nothing picked
  «?»       All keys has the zoom's rows from the same table (words, keys, icons), no stale rows (pages, the second library key, show all)

  nice -n 10 python3 -m pytest -q tests/test_zoom_r20.py
"""
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from test_p4_studio_keys import board, serve  # noqa: E402

# the camera fits these ids as canvas.html fit() does: the screen box of their union
BOX = """(ids) => { const b = bbox(ids), r = stage.getBoundingClientRect(); return { x: (b.x - cam.x) * cam.z + r.left, y: (b.y - cam.y) * cam.z + r.top,
  w: b.w * cam.z, h: b.h * cam.z, W: r.width, H: r.height, z: cam.z }; }"""


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    with serve(tmp_path_factory.mktemp("zoom")) as s: yield s


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try: b = p.chromium.launch()
        except Exception as e: pytest.skip(f"no Chromium for Playwright: {e}")
        yield b; b.close()


def click_card(page, cid, shift=False):
    b = page.locator(f".it[data-id={cid}], .plg[data-id={cid}]").first.bounding_box()
    if shift: page.keyboard.down("Shift")
    page.mouse.click(b["x"] + b["width"] * .5, b["y"] + b["height"] * .6)
    if shift: page.keyboard.up("Shift")


def test_the_zoom_keys_on_the_board(srv, browser):
    port, _ = srv
    page, errors = board(browser, port)
    click_card(page, "a1"); page.wait_for_function("() => sel.has('a1') && sel.size === 1")
    page.mouse.move(700, 120); page.keyboard.press("Shift+Digit2"); page.wait_for_timeout(150)
    b = page.evaluate(BOX, ["a1"])
    assert b["w"] > 700 and abs(b["x"] + b["w"] / 2 - b["W"] / 2) < 4, f"⇧2 did not bring the selection in: {b}"   # in the middle, big
    page.keyboard.press("Shift+Digit0"); assert page.evaluate("cam.z") == 1
    page.keyboard.press("Meta+Equal"); assert page.evaluate("cam.z") == 2
    page.keyboard.press("Meta+Minus"); page.keyboard.press("Meta+Minus"); assert page.evaluate("cam.z") == 0.5
    page.keyboard.press("Shift+Digit1"); page.wait_for_timeout(100)
    b = page.evaluate(BOX, ["a1", "c", "e1"]); assert b["x"] >= 0 and b["y"] >= 0 and b["x"] + b["w"] <= b["W"] + 1, b   # everything in sight
    assert page.evaluate("document.body.style.zoom || '1'") == "1"
    assert not errors, errors
    page.close()


def test_the_menu_at_the_view_percent(srv, browser):
    port, _ = srv
    page, errors = board(browser, port)
    page.evaluate("() => { sel.clear(); render(); }")
    page.click("#bfit"); page.wait_for_selector("#bzoomm:not([hidden])")
    rows = page.evaluate("""() => [...document.querySelectorAll('#bzoomm > button')].map(b => [b.dataset.zoom, b.querySelector('.ml').textContent,
      [...b.querySelectorAll('.mk kbd')].map(k => k.textContent).join(''), b.getAttribute('aria-disabled') === 'true', (b.querySelector('svg') || {}).outerHTML || ''])""")
    want = page.evaluate("""() => hyBoardZoom.ROWS.map(([id, ic, w, k]) => { const d = document.createElement('div'); d.innerHTML = hyIcon(ic, 15, 1.9);
      return [id, w, k.join(''), d.firstElementChild.outerHTML]; })""")
    assert [r[:3] for r in rows] == [[w[0], w[1], w[2]] for w in want] + [["z0.5", "50 %", ""], ["z2", "200 %", ""]], rows
    assert [r[3] for r in rows][:5] == [False, True, False, False, False], "to the selection is grey with nothing picked"
    for r, w in zip(rows, want): assert r[4] and r[4].replace(' data-ic-done="1"', "") == w[3], (r[0], r[4][:80], w[3][:80])   # the icon of the table
    page.locator('#bzoomm [data-zoom="100"]').click(); assert page.evaluate("cam.z") == 1
    assert page.evaluate("document.getElementById('bzoomm').hidden")
    page.click("#bfit"); page.locator('#bzoomm [data-zoom="z2"]').click(); assert page.evaluate("cam.z") == 2
    assert page.evaluate("document.getElementById('zl').textContent") == "200%"
    assert not errors, errors
    page.close()


def test_the_keys_panel_has_the_zooms_rows_and_none_stale(srv, browser):
    port, _ = srv
    page, errors = board(browser, port)
    page.click("#bkeys"); page.wait_for_selector("#keys.open"); page.click("#keys [data-kt=all].kp-tab")
    rows = page.evaluate("""() => [...document.querySelectorAll('#keys .kp-all .kp-row')].map(r => [[...r.querySelectorAll('.k kbd')].map(k => k.textContent).join(''),
      r.querySelector('.t').textContent.trim(), r.querySelector('.kpi').dataset.icon || ''])""")
    want = page.evaluate("() => hyBoardZoom.ROWS.map(([id, ic, w, k]) => [k.join(''), w, ic])")
    for w in want: assert w in rows, (w, [r for r in rows if r[0] == w[0]])
    keys = [r[0] for r in rows]
    for k in ("⇧1", "⇧2", "⇧0", "⌘+", "⌘−"): assert keys.count(k) == 1, k
    assert not [r for r in rows if r[1].startswith(("the first button of the bar", "show all", "the library, as")) or "another page" in r[1]], "stale rows"
    assert [r for r in rows if "library" in r[1].lower() and "M" in r[0]] == [["⌘M\\", "the library: open, close", "library"]]
    assert dict((r[0], r[2]) for r in rows)["R"] == "fit"   # the whole frame, not the frame's #
    main = page.evaluate("() => [...document.querySelectorAll('#keys .kp-main .kp-row')].map(r => r.querySelector('.t').textContent)")
    assert "Zoom to fit" in main and "Show all" not in main and len(main) == 9   # round 15's nine rows, ⇧1 from the zoom's table
    assert not errors, errors
    page.close()
