"""Thumbnails of pictures (server.thumb), the library's 3D files and their turntables (scan3d, models3d_info, save_sprite,
sprite_file), and what the pages poll to notice changes (board_stamp, library_signature)."""
import io
import json
import os

import pytest
from PIL import Image

import server


def png(w, h, color=(10, 200, 30)):
    buf = io.BytesIO(); Image.new("RGB", (w, h), color).save(buf, "PNG"); return buf.getvalue()


def put(lib, rel, data=b"x"):
    p = lib / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data); return p


class TestThumbs:
    def test_a_thumbnail_fits_the_size_across_and_is_made_once(self, lib):
        put(lib, "a/big.png", png(1280, 640))
        out = server.thumb("a/big.png", 320)
        with Image.open(out) as im:
            assert im.size == (320, 160) and im.format == "JPEG"
        t = os.path.getmtime(out)
        assert server.thumb("a/big.png", 320) == out and os.path.getmtime(out) == t

    def test_a_new_version_of_the_file_gets_a_new_thumbnail(self, lib):
        p = put(lib, "a/x.png", png(64, 64))
        a = server.thumb("a/x.png", 32)
        os.utime(p, (1_000_000, 1_000_000))
        assert server.thumb("a/x.png", 32) != a

    def test_a_small_thumbnail_is_cut_from_the_bigger_one_when_it_exists(self, lib):
        put(lib, "a/x.png", png(1000, 1000, (255, 0, 0)))
        big = server.thumb("a/x.png", 640)
        Image.new("RGB", (640, 640), (0, 0, 255)).save(big)   # the 640 one says blue: the 160 one must come from it, not the file
        with Image.open(server.thumb("a/x.png", 160)) as im:
            assert im.getpixel((5, 5))[2] > 200

    @pytest.mark.xfail(strict=True, reason="review/server.py:941 (and :842 _pdf_base, :977 _sprite_base): the thumbnail key replaces '/' with '_', so "
                                           "'a/x.png' and 'a_x.png' changed in the same second share one cached thumbnail")
    def test_two_files_whose_paths_differ_only_by_a_slash_have_their_own_thumbnails(self, lib):
        put(lib, "a/x.png", png(10, 10, (255, 0, 0))); put(lib, "a_x.png", png(10, 10, (0, 0, 255)))
        os.utime(lib / "a/x.png", (2_000_000, 2_000_000)); os.utime(lib / "a_x.png", (2_000_000, 2_000_000))
        assert server.thumb("a/x.png", 32) != server.thumb("a_x.png", 32)


class TestModels:
    def test_the_3d_files_are_listed_with_a_project_model_as_one_entry_and_scenes_left_out(self, lib):
        for rel in ("parts/a.glb", "parts/b.STEP", "parts/c.png", "3d/scenes/s/scene.glb", "3d/shots/x.glb", "_skipme/z.glb", "hidden/deep/h.glb"):
            put(lib, rel)
        put(lib, "3d/models/m1/model.json", json.dumps({"title": "Case"}).encode()); put(lib, "3d/models/m1/part.glb")
        got = {i["path"]: i for i in server.scan3d()}
        assert sorted(got) == ["3d/models/m1/model.json", "parts/a.glb", "parts/b.STEP"]
        m = got["3d/models/m1/model.json"]
        assert m["name"] == "Case" and m["ext"] == "MODEL" and m["model"] == "m1" and m["size"] == len(json.dumps({"title": "Case"})) + 1
        assert got["parts/b.STEP"]["ext"] == "STEP" and got["parts/a.glb"]["sprite"] is None and got["parts/a.glb"]["kind"] == "model"

    def test_info_for_given_paths_says_none_for_what_is_gone_or_not_3d(self, lib):
        put(lib, "m/a.glb"); put(lib, "m/b.png")
        out = server.models3d_info(["m/a.glb", "m/b.png", "m/none.glb", "../x.glb"])
        assert out[0]["path"] == "m/a.glb" and out[1:] == [None, None, None]

    def test_a_turntable_sheet_is_kept_as_webp_with_its_numbers_and_its_first_view_is_the_still(self, lib):
        put(lib, "m/a.glb")
        res = server.save_sprite("m/a.glb", png(4 * 64, 2 * 64), 8, 4, 64)
        assert res["n"] == 8 and res["cols"] == 4 and res["bytes"] > 0
        ver = server._model_version(str(lib / "m/a.glb"))
        assert server.sprite_info("m/a.glb", ver)["cell"] == 64
        assert server.sprite_file("m/a.glb").endswith(".sprite.webp")
        with Image.open(server.sprite_file("m/a.glb", 32)) as im:
            assert im.size == (32, 32)

    @pytest.mark.parametrize("n,cols,cell,size", [(8, 4, 64, (200, 128)), (1, 1, 64, (64, 64)), (8, 17, 64, (17 * 64, 64)), (8, 4, 16, (64, 32))])
    def test_a_sheet_of_the_wrong_size_or_numbers_is_refused(self, lib, n, cols, cell, size):
        put(lib, "m/a.glb")
        with pytest.raises(ValueError):
            server.save_sprite("m/a.glb", png(*size), n, cols, cell)

    def test_a_sheet_for_a_file_that_is_not_3d_is_refused(self, lib):
        put(lib, "m/a.png")
        with pytest.raises(ValueError):
            server.save_sprite("m/a.png", png(128, 64), 2, 2, 64)

    def test_a_new_version_of_the_file_drops_the_old_sheet(self, lib):
        p = put(lib, "m/a.glb")
        server.save_sprite("m/a.glb", png(128, 64), 2, 2, 64)
        os.utime(p, (3_000_000, 3_000_000))
        server.save_sprite("m/a.glb", png(128, 64), 2, 2, 64)
        sheets = [f for f in os.listdir(server.THUMBS) if f.endswith(".sprite.webp")]   # the app's cache (thumbcache.py)
        assert sheets == ["m_a.glb.3000000.sprite.webp"]

    def test_no_sheet_yet_is_none(self, lib):
        put(lib, "m/a.glb")
        assert server.sprite_file("m/a.glb") is None


class TestChangeStamps:
    def test_a_boards_stamp_follows_its_file_and_revision(self, lib):
        assert server.board_stamp("main") == {"mtime": 0, "revision": 0}
        server.save_board("main", {"revision": 0, "items": {}})
        a = server.board_stamp("main")
        assert a["revision"] == 1 and a["mtime"] > 0

    def test_the_library_signature_changes_when_a_folder_gets_a_file_and_not_for_the_state_folder(self, lib):
        (lib / "a").mkdir()
        s0 = server.library_signature()
        assert server.library_signature() == s0
        os.utime(lib / "_review", (5, 5)); (lib / "_review" / "live.json").write_text("{}")
        os.utime(lib / "_review", (5, 5))
        assert server.library_signature() == s0
        (lib / "a" / "new.png").write_bytes(b"x"); os.utime(lib / "a", (7, 7))
        assert server.library_signature() != s0

    def test_fetching_a_picture_needs_a_web_address(self, lib):
        for url in ("file:///etc/hosts", "ftp://x/y.png", "/etc/hosts", "javascript:alert(1)"):
            with pytest.raises(ValueError):
                server.added.fetch_image(server, url)   # review/added.py since 2026-10-10
