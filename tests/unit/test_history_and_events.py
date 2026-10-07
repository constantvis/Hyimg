"""Version snapshots of a board (history.py) and what happened on a page event by event (events.py)."""
import gzip
import json
import os
import time

import pytest

import events
import history


@pytest.fixture
def boards(tmp_path, monkeypatch):
    d = tmp_path / "boards"; d.mkdir()
    monkeypatch.setattr(history, "BOARDS", str(d)); monkeypatch.setattr(events, "BOARDS", str(d))
    history._MISS.clear()
    return d


def board(rev=1, pics=("a/1.png",), notes=0, groups=0):
    items = {f"p{n}": {"path": p, "x": 0, "y": 0} for n, p in enumerate(pics)}
    items.update({f"n{n}": {"type": "note", "text": "hi"} for n in range(notes)})
    return {"revision": rev, "items": items, "groups": {f"g{n}": {"members": []} for n in range(groups)}}


class TestHistory:
    def test_counts_tell_pictures_notes_titles_and_groups_apart(self):
        b = board(pics=("a", "b"), notes=1, groups=2); b["items"]["t"] = {"type": "text", "text": "T"}
        assert history.counts(b) == {"pictures": 2, "notes": 1, "titles": 1, "groups": 2}

    def test_a_snapshot_stores_the_board_gzipped_and_lists_it(self, boards):
        e = history.snapshot("main", "ai", "before", board(rev=7))
        assert e["who"] == "ai" and e["label"] == "before" and e["revision"] == 7 and e["pictures"] == 1
        with gzip.open(boards / "_history" / "main" / (e["id"] + ".json.gz"), "rt") as f:
            assert json.load(f)["revision"] == 7
        assert history.entries("main") == [e] and history.load("main", e["id"])["revision"] == 7

    def test_snapshots_in_the_same_second_get_their_own_ids(self, boards, monkeypatch):
        monkeypatch.setattr(history.time, "time", lambda: 1_700_000_000.0)
        ids = [history.snapshot("main", "owner", "", board())["id"] for _ in range(3)]
        assert len(set(ids)) == 3 and ids[1].endswith("~2") and ids[2].endswith("~3")
        assert all(history.load("main", i) for i in ids)

    def test_a_snapshot_without_a_board_reads_the_board_file(self, boards):
        (boards / "main.json").write_text(json.dumps(board(rev=4)))
        assert history.snapshot("main")["revision"] == 4

    def test_a_page_without_history_has_no_entries(self, boards):
        assert history.entries("none") == []

    def test_auto_snapshots_once_per_ten_minutes(self, boards, monkeypatch):
        now = [time.mktime(time.strptime("2026-10-06 12:00:00", "%Y-%m-%d %H:%M:%S"))]
        monkeypatch.setattr(history.time, "time", lambda: now[0])
        assert history.auto("main", board())["who"] == "auto"
        now[0] += history.AUTO_EVERY - 5
        assert history.auto("main", board()) is None
        now[0] += 10
        assert history.auto("main", board()) is not None

    def test_restore_snapshots_the_current_board_first_and_keeps_its_revision(self, boards):
        (boards / "main.json").write_text(json.dumps(board(rev=1, pics=("old.png",))))
        old = history.snapshot("main", "owner", "v1")
        (boards / "main.json").write_text(json.dumps(board(rev=9, pics=("new.png",))))
        written = []
        assert history.restore("main", old["id"], lambda b: written.append(b) or "ok") == "ok"
        assert written[0]["revision"] == 9 and written[0]["items"]["p0"]["path"] == "old.png"
        last = history.entries("main")[-1]
        assert last["who"] == "auto" and last["revision"] == 9 and "before restoring" in last["label"]

    def test_missing_lists_a_snapshots_gone_pictures_once_and_remembers(self, boards):
        e = history.snapshot("main", "owner", "", board(pics=("a.png", "b.png", "a.png")))
        asked = []
        assert history.missing("main", e["id"], lambda p: asked.append(p) or p == "b.png") == ["a.png"]
        n = len(asked)
        history.missing("main", e["id"], lambda p: asked.append(p))
        assert len(asked) == n


