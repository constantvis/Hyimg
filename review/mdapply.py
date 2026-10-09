"""hy.py md apply: an edit of a page's Markdown goes back onto the board (owner 2026-10-09 on «Board structure» › «Markdown as edits» and
«Agent layouts» › «5 · Board as Markdown»: «реализуй это»). `hy.py md` is the read view; an agent edits that text and applies it. Lines
become board operations by reference, never coordinates: the grids and gravity (after the line before) place things.

  hy.py md [PAGE] > page.md          the view; its first line <!-- hyimg md page=… rev=… vid=… --> names the version it was made from
  hy.py md apply page.md --dry       the planned operations, nothing saved (always look at them first)
  hy.py md apply page.md             saved: a version before and after (who: ai), a notification of what was added (--say, --quiet)
  hy.py md apply -                   the edit from stdin; a part of the page is enough, what the file does not mention stays as it is

What a line changes:
  ## Heading [id], #### … [id]        the heading's text (its first line)
  ## ▣ Группа «Title» [id]            the group's title
  > text … [id]                       the note's text: every > line of the quote
  → name [id] under a note            a new line links the note to it (a note: a reply), a struck one unlinks
  - name [id] under another group     the picture or card moves into that group, after the line before it (the frame grows); free
                                      lines of one group in another order trade places
  cells of a table (▦ сетка … [id])   the grid's order and its columns: a cell moved, brought from another table or list, a new column;
                                      «Text» in a cell is a heading (its text, or a new heading there); a library path adds that picture
  a line without [id]                 a new thing: «## Heading», «> note» (blue, yours), «- folder/picture.png» from the library, a cell;
                                      «## ▣ Группа «Title»» makes a group of the lines under it, beside the group before it
  ~~line~~                            removes what it names: a heading, a note, an arrow, a picture or card (a picture gone from every page
                                      is the archive), a group's frame (its contents stay). Nothing is removed because its line is missing.
Conflicts: the edit is compared with the version it was made from (this Mac's copy of what `hy.py md` printed, else History). A change to
a thing that someone changed since is skipped and named («! пропуск»), the rest applies to the page as it is now."""
import copy
import json
import os
import re
import sys
import tempfile
import urllib.parse

import grids
import hymd

GAP = 24
ID = r"[A-Za-z0-9_-]+"
TAIL = re.compile(r"\s*\[(" + ID + r")\]\s*$")
MARKS = re.compile(r"\s*(?:💬|✎)\d+")
STAMP = re.compile(r"<!--\s*hyimg md\b(.*?)-->")
GROUP = re.compile(r"^(#{2,6})\s+▣\s*Группа\s*«(.*)»\s*$")
HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
TIMELINE = re.compile(r"^Таймлайн\s«.*?»\s*\[(" + ID + r")\]")
CACHE = os.path.join(tempfile.gettempdir(), "hyimg-md")   # what hy.py md printed, as bases for an apply (this Mac, not the owner's cache)
KEEP = 40


# ---- the view's stamp and its base --------------------------------------------------------------------------------------------------
def _key(page, b): return re.sub(r"[^A-Za-z0-9_-]", "_", f"{page}-{b.get('vid') or ''}-{b.get('revision', 0)}")


def stamp(b, page):
    """the first line of hy.py md: the version the view shows; that version is kept as the base of a later apply"""
    try:
        os.makedirs(CACHE, exist_ok=True)
        p = os.path.join(CACHE, _key(page, b) + ".json")
        if not os.path.exists(p):
            with open(p + ".tmp", "w", encoding="utf-8") as f: json.dump(b, f, ensure_ascii=False)
            os.replace(p + ".tmp", p)
        old = sorted((e for e in os.scandir(CACHE) if e.name.endswith(".json")), key=lambda e: e.stat().st_mtime)
        for e in old[:-KEEP]: os.remove(e.path)
    except OSError:
        pass
    return f"<!-- hyimg md page={page} rev={b.get('revision', 0)} vid={b.get('vid') or '-'} -->\n"


def base_of(api, page, st, cur):
    """the board the view was made from: the page itself when nothing changed, this Mac's copy, History's version; or None"""
    rev, vid = int(st.get("rev", -1)), st.get("vid", "-")
    if cur.get("revision", 0) == rev and (cur.get("vid") or "-") == vid: return copy.deepcopy(cur), "та же версия"
    try:
        with open(os.path.join(CACHE, _key(page, {"vid": None if vid == "-" else vid, "revision": rev}) + ".json"), encoding="utf-8") as f:
            b = json.load(f)
        I0, I1 = set(b.get("items") or {}), set(cur.get("items") or {})
        if vid != "-" or I0 & I1 or not (I0 or I1): return b, "копия вида"   # without a vid: the same page of the same board, not a namesake
    except (OSError, ValueError):
        pass
    try:
        code, L = api(f"/api/history?name={urllib.parse.quote(page)}")
        for e in (L if code == 200 and isinstance(L, list) else []):
            if e.get("revision") != rev: continue
            c2, b = api(f"/api/history/board?name={urllib.parse.quote(page)}&id={urllib.parse.quote(str(e['id']))}")
            if c2 == 200 and isinstance(b, dict) and (b.get("vid") or "-") == vid: return b, "версия из истории"
    except Exception:
        pass
    return None, ""


# ---- reading the edited text ----------------------------------------------------------------------------------------------------------
def strike(s):
    t = s.strip()
    if len(t) > 4 and t.startswith("~~") and t.endswith("~~"): return t[2:-2].strip(), True
    return s.strip(), False


