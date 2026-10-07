"""One picture, one place in the library (dedup.py): the sha1 index, folding byte-identical copies, empty files kept apart."""
import json
import os

import pytest

import dedup


@pytest.fixture
def lib2(tmp_path, monkeypatch):
    """a library of its own with the state folder inside it, as a board has"""
    root = tmp_path / "lib"; state = root / "_review"; state.mkdir(parents=True)
    monkeypatch.setattr(dedup, "W", str(root)); monkeypatch.setattr(dedup, "HERE", str(state))
    monkeypatch.setattr(dedup, "INDEX", str(state / "sha-index.json"))
    monkeypatch.setattr(dedup, "_IDX", None)

    def put(rel, data=b"pic"):
        p = root / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data); return p
    put.root, put.state = root, state
    return put


def test_the_sha_of_a_file_is_its_sha1(lib2):
    p = lib2("a.png", b"abc")
    assert dedup.sha_file(str(p)) == "a9993e364706816aba3e25717850c26c9cd0d89d"


def test_only_pictures_outside_the_state_hidden_and_skipped_folders_are_listed(lib2):
    for rel in ("a/1.png", "a/2.JPG", "a/3.webp", "a/4.jpeg", "a/doc.pdf", "a/clip.mp4", "_review/x.png", ".hidden/x.png", "skip/x.png", "a/skip/y.png"):
        lib2(rel)
    assert sorted(dedup.library_files(skip={"skip"}, here=str(lib2.state))) == ["a/1.png", "a/2.JPG", "a/3.webp", "a/4.jpeg"]


def test_fill_hashes_new_files_once_and_again_only_when_they_change(lib2, monkeypatch):
    lib2("a.png", b"1"); lib2("b.png", b"2")
    assert dedup.fill() == 2
    assert dedup.fill() == 0
    lib2("a.png", b"changed")
    assert dedup.fill() == 1
    saved = json.load(open(dedup.INDEX))
    assert set(saved) == {"a.png", "b.png"} and saved["a.png"][2] == dedup.sha_file(str(lib2.root / "a.png"))


def test_fill_forgets_files_that_are_gone(lib2):
    p = lib2("a.png"); lib2("b.png", b"x")
    dedup.fill(); p.unlink()
    dedup.fill()
    assert dedup.sha_of("a.png") is None and dedup.sha_of("b.png")


def test_an_empty_file_is_never_hashed_and_leaves_the_index_when_it_empties(lib2):
    p = lib2("a.png", b"x"); lib2("e1.png", b""); lib2("e2.png", b"")
    dedup.fill()
    assert dedup.sha_of("e1.png") is None and dedup.sha_of("a.png")
    p.write_bytes(b"")
    dedup.fill()
    assert dedup.sha_of("a.png") is None


def test_a_broken_index_file_is_started_again(lib2):
    open(dedup.INDEX, "w").write("{nope")
    lib2("a.png")
    assert dedup.fill() == 1


def test_known_names_the_shortest_then_first_path_of_a_sha(lib2):
    lib2("long/name/a.png", b"same"); lib2("b/a.png", b"same"); lib2("a/a.png", b"same")
    dedup.fill()
    sha = dedup.sha_of("b/a.png")
    assert dedup.known([sha, "0" * 40]) == {sha: "a/a.png"}


def test_rekey_moves_a_files_sha_with_it_and_never_overwrites(lib2):
    lib2("a.png", b"1"); lib2("b.png", b"2")
    dedup.fill()
    sa, sb = dedup.sha_of("a.png"), dedup.sha_of("b.png")
    assert dedup.rekey([("a.png", "moved/a.png"), ("b.png", "moved/a.png"), ("none.png", "x.png")]) == 1
    assert dedup.sha_of("moved/a.png") == sa and dedup.sha_of("b.png") == sb and dedup.sha_of("a.png") is None
    assert json.load(open(dedup.INDEX))["moved/a.png"][2] == sa


def _items(lib2, spec):
    """spec: (path, bytes, extra fields); the index filled, items as scan gives them"""
    for path, data, _ in spec: lib2(path, data)
    dedup.fill()
    return [{"path": p, "size": len(d), **extra} for p, d, extra in spec]


def test_identical_files_fold_into_the_oldest_one(lib2):
    items = _items(lib2, [("new/a.png", b"same", {"born": 20}), ("old/a.png", b"same", {"born": 10}), ("c.png", b"other", {"born": 5})])
    out = dedup.collapse(items)
    assert [i["path"] for i in out] == ["old/a.png", "c.png"]
    assert out[0]["copies"] == ["new/a.png"] and items[0]["copy_of"] == "old/a.png"


def test_the_copy_the_owner_reacted_to_is_the_one_kept(lib2):
    items = _items(lib2, [("old.png", b"same", {"born": 1}), ("loved.png", b"same", {"born": 9, "feedback": {"fav": True}})])
    assert [i["path"] for i in dedup.collapse(items)] == ["loved.png"]


def test_a_copy_with_a_reaction_is_never_hidden(lib2):
    items = _items(lib2, [("a.png", b"same", {"born": 1, "feedback": {"fav": True}}), ("b.png", b"same", {"born": 2, "feedback": {"comment": "x"}}),
                          ("c.png", b"same", {"born": 3, "feedback": {"comment": "", "fav": False}})])
    assert [i["path"] for i in dedup.collapse(items)] == ["a.png", "b.png"]


def test_an_archived_copy_gives_way_to_one_on_a_board(lib2):
    items = _items(lib2, [("arch.png", b"same", {"born": 1, "archived": True}), ("live.png", b"same", {"born": 2})])
    assert [i["path"] for i in dedup.collapse(items)] == ["live.png"]


def test_keep_copies_marks_them_hidden_instead_of_dropping_them(lib2):
    items = _items(lib2, [("a.png", b"same", {"born": 1}), ("b.png", b"same", {"born": 2})])
    out = dedup.collapse(items, keep_copies=True)
    assert len(out) == 2 and out[1]["hidden"] is True and "hidden" not in out[0]


def test_empty_files_are_never_copies_of_each_other(lib2):
    items = _items(lib2, [("e1.png", b"", {"born": 1}), ("e2.png", b"", {"born": 2}), ("u.png", b"x", {"born": 3, "empty": True})])
    assert len(dedup.collapse(items)) == 3


def test_a_file_not_in_the_index_stays(lib2):
    assert dedup.collapse([{"path": "nowhere.png", "size": 4}]) == [{"path": "nowhere.png", "size": 4}]
