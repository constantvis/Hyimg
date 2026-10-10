"""Annotations inside a Studio (owner 2026-10-09 on round 15: «3D у нас, естественно, тоже не хватает аннотаций, чтобы можно было так же
выделить какой-то слой и комментировать его ... Image Studio точно так же, чтобы я мог выбрать и слой»): a thread's anchor names the part
of the card it is tied to (review/comments.py clean_part), op place moves its pin on the card without an event, and the words for agents
(review/annotext.py) name the layer or the 3D object with its id and point."""
import json

import pytest

import unit_env  # noqa: F401
import annotext
import comments
import events
import people


@pytest.fixture
def root(tmp_path, lib):
    me = people.save_me(tmp_path, "Ann Lee", "green")
    return tmp_path, me["id"]


def by(person, via="app"): return {"person": person, "via": via}


def test_a_layer_and_a_3d_object_are_kept_in_the_anchor(root, lib):
    r, me = root
    layer = {"obj": "f1", "kind": "imgframe", "file": "frames/x/frame.1.json", "r": [0, 0, 1000, 450],
             "part": {"kind": "layer", "id": "p3_ab12", "name": "  Logo  ", "local": [0.5, 0.44], "area": [0.1, 0.2, 0.3, 0.4], "junk": 1}}
    t = comments.comment(r, "main", "new", by(me), {"anchor": layer, "at": [0.85, 0.44], "text": "Brighter here"})["thread"]
    assert t["anchor"]["part"] == {"kind": "layer", "id": "p3_ab12", "name": "Logo", "local": [0.5, 0.44], "area": [0.1, 0.2, 0.3, 0.4]}
    assert json.loads((lib / "comments" / f"main__{t['id']}.json").read_text())["anchor"]["part"]["id"] == "p3_ab12"
    obj = {"obj": "c", "kind": "model3d", "part": {"kind": "object", "id": "oqpn6rf1", "name": "Case", "layer": "Atlas/Case", "local": [0.01, -0.02, 0.3]}}
    t3 = comments.comment(r, "main", "new", by(me), {"anchor": obj, "at": [0.5, 0.5], "text": "Thinner edge"})["thread"]
    assert t3["anchor"]["part"]["layer"] == "Atlas/Case" and t3["anchor"]["part"]["local"] == [0.01, -0.02, 0.3]
    # what is not a part is left out, the anchor stays
    for bad in ({"kind": "pixel", "id": "x"}, {"kind": "layer", "id": "../x"}, {"kind": "layer"}, "layer"):
        assert "part" not in comments.clean_anchor({"obj": "f1", "part": bad})
    assert "local" not in comments.clean_part({"kind": "object", "id": "a", "local": [1, 2]})   # a 3D point has three numbers


def test_place_moves_the_pin_on_the_card_quietly(root, lib):
    r, me = root
    an = {"obj": "f1", "kind": "imgframe", "part": {"kind": "layer", "id": "p1", "name": "b", "local": [0.5, 0.5]}}
    t = comments.comment(r, "main", "new", by(me), {"anchor": an, "at": [0.85, 0.44], "text": "x"})["thread"]
    n = len(events.read("main"))
    t2 = comments.comment(r, "main", "place", by(me), {"id": t["id"], "at": [0.65, 0.51], "area": [0.5, 0.4, 0.2, 0.2]})["thread"]
    assert t2["at"] == [0.65, 0.51] and t2["area"] == [0.5, 0.4, 0.2, 0.2] and t2["updated"] == t["updated"]
    assert len(events.read("main")) == n   # no event: the layer moved, nobody wrote anything
    plain = comments.comment(r, "main", "new", by(me), {"anchor": {"obj": "f1"}, "at": [0.1, 0.1], "text": "y"})["thread"]
    with pytest.raises(ValueError): comments.comment(r, "main", "place", by(me), {"id": plain["id"], "at": [0.2, 0.2]})


def test_the_words_for_agents_name_the_part():
    b = {"items": {"f1": {"type": "imgframe", "x": 0, "y": 0, "w": 1000, "h": 450, "name": "Cover"}}}
    t = {"id": "c1", "page": "main", "anchor": {"obj": "f1", "kind": "imgframe", "part": {"kind": "layer", "id": "p3", "name": "Logo", "local": [0.4, 0.6]}},
         "at": [0.5, 0.5], "messages": [{"id": "m1", "text": "x"}]}
    assert "слой «Logo» (layer p3, точка слоя u 40 %, v 60 %)" in annotext.describe_thread(t, b, {})["text"]
    t["anchor"]["part"]["area"] = [0.1, 0.2, 0.3, 0.4]
    assert "область слоя x 10–40 %, y 20–60 %" in annotext.describe_thread(t, b, {})["text"]
    t["anchor"] = {"obj": "c", "part": {"kind": "object", "id": "k2", "name": "Case", "layer": "Atlas/Case", "local": [0.01, 0.02, -0.3]}}
    assert "объект 3D-сцены «Case» (object k2, слой Atlas/Case, точка x 0.010 y 0.020 z -0.300 в его осях)" in annotext.describe_thread(t, b, {})["text"]
