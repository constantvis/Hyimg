"""pattern table: things already on the page laid out as a table by two keys (owner 2026-10-11 on «Workflows» › «Batch 2 · макеты для
генерации»: «Я ожидаю, что тут может быть табличная расстановка, чтобы related объекты можно было сравнивать ... чтобы были в одном
column»). An agent had laid 15 series of a pipeline as blocks of 7 a row, and v1 and v2 of one step stood in different rows and columns.

  hy.py do 'pattern table <group|id,id|mask> rows=note cols="Оригинал=^added/;Поза=pose;Макет=mockup;Маска макета=mockup.*mask"' --dry

rows=, cols= name a key each:
  note       the note whose dashed zone holds the card's centre (else the last note above it): the row's title is that note, moved
  folder     the file's folder; the title a heading (or the note whose zone holds most of that folder)
  step       the pipeline step in the file name: -02-, -03a- → «02 pose»; a file with no step is «00 исходник»
  "T=re;…"   an ordered list of titles with a pattern each, matched against the path in lower case; the longest match wins, so
             «mockup.*mask» takes B2-05-mockup-mask.png from «mockup»; titles no card matched are left out
Defaults rows=note cols=step; a second run on the same group takes the keys of the first, so a batch that goes on is laid out again.

The table: a header row of column titles (plain headings), every column one width (the widest card, or w=) with gap= between, every row
as tall as its tallest cell plus between= (half a card) to the next, the row's title on the left, the cards of one row × column stacked
in that cell in name order (B2-06-crops, then B2-06-crops-v2). No column limit: as many columns as there are keys. The cards keep their
ids, groups, notes and arrows; the grids they were in are dropped (a grid has no stacks and no holes); each note's zone is fitted to its
row; the group frame holds the table (grows, pushing what stands right of and under it; shrinks to it when it holds only the table).
check --pattern: every card in its column (x of its title), nothing on top of anything, nothing out of the frame."""
import collections
import os
import re

import grids
import notelinks
import patterns

GAP = 24
STEP = re.compile(r"-(\d{2})[a-z]?(?=[-_.]|$)")
NAMED = ("note", "folder", "step")


def _h(): return patterns._hy


def box(it): return notelinks.rect(it)


def stem(p): return os.path.splitext(os.path.basename(p or ""))[0]


def spec_list(s):
    """«Title=re;Title=re» -> [(title, regex)]"""
    out = []
    for part in [p for p in str(s).split(";") if p.strip()]:
        if "=" not in part: raise SystemExit(f"pattern table: «{part}» без «=»: пиши Название=шаблон;Название=шаблон")
        t, rx = part.split("=", 1)
        try: out.append((t.strip(), re.compile(rx.strip(), re.I)))
        except re.error as e: raise SystemExit(f"pattern table: шаблон «{rx}» не разобрать: {e}")
    if not out: raise SystemExit("pattern table: пустой список колонок")
    return out


def name_of(b, i):
    it = b["items"][i]; return (it.get("path") or notelinks.file_of(it) or it.get("name") or i).lower()


def by_list(b, ids, spec):
    L = spec_list(spec); key = {}
    for i in ids:
        s, best = name_of(b, i), None
        for k, (_t, rx) in enumerate(L):
            m = rx.search(s); n = len(m.group(0)) if m else -1
            if m and (best is None or n > best[1]): best = (k, n)
        if best: key[i] = L[best[0]][0]
    return key, [t for t, _rx in L]


def by_step(b, ids):
    key, words = {}, collections.defaultdict(collections.Counter)
    for i in ids:
        s = stem(name_of(b, i)); m = ([None] + list(STEP.finditer(s)))[-1]; n = m.group(1) if m else "00"   # the last: a series may carry digits
        key[i] = n
        w = re.match(r"[-_]([a-z]+)", s[m.end():]) if m else None
        if w: words[n][w.group(1)] += 1
    titles = {n: f"{n} {words[n].most_common(1)[0][0]}" if words[n] else ("00 исходник" if n == "00" else n) for n in set(key.values())}
    return {i: titles[n] for i, n in key.items()}, [titles[n] for n in sorted(titles)]


def by_folder(b, ids):
    key = {i: os.path.basename(os.path.dirname(name_of(b, i))) or "—" for i in ids}
    return key, sorted(set(key.values()), key=_h()["natkey"])


def notes_of(b, ids, gid):
    """the notes that may title rows: the group's, else those whose zone holds one of the cards"""
    I = b["items"]
    if gid: return [m for m in b["groups"][gid]["members"] if (I.get(m) or {}).get("type") == "note"]
    cs = [box(I[i]) for i in ids]
    return [k for k, it in I.items() if it.get("type") == "note" and it.get("reach") and any(_inside(c, _h()["zone_rect"](it)) for c in cs)]


def _inside(r, z): return z and z["x"] <= r[0] + r[2] / 2 <= z["x"] + z["w"] and z["y"] <= r[1] + r[3] / 2 <= z["y"] + z["h"]


