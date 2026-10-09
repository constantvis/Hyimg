"""Every notification has a place on the board (notifplace.py, owner 2026-10-08: a notification «put 21 references next to the
storyboard» came without ids, and a click on it in the bell went nowhere). One that names nothing gets its author's things from the
page's events; a click on an old one finds them around its time; a repair writes them in through the server."""
import json
import time

import pytest

import events
import notifplace
from unit_env import server

ME = {"person": "p-1", "via": "claude"}
OTHER = {"person": "p-1", "via": "codex"}


def pic(x, y=0, path=None):
    return {"path": path or f"a/{x}.png", "x": x, "y": y, "w": 100, "ar": 1.0, "crop": None}


def ev(kind, ids, t, by=ME, **kw):
    return {"kind": kind, "ids": ids, "ts": t, "t": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)), "who": "ai", "by": by, **kw}


T0 = 1_790_000_000.0
BOARD = {"items": {"a": pic(0), "b": pic(200), "c": pic(400, 300), "n": {"type": "note", "text": "hi", "x": 0, "y": -300, "w": 200},
                   "old": pic(5000), "x": pic(9000)},
         "groups": {"g": {"title": "Refs", "x": -50, "y": -50, "w": 600, "h": 500, "members": ["a", "b"]}}}


class TestFind:
    def test_names_what_the_author_put_since_its_last_notification(self):
        notes = [{"id": "prev", "ts": T0 - 600, "page": "main", "by": ME}]
        evs = [ev("add", ["old"], T0 - 700),                      # before its previous notification: told then
               ev("group", ["g"], T0 - 300), ev("note", ["n"], T0 - 290), ev("add", ["c", "gone"], T0 - 200),
               ev("add", ["x"], T0 - 100, by=OTHER)]               # another agent's
        got = notifplace.find({"id": "", "ts": T0, "page": "main", "by": ME}, evs, BOARD, notes)
        assert got["ids"] == ["g", "n", "c"], "in order, only what is still on the page"
        assert got["area"] == {"x": -50.0, "y": -300.0, "w": 600.0, "h": 750.0}
        assert got["previews"] == ["a/0.png", "a/200.png", "a/400.png"], "a group's own pictures among the previews"

    def test_two_hours_back_at_most_and_moves_only_when_nothing_else(self):
        n = {"id": "", "ts": T0, "page": "main", "by": ME}
        assert notifplace.find(n, [ev("add", ["a"], T0 - 3 * 3600)], BOARD) is None
        got = notifplace.find(n, [ev("move", ["b"], T0 - 60, count=1)], BOARD)
        assert got["ids"] == ["b"]
        assert notifplace.find(n, [ev("move", ["b"], T0 - 60), ev("add", ["c"], T0 - 50)], BOARD)["ids"] == ["c"]

    def test_the_same_author_is_person_and_kind_case_aside_and_an_old_one_by_its_who(self):
        n = {"id": "", "ts": T0, "page": "main", "by": {"person": "p-1", "via": "Claude"}}
        assert notifplace.find(n, [ev("add", ["a"], T0 - 10)], BOARD)["ids"] == ["a"]
        assert notifplace.find(dict(n, by={"person": "p-2", "via": "claude"}), [ev("add", ["a"], T0 - 10)], BOARD) is None
        kind_only = dict(n, by={"via": "claude"})   # a board without profiles
        assert notifplace.find(kind_only, [ev("add", ["a"], T0 - 10, by={"via": "Claude"})], BOARD)["ids"] == ["a"]
        old = {"id": "o", "ts": T0, "page": "main", "who": "Claude"}
        assert notifplace.find(old, [ev("add", ["a"], T0 - 10, agent="Claude")], BOARD)["ids"] == ["a"]

    def test_a_click_also_looks_after_it_up_to_the_next_notification(self):
        """the agent wrote first and placed after (the case of 2026-10-08)"""
        n = {"id": "n1", "t": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(T0)), "page": "main", "by": ME, "ids": [], "previews": []}
        notes = [n, {"id": "n2", "ts": T0 + 300, "page": "main", "by": ME}]
        evs = [ev("add", ["a", "b"], T0 + 70), ev("add", ["c"], T0 + 400)]
        assert notifplace.find(n, evs, BOARD, notes) is None, "posting: only what came before it"
        assert notifplace.place(n, evs, BOARD, notes)["ids"] == ["a", "b"], "not what belongs to the next notification"
        assert notifplace.place(n, [ev("add", ["c"], T0 + 800)], BOARD, [n])["ids"] == ["c"]
        assert notifplace.place(n, [ev("add", ["c"], T0 + 16 * 60)], BOARD, [n]) is None, "15 minutes at most"

    def test_place_keeps_a_notifications_own_things_and_area(self):
        n = {"id": "n", "ts": T0, "page": "main", "by": ME, "ids": ["c"], "previews": ["z.png"]}
        assert notifplace.place(n, [], BOARD) == {"ids": ["c"], "area": {"x": 400.0, "y": 300.0, "w": 100.0, "h": 100.0}, "previews": ["z.png"]}
        area = {"x": 1, "y": 2, "w": 3, "h": 4}
        assert notifplace.place(dict(n, ids=["gone"], area=area), [], BOARD)["area"] == area

    def test_parts_counts_as_the_bell_says(self):
        b = {"items": {"a": pic(0), "b": pic(1), "n": {"type": "note"}, "h": {"type": "text"}, "m": {"type": "model3d"}, "f": {"type": "html"}},
             "groups": {"g": {}}}
        assert notifplace.parts(b, ["a", "b", "n", "h", "m", "f", "g"]) == "2 кадра, 1 заметка, 1 3D-карточка, 1 заголовок, 1 объект, 1 группа"


