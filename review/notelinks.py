"""What a sticky note on the board is linked to, for every kind of thing (owner 2026-10-07: «Что 3D, что картинка, неважно что, это
объект. Любой объект должен функционировать как все остальные объекты по логике нашей системы»). Until then only pictures counted: a
note with an arrow to an HTML card fell back to its group and named the one picture in it.

One rule for the server (note files, pictures' related_notes, the board's index by item id), hy.py (map, find) and the page
(ui/notelink.js does the same in canvas.html). A note touches a thing when
  overlap  the note card overlaps it
  zone     the note's dashed zone (the card grown by its reach margins) holds its centre
  arrow    an arrow from the note points at it, or at a group (then every member of that group)
  group    the note has no zone, no arrow and overlaps nothing, and sits inside a group frame: it speaks for every member of the
           smallest frame holding its centre
A thing is a picture, a video or PDF of the library, or any plugin's card (an HTML frame or page, a 3D scene, an image frame, a card
of a plugin this file does not know). A heading and a timeline only by an arrow: a card lying on a heading is not about it. A note is
never a thing of another note.

A reply (owner 2026-10-08: «привязывать стрелочку от моей заметки к другой заметке, как ответ на заметку»): an arrow from a note to
another note, in the same "to" as its other arrows, answers that note. Overlap and a zone never link a note to a note, only an arrow
does. One such arrow per note (a new one replaces it), a note may have many replies, chains are allowed, a circle is refused. A reply
speaks about what the note it answers (and that one's own parent, up the chain) is linked to: those things get the reply too, by
"reply"; its own overlap, zone and arrows to things count as for any note, and a reply never falls back to its group. The note files
carry "reply_to" and "replies" ("<board>/<id>"), the board item its author "by" (people.py), kept by merge.py on every save.

Where a link is kept: a picture's json gets "related_notes" (server.py sync_notes); a card points at a file it does not own (the user's
.html, a scene the 3D studio rewrites whole), so its links stay on the board's side: the note file lists every thing by id
("objects") and boards/<page>.notes-index.json maps item id -> notes. Nothing here reads or writes files."""

import sys

ARROW_ONLY = {"text", "timeline"}
KIND = {"htmlframe": "html", "html": "html", "model3d": "3d", "imgframe": "frame", "text": "heading", "timeline": "timeline"}
KIND_RU = {"picture": "кадр", "video": "видео", "pdf": "PDF", "html": "HTML", "3d": "3D", "frame": "фрейм", "heading": "заголовок",
           "timeline": "таймлайн", "card": "карточка"}
VIDEO = (".mp4", ".mov", ".m4v", ".webm")
FILE_KEYS = ("path", "src", "scene", "doc")
CELL = 2048   # things by cells of the board: a note is tested only against the things near it (520 notes x 3600 frames, 2026-10-02)


def target(it):
    """an arrow may point at it: anything on the board but a note"""
    return isinstance(it, dict) and it.get("type") != "note" and bool(it.get("type") or it.get("path"))


def caught(it):
    """overlap, a zone and a group's note catch it: a picture or a card, not a heading or a timeline"""
    return target(it) and it.get("type") not in ARROW_ONLY


def card(it):
    """a plugin's card, whichever plugin (an image frame is listed by hy.py img_frames with its pictures)"""
    return bool(it.get("type")) and it["type"] not in ("note", "text", "timeline", "imgframe")


def kind(it):
    t = it.get("type")
    if t: return KIND.get(t, "card")
    p = (it.get("path") or "").lower()
    return "video" if p.endswith(VIDEO) else "pdf" if p.endswith(".pdf") else "picture"


def file_of(it):
    return next((it[k] for k in FILE_KEYS if isinstance(it.get(k), str) and it[k]), "")


def rect(it):
    """the box of an item in board units, as canvas.html rectOf / itemH"""
    x, y, w = float(it["x"]), float(it["y"]), float(it["w"])
    t = it.get("type")
    if not t:
        c = it.get("crop") or [0, 0, 1, 1]
        return (x, y, w, w * ((c[3] - c[1]) / float(it.get("ar") or 1)) / (c[2] - c[0]))
    h = float(it.get("h") or float(it.get("fs") or 16) * 1.2)
    return (x, y, w, max(w, h) if t == "note" else h)   # a note is at least a square on the canvas (min-height = width)


