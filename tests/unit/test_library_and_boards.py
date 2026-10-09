"""The library list (server.scan, scan_mounts, titles, refpaths), what the owner writes into a picture's sidecar (save_feedback,
save_fav, save_answer), pictures added by hand or by a plugin (add_image, save_snapshot), boards and pages (save_board, save_pages,
pages_state, with_archive) and the sticky notes' links (note_index, sync_notes)."""
import json
import os
import struct

import pytest
from PIL import Image

import server
from unit_env import MOUNT


def put(lib, rel, data=b"pic", meta=None):
    p = lib / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    if meta is not None:
        side = p.with_suffix(".json") if p.suffix.lower() in server.EXT else p.with_name(p.name + ".json")
        side.write_text(meta if isinstance(meta, str) else json.dumps(meta))
    return p


def paths(items):
    return sorted(i["path"] for i in items)


class TestScan:
    def test_the_library_lists_media_files_and_leaves_out_what_the_rules_hide(self, lib):
        for rel in ("a/1.png", "a/2.jpg", "a/doc.pdf", "a/art.psd", "root.png", "a/notes.txt", "a/raw-crop.png",
                    "_skipme/x.png", "a/_skipme/x.png", "hidden/deep/x.png", "hidden/deep/more/x.png", "hidden/ok.png",
                    "b/storyboard/x.png", "b/mask-1/x.png", "html/page/x.png", "frames/1/render.png", ".git/x.png", "a/.posters/x.png"):
            put(lib, rel)
        assert paths(server.scan()) == ["a/1.png", "a/2.jpg", "a/art.psd", "a/doc.pdf", "hidden/ok.png", "root.png"]

    def test_a_picture_carries_its_sidecars_prompt_model_and_feedback(self, lib):
        put(lib, "a/1.png", meta={"prompt": "two birds", "model": "gpt-image", "feedback": {"fav": True}, "owner_tags": ["Mine"]})
        it = server.scan()[0]
        assert it["prompt"] == "two birds" and it["feedback"] == {"fav": True} and it["title"] == "Title A"
        assert it["tags"] == ["Bird", "GPT Image", "Mine"] and "kind" not in it

    def test_a_file_that_is_not_a_picture_says_its_kind_and_extension_and_has_its_own_sidecar(self, lib):
        put(lib, "a/IMG.psd", b"8BPS", meta={"prompt": "psd"}); put(lib, "a/IMG.png", b"png", meta={"prompt": "png"})
        by = {i["path"]: i for i in server.scan()}
        assert by["a/IMG.psd"]["kind"] == "doc" and by["a/IMG.psd"]["ext"] == "PSD" and by["a/IMG.psd"]["prompt"] == "psd"
        assert by["a/IMG.png"]["prompt"] == "png"

    @pytest.mark.parametrize("side", ["[1, 2]", "{nope", '"text"'])
    def test_an_odd_sidecar_loses_only_what_cannot_be_read(self, lib, side):
        put(lib, "a/1.png", meta=side)
        it = server.scan()[0]
        assert it["path"] == "a/1.png" and it["feedback"] == {} and it["prompt"] == ""

    def test_feedback_written_as_plain_text_is_kept_aside(self, lib):
        put(lib, "a/1.png", meta={"feedback": "great", "qa": "ok"})
        it = server.scan()[0]
        assert it["feedback"] == {} and it["gate"] is None

    def test_a_grid_already_cut_into_frames_is_not_listed(self, lib):
        put(lib, "a/grid.png", meta={"cut": True}); put(lib, "a/cell.png", meta={"grid": "grid.png"})
        assert paths(server.scan()) == ["a/cell.png"]

    def test_a_cut_frame_without_a_model_takes_its_grids(self, lib):
        put(lib, "a/grid.png", meta={"cut": True, "model": "midjourney"}); put(lib, "a/cell.png", meta={"grid": "grid.png"})
        assert server.scan()[0]["model"] == "midjourney"

    def test_an_empty_file_is_listed_with_a_mark(self, lib):
        put(lib, "a/e.png", b""); put(lib, "a/f.png", b"x")
        by = {i["path"]: i for i in server.scan()}
        assert by["a/e.png"]["empty"] is True and "empty" not in by["a/f.png"]

    def test_a_plugins_kind_of_file_is_listed(self, lib, plugin_root):
        plugin_root("dev", {"kinds": {"html": [".html"]}})
        put(lib, "site/index.html", b"<html>")
        it = server.scan()[0]
        assert it["kind"] == "html" and it["ext"] == "HTML"

    def test_a_mounted_folder_is_its_own_collection_with_its_gallery_caption(self, lib):
        (MOUNT / "p.jpg").write_bytes(b"x")
        (MOUNT / "p.jpg.json").write_text(json.dumps({"width": 3, "height": 4, "post_date": "2026-01-02 10:00", "post_url": "https://x", "description": "cap"}))
        (MOUNT / "q.jpg").write_bytes(b"x"); (MOUNT / "q.json").write_text(json.dumps({"prompt": "mine", "feedback": {"fav": True}}))
        by = {i["path"]: i for i in server.scan()}
        assert by["ext/refs/p.jpg"]["aspect"] == "3:4" and by["ext/refs/p.jpg"]["prompt"] == "2026-01-02 · https://x\ncap" and by["ext/refs/p.jpg"]["title"] == "Refs"
        assert by["ext/refs/q.jpg"]["prompt"] == "mine" and by["ext/refs/q.jpg"]["feedback"] == {"fav": True}

    def test_every_picture_carries_its_collections_start_as_yymmddhhmm(self, lib):
        put(lib, "old/1.png"); put(lib, "new/1.png")
        assert all(len(i["start"]) == 10 and i["start"].isdigit() for i in server.scan())

    def test_titles_come_from_the_rules_then_a_titles_file_in_the_library(self, lib, monkeypatch):
        put(lib, "titles.py", b'TITLES = [("a", "From file"), ("b", "B title")]')
        monkeypatch.setitem(server.RULES, "titlesFrom", "titles.py")
        t = server.titles()
        assert t["a"] == "From file" and t["b"] == "B title" and server.ADDED in t
        monkeypatch.setitem(server.RULES, "titlesFrom", "../outside/x.py")
        assert server.titles()["a"] == "Title A"


