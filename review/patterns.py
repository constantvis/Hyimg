"""The board's layout patterns (owner 2026-10-09 on the page «Agent layouts»: «реализуй это»; its recommendation s5 «A + C now»): the
ways the owner wants an agent's work laid out, as building blocks an agent picks instead of improvising, plus a check after placing.

  hy.py do 'pattern variants "batch/*" into="Group" title="Light left"'      one prompt, many tries: a numbered grid, he answers 2, 7
  hy.py do 'pattern ab "a/*" "b/*" into="Group" a="current" b="new"'        two directions side by side, A1 B1 …: he answers A, B or A3
  hy.py do 'pattern timeline "2610…/*" phase="P2 · 1003" title="…"'          a batch under its phase on the timeline, numbered
  hy.py do 'pattern directions "d1/*" "d2/*" … into="Group"'                 a row per direction, its label first: D2, or D3·4
  hy.py do 'pattern docs a.html b.png … title="Editors · round 6" captions="layers;camera"'   a heading, cards 720 wide, a legend
  hy.py do 'pattern before-after "before/*" "after/*" into="Group"'          a two-column table, a row per pair: keep or revert
  hy.py do 'pattern moodboard "refs/*" into="Group" title="Cold studio light"'   references, 5 a row, no numbers: he hearts them
  hy.py do 'pattern review "batch/*" near="Group" title="Review P7"'         Picked (his ♥) · To decide · Rejected, he drags between
  hy.py do 'pattern flow "Brief" "Refs" "Generate" "Pick" labels="…;…"'     steps joined by arrows; a missing step: a new frame
  hy.py do 'pattern glossary html/glossary/*.html title="Glossary"'          term cards 640 wide, 6 a row
  hy.py do 'pattern mark "Name" REF' | 'pattern unmark REF'                  an invented layout tagged «new pattern» for the owner (s4)
  hy.py check --pattern [REF]                                                every pattern on the page against its own rules
  hy.py patterns                                                             this catalogue: when, how the owner answers, the command

The owner's fixed rules (a-rules) are checked after every do as hy.py's other problems are (problems(), only what is new is reported):
an agent's note is short (headings and captions, no long notes), a caption has 4 words at most, a row has 8 at most, a choice grid has
numbers, a group is a broad theme (not a batch's stamp), an agent's note is blue. Defaults the agent may change: cards 320 in batches
and 720 in docs, gaps 24 in a row and 80 between, headings 160 · 80 · 40.

A pattern leaves a light mark: "pattern": <name> on its note (or its group, or its heading), and a choice grid's "num": "seq" (1…N),
"rc" (A1, B1: the column's letter and the row), "row" (the row) or "col" (the place in the row): the board draws the numbers on the
cells (ui/patterns.js), map and md show them. hook() in connectors.py registers all this with hy.py."""
import fnmatch
import math
import re

import grids
import notelinks

GAP, BETWEEN, CARD, DOC = 24, 80, 320, 720
HEAD = {"section": 160, "heading": 80, "caption": 40}
NOTE_WORDS, CAPTION_WORDS, ROW_MAX = 30, 4, 8
STAMP = re.compile(r"\b\d{10}\b")
CHOICE = {"variants", "ab", "directions", "before-after", "timeline"}
CATALOGUE = [   # id, when, how the owner answers, the command; the order of the cards p01…p10
    ("variants", "одна идея, много попыток", "номерами: 2, 7", 'pattern variants "batch/*" into="Группа" title="Свет слева" [cols=3]'),
    ("ab", "два направления рядом", "A или B, или клетка: A3", 'pattern ab "a/*" "b/*" into="Группа" a="сейчас" b="новое"'),
    ("timeline", "работа фазами", "по фазе, номером", 'pattern timeline "2610…/*" phase="P2 · 1003" [tl=Таймлайн] title="…"'),
    ("directions", "несколько направлений", "D2 или D3·4", 'pattern directions "d1/*" "d2/*" "d3/*" into="Группа" [labels="D1,D2,D3"]'),
    ("docs", "объяснить интерфейс или систему", "номер и слово", 'pattern docs a.html b.png title="Editors · round 6" captions="слои;камера"'),
    ("before-after", "правка или исправление", "оставить или вернуть", 'pattern before-after "before/*" "after/*" into="Группа"'),
    ("moodboard", "собрать референсы", "♥ на любимых", 'pattern moodboard "refs/*" into="Группа" title="Холодный свет" [cols=5]'),
    ("review", "после партии", "перетаскивает между колонками", 'pattern review "batch/*" near="Группа" title="Разбор P7"'),
    ("flow", "конвейер шагов", "слово на шаге", 'pattern flow "Бриф" "Рефы" "Генерация" "Выбор" labels="…;…"'),
    ("glossary", "имена и термины", "переименовать, ? чтобы решить", 'pattern glossary html/glossary/*.html title="Термины"'),
]
ALIAS = {"variants-grid": "variants", "grid": "variants", "a/b": "ab", "abtest": "ab", "batches": "timeline", "rows": "directions",
         "documentation": "docs", "beforeafter": "before-after", "before/after": "before-after", "moods": "moodboard", "process": "flow",
         "terms": "glossary"}
_hy = {}


