"""A library path from a page never reaches a file outside the library or its mounts (server.py safe, resolve, library_file, reveal,
save_plugin_file, board_path, history.load)."""
import os

import pytest

import config
import history
import server
from unit_env import MOUNT, OUTSIDE


def test_a_file_inside_the_library_resolves_to_its_real_path(lib):
    (lib / "a").mkdir(); (lib / "a" / "x.png").write_bytes(b"1")
    assert server.safe("a/x.png") == str(lib / "a" / "x.png")


@pytest.mark.parametrize("rel", ["../outside/secret.txt", "a/../../outside/secret.txt", "..", ""])
def test_a_path_climbing_out_of_the_library_is_refused(lib, rel):
    (OUTSIDE / "secret.txt").write_text("no")
    with pytest.raises(PermissionError):
        server.safe(rel)


def test_an_absolute_path_is_refused_even_when_the_file_exists(lib):
    (OUTSIDE / "secret.txt").write_text("no")
    with pytest.raises(PermissionError):
        server.safe(str(OUTSIDE / "secret.txt"))


def test_a_symlink_inside_the_library_pointing_out_of_it_is_refused(lib):
    (OUTSIDE / "secret.txt").write_text("no")
    os.symlink(OUTSIDE / "secret.txt", lib / "link.txt")
    os.symlink(OUTSIDE, lib / "linkdir")
    with pytest.raises(PermissionError):
        server.safe("link.txt")
    with pytest.raises(PermissionError):
        server.safe("linkdir/secret.txt")


def test_a_symlink_that_stays_inside_the_library_is_followed(lib):
    (lib / "a").mkdir(); (lib / "a" / "x.png").write_bytes(b"1")
    os.symlink(lib / "a", lib / "alias")
    assert server.safe("alias/x.png") == str(lib / "a" / "x.png")


def test_a_mounted_folder_is_served_under_its_prefix(lib):
    (MOUNT / "pin.jpg").write_bytes(b"1")
    assert config.real("ext/refs/pin.jpg") == str(MOUNT / "pin.jpg")
    assert server.safe("ext/refs/pin.jpg") == str(MOUNT / "pin.jpg")


def test_a_mount_path_cannot_climb_out_of_its_folder(lib):
    (OUTSIDE / "secret.txt").write_text("no")
    with pytest.raises(PermissionError):
        server.safe("ext/refs/../outside/secret.txt")


def test_a_mount_prefix_needs_its_slash_to_match(lib):
    # "ext/refsX/..." is a library path, not the mount's
    assert config.real("ext/refsX/a.png") == os.path.join(config.W, "ext/refsX/a.png")


@pytest.mark.parametrize("p", ["/etc/hosts", "~/x.png", "../x.png", "a/../../x.png", "a\\..\\..\\x.png", "", None, 3])
def test_library_file_refuses_absolute_home_and_parent_paths_before_resolving(lib, p):
    with pytest.raises(PermissionError):
        server.library_file(p)


def test_library_file_says_not_found_for_a_missing_file_and_for_a_folder(lib):
    (lib / "a").mkdir()
    with pytest.raises(FileNotFoundError):
        server.library_file("a/none.png")
    with pytest.raises(FileNotFoundError):
        server.library_file("a")


def test_an_old_path_resolves_through_the_moved_files_list(lib):
    (lib / "new").mkdir(); (lib / "new" / "x.png").write_bytes(b"1")
    (lib / "_review" / "_favs-moved.json").write_text('{"moved_back": [{"from": "_favs/x.png", "to": "new/x.png"}]}')
    assert server.resolve("_favs/x.png") == "new/x.png"
    assert server.resolve("new/x.png") == "new/x.png"
    assert server.library_file("_favs/x.png") == str(lib / "new" / "x.png")


def test_a_broken_moved_files_list_leaves_paths_as_they_are(lib):
    (lib / "_review" / "_favs-moved.json").write_text("[1, 2")
    assert server.resolve("gone.png") == "gone.png"