def by_note(b, ids, notes):
    """a card's note: the smallest zone holding its centre, else the last note above it (a card left under its block)"""
    I = b["items"]
    if not notes: raise SystemExit("pattern table rows=note: у этих кадров нет заметок; rows=folder или rows=\"Ряд=шаблон;…\"")
    order = sorted(notes, key=lambda n: (I[n]["y"], I[n]["x"])); Z = {n: _h()["zone_rect"](I[n]) for n in notes}
    key = {}
    for i in ids:
        r = box(I[i]); hit = [n for n in notes if _inside(r, Z[n])]
        if hit: key[i] = min(hit, key=lambda n: Z[n]["w"] * Z[n]["h"]); continue
        above = [n for n in order if I[n]["y"] <= r[1] + r[3] / 2]
        key[i] = above[-1] if above else order[0]
    return key, [n for n in order if n in set(key.values())]


def classify(b, ids, spec, notes):
    s = str(spec)
    if s == "note": return by_note(b, ids, notes)
    if s == "step": return by_step(b, ids)
    if s == "folder": return by_folder(b, ids)
    return by_list(b, ids, s)


def things(b, args):
    """the cards the arguments name (ids, a group by id or name, a note's zone, a path mask) and the one group they are in"""
    I, G = b["items"], b["groups"]; ids, gid = [], None
    for a in args:
        got = patterns.on_page(b, a)
        if got is None:
            try:
                k, i, _nm, _r = _h()["resolve"](b, a, {"group"})
                got, gid = [m for m in G[i]["members"] if grids.gridable(I.get(m)) and I[m].get("type") != "text"], gid or i
            except SystemExit: got = _h()["pics_of"](b, a)
        elif len(args) == 1 and a in G: gid = a
        ids += [i for i in got if i not in ids and not I[i].get("table_of")]
    if len(ids) < 2: raise SystemExit("pattern table: нужны хотя бы 2 кадра или карточки")
    return ids, gid or patterns._one_group(b, ids)


def headers(b, gid, ids):
    """the header row a former run left: texts with table_of, among the group or next to these cards"""
    I = b["items"]; S = set(b["groups"][gid]["members"]) if gid else set()
    return [k for k, it in I.items() if it.get("table_of") and (k in S or not gid)]


def run(b, args, kv):
    I, G = b["items"], b["groups"]
    if not args: raise SystemExit('pattern table <группа|id,id|маска> rows=note cols="Оригинал=^added/;Поза=pose;…" [w=] [gap=24] [between=]')
    ids, gid = things(b, args)
    old = headers(b, gid, ids); saved = next((I[k].get("table") for k in old if I[k].get("table")), None) or {}
    rs, cs = str(kv.get("rows") or saved.get("rows") or "note"), str(kv.get("cols") or saved.get("cols") or "step")
    notes = notes_of(b, ids, gid) if rs == "note" else []
    rkey, rorder = classify(b, ids, rs, notes)
    ckey, corder = classify(b, ids, cs, notes)
    lost = [i for i in ids if i not in ckey]
    if lost: raise SystemExit(f"pattern table: {len(lost)} без колонки, допиши шаблон в cols=: " + ", ".join(stem(name_of(b, i)) for i in lost[:8]))
    corder = [c for c in corder if c in set(ckey.values())]   # the empty columns go
    cells = collections.defaultdict(list)
    for i in ids: cells[(rkey[i], ckey[i])].append(i)
    nat = _h()["natkey"]
    for k in cells: cells[k].sort(key=lambda i: nat(stem(name_of(b, i))))
    if kv.get("w"):
        for i in ids:
            it = I[i]
            if it.get("type") and it.get("h"): it["h"] = round(it["h"] * kv["w"] / it["w"])
            it["w"] = round(kv["w"])
    W = max(I[i]["w"] for i in ids); gap = round(kv.get("gap", GAP)); between = round(kv.get("between", W / 2))
    fs = patterns.hs("caption", W, patterns.CARD)
    titled = rs == "note"
    tnotes = {r: r for r in rorder} if titled else {}
    before = patterns.bbox([box(I[i]) for i in ids] + [box(I[n]) for n in tnotes.values()])
    x0 = kv["x"] if "x" in kv else min([I[n]["x"] for n in tnotes.values()] or [before["x"]])
    y0 = kv["y"] if "y" in kv else min([before["y"]] + [I[k]["y"] for k in old])   # a second run: the header row stays where it is
    grids.leave(b, ids)
    for k, g in list(grids.table(b).items()):   # the grids these cards made are gone (a grid has no stacks and no holes)
        if set(g["members"]) <= set(ids) | set(old): del b["grids"][k]
    tid = next((I[k]["table_of"] for k in old), None) or _h()["uid"]("tb")
    rowt = {}   # row titles: the notes (moved, never made again), or headings
    for r in rorder:
        if titled: rowt[r] = r; continue
        t = next((k for k in old if I[k].get("table_row") == r), None) or _h()["uid"]("t")
        I[t] = {**patterns.heading(r, fs), "table_row": r, "table_of": tid, "x": x0, "y": y0}; rowt[r] = t
    NW = max(I[t]["w"] for t in rowt.values()); cx = x0 + NW + round(W * .15)
    colx = {c: cx + k * (W + gap) for k, c in enumerate(corder)}
    # the header row: a heading a column, reused by its title on a second run
    head = {}
    for c in corder:
        k = next((k for k in old if I[k].get("pattern_col") == c), None) or _h()["uid"]("t")
        h = patterns.heading(c, fs); I[k] = {**h, "x": colx[c], "y": y0, "pattern_col": c, "table_of": tid}; head[c] = k
    for k in old:
        if k not in head.values() and k not in rowt.values():
            del I[k]
            for g in G.values(): g["members"] = [m for m in g["members"] if m != k]
    for k in head.values(): I[k].pop("pattern", None); I[k].pop("table", None)
    first = head[corder[0]]; I[first].update(pattern="table", table={"rows": rs, "cols": cs})
    y = y0 + max(box(I[k])[3] for k in head.values()) + between
    tall = 1
    for r in rorder:
        t = rowt[r]; I[t]["x"], I[t]["y"] = x0, y; hh = box(I[t])[3]; row = []
        for c in corder:
            yy = y
            for i in cells.get((r, c), []):
                I[i]["x"], I[i]["y"] = colx[c], yy; yy += box(I[i])[3] + gap; row.append(i)
            hh = max(hh, yy - gap - y); tall = max(tall, len(cells.get((r, c), [])))
        if titled and row: grids.zone(b, t, row, round(between / 2))
        y += hh + between
    made = list(head.values()) + ([t for t in rowt.values() if not titled])
    allr = [box(I[k]) for k in ids + list(rowt.values()) + list(head.values())]
    allr += [tuple(_h()["zone_rect"](I[t]).values()) for t in rowt.values() if I[t].get("reach")]
    placed = patterns.bbox(allr)
    log = (f"pattern table: {len(rorder)} рядов × {len(corder)} колонок, {len(ids)} кадров, в клетке до {tall}"
           f" · колонки: " + ", ".join(f"{c} {sum(1 for i in ids if ckey[i] == c)}" for c in corder))
    if gid: log += _frame(b, gid, ids, made, list(rowt.values()), placed, before, W)
    else: grids.regroup(b, made)
    return log + f" · таблица {tid}, заголовок [{first}]"