def ref(s):
    """«name [id]» -> (name, id); no [id]: (s, None)"""
    m = TAIL.search(s)
    return (s[:m.start()].strip(), m.group(1)) if m else (s.strip(), None)


def cell(s):
    s, st = strike(s)
    if not s: return None
    name, i = ref(s)
    q = re.fullmatch(r"«(.*)»", name)
    return {"id": i, "name": name, "text": q.group(1) if q else None, "struck": st}


def starter(lines, i, lvl):
    """does line i begin a thing of the board (and so end the body of a heading of level lvl)? A document's own headings are deeper"""
    s, _ = strike(MARKS.sub("", lines[i]).rstrip())
    if not s: return False
    if s.startswith(("## 💬", "## ↦", "▦", "→", "# «")) or s == "Свободно:" or STAMP.search(s): return True
    h = HEAD.match(s)
    if h: return "▣" in s or len(h.group(1)) <= lvl or bool(TAIL.search(s))
    if s.startswith("- "): b = strike(s[2:])[0]; return bool(TIMELINE.match(b) or TAIL.search(b))
    return s.startswith(">")   # a quote is a note: a document's own quotes come back as lines the view printed (plan: seen)


def unshift(body, lvl):
    """a body as the view prints it back to the document's own Markdown: its headings lvl levels up again (textdocs.body_md)"""
    out = []
    for x in (body or "").split("\n"):
        m = re.match(r"^(#{1,6})\s+(.*)$", x)
        out.append(f"{'#' * max(1, min(3, len(m.group(1)) - lvl))} {m.group(2)}" if m and len(m.group(1)) > lvl else x)
    return "\n".join(out)


def parse(text):
    """the page's Markdown as blocks in order: {k: group|heading|note|item|timeline|grid, id, sec (the group section it stands in), ln, …}"""
    doc = {"stamp": {}, "title": False, "blocks": [], "bad": []}
    stack, lines, i, B = [], text.split("\n"), 0, doc["blocks"]
    sec = lambda: stack[-1][1] if stack else None
    while i < len(lines):
        ln, raw = i + 1, MARKS.sub("", lines[i]).rstrip(); i += 1
        if not raw.strip(): continue
        m = STAMP.search(raw)
        if m:
            doc["stamp"] = dict(kv.split("=", 1) for kv in m.group(1).split() if "=" in kv); continue
        if raw.startswith(("## 💬", "## ↦")): break   # comments and drawings (mdmarks.py), the arrows (connectors.py): read only
        line, st = strike(raw)
        if line.startswith("# «") or line == "#": doc["title"] = True; continue
        g = GROUP.match(line)
        if line.startswith("#") and "▣" in line and g is None:   # «## ▣ Группа «Title» [id]»: the id after the title
            name, gid = ref(line); g2 = GROUP.match(name)
            if g2:
                lvl, title = len(g2.group(1)), g2.group(2)
                stack[:] = [s for s in stack if s[0] < lvl]; stack.append((lvl, gid))
                B.append({"k": "group", "id": gid, "sec": stack[-2][1] if len(stack) > 1 else None, "ln": ln, "struck": st, "text": title, "lvl": lvl})
                continue
        if g:   # a new group: no id
            lvl, key = len(g.group(1)), f"+{ln}"
            stack[:] = [s for s in stack if s[0] < lvl]; stack.append((lvl, key))
            B.append({"k": "group", "id": None, "key": key, "sec": stack[-2][1] if len(stack) > 1 else None, "ln": ln, "struck": st, "text": g.group(2), "lvl": lvl})
            continue
        h = HEAD.match(line)
        if h:   # a heading, and the lines under it up to the next thing of the board: its text document's body (textdocs.py)
            body, s2 = strike(h.group(2)); name, hid = ref(body); lvl, doc_ = len(h.group(1)), []
            while i < len(lines) and not starter(lines, i, lvl): doc_.append(lines[i].rstrip()); i += 1
            while doc_ and not doc_[-1].strip(): doc_.pop()
            while doc_ and not doc_[0].strip(): doc_.pop(0)
            B.append({"k": "heading", "id": hid, "sec": sec(), "ln": ln, "struck": st or s2, "text": name, "lvl": lvl, "body": "\n".join(doc_)}); continue
        if raw.lstrip().startswith(">") or (st and line.startswith(">")):   # a quote: one note, its id on the last line
            q, j = [lines[i - 1]], i
            while j < len(lines) and MARKS.sub("", lines[j]).lstrip().startswith(">"): q.append(lines[j]); j += 1
            i = j; body = []
            for x in q:
                x = MARKS.sub("", x).rstrip(); y, s3 = strike(x) if x.strip().startswith("~~") else (x.lstrip(), False)
                y = y[2:] if y.startswith("> ") else y[1:] if y.startswith(">") else y
                y2, s4 = strike(y) if y.strip().startswith("~~") else (y, False)
                body.append([y2, s3 or s4])
            last, nid = ref(body[-1][0]); body[-1][0] = last
            n = {"k": "note", "id": nid, "sec": sec(), "ln": ln, "struck": body[-1][1], "text": "\n".join(b for b, _ in body), "links": []}
            while i < len(lines) and MARKS.sub("", lines[i]).strip().lstrip("~").startswith("→"):
                x, s5 = strike(MARKS.sub("", lines[i])); x = x.lstrip("→").strip(); name, t = ref(x)
                if t: n["links"].append({"id": t, "struck": s5, "ln": i + 1})
                else: doc["bad"].append((i + 1, "стрелка без [id]: к чему она"))
                i += 1
            B.append(n); continue
        if line.startswith("→"): doc["bad"].append((ln, "стрелка не под заметкой")); continue
        if line.startswith("▦"):
            name, gid = ref(line.split("]", 1)[0] + "]" if "]" in line else line)
            rows = []
            while i < len(lines) and MARKS.sub("", lines[i]).strip().startswith("|"):
                rows.append([c for c in MARKS.sub("", lines[i]).strip().strip("|").split("|")]); i += 1
            rows = [r for r in rows if not all(re.fullmatch(r"\s*:?-+:?\s*", c) for c in r)]
            if not rows: doc["bad"].append((ln, "сетка без таблицы")); continue
            head, body = [cell(c) for c in rows[0]], [[cell(c) for c in r] for r in rows[1:]]
            blank = all(c is None for c in head)
            B.append({"k": "grid", "id": gid, "key": f"+{ln}", "sec": sec(), "ln": ln, "struck": st, "cols": max(len(r) for r in rows),
                      "cells": ([] if blank else [head]) + body})
            continue
        if line == "Свободно:" or line.endswith(":") and line.lower().startswith("свободно"): continue
        if line.startswith("- ") or line == "-":
            body, s6 = strike(line[2:]); st = st or s6
            t = TIMELINE.match(body)
            if t: B.append({"k": "timeline", "id": t.group(1), "sec": sec(), "ln": ln, "struck": st}); continue
            name, iid = ref(body)
            B.append({"k": "item", "id": iid, "sec": sec(), "ln": ln, "struck": st, "name": name.lstrip("+").strip()}); continue
        doc["bad"].append((ln, "не понял строку: " + line[:60]))
    return doc


