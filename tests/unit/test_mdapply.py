"""hy.py md apply's reading and planning (review/mdapply.py, owner 2026-10-09 on «Board structure» › «Markdown as edits»: «реализуй это»):
the view read back unchanged plans nothing, a heading's document body is its text, lines the view printed itself are not new things, a
long note keeps its tail, an id twice is refused, a missing line removes nothing, a page part without headers moves nothing. No server."""
import copy

import unit_env  # noqa: F401  (review/ on the path)
import grids
import hy
import hymd
import mdapply


def pic(x, y, path):
    return {"path": path, "x": x, "y": y, "w": 300, "ar": 1.5}


def page():
    I = {"a": pic(0, 0, "a/a.png"), "b": pic(324, 0, "a/b.png"), "c": pic(648, 0, "a/c.png"), "d": pic(0, 400, "a/d.png"),
         "e": pic(324, 400, "a/e.png"), "f": pic(3000, 0, "a/f.png"),
         "h": {"type": "text", "text": "Свет\nпервый абзац\n- пункт списка\n> цитата в документе", "x": 0, "y": -500, "w": 400, "fs": 120},
         "n": {"type": "note", "text": "х" * 650, "x": -400, "y": 0, "w": 300, "fs": 20, "to": []}}
    b = {"items": I, "groups": {"G": {"title": "Свет", "x": -500, "y": -700, "w": 1700, "h": 1500, "members": ["a", "b", "c", "d", "e", "h", "n"]},
                                "H": {"title": "Другое", "x": 2800, "y": -200, "w": 800, "h": 800, "members": ["f"]}}}
    grids.make(b, ["a", "b", "c"])
    return b


def ops_for(b, text):
    return mdapply.plan(copy.deepcopy(b), mdapply.parse(text))


def test_the_view_read_back_unchanged_plans_nothing():
    b = page(); md = hymd.render(b, "P", "p")
    assert ops_for(b, md) == []
    assert ops_for(b, mdapply.stamp(b, "p") + md) == []


def test_a_document_body_is_the_headings_text_not_new_things():
    b = page(); md = hymd.render(b, "P", "p")
    body = mdapply.parse(md)["blocks"]
    h = next(x for x in body if x["id"] == "h")
    if "первый абзац" in md:   # the view prints a text document's body (textdocs.py): its list stays in the body
        assert "- пункт списка" in h["body"]
    ops = ops_for(b, md.replace("первый абзац", "второй абзац") if "первый абзац" in md else md.replace("### Свет [h]", "### Свет [h]\n\nвторой абзац"))
    assert [o["show"] for o in ops] == ["~ заголовок «Свет» и его текст"]
    cur = copy.deepcopy(b); mdapply.execute(ops, b, cur, hy)
    assert cur["items"]["h"]["text"].split("\n")[0] == "Свет" and "второй абзац" in cur["items"]["h"]["text"]


def test_a_long_note_keeps_its_tail_and_refuses_a_cut_one():
    b = page(); md = hymd.render(b, "P", "p")
    e = mdapply.parse(md.replace("х" * 600 + "… [n]", "ю" + "х" * 599 + "… [n]"))
    ops = mdapply.plan(copy.deepcopy(b), e); cur = copy.deepcopy(b); mdapply.execute(ops, b, cur, hy)
    assert cur["items"]["n"]["text"] == "ю" + "х" * 649
    e = mdapply.parse(md.replace("х" * 600 + "… [n]", "коротко [n]"))
    assert mdapply.plan(copy.deepcopy(b), e) == [] and any("длиннее" in why for _ln, why in e["bad"])


def test_an_id_twice_and_a_missing_line():
    b = page(); md = hymd.render(b, "P", "p")
    e = mdapply.parse(md.replace("- a/f.png", "x").replace("- f.png [f]", "- f.png [f]\n- d.png [d]"))
    ops = mdapply.plan(copy.deepcopy(b), e)
    assert ops == [] and any("[d] встречается 2 раза" in why for _ln, why in e["bad"])
    assert ops_for(b, md.replace("- e.png [e]\n", "")) == []   # e not mentioned: nothing happens to it


def test_a_part_without_section_headers_moves_nothing_and_a_cell_takes_a_picture():
    b = page()
    assert ops_for(b, "Свободно:\n- f.png [f]\n") == []
    table = "▦ сетка 3 × 1 [" + next(iter(b["grids"])) + "]\n|   |   |   |\n|---|---|---|\n| c.png [c] | a.png [a] | b.png [b] |\n| f.png [f] | | |\n"
    ops = ops_for(b, table)
    assert len(ops) == 1 and ops[0]["show"].startswith("▦ сетка")
    cur = copy.deepcopy(b); mdapply.execute(ops, b, cur, hy)
    g = next(iter(cur["grids"].values()))
    assert g["members"] == ["c", "a", "b", "f"] and "f" in cur["groups"]["G"]["members"] and "f" not in cur["groups"]["H"]["members"]


def test_struck_lines_remove_and_new_lines_add():
    b = page(); md = hymd.render(b, "P", "p")
    e = md.replace("- d.png [d]", "- ~~d.png [d]~~").replace("## ▣ Группа «Другое» [H]", "~~## ▣ Группа «Другое» [H]~~")
    shows = [o["show"] for o in ops_for(b, e)]
    assert "− d.png [d]" in shows and "− рамка группы «Другое» (содержимое остается)" in shows
    cur = copy.deepcopy(b); mdapply.execute(ops_for(b, e), b, cur, hy)
    assert "d" not in cur["items"] and "H" not in cur["groups"] and "f" in cur["items"]