# ---- the pieces ---------------------------------------------------------------------------------------------------------------------
def words(t): return len(re.findall(r"[\w'’-]+", t or "", re.U))


def paths(masks):
    """library pictures by folder or glob, in natural order, each mask its own list"""
    lib = _hy["lib_paths"](); out = []
    for m in masks:
        got = sorted((p for p in lib if fnmatch.fnmatch(p, m) or fnmatch.fnmatch(p, m.rstrip("/") + "/*")), key=_hy["natkey"])
        if not got: raise SystemExit(f"в библиотеке нет файлов по «{m}»")
        out.append(got)
    return out


def card(path, w, sizes, html=None):
    """an item for a library file: a picture (its aspect from the server), or an .html page as the plugin's card"""
    if path.lower().endswith(".html"):
        if html == "html": return {"type": "html", "src": path, "vw": 1280, "ar": 1.6, "pics": [path], "w": w, "h": round(w / 1.6)}
        if html == "htmlframe": return {"type": "htmlframe", "src": path, "vw": 1440, "w": w, "h": round(w * 900 / 1440)}
        raise SystemExit("HTML-карточке нужен плагин «Dev Studio» или «Фреймы»: scripts/install_plugins.sh, потом ⇧⌘R")
    sw, sh = sizes.get(path) or [1, 1]
    return {"path": path, "w": w, "ar": sw / sh if sh else 1}


def heading(text, fs, size=None):
    t = {"type": "text", "text": text, "fs": fs, "size": 1 if fs <= HEAD["caption"] else 3 if fs <= HEAD["heading"] else 4,
         "w": round(fs * .56 * max(2, len(text))), "h": round(fs * 1.15)}
    if size is not None: t["size"] = size
    return t


def box(it): return notelinks.rect(it)


def bbox(rs):
    x0, y0 = min(r[0] for r in rs), min(r[1] for r in rs)
    return {"x": x0, "y": y0, "w": max(r[0] + r[2] for r in rs) - x0, "h": max(r[1] + r[3] for r in rs) - y0}


class Block:
    """a pattern's things laid out at the origin: rows of grids (each [items], cols, num), a heading over them, a legend right of them,
    a blue note on the left with its zone round the grids; then placed as hy.py block places (into= the group's note column, under its
    last block; near= free room; x= y=) and written to the board, grids recorded"""
    def __init__(self, w):
        self.w, self.rows, self.top, self.legend, self.note = w, [], None, None, None

    def grid(self, items, cols, num=None): self.rows.append((items, max(1, min(cols, len(items))), num)); return self

    def layout(self):
        tmp = {"items": {}}; y, gx = 0, 0
        if self.note: gx = self.w + round(self.w * .15)
        if self.top:
            self.top["x"], self.top["y"] = 0, 0; y = self.top["h"] + BETWEEN
        shapes = []
        for items, cols, _num in self.rows:
            ids = []
            for k, it in enumerate(items): it["x"], it["y"] = 0, 0; tmp["items"][f"_{len(tmp['items'])}"] = it; ids.append(f"_{len(tmp['items']) - 1}")
            pos, s = grids.layout(tmp, {"members": ids, "cols": cols, "gap": GAP}, at=(gx, y))
            for i, (px, py) in pos.items(): tmp["items"][i]["x"], tmp["items"][i]["y"] = round(px), round(py)
            shapes.append(s); y += s["h"] + GAP
        gb = bbox([(s["x"], s["y"], s["w"], s["h"]) for s in shapes])
        if self.legend:
            self.legend["x"], self.legend["y"] = round(gb["x"] + gb["w"] + BETWEEN), round(gb["y"])
        if self.note:
            n, P = self.note, round(self.w / 2)
            n.update(x=0, y=round(gb["y"]))
            n["reach"] = {"l": P, "t": P, "r": round(gb["x"] + gb["w"] - (n["x"] + n["w"]) + P), "b": round(max(0, gb["y"] + gb["h"] - (n["y"] + box(n)[3])) + P)}
        return gb

    def things(self):
        return [it for items, _c, _n in self.rows for it in items] + [t for t in (self.top, self.legend, self.note) if t]

    def place(self, b, kv, what, moving=()):
        """onto the board; returns (log, {"ids": [...], "grids": [...], "note": id, "box": placed box})"""
        g = _hy; self.layout(); w = self.w
        rs = [box(t) for t in self.things()] + ([tuple(g["zone_rect"](self.note).values())] if self.note else [])
        outer = bbox(rs); dx, dy, into = where(b, kv, outer, w, what, moving)
        made, ids, by = [], [], {}
        for it in self.things():
            it["x"], it["y"] = round(it["x"] + dx), round(it["y"] + dy)
            old = next((k for k, v in b["items"].items() if v is it), None)
            k = old or _hy["uid"]({"note": "n", "text": "t"}.get(it.get("type"), "i")); b["items"][k] = it; ids.append(k); by[id(it)] = k
            if it.get("path"): b.get("removed", {}).pop(it["path"], None)
        for items, cols, num in self.rows:
            mem = [by[id(it)] for it in items]
            if len(mem) >= 2:
                gid = grids.make(b, mem, cols=cols, order=False)
                if num: b["grids"][gid]["num"] = num
                made.append(gid)
        note = by.get(id(self.note)) if self.note else None
        placed = {"x": outer["x"] + dx, "y": outer["y"] + dy, "w": outer["w"], "h": outer["h"]}
        log = f"{what}: {len([i for i in ids if not b['items'][i].get('type')])} кадров" + (f", заметка {note}" if note else "") + (f", сетки {', '.join(made)}" if made else "")
        log += f" x {round(placed['x'])} y {round(placed['y'])}, {round(placed['w'])}×{round(placed['h'])}"
        if into:
            log += g["grow_into"](b, into, ids, placed, round(w * 1.5))
        elif kv.get("group"):
            pad = round(w * 1.5); gid = g["uid"]("g")
            for o in b["groups"].values(): o["members"] = [m for m in o["members"] if m not in ids]
            b["groups"][gid] = {"title": str(kv["group"]), "x": round(placed["x"] - pad), "y": round(placed["y"] - pad), "w": round(placed["w"] + 2 * pad),
                                "h": round(placed["h"] + 2 * pad), "members": ids}
            log += f" · группа «{kv['group']}» [{gid}]"
        else: grids.regroup(b, ids)
        return log, {"ids": ids, "grids": made, "note": note, "box": placed}


