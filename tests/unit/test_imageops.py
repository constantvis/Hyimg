"""hy.py image look (review/imageops.py, owner 2026-10-10: an agent reads coordinates off the picture before it selects): a line every 100 px
of the picture, labelled in the picture's own pixels, also on a part of it and when it is shown smaller; the card takes a saved version
as the board does (imgframe.js saved)."""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "review"))
import imageops  # noqa: E402


def test_grid_lines_fall_on_the_pictures_own_pixels():
    im = Image.new("RGB", (640, 480), (20, 20, 20))
    g, s = imageops.grid(im, 100)
    assert s == 1 and g.size == (640, 480)
    assert g.getpixel((300, 250))[0] > 100 and g.getpixel((350, 250))[0] < 40   # a line at x 300, none between
    # a part: the lines stay at the picture's hundreds, not the crop's
    g, s = imageops.grid(im, 100, crop=(150, 150, 300, 200))
    assert g.size == (300, 200) and g.getpixel((50, 120))[0] > 100 and g.getpixel((100, 120))[0] < 40   # x 200 is 50 px into the crop
    # shown smaller: the lines move with the picture
    g, s = imageops.grid(Image.new("RGB", (4000, 2000), (20, 20, 20)), 100, maxside=1000)
    assert g.size == (1000, 500) and s == 0.25 and g.getpixel((500, 400))[0] > 100   # x 2000


def test_saved_version_goes_onto_the_card():
    card = {"type": "imgframe", "x": 0, "y": 0, "w": 400, "h": 300, "name": "F", "doc": "frames/a/frame.1.json", "render": "frames/a/render.1.png", "v": 1,
            "grade": {"exposure": 1}, "alpha": True}
    imageops.apply_saved(card, {"name": "F", "size": [800, 800], "rv": 5, "pics": ["p.png"], "alpha": False, "doc": "frames/a/frame.2.json",
                                "render": "frames/a/render.2.png", "v": 2, "grade": None, "mask": None})
    assert card["v"] == 2 and card["doc"].endswith("frame.2.json") and card["h"] == 400 and "grade" not in card and "alpha" not in card and card["rv"] == 5
