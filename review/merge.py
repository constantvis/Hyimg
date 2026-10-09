"""Saves of a board merged object by object (owner 2026-10-08: «Две правки одной доски с двух Маков могут перезаписать друг друга.
Сделать слияние по объектам? — да»). Two windows, an agent writing through hy.py while the owner works, two Macs over one Dropbox
folder: every writer starts from a version of the board and sends the whole board back. Before 2026-10-08 a save from an old version
was refused (409), the page merged on its side and an agent retried. Now the server merges.

Every version the server writes carries a "vid" (random), its "parent" (the vid it replaced), "edited" (when its newest change was
made, epoch seconds) and "by" (who wrote it, people.py). A save names its base by the revision and vid it was loaded with. When the
file changed since (disk != base), the save is a three-way merge of base, ours (the save) and theirs (the file):

- items, groups, grids and links (connectors.py) by id, the page's own fields (anything beside these and removed) one by one, "removed" by
  path; a connector whose end is gone from the merged page goes with it;
- changed on one side only: that side; added on either side: kept; deleted on one side and untouched on the other: deleted;
  deleted on one side and changed on the other: the changed one stays (nothing disappears silently), with a conflict record;
- changed on both sides: field by field. x and y are one field (position), w and h another (size), any other key its own
  (text, color, crop, reach, ...). A group's members merge as sets: each side's additions and removals both apply; a grid's members
  so too, in ours' order with theirs' new ones after, and a grid whose members came from both sides is laid out again (grids.py);
- the same field changed on both sides to different values: the newer change wins by its time (ours: the page's last edit,
  ?edited= of the save, else the time of the save; theirs: the file's "edited"); the losing value is kept in a conflict record.

A conflict record is an event of the page (kind "merge", with every field, both values and both authors) and a version in History
with the losing side's whole board («2 changes to the same thing merged; kept Claude · Ann's position»), so it can be restored.

The base comes from this Mac's cache: every version the server writes or hands out is kept, gzipped, in
~/Library/Caches/Hyimg/<board>/bases/<page>/<vid>.json.gz (the last KEEP per page, outside Dropbox), and the last few in memory;
then History's snapshots with that revision. Without a base (a cleared cache) nothing is deleted: one-sided things are kept,
different values are conflicts.

Dropbox's conflicted copies of a page ("main (Ann's conflicted copy 2026-10-08).json") are merged into the page the same way, their
common ancestor found through the parents, and then moved to boards/_history/<page>/dropbox/ (History also gets the copy as a
version, the event "dropbox" says so). Comments, drawings and notes' files are not board saves: a page save never writes them
(comments.py, server.sync_notes).
"""
import gzip
import hashlib
import json
import os
import re
import secrets
import threading
import time
from collections import OrderedDict

import agents
import connectors
import events
import grids
import history
import notelinks
import people
from config import BOARDS, CACHE_ROOT, PROJECT_ID, W

tr = lambda en, ru: en   # server.py sets its own (the app's language)
PEOPLE = ""              # server.py: the folder of profile.json and the address book, for the names in the labels
KEEP, MEM = 40, 6        # versions kept per page on disk and in memory
META = ("revision", "saved", "vid", "parent", "edited", "by", "schema")
MAPS = ("items", "groups", "grids", "links", "removed")
FIELD = {"x": "position", "y": "position", "w": "size", "h": "size"}
COPY = re.compile(r"^([A-Za-z0-9_-]{1,40}) \(.*conflicted copy.*\)\.json$", re.I)
NONE = object()          # a key one side does not have
_GUARD, _MEMO = threading.Lock(), {}