def note_for(kind, kv, w, default):
    title = str(kv.get("title") or default); more = str(kv.get("text") or "").replace("\\n", "\n").strip()
    n = {"type": "note", "text": f"# {title}" + (f"\n{more}" if more else ""), "w": w, "fs": w * _hy["NSIZE"][2], "size": 2, "h": 0, "color": "blue", "to": [],
         "pattern": kind}
    return n


def sizes_of(rows):
    ps = [p for r in rows for p in r if not p.lower().endswith(".html")]
    return _hy["api"]("/api/sizes", {"paths": ps})[1] if ps else {}


def html_kind():
    return "html" if _hy["plugin_name"]("dev") else "htmlframe" if _hy["plugin_name"]("frames") else None


def ncols(n): return n if n <= 4 else max(3, min(ROW_MAX, math.ceil(math.sqrt(n))))


# ---- the patterns ---------------------------------------------------------------------------------------------------------------
def p_variants(b, args, kv, kind="variants"):
    """p01 one prompt, many tries: one numbered grid per mask, under a note «# title»; p07 moodboard: 5 a row, no numbers"""
    if not args: raise SystemExit(f'pattern {kind} "папка/*" into="Группа" title="…" [cols=N]')
    title = str(kv.get("title") or args[0].rstrip("/*").rsplit("/", 1)[-1])
    if kv.get("into") and len(args) == 1:   # a batch still running: the same call adds its new frames to the same grid, the numbers go on
        old = _same_note(b, kv["into"], kind, title)[0]
        if old: return _hy["OPS"]["block"](b, args, {"into": kv["into"], "note": "# " + title}) + f" · {kind}: дописал в «{title}»"
    rows = paths(args); S = sizes_of(rows); w = round(kv.get("w", CARD)); blk = Block(w)
    blk.note = note_for(kind, {**kv, "title": title}, w, title)
    for r in rows:
        cols = int(kv.get("cols") or (5 if kind == "moodboard" else ncols(len(r))))
        blk.grid([card(p, w, S) for p in r], cols, None if kind == "moodboard" else "seq")
    log, got = blk.place(b, kv, f"pattern {kind}")
    return log


def p_ab(b, args, kv, kind="ab"):
    """p02 two (or more) directions side by side: a table, its titles «A · current» «B · new», a row per try; p06 before / after"""
    if len(args) < 2: raise SystemExit(f'pattern {kind} "a/*" "b/*" into="Группа"' + (' a="сейчас" b="новое"' if kind == "ab" else ""))
    rows = paths(args); S = sizes_of(rows); w = round(kv.get("w", CARD)); n = min(len(r) for r in rows)
    if any(len(r) != n for r in rows): rows = [r[:n] for r in rows]   # a table has no holes: the shortest side sets the rows
    letters = "ABCDEFGH"
    if kind == "before-after": titles = [str(kv.get("before", "До")), str(kv.get("after", "После"))] + [f"{k + 3}" for k in range(len(rows) - 2)]
    else: titles = [f"{letters[k]} · {kv[letters[k].lower()]}" if kv.get(letters[k].lower()) else letters[k] for k in range(len(rows))]
    cells = [heading(t, HEAD["caption"]) for t in titles] + [card(rows[c][k], w, S) for k in range(n) for c in range(len(rows))]
    title = str(kv.get("title") or ("A / B" if kind == "ab" else "До / после"))
    if kv.get("into"):   # a batch still running: its new pairs join the same table as new rows
        old = _same_note(b, kv["into"], kind, title)
        if old[0]: return _more_rows(b, old, kv, [[p for p in r] for r in rows], w, S) + f" · {kind}: дописал в «{title}»"
    blk = Block(w); blk.note = note_for(kind, {**kv, "title": title}, w, title)
    blk.grid(cells, len(rows), "rc" if kind == "ab" else "row")
    return blk.place(b, kv, f"pattern {kind}")[0] + (f" · по {n} в столбце, лишние не положил" if any(len(r) > n for r in paths(args)) else "")


