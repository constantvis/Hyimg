"""A text's five sizes stay in its own scale, each one step about 1.75× (owner 2026-10-10: «text: при переключении с H1 или H2, и вот
уменьшение-увеличение текста, какая-то просто колоссальнейшая разница в размерах. Что-то там не так ты посчитал»). A text made zoomed in
is made smaller, as big on screen as at 100 % (ui/newsize.js); H2, H1 and the two A's jumped from there to the ladder's absolute sizes,
and H1 was 874 against H2's 128. Now (ui/textsize.js) the ladder is 24, 40, 72, 128, 224 times the text's scale: at 400 % a new text is
10, H2 32, H1 56; at 100 % 40, 128, 224. The size lit on the bar is the text's own. Made with the mouse, a double click on the empty
board, the size bar's buttons clicked. Chromium, dark."""
import pytest

from test_text_docs import open_board, server  # noqa: F401

playwright = pytest.importorskip("playwright.sync_api")
LADDER = [24, 40, 72, 128, 224]


def newest(page):
    return page.evaluate("() => { const t = Object.entries(board.items).filter(([, i]) => i.type === 'text').at(-1); return [t[0], t[1].fs]; }")


def lit(page):
    return page.evaluate("() => [...document.querySelectorAll('.tidy.tsz .hx.on')].map(b => b.textContent).join() + '|'"
                         " + ((document.querySelector('.tidy.tsz .tsl') || {}).textContent || '')")


@pytest.mark.parametrize("zoom", [4, 1])
def test_h1_h2_and_the_a_steps_keep_the_texts_own_scale(server, zoom):  # noqa: F811
    port, _env = server
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, port)
        page.evaluate(f"() => {{ cam = {{ x: -2000, y: -2000, z: {zoom} }}; renderCam(); render(); }}"); page.wait_for_timeout(300)
        page.mouse.dblclick(700, 450); page.wait_for_selector(".tx textarea", timeout=4000)
        page.keyboard.type("Size"); page.keyboard.press("Escape"); page.wait_for_timeout(200)
        tid, fs = newest(page); k = min(1, 1 / zoom)
        assert fs == pytest.approx(LADDER[1] * k), fs
        page.evaluate(f"() => {{ sel = new Set(['{tid}']); render(); }}"); page.wait_for_selector(".tidy.tsz")
        assert lit(page) == "|Regular", lit(page)
        sizes = []
        down, up = ".fz[title='Smaller text']", ".fz[title='Bigger text']"
        for q in ("[data-tsize='3']", "[data-tsize='4']", down, down, up, up):
            page.click(f".tidy.tsz {q}"); page.wait_for_timeout(150); sizes.append(page.evaluate(f"() => board.items['{tid}'].fs"))
        assert sizes == pytest.approx([x * k for x in (128, 224, 128, 72, 128, 224)]), sizes
        assert sizes[1] / sizes[0] == pytest.approx(1.75), "H1 is one step over H2"
        assert lit(page) == "H1|Big heading", lit(page)
        assert page.evaluate("() => document.querySelector(\".tidy.tsz .fz[title='Bigger text']\").disabled")
        # a text made zoomed in before the scale was kept: read from its size; an old Big heading of 874 keeps its size and lights none
        old = page.evaluate("() => [hyTextSize.k({ size: 1, fs: 10 }), hyTextSize.k({ size: 4, fs: 874 }), hyTextSize.cur({ size: 4, fs: 874 })]")
        assert old == [0.25, 1, -1], old
        assert not errors, errors
        browser.close()