# ---- the merge ---------------------------------------------------------------------------------------------------------------------
class Merge:
    """merge3 below. nobase: the base is unknown, so a difference is a conflict and nothing one-sided is deleted"""
    def __init__(self, nobase, t_ours, t_theirs, by_ours, by_theirs):
        self.nobase, self.ours_newer, self.conflicts = nobase, t_ours >= t_theirs, []
        self.side = {"ours": (t_ours, by_ours or {}), "theirs": (t_theirs, by_theirs or {})}

    def record(self, kind, oid, field, keep, kept, lost, about):
        other = "theirs" if keep == "ours" else "ours"
        e = {"kind": kind, "id": oid, "field": field, "kept": keep, "value": _short(kept), "lost": _short(lost),
             "kept_by": self.side[keep][1], "lost_by": self.side[other][1], "kept_t": self.side[keep][0], "lost_t": self.side[other][0]}
        self.conflicts.append({**e, **{k: v for k, v in (about or {}).items() if v}})

    def value(self, kind, oid, field, b, o, t, about=None):
        """one field (a tuple of keys' values, NONE for a missing key)"""
        if o == t: return o
        if self.nobase and (_gone(o) or _gone(t)): return t if _gone(o) else o
        if not self.nobase and o == b: return t
        if not self.nobase and t == b: return o
        keep = "ours" if self.ours_newer else "theirs"
        self.record(kind, oid, field, keep, _val(field, o if keep == "ours" else t), _val(field, t if keep == "ours" else o), about)
        return o if keep == "ours" else t

    def thing(self, kind, oid, b, o, t):
        """one item or group: whole when only one side changed it, else field by field"""
        about = _about(t if o is NONE else o)
        if o is NONE or t is NONE:
            here, keep = (t, "theirs") if o is NONE else (o, "ours")
            if here is NONE or b is NONE or self.nobase: return here   # added on one side (or no base: kept)
            if here == b: return NONE                                  # deleted there, untouched here
            self.record(kind, oid, "deleted", keep, here, None, about)  # deleted there, changed here: it stays
            return here
        if o == t: return o
        if b is NONE: b = {}
        if not self.nobase and o == b: return t
        if not self.nobase and t == b: return o
        out = {}
        for field, keys in _fields(o, t, b):
            ov, tv, bv = (tuple(d.get(k, NONE) for k in keys) for d in (o, t, b))
            v = (members(bv[0], ov[0], tv[0]),) if field == "members" and kind in ("group", "grid") else self.value(kind, oid, field, bv, ov, tv, about)
            out.update({k: x for k, x in zip(keys, v) if x is not NONE})
        return out

    def map(self, kind, b, o, t):
        out = {}
        b, o, t = b or {}, o or {}, t or {}
        for k in order(b, o, t):
            bv, ov, tv = b.get(k, NONE), o.get(k, NONE), t.get(k, NONE)
            v = self.thing(kind, k, bv, ov, tv) if kind != "removed" else self.plain(bv, ov, tv)
            if v is not NONE: out[k] = v
        return out

    def plain(self, b, o, t):
        """a value merged whole, no record (the archive marks of "removed")"""
        if o == t: return o
        if o == b or (self.nobase and o is NONE): return t
        if t == b or (self.nobase and t is NONE): return o
        return o if self.ours_newer else t


def merge3(base, ours, theirs, t_ours, t_theirs, by_ours=None, by_theirs=None):
    """(the merged board, the conflict records). base None: unknown, nothing is deleted"""
    m = Merge(base is None, t_ours, t_theirs, by_ours, by_theirs)
    b = base or {}
    out = {k: v for k, v in theirs.items() if k not in MAPS}
    for k in order({}, ours, theirs):
        if k in META or k in MAPS: continue
        v = m.value("page", "", k, (b.get(k, NONE),), (ours.get(k, NONE),), (theirs.get(k, NONE),))[0]
        if v is NONE: out.pop(k, None)
        else: out[k] = v
    for k in MAPS:
        if k in ("grids", "links") and not any(x.get(k) for x in (b, ours, theirs)): continue   # a page that never had one gets no empty map
        out[k] = m.map({"items": "item", "groups": "group", "grids": "grid", "links": "link"}.get(k, k), b.get(k), ours.get(k), theirs.get(k))
    if "grids" in out: grids.merged(out, ours, theirs)   # a grid edited on both sides: one grid again, in the merged order
    connectors.prune(out)   # an arrow to a thing the other side deleted goes with it
    return out, m.conflicts


def members(b, o, t):
    """a group's members as sets: what either side added, minus what either side took out; ours' order first"""
    b, o, t = [x if isinstance(x, list) else [] for x in (b, o, t)]
    gone = (set(b) - set(o)) | (set(b) - set(t))
    return list(dict.fromkeys(m for m in o + t if m not in gone))


