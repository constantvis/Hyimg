"""Pure helpers of the bigger modules: folder names and the page's folders (foldersync.py; plan/apply/undo are covered end to end by
tests/test_layout_sync.py), the WebM copy's cache and command (webvideo.py, ffmpeg never runs) and the agent CLI's script parsing and
naming (hy.py, no server)."""
import os
import subprocess
import threading

import pytest

import foldersync
import webvideo


class TestFolderNames:
    @pytest.mark.parametrize("text,name", [
        ("# Studio light\nmore", "Studio light"), ("- item", "item"), ("1) first", "first"), ("**bold** and *it*", "bold and it"),
        ('a/b:c<d>"e|f?g*h', "a b c d e f g h"), ("...dots", "dots"), ("  ", "Fallback"), (None, "Fallback"), ("end -", "end"),
    ])
    def test_a_title_becomes_a_folder_name_the_mac_and_dropbox_accept(self, text, name):
        assert foldersync.clean(text, "Fallback") == name

    def test_a_long_title_is_cut_at_a_word(self):
        out = foldersync.clean("word " * 30, "F", limit=20)
        assert out == "word word word word" and len(out) <= 20

    def test_names_side_by_side_are_unique_whatever_their_case_and_unicode_form(self):
        taken = set()
        assert [foldersync._unique(n, taken) for n in ("Group", "group", "GROUP", "é", "é")] == ["Group", "group 2", "GROUP 3", "é", "é 2"]

    def test_a_cycle_of_parents_is_cut(self):
        par = {"a": "b", "b": "a", "c": "a"}
        foldersync._cut_cycles(par)
        x, seen = "c", set()
        while x in par:
            assert x not in seen; seen.add(x); x = par[x]


def pic(path, x, y, w=100):
    return {"path": path, "x": x, "y": y, "w": w, "ar": 1}


class TestPageFolders:
    def test_a_picture_goes_into_the_smallest_group_holding_its_centre_and_a_nested_group_into_its_parent(self):
        b = {"items": {"p": pic("p.png", 150, 150), "q": pic("q.png", 900, 900), "free": pic("f.png", 5000, 5000)},
             "groups": {"outer": {"title": "Outer", "x": 0, "y": 0, "w": 1000, "h": 1000},
                        "inner": {"title": "Inner", "x": 100, "y": 100, "w": 200, "h": 200}}}
        assert foldersync.page_folders(b) == {"p": ("Outer", "Inner"), "q": ("Outer",), "free": ()}

    def test_membership_wins_over_position(self):
        b = {"items": {"p": pic("p.png", 150, 150)},
             "groups": {"a": {"title": "A", "members": ["p"], "x": 5000, "y": 0, "w": 10, "h": 10}, "b": {"title": "B", "x": 0, "y": 0, "w": 1000, "h": 1000}}}
        assert foldersync.page_folders(b)["p"] == ("A",)

    def test_a_note_with_a_row_in_its_zone_is_a_folder_inside_its_group(self):
        b = {"items": {"n": {"type": "note", "text": "Close-ups", "x": 0, "y": 0, "w": 100, "h": 100, "reach": {"l": 0, "t": 0, "r": 400, "b": 0}},
                       "p": pic("p.png", 200, 0), "other": pic("o.png", 200, 900)},
             "groups": {"g": {"title": "Shoot", "x": -10, "y": -10, "w": 2000, "h": 2000}}}
        assert foldersync.page_folders(b) == {"p": ("Shoot", "Close-ups"), "other": ("Shoot",)}

    def test_a_name_the_library_would_hide_gets_its_kind_after_it(self):
        b = {"items": {"p": pic("p.png", 10, 10)}, "groups": {"g": {"title": "Skipped", "x": 0, "y": 0, "w": 500, "h": 500}}}
        assert foldersync.page_folders(b, bad=lambda n: n == "Skipped")["p"] == ("Skipped (группа)",)

    def test_odd_items_and_groups_are_skipped(self):
        b = {"items": {"x": "text", "t": {"type": "text", "path": "t.png", "x": 0, "y": 0, "w": 1}, "p": pic("p.png", 0, 0)},
             "groups": {"bad": {"title": "no rect"}, "s": "x"}}
        assert foldersync.page_folders(b) == {"p": ()}


@pytest.fixture
def cache(tmp_path, monkeypatch):
    d = tmp_path / "cache"
    monkeypatch.setattr(webvideo, "CACHE", str(d))
    monkeypatch.setattr(webvideo, "_JOBS", {})
    return d


