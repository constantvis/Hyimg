"""Saves of a board merged object by object (review/merge.py, owner 2026-10-08: «Две правки одной доски с двух Маков могут перезаписать
друг друга. Сделать слияние по объектам? — да»): the three-way merge itself, a stale save through the server, the conflict records,
the base found again after a restart, and Dropbox's conflicted copies."""
import gzip
import json
import os
import shutil
import threading
import time

import pytest

from unit_env import LIB, history, server

import events
import foldersync
import merge

ANN = "5b1f6c2e-7d3a-4e8b-9c0d-1e2f3a4b5c6d"
A, B = {"via": "app", "person": ANN}, {"via": "claude", "person": ANN}


def pic(x=0, y=0, **k):
    return {"path": k.pop("path", "a/1.png"), "x": x, "y": y, "w": 320, "ar": 1.5, **k}


def bd(items=None, groups=None, **k):
    return {"schema": 1, "revision": 1, "items": items or {}, "groups": groups or {}, "removed": {}, **k}


def m3(base, ours, theirs, t_ours=2.0, t_theirs=1.0):
    return merge.merge3(base, ours, theirs, t_ours, t_theirs, A, B)


@pytest.fixture
def boards(lib):
    merge._MEMO.clear(); merge._SWEPT["t"] = 0.0
    shutil.rmtree(merge._file("main", "x")[0], ignore_errors=True)
    merge.PEOPLE = ""
    yield LIB / "_review" / "boards"
    merge._MEMO.clear()


def evs(page="main"):
    return list(reversed(events.read(page)))


class TestMergeOneSide:
    def test_a_thing_changed_on_one_side_takes_that_side(self):
        base = bd({"i": pic(0)})
        out, c = m3(base, bd({"i": pic(100)}), base)
        assert out["items"]["i"]["x"] == 100 and c == []
        out, c = m3(base, base, bd({"i": pic(0, 50)}))
        assert out["items"]["i"]["y"] == 50 and c == []

    def test_added_on_either_side_are_kept(self):
        base = bd({"i": pic()})
        out, c = m3(base, bd({"i": pic(), "o": pic(path="o.png")}), bd({"i": pic(), "t": pic(path="t.png")}))
        assert set(out["items"]) == {"i", "o", "t"} and c == []

    def test_deleted_on_one_side_and_untouched_on_the_other_is_deleted(self):
        base = bd({"i": pic(), "j": pic(path="j.png")})
        out, _ = m3(base, bd({"j": pic(path="j.png")}), base)
        assert set(out["items"]) == {"j"}
        out, _ = m3(base, base, bd({"i": pic()}))
        assert set(out["items"]) == {"i"}

    def test_deleted_on_both_sides_is_deleted_without_a_record(self):
        base = bd({"i": pic(), "j": pic()})
        out, c = m3(base, bd({"j": pic()}), bd({"j": pic()}))
        assert set(out["items"]) == {"j"} and c == []

    def test_the_same_change_on_both_sides_is_no_conflict(self):
        base = bd({"i": pic(0)})
        out, c = m3(base, bd({"i": pic(9)}), bd({"i": pic(9)}))
        assert out["items"]["i"]["x"] == 9 and c == []

    def test_a_key_taken_out_on_one_side_goes(self):
        base = bd({"i": pic(crop={"x": 0.1, "y": 0, "w": 0.5, "h": 1})})
        out, c = m3(base, bd({"i": pic()}), base)
        assert "crop" not in out["items"]["i"] and c == []

    def test_a_dict_value_compares_by_content_not_key_order(self):
        base = bd({"i": pic(crop={"x": 0.1, "y": 0})})
        out, c = m3(base, bd({"i": pic(crop={"y": 0, "x": 0.1}, grade=2)}), bd({"i": pic(crop={"x": 0.1, "y": 0}, x=5)}))
        assert out["items"]["i"]["grade"] == 2 and out["items"]["i"]["x"] == 5 and c == []


