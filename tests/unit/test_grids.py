"""Grids (review/grids.py, owner 2026-10-08: «Arrange: пользователю нативно и удобно ... для агента структура — win-win»): the record, the
reflow math, what keeps a grid right after other edits, the merge of two edits of one grid (review/merge.py), hy.py's grid, put and ungrid,
and the Markdown view of a sample page (review/hymd.py). No server, no browser."""
import json

import pytest

import unit_env  # noqa: F401  (review/ on the path, the throwaway library)
import grids
import hymd
import merge


def pic(x, y, w=300, ar=1.5, path=None, **k):
    return {"path": path or f"a/{x}-{y}.png", "x": x, "y": y, "w": w, "ar": ar, **k}


def page():
    I = {"a": pic(0, 0), "b": pic(380, 30), "c": pic(700, -20, ar=1.0), "d": pic(20, 300), "e": pic(360, 330),
         "h": {"type": "text", "text": "Свет", "x": 0, "y": -500, "w": 400, "fs": 200},
         "n": {"type": "note", "text": "# Свет\nмягкий", "x": -400, "y": 0, "w": 300, "fs": 20, "to": ["a"]},
         "r": {"type": "note", "text": "да", "x": -400, "y": 400, "w": 300, "fs": 20, "to": ["n"]},
         "f": pic(2000, 0, path="x/f.png"), "t": {"type": "timeline", "label": "Фазы", "x": 0, "y": 2000, "w": 1000, "h": 40,
                                                   "points": [{"id": "p1", "t": 0, "text": "старт"}, {"id": "p2", "t": 500, "text": "сдача"}]}}
    return {"items": I, "groups": {"G": {"title": "Свет", "x": -500, "y": -100, "w": 1600, "h": 900, "members": ["a", "b", "c", "d", "e", "n", "r"]}}}


def xy(b, *ids): return [(b["items"][i]["x"], b["items"][i]["y"]) for i in ids]


def test_make_records_reading_order_and_lays_out_fit_cells():
    b = page(); gid = grids.make(b, ["e", "a", "c", "b", "d"])
    g = b["grids"][gid]
    assert g == {"members": ["a", "b", "c", "d", "e"], "cols": 3, "rows": 2, "gap": 24, "cell": "fit"}
    # columns as wide as their widest member, rows as tall as their tallest (c is square: 300 tall), from the top left (0, -20)
    assert xy(b, *g["members"]) == [(0, -20), (324, -20), (648, -20), (0, 304), (324, 304)]
    pos, s = grids.layout(b, g)
    assert s["rowh"] == [300, 200] and s["colw"] == [300, 300, 300] and (s["w"], s["h"]) == (948, 524)
    assert grids.make(b, ["a", "b", "c", "d", "e"], cols=2) == gid and b["grids"][gid]["cols"] == 2   # the same set: the same grid
    assert xy(b, "c") == [(0, 200 - 20 + 24)]


def test_titles_from_a_heading_row():
    b = page(); b["items"].update(t1={"type": "text", "text": "A", "x": 0, "y": -100, "w": 100, "fs": 40}, t2={"type": "text", "text": "B", "x": 400, "y": -100, "w": 100, "fs": 40})
    gid = grids.make(b, ["t1", "t2", "a", "b"])
    assert b["grids"][gid]["head"] == {"row": True} and b["grids"][gid]["cols"] == 2
    assert grids.md_table(b, gid)[0] == "| # | «A» [t1] | «B» [t2] |"


def test_one_item_one_grid_and_a_grid_lives_with_two():
    b = page(); g1 = grids.make(b, ["a", "b", "c"]); g2 = grids.make(b, ["c", "d", "e"])
    assert "c" not in b["grids"][g1]["members"] and b["grids"][g2]["members"] == ["c", "d", "e"]
    grids.leave(b, ["a"])
    assert g1 not in b["grids"]   # one member left: no grid


def test_put_at_after_out_and_prune_reflow_from_the_old_top_left():
    b = page(); gid = grids.make(b, ["a", "b", "c", "d", "e"])
    cells = xy(b, "a", "b", "c", "d", "e")
    grids.put(b, gid, "f", 0)
    assert b["grids"][gid]["members"][0] == "f" and xy(b, "f") == [cells[0]]
    grids.put(b, gid, "f", 5)   # a member moved: its order changes, the cells stay
    assert b["grids"][gid]["members"] == ["a", "b", "c", "d", "e", "f"]
    at = grids.origins(b); del b["items"]["a"]; grids.prune(b, at)
    assert b["grids"][gid]["members"] == ["b", "c", "d", "e", "f"] and xy(b, "b") == [cells[0]]


