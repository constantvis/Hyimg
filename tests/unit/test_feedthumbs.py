"""The bell's pictures (feedthumbs.py, owner 2026-10-08: «Расстраивает, что нет картинок ... показать либо пространство, либо прям
этот объект, который выделен»): every row's tiles from the board alone, per kind of thing, and the crops and regions drawn once into
the thumbnail cache."""
import io
import json
import os
import urllib.parse

import pytest
from PIL import Image

import feedthumbs
import notifplace
import thumbcache
from unit_env import server


def pic(x, y=0, path="a/1.png", w=300, ar=1.5, crop=None):
    return {"path": path, "x": x, "y": y, "w": w, "ar": ar, "crop": crop}


B = {"items": {"p1": pic(0), "p2": pic(400, path="a/2.png"), "p3": pic(800, path="a/3.png"), "p4": pic(0, 400, "a/4.png"),
               "p5": pic(400, 400, "a/5.png"), "p6": pic(800, 400, "a/6.png"),
               "h": {"type": "htmlframe", "src": "html/x/index.html", "vw": 1440, "x": 2000, "y": 0, "w": 720, "h": 450},
               "m": {"type": "model3d", "scene": "3d/s/scene.json", "x": 3000, "y": 0, "w": 400, "h": 400},
               "n1": {"type": "note", "text": "look", "x": 0, "y": -400, "w": 200, "h": 200, "to": ["p2"]},
               "n2": {"type": "note", "text": "alone", "x": 5000, "y": 5000, "w": 200, "h": 200},
               "t": {"type": "text", "text": "Section", "x": 0, "y": -900, "w": 600, "fs": 40}},
         "groups": {"g": {"title": "Six", "x": -20, "y": -20, "w": 1140, "h": 640, "members": ["p1", "p2", "p3", "p4", "p5", "p6"]},
                    "e": {"title": "Empty", "x": 9000, "y": 0, "w": 300, "h": 200, "members": []}}}


def q(d):
    path, qs = d["src"].split("?", 1)
    return path, {k: v[0] for k, v in urllib.parse.parse_qs(qs).items()}


def nums(s): return [float(x) for x in s.split(",")]


