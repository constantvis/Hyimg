"""hy.py comments, annotations and look: the board's comment threads and drawings for an agent, in words (owner 2026-10-07: comments with
@mentions, as in Figma, an @mention of an agent is how the owner gives it a task on the board; «как аннотации будут работать в json? ...
чтобы они всё понимали, не смотря на картинки»). Threads live in comments/<page>__<id>.json, drawings in annotations/<page>__<id>.json
(review/comments.py), each with a `describe` line the server keeps fresh (review/annotext.py).

  hy.py comments [PAGE] [--open | --resolved] [--mentions me|claude|codex|gemini|kimi|opencode|self] [--all]
                                     the threads, newest first: id, where (an area or a pin, an element), the drawings about it, who, the messages
  hy.py comments add REF "text"      a new thread pinned to a thing (REF as in do: a name, an id, @Стили) or at --x X --y Y on the page
  hy.py comments reply ID "text"     an answer in a thread (an @name in the text mentions that person or agent)
  hy.py comments resolve ID | reopen ID
  hy.py comments delete ID MID       takes back one of your own messages (MID, the [m…] before it in the list); the server refuses
                                     anyone else's. Did work because of a comment: write nothing in the thread, notify is the news
                                     (owner 2026-10-08); a reply only answers his question or asks the one thing you can't do without
  hy.py annotations [PAGE] [--object REF] [--author TEXT] [--all]
                                     the drawings by object, each in words and numbers, the comments they are about, the library's marks
  hy.py look [REF] --ann ID | --comment ID | --mark N   the marked region of the picture's own pixels (a margin around), as a png in a
                                     temporary folder; its path and the mark's words are printed. REF alone: the whole picture
The server signs each with this Mac's person and the agent it sees running hy.py; nothing to set. find and map list the drawings and
comments under each object too (notelinks.tail)."""
import io
import os
import sys
import tempfile
import urllib.parse

SUBS = ("add", "reply", "resolve", "reopen", "delete")
PIN_STEP_SHARE, PIN_STEP_FREE = 0.12, 120   # a pin's step down past the pins already there: a share of the thing's height, board units


def spread(at, anchor, threads):
    """Where a new pin goes when pins are already at that place (2026-10-08: ten questions added to one group lay on one spot): it steps
    down past each pin on the same thing (or a free pin near the point), a column of pins; inside a thing, past its bottom it starts a
    new column to the left. Areas don't count, their pin is the area's corner."""
    at = list(at)
    if anchor:
        taken = [t["at"] for t in threads if (t.get("anchor") or {}).get("obj") == anchor["obj"] and not t.get("area") and t.get("at")]
        step, near = PIN_STEP_SHARE, PIN_STEP_SHARE / 2
    else:
        taken = [t["at"] for t in threads if not t.get("anchor") and t.get("at")]
        step, near = PIN_STEP_FREE, PIN_STEP_FREE / 2
    for _ in range(200):
        if not any(abs(a[0] - at[0]) < near and abs(a[1] - at[1]) < near for a in taken): break
        at[1] += step
        if anchor and at[1] > 0.95: at = [round(at[0] - step, 4), 0.08]
    return [round(v, 4) for v in at]


def _page(api, page, name):
    """a page by its id or its title; None: the one the owner has open"""
    if name:
        try: pages = api("/api/pages")[1]["pages"]
        except Exception: return name
        return next((p["id"] for p in pages if name in (p["id"], p.get("title"))), name)
    if page: return page
    try: return (api("/api/live")[1].get("canvas") or {}).get("page") or "main"
    except Exception: return "main"


def _who(by, people):
    p = people.get((by or {}).get("person")) or {}
    via = (by or {}).get("via", "app")
    name = p.get("name") or "?"
    return name if via == "app" else f"{via.capitalize() if via != 'opencode' else 'OpenCode'} · {name}"


def _described(api, page, all_pages=False):
    """{page: {items, threads, library}} with the server's words, fresh"""
    code, res = api("/api/annotations?" + urllib.parse.urlencode({"name": page, "describe": "1", **({"all": "1"} if all_pages else {})}))
    if code != 200: raise SystemExit(f"сервер: {code} {res}")
    return res["pages"] if all_pages else {page: res}