def occurrences(doc):
    """id -> where it stands: (block, the cell's index in the grid's member order or None)"""
    out = {}
    for b in doc["blocks"]:
        if b["k"] == "grid":
            n = 0
            for row in b["cells"]:
                for c in row:
                    if c is None: continue
                    if c["id"]: out.setdefault(c["id"], []).append((b, n))
                    n += 1
        elif b["id"]: out.setdefault(b["id"], []).append((b, None))
    return out


def gcells(blk):
    return [c for row in blk["cells"] for c in row if c is not None]


# ---- planning: the edit against the view it was made from -----------------------------------------------------------------------
def first(t): return (t or "").strip().split("\n")[0].lstrip("#").strip()


def norm(t): return "\n".join(x.rstrip() for x in (t or "").strip().split("\n"))   # as the view prints a note: each line rstripped


def new_first(old, text):
    """old's first line replaced by text, its leading # kept, the other lines kept"""
    lines = (old or "").split("\n"); m = re.match(r"\s*#*\s*", lines[0] if lines else "")
    return "\n".join([(m.group(0) if m else "") + text] + lines[1:])


def sig(B, k):
    """a line without an id, by what it says, its section and the thing with an id before it"""
    x = B[k]; prev = next((y["id"] for y in reversed(B[:k]) if y["id"]), None)
    return (x["k"], x["sec"], x.get("text") or x.get("name"), x.get("body", ""), prev)