class TestHyClient:
    def test_ask_takes_the_servers_answer_or_reads_the_events_itself(self, monkeypatch):
        calls = []

        def new(path, body=None):
            calls.append((path, body)); return 200, {"ids": ["a"], "found": True}
        assert notifplace.ask(new, "main", BOARD) == ["a"] and calls[0][1] == {"action": "place", "page": "main"}
        monkeypatch.setenv("HYIMG_AGENT", "Claude")
        now = time.time()

        def old(path, body=None):   # a server without {"action": "place"}: a notification without a title is refused
            if body is not None: return 400, "не записано: no title"
            if path.startswith("/api/events"): return 200, [ev("add", ["c"], now - 30, by={"person": "p", "via": "claude"}, agent="Claude")]
            return 200, {"items": []}
        assert notifplace.ask(old, "main", BOARD) == ["c"]


@pytest.fixture
def board_dir(lib, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "NOTIFS", str(tmp_path / "notifications.json"))
    return lib / "_review" / "boards"


class TestServer:
    def test_notify_without_ids_names_the_authors_things_from_the_events(self, board_dir):
        before = {"revision": 1, "items": {}, "groups": {}}
        after = {"revision": 2, "items": {"a": pic(0), "c": pic(400, 300)}, "groups": {}}
        (board_dir / "main.json").write_text(json.dumps(after))
        events.record("main", before, after, who="ai", agent="Claude", by=ME)
        events.record("main", after, dict(after, items={**after["items"], "x": pic(9000)}), who="ai", agent="Codex", by=OTHER)
        n = server.notify({"title": "Положил референсы", "page": "main", "by": ME})
        assert n["ids"] == ["a", "c"] and n["area"] == {"x": 0.0, "y": 0.0, "w": 500.0, "h": 400.0} and n["previews"] == ["a/0.png", "a/400.png"]
        again = server.notify({"title": "И еще раз", "page": "main", "by": ME})
        assert again["ids"] == [] and "area" not in again, "nothing new since its last one: it stays without a place"

    def test_a_repair_fills_an_old_notification_and_leaves_the_board_alone(self, board_dir):
        b = {"revision": 3, "items": {"a": pic(0), "b": pic(200)}, "groups": {}}
        (board_dir / "main.json").write_text(json.dumps(b)); raw = (board_dir / "main.json").read_bytes()
        t = time.time() - 100
        old = {"id": "old-1", "t": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)), "read": True, "title": "Положил", "text": "", "who": "Claude",
               "page": "main", "ids": [], "previews": [], "by": ME}
        json.dump([old], open(server.NOTIFS, "w"))
        events.append("main", ev("add", ["a", "b"], t + 60, paths=["a/0.png", "a/200.png"], count=2))   # placed after it was written
        got = server.notif_place({"id": "old-1"}, {})
        assert got["found"] and got["ids"] == ["a", "b"] and not got["had"]
        assert json.load(open(server.NOTIFS))[0]["ids"] == [], "the bell's look writes nothing"
        got = server.notif_place({"id": "old-1", "fill": True}, {})
        stored = json.load(open(server.NOTIFS))[0]
        assert stored["ids"] == ["a", "b"] and stored["area"] == {"x": 0.0, "y": 0.0, "w": 300.0, "h": 100.0} and len(stored["previews"]) == 2
        assert (board_dir / "main.json").read_bytes() == raw
        assert server.notif_place({"id": "old-1", "fill": True}, {})["had"]
        with pytest.raises(ValueError): server.notif_place({"id": "nope"}, {})
