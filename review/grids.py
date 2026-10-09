"""Grids on the board (owner 2026-10-08: «добавить в нашу систему Arrange: пользователю нативно и удобно, он даже не поймет, что
таблицей что-то разложил, а для агента структура — win-win»). Arrange (⌥A as a block, ⌥S a row, ⌥D tidy when its result is a grid,
«Make grid» in the right click) and an agent's `grid`, `block`, `arrange` leave a light record on the page, so the structure is explicit
and nobody has to guess it from positions:

  board["grids"][<id>] = {"members": [ids, rows top to bottom, each left to right], "cols": N, "rows": M, "gap": 24, "cell": "fit",
                          "head": {"row": true, "col": true}   (only when headings fill the first row or column: its titles)}

The cell policy "fit" is the one there is: a column is as wide as its widest member, a row as tall as its tallest, a member sits at its
cell's top left, gap between cells (what ⌥A always did). No frame is drawn for a grid; the board shows a faint «Grid 4 × 3» while one
of its members is selected or dragged. One item is in one grid at most; a grid lives on as long as it has 2 members.

A table (Arrange's A5 Table) is a grid whose first row and first column are headings (text items, the corner one too): head {row, col}
comes by itself. What put moves into a grid joins the group frame its cell is in, as a drop on the canvas does, so a table's headings
move with their group; zone fits a note's dashed zone around its grid when the grid grew (2026-10-08, the sb06 tables on «Renderings»).

Here: the record, the layout (reflow), what keeps a grid right after other edits (prune, merged), the commands for hy.py do (grid, put,
ungrid) and the tables map, find and md show. ui/grid.js is the same model on the board, with the gestures. Nothing here reads files."""
import math
import random
import string

import notelinks

GAP = 24
MAXCOLS = 8   # ⌥A's block is never wider than 8 (canvas.html MAXCOLS)
KIND = {"htmlframe": "HTML", "html": "HTML", "model3d": "3D", "imgframe": "фрейм"}


def items(b): return b.get("items") or {}
def table(b): return b.get("grids") or {}
def box(it): return notelinks.rect(it)
def uid(): return "gr" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(7))


def gridable(it):
    """what a grid holds: a picture, a video, a PDF, a plugin's card, a heading; never a note or a timeline"""
    return isinstance(it, dict) and it.get("type") not in ("note", "timeline") and bool(it.get("type") or it.get("path")) and it.get("x") is not None


def placed(b, ids):
    return [i for i in ids if gridable(items(b).get(i))]


def of(b, iid):
    """the grid an item is in, or None"""
    return next((gid for gid, g in table(b).items() if iid in g.get("members", [])), None)


def rows_of(b, ids):
    """reading order: rows top to bottom (a thing joins a row when its top is within half the shortest height of the row's first),
    each row left to right"""
    R = {i: box(items(b)[i]) for i in ids}
    if not R: return []
    tol = min(r[3] for r in R.values()) / 2
    out = []
    for i in sorted(R, key=lambda i: (R[i][1], R[i][0])):
        if out and abs(R[i][1] - R[out[-1][0]][1]) <= tol: out[-1].append(i)
        else: out.append([i])
    return [sorted(r, key=lambda i: R[i][0]) for r in out]


def origin(b, ids):
    rs = [box(items(b)[i]) for i in ids if i in items(b)]
    return (min(r[0] for r in rs), min(r[1] for r in rs)) if rs else (0.0, 0.0)