class TestEventsDiff:
    def test_nothing_changed_gives_no_events(self):
        assert events.diff(board(), board()) == []

    def test_added_and_removed_pictures_are_one_event_each(self):
        old = {"items": {"a": {"path": "1.png"}, "b": {"path": "2.png"}}}
        new = {"items": {"a": {"path": "1.png"}, "c": {"path": "3.png"}, "d": {"path": "4.png"}}}
        ev = events.diff(old, new)
        assert [(e["kind"], e["count"]) for e in ev] == [("add", 2), ("remove", 1)]
        assert ev[0]["paths"] == ["3.png", "4.png"] and ev[1]["paths"] == ["2.png"]

    def test_a_new_group_with_its_new_pictures_is_one_group_event(self):
        new = {"items": {"a": {"path": "1.png"}, "b": {"path": "2.png"}, "n": {"type": "note", "text": ""}},
               "groups": {"g": {"title": "  Shoot\n day ", "members": ["a", "n"]}}}
        ev = events.diff({}, new)
        assert ev[0] == {"kind": "group", "ids": ["g"], "title": "Shoot day", "count": 1, "paths": ["1.png"], "new": 1}
        assert ev[1]["kind"] == "add" and ev[1]["ids"] == ["b"]

    def test_an_untitled_group_is_called_group(self):
        assert events.diff({}, {"groups": {"g": {}}})[0]["title"] == "Group"

    def test_a_removed_and_a_renamed_group(self):
        old = {"items": {"a": {"path": "1.png"}}, "groups": {"g1": {"title": "A", "members": ["a"]}, "g2": {"title": "B"}}}
        new = {"items": {"a": {"path": "1.png"}}, "groups": {"g2": {"title": "C"}}}
        ev = events.diff(old, new)
        assert {"kind": "group-remove", "ids": ["g1"], "title": "A", "count": 1} in ev
        assert {"kind": "rename", "ids": ["g2"], "title": "C", "was": "B"} in ev

    def test_notes_and_titles_written_edited_and_removed(self):
        old = {"items": {"n1": {"type": "note", "text": "old"}, "n2": {"type": "note", "text": "bye", "color": "red"}, "t": {"type": "text", "text": "Same"}}}
        new = {"items": {"n1": {"type": "note", "text": "new text"}, "t": {"type": "text", "text": "Same"}, "n3": {"type": "note", "text": "hello", "color": "blue"},
                         "tl": {"type": "timeline", "label": "Phase 1"}}}
        kinds = {e["kind"]: e for e in events.diff(old, new)}
        assert kinds["note-edit"]["text"] == "new text" and kinds["note-remove"]["text"] == "bye" and kinds["note"]["color"] == "blue"
        assert kinds["timeline"]["text"] == "Phase 1" and "text-edit" not in kinds

    def test_a_note_emptied_is_not_an_edit(self):
        assert events.diff({"items": {"n": {"type": "note", "text": "x"}}}, {"items": {"n": {"type": "note", "text": "  "}}}) == []

    def test_moves_under_half_a_point_are_not_moves(self):
        old = {"items": {"a": {"path": "1.png", "x": 10.2, "y": 0}}}
        assert events.diff(old, {"items": {"a": {"path": "1.png", "x": 10.4, "y": 0}}}) == []
        ev = events.diff(old, {"items": {"a": {"path": "1.png", "x": 30, "y": 0}}})
        assert ev == [{"kind": "move", "ids": ["a"], "count": 1, "groups": 0, "titles": [], "paths": ["1.png"]}]

    def test_a_moved_group_is_named_in_the_move(self):
        old = {"groups": {"g": {"title": "G", "x": 0, "y": 0}}}
        ev = events.diff(old, {"groups": {"g": {"title": "G", "x": 5, "y": 0}}})
        assert ev[0]["groups"] == 1 and ev[0]["titles"] == ["G"] and ev[0]["ids"] == ["g"]

    def test_at_most_24_paths_and_200_ids_are_remembered(self):
        new = {"items": {f"i{n}": {"path": f"{n}.png"} for n in range(300)}}
        ev = events.diff({}, new)[0]
        assert ev["count"] == 300 and len(ev["ids"]) == 200 and len(ev["paths"]) == events.SAMPLE


