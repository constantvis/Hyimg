"""hy.py comments add steps a new pin past the pins already at that place (review/hycomments.py spread)."""
import unit_env  # noqa: F401
import hycomments as hc

OBJ = {"obj": "d1", "kind": "html", "file": "a.html", "r": [0, 0, 720, 450]}


def test_pins_on_one_thing_form_a_column_and_wrap_left():
    threads, placed = [], []
    for _ in range(9):
        at = hc.spread([0.92, 0.08], OBJ, threads)
        placed.append(at); threads.append({"anchor": OBJ, "at": at})
    assert placed[0] == [0.92, 0.08] and placed[1] == [0.92, 0.2]
    assert len({tuple(p) for p in placed}) == 9   # no two on one spot
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in placed)
    assert placed[8][0] < 0.92   # past the bottom: a new column to the left


def test_free_pins_and_areas_and_other_things():
    threads = [{"anchor": None, "at": [100, 100]}, {"anchor": OBJ, "at": [0.92, 0.08], "area": [0.1, 0.1, 0.2, 0.2]},
               {"anchor": {"obj": "other"}, "at": [0.92, 0.08]}]
    assert hc.spread([100, 100], None, threads) == [100, 220]
    assert hc.spread([500, 100], None, threads) == [500, 100]
    assert hc.spread([0.92, 0.08], OBJ, threads) == [0.92, 0.08]   # an area's pin and another thing's pin don't count