def plan(base, edit):
    """the operations the edit expresses: [{show, ph (phase), touch [(coll, id, field)], run(b, ctx) -> str}]; bad lines in edit["bad"]"""
    view = parse(hymd.render(base))
    BO, EO = occurrences(view), occurrences(edit)
    I, G, T = base.get("items") or {}, base.get("groups") or {}, grids.table(base)
    ops, bad = [], edit["bad"]
    dup = {i for i, o in EO.items() if len(o) > 1}
    for i in sorted(dup): bad.append((EO[i][1][0]["ln"], f"[{i}] встречается {len(EO[i])} раза: оставил как есть"))
    nm = lambda i: grids.cell(base, i) if i in I else f"«{first(G[i].get('title'))}» [{i}]" if i in G else f"[{i}]"
    full = edit["title"]

    def op(ph, show, run, *touch): ops.append({"ph": ph, "show": show, "run": run, "touch": list(touch)})

    for blk in edit["blocks"]:   # texts, titles, arrows
        i = blk["id"]
        if not i or i in dup or blk["struck"]: continue
        if i not in I and i not in G and blk["k"] != "grid":
            bad.append((blk["ln"], f"[{i}] нет на странице (в той версии, с которой сделан вид)")); continue
        if blk["k"] == "heading":
            if I.get(i, {}).get("type") != "text": bad.append((blk["ln"], f"[{i}] не заголовок")); continue
            vb = BO[i][0][0].get("body", "") if i in BO else ""
            title = blk["text"] or first(I[i].get("text")); body = None if blk["body"] == vb else unshift(blk["body"], blk["lvl"])
            if title != first(I[i].get("text")) or body is not None:
                what = f"«{first(I[i].get('text'))}» → «{title}»" if title != first(I[i].get("text")) else f"«{title}»"
                op(1, f"~ заголовок {what}" + (" и его текст" if body is not None else ""), _set_text(i, title, body), ("items", i, "text"))
        elif blk["k"] == "group" and i in G:
            if blk["text"] != (first(G[i].get("title")) or "без названия") and blk["text"]:
                op(1, f"~ группа «{first(G[i].get('title'))}» → «{blk['text']}»", _set_title(i, blk["text"]), ("groups", i, "title"))
        elif blk["k"] == "note":
            if I.get(i, {}).get("type") != "note": bad.append((blk["ln"], f"[{i}] не заметка")); continue
            old = (I[i].get("text") or "").strip(); shown = old[:hymd.QUOTE] + ("…" if len(old) > hymd.QUOTE else "")
            if norm(blk["text"]) != norm(shown):
                if len(old) > hymd.QUOTE and not blk["text"].rstrip().endswith("…"):
                    bad.append((blk["ln"], f"заметка [{i}] длиннее {hymd.QUOTE} знаков, ее конца в виде нет: оставь … в конце, чтобы он сохранился"))
                else:
                    new = blk["text"].rstrip()[:-1] + old[hymd.QUOTE:] if len(old) > hymd.QUOTE else blk["text"]
                    op(1, f"~ заметка [{i}] «{first(new)[:40]}»", _set_note(i, new), ("items", i, "text"))
            had = {t for t in I[i].get("to") or []}
            for L in blk["links"]:
                t = L["id"]
                if L["struck"] and t in had: op(1, f"− стрелка [{i}] → {nm(t)}", _unlink(i, t), ("items", i, "to"))
                elif not L["struck"] and t not in had:
                    if t not in I and t not in G: bad.append((L["ln"], f"стрелка к [{t}]: такого на странице нет")); continue
                    op(1, f"→ стрелка [{i}] → {nm(t)}", _link(i, t), ("items", i, "to"))

    for blk in edit["blocks"]:   # grids: their tables as the new member order
        if blk["k"] != "grid": continue
        gid, cs = blk["id"], gcells(blk)
        for c in cs:   # a heading's text in a cell
            if c["id"] and not c["struck"] and c["text"] is not None and I.get(c["id"], {}).get("type") == "text" and c["id"] not in dup:
                was = "«" + first(I[c["id"]].get("text"))[:40] + "»"
                if c["name"] != was: op(1, f"~ заголовок {was} → «{c['text']}»", _set_text(c["id"], c["text"]), ("items", c["id"], "text"))
        live = [c for c in cs if not c["struck"] and (not c["id"] or c["id"] not in dup)]
        if gid and gid in T:
            ids = [c["id"] for c in live if c["id"]]
            ms = [m for m in T[gid]["members"] if m in I]
            if ids == ms and blk["cols"] == max(1, min(T[gid].get("cols") or 1, len(ms) or 1)) and all(c["id"] for c in live): continue
            gone = [m for m in T[gid]["members"] if m not in ids and m in I and m not in EO]   # out of the table and mentioned nowhere else
            op(2, f"▦ сетка {gid}: {len(live)} ячеек, {blk['cols']} колонок" + (f", вышли {', '.join(gone)}" if gone else ""),
               _grid(blk, gid, live, gone), ("grids", gid, "*"), *[("items", c["id"], "pos") for c in live if c["id"] and c["id"] not in T[gid]["members"]])
        elif gid and gid not in T: bad.append((blk["ln"], f"сетки {gid} нет на странице"))
        elif len(live) >= 2:
            op(2, f"▦ новая сетка: {len(live)} ячеек, {blk['cols']} колонок", _grid(blk, None, live, []), *[("items", c["id"], "pos") for c in live if c["id"]])

    E = edit["blocks"]
    seen = {}   # lines without an id that the view printed itself (a document's quote or list): not new things
    for k, x in enumerate(view["blocks"]):
        if not x["id"] and x["k"] in ("item", "note", "heading"): seen[sig(view["blocks"], k)] = seen.get(sig(view["blocks"], k), 0) + 1
    for k, blk in enumerate(E):   # moves and new things, in the edit's order: each after the line before it
        i = blk["id"]
        if blk["struck"] or (i and i in dup): continue
        if not i and blk["k"] in ("item", "note", "heading") and seen.get(sig(E, k)):
            seen[sig(E, k)] -= 1; continue
        if blk["k"] == "group" and not i:
            inside = [b for b in E if b["sec"] == blk["key"] and not b["struck"]]
            op(3, f"+ группа «{blk['text']}»: {len(inside)} строк", _new_group(E, k, blk, inside))
            continue
        if str(blk["sec"]).startswith("+"): continue   # inside a new group: made with it
        if blk["k"] == "item" and i and i in I and i in BO:
            b0, at0 = BO[i][0]
            was = (b0["sec"], b0["id"] if b0["k"] == "grid" else None)
            if was == (blk["sec"], None): continue
            if blk["sec"] is None and not full and was[0] is not None: continue   # a part of the page: no section header, nothing moved
            where = f"в группу «{first(G[blk['sec']].get('title'))}»" if blk["sec"] in G else "на страницу"
            op(3, f"⇢ {nm(i)} {where}" + (f" (из сетки {was[1]})" if was[1] else ""), _place_after(E, k, i), ("items", i, "pos"), ("member", i, "group"))
        elif blk["k"] == "item" and not i and blk["name"]:
            op(3, f"+ кадр {blk['name']}", _new_pic(E, k, blk["name"]))
        elif blk["k"] in ("heading", "note") and not i and blk["text"].strip():
            what = "заголовок" if blk["k"] == "heading" else "заметка"
            op(3, f"+ {what} «{first(blk['text'])[:40]}»", _new_text(E, k, blk))
        elif blk["k"] in ("heading", "note") and i and i in BO and BO[i][0][0]["sec"] != blk["sec"] and (blk["sec"] is not None or full):
            bad.append((blk["ln"], f"{nm(i)}: заголовки и заметки между группами переносит hy.py do move, не md"))

    for sec in {b["sec"] for b in E}:   # free lines of one section in another order: they trade places
        mine = [b["id"] for b in E if b["k"] == "item" and b["sec"] == sec and b["id"] and b["id"] in BO and not b["struck"] and b["id"] not in dup
                and (BO[b["id"]][0][0]["sec"], BO[b["id"]][0][0]["k"]) == (sec, "item")]
        was = [b["id"] for b in view["blocks"] if b["id"] in mine]
        if len(mine) > 1 and mine != was:
            op(4, f"↕ порядок: {' '.join(nm(x).rsplit(' [', 1)[0] for x in mine[:6])}" + (" …" if len(mine) > 6 else ""), _reorder(was, mine),
               *[("items", x, "pos") for x in mine])

    for blk in E:   # struck lines: what they name goes
        if not blk["struck"] or not blk["id"]: continue
        i = blk["id"]
        if blk["k"] == "group" and i in G: op(5, f"− рамка группы «{first(G[i].get('title'))}» (содержимое остается)", _remove(i, True), ("groups", i, "*"))
        elif i in I: op(5, f"− {nm(i)}", _remove(i), ("items", i, "*"))
    for blk in E:
        if blk["k"] == "grid":
            for c in gcells(blk):
                if c["struck"] and c["id"] in I: op(5, f"− {nm(c['id'])} (из сетки)", _remove(c["id"]), ("items", c["id"], "*"))
    ops.sort(key=lambda o: o["ph"])
    return ops