def _same_note(b, into, kind, title):
    gid = _hy["resolve"](b, str(into), {"group"})[1]
    return next((m for m in b["groups"][gid]["members"] if (b["items"].get(m) or {}).get("pattern") == kind
                 and notelinks.first_line(b["items"][m].get("text")) == title), None), gid


def _more_rows(b, found, kv, rows, w, S):
    """the table under this note gets the pairs whose pictures are not on the page yet, as rows after its last; zone and frame grow"""
    nid, gid = found; gs = zone_grids(b, nid)
    if not gs: raise SystemExit("у этой заметки нет таблицы: положи заново с другим title")
    tid = gs[0]
    on = {it.get("path") for it in b["items"].values()}
    pairs = [k for k in range(min(len(r) for r in rows)) if not all(r[k] in on for r in rows)]
    if not pairs: return "новых пар нет"
    new = []
    for k in pairs:
        for r in rows:
            it = card(r[k], w, S); it.update(x=-1e6, y=-1e6); i = _hy["uid"]("i"); b["items"][i] = it; new.append(i)
    g = grids.table(b)[tid]; at = grids.origin(b, g["members"]); g["members"] += new; grids.reflow(b, tid, at)
    z = grids.zone(b, nid, g["members"])
    return f"+{len(pairs)} пар в таблицу {tid}" + _hy["grow_into"](b, gid, new, z, round(w * 1.5))


def p_directions(b, args, kv):
    """p04 several directions: a row each, its label (D1, D2 …) first, the cells numbered in the row: he answers D2 or D3·4"""
    if not args: raise SystemExit('pattern directions "d1/*" "d2/*" … into="Группа" [labels="D1,D2"]')
    rows = paths(args); S = sizes_of(rows); w = round(kv.get("w", CARD))
    labels = [s.strip() for s in str(kv.get("labels") or "").split(",") if s.strip()] or [f"D{k + 1}" for k in range(len(rows))]
    if len(labels) < len(rows): labels += [f"D{k + 1}" for k in range(len(labels), len(rows))]
    blk = Block(w); blk.note = note_for("directions", kv, w, "Направления")
    for lab, r in zip(labels, rows):
        r = r[:ROW_MAX]
        blk.grid([heading(lab, HEAD["heading"])] + [card(p, w, S) for p in r], len(r) + 1, "col")
    return blk.place(b, kv, "pattern directions")[0]


def p_timeline(b, args, kv):
    """p03 work in phases: the batch under its phase's dot on the timeline (a new dot right of the last phase's batch), numbered"""
    if not args or not kv.get("phase"): raise SystemExit('pattern timeline "папка/*" phase="P2 · 1003" [tl=Таймлайн] [title=…]')
    I = b["items"]; tls = [k for k, it in I.items() if it.get("type") == "timeline"]
    if kv.get("tl"): tl = _hy["resolve"](b, str(kv["tl"]), {"timeline", "dot"})[1].split("/")[0]
    elif len(tls) == 1: tl = tls[0]
    else: raise SystemExit("pattern timeline: " + ("на странице нет таймлайна: его ставит владелец (L) или назови tl=" if not tls else
                                                    f"таймлайнов {len(tls)}, назови tl=<подпись или id>"))
    t = I[tl]; phase = str(kv["phase"]); norm = _hy["norm"]
    dot = next((p for p in t["points"] if norm(p.get("text")) == norm(phase)), None)
    if dot is None:   # a new phase: right of everything under the timeline's last phase
        span = [box(it) for k, it in I.items() if k != tl and it.get("x") is not None and box(it)[1] > t["y"] and box(it)[0] >= t["x"] - 1]
        last = max([t["x"] + max((p["t"] for p in t["points"]), default=0)] + [r[0] + r[2] + BETWEEN * 6 for r in span])
        _hy["OPS"]["point"](b, [tl, phase], {"x": last}); dot = next(p for p in t["points"] if norm(p.get("text")) == norm(phase))
    kv = {**kv, "near": f"{tl}/{dot['id']}", "side": "below"}
    kv.setdefault("title", phase)
    return p_variants(b, args, kv, "timeline") + f" · под фазой «{phase}»"


def p_docs(b, args, kv, kind="docs"):
    """p05 documentation: a heading (160), the cards (720) in a numbered grid, a legend «1 layers, 2 camera» to its right; p10 glossary:
    term cards 640 wide, 6 a row, no numbers"""
    if not args: raise SystemExit(f'pattern {kind} ФАЙЛЫ… title="…"' + (' captions="слои;камера"' if kind == "docs" else ""))
    rows = paths(args); files = [p for r in rows for p in r]; S = sizes_of([files])
    w = round(kv.get("w", DOC if kind == "docs" else 640)); hk = html_kind() if any(p.lower().endswith(".html") for p in files) else None
    cols = int(kv.get("cols") or (min(3, len(files)) if kind == "docs" else min(6, len(files))))
    blk = Block(w); blk.top = heading(str(kv.get("title") or ("Документация" if kind == "docs" else "Термины")), HEAD["section"], 4)
    blk.top["pattern"] = kind
    blk.grid([card(p, w, S, hk) for p in files], cols, "seq" if kind == "docs" else None)
    caps = [c.strip() for c in str(kv.get("captions") or "").split(";") if c.strip()]
    if caps: blk.legend = heading("\n".join(f"{k + 1} {c}" for k, c in enumerate(caps)), HEAD["caption"])
    if blk.legend: blk.legend["h"] = round(HEAD["caption"] * 1.3 * len(caps)); blk.legend["w"] = round(HEAD["caption"] * .56 * max(len(c) + 2 for c in caps))
    return blk.place(b, kv, f"pattern {kind}")[0]


