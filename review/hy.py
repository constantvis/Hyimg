#!/usr/bin/env python3
"""hy: the canvas for an agent, in a few short commands (owner 2026-10-01: "so we both work easily and you spend few tokens").

Talks to the running Hyimg server over HTTP, so it needs no environment variables. Things are named by what the owner
sees (a heading, a group title, a note's first line, a timeline dot's label) or by id; positions can be taken from them.

  hy.py map                     sections: headings, groups, timelines, notes, image frames (F, with the pictures inside them),
                                plus near-misses in alignment
  hy.py map Стили               what lies around one thing, pictures counted
  hy.py find бабушка            ids and boxes of everything whose name has the text (also a picture inside an image frame)
  hy.py do 'point Canon x=@Стили; move "Style cards" y=@Стили.bottom+400' --label "выровнял фазы"
  hy.py check [название]        overlaps, crooked rows, pictures sticking out of a group frame
  hy.py hist                    the last versions;  hy.py restore <id>
  hy.py guide                   everything for an agent: what is open, the project's rules, the skills (same as /agent)
  hy.py save FILE... --to DIR [--move]   pictures into a library folder (a batch), leaving out every picture the library already
                                has (same bytes, any name or folder) and repeats among FILE; names without an extension get one
  hy.py dupes                   byte-identical copies in the library: which file the library shows, which it folds into it
  hy.py undocumented [folder]   frames whose json says nothing about them (no prompt, no model), by folder
  hy.py notify "что сделано" [--text "подробнее"] [--ids a,b]   a notification for the owner (the bell on the canvas, red dot)
  hy.py layout plan             «Разложить по папкам как на доске»: what would move where, read only (counts and examples)
  hy.py layout apply|undo --owner-said-yes   moves the files / puts the last run back. NEVER on the owner's projects without his word

Commands inside do (separated by ;):
  move REF x=V y=V | dx=N dy=N       a group moves with its pictures, a note with the pictures in its zone
  fit GROUP                           the frame fitted to its contents, a group's air around
  set REF key=V ...                   any field: text, title, w, fs, color
  point TL "Label" x=V                a timeline dot by its label: moved, or added if new (TL: the timeline, or any label on it)
  note "text" x=V y=V [w=N] [color=blue]
  text "Heading" x=V y=V [fs=N]
  block PATTERN... into=GROUP | near=REF [side=right|below|left|above] | x=V y=V   [cols=8] [w=N] [gap=24] [note="текст"] [group="Название"]
                                      into= the usual way: a sub-group (note + rows) under the last block of that theme group, the frame
                                      grows and what stands below moves down; group= only for a genuinely new theme
                                      library pictures as a block, one row per pattern (folder or glob), with a zone note and a group;
                                      near= finds free room next to REF by itself (nothing overlaps, a group's air between)
  arrange ID|"glob"|REF... near=REF | x=V y=V [cols] [note=] [group=]
                                      pictures already on the page, laid out again as a tidy block (one row per argument)
  group "Название" REF...             a group frame around notes (with their zone pictures), headings, groups
  remove REF... | remove "glob"       take things off this page: pictures by id or path glob, notes, headings; a group goes with
                                      everything in it, as Delete on the canvas (only=frame keeps the contents, like ⇧⌘G).
                                      A picture gone from every page is the archive = rejected
  frame REF... [name="Имя"]           the pictures (ids, path globs, a group with its nested groups, a note's zone) into one image frame,
                                      as ⌥⌘G: they leave the page and lie inside it; frame each REF...: every picture its own frame (⌥⇧⌘G)
  frame unframe F | frame rename F "Имя" | frame layers F   take a frame apart (pictures back where they lie in it), a new name (a new
                                      version of its frame.json), its layers top first (read only, nothing is saved)
A value V is a number or @REF[.left|.right|.top|.bottom|.cx|.cy][+N|-N]; x defaults to .left, y to .top.
Every do saves a version before and after (who: ai), retries if the owner saved in between and reports new problems (check).
Every do that adds something writes a notification for the owner by itself (owner 2026-10-03): how many pictures, notes, groups, the
first pictures as previews, the place to jump to. --say "Собрал 3x3 по направлению «процедуры»" gives it the words, --quiet skips it
(only for rearranging what is there). HYIMG_AGENT=Codex names the agent in it.
Without --page the page is the one the owner has open on the canvas; every command names it in its first line.
"""
import json, os, random, re, shlex, string, sys, time, urllib.error, urllib.parse, urllib.request

BASE = f"http://localhost:{os.environ.get('HYIMG_PORT', '4180')}"
NSIZE = [1 / 32, 1 / 24, 1 / 18, 1 / 13, 1 / 9]   # note font size per size step, as in canvas.html


LABEL = ""   # what the current do is about: the page's event timeline shows it next to the change


def api(path, body=None):
    if body is not None and path.startswith("/api/board?"):   # saves made from here are the AI's in the page's event timeline
        path += "&who=ai" + ("&label=" + urllib.parse.quote(LABEL) if LABEL else "")
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=240 if path.startswith("/api/items") else 60) as r:   # the library list is 15 MB and takes 30-120 s on a big project (2026-10-02)
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try: return e.code, json.loads(raw)
        except ValueError: return e.code, raw.decode(errors="replace")


def api_text(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r: return r.status, r.read().decode()
    except urllib.error.URLError as e: raise SystemExit(f"Hyimg не отвечает на {BASE}: {e}. Открой проект в приложении или задай HYIMG_PORT")


# ---- geometry, the same rules as canvas.html (itemH, rectOf, reachRect)
def is_pic(it): return bool(it) and not it.get("type")


def item_h(it):
    if it.get("type") == "note": return max(it.get("h") or it.get("fs", 0) * 1.2, it["w"])
    if it.get("type"): return it.get("h") or it.get("fs", 0) * 1.2
    c = it.get("crop") or [0, 0, 1, 1]
    return it["w"] * ((c[3] - c[1]) / it["ar"]) / (c[2] - c[0])


def rect(b, id):
    if id in b["items"]:
        it = b["items"][id]; return {"x": it["x"], "y": it["y"], "w": it["w"], "h": item_h(it)}
    g = b["groups"].get(id)
    return {k: g[k] for k in "xywh"} if g else None


def first_line(t): return (t or "").strip().split("\n")[0].lstrip("#").strip()


def names(b):
    """every nameable thing: (kind, id, name, rect); timeline dots are ('dot', 'tl/pid', label, rect)"""
    out = []
    for gid, g in b["groups"].items(): out.append(("group", gid, first_line(g.get("title")) or "группа", rect(b, gid)))
    for id, it in b["items"].items():
        t = it.get("type")
        if t == "text": out.append(("heading", id, first_line(it.get("text")), rect(b, id)))
        elif t == "note": out.append(("note", id, first_line(it.get("text")), rect(b, id)))
        elif t == "timeline":
            out.append(("timeline", id, first_line(it.get("label")) or "таймлайн", rect(b, id)))
            for p in it.get("points", []):
                x = it["x"] + p["t"]
                out.append(("dot", f"{id}/{p['id']}", first_line(p.get("text")), {"x": x, "y": it["y"], "w": 0, "h": it.get("h", 0)}))
    return out


def norm(s): return re.sub(r"\s+", " ", (s or "").lower().replace("ё", "е")).strip().lstrip("#").strip()   # "# Блок" finds the note «Блок»


def resolve(b, ref, kinds=None):
    L = [n for n in names(b) if not kinds or n[0] in kinds]
    for n in L:
        if n[1] == ref or n[1].split("/")[-1] == ref: return n
    exact = [n for n in L if norm(n[2]) == norm(ref)]
    if len(exact) == 1: return exact[0]
    if len(exact) > 1 and sum(n[0] == "group" for n in exact) == 1:   # a block names its group and its note alike: the group wins
        return next(n for n in exact if n[0] == "group")
    part = exact or [n for n in L if norm(ref) in norm(n[2])]
    if len(part) == 1: return part[0]
    if sum(n[0] == "group" for n in part) == 1: return next(n for n in part if n[0] == "group")   # the group over its own note
    if not part: raise SystemExit(f"не нашел «{ref}»")
    raise SystemExit(f"«{ref}» неоднозначно: " + "; ".join(f"{k} {i} «{nm[:30]}»" for k, i, nm, _ in part[:8]))


EDGE = {"left": lambda r: r["x"], "right": lambda r: r["x"] + r["w"], "top": lambda r: r["y"], "bottom": lambda r: r["y"] + r["h"],
        "cx": lambda r: r["x"] + r["w"] / 2, "cy": lambda r: r["y"] + r["h"] / 2}


def value(b, v, key):
    m = re.fullmatch(r"@(.+?)(?:\.(left|right|top|bottom|cx|cy))?([+-]\d+(?:\.\d+)?)?", v)
    if not m:
        try: return float(v)
        except ValueError: return v
    r = resolve(b, m.group(1))[3]
    return round(EDGE[m.group(2) or ("top" if key in ("y", "dy") else "left")](r) + float(m.group(3) or 0))


def uid(p): return p + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(7))


