"""Layout patterns and arrows between anything through hy.py on a running server (owner 2026-10-09 on the page «Agent layouts»:
«реализуй это»; s5 «A + C now», st6 «A, then C»). Each pattern places what its card shows (a numbered grid under a note, a two-column
table, a batch under its phase, a row per direction, a heading with cards and a legend, Picked · To decide · Rejected, steps joined by
arrows, term cards), check --pattern passes on what the patterns made, a do reports the owner's rules it broke (a long agent note), the
new pattern loop marks and unmarks; connect, disconnect, map, find, md, map --graph, mermaid and structure work on the page."""
import json
import urllib.request

from test_agent_tools import hyimg  # noqa: F401  (the fixture: a library with old/ and new/, a group «Старые»)


def post(port, page, b):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/board?name={page}", data=json.dumps(b).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return urllib.request.urlopen(req).status


def note_of(b, head):
    return next(k for k, it in b["items"].items() if it.get("type") == "note" and (it.get("text") or "").startswith("# " + head))


def grids_in_zone(b, nid):
    n = b["items"][nid]; m = n["reach"]; z = (n["x"] - m["l"], n["y"] - m["t"], n["x"] + n["w"] + m["r"], n["y"] + n["w"] + m["b"] + 4000)
    ins = {k for k, it in b["items"].items() if it.get("x") is not None and z[0] <= it["x"] + it["w"] / 2 <= z[2] and z[1] <= it["y"] <= z[3]}
    return [g for g in (b.get("grids") or {}).values() if set(g["members"]) & ins]


def test_patterns_place_as_the_cards_show_and_pass_their_check(hyimg):
    port, hy, board, state = hyimg
    out = hy("do", 'pattern variants "new/[0-2].png" into=Старые title="Light left"', "--quiet")
    assert "pattern variants: 3 кадров" in out and "подгруппой в «Старые»" in out, out
    out = hy("do", 'pattern variants "new/[0-3].png" into=Старые title="Light left"', "--quiet")   # the batch goes on: the grid grows
    assert "+1 кадров в «Light left»" in out and "дописал" in out, out
    b = board(); nid = note_of(b, "Light left")
    assert b["items"][nid]["pattern"] == "variants" and b["items"][nid]["color"] == "blue"
    g = grids_in_zone(b, nid)[0]
    assert g["num"] == "seq" and g["cols"] == 3 and len(g["members"]) == 4   # 3 a row, numbered 1…4
    assert "№1 0.png" in hy("map", "Старые") and "№4 3.png" in hy("md")

    out = hy("do", 'pattern ab "old/0.png" "new/4.png" into=Старые a=current b=new', "--quiet")
    out = hy("do", 'pattern ab "old/[0-1].png" "new/[4-5].png" into=Старые a=current b=new', "--quiet")   # one more pair: one more row
    assert "+1 пар в таблицу" in out, out
    b = board(); g = grids_in_zone(b, note_of(b, "A / B"))[0]
    heads = [b["items"][m].get("text") for m in g["members"][:2]]
    assert heads == ["A · current", "B · new"] and g["cols"] == 2 and g["num"] == "rc" and g["head"] == {"row": True}
    assert [b["items"][m]["path"] for m in g["members"][2:]] == ["old/0.png", "new/4.png", "old/1.png", "new/5.png"]   # rows: A1 B1, A2 B2
    assert "№A1 0.png" in hy("map", "Старые") and "№B2 5.png" in hy("map", "Старые")

    hy("do", 'pattern directions "old/[0-2].png" "new/[3-5].png" into=Старые labels="D1,D2"', "--quiet")
    b = board(); gs = grids_in_zone(b, note_of(b, "Направления"))
    assert [b["items"][g["members"][0]]["text"] for g in gs[:2]] == ["D1", "D2"] and all(g["num"] == "col" for g in gs[:2])

    hy("do", 'pattern before-after "old/[0-1].png" "new/[0-1].png" near=Старые side=below group="Правка"', "--quiet")
    hy("do", 'pattern moodboard "old/*" near=Правка side=right title="Cold studio light"', "--quiet")
    b = board(); mood = grids_in_zone(b, note_of(b, "Cold studio light"))[0]
    assert mood["cols"] == 5 and "num" not in mood   # references are hearted, not numbered

    out = hy("check", "--pattern")
    assert out.count("✓") == 5 and "⚠" not in out and "правила владельца: все соблюдены" in out, out
    assert "проблем не нашел" in hy("check"), hy("check")

    # a do that breaks an owner's rule says so: a long agent note
    out = hy("do", 'note "' + "слово " * 40 + '" x=-3000 y=-3000', "--quiet")
    assert "длинная: 40 слов" in out, out


