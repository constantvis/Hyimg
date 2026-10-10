"""Annotations and comments on the board (owner 2026-10-07: «Добавь annotations на доске рядом с notes, чтобы я прямо не заходя в
картинку мог по ней рисовать и добавлять комменты, как в Figma ... возможность тегать участников»).

Both lie on top of the canvas, never in a picture's pixels, and are stored per page beside the notes, one file each:
  annotations/<page>__<id>.json  a drawing: {id, page, kind: pen | arrow | rect | ellipse | text, color, w, pts, text?, size?,
                                 anchor: {obj, kind, file, r: [x, y, w, h]} | null, by, created, edited?, edited_by?}
                                 Anchored, pts, w and size are shares of the object's box (it moves and scales with the object, r is
                                 its box when last drawn, used when the object is gone); free, they are board units.
  comments/<page>__<id>.json     a thread: {id, page, anchor, at: [u, v] or board [x, y], by, created, updated, resolved: {by, t} | null,
                                 objects: [ids], messages: [{id, by, text, mentions: [{person, agent?, label}], created, edited?}],
                                 element?: {key, css, tag, text, page: [x, y], pin?}}: pinned to an element of an HTML page in Dev
                                 Studio, by a click or from its tree (key: the tree's row path «html>body:1>main:0», css: a selector,
                                 page: its point in page px; pin when the point is not on the element's own box: "kids" its contents,
                                 "parent" its nearest ancestor with a box, "edge" the nearest point in sight);
                                 at then is the point's share of the card, the pin's place on the card's still (y at most
                                 0.98: an element further down the page waits at the still's bottom edge, describe says so);
                                 area?: [u, v, w, h] a region of its object in shares (board units when free): the Comment
                                 tool's drag, the library preview's «Comment on area N» on the board;
                                 anchor.part: a layer of an Image Studio frame or an object of a 3D scene, the pin follows it
                                 (clean_part; op place moves at and area after it without an event)
Every drawing and thread also carries what an agent reads without the geometry (annotext.py, refresh() after each change and when
an agent asks): describe (one line in words and numbers), region (shares, pixels), about (a drawing's threads), marks (a thread's
drawings).
A thread has one writer at a time on this Mac (the lock); two Macs answering the same thread within seconds may leave a Dropbox
conflicted copy, which nothing reads. Every change is an event of the page (events.append: comment, reply, comment-edit,
comment-remove, resolve, reopen, annotate, annotate-edit, annotate-remove), so History shows it and Home counts it.

An @mention names a person ({person}) or an agent of a person ({person, agent: kind}; an agent is never a participant of its own,
agents.py). @Claude written on this Mac is this Mac's person's Claude. Mentioning an agent is how the owner gives it a task on the
board: the agent reads `hy.py comments --open --mentions claude` and answers in the thread.

The bell (feed): another person's new comments and replies, an agent's, and every mention of this Mac's person or of his agents;
what this person wrote himself in the app never notifies him. A reply arrow from a note to this person's note or his agent's (events
"note-reply", notelinks.py) by someone else rings it too, "n:<page>:<note>:<time>". Read up to a time, kept on this Mac (reads.json beside the profile).
"""
import json
import os
import re
import threading
import time
import uuid

import agents
import annotext
import events
import people
from config import BOARDS, W

tr = lambda en, ru: en   # server.py sets its own (the app's language)

ANN, COM = os.path.join(W, "annotations"), os.path.join(W, "comments")
KINDS = ("pen", "arrow", "rect", "ellipse", "text")
PART_KINDS = ("layer", "object")
PAGE = re.compile(r"[\w-]{1,80}")
ID = re.compile(r"[a-z0-9]{4,32}")
_LOCK = threading.RLock()
TEXT_MAX, LABEL_MAX, PTS_MAX = 4000, 200, 4000


def _now(): return time.strftime("%Y-%m-%dT%H:%M:%S")


def _id(p): return p + uuid.uuid4().hex[:10]


def _rev(t):
    """the thread's next rev: a count of its writes, exact where updated (whole seconds) is not"""
    try: return int((t or {}).get("rev") or 0) + 1
    except (TypeError, ValueError): return 1


def _page(v):
    if not isinstance(v, str) or not PAGE.fullmatch(v): raise ValueError("bad page")
    return v