# ---- running: the operations on the page as it is now ------------------------------------------------------------------------------
def _members(b, i): return sorted(k for k, g in (b.get("groups") or {}).items() if i in g.get("members", []))


def changed(base, cur, touch):
    """why an operation must not run: the thing it changes was changed (or removed) since the version the view was made from"""
    for coll, i, f in touch:
        if coll == "member":
            if _members(base, i) != _members(cur, i): return f"[{i}] переложили в другую группу"
            continue
        o0, o1 = (base.get(coll) or {}).get(i), (cur.get(coll) or {}).get(i)
        if o0 is None: continue
        if o1 is None: return f"[{i}] уже убрали"
        if f == "pos": same = (o0.get("x"), o0.get("y")) == (o1.get("x"), o1.get("y"))
        elif f == "*":
            strip = lambda o: {k: v for k, v in o.items() if k not in ("rows", "head")}
            same = strip(o0) == strip(o1)
        else: same = o0.get(f) == o1.get(f)
        if not same: return f"[{i}] изменили после этой версии ({'место' if f == 'pos' else 'поле ' + f if f != '*' else 'целиком'})"
    return None


def fit_text(it):
    """a heading's box after its words changed: a text document's estimate (textdocs.py), else as wide as its letters"""
    try:
        import textdocs
        if textdocs.is_doc(it): it["tw"] = it.get("tw") or round((it.get("fs") or 40) * textdocs.WRAP)
        else: it.pop("tw", None)
        it["w"], it["h"] = textdocs.estimate(it); return
    except ImportError:
        pass
    if it.get("fs"): it["w"] = max(it.get("w") or 0, round(it["fs"] * .6 * len(first(it.get("text")))))


def _set_text(i, text, body=None):
    def run(b, c):
        it = b["items"][i]; t = new_first(it.get("text"), text)
        if body is not None: t = t.split("\n")[0] + ("\n" + body if body.strip() else "")
        it["text"] = t; fit_text(it)
        return f"заголовок [{i}] «{text}»" + (f" +{len(body.splitlines())} строк" if body else "")
    return run


def _set_title(i, text):
    def run(b, c): g = b["groups"][i]; g["title"] = new_first(g.get("title"), text); return f"группа [{i}] «{text}»"
    return run


def _set_note(i, text):
    def run(b, c): b["items"][i]["text"] = text; return f"заметка [{i}]"
    return run


def _link(i, t):
    def run(b, c): return c.hy.OPS["link"](b, [i, t], {})
    return run


def _unlink(i, t):
    def run(b, c): n = b["items"][i]; n["to"] = [x for x in n.get("to") or [] if x != t]; return f"стрелка [{i}] → [{t}] снята"
    return run


def _remove(i, frame=False):
    def run(b, c): return c.hy.OPS["remove"](b, [i], {"only": "frame"} if frame else {})
    return run


def box(c, b, i):
    if i in (b.get("items") or {}) and b["items"][i].get("x") is not None: return c.hy.rect(b, i)
    if i in (b.get("groups") or {}) and b["groups"][i].get("x") is not None: return {k: b["groups"][i][k] for k in "xywh"}
    if i in grids.table(b): return grids.bbox(b, i)
    return None


def holders(b, gid):
    """gid and the frames that hold it"""
    G = b.get("groups") or {}
    if gid not in G: return set()
    g = G[gid]
    return {k for k, o in G.items() if o.get("x") is not None and o["x"] <= g["x"] and o["y"] <= g["y"] and o["x"] + o["w"] >= g["x"] + g["w"]
            and o["y"] + o["h"] >= g["y"] + g["h"]} | {gid}


