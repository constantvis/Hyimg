"""Folders as on the board (owner 2026-10-05: «Разложить по папкам как на доске»).

The board is the source of truth and the files follow it, never the other way round: a folder per page, inside it a folder per
group (a group inside a group is a folder inside a folder), and a folder per sticky note that a row of pictures belongs to, inside
its group's folder. A picture that lies in one place goes into that place's folder; a picture placed in several places (copies on
two pages, in two groups) goes into the project's root. Library files that are on no page stay where they are.

The owner: «we don't need to sync anything now, we just build the functionality so the possibility exists». So it is off by
default; nothing here runs unless the owner presses «Разложить» in the library or switches on «Всегда держать папки как на доске».

Every run writes a journal <state>/layout-sync/<YYMMDDHHmmss>.json with every move (and every json it rewrote, with the text it had),
so the last run can be undone and the old paths keep resolving (server.py aliases() reads the journals).

Rules the owner set (2026-10-05):
  - a group inside a group: the group whose members list it first, else the smallest group frame that holds it whole
  - a picture's group: the group whose members list it first, else the smallest frame holding its centre (canvas.html regroup)
  - a note's pictures: the ones its card overlaps, the ones in its dashed zone and the ones its arrows point at (an arrow at a
    group and a note that speaks for its whole group make no folder of their own: that is the group's folder). A picture counts
    for a note only when both are in the same group. A picture in two notes goes to the one with the stronger tie
    (zone, then overlap, then arrow), then the smaller zone
  - a note inside a note: a note whose centre lies inside another note's zone (same group, bigger zone) is a folder inside that
    note's folder; otherwise notes are side by side (the owner was unsure, this is the rule to look at)
  - names: page title, group title, the note's first line, cleaned for the file system, up to 80 characters
  - a name taken in the target folder: «b1 (r30-studio-light).png» (the folder it came from), then «-2», «-3»
  - never moved: anything outside the library root, external folders (MOUNTS), the state folder, hidden folders, the folders the
    library skips (SKIP), _rejected, html/, frames/, 3d/
  - only folders left with no file at all are removed (a Finder .DS_Store does not count)
"""
import hashlib, json, os, re, shutil, threading, time, unicodedata

from config import BOARDS, HERE, W

# The reasons and errors this file gives for the interface in the app's language (owner 2026-10-06: «make 2 versions, Russian and English,
# switchable in settings»): server.py sets tr to its own (the app's setting cv.lang); alone, English.
tr = lambda en, ru: en
# The names of the folders it makes on disk stay as they are in every language: they are the library's data, a language switch
# must not make the layout move files.

JDIR = os.path.join(HERE, "layout-sync")
AUTO = os.path.join(JDIR, "auto.json")
MULTI_HIDDEN_ROOT = "В нескольких местах"   # where copies go when the library does not show files lying right in the root
PROTECTED_TOP = {"_rejected", "html", "frames", "3d", "notes", "_review", "ext"}
RESERVED = PROTECTED_TOP | {"added", "_favs", "_thumbs", "layout-sync"}
REL_KEYS = ("grid", "derived_from")       # a path relative to the json's folder (or to the library root)
REL_LISTS = ("inputs", "images")         # lists of paths relative to the json's folder
JUNK = {".DS_Store"}
RUN = threading.Lock()                   # one run at a time: a button, an agent and the auto mode never move files side by side


def k(s):
    """a name as the Mac's file system compares it: case and Unicode form do not matter"""
    return unicodedata.normalize("NFC", s).lower()


# ---------------------------------------------------------------- names
def clean(text, fallback, limit=80):
    t = (text or "").strip().split("\n")[0]
    t = re.sub(r"^\s*(#+\s*|[-*+]\s+|\d+[.)]\s+)", "", t)              # a heading, a list item
    t = t.replace("**", "").replace("__", "").replace("`", "")
    t = re.sub(r"(?<!\w)[*_]|[*_](?!\w)", "", t)                      # *italic*
    t = re.sub(r'[/\\:<>"|?*\x00-\x1f\x7f]', " ", t)                  # not allowed on the Mac or in Dropbox
    t = re.sub(r"\s+", " ", t).strip().lstrip(".").strip()
    if len(t) > limit:
        cut = t[:limit]
        t = cut.rsplit(" ", 1)[0] if " " in cut[limit // 2:] else cut
    t = t.rstrip(" .,;-·–—").strip()
    return t or fallback


def _unique(name, taken):
    n, out = 2, name
    while k(out) in taken:
        out = f"{name} {n}"; n += 1
    taken.add(k(out))
    return out


# ---------------------------------------------------------------- geometry (the same rules as canvas.html and server.note_index)
def _num(*v): return all(isinstance(x, (int, float)) for x in v)


def item_rect(it):
    if not _num(it.get("x"), it.get("y"), it.get("w")): return None
    x, y, w = float(it["x"]), float(it["y"]), float(it["w"])
    t = it.get("type")
    if not t:
        c = it.get("crop") or [0, 0, 1, 1]; ar = float(it.get("ar") or 1)
        try: h = w * ((c[3] - c[1]) / ar) / (c[2] - c[0])
        except (ZeroDivisionError, TypeError, IndexError): h = w / ar
        return (x, y, w, h)
    if t == "note": return (x, y, w, max(w, float(it.get("h") or float(it.get("fs") or 16) * 1.2)))
    return (x, y, w, float(it.get("h") or (it.get("fs") or 16) * 1.2))


def _grect(g): return (float(g["x"]), float(g["y"]), float(g["w"]), float(g["h"]))
def _area(r): return r[2] * r[3]
def _centre(r): return (r[0] + r[2] / 2, r[1] + r[3] / 2)
def _inside(p, r): return r[0] <= p[0] <= r[0] + r[2] and r[1] <= p[1] <= r[1] + r[3]
def _hit(a, b): return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]
def _holds(o, i): return o[0] <= i[0] and o[1] <= i[1] and i[0] + i[2] <= o[0] + o[2] and i[1] + i[3] <= o[1] + o[3]


