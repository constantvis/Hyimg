"""The bell's pictures (owner 2026-10-08, a screenshot of the bell: «Расстраивает, что нет картинок. Делает аннотации, а к чему он
сделал аннотацию, в основном какая-то картинка, а не пустое пространство. Желательно показать либо пространство, либо прям этот
объект, который выделен»). Every row of the bell shows what it is about, as tiles under its text: four at most, then «+N».

  a comment on an area          the crop of that area of its object (the picture's own pixels, an HTML card's still at its viewport,
                                a 3D card's still), the area outlined in its author's colour
  a pin on an object            the object's still, the pin as a dot
  a pin on an element of a page the card's still around the element's point, the dot on it
  a pin or an area on the board a small picture of the board there: the things lying in it drawn from their thumbnails (a region)
  agent news with ids           a picture: its thumbnail; a card: its still; a group: its members (up to 4); a note: what it is linked
                                to, or the board around it; a heading or a timeline: the board under it
  agent news with an area alone the board there; old news with previews alone: those pictures
A tile is a descriptor {"src", "k": "pic" | "crop" | "region", "mark"?: {"r": [x, y, w, h]} | {"pin": [x, y]} in shares of the tile,
"who"?: the person whose colour the mark takes}. A picture's tile is /thumb (square); a crop or a region is /feedthumb, 3:2, drawn
here once and kept in the thumbnail cache (~/Library/Caches/Hyimg/<board>/thumbs/feed.<hash>.webp, outside Dropbox, under the same
ceiling as every thumbnail; thumbcache.py's sweep leaves them, the ceiling ages them out). The mark is drawn by the page over the
tile (crisp, in the author's colour, either theme), so one cached picture serves every colour.

notifplace.of_ids writes the tiles into a notification when it is made ("pv", "pvn"); /api/notifications computes them on read for
one without (old news, every comment: a thread's area may have moved), cheaply: no picture is opened, only the board read (kept by
its time) and the thread file. The page loads the pictures lazily (ui/bellthumbs.js)."""
import hashlib
import json
import os
import re
import threading
import urllib.parse

import notelinks

TILES = 4             # tiles in a row, then «+N»
AR = 1.5              # a crop's and a region's tile: 3:2
OUT = (360, 240)      # its pixels (72 x 48 css, and the large one of 144 x 96, at 2.5x)
MARGIN = .25          # around an area: a share of its larger side, so the area is about two thirds of the tile
FREE_PIN = (400, 300)  # the board around a free pin, board units (comments.feed's area)
MAX_DRAWN = 160       # things drawn into one region; past that, plates
NCOL = {"yellow": ("#f4c430", "#241c04"), "orange": ("#f59a3d", "#2b1400"), "red": ("#ef6a6a", "#2b0707"), "pink": ("#f08cc4", "#2b0a1b"),
        "purple": ("#b79cf2", "#1d1032"), "blue": ("#7dbbf5", "#06192d"), "green": ("#7fd49b", "#062310"), "grey": ("#d9d9de", "#1b1b1e")}   # canvas.html NCOL
INK = {"dark": (250, 250, 250, 235), "light": (9, 9, 11, 235)}
LINE = {"dark": (255, 255, 255, 46), "light": (0, 0, 0, 40)}
ID = re.compile(r"[\w-]{1,60}")
_LOCK = threading.Lock()


# ---- descriptors: what a row shows, from the board alone ------------------------------------------------------------------------------
def kind(it):
    """pic (a library file on the board), card (any plugin's card), note, text, timeline, or None"""
    if not isinstance(it, dict): return None
    t = it.get("type")
    if not t: return "pic" if it.get("path") else None
    return t if t in ("note", "text", "timeline") else "card"


def rect(it):
    try: return notelinks.rect(it)
    except (KeyError, TypeError, ValueError, ZeroDivisionError): return None