def _hit(a, b): return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


def _rect_or_none(it):
    try: return rect(it)
    except (KeyError, TypeError, ValueError, ZeroDivisionError): return None


def links(b):
    """{note id: {text, color, scope, group?, items: {item id: set(via)}}} for one board dict; notes without text are left out"""
    items, groups = b.get("items") or {}, b.get("groups") or {}
    rects = {i: r for i, v in items.items() if caught(v) and (r := _rect_or_none(v))}
    cells = {}
    for i, r in rects.items():
        for cx in range(int(r[0] // CELL), int((r[0] + r[2]) // CELL) + 1):
            for cy in range(int(r[1] // CELL), int((r[1] + r[3]) // CELL) + 1): cells.setdefault((cx, cy), []).append(i)

    def near(a):
        seen = []
        for cx in range(int(a[0] // CELL), int((a[0] + a[2]) // CELL) + 1):
            for cy in range(int(a[1] // CELL), int((a[1] + a[3]) // CELL) + 1): seen += cells.get((cx, cy), ())
        return dict.fromkeys(seen)

    def members(g): return [m for m in g.get("members", []) if caught(items.get(m))]
    out = {}
    for nid, n in items.items():
        if not isinstance(n, dict) or n.get("type") != "note" or not (n.get("text") or "").strip(): continue
        nr = _rect_or_none(n)
        if not nr: continue
        z = n.get("reach")
        zr = (nr[0] - z["l"], nr[1] - z["t"], nr[2] + z["l"] + z["r"], nr[3] + z["t"] + z["b"]) if z else None
        box = (min(nr[0], zr[0]), min(nr[1], zr[1]), max(nr[0] + nr[2], zr[0] + zr[2]) - min(nr[0], zr[0]),
               max(nr[1] + nr[3], zr[1] + zr[3]) - min(nr[1], zr[1])) if zr else nr
        via, grp, scope = {}, None, "pictures"
        for i in near(box):
            r = rects[i]
            if _hit(nr, r): via.setdefault(i, set()).add("overlap")
            # in a zone by its centre (owner 2026-09-30): a roomy zone must not catch the edges of the next row
            if zr and zr[0] <= r[0] + r[2] / 2 <= zr[0] + zr[2] and zr[1] <= r[1] + r[3] / 2 <= zr[1] + zr[3]: via.setdefault(i, set()).add("zone")
        for t in n.get("to") or []:
            if t != nid and target(items.get(t)): via.setdefault(t, set()).add("arrow")
            elif t in groups:
                grp = grp or (groups[t].get("title") or "").strip()
                for m in members(groups[t]): via.setdefault(m, set()).add("arrow")
        if not via and not z and not (n.get("to") or []):   # a note inside a group frame, linked to nothing: the whole group
            cx, cy = nr[0] + nr[2] / 2, nr[1] + nr[3] / 2
            hit = sorted((g["w"] * g["h"], gid) for gid, g in groups.items() if g["x"] <= cx <= g["x"] + g["w"] and g["y"] <= cy <= g["y"] + g["h"])
            if hit:
                g = groups[hit[0][1]]; grp = (g.get("title") or "").strip(); scope = "group"
                for m in members(g): via.setdefault(m, set()).add("group")
        e = {"text": n["text"].strip(), "color": n.get("color") or "yellow", "scope": scope, "items": via}
        if grp: e["group"] = grp
        out[nid] = e
    own = {nid: list(e["items"]) for nid, e in out.items()}
    for nid, e in out.items():   # a reply: what the notes up its chain are about, by "reply"
        p, seen = reply_of(items, nid), {nid}
        if p: e["reply_to"] = p
        while p and p not in seen:
            seen.add(p)
            for i in own.get(p, ()): e["items"].setdefault(i, set()).add("reply")
            p = reply_of(items, p)
    for nid in sorted(out, key=lambda k: (items[k].get("y", 0), items[k].get("x", 0))):
        if out[nid].get("reply_to") in out: out[out[nid]["reply_to"]].setdefault("replies", []).append(nid)
    return out


# ---- replies: an arrow from a note to another note (owner 2026-10-08) ----
def is_note(it): return isinstance(it, dict) and it.get("type") == "note"


def reply_of(items, nid):
    """the note this note answers: its arrow that ends on another note (the first, there is one at most)"""
    return next((t for t in (items.get(nid) or {}).get("to") or [] if t != nid and is_note(items.get(t))), None)


def replies_of(items, nid):
    """the notes that answer this one, top to bottom"""
    R = [k for k, it in items.items() if is_note(it) and reply_of(items, k) == nid]
    return sorted(R, key=lambda k: (items[k].get("y", 0), items[k].get("x", 0)))


def circle(items, nid, t):
    """True when nid answering t would close a circle: t is nid or answers it, directly or down a chain"""
    p, seen = t, set()
    while p and p not in seen:
        if p == nid: return True
        seen.add(p); p = reply_of(items, p)
    return False


def set_reply(items, nid, t):
    """nid answers t (its earlier reply arrow goes): None, or why not in words (hy.py link)"""
    if not is_note(items.get(t)): return "это не заметка"
    if circle(items, nid, t): return "ответ по кругу нельзя: та заметка уже отвечает на эту"
    n = items[nid]; n["to"] = [x for x in n.get("to") or [] if not is_note(items.get(x))] + [t]
    return None


def keep_authors(new, cur, by):
    """a note's author: who saved it first (by, people.py); a save that does not carry it (a page loaded before) keeps the file's"""
    old = (cur or {}).get("items") or {}
    for i, it in ((new or {}).get("items") or {}).items():
        if not is_note(it) or it.get("by"): continue
        if (old.get(i) or {}).get("by"): it["by"] = old[i]["by"]
        elif i not in old and by: it["by"] = by


def index(b):
    """links() plus what the files need: pics {path: set(via)} (a picture that sits twice is one entry) and objects, every thing by id"""
    items, out = b.get("items") or {}, links(b)
    for nid, e in out.items():
        e["pics"], e["objects"] = {}, []
        if items[nid].get("by"): e["by"] = items[nid]["by"]
        for i, v in sorted(e["items"].items()):
            it = items[i]
            if kind(it) in ("picture", "video", "pdf") and it.get("path"): e["pics"].setdefault(it["path"], set()).update(v)
            o = {"id": i, "kind": kind(it), "via": sorted(v)}
            if file_of(it): o["file"] = file_of(it)
            if it.get("type") and (it.get("name") or it.get("text") or it.get("label")): o["name"] = first_line(it.get("name") or it.get("text") or it.get("label"))
            e["objects"].append(o)
    return out


def public(idx):
    """an index() as JSON for /api/notes: sets as sorted lists"""
    return {k: {**{x: y for x, y in v.items() if x != "items"}, "pics": {p: sorted(s) for p, s in v["pics"].items()}} for k, v in idx.items()}


def by_item(idx, board):
    """{item id: [{"note": "<board>/<id>", "via": [...]}]}: the reverse lookup by id, for every kind"""
    out = {}
    for nid, e in sorted(idx.items()):
        for i, v in e["items"].items(): out.setdefault(i, []).append({"note": f"{board}/{nid}", "via": sorted(v)})
    return out


def first_line(t): return (t or "").strip().split("\n")[0].lstrip("#").strip()


# ---- for hy.py: notes beside what map and find print
VIA_RU = {"overlap": "лежит на нем", "zone": "в зоне", "arrow": "стрелка", "group": "через группу", "reply": "ответ на заметку о нем"}
_CACHE, _PEOPLE = {}, {}


def _of(b):
    k = (id(b), b.get("revision"), len(b.get("items") or {}))
    if _CACHE.get("k") != k: _CACHE.update(k=k, links=links(b))
    return _CACHE["links"]


def tail(b, item_id):
    """the lines under a thing in find: every note linked to it, how, and its id"""
    out = ""
    for nid, e in _of(b).items():
        v = e["items"].get(item_id)
        if v: out += f"\n   заметка «{first_line(e['text'])[:50]}» ({', '.join(VIA_RU.get(x, x) for x in sorted(v))}) [{nid}]" + also(b, nid, item_id)
    try:   # hy.py: the drawings and comments on it, in words (hycomments.py asks the server; elsewhere nothing)
        import hycomments; out += hycomments.tail(b, item_id)
    except ImportError: pass
    return out


def also(b, nid, item_id, most=6):
    """the rest a note is about, under a thing it is linked to (owner 2026-10-08: one note with arrows to a screenshot and a page; who
    reads one of them must learn the note speaks of the other too): «она же про: HTML 3d-icons.html [dwkimd3z], кадр a.png [i1]»"""
    items, rest = b.get("items") or {}, [i for i in _of(b)[nid]["items"] if i != item_id]
    if not rest: return ""
    def name(i):
        f = file_of(items[i]) or items[i].get("text") or ""
        return f"{KIND_RU.get(kind(items[i]), 'вещь')} {first_line(f).rsplit('/', 1)[-1][:40]} [{i}]"
    more = f", еще {len(rest) - most}" if len(rest) > most else ""
    return "\n      она же про: " + ", ".join(name(i) for i in rest[:most]) + more


def marks(b, area=None):
    """after map: the things in the area that carry drawings or comments, each with them (hy.py; hycomments.py asks the server)"""
    try: import hycomments
    except ImportError: return ""
    return hycomments.marks(b, area)


def about(b, nid, whole=False):
    """after a note in map: its author, what it is linked to, counted by kind («→ кадр 3, HTML 1»), or that it speaks for a group,
    and the note it answers; whole (find): its thread instead, the notes up the chain and the replies under it"""
    e, items = _of(b).get(nid), b.get("items") or {}
    w = who((items.get(nid) or {}).get("by")); out = f" · {w}" if w else ""
    if e and e["items"]:
        n = {}
        for i in e["items"]: n[kind(items[i])] = n.get(kind(items[i]), 0) + 1
        out += (" → вся группа: " if e["scope"] == "group" else " → ") + ", ".join(f"{KIND_RU[k]} {c}" for k, c in sorted(n.items()))
    p = reply_of(items, nid)
    if whole: return out + thread(b, nid, True)
    return out + (f" · ответ на «{first_line(items[p].get('text'))[:40]}» [{p}]" if p else "")


def who(by):
    """a note's author in words, as hy.py comments names them: «Ann», «Claude · Ann» (the names asked from the server once)"""
    if not by: return ""
    if "p" not in _PEOPLE:
        api = getattr(sys.modules.get("__main__"), "api", None)
        try: _PEOPLE["p"] = (api("/api/profile")[1] or {}).get("people") or {} if api else {}
        except BaseException: _PEOPLE["p"] = {}
    p, via = _PEOPLE["p"].get(by.get("person")) or {}, by.get("via", "app")
    name = p.get("name") or ("" if via != "app" else "человек")
    if via == "app": return name
    return " · ".join(x for x in (via.capitalize() if via != "opencode" else "OpenCode", name) if x)


def thread(b, nid, up=False, depth=1):
    """the lines of a note's thread for map and find: up=True first the notes it answers, up the chain; then its replies, indented"""
    items, out = b.get("items") or {}, ""

    def line(k, mark, d):
        w = who(items[k].get("by"))
        return f"\n{'   ' * d}{mark} «{first_line(items[k].get('text'))[:60]}»" + (f" · {w}" if w else "") + f" [{k}]"
    p, seen = reply_of(items, nid) if up else None, {nid}
    while p and p not in seen: out += line(p, "↑ ответ на", 1); seen.add(p); p = reply_of(items, p)
    tree = _tree(b)
    for r in tree.get(nid, ()):
        if depth < 12: out += line(r, "↳", depth) + thread(b, r, False, depth + 1)
    return out


def _tree(b):
    """{note id: its replies, top to bottom} for one board, cached as links are"""
    items = b.get("items") or {}
    k = (id(b), b.get("revision"), len(items))
    if _CACHE.get("tk") != k:
        T = {}
        for r in sorted((r for r, it in items.items() if is_note(it)), key=lambda r: (items[r].get("y", 0), items[r].get("x", 0))):
            p = reply_of(items, r)
            if p: T.setdefault(p, []).append(r)
        _CACHE.update(tk=k, tree=T)
    return _CACHE["tree"]