def _read(p):
    try:
        with open(p, encoding="utf-8") as fh: d = json.load(fh)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def _write(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh: json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def _file(folder, page, i):
    if not ID.fullmatch(str(i)): raise ValueError("bad id")
    return os.path.join(folder, f"{_page(page)}__{i}.json")


def _all(folder, page=None):
    out = []
    try: names = sorted(os.listdir(folder))
    except OSError: return out
    for n in names:
        if not n.endswith(".json") or "__" not in n or (page and not n.startswith(page + "__")): continue
        d = _read(os.path.join(folder, n))
        if d and d.get("id") and d.get("page"): out.append(d)
    return out


def _num(v, lo=-1e7, hi=1e7):
    v = float(v)
    if v != v or not lo <= v <= hi: raise ValueError("bad number")
    return round(v, 5)


def clean_anchor(a):
    if not isinstance(a, dict) or not a.get("obj"): return None
    obj = str(a["obj"])
    if not re.fullmatch(r"[\w-]{1,60}", obj): raise ValueError("bad object")
    out = {"obj": obj, "kind": str(a.get("kind") or "")[:16]}
    if isinstance(a.get("file"), str) and a["file"]: out["file"] = a["file"][:400]
    r = a.get("r")
    if isinstance(r, (list, tuple)) and len(r) == 4: out["r"] = [_num(x) for x in r]
    part = clean_part(a.get("part"))
    if part: out["part"] = part
    return out


def clean_part(p):
    """the part of a card a thread is tied to inside a Studio (owner 2026-10-09: «3D у нас ... не хватает аннотаций, чтобы можно было так же
    выделить какой-то слой и комментировать его ... Image Studio точно так же, чтобы я мог выбрать и слой»): {kind: layer (an Image Studio
    layer) | object (a 3D scene's object, light or camera), id, name, layer?: the path of a 3D object's layer (scene.js layerPath),
    local: [u, v] shares of the layer's own pixels | [x, y, z] in the 3D object's (or its layer's) own axes, area?: [u, v, w, h] of the
    layer's own pixels}. The pin follows the part; the thread's at and area stay its place on the card's picture (op place)"""
    if not isinstance(p, dict) or p.get("kind") not in PART_KINDS: return None
    pid = str(p.get("id") or "")
    if not re.fullmatch(r"[\w.:~-]{1,80}", pid): return None
    out = {"kind": p["kind"], "id": pid, "name": " ".join(str(p.get("name") or "").split())[:80]}
    if p["kind"] == "object" and isinstance(p.get("layer"), str) and p["layer"]: out["layer"] = p["layer"][:400]
    loc = p.get("local")
    if isinstance(loc, (list, tuple)) and len(loc) == (2 if p["kind"] == "layer" else 3): out["local"] = [_num(v) for v in loc]
    ar = p.get("area")
    if p["kind"] == "layer" and isinstance(ar, (list, tuple)) and len(ar) == 4: out["area"] = [_num(v) for v in ar]
    return out


def _stamp_event(page, kind, by, ids=(), **more):
    e = {"kind": kind, "ids": [i for i in ids if i][:20], "who": people.who_of(by), "by": by, **{k: v for k, v in more.items() if v not in (None, "")}}
    a = people.agent_of(by)
    if a: e["agent"] = a
    try: events.append(page, e)
    except OSError: pass


# ---- drawings ----------------------------------------------------------------------------------------------------------------------
def clean_annotation(d, old=None):
    if not isinstance(d, dict): raise ValueError("no drawing")
    kind = d.get("kind")
    if kind not in KINDS: raise ValueError("bad kind")
    pts = d.get("pts")
    if not isinstance(pts, list) or not pts or len(pts) > PTS_MAX: raise ValueError("bad points")
    pts = [[_num(p[0]), _num(p[1])] for p in pts]
    if kind in ("arrow", "rect", "ellipse") and len(pts) != 2: raise ValueError("two points")
    anchor = clean_anchor(d.get("anchor"))
    out = {"id": str(d.get("id") or ""), "page": _page(d.get("page")), "kind": kind, "color": d.get("color") if d.get("color") in people.COLORS else "red",
           "w": _num(d.get("w", 3), 0, 1e4), "pts": pts, "anchor": anchor}
    if kind == "text":
        out["text"] = " ".join(str(d.get("text") or "").split())[:LABEL_MAX]
        if not out["text"]: raise ValueError("empty text")
        out["size"] = _num(d.get("size", 16), 0, 1e5)
    return out


def annotations(page):
    return _all(ANN, _page(page))


def annotate(page, op, by, item=None, ids=(), base=None):
    """op: put (add or replace one drawing; restore: keeps its first author), delete (ids). Returns {items, removed}"""
    page, item = _page(page), item or {}
    with _LOCK:
        if op == "put":
            d = clean_annotation({**item, "page": page})
            if not d["id"]: d["id"] = _id("a")
            p = _file(ANN, page, d["id"])
            old = _read(p)
            if old:
                d.update(by=old.get("by"), created=old.get("created"), edited=_now(), edited_by=by)
            else:
                keep = item.get("restore") and isinstance(item.get("by"), dict)
                d.update(by=item["by"] if keep else by, created=item.get("created") if keep and item.get("created") else _now())
            _write(p, d)
            _stamp_event(page, "annotate-edit" if old else "annotate", by, [(d.get("anchor") or {}).get("obj")], shape=d["kind"], color=d["color"],
                         text=d.get("text", ""), annot=d["id"])
            return {"items": [d], "removed": []}
        if op == "delete":
            gone = []
            for i in ids or []:
                p = _file(ANN, page, i)
                old = _read(p)
                if old:
                    os.remove(p); gone.append(old)
            if gone:
                objs = list(dict.fromkeys((g.get("anchor") or {}).get("obj") for g in gone))
                _stamp_event(page, "annotate-remove", by, objs, count=len(gone), color=gone[0].get("color"), shape=gone[0].get("kind"))
            return {"items": [], "removed": gone}
    raise ValueError("unknown op")


# ---- comments ---------------------------------------------------------------------------------------------------------------------
def _candidates(root):
    """what an @ can name, longest first: another person's agents («Codex · Bob»), people (by this Mac's name and their own), this Mac's
    person's agents («@Claude»)"""
    v = people.view(root)
    me = (v.get("me") or {}).get("id")
    out = []
    for pid, p in v["people"].items():
        if p.get("hidden"): continue
        for nm in {p.get("name"), p.get("own")} - {None, ""}:
            out.append((nm, {"person": pid}))
            for k in (p.get("agents") or {}):
                out.append((f"{agents.LABEL.get(k, k)} · {nm}", {"person": pid, "agent": k}))
    if me:
        for k in agents.CATALOG[:-1]: out.append((agents.LABEL[k], {"person": me, "agent": k}))
    return sorted(out, key=lambda c: -len(c[0]))


def mentions(root, text, given=None):
    """the mentions of a message: those the page picked (autocomplete) whose @label is still in the text, and any @name of the address
    book or @<agent> written by hand (hy.py, an agent's reply)"""
    out, seen = [], set()
    low = (text or "").lower()

    def add(m, label):
        k = (m["person"], m.get("agent", ""))
        if k in seen: return
        seen.add(k); out.append({**m, "label": label[:60]})
    for m in given or []:
        if not isinstance(m, dict) or not people._is_id(m.get("person")): continue
        label = str(m.get("label") or "")
        if label and "@" + label.lower() not in low: continue
        mm = {"person": m["person"]}
        if m.get("agent"): mm["agent"] = agents.kind(m["agent"]) or "agent"
        add(mm, label)
    cands = _candidates(root)
    for at in re.finditer(r"@", text or ""):
        rest = low[at.end():]
        for label, m in cands:
            if rest.startswith(label.lower()) and (len(rest) == len(label) or not rest[len(label)].isalnum()):
                add(m, label); break
    return out


def clean_element(e):
    """an element of an HTML card's page a comment is pinned to (Dev mode, owner 2026-10-07): where the editor finds it again"""
    if not isinstance(e, dict) or not (e.get("key") or e.get("css")): return None
    out = {"key": str(e.get("key") or "")[:400], "css": str(e.get("css") or "")[:300], "tag": str(e.get("tag") or "")[:20],
           "text": " ".join(str(e.get("text") or "").split())[:80]}
    if isinstance(e.get("page"), (list, tuple)) and len(e["page"]) == 2: out["page"] = [_num(v) for v in e["page"]]
    if e.get("pin") in annotext.PINS: out["pin"] = e["pin"]
    return out


def clean_area(v, anchored):
    """a comment's region: [u, v, w, h] in shares of its object (anchored) or board units (free); None for a plain pin"""
    if not isinstance(v, (list, tuple)) or len(v) != 4: return None
    a = [_num(x) for x in v]
    if anchored:
        u0, v0 = max(0.0, min(1.0, a[0])), max(0.0, min(1.0, a[1]))
        a = [u0, v0, max(0.0, min(1.0 - u0, a[2])), max(0.0, min(1.0 - v0, a[3]))]
    if a[2] <= 0 or a[3] <= 0: return None
    return [round(x, 5) for x in a]


def clean_text(t):
    t = str(t or "").replace("\r\n", "\n").strip()[:TEXT_MAX]
    if not t: raise ValueError("empty text")
    return t


def _thread_path(page, tid): return _file(COM, page, tid)


def threads(page=None):
    return _all(COM, _page(page) if page else None)


def _at(v):
    if not isinstance(v, (list, tuple)) or len(v) != 2: raise ValueError("bad point")
    return [_num(v[0]), _num(v[1])]


def _own(root, by, who):
    """an author may change his message: the same person in the app (his agents' messages are his too); an agent only its own kind's
    (2026-10-08: an agent takes back its own reply in the owner's thread, never his words)"""
    me = (people.me(root) or {}).get("id")
    if not (bool(me) and (who or {}).get("person") == me and (by or {}).get("person") == me): return False
    via = (by or {}).get("via", "app")
    return via == "app" or (who or {}).get("via", "app") == via


def comment(root, page, op, by, d):
    """op: new {anchor, at, text, mentions}, reply {id, text, mentions}, edit {id, mid, text, mentions}, delete {id, mid} (the first message
    takes the thread), resolve {id}, reopen {id}, move {id, anchor, at}, put {thread, base} (undo and redo: the thread as it was; base, the
    updated it must still have, refuses a thread someone changed since; base_rev, its rev, when the client sends one), place {id, at, area?}
    (a Studio's thread on a layer or a 3D object: its pin's place on the card's picture after the part moved; no event, updated and rev stay).
    Every other write counts the thread's rev up by one: updated is in whole seconds, and two edits in the same second looked the same to
    undo's check, which then put back a thread over the other edit (П4 audit 2026-10-10). Returns {thread} or {deleted, thread}"""
    page = _page(page)
    with _LOCK:
        if op == "new":
            tid, now = _id("c"), _now()
            anchor = clean_anchor(d.get("anchor"))
            text = clean_text(d.get("text"))
            t = {"id": tid, "page": page, "anchor": anchor, "at": _at(d.get("at")), "by": by, "created": now, "updated": now, "rev": 1, "resolved": None,
                 "objects": [anchor["obj"]] if anchor else [],
                 "messages": [{"id": _id("m"), "by": by, "text": text, "mentions": mentions(root, text, d.get("mentions")), "created": now}]}
            if anchor and clean_element(d.get("element")): t["element"] = clean_element(d.get("element"))
            if clean_area(d.get("area"), bool(anchor)): t["area"] = clean_area(d.get("area"), bool(anchor))
            _write(_thread_path(page, tid), t)
            _stamp_event(page, "comment", by, t["objects"], text=text[:140], thread=tid)
            return {"thread": t}
        tid = str(d.get("id") or (d.get("thread") or {}).get("id") or "")
        p = _thread_path(page, tid)
        t = _read(p)
        if op == "put":
            new, base, base_rev = d.get("thread"), d.get("base"), d.get("base_rev")
            if base_rev is not None and t and t.get("rev") is not None: changed = t.get("rev") != base_rev
            else: changed = base is not None and (t or {}).get("updated") != base
            if changed or (base_rev is not None and not t): raise ValueError(tr("changed since", "изменено с тех пор"))
            if not new:
                if t: os.remove(p); _stamp_event(page, "comment-remove", by, t.get("objects") or [], text=t["messages"][0]["text"][:140], thread=tid)
                return {"deleted": tid, "thread": t}
            new = clean_thread(root, page, new)
            new["updated"], new["rev"] = _now(), _rev(t)
            _write(p, new)
            was, now_r = bool((t or {}).get("resolved")), bool(new.get("resolved"))
            kind = "comment" if not t else "resolve" if now_r and not was else "reopen" if was and not now_r else "comment-edit"
            _stamp_event(page, kind, by, new.get("objects") or [], text=new["messages"][0]["text"][:140], thread=tid)
            return {"thread": new}
        if not t: raise ValueError(tr("no such annotation", "нет такой аннотации"))
        if op == "place":   # the part moved in its Studio: the pin's place on the card follows, quietly (no event, no new updated)
            if not (t.get("anchor") or {}).get("part"): raise ValueError("not a Studio's annotation")
            t["at"] = _at(d.get("at"))
            if "area" in d:
                ar = clean_area(d.get("area"), True)
                if ar: t["area"] = ar
                else: t.pop("area", None)
            _write(p, t)
            return {"thread": t}
        now, kind, text = _now(), "", ""
        if op == "reply":
            text = clean_text(d.get("text"))
            t["messages"].append({"id": _id("m"), "by": by, "text": text, "mentions": mentions(root, text, d.get("mentions")), "created": now})
            if t.get("resolved") and d.get("reopen", True): t["resolved"] = None
            kind = "reply"
        elif op in ("edit", "delete"):
            m = next((m for m in t["messages"] if m["id"] == d.get("mid")), None)
            if not m: raise ValueError(tr("no such message", "нет такого сообщения"))
            if not _own(root, by, m.get("by")): raise ValueError(tr("only your own", "только свое"))
            if op == "edit":
                m["text"] = text = clean_text(d.get("text")); m["mentions"] = mentions(root, text, d.get("mentions")); m["edited"] = now
                kind = "comment-edit"
            elif m is t["messages"][0]:
                os.remove(p)
                _stamp_event(page, "comment-remove", by, t.get("objects") or [], text=m["text"][:140], thread=tid)
                return {"deleted": tid, "thread": t}
            else:
                t["messages"].remove(m); kind, text = "comment-edit", m["text"]
        elif op in ("resolve", "reopen"):
            t["resolved"] = {"by": by, "t": now} if op == "resolve" else None
            kind, text = op, t["messages"][0]["text"]
        elif op == "move":
            t["anchor"] = clean_anchor(d.get("anchor")); t["at"] = _at(d.get("at"))
            t["objects"] = [t["anchor"]["obj"]] if t["anchor"] else []
            if clean_element(d.get("element")) and t["anchor"]: t["element"] = clean_element(d.get("element"))
            else: t.pop("element", None)   # a pin moved by hand leaves its element
            if clean_area(d.get("area"), bool(t["anchor"])): t["area"] = clean_area(d.get("area"), bool(t["anchor"]))
            else: t.pop("area", None)
            kind, text = "comment-edit", t["messages"][0]["text"]
        else:
            raise ValueError("unknown op")
        t["updated"], t["rev"] = now, _rev(t)
        _write(p, t)
        _stamp_event(page, kind, by, t.get("objects") or [], text=text[:140], thread=tid)
        return {"thread": t}


def clean_thread(root, page, t):
    """a whole thread sent back by undo or redo: the same shape as one this module writes"""
    if not isinstance(t, dict) or not ID.fullmatch(str(t.get("id") or "")): raise ValueError("bad thread")
    msgs = []
    for m in t.get("messages") or []:
        if not isinstance(m, dict) or not ID.fullmatch(str(m.get("id") or "")): continue
        mm = {"id": m["id"], "by": m.get("by") if isinstance(m.get("by"), dict) else {}, "text": clean_text(m.get("text")),
              "mentions": mentions(root, m.get("text"), m.get("mentions")), "created": str(m.get("created") or _now())}
        if m.get("edited"): mm["edited"] = str(m["edited"])
        msgs.append(mm)
    if not msgs: raise ValueError("a thread with no message")
    anchor = clean_anchor(t.get("anchor"))
    res = t.get("resolved")
    el = clean_element(t.get("element")) if anchor else None
    ar = clean_area(t.get("area"), bool(anchor))
    return {**({"element": el} if el else {}), **({"area": ar} if ar else {}), "id": t["id"], "page": page, "anchor": anchor, "at": _at(t.get("at")),
            "by": t.get("by") if isinstance(t.get("by"), dict) else msgs[0]["by"],
            "created": str(t.get("created") or msgs[0]["created"]), "updated": str(t.get("updated") or _now()),
            "resolved": {"by": res.get("by"), "t": str(res.get("t") or "")} if isinstance(res, dict) else None,
            "objects": [anchor["obj"]] if anchor else [], "messages": msgs}


def query(root, page=None, open_only=False, resolved_only=False, mention=None, agent_kind=None):
    """threads for hy.py and the agents' guide. mention: "me" (this Mac's person himself), a kind (his agent of that kind), "self" (the
    agent asking: agent_kind)"""
    me = (people.me(root) or {}).get("id")
    want = None
    if mention == "self": mention = agent_kind or "agent"
    if mention == "me": want = (me, "")
    elif mention: want = (me, agents.kind(mention) or "agent")
    out = []
    for t in threads(page):
        if open_only and t.get("resolved"): continue
        if resolved_only and not t.get("resolved"): continue
        if want and not any((m.get("person"), m.get("agent", "")) == want for msg in t["messages"] for m in msg.get("mentions") or []): continue
        out.append(t)
    return sorted(out, key=lambda t: t.get("updated", ""), reverse=True)


# ---- in words, for agents (annotext.py) -------------------------------------------------------------------------------------------
real = lambda rel: os.path.join(W, rel)   # server.py sets its own (mounted folders)
_SIZES = {}


def size_of(rel):
    """a picture's pixel size from its header, cached by modification time; None for anything unreadable"""
    try:
        full = real(rel); mt = os.path.getmtime(full)
        if _SIZES.get(full, (None,))[0] != mt:
            from PIL import Image
            with Image.open(full) as im: _SIZES[full] = (mt, im.size)
        return _SIZES[full][1]
    except Exception:
        return None


def _board(page):
    try:
        with open(os.path.join(BOARDS, page + ".json"), encoding="utf-8") as fh: return json.load(fh)
    except (OSError, ValueError):
        return {"items": {}}


def library_marks(b):
    """{item id: [marks]}: the library preview's marks (feedback.notes in a picture's json) of the pictures on a board"""
    out = {}
    for oid, it in (b.get("items") or {}).items():
        if not isinstance(it, dict) or it.get("type") or not it.get("path"): continue
        try:
            full = real(it["path"]); sp = (os.path.splitext(full)[0] if annotext.kind_of(it) == "picture" else full) + ".json"
            with open(sp, encoding="utf-8") as fh: meta = json.load(fh)
            notes = (meta.get("feedback") or {}).get("notes") if isinstance(meta, dict) else None
        except (OSError, ValueError, AttributeError):
            continue
        if notes: out[oid] = annotext.library_marks(it["path"], notes, it, oid, size_of)
    return out


def refresh(page, root):
    """describe, region, about and marks of every drawing and thread of a page, written into their files where they changed"""
    page = _page(page)
    with _LOCK:
        b, ppl = _board(page), people.view(root)["people"]
        anns, ths = annotations(page), threads(page)
        marks = []
        for a in anns:
            d = annotext.describe(a, b, ppl, size_of, ths)
            new = {**a, "describe": d["text"], "about": d["about"], **{k: d[k] for k in ("region", "to") if d.get(k)}}
            for k in ("region", "to"):
                if not d.get(k): new.pop(k, None)
            if new != a:
                try: _write(_file(ANN, page, a["id"]), new)
                except (OSError, ValueError): pass
            a.clear(); a.update(new); marks.append({"id": a["id"], "about": d["about"]})
        for t in ths:
            d = annotext.describe_thread(t, b, ppl, size_of, marks)
            new = {**t, "describe": d["text"], "marks": d["marks"], **({"region": d["region"]} if d.get("region") else {})}
            if not d.get("region"): new.pop("region", None)
            if new != t:
                try: _write(_thread_path(page, t["id"]), new)
                except (OSError, ValueError): pass
            t.clear(); t.update(new)
        return {"items": anns, "threads": ths, "library": library_marks(b)}


def pages_with_marks():
    names = set()
    for d in (ANN, COM):
        try: names |= {n.split("__", 1)[0] for n in os.listdir(d) if "__" in n and n.endswith(".json")}
        except OSError: pass
    return sorted(n for n in names if PAGE.fullmatch(n))


# ---- the bell -------------------------------------------------------------------------------------------------------------------
def _reads(root):
    return _read(os.path.join(root, "reads.json")) or {}


def read(root, state, ids=None):
    """the bell was opened (ids None: everything up to now) or some were clicked; returns how many comment notifications stay unread"""
    with _LOCK:
        r = _reads(root); e = r.get(state) if isinstance(r.get(state), dict) else {}
        if ids is None: e = {"ts": time.time(), "ids": []}
        else: e = {"ts": e.get("ts", 0), "ids": list(dict.fromkeys((e.get("ids") or []) + [i for i in ids if str(i).startswith(("c:", "n:"))]))[-500:]}
        r[state] = e
        try: _write(os.path.join(root, "reads.json"), r)
        except OSError: pass
    return sum(not n["read"] for n in feed(root, state))


def _when(iso):
    try: return time.mktime(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError): return 0.0


def feed(root, state, limit=100):
    """the bell's comment notifications for this Mac's person, as /api/notifications items, oldest first"""
    m = people.me(root)
    if not m: return []
    me = m["id"]
    r = _reads(root).get(state) if isinstance(_reads(root).get(state), dict) else {}
    seen_ts, seen_ids = r.get("ts", 0), set(r.get("ids") or [])
    names = people.view(root)["people"]
    out = []
    for t in threads():
        first = t["messages"][0]["id"] if t.get("messages") else ""
        wrote = False   # this person or his agent wrote in the thread before this message: it is a reply to him (the Mac's banners, notifsince.py)
        for msg in t.get("messages") or []:
            by = msg.get("by") or {}
            was, wrote = wrote, wrote or by.get("person") == me
            mine_app = by.get("person") == me and by.get("via", "app") == "app"
            if mine_app: continue
            hit = [x for x in msg.get("mentions") or [] if x.get("person") == me]
            other = by.get("person") != me
            if not hit and not other and by.get("via", "app") == "app": continue
            who = _who(by, names)
            if hit:
                ag = "" if any(not x.get("agent") for x in hit) else hit[0]["agent"]
                title = tr("Mentioned {}", "Упоминание: {}").format(agents.label(ag)) if ag else tr("Mentioned you", "Вас упомянули")
            else:
                title = tr("New annotation", "Новая аннотация") if msg["id"] == first else tr("Reply in a thread", "Ответ в обсуждении")
            nid = f"c:{t['id']}:{msg['id']}"
            ts = _when(msg.get("created"))
            n = {"id": nid, "t": (msg.get("created") or "").replace("T", " ")[:19], "read": ts <= seen_ts or nid in seen_ids, "title": title,
                 "text": msg.get("text", "")[:300], "who": who, "by": by, "page": t["page"], "ids": list(t.get("objects") or []),
                 "kind": "comment", "thread": t["id"], "ts": ts, "type": "mention" if hit else "reply" if was and msg["id"] != first else "comment"}
            if not t.get("anchor") and t.get("at"): n["area"] = {"x": t["at"][0] - 200, "y": t["at"][1] - 150, "w": 400, "h": 300}
            out.append(n)
    for e in note_replies():   # a reply arrow to this person's note or his agent's, by someone else (notelinks.py, 2026-10-08)
        by, to = e.get("by") or {}, e.get("to_by") or {}
        if to.get("person") != me or by == to or (by.get("person") == me and by.get("via", "app") == "app"): continue
        nid = f"n:{e['page']}:{e['ids'][0]}:{int(e.get('ts', 0))}"
        ag = agents.label(to.get("via")) if to.get("via", "app") != "app" else ""
        out.append({"id": nid, "t": e.get("t", ""), "read": e.get("ts", 0) <= seen_ts or nid in seen_ids, "kind": "note", "type": "note", "ts": e.get("ts") or 0, "by": by, "who": _who(by, names),
                    "title": tr("Reply to {}'s note", "Ответ на заметку {}").format(ag) if ag else tr("Reply to your note", "Ответ на вашу заметку"),
                    "text": e.get("text", "")[:300], "page": e["page"], "ids": list(e.get("ids") or [])})
    out.sort(key=lambda n: n["t"])
    return out[-limit:]


def _who(by, names):
    p = names.get(by.get("person")) or {}
    return (f"{agents.label(by.get('via'))} · " if by.get("via", "app") != "app" else "") + (p.get("name") or tr("Someone", "Кто-то"))


_NR = {}


def note_replies():
    """every page's note-reply events (events.py: a note's arrow to another note), oldest first, each with its page; read again when
    the page's log changed"""
    d, out = os.path.join(BOARDS, "_events"), []
    try: logs = sorted(f for f in os.listdir(d) if f.endswith(".jsonl"))
    except OSError: return out
    for f in logs:
        p = os.path.join(d, f)
        try: mt = os.path.getmtime(p)
        except OSError: continue
        if _NR.get(p, (None,))[0] != mt:
            L = []
            try:
                with open(p, encoding="utf-8") as fh:
                    for line in fh:
                        if '"note-reply"' not in line: continue
                        try: L.append({**json.loads(line), "page": f[:-6]})
                        except ValueError: pass
            except OSError: pass
            _NR[p] = (mt, L)
        out += _NR[p][1]
    return out


# ---- for agents: /agent and hy.py ------------------------------------------------------------------------------------------------
def agent_brief(hy, root):
    """the lines /agent shows: what a mention is, the commands, and the open threads that wait for an agent"""
    me = people.me(root) or {}
    L = ["## Комментарии и упоминания на доске", "",
         "Владелец рисует поверх доски и оставляет комментарии, как в Figma. Упоминание агента в комментарии (`@Claude`, `@Codex`)"
         " это задача тебе от владельца. Найди свои: `" + hy + " comments --open --mentions claude` (свой вид: claude, codex, gemini, kimi,"
         " opencode), прочитай ветку целиком и сделай.", "",
         "Сделал по комментарию: в ветке ничего не пиши, ни ответа, ни ссылки. Объявление работы только одно, уведомление `" + hy + " notify`"
         " (без --ids оно само назовет, что ты положил): колокольчик покажет, где ответ"
         " (владелец 2026-10-08: строки «Раунд 8, карточки 12 и 4» в его ветках это шум)."
         " Отвечай в ветке (`" + hy + " comments reply <id> \"…\"`) только если (а) владелец там задал вопрос, которому нужен ответ словами,"
         " или (б) сделать нельзя и нужно одно уточнение именно про это место. Новая ветка (`" + hy + " comments add <REF> \"текст\"`)"
         " только для вопроса про конкретное место на вещи, которую ты разложил, если там ответить быстрее, чем в чате; не больше 3 открытых"
         " твоих, общие вопросы в чат. Ветки владельца не закрывай (resolve), их закрывает он. Свой лишний ответ убери:"
         " `" + hy + " comments delete <id> <id сообщения>`, чужие сообщения сервер тебе удалить не даст. Подписывать себя не нужно:"
         " сервер сам видит, кто пишет.", "",
         "Пометки владельца (область комментария, овал, стрелка, обводка, надпись) читай словами, а не по картинке доски: `" + hy + " annotations`"
         " (по объектам, где именно в процентах и пикселях кадра, к какому комментарию), они же под каждой вещью в `find` и `map`."
         " Посмотреть именно отмеченное место: `" + hy + " look --comment <id>` или `--ann <id>` дает png с этим куском оригинала.", ""]
    wait = [t for t in query(root, open_only=True) if any(x.get("agent") and x.get("person") == me.get("id") for msg in t["messages"]
                                                            for x in msg.get("mentions") or [])]
    for t in wait[:10]:
        ag = sorted({x["agent"] for msg in t["messages"] for x in msg.get("mentions") or [] if x.get("agent")})
        el = f", элемент `{(t.get('element') or {}).get('css') or (t.get('element') or {}).get('key')}`" if t.get("element") else ""
        L.append(f"- `{t['id']}` страница `{t['page']}`{el}, для {', '.join(agents.LABEL.get(a, a) for a in ag)}: {t['messages'][-1]['text'][:120]!r}")
    if wait: L.append("")
    L += ["## Ответы на заметки", "",
          "Стрелка от заметки к другой заметке это ответ на нее, как ветка комментариев. Стрелка от заметки владельца к твоей заметке"
          " значит, что владелец отвечает на эту заметку. Прежде чем делать, прочитай всю ветку: `" + hy + " find <id заметки>` печатает,"
          " на что она отвечает (↑) и ответы под ней (↳) с авторами, `" + hy + " map <название>` показывает заметки ветками."
          " Слова ответа относятся к тем же кадрам и карточкам, что и заметка, на которую он отвечает. Ответить самому:"
          " `" + hy + " do 'note \"текст\" x=… y=…; link \"текст\" <id заметки>'`, одна такая стрелка у заметки, по кругу нельзя.", ""]
    mine = [e for e in note_replies() if (e.get("to_by") or {}).get("person") == me.get("id") and (e.get("to_by") or {}).get("via", "app") != "app"
            and (e.get("by") or {}).get("via", "app") == "app"][-8:]
    for e in reversed(mine):
        L.append(f"- страница `{e['page']}`, ответ владельца [{e['ids'][0]}] на заметку {agents.label(e['to_by'].get('via'))} «{e.get('to', '')[:60]}»"
                 f" [{e['ids'][1]}]: {e.get('text', '')[:120]!r}")
    if mine: L.append("")
    return L


# ---- HTTP ---------------------------------------------------------------------------------------------------------------------------
def http(handler, method, root, state, q=None):
    """GET /api/annotations?name=, GET /api/comments?name=&open=1&resolved=1&mentions=me|<kind>|self&all=1,
    POST /api/annotations {op: put | delete, name, item | ids}, POST /api/comments {op, name, ...} (comment())"""
    send = lambda code, body: handler.send(code, json.dumps(body, ensure_ascii=False).encode(), "application/json")
    path, q = handler.path.split("?", 1)[0], q or {}
    one = lambda k, d="": (q.get(k) or [d])[0]
    try:
        if method == "GET":
            if path == "/api/annotations":
                if one("describe") != "1": return send(200, {"items": annotations(one("name", "main"))})
                if one("all") != "1": return send(200, {"page": one("name", "main"), **refresh(one("name", "main"), root)})
                return send(200, {"pages": {pg: refresh(pg, root) for pg in sorted(set(pages_with_marks()) | {one("name", "main")})}})
            if path == "/api/comments":
                kind = (agents.detect(handler) or agents.kind(handler.headers.get("X-Hyimg-Agent") or "")) if one("mentions") == "self" else ""
                page = None if one("all") == "1" else one("name", "main")
                return send(200, {"items": query(root, page, one("open") == "1", one("resolved") == "1", one("mentions") or None, kind)})
            return send(404, {"error": "not found"})
        n = int(handler.headers.get("Content-Length", 0) or 0)
        req = json.loads(handler.rfile.read(n) or b"{}")
        by = people.stamp(root, state, handler)
        page = req.get("name") or req.get("page") or "main"
        if path == "/api/annotations": res = annotate(page, req.get("op"), by, req.get("item"), req.get("ids") or [])
        elif path == "/api/comments": res = comment(root, page, req.get("op"), by, req)
        else: return send(404, {"error": "not found"})
        try:   # the words for agents, fresh after every change; the answer carries them
            done = refresh(page, root); fresh = {x["id"]: x for x in done["items"] + done["threads"]}
            for k in ("items", "removed"): res[k] = [fresh.get(x["id"], x) for x in res.get(k) or []] if k in res else res.get(k)
            if res.get("thread") and not res.get("deleted"): res["thread"] = fresh.get(res["thread"]["id"], res["thread"])
        except Exception: pass
        return send(200, {k: v for k, v in res.items() if v is not None})
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as ex:
        return send(400, {"error": str(ex)[:200]})
