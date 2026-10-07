"""What the owner's arrangement on a board means (layout.py: rows, series in a row, blocks, sections) and the questions an agent asks
about a picture (ask.py), live.py's geometry."""
import json

import pytest

import ask
import layout
import live

U = layout.UNIT


def pics(*xy, w=U, ar=1.0):
    return {f"p{n}": {"path": f"{n}.png", "x": x, "y": y, "w": w, "ar": ar} for n, (x, y) in enumerate(xy)}


def R(items):
    return {i: layout.rect(v) for i, v in items.items()}


class TestRowsAndSeries:
    def test_pictures_sharing_half_their_height_are_one_row_ordered_left_to_right(self):
        it = pics((0, 0), (350, 150), (700, 0), (0, 1000))
        assert layout.rows(it, R(it)) == [["p0", "p1", "p2"], ["p3"]]

    def test_a_picture_less_than_half_in_the_band_starts_its_own_row(self):
        it = pics((0, 0), (350, 170))
        assert layout.rows(it, R(it)) == [["p0"], ["p1"]]

    def test_a_cropped_picture_is_as_tall_as_its_crop(self):
        assert layout.rect({"x": 1, "y": 2, "w": 100, "ar": 0.5, "crop": [0, 0, 1, 0.5]}) == (1, 2, 100, 100)

    def test_the_usual_gap_is_the_median_of_the_others_or_the_gutter(self):
        assert layout.usual([0.1, 0.2, 5.0], skip=2) == pytest.approx(0.15)
        assert layout.usual([0.5]) == layout.GUTTER and layout.usual([0.01, 0.02, 0.03]) == layout.GUTTER

    def test_a_gap_much_wider_than_the_rows_usual_one_splits_it_into_series(self):
        gap = 24
        xs = [0, U + gap, 2 * (U + gap), 2 * (U + gap) + U + 5 * U, 2 * (U + gap) + U + 5 * U + U + gap]
        it = pics(*((x, 0) for x in xs))
        row = layout.rows(it, R(it))[0]
        segs, unsure = layout.segments(row, R(it))
        assert segs == [["p0", "p1", "p2"], ["p3", "p4"]] and unsure == []

    def test_a_gap_between_one_and_a_half_and_two_times_is_reported_as_unsure(self):
        g = 0.2 * U
        xs = [0, U + g, 2 * (U + g), 2 * (U + g) + U + 0.35 * U]   # the last gap 0.35 U: 1.75 times the usual 0.2 U
        it = pics(*((x, 0) for x in xs))
        segs, unsure = layout.segments(layout.rows(it, R(it))[0], R(it))
        assert len(segs) == 1 and len(unsure) == 1


class TestBlocks:
    def test_an_empty_band_much_wider_than_the_others_splits_a_group_into_blocks(self):
        it = pics((0, 0), (0, U + 24), (0, 2 * (U + 24)), (0, 3 * (U + 24) + 4 * U))
        b = layout.build({"items": it, "groups": {"g": {"title": " G ", "members": list(it)}}}, "main")
        g = b["groups"][0]
        assert g["title"] == "G" and g["kind"] == "group" and [len(bl["rows"]) for bl in g["blocks"]] == [3, 1]

    def test_pictures_in_no_group_are_one_inferred_scope(self):
        b = layout.build({"items": pics((0, 0)), "groups": {}}, "main")
        assert b["groups"][0]["kind"] == "loose" and b["groups"][0]["status"] == "inferred"

    def test_ids_are_stable_for_the_same_pictures(self):
        it = pics((0, 0), (400, 0))
        a, b = layout.build({"items": it, "groups": {}}, "main"), layout.build({"items": dict(reversed(list(it.items()))), "groups": {}}, "main")
        assert a["groups"][0]["blocks"][0]["id"] == b["groups"][0]["blocks"][0]["id"]

    def test_a_big_title_heads_the_groups_below_it_and_a_small_one_captions_what_is_right_under_it(self):
        it = pics((0, 400))
        it["big"] = {"type": "text", "text": "Section", "x": 0, "y": 0, "w": 800, "h": 200, "fs": 200}
        it["cap"] = {"type": "text", "text": "Caption", "x": 0, "y": 300, "w": 200, "h": 30, "fs": 20}
        b = layout.build({"items": it, "groups": {}}, "main")
        assert b["sections"][0]["title"] == "Section" and b["sections"][0]["groups"] == [b["groups"][0]["id"]]
        assert b["groups"][0]["captions"] == ["Caption"]


class TestQuestions:
    @pytest.fixture
    def lib(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ask, "W", str(tmp_path))
        return tmp_path

    def test_a_question_is_added_once_numbered_and_kept_outside_feedback(self, lib):
        (lib / "a").mkdir(); (lib / "a" / "x.json").write_text(json.dumps({"feedback": {"fav": True}}))
        assert ask.add("a/x.png", "Why blue?", "pick") is True
        assert ask.add("a/x.png", "Why blue?") is False
        assert ask.add("a/x.png", "And red?") is True
        meta = json.loads((lib / "a" / "x.json").read_text())
        assert [q["id"] for q in meta["questions"]] == ["q1", "q2"] and meta["questions"][0]["kind"] == "pick" and meta["feedback"] == {"fav": True}

    def test_a_picture_without_a_sidecar_gets_one(self, lib):
        ask.add("x.png", "?")
        assert json.loads((lib / "x.json").read_text())["questions"][0]["a"] == ""


class TestLive:
    def test_a_note_or_title_without_a_size_has_one_from_its_font(self):
        assert live.rect({"type": "text", "x": 1, "y": 2, "fs": 10}) == (1, 2, 1, 12)

    def test_a_picture_without_a_shape_is_taken_as_three_by_four(self):
        assert live.rect({"x": 0, "y": 0, "w": 75}) == (0, 0, 75, 100)