def where(b, kv, outer, w, what, moving=()):
    """how far to move a block laid out at outer: into= the group's note column under its last block (as hy.py block into=), near= free
    room beside a thing (what moves is not in its own way), x= y= its top left. Returns (dx, dy, the group of into= or None)"""
    g = _hy
    if "into" in kv:
        into = g["resolve"](b, str(kv["into"]), {"group"})[1]; G = b["groups"][into]
        inside_ = [m for m in G["members"] if m in b["items"] and m not in moving]
        own = [g["rect"](b, m) for m in inside_]
        zs = [g["zone_rect"](b["items"][m]) for m in inside_ if b["items"][m].get("reach")]
        left = min((r["x"] for r in own), default=G["x"] + round(w * 1.5))
        bottom = max((r["y"] + r["h"] for r in own + zs), default=G["y"] + round(w * .5))
        return left - outer["x"], bottom + w - outer["y"], into
    if "near" in kv:
        keep = {i: b["items"].pop(i) for i in moving if i in b["items"]}
        try:
            n = str(kv["near"]); r = g["rect"](b, n) if n in b["items"] or n in b["groups"] else g["resolve"](b, n)[3]
            spot = g["free_spot"](b, r, outer, kv.get("side", "right"), round(w * 1.5))
        finally: b["items"].update(keep)
        return spot["x"] - outer["x"], spot["y"] - outer["y"], None
    if "x" in kv and "y" in kv: return kv["x"] - outer["x"], kv["y"] - outer["y"], None
    raise SystemExit(f"{what}: укажи into=<группа> (подгруппой в тему), near=<что рядом> или x= и y=")


def p_review(b, args, kv):
    """p08 after a batch: three columns, Picked (the pictures with his ♥), To decide (the rest), Rejected (empty), each a caption over a
    grid 2 a row, in one group; the pictures already on the page move (as arrange), the others come from the library. He drags
    between the columns (a drop on a grid takes its cell)"""
    if not args: raise SystemExit('pattern review "папка/*" | ID | "Группа"… near="Группа" title="Разбор P7"')
    I = b["items"]; on, new = [], []
    for a in args:
        try: on += [i for i in _hy["pics_of"](b, a) if i not in on]
        except SystemExit: new += [p for r in paths([a]) for p in r]
    fav = {i.get("path") for i in _hy["api"]("/api/items?all=1")[1] if (i.get("feedback") or {}).get("fav")}
    S = sizes_of([new]); w = round(kv.get("w", CARD))
    things = [I[i] for i in on] + [card(p, w, S) for p in new]
    for it in things: it["w"] = w
    cols = [(str(kv.get("picked", "Picked")), [it for it in things if it.get("path") in fav]),
            (str(kv.get("decide", "To decide")), [it for it in things if it.get("path") not in fav]), (str(kv.get("rejected", "Rejected")), [])]
    grids.leave(b, on)
    tmp, x, plan = {"items": {}}, 0, []
    for title, its in cols:   # a caption, then a grid of 2 a row under it
        cap = heading(title, HEAD["heading"]); cap.update(x=x, y=0, pattern_col=title); y0 = cap["h"] + GAP; ids = []
        for k, it in enumerate(its): tmp["items"][f"_{id(it)}"] = it; it["x"], it["y"] = x, y0; ids.append(f"_{id(it)}")
        if ids:
            pos, _s = grids.layout(tmp, {"members": ids, "cols": 2, "gap": GAP}, at=(x, y0))
            for i, (px, py) in pos.items(): tmp["items"][i]["x"], tmp["items"][i]["y"] = round(px), round(py)
        plan.append((cap, its)); x += 2 * w + GAP + BETWEEN * 2
    allr = [box(c) for c, _ in plan] + [box(it) for _c, its in plan for it in its]
    outer = bbox(allr); outer["w"] = max(outer["w"], x - BETWEEN * 2)
    dx, dy, into = where(b, kv, outer, w, "pattern review", on)
    ids, made = [], []
    for cap, its in plan:
        mem = []
        for it in [cap] + its:
            it["x"], it["y"] = round(it["x"] + dx), round(it["y"] + dy)
            k = next((i for i, v in I.items() if v is it), None) or _hy["uid"]("t" if it is cap else "i"); I[k] = it; mem.append(k)
            if it.get("path"): b.get("removed", {}).pop(it["path"], None)
        if len(mem) >= 3: made.append(grids.make(b, mem[1:], cols=2, order=False))
        ids += mem
    for o in b["groups"].values(): o["members"] = [m for m in o["members"] if m not in ids]
    placed = {"x": outer["x"] + dx, "y": outer["y"] + dy, "w": outer["w"], "h": outer["h"]}
    title = str(kv.get("title") or "Разбор"); n = len(cols[0][1])
    if into:
        b["groups"][into]["pattern"] = b["groups"][into].get("pattern") or "review"
        return f"pattern review: ♥ {n}, решить {len(cols[1][1])}" + _hy["grow_into"](b, into, ids, placed, round(w * 1.5))
    pad = round(w * 1.5); gid = _hy["uid"]("g")
    b["groups"][gid] = {"title": title, "x": round(placed["x"] - pad), "y": round(placed["y"] - pad), "w": round(placed["w"] + 2 * pad),
                        "h": round(placed["h"] + 2 * pad), "members": ids, "pattern": "review"}
    return f"pattern review «{title}» [{gid}]: ♥ {n}, решить {len(cols[1][1])}, отказ 0, сетки {', '.join(made) or 'нет'}"