def order(b, o, t):
    """the keys in draw order (Order ›): ours when ours reordered what all three had, else theirs; the other side's new ones after"""
    both = [k for k in b if k in o and k in t]
    first, second = (o, t) if [k for k in o if k in b and k in t] != both else (t, o)
    return list(dict.fromkeys([*first, *second]))


def _fields(*ds):
    out = OrderedDict()
    for d in ds:
        for k in d:
            keys = out.setdefault(FIELD.get(k, k), [])
            if k not in keys: keys.append(k)
    return [(f, tuple(sorted(ks, key="xywh".find) if f in ("position", "size") else ks)) for f, ks in out.items()]


def _gone(v):
    return v is NONE or (isinstance(v, tuple) and all(x is NONE for x in v))


def _val(field, v):
    """a field's value as a record shows it: {x, y} for position, {w, h} for size, the value itself otherwise"""
    if not isinstance(v, tuple): return None if v is NONE else v
    if len(v) == 1: return None if v[0] is NONE else v[0]
    keys = ("x", "y") if field == "position" else ("w", "h")
    return {k: x for k, x in zip(keys, v) if x is not NONE}


def _short(v):
    s = json.dumps(v, ensure_ascii=False, default=str)
    return v if len(s) <= 2000 else s[:2000] + "…"


def _about(it):
    if not isinstance(it, dict): return {}
    return {"path": it.get("path"), "text": " ".join(str(it.get("text") or it.get("title") or it.get("label") or "").split())[:80]}


# ---- versions: the cache of bases ---------------------------------------------------------------------------------------------------
def key_of(b):
    """a version's name: its vid with its revision (an older Hyimg rewrites the file and keeps the vid it read), r<revision> before vids"""
    b = b or {}
    return f"{b['vid']}~{b.get('revision', 0)}" if b.get("vid") else f"r{b.get('revision', 0)}"


def _file(page, key):
    d = os.path.join(CACHE_ROOT, PROJECT_ID or hashlib.sha1(W.encode()).hexdigest()[:16], "bases", page)
    return d, os.path.join(d, re.sub(r"[^A-Za-z0-9_-]", "_", key) + ".json.gz")


def seen(page, b):
    """remember a version this server wrote or handed out, as a base for later saves; returns b"""
    k = key_of(b)
    with _GUARD:
        mem = _MEMO.setdefault(page, OrderedDict())
        if k in mem: mem.move_to_end(k); return b
        mem[k] = text = json.dumps(b, ensure_ascii=False)
        while len(mem) > MEM: mem.popitem(last=False)
    d, p = _file(page, k)
    try:
        if not os.path.exists(p):
            os.makedirs(d, exist_ok=True)
            with gzip.open(p + ".tmp", "wt", encoding="utf-8", compresslevel=1) as fh: fh.write(text)
            os.replace(p + ".tmp", p)
            old = sorted((e for e in os.scandir(d) if e.name.endswith(".json.gz")), key=lambda e: e.stat().st_mtime)
            for e in old[:-KEEP]: os.remove(e.path)
    except OSError:
        pass
    return b


def recall(page, key, revision=None):
    """a version by its key: memory, this Mac's cache, then History's snapshot with that revision"""
    with _GUARD: text = _MEMO.get(page, {}).get(key)
    if text: return json.loads(text)
    try:
        with gzip.open(_file(page, key)[1], "rt", encoding="utf-8") as fh: return json.load(fh)
    except (OSError, ValueError, EOFError):
        pass
    for e in reversed(history.entries(page) if revision is not None else []):
        if e.get("revision") != revision: continue
        try: b = history.load(page, e["id"])
        except (OSError, ValueError, PermissionError): continue
        if key_of(b) == key: return b
    return None


def chain(page, b, depth=40):
    """the keys of b and of its parents, as far as this Mac knows them"""
    out = []
    while b is not None and len(out) < depth:
        out.append(key_of(b))
        b = recall(page, b["parent"]) if b.get("parent") else None
    return out


def when(b):
    if isinstance(b.get("edited"), (int, float)): return float(b["edited"])
    try: return time.mktime(time.strptime(b.get("saved", ""), "%Y-%m-%d %H:%M:%S"))
    except (ValueError, TypeError): return 0.0


