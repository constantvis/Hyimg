"""The text document model for agents (review/textdocs.py, owner 2026-10-09: a text is a title line and a Markdown body, as in Apple
Notes): split, a heading stays a heading, hy.py's `text` and `set` with \\n, the body in hy.py md under its title, a grid's heading cell by
its title only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "review"))

import grids  # noqa: E402
import hymd  # noqa: E402
import textdocs  # noqa: E402

uid = lambda p: p + "1"


def test_split_and_doc():
    assert textdocs.split("Title") == ("Title", "")
    assert textdocs.split("Title\nbody\n- a") == ("Title", "body\n- a")
    assert not textdocs.is_doc({"type": "text", "text": "Title\n  \n"})   # blank lines under a title: still a heading
    assert textdocs.is_doc({"type": "text", "text": "Title\nbody"})
    assert not textdocs.is_doc({"type": "note", "text": "Title\nbody"})


def test_body_md_shifts_headings_under_the_title():
    assert textdocs.body_md("Title", 3) == []
    assert textdocs.body_md("Title\n\n# Goal\n- [ ] ship\n## Why\n> because\n", 2) == ["", "### Goal", "- [ ] ship", "#### Why", "> because"]
    assert textdocs.body_md("T\n### Deep", 5) == ["", "###### Deep"]   # never past six


def test_text_command_heading_unchanged():
    b = {"items": {}}
    out = textdocs.op_text(b, ["Section"], {"x": 10, "y": 20}, uid)
    it = b["items"]["t1"]
    assert it == {"type": "text", "text": "Section", "x": 10, "y": 20, "fs": 874, "size": 4, "w": round(874 * .6 * 7), "h": round(874 * 1.15)}, it
    assert out.startswith("text t1 «Section»")
    textdocs.op_text(b, ["Row"], {"x": 0, "y": 0, "fs": 40}, uid)
    assert b["items"]["t1"]["size"] == 4 and b["items"]["t1"]["fs"] == 40 and "tw" not in b["items"]["t1"]   # as hy.py always made it


def test_text_command_document():
    b = {"items": {}}
    out = textdocs.op_text(b, ["Brief\\n## Goal\\n- [ ] ship it"], {"x": 0, "y": 0}, uid)
    it = b["items"]["t1"]
    assert it["text"] == "Brief\n## Goal\n- [ ] ship it" and it["size"] == 1 and it["fs"] == 40 and it["tw"] == 560 and it["w"] == 560
    assert it["h"] > 40 * 1.15 + 3 * 20 and "+2 строк" in out
    textdocs.op_text(b, ["Big\nbody"], {"x": 0, "y": 0, "size": 3, "w": 900}, uid)
    assert (b["items"]["t1"]["fs"], b["items"]["t1"]["size"], b["items"]["t1"]["tw"]) == (128, 3, 900)


def test_set_reads_newlines_and_width():
    b = {"items": {"t1": {"type": "text", "text": "Plan", "x": 0, "y": 0, "fs": 40, "size": 1, "w": 100, "h": 46}}, "groups": {}}
    ops = {"set": lambda b, args, kv: (b["items"][args[0]].update(kv), "set")[1]}
    textdocs.register(ops, uid, lambda b, ref, kinds=None: ("heading", ref, "Plan", None))
    ops["set"](b, ["t1"], {"text": "Plan\\n- one"})
    assert b["items"]["t1"]["text"] == "Plan\n- one" and b["items"]["t1"]["tw"] == 560
    ops["set"](b, ["t1"], {"w": 700})
    assert b["items"]["t1"]["tw"] == 700 and b["items"]["t1"]["w"] == 700
    ops["set"](b, ["t1"], {"text": "Plan"})
    assert "tw" not in b["items"]["t1"] and b["items"]["t1"]["h"] == round(40 * 1.15)


def test_md_prints_the_body_and_a_grid_names_the_title():
    b = {"items": {"t1": {"type": "text", "text": "Brief\n# Goal\n- [x] done", "x": 0, "y": 0, "fs": 40, "w": 560, "h": 200},
                   "t2": {"type": "text", "text": "Old", "x": 0, "y": 400, "fs": 40, "w": 80, "h": 46}}, "groups": {}}
    md = hymd.render(b, "P", "main")
    assert "### Brief [t1]\n\n#### Goal\n- [x] done\n\n### Old [t2]" in md, md
    assert grids.cell(b, "t1") == "«Brief» [t1]"   # a heading cell: its title only
