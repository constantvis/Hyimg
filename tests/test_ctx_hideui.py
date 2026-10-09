"""The right-click menu opens at the pointer with the interface hidden too (owner 2026-10-09: «когда я отключаю весь интерфейс, я нажимаю на
правую кнопку, и у меня улетает моя правая кнопка, что не должно быть: правая кнопка должна оставаться у моего нажатия»).

⌘. hides the interface by giving its parts an animation that ends invisible: grown 1.18 around the window's centre («zoom») or slid off
their edge («slide»). The menu was one of those parts, so a menu opened while hidden played the same animation from its first frame: it grew
away from the click and faded. The menu now closes when the interface hides and opens where it is clicked, hidden or not, its submenus too;
near the window's edges it still flips and clamps to stay on screen.
Runs in Chromium, dark, on a temporary library only."""
import pytest

from test_menu_grey import server, open_board   # noqa: F401  (the fixture and the board of a picture, a PDF, a note and a group)

playwright = pytest.importorskip("playwright.sync_api")

# the menu's box and what it looks like a moment after it opened: where it is, how big against its own layout size, how visible
BOX = """() => { const m = document.querySelector('#ctx'), r = m.getBoundingClientRect(), s = getComputedStyle(m);
  return { x: r.left, y: r.top, w: r.width, ow: m.offsetWidth, oh: m.offsetHeight, op: +s.opacity, anim: s.animationName, pe: s.pointerEvents }; }"""


def right_click(page, x, y):
    page.mouse.click(x, y, button="right")
    page.wait_for_selector("#ctx.open [role=menuitem]")
    page.wait_for_timeout(450)   # longer than the hiding animation (.36 s): a menu that plays it has flown by now
    return page.evaluate(BOX)


def at_pointer(box, x, y, vw, vh):
    # the menu's top-left is the click, or it is clamped 8 px inside the window when the click is that close to an edge
    ex = min(x, vw - box["ow"] - 8); ey = max(8, min(y, vh - box["oh"] - 8))
    return abs(box["x"] - ex) <= 2 and abs(box["y"] - ey) <= 2 and abs(box["w"] - box["ow"]) <= 1 and box["op"] > 0.99


@pytest.mark.parametrize("mode", ["zoom", "slide"])
def test_menu_at_the_pointer_with_the_interface_hidden(server, mode):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, "chromium", server["port"])
        vw, vh = 1400, 1000
        page.evaluate("m => localStorage.setItem('cv.hideui', m)", mode)
        page.evaluate("() => { cam.x = -60; cam.y = -60; cam.z = 1; renderCam(); render(); }")   # the picture covers 60..360 × 60..510
        page.wait_for_timeout(200)
        # shown: the reference
        box = right_click(page, 200, 150)
        assert at_pointer(box, 200, 150, vw, vh), box
        page.keyboard.press("Escape")
        # hidden (⌘. as the owner does)
        page.keyboard.press("Meta+Period"); page.wait_for_timeout(500)
        assert page.evaluate("() => document.documentElement.classList.contains('hy-hideui')")
        for x, y, what in [(80, 80, "p"), (200, 150, "p"), (340, 480, "p"), (120, 300, "p"), (900, 100, "n"), (560, 900, "G")]:   # a picture, a note, a group
            box = right_click(page, x, y)
            assert page.evaluate("() => [...sel].join()") == what, (x, y)
            assert at_pointer(box, x, y, vw, vh), (mode, x, y, box)
            assert box["pe"] != "none", box   # it can be clicked
            page.keyboard.press("Escape")
        # the empty board, near the bottom-right corner: flipped and clamped inside the window, nothing more
        box = right_click(page, vw - 20, vh - 20)
        assert at_pointer(box, vw - 20, vh - 20, vw, vh), box
        page.keyboard.press("Escape")
        # a submenu sits beside its row, not flown off with an animation either
        right_click(page, 200, 150)
        page.locator("#ctx [data-sub=order]").hover()
        page.wait_for_selector("#ctx .hy-sub [role=menuitem]"); page.wait_for_timeout(450)
        sub = page.evaluate("""() => { const s = document.querySelector('#ctx .hy-sub'), r = s.getBoundingClientRect(), row = document.querySelector('#ctx [data-sub=order]').getBoundingClientRect();
          return { dx: Math.min(Math.abs(r.left - row.right), Math.abs(r.right - row.left)), dy: r.top - row.top, w: r.width, ow: s.offsetWidth, op: +getComputedStyle(s).opacity }; }""")
        assert sub["dx"] < 24 and abs(sub["dy"]) < 24 and abs(sub["w"] - sub["ow"]) <= 1 and sub["op"] > 0.99, sub
        page.keyboard.press("Escape")
        # a menu open when ⌘. hides the interface closes with it, and shown again the menu opens at the pointer as before
        page.keyboard.press("Meta+Period"); page.wait_for_timeout(500)
        right_click(page, 200, 150)
        page.keyboard.press("Meta+Period"); page.wait_for_timeout(500)
        assert not page.evaluate("() => $('#ctx').classList.contains('open')")
        page.keyboard.press("Meta+Period"); page.wait_for_timeout(500)
        box = right_click(page, 250, 200)
        assert at_pointer(box, 250, 200, vw, vh), box
        assert not errors, errors
        browser.close()