class TestMergeBothSides:
    def test_different_fields_of_one_thing_both_apply(self):
        base = bd({"n": {"type": "note", "text": "hi", "x": 0, "y": 0, "w": 200, "color": "yellow"}})
        ours = bd({"n": {"type": "note", "text": "hi", "x": 300, "y": 40, "w": 200, "color": "yellow"}})
        theirs = bd({"n": {"type": "note", "text": "hello", "x": 0, "y": 0, "w": 200, "color": "red"}})
        out, c = m3(base, ours, theirs)
        assert out["items"]["n"] == {"type": "note", "text": "hello", "x": 300, "y": 40, "w": 200, "color": "red"} and c == []

    def test_position_and_size_are_separate_fields(self):
        base = bd({"i": pic(0, 0, h=200)})
        out, c = m3(base, bd({"i": pic(50, 60, h=200)}), bd({"i": {**pic(0, 0, h=400), "w": 640}}))
        assert (out["items"]["i"]["x"], out["items"]["i"]["y"], out["items"]["i"]["w"], out["items"]["i"]["h"]) == (50, 60, 640, 400) and c == []

    def test_x_and_y_are_one_position_so_a_move_is_never_half_taken(self):
        base = bd({"i": pic(0, 0)})
        out, c = m3(base, bd({"i": pic(100, 0)}), bd({"i": pic(0, 100)}), t_ours=1, t_theirs=2)
        assert (out["items"]["i"]["x"], out["items"]["i"]["y"]) == (0, 100)
        assert len(c) == 1 and c[0]["field"] == "position" and c[0]["value"] == {"x": 0, "y": 100} and c[0]["lost"] == {"x": 100, "y": 0}

    @pytest.mark.parametrize("t_ours,t_theirs,kept", [(2, 1, "ours"), (1, 2, "theirs")])
    def test_the_same_field_the_newer_change_wins_and_the_loser_is_recorded(self, t_ours, t_theirs, kept):
        base = bd({"n": {"type": "note", "text": "a", "x": 0, "y": 0}})
        ours, theirs = bd({"n": {"type": "note", "text": "ours", "x": 0, "y": 0}}), bd({"n": {"type": "note", "text": "theirs", "x": 0, "y": 0}})
        out, c = m3(base, ours, theirs, t_ours, t_theirs)
        assert out["items"]["n"]["text"] == kept
        lost = "theirs" if kept == "ours" else "ours"
        assert c == [{"kind": "item", "id": "n", "field": "text", "kept": kept, "value": kept, "lost": lost, "text": "ours",
                      "kept_by": A if kept == "ours" else B, "lost_by": B if kept == "ours" else A,
                      "kept_t": max(t_ours, t_theirs), "lost_t": min(t_ours, t_theirs)}]

    def test_a_tie_keeps_the_save_in_hand(self):
        base = bd({"i": pic(0)})
        out, c = m3(base, bd({"i": pic(1)}), bd({"i": pic(2)}), 5, 5)
        assert out["items"]["i"]["x"] == 1 and c[0]["kept"] == "ours"

    @pytest.mark.parametrize("deleter", ["ours", "theirs"])
    def test_deleted_on_one_side_and_changed_on_the_other_stays_with_a_record(self, deleter):
        base, moved = bd({"i": pic(0)}), bd({"i": pic(500)})
        ours, theirs = (bd(), moved) if deleter == "ours" else (moved, bd())
        out, c = m3(base, ours, theirs)
        assert out["items"]["i"]["x"] == 500
        assert len(c) == 1 and c[0]["field"] == "deleted" and c[0]["lost"] is None and c[0]["kept"] != deleter and c[0]["path"] == "a/1.png"

    def test_several_conflicts_are_all_recorded(self):
        base = bd({"i": pic(0, color="a"), "j": pic(0, path="j.png")})
        out, c = m3(base, bd({"i": pic(1, color="b"), "j": pic(1, path="j.png")}), bd({"i": pic(2, color="c"), "j": pic(2, path="j.png")}))
        assert sorted((x["id"], x["field"]) for x in c) == [("i", "color"), ("i", "position"), ("j", "position")]


