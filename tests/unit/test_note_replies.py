"""A reply arrow from a note to another note (owner 2026-10-08: «Почему я не могу привязывать стрелочку от моей заметки к другой заметке,
как ответ на заметку?»): review/notelinks.py's rule (one per note, chains, no circles, overlap and a zone never link two notes), what a
reply is about (the things of the notes up its chain), the note files' reply_to and replies, a note's author kept by every save, the
history event and the bell for the author of the note answered, hy.py's threads."""
import json
import uuid

import pytest

import unit_env  # noqa: F401
import comments
import events
import merge
import notelinks
import people
import server

OTHER = str(uuid.uuid4())


def note(x, y, text="Look", w=100, **kw):
    return {"type": "note", "x": x, "y": y, "w": w, "h": w, "text": text, "to": [], **kw}


def pic(path, x, y, w=100):
    return {"path": path, "x": x, "y": y, "w": w, "ar": 1.0, "crop": None}


def board():
    """an agent's note A on a picture, the owner's reply R to it (lying on A too), a reply to the reply RR with an arrow of its own"""
    return {"items": {"p": pic("a.png", 0, 0), "q": pic("b.png", 3000, 0), "g1": pic("c.png", 6000, 0),
                      "A": note(20, 20, "# Тон теплее?", by={"person": "me", "via": "claude"}),
                      "R": note(60, 60, "Да, на 10 %", to=["A"], by={"person": "me", "via": "app"}),
                      "RR": note(900, 900, "Сделаю", to=["R", "q"]),
                      "G": note(6020, 400, "Inside a group, replying", to=["A"])},
            "groups": {"grp": {"title": "G", "members": ["g1", "G"], "x": 5900, "y": -100, "w": 800, "h": 800}}}


def test_a_reply_is_about_what_the_notes_up_its_chain_are_about():
    L = notelinks.links(board())
    assert L["A"]["items"] == {"p": {"overlap"}} and "reply_to" not in L["A"]
    # overlap of two notes links nothing; the reply gets the answered note's picture by "reply" (and lies on it itself)
    assert L["R"]["items"] == {"p": {"overlap", "reply"}} and L["R"]["reply_to"] == "A"
    # a reply to a reply: its own arrow, and the pictures of both notes up the chain
    assert L["RR"]["items"] == {"q": {"arrow"}, "p": {"reply"}} and L["RR"]["reply_to"] == "R"
    # a reply inside a group frame does not speak for the group: only what it answers
    assert L["G"]["items"] == {"p": {"reply"}} and L["G"]["scope"] == "pictures"
    assert L["A"]["replies"] == ["R", "G"] and L["R"]["replies"] == ["RR"]


def test_one_reply_per_note_and_no_circles():
    it = board()["items"]
    assert notelinks.reply_of(it, "RR") == "R" and notelinks.replies_of(it, "A") == ["R", "G"]
    assert notelinks.circle(it, "A", "RR") and notelinks.circle(it, "A", "A") and not notelinks.circle(it, "RR", "G")
    assert notelinks.set_reply(it, "A", "RR") == "ответ по кругу нельзя: та заметка уже отвечает на эту" and it["A"]["to"] == []
    assert notelinks.set_reply(it, "RR", "G") is None and it["RR"]["to"] == ["q", "G"]   # the old reply arrow goes, the picture stays
    assert notelinks.set_reply(it, "RR", "p") == "это не заметка"
    it["A"]["to"] = ["RR"]   # a circle written by hand: nothing loops
    assert notelinks.links({"items": it, "groups": {}})["A"]["items"]["p"] == {"overlap"}
    assert notelinks.thread({"items": it, "groups": {}, "revision": 9}, "A").count("\n") < 40


def test_the_note_files_carry_the_thread_and_the_author(lib):
    (lib / "a.png").write_bytes(b"pic"); (lib / "b.png").write_bytes(b"pic")
    b = board(); server.save_board("main", {"revision": 0, **b})
    server.sync_notes("main")
    doc = lambda n: json.loads((lib / "notes" / f"main__{n}.json").read_text())
    assert doc("A")["replies"] == ["main/R", "main/G"] and "reply_to" not in doc("A") and doc("A")["by"] == {"person": "me", "via": "claude"}
    assert doc("R")["reply_to"] == "main/A" and doc("R")["replies"] == ["main/RR"]
    assert {o["id"]: o["via"] for o in doc("RR")["objects"]} == {"p": ["reply"], "q": ["arrow"]}
    refs = json.loads((lib / "a.json").read_text())["related_notes"]   # the reply's words count for the picture of the note it answers
    assert {r["note"]: r["via"] for r in refs} == {"main/A": ["overlap"], "main/R": ["overlap", "reply"], "main/RR": ["reply"], "main/G": ["reply"]}