def _frame(b, gid, ids, made, rows, placed, before, W):
    """the group holds the table: its other things under the old block move down by as much as the table grew; the frame grows (and
    what stands right of or under it moves away); a frame that holds only the table fits it"""
    I, G = b["items"], b["groups"][gid]; pad = round(W * 1.5); mine = set(ids) | set(made) | set(rows)
    dh = placed["y"] + placed["h"] - (before["y"] + before["h"])
    if dh > 0:
        for m in G["members"]:
            if m in I and m not in mine and I[m].get("y") is not None and I[m]["y"] >= before["y"] + before["h"] - 1: I[m]["y"] += dh
    log = patterns.hold(b, gid, [m for m in made if m not in G["members"]], placed, pad)
    if all(m in mine for m in G["members"] if m in I):
        G["w"] = round(placed["x"] + placed["w"] + pad - G["x"]); G["h"] = round(placed["y"] + placed["h"] + pad - G["y"])
        log += f" · рамка по таблице {G['w']}×{G['h']}"
    return log


def check(b, k):
    """(ok, words) for a table on the page: every card under its column's title, nothing on top of anything, nothing out of the frame"""
    I = b["items"]; tid = I[k].get("table_of"); hs = {I[h]["pattern_col"]: h for h, it in I.items() if it.get("table_of") == tid and it.get("pattern_col")}
    gid = patterns._one_group(b, [k]); bad = []
    xs = sorted(I[h]["x"] for h in hs.values()); W = (xs[1] - xs[0]) if len(xs) > 1 else 320
    cards = [m for m in (b["groups"][gid]["members"] if gid else []) if grids.gridable(I.get(m)) and I[m].get("type") != "text"]
    off = [m for m in cards if xs and xs[0] - W / 2 <= I[m]["x"] <= xs[-1] + W and min(abs(I[m]["x"] - x) for x in xs) > 1]
    if off: bad.append(f"не в своей колонке: {len(off)} ({', '.join(off[:4])})")
    P = _h()["problems0"](b); S = set(cards) | set(hs.values())
    over = [m for kk, m in P.items() if kk[0] == "over" and set(kk[1:]) & S]
    if over: bad.append(f"кадры друг на друге: {len(over)}")
    edge = [m for kk, m in P.items() if kk[0] == "edge" and kk[1] == gid]
    if edge: bad.append(f"торчат из рамки: {len(edge)}")
    return not bad, "; ".join(bad) or f"по правилам: {len(hs)} колонок, {len(cards)} кадров"