class TestRefs:
    def test_references_are_found_three_ways_and_kept_inside_the_library(self, lib):
        put(lib, "refs/r1.png"); put(lib, "a/in.png"); put(lib, "a/sub/img.png")
        from unit_env import OUTSIDE
        (OUTSIDE / "o.png").write_bytes(b"x")
        meta = {"refs": ["r1.png", "none.png"], "inputs": ["in.png", "../../outside/o.png"], "images": ["sub/img.png", "in.png"]}
        assert server.refpaths(meta, str(lib / "a")) == ["refs/r1.png", "a/in.png", "a/sub/img.png"]

    def test_a_cut_frame_shows_its_grids_references(self, lib):
        put(lib, "a/r.png"); put(lib, "a/grid.png", meta={"inputs": ["r.png"]})
        assert server.inherited_refs({"grid": "grid.png"}, str(lib / "a")) == ["a/r.png"]
        assert server.inherited_refs({"derived_from": "a/grid.png"}, str(lib / "b")) == ["a/r.png"]
        assert server.inherited_refs({"grid": "../../x.png"}, str(lib / "a")) == []

    @pytest.mark.parametrize("folders,order", [(["b", "v10", "_favs", "v2"], ["v2", "v10", "_favs", "b"])])
    def test_versioned_folders_sort_by_number_then_favourites_then_the_rest(self, folders, order):
        assert sorted(folders, key=server.folder_key) == order