class TestGroupsPageAndOrder:
    def test_group_members_merge_as_sets(self):
        base = bd(groups={"g": {"title": "G", "x": 0, "y": 0, "members": ["a", "b", "c"]}})
        ours = bd(groups={"g": {"title": "G", "x": 0, "y": 0, "members": ["a", "b", "c", "d"]}})
        theirs = bd(groups={"g": {"title": "G2", "x": 0, "y": 0, "members": ["a", "c", "e"]}})
        out, c = m3(base, ours, theirs)
        assert out["groups"]["g"] == {"title": "G2", "x": 0, "y": 0, "members": ["a", "c", "d", "e"]} and c == []

    def test_members_never_conflict_even_when_both_sides_rewrote_them(self):
        base = bd(groups={"g": {"members": ["a"]}})
        out, c = m3(base, bd(groups={"g": {"members": ["b"]}}), bd(groups={"g": {"members": ["c"]}}))
        assert out["groups"]["g"]["members"] == ["b", "c"] and c == []

    def test_a_group_title_changed_on_both_sides_is_a_conflict(self):
        base = bd(groups={"g": {"title": "G", "members": []}})
        out, c = m3(base, bd(groups={"g": {"title": "Ours", "members": []}}), bd(groups={"g": {"title": "Theirs", "members": []}}), 1, 2)
        assert out["groups"]["g"]["title"] == "Theirs" and c[0]["kind"] == "group" and c[0]["field"] == "title"

    def test_removed_marks_merge_by_path(self):
        base = {**bd(), "removed": {"a.png": 1, "b.png": 1}}
        out, c = m3(base, {**bd(), "removed": {"a.png": 1, "b.png": 1, "c.png": 2}}, {**bd(), "removed": {"a.png": 1}})
        assert out["removed"] == {"a.png": 1, "c.png": 2} and c == []

    def test_page_fields_merge_one_by_one(self):
        base = bd(bg="grey", title="P")
        out, c = m3(base, bd(bg="white", title="P"), bd(bg="grey", title="Q", extra=1))
        assert (out["bg"], out["title"], out["extra"]) == ("white", "Q", 1) and c == []
        out, c = m3(base, bd(bg="white"), bd(bg="black"), 1, 2)
        assert out["bg"] == "black" and c[0]["kind"] == "page" and c[0]["field"] == "bg"

    def test_draw_order_is_ours_when_ours_reordered_else_theirs_new_ones_after(self):
        base = bd({"a": pic(), "b": pic(), "c": pic()})
        out, _ = m3(base, bd({"c": pic(), "a": pic(), "b": pic()}), bd({"a": pic(), "b": pic(), "c": pic(), "t": pic()}))
        assert list(out["items"]) == ["c", "a", "b", "t"]
        out, _ = m3(base, bd({"a": pic(), "b": pic(), "c": pic(), "o": pic()}), bd({"b": pic(), "a": pic(), "c": pic()}))
        assert list(out["items"]) == ["b", "a", "c", "o"]

    def test_the_merged_board_keeps_the_files_meta_for_the_writer_to_restamp(self):
        out, _ = m3(bd(), bd(revision=1, vid="o"), bd(revision=4, vid="t", saved="s"))
        assert (out["revision"], out["vid"], out["saved"]) == (4, "t", "s")


class TestNoBase:
    def test_without_a_base_nothing_is_deleted_and_differences_are_conflicts(self):
        ours = bd({"i": pic(1), "o": pic(path="o.png")})
        theirs = bd({"i": pic(2, crop={"x": 0}), "t": pic(path="t.png")})
        out, c = merge.merge3(None, ours, theirs, 1, 2)
        assert set(out["items"]) == {"i", "o", "t"} and out["items"]["i"]["x"] == 2 and out["items"]["i"]["crop"] == {"x": 0}
        assert [(x["id"], x["field"]) for x in c] == [("i", "position")]