def fit(x, y, w, h, margin=0.0, bound=None, min_w=0.0):
    """a 3:2 box around (x, y, w, h), grown by margin (a share of its larger side); kept inside bound (x, y, w, h) where it fits there,
    centred on bound where it is larger"""
    m = margin * max(w, h)
    x, y, w, h = x - m, y - m, w + 2 * m, h + 2 * m
    if w < min_w: x, w = x - (min_w - w) / 2, min_w
    if w / max(h, 1e-9) < AR: x, w = x - (h * AR - w) / 2, h * AR
    else: y, h = y - (w / AR - h) / 2, w / AR
    if bound:
        bx, by, bw, bh = bound
        x = bx + (bw - w) / 2 if w >= bw else min(max(x, bx), bx + bw - w)
        y = by + (bh - h) / 2 if h >= bh else min(max(y, by), by + bh - h)
    return x, y, w, h


def _n(v): return f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def _src(path, **q): return path + "?" + urllib.parse.urlencode({k: v if isinstance(v, str) else ",".join(map(_n, v)) for k, v in q.items()})


def _share(r, box):
    """r (x, y, w, h) as shares of box: where a mark lies on its tile"""
    return [round((r[0] - box[0]) / box[2], 4), round((r[1] - box[1]) / box[3], 4), round(r[2] / box[2], 4), round(r[3] / box[3], 4)]


def pic_tile(path): return {"src": _src("/thumb", p=path, s="320"), "k": "pic"}


def obj_tile(page, oid, it, area=None, pin=None, around=None):
    """a crop of an object's still: area (u, v, w, h shares) outlined, or the whole object with a pin (u, v) on it, or the part around
    a point (around: (u, v, width share))"""
    r = rect(it)
    if not r: return None
    W, H = r[2], r[3]
    if area:
        t = (area[0] * W, area[1] * H, area[2] * W, area[3] * H)
        box = fit(*t, margin=MARGIN, bound=(0, 0, W, H))
    elif around:
        cw = around[2] * W; t = (around[0] * W - cw / 2, around[1] * H - cw / AR / 2, cw, cw / AR)
        box = fit(*t, bound=(0, 0, W, H))
    else:
        box = fit(0, 0, W, H)
    d = {"src": _src("/feedthumb", page=page, obj=oid, box=[box[0] / W, box[1] / H, box[2] / W, box[3] / H]), "k": "crop"}
    if area: d["mark"] = {"r": _share(t, box)}
    pt = pin or (around and around[:2])
    if pt: d["mark"] = {"pin": _share((pt[0] * W, pt[1] * H, 0, 0), box)[:2]}
    return d


def region_tile(page, r, mark=None, margin=0.0, top=False):
    """the board in r (x, y, w, h board units): mark "r" outlines r itself, "pin" puts a dot at r's centre; top: r is the box's top"""
    box = fit(*r, margin=margin)
    if top: box = (box[0], r[1] - margin * max(r[2], r[3]), box[2], box[3])
    d = {"src": _src("/feedthumb", page=page, r=[round(v) for v in box]), "k": "region"}
    if mark == "r": d["mark"] = {"r": _share(r, box)}
    elif mark == "pin": d["mark"] = {"pin": _share((r[0] + r[2] / 2, r[1] + r[3] / 2, 0, 0), box)[:2]}
    return d


def linked(b, nid):
    """what a note speaks about, as the board shows it: its arrows (a group: its members) and the things it overlaps"""
    items, groups = b.get("items") or {}, b.get("groups") or {}
    n, out = items.get(nid) or {}, []
    for t in n.get("to") or []:
        out += [t] if notelinks.target(items.get(t)) else [m for m in (groups.get(t) or {}).get("members") or [] if m in items]
    nr = rect(n)
    if nr:
        for i, it in items.items():
            if i != nid and notelinks.caught(it) and (r := rect(it)) and notelinks._hit(nr, r): out.append(i)
    return list(dict.fromkeys(out))


def _union(rs):
    x0, y0 = min(r[0] for r in rs), min(r[1] for r in rs)
    return (x0, y0, max(r[0] + r[2] for r in rs) - x0, max(r[1] + r[3] for r in rs) - y0)