class TestFeedback:
    def test_feedback_goes_to_every_copy_with_the_same_name_and_size(self, lib):
        put(lib, "a/x.png", b"same"); put(lib, "b/x.png", b"same"); put(lib, "c/x.png", b"other")
        out = server.save_feedback({"path": "a/x.png", "verdict": "take", "comment": "nice", "junk": 1})
        assert sorted(out["paths"]) == ["a/x.png", "b/x.png"] and out["feedback"]["verdict"] == "take" and "junk" not in out["feedback"]
        assert json.loads((lib / "b/x.json").read_text())["feedback"]["comment"] == "nice" and not (lib / "c/x.json").exists()
        log = (lib / "_review" / "feedback-log.jsonl").read_text().splitlines()
        assert json.loads(log[-1])["junk"] == 1

    def test_an_empty_verdict_takes_the_feedback_off_and_keeps_the_rest(self, lib):
        put(lib, "a/x.png", meta={"prompt": "p", "feedback": {"verdict": "take"}})
        assert server.save_feedback({"path": "a/x.png", "verdict": "", "comment": ""})["feedback"] == {}
        assert json.loads((lib / "a/x.json").read_text()) == {"prompt": "p"}

    def test_a_heart_from_the_canvas_changes_only_the_heart(self, lib):
        put(lib, "a/x.png", meta={"feedback": {"comment": "keep", "updated": "old"}})
        out = server.save_fav(["a/x.png"], True)["feedback"]["a/x.png"]
        assert out["fav"] is True and out["comment"] == "keep" and out["updated"] != "old"
        server.save_fav(["a/x.png"], False)
        fb = json.loads((lib / "a/x.json").read_text())["feedback"]
        assert "fav" not in fb and fb["comment"] == "keep"

    def test_taking_the_last_heart_off_takes_the_feedback_off(self, lib):
        put(lib, "a/x.png")
        server.save_fav(["a/x.png"], True); server.save_fav(["a/x.png"], False)
        assert json.loads((lib / "a/x.json").read_text()) == {}

    def test_a_heart_for_a_path_out_of_the_library_changes_nothing(self, lib):
        put(lib, "a/x.png")
        with pytest.raises(PermissionError):
            server.save_fav(["a/x.png", "../x.png"], True)
        assert not (lib / "a/x.json").exists()

    def test_an_answer_is_written_into_its_question(self, lib):
        put(lib, "a/x.png", meta={"questions": [{"id": "q1", "q": "why?"}, {"id": "q2", "q": "?"}]})
        qs = server.save_answer({"path": "a/x.png", "id": "q1", "a": "because"})["questions"]
        assert qs[0]["a"] == "because" and qs[0]["answered"] and "a" not in qs[1]
        assert server.save_answer({"path": "a/x.png", "id": "q1", "a": "  "})["questions"][0]["answered"] == ""

    def test_a_write_by_the_server_makes_the_library_list_stale(self, lib):
        put(lib, "a/x.png")
        g = server.LIB_GEN[0]
        server.save_feedback({"path": "a/x.png", "verdict": "take"})
        assert server.LIB_GEN[0] > g


class TestAddedPictures:
    def test_a_pasted_picture_is_saved_under_added_with_its_story(self, lib, png_bytes):
        out = server.add_image(png_bytes(8, 4), name="My Shot!.PNG")
        assert out["ar"] == 2 and out["path"].startswith("added/") and out["path"].endswith("-my-shot.png")
        meta = json.loads((lib / out["path"]).with_suffix(".json").read_text())
        assert meta["how"] == "file" and meta["size"] == [8, 4] and "from the file My Shot!.PNG" in meta["prompt"]

    def test_the_same_bytes_pasted_again_give_the_first_picture(self, lib, png_bytes):
        data = png_bytes()
        a = server.add_image(data, name="a.png"); b = server.add_image(data, name="b.png")
        assert b == {"path": a["path"], "ar": a["ar"], "again": True}

    def test_bytes_already_in_the_library_are_not_pasted_twice(self, lib, png_bytes, monkeypatch):
        data = png_bytes(); put(lib, "shoot/x.png", data)
        server.dedup.fill()
        assert server.add_image(data)["path"] == "shoot/x.png"

    def test_a_gif_is_kept_as_a_png_and_not_an_image_is_refused(self, lib):
        import io
        buf = io.BytesIO(); Image.new("P", (3, 3)).save(buf, "GIF")
        assert server.add_image(buf.getvalue(), url="https://x/y/anim.gif?s=1")["path"].endswith("-anim.png")
        for bad in (b"", b"not an image"):
            with pytest.raises(ValueError):
                server.add_image(bad)

    def test_pictures_pasted_in_the_same_second_get_their_own_names(self, lib, png_bytes, monkeypatch):
        monkeypatch.setattr(server.time, "strftime", lambda f, *a: {"%y%m%d": "261006", "%H%M%S": "120000"}.get(f, "2026-10-06 12:00:00"))
        names = [server.add_image(png_bytes(2, 2, (n, 0, 0)), name="s.png")["path"] for n in range(3)]
        assert names == ["added/261006/120000-s.png", "added/261006/120000-s~2.png", "added/261006/120000-s~3.png"]

    def test_a_plugin_snapshot_goes_to_its_folder_with_its_json(self, lib, png_bytes):
        out = server.save_snapshot(png_bytes(4, 2), "Front View", "3d/shots", {"camera": 1})
        meta = json.loads((lib / out["path"]).with_suffix(".json").read_text())
        assert out["ar"] == 2 and out["path"].startswith("3d/shots/") and out["path"].endswith("-front-view.png") and meta["camera"] == 1

    @pytest.mark.parametrize("folder", ["", "../x", "/abs", "_review/x", "Upper", "a/../../b"])
    def test_a_snapshot_into_a_bad_folder_is_refused(self, lib, png_bytes, folder):
        with pytest.raises(ValueError):
            server.save_snapshot(png_bytes(), "x", folder, {})