def p_flow(b, args, kv):
    """p09 a pipeline of steps: each step a thing on the page (by id, name or file) or, when missing, a new frame; joined by arrows
    (a Mermaid flowchart through structure, so the steps found by name are the same ones structure finds)"""
    import connectors
    if len(args) < 2: raise SystemExit('pattern flow "Шаг 1" "Шаг 2" … [labels="a;b"] [style=dashed|dotted] [color=blue] [near=REF]')
    labs = [s.strip() for s in str(kv.get("labels") or "").split(";")]
    st, col = str(kv.get("style") or "solid"), str(kv.get("color") or "grey")
    arrow = "==>" if col == "blue" else "-.->" if st in ("dashed", "dotted") else "-->"
    text = ["flowchart " + ("TB" if str(kv.get("dir", "")).upper() in ("TB", "TD") else "LR")]
    for k, a in enumerate(args):
        try: text.append(f"  %% hyimg: s{k} = {connectors.ref(b, a)}")
        except SystemExit: pass
    q = lambda s: '"' + s.replace('"', "'") + '"'
    for k in range(len(args) - 1):
        lab = labs[k] if k < len(labs) else ""
        text.append(f"  s{k}[{q(args[k])}] {arrow}" + (f"|{q(lab)}|" if lab else "") + f" s{k + 1}[{q(args[k + 1])}]")
        if st == "dotted": text.append(f"  linkStyle {k} stroke-dasharray:2 6")
    rest = {k: v for k, v in kv.items() if k in ("near", "side", "x", "y")}
    out = connectors.op_structure(b, [], {**rest, "text": "\n".join(text), "keep": 1})
    return out.replace("structure:", "pattern flow:")


# ---- the new pattern loop (s4: invent → mark → the owner keeps it or says no → adopt) ---------------------------------------------
def p_mark(b, args, kv):
    """a layout the agent invented: «new pattern · Name» over it and "pattern": "new:Name" on it, until the owner answers"""
    if len(args) < 2: raise SystemExit('pattern mark "Название" REF  (REF: группа, заметка или заголовок нового расклада)')
    import connectors
    nm, i = args[0], connectors.ref(b, args[1]); tgt = b["groups"].get(i) or b["items"][i]
    tgt["pattern"] = f"new:{nm}"; r = _hy["rect"](b, i)
    t = heading(f"new pattern · {nm}", HEAD["caption"]); t.update(x=round(r["x"]), y=round(r["y"] - t["h"] - GAP), pattern_tag=i)
    k = _hy["uid"]("t"); b["items"][k] = t
    return f"pattern mark «{nm}» на {connectors.name(b, i)}, метка [{k}]: спроси владельца, оставить ли расклад (скилл hyimg-board, «Новый шаблон»)"


def p_unmark(b, args, kv):
    import connectors
    if not args: raise SystemExit("pattern unmark REF")
    i = connectors.ref(b, args[0]); tgt = b["groups"].get(i) or b["items"][i]; was = tgt.pop("pattern", None)
    tags = [k for k, it in b["items"].items() if it.get("pattern_tag") == i]
    for k in tags:
        del b["items"][k]
        for g in b["groups"].values(): g["members"] = [m for m in g["members"] if m != k]
    return f"pattern unmark {connectors.name(b, i)}: было {was or 'без отметки'}, меток убрано {len(tags)}"


RUN = {"variants": p_variants, "moodboard": lambda b, a, kv: p_variants(b, a, kv, "moodboard"), "ab": p_ab,
       "before-after": lambda b, a, kv: p_ab(b, a, kv, "before-after"), "directions": p_directions, "timeline": p_timeline, "docs": p_docs,
       "glossary": lambda b, a, kv: p_docs(b, a, kv, "glossary"), "review": p_review, "flow": p_flow, "mark": p_mark, "unmark": p_unmark}


def op_pattern(b, args, kv):
    if not args: raise SystemExit("pattern ИМЯ …: " + ", ".join(RUN) + "  (hy.py patterns: когда какой)")
    k = ALIAS.get(args[0].lower(), args[0].lower())
    if k not in RUN: raise SystemExit(f"нет шаблона «{args[0]}»: {', '.join(RUN)}. Свой расклад: собери его и отметь pattern mark")
    return RUN[k](b, args[1:], kv)