def stamp(page, b, cur, by=None, t=None):
    """b becomes the version after cur: revision, time, a new vid, its parent; remembered as a base"""
    b["revision"] = max(int(cur.get("revision", 0) or 0), int(b.get("revision", 0) or 0)) + 1
    b["saved"] = time.strftime("%Y-%m-%d %H:%M:%S"); b["vid"] = secrets.token_hex(6)
    if cur.get("vid") or cur.get("revision"): b["parent"] = key_of(cur)
    else: b.pop("parent", None)
    b["edited"] = round(t or time.time(), 3)
    if by: b["by"] = by
    else: b.pop("by", None)
    return seen(page, b)


def _path(page):
    return os.path.join(BOARDS, page + ".json")


def _load(page):
    try:
        with open(_path(page), encoding="utf-8") as fh: return json.load(fh)
    except FileNotFoundError:
        return {"schema": 1, "revision": 0, "items": {}, "groups": {}}


def _write(page, b):
    os.makedirs(BOARDS, exist_ok=True)
    p = _path(page); tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh: json.dump(b, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return os.stat(p).st_mtime_ns


def content(b):
    return {k: v for k, v in (b or {}).items() if k not in META}


# ---- a save --------------------------------------------------------------------------------------------------------------------------
def commit(page, new, by=None, edited=None):
    """write a page's save, merged with the file when it changed since the save's base; the caller holds the server's lock.
    Returns (200, answer): revision, saved, mtime, vid; a merged save also "merged" {from, conflicts, base} and "board" (what was written)"""
    now = time.time()
    try: t_new = min(now, float(edited)) if edited else now
    except (TypeError, ValueError): t_new = now
    cur = seen(page, _load(page))
    same = new.get("revision", 0) == cur.get("revision", 0) and (not new.get("vid") or new.get("vid") == cur.get("vid"))
    info = posted = None
    if not same:
        base = recall(page, key_of(new), new.get("revision", 0))
        t_cur = when(cur)
        out, conflicts = merge3(base, new, cur, t_new, t_cur, by, cur.get("by"))
        came = base is None or content(cur) != content(base)
        info = {"from": authors(page, cur, key_of(new)) if came else [], "conflicts": conflicts, "base": base is not None}
        posted, new, t_new = new, out, max(t_new, t_cur)
    notelinks.keep_authors(new, cur, by)   # a note's author (its first save), never dropped by a page that loaded before it was known
    stamp(page, new, cur, by, t_new)
    mtime = _write(page, new)
    res = {"revision": new["revision"], "saved": new["saved"], "mtime": mtime, "vid": new["vid"]}
    if info is not None:
        res.update(merged=info, board=new)
        if info["conflicts"]: log_conflicts(page, info["conflicts"], {"ours": posted, "theirs": cur}, by, new["revision"])
    return 200, res


def authors(page, cur, stop, depth=10):
    """who wrote the versions between the save's base and the file: the other side's people and agents"""
    out, b = [], cur
    for _ in range(depth):
        if b is None or key_of(b) == stop: break
        if b.get("by") and b["by"] not in out: out.append(b["by"])
        b = recall(page, b["parent"]) if b.get("parent") else None
    return out


def who_text(by):
    by = by or {}
    try: names = people.view(PEOPLE)["people"] if PEOPLE else {}
    except Exception: names = {}
    name = (names.get(by.get("person")) or {}).get("name", "")
    via = agents.label(by.get("via")) if by.get("via") not in (None, "", "app") else ""
    return " · ".join(x for x in (via, name) if x) or tr("someone", "кто-то")


# what was kept, in words: {who} is the author of the kept change
KEPT = {"position": ("{who}'s position", "оставлено положение от {who}"), "size": ("{who}'s size", "оставлен размер от {who}"),
        "text": ("{who}'s text", "оставлен текст от {who}"), "color": ("{who}'s colour", "оставлен цвет от {who}"),
        "title": ("{who}'s title", "оставлено название от {who}"), "deleted": ("{who}'s edit of a deleted thing", "оставлена правка {who}, удаление отменено")}


def label(conflicts):
    c = conflicts[0]; who = who_text(c["kept_by"])
    en, ru = KEPT.get(c["field"], ("{who}'s " + c["field"], "оставлено «" + c["field"] + "» от {who}"))
    en, ru = en.format(who=who), ru.format(who=who)
    if len(conflicts) == 1: return tr(f"2 changes to the same thing merged; kept {en}", f"2 правки одного и того же слиты: {ru}")
    return tr(f"{len(conflicts)} things changed on both sides merged; kept {en} and more", f"Слиты правки с двух сторон ({len(conflicts)}): {ru} и другое")


def log_conflicts(page, conflicts, boards, by, rev, kind="merge", extra=None):
    """the event and the History versions of the sides that lost something"""
    ids = list(dict.fromkeys(c["id"] for c in conflicts if c["id"]))
    paths = list(dict.fromkeys(c["path"] for c in conflicts if c.get("path")))[:events.SAMPLE]
    text = label(conflicts)
    events.append(page, {"kind": kind, "ids": ids[:200], "count": len(conflicts), "conflicts": conflicts[:50], "paths": paths,   # the words: ui/merge.js
                         "who": people.who_of(by), "rev": rev, **({"by": by} if by else {}), **(extra or {})})
    for side in ("ours", "theirs"):
        lost = [c for c in conflicts if c["kept"] != side]
        if lost and boards.get(side):
            history.snapshot(page, "auto", text, boards[side], lost[0]["lost_by"] or None, extra={"conflicts": len(lost), "merge": side})


# ---- Dropbox's conflicted copies ---------------------------------------------------------------------------------------------------
_SWEPT = {"t": 0.0}


def sweep(lock, after=None, every=5.0, settle=2.0):
    """merge every "<page> (… conflicted copy …).json" in boards/ into its page, at most every few seconds; after(page) then
    (the server's note files). Returns the pages that changed."""
    if time.time() - _SWEPT["t"] < every: return []
    _SWEPT["t"] = time.time()
    try: names = sorted(os.listdir(BOARDS))
    except OSError: return []
    done = []
    for f in names:
        m = COPY.match(f)
        if not m: continue
        try:
            if time.time() - os.path.getmtime(os.path.join(BOARDS, f)) < settle: continue   # Dropbox may still be writing it
            with lock: changed = merge_copy(m.group(1), f)
            if changed:
                done.append(m.group(1))
                if after: after(m.group(1))
        except Exception as ex:   # one broken copy never stops the server or the others
            print(f"merge: {f}: {ex}", flush=True)
    return done


def merge_copy(page, name):
    """one conflicted copy into its page; the copy goes to boards/_history/<page>/dropbox/. True when the page changed"""
    src = os.path.join(BOARDS, name)
    try:
        with open(src, encoding="utf-8") as fh: copy = json.load(fh)
    except ValueError:
        copy = None
    cur = seen(page, _load(page)); changed = False
    if isinstance(copy, dict) and isinstance(copy.get("items"), dict):
        mine = set(chain(page, cur))
        base_key = next((k for k in chain(page, copy) if k in mine), None)
        base = recall(page, base_key) if base_key else None
        out, conflicts = merge3(base, cur, copy, when(cur), when(copy), cur.get("by"), copy.get("by"))
        what = tr(f"Dropbox conflicted copy merged: {name}", f"Слита конфликтная копия Dropbox: {name}")
        history.snapshot(page, "auto", what, copy, copy.get("by"), extra={"dropbox": name})
        if content(out) != content(cur):
            stamp(page, out, cur, cur.get("by"), max(when(cur), when(copy)))
            _write(page, out); changed = True
            events.record(page, cur, out, "auto", what, by=copy.get("by"))
        extra = {"file": name, "from": [copy["by"]] if copy.get("by") else []}
        rev = out.get("revision") if changed else cur.get("revision")
        if conflicts: log_conflicts(page, conflicts, {"ours": cur, "theirs": copy}, copy.get("by"), rev, "dropbox", extra)
        else: events.append(page, {"kind": "dropbox", "ids": [], "count": 0, "who": "auto", "rev": rev, **extra})
    dest = os.path.join(BOARDS, "_history", page, "dropbox"); os.makedirs(dest, exist_ok=True)
    stem, n, to = name[:-5], 2, os.path.join(dest, name)
    while os.path.exists(to): to = os.path.join(dest, f"{stem} ~{n}.json"); n += 1
    os.replace(src, to)
    print(f"merge: {name} → {os.path.relpath(to, BOARDS)}" + (" (merged)" if changed else ""), flush=True)
    return changed