def show(t, people, words=None):
    words = words or t.get("describe")
    if not words:
        words = (t.get("anchor") or {}).get("file") or (t.get("anchor") or {}).get("obj") or "x {} y {}".format(*[round(v) for v in t.get("at") or [0, 0]])
        el = t.get("element")
        if el:
            from annotext import element_text   # review/ is on the path of hy.py
            words += element_text(el)
    el = t.get("element")
    if el and el.get("text"): words += f" «{el['text'][:40]}»"
    state = "решено" if t.get("resolved") else "открыто"
    out = [f"[{t['id']}] страница {t['page']}, {words}, {state}, ответов {len(t['messages']) - 1}"]
    for m in t["messages"]:
        ment = ", ".join("@" + x.get("label", "") for x in m.get("mentions") or [])
        out.append(f"   {m['created'][5:16].replace('T', ' ')} [{m['id']}] {_who(m.get('by'), people)}: {m['text']}" + (f"  (упомянуты: {ment})" if ment else ""))
    return "\n".join(out)


def comments(args, page, api, resolve, rect, flags, pos):
    sub = pos[0] if pos and pos[0] in SUBS else None
    if sub is None:
        page = _page(api, page, pos[0] if pos else None)
        qs = {"name": page, **{k: v for k, v in flags.items() if k in ("open", "resolved", "all", "mentions")}}
        code, res = api("/api/comments?" + urllib.parse.urlencode(qs))
        if code != 200: raise SystemExit(f"сервер: {code} {res}")
        words = {t["id"]: t.get("describe") for d in _described(api, page, bool(flags.get("all"))).values() for t in d["threads"]}
        people = (api("/api/profile")[1] or {}).get("people") or {}
        items = res.get("items") or []
        print(f"# комментарии: {'все страницы' if flags.get('all') else 'страница ' + page}, {len(items)}")
        for t in items: print(show(t, people, words.get(t["id"])))
        return
    page = _page(api, page, None)
    if sub == "add":
        if len(pos) < 3 and not ("x" in flags and len(pos) >= 2): raise SystemExit('hy.py comments add REF "текст"  или  add "текст" --x X --y Y')
        text, anchor, at = pos[-1], None, None
        if len(pos) >= 3:
            _, b = api(f"/api/board?name={page}")
            if pos[1] in b["items"]: rid, r = pos[1], rect(b, pos[1])   # a thing by its id (find, an obj= link)
            else: _, rid, _, r = resolve(b, pos[1])
            it = b["items"].get(rid)
            if it:
                anchor = {"obj": rid, "kind": it.get("type") or "picture", "file": it.get("path") or it.get("src") or it.get("scene") or "",
                          "r": [r["x"], r["y"], r["w"], r["h"]]}
                at = [0.92, 0.08]   # the pin near its top right corner, inside the thing
            else:
                at = [r["x"] + r["w"] - 24, r["y"] + 24]
        else:
            at = [float(flags["x"]), float(flags["y"])]
        try: at = spread(at, anchor, api("/api/comments?" + urllib.parse.urlencode({"name": page, "open": 1}))[1].get("items") or [])
        except Exception: pass   # no list: the pin where it was asked
        code, res = api("/api/comments", {"op": "new", "name": page, "anchor": anchor, "at": at, "text": text})
    elif sub == "reply":
        if len(pos) < 3: raise SystemExit('hy.py comments reply ID "текст"')
        code, res = api("/api/comments", {"op": "reply", "name": _thread_page(api, pos[1], page), "id": pos[1], "text": pos[2]})
    elif sub == "delete":   # one's own message only (comments._own); the first message would take the whole thread, so not here
        if len(pos) < 3: raise SystemExit("hy.py comments delete ID MID")
        name = _thread_page(api, pos[1], page)
        t = next((x for x in (api("/api/comments?" + urllib.parse.urlencode({"name": name}))[1].get("items") or []) if x["id"] == pos[1]), None)
        if not t: raise SystemExit(f"нет комментария {pos[1]}")
        if t["messages"] and t["messages"][0]["id"] == pos[2]: raise SystemExit("это первое сообщение, оно удалит всю ветку; так не удаляю")
        code, res = api("/api/comments", {"op": "delete", "name": name, "id": pos[1], "mid": pos[2]})
    else:
        if len(pos) < 2: raise SystemExit(f"hy.py comments {sub} ID")
        code, res = api("/api/comments", {"op": sub, "name": _thread_page(api, pos[1], page), "id": pos[1]})
    if code != 200: raise SystemExit(f"не записано: {code} {res}")
    people = (api("/api/profile")[1] or {}).get("people") or {}
    print(show(res["thread"], people))


