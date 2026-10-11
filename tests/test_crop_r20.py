"""The crop's bar, round 20 (owner 2026-10-11 on the crop as it was: «недостаточность форматов и описании при наведении»; the coordinator's
pick of crop-b.html for the buttons). More formats a designer needs (1.91:1 and 21:9 beside 1:1, 4:5, 3:4, 2:3, 9:16), every pill named on
the plate over it, X still turns them all; Cancel and Done ↵ in the bar, while a press beside the picture still does nothing (P4 B-46,
2026-10-10). Each test failed on the code before: there were five ratios, 3:2 and 4:3 had no name, the bar had no buttons.
Chromium, dark theme, our own server and folders (tests/test_p4_board.py's harness), the mouse for every gesture."""
import pytest

from test_crop_frame import ITEMS, WIN, crop, run
from test_p4_board import box, saved, serve, settle, browser_of, board_page

playwright = pytest.importorskip("playwright.sync_api")

LABELS = "() => [...document.querySelectorAll('#crop .cratio button[data-ratio]')].map(b => b.textContent.trim() || b.dataset.ratio)"
TIP = "() => { const t = document.querySelector('#crop .cratio .rtip.on'); return t && getComputedStyle(t).opacity === '1' ? t.textContent : null; }"


def hover(page, k):
    b = box(page, f"#crop .cratio button[data-k='{k}']"); page.mouse.move(b["cx"], b["cy"]); page.wait_for_timeout(250)
    return page.evaluate(TIP)


def test_the_formats_a_designer_needs_each_named_and_turned_by_x(tmp_path):
    def go(page, ev):
        crop(page, ev)
        assert ev(LABELS) == ["Free", "1:1", "5:4", "4:3", "3:2", "1.91:1", "16:9", "21:9", "flip"]
        names = {k: hover(page, k) for k in ("1:1", "5:4", "4:3", "3:2", "1.91:1", "16:9", "21:9")}
        assert all(names.values()), ("every format says what it is", names)
        assert names["21:9"] == "Cinema · Ultrawide" and names["1.91:1"] == "Facebook · LinkedIn · X link" and names["16:9"] == "YouTube"
        b = box(page, "#crop .cratio button[data-k='21:9']"); page.mouse.click(b["cx"], b["cy"])
        assert ev(WIN)[2:] == [720, 309], "the biggest 21:9 frame in a 720 × 480 picture"
        b = box(page, "#crop .cratio button[data-k='1.91:1']"); page.mouse.click(b["cx"], b["cy"])
        assert ev(WIN)[2:] == [720, 377]
        page.mouse.move(5, 890); page.keyboard.press("x")
        assert ev(LABELS) == ["Free", "1:1", "4:5", "3:4", "2:3", "1:1.91", "9:16", "9:21", "flip"], "X turns every pill"
        assert ev(WIN)[2:] == [251, 480], "1:1.91, the biggest that stands in the picture"
        assert hover(page, "9:21") and hover(page, "1:1.91")
    run(tmp_path, go)


def test_done_and_cancel_in_the_bar_and_a_press_beside_still_does_nothing(tmp_path):
    with serve(tmp_path, ITEMS) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        try:
            crop(page, ev)
            words = ev("() => [...document.querySelectorAll('#crop .cratio [data-cropend]')].map(b => [b.dataset.cropend, b.textContent.trim()])")
            assert words == [["cancel", "Cancel"], ["done", "Done↵"]], words
            done = box(page, "#crop .cratio [data-cropend=done]"); bar = box(page, "#crop .cratio")
            assert done["x"] + done["w"] <= bar["x"] + bar["w"] + 0.5, "Done is the bar's last button"
            assert ev("() => getComputedStyle(document.querySelector('#crop [data-cropend=done]')).backgroundColor") != "rgba(0, 0, 0, 0)", "Done is filled"
            b = box(page, "#crop .cratio button[data-k='1:1']"); page.mouse.click(b["cx"], b["cy"])
            # a press beside the picture: the crop stays open, nothing applied (2026-10-10)
            w = ev(WIN); page.mouse.click(w[0] + 900, w[1] + 200); page.wait_for_timeout(150)
            assert ev("() => !!cropState") and ev("() => board.items.i0.crop") is None
            # Cancel: the crop closes, the picture as it was
            c = box(page, "#crop .cratio [data-cropend=cancel]"); page.mouse.click(c["cx"], c["cy"])
            page.wait_for_function("() => !cropState"); assert ev("() => board.items.i0.crop") is None
            assert ev("() => getComputedStyle(document.querySelector('#crop')).display") == "none"
            # Done: the square frame is the picture's crop, saved
            crop(page, ev); b = box(page, "#crop .cratio button[data-k='1:1']"); page.mouse.click(b["cx"], b["cy"])
            d = box(page, "#crop .cratio [data-cropend=done]"); page.mouse.click(d["cx"], d["cy"])
            page.wait_for_function("() => !cropState"); settle(page, port)
            c = saved(port)["items"]["i0"]["crop"]
            assert c and abs((c[2] - c[0]) * 720 - (c[3] - c[1]) * 480) < 1, ("a square crop", c)
            assert not ev("() => document.querySelector('#crop').innerHTML"), "the bar went with the crop"
        finally: browser.close()
        assert not errors, errors