class TestSizes:
    def test_a_psd_header_gives_width_and_height(self, lib):
        p = put(lib, "a.psd", b"8BPS" + b"\0" * 10 + struct.pack(">II", 300, 500) + b"\0" * 4)
        assert server.psd_size(str(p)) == [500, 300]
        assert server.psd_size(str(put(lib, "b.psd", b"GIF89a" + b"\0" * 30))) is None

    def test_image_sizes_reads_headers_and_skips_what_it_cannot(self, lib, png_bytes):
        put(lib, "a/x.png", png_bytes(5, 7))
        assert server.image_sizes(["a/x.png", "a/none.png", "../x.png"]) == {"a/x.png": [5, 7]}

    def test_an_empty_or_unreadable_file_is_empty(self, lib):
        assert server.is_empty(str(put(lib, "e.png", b""))) and not server.is_empty(str(put(lib, "f.png", b"x")))
        assert server.is_empty(str(lib / "none.png"))


class TestDefaultApp:
    def test_the_test_variable_answers_for_every_file(self, lib, monkeypatch):
        monkeypatch.setenv("HYIMG_DEFAULT_APP", '{"name": "Preview", "path": "/Applications/Preview.app"}')
        assert server.default_app("/x.psd") == {"name": "Preview", "path": "/Applications/Preview.app"}
        monkeypatch.setenv("HYIMG_DEFAULT_APP", "{nope")
        assert server.default_app("/x.psd") == {}

    def test_launchservices_is_asked_once_per_extension_and_odd_answers_are_no_app(self, lib, monkeypatch):
        import subprocess
        monkeypatch.delenv("HYIMG_DEFAULT_APP", raising=False)
        answers = iter(['{"name": "Photoshop", "path": "/A/P.app"}', '{"name": 3}'])
        calls = []
        monkeypatch.setattr(server.subprocess, "run", lambda a, **k: calls.append(a) or subprocess.CompletedProcess(a, 0, next(answers), ""))
        assert server.default_app("/x.psd")["name"] == "Photoshop" and server.default_app("/y.PSD")["name"] == "Photoshop"
        assert server.default_app("/z.ai") == {} and len(calls) == 2

    def test_an_icon_is_drawn_only_for_an_app_default_app_named(self, lib, monkeypatch):
        monkeypatch.setattr(server.subprocess, "run", lambda *a, **k: pytest.fail("no icon for an app nobody named"))
        assert server.app_icon("/Applications/Calculator.app") is None


class TestBoards:
    def test_a_save_with_a_stale_revision_is_merged_with_the_current_board(self, lib):   # merge.py, 2026-10-08 (was a 409)
        code, res = server.save_board("main", {"revision": 0, "items": {"a": {"x": 1}}})
        assert code == 200 and res["revision"] == 1
        code, res = server.save_board("main", {"revision": 0, "items": {"x": {}}})
        assert code == 200 and res["revision"] == 2 and res["board"]["items"] == {"a": {"x": 1}, "x": {}}

    def test_a_board_with_no_pages_has_its_first_page(self, lib):
        assert server.load_pages() == [{"id": "main", "title": "Page 1"}]

    def test_saving_pages_drops_copies_names_untitled_and_keeps_a_removed_pages_board(self, lib):
        server.save_board("main", {"revision": 0, "items": {}}); server.save_board("two", {"revision": 0, "items": {}})
        server.save_pages([{"id": "main", "title": "  One "}, {"id": "two"}, {"id": "main", "title": "dup"}])
        assert server.load_pages() == [{"id": "main", "title": "One"}, {"id": "two", "title": "Untitled"}]
        server.save_pages([{"id": "main", "title": "One"}])
        assert not (lib / "_review/boards/two.json").exists() and len(os.listdir(lib / "_review/boards/_deleted")) == 1

    @pytest.mark.parametrize("pages", [[], [{"id": "../x"}]])
    def test_no_pages_or_a_bad_page_id_is_refused(self, lib, pages):
        with pytest.raises(PermissionError):
            server.save_pages(pages)

    def test_pictures_off_every_page_are_the_archive(self, lib):
        b = {"revision": 0, "items": {"a": {"path": "on.png"}, "f": {"type": "imgframe", "pics": ["framed.png", 3]}, "t": {"type": "text", "path": "t.png"}},
             "removed": {"gone.png": 1, "on.png": 1}}
        server.save_board("main", b)
        st = server.pages_state()
        assert st["on"] == ["framed.png", "on.png"] and st["removed"] == ["gone.png"]
        items = server.with_archive([{"path": "gone.png"}, {"path": "on.png"}])
        assert items[0]["archived"] is True and "archived" not in items[1]