class TestDescriptors:
    def test_a_picture_is_its_thumbnail_and_a_card_its_still_at_3_by_2(self):
        tiles, total = feedthumbs.of_ids("main", B, ["p1", "h"])
        assert total == 2 and tiles[0] == {"src": "/thumb?p=a%2F1.png&s=320", "k": "pic"}
        path, a = q(tiles[1])
        assert path == "/feedthumb" and a["page"] == "main" and a["obj"] == "h" and tiles[1]["k"] == "crop"
        u, v, w, h = nums(a["box"])
        assert (u, w) == (0, 1) and v < 0 and h > 1 and abs(720 * w / (450 * h) - 1.5) < 1e-3, "the whole card, letterboxed to 3:2"

    def test_a_group_is_its_members_four_at_most_and_an_empty_one_the_board_there(self):
        tiles, total = feedthumbs.of_ids("main", B, ["g"])
        assert total == 6 and [t["src"].split("p=")[1].split("&")[0] for t in tiles] == ["a%2F1.png", "a%2F2.png", "a%2F3.png", "a%2F4.png"]
        tiles, total = feedthumbs.of_ids("main", B, ["e"])
        assert total == 1 and tiles[0]["k"] == "region"
        x, y, w, h = nums(q(tiles[0])[1]["r"])
        assert x <= 9000 and x + w >= 9300 and abs(w / h - 1.5) < .01

    def test_a_note_is_what_it_is_linked_to_else_the_board_around_it_and_a_heading_its_section(self):
        assert feedthumbs.of_ids("main", B, ["n1"])[0] == [feedthumbs.pic_tile("a/2.png")]
        tiles, total = feedthumbs.of_ids("main", B, ["n2", "t"])
        assert total == 1 and len(tiles) == 1 and tiles[0]["k"] == "region", "the loose things together, one region"
        tiles, _ = feedthumbs.of_ids("main", B, ["t"])
        x, y, w, h = nums(q(tiles[0])[1]["r"])
        assert y <= -900 and y + h >= -900 + 600 / 1.5 - 1, "a heading shows the section under it"

    def test_a_comment_on_an_area_is_its_crop_with_the_area_outlined(self):
        t = {"page": "main", "anchor": {"obj": "p1"}, "at": [.9, .1], "area": [.5, .1, .4, .3], "by": {"person": "ann"}}
        d = feedthumbs.of_thread(t, B)
        path, a = q(d)
        assert path == "/feedthumb" and a["obj"] == "p1" and d["who"] == "ann"
        u, v, w, h = nums(a["box"])
        mx, my, mw, mh = d["mark"]["r"]
        assert 0 <= u and u + w <= 1.0001 and 0 <= v, "inside the picture where it fits"
        assert abs(u + mx * w - .5) < 1e-3 and abs(v + my * h - .1) < 1e-3 and abs(mw * w - .4) < 1e-3 and abs(mh * h - .3) < 1e-3
        assert abs(300 * w / (200 * h) - 1.5) < 1e-3

    def test_a_pin_is_the_object_with_a_dot_and_an_element_the_part_of_the_page_around_it(self):
        d = feedthumbs.of_thread({"page": "main", "anchor": {"obj": "p1"}, "at": [.25, .5], "by": {}}, B)
        assert q(d)[1]["box"] == "0,0,1,1" and d["mark"] == {"pin": [.25, .5]}, "a 3:2 picture: itself, the dot where the pin is"
        d = feedthumbs.of_thread({"page": "main", "anchor": {"obj": "h"}, "at": [.8, .9], "element": {"css": "#buy"}, "by": {}}, B)
        u, v, w, h = nums(q(d)[1]["box"])
        assert abs(w - 640 / 1440) < 1e-3 and u + w <= 1.0001 and v + h <= 1.0001
        px, py = d["mark"]["pin"]
        assert abs(u + px * w - .8) < 1e-3 and abs(v + py * h - .9) < 1e-3

    def test_a_free_pin_or_area_is_the_board_there(self):
        d = feedthumbs.of_thread({"page": "main", "anchor": None, "at": [500, 300], "by": {"person": "x"}}, B)
        assert d["k"] == "region" and d["mark"] == {"pin": [.5, .5]}
        d = feedthumbs.of_thread({"page": "main", "anchor": None, "at": [0, 0], "area": [100, 100, 200, 100], "by": {}}, B)
        x, y, w, h = nums(q(d)[1]["r"])
        mx, my, mw, mh = d["mark"]["r"]
        assert abs(x + mx * w - 100) < 2 and abs(mw * w - 200) < 2 and abs(mh * h - 100) < 2

    def test_news_with_an_area_alone_and_old_news_with_pictures_alone(self):
        tiles, total = feedthumbs.of_notification({"page": "main", "ids": [], "area": {"x": 0, "y": 0, "w": 900, "h": 300}}, B)
        assert total == 1 and tiles[0]["k"] == "region"
        assert feedthumbs.of_notification({"page": "main", "ids": ["gone"], "previews": ["a/9.png"]}, B) == ([feedthumbs.pic_tile("a/9.png")], 1)

    def test_notify_time_and_read_time(self, lib):
        (lib / "_review" / "boards" / "main.json").write_text(json.dumps(B))
        n = notifplace.tiles({"id": "1", "page": "main", "ids": ["g", "h"]}, server.load_board)
        assert n["pvn"] == 7 and len(n["pv"]) == 4
        old = {"id": "2", "page": "main", "ids": ["h"], "previews": []}
        got = feedthumbs.fill(server, [n, old])
        assert got[0]["pv"][0] == n["pv"][0], "a stored picture tile as it was"
        assert got[1]["pvn"] == 1 and "&v=" in got[1]["pv"][0]["src"], "an old one computed on read, its crop with the board's time"
        assert "pv" not in old, "the stored records are not touched"