def test_reveal_groups_files_by_folder_and_runs_no_shell(lib, monkeypatch):
    for d in ("a", "b"):
        (lib / d).mkdir()
        for n in (1, 2): (lib / d / f"{n}.png").write_bytes(b"1")
    calls = []
    monkeypatch.setattr(server.subprocess, "run", lambda args, **kw: calls.append(args))
    out = server.reveal(["a/1.png", "a/2.png", "b/1.png", "a/1.png"])
    assert out == {"revealed": 3, "folders": 2, "skipped": 0}
    assert calls[0][:2] == [server.REVEAL_CMD, "-R"] and len(calls[0]) == 4 and len(calls[1]) == 3


def test_reveal_opens_at_most_five_folders(lib, monkeypatch):
    for n in range(7):
        (lib / f"d{n}").mkdir(); (lib / f"d{n}" / "x.png").write_bytes(b"1")
    monkeypatch.setattr(server.subprocess, "run", lambda args, **kw: None)
    assert server.reveal([f"d{n}/x.png" for n in range(7)]) == {"revealed": 5, "folders": 5, "skipped": 2}


@pytest.mark.parametrize("p", ["/etc/hosts", "../x", "~/x"])
def test_reveal_refuses_paths_outside_the_library(lib, monkeypatch, p):
    monkeypatch.setattr(server.subprocess, "run", lambda *a, **k: pytest.fail("nothing may run"))
    with pytest.raises(PermissionError):
        server.reveal([p])


def test_open_file_runs_the_open_command_with_the_resolved_file(lib, monkeypatch):
    (lib / "x.psd").write_bytes(b"1")
    calls = []
    monkeypatch.setattr(server.subprocess, "run", lambda args, **kw: calls.append(args))
    assert server.open_file("x.psd") == {"opened": "x.psd"}
    assert calls == [[server.REVEAL_CMD, str(lib / "x.psd")]]


@pytest.mark.parametrize("name", ["main", "page_2", "A-b", "x" * 40])
def test_a_board_name_of_letters_digits_dash_and_underscore_is_a_board_file(name):
    assert server.board_path(name).endswith(f"/boards/{name}.json")


@pytest.mark.parametrize("name", ["", "../main", "a/b", "a.b", "x" * 41, "main\n", "ёлка"])
def test_any_other_board_name_is_refused(name):
    with pytest.raises(PermissionError):
        server.board_path(name)


def test_a_missing_board_loads_as_an_empty_board(lib):
    assert server.load_board("nothing") == {"schema": 1, "revision": 0, "items": {}, "groups": {}}


@pytest.mark.parametrize("sid", ["../main", "a/b", "x.json", "a b"])
def test_a_history_version_id_with_a_path_in_it_is_refused(lib, sid):
    with pytest.raises(PermissionError):
        history.load("main", sid)


class TestPluginData:
    @pytest.mark.parametrize("rel", ["3d/scenes/a.json", "3d/a/b.glb", "3d/scenes/x/.posters/card-front.jpg"])
    def test_plugin_data_under_3d_is_written(self, lib, rel):
        data = b'{"a": 1}' if rel.endswith(".json") else b"bytes"
        out = server.save_plugin_file(rel, data)
        assert out["path"] == rel and (lib / rel).read_bytes() == data

    @pytest.mark.parametrize("rel", ["a.json", "3d/../a.json", "/3d/a.json", "3d/a.png", "3d/a.py", "", None])
    def test_anything_else_is_refused(self, lib, rel):
        with pytest.raises((ValueError, PermissionError, TypeError)):
            server.save_plugin_file(rel, b"{}")

    def test_a_json_that_does_not_parse_is_refused(self, lib):
        with pytest.raises(ValueError):
            server.save_plugin_file("3d/a.json", b"{nope")
        assert not (lib / "3d" / "a.json").exists()

    def test_a_3d_folder_linked_out_of_the_library_is_refused(self, lib):
        os.symlink(OUTSIDE, lib / "3d")
        with pytest.raises(PermissionError):
            server.save_plugin_file("3d/a.json", b"{}")
        assert not (OUTSIDE / "a.json").exists()

    def test_a_new_poster_replaces_the_cards_other_poster(self, lib):
        server.save_plugin_file("3d/s/.posters/c1-front.jpg", b"1")
        server.save_plugin_file("3d/s/.posters/c2-front.jpg", b"1")
        server.save_plugin_file("3d/s/.posters/c1-side.png", b"2")
        assert sorted(os.listdir(lib / "3d/s/.posters")) == ["c1-side.png", "c2-front.jpg"]