def of_ids(page, b, ids, previews=()):
    """(tiles, how many there are in all) for things on board b: pictures and cards themselves, a group by its members, a note by
    what it is linked to; what has no picture of its own (a note linked to nothing, a heading, a timeline, an empty group) by one
    region of the board around all of them"""
    items, groups = b.get("items") or {}, b.get("groups") or {}
    things, loose = [], []
    for i in dict.fromkeys(ids or []):
        if i in groups:
            mem = [m for m in groups[i].get("members") or [] if kind(items.get(m)) in ("pic", "card")]
            if mem: things += mem
            elif all(isinstance(groups[i].get(k), (int, float)) for k in "xywh"): loose.append(tuple(float(groups[i][k]) for k in "xywh"))
            continue
        k = kind(items.get(i))
        if k in ("pic", "card"): things.append(i)
        elif k == "note":
            got = [x for x in linked(b, i) if kind(items.get(x)) in ("pic", "card")]
            if got: things += got
            elif rect(items[i]): loose.append(rect(items[i]))
        elif k in ("text", "timeline") and rect(items[i]):
            r = rect(items[i]); loose.append((r[0], r[1], r[2], max(r[3], r[2] / AR)))   # the board under a heading: its section
    things = list(dict.fromkeys(things))[:500]
    tiles = [pic_tile(items[i]["path"]) if kind(items[i]) == "pic" else obj_tile(page, i, items[i]) for i in things[:TILES]]
    tiles = [t for t in tiles if t]
    total = len(things)
    if loose and len(tiles) < TILES: tiles.append(region_tile(page, _union(loose), margin=.08)); total += 1
    elif loose: total += 1
    if not tiles and previews:
        tiles, total = [pic_tile(p) for p in previews[:TILES]], len(previews)
    return tiles, total


def of_thread(t, b):
    """the tile of a comment thread: its area's crop, its pin on the object or the page's element, or the board where it lies"""
    page, an, area, at = t.get("page") or "main", t.get("anchor") or None, t.get("area"), t.get("at")
    items = b.get("items") or {}
    it = items.get(an["obj"]) if an else None
    if it and kind(it) in ("pic", "card"):
        if area: d = obj_tile(page, an["obj"], it, area=area)
        elif t.get("element") and at:
            vw = it.get("vw") if isinstance(it.get("vw"), (int, float)) and it["vw"] > 0 else 0
            d = obj_tile(page, an["obj"], it, around=(at[0], at[1], min(1.0, 640 / vw) if vw else .45))
        else: d = obj_tile(page, an["obj"], it, pin=at if at else None)
    elif an:   # a note, a heading, or the object gone: the board where it lies (its box when last drawn)
        r = rect(it) if it else None
        r = r or (tuple(an["r"]) if isinstance(an.get("r"), list) and len(an["r"]) == 4 else None)
        if not r: return None
        if area: d = region_tile(page, (r[0] + area[0] * r[2], r[1] + area[1] * r[3], area[2] * r[2], area[3] * r[3]), "r", MARGIN)
        else: d = region_tile(page, r, "pin" if not at else None, .15)
        if at and not area:
            d["mark"] = {"pin": _share((r[0] + at[0] * r[2], r[1] + at[1] * r[3], 0, 0), _box_of(d))[:2]}
    elif area: d = region_tile(page, tuple(area), "r", MARGIN)
    elif at: d = region_tile(page, (at[0] - FREE_PIN[0] / 2, at[1] - FREE_PIN[1] / 2, *FREE_PIN), "pin")
    else: return None
    if d and d.get("mark"): d["who"] = (t.get("by") or {}).get("person") or ""
    return d


def _box_of(d):
    q = urllib.parse.parse_qs(d["src"].split("?", 1)[1])
    return [float(v) for v in q["r"][0].split(",")]


def of_notification(n, b, thread=None):
    """(tiles, total) for one row of the bell: a comment by its thread, a note reply and agent news by their ids, else the area, else
    the pictures it named"""
    page = n.get("page") or "main"
    if thread:
        d = of_thread(thread, b)
        if d: return [d], 1
    if n.get("ids"):
        tiles, total = of_ids(page, b, n["ids"], n.get("previews") or ())
        if tiles: return tiles, total
    a = n.get("area")
    if isinstance(a, dict) and all(isinstance(a.get(k), (int, float)) for k in "xywh") and a["w"] > 0 and a["h"] > 0:
        return [region_tile(page, (a["x"], a["y"], a["w"], a["h"]), margin=.04)], 1
    pv = n.get("previews") or []
    return [pic_tile(p) for p in pv[:TILES]], len(pv)


# ---- on read: every row of /api/notifications, cached by the board's time and the thread's -----------------------------------------
_BOARDS, _MEMO = {}, {}