def layout(b, g, at=None):
    """{member: (x, y)} and the shape {cols, rows, colw, rowh, x, y, w, h}: row-major, cols from the record (fewer when fewer members)"""
    ms = [m for m in g.get("members", []) if m in items(b)]
    n, gap = len(ms), g.get("gap", GAP)
    cols = max(1, min(int(g.get("cols") or 1), n or 1)); rows = math.ceil(n / cols) if n else 0
    R = [box(items(b)[m]) for m in ms]
    colw = [max((R[k][2] for k in range(c, n, cols)), default=0) for c in range(cols)]
    rowh = [max(r[3] for r in R[k * cols:(k + 1) * cols]) for k in range(rows)]
    x0, y0 = at or origin(b, ms)
    pos = {m: (x0 + sum(colw[:k % cols]) + (k % cols) * gap, y0 + sum(rowh[:k // cols]) + (k // cols) * gap) for k, m in enumerate(ms)}
    shape = {"cols": cols, "rows": rows, "colw": colw, "rowh": rowh, "x": x0, "y": y0,
             "w": sum(colw) + gap * (cols - 1), "h": sum(rowh) + gap * max(0, rows - 1)}
    return pos, shape


def heads(b, g):
    """headings that fill the first row (column titles) or the first column (row titles)"""
    ms = [m for m in g["members"] if m in items(b)]; cols = max(1, min(g.get("cols") or 1, len(ms) or 1))
    text = lambda m: items(b)[m].get("type") == "text"
    h = {"row": len(ms) > cols and all(text(m) for m in ms[:cols]), "col": cols > 1 and len(ms) > cols and all(text(m) for m in ms[::cols])}
    return {k: v for k, v in h.items() if v}


def reflow(b, gid, at=None):
    """members to their cells; the record's rows and titles brought up to date"""
    g = table(b)[gid]; g["members"] = [m for m in dict.fromkeys(g["members"]) if m in items(b)]
    pos, shape = layout(b, g, at)
    for m, (x, y) in pos.items(): items(b)[m]["x"], items(b)[m]["y"] = round(x, 2), round(y, 2)
    g["rows"] = shape["rows"]
    h = heads(b, g)
    if h: g["head"] = h
    else: g.pop("head", None)
    return shape


def drop_small(b):
    for gid in [k for k, g in table(b).items() if len([m for m in g.get("members", []) if m in items(b)]) < 2]: del b["grids"][gid]


def leave(b, ids, keep=None):
    """ids out of the grids they are in; those grids close the gap from where they stood"""
    ids = set(ids)
    for gid, g in list(table(b).items()):
        if gid == keep or not ids & set(g["members"]): continue
        at = origin(b, g["members"]); g["members"] = [m for m in g["members"] if m not in ids]
        if len([m for m in g["members"] if m in items(b)]) >= 2: reflow(b, gid, at)
    drop_small(b)


def make(b, ids, cols=None, gap=GAP, order=True, gid=None):
    """a grid of these things (reading order unless order=False), laid out from their top left; cols None keeps the shape they have:
    as many columns as the longest row. The same set as a grid that exists updates that grid. Returns the grid's id"""
    ids = list(dict.fromkeys(placed(b, ids)))
    if len(ids) < 2: raise ValueError("сетке нужны хотя бы 2 вещи: картинки, карточки, заголовки")
    at = origin(b, ids); rws = rows_of(b, ids)
    if order: ids = [i for r in rws for i in r]
    cols = int(cols or max(len(r) for r in rws))
    gid = gid or next((k for k, g in table(b).items() if set(g["members"]) == set(ids)), None) or uid()
    leave(b, ids, keep=gid)
    b.setdefault("grids", {})[gid] = {"members": ids, "cols": max(1, cols), "rows": 0, "gap": gap, "cell": "fit"}
    reflow(b, gid, at)
    grouped = {m for g in (b.get("groups") or {}).values() for m in g.get("members", [])}
    regroup(b, [i for i in ids if i not in grouped])   # loose things (a new heading) join the frame they now stand in
    return gid


def regroup(b, ids):
    """as canvas.html regroup: a thing belongs to the smallest group frame holding its centre, or to none"""
    G = b.get("groups") or {}
    for i in ids:
        it = items(b).get(i)
        if not it or it.get("x") is None: continue
        x, y, w, h = box(it); cx, cy = x + w / 2, y + h / 2
        hit = sorted((g for g in G.values() if g.get("x") is not None and g["x"] <= cx <= g["x"] + g["w"] and g["y"] <= cy <= g["y"] + g["h"]),
                     key=lambda g: g["w"] * g["h"])
        if hit and i in hit[0].get("members", []) and sum(i in g.get("members", []) for g in G.values()) == 1: continue
        for g in G.values(): g["members"] = [m for m in g.get("members", []) if m != i]
        if hit: hit[0]["members"].append(i)


def put(b, gid, iid, index=None):
    """iid into a grid at a place of its member order (None: last), out of any other grid; the grid keeps its top left. iid joins the
    group frame of its cell, as a drop on the canvas does (a heading made by hy.py text was in no group, and a table came apart when
    its group was moved)"""
    g = table(b)[gid]; at = origin(b, g["members"])
    leave(b, [iid], keep=gid)
    ms = [m for m in g["members"] if m != iid]
    ms.insert(len(ms) if index is None else max(0, min(index, len(ms))), iid)
    g["members"] = ms; reflow(b, gid, at); regroup(b, [iid])


def zone(b, nid, ids, pad=None):
    """a note's dashed zone fitted around these things and the note itself, pad of air on every side (half the note's width, as
    hy.py block makes it): the zone is what the note is about, a picture by its centre (notelinks.py)"""
    n = items(b)[nid]; P = round(n["w"] / 2) if pad is None else pad
    nx, ny, nw, nh = box(n)
    R = [box(items(b)[i]) for i in ids if i in items(b) and items(b)[i].get("x") is not None] + [(nx, ny, nw, nh)]
    x0, y0 = min(r[0] for r in R) - P, min(r[1] for r in R) - P
    x1, y1 = max(r[0] + r[2] for r in R) + P, max(r[1] + r[3] for r in R) + P
    n["reach"] = {"l": round(nx - x0), "t": round(ny - y0), "r": round(x1 - nx - nw), "b": round(y1 - ny - nh)}
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def prune(b, before=None):
    """after any edit: members gone from the page leave their grid, which closes the gap from its old top left (before: {gid: (x, y)})"""
    for gid, g in list(table(b).items()):
        ms = [m for m in g.get("members", []) if m in items(b)]
        if ms == g.get("members"): continue
        g["members"] = ms
        if len(ms) >= 2: reflow(b, gid, (before or {}).get(gid))
    drop_small(b)


def origins(b):
    return {gid: origin(b, g.get("members", [])) for gid, g in table(b).items()}


def merged(out, ours, theirs):
    """a merged save (merge.py): a grid whose members came from both sides is laid out again, so two edits of one grid (a reorder here,
    an insert there) end as one tidy grid in the merged order; members gone from the page leave it"""
    for gid, g in list(table(out).items()):
        mine, other = (table(x).get(gid, {}).get("members") for x in (ours, theirs))
        if g.get("members") not in (mine, other) and len([m for m in g["members"] if m in items(out)]) >= 2: reflow(out, gid)
    prune(out)
    if "grids" in out and not out["grids"]: del out["grids"]


def made_rows(b, rows, cols, gap):
    """hy.py's block and arrange: each row of an argument, wrapped at cols, is a grid (they are laid out as one)"""
    ident = {id(it): i for i, it in items(b).items()}
    made = []
    for r in rows:
        ids = [ident[id(it)] for it in r if id(it) in ident]
        if len(ids) >= 2: made.append(make(b, ids, cols=min(cols, len(ids)), gap=gap, order=False))
    return f" · сетка {', '.join(made)}" if made else ""


def extend(b, have, new):
    """a sub-block that grows (hy.py block into= the same note): its new frames join the grid its frames are in"""
    gs = {of(b, i) for i in have}
    if len(gs) != 1 or None in gs or not new: return ""
    gid = gs.pop(); at = origin(b, table(b)[gid]["members"])
    table(b)[gid]["members"] += [i for i in new if i not in table(b)[gid]["members"]]; reflow(b, gid, at)
    return f" · в сетке {gid}"


# ---- names and tables ---------------------------------------------------------------------------------------------------------------
def name(b, i):
    it = items(b).get(i) or {}
    t = it.get("type")
    if not t: return (it.get("path") or i).rsplit("/", 1)[-1]
    if t == "text": return "«" + (it.get("text") or "").strip().split("\n")[0].lstrip("#").strip()[:40] + "»"
    f = notelinks.file_of(it)
    return f"{KIND.get(t, t)} {(it.get('name') or f.rstrip('/').split('/')[-2 if f.endswith('index.html') else -1] or i)}"


def cell(b, i): return f"{name(b, i)} [{i}]".replace("|", "/")


def group_of(b, gid):
    """the group the grid belongs to: the one holding most of its members"""
    ms = set(table(b)[gid]["members"]); best = None
    for k, g in (b.get("groups") or {}).items():
        n = len(ms & set(g.get("members", [])))
        if n and (best is None or n > best[0]): best = (n, k)
    return best[1] if best else None


def bbox(b, gid):
    _, s = layout(b, table(b)[gid]); return {"x": s["x"], "y": s["y"], "w": s["w"], "h": s["h"]}


def grid_rows(b, gid):
    g = table(b)[gid]; ms = [m for m in g["members"] if m in items(b)]; cols = max(1, min(g.get("cols") or 1, len(ms) or 1))
    return [ms[k:k + cols] for k in range(0, len(ms), cols)], cols


def num_labels(b, gid):
    """a choice grid's numbers (its "num", set by a layout pattern, patterns.py; ui/gridnum.js draws them on the cells): seq 1…N, rc A1 B1
    (the column title's first word and the row), row (the row), col (the place in its row); headings are not numbered"""
    g = table(b)[gid]; mode = g.get("num")
    if not mode: return {}
    rws, cols = grid_rows(b, gid); text = lambda m: items(b)[m].get("type") == "text"
    head = 1 if len(rws) > 1 and all(text(m) for m in rws[0]) else 0
    def letter(c):
        t = ((items(b)[rws[0][c]].get("text") or "").strip().replace("·", " ").split() or [""])[0] if head and c < len(rws[0]) else ""
        return t if t and len(t) <= 3 else "ABCDEFGH"[c] if c < 8 else ""
    out, n = {}, 0
    for ri, r in enumerate(rws[head:]):
        k = 0
        for c, m in enumerate(r):
            if text(m): continue
            n += 1; k += 1
            out[m] = f"{letter(c)}{ri + 1}" if mode == "rc" else str(ri + 1) if mode == "row" else str(k) if mode == "col" else str(n)
    return out


def md_table(b, gid, numbers=True):
    """a grid as a Markdown table: titles from a heading row or column; numbers=True adds the row and column numbers put uses (from 1);
    a choice grid's own numbers (num_labels) lead its cells: «№2 a.png [id]», the owner answers by them"""
    g = table(b)[gid]; rws, cols = grid_rows(b, gid); h = g.get("head", {}); nl = num_labels(b, gid)
    cl = lambda i: (f"№{nl[i]} " if i in nl else "") + cell(b, i)
    out = []
    pad = lambda r: r + [""] * (cols - len(r))
    if h.get("row"): head, body, first = [cl(i) for i in rws[0]], rws[1:], 2
    else: head, body, first = [str(c + 1) for c in range(cols)], rws, 1
    lead = ["#"] if numbers else []
    if not numbers and not h.get("row"): head = [" "] * cols   # the md view: no titles, an empty header row
    out.append("| " + " | ".join(lead + pad(head)) + " |")
    out.append("|" + "---|" * (len(lead) + cols))
    for k, r in enumerate(body):
        out.append("| " + " | ".join(([str(first + k)] if numbers else []) + pad([cl(i) for i in r])) + " |")
    return out


def title(b, gid):
    g = table(b)[gid]; _, cols = grid_rows(b, gid); gg = group_of(b, gid)
    where = f" в «{((b['groups'][gg].get('title') or 'группа').split(chr(10))[0])}»" if gg else ""
    return f"▦ сетка {cols} × {g.get('rows', 0)} [{gid}]{where}"


def show(b, group=None, pad="", area=None):
    """hy.py map: the grids of a group (group id) or those outside groups (None), as tables"""
    for gid in table(b):
        if group_of(b, gid) != group: continue
        if area and not _hit(bbox(b, gid), area): continue
        print(pad + title(b, gid) + ": ряды сверху вниз, колонки слева направо")
        for line in md_table(b, gid): print(pad + "  " + line)


def show_find(b, q):
    """hy.py find: a grid by its id, and where a found thing sits in its grid"""
    for gid in table(b):
        if q == gid: print(title(b, gid)); [print("  " + line) for line in md_table(b, gid)]
    for gid, g in table(b).items():
        rws, cols = grid_rows(b, gid)
        for k, i in enumerate(m for r in rws for m in r):
            it = items(b)[i]
            if q == i or (q and q.lower() in (it.get("path") or "").lower()):
                print(f"  {cell(b, i)}: в сетке {gid} ряд {k // cols + 1}, колонка {k % cols + 1}")


def _hit(a, r): return a["x"] < r["x"] + r["w"] and a["x"] + a["w"] > r["x"] and a["y"] < r["y"] + r["h"] and a["y"] + a["h"] > r["y"]


# ---- hy.py do -------------------------------------------------------------------------------------------------------------------------
HELP = """
  grid REF... [cols=N] [gap=24]       a grid of pictures, cards and headings (ids, a path glob, a group: its pictures and cards, a note's
                                      zone), as Arrange does on the board: map, find and md show it as a table; cols left out keeps the
                                      shape they have (as many columns as the longest row)
  put REF in GRID [at R,C] | put REF after|before REF | put REF out   into a grid without coordinates: GRID is a grid's id, a member or
                                      the group of one grid; R,C from 1 as in map's table; out leaves the grid, the others close the gap
  ungrid GRID|REF                     the grid record goes, everything stays where it is; a member: only it leaves
  zone NOTE REF... [pad=N]            the note's dashed zone around a grid (its id or a member), ids or a heading, pad of air (half the
                                      note's width): after a grid grew into a table, its pictures stay the note's
  a table: text items as headings in the first row and the first column, the corner too (text "…" fs=40; set REF size=1), then
                                      grid CORNER FIRST-COLUMN-TITLE cols=N and put the rest in reading order: head is set by itself
"""
_hy = {}


def _ids(b, ref):
    if ref in items(b): return [ref]
    if ref in table(b): return list(table(b)[ref]["members"])
    if ref in (b.get("groups") or {}): return [m for m in b["groups"][ref]["members"] if gridable(items(b).get(m)) and items(b)[m].get("type") != "text"]
    k, id_, _nm, _r = _hy["resolve"](b, ref)
    if k == "group": return [m for m in b["groups"][id_]["members"] if gridable(items(b).get(m)) and items(b)[m].get("type") != "text"]
    if k in ("heading",): return [id_]
    return _hy["pics_of"](b, ref)


def _item(b, ref):
    if ref in items(b): return ref
    got = _ids(b, ref)
    if len(got) != 1: raise SystemExit(f"«{ref}»: нужна одна вещь, нашел {len(got)}")
    return got[0]


def _grid(b, ref):
    if ref in table(b): return ref
    if ref in items(b):
        g = of(b, ref)
        if not g: raise SystemExit(f"{ref} не в сетке")
        return g
    k, id_, nm, _r = _hy["resolve"](b, ref)
    if k == "group":
        gs = [g for g in table(b) if group_of(b, g) == id_]
        if len(gs) == 1: return gs[0]
        raise SystemExit(f"в группе «{nm}» сеток {len(gs)}: назови сетку по id (hy.py map)")
    g = of(b, id_)
    if not g: raise SystemExit(f"«{nm}» не в сетке")
    return g


def op_grid(b, args, kv):
    if not args: raise SystemExit("grid REF... [cols=N]: что сложить в сетку")
    ids = [i for a in args for i in _ids(b, a)]
    try: gid = make(b, ids, cols=int(kv["cols"]) if "cols" in kv else None, gap=round(kv.get("gap", GAP)))
    except ValueError as e: raise SystemExit(f"grid: {e}")
    s = bbox(b, gid)
    return f"{title(b, gid)} x {round(s['x'])} y {round(s['y'])}, {round(s['w'])}×{round(s['h'])}"


def op_put(b, args, kv):
    if len(args) < 2: raise SystemExit("put REF in GRID [at R,C] | put REF after|before REF | put REF out")
    iid, how = _item(b, args[0]), args[1]
    if how == "out":
        g = of(b, iid)
        if not g: raise SystemExit(f"{iid} не в сетке")
        leave(b, [iid]); return f"put {cell(b, iid)} вне сетки {g}"
    if how in ("after", "before"):
        ref = _item(b, args[2]); gid = _grid(b, ref); ms = [m for m in table(b)[gid]["members"] if m != iid]
        put(b, gid, iid, ms.index(ref) + (1 if how == "after" else 0))
    elif how == "in":
        gid = _grid(b, args[2]); at = kv.get("at") or (args[4] if len(args) > 4 and args[3] == "at" else None)
        if at is None: put(b, gid, iid)
        else:
            r, c = (int(float(v)) for v in str(at).split(","))
            cols = max(1, int(table(b)[gid].get("cols") or 1)); put(b, gid, iid, (r - 1) * cols + (c - 1))
    else: raise SystemExit("put REF in GRID [at R,C] | after REF | before REF | out")
    rws, cols = grid_rows(b, gid); k = [m for r in rws for m in r].index(iid)
    return f"put {cell(b, iid)} в сетку {gid}: ряд {k // cols + 1}, колонка {k % cols + 1}"


def op_ungrid(b, args, kv):
    out = []
    for a in args:
        if a in table(b): del b["grids"][a]; out.append(a); continue
        if a in items(b) and of(b, a): g = of(b, a); leave(b, [a]); out.append(f"{a} из {g}"); continue
        gid = _grid(b, a); del b["grids"][gid]; out.append(gid)
    if "grids" in b and not b["grids"]: del b["grids"]
    return "ungrid " + ", ".join(out)


def op_zone(b, args, kv):
    if len(args) < 2: raise SystemExit("zone NOTE REF... [pad=N]: зона заметки вокруг сетки, кадров или заголовков")
    _k, nid, nm, _r = _hy["resolve"](b, args[0], {"note"})
    ids = []
    for a in args[1:]:   # a grid by its id or by any member (an id, a heading's text): the whole grid
        for i in (table(b)[a]["members"] if a in table(b) else _ids(b, a)): ids += table(b)[of(b, i)]["members"] if of(b, i) else [i]
    z = zone(b, nid, list(dict.fromkeys(ids)), round(kv["pad"]) if "pad" in kv else None)
    return f"zone «{nm[:30]}» вокруг {len(set(ids))}: x {round(z['x'])}..{round(z['x'] + z['w'])} y {round(z['y'])}..{round(z['y'] + z['h'])}"


def _keep(f):
    """every do command: members it took off the page leave their grids, which close the gap from where they stood"""
    def run(b, args, kv):
        at = origins(b); res = f(b, args, kv); prune(b, at)
        if "grids" in b and not b["grids"]: del b["grids"]
        return res
    return run


def register(OPS, resolve, pics_of):
    """hy.py: its do commands keep the grids right; grid, put and ungrid join them"""
    _hy.update(resolve=resolve, pics_of=pics_of)
    for k in list(OPS): OPS[k] = _keep(OPS[k])
    OPS.update(grid=_keep(op_grid), put=_keep(op_put), ungrid=_keep(op_ungrid), zone=_keep(op_zone))
