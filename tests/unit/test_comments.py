"""Drawings and comment threads on the board (review/comments.py, owner 2026-10-07): stored per page beside the notes, every change an
event of the page, @mentions of people and of a person's agents, the bell for this Mac's person (others' comments, his agents', any
mention of him or of his agents; never what he wrote himself in the app)."""
import json
import uuid

import pytest

import unit_env  # noqa: F401
import comments
import events
import people

OTHER = str(uuid.uuid4())


@pytest.fixture
def root(tmp_path, lib):
    me = people.save_me(tmp_path, "Ann Lee", "green")
    (tmp_path / "people.json").write_text(json.dumps({**people.book(tmp_path), OTHER: {"name": "Bob", "color": "orange", "agents": {"codex": 1}}}))
    return tmp_path, me["id"], str(lib / "_review")


def by(person, via="app"): return {"person": person, "via": via}


def test_a_drawing_is_stored_with_its_anchor_and_every_change_is_an_event(root, lib):
    r, me, state = root
    item = {"kind": "pen", "color": "red", "w": 0.01, "pts": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.5]], "anchor": {"obj": "i1", "kind": "picture", "file": "a/1.png",
            "r": [0, 0, 320, 480]}}
    a = comments.annotate("main", "put", by(me), item)["items"][0]
    assert (lib / "annotations" / f"main__{a['id']}.json").exists() and a["anchor"]["obj"] == "i1" and a["by"] == by(me)
    moved = comments.annotate("main", "put", by(me, "claude"), {**a, "pts": [[0.2, 0.2], [0.4, 0.4], [0.6, 0.5]]})["items"][0]
    assert moved["by"] == by(me) and moved["edited_by"] == by(me, "claude")   # the first author stays
    gone = comments.annotate("main", "delete", by(me), ids=[a["id"]])["removed"]
    assert [g["id"] for g in gone] == [a["id"]] and comments.annotations("main") == []
    back = comments.annotate("main", "put", by(me), {**gone[0], "restore": True})["items"][0]   # undo of the delete keeps its author and time
    assert back["created"] == a["created"] and back["by"] == by(me)
    kinds = [e["kind"] for e in events.read("main")][::-1]
    assert kinds == ["annotate", "annotate-edit", "annotate-remove", "annotate"]
    assert events.read("main")[2]["who"] == "ai" and events.read("main")[2]["agent"] == "Claude" and events.read("main")[0]["who"] == "owner"
    with pytest.raises(ValueError): comments.annotate("main", "put", by(me), {"kind": "rect", "pts": [[0, 0]]})
    with pytest.raises(ValueError): comments.annotate("../x", "put", by(me), item)


def test_threads_mentions_and_their_rules(root, lib):
    r, me, state = root
    t = comments.comment(r, "main", "new", by(me), {"anchor": {"obj": "i2", "kind": "picture"}, "at": [0.9, 0.1],
                                                   "text": "@Claude make the sky darker, @Bob what do you think?"})["thread"]
    assert (lib / "comments" / f"main__{t['id']}.json").exists() and t["objects"] == ["i2"]
    ms = t["messages"][0]["mentions"]
    assert {(m["person"], m.get("agent")) for m in ms} == {(me, "claude"), (OTHER, None)}
    t = comments.comment(r, "main", "reply", by(me, "claude"), {"id": t["id"], "text": "Done, darker by a third"})["thread"]
    t = comments.comment(r, "main", "reply", by(OTHER, "codex"), {"id": t["id"], "text": "@Codex · Bob? no, @Ann Lee looks good"})["thread"]
    assert {(m["person"], m.get("agent")) for m in t["messages"][2]["mentions"]} == {(OTHER, "codex"), (me, None)}
    with pytest.raises(ValueError): comments.comment(r, "main", "edit", by(me), {"id": t["id"], "mid": t["messages"][2]["id"], "text": "x"})   # only one's own
    t = comments.comment(r, "main", "edit", by(me), {"id": t["id"], "mid": t["messages"][1]["id"], "text": "Done (my agent's, so mine)"})["thread"]
    t = comments.comment(r, "main", "resolve", by(me), {"id": t["id"]})["thread"]
    assert t["resolved"]["by"] == by(me)
    assert [x["id"] for x in comments.query(r, "main", open_only=True)] == []
    assert [x["id"] for x in comments.query(r, "main", mention="claude")] == [t["id"]]
    assert comments.query(r, "main", mention="self", agent_kind="codex") == []   # @Codex · Bob is Bob's codex, not this Mac's
    t = comments.comment(r, "main", "reopen", by(me), {"id": t["id"]})["thread"]
    kinds = [e["kind"] for e in events.read("main")][::-1]
    assert kinds == ["comment", "reply", "reply", "comment-edit", "resolve", "reopen"]
    # undo and redo send the thread back as it was; a thread changed since is refused
    before = dict(t)
    t2 = comments.comment(r, "main", "reply", by(me), {"id": t["id"], "text": "one more"})["thread"]
    with pytest.raises(ValueError): comments.comment(r, "main", "put", by(me), {"thread": before, "base": "2000-01-01T00:00:00"})
    back = comments.comment(r, "main", "put", by(me), {"thread": before, "base": t2["updated"]})["thread"]
    assert len(back["messages"]) == 3
    # the first message deleted takes the thread
    res = comments.comment(r, "main", "delete", by(me), {"id": t["id"], "mid": t["messages"][0]["id"]})
    assert res["deleted"] == t["id"] and comments.threads("main") == []


