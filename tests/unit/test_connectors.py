"""Arrows between anything (review/connectors.py, owner 2026-10-09 on «Agent layouts» › 4 Structures: «реализуй это»): the record,
prune, what map, find and md say, Mermaid out and back in (st3 «text in, real objects out, back again»), the merge of arrows made on
both sides (review/merge.py); the layout patterns' rules after placing (review/patterns.py, s3 «C»). No server, no browser."""
import pytest

import unit_env  # noqa: F401  (review/ on the path, the throwaway library)
import connectors
import merge
import patterns


def pic(x, y, path):
    return {"path": path, "x": x, "y": y, "w": 300, "ar": 1.5}


def page():
    I = {"p": pic(0, 0, "a/p.png"), "q": pic(700, 0, "a/q.png"), "r": pic(1400, 0, "b/r.png"),
         "h": {"type": "text", "text": "Research", "x": 0, "y": -400, "w": 600, "fs": 80},
         "n": {"type": "note", "text": "# Brief\nchrome, silk", "x": 0, "y": 600, "w": 300, "fs": 17, "to": []}}
    return {"items": I, "groups": {"G": {"title": "Picks", "x": 1300, "y": -100, "w": 600, "h": 500, "members": ["r"]}}}


def test_put_keeps_one_arrow_a_pair_and_writes_only_what_is_not_the_default():
    b = page()
    cid, new = connectors.put(b, "h", "p", "contains")
    assert new and b["links"][cid] == {"from": "h", "to": "p", "label": "contains"}
    same, again = connectors.put(b, "h", "p", None, "dashed", "blue")
    assert same == cid and not again and b["links"][cid] == {"from": "h", "to": "p", "label": "contains", "style": "dashed", "color": "blue"}
    connectors.put(b, "h", "p", "", "solid", "grey")
    assert b["links"][cid] == {"from": "h", "to": "p"}
    back, _ = connectors.put(b, "p", "h")   # the other way is another arrow
    assert back != cid and len(b["links"]) == 2
    with pytest.raises(SystemExit): connectors.put(b, "p", "p")
    with pytest.raises(SystemExit): connectors.put(b, "p", "gone")
    with pytest.raises(SystemExit): connectors.put(b, "p", "q", style="wavy")


def test_prune_takes_arrows_whose_end_left_and_the_empty_map():
    b = page(); connectors.put(b, "p", "q"); connectors.put(b, "q", "G")
    del b["items"]["q"]
    assert connectors.prune(b) == 2 and "links" not in b


def test_lines_name_things_as_the_owner_sees_them():
    b = page(); cid, _ = connectors.put(b, "n", "G", "brief for", "dotted")
    assert connectors.line(b, cid) == f"↦ заметка «Brief» → группа «Picks» · «brief for», точки [{cid}]"
    assert "## ↦ Стрелки" in connectors.md(b) and "brief for" in connectors.md(b)
    assert connectors.graph(b) == "Brief ┄> Picks [brief for]"


def test_md_apply_reads_the_arrows_section_as_read_only():
    import copy, hymd, mdapply
    b = page(); b.update(revision=3, vid="v"); connectors.put(b, "h", "p", "contains"); connectors.put(b, "n", "G")
    text = mdapply.stamp(b, "p") + hymd.render(b, "P", "p") + connectors.md(b)
    assert "## ↦ Стрелки" in text and mdapply.plan(copy.deepcopy(b), mdapply.parse(text)) == []


def test_mermaid_out_and_back_in_is_the_same_arrows():
    b = page()
    connectors.put(b, "h", "p", "contains"); connectors.put(b, "p", "q", "same light", "dashed"); connectors.put(b, "q", "G", None, "dotted", "blue")
    connectors.put(b, "n", "p", None, None, "blue")
    text = connectors.mermaid(b)
    assert text.startswith("flowchart LR\n") and "%% hyimg: research = h" in text and "linkStyle" in text
    m = connectors.parse(text)
    ids = {k: m["ids"][k] for k in m["order"]}
    got = sorted((ids[a], ids[z], lab, st, col) for a, z, lab, st, col in m["edges"])
    want = sorted((c["from"], c["to"], c.get("label", ""), c.get("style", "solid"), c.get("color")) for c in b["links"].values())
    assert got == want


def test_parse_reads_the_flowchart_of_the_concept_card():
    m = connectors.parse("""flowchart LR
  research[Research] --> dirs[Directions]
  dirs -- "D1…D6" --> gen[Generations]
  gen -- "♥ 12" --> picks[Picks]
  picks ==> rel[Release]
  gen -.->|redo D3| dirs
  a --> b --> c
  %% hyimg: research = g1ar3s50
  %% hyimg: rel = new""")
    assert m["nodes"]["dirs"] == "Directions" and m["ids"] == {"research": "g1ar3s50", "rel": "new"}
    assert ("dirs", "gen", "D1…D6", "solid", None) in m["edges"] and ("picks", "rel", "", "solid", "blue") in m["edges"]
    assert ("gen", "dirs", "redo D3", "dashed", None) in m["edges"] and ("b", "c", "", "solid", None) in m["edges"]


def test_ranks_lay_a_flow_left_to_right_and_a_circle_ends():
    r = connectors.ranks(["a", "b", "c", "d"], [("a", "b"), ("b", "c"), ("c", "b"), ("a", "d")])
    assert r["a"] == 0 and r["b"] >= 1 and r["d"] == 1 and max(r.values()) < 4


def test_merge_keeps_arrows_made_on_both_sides_and_drops_those_to_what_was_deleted():
    base = page(); connectors.put(base, "h", "p", "contains")
    ours, theirs = (__import__("copy").deepcopy(base) for _ in range(2))
    connectors.put(ours, "p", "q", "ours"); connectors.put(theirs, "q", "G", "theirs")
    k = next(iter(base["links"])); theirs["links"][k]["label"] = "holds"
    del theirs["items"]["p"]; theirs["links"] = {k2: c for k2, c in theirs["links"].items() if "p" not in (c["from"], c["to"])}
    out, _conf = merge.merge3(base, ours, theirs, 2, 1)
    labels = sorted(c.get("label") for c in out["links"].values())
    assert labels == ["theirs"], out["links"]   # «ours» went with p, deleted on theirs; «contains» changed there and lost its end too
    out2, _ = merge.merge3(base, ours, __import__("copy").deepcopy(base), 2, 1)
    assert sorted(c.get("label") for c in out2["links"].values()) == ["contains", "ours"]


def test_rules_after_placing_flag_what_hurt_him():
    b = page()
    b["items"]["n"].update(color="blue", text="# Batch\n" + "word " * 40)
    b["items"]["c"] = {"type": "text", "text": "a caption with far too many words", "x": 0, "y": -100, "w": 600, "fs": 40}
    b["groups"]["S"] = {"title": "P7 · 2610020900", "x": 3000, "y": 0, "w": 600, "h": 500, "members": []}
    b["items"]["v"] = {"type": "note", "text": "# Light", "x": 0, "y": 900, "w": 300, "fs": 17, "color": "blue", "pattern": "variants"}
    b["grids"] = {"gw": {"members": [f"w{k}" for k in range(10)], "cols": 10}}
    for k in range(10): b["items"][f"w{k}"] = pic(k * 320, 3000, f"w/{k}.png")
    kinds = {k[0] for k in patterns.rules(b)}
    assert kinds == {"words", "caption", "stamp", "nonum", "wide"}, patterns.rules(b)
    b["items"]["n"]["color"] = "yellow"   # the owner's own long note is his business
    assert "words" not in {k[0] for k in patterns.rules(b)}