def test_timeline_docs_review_flow_and_the_new_pattern_loop(hyimg):
    port, hy, board, state = hyimg
    b = board(); b["items"]["tl"] = {"type": "timeline", "dir": "h", "fs": 40, "len": 2000, "x": 0, "y": -1400, "w": 2000, "h": 60,
                                     "points": [{"id": "p0", "t": 0, "text": "Brief"}, {"id": "p1", "t": 900, "text": "P1 · 1001"}]}
    assert post(port, "main", b) == 200
    out = hy("do", 'pattern timeline "new/[0-3].png" phase="P2 · 1003"', "--quiet")
    b = board(); t = b["items"]["tl"]; dot = next(p for p in t["points"] if p["text"] == "P2 · 1003")
    nid = note_of(b, "P2 · 1003"); n = b["items"][nid]
    assert n["y"] > t["y"] and abs(n["x"] - (t["x"] + dot["t"])) < 700, (n, dot, out)   # under its phase
    assert grids_in_zone(b, nid)[0]["num"] == "seq"

    out = hy("do", 'pattern docs "old/[0-2].png" title="Editors · round 6" captions="layers;camera;library" near=Старые side=below', "--quiet")
    b = board(); top = next(k for k, it in b["items"].items() if it.get("pattern") == "docs")
    assert b["items"][top]["fs"] == 160 and any((it.get("text") or "").startswith("1 layers\n2 camera") for it in b["items"].values())
    cards = [it for it in b["items"].values() if it.get("path", "").startswith("old/") and it["w"] == 720]
    assert len(cards) == 3

    b = board(); fav = b["items"]["o1"]["path"]
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/fav", data=json.dumps({"paths": [fav], "fav": True}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    assert urllib.request.urlopen(req).status == 200
    out = hy("do", 'pattern review "new/[4-5].png" o1 near=Старые side=right title="Review P7"', "--quiet")
    b = board(); gid = next(k for k, g in b["groups"].items() if g.get("pattern") == "review")
    cols = {b["items"][m]["text"]: m for m in b["groups"][gid]["members"] if b["items"][m].get("pattern_col")}
    assert set(cols) == {"Picked", "To decide", "Rejected"}
    assert "♥ 1, решить 2" in out, out
    assert b["items"]["o1"]["x"] < b["items"][cols["To decide"]]["x"]   # the hearted one stands under Picked

    out = hy("do", 'pattern flow Старые "Review P7" "Release" labels="pick;ship"', "--quiet")
    assert "новых 1" in out and "стрелок новых 2" in out, out
    g = hy("map", "--graph")
    assert "Старые → Review P7 [pick]" in g and "Review P7 → Release [ship]" in g

    out = hy("do", 'pattern mark "Contact sheet" "Review P7"', "--quiet")
    assert "спроси владельца" in out
    assert "новый расклад «Contact sheet»: ждет ответа владельца" in hy("check", "--pattern")
    hy("do", 'pattern unmark "Review P7"', "--quiet")
    b = board()
    assert not any(it.get("pattern_tag") for it in b["items"].values()) and b["groups"][gid].get("pattern") is None
    assert "Шаблоны раскладки" in hy("patterns")


def test_connect_read_mermaid_and_structure(hyimg, tmp_path):
    port, hy, board, state = hyimg
    out = hy("do", 'connect Старые o2 label="contains"; connect o0 o5 style=dashed color=blue', "--quiet")
    assert "connect группа «Старые» → 0.png" not in out and "· «contains»" in out and "пунктир, синяя" in out, out
    b = board(); assert sorted((c["from"], c["to"]) for c in b["links"].values()) == [("g1", "o2"), ("o0", "o5")]
    assert "↦ группа «Старые» → 2.png · «contains»" in hy("map")
    assert "↦ 0.png → 5.png · пунктир, синяя" in hy("find", "o0")
    assert "## ↦ Стрелки" in hy("md")
    mm = hy("mermaid")
    assert "%% hyimg:" in mm and '-- "contains" -->' in mm
    flow = tmp_path / "flow.mmd"
    flow.write_text('flowchart LR\n  a[Старые] --> b[Directions]\n  b -- "D1…D6" --> c[Generations]\n  c -.->|redo| b\n')
    out = hy("structure", str(flow), "near=Старые", "--quiet")
    assert "новых 2" in out and "стрелок новых 3" in out, out
    g = hy("map", "--graph")
    assert "Directions → Generations [D1…D6]" in g and "Generations ┄> Directions [redo]" in g
    out = hy("do", "disconnect Старые", "--quiet")
    b = board(); assert not any(c["from"] == "g1" for c in b["links"].values())
    hy("do", 'remove o5', "--quiet")   # an arrow goes with its end
    b = board(); assert not any("o5" in (c["from"], c["to"]) for c in b["links"].values())
    assert "o0" not in json.dumps(b.get("links", {}))