def _board(S, page):
    """the page's board, read again only when its file changed; ({} , 0) for a page that cannot be read"""
    try: p = S.board_path(page); mt = os.path.getmtime(p)
    except (PermissionError, OSError): return {}, 0
    got = _BOARDS.get(page)
    if not got or got[0] != mt:
        try: got = (mt, S.load_board(page))
        except (OSError, ValueError, PermissionError): return {}, 0
        _BOARDS[page] = got
    return got[1], got[0]


def _thread(page, tid):
    import comments
    try: return comments._read(comments._file(comments.COM, page, tid))
    except (OSError, ValueError, AttributeError): return None


def fill(S, L):
    """the rows with their tiles: "pv" (4 at most) and "pvn" (how many in all); a stored "pv" is kept, its crops and regions get the
    board's time (v=) so a changed board draws them again"""
    out = []
    for n in L:
        n = dict(n); page = n.get("page") or "main"
        b, mt = _board(S, page)
        th = _thread(page, n["thread"]) if n.get("kind") == "comment" and n.get("thread") else None
        if "pv" not in n:
            key = (n.get("id"), mt, (th or {}).get("updated"))
            if key not in _MEMO:
                if len(_MEMO) > 2000: _MEMO.clear()
                _MEMO[key] = of_notification(n, b, th) if b or th or n.get("previews") else ([], 0)
            n["pv"], n["pvn"] = _MEMO[key]
        n["pv"] = [dict(d, src=d["src"] + f"&v={int(mt)}") if d.get("k") != "pic" else d for d in n["pv"] or []]
        out.append(n)
    return out


# ---- drawing: GET /feedthumb ---------------------------------------------------------------------------------------------------------
def _img(full):
    from PIL import Image
    im = Image.open(full)
    if getattr(im, "draft", None) and im.format == "JPEG": im.draft("RGB", (2560, 2560))
    im.load()
    return im.convert("RGBA")


def source(S, it, oid, need):
    """(key, load) of the picture the board shows in a thing, at need px across its whole width: a picture's file (the original when
    more than 1280 px are needed), a card's still (an HTML card's at its viewport, an image frame's render, a 3D card's poster); and
    the share of it the board shows (a picture's crop). None when it has none"""
    size = 320 if need <= 320 else 1280 if need <= 1280 else 2560
    t, crop = it.get("type"), None
    if not t or t == "imgframe" or (t not in ("model3d",) and it.get("path") and not it.get("src")):
        rel = it.get("path") if not t else it.get("render") or it.get("path")
        if not rel: return None
        rel = S.resolve(rel); full = S.safe(rel); crop = it.get("crop") if not t else None
        mt = os.path.getmtime(full)
        if size == 2560 and S.kind_of(rel) == "image": return (rel, mt, "orig"), lambda: _img(full), crop
        size = min(size, 1280)
        return (rel, mt, size), lambda: _img(S.thumb(rel, size)), crop
    if t == "model3d":
        scene = it.get("scene") or ""
        if not scene: return None
        d = scene.rsplit("/", 1)[0] + "/.posters" if "/" in scene else ".posters"
        try:
            full_d = S.safe(d)
            names = [x for x in os.listdir(full_d) if x.startswith(oid + "-") and x.endswith((".jpg", ".png"))]
        except (OSError, PermissionError): return None
        if not names: return None
        best = max(names, key=lambda x: os.path.getmtime(os.path.join(full_d, x)))
        full = os.path.join(full_d, best)
        return (d + "/" + best, os.path.getmtime(full)), lambda: _img(full), None
    rel = it.get("src") or it.get("path")
    if not isinstance(rel, str) or not rel: return None
    rel = S.resolve(rel); full = S.safe(rel); view = None
    vw = it.get("vw")
    if isinstance(vw, (int, float)) and vw > 0 and it.get("w") and it.get("h"):
        view = S.view_of(rel, round(vw), max(1, round(vw * it["h"] / it["w"])))
    size = min(size, 2560 if view else 1280)
    return (rel, os.path.getmtime(full), size, view), lambda: _img(S.thumb(rel, size, 1, view)), None