class TestEventsLog:
    def test_record_appends_one_line_per_event_newest_read_first(self, boards):
        assert events.record("main", {}, {"revision": 2, "items": {"a": {"path": "1.png"}}}, "ai", "batch") == 1
        events.record("main", {}, {"items": {"n": {"type": "note", "text": "x"}}})
        got = events.read("main")
        assert [e["kind"] for e in got] == ["note", "add"] and got[1]["who"] == "ai" and got[1]["label"] == "batch" and got[1]["rev"] == 2

    def test_the_agent_behind_an_ai_save_is_kept_and_its_moves_fold_only_with_its_own(self, boards, monkeypatch):
        """Home names the agent in a board's news (owner 2026-10-06): hy.py sends HYIMG_AGENT with its saves"""
        monkeypatch.setattr(events.time, "time", lambda: 1000.0)
        a0, a1, a2 = ({"items": {"a": {"path": "1.png", "x": x, "y": 0}}} for x in (0, 10, 20))
        events.record("main", {}, {"items": {"n": {"type": "note", "text": "x"}}}, "ai", agent="Codex")
        events.record("main", a0, a1, "ai", agent="Codex"); events.record("main", a1, a2, "ai", agent="Claude")
        got = events.read("main")
        assert [(e["kind"], e.get("agent")) for e in got] == [("move", "Claude"), ("move", "Codex"), ("note", "Codex")]
        events.record("main", {}, {"items": {"b": {"path": "2.png"}}})
        assert "agent" not in events.read("main")[0]

    def test_record_of_no_change_writes_nothing(self, boards):
        assert events.record("main", board(), board()) == 0 and not (boards / "_events").exists()

    def test_moves_of_one_author_within_the_fold_time_are_one_event(self, boards, monkeypatch):
        now = [1000.0]
        monkeypatch.setattr(events.time, "time", lambda: now[0])
        a0, a1, a2 = ({"items": {"a": {"path": "1.png", "x": x, "y": 0}, "b": {"path": "2.png", "x": 0, "y": 0}}} for x in (0, 10, 20))
        events.record("main", a0, a1)
        now[0] += 60
        b2 = json.loads(json.dumps(a2)); b2["items"]["b"]["x"] = 50
        events.record("main", a1, b2)
        got = events.read("main")
        assert len(got) == 1 and set(got[0]["ids"]) == {"a", "b"} and got[0]["count"] == 2 and "since" in got[0]

    def test_moves_by_another_author_or_after_the_fold_time_are_new_events(self, boards, monkeypatch):
        now = [1000.0]
        monkeypatch.setattr(events.time, "time", lambda: now[0])
        a0, a1, a2 = ({"items": {"a": {"path": "1.png", "x": x, "y": 0}}} for x in (0, 10, 20))
        events.record("main", a0, a1, "owner")
        events.record("main", a1, a2, "ai")
        now[0] += events.FOLD_S + 1
        events.record("main", a2, a0, "ai")
        assert len(events.read("main")) == 3

    def test_the_log_keeps_the_last_events_when_it_grows_past_its_slack(self, boards, monkeypatch):
        monkeypatch.setattr(events, "KEEP", 5)
        for n in range(306):
            events.record("main", {}, {"items": {f"a{n}": {"path": f"{n}.png"}}})
        lines = (boards / "_events" / "main.jsonl").read_text().splitlines()
        assert len(lines) == 5 and json.loads(lines[-1])["paths"] == ["305.png"]

    def test_read_skips_broken_lines_and_honours_limit_and_before(self, boards):
        p = boards / "_events"; p.mkdir()
        (p / "main.jsonl").write_text("\n".join([json.dumps({"kind": "add", "ts": t}) for t in (1, 2, 3)] + ["{broken"]) + "\n")
        assert [e["ts"] for e in events.read("main")] == [3, 2, 1]
        assert [e["ts"] for e in events.read("main", limit=2)] == [3, 2]
        assert [e["ts"] for e in events.read("main", before=3)] == [2, 1]

    def test_a_page_without_a_log_reads_empty(self, boards):
        assert events.read("none") == []