def test_merge_of_two_edits_of_one_grid():
    base = page(); gid = grids.make(base, ["a", "b", "c", "d", "e"]); cells = xy(base, "a", "b", "c", "d", "e")
    base.update(schema=1, revision=1, removed={})
    ours = json.loads(json.dumps(base)); theirs = json.loads(json.dumps(base))
    g = ours["grids"][gid]; g["members"] = ["c", "a", "b", "d", "e"]; grids.reflow(ours, gid)   # here: c dragged to the first cell
    grids.put(theirs, gid, "f")                                                                   # there: f put at the end
    theirs["grids"][gid]["gap"] = 40                                                              # and the gap made wider
    out, conflicts = merge.merge3(base, ours, theirs, 2.0, 1.0)
    m = out["grids"][gid]
    assert m["members"] == ["c", "a", "b", "d", "e", "f"] and m["gap"] == 40 and m["rows"] == 2
    assert xy(out, "c", "a") == [cells[0], (cells[0][0] + 300 + 40, cells[0][1])]   # laid out again, in the merged order, with the new gap
    # a member deleted on one side leaves the grid on merge; a page with no grids gets no empty map
    theirs2 = json.loads(json.dumps(base)); del theirs2["items"]["e"]
    out2, _ = merge.merge3(base, json.loads(json.dumps(base)), theirs2, 2.0, 1.0)
    assert "e" not in out2["grids"][gid]["members"]
    plain = {k: v for k, v in base.items() if k != "grids"}
    assert "grids" not in merge.merge3(plain, dict(plain), dict(plain), 2.0, 1.0)[0]


def test_hy_commands_grid_put_ungrid_and_every_do_keeps_grids():
    b = page(); ops = {"remove": lambda b, a, kv: [b["items"].pop(i) for i in a] and "remove"}
    def resolve(b, ref, kinds=None):
        if ref in b["groups"]: return ("group", ref, b["groups"][ref]["title"], None)
        raise SystemExit(f"не нашел «{ref}»")
    grids.register(ops, resolve, lambda b, ref: [ref])
    assert ops["grid"](b, ["G"], {"cols": 2}).startswith("▦ сетка 2 × 3")
    gid = next(iter(b["grids"]))
    assert b["grids"][gid]["members"] == ["a", "b", "c", "d", "e"]   # a group: its pictures and cards, not its notes
    ops["put"](b, ["f", "in", gid, "at", "1,2"], {})
    assert b["grids"][gid]["members"][1] == "f"
    ops["put"](b, ["d", "after", "a"], {})
    assert b["grids"][gid]["members"][:3] == ["a", "d", "f"]
    ops["put"](b, ["d", "out"], {})
    assert "d" not in b["grids"][gid]["members"]
    ops["remove"](b, ["a"], {})
    assert "a" not in b["grids"][gid]["members"]   # a do that took something off the page: its grid closed the gap
    ops["ungrid"](b, [gid], {})
    assert "grids" not in b


def test_a_table_its_headings_join_the_group_and_a_zone_fits_it():
    """A5 Table built as an agent does (2026-10-08, the sb06 tables): headings made loose, gridded and put in reading order; they join the
    group frame of their cell (a group moved without them left the table behind), head is set by itself, zone fits the note around it"""
    b = page(); T = lambda x, y, s: {"type": "text", "text": s, "x": x, "y": y, "w": 60, "h": 46, "fs": 40}
    b["items"].update(k=T(0, -60, "Угол"), c1=T(0, -60, "1"), c2=T(0, -60, "2"), r1=T(0, -60, "A"), r2=T(0, -60, "B"))
    ops = {}
    def resolve(b, ref, kinds=None):
        if ref in b["items"]: return ("note" if b["items"][ref].get("type") == "note" else "heading", ref, ref, None)
        raise SystemExit(f"не нашел «{ref}»")
    grids.register(ops, resolve, lambda b, ref: [ref])
    ops["grid"](b, ["k", "c1"], {"cols": 3})
    for i in ("c2", "r1", "a", "b", "r2", "d", "e"): ops["put"](b, [i, "in", "k"], {})
    gid = grids.of(b, "k"); g = b["grids"][gid]
    assert g["members"] == ["k", "c1", "c2", "r1", "a", "b", "r2", "d", "e"] and g["head"] == {"row": True, "col": True} and g["rows"] == 3
    assert xy(b, "k", "c1", "a", "d") == [(0, -60), (84, -60), (84, 10), (84, 234)]   # heading column 60 + 24, heading row 46 + 24
    assert all(i in b["groups"]["G"]["members"] for i in ("k", "c1", "c2", "r1", "r2"))   # loose headings joined the frame they stand in
    assert sum("a" in x["members"] for x in b["groups"].values()) == 1
    assert ops["zone"](b, ["n", "c1"], {}).startswith("zone «n» вокруг 9")   # a member names its whole grid
    n = b["items"]["n"]; assert n["reach"] == {"l": 150, "t": 210, "r": 958, "b": 284}   # the table and the note itself, 150 of air
    assert grids.md_table(b, gid, numbers=False)[0] == "| «Угол» [k] | «1» [c1] | «2» [c2] |"


def test_md_view_of_a_sample_page():
    b = page(); gid = grids.make(b, ["a", "b", "c", "d", "e"])
    md = hymd.render(b, "Main", "main")
    assert md == f"""# «Main» (main)

## Свет [h]

## ▣ Группа «Свет» [G]

> # Свет
> мягкий [n]
→ 0-0.png [a]

▦ сетка 3 × 2 [{gid}]
|   |   |   |
|---|---|---|
| 0-0.png [a] | 380-30.png [b] | 700--20.png [c] |
| 20-300.png [d] | 360-330.png [e] |  |

> да [r]
→ ответ на «Свет» [n]

Свободно:
- f.png [f]
- Таймлайн «Фазы» [t]: старт · сдача
"""


def test_gravity_reads_rows_top_to_bottom_left_to_right():
    E = [((500, 0, 100, 100), "b"), ((0, 10, 100, 100), "a"), ((0, 300, 100, 100), "c"), ((0, -400, 2000, 100), "h")]
    assert hymd.gravity(E) == ["h", "a", "b", "c"]
