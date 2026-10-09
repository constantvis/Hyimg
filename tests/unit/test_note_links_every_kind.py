"""A note links every kind of thing on the board, not only pictures (owner 2026-10-07: «Что 3D, что картинка, неважно что, это объект»):
review/notelinks.py's rule, the note file's "objects", the board's index by item id, the user's .html never written, old boards and
pictures' related_notes as before."""
import json

import notelinks
import server


def note(x, y, w=100, text="Look", **kw):
    return {"type": "note", "x": x, "y": y, "w": w, "h": w, "text": text, **kw}


def pic(path, x, y, w=100, ar=1.0):
    return {"path": path, "x": x, "y": y, "w": w, "ar": ar, "crop": None}


HTML = {"type": "htmlframe", "src": "html/a/index.html", "vw": 1280, "x": 1000, "y": 0, "w": 400, "h": 250}
DEV = {"type": "html", "src": "site/index.html", "vw": 1280, "x": 2000, "y": 0, "w": 400, "h": 250, "pics": ["site/index.html"]}
CUBE = {"type": "model3d", "scene": "3d/scenes/s/scene.json", "x": 3000, "y": 0, "w": 400, "h": 300}
FRAME = {"type": "imgframe", "doc": "frames/1/frame.json", "pics": ["a.png"], "x": 4000, "y": 0, "w": 400, "h": 300}
ODD = {"type": "someplugin", "x": 5000, "y": 0, "w": 100, "h": 100}   # a plugin this code does not know is a card too


def board(**more):
    return {"items": {"html": dict(HTML), "dev": dict(DEV), "cube": dict(CUBE), "frame": dict(FRAME), "odd": dict(ODD),
                      "head": {"type": "text", "text": "Title", "x": 0, "y": -900, "w": 300, "h": 60, "fs": 50}, **more}, "groups": {}}


def test_overlap_zone_and_arrow_reach_every_kind_of_card():
    b = board(on=note(1100, 50), zone=note(1900, -100, w=50, reach={"l": 20, "t": 20, "r": 500, "b": 400}),
              arrow=note(-900, -900, to=["cube", "frame", "odd", "head", "on"]))
    L = notelinks.links(b)
    assert L["on"]["items"] == {"html": {"overlap"}}
    assert L["zone"]["items"] == {"dev": {"zone"}}
    # a note is never a thing of a note: the arrow to it is a reply (2026-10-08), the reply is about that note's things
    assert L["arrow"]["items"] == {"cube": {"arrow"}, "frame": {"arrow"}, "odd": {"arrow"}, "head": {"arrow"}, "html": {"reply"}}
    kinds = {o["id"]: (o["kind"], o.get("file")) for o in notelinks.index(b)["arrow"]["objects"]}
    assert kinds == {"cube": ("3d", "3d/scenes/s/scene.json"), "frame": ("frame", "frames/1/frame.json"), "odd": ("card", None), "head": ("heading", None),
                     "html": ("html", "html/a/index.html")}


def test_a_heading_is_not_caught_by_overlap_or_a_zone():
    b = board(on=note(10, -880, w=50, reach={"l": 50, "t": 50, "r": 50, "b": 50}))
    assert notelinks.links(b)["on"]["items"] == {}


def test_a_note_pointing_at_a_card_in_a_group_names_the_card_not_the_group():
    # the owner's case: a group «Figma · раунд 4» with an HTML frame and its png snapshot, a note with an arrow to the frame
    b = {"items": {"html": dict(HTML), "snap": pic("snap.png", 1500, 0), "n": note(1100, 400, to=["html"])},
         "groups": {"g": {"title": "Figma · раунд 4", "members": ["html", "snap", "n"], "x": 900, "y": -100, "w": 900, "h": 800}}}
    e = notelinks.index(b)["n"]
    assert e["scope"] == "pictures" and e["items"] == {"html": {"arrow"}} and e["pics"] == {} and "group" not in e
    # without the arrow it speaks for the whole group: the card and the picture both
    b["items"]["n"]["to"] = []
    e = notelinks.index(b)["n"]
    assert e["scope"] == "group" and e["items"] == {"html": {"group"}, "snap": {"group"}} and e["pics"] == {"snap.png": {"group"}}