# ---- commands inside do
def op_move(b, args, kv):
    k, id, nm, r = resolve(b, args[0])
    dx = kv["x"] - r["x"] if "x" in kv else kv.get("dx", 0)
    dy = kv["y"] - r["y"] if "y" in kv else kv.get("dy", 0)
    if k == "dot": raise SystemExit("точку двигай командой point")
    ids = [id] + (b["groups"][id]["members"] if k == "group" else [])
    if k == "note" and b["items"][id].get("reach"):   # a sub-block moves whole: the note with the pictures in its zone
        z = zone_rect(b["items"][id])
        ids += [i for i, it in b["items"].items() if is_pic(it) and z["x"] <= it["x"] + it["w"] / 2 <= z["x"] + z["w"] and z["y"] <= it["y"] + item_h(it) / 2 <= z["y"] + z["h"]]
    if k == "group": b["groups"][id]["x"] += dx; b["groups"][id]["y"] += dy
    for i in ids:
        if i in b["items"]: b["items"][i]["x"] += dx; b["items"][i]["y"] += dy
    return f"move «{nm}» → x {round(r['x'] + dx)} y {round(r['y'] + dy)}" + (f" (+{len(ids) - 1} кадров)" if len(ids) > 1 else "")


def op_fit(b, args, kv):
    """a group frame fitted to what is in it, with a group's air around (as a double click on its corner in the canvas)"""
    k, id, nm, _ = resolve(b, args[0], {"group"}); g = b["groups"][id]
    inside = [m for m in g["members"] if m in b["items"]]
    if not inside: raise SystemExit(f"«{nm}» пустая")
    pw = sorted(b["items"][m]["w"] for m in inside if is_pic(b["items"][m])); pad = round(kv.get("pad", (pw[len(pw) // 2] if pw else 320) * 1.5))
    rs = [rect(b, m) for m in inside] + [zone_rect(b["items"][m]) for m in inside if b["items"][m].get("reach")]
    x0, y0 = min(r["x"] for r in rs), min(r["y"] for r in rs); x1, y1 = max(r["x"] + r["w"] for r in rs), max(r["y"] + r["h"] for r in rs)
    g.update(x=round(x0 - pad), y=round(y0 - pad), w=round(x1 - x0 + 2 * pad), h=round(y1 - y0 + 2 * pad))
    return f"fit «{nm}» x {g['x']} y {g['y']} {g['w']}×{g['h']}"


def op_set(b, args, kv):
    k, id, nm, _ = resolve(b, args[0], {"group", "heading", "note", "timeline"})
    tgt = b["groups"][id] if k == "group" else b["items"][id]
    tgt.update(kv); return f"set «{nm}» " + " ".join(f"{a}={v}" for a, v in kv.items())


def op_point(b, args, kv):
    k, id, nm, _ = resolve(b, args[0], {"timeline", "dot"})
    tl = b["items"][id.split("/")[0]]
    label, x = args[1] if len(args) > 1 else nm, kv["x"]
    p = next((p for p in tl["points"] if norm(p.get("text")) == norm(label)), None)
    if p is None: p = {"id": uid("p"), "t": None, "text": label}; tl["points"].append(p)
    elif p["t"] == 0 and round(x) != round(tl["x"]):
        raise SystemExit("начальную точку не двигаю: сдвинь весь таймлайн через move")
    p["t"] = round(x - tl["x"])
    if p["t"] < 0: raise SystemExit(f"«{label}» левее начала таймлайна")
    tl["points"].sort(key=lambda q: q["t"])
    tl["len"] = tl["w"] = max(tl["len"], max(q["t"] for q in tl["points"]))
    return f"point «{label}» → x {round(x)}"


def op_note(b, args, kv):
    pw = sorted(it["w"] for it in b["items"].values() if is_pic(it)); w = kv.get("w") or round(pw[len(pw) // 2] if pw else 320)
    size = int(kv.get("size", 2)); id = uid("n")
    b["items"][id] = {"type": "note", "text": args[0], "x": kv["x"], "y": kv["y"], "w": w, "fs": w * NSIZE[size], "size": size, "h": 0,
                      "color": kv.get("color", "blue"), "reach": None, "to": []}
    return f"note {id} «{first_line(args[0])[:30]}» x {round(kv['x'])} y {round(kv['y'])}"


def op_text(b, args, kv):
    id = uid("t"); fs = kv.get("fs", 874)
    b["items"][id] = {"type": "text", "text": args[0], "x": kv["x"], "y": kv["y"], "fs": fs, "size": 4, "w": round(fs * .6 * len(args[0])), "h": round(fs * 1.15)}
    return f"text {id} «{args[0][:30]}» x {round(kv['x'])} y {round(kv['y'])}"


def op_htmlframe(b, args, kv):
    """an HTML frame (Hyimg-frames plugin): a page of the library (html/<name>/index.html) seen at a viewport of vw × vh css px, the card
    w wide on the board (owner 2026-10-04: «a frame for HTML, interactive; change its width and height and see how it works»)"""
    try: st, _ = api_text("/lib/" + urllib.parse.quote(args[0]))
    except SystemExit: st = 404
    if st != 200: raise SystemExit(f"нет страницы {args[0]}")
    vw, vh = int(kv.get("vw", 1440)), int(kv.get("vh", 900)); w = kv.get("w", 720); id = uid("h")
    # the viewport's height follows the card's shape (vh = vw · h / w): resizing at rest zooms the page, resizing in its editor widens it
    b["items"][id] = {"type": "htmlframe", "src": args[0], "vw": vw, "x": kv["x"], "y": kv["y"], "w": w, "h": round(w * vh / vw),
                      **({"name": kv["name"]} if kv.get("name") else {})}
    return f"htmlframe {id} «{args[0]}» {vw}×{vh} x {round(kv['x'])} y {round(kv['y'])}"


_ITEMS, _COPY, _HID, _DESC, _NOREF = [], {}, {}, {}, set()   # library paths; copy -> its first file; hidden copy -> that first; path -> described; prompt names images it has not
def lib_paths():
    if not _ITEMS:
        for i in api("/api/items?all=1")[1]:
            _ITEMS.append(i["path"]); _DESC[i["path"]] = bool((i.get("prompt") or "").strip() or (i.get("model") or "").strip())
            if re.search(r"\bimage\s*\d", i.get("prompt") or "", re.I) and not i.get("refpaths"): _NOREF.add(i["path"])
            if i.get("copy_of"): _COPY[i["path"]] = i["copy_of"]
            if i.get("hidden"): _HID[i["path"]] = i["copy_of"]
    return _ITEMS


def same(p): lib_paths(); return _COPY.get(p, p)          # one key for byte-identical files (owner 2026-10-02: no picture twice)
def shown(p): lib_paths(); return _HID.get(p, p)          # the file the library shows for this picture


def natkey(p): return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p)]


def lay_out(b, rows, kv, what, moving=()):
    """rows of picture dicts (new ones or the board's own) as a block: each row wrapped at cols, optional blue note with a zone on the
    left (as N on a selection in the canvas) and a group frame around it all (as ⌘G). Laid out at the origin, then moved to x/y (the
    top left picture) or, with near=, to free room beside that thing (the pictures being moved are not in the way)"""
    if "near" not in kv and "into" not in kv and not ("x" in kv and "y" in kv):
        raise SystemExit(f"{what}: укажи into=<группа> (подгруппой внутрь темы), near=<что рядом> или x= и y=")
    pw = sorted(it["w"] for it in b["items"].values() if is_pic(it))
    w = round(kv.get("w") or (pw[len(pw) // 2] if pw else 320)); gap = round(kv.get("gap", 24)); cols = int(kv.get("cols", 8))
    into = None
    if "into" in kv:   # a sub-group (note + rows) under the last block of a theme group, not a group of its own (owner 2026-10-02)
        into = resolve(b, str(kv["into"]), {"group"})[1]; g = b["groups"][into]; pad = round(w * 1.5)
        inside = [m for m in g["members"] if m in b["items"] and m not in moving]
        own = [rect(b, m) for m in inside]; rs = own + [zone_rect(b["items"][m]) for m in inside if b["items"][m].get("reach")]
        left = min((r["x"] for r in own), default=g["x"] + pad)   # the notes' column itself, not their dashed zones
        bottom = max((r["y"] + r["h"] for r in rs), default=g["y"] + pad - w)
        if "cols" not in kv:   # as wide as the group already is, 4 to 8 pictures
            room = g["x"] + g["w"] - pad - (left + (round(w * .15) + w if kv.get("note") else 0))
            cols = max(4, min(8, int((room + gap) // (w + gap))))
    y, pics = 0, []
    for r in rows:
        for k in range(0, len(r), cols):
            hmax = 0
            for c, it in enumerate(r[k:k + cols]):
                it["x"], it["y"], it["w"] = c * (w + gap), y, w; pics.append(it); hmax = max(hmax, item_h(it))
            y += hmax + gap
    bx = {"x": 0, "y": 0, "w": min(cols, max(len(r) for r in rows)) * (w + gap) - gap, "h": y - gap}
    extra, msg, group = [], f"{what} {len(pics)} кадров", None
    if kv.get("note"):
        G, P = round(w * .15), round(w / 2); size = 2
        n = {"type": "note", "text": str(kv["note"]).replace("\\n", "\n"), "x": round(bx["x"] - G - w), "y": round(bx["y"]), "w": w, "fs": w * NSIZE[size], "size": size,
             "h": 0, "color": "blue", "to": []}
        n["reach"] = {"l": P, "t": P, "r": round(bx["x"] + bx["w"] - (n["x"] + w) + P), "b": round(max(0, bx["y"] + bx["h"] - (n["y"] + w)) + P)}
        extra.append(n); bx = {"x": n["x"], "y": bx["y"], "w": bx["w"] + G + w, "h": max(bx["h"], w)}
    outer = dict(bx)
    if kv.get("group"):
        pad = round(w * 1.5); group = {"title": str(kv["group"]), "x": bx["x"] - pad, "y": bx["y"] - pad, "w": bx["w"] + 2 * pad, "h": bx["h"] + 2 * pad}
        outer = {k: group[k] for k in "xywh"}
    if into:
        dx, dy = left - outer["x"], bottom + w - outer["y"]   # the note column of the group, one picture width under the last block
    elif "near" in kv:
        keep = {i: b["items"].pop(i) for i in moving}   # what moves is not in the way of itself
        try: spot = free_spot(b, resolve(b, str(kv["near"]))[3], outer, kv.get("side", "right"), round(w * 1.5))
        finally: b["items"].update(keep)
        dx, dy = spot["x"] - outer["x"], spot["y"] - outer["y"]
    else:
        dx, dy = kv["x"], kv["y"]
    for it in pics + extra: it["x"] = round(it["x"] + dx); it["y"] = round(it["y"] + dy)
    ids = [i for i, it in b["items"].items() if any(it is p for p in pics)]
    for it in pics:
        if not any(it is o for o in b["items"].values()): i = uid("i"); b["items"][i] = it; ids.append(i)
        b.get("removed", {}).pop(it["path"], None)
    members = list(ids)
    for n in extra: nid = uid("n"); b["items"][nid] = n; members.append(nid); msg += f" · заметка {nid}"
    msg += f" x {round(bx['x'] + dx)} y {round(bx['y'] + dy)}, {round(bx['w'])}×{round(bx['h'])}"
    if "near" in kv and spot["side"] != kv.get("side", "right"):
        msg += f" · {dict(right='справа', left='слева', below='снизу', above='сверху')[kv.get('side', 'right')]} от «{kv['near']}» места не было, встало {dict(right='справа', left='слева', below='снизу', above='сверху')[spot['side']]}"
    if group and not into:
        for g in b["groups"].values(): g["members"] = [m for m in g["members"] if m not in members]
        group.update(x=round(group["x"] + dx), y=round(group["y"] + dy), members=members); gid = uid("g"); b["groups"][gid] = group
        msg += f" · группа «{group['title']}» [{gid}]"
    if into:
        msg += grow_into(b, into, members, {"x": bx["x"] + dx, "y": bx["y"] + dy, "w": bx["w"], "h": bx["h"]}, round(w * 1.5))
    return msg


def shift(b, kind, id, dx, dy):
    ids = [id] + (b["groups"][id]["members"] if kind == "group" else [])
    if kind == "group": b["groups"][id]["x"] += dx; b["groups"][id]["y"] += dy
    for i in ids:
        if i in b["items"]: b["items"][i]["x"] += dx; b["items"][i]["y"] += dy


def grow_into(b, gid, members, box, pad, also=()):
    """the new block joins the group; the frame grows to hold it, and whatever stood under the group (or right of it, if it got wider)
    moves away by the same amount, so the column keeps its order and nothing ends up on top of anything"""
    g = b["groups"][gid]
    for o in b["groups"].values(): o["members"] = [m for m in o["members"] if m not in members]
    g["members"] += members
    # only what is new or was pushed down needs room: the owner's own pictures may stand closer to the frame than a group's air,
    # and fitting the frame to all of them moved neighbouring groups for nothing (2026-10-02: 12 frames added, 172 moved)
    rs = [box] + [r for r in also if r]
    old = dict(g); right = max([g["x"] + g["w"]] + [r["x"] + r["w"] + pad for r in rs]); bottom = max([g["y"] + g["h"]] + [r["y"] + r["h"] + pad for r in rs])
    g["w"], g["h"] = right - g["x"], bottom - g["y"]; dw, dh = g["w"] - old["w"], g["h"] - old["h"]
    grouped = {m for o in b["groups"].values() for m in o["members"]}
    others = [("group", k, o) for k, o in b["groups"].items() if k != gid] + [("item", k, rect(b, k)) for k, it in b["items"].items() if k not in grouped]
    moved = 0
    for kind, k, r in others:
        r = {q: r[q] for q in "xywh"}
        if dh > 0 and r["y"] >= old["y"] + old["h"] - 1 and r["x"] < g["x"] + g["w"] and r["x"] + r["w"] > g["x"]: shift(b, kind, k, 0, dh); moved += 1
        elif dw > 0 and r["x"] >= old["x"] + old["w"] - 1 and r["y"] < g["y"] + g["h"] and r["y"] + r["h"] > g["y"]: shift(b, kind, k, dw, 0); moved += 1
    title = first_line(g.get("title")) or "группа"
    return f" · подгруппой в «{title}»" + (f", рамка выросла на {round(dh)} вниз" if dh > 0 else "") + (f" и {round(dw)} вправо" if dw > 0 else "") + (f", ниже и правее сдвинуто {moved}" if moved else "")


def op_block(b, args, kv):
    """pictures from the library as a block, one row per pattern (folder or glob)"""
    import fnmatch
    rows = []
    for pat in args:
        got = sorted((p for p in lib_paths() if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(p, pat.rstrip("/") + "/*")), key=natkey)
        if not got: raise SystemExit(f"в библиотеке нет кадров по «{pat}»")
        rows.append(got)
    # byte-identical files are one picture (owner 2026-10-02): a copy the library hides is placed as the file the library shows, and a
    # copy of a picture already on the page under another file is skipped (the same file again works as before); again=1 places all
    on = {it.get("path") for it in b["items"].values() if is_pic(it)}
    seen, skipped = ({same(p): p for p in on} if not kv.get("again") else {}), []
    for r in rows:
        keep = []
        for p in r:
            k, f = same(p), shown(p)
            if k in seen and seen[k] != p: skipped.append(p); continue
            seen.setdefault(k, f); keep.append(f)
        r[:] = list(dict.fromkeys(keep))
    rows = [r for r in rows if r]
    note = f"; пропустил {len(skipped)}: эти картинки уже на странице другим файлом (again=1 положит все равно)" if skipped else ""
    bare = [p for r in rows for p in r if not _DESC.get(p, True)]
    if bare:   # owner 2026-10-03: a frame from a one-off script came with no json and its card said nothing
        note += (f"\nвнимание: {len(bare)} кадров без описания (в json нет prompt и model), карточка в Hyimg пустая: " + ", ".join(bare[:3]) + (" …" if len(bare) > 3 else "")
                 + ". Допиши json: что это, чем и из чего сделано, как повторить (скилл hyimg-generate, шаг 6); список: hy.py undocumented")
    noref = [p for r in rows for p in r if p in _NOREF]
    if noref:   # owner 2026-10-03: strips cut from a grid lost "inputs" and their card showed no references although the prompt names Image 1 and 2
        note += (f"\nвнимание: у {len(noref)} кадров промпт ссылается на Image 1, 2…, а эталонов в json нет: " + ", ".join(noref[:3]) + (" …" if len(noref) > 3 else "")
                 + ". Запиши \"inputs\" (пути к эталонам от папки кадра) или \"grid\" / \"derived_from\" (из какого файла вырезан)")
    if not rows: return (f"«{first_line(str(kv['note']))}»: новых кадров нет" if kv.get("note") else "новых кадров нет") + note
    sizes = api("/api/sizes", {"paths": [p for r in rows for p in r]})[1]
    def pic(path):
        sw, sh = (sizes.get(path) or [1, 1]); return {"path": path, "x": 0, "y": 0, "w": 320, "ar": sw / sh if sh else 1}
    if kv.get("into") and kv.get("note"):   # the sub-group is there already: a batch still running adds only its new frames to it
        gid = resolve(b, str(kv["into"]), {"group"})[1]; head = first_line(str(kv["note"]).replace("\\n", "\n"))
        nid = next((m for m in b["groups"][gid]["members"] if b["items"].get(m, {}).get("type") == "note" and first_line(b["items"][m].get("text")) == head), None)
        if nid:
            new = [pic(p) for r in rows for p in r if p not in on]
            return (append_block(b, gid, nid, new, kv) if new else f"«{head}»: новых кадров нет") + note
    return lay_out(b, [[pic(p) for p in r] for r in rows], kv, "block") + note


def append_block(b, gid, nid, new, kv):
    """new frames continue the rows of an existing sub-block (note + its zone); the zone, the group and everything under them make room"""
    g, n = b["groups"][gid], b["items"][nid]; w, gap, pad = n["w"], round(kv.get("gap", 24)), round(n["w"] * 1.5)
    z = zone_rect(n) or rect(b, nid)
    have = [i for i in g["members"] if is_pic(b["items"].get(i)) and z["x"] <= b["items"][i]["x"] + b["items"][i]["w"] / 2 <= z["x"] + z["w"]
            and z["y"] <= b["items"][i]["y"] + item_h(b["items"][i]) / 2 <= z["y"] + z["h"]]
    x0 = n["x"] + w + round(w * .15)
    cols = int(kv.get("cols") or max(1, len({round(b["items"][i]["x"]) for i in have})) if have else kv.get("cols", 8))
    rowh = max([item_h(b["items"][i]) for i in have] + [item_h(dict(it, w=w)) for it in new])
    k = len(have); ids = []
    for j, it in enumerate(new):
        i = k + j; it.update(x=x0 + (i % cols) * (w + gap), y=n["y"] + (i // cols) * (rowh + gap), w=w)
        iid = uid("i"); b["items"][iid] = it; ids.append(iid); b.get("removed", {}).pop(it["path"], None)
    old_bottom = z["y"] + z["h"]
    allp = [rect(b, i) for i in have + ids]
    P = round(w / 2)
    n["reach"] = {"l": P, "t": P, "r": round(max(r["x"] + r["w"] for r in allp) - (n["x"] + w) + P), "b": round(max(0, max(r["y"] + r["h"] for r in allp) - (n["y"] + item_h(n))) + P)}
    dh = max(0, zone_rect(n)["y"] + zone_rect(n)["h"] - old_bottom)
    pushed = []
    for m in g["members"]:   # the blocks under this one, inside the group, move down
        if m in b["items"] and m not in ids and m != nid and b["items"][m]["y"] >= old_bottom - 1:
            b["items"][m]["y"] += dh; pushed.append(rect(b, m))
            if b["items"][m].get("reach"): pushed.append(zone_rect(b["items"][m]))
    msg = grow_into(b, gid, ids, zone_rect(n), pad, pushed if dh else ())
    return f"+{len(ids)} кадров в «{first_line(n.get('text'))}»" + msg


def pics_of(b, ref):
    """picture ids named by an id, a path glob, or a group / note (its zone) / heading: what arrange and remove act on"""
    import fnmatch
    if ref in b["items"]: return [ref]
    if any(ch in ref for ch in "*?/"):
        got = sorted((i for i, it in b["items"].items() if is_pic(it) and fnmatch.fnmatch(it["path"], ref)), key=lambda i: natkey(b["items"][i]["path"]))
        if not got: raise SystemExit(f"на странице нет кадров по «{ref}»")
        return got
    k, id, nm, r = resolve(b, ref, {"group", "note"})
    if k == "group": return [m for m in b["groups"][id]["members"] if is_pic(b["items"].get(m))]
    z = zone_rect(b["items"][id]) or r
    return [i for i, it in b["items"].items() if is_pic(it) and z["x"] <= it["x"] + it["w"] / 2 <= z["x"] + z["w"] and z["y"] <= it["y"] + item_h(it) / 2 <= z["y"] + z["h"]]


def op_arrange(b, args, kv):
    """pictures already on the page (ids, path globs, a group's or a note's) laid out again as a tidy block, one row per argument"""
    rows = [[b["items"][i] for i in pics_of(b, a)] for a in args]
    if not any(rows): raise SystemExit("arrange: нечего раскладывать")
    ids = [i for a in args for i in pics_of(b, a)]
    for g in b["groups"].values():   # they leave the frames they were dropped into; a group= gives them their own (into= is handled in lay_out)
        if kv.get("group") and "into" not in kv: g["members"] = [m for m in g["members"] if m not in ids]
    return lay_out(b, [r for r in rows if r], kv, "arrange", moving=ids)


def all_rects(b):
    """everything that takes room on the page: group frames, pictures, notes with their zones, headings, timelines"""
    out = [{k: g[k] for k in "xywh"} for g in b["groups"].values()]
    for id, it in b["items"].items():
        out.append(rect(b, id))
        if it.get("type") == "note" and it.get("reach"): out.append(zone_rect(it))
    return out


def _spot(obs, ref, size, side, gap):
    """top left of a size-box beside ref on one side with nothing under it, and how far it had to step from right next to ref"""
    x0 = {"right": ref["x"] + ref["w"] + gap, "left": ref["x"] - gap - size["w"]}.get(side, ref["x"])
    y0 = {"below": ref["y"] + ref["h"] + gap, "above": ref["y"] - gap - size["h"]}.get(side, ref["y"])
    x, y = x0, y0
    for _ in range(500):
        c = {"x": x - gap / 2, "y": y - gap / 2, "w": size["w"] + gap, "h": size["h"] + gap}
        hits = [o for o in obs if inter(c, o)]
        if not hits: return {"x": round(x), "y": round(y), "side": side}, abs(x - x0) + abs(y - y0)
        if side == "right": x = max(o["x"] + o["w"] for o in hits) + gap
        elif side == "left": x = min(o["x"] for o in hits) - gap - size["w"]
        elif side == "below": y = max(o["y"] + o["h"] for o in hits) + gap
        else: y = min(o["y"] for o in hits) - gap - size["h"]
    return None, float("inf")


def free_spot(b, ref, size, side, gap):
    """free room beside ref, on the asked side when there is room right there; when something is in the way, the nearest of the four
    sides (another agent's batch once landed 16000 to the right, past two groups, because the gap next to its target was too narrow)"""
    if side not in ("right", "left", "below", "above"): raise SystemExit(f"side: right, below, left или above, не «{side}»")
    obs = all_rects(b)
    best, d = _spot(obs, ref, size, side, gap)
    if d > gap:
        for other in ("right", "below", "left", "above"):
            if other == side: continue
            sp, d2 = _spot(obs, ref, size, other, gap)
            if d2 < d - gap: best, d = sp, d2
    if best is None: raise SystemExit("не нашел свободного места")
    return best


def op_remove(b, args, kv):
    import fnmatch
    out, ids = [], []
    for a in args:
        if a in b["items"]: ids.append(a); continue
        if any(ch in a for ch in "*?/"):
            got = [i for i, it in b["items"].items() if is_pic(it) and fnmatch.fnmatch(it["path"], a)]
            if not got: raise SystemExit(f"на странице нет кадров по «{a}»")
            ids += got; continue
        k, id, nm, _ = resolve(b, a)
        if k == "dot": raise SystemExit("точку таймлайна убирает владелец на холсте (Backspace)")
        if k == "group":   # with its contents, as Delete on the canvas (owner 2026-10-01); only=frame keeps them, like ⇧⌘G
            if kv.get("only") != "frame": ids += b["groups"][id]["members"]
            del b["groups"][id]; out.append(f"группа «{nm}»" + (" (только рамка)" if kv.get("only") == "frame" else " с содержимым")); continue
        ids.append(id)
    t = time.strftime("%Y-%m-%dT%H:%M:%S")
    for i in dict.fromkeys(ids):
        it = b["items"].pop(i, None)
        if it is None: continue
        for g in b["groups"].values(): g["members"] = [m for m in g["members"] if m != i]
        if is_pic(it) and not any(o.get("path") == it["path"] for o in b["items"].values()): b.setdefault("removed", {})[it["path"]] = t
    return "remove " + ", ".join(out + ([f"{len(dict.fromkeys(ids))} шт."] if ids else []))


def zone_rect(n):
    m = n.get("reach")
    return {"x": n["x"] - m["l"], "y": n["y"] - m["t"], "w": n["w"] + m["l"] + m["r"], "h": item_h(n) + m["t"] + m["b"]} if m else None


def op_group(b, args, kv):
    """a group frame (as ⌘G) around things named in REF...: a note with a zone brings its zone's pictures along"""
    title, refs, ids = args[0], args[1:], []
    for r in refs:
        k, id, nm, _ = resolve(b, r, {"note", "heading", "group"})
        if k == "group": ids += b["groups"][id]["members"]; continue
        ids.append(id); z = zone_rect(b["items"][id]) if k == "note" else None
        if z:
            for pid, it in b["items"].items():
                if is_pic(it):
                    c = (it["x"] + it["w"] / 2, it["y"] + item_h(it) / 2)
                    if z["x"] <= c[0] <= z["x"] + z["w"] and z["y"] <= c[1] <= z["y"] + z["h"]: ids.append(pid)
    ids = list(dict.fromkeys(ids)); rs = [rect(b, i) for i in ids]
    x0, y0 = min(r["x"] for r in rs), min(r["y"] for r in rs); x1, y1 = max(r["x"] + r["w"] for r in rs), max(r["y"] + r["h"] for r in rs)
    pw = sorted(b["items"][i]["w"] for i in ids if is_pic(b["items"][i])); pad = round(kv.get("pad", (pw[len(pw) // 2] if pw else 320) * 1.5))
    for g in b["groups"].values(): g["members"] = [m for m in g["members"] if m not in ids]
    gid = uid("g"); b["groups"][gid] = {"title": title, "x": x0 - pad, "y": y0 - pad, "w": x1 - x0 + 2 * pad, "h": y1 - y0 + 2 * pad, "members": ids}
    return f"group «{title}» {len(ids)} шт. x {round(x0 - pad)} y {round(y0 - pad)} [{gid}]"

# ---- image frames (Hyimg-frames, owner 2026-10-05): an agent makes, takes apart, renames and reads frames as the owner does with ⌥⌘G
# and ⌥⇧⌘G on the canvas; the files are the same (frames/<stamp>/frame.<n>.json, render.<n>.png), the pictures are only read
def post_bytes(path, data):
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/octet-stream"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: raise SystemExit(f"сервер не записал {path}: {e.code} {e.read()[:200]!r}")


def frame_ref(b, ref):
    """an image frame by its id or its name (a part of the name when only one frame has it)"""
    fr = {id: it for id, it in b["items"].items() if it.get("type") == "imgframe"}
    if ref in fr: return ref
    ex = [id for id, it in fr.items() if norm(it.get("name")) == norm(ref)] or [id for id, it in fr.items() if norm(ref) in norm(it.get("name"))]
    if len(ex) == 1: return ex[0]
    if not ex: raise SystemExit(f"нет фрейма «{ref}»: " + ", ".join(f"«{it.get('name')}» [{id}]" for id, it in fr.items()))
    raise SystemExit(f"«{ref}» неоднозначно: " + ", ".join(f"«{fr[i].get('name')}» [{i}]" for i in ex))


def frame_sel_pics(b, refs):
    """the pictures named by ids, path globs, notes or groups; a group brings every picture whose centre is in its frame (nested groups too)"""
    out = []
    for ref in refs:
        got = list(pics_of(b, ref))
        if ref not in b["items"] and not any(ch in ref for ch in "*?/"):
            try: k, gid, _nm, _r = resolve(b, ref, {"group"})
            except SystemExit: k = None
            if k == "group":
                g = b["groups"][gid]
                got += [i for i, it in b["items"].items() if is_pic(it) and g["x"] <= it["x"] + it["w"] / 2 <= g["x"] + g["w"] and g["y"] <= it["y"] + item_h(it) / 2 <= g["y"] + g["h"]]
        out += [i for i in got if i not in out and not re.search(r"\.(mp4|m4v|mov|webm)$", b["items"][i].get("path", ""), re.I)]
    if not out: raise SystemExit("во фрейм идут картинки: не нашел ни одной")
    order = list(b["items"]); return sorted(out, key=order.index)


def regroup_one(b, id):
    """an item belongs to the smallest group whose frame holds its centre (canvas.html regroup)"""
    r = rect(b, id); c = (r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)
    for g in b["groups"].values(): g["members"] = [m for m in g["members"] if m != id]
    hit = sorted((g for g in b["groups"].values() if g.get("x") is not None and g["x"] <= c[0] <= g["x"] + g["w"] and g["y"] <= c[1] <= g["y"] + g["h"]), key=lambda g: g["w"] * g["h"])
    if hit: hit[0]["members"].append(id)


def build_frame(b, ids, name):
    """one frame of these pictures, as imgframe.js buildFrame: the document is their box in the largest picture's own pixels (at most
    8000 a side), the render the pictures with their crops on white; returns the card"""
    import io
    from PIL import Image, ImageOps
    R = {i: rect(b, i) for i in ids}
    x0, y0 = min(r["x"] for r in R.values()), min(r["y"] for r in R.values())
    bb = {"x": x0, "y": y0, "w": max(r["x"] + r["w"] for r in R.values()) - x0, "h": max(r["y"] + r["h"] for r in R.values()) - y0}
    ims = {}
    for i in ids:
        p = b["items"][i]["path"]
        if p in ims: continue
        with urllib.request.urlopen(BASE + "/img?p=" + urllib.parse.quote(p), timeout=120) as r: ims[p] = ImageOps.exif_transpose(Image.open(io.BytesIO(r.read()))).convert("RGBA")
    best = None
    for i in ids:
        it = b["items"][i]; c = it.get("crop") or [0, 0, 1, 1]; im = ims[it["path"]]; pw, ph = im.width * (c[2] - c[0]), im.height * (c[3] - c[1])
        if not best or pw * ph > best[0]: best = (pw * ph, pw / R[i]["w"])
    s = best[1]; capped = max(bb["w"], bb["h"]) * s > 8000
    if capped: s = 8000 / max(bb["w"], bb["h"])
    W, H = max(16, min(8000, round(bb["w"] * s))), max(16, min(8000, round(bb["h"] * s))); sx, sy = W / bb["w"], H / bb["h"]
    d = "frames/" + time.strftime("%y%m%d-%H%M%S") + "-" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(3))
    layers, canvas = [], Image.new("RGBA", (W, H), (255, 255, 255, 255))
    for n, i in enumerate(ids, 1):
        it, r = b["items"][i], R[i]; c = it.get("crop") or [0, 0, 1, 1]; im = ims[it["path"]]
        l = {"id": f"p{n}_" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4)), "kind": "pic", "name": os.path.splitext(os.path.basename(it["path"]))[0],
             "path": it["path"], "crop": it.get("crop"), "x": (r["x"] - bb["x"]) * sx, "y": (r["y"] - bb["y"]) * sy, "w": r["w"] * sx, "h": r["h"] * sy, "rot": 0, "flip": [False, False],
             "visible": True, "opacity": round((it.get("opacity") or 1) * 100), "fill": 100, "blend": "source-over", "clip": False, "locked": True,
             "locks": {"alpha": False, "pixels": True, "pos": False, "all": False}, "board": {"id": i, "item": it}}
        layers.append(l)
        part = im.crop((round(c[0] * im.width), round(c[1] * im.height), round(c[2] * im.width), round(c[3] * im.height))).resize((max(1, round(l["w"])), max(1, round(l["h"]))), Image.LANCZOS)
        if l["opacity"] < 100: part.putalpha(part.getchannel("A").point(lambda v: v * l["opacity"] // 100))
        canvas.alpha_composite(part, (round(l["x"]), round(l["y"])))
    buf = io.BytesIO(); canvas.convert("RGB").save(buf, "PNG")
    doc = {"version": 1, "v": 1, "name": name, "size": [W, H], "background": "#ffffff", "order": "bottom-to-top", "layers": layers, "render": f"{d}/render.1.png",
           "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "by": "hy.py"}
    _, rr = post_bytes(f"/api/file?p={urllib.parse.quote(d + '/render.1.png')}", buf.getvalue())
    post_bytes(f"/api/file?p={urllib.parse.quote(d + '/frame.1.json')}", json.dumps(doc, ensure_ascii=False, indent=1).encode())
    card = {"type": "imgframe", "x": round(bb["x"]), "y": round(bb["y"]), "w": round(bb["w"]), "h": round(bb["h"]), "name": name, "doc": f"{d}/frame.1.json",
            "render": f"{d}/render.1.png", "v": 1, "rv": round(rr["mtime"] / 1e6), "size": [W, H], "pics": list(dict.fromkeys(l["path"] for l in layers))}
    return card, capped


def frame_doc(card):
    st, doc = api("/file?p=" + urllib.parse.quote(card.get("doc", "")))
    if st != 200 or not isinstance(doc, dict): raise SystemExit(f"не прочитал {card.get('doc')}: {st}")
    return doc


def layer_lines(layers, depth=0):
    out = []
    for l in reversed(layers or []):   # top first, as the Layers panel shows them
        k = l.get("kind"); what = l.get("path") if k == "pic" else l.get("file", "") if k == "paint" else "Color Grading" if k == "grade" else ""
        geo = f" {round(abs(l.get('w', 0)))}×{round(abs(l.get('h', 0)))} @ {round(l.get('x', 0))},{round(l.get('y', 0))}" if k in ("pic", "paint") else ""
        flags = [f for f, on in (("скрыт", l.get("visible") is False), (f"непрозр. {l.get('opacity')}%", (l.get("opacity") or 100) < 100), (l.get("blend"), l.get("blend") not in (None, "source-over", "pass")),
                                 ("обтравка", l.get("clip")), ("маска", bool(l.get("mask"))), ("оригинал", k == "pic")) if on]
        out.append(f"{'  ' * depth}{k} «{l.get('name')}»{geo} {what}" + (f" ({', '.join(flags)})" if flags else "") + f" [{l.get('id')}]")
        out += layer_lines(l.get("children"), depth + 1)
    return out


def op_frame(b, args, kv):
    """frame REF... [name=..]: the pictures into one frame; frame each REF...: every picture into its own frame at its place; frame unframe F:
    the pictures back onto the page where they lie in it; frame rename F "Имя": a new version with the new name; frame layers F: its layers"""
    sub = args[0] if args and args[0] in ("each", "unframe", "rename", "layers") else "make"
    rest = args[1:] if sub != "make" else args
    if sub in ("make", "each"):
        ids = frame_sel_pics(b, rest)
        n0 = sum(1 for it in b["items"].values() if it.get("type") == "imgframe")
        groups = [ids] if sub == "make" else [[i] for i in ids]
        lines = []
        for k, g in enumerate(groups):
            name = str(kv["name"]) if "name" in kv and sub == "make" else f"Фрейм {n0 + k + 1}"
            card, capped = build_frame(b, g, name)
            for i in g: del b["items"][i]
            for gr in b["groups"].values(): gr["members"] = [m for m in gr["members"] if m in b["items"]]
            fid = uid("f"); b["items"][fid] = card; regroup_one(b, fid)
            lines.append(f"frame {fid} «{name}» {card['size'][0]}×{card['size'][1]} px из {len(g)}: {', '.join(card['pics'][:4])}" + (" … " if len(card["pics"]) > 4 else "") + (" (уменьшен до 8000 px)" if capped else ""))
        return "\n".join(lines)
    if not rest: raise SystemExit(f"frame {sub} ФРЕЙМ")
    fid = frame_ref(b, rest[0]); card = b["items"][fid]; doc = frame_doc(card)
    if sub == "layers":
        return f"F «{doc.get('name') or card.get('name')}» {doc['size'][0]}×{doc['size'][1]} px, версия {doc.get('v', 0)}, фон {doc.get('background') or 'прозрачный'} [{fid}]\n" + "\n".join(layer_lines(doc.get("layers")))
    if sub == "rename":
        new = str(kv.get("name") or (rest[1] if len(rest) > 1 else "")).strip()
        if not new: raise SystemExit('frame rename ФРЕЙМ "Новое имя"')
        d = card["doc"].rsplit("/", 1)[0]
        st, ver = api(f"/api/plugin/frames/versions", {"dir": d}); v = ver.get("next", 1) if st == 200 and isinstance(ver, dict) else (card.get("v") or 0) + 1
        doc.update(name=new, v=v, render=card["render"])   # the same render: only the name changed
        post_bytes(f"/api/file?p={urllib.parse.quote(f'{d}/frame.{v}.json')}", json.dumps(doc, ensure_ascii=False, indent=1).encode())
        old = card.get("name"); card.update(name=new, doc=f"{d}/frame.{v}.json", v=v)
        return f"frame {fid} «{old}» → «{new}» (версия {v})"
    # unframe: as «Разобрать фрейм» on the canvas
    def pics(ls):
        out = []
        for l in ls or []:
            if l.get("kind") == "pic" and l.get("path"): out.append(l)
            out += pics(l.get("children"))
        return out
    ls = pics(doc.get("layers")); k = card["w"] / doc["size"][0]
    if not ls: raise SystemExit("во фрейме нет картинок из библиотеки")
    del b["items"][fid]
    for g in b["groups"].values(): g["members"] = [m for m in g["members"] if m in b["items"]]
    back = []
    for l in ls:
        o = dict((l.get("board") or {}).get("item") or {}); was = (l.get("board") or {}).get("id")
        pid = was if was and was not in b["items"] else uid("i")
        o.update(path=l["path"], x=round(card["x"] + l["x"] * k), y=round(card["y"] + l["y"] * k), w=round(abs(l["w"]) * k), crop=l.get("crop"))
        if not o.get("ar"): o["ar"] = abs(l["w"] / l["h"]) if l.get("h") else 1
        if (l.get("opacity") or 100) < 100: o["opacity"] = round(l["opacity"]) / 100
        else: o.pop("opacity", None)
        b["items"][pid] = o; regroup_one(b, pid); back.append(pid)
    return f"unframe «{card.get('name')}»: {len(back)} картинок снова на странице: {', '.join(back)}"



OPS = {"group": op_group, "block": op_block, "arrange": op_arrange, "remove": op_remove, "fit": op_fit, "move": op_move, "set": op_set, "point": op_point, "note": op_note, "text": op_text, "htmlframe": op_htmlframe, "frame": op_frame}


def parse(script):
    lex = shlex.shlex(script, posix=True, punctuation_chars=";"); lex.whitespace_split = True
    cmds, cur = [], []
    for t in lex:
        if t == ";":
            if cur: cmds.append(cur); cur = []
        else: cur.append(t)
    if cur: cmds.append(cur)
    return cmds


def apply(b, cmds):
    out = []
    for c in cmds:
        if c[0] not in OPS: raise SystemExit(f"не знаю команду {c[0]}: есть {', '.join(OPS)}")
        args = [a for a in c[1:] if not re.fullmatch(r"[a-z]+=.*", a, re.S)]
        kv = {}
        for a in c[1:]:
            if re.fullmatch(r"[a-z]+=.*", a, re.S):
                key, v = a.split("=", 1); kv[key] = value(b, v, key)
        out.append(OPS[c[0]](b, args, kv))
    return out


def do(script, page, label, dry):
    global LABEL; LABEL = label
    cmds = parse(script)
    for attempt in range(4):
        _, b = api(f"/api/board?name={page}")
        before = json.loads(json.dumps(b))
        log = apply(b, cmds)
        if dry: print("\n".join(log) + "\n(проба, не сохранено)"); report(before, b); return
        if attempt == 0:
            _, e = api("/api/history", {"action": "save", "name": page, "who": "ai", "label": f"до: {label}"})
        code, res = api(f"/api/board?name={page}", b)
        if code == 200: break
        if code != 409: raise SystemExit(f"сервер не сохранил: {code} {res}")
    else:
        raise SystemExit("владелец все время сохраняет, не смог записать; попробуй еще раз")
    _, e2 = api("/api/history", {"action": "save", "name": page, "who": "ai", "label": f"после: {label}"})
    print("\n".join(log)); print(f"ревизия {res['revision']} · версии {e.get('id')} → {e2.get('id')}")
    report(before, b)


# ---- checking (owner 2026-10-01: another agent laid pictures out crooked, on top of each other, half out of their groups)
def problems(b):
    """what looks broken on the page, keyed so a change can be told from what was already there:
    pictures over pictures, crooked rows and columns, pictures half in a group frame, group frames cutting into each other"""
    pics = {id: rect(b, id) for id, it in b["items"].items() if is_pic(it)}
    if not pics: return {}
    w = sorted(r["w"] for r in pics.values())[len(pics) // 2]; tol, far = w * .025, w * .15   # a near miss: under ~8 of 320 nobody sees it, over ~48 it is a deliberate stagger
    cell, grid = w * 3, {}
    for id, r in pics.items():
        for gx in range(int(r["x"] // cell), int((r["x"] + r["w"]) // cell) + 1):
            for gy in range(int(r["y"] // cell), int((r["y"] + r["h"]) // cell) + 1): grid.setdefault((gx, gy), []).append(id)
    out, seen = {}, set()
    for ids in grid.values():
        for i, a in enumerate(ids):
            for c in ids[i + 1:]:
                k = tuple(sorted((a, c)))
                if k in seen: continue
                seen.add(k); r1, r2 = pics[a], pics[c]
                ox = min(r1["x"] + r1["w"], r2["x"] + r2["w"]) - max(r1["x"], r2["x"]); oy = min(r1["y"] + r1["h"], r2["y"] + r2["h"]) - max(r1["y"], r2["y"])
                if ox > 0 and oy > 0 and ox * oy > .05 * min(r1["w"] * r1["h"], r2["w"] * r2["h"]):
                    out[("over",) + k] = f"кадры {a} и {c} лежат друг на друге (x {round(r1['x'])} y {round(r1['y'])})"
                elif oy > .5 * min(r1["h"], r2["h"]) and -w < ox <= 0 and tol < abs(r1["y"] - r2["y"]) <= far:
                    out[("row",) + k] = f"ряд не ровный: {a} и {c} по верху расходятся на {round(abs(r1['y'] - r2['y']))} (y {round(r1['y'])})"
                elif ox > .5 * min(r1["w"], r2["w"]) and -w < oy <= 0 and tol < abs(r1["x"] - r2["x"]) <= far:
                    out[("col",) + k] = f"колонка не ровная: {a} и {c} по левому краю расходятся на {round(abs(r1['x'] - r2['x']))} (x {round(r1['x'])})"
    for gid, g in b["groups"].items():   # the notes of a group's sub-blocks stand in one column (owner 2026-10-02: no staircases)
        ns = sorted((b["items"][m]["x"], m) for m in g["members"] if b["items"].get(m, {}).get("type") == "note")
        for (x1, a), (x2, c) in zip(ns, ns[1:]):
            if tol < x2 - x1 <= w * .5:
                out[("notes", a, c)] = f"заметки «{first_line(b['items'][a].get('text'))[:25]}» и «{first_line(b['items'][c].get('text'))[:25]}» не в одну колонку: {round(x2 - x1)}"
    for gid, g in b["groups"].items():
        mem = set(g["members"]); title = first_line(g.get("title")) or "группа"
        for id, r in pics.items():
            if inter(r, g) and not (g["x"] <= r["x"] and g["y"] <= r["y"] and r["x"] + r["w"] <= g["x"] + g["w"] and r["y"] + r["h"] <= g["y"] + g["h"]):
                out[("edge", gid, id)] = f"кадр {id} торчит из рамки «{title}»" + ("" if id in mem else " (и не входит в нее)")
        for g2id, g2 in b["groups"].items():
            if g2id <= gid or not inter(g, g2): continue
            inside = lambda a, c: c["x"] <= a["x"] and c["y"] <= a["y"] and a["x"] + a["w"] <= c["x"] + c["w"] and a["y"] + a["h"] <= c["y"] + c["h"]
            if not inside(g, g2) and not inside(g2, g):
                out[("groups", gid, g2id)] = f"рамки «{title}» и «{first_line(g2.get('title')) or 'группа'}» залезают друг на друга"
    return out


def report(before, after):
    new = [m for k, m in problems(after).items() if k not in problems(before)]
    if new:
        print(f"⚠ после правки новых проблем: {len(new)}"); print("\n".join("  " + m for m in new[:12]))
        print("  поправь и проверь снова: hy.py check")


def cmd_check(b, ref):
    P = problems(b)
    if ref:
        r = resolve(b, ref)[3]; ids = {i for i in b["items"] if inter(rect(b, i), r)} | {g for g in b["groups"] if inter(b["groups"][g], r)}
        P = {k: m for k, m in P.items() if set(k[1:]) & ids}
    if not P: print("проблем не нашел"); return
    by = {}
    for k, m in P.items(): by.setdefault(k[0], []).append(m)
    names_ = {"over": "друг на друге", "row": "кривые ряды", "col": "кривые колонки", "edge": "торчат из рамок", "groups": "рамки пересекаются",
              "notes": "заметки лесенкой"}
    for kind, L in by.items():
        print(f"{names_[kind]}: {len(L)}"); print("\n".join("  " + m for m in L[:15]))


# ---- reading
def fmt(r): return f"x {round(r['x'])}..{round(r['x'] + r['w'])} y {round(r['y'])}..{round(r['y'] + r['h'])}"


def near_misses(b, tol, groups):
    cols = [(k, nm, r["x"]) for k, _, nm, r in names(b) if k in ("heading", "dot") or (groups and k == "group")]
    out = []
    for i, (k1, n1, x1) in enumerate(cols):
        for k2, n2, x2 in cols[i + 1:]:
            if k1 == k2 == "group": continue
            if 0.5 < abs(x1 - x2) <= tol: out.append(f"  ≈ «{n1}» ({k1}) x {round(x1)} и «{n2}» ({k2}) x {round(x2)}: {round(x2 - x1):+d}")
    return out


def inter(a, r): return a["x"] < r["x"] + r["w"] and a["x"] + a["w"] > r["x"] and a["y"] < r["y"] + r["h"] and a["y"] + a["h"] > r["y"]


def frame_pics(layers):
    """the library pictures inside an image frame's layers (frame.json), groups opened"""
    out = []
    for l in layers or []:
        if l.get("kind") == "pic" and l.get("path"): out.append(l["path"])
        out += frame_pics(l.get("children"))
    return out


def img_frames(b):
    """image frames on the page (Hyimg-frames, owner 2026-10-05): (id, name, size, pictures inside), read from each frame's frame.json;
    a frame whose file cannot be read shows what its card remembers"""
    out = []
    for id, it in b["items"].items():
        if it.get("type") != "imgframe": continue
        st, doc = api("/file?p=" + urllib.parse.quote(it.get("doc", ""))) if it.get("doc") else (404, None)
        doc = doc if st == 200 and isinstance(doc, dict) else {}
        size = doc.get("size") or it.get("size") or [0, 0]
        out.append((id, doc.get("name") or it.get("name") or "фрейм", size, frame_pics(doc.get("layers")) or list(it.get("pics") or []), it))
    return out


def frame_line(b, id, nm, size, pics, it):
    return (f"F «{nm[:40]}» {size[0]}×{size[1]} px · картинок {len(pics)}: {', '.join(pics[:6])}" + (" …" if len(pics) > 6 else "")
            + f"  {fmt(rect(b, id))}  {it.get('doc', '')}  [{id}]")


def cmd_map(b, ref, tol, groups):
    L = names(b); area = None
    if ref:
        r = resolve(b, ref)[3]; m = max(r["w"], r["h"], 2000) * .6
        area = {"x": r["x"] - m, "y": r["y"] - m, "w": r["w"] + 2 * m, "h": r["h"] + 2 * m}
        L = [n for n in L if inter({**n[3], "w": max(n[3]["w"], 1), "h": max(n[3]["h"], 1)}, area)]
        print(f"область вокруг «{ref}»: {fmt(area)}")
    tag = {"heading": "H", "group": "G", "note": "N", "timeline": "L", "dot": " ·"}
    tls = {}
    for k, id, nm, r in L:
        if k == "dot": tls.setdefault(id.split("/")[0], []).append(f"{nm} {round(r['x'])}"); continue
    for k, id, nm, r in sorted(L, key=lambda n: (n[0] != "timeline", n[0] != "heading", round(n[3]["x"] / 500), n[3]["y"])):
        if k == "dot" or (k == "note" and not ref): continue   # the overview leaves notes out: map <name> shows them
        extra = f" · {len(b['groups'][id]['members'])} кадров" if k == "group" else ""
        if k == "timeline": extra = " · " + " · ".join(tls.get(id, []))
        if k == "note" and b["items"][id].get("color") == "blue": extra = " · моя"
        print(f"{tag[k]} {nm[:40]}  {fmt(r)}{extra}  [{id}]")
    for f in img_frames(b):   # an image frame and the pictures inside it (they count as lying on the page)
        if not area or inter(rect(b, f[0]), area): print(frame_line(b, *f))
    pics = [id for id, it in b["items"].items() if is_pic(it) and (not area or inter(rect(b, id), area))]
    grouped = {m for g in b["groups"].values() for m in g["members"]}
    if not ref: print(f"заметок {sum(1 for n in L if n[0] == 'note')}: видны в map <название>")
    print(f"кадров: {len(pics)}, вне групп {sum(1 for p in pics if p not in grouped)} · ревизия {b.get('revision')}")
    nm = near_misses(b, tol, groups) if not ref else []
    if nm: print(f"почти на одной вертикали (до {tol}):"); print("\n".join(nm[:30]))


def cmd_find(b, q):
    for k, id, nm, r in names(b):
        if norm(q) in norm(nm) or q == id: print(f"{k} «{nm[:50]}» {fmt(r)} [{id}]")
    grouped = {m: first_line(g.get("title")) for g in b["groups"].values() for m in g["members"]}
    for id, it in b["items"].items():   # pictures by a part of their path
        if is_pic(it) and (norm(q) in norm(it["path"]) or q == id):
            print(f"pic {it['path']} {fmt(rect(b, id))}" + (f" в «{grouped[id]}»" if id in grouped else " вне групп") + f" [{id}]")
    for id, nm, size, pics, it in img_frames(b):   # an image frame by its name, or a picture inside it by a part of its path
        inside = [p for p in pics if norm(q) in norm(p)]
        if norm(q) in norm(nm) or q == id: print(frame_line(b, id, nm, size, pics, it))
        for p in inside: print(f"pic {p} во фрейме «{nm[:40]}» {fmt(rect(b, id))} [{id}]")


IMG_EXT = ((b"\x89PNG", ".png"), (b"\xff\xd8", ".jpg"), (b"RIFF", ".webp"))   # by the first bytes: downloads often come as bare UUIDs


def cmd_save(files, to, move=False):
    """files into a library folder without the pictures the library has already (owner 2026-10-02: "so we don't load the same
    pictures ten times"): same bytes under another name or in another folder count as the same picture"""
    import hashlib, shutil
    root = os.path.realpath(api("/api/health")[1]["libraryRoot"])
    dest = os.path.realpath(to if os.path.isabs(to) else os.path.join(root, to))
    if not dest.startswith(root + os.sep): raise SystemExit(f"--to должна быть папкой внутри библиотеки {root}")
    sha = lambda f: hashlib.sha1(open(f, "rb").read()).hexdigest()
    pics = {}
    for f in files:
        head = open(f, "rb").read(12)
        ext = next((e for magic, e in IMG_EXT if head.startswith(magic) and (e != ".webp" or head[8:12] == b"WEBP")), None)
        if not ext: print(f"не картинка, пропустил: {f}"); continue
        pics[f] = (sha(f), ext)
    known = api("/api/known", {"sha": sorted({s for s, _ in pics.values()})})[1].get("known", {})
    os.makedirs(dest, exist_ok=True)
    here = {}   # pictures already in the folder, in case the library has not hashed them yet (it looks every 3 s)
    for n in os.listdir(dest):
        q = os.path.join(dest, n)
        if os.path.isfile(q) and n.lower().endswith((".png", ".jpg", ".jpeg", ".webp")): here[sha(q)] = os.path.relpath(q, root)
    saved, dup = [], 0
    for f, (s, ext) in pics.items():
        was = known.get(s) or here.get(s)
        if was: print(f"уже есть: {os.path.basename(f)} = {was}"); dup += 1; continue
        stem, own = os.path.splitext(os.path.basename(f))
        if own.lower() not in (".png", ".jpg", ".jpeg", ".webp"): stem, own = os.path.basename(f), ext
        name, k = stem + own, 2
        while os.path.exists(os.path.join(dest, name)): name = f"{stem}~{k}{own}"; k += 1
        (shutil.move if move else shutil.copy2)(f, os.path.join(dest, name))
        side = os.path.splitext(f)[0] + ".json"
        if os.path.exists(side): (shutil.move if move else shutil.copy2)(side, os.path.join(dest, os.path.splitext(name)[0] + ".json"))
        here[s] = os.path.relpath(os.path.join(dest, name), root); saved.append(here[s])
    print(f"сохранил {len(saved)} в {os.path.relpath(dest, root)}, пропустил {dup}: уже в библиотеке" + (f", {len(files) - len(pics)} не картинки" if len(files) > len(pics) else ""))


def cmd_undocumented(pat):
    """library frames whose json says nothing about what they are (no prompt, no model): their card in Hyimg is empty"""
    import fnmatch
    items = [i for i in api("/api/items")[1] if not i["path"].startswith("ext/") and not ((i.get("prompt") or "").strip() or (i.get("model") or "").strip())
             and (not pat or fnmatch.fnmatch(i["path"], pat) or fnmatch.fnmatch(i["path"], pat.rstrip("/") + "/*"))]
    by = {}
    for i in items: by.setdefault(i["folder"], []).append(i["path"])
    print(f"{len(items)} кадров без описания в {len(by)} папках" + (f" по «{pat}»" if pat else ""))
    for f, ps in sorted(by.items(), key=lambda x: -len(x[1])): print(f"{len(ps):5}  {f}")


def cmd_dupes():
    items = api("/api/items?all=1")[1]
    mains = [i for i in items if i.get("copies")]
    print(f"{len(mains)} картинок лежат в библиотеке больше одного раза, лишних файлов {sum(len(i['copies']) for i in mains)}")
    for i in mains: print(f"{i['path']}  ←  " + ", ".join(i["copies"]))


# ---- notifications (owner 2026-10-03): the owner sees what an agent put on a board with a red dot on the bell, a few words, previews
# and a jump to the place. «do» writes one by itself whenever it adds something (--say gives the words, --quiet skips it for a pure
# rearrangement); «notify» writes one for anything else worth knowing.
def plural(n, one, few, many):
    return one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def send_notification(title, text, page, ids=(), previews=(), area=None, who=None):
    body = {"action": "add", "title": title, "text": text, "page": page, "ids": list(ids), "previews": list(previews), "who": who or os.environ.get("HYIMG_AGENT") or "агент"}
    if area: body["area"] = area
    code, res = api("/api/notifications", body)
    if code != 200: print(f"уведомление не записано: {code} {res}")
    else: print(f"уведомление: {title}")


def js_json(v):
    """JSON as JavaScript's JSON.stringify writes it (whole floats without .0), for names the canvas derives from it"""
    if isinstance(v, bool) or v is None: return json.dumps(v)
    if isinstance(v, float): return str(int(v)) if v.is_integer() else repr(v)
    if isinstance(v, int): return str(v)
    if isinstance(v, str): return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list): return "[" + ",".join(js_json(x) for x in v) + "]"
    return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + js_json(x) for k, x in v.items()) + "}"


def still_of(it, iid):
    """the still a 3D card shows, named as the 3D plugin's canvas.js names it (stillOf): its preview in a notification"""
    if it.get("type") != "model3d" or not it.get("scene") or not it.get("w") or not it.get("h"): return None
    bg = it.get("bg"); see = bool(bg) and (bool(bg.get("transparent")) or (bg.get("opacity", 100) if bg.get("opacity") is not None else 100) < 100)
    key = js_json([it.get("camera") or "", bg or None, int(it["w"] / it["h"] * 100 + 0.5) / 100])
    h = 0x811c9dc5
    for ch in key: h = ((h ^ ord(ch)) * 0x01000193) & 0xffffffff
    return f"{it['scene'].rsplit('/', 1)[0]}/.posters/{iid}-{h:08x}.{'png' if see else 'jpg'}"


def notify_added(before, after, page, say, label):
    """what «do» added to the page, told to the owner: how many pictures, notes, groups, the first pictures as previews, the area"""
    new = [i for i in after["items"] if i not in before["items"]]
    new_groups = [g for g in after["groups"] if g not in before["groups"]]
    if not new and not new_groups: return
    pics = [i for i in new if is_pic(after["items"][i])]
    notes = [i for i in new if after["items"][i].get("type") == "note"]
    cards = [i for i in new if after["items"][i].get("type") == "model3d"]
    heads = [i for i in new if after["items"][i].get("type") == "text"]
    other = [i for i in new if i not in pics and i not in notes and i not in cards and i not in heads]
    parts = []
    if pics: parts.append(f"{len(pics)} {plural(len(pics), 'кадр', 'кадра', 'кадров')}")
    if notes: parts.append(f"{len(notes)} {plural(len(notes), 'заметка', 'заметки', 'заметок')}")
    if cards: parts.append(f"{len(cards)} {plural(len(cards), '3D-карточка', '3D-карточки', '3D-карточек')}")   # 2026-10-04: they were not counted
    if heads: parts.append(f"{len(heads)} {plural(len(heads), 'заголовок', 'заголовка', 'заголовков')}")
    if other: parts.append(f"{len(other)} {plural(len(other), 'объект', 'объекта', 'объектов')}")
    if new_groups: parts.append(f"{len(new_groups)} {plural(len(new_groups), 'группа', 'группы', 'групп')}")
    rs = [rect(after, i) for i in new] + [after["groups"][g] for g in new_groups]
    x0, y0 = min(r["x"] for r in rs), min(r["y"] for r in rs)
    area = {"x": x0, "y": y0, "w": max(r["x"] + r["w"] for r in rs) - x0, "h": max(r["y"] + r["h"] for r in rs) - y0}
    title = say or ("На доске новое: " + ", ".join(parts))
    text = ("На доске новое: " + ", ".join(parts) + ". ") if say else ""
    previews = [after["items"][i]["path"] for i in pics] + [p for p in (still_of(after["items"][i], i) for i in cards) if p]   # a 3D card shows its still
    send_notification(title, text + (label if label != "правка ИИ" else ""), page, new + new_groups, previews[:6], area)


LAYOUT_WARN = ("ВНИМАНИЕ: раскладка переносит файлы картинок проекта на диске. Агент запускает apply или undo только по прямому слову"
               " владельца в этом разговоре, никогда сам и никогда на проектах владельца для проверки (для тестов есть временный сервер).")


def cmd_layout(args):
    """folders as on the board (owner 2026-10-05, server.py layout_*, foldersync.py): plan is read only, apply and undo need a flag"""
    sub = args[0] if args else "plan"
    if sub == "plan":
        code, p = api("/api/layout/plan")
        if code != 200: raise SystemExit(f"план не посчитан: {code} {p}")
        print(f"переедут {p['move']} (с ними json: {p['sidecars']}), новых папок {p['make']}, пустых папок удалится {p['remove']}, "
              f"останутся на месте {p['stay']} с досок" + (f" и {p['off_board']} не на досках" if p.get("off_board") is not None else ""))
        print(f"совпали имена: {p['renamed']}, в нескольких местах (в {('папку «' + p['multi_dir'] + '»') if p.get('multi_dir') else 'корень'}): {p['multi']}, нет файла: {p['missing']}, старые пути на досках: {p['fixes']}")
        if p.get("reasons"): print("не двигаются: " + ", ".join(f"{k} {v}" for k, v in p["reasons"].items()))
        print("страницы: " + ", ".join(p.get("pages", [])) + (" · режим «всегда как на доске» включен" if p.get("auto") else ""))
        for e in p.get("examples", []): print(f"  было  {e['from']}\n  стало {e['to']}")
        print(LAYOUT_WARN, file=sys.stderr)
        return
    if sub not in ("apply", "undo"): raise SystemExit("hy.py layout plan | apply --owner-said-yes | undo --owner-said-yes")
    print(LAYOUT_WARN, file=sys.stderr)
    if "--owner-said-yes" not in args: raise SystemExit(f"не запущено: нужен флаг --owner-said-yes (hy.py layout {sub} --owner-said-yes)")
    code, res = api(f"/api/layout/{sub}", {"who": "agent"} if sub == "apply" else {})
    print(code, json.dumps(res, ensure_ascii=False))


def main(argv):
    page, label, dry, tol, groups, to, move = None, "правка ИИ", False, 1000, False, None, False
    say, quiet, text, ids = None, False, "", []
    a = []
    it = iter(argv)
    for x in it:
        if x == "--page": page = next(it)
        elif x == "--port": global BASE; BASE = f"http://localhost:{int(next(it))}"
        elif x == "--label": label = next(it)
        elif x == "--dry": dry = True
        elif x == "--tol": tol = float(next(it))
        elif x == "--groups": groups = True
        elif x == "--to": to = next(it)
        elif x == "--move": move = True
        elif x == "--say": say = next(it)
        elif x == "--quiet": quiet = True
        elif x == "--text": text = next(it)
        elif x == "--ids": ids = [v for v in next(it).split(",") if v]
        else: a.append(x)
    if not a: print(__doc__); return
    c = a[0]
    if c == "guide":
        code, txt = api_text("/agent"); print(txt); return
    if c == "save":
        if not to or len(a) < 2: raise SystemExit("hy.py save ФАЙЛЫ... --to ПАПКА [--move]")
        return cmd_save(a[1:], to, move)
    if c == "dupes": return cmd_dupes()
    if c == "layout": return cmd_layout(a[1:])
    if c == "undocumented": return cmd_undocumented(a[1] if len(a) > 1 else "")
    if page is None:   # the page the owner is looking at
        try: page = (api("/api/live")[1].get("canvas") or {}).get("page") or "main"
        except Exception: page = "main"
    try: title = next((p.get("title", p["id"]) for p in api("/api/pages")[1]["pages"] if p["id"] == page), page)
    except Exception: title = page
    print(f"# страница «{title}» ({page})")
    if c == "do" and all(cm[:2] == ["frame", "layers"] for cm in parse(" ".join(a[1:]))):   # reading a frame's layers saves nothing
        _, b = api(f"/api/board?name={page}"); print("\n".join(apply(b, parse(" ".join(a[1:]))))); return
    if c == "do":
        _, b0 = api(f"/api/board?name={page}")
        do(" ".join(a[1:]), page, label, dry)
        if not dry and not quiet:
            _, b1 = api(f"/api/board?name={page}"); notify_added(b0, b1, page, say, label)
        return
    if c == "notify":
        if len(a) < 2: raise SystemExit('hy.py notify "что сделано" [--text "подробнее"] [--ids a,b] [--page p]')
        _, b = api(f"/api/board?name={page}")
        have = [i for i in ids if i in b["items"] or i in b["groups"]]
        rs = [rect(b, i) if i in b["items"] else b["groups"][i] for i in have]
        area = None
        if rs:
            x0, y0 = min(r["x"] for r in rs), min(r["y"] for r in rs)
            area = {"x": x0, "y": y0, "w": max(r["x"] + r["w"] for r in rs) - x0, "h": max(r["y"] + r["h"] for r in rs) - y0}
        prev = [b["items"][i]["path"] for i in have if i in b["items"] and is_pic(b["items"][i])][:6]
        return send_notification(" ".join(a[1:]), text, page, have, prev, area)
    if c == "hist":
        _, L = api(f"/api/history?name={page}")
        for e in L[-int(a[1] if len(a) > 1 else 8):]: print(e.get("id"), e.get("who"), e.get("label"), "rev", e.get("revision"))
        return
    if c == "restore":
        code, res = api("/api/history", {"action": "restore", "name": page, "id": a[1]}); print(code, res); return
    _, b = api(f"/api/board?name={page}")
    if c == "map": return cmd_map(b, " ".join(a[1:]) or None, tol, groups)
    if c == "find": return cmd_find(b, " ".join(a[1:]))
    if c == "check": return cmd_check(b, " ".join(a[1:]) or None)
    raise SystemExit(f"не знаю {c}: map, find, check, do, notify, hist, restore, guide, save, dupes, undocumented")


if __name__ == "__main__":
    main(sys.argv[1:])