def test_the_bell_for_this_macs_person(root, lib):
    r, me, state = root
    mine = comments.comment(r, "main", "new", by(me), {"at": [10, 20], "text": "@Claude tidy this row"})["thread"]
    assert comments.feed(r, state) == []   # one's own comment never notifies, his mention of his own agent neither
    comments.comment(r, "main", "reply", by(me, "claude"), {"id": mine["id"], "text": "Tidied"})
    theirs = comments.comment(r, "p2", "new", by(OTHER), {"anchor": {"obj": "x1"}, "at": [0.5, 0.5], "text": "@Ann Lee look, and @Claude too"})["thread"]
    comments.comment(r, "p2", "reply", by(OTHER, "codex"), {"id": theirs["id"], "text": "I can do it"})
    f = comments.feed(r, state)
    assert [(n["title"], n["page"]) for n in f] == [("Reply in a thread", "main"), ("Mentioned you", "p2"), ("Reply in a thread", "p2")]
    assert f[0]["who"] == "Claude · Ann Lee" and f[1]["ids"] == ["x1"] and f[0]["area"]["x"] == -190 and not any(n["read"] for n in f)
    assert comments.read(r, state, [f[0]["id"]]) == 2
    assert comments.read(r, state) == 0 and all(n["read"] for n in comments.feed(r, state))
    brief = "\n".join(comments.agent_brief("hy.py", r))
    assert "comments --open --mentions claude" in brief and mine["id"] in brief and theirs["id"] in brief


def test_an_agent_takes_back_its_own_reply_and_the_bell_gets_no_row(root, lib):
    """owner 2026-10-08: an agent's «Round 8, cards 12 and 4» in his thread is noise; the agent deletes it, which rings nothing"""
    r, me, state = root
    t = comments.comment(r, "main", "new", by(me), {"anchor": {"obj": "i3"}, "at": [0.9, 0.1], "text": "the sky darker"})["thread"]
    t = comments.comment(r, "main", "reply", by(me), {"id": t["id"], "text": "and the sea too"})["thread"]
    t = comments.comment(r, "main", "reply", by(me, "claude"), {"id": t["id"], "text": "Round 8, cards 12 and 4"})["thread"]
    t = comments.comment(r, "main", "reply", by(OTHER, "codex"), {"id": t["id"], "text": "seen"})["thread"]
    owner, noise, codex = t["messages"][1]["id"], t["messages"][2]["id"], t["messages"][3]["id"]
    before = {n["id"] for n in comments.feed(r, state)}
    assert len(before) == 2   # the agent's reply rang, Bob's codex too
    for mid in (owner, codex, t["messages"][0]["id"]):   # the owner's words and another kind's: never the agent's to delete
        with pytest.raises(ValueError): comments.comment(r, "main", "delete", by(me, "claude"), {"id": t["id"], "mid": mid})
    with pytest.raises(ValueError): comments.comment(r, "main", "edit", by(me, "claude"), {"id": t["id"], "mid": owner, "text": "x"})
    n_events = len(events.read("main"))
    t = comments.comment(r, "main", "delete", by(me, "claude"), {"id": t["id"], "mid": noise})["thread"]
    assert [m["id"] for m in t["messages"]] == [t["messages"][0]["id"], owner, codex] and not t["resolved"]
    after = comments.feed(r, state)
    assert {n["id"] for n in after} < before and len(after) == 1 and after[0]["text"] == "seen"   # no row added, the agent's row gone
    assert len(events.read("main")) == n_events + 1 and events.read("main")[0]["kind"] == "comment-edit"   # History keeps one line
    assert comments.read(r, state) == 0
    # the person in the app still edits and deletes his own agent's words
    t = comments.comment(r, "main", "reply", by(me, "claude"), {"id": t["id"], "text": "one more"})["thread"]
    t = comments.comment(r, "main", "delete", by(me), {"id": t["id"], "mid": t["messages"][-1]["id"]})["thread"]
    assert len(t["messages"]) == 3


def test_the_rule_for_agents_in_the_skill_and_the_guide(root):
    """owner 2026-10-08: work done because of a comment is announced by notify alone, nothing written in his thread"""
    r, me, state = root
    skill = (unit_env.REVIEW.parent / "skills" / "hyimg-board" / "SKILL.md").read_text(encoding="utf-8")
    brief = "\n".join(comments.agent_brief("hy.py", r))
    for text in (skill, brief):
        assert "ничего не пиши, ни ответа, ни ссылки" in text and "comments delete" in text and "не закрывай" in text
        assert "(а) владелец" in text and "(б) сделать" in text
    assert "не больше 3 открытых" in skill and "не больше 3 открытых" in brief
    assert "ответь в той же ветке" not in skill and "сделай и ответь" not in brief.lower()


def test_hy_comments_delete_names_its_message_and_never_the_first(monkeypatch, capsys):
    import hycomments
    th = {"id": "c123456", "page": "main", "anchor": None, "at": [0, 0], "resolved": None,
          "messages": [{"id": "m0000a", "by": by("p"), "text": "first", "created": "2026-10-08T10:00:00"},
                       {"id": "m0000b", "by": by("p", "claude"), "text": "Round 8", "created": "2026-10-08T10:01:00"}]}
    sent = []

    def api(path, body=None):
        if body is not None:
            sent.append(body)
            return 200, {"thread": {**th, "messages": th["messages"][:1]}}
        if path.startswith("/api/comments"): return 200, {"items": [th]}
        return 200, {}
    hycomments.comments([], "main", api, None, None, {}, ["delete", "c123456", "m0000b"])
    assert sent == [{"op": "delete", "name": "main", "id": "c123456", "mid": "m0000b"}]
    assert "[m0000a]" in capsys.readouterr().out   # the list names every message, for the next delete
    with pytest.raises(SystemExit): hycomments.comments([], "main", api, None, None, {}, ["delete", "c123456", "m0000a"])
    assert len(sent) == 1
