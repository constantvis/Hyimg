"""The bell since a time, for the Mac's banners (review/notifsince.py, native/MacNotifications.swift, owner 2026-10-08): every row of
/api/notifications has its time in seconds, its type and who it is from; ?since= gives only the rows after it, the unread count stays the
board's; a comment is a reply to this Mac's person once he or his agent wrote in the thread, a mention is a mention."""
import http.client
import io
import json
import time
import types
import uuid

import pytest

import unit_env  # noqa: F401
import comments
import notifsince
import people
import server

OTHER = str(uuid.uuid4())


def by(person, via="app"): return {"person": person, "via": via}


@pytest.fixture
def me(tmp_path, monkeypatch, lib):
    m = people.save_me(tmp_path, "Ann Lee", "green")
    (tmp_path / "people.json").write_text(json.dumps({**people.book(tmp_path), OTHER: {"name": "Bob", "color": "orange"}}))
    monkeypatch.setattr(server, "PEOPLE", tmp_path)
    return tmp_path, m["id"], str(lib / "_review")


def get(path):
    """GET through the server's handler, no socket (as tests/unit/test_http_handler.py)"""
    raw = f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:4180\r\nConnection: close\r\n\r\n".encode()
    out = bytearray()
    conn = types.SimpleNamespace(makefile=lambda mode, *a, **k: io.BytesIO(raw) if "r" in mode else io.BytesIO(), sendall=out.extend)
    server.H(conn, ("127.0.0.1", 50000), types.SimpleNamespace(server_port=4180))
    r = http.client.HTTPResponse(types.SimpleNamespace(makefile=lambda *a, **k: io.BytesIO(bytes(out)))); r.begin()
    return r.status, json.loads(r.read())


def test_time_type_and_sender_of_every_row(me):
    r, mid, _ = me
    view = people.view(r)
    rows = notifsince.typed([
        {"id": "1", "t": "2026-10-08 12:00:00", "title": "old news", "who": "claude"},
        {"id": "2", "ts": 1000.0, "title": "news", "who": "x", "by": by(mid, "claude")},
        {"id": "3", "ts": 1001.0, "title": "news", "who": "x", "by": by(OTHER, "codex")},
        {"id": "c:1:2", "ts": 1002.0, "kind": "comment", "type": "mention", "who": "Bob", "by": by(OTHER)},
        {"id": "n:main:a:1", "t": "", "ts": 0, "kind": "note", "who": "Bob", "by": by(OTHER)},
    ], view)
    assert rows[0]["ts"] == time.mktime(time.strptime("2026-10-08 12:00:00", "%Y-%m-%d %H:%M:%S"))   # old news: its t
    assert [n["type"] for n in rows] == ["agent", "agent", "agent", "mention", "note"]
    assert [n["from"] for n in rows] == ["Claude", "Claude", "Codex · Bob", "Bob", "Bob"]   # his own agent by its name alone
    assert rows[4]["ts"] == 0.0
    assert notifsince.since(rows, {"since": ["1000.5"]}) == [rows[0], rows[2], rows[3]]
    assert notifsince.since(rows, {"since": ["nan"]}) == rows and notifsince.since(rows, {"since": ["soon"]}) == rows and notifsince.since(rows, {}) == rows


def test_the_endpoint_since(me):
    now = time.time()
    rows = [{"id": f"n{k}", "t": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 100 + k)), "ts": now - 100 + k, "read": k == 0,
             "title": f"news {k}", "text": "", "who": "claude", "page": "main", "ids": [], "previews": [], "by": {"via": "claude"}} for k in range(3)]
    with open(server.NOTIFS, "w") as fh: json.dump(rows, fh)
    status, d = get(f"/api/notifications?since={now - 99.5:.3f}")
    assert status == 200 and [n["id"] for n in d["items"]] == ["n2", "n1"]   # newest first, n0 is before since
    assert d["unread"] == 2 and abs(d["now"] - time.time()) < 5   # the board's unread count, not the answer's
    assert all(n["type"] == "agent" and n["from"] == "Claude" and "pv" in n for n in d["items"])
    assert [n["id"] for n in get("/api/notifications?limit=60")[1]["items"]] == ["n2", "n1", "n0"]   # without since: as before
    assert get(f"/api/notifications?since={now + 10:.3f}")[1]["items"] == []


def test_a_reply_to_me_a_comment_and_a_mention(me):
    r, mid, state = me
    mine = comments.comment(r, "main", "new", by(mid), {"at": [10, 20], "text": "the sky darker"})["thread"]
    comments.comment(r, "main", "reply", by(OTHER), {"id": mine["id"], "text": "ok"})
    theirs = comments.comment(r, "main", "new", by(OTHER), {"at": [50, 20], "text": "first"})["thread"]
    comments.comment(r, "main", "reply", by(OTHER, "codex"), {"id": theirs["id"], "text": "second, not to her"})
    comments.comment(r, "main", "reply", by(mid, "claude"), {"id": theirs["id"], "text": "her agent wrote here"})
    comments.comment(r, "main", "reply", by(OTHER), {"id": theirs["id"], "text": "so this one is to her"})
    comments.comment(r, "main", "reply", by(OTHER), {"id": theirs["id"], "text": "@Ann Lee look"})
    f = {n["text"]: n for n in comments.feed(r, state)}
    assert f["ok"]["type"] == "reply" and f["first"]["type"] == "comment" and f["second, not to her"]["type"] == "comment"
    assert f["her agent wrote here"]["type"] == "comment"   # her agent's message in a thread she never wrote in: a comment to her
    assert f["so this one is to her"]["type"] == "reply" and f["@Ann Lee look"]["type"] == "mention"
    assert all(isinstance(n["ts"], float) and n["ts"] > 0 for n in f.values())