def note(x, y, w=100, text="Look", **kw):
    return {"type": "note", "x": x, "y": y, "w": w, "h": w, "text": text, **kw}


def pic(path, x, y, w=100, ar=1.0):
    return {"path": path, "x": x, "y": y, "w": w, "ar": ar}


class TestNotes:
    def test_a_note_touches_what_it_overlaps_its_zone_holds_by_centre_and_its_arrows_point_at(self, lib):
        b = {"items": {"n": note(0, 0, reach={"l": 0, "t": 0, "r": 300, "b": 0}, to=["far", "g"]),
                       "over": pic("over.png", 50, 50), "zone": pic("zone.png", 220, 0), "edge": pic("edge.png", 380, 0),
                       "far": pic("far.png", 5000, 5000), "gm": pic("gm.png", 9000, 0)},
             "groups": {"g": {"title": " Group ", "members": ["gm"], "x": 0, "y": 0, "w": 1, "h": 1}}}
        e = server.note_index(b)["n"]
        assert e["pics"] == {"over.png": {"overlap", "zone"}, "zone.png": {"zone"}, "far.png": {"arrow"}, "gm.png": {"arrow"}}
        assert e["group"] == "Group" and e["scope"] == "pictures" and e["color"] == "yellow"

    def test_a_note_alone_in_a_group_frame_speaks_for_the_whole_group(self, lib):
        b = {"items": {"n": note(10, 10, w=20), "a": pic("a.png", 500, 500), "b": pic("b.png", 600, 500)},
             "groups": {"big": {"title": "Big", "members": ["b"], "x": 0, "y": 0, "w": 2000, "h": 2000},
                        "small": {"title": "Small", "members": ["a"], "x": 0, "y": 0, "w": 100, "h": 100}}}
        e = server.note_index(b)["n"]
        assert e["scope"] == "group" and e["group"] == "Small" and e["pics"] == {"a.png": {"group"}}

    def test_a_note_without_text_is_left_out_and_a_picture_twice_on_the_board_is_one_entry(self, lib):
        b = {"items": {"empty": note(0, 0, text="  "), "n": note(0, 0), "a1": pic("a.png", 0, 0), "a2": pic("a.png", 10, 10)}}
        idx = server.note_index(b)
        assert list(idx) == ["n"] and idx["n"]["pics"] == {"a.png": {"overlap"}}

    def test_a_cropped_picture_is_as_tall_as_its_crop(self):
        assert server._pic_rect({"x": 0, "y": 0, "w": 100, "ar": 2, "crop": [0, 0, 0.5, 1]}) == (0, 0, 100, 100)

    def test_sync_writes_one_file_per_note_and_short_references_into_sidecars(self, lib):
        put(lib, "a.png", meta={"prompt": "p"}); put(lib, "b.png")
        server.save_board("main", {"revision": 0, "items": {"n": note(0, 0), "a": pic("a.png", 0, 0), "b": pic("b.png", 50, 50)}})
        assert server.sync_notes("main") > 0
        doc = json.loads((lib / "notes" / "main__n.json").read_text())
        assert doc["text"] == "Look" and [p["path"] for p in doc["pictures"]] == ["a.png", "b.png"]
        assert json.loads((lib / "a.json").read_text()) == {"prompt": "p", "related_notes": [{"note": "main/n", "via": ["overlap"]}]}
        assert server.sync_notes("main") == 0
        assert server.notes_for(json.loads((lib / "a.json").read_text()))[0]["text"] == "Look"

    def test_a_note_moved_away_takes_its_references_and_file_with_it(self, lib):
        put(lib, "a.png", meta={"prompt": "p"}); put(lib, "b.png")
        server.save_board("main", {"revision": 0, "items": {"n": note(0, 0), "a": pic("a.png", 0, 0), "b": pic("b.png", 50, 50)}})
        server.sync_notes("main")
        server.save_board("main", {"revision": 1, "items": {"n": note(9000, 9000), "a": pic("a.png", 0, 0), "b": pic("b.png", 50, 50)}})
        server.sync_notes("main")
        assert json.loads((lib / "a.json").read_text()) == {"prompt": "p"}
        assert not (lib / "b.json").exists() and not (lib / "notes" / "main__n.json").exists()