def pad_of(b, hy):
    pw = sorted(it["w"] for it in b["items"].values() if hy.is_pic(it))
    return round((pw[len(pw) // 2] if pw else 320) * 1.5)


def neighbours(E, k, b):
    """the thing on the board the line before (else after) this one names, in the same section"""
    sec = E[k]["sec"]
    for j in range(k - 1, -1, -1):
        x = E[j]
        if x["k"] == "group" and (x["id"] or x.get("key")) == sec: break
        if x["sec"] != sec or x["struck"]: continue
        i = x["id"] or x.get("made")
        if x["k"] == "grid" and x["id"] is None: i = x.get("made")
        if i and (i in b["items"] or i in grids.table(b) or i in b["groups"]): return i, "after"
    for x in E[k + 1:]:
        if x["sec"] != sec or x["struck"] or x["k"] == "group": continue
        if x["id"] and (x["id"] in b["items"] or x["id"] in grids.table(b)): return x["id"], "before"
    return None, None


def place(c, b, iid, sec, near, how, below=False):
    """iid beside near (after: right of it, or under it for a heading or a note; before: left / above) with nothing under it, inside the
    group sec, whose frame (and the frames holding it) grows to hold it; no near: the group's top left, or under the page's content"""
    hy = c.hy; r = hy.rect(b, iid); size = {"w": r["w"], "h": r["h"]}
    sec = sec if sec in (b.get("groups") or {}) else None
    skip = holders(b, sec) if sec else set()
    ref = box(c, b, near) if near else None
    if ref: side = ("below" if below else "right") if how == "after" else ("above" if below else "left")
    elif sec: g = b["groups"][sec]; p = pad_of(b, hy); ref, side = {"x": g["x"] + p - GAP, "y": g["y"] + p, "w": 0, "h": 0}, "right"
    else:
        rs = [x for x in hy.all_rects(b) if x] or [{"x": 0, "y": 0, "w": 0, "h": 0}]
        ref, side = {"x": min(x["x"] for x in rs), "y": max(x["y"] + x["h"] for x in rs) + pad_of(b, hy), "w": 0, "h": 0}, "right"
    cx, cy = ref["x"] + ref["w"] / 2, ref["y"] + ref["h"] / 2
    obs = [{k: g[k] for k in "xywh"} for k, g in b["groups"].items() if k not in skip and g.get("x") is not None]
    for k, it in b["items"].items():
        if k == iid or it.get("x") is None: continue
        obs.append(hy.rect(b, k))
        z = hy.zone_rect(it) if it.get("type") == "note" and it.get("reach") else None
        if z and not (z["x"] <= cx <= z["x"] + z["w"] and z["y"] <= cy <= z["y"] + z["h"]): obs.append(z)   # a zone it joins is no obstacle
    sp, _ = hy._spot(obs, ref, size, side, GAP if not below else GAP * 2)
    if sp is None: sp = hy.free_spot(b, ref, size, side, GAP)
    it = b["items"][iid]; it["x"], it["y"] = sp["x"], sp["y"]
    for g in b["groups"].values(): g["members"] = [m for m in g.get("members", []) if m != iid]
    if not sec: return " на странице"
    msg = hy.grow_into(b, sec, [iid], hy.rect(b, iid), pad_of(b, hy))
    inner = b["groups"][sec]
    for k in sorted(skip - {sec}, key=lambda k: b["groups"][k]["w"] * b["groups"][k]["h"]):   # the frames around grow too, inner first
        o = b["groups"][k]
        if not (o["x"] <= inner["x"] and o["y"] <= inner["y"] and o["x"] + o["w"] >= inner["x"] + inner["w"] and o["y"] + o["h"] >= inner["y"] + inner["h"]):
            hy.grow_into(b, k, [], {q: inner[q] for q in "xywh"}, pad_of(b, hy))
    return msg


def _place_after(E, k, iid):
    def run(b, c):
        if iid not in b["items"]: return f"[{iid}] уже нет"
        if grids.of(b, iid): grids.leave(b, [iid])
        near, how = neighbours(E, k, b)
        return f"{grids.cell(b, iid)}" + place(c, b, iid, E[k]["sec"], near, how)
    return run


def _sizes(c, paths):
    try: got = c.hy.api("/api/sizes", {"paths": list(paths)})[1]
    except Exception: got = {}
    return got if isinstance(got, dict) else {}


def _pic(c, b, path, w=None):
    """a library picture as a new item at 0, 0 (placed after), or None when the library has no such file"""
    s = _sizes(c, [path]).get(path)
    if not s or not s[0] or not s[1]: return None
    pw = sorted(it["w"] for it in b["items"].values() if c.hy.is_pic(it))
    i = c.hy.uid("i"); b["items"][i] = {"path": path, "x": 0, "y": 0, "w": w or (pw[len(pw) // 2] if pw else 320), "ar": s[0] / s[1]}
    b.get("removed", {}).pop(path, None)
    return i


def _new_pic(E, k, path):
    def run(b, c):
        i = _pic(c, b, path)
        if not i: raise Refused(f"в библиотеке нет картинки «{path}»")
        E[k]["made"] = i; near, how = neighbours(E, k, b)
        return f"+ {grids.cell(b, i)}" + place(c, b, i, E[k]["sec"], near, how)
    return run


def heading_fs(b, lvl, sec):
    """a new heading's size: the headings of this level in that section, else of the page, else 874 for ## (a section) and 120 under it"""
    hs = [it["fs"] for it in b["items"].values() if it.get("type") == "text" and it.get("fs")]
    big = [f for f in hs if f >= hymd.SECTION_FS]; small = [f for f in hs if f < hymd.SECTION_FS]
    pool = big if lvl == 2 and sec is None else small
    return sorted(pool)[len(pool) // 2] if pool else (874 if lvl == 2 and sec is None else 120)


def _new_text(E, k, blk):
    def run(b, c):
        hy = c.hy
        if blk["k"] == "heading":
            fs = heading_fs(b, blk["lvl"], blk["sec"]); t = blk["text"] + ("\n" + unshift(blk["body"], blk["lvl"]) if blk.get("body") else "")
            i = hy.uid("t"); b["items"][i] = {"type": "text", "text": t, "x": 0, "y": 0, "fs": fs, "size": 4, "w": round(fs * .6 * len(blk["text"])), "h": round(fs * 1.15)}
            fit_text(b["items"][i])
        else:
            pw = sorted(it["w"] for it in b["items"].values() if hy.is_pic(it)); w = round(pw[len(pw) // 2] if pw else 320)
            i = hy.uid("n"); b["items"][i] = {"type": "note", "text": blk["text"], "x": 0, "y": 0, "w": w, "fs": w * hy.NSIZE[2], "size": 2, "h": 0,
                                               "color": "blue", "reach": None, "to": []}
        E[k]["made"] = i; near, how = neighbours(E, k, b)
        msg = f"+ [{i}]" + place(c, b, i, blk["sec"], near, how, below=True)
        for L in blk.get("links", []):
            if not L["struck"] and (L["id"] in b["items"] or L["id"] in b["groups"]): msg += " · " + hy.OPS["link"](b, [i, L["id"]], {})
        return msg
    return run


def _grid(blk, gid, live, gone):
    def run(b, c):
        hy, made = c.hy, []
        if gid and gid not in grids.table(b): return f"сетки {gid} уже нет"
        old = list(grids.table(b)[gid]["members"]) if gid else []
        heads_fs = [b["items"][m]["fs"] for m in old if b["items"].get(m, {}).get("type") == "text" and b["items"][m].get("fs")]
        w = next((b["items"][m]["w"] for m in old if hy.is_pic(b["items"].get(m))), None)
        ids = []
        for x in live:
            if x["id"]:
                if x["id"] in b["items"]: ids.append(x["id"])
                continue
            if x["text"] is not None:
                fs = heads_fs[0] if heads_fs else 40; i = hy.uid("t")
                b["items"][i] = {"type": "text", "text": x["text"], "x": 0, "y": 0, "fs": fs, "size": 1, "w": round(fs * .6 * max(1, len(x["text"]))), "h": round(fs * 1.15)}
            else:
                i = _pic(c, b, x["name"], w)
                if not i: raise Refused(f"в библиотеке нет картинки «{x['name']}» (ячейка сетки)")
            made.append(i); ids.append(i)
        ids = list(dict.fromkeys(ids))
        if gid is None:
            at = [m for m in ids if m not in made]
            if not at: raise Refused("новая сетка только из новых вещей: положи хотя бы одну, что уже на странице")
            for i in made: b["items"][i]["x"], b["items"][i]["y"] = grids.origin(b, at)
            try: g2 = grids.make(b, ids, cols=blk["cols"], order=False)
            except ValueError as e: raise Refused(str(e))
            blk["made"] = g2
            return f"{grids.title(b, g2)}" + (f" · новых {len(made)}" if made else "")
        g = grids.table(b)[gid]; at = grids.origin(b, g["members"])
        for i in made: b["items"][i]["x"], b["items"][i]["y"] = at
        come = [m for m in ids if m not in g["members"]]
        grids.leave(b, come, keep=gid)
        g["members"], g["cols"] = ids, max(1, int(blk["cols"]))
        if len(ids) < 2:
            del b["grids"][gid]; return f"сетка {gid} распалась: в таблице меньше 2 вещей"
        grids.reflow(b, gid, at); grids.regroup(b, come)
        msg = grids.title(b, gid) + (f" · новых {len(made)}" if made else "")
        for m in gone:   # out of the table and nowhere else in the edit: under the grid, not under its cells
            if m in b["items"]:
                gg = grids.group_of(b, gid) if gid in grids.table(b) else None
                msg += f" · {grids.cell(b, m)} вышел" + place(c, b, m, gg, gid, "after", below=True)
        return msg
    return run


def _reorder(was, now):
    def run(b, c):
        ids = [i for i in was if i in b["items"]]
        slots = [(b["items"][i]["x"], b["items"][i]["y"]) for i in ids]
        order = [i for i in now if i in ids]
        for i, (x, y) in zip(order, slots): b["items"][i]["x"], b["items"][i]["y"] = x, y
        return "порядок: " + " ".join(order)
    return run


def _new_group(E, k, blk, inside):
    def run(b, c):
        hy = c.hy; pics, texts = [], []
        for x in inside:
            if x["k"] == "item" and x["id"] and x["id"] in b["items"]: pics.append(x["id"])
            elif x["k"] == "item" and not x["id"] and x["name"]:
                i = _pic(c, b, x["name"])
                if not i: raise Refused(f"в библиотеке нет картинки «{x['name']}»")
                x["made"] = i; pics.append(i)
            elif x["k"] in ("heading", "note") and not x["id"]: texts.append(x)
        if not pics: raise Refused(f"новая группа «{blk['text']}»: в ней нет ни одного кадра или карточки (без них hy.py do group)")
        grids.leave(b, pics)
        near = next((x["id"] for x in reversed(E[:k]) if x["k"] == "group" and x["id"] in b["groups"]), None)
        kv = {"group": blk["text"]}
        if near: kv.update(near=near, side="right")
        else:
            rs = hy.all_rects(b); kv.update(x=max((r["x"] + r["w"] for r in rs), default=0) + pad_of(b, hy), y=min((r["y"] for r in rs), default=0))
        note = next((t for t in texts if t["k"] == "note"), None)
        if note: kv["note"] = note["text"]; texts.remove(note)
        msg = hy.lay_out(b, [[b["items"][i] for i in pics]], kv, "md", moving=pics)
        gid = next(g for g, o in b["groups"].items() if pics[0] in o.get("members", []))
        blk["made"] = gid
        for t in texts:
            j = E.index(t); t["sec"] = gid
            msg += " · " + _new_text(E, j, t)(b, c)
        return msg
    return run


class Refused(Exception):
    pass


class Ctx:
    def __init__(self, hy): self.hy = hy


def execute(ops, base, cur, hy):
    """the operations on cur (changed in place): [(op, result or None, why skipped)]"""
    c, out = Ctx(hy), []
    for o in ops:
        why = changed(base, cur, o["touch"])
        if why: out.append((o, None, why)); continue
        keep = copy.deepcopy(cur)   # an operation that fails leaves nothing half done
        try:
            before = grids.origins(cur); res = o["run"](cur, c); grids.prune(cur, before)
            out.append((o, res, None))
        except (Refused, SystemExit, KeyError, ValueError, TypeError) as e:
            cur.clear(); cur.update(keep); out.append((o, None, f"не вышло: {e}"))
    if "grids" in cur and not cur["grids"]: del cur["grids"]
    return out


# ---- hy.py md apply -------------------------------------------------------------------------------------------------------------
def _flag(name, default=None):
    a = sys.argv
    if name in a:
        k = a.index(name)
        return a[k + 1] if default is not None and k + 1 < len(a) else True
    return default if default is not None else False


def main(args, page, hy):
    src = next((a for a in args if not a.startswith("--") or a == "-"), None)
    if not src: raise SystemExit("hy.py md apply ФАЙЛ.md | - [--dry] [--page P]: правка вида hy.py md обратно на доску")
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    dry, label = "--dry" in args or _flag("--dry"), _flag("--label", "правка через md")
    say, quiet = _flag("--say", ""), _flag("--quiet")
    edit = parse(text); st = edit["stamp"]
    if page and st.get("page") and page != st["page"]: raise SystemExit(f"вид сделан со страницы {st['page']}, а --page {page}")
    page = st.get("page") or page
    if not page:
        try: page = (hy.api("/api/live")[1].get("canvas") or {}).get("page") or "main"
        except Exception: page = "main"
    hy.LABEL = label
    code, cur = hy.api(f"/api/board?name={urllib.parse.quote(page)}")
    if code != 200 or not isinstance(cur, dict): raise SystemExit(f"нет страницы «{page}»: {code}")
    base, how = base_of(hy.api, page, st, cur) if st else (None, "")
    print(f"# md apply · страница {page} · сейчас ревизия {cur.get('revision', 0)}")
    if base is None:
        base = copy.deepcopy(cur)
        print("! нет версии, с которой сделан вид" + (f" (ревизия {st.get('rev')})" if st else " (нет первой строки <!-- hyimg md … -->)")
              + ": сравниваю с доской как сейчас, чужие правки после вида не отличить")
    elif how != "та же версия":
        print(f"база: ревизия {st.get('rev')} ({how}); после нее доску меняли, правки тех же вещей пропускаю")
    ops = plan(base, edit)
    for ln, why in edit["bad"]: print(f"? строка {ln}: {why}")
    if not ops: print("изменений нет"); return
    work = copy.deepcopy(cur); res = execute(ops, base, work, hy)
    for o, r, why in res:   # the operation, and under it what it did: where a thing landed, how a frame grew, what moved aside
        print(("! пропуск " + o["show"][2:] + f": {why}") if why else o["show"] + (f"\n    {r.strip()}" if isinstance(r, str) and r.strip() else ""))
    if dry:
        print("(проба, не сохранено)"); hy.report(cur, work); return
    if not any(r for _, r, _w in res): print("сохранять нечего"); return
    for attempt in range(4):
        if attempt:
            code, cur = hy.api(f"/api/board?name={urllib.parse.quote(page)}"); work = copy.deepcopy(cur); res = execute(ops, base, work, hy)
        if attempt == 0: _, e = hy.api("/api/history", {"action": "save", "name": page, "who": "ai", "label": f"до: {label}"})
        code, r = hy.api(f"/api/board?name={urllib.parse.quote(page)}", work)
        if code == 200: break
        if code != 409: raise SystemExit(f"сервер не сохранил: {code} {r}")
    else:
        raise SystemExit("доску все время сохраняют, не смог записать; попробуй еще раз")
    _, e2 = hy.api("/api/history", {"action": "save", "name": page, "who": "ai", "label": f"после: {label}"})
    vid = lambda x: x.get("id") if isinstance(x, dict) else "нет"
    print(f"ревизия {r.get('revision')} · версии {vid(e)} → {vid(e2)}")
    hy.report(cur, work)
    if not quiet:
        try: hy.notify_added(cur, work, page, say or None, label)
        except Exception as ex: print(f"уведомление не ушло: {ex}")