def test_an_arrow_at_a_group_reaches_its_cards_too():
    b = {"items": {"html": dict(HTML), "a": pic("a.png", 1500, 0), "n": note(-500, 0, to=["g"])},
         "groups": {"g": {"title": "G", "members": ["html", "a"], "x": 900, "y": -100, "w": 900, "h": 600}}}
    assert notelinks.links(b)["n"]["items"] == {"html": {"arrow"}, "a": {"arrow"}}


def test_an_old_board_of_pictures_gives_what_it_gave():
    b = {"items": {"n": note(0, 0, reach={"l": 0, "t": 0, "r": 300, "b": 0}, to=["far"]), "over": pic("over.png", 50, 50),
                   "zone": pic("zone.png", 250, 0), "far": pic("far.png", 5000, 5000)}, "groups": {}}
    e = server.note_index(b)["n"]
    assert e["pics"] == {"over.png": {"overlap", "zone"}, "zone.png": {"zone"}, "far.png": {"arrow"}}
    assert [o["id"] for o in e["objects"]] == ["far", "over", "zone"] and all(o["kind"] == "picture" for o in e["objects"])


def test_sync_keeps_a_cards_link_on_the_board_side_and_never_writes_the_html(lib):
    (lib / "site").mkdir(); page = lib / "site" / "index.html"; page.write_text("<!doctype html><p>mine</p>")
    (lib / "a.png").write_bytes(b"pic"); (lib / "a.json").write_text(json.dumps({"prompt": "p"}))
    items = {"dev": dict(DEV), "cube": dict(CUBE), "a": pic("a.png", 0, 0), "n": note(2100, 50, to=["cube"]), "m": note(0, 0, text="On a")}
    server.save_board("main", {"revision": 0, "items": items})
    assert server.sync_notes("main") > 0
    doc = json.loads((lib / "notes" / "main__n.json").read_text())
    assert doc["pictures"] == [] and {o["id"]: o["via"] for o in doc["objects"]} == {"dev": ["overlap"], "cube": ["arrow"]}
    assert [o["file"] for o in doc["objects"]] == ["3d/scenes/s/scene.json", "site/index.html"]
    idx = json.loads((lib / "_review" / "boards" / "main.notes-index.json").read_text())
    assert idx["items"]["dev"] == [{"note": "main/n", "via": ["overlap"]}] and idx["items"]["a"] == [{"note": "main/m", "via": ["overlap"]}]
    assert idx["paths"] == ["a.png"]
    assert page.read_text() == "<!doctype html><p>mine</p>" and not (lib / "site" / "index.html.json").exists() and not (lib / "site" / "index.json").exists()
    assert json.loads((lib / "a.json").read_text()) == {"prompt": "p", "related_notes": [{"note": "main/m", "via": ["overlap"]}]}
    assert server.sync_notes("main") == 0   # nothing changed, nothing written
    out = json.loads(server.json.dumps(notelinks.public(server.note_index(server.load_board("main")))))
    assert out["n"]["pics"] == {} and [o["id"] for o in out["n"]["objects"]] == ["cube", "dev"]


def test_hy_find_lines_name_the_notes_of_a_card():
    b = board(on=note(1100, 50, text="# Про фрейм\nдальше"))
    assert notelinks.tail(b, "html") == "\n   заметка «Про фрейм» (лежит на нем) [on]"
    assert notelinks.tail(b, "dev") == "" and notelinks.about(b, "on") == " → HTML 1"


def test_a_thing_tells_what_else_its_note_is_about():
    """owner 2026-10-08: a note with arrows to a screenshot and a page: who reads the screenshot learns the page is in it too"""
    b = {"revision": 1, "items": {
        "shot": {"path": "added/261008/shot.png", "x": 0, "y": 0, "w": 300, "ar": 1.5},
        "page": {"type": "htmlframe", "src": "html/r11/3d-icons.html", "x": 900, "y": 0, "w": 720, "h": 450},
        "n": {"type": "note", "text": "Так вот тут на скриншоте\nи еще", "x": 500, "y": 900, "w": 200, "h": 200, "to": ["shot", "page"]}}}
    assert notelinks.tail(b, "shot") == "\n   заметка «Так вот тут на скриншоте» (стрелка) [n]\n      она же про: HTML 3d-icons.html [page]"
    assert notelinks.tail(b, "page").endswith("она же про: кадр shot.png [shot]")