def _thread_page(api, tid, page):
    """the page a thread lives on (the agent names only its id)"""
    code, res = api("/api/comments?" + urllib.parse.urlencode({"all": "1"}))
    return next((t["page"] for t in (res.get("items") or []) if t["id"] == tid), page) if code == 200 else page


def _obj_name(b, oid):
    it = (b.get("items") or {}).get(oid) or {}
    return it.get("path") or it.get("src") or it.get("scene") or it.get("name") or oid


def annotations(args, page, api, resolve, rect, flags, pos):
    page = _page(api, page, pos[0] if pos else None)
    pages = _described(api, page, bool(flags.get("all")))
    want = None
    if flags.get("object"):
        _, b = api(f"/api/board?name={page}")
        want = flags["object"] if flags["object"] in b["items"] else resolve(b, flags["object"])[1]
    author = (flags.get("author") or "").lower()
    for pg, d in pages.items():
        _, b = api(f"/api/board?name={pg}")
        by_obj = {}
        for a in d["items"]:
            if author and author not in (a.get("describe") or "").lower(): continue
            by_obj.setdefault((a.get("anchor") or {}).get("obj"), []).append(f"✎ [{a['id']}] {a.get('describe') or a.get('kind')}")
        for t in d["threads"]:
            if t.get("area") and (not author or author in (t.get("describe") or "").lower() or author in str(t.get("by"))):
                by_obj.setdefault((t.get("anchor") or {}).get("obj"), []).append(f"комментарий [{t['id']}] {t.get('describe')}: «{t['messages'][0]['text'][:80]}»")
        for oid, marks in (d.get("library") or {}).items():
            for m in marks: by_obj.setdefault(oid, []).append(f"✎ [метка {m['n']}] {m['text']}")
        keys = [k for k in by_obj if want is None or k == want]
        print(f"# аннотации: страница {pg}, объектов {len(keys)}")
        for k in keys:
            print(f"{_obj_name(b, k) if k else 'пустое место доски'} [{k or '-'}]")
            for line in by_obj[k]: print("   " + line)


def picture_url(it):
    """the pixels look crops: a picture's own file; a card of a page (an HTML card, an HTML frame) its largest still, the page drawn at
    twice its css size, 2560 px wide (2026-10-08: s=2048 was no size /thumb has, so it handed out 640 px and a comment's slider row came
    out a blur no agent could read)"""
    if it.get("path"): return "/img?p=" + urllib.parse.quote(it["path"])
    url = "/thumb?s=2560&p=" + urllib.parse.quote(it.get("src") or "")
    vw = it.get("vw")   # drawn at the card's own viewport, as its live page lays out (vh follows the card's shape)
    if isinstance(vw, (int, float)) and vw > 0 and it.get("w") and it.get("h"):
        url += f"&vw={round(vw)}&vh={max(1, round(vw * it['h'] / it['w']))}"
    return url


def look(args, page, api, resolve, rect, flags, pos):
    """the marked region of an object's own pixels, as a png"""
    page = _page(api, page, None)
    d = _described(api, page, True)
    region, oid, words = None, None, ""
    if flags.get("ann") or flags.get("comment"):
        key = "items" if flags.get("ann") else "threads"
        hit = next(((pg, x) for pg, v in d.items() for x in v[key] if x["id"] == (flags.get("ann") or flags.get("comment"))), None)
        if not hit: raise SystemExit(f"нет {'рисунка' if flags.get('ann') else 'комментария'} {flags.get('ann') or flags.get('comment')}")
        page, x = hit; region, oid, words = x.get("region"), (x.get("anchor") or {}).get("obj"), x.get("describe") or ""
        if not oid: raise SystemExit("он на пустом месте доски, смотреть нечего: " + words)
    _, b = api(f"/api/board?name={page}")
    if pos:
        oid = pos[0] if pos[0] in b["items"] else resolve(b, pos[0])[1]
    if flags.get("mark"):
        m = next((m for m in (d.get(page, {}).get("library") or {}).get(oid, []) if str(m["n"]) == str(flags["mark"])), None)
        if not m: raise SystemExit(f"у {oid} нет метки {flags['mark']}")
        region, words = m["region"], m["text"]
    it = b["items"].get(oid)
    if not it: raise SystemExit(f"не нашел объект {oid}")
    from PIL import Image
    path = it.get("path")
    code, raw = _bytes(api, picture_url(it))
    if code != 200: raise SystemExit(f"картинка не пришла: {code}")
    im = Image.open(io.BytesIO(raw)); W, H = im.size
    if region and region.get("px") and region.get("unit") == "px" and region.get("size"):
        sx, sy = W / region["size"][0], H / region["size"][1]
        x0, x1, y0, y1 = [v * s for v, s in zip(region["px"], (sx, sx, sy, sy))]
    else:
        c = (it.get("crop") or [0, 0, 1, 1]) if path else [0, 0, 1, 1]
        u, v = (region or {}).get("u") or [0, 1], (region or {}).get("v") or [0, 1]
        x0, x1 = [(c[0] + t * (c[2] - c[0])) * W for t in u]; y0, y1 = [(c[1] + t * (c[3] - c[1])) * H for t in v]
    m = max(16, .08 * max(x1 - x0, y1 - y0))
    box = (max(0, int(x0 - m)), max(0, int(y0 - m)), min(W, int(x1 + m + 1)), min(H, int(y1 + m + 1)))
    out = os.path.join(tempfile.mkdtemp(prefix="hyimg-look-"), f"{oid}-{box[0]}-{box[1]}.png")
    im.crop(box).save(out)
    print(out)
    print(f"# {path or it.get('src')}: px {box[0]}–{box[2]} × {box[1]}–{box[3]} из {W}×{H}" + (f"; {words}" if words else ""))
    try:   # the notes about it, and what else each of them is about (owner 2026-10-08: a note's other targets are part of its meaning)
        import notelinks; t = notelinks.tail(b, oid).strip("\n")
        if t: print(t)
    except Exception: pass


