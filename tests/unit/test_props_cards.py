"""Which cards take which look in hy.py (do 'opacity …', 'grade …', 'props …'), as on the canvas (owner 2026-10-06: «a 3D object ... in the
end it is a picture»): a 3D card takes the opacity and the colour grade, an HTML card only the opacity, a note neither."""
import hy

CARDS = {"pic": {"path": "a/x.png"}, "video": {"path": "a/x.mp4"}, "frame": {"type": "imgframe"}, "model3d": {"type": "model3d", "scene": "3d/scenes/a/scene.json"},
         "htmlframe": {"type": "htmlframe", "src": "html/a/index.html"}, "html": {"type": "html", "src": "site/index.html"}, "note": {"type": "note", "text": "x"}}
WANT = {"opacity": {"pic", "video", "frame", "model3d", "htmlframe", "html"}, "grade": {"pic", "frame", "model3d"}}


def test_the_looks_go_to_the_cards_that_show_a_picture():
    for kind, want in WANT.items():
        got = {n for n, it in CARDS.items() if hy.prop_applies(kind, it)}
        assert got == want, (kind, got)


def test_a_3d_card_keeps_its_opacity_and_grade():
    it = dict(CARDS["model3d"])
    hy.prop_set("opacity", it, 0.5); hy.prop_set("grade", it, {"exposure": 0.3})
    assert it["opacity"] == 0.5 and it["grade"] == {"exposure": 0.3}
    assert hy.prop_has("opacity", it) and hy.prop_has("grade", it)