def test_a_notes_author_is_its_first_save_and_never_dropped():
    cur = {"items": {"A": note(0, 0, by={"person": "me", "via": "claude"}), "old": note(0, 0)}}
    new = {"items": {"A": note(0, 0), "old": note(0, 0), "N": note(0, 0)}}
    notelinks.keep_authors(new, cur, {"person": "me", "via": "app"})
    assert new["items"]["A"]["by"]["via"] == "claude" and "by" not in new["items"]["old"] and new["items"]["N"]["by"]["via"] == "app"
    assert merge.notelinks is notelinks


def test_the_history_tells_a_reply_once_with_the_author_answered():
    old = {"items": {"A": note(0, 0, "Q", by={"person": "me", "via": "claude"}), "R": note(0, 0, "")}}
    new = json.loads(json.dumps(old)); new["items"]["R"]["to"] = ["A"]
    assert [e["kind"] for e in events.diff(old, new)] == []   # no words yet: no reply to tell
    newer = json.loads(json.dumps(new)); newer["items"]["R"]["text"] = "Yes"
    ev = [e for e in events.diff(new, newer) if e["kind"] == "note-reply"]
    assert ev == [{"kind": "note-reply", "ids": ["R", "A"], "text": "Yes", "to": "Q", "color": "", "to_by": {"person": "me", "via": "claude"}}]
    moved = json.loads(json.dumps(newer)); moved["items"]["R"]["x"] = 50
    assert not [e for e in events.diff(newer, moved) if e["kind"] == "note-reply"]


@pytest.fixture
def root(tmp_path, lib):
    me = people.save_me(tmp_path, "Ann Lee", "green")
    (tmp_path / "people.json").write_text(json.dumps({**people.book(tmp_path), OTHER: {"name": "Bob", "color": "orange"}}))
    return tmp_path, me["id"], str(lib / "_review")


def test_the_bell_rings_for_the_author_of_the_note_answered(root, lib):
    r, me, state = root
    comments._NR.clear()
    A = {"items": {"A": note(0, 0, "Q", by={"person": me, "via": "app"}), "C": note(0, 0, "Claude's", by={"person": me, "via": "claude"}),
                   "R": note(0, 0, "")}}
    def answer(rid, to, by, text):
        cur = server.load_board("main") if (lib / "_review" / "boards" / "main.json").exists() else A
        new = json.loads(json.dumps(cur)); new["items"].setdefault(rid, note(0, 0, ""))["to"] = [to]; new["items"][rid]["text"] = text
        events.record("main", cur, new, by=by); server.save_board("main", new)
    answer("R1", "A", {"person": OTHER, "via": "app"}, "Bob answers Ann")      # another person: rings
    answer("R2", "A", {"person": me, "via": "app"}, "Ann answers herself")     # herself in the app: never
    answer("R3", "C", {"person": me, "via": "app"}, "Ann answers her Claude")  # her own reply to her agent: never, it is the agent's
    answer("R4", "C", {"person": me, "via": "codex"}, "Codex answers Claude")  # another agent of hers: rings, «Claude's note»
    f = [n for n in comments.feed(r, state) if n["id"].startswith("n:")]
    assert [(n["title"], n["text"], n["who"]) for n in f] == [("Reply to your note", "Bob answers Ann", "Bob"),
                                                            ("Reply to Claude's note", "Codex answers Claude", "Codex · Ann Lee")]
    assert f[0]["ids"] == ["R1", "A"] and f[0]["page"] == "main" and not f[0]["read"]
    assert comments.read(r, state, [f[0]["id"]]) == 1
    brief = "\n".join(comments.agent_brief("hy.py", r))   # the agents' guide: what a reply is, and the owner's replies to them
    assert "## Ответы на заметки" in brief and "[R3]" in brief and "Ann answers her Claude" in brief and "[R4]" not in brief


def test_hy_map_and_find_show_notes_as_threads():
    b = board(); b["revision"] = 3
    assert notelinks.about(b, "R") == " · человек → кадр 1 · ответ на «Тон теплее?» [A]"
    t = notelinks.thread(b, "A")
    assert t == ("\n   ↳ «Да, на 10 %» · человек [R]\n      ↳ «Сделаю» [RR]\n   ↳ «Inside a group, replying» [G]")
    whole = notelinks.about(b, "RR", True)
    assert "↑ ответ на «Да, на 10 %» · человек [R]" in whole and "↑ ответ на «Тон теплее?» · Claude [A]" in whole
    assert "ответ на заметку о нем" in notelinks.tail(b, "q") or "(стрелка) [RR]" in notelinks.tail(b, "q")
    assert "заметка «Сделаю» (ответ на заметку о нем) [RR]" in notelinks.tail(b, "p")