def _zone(n, r):
    z = n.get("reach")
    if not isinstance(z, dict) or not _num(*(z.get(s, 0) for s in "ltrb")): return None
    return (r[0] - z.get("l", 0), r[1] - z.get("t", 0), r[2] + z.get("l", 0) + z.get("r", 0), r[3] + z.get("t", 0) + z.get("b", 0))


def _cut_cycles(parent):
    for start in list(parent):
        seen, x = set(), start
        while x in parent:
            if x in seen:
                parent.pop(x, None); break
            seen.add(x); x = parent[x]


def page_folders(b, bad=lambda name: False):
    """{item id: tuple of folder names under the page's folder} for every picture and image frame card of one board;
    bad(name): a name the library would hide (a skipped folder), it gets the kind of thing after it"""
    items, groups = b.get("items") or {}, b.get("groups") or {}
    G = {g: v for g, v in groups.items() if isinstance(v, dict) and _num(v.get("x"), v.get("y"), v.get("w"), v.get("h"))}
    GR = {g: _grect(v) for g, v in G.items()}
    owners = {}
    for g, v in G.items():
        for m in v.get("members") or []:
            owners.setdefault(m, []).append(g)
    # a group in a group: membership first, then the smallest frame that holds it whole
    gpar = {}
    for g in G:
        own = [p for p in owners.get(g, []) if p != g]
        if own: gpar[g] = min(own, key=lambda p: (_area(GR[p]), p)); continue
        hold = [p for p in G if p != g and _holds(GR[p], GR[g]) and _area(GR[p]) > _area(GR[g])]
        if hold: gpar[g] = min(hold, key=lambda p: (_area(GR[p]), p))
    _cut_cycles(gpar)

    def group_of(iid, r):
        own = [g for g in owners.get(iid, []) if g in G]
        if own: return min(own, key=lambda g: (_area(GR[g]), g))
        if r is None: return None
        c = _centre(r); hit = [g for g in G if _inside(c, GR[g])]
        return min(hit, key=lambda g: (_area(GR[g]), g)) if hit else None

    rects = {i: item_rect(v) for i, v in items.items() if isinstance(v, dict)}
    placed = {i for i, v in items.items() if isinstance(v, dict) and rects.get(i) and (not v.get("type") and v.get("path") or v.get("type") == "imgframe" and isinstance(v.get("pics"), list))}
    igrp = {i: group_of(i, rects[i]) for i in placed}

    # notes and the pictures they hold: zone 3, overlap 2, arrow 1
    C, cells = 2048, {}
    for i in placed:
        r = rects[i]
        for cx in range(int(r[0] // C), int((r[0] + r[2]) // C) + 1):
            for cy in range(int(r[1] // C), int((r[1] + r[3]) // C) + 1): cells.setdefault((cx, cy), []).append(i)

    def near(a):
        out = []
        for cx in range(int(a[0] // C), int((a[0] + a[2]) // C) + 1):
            for cy in range(int(a[1] // C), int((a[1] + a[3]) // C) + 1): out += cells.get((cx, cy), ())
        return dict.fromkeys(out)

    notes = {}
    for nid, n in items.items():
        if not isinstance(n, dict) or n.get("type") != "note" or not (n.get("text") or "").strip() or not rects.get(nid): continue
        r = rects[nid]; z = _zone(n, r); rows = {}
        box = r if not z else (min(r[0], z[0]), min(r[1], z[1]), max(r[0] + r[2], z[0] + z[2]) - min(r[0], z[0]), max(r[1] + r[3], z[1] + z[3]) - min(r[1], z[1]))
        for i in near(box):
            q = rects[i]
            if z and _inside(_centre(q), z): rows[i] = 3
            elif _hit(r, q): rows[i] = max(rows.get(i, 0), 2)
        for t in n.get("to") or []:
            if t in placed: rows[t] = max(rows.get(t, 0), 1)
        if rows:
            notes[nid] = {"r": r, "z": z, "rows": rows, "g": group_of(nid, r), "a": _area(z or r)}
    # a note inside a note: its centre in another note's zone, the same group, the other zone bigger
    npar = {}
    for nid, n in notes.items():
        c = _centre(n["r"])
        hold = [o for o, m in notes.items() if o != nid and m["z"] and m["g"] == n["g"] and _inside(c, m["z"]) and m["a"] > n["a"]]
        if hold: npar[nid] = min(hold, key=lambda o: (notes[o]["a"], o))
    _cut_cycles(npar)

    # names, unique among the folders side by side (groups first, by id, then notes)
    kids = {}
    for g in sorted(G): kids.setdefault(("g", gpar.get(g)), []).append(("g", g))
    for nid in sorted(notes):
        par = ("n", npar[nid]) if nid in npar else ("g", notes[nid]["g"])
        kids.setdefault(par, []).append(("n", nid))
    name = {}
    for par, L in kids.items():
        taken = set()
        for kind, x in L:
            raw = G[x].get("title") if kind == "g" else items[x].get("text")
            nm = clean(raw, "Группа" if kind == "g" else "Заметка")
            if bad(nm): nm += " (группа)" if kind == "g" else " (заметка)"
            name[(kind, x)] = _unique(nm, taken)

    memo = {}

    def chain(node):
        if node in memo: return memo[node]
        kind, x = node
        if x is None: out = ()
        elif kind == "g": out = chain(("g", gpar.get(x))) + (name[node],)
        else: out = chain(("n", npar[x]) if x in npar else ("g", notes[x]["g"])) + (name[node],)
        memo[node] = out
        return out

    out = {}
    for i in placed:
        g = igrp[i]
        best = min(((-n["rows"][i], n["a"], nid) for nid, n in notes.items() if i in n["rows"] and n["g"] == g), default=None)
        out[i] = chain(("n", best[2])) if best else chain(("g", g))
    return out


# ---------------------------------------------------------------- the plan
def load_pages():
    try: L = json.load(open(os.path.join(BOARDS, "pages.json"), encoding="utf-8"))["pages"]
    except (OSError, ValueError, KeyError): L = []
    return L or [{"id": "main", "title": tr("Page 1", "Страница 1")}]   # as server.py load_pages names it: the page the owner sees (owner 2026-10-06)


def load_board(name):
    try: return json.load(open(os.path.join(BOARDS, name + ".json"), encoding="utf-8"))
    except (OSError, ValueError): return {"items": {}, "groups": {}}


class Env:
    """what the server knows about its library: the folders it skips, the external mounts, which files are media"""
    def __init__(self, skip=(), hide=(), media=(), images=(), mounts=(), root_shown=True, aliases=None, hide_named=(), hide_prefixes=()):
        self.skip, self.hide, self.media, self.images = {k(s) for s in skip}, list(hide), tuple(media), tuple(images)
        self.hide_named, self.hide_prefixes = {k(s) for s in hide_named}, tuple(k(s) for s in hide_prefixes)   # the board's rules
        self.mounts, self.root_shown, self.aliases = list(mounts), root_shown, aliases or (lambda: {})


def protected(rel, env):
    """why a library path must stay where it is, or None"""
    if not rel or rel.startswith("/") or ".." in rel.split("/"): return tr("outside the library", "вне библиотеки")
    if any(rel.startswith(m + "/") for m in env.mounts) or rel.startswith("ext/"): return tr("external folder", "внешняя папка")
    full = os.path.realpath(os.path.join(W, rel))
    if not full.startswith(os.path.realpath(W) + os.sep): return tr("outside the library", "вне библиотеки")
    if full.startswith(os.path.realpath(HERE) + os.sep): return tr("state folder", "папка состояния")
    parts = rel.split("/")[:-1]
    if parts and k(parts[0]) in PROTECTED_TOP: return tr("service folder", "служебная папка")
    if any(p.startswith(".") or k(p) in env.skip for p in parts): return tr("service folder", "служебная папка")
    return None


def _dir_ok(rel_dir, env):
    """a folder the library shows and this module may write into"""
    parts = rel_dir.split("/")
    if k(parts[0]) in RESERVED: return False
    if any(k(p) in env.skip or k(p) in env.hide_named or (env.hide_prefixes and k(p).startswith(env.hide_prefixes)) or p.startswith(".") for p in parts): return False
    return not any(rel_dir == h or rel_dir.startswith(h + "/") for h in env.hide)


def _listdir(d, cache):
    if d not in cache:
        try: cache[d] = os.listdir(os.path.join(W, d) if d else W)
        except OSError: cache[d] = None
    return cache[d]


def _on_disk(segs, cache):
    """the folder path with each step spelled as it already is on disk (case, Unicode form)"""
    cur = []
    for s in segs:
        names = _listdir("/".join(cur), cache) or []
        hit = next((n for n in names if k(n) == k(s) and os.path.isdir(os.path.join(W, *cur, n))), None)
        cur.append(hit or s)
    return "/".join(cur)


def companions(rel, env):
    """(sidecar json paths that travel with a picture, those shared with another picture of the same name in its folder)"""
    d, f = os.path.split(rel); stem, ext = os.path.splitext(f)
    names, stems = _ls(d), _stems(d, env)
    found, shared = [], set()
    want = [f + ".json"] + ([stem + ".json"] if ext.lower() in env.images else [])
    for w in want:
        if w not in names: continue
        found.append(w)
        if w == stem + ".json" and stems.get(stem, 0) > 1: shared.add(w)   # <stem>.json of a picture: b1.jpg beside b1.png reads it too
    return [(d + "/" if d else "") + n for n in found], {(d + "/" if d else "") + n for n in shared}


_LS, _ST = {}, {}


def _ls(d):
    if d not in _LS:
        try: _LS[d] = set(os.listdir(os.path.join(W, d) if d else W))
        except OSError: _LS[d] = set()
    return _LS[d]


def _stems(d, env):
    """how many pictures of a folder share each stem (one listing per folder, the plan asks for thousands of files)"""
    if d not in _ST:
        c = {}
        for n in _ls(d):
            st, e = os.path.splitext(n)
            if e.lower() in env.images: c[st] = c.get(st, 0) + 1
        _ST[d] = c
    return _ST[d]


def _blocks(names):
    """every stem a folder's names keep from being reused: b1.png and b1.json block «b1», x.jpg.json blocks «x» and «x.jpg»"""
    out = set()
    for n in names:
        i = n.find(".")
        while i > 0:
            out.add(n[:i]); i = n.find(".", i + 1)
    return out


def _exists(rel):
    return os.path.lexists(os.path.join(W, rel))


_PLAN = threading.Lock()


def plan(env, count_library=False):
    """what a run would do, changing nothing: moves, folders made and removed, examples, counts"""
    with _PLAN:   # the folder listings are kept for one plan (_LS)
        return _plan(env, count_library)


def _plan(env, count_library):
    _LS.clear(); _ST.clear(); cache = {}
    pages = load_pages()
    taken, page_seg = set(), {}
    ours = {k(d) for j in _journals() if j.get("status") == "done" for d in j.get("dirs_made", []) if "/" not in d}
    root = {k(n) for n in (_listdir("", cache) or []) if os.path.isdir(os.path.join(W, n))}
    for pg in pages:   # page folders: unique, never a reserved or skipped name, never a folder that was there before (a batch)
        nm = clean(pg.get("title"), "Страница")
        if not _dir_ok(nm, env) or (k(nm) in root and k(nm) not in ours): nm = nm + " (страница)"
        page_seg[pg["id"]] = _unique(nm, taken)
    multi = () if env.root_shown else (MULTI_HIDDEN_ROOT,)
    al = env.aliases() or {}
    where, fixes, frames = {}, {}, {}
    for pg in pages:
        b = load_board(pg["id"])
        folders = page_folders(b, lambda nm: not _dir_ok("x/" + nm, env))
        for iid, segs in folders.items():
            it = b["items"][iid]
            for p in ([it["path"]] if not it.get("type") else [x for x in it.get("pics") or [] if isinstance(x, str)]):
                cur = p
                if not _exists(cur) and al.get(cur) and _exists(al[cur]): fixes[p] = cur = al[cur]
                where.setdefault(cur, set()).add((page_seg[pg["id"]],) + segs)
            if it.get("type") == "imgframe" and isinstance(it.get("doc"), str): frames[it["doc"]] = 1
    moves, stay, reasons, missing = [], [], {}, []
    for p in sorted(where):
        why = protected(p, env)
        if why:
            stay.append(p); reasons[why] = reasons.get(why, 0) + 1; continue
        if not os.path.isfile(os.path.join(W, p)):
            missing.append(p); continue
        segs = sorted(where[p])[0] if len(where[p]) == 1 else multi
        tdir = _on_disk(segs, cache) if segs else ""
        if tdir and not _dir_ok(tdir, env):   # a folder the library would hide: the copies' place instead
            tdir = _on_disk(multi, cache) if multi else ""
        sdir = os.path.dirname(p)
        if k(sdir) == k(tdir):
            why = tr("already in place", "уже на месте"); stay.append(p); reasons[why] = reasons.get(why, 0) + 1; continue
        moves.append({"from": p, "dir": tdir, "multi": len(where[p]) > 1})
    # names: what is in a folder keeps its name; what comes in takes a free one. A name freed by a file leaving in the same run is
    # not reused, so the moves need no order
    for m in moves:
        m["side"], m["shared"] = companions(m["from"], env)
    occ = {}
    for m in sorted(moves, key=lambda m: (k(m["dir"]), m["from"])):
        d = m["dir"]
        if d not in occ:
            names = {k(n) for n in (_listdir(d, cache) or [])}
            occ[d] = (names, _blocks(names))
        f = os.path.basename(m["from"]); stem, ext = os.path.splitext(f)
        src = os.path.basename(os.path.dirname(m["from"])) or "корень"
        free = lambda s: k(s + ext) not in occ[d][0] and k(s) not in occ[d][1]
        cands = [stem, f"{stem} ({clean(src, 'корень')})"]
        s = next((c for c in cands if free(c)), None)
        n = 2
        while s is None:
            c = f"{cands[1]}-{n}"; n += 1
            if free(c): s = c
        new = (d + "/" if d else "") + s + ext
        m["to"], m["renamed"] = new, s != stem
        sides = []
        for x in m["side"]:
            b = os.path.basename(x)
            nb = s + ext + ".json" if b == f + ".json" else s + ".json"
            sides.append([x, (d + "/" if d else "") + nb, "copy" if x in m["shared"] else "move"])
        m["side"] = sides
        added = {k(os.path.basename(new))} | {k(os.path.basename(t)) for _f, t, _w in sides}
        occ[d][0].update(added); occ[d][1].update(_blocks(added))
    # folders made and folders left empty
    make = set()
    for m in moves:
        parts = m["dir"].split("/") if m["dir"] else []
        for i in range(1, len(parts) + 1):
            dd = "/".join(parts[:i])
            if not os.path.isdir(os.path.join(W, dd)): make.add(dd)
    gone_files = {}
    for m in moves:
        for x in [m["from"]] + [f for f, _t, w in m["side"] if w == "move"]:
            gone_files.setdefault(os.path.dirname(x), set()).add(os.path.basename(x))
    targets = {m["dir"] for m in moves}
    removed = set()
    todo = sorted(gone_files, key=lambda d: -d.count("/"))
    while todo:
        d = todo.pop(0)
        if not d or d in removed or any(k(t) == k(d) or k(t).startswith(k(d) + "/") for t in targets): continue
        if protected(d + "/x", env): continue
        left = [n for n in (_listdir(d, cache) or []) if n not in JUNK and n not in gone_files.get(d, set()) and (d + "/" + n) not in removed]
        if not left:
            removed.add(d)
            par = os.path.dirname(d)
            if par and par not in todo: todo.append(par); todo.sort(key=lambda x: -x.count("/"))
    off = None
    if count_library:
        on = set(where) | set(fixes)
        off = sum(1 for p in library_media(env) if p not in on)
    return {"moves": moves, "make": sorted(make), "remove": sorted(removed, key=lambda d: -d.count("/")), "stay": len(stay), "reasons": reasons,
            "missing": missing, "fixes": fixes, "frames": sorted(frames), "off_board": off, "pages": [page_seg[p["id"]] for p in pages],
            "multi_dir": "/".join(multi)}


def library_media(env):
    for root, dirs, files in os.walk(W):
        rel = os.path.relpath(root, W); rel = "" if rel == "." else rel
        if os.path.realpath(root) == os.path.realpath(HERE): dirs[:] = []; continue
        if rel and protected(rel + "/x", env): dirs[:] = []; continue
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.lower().endswith(env.media): yield (rel + "/" if rel else "") + f


def summary(p, n=5):
    """counts and a few real examples for the dialog and hy.py"""
    moves = p["moves"]
    pick, seen = [], set()
    for want in (lambda m: m["renamed"], lambda m: m["multi"], lambda m: m["dir"].count("/") >= 2, lambda m: m["dir"].count("/") == 1,
                 lambda m: m["dir"].count("/") == 0 and not m["multi"], lambda m: True):
        m = next((m for m in moves if want(m) and m["from"] not in seen), None)
        if m and len(pick) < n: pick.append(m); seen.add(m["from"])
    return {"move": len(moves), "make": len(p["make"]), "remove": len(p["remove"]), "stay": p["stay"], "off_board": p["off_board"],
            "missing": len(p["missing"]), "fixes": len(p["fixes"]), "reasons": p["reasons"], "pages": p["pages"],
            "sidecars": sum(len(m["side"]) for m in moves), "renamed": sum(1 for m in moves if m["renamed"]), "multi": sum(1 for m in moves if m["multi"]), "multi_dir": p.get("multi_dir", ""),
            "examples": [{"from": m["from"], "to": m["to"]} for m in pick]}


# ---------------------------------------------------------------- rewriting paths in json files and boards
def _sub_strings(v, mp):
    """every string equal to a moved path, replaced, anywhere in a json value; returns (value, changed)"""
    if isinstance(v, str): return (mp[v], True) if v in mp else (v, False)
    if isinstance(v, list):
        ch, out = False, []
        for x in v:
            y, c = _sub_strings(x, mp); out.append(y); ch |= c
        return out, ch
    if isinstance(v, dict):
        ch, out = False, {}
        for a, x in v.items():
            y, c = _sub_strings(x, mp); out[a] = y; ch |= c
        return out, ch
    return v, False


def rewrite_board(b, mp):
    """picture paths, image frame cards' pics and the archive (removed) keyed by path"""
    ch = False
    for it in (b.get("items") or {}).values():
        if not isinstance(it, dict): continue
        if isinstance(it.get("path"), str) and it["path"] in mp: it["path"] = mp[it["path"]]; ch = True
        if isinstance(it.get("pics"), list):
            new = [mp.get(x, x) if isinstance(x, str) else x for x in it["pics"]]
            if new != it["pics"]: it["pics"] = new; ch = True
    rm = b.get("removed")
    if isinstance(rm, dict) and any(x in mp for x in rm):
        b["removed"] = {mp.get(x, x): v for x, v in rm.items()}; ch = True
    return ch


def _ref_fix(meta, old_dir, new_dir, amap):
    """relative paths in a sidecar (grid, derived_from, inputs, images) that point at a file which moved, or that the json itself
    moved away from: rewritten so they reach the same file. amap: old absolute path -> new absolute path"""
    ch = False

    def fix(v):
        nonlocal ch
        if not isinstance(v, str) or not v or v.startswith(("/", "http:", "https:")): return v
        here = os.path.normpath(os.path.join(old_dir, v))
        if here in amap or (old_dir != new_dir and os.path.exists(here)):
            nv = os.path.relpath(amap.get(here, here), new_dir)
            if nv != v: ch = True; return nv
            return v
        top = os.path.normpath(os.path.join(W, v))   # written relative to the library root (cut_grids.py)
        if top in amap:
            ch = True; return os.path.relpath(amap[top], W)
        return v
    for key in REL_KEYS:
        if key in meta: meta[key] = fix(meta[key])
    for key in REL_LISTS:
        if isinstance(meta.get(key), list): meta[key] = [fix(x) for x in meta[key]]
    return ch


def _dump_like(raw, doc):
    if "\n" in raw.strip():
        ind = re.match(r"\{\s*\n( +)\"", raw)
        return json.dumps(doc, ensure_ascii=False, indent=len(ind.group(1)) if ind else 1)
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":") if '":' in raw and '": ' not in raw else None)


def _write_text(full, text):
    tmp = full + ".fs-tmp"
    with open(tmp, "w", encoding="utf-8") as fh: fh.write(text)
    os.replace(tmp, full)


def _sha(text): return hashlib.sha1(text.encode("utf-8")).hexdigest()


def json_candidates(env, names):
    """library jsons that may point at one of the moved files by a relative path: read outside the lock"""
    keys = [b'"' + x.encode() + b'"' for x in REL_KEYS + REL_LISTS]
    names = set(names)
    out = []
    for root, dirs, files in os.walk(W):
        rel = os.path.relpath(root, W); rel = "" if rel == "." else rel
        if os.path.realpath(root) == os.path.realpath(HERE) or (rel and protected(rel + "/x", env)): dirs[:] = []; continue
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if not f.endswith(".json"): continue
            full = os.path.join(root, f)
            try: raw = open(full, "rb").read()
            except OSError: continue
            if not any(x in raw for x in keys): continue
            try: meta = json.loads(raw)
            except ValueError: continue
            if not isinstance(meta, dict): continue
            vals = [meta.get(x) for x in REL_KEYS] + [v for x in REL_LISTS if isinstance(meta.get(x), list) for v in meta[x]]
            if any(isinstance(v, str) and os.path.basename(v) in names for v in vals): out.append((rel + "/" if rel else "") + f)
    return out


# ---------------------------------------------------------------- journals and aliases
def _journals():
    try: names = sorted(n for n in os.listdir(JDIR) if re.fullmatch(r"\d{12}(-\d+)?\.json", n))
    except OSError: return []
    out = []
    for n in names:
        try: out.append(json.load(open(os.path.join(JDIR, n), encoding="utf-8")))
        except (OSError, ValueError): pass
    return out


def _save_journal(j):
    os.makedirs(JDIR, exist_ok=True)
    _write_text(os.path.join(JDIR, j["id"] + ".json"), json.dumps(j, ensure_ascii=False, indent=1))


_AL = {"key": None, "map": {}}


def aliases(base):
    """old path -> where the file is now: base (older moves) plus every run of this module, followed to the end"""
    try: key = (os.stat(JDIR).st_mtime_ns, tuple(sorted(base.items())) if len(base) < 2000 else len(base))
    except OSError: key = (None, len(base))
    if _AL["key"] != key:
        A = dict(base)
        ev = []
        for j in _journals():
            if j.get("status") not in ("done", "undone"): continue
            ev.append((j.get("t", ""), 0, j))
            if j.get("status") == "undone": ev.append((j.get("undone_t", ""), 1, j))
        for _t, undo, j in sorted(ev, key=lambda e: (e[0], e[1])):
            for m in j.get("moves", []):
                pairs = [(m["from"], m["to"])] + [(f, t) for f, t, w in m.get("side", []) if w == "move"]
                for f, t in pairs:
                    if undo:
                        if A.get(f) == t: A.pop(f)
                        A[t] = f
                    else:
                        if A.get(t) == f: A.pop(t)
                        A[f] = t
        out = {}
        for a in A:
            seen, x = {a}, A[a]
            while x in A and x not in seen: seen.add(x); x = A[x]
            if x != a: out[a] = x
        _AL.update(key=key, map=out)
    return _AL["map"]


def last_run():
    js = [j for j in _journals() if j.get("status") in ("done", "undone", "failed")]
    if not js: return None
    j = js[-1]
    return {"id": j["id"], "t": j.get("t"), "who": j.get("who"), "status": j["status"], "moved": len(j.get("moves", [])),
            "made": len(j.get("dirs_made", [])), "removed": len(j.get("dirs_removed", [])), "error": j.get("error"), "undone_t": j.get("undone_t")}


def stamp():
    return os.path.getmtime(JDIR) if os.path.isdir(JDIR) else 0


def auto_on():
    try: return bool(json.load(open(AUTO, encoding="utf-8")).get("on"))
    except (OSError, ValueError, AttributeError): return False


def set_auto(on):
    os.makedirs(JDIR, exist_ok=True)
    _write_text(AUTO, json.dumps({"on": bool(on), "t": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False))
    return bool(on)


def _new_id():
    base = time.strftime("%y%m%d%H%M%S"); n, sid = 2, base
    while os.path.exists(os.path.join(JDIR, sid + ".json")): sid = f"{base}-{n}"; n += 1
    return sid


# ---------------------------------------------------------------- apply and undo
class Failed(Exception):
    pass


def _rm_empty(d):
    """removes folder d (library relative) if nothing but Finder's .DS_Store is in it; True when it went"""
    full = os.path.join(W, d)
    try: names = os.listdir(full)
    except OSError: return False
    if any(n not in JUNK for n in names): return False
    for n in names: os.remove(os.path.join(full, n))
    os.rmdir(full)
    return True


def _rewrite_frames(docs, mp, undo, done):
    for doc in docs:
        full = os.path.normpath(os.path.join(W, doc))
        if not doc.startswith("frames/") or not full.startswith(os.path.join(W, "frames") + os.sep): continue
        try: raw = open(full, encoding="utf-8").read(); d = json.loads(raw)
        except (OSError, ValueError): continue
        nd, ch = _sub_strings(d, mp)
        if not ch: continue
        text = _dump_like(raw, nd); _write_text(full, text)
        done.append({"file": doc, "orig": raw, "sha": _sha(text)})
        undo.append(lambda full=full, raw=raw: _write_text(full, raw))


def write_board(name, b):
    p = os.path.join(BOARDS, name + ".json")
    b["revision"] = int(b.get("revision", 0)) + 1
    b["saved"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_text(p, json.dumps(b, ensure_ascii=False, indent=1))


def _boards_rewrite(mp, undo):
    changed = []
    for pg in load_pages():
        b = load_board(pg["id"])
        if not b.get("items") and not b.get("removed"): continue
        if rewrite_board(b, mp):
            write_board(pg["id"], b); changed.append(pg["id"])
            inv = {v: a for a, v in mp.items()}
            undo.append(lambda name=pg["id"], inv=inv: (lambda bb: rewrite_board(bb, inv) and write_board(name, bb))(load_board(name)))
    return changed


def apply(env, who="owner", candidates=None, pl=None):
    """moves the files as plan() says; the caller holds the server's lock. Returns the journal. Rolls back on any failure."""
    pl = pl or plan(env)
    moves = pl["moves"]
    j = {"id": _new_id(), "t": time.strftime("%Y-%m-%d %H:%M:%S"), "who": who, "status": "pending", "moves": [], "dirs_made": [],
         "dirs_removed": [], "json": [], "boards": [], "frames": [], "fixes": pl["fixes"]}
    if not moves and not pl["fixes"]:
        return dict(j, status="nothing")
    # every source there, every target free (case-insensitively, as the Mac sees it)
    for m in moves:
        if not os.path.isfile(os.path.join(W, m["from"])): raise Failed(tr("no file ", "нет файла ") + m["from"])
        for t in [m["to"]] + [t for _f, t, _w in m["side"]]:
            if _exists(t): raise Failed(tr("the place is taken: ", "место занято: ") + t)
    j["planned"] = [{"from": m["from"], "to": m["to"], "side": m["side"]} for m in moves]
    _save_journal(j)
    undo = []
    try:
        for d in pl["make"]:
            os.makedirs(os.path.join(W, d), exist_ok=True); j["dirs_made"].append(d)
        undo.append(lambda made=list(pl["make"]): [_rm_empty(d) for d in sorted(made, key=lambda d: -d.count("/"))])
        amap = {}
        for m in moves:
            src, dst = os.path.join(W, m["from"]), os.path.join(W, m["to"])
            if _exists(m["to"]): raise Failed(tr("the place is taken: ", "место занято: ") + m["to"])
            os.rename(src, dst); undo.append(lambda s=src, d=dst: os.rename(d, s))
            amap[os.path.normpath(src)] = os.path.normpath(dst)
            done_side = []
            for f, t, how in m["side"]:
                fs, ts = os.path.join(W, f), os.path.join(W, t)
                if how == "copy":
                    shutil.copy2(fs, ts); undo.append(lambda ts=ts: os.remove(ts))
                else:
                    os.rename(fs, ts); undo.append(lambda fs=fs, ts=ts: os.rename(ts, fs))
                    amap[os.path.normpath(fs)] = os.path.normpath(ts)
                done_side.append([f, t, how])
            j["moves"].append({"from": m["from"], "to": m["to"], "side": done_side})
        mp = {m["from"]: m["to"] for m in moves}
        mp.update({a: b for a, b in pl["fixes"].items() if a not in mp})
        for a, b in pl["fixes"].items():   # a board path that had moved before (an old link): now the file's place after this run
            if b in mp: mp[a] = mp[b]
        # sidecars: the ones that moved (their relative links now start from another folder), the ones pointing at a moved file,
        # and "path" inside a pasted picture's json
        side_new = {}
        for m in j["moves"]:
            for f, t, _how in m["side"]: side_new[t] = (os.path.dirname(os.path.join(W, f)), m)
        todo = list(side_new) + [c for c in candidates or [] if c not in side_new and os.path.normpath(os.path.join(W, c)) not in amap]
        for rel in todo:
            full = os.path.join(W, rel)
            try: raw = open(full, encoding="utf-8").read(); meta = json.loads(raw)
            except (OSError, ValueError): continue
            if not isinstance(meta, dict): continue
            old_dir = side_new[rel][0] if rel in side_new else os.path.dirname(full)
            ch = _ref_fix(meta, old_dir, os.path.dirname(full), amap)
            if rel in side_new and meta.get("path") == side_new[rel][1]["from"]: meta["path"] = side_new[rel][1]["to"]; ch = True
            if not ch: continue
            text = _dump_like(raw, meta); _write_text(full, text)
            j["json"].append({"file": rel, "orig": raw, "sha": _sha(text)})
            undo.append(lambda full=full, raw=raw: _write_text(full, raw))
        _rewrite_frames(pl["frames"], mp, undo, j["frames"])
        j["boards"] = _boards_rewrite(mp, undo)
        for d in pl["remove"]:
            if _rm_empty(d):
                j["dirs_removed"].append(d); undo.append(lambda d=d: os.makedirs(os.path.join(W, d), exist_ok=True))
        j["status"] = "done"; j.pop("planned", None)
        _save_journal(j)
        return j
    except Exception as ex:
        errs = 0
        for fn in reversed(undo):
            try: fn()
            except Exception: errs += 1
        j.update(status="failed", error=f"{type(ex).__name__}: {str(ex)[:300]}", rollback_errors=errs, moves=[], dirs_made=[], dirs_removed=[])
        _save_journal(j)
        raise Failed(tr("the layout stopped and was undone: ", "раскладка остановлена и отменена: ") + str(ex)[:200]
                     + (tr(" (steps not undone: {})", " (не вернулось шагов: {})").format(errs) if errs else "")) from ex


def undo_last(env):
    """moves the last run's files back, puts its rewritten jsons back as they were, recreates the folders it removed"""
    js = [j for j in _journals() if j.get("status") == "done"]
    if not js: raise Failed(tr("nothing to undo", "нечего отменять"))
    j = js[-1]
    moves = j.get("moves", [])
    for m in moves:   # the old places must be free again
        for f in [m["from"]] + [f for f, _t, w in m.get("side", []) if w == "move"]:
            if _exists(f): raise Failed(tr("there is already a file in the old place: ", "на старом месте уже есть файл: ") + f)
    missing = []
    # jsons this run wrote: back to their text, unless they were changed since (then only the paths are turned back)
    inv_abs = {}
    for m in moves:
        inv_abs[os.path.normpath(os.path.join(W, m["to"]))] = os.path.normpath(os.path.join(W, m["from"]))
        for f, t, w in m.get("side", []):
            if w == "move": inv_abs[os.path.normpath(os.path.join(W, t))] = os.path.normpath(os.path.join(W, f))
    for e in j.get("json", []) + j.get("frames", []):
        full = os.path.join(W, e["file"])
        try: cur = open(full, encoding="utf-8").read()
        except OSError: continue
        if _sha(cur) == e["sha"]: _write_text(full, e["orig"])
    for d in sorted(j.get("dirs_removed", []), key=lambda d: d.count("/")):
        os.makedirs(os.path.join(W, d), exist_ok=True)
    back = 0
    for m in reversed(moves):
        if not os.path.isfile(os.path.join(W, m["to"])): missing.append(m["to"]); continue
        os.makedirs(os.path.dirname(os.path.join(W, m["from"])) or W, exist_ok=True)
        os.rename(os.path.join(W, m["to"]), os.path.join(W, m["from"])); back += 1
        # a json made for the picture after the run (a heart, a rating, a note's reference) goes back with it too
        sides = [list(x) for x in m.get("side", [])]
        (fd, ff), (td, tf) = os.path.split(m["from"]), os.path.split(m["to"])
        for old, new in ((ff + ".json", tf + ".json"), (os.path.splitext(ff)[0] + ".json", os.path.splitext(tf)[0] + ".json")):
            o, n = (fd + "/" if fd else "") + old, (td + "/" if td else "") + new
            if not any(t == n for _f, t, _w in sides) and _exists(n) and not _exists(o) and (old != os.path.splitext(ff)[0] + ".json" or os.path.splitext(ff)[1].lower() in env.images):
                sides.append([o, n, "move"])
        for f, t, w in sides:
            if not _exists(t): continue
            if w == "copy": os.remove(os.path.join(W, t))
            else:
                os.makedirs(os.path.dirname(os.path.join(W, f)) or W, exist_ok=True)
                os.rename(os.path.join(W, t), os.path.join(W, f))
    inv = {m["to"]: m["from"] for m in moves}
    for doc in j.get("frames", []):
        full = os.path.join(W, doc["file"])
        try: raw = open(full, encoding="utf-8").read(); d = json.loads(raw)
        except (OSError, ValueError): continue
        nd, ch = _sub_strings(d, inv)
        if ch: _write_text(full, _dump_like(raw, nd))
    boards = []
    for pg in load_pages():
        b = load_board(pg["id"])
        if rewrite_board(b, inv): write_board(pg["id"], b); boards.append(pg["id"])
    gone = 0
    for d in sorted(j.get("dirs_made", []), key=lambda d: -d.count("/")):
        if _rm_empty(d): gone += 1
    j.update(status="undone", undone_t=time.strftime("%Y-%m-%d %H:%M:%S"), undo={"back": back, "missing": missing, "boards": boards, "dirs_gone": gone})
    _save_journal(j)
    return j


def thumbs_rekey(thumbs, pairs):
    """the thumbnail cache is keyed by the path: the made thumbnails follow the file (its time stays the same after a rename)"""
    key = lambda rel: re.sub(r"[^A-Za-z0-9._-]", "_", rel)
    for a, b in pairs:
        try: mt = int(os.stat(os.path.join(W, b)).st_mtime)
        except OSError: continue
        for tail in [f".{mt}.{s}.jpg" for s in (96, 320, 640, 1280)] + [f".{mt}.prev.jpg", f".{mt}.prev.png"]:
            src, dst = os.path.join(thumbs, key(a) + tail), os.path.join(thumbs, key(b) + tail)
            try:
                if os.path.exists(src) and not os.path.exists(dst): os.rename(src, dst)
            except OSError: pass