def paint(dst, im, crop, box, at, size):
    """the part box (u, v, w, h shares of the thing, may stick out) of the thing's picture im (crop: the share of im the thing shows)
    painted into dst at (x, y) as size (w, h) px"""
    from PIL import Image
    c = crop if isinstance(crop, (list, tuple)) and len(crop) == 4 else (0, 0, 1, 1)
    u0, v0, u1, v1 = max(0.0, box[0]), max(0.0, box[1]), min(1.0, box[0] + box[2]), min(1.0, box[1] + box[3])
    if u1 <= u0 or v1 <= v0: return
    iw, ih = im.size
    px = lambda u: (c[0] + u * (c[2] - c[0])) * iw
    py = lambda v: (c[1] + v * (c[3] - c[1])) * ih
    x0, y0 = at[0] + (u0 - box[0]) / box[2] * size[0], at[1] + (v0 - box[1]) / box[3] * size[1]
    w, h = (u1 - u0) / box[2] * size[0], (v1 - v0) / box[3] * size[1]
    if w < 1 or h < 1: return
    part = im.crop((int(px(u0)), int(py(v0)), max(int(px(u0)) + 1, round(px(u1))), max(int(py(v0)) + 1, round(py(v1)))))
    part = part.resize((max(1, round(w)), max(1, round(h))), Image.LANCZOS)
    dst.alpha_composite(part, (max(0, round(x0)), max(0, round(y0))))


_FONT = {}


def font(px):
    from PIL import ImageFont
    px = max(6, min(64, int(px)))
    if px not in _FONT:
        here = os.path.dirname(os.path.abspath(__file__))
        for f in ("/System/Library/Fonts/Helvetica.ttc", os.path.join(here, "ui/fonts/geist-latin.woff2")):
            try: _FONT[px] = ImageFont.truetype(f, px); break
            except OSError: continue
        else: _FONT[px] = ImageFont.load_default()
    return _FONT[px]


