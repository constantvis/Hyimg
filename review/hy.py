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
  hy.py features [слово]        what Hyimg can do and how an agent does each thing (review/features.json); a word shows those in full
  hy.py pages | page new "Имя"  the pages with their picture counts | a new page (its id printed, for --page)
  hy.py presets | preset save "Имя" REF [only=grade,crop] | preset delete "Имя"   the project's presets of properties

Commands inside do (separated by ;):
  move REF x=V y=V | dx=N dy=N       a group moves with its pictures, a note with the pictures in its zone
  fit GROUP                           the frame fitted to its contents, a group's air around
  set REF key=V ...                   any field: text, title, w, fs, color
  point TL "Label" x=V                a timeline dot by its label: moved, or added if new (TL: the timeline, or any label on it)
  note "text" x=V y=V [w=N] [color=blue]
  text "Heading" x=V y=V [fs=N]
  model FILE x=V y=V | near=REF [w=360]   a 3D card (plugin 3d) from a library glb or STEP/IGES (FreeCAD converts it): a new scene
                                      3d/scenes/<stamp>-<name>/scene.json with the file on the floor, two lights and a camera
  html FILE.html x=V y=V | near=REF [w=480] [vw=1280] [vh=800]   Dev studio's HTML card (plugin dev); refuses without the plugin
  crop REF... box=x0,y0,x1,y1 | trim REF... in=S out=S | opacity REF... value=0.5 | pdfpage REF... n=2    a card's look, by the
                                      canvas's rules (what does not apply is skipped and counted); clear=1 takes it off
  grade REF... exposure=0.3 saturation=-20 temp=15 hue=30 sat=10 light=0 | json='{...}'   the colour grade (plugin frames) of pictures
                                      and image frames; hue/sat/light: Hue/Saturation's Master; clear=1 takes it off
  mask REF... alpha=1 | file=PATH.png | clear=1   the master mask (plugin frames): from the picture's own alpha, or a png
  link NOTE REF...                    arrows from a note to pictures, cards or groups (clear=1 takes them off)
  block PATTERN... into=GROUP | near=REF [side=right|below|left|above] | x=V y=V   [cols=8] [w=N] [gap=24] [note="текст"] [group="Название"]
                                      into= the usual way: a sub-group (note + rows) under the last block of that theme group, the frame
                                      grows and what stands below moves down; group= only for a genuinely new theme
                                      library pictures as a block, one row per pattern (folder or glob), with a zone note and a group;
                                      near= finds free room next to REF by itself (nothing overlaps, a group's air between)
  arrange ID|"glob"|REF... near=REF | x=V y=V [cols] [note=] [group=]
                                      pictures already on the page, laid out again as a tidy block (one row per argument)
  group "Название" REF...             a group frame around notes (with their zone pictures), headings, groups
  topage PAGE REF...                  onto another page (its name or id), as «Move to page ›» on the canvas: a group with everything in
                                      it, a note with its zone; the layout kept, where they stood when that room is free there, else right
                                      of its content; arrows to what stays are dropped; versions before and after on both pages
  props from=REF to=REF,REF... [only=grade,crop]   the canvas's «Paste properties»: crop, trim, size, opacity, PDF page, colour grade
  props preset=NAME to=REF...         (a plugin's kind, the mask, as the item's field of its name); preset= one saved on the canvas
  front REF... | forward | backward | back   the draw order, as «Order ›» on the canvas (⌥⌘] ⌘] ⌘[ ⌥⌘[): among the siblings in the
                                      same group (or the page's top level) and layer only; several keep their order among themselves
  remove REF... | remove "glob"       take things off this page: pictures by id or path glob, notes, headings; a group goes with
                                      everything in it, as Delete on the canvas (only=frame keeps the contents, like ⇧⌘G).
                                      A picture gone from every page is the archive = rejected
  frame REF... [name="Имя"]           the pictures (ids, path globs, a group with its nested groups, a note's zone) into one image frame,
                                      as ⌥⌘G: they leave the page and lie inside it; frame each REF...: every picture its own frame (⌥⇧⌘G)
  frame unframe F | frame rename F "Имя" | frame layers F   take a frame apart (pictures back where they lie in it), a new name (a new
                                      version of its frame.json), its layers top first (read only, nothing is saved)
  cards3d SCENE beside=REF into=GROUP [align=NOTE] [cameras=ID,…] [cols=4] [w=320] [note="текст"]   3D cards of a scene, a card per
                                      camera, in rows with a note, right of REF (a note's zone) inside GROUP, whose frame grows; or at x= y=
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
        path += "&who=ai" + ("&label=" + urllib.parse.quote(LABEL) if LABEL else "") + ("&agent=" + urllib.parse.quote(os.environ["HYIMG_AGENT"]) if os.environ.get("HYIMG_AGENT") else "")   # Home names the agent in a board's news
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
    r = rect(b, m.group(1)) if m.group(1) in b["items"] else resolve(b, m.group(1))[3]   # any item by its id: a 3D card, an HTML frame, a note
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
        if r in b["items"]: ids.append(r); continue   # anything by its id: a picture, a 3D card, an image frame, an HTML card (2026-10-06)
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


CARD_TYPES = {"htmlframe": "HTML-фрейм", "html": "HTML-карточка", "model3d": "3D-карточка"}


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
    cards = {}   # the plugins' cards: how many of each, find shows them by their file
    for id, it in b["items"].items():
        if it.get("type") in CARD_TYPES and (not area or inter(rect(b, id), area)): cards[it["type"]] = cards.get(it["type"], 0) + 1
    if cards: print("карточки плагинов: " + ", ".join(f"{CARD_TYPES[k]} {n}" for k, n in cards.items()) + " (hy.py find <файл> дает их id)")
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
    for id, it in b["items"].items():   # plugins' cards by their file or name: an HTML frame or card, a 3D card's scene (2026-10-06)
        if it.get("type") in CARD_TYPES and (q == id or any(norm(q) in norm(it.get(k) or "") for k in ("src", "scene", "name"))):
            print(f"{it['type']} {it.get('src') or it.get('scene') or ''}" + (f" «{it['name']}»" if it.get("name") else "") + f" {fmt(rect(b, id))} [{id}]")
    for id, nm, size, pics, it in img_frames(b):   # an image frame by its name, or a picture inside it by a part of its path
        inside = [p for p in pics if norm(q) in norm(p)]
        if norm(q) in norm(nm) or q == id: print(frame_line(b, id, nm, size, pics, it))
        for p in inside: print(f"pic {p} во фрейме «{nm[:40]}» {fmt(rect(b, id))} [{id}]")


IMG_EXT = ((b"\x89PNG", ".png"), (b"\xff\xd8", ".jpg"), (b"RIFF", ".webp"))   # by the first bytes: downloads often come as bare UUIDs
OTHER_MEDIA = (".mp4", ".mov", ".m4v", ".webm", ".pdf", ".psd", ".psb", ".ai", ".tif", ".tiff", ".heic", ".heif", ".svg", ".glb", ".gltf", ".obj", ".stl", ".fbx", ".step", ".stp", ".iges", ".igs")   # by the name


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
        if not ext and f.lower().endswith(OTHER_MEDIA): ext = os.path.splitext(f)[1].lower()   # a video, PDF, design or 3D file by its name (2026-10-06)
        if not ext: print(f"не картинка, пропустил: {f}"); continue
        pics[f] = (sha(f), ext)
    known = api("/api/known", {"sha": sorted({s for s, _ in pics.values()})})[1].get("known", {})
    os.makedirs(dest, exist_ok=True)
    here = {}   # pictures already in the folder, in case the library has not hashed them yet (it looks every 3 s)
    for n in os.listdir(dest):
        q = os.path.join(dest, n)
        if os.path.isfile(q) and n.lower().endswith((".png", ".jpg", ".jpeg", ".webp") + OTHER_MEDIA): here[sha(q)] = os.path.relpath(q, root)
    saved, dup = [], 0
    for f, (s, ext) in pics.items():
        was = known.get(s) or here.get(s)
        if was: print(f"уже есть: {os.path.basename(f)} = {was}"); dup += 1; continue
        stem, own = os.path.splitext(os.path.basename(f))
        if own.lower() not in (".png", ".jpg", ".jpeg", ".webp") + OTHER_MEDIA: stem, own = os.path.basename(f), ext
        name, k = stem + own, 2
        while os.path.exists(os.path.join(dest, name)): name = f"{stem}~{k}{own}"; k += 1
        (shutil.move if move else shutil.copy2)(f, os.path.join(dest, name))
        pic = own.lower() in (".png", ".jpg", ".jpeg", ".webp")   # a picture's json is <name>.json, another kind's <name.ext>.json (server.py scan)
        side = next((x for x in (f + ".json", os.path.splitext(f)[0] + ".json") if os.path.exists(x)), None)
        if side: (shutil.move if move else shutil.copy2)(side, os.path.join(dest, (os.path.splitext(name)[0] if pic else name) + ".json"))
        here[s] = os.path.relpath(os.path.join(dest, name), root); saved.append(here[s])
    print(f"сохранил {len(saved)} в {os.path.relpath(dest, root)}, пропустил {dup}: уже в библиотеке" + (f", {len(files) - len(pics)} не медиафайлы" if len(files) > len(pics) else ""))


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


# ---- every card and look of the board through hy.py (2026-10-06, the «Playground» page of «Hyimg App»: an agent never writes board
# JSON by hand). Cards the plugins make in the browser (a 3D card from a 3D file, Dev studio's HTML card) and the looks a card keeps
# (crop, time, opacity, PDF page, colour grade, mask) by the canvas's own rules: prop_applies / prop_set, the «Paste properties» kinds.
# Also the pages, the presets of properties and the feature catalog (review/features.json: what Hyimg can do and how an agent does it).
FEATURES_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "features.json")
PLUGIN_NAMES = {"3d": ("3d", "hyimg-3d-studio", "hyimg-3d"), "frames": ("frames", "hyimg-frames"), "dev": ("dev", "hyimg-dev-studio", "dev-studio")}


def plugin_name(kind):
    """the name the running server knows a plugin by (its folder under plugins/), or None when it is not installed"""
    _, L = api("/api/plugins")
    have = {p.get("name") for p in L} if isinstance(L, list) else set()
    return next((n for n in PLUGIN_NAMES[kind] if n in have), None)


def place_at(b, kv, size, what):
    """the top left of a new card: x= y=, or near=REF [side=right|below|left|above] in free room"""
    if "x" in kv and "y" in kv: return round(kv["x"]), round(kv["y"])
    if "near" not in kv: raise SystemExit(f"{what}: укажи x= и y= или near=<что рядом> [side=right]")
    ref = str(kv["near"]); r = rect(b, ref) if ref in b["items"] or ref in b["groups"] else resolve(b, ref)[3]
    s = free_spot(b, r, {"x": 0, "y": 0, "w": size[0], "h": size[1]}, kv.get("side", "right"), 160)
    return s["x"], s["y"]


def _quat_look(eye, target):
    """[w, x, y, z] of a Blender camera or light at eye looking at target (its -z there, +y up), as scene.js look()"""
    import math
    z = [eye[i] - target[i] for i in range(3)]; n = math.sqrt(sum(v * v for v in z)) or 1; z = [v / n for v in z]
    up = [0, 0, 1]; x = [up[1] * z[2] - up[2] * z[1], up[2] * z[0] - up[0] * z[2], up[0] * z[1] - up[1] * z[0]]
    n = math.sqrt(sum(v * v for v in x)) or 1; x = [v / n for v in x]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    m = [[x[0], y[0], z[0]], [x[1], y[1], z[1]], [x[2], y[2], z[2]]]; tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1) * 2; q = [s / 4, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s]
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1 + m[0][0] - m[1][1] - m[2][2]) * 2; q = [(m[2][1] - m[1][2]) / s, s / 4, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s]
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1 + m[1][1] - m[0][0] - m[2][2]) * 2; q = [(m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, s / 4, (m[1][2] + m[2][1]) / s]
    else:
        s = math.sqrt(1 + m[2][2] - m[0][0] - m[1][1]) * 2; q = [(m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, s / 4]
    sg = -1 if q[0] < 0 else 1
    return [round(v * sg, 5) for v in q]


def _glb_box(data):
    """the box of a glb's meshes from its POSITION accessors (glTF keeps their min and max): (min, max) in glTF's y-up metres"""
    import struct
    if data[:4] != b"glTF": raise SystemExit("это не glb")
    n = struct.unpack("<I", data[12:16])[0]; doc = json.loads(data[20:20 + n])
    lo, hi = [float("inf")] * 3, [float("-inf")] * 3
    for m in doc.get("meshes", []):
        for p in m.get("primitives", []):
            a = doc["accessors"][p["attributes"]["POSITION"]]
            if a.get("min") and a.get("max"):
                lo = [min(lo[i], a["min"][i]) for i in range(3)]; hi = [max(hi[i], a["max"][i]) for i in range(3)]
    if lo[0] == float("inf"): raise SystemExit("в glb нет геометрии")
    return lo, hi


def _cad_glb(plugin, path):
    """a STEP or IGES file of the library as a glb, converted by FreeCAD through the 3D plugin's routes (cad.py), as the card does it"""
    for _ in range(400):
        code, st = api(f"/api/plugin/{plugin}/cad", {"path": path})
        if code != 200 or not isinstance(st, dict): raise SystemExit(f"FreeCAD не ответил: {code} {st}")
        if st.get("state") != "working": break
        time.sleep(0.9)
    if st.get("state") != "ready": raise SystemExit(f"FreeCAD не прочитал {path}: {st.get('reason') or st.get('state')} {st.get('error') or ''}")
    req = urllib.request.Request(BASE + f"/api/plugin/{plugin}/cadglb", data=json.dumps({"key": st["key"]}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r: return r.read()


def op_model(b, args, kv):
    """a 3D card from a 3D file of the library (glb, or STEP / IGES through FreeCAD): a new scene 3d/scenes/<stamp>-<name>/scene.json
    as the card's «Open file…» makes it (the file on the floor, a key and a fill light, one camera), and the card on the board"""
    if not args: raise SystemExit("model ФАЙЛ x= y= | near=ЧТО [w=360] [name=Имя]: glb, gltf-бинарник, step, stp, iges, igs из библиотеки")
    plugin = plugin_name("3d")
    if not plugin: raise SystemExit("плагин «3D-объекты» не установлен: scripts/install_plugins.sh --3d --yes, потом ⇧⌘R")
    path = args[0]; ext = os.path.splitext(path)[1].lower(); stem = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.splitext(os.path.basename(path))[0]).strip("._") or "model"
    if ext in (".step", ".stp", ".iges", ".igs"):
        h = 0x811c9dc5
        for ch in f"{path}@0": h = ((h ^ ord(ch)) * 0x01000193) & 0xffffffff
        glb = f"3d/converted/{h:08x}/{stem}.glb"
        if api_head(glb) != 200: post_bytes(f"/api/file?p={urllib.parse.quote(glb)}", _cad_glb(plugin, path))
    elif ext == ".glb": glb = path
    else: raise SystemExit(f"{ext}: hy.py кладет glb и STEP/IGES; obj, stl, fbx открой через карточку в приложении (она переводит их в glb)")
    with urllib.request.urlopen(BASE + "/file?p=" + urllib.parse.quote(glb), timeout=120) as r: data = r.read()
    lo, hi = _glb_box(data); size = [hi[i] - lo[i] for i in range(3)]; big = max(size)
    if not big > 0: raise SystemExit("в файле нет геометрии")
    k = 1 if 0.05 <= big <= 0.3 else 0.2 / big   # as engine.js putFile: its real size when it is a few cm to 30 cm, else 20 cm
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]; H = k * size[1]
    r5 = lambda v: round(v, 5) or 0
    nid = lambda: "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    f = max(0.45, min(4, 1.25 * k * big / 0.12))   # the new scene's camera is set for a 12 cm shape: as far again for this one's size
    key, fill, cam = [-0.45, -0.55, 0.55], [0.7, -0.2, 0.25], [round(0.32 * f, 4), round(-0.62 * f, 4), round(0.2 * f, 4)]
    doc = {"format": "hyimg-scene/1", "rev": 0, "by": "hy.py", "render": {"x": 1280, "y": 1600},
           "world": {"color": [0.18, 0.18, 0.18], "strength": 1, "exposure": 0, "look": "AgX"},
           "objects": [{"id": nid(), "name": kv.get("name") or stem, "src": {"type": "file", "path": glb}, "loc": [r5(-k * c[0]), r5(k * c[2]), r5(-k * lo[1] + 0.0005)],
                        "rot": [1, 0, 0, 0], "scale": [r5(k)] * 3, "ai": ""},
                       {"id": nid(), "name": "Floor", "src": {"type": "prim", "shape": "plane", "size": [3, 3, 0]}, "loc": [0, 0, 0], "rot": [1, 0, 0, 0], "scale": [1, 1, 1],
                        "color": "#c9c8c3", "ai": "studio floor"}],
           "lights": [{"id": nid(), "name": "Key", "type": "area", "loc": key, "rot": _quat_look(key, [0, 0, 0.08]), "color": [1, 1, 1], "power": 25, "size": 0.6, "size_y": 0.6, "shape": "SQUARE"},
                      {"id": nid(), "name": "Fill", "type": "area", "loc": fill, "rot": _quat_look(fill, [0, 0, 0.08]), "color": [1, 1, 1], "power": 8, "size": 1, "size_y": 1, "shape": "SQUARE"}],
           "cameras": [{"id": nid(), "name": "Camera 1", "loc": cam, "rot": _quat_look(cam, [0, 0, round(H / 2 + 0.003, 3)]), "lens": 70, "sensor": 36, "sensor_h": 24,
                        "fit": "AUTO", "shift": [0, 0], "clip": [0.01, 100]}],
           "removed": []}
    doc["active_camera"] = doc["cameras"][0]["id"]
    scene = f"3d/scenes/{time.strftime('%y%m%d-%H%M%S')}-{stem[:40]}/scene.json"
    post_bytes(f"/api/file?p={urllib.parse.quote(scene)}", json.dumps(doc, ensure_ascii=False, indent=1).encode())
    w = round(kv.get("w", 360)); h = round(w * 1600 / 1280); x, y = place_at(b, kv, (w, h), "model"); id = uid("m")
    b["items"][id] = {"type": "model3d", "scene": scene, "camera": doc["active_camera"], "x": x, "y": y, "w": w, "h": h}
    return f"model {id} «{path}» сцена {scene} x {x} y {y} (картинку карточки дорисует холст, когда страница откроется)"


def api_head(path):
    req = urllib.request.Request(BASE + "/file?p=" + urllib.parse.quote(path), method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return r.status
    except urllib.error.HTTPError as e: return e.code


def op_html(b, args, kv):
    """Dev studio's HTML card: an .html file of the library as a card (its first screen drawn by Chromium, the live page when big on
    screen, Dev mode on a double click), as the plugin's placeAs makes it"""
    if not args: raise SystemExit("html ФАЙЛ.html x= y= | near=ЧТО [w=480] [vw=1280] [vh=800]")
    if not plugin_name("dev") and not kv.get("force"):
        raise SystemExit("плагин «Dev studio» не установлен: карточка не нарисуется. Поставить: scripts/install_plugins.sh --dev --yes, потом ⇧⌘R"
                         " (force=1 положит ее все равно)")
    if api_head(args[0]) != 200: raise SystemExit(f"нет файла {args[0]}")
    vw, vh = int(kv.get("vw", 1280)), int(kv.get("vh", 800)); w = round(kv.get("w", 480)); h = round(w * vh / vw)
    x, y = place_at(b, kv, (w, h), "html"); id = uid("d")
    b["items"][id] = {"type": "html", "src": args[0], "vw": vw, "ar": round(vw / vh, 4), "pics": [args[0]], "x": x, "y": y, "w": w, "h": h}
    return f"html {id} «{args[0]}» {vw}×{vh} x {x} y {y}"


GRADE_KEYS = ("temp", "tint", "exposure", "contrast", "highlights", "shadows", "whites", "blacks", "texture", "clarity", "dehaze", "vibrance", "saturation", "sharpening")


def _look_value(kind, b, it, kv):
    """the value of one look from the do command's keys; None takes it off"""
    if kv.get("clear"): return None
    if kind == "crop":
        try: v = [float(x) for x in str(kv["box"]).split(",")]
        except (KeyError, ValueError): raise SystemExit("crop ЧТО... box=x0,y0,x1,y1 (доли кадра от 0 до 1) или clear=1")
        if len(v) != 4 or not (0 <= v[0] < v[2] <= 1 and 0 <= v[1] < v[3] <= 1): raise SystemExit("box: x0,y0,x1,y1, доли от 0 до 1, x0 < x1, y0 < y1")
        return v
    if kind == "trim":
        if "in" not in kv or "out" not in kv or not 0 <= float(kv["in"]) < float(kv["out"]): raise SystemExit("trim ЧТО... in=СЕКУНДЫ out=СЕКУНДЫ или clear=1")
        return [round(float(kv["in"]), 2), round(float(kv["out"]), 2)]
    if kind == "opacity":
        if not isinstance(kv.get("value"), float) or not 0 <= kv["value"] <= 1: raise SystemExit("opacity ЧТО... value=0.5 (от 0 до 1)")
        return kv["value"]
    if kind == "page":
        if not isinstance(kv.get("n"), float) or kv["n"] < 1: raise SystemExit("pdfpage ЧТО... n=2")
        return int(kv["n"])
    if kind == "grade":
        g = {}
        if kv.get("json"):
            try: g = json.loads(str(kv["json"]))
            except ValueError as e: raise SystemExit(f"json= не JSON: {e}")
            if not isinstance(g, dict): raise SystemExit("json= объект, например {\"exposure\": 0.3}")
        for k in GRADE_KEYS:
            if k in kv: g[k] = kv[k]
        hs = {k2: kv[k1] for k1, k2 in (("hue", "hue"), ("sat", "sat"), ("light", "light")) if k1 in kv}
        if hs: g.setdefault("hs", {})["master"] = dict(g.get("hs", {}).get("master", {}), **hs)
        if not g: raise SystemExit("grade ЧТО... exposure=0.3 saturation=-20 temp=15 hue=30 sat=10 light=0 или json='{...}' или clear=1")
        return g
    if kind == "mask":
        if kv.get("file"):
            if api_head(str(kv["file"])) != 200: raise SystemExit(f"нет файла маски {kv['file']}")
            return {"file": str(kv["file"])}
        if kv.get("alpha"): return _alpha_mask(it)
        raise SystemExit("mask ЧТО... alpha=1 (из прозрачности картинки) | file=ПУТЬ.png | clear=1")


def _alpha_mask(it):
    """the picture's own alpha as its master mask, as «Mask from alpha» on the canvas (mask.js alphaOf): white where it shows"""
    import io
    try: from PIL import Image
    except ImportError: raise SystemExit("для alpha=1 нужен Pillow (pip install pillow)")
    src = it.get("render") if it.get("type") == "imgframe" else it.get("path")
    with urllib.request.urlopen(BASE + "/file?p=" + urllib.parse.quote(src), timeout=120) as r: im = Image.open(io.BytesIO(r.read()))
    a = im.convert("RGBA").getchannel("A")
    if a.getextrema()[0] >= 250: return False   # nothing transparent
    k = min(1, (4e6 / (im.width * im.height)) ** .5)
    if k < 1: a = a.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    out = Image.new("RGBA", a.size, (255, 255, 255, 0)); out.putalpha(a)
    buf = io.BytesIO(); out.save(buf, "PNG")
    path = "frames/board-masks/masks/m" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12)) + ".png"
    post_bytes(f"/api/file?p={urllib.parse.quote(path)}", buf.getvalue())
    return {"file": path}


def look_op(kind):
    def op(b, args, kv):
        if not args: raise SystemExit(f"{kind}: что менять? id, имя, группа или маска путей")
        ids = list(dict.fromkeys(i for a in args for i in _prop_items(b, a)))
        done, skip, none = [], [], []
        for i in ids:
            it = b["items"][i]
            if not prop_applies(kind, it): skip.append(i); continue
            v = _look_value(kind, b, it, kv)
            if v is False: none.append(i); continue
            if v is None and kind == "crop": it.pop("crop", None)
            else: prop_set(kind, it, v)
            done.append(i)
        name = {"page": "pdfpage"}.get(kind, kind)
        msg = f"{name} {'снят' if kv.get('clear') else PROP_RU.get(kind, kind)}: {len(done)} из {len(ids)}" + (f" [{', '.join(done[:6])}]" if done else "")
        if skip: msg += f" · не подходит {len(skip)}: {', '.join(skip[:4])}"
        if none: msg += f" · без прозрачных пикселей {len(none)}"
        return msg
    op.__name__ = f"op_{kind}"
    return op


def op_link(b, args, kv):
    """arrows from a note to things (as dragging from a note's edge on the canvas): the note is about them wherever they lie"""
    if len(args) < 2: raise SystemExit("link ЗАМЕТКА ЧТО...: стрелки от заметки к кадрам, карточкам, группам (clear=1 снимает все)")
    k, nid, nm, _ = resolve(b, args[0], {"note"})
    n = b["items"][nid]
    if kv.get("clear"): n["to"] = []; return f"link «{nm[:30]}»: стрелки сняты"
    tg = []
    for r in args[1:]:
        if r in b["items"] or r in b["groups"]: tg.append(r)
        else: tg.append(resolve(b, r)[1])
    n["to"] = list(dict.fromkeys((n.get("to") or []) + [t for t in tg if t != nid]))
    return f"link «{nm[:30]}» → {len(n['to'])}: {', '.join(n['to'][:8])}"


MORE_OPS = {"model": op_model, "link": op_link, "html": op_html, "crop": look_op("crop"), "trim": look_op("trim"), "opacity": look_op("opacity"),
            "pdfpage": look_op("page"), "grade": look_op("grade"), "mask": look_op("mask")}
OPS.update(MORE_OPS)


def cmd_features(word):
    """the feature catalog (review/features.json), all of it short or the entries with the word, in full"""
    cat = json.load(open(FEATURES_JSON, encoding="utf-8"))
    F = cat["features"]
    if not word:
        print(f"Что умеет Hyimg: {len(F)} функций. hy.py features <слово> покажет подробно")
        for f in F: print(f"  {f['id']:<16} {f['title']}" + (f"  [плагин {f['plugin']}]" if f.get("plugin") else "") + f"  · {f.get('skill', '')}")
        return
    q = norm(word)
    hit = [f for f in F if q in norm(" ".join([f["id"], f["title"], f.get("what", ""), f.get("owner", ""), " ".join(f.get("agent", [])),
                                                " ".join(f.get("commands", []) + f.get("ops", []) + f.get("routes", []) + f.get("props", []) + f.get("modes", []))]))]
    if not hit: print(f"по «{word}» ничего; hy.py features покажет все"); return
    for f in hit:
        print(f"## {f['title']} ({f['id']})" + (f" · плагин {f['plugin']}" if f.get("plugin") else "") + (f" · скилл {f['skill']}" if f.get("skill") else ""))
        print(f["what"])
        if f.get("owner"): print("Владелец: " + f["owner"])
        for a in f.get("agent", []): print("  агент: " + a)
        print()


def cmd_pages():
    _, st = api("/api/pages")
    for p in st.get("pages", []): print(f"«{p.get('title')}» ({p['id']}): кадров {len(p.get('on', []))}")


def cmd_page(args):
    """page new "Название": a new page at the end of the list (as «+» on the canvas's pages), its id printed"""
    if len(args) < 2 or args[0] != "new": raise SystemExit('hy.py page new "Название"')
    title = " ".join(args[1:]).strip()
    _, st = api("/api/pages"); pages = [{"id": p["id"], "title": p.get("title", "")} for p in st.get("pages", [])]
    if any(norm(p["title"]) == norm(title) for p in pages): raise SystemExit(f"страница «{title}» уже есть: hy.py pages")
    pid = "p" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    code, res = api("/api/pages", {"pages": pages + [{"id": pid, "title": title}]})
    if code != 200: raise SystemExit(f"страница не добавлена: {code} {res}")
    print(f"страница «{title}» ({pid}): hy.py --page {pid} ...")


def cmd_presets():
    _, st = api("/api/presets")
    L = st.get("presets", []) if isinstance(st, dict) else []
    if not L: print("пресетов нет: на холсте «Copy properties ›» › «Save as preset…» или hy.py preset save ИМЯ ЧТО")
    for p in L: print(f"«{p['name']}»: {', '.join(PROP_RU.get(k, k) for k in p.get('kinds', {}))}" + (f" (из {p['from']})" if p.get("from") else ""))


def cmd_preset(args, page):
    """preset save "Имя" REF [only=grade,crop] | preset delete "Имя": the project's presets of properties (as «Save as preset…»)"""
    if len(args) >= 2 and args[0] == "delete":
        code, res = api("/api/presets", {"name": args[1], "delete": True, "kinds": {}}); print(code, "удален" if code == 200 else res); return
    if len(args) < 3 or args[0] != "save": raise SystemExit('hy.py preset save "Имя" ЧТО [only=grade,crop] | hy.py preset delete "Имя"')
    only = [x for a in args[3:] if a.startswith("only=") for x in a[5:].split(",") if x]
    _, b = api(f"/api/board?name={page}")
    sid = _prop_items(b, args[2])
    if len(sid) != 1: raise SystemExit("ЧТО: одна вещь (картинка, фрейм, карточка)")
    it = b["items"][sid[0]]
    kinds = {k: prop_get(k, it, b, sid[0]) for k in PROP_ORDER if prop_has(k, it) and (not only or k in only)}
    if not kinds: raise SystemExit("у этой вещи нет таких свойств")
    src = it.get("path", "").rsplit("/", 1)[-1] or it.get("name") or sid[0]
    code, res = api("/api/presets", {"name": args[1], "from": src, "kinds": kinds, "at": int(time.time() * 1000)})
    if code != 200: raise SystemExit(f"не сохранен: {code} {res}")
    print(f"пресет «{args[1]}»: {', '.join(PROP_RU.get(k, k) for k in kinds)} (из {src}); применить: hy.py do 'props preset=\"{args[1]}\" to=ЧТО'")


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


# ---- topage (owner 2026-10-06, «Move to page ›» on the canvas): things off this page onto another one, as the board's right-click menu
# does it (canvas.html moveToPage): a group with its members and the groups wholly inside its frame, a note with the pictures in its zone;
# the layout among them kept; on the other page where they stood when that room is free, else right of its content at its top with a
# group's air; arrows between moved things stay, the others are dropped. The other page gets its own versions before and after; this
# page's come from do. Written once per do: a retry after the owner saved in between takes them off the fresh board again
_TOPAGE = {}


def _src_page():
    a = sys.argv
    if "--page" in a: return a[a.index("--page") + 1]
    try: return (api("/api/live")[1].get("canvas") or {}).get("page") or "main"
    except Exception: return "main"


def op_topage(b, args, kv):
    import fnmatch
    if len(args) < 2: raise SystemExit("topage СТРАНИЦА ЧТО...: страница по имени или id, потом что переносить")
    _, st = api("/api/pages"); pages = st.get("pages", []) if isinstance(st, dict) else []
    pg = next((p for p in pages if p["id"] == args[0]), None) or next((p for p in pages if norm(p.get("title")) == norm(args[0])), None)
    if not pg: raise SystemExit(f"нет страницы «{args[0]}»: " + ", ".join(f"«{p.get('title')}» ({p['id']})" for p in pages))
    src = _src_page()
    if pg["id"] == src: raise SystemExit("это та же страница")
    items, groups = [], []
    def add_group(gid):
        g = b["groups"].get(gid)
        if not g or gid in groups: return
        groups.append(gid); items.extend(m for m in g["members"] if m in b["items"] and m not in items)
        for o, h in b["groups"].items():
            if o != gid and None not in (h.get("x"), g.get("x")) and h["x"] >= g["x"] and h["y"] >= g["y"] and h["x"] + h["w"] <= g["x"] + g["w"] and h["y"] + h["h"] <= g["y"] + g["h"]: add_group(o)
    for a in args[1:]:
        if a in b["items"]:
            if a not in items: items.append(a)
        elif a in b["groups"]: add_group(a)
        elif any(ch in a for ch in "*?/"):
            got = [i for i, it in b["items"].items() if is_pic(it) and fnmatch.fnmatch(it["path"], a)]
            if not got: raise SystemExit(f"на странице нет кадров по «{a}»")
            items.extend(i for i in got if i not in items)
        else:
            k, id, nm, _ = resolve(b, a)
            if k == "dot": raise SystemExit("точка таймлайна переносится вместе с таймлайном")
            if k == "group": add_group(id)
            elif id not in items: items.append(id)
    for s in list(items):   # a note's zone takes the pictures whose centre is in it
        z = b["items"][s].get("type") == "note" and zone_rect(b["items"][s])
        if not z: continue
        for i, it in b["items"].items():
            if i not in items and is_pic(it) and it.get("x") is not None and z["x"] <= it["x"] + it["w"] / 2 <= z["x"] + z["w"] and z["y"] <= it["y"] + item_h(it) / 2 <= z["y"] + z["h"]: items.append(i)
    moved = set(items) | set(groups)
    key = (pg["id"], tuple(args[1:]))
    load = {"items": {i: json.loads(json.dumps(b["items"][i])) for i in items}, "groups": {g: json.loads(json.dumps(b["groups"][g])) for g in groups}}
    dropped = 0
    for n in load["items"].values():
        if n.get("type") == "note" and n.get("to"):
            keep = [t for t in n["to"] if t in moved]; dropped += len(n["to"]) - len(keep); n["to"] = keep
    for g in load["groups"].values(): g["members"] = [m for m in g["members"] if m in moved]
    for i, n in b["items"].items():
        if i not in moved and n.get("type") == "note" and n.get("to"):
            keep = [t for t in n["to"] if t not in moved]; dropped += len(n["to"]) - len(keep); n["to"] = keep
    done = _TOPAGE.get(key)
    if not done and "--dry" not in sys.argv:
        def room(bb, ids, gids):
            out = []
            for i in ids:
                it = bb["items"].get(i)
                if not it or it.get("x") is None or it.get("y") is None: continue
                out.append(rect(bb, i)); z = it.get("type") == "note" and zone_rect(it)
                if z: out.append(z)
            out += [{k: bb["groups"][g][k] for k in "xywh"} for g in gids if g in bb["groups"] and bb["groups"][g].get("x") is not None]
            return [r for r in out if None not in r.values()]
        def boxof(rs):
            x, y = min(r["x"] for r in rs), min(r["y"] for r in rs)
            return {"x": x, "y": y, "w": max(r["x"] + r["w"] for r in rs) - x, "h": max(r["y"] + r["h"] for r in rs) - y}
        box = boxof(room(b, items, groups) or [{"x": 0, "y": 0, "w": 0, "h": 0}])
        ws = sorted(b["items"][i]["w"] for i in items if is_pic(b["items"][i])); air = round((ws[len(ws) // 2] if ws else 320) * 1.5)
        _, e = api("/api/history", {"action": "save", "name": pg["id"], "who": "ai", "label": f"до: {LABEL or 'перенос'}"})
        for attempt in range(4):
            _, t = api(f"/api/board?name={pg['id']}")
            for k in ("items", "groups", "removed"): t.setdefault(k, {})
            obs = room(t, list(t["items"]), list(t["groups"]))
            pad = {"x": box["x"] - air / 2, "y": box["y"] - air / 2, "w": box["w"] + air, "h": box["h"] + air}
            if any(inter(pad, o) for o in obs): a = boxof(obs); dx, dy = round(a["x"] + a["w"] + air - box["x"]), round(a["y"] - box["y"])
            else: dx = dy = 0
            idmap = {i: (uid(i[:1] or "i") if i in t["items"] or i in t["groups"] else i) for i in items}
            idmap.update({g: (uid("g") if g in t["items"] or g in t["groups"] else g) for g in groups})
            for i, it in load["items"].items():
                o = json.loads(json.dumps(it)); o["x"] = round(o["x"] + dx); o["y"] = round(o["y"] + dy)
                if o.get("to"): o["to"] = [idmap.get(x, x) for x in o["to"]]
                t["items"][idmap[i]] = o
                for p in ([o["path"]] if is_pic(o) else o.get("pics") or []): t["removed"].pop(p, None)
            for g, gr in load["groups"].items():
                t["groups"][idmap[g]] = dict(gr, x=round(gr["x"] + dx), y=round(gr["y"] + dy), members=[idmap.get(m, m) for m in gr["members"]])
            code, res = api(f"/api/board?name={pg['id']}", t)
            if code == 200: break
            if code != 409: raise SystemExit(f"страница «{pg.get('title')}» не сохранилась: {code} {res}")
        else: raise SystemExit(f"страницу «{pg.get('title')}» все время сохраняют, не смог записать")
        _, e2 = api("/api/history", {"action": "save", "name": pg["id"], "who": "ai", "label": f"после: {LABEL or 'перенос'}"})
        vid = lambda x: x.get("id") if isinstance(x, dict) else "нет"
        done = _TOPAGE[key] = {"at": (dx, dy), "ver": f"{vid(e)} → {vid(e2)}"}
    for i in items: b["items"].pop(i, None)
    for g in groups: b["groups"].pop(g, None)
    for g in b["groups"].values(): g["members"] = [m for m in g["members"] if m in b["items"]]
    on = {p for it in b["items"].values() for p in ([it.get("path")] if is_pic(it) else it.get("pics") or [])}
    for it in load["items"].values():   # on the other page now: not gone to the archive
        for p in ([it["path"]] if is_pic(it) else it.get("pics") or []):
            if p not in on: b.get("removed", {}).pop(p, None)
    where = "" if not done else (" на свое место" if done["at"] == (0, 0) else f" правее содержимого (сдвиг {done['at'][0]}, {done['at'][1]})")
    return (f"topage «{pg.get('title')}»{where}: {len(items)} шт. и групп {len(groups)}" + (f", стрелок убрано: {dropped}" if dropped else "")
            + (f" · версии той страницы {done['ver']}" if done else " (проба: та страница не тронута)"))


OPS["topage"] = op_topage


# ---- props (owner 2026-10-06, «Copy properties ›» / «Paste properties ›» on the canvas): a look and a geometry from one object onto others,
# by the canvas's rules: crop is a share of the frame (any size takes it), trim the seconds (as they are: hy.py does not know a video's
# length, the canvas cuts it at a shorter video's end), size the width (a plugin card's height keeps its own proportions), opacity, a PDF's
# page, the colour grade; any other kind a plugin registers (the mask) is the item's field of that name. Never rating, ♥ or tags
VIDEO_RE = re.compile(r"\.(mp4|m4v|mov|webm)$", re.I)
PROP_ORDER = ["grade", "mask", "crop", "trim", "size", "opacity", "page"]
PROP_RU = {"grade": "цветокор", "mask": "маска", "crop": "обрезка", "trim": "время", "size": "размер", "opacity": "прозрачность", "page": "страница PDF"}


def _vid(it): return is_pic(it) and bool(VIDEO_RE.search(it.get("path", "")))
def _pdf(it): return is_pic(it) and it.get("path", "").lower().endswith(".pdf")


def prop_has(k, it):
    return {"crop": lambda: is_pic(it) and bool(it.get("crop")), "trim": lambda: _vid(it) and bool(it.get("trim")), "size": lambda: it.get("type") != "timeline" and bool(it.get("w")),
            "opacity": lambda: it.get("opacity") is not None and it["opacity"] < 1, "page": lambda: _pdf(it),
            "grade": lambda: bool(it.get("grade"))}.get(k, lambda: it.get(k) is not None)()


# plugin cards that are pictures for the looks (2026-10-06: a 3D card's still, live view or Blender render takes the opacity and the colour
# grade as a picture does), and the cards that take only the opacity (an HTML page: its live page cannot be graded)
PICTURE_CARDS = ("imgframe", "model3d")
OPACITY_CARDS = PICTURE_CARDS + ("htmlframe", "html")


def prop_applies(k, it):
    return {"crop": lambda: is_pic(it), "trim": lambda: _vid(it), "size": lambda: it.get("type") != "timeline", "opacity": lambda: is_pic(it) or it.get("type") in OPACITY_CARDS,
            "page": lambda: _pdf(it) and not it.get("pageFixed"), "grade": lambda: (is_pic(it) and not _vid(it)) or it.get("type") in PICTURE_CARDS}.get(k, lambda: True)()


def prop_get(k, it, b, id):
    if k == "size": return {"w": round(it["w"]), "h": round(rect(b, id)["h"])}
    if k == "opacity": return 1 if it.get("opacity") is None else it["opacity"]
    if k == "page": return it.get("page") or 1
    return json.loads(json.dumps(it.get(k)))


def prop_set(k, it, v):
    if k == "size":
        if not v or not v.get("w"): return
        if it.get("type") and it.get("h") and it.get("type") not in ("note", "text"): it["h"] = round(it["h"] * v["w"] / it["w"])
        it["w"] = round(v["w"]); return
    if k == "opacity":
        if v is None or v >= 1: it.pop("opacity", None)
        else: it["opacity"] = round(max(0, v), 2)
        return
    if k == "page":
        if v and v > 1: it["page"] = int(v)
        else: it.pop("page", None)
        return
    if k == "crop": it["crop"] = list(v) if v else None; return
    if v is None: it.pop(k, None)
    else: it[k] = json.loads(json.dumps(v))


def _prop_items(b, ref):
    import fnmatch
    if ref in b["items"]: return [ref]
    if ref in b["groups"]: return [m for m in b["groups"][ref]["members"] if m in b["items"]]
    if any(ch in ref for ch in "*?/"): return [i for i, it in b["items"].items() if is_pic(it) and fnmatch.fnmatch(it["path"], ref)]
    k, id, nm, _ = resolve(b, ref)
    if k == "group": return [m for m in b["groups"][id]["members"] if m in b["items"]]
    if k == "dot": raise SystemExit("у точки таймлайна нет свойств")
    return [id]


def op_props(b, args, kv):
    only = [x.strip() for x in str(kv.get("only", "")).split(",") if x.strip()]
    if "preset" in kv:
        _, st = api("/api/presets"); L = st.get("presets", []) if isinstance(st, dict) else []
        p = next((x for x in L if x["name"] == str(kv["preset"])), None) or next((x for x in L if norm(x["name"]) == norm(str(kv["preset"]))), None)
        if not p: raise SystemExit(f"нет пресета «{kv['preset']}»: " + ", ".join(f"«{x['name']}»" for x in L))
        kinds, src = dict(p["kinds"]), f"пресет «{p['name']}»"
    elif "from" in kv:
        sid = _prop_items(b, str(kv["from"]))
        if len(sid) != 1: raise SystemExit("from= одна вещь: картинка, заметка, карточка")
        it = b["items"][sid[0]]
        kinds = {k: prop_get(k, it, b, sid[0]) for k in (PROP_ORDER + [k for k in only if k not in PROP_ORDER]) if prop_has(k, it)}
        src = f"«{it.get('path', '').rsplit('/', 1)[-1] or first_line(it.get('text')) or it.get('name') or sid[0]}»"
    else: raise SystemExit("props from=ЧТО to=КУДА... [only=grade,crop] или props preset=ИМЯ to=КУДА...")
    if only: kinds = {k: v for k, v in kinds.items() if k in only}
    if not kinds: raise SystemExit(f"у {src} нет таких свойств" + (f": {', '.join(only)}" if only else ""))
    refs = [x for x in str(kv.get("to", "")).split(",") if x.strip()] + list(args)
    if not refs: raise SystemExit("to=КУДА: id, имя, группа или маска путей")
    tg = list(dict.fromkeys(i for r in refs for i in _prop_items(b, r.strip())))
    done, skipped = 0, {}
    for i in tg:
        it, hit = b["items"][i], False
        for k, v in kinds.items():
            if prop_applies(k, it): prop_set(k, it, v); hit = True
            else: skipped[k] = skipped.get(k, 0) + 1
        done += hit
    names = ", ".join(PROP_RU.get(k, k) for k in kinds)
    return f"props из {src} на {done} из {len(tg)}: {names}" + ("" if not skipped else " · не подошло: " + ", ".join(f"{PROP_RU.get(k, k)} ({n})" for k, n in skipped.items()))


OPS["props"] = op_props


def op_cards3d(b, args, kv):
    """3D cards of one scene as a block, a card per camera (owner 2026-10-06: «put my 3D previews to the right of this group», 18 angles of
    one Blender studio scene beside the pictures they came from): cameras=ID,ID… picks and orders them (default: all, in the scene's
    order); each card has its camera's frame (the camera's "render": [x, y], else the scene's); rows of cols= (4), w= (320), gap= (24),
    or align=NOTE: each card at the height of the picture of the same place in that note's zone (rows like the pictures beside);
    note= puts a blue note with its zone on the left, as block does. Placed at x= y= (the block's top left), or beside=REF: right of REF
    (a note: of its zone with the pictures in it) with a card's width of air, its top at REF's top. into=GROUP: the cards and the note
    join that group and its frame grows to hold them; nothing else moves (a frame that grows only covers more of the page)"""
    st, doc = api("/file?p=" + urllib.parse.quote(args[0]))
    if st != 200 or not isinstance(doc, dict): raise SystemExit(f"нет сцены {args[0]}")
    cams = {c["id"]: c for c in doc.get("cameras", [])}
    pick = kv.get("cameras")
    order = [str(int(pick)) if isinstance(pick, float) and pick.is_integer() else c for c in str(pick).split(",")] if pick is not None else list(cams)
    miss = [c for c in order if c not in cams]
    if miss: raise SystemExit(f"в сцене нет камер {', '.join(miss)}: есть {', '.join(cams)}")
    w, gap, cols = round(kv.get("w", 320)), round(kv.get("gap", 24)), int(kv.get("cols", 4))
    base = doc.get("render") or {"x": 1600, "y": 2000}
    cards = []
    for cid in order:
        rx, ry = cams[cid].get("render") or [base["x"], base["y"]]
        cards.append({"type": "model3d", "scene": args[0], "camera": cid, "x": 0, "y": 0, "w": w, "h": round(w * ry / rx)})
    y = 0
    for k in range(0, len(cards), cols):
        row = cards[k:k + cols]
        for c, it in enumerate(row): it["x"], it["y"] = c * (w + gap), y
        y += max(it["h"] for it in row) + gap
    if kv.get("align"):   # the rows of the pictures in a note's zone: card i stands at the height of picture i (reading order)
        aid = resolve(b, str(kv["align"]), {"note"})[1]; z = zone_rect(b["items"][aid])
        pics = sorted((it for it in b["items"].values() if is_pic(it) and it.get("x") is not None and z["x"] <= it["x"] + it["w"] / 2 <= z["x"] + z["w"]
                       and z["y"] <= it["y"] + item_h(it) / 2 <= z["y"] + z["h"]), key=lambda it: (round(it["y"]), it["x"]))
        if len(pics) != len(cards): raise SystemExit(f"align: в зоне {len(pics)} кадров, карточек {len(cards)}")
        for it, pic in zip(cards, pics): it["y"] = round(pic["y"] - pics[0]["y"])
        y = max(it["y"] + it["h"] for it in cards) + gap
    bx = {"x": 0, "y": 0, "w": min(cols, len(cards)) * (w + gap) - gap, "h": y - gap}
    note = None
    if kv.get("note"):   # as lay_out's note: left of the cards, its zone around them
        G, P, size = round(w * .15), round(w / 2), 2
        note = {"type": "note", "text": str(kv["note"]).replace("\\n", "\n"), "x": -G - w, "y": 0, "w": w, "fs": w * NSIZE[size], "size": size, "h": 0, "color": "blue", "to": []}
        note["reach"] = {"l": P, "t": P, "r": round(bx["w"] + G + P), "b": round(max(0, bx["h"] - w) + P)}
        bx = {"x": note["x"], "y": 0, "w": bx["w"] + G + w, "h": max(bx["h"], w)}
    if "beside" in kv:
        k, rid, nm, r = resolve(b, str(kv["beside"]))
        z = zone_rect(b["items"][rid]) if rid in b["items"] and b["items"][rid].get("reach") else r
        dx, dy = z["x"] + z["w"] + w - bx["x"], r["y"] - bx["y"]
    elif "x" in kv and "y" in kv:
        dx, dy = kv["x"] - bx["x"], kv["y"] - bx["y"]
    else:
        raise SystemExit("cards3d: укажи beside=<что слева> или x= и y=")
    ids = []
    for it in ([note] if note else []) + cards:
        it["x"], it["y"] = round(it["x"] + dx), round(it["y"] + dy)
        i = uid("n" if it["type"] == "note" else "m"); b["items"][i] = it; ids.append(i)
    msg = f"cards3d {len(cards)} карточек «{args[0]}» x {round(bx['x'] + dx)} y {round(bx['y'] + dy)}, {round(bx['w'])}×{round(bx['h'])}"
    if kv.get("into"):
        gid = resolve(b, str(kv["into"]), {"group"})[1]; g = b["groups"][gid]; pad = round(w * 1.5)
        for o in b["groups"].values(): o["members"] = [m for m in o["members"] if m not in ids]
        g["members"] += ids
        old = dict(g)
        right, bottom = max(g["x"] + g["w"], bx["x"] + dx + bx["w"] + pad), max(g["y"] + g["h"], bx["y"] + dy + bx["h"] + pad)
        g["w"], g["h"] = right - g["x"], bottom - g["y"]
        msg += f" · в группе «{first_line(g.get('title')) or 'группа'}»" + (f", рамка шире на {g['w'] - old['w']}" if g["w"] > old["w"] else "") + (f" и ниже на {g['h'] - old['h']}" if g["h"] > old["h"] else "")
    return msg


OPS["cards3d"] = op_cards3d; import hy3d; hy3d.register(OPS, api, resolve)   # camera3d and the 3D cards' own view (hy3d.py)


# ---- order (owner 2026-10-06, the canvas's «Order ›», ⌥⌘] ⌘] ⌘[ ⌥⌘[): front, forward, backward, back among a thing's siblings only, as
# canvas.html orderMove: the members of its group (or the page's top level) in its layer (notes, headings, timelines lie over the pictures),
# a group among the groups in the same smallest group frame; the draw order is the order of items and groups in the board file
def _gparent(b, gid):
    g, best = b["groups"][gid], None
    for o, h in b["groups"].items():
        if o != gid and None not in (h.get("x"), g.get("x")) and h["x"] <= g["x"] and h["y"] <= g["y"] and h["x"] + h["w"] >= g["x"] + g["w"] and h["y"] + h["h"] >= g["y"] + g["h"] \
                and (best is None or h["w"] * h["h"] < b["groups"][best]["w"] * b["groups"][best]["h"]): best = o
    return best


def _scope(b, k):
    if k in b["groups"]: return "G:" + (_gparent(b, k) or "")
    it = b["items"][k]; g = next((gid for gid, gr in b["groups"].items() if k in gr["members"]), None)
    return (f"g:{g}" if g else "top") + ("|w" if it.get("type") in ("note", "text", "timeline") else "|p")


def _reorder(b, keys, picked, how):
    scopes = {}
    for k in keys: scopes.setdefault(_scope(b, k), []).append(k)
    out, moved = list(keys), False
    for lst in scopes.values():
        if not any(k in picked for k in lst): continue
        nxt = list(lst)
        if how == "front": nxt = [k for k in lst if k not in picked] + [k for k in lst if k in picked]
        elif how == "back": nxt = [k for k in lst if k in picked] + [k for k in lst if k not in picked]
        elif how == "forward":
            for i in range(len(nxt) - 2, -1, -1):
                if nxt[i] in picked and nxt[i + 1] not in picked: nxt[i], nxt[i + 1] = nxt[i + 1], nxt[i]
        else:
            for i in range(1, len(nxt)):
                if nxt[i] in picked and nxt[i - 1] not in picked: nxt[i], nxt[i - 1] = nxt[i - 1], nxt[i]
        if nxt != lst:
            moved = True
            for at, k in zip([keys.index(k) for k in lst], nxt): out[at] = k
    return out if moved else None


def _order_op(how):
    def op(b, args, kv):
        if not args: raise SystemExit(f"{how} ЧТО...: id, имя заметки, заголовка или группы")
        picked = set()
        for a in args:
            a = a[1:] if a.startswith("@") else a
            if a in b["items"] or a in b["groups"]: picked.add(a); continue
            k, id, nm, _ = resolve(b, a)
            if k == "dot": raise SystemExit("точка таймлайна двигается с таймлайном")
            picked.add(id.split("/")[0])
        ni, ng = _reorder(b, list(b["items"]), picked, how), _reorder(b, list(b["groups"]), picked, how)
        if ni: b["items"] = {k: b["items"][k] for k in ni}
        if ng: b["groups"] = {k: b["groups"][k] for k in ng}
        word = {"front": "на передний план", "forward": "выше", "backward": "ниже", "back": "на задний план"}[how]
        return f"{how}: {len(picked)} шт. {word}" if ni or ng else f"{how}: ничего не сдвинулось (уже {'сверху' if how in ('front', 'forward') else 'снизу'} или нет соседей)"
    return op


for _how in ("front", "forward", "backward", "back"): OPS[_how] = _order_op(_how)


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
    if not a: print(__doc__ + hy3d.HELP); return
    c = a[0]
    if c == "guide":
        code, txt = api_text("/agent"); print(txt); return
    if c == "save":
        if not to or len(a) < 2: raise SystemExit("hy.py save ФАЙЛЫ... --to ПАПКА [--move]")
        return cmd_save(a[1:], to, move)
    if c == "dupes": return cmd_dupes()
    if c == "layout": return cmd_layout(a[1:])
    if c == "undocumented": return cmd_undocumented(a[1] if len(a) > 1 else "")
    if c == "features": return cmd_features(" ".join(a[1:]))
    if c == "pages": return cmd_pages()
    if c == "page": return cmd_page(a[1:])
    if c == "presets": return cmd_presets()
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
    if c == "preset": return cmd_preset(a[1:], page)
    raise SystemExit(f"не знаю {c}: map, find, check, do, notify, hist, restore, guide, features, pages, page, presets, preset, save, dupes, layout, undocumented")


if __name__ == "__main__":
    main(sys.argv[1:])