class TestSaveThroughTheServer:
    def test_a_save_from_the_current_version_is_written_with_a_vid_and_its_parent(self, boards):
        code, r1 = server.save_board("main", bd(revision=0), A)
        code, r2 = server.save_board("main", {**bd({"i": pic()}), "revision": r1["revision"], "vid": r1["vid"]}, A)
        b = json.loads((boards / "main.json").read_text())
        assert code == 200 and "merged" not in r2 and b["revision"] == 2 and b["vid"] == r2["vid"] != r1["vid"]
        assert b["parent"] == f"{r1['vid']}~1" == merge.key_of({"vid": r1["vid"], "revision": 1}) and b["by"] == A and isinstance(b["edited"], float)

    def test_a_stale_save_is_merged_with_the_newer_file_not_refused(self, boards):
        server.save_board("main", bd({"i": pic(0), "j": pic(0, path="j.png")}, revision=0), A)
        loaded = json.loads((boards / "main.json").read_text())
        agent = json.loads(json.dumps(loaded)); agent["items"]["j"]["x"] = 900
        code, ra = server.save_board("main", agent, B)
        assert "merged" not in ra
        owner = json.loads(json.dumps(loaded)); owner["items"]["i"]["x"] = 400
        code, r = server.save_board("main", owner, A, time.time())
        b = json.loads((boards / "main.json").read_text())
        assert code == 200 and b["items"]["i"]["x"] == 400 and b["items"]["j"]["x"] == 900 and b["revision"] == 3
        assert r["merged"] == {"from": [B], "conflicts": [], "base": True} and r["board"]["items"] == b["items"]
        assert not [e for e in evs() if e["kind"] == "merge"]

    def test_a_conflict_keeps_the_newer_and_records_the_older_in_events_and_history(self, boards):
        server.save_board("main", bd({"n": {"type": "note", "text": "a", "x": 0, "y": 0}}, revision=0), A)
        loaded = json.loads((boards / "main.json").read_text())
        owner = json.loads(json.dumps(loaded)); owner["items"]["n"]["x"] = 111
        t_owner = time.time() - 30   # the owner moved it half a minute ago, the save comes late
        agent = json.loads(json.dumps(loaded)); agent["items"]["n"]["x"] = 222
        server.save_board("main", agent, B)
        code, r = server.save_board("main", owner, A, t_owner)
        b = json.loads((boards / "main.json").read_text())
        assert b["items"]["n"]["x"] == 222
        c = r["merged"]["conflicts"]
        assert len(c) == 1 and c[0]["kept"] == "theirs" and c[0]["lost"] == {"x": 111, "y": 0} and c[0]["kept_by"] == B
        e = [e for e in evs() if e["kind"] == "merge"][-1]
        assert e["ids"] == ["n"] and e["count"] == 1 and e["by"] == A and e["conflicts"][0]["value"] == {"x": 222, "y": 0}
        h = [x for x in history.entries("main") if x.get("merge")][-1]
        assert h["label"] == "2 changes to the same thing merged; kept Claude's position" and h["merge"] == "ours" and h["conflicts"] == 1
        assert history.load("main", h["id"])["items"]["n"]["x"] == 111   # the losing side's board, restorable

    def test_the_label_names_the_person_and_the_agent(self, boards, tmp_path):
        (tmp_path / "people.json").write_text(json.dumps({ANN: {"name": "Ann", "color": "blue"}}))
        merge.PEOPLE = str(tmp_path)
        assert merge.who_text(B) == "Claude · Ann" and merge.who_text({"via": "app", "person": ANN}) == "Ann"
        assert merge.who_text({}) == "someone"

    def test_the_base_is_found_in_the_cache_on_disk_after_a_restart(self, boards):
        server.save_board("main", bd({"i": pic(0), "j": pic(0, path="j.png")}, revision=0), A)
        loaded = json.loads((boards / "main.json").read_text())
        other = json.loads(json.dumps(loaded)); other["items"]["j"]["x"] = 5
        server.save_board("main", other, B)
        merge._MEMO.clear()   # a restarted server
        mine = json.loads(json.dumps(loaded)); del mine["items"]["i"]
        code, r = server.save_board("main", mine, A)
        b = json.loads((boards / "main.json").read_text())
        assert r["merged"]["base"] and set(b["items"]) == {"j"} and b["items"]["j"]["x"] == 5

    def test_the_base_comes_from_history_when_the_cache_is_gone(self, boards):
        server.save_board("main", bd({"i": pic(0), "j": pic(0, path="j.png")}, revision=0), A)
        loaded = json.loads((boards / "main.json").read_text())
        history.snapshot("main", "auto", "auto", loaded)
        other = json.loads(json.dumps(loaded)); other["items"]["j"]["x"] = 5
        server.save_board("main", other, B)
        merge._MEMO.clear(); shutil.rmtree(merge._file("main", "x")[0])
        mine = json.loads(json.dumps(loaded)); del mine["items"]["i"]
        code, r = server.save_board("main", mine, A)
        assert r["merged"]["base"] and set(json.loads((boards / "main.json").read_text())["items"]) == {"j"}

    def test_without_any_base_a_save_keeps_everything(self, boards):
        server.save_board("main", bd({"i": pic(0), "j": pic(0, path="j.png")}, revision=0), A)
        loaded = json.loads((boards / "main.json").read_text())
        server.save_board("main", json.loads(json.dumps(loaded)) | {"bg": "x"}, B)
        merge._MEMO.clear(); shutil.rmtree(merge._file("main", "x")[0])
        mine = json.loads(json.dumps(loaded)); del mine["items"]["i"]
        code, r = server.save_board("main", mine, A)
        assert r["merged"]["base"] is False and set(json.loads((boards / "main.json").read_text())["items"]) == {"i", "j"}

    def test_a_page_save_never_writes_comments_drawings_or_another_pages_notes(self, boards):
        files = {LIB / "comments" / "main__c1.json": '{"id": "c1"}', LIB / "annotations" / "main__a1.json": '{"id": "a1"}',
                 LIB / "notes" / "other__n1.json": '{"id": "other/n1"}'}
        for p, t in files.items(): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t)
        server.save_board("main", bd({"i": pic()}, revision=0), A)
        stale = bd({"n": {"type": "note", "text": "x", "x": 9000, "y": 9000, "w": 100, "h": 50, "to": [], "reach": None}}, revision=0)
        server.save_board("main", stale, B); server.sync_notes("main")
        assert {p: p.read_text() for p in files} == files

    def test_a_layout_rewrite_and_a_restore_give_the_board_a_new_vid(self, boards):
        server.save_board("main", bd({"i": pic()}, revision=0), A)
        b = json.loads((boards / "main.json").read_text()); old = b["vid"]
        foldersync.write_board("main", b)
        nb = json.loads((boards / "main.json").read_text())
        assert nb["vid"] != old and nb["parent"] == f"{old}~1" and nb["revision"] == 2

    def test_a_version_rewritten_by_an_older_hyimg_with_the_vid_it_read_is_another_version(self, boards):
        server.save_board("main", bd({"i": pic(0), "j": pic(0, path="j.png")}, revision=0), A)
        v1 = json.loads((boards / "main.json").read_text())
        v2 = json.loads(json.dumps(v1)); v2["items"]["j"]["x"] = 50; v2["revision"] = 2   # the partner's old app: same vid, new content
        (boards / "main.json").write_text(json.dumps(v2))
        page = json.loads(json.dumps(v2)); page["items"]["i"]["x"] = 70   # a page that loaded the partner's version
        server.save_board("main", json.loads(json.dumps(v2)) | {"items": {**v2["items"], "j": pic(60, path="j.png")}}, B)
        code, r = server.save_board("main", page, A)
        b = json.loads((boards / "main.json").read_text())
        assert merge.key_of(v1) != merge.key_of(v2) and (b["items"]["i"]["x"], b["items"]["j"]["x"]) == (70, 60) and r["merged"]["conflicts"] == []