def _bytes(api, path):
    import urllib.request
    base = getattr(sys.modules.get("__main__"), "BASE", None) or f"http://localhost:{os.environ.get('HYIMG_PORT', '4180')}"
    try:
        with urllib.request.urlopen(base + path, timeout=60) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, b""


def main(args, page, api, resolve, rect):
    cmd, flags, pos, it = (args or ["comments"])[0], {}, [], iter((args or ["comments"])[1:])
    for x in it:
        if x in ("--open", "--resolved", "--all"): flags[x[2:]] = "1"
        elif x in ("--mentions", "--x", "--y", "--object", "--author", "--ann", "--comment", "--mark"): flags[x[2:]] = next(it, "")
        elif x.startswith("--"): raise SystemExit(f"не знаю {x}")
        else: pos.append(x)
    return {"comments": comments, "annotations": annotations, "look": look}[cmd](args, page, api, resolve, rect, flags, pos)


# ---- under each object in find and map (notelinks.tail): its drawings and comments, its library marks -------------------------------
_CACHE = {}


def tail(b, item_id):
    api = getattr(sys.modules.get("__main__"), "api", None)
    if not api: return ""
    if "pages" not in _CACHE:
        try: _CACHE["pages"] = _described(api, "main", True)
        except BaseException: _CACHE["pages"] = {}
    out = ""
    for d in _CACHE["pages"].values():
        for a in d.get("items") or []:
            if (a.get("anchor") or {}).get("obj") == item_id: out += f"\n   ✎ {a.get('describe') or a.get('kind')} [{a['id']}]"
        for t in d.get("threads") or []:
            if (t.get("anchor") or {}).get("obj") == item_id:
                out += f"\n   комментарий {t.get('describe') or ''}: «{t['messages'][0]['text'][:60]}»" + (" · решено" if t.get("resolved") else "") + f" [{t['id']}]"
        for m in (d.get("library") or {}).get(item_id, []): out += f"\n   ✎ {m['text']}"
    return out


def marks(b, area=None):
    """map's lines: every picture or card in the area with drawings or comments on it, and them"""
    tail("x", "-")   # the cache filled
    on = {(x.get("anchor") or {}).get("obj") for d in _CACHE.get("pages", {}).values() for x in (d.get("items") or []) + (d.get("threads") or [])}
    on |= {k for d in _CACHE.get("pages", {}).values() for k in (d.get("library") or {})}
    out = ""
    for oid in sorted(x for x in on if x in (b.get("items") or {})):
        it = b["items"][oid]
        if area and not (it["x"] < area["x"] + area["w"] and it["x"] + it["w"] > area["x"] and it["y"] < area["y"] + area["h"] and it["y"] + it.get("h", it["w"]) > area["y"]):
            continue
        out += f"\nпометки на {it.get('path') or it.get('src') or it.get('scene') or oid} [{oid}]:" + tail(b, oid)
    return out