def png(lib, rel, w, h, left, right):
    im = Image.new("RGB", (w, h), left); im.paste(right, (w // 2, 0, w, h))
    p = lib / rel; p.parent.mkdir(parents=True, exist_ok=True); im.save(p); return p


class TestDrawing:
    def test_an_area_crop_comes_from_the_pictures_pixels_and_is_kept(self, lib):
        png(lib, "a/1.png", 600, 400, (255, 0, 0), (0, 0, 255))
        (lib / "_review" / "boards" / "main.json").write_text(json.dumps({"items": {"p1": pic(0)}, "groups": {}}))
        d = feedthumbs.of_thread({"page": "main", "anchor": {"obj": "p1"}, "at": [1, 0], "area": [.6, .3, .3, .3], "by": {}}, {"items": {"p1": pic(0)}})
        a = {k: [v] for k, v in q(d)[1].items()}
        out = feedthumbs.http(server, a)
        assert os.path.dirname(out) == thumbcache.THUMBS and os.path.basename(out).startswith("feed.") and out.endswith(".webp")
        with Image.open(out) as im:
            assert im.size == feedthumbs.OUT
            mx, my, mw, mh = d["mark"]["r"]
            r, g, b, _ = im.convert("RGBA").getpixel((int((mx + mw / 2) * im.width), int((my + mh / 2) * im.height)))
            assert b > 200 and r < 60, "the right half of the picture: blue"
        t = os.path.getmtime(out)
        assert feedthumbs.http(server, a) == out and os.path.getmtime(out) == t, "drawn once"

    def test_a_region_draws_the_things_lying_there(self, lib):
        png(lib, "a/1.png", 300, 200, (0, 200, 0), (0, 200, 0))
        b = {"items": {"p1": pic(0), "n": {"type": "note", "text": "hi", "color": "pink", "x": 400, "y": 0, "w": 200, "h": 200}}, "groups": {}}
        (lib / "_review" / "boards" / "main.json").write_text(json.dumps(b))
        out = feedthumbs.http(server, {"page": ["main"], "r": ["0,-100,600,400"], "th": ["dark"]})
        with Image.open(out) as im:
            im = im.convert("RGBA"); s = im.width / 600
            g = im.getpixel((int(150 * s), int(200 * s)))
            assert g[1] > 150 and g[0] < 60 and g[3] == 255, "the picture from its thumbnail"
            px = im.getpixel((int(590 * s), int(110 * s)))
            assert all(abs(a - b) < 6 for a, b in zip(px, (240, 140, 196, 255))), ("the note in its colour", px)
            assert im.getpixel((2, 2))[3] == 0, "the empty board stays see-through: the tile's background shows"

    def test_a_3d_card_is_its_newest_still(self, lib):
        (lib / "3d" / "s" / ".posters").mkdir(parents=True); (lib / "3d" / "s" / "scene.json").write_text("{}")
        png(lib, "3d/s/.posters/m-old.jpg", 400, 400, (255, 0, 0), (255, 0, 0)); os.utime(lib / "3d/s/.posters/m-old.jpg", (1e9, 1e9))
        png(lib, "3d/s/.posters/m-new.jpg", 400, 400, (0, 0, 255), (0, 0, 255))
        png(lib, "3d/s/.posters/other-x.jpg", 400, 400, (0, 255, 0), (0, 255, 0))
        (lib / "_review" / "boards" / "main.json").write_text(json.dumps(B))
        d = feedthumbs.of_ids("main", B, ["m"])[0][0]
        out = feedthumbs.http(server, {k: [v] for k, v in q(d)[1].items()})
        with Image.open(out) as im:
            r, g, b, a = im.convert("RGBA").getpixel((im.width // 2, im.height // 2))
            assert b > 200 and r < 60 and a == 255
            assert im.convert("RGBA").getpixel((2, im.height // 2))[3] == 0, "a square card letterboxed in its 3:2 tile"

    def test_bad_requests_draw_nothing(self, lib):
        (lib / "_review" / "boards" / "main.json").write_text(json.dumps(B))
        for a in ({"page": ["main"], "obj": ["p1"], "box": ["0,0,0,1"]}, {"page": ["main"], "obj": ["n1"], "box": ["0,0,1,1"]},
                  {"page": ["../x"], "r": ["0,0,1,1"]}, {"page": ["main"], "r": ["0,0,-1,1"]}, {"page": ["main"], "obj": ["p1"], "box": ["a"]}):
            assert feedthumbs.http(server, a) is None, a