class TestDropboxCopies:
    def _base(self, boards):
        server.save_board("main", bd({"i": pic(0), "j": pic(0, path="j.png")}, revision=0), A)
        return json.loads((boards / "main.json").read_text())

    def _copy(self, boards, b, name="main (Bob's conflicted copy 2026-10-08).json"):
        b = {**b, "revision": b["revision"] + 1, "vid": "bobvid", "parent": merge.key_of(b), "by": {"via": "app", "person": "bob"}}
        (boards / name).write_text(json.dumps(b)); return name

    def test_a_conflicted_copy_is_merged_into_its_page_and_moved_to_history(self, boards):
        base = self._base(boards)
        mine = json.loads(json.dumps(base)); mine["items"]["i"]["x"] = 300
        server.save_board("main", mine, A)
        theirs = json.loads(json.dumps(base)); theirs["items"]["j"]["x"] = 700; theirs["items"]["k"] = pic(9, path="k.png")
        name = self._copy(boards, theirs)
        assert merge.sweep(threading.Lock(), settle=0) == ["main"]
        b = json.loads((boards / "main.json").read_text())
        assert (b["items"]["i"]["x"], b["items"]["j"]["x"], "k" in b["items"]) == (300, 700, True) and b["revision"] == 3
        assert not (boards / name).exists() and (boards / "_history" / "main" / "dropbox" / name).exists()
        e = [e for e in evs() if e["kind"] == "dropbox"][-1]
        assert e["file"] == name and e["count"] == 0 and e["from"] == [{"via": "app", "person": "bob"}]
        assert any(e["kind"] == "add" for e in evs())   # what came from the copy is in the timeline
        h = [x for x in history.entries("main") if x.get("dropbox") == name]
        assert h and history.load("main", h[0]["id"])["items"]["j"]["x"] == 700

    def test_a_copy_that_changed_the_same_field_is_a_recorded_conflict(self, boards):
        base = self._base(boards)
        mine = json.loads(json.dumps(base)); mine["items"]["i"]["x"] = 300
        server.save_board("main", mine, A, time.time() - 60)
        theirs = json.loads(json.dumps(base)); theirs["items"]["i"]["x"] = 800; theirs["edited"] = time.time()
        self._copy(boards, theirs)
        merge.sweep(threading.Lock(), settle=0)
        b = json.loads((boards / "main.json").read_text())
        e = [e for e in evs() if e["kind"] == "dropbox"][-1]
        assert b["items"]["i"]["x"] == 800 and e["count"] == 1 and e["conflicts"][0]["lost"] == {"x": 300, "y": 0}

    def test_a_copy_with_nothing_new_is_only_moved_away(self, boards):
        base = self._base(boards)
        name = self._copy(boards, base)
        rev = json.loads((boards / "main.json").read_text())["revision"]
        assert merge.sweep(threading.Lock(), settle=0) == []
        assert json.loads((boards / "main.json").read_text())["revision"] == rev and not (boards / name).exists()

    def test_a_broken_copy_is_moved_aside_and_the_page_kept(self, boards):
        self._base(boards)
        before = (boards / "main.json").read_text()
        (boards / "main (conflicted copy).json").write_text("{not json")
        merge.sweep(threading.Lock(), settle=0)
        assert (boards / "main.json").read_text() == before and (boards / "_history" / "main" / "dropbox" / "main (conflicted copy).json").exists()

    def test_a_fresh_copy_waits_and_sweeps_are_spaced(self, boards):
        self._base(boards)
        name = self._copy(boards, json.loads((boards / "main.json").read_text()))
        assert merge.sweep(threading.Lock()) == [] and (boards / name).exists()   # Dropbox may still be writing it
        os.utime(boards / name, (time.time() - 10, time.time() - 10))
        assert merge.sweep(threading.Lock()) == [] and (boards / name).exists()   # the next look is in a few seconds
        merge._SWEPT["t"] = 0.0; merge.sweep(threading.Lock())
        assert not (boards / name).exists()

    def test_only_board_pages_count_as_copies(self):
        assert merge.COPY.match("main (Ann's conflicted copy 2026-10-08).json").group(1) == "main"
        assert merge.COPY.match("p2 (conflicted copy 2026-10-08 1).json").group(1) == "p2"
        assert not merge.COPY.match("pages (x).json") and not merge.COPY.match("../x (conflicted copy).json")


def test_the_cache_keeps_the_last_versions_gzipped_outside_dropbox(boards, monkeypatch):
    monkeypatch.setattr(merge, "KEEP", 3)
    for n in range(5):
        merge.seen("main", bd(revision=n, vid=f"v{n}")); time.sleep(0.01)
    d = merge._file("main", "x")[0]
    assert sorted(os.listdir(d)) == ["v2_2.json.gz", "v3_3.json.gz", "v4_4.json.gz"] and not d.startswith(str(LIB))
    with gzip.open(os.path.join(d, "v4_4.json.gz"), "rt") as fh: assert json.load(fh)["vid"] == "v4"