# ---- the checklist after placing (s3 «C», s5 «Now: C») ---------------------------------------------------------------------------
def agent_note(it):
    by = it.get("by") if isinstance(it.get("by"), dict) else {}
    return it.get("color") == "blue" or (by.get("via") not in (None, "", "app", "owner"))


def rules(b):
    """the owner's fixed rules, keyed as hy.py's problems() so a do reports only what it made new"""
    I, G, out = b.get("items") or {}, b.get("groups") or {}, {}
    for k, it in I.items():
        t = it.get("type")
        if t == "note" and agent_note(it) and words(it.get("text")) > NOTE_WORDS:
            out[("words", k)] = (f"заметка «{notelinks.first_line(it.get('text'))[:30]}» длинная: {words(it.get('text'))} слов"
                                 f" (до {NOTE_WORDS}: заголовок и подпись, подробности в json кадра или в чат)")
        if t == "note" and isinstance(it.get("by"), dict) and it["by"].get("via") not in (None, "", "app") and it.get("color") not in (None, "blue"):
            out[("blue", k)] = f"заметка агента «{notelinks.first_line(it.get('text'))[:30]}» не синяя: у агента синие, у владельца желтые"
        if t == "text" and (it.get("fs") or 0) < HEAD["section"] and not it.get("pattern_tag") and words(it.get("text")) > CAPTION_WORDS \
                and "\n" not in (it.get("text") or "").strip():
            out[("caption", k)] = f"подпись «{(it.get('text') or '')[:40]}» длиннее {CAPTION_WORDS} слов"
    for gid, g in grids.table(b).items():
        ms = [m for m in g.get("members", []) if m in I]; cols = min(int(g.get("cols") or 1), len(ms) or 1)
        lead = 1 if g.get("head", {}).get("col") or (ms and I[ms[0]].get("type") == "text" and g.get("num") == "col") else 0
        if cols - lead > ROW_MAX: out[("wide", gid)] = f"сетка {gid}: {cols - lead} в ряд, больше {ROW_MAX}"
    for k, it in list(I.items()) + list(G.items()):
        p = it.get("pattern")
        if p in CHOICE and not _numbered(b, k): out[("nonum", k)] = f"выбор «{_title(b, k)}» ({p}) без номеров на клетках: владелец отвечает номером"
    for gid, g in G.items():
        if STAMP.search(g.get("title") or "") and len([m for m in g.get("members", []) if (I.get(m) or {}).get("type") == "note"]) <= 1:
            out[("stamp", gid)] = f"группа «{notelinks.first_line(g.get('title'))[:40]}» на одну партию: партия ложится подгруппой в тему (block into=)"
    return out


NAMES = {"words": "длинные заметки", "blue": "заметки агента не синие", "caption": "длинные подписи", "wide": "больше 8 в ряд",
         "nonum": "выбор без номеров", "stamp": "группа на партию"}


def _title(b, k):
    it = (b.get("items") or {}).get(k) or (b.get("groups") or {}).get(k) or {}
    return notelinks.first_line(it.get("text") or it.get("title"))[:40]


def zone_grids(b, k):
    """the grids a pattern's note (its zone) or group (its members) holds"""
    I, G = b["items"], b["groups"]
    if k in G: S = set(G[k]["members"])
    else:
        z = _hy["zone_rect"](I[k]) if I[k].get("reach") else None
        if not z: return []
        S = {i for i, it in I.items() if it.get("x") is not None and z["x"] <= box(it)[0] + box(it)[2] / 2 <= z["x"] + z["w"]
             and z["y"] <= box(it)[1] + box(it)[3] / 2 <= z["y"] + z["h"]}
    return [gid for gid, g in grids.table(b).items() if set(g.get("members", [])) & S]


def _numbered(b, k):
    gs = zone_grids(b, k); return bool(gs) and all(grids.table(b)[g].get("num") for g in gs)


def check_one(b, k):
    """(ok, words) for one pattern on the page"""
    I, G = b["items"], b["groups"]; it = I.get(k) or G.get(k); p = it["pattern"]
    if str(p).startswith("new:"): return None, f"новый расклад «{p[4:]}»: ждет ответа владельца (оставить → в библиотеку, нет → pattern unmark)"
    bad, gs = [], zone_grids(b, k)
    T = grids.table(b)
    if p in ("variants", "moodboard", "timeline", "ab", "before-after", "directions", "docs", "glossary") and not gs and p not in ("docs", "glossary"):
        bad.append("нет сетки в зоне заметки")
    if p in CHOICE and gs and not all(T[g].get("num") for g in gs): bad.append("нет номеров")
    for g in gs:
        ms = [m for m in T[g]["members"] if m in I]; cols = min(int(T[g].get("cols") or 1), len(ms) or 1)
        lim = 6 if p == "glossary" else ROW_MAX + (1 if p == "directions" else 0)
        if cols > lim: bad.append(f"сетка {g}: {cols} в ряд, больше {lim}")
    if p in ("ab", "before-after") and gs and not all(T[g].get("head", {}).get("row") for g in gs): bad.append("у таблицы нет строки заголовков")
    if p == "directions" and gs and not all((I.get(T[g]["members"][0]) or {}).get("type") == "text" for g in gs): bad.append("ряд без подписи направления")
    if p == "timeline":
        tl = [t for t in I.values() if t.get("type") == "timeline"]; x = it.get("x", 0) + it.get("w", 0)
        if not any(t["x"] + q["t"] - 2 * CARD <= x <= t["x"] + q["t"] + 2 * CARD and t["y"] < it["y"] for t in tl for q in t["points"]):
            bad.append("не под точкой своей фазы на таймлайне")
    if p == "review":
        cols_ = [m for m in (it.get("members") or []) if (I.get(m) or {}).get("pattern_col")]
        if len(cols_) != 3: bad.append(f"колонок {len(cols_)}, нужно 3: Picked, To decide, Rejected")
    if p in ("docs", "glossary") and it.get("type") == "text" and words(it.get("text")) > 6: bad.append("заголовок длинный")
    over = [m for kk, m in _hy["problems0"](b).items() if kk[0] == "over" and set(kk[1:]) & set(_area_ids(b, k))]
    if over: bad.append(f"кадры друг на друге: {len(over)}")
    return not bad, "; ".join(bad) or "по правилам"


