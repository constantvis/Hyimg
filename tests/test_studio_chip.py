"""The Studio chip on the bar over a selected card (owner 2026-10-10 on round 19, Concepts r19/switch-d.html: «Отличная идея, очень нравится,
делаем»): one card a Studio opens, and the bar starts with «Image Studio ↵», «3D Studio ↵» or «Dev Studio ↵» in that Studio's colour, a
hairline after it; a click or ↵ opens that Studio as the dock's switch does. Nothing selected, two cards or a note: no chip. The bar with
the chip stays on screen and off the Info card in a narrow window with the card at the top. The plugins beside this repository, Chromium,
dark, our own temporary server and library.

  nice -n 10 python3 -m pytest -q tests/test_studio_chip.py
"""
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from test_p4_studio_keys import Dev, Image, Studio3D, blur, board, serve  # noqa: E402

CHIP = """() => { const t = document.querySelector('#handles .tidy'), b = t && t.querySelector('[data-studiochip]'); if (!b) return null;
  return [b.dataset.studiochip, b.textContent.trim(), t.firstElementChild === b, (b.nextElementSibling || {}).className, b.style.getPropertyValue('--hy-mode-c'),
    getComputedStyle(b).backgroundColor !== 'rgba(0, 0, 0, 0)']; }"""
NOTE = {"type": "note", "text": "n", "x": 0, "y": 1300, "w": 300, "fs": 14, "size": 2, "h": 0, "color": "yellow"}


def pick(page, *ids):
    """the cards clicked with the mouse, ⇧ for the next ones"""
    page.mouse.click(5, 5); page.evaluate("() => { sel = new Set(); render(); }")
    for n, i in enumerate(ids):
        b = page.locator(f"#items [data-id='{i}']").bounding_box()
        if n: page.keyboard.down("Shift")
        page.mouse.click(b["x"] + 30, b["y"] + 30)
        if n: page.keyboard.up("Shift")
    page.wait_for_timeout(250)


def test_the_chip_names_the_cards_studio_and_opens_it(tmp_path):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        br = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page, errors = board(br, port)
        page.evaluate(f"() => {{ board.items.n1 = {NOTE}; render(); }}")
        page.evaluate("() => { cam.x = -100; cam.y = -150; cam.z = 0.5; renderCam(); render(); }"); page.wait_for_timeout(500)
        for cid, key, name, colour in (("a1", "image", "Image Studio", "var(--frame)"), ("c", "3d", "3D Studio", "var(--pink)"), ("e1", "dev", "Dev Studio", "var(--dev)")):
            pick(page, cid)
            assert page.evaluate(CHIP) == [key, name + "↵", True, "sep", colour, True], (cid, page.evaluate(CHIP))
        # nothing, two cards, a note: no chip
        page.mouse.click(5, 5); page.evaluate("() => { sel = new Set(); render(); }"); page.wait_for_timeout(200)
        assert page.evaluate(CHIP) is None
        pick(page, "a1", "e1"); assert page.evaluate(CHIP) is None, "a chip over two cards"
        pick(page, "n1"); assert page.evaluate(CHIP) is None, "a chip over a note"
        # a click opens the picture's Image Studio, ↵ the 3D card's and the HTML card's Studio
        pick(page, "a1"); page.locator("#handles .tidy [data-studiochip]").click()
        page.wait_for_function("() => MODES.open === 'image'", timeout=30000); st = Image(page).open(); st.close()
        page.wait_for_function("() => MODES.open === 'board'", timeout=10000)
        pick(page, "c"); blur(page); page.keyboard.press("Enter")
        page.wait_for_function("() => MODES.open === '3d'", timeout=30000)
        assert page.evaluate("() => document.querySelector('.plg-live').dataset.id") == "c"
        Studio3D(page, lib).close(); page.wait_for_function("() => MODES.open === 'board'", timeout=10000)
        pick(page, "e1"); blur(page); page.keyboard.press("Enter")
        page.wait_for_function("() => MODES.open === 'dev' && __dev.D && __dev.D.id === 'e1'", timeout=30000)
        Dev(page, lib).close()
        assert not errors, errors
        br.close()


def test_the_bar_with_the_chip_stays_on_screen_and_off_the_info_card(tmp_path):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        br = p.chromium.launch(); page, errors = board(br, port)
        page.set_viewport_size({"width": 900, "height": 640}); page.wait_for_timeout(400)
        for cid in ("a1", "c", "e1"):
            # the card at the very top of the board, then at its left edge
            for cam in ("{ x: board.items[ID].x - 40, y: board.items[ID].y - 4, z: 0.6 }", "{ x: board.items[ID].x + 40, y: board.items[ID].y - 30, z: 0.6 }"):
                page.evaluate(f"() => {{ const ID = '{cid}'; cam = {cam}; renderCam(); sel = new Set([ID]); render(); }}"); page.wait_for_timeout(500)
                r = page.evaluate("""() => { const t = document.querySelector('#handles .tidy').getBoundingClientRect(), i = document.getElementById('info'),
                  f = i && i.style.display !== 'none' && i.getClientRects().length ? i.getBoundingClientRect() : null;
                  return { t: [t.left, t.top, t.right, t.bottom], over: !!f && t.left < f.right && f.left < t.right && t.top < f.bottom && f.top < t.bottom,
                    chip: !!document.querySelector('#handles .tidy [data-studiochip]') }; }""")
                l, t, rr, b = r["t"]
                assert r["chip"] and l >= 0 and t >= 0 and rr <= 900 and b <= 640, (cid, cam, r)
                assert not r["over"], (cid, cam, r)
        assert not errors, errors
        br.close()