def _rgb(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _words(draw, text, x, y, w, h, px, ink):
    """text in the box, line by line while it fits; too small to read: grey bars where the lines are"""
    lines = [ln.strip().lstrip("#").strip() for ln in str(text or "").split("\n") if ln.strip()]
    if px < 6:
        for k in range(min(len(lines), int(h // max(2, px * 1.6)))):
            draw.rectangle((x, y + k * px * 1.6, x + w * (.85 if k % 2 else .6), y + k * px * 1.6 + max(1, px * .7)), fill=ink[:3] + (90,))
        return
    f, yy = font(px), y
    for ln in lines:
        if yy + px > y + h: break
        while ln and draw.textlength(ln, font=f) > w: ln = ln[:-1]
        draw.text((x, yy), ln, font=f, fill=ink); yy += px * 1.3


def draw_region(S, b, r, th):
    """the board in r (x, y, w, h board units) as OUT px with a see-through background: group frames, pictures and cards from their
    thumbnails, notes as their colour with their words, headings in the theme's ink"""
    from PIL import Image, ImageDraw
    W, H = OUT
    s = W / r[2]
    out = Image.new("RGBA", OUT, (0, 0, 0, 0))
    draw = ImageDraw.Draw(out)
    for g in (b.get("groups") or {}).values():
        if not all(isinstance(g.get(k), (int, float)) for k in "xywh"): continue
        gx, gy, gw, gh = (g["x"] - r[0]) * s, (g["y"] - r[1]) * s, g["w"] * s, g["h"] * s
        if gx > W or gy > H or gx + gw < 0 or gy + gh < 0: continue
        draw.rounded_rectangle((gx, gy, gx + gw, gy + gh), radius=max(2, 12 * s), outline=LINE[th], width=1)
        if g.get("title") and 14 * s >= 6: _words(draw, g["title"], gx + 6 * s, gy - 22 * s, gw, 22 * s, 14 * s, INK[th])
    drawn = 0
    for oid, it in (b.get("items") or {}).items():
        k, rr = kind(it), rect(it) if isinstance(it, dict) else None
        if not k or not rr: continue
        x, y, w, h = (rr[0] - r[0]) * s, (rr[1] - r[1]) * s, rr[2] * s, rr[3] * s
        if x > W or y > H or x + w < 0 or y + h < 0 or w < 1.5: continue
        if k == "note":
            bg, ink = NCOL.get(it.get("color") or "yellow", NCOL["yellow"])
            draw.rounded_rectangle((x, y, x + w, y + h), radius=max(1, 6 * s), fill=_rgb(bg) + (255,))
            fs = float(it.get("fs") or 16) * s
            _words(draw, it.get("text"), x + 10 * s, y + 10 * s, w - 20 * s, h - 20 * s, fs, _rgb(ink) + (255,))
        elif k == "text":
            _words(draw, it.get("text"), x, y, w, h, float(it.get("fs") or 16) * s, INK[th])
        elif k == "timeline":
            draw.line((x, y + h / 2, x + w, y + h / 2), fill=LINE[th][:3] + (120,), width=1)
        else:
            box = ((r[0] - rr[0]) / rr[2], (r[1] - rr[1]) / rr[3], r[2] / rr[2], r[3] / rr[3])   # the tile in the thing's shares
            got = None
            if drawn < MAX_DRAWN:
                try: got = source(S, it, oid, w)
                except (OSError, PermissionError, ValueError): got = None
            if got:
                try: paint(out, got[1](), got[2], box, (0, 0), OUT); drawn += 1; continue
                except Exception: pass
            draw.rectangle((max(0, x), max(0, y), min(W, x + w), min(H, y + h)), fill=LINE[th][:3] + (60,))
    return out


def _cached(key, make):
    """the file of a tile in the thumbnail cache by its key: made once (a temporary name, then in place), touched when handed out"""
    import thumbcache
    name = "feed." + hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:24] + ".webp"
    out = os.path.join(thumbcache.THUMBS, name)
    if not os.path.exists(out):
        im = make()
        if im is None: return None
        os.makedirs(thumbcache.THUMBS, exist_ok=True)
        tmp = out + f".{threading.get_ident()}.tmp"
        im.save(tmp, "WEBP", quality=82, alpha_quality=90, method=4)
        os.replace(tmp, out)
    return thumbcache.used(out)


def _nums(v, n, lo, hi):
    try: a = [float(x) for x in str(v).split(",")]
    except ValueError: return None
    return a if len(a) == n and all(lo <= x <= hi for x in a) else None


def http(S, q):
    """GET /feedthumb?page=&obj=&box=u,v,w,h (a crop of one thing's picture) | ?page=&r=x,y,w,h (the board there) [&th=dark|light]:
    the file of the tile, or None (404)"""
    one = lambda k: (q.get(k) or [""])[0]
    page, th = one("page") or "main", "light" if one("th") == "light" else "dark"
    b, mt = _board(S, page)
    if not b: return None
    if one("obj"):
        oid, box = one("obj"), _nums(one("box"), 4, -50, 50)
        it = (b.get("items") or {}).get(oid)
        if not ID.fullmatch(oid) or not box or box[2] <= 0 or box[3] <= 0 or kind(it) not in ("pic", "card"): return None
        need = OUT[0] / box[2]
        got = source(S, it, oid, need)
        if not got: return None
        key, load, crop = got

        def make():
            from PIL import Image
            out = Image.new("RGBA", OUT, (0, 0, 0, 0))
            paint(out, load(), crop, box, (0, 0), OUT)
            return out
        return _cached(["obj", key, crop, [round(v, 4) for v in box], OUT], make)
    r = _nums(one("r"), 4, -1e7, 1e7)
    if not r or not 0 < r[2] <= 1e6 or not 0 < r[3] <= 1e6: return None
    inside = []
    for oid, it in (b.get("items") or {}).items():
        rr = rect(it) if isinstance(it, dict) else None
        if rr and rr[0] < r[0] + r[2] and rr[0] + rr[2] > r[0] and rr[1] < r[1] + r[3] and rr[1] + rr[3] > r[1]:
            inside.append([oid, [round(v, 2) for v in rr], it.get("path") or it.get("src") or it.get("scene") or it.get("render"), it.get("crop"),
                           it.get("text"), it.get("color"), it.get("v") or it.get("rv")])
    groups = [[g.get(k) for k in ("x", "y", "w", "h", "title")] for g in (b.get("groups") or {}).values() if isinstance(g, dict)]
    for e in inside:
        try: e.append(os.path.getmtime(S.safe(S.resolve(e[2])))) if e[2] else None
        except (OSError, PermissionError): pass
    return _cached(["region", page, r, th, inside, groups, OUT], lambda: draw_region(S, b, r, th))