def _area_ids(b, k):
    gs = zone_grids(b, k); return [m for g in gs for m in grids.table(b)[g]["members"]] + ([*b["groups"][k]["members"]] if k in b["groups"] else [])


def check_patterns(b, ref=None):
    I, G = b["items"], b["groups"]; ks = [k for k, it in list(I.items()) + list(G.items()) if it.get("pattern")]
    if ref:
        import connectors
        i = connectors.ref(b, ref); keep = connectors.inside(b, i) if i in G else {i}
        ks = [k for k in ks if k in keep]
    if not ks: print("шаблонов на странице нет (hy.py patterns: какие есть)")
    for k in ks:
        ok, why = check_one(b, k)
        print(f"{'✓' if ok else '?' if ok is None else '⚠'} {(I.get(k) or G.get(k))['pattern']} «{_title(b, k)}» [{k}]: {why}")
    R = rules(b)
    if R:
        by = {}
        for kk, m in R.items(): by.setdefault(kk[0], []).append(m)
        print("правила владельца:")
        for kind, L in by.items(): print(f"  {NAMES[kind]}: {len(L)}"); [print("    " + m) for m in L[:10]]
    else: print("правила владельца: все соблюдены")


def catalogue():
    out = ["Шаблоны раскладки (карточки «Agent layouts» p01–p10): выбери по задаче, не придумывай. Команда внутри hy.py do."]
    for k, (pid, when, ans, cmd) in enumerate(CATALOGUE, 1):
        out.append(f"{k:>2}. {pid:<13} когда: {when}; владелец отвечает: {ans}\n      {cmd}")
    out.append("Свой расклад: собери, потом pattern mark \"Название\" <группа|заметка> и спроси владельца; после проверки: hy.py check --pattern")
    return "\n".join(out)


def agent_brief(hy):
    """the /agent guide's section (server.py agent_page)"""
    return ["## Шаблоны раскладки", "",
            "Раскладку не придумывай: выбери шаблон под задачу (владелец 2026-10-09, «Agent layouts»). Каталог: `" + hy + " patterns`.",
            "".join(f"`{pid}` ({when}), " for pid, when, _a, _c in CATALOGUE).rstrip(", ") + ".",
            f"Пример: `{hy} do 'pattern variants \"<папка>/*\" into=\"<группа>\" title=\"Свет слева\"'`, потом `{hy} check --pattern`."
            " Своего шаблона нет: собери расклад и отметь `pattern mark \"Название\" <группа>`, спроси владельца.",
            f"Стрелки между любыми вещами: `{hy} do 'connect A B label=\"бриф для\" style=dashed'`, процесс из Mermaid:"
            f" `{hy} structure flow.mmd near=<что рядом>`, обратно `{hy} mermaid [группа]`, коротко `{hy} map --graph`.", ""]


def register(g):
    _hy.update({k: g[k] for k in ("resolve", "rect", "free_spot", "uid", "norm", "api", "lib_paths", "natkey", "zone_rect", "grow_into",
                                   "NSIZE", "plugin_name", "pics_of", "OPS")})
    g["OPS"]["pattern"] = op_pattern
    problems0, cmd_check = g["problems"], g["cmd_check"]
    _hy["problems0"] = problems0
    g["problems"] = lambda b: {**problems0(b), **rules(b)}

    def check_(b, ref):
        if ref and ref.split()[0] == "--pattern":
            return check_patterns(b, ref.split(None, 1)[1] if len(ref.split()) > 1 else None)
        g["problems"] = problems0
        try: cmd_check(b, ref)
        finally: g["problems"] = lambda bb: {**problems0(bb), **rules(bb)}
        R = rules(b)
        if ref:
            import connectors
            i = connectors.ref(b, ref); keep = connectors.inside(b, i) if i in b["groups"] else {i}
            R = {k: m for k, m in R.items() if set(k[1:]) & keep}
        by = {}
        for k, m in R.items(): by.setdefault(k[0], []).append(m)
        for kind, L in by.items(): print(f"{NAMES[kind]}: {len(L)}"); print("\n".join("  " + m for m in L[:15]))
    g["cmd_check"] = check_