class TestWebVideo:
    def test_the_copy_is_named_by_the_files_path_time_and_size(self, cache, tmp_path):
        clip = tmp_path / "c.mov"; clip.write_bytes(b"1")
        a = webvideo.target(str(clip))
        assert a.startswith(str(cache)) and a.endswith(".webm") and webvideo.target(str(clip)) == a
        os.utime(clip, (5, 5))
        b = webvideo.target(str(clip)); clip.write_bytes(b"12")
        assert len({a, b, webvideo.target(str(clip))}) == 3

    def test_the_command_is_vp9_with_opus_or_without_sound(self):
        with_audio = webvideo.command("/ff", "/in.mov", "/out.webm", True)
        without = webvideo.command("/ff", "/in.mov", "/out.webm", False)
        assert with_audio[0] == "/ff" and "libvpx-vp9" in with_audio and "libopus" in with_audio and with_audio[-2:] == ["webm", "/out.webm"]
        assert "-an" in without and "libopus" not in without

    def test_a_missing_ffmpeg_named_by_the_test_variable_is_no_ffmpeg(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HYIMG_FFMPEG", str(tmp_path / "none"))
        assert webvideo.ffmpeg() is None
        (tmp_path / "ff").write_text("")
        monkeypatch.setenv("HYIMG_FFMPEG", str(tmp_path / "ff"))
        assert webvideo.ffmpeg() == str(tmp_path / "ff")

    def test_state_tells_ready_none_and_no_ffmpeg_without_starting_anything(self, cache, tmp_path, monkeypatch):
        clip = tmp_path / "c.mov"; clip.write_bytes(b"1")
        monkeypatch.setenv("HYIMG_FFMPEG", str(tmp_path / "none"))
        assert webvideo.state(str(clip)) == "noffmpeg"
        (tmp_path / "ff").write_text(""); monkeypatch.setenv("HYIMG_FFMPEG", str(tmp_path / "ff"))
        assert webvideo.state(str(clip)) == "none"
        cache.mkdir(); open(webvideo.target(str(clip)), "w").write("x")
        assert webvideo.state(str(clip)) == "ready" and webvideo.start(str(clip)) is None

    def _job(self):
        return {"done": threading.Event(), "error": None}

    def test_a_failed_ffmpeg_leaves_no_copy_and_says_why(self, cache, tmp_path, monkeypatch):
        clip = tmp_path / "c.mov"; clip.write_bytes(b"1"); (tmp_path / "ff").write_text("")
        monkeypatch.setenv("HYIMG_FFMPEG", str(tmp_path / "ff"))
        monkeypatch.setattr(webvideo, "has_audio", lambda exe, full: False)
        monkeypatch.setattr(webvideo.subprocess, "run", lambda a, **k: (open(a[-1], "w").write("half"), subprocess.CompletedProcess(a, 1, "", "Invalid data\n"))[1])
        out, job = webvideo.target(str(clip)), self._job()
        webvideo._run(str(clip), out, job)
        assert job["done"].is_set() and job["error"] == "Invalid data" and not os.path.exists(out) and os.listdir(cache) == []

    def test_a_good_run_puts_the_copy_in_place_whole(self, cache, tmp_path, monkeypatch):
        clip = tmp_path / "c.mov"; clip.write_bytes(b"1"); (tmp_path / "ff").write_text("")
        monkeypatch.setenv("HYIMG_FFMPEG", str(tmp_path / "ff"))
        monkeypatch.setattr(webvideo, "has_audio", lambda exe, full: True)
        monkeypatch.setattr(webvideo.subprocess, "run", lambda a, **k: (open(a[-1], "w").write("webm"), subprocess.CompletedProcess(a, 0, "", ""))[1])
        out, job = webvideo.target(str(clip)), self._job()
        webvideo._run(str(clip), out, job)
        assert job["error"] is None and open(out).read() == "webm" and os.listdir(cache) == [os.path.basename(out)]

    def test_a_timeout_is_an_error_not_a_crash(self, cache, tmp_path, monkeypatch):
        clip = tmp_path / "c.mov"; clip.write_bytes(b"1"); (tmp_path / "ff").write_text("")
        monkeypatch.setenv("HYIMG_FFMPEG", str(tmp_path / "ff"))
        monkeypatch.setattr(webvideo, "has_audio", lambda exe, full: True)
        def slow(a, **k): raise subprocess.TimeoutExpired(a, 600)
        monkeypatch.setattr(webvideo.subprocess, "run", slow)
        job = self._job(); webvideo._run(str(clip), webvideo.target(str(clip)), job)
        assert job["error"].startswith("TimeoutExpired")

    def test_a_file_that_failed_once_is_not_tried_again_on_every_hover(self, cache, tmp_path, monkeypatch):
        clip = tmp_path / "c.mov"; clip.write_bytes(b"1")
        j = self._job(); j["error"] = "broken"; j["done"].set()
        webvideo._JOBS[webvideo.target(str(clip))] = j
        monkeypatch.setattr(webvideo.threading, "Thread", lambda *a, **k: pytest.fail("no new job"))
        assert webvideo.start(str(clip)) is j and webvideo.state(str(clip)) == "failed"

    def test_the_cache_drops_the_copies_used_longest_ago_past_its_limit_but_never_the_new_one(self, cache, monkeypatch):
        cache.mkdir()
        for n, t in (("old", 100), ("mid", 200), ("new", 50)):
            p = cache / f"{n}.webm"; p.write_bytes(b"x" * 10); os.utime(p, (t, t))
        monkeypatch.setattr(webvideo, "LIMIT", 15)
        webvideo.prune(keep=str(cache / "new.webm"))
        assert sorted(os.listdir(cache)) == ["mid.webm", "new.webm"] or sorted(os.listdir(cache)) == ["new.webm"]
        assert (cache / "new.webm").exists()

    def test_has_audio_asks_ffprobe_and_assumes_sound_when_it_cannot(self, tmp_path, monkeypatch):
        (tmp_path / "ffprobe").write_text("")
        monkeypatch.setattr(webvideo.subprocess, "run", lambda a, **k: subprocess.CompletedProcess(a, 0, "", ""))
        assert webvideo.has_audio(str(tmp_path / "ffmpeg"), "/c.mov") is False
        monkeypatch.setattr(webvideo.subprocess, "run", lambda a, **k: subprocess.CompletedProcess(a, 0, "1\n", ""))
        assert webvideo.has_audio(str(tmp_path / "ffmpeg"), "/c.mov") is True
        def boom(a, **k): raise OSError("x")
        monkeypatch.setattr(webvideo.subprocess, "run", boom)
        assert webvideo.has_audio(str(tmp_path / "ffmpeg"), "/c.mov") is True


@pytest.fixture(scope="module")
def hy():
    import hy as module
    return module


def board():
    return {"items": {"h": {"type": "text", "text": "# Стили\nmore", "x": 0, "y": 0, "w": 400, "fs": 40},
                      "n": {"type": "note", "text": "Ёлки note", "x": 0, "y": 100, "w": 200, "h": 50},
                      "n2": {"type": "note", "text": "Стили", "x": 0, "y": 900, "w": 100},
                      "p": {"path": "a/p.png", "x": 10, "y": 300, "w": 200, "ar": 2, "crop": [0, 0, 0.5, 1]},
                      "tl": {"type": "timeline", "label": "Phases", "x": 1000, "y": 50, "w": 900, "h": 20, "points": [{"id": "d1", "t": 30, "text": "Start"}]}},
            "groups": {"g": {"title": "Стили", "x": -20, "y": -20, "w": 600, "h": 1200}}}


class TestHyCli:
    def test_a_script_splits_into_commands_at_semicolons_with_quotes_kept(self, hy):
        assert hy.parse('point Canon x=@Стили; move "Style cards" y=@Стили.bottom+400;') == [["point", "Canon", "x=@Стили"], ["move", "Style cards", "y=@Стили.bottom+400"]]
        assert hy.parse('note "a; b" x=1') == [["note", "a; b", "x=1"]]

    @pytest.mark.xfail(strict=True, reason="review/hy.py:707 parse: shlex with punctuation_chars reads ';;' as one token, so a doubled ';' becomes an argument of the command before it instead of an empty separator")
    def test_a_doubled_semicolon_is_just_a_separator(self, hy):
        assert hy.parse("fit A;; fit B") == [["fit", "A"], ["fit", "B"]]

    def test_names_are_compared_without_case_hashes_and_yo(self, hy):
        assert hy.norm("  # Ёлки   Note ") == "елки note"

    def test_a_cropped_pictures_height_follows_its_crop_and_a_note_is_at_least_square(self, hy):
        b = board()
        assert hy.rect(b, "p") == {"x": 10, "y": 300, "w": 200, "h": 200}
        assert hy.rect(b, "n")["h"] == 200 and hy.rect(b, "g") == {"x": -20, "y": -20, "w": 600, "h": 1200} and hy.rect(b, "none") is None

    def test_a_name_resolves_to_its_one_thing_and_a_group_wins_over_a_note_named_alike(self, hy):
        b = board()
        assert hy.resolve(b, "стили")[:2] == ("group", "g")
        assert hy.resolve(b, "елки")[:2] == ("note", "n")
        assert hy.resolve(b, "d1")[:2] == ("dot", "tl/d1")
        assert hy.resolve(b, "Стили", kinds=("heading",))[:2] == ("heading", "h")

    def test_a_name_that_finds_nothing_or_too_much_stops_with_a_message(self, hy):
        b = board()
        with pytest.raises(SystemExit, match="не нашел"):
            hy.resolve(b, "nothing here")
        b["groups"]["g2"] = dict(b["groups"]["g"], title="Стили")
        with pytest.raises(SystemExit, match="неоднозначно"):
            hy.resolve(b, "Стили")

    @pytest.mark.parametrize("v,key,out", [("12.5", "x", 12.5), ("blue", "color", "blue"), ("@Стили", "x", -20), ("@Стили", "y", -20),
                                           ("@Стили.bottom+400", "y", 1580), ("@Стили.right-20", "x", 560), ("@Стили.cx", "x", 280)])
    def test_a_value_is_a_number_a_word_or_an_edge_of_a_named_thing(self, hy, v, key, out):
        assert hy.value(board(), v, key) == out

    def test_an_unknown_command_stops_before_anything_changes(self, hy):
        b = board()
        with pytest.raises(SystemExit, match="не знаю команду"):
            hy.apply(b, [["explode", "x"]])
        assert b == board()
