# Board "gravity" (layout-v1, 2026-09-30): what the owner's spatial arrangement on the canvas means, without looking at the picture.
# Pictures on one line are a row; a much wider gap inside a row splits it into series; a much wider empty band splits a group into
# blocks; a big title heads the groups under it. "Much wider" is always compared with the usual gap in the same place, never a pixel
# number. Explicit things win: a group frame (members[]) is never crossed, sticky notes stay as they are.
# Derived only: reads boards/<page>.json, writes boards/<page>.layout.json (cached by revision), nothing goes into picture json.
# The rules are open to question (owner): disagreements and their fixes go to LAYOUT.md, the parameters are the constants below.
#   python3 _review/layout.py [page]            outline for an agent
#   python3 _review/layout.py [page] --json     the layout file
#   python3 _review/layout.py [page] --draw "Title" [out.jpg]   one group with its rows and blocks drawn, to check by eye
import hashlib, json, os, statistics, sys

VERSION = "layout-v1"
UNIT = 320          # picture width on the board: every length is measured in pictures
ROW_OVERLAP = 0.5   # a picture joins a row when half of it (of the shorter one) shares the row's height band
CUT = 2.0           # a gap this many times wider than the usual one splits
UNSURE = 1.5        # from here up to CUT the split is reported as "unsure"
GUTTER = 0.075      # the usual gap when a place has too few gaps to tell (the canvas "tidy" gutter, 24 / 320)
TITLE_REACH = 2.0   # a small title belongs to what starts within this many pictures below it
SECTION_FS = 0.5    # a title whose letters are at least half a picture tall heads a section; smaller ones are captions

from config import HERE, W, BOARDS

CODE = hashlib.sha1(open(os.path.abspath(__file__), "rb").read()).hexdigest()[:8]   # any change of rules or parameters rebuilds the cache


def rect(it):   # displayed rectangle, crop-aware like canvas.html itemH()
    c = it.get("crop") or [0, 0, 1, 1]
    return (it["x"], it["y"], it["w"], it["w"] * ((c[3] - c[1]) / (it.get("ar") or 1)) / (c[2] - c[0]))


def bbox(rs):
    x0 = min(r[0] for r in rs); y0 = min(r[1] for r in rs)
    return (x0, y0, max(r[0] + r[2] for r in rs) - x0, max(r[1] + r[3] for r in rs) - y0)


def nid(*parts):
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:8]


def usual(gaps, skip=None):   # the usual gap here: median of the other positive gaps, or the board gutter
    g = [x for i, x in enumerate(gaps) if i != skip and x > 0]
    return max(statistics.median(g), GUTTER) if len(g) >= 2 else GUTTER


def rows(ids, R):
    """pictures on one line; the band is the part of the height all members share, so a row cannot drift"""
    out = []
    for i in sorted(ids, key=lambda i: (R[i][1], R[i][0], i)):
        y0, y1 = R[i][1], R[i][1] + R[i][3]
        for row in out:
            b0, b1 = max(row["band"][0], y0), min(row["band"][1], y1)
            if b1 - b0 >= ROW_OVERLAP * min(y1 - y0, row["band"][1] - row["band"][0]):
                row["ids"].append(i); row["band"] = (b0, b1); break
        else:
            out.append({"ids": [i], "band": (y0, y1)})
    return [sorted(r["ids"], key=lambda i: (R[i][0], i)) for r in out]


def segments(row, R):
    """a row split where a gap is much wider than the usual gap of that row: several series on one line"""
    gaps = [(R[b][0] - R[a][0] - R[a][2]) / UNIT for a, b in zip(row, row[1:])]
    out, cur, unsure = [], [row[0]], []
    for k, (b, g) in enumerate(zip(row[1:], gaps)):
        r = g / usual(gaps, k)
        if r >= CUT: out.append(cur); cur = [b]; continue
        if r >= UNSURE: unsure.append(f"промежуток в ряду в {r:.1f} раза шире обычного")
        cur.append(b)
    return out + [cur], unsure


def corridors(atoms, axis):
    """empty bands across the whole set along one axis (0 = vertical cut, 1 = horizontal cut): (width, position, before, after)"""
    iv = sorted((a["box"][axis], a["box"][axis] + a["box"][axis + 2], n) for n, a in enumerate(atoms))
    out, end, left = [], iv[0][1], [iv[0][2]]
    for s, e, n in iv[1:]:
        if s > end: out.append(((s - end) / UNIT, (s + end) / 2, list(left)))
        end = max(end, e); left.append(n)
    return [(w, pos, set(l)) for w, pos, l in out]


def blocks(atoms, why):
    """recursive cut at the empty band that stands out most against the usual bands of the same axis"""
    if len(atoms) < 2: return [atoms]
    best = None
    for axis in (1, 0):   # horizontal bands first: rows stacked into blocks are the common case
        cs = corridors(atoms, axis)
        if not cs: continue
        ws = [c[0] for c in cs]
        k = max(range(len(cs)), key=lambda i: (ws[i], -i))
        r = ws[k] / usual(ws, k)
        if best is None or r > best[0]: best = (r, cs[k][2])
    if best is None or best[0] < CUT:
        if best and best[0] >= UNSURE: why.append(f"пустая полоса в {best[0]:.1f} раза шире обычной, оставлено одним блоком")
        return [atoms]
    a = [x for n, x in enumerate(atoms) if n in best[1]]; b = [x for n, x in enumerate(atoms) if n not in best[1]]
    return blocks(a, why) + blocks(b, why)


def build(board, page):
    items, groups = board.get("items", {}), board.get("groups", {})
    R = {i: rect(v) for i, v in items.items() if v.get("path")}
    owner = {m: g for g, gv in groups.items() for m in gv.get("members", []) if m in R}
    scopes = [(g, gv.get("title", "").strip(), [m for m in gv.get("members", []) if m in R]) for g, gv in groups.items()]
    loose = sorted(i for i in R if i not in owner)
    if loose: scopes.append((None, "вне групп", loose))
    notes = {}   # picture path -> first lines of the sticky notes that touch it (the notes/ files)
    nd = os.path.join(W, "notes")
    for f in sorted(os.listdir(nd)) if os.path.isdir(nd) else []:
        if f.startswith(page + "__") and f.endswith(".json"):
            d = json.load(open(os.path.join(nd, f), encoding="utf-8"))
            for p in d.get("pictures", []): notes.setdefault(p["path"], []).append(d["text"].strip().splitlines()[0][:60])
    out = []
    for gid, title, ids in scopes:
        if not ids: continue
        atoms, why = [], []
        for row in rows(ids, R):
            segs, u = segments(row, R); why += u
            for s in segs: atoms.append({"ids": s, "box": bbox([R[i] for i in s])})
        bl = blocks(sorted(atoms, key=lambda a: (a["box"][1], a["box"][0])), why)
        node = {"id": gid or nid(page, "loose"), "kind": "group" if gid else "loose", "title": title,
                "box": [round(v) for v in bbox([R[i] for i in ids])], "status": "explicit" if gid else "inferred", "blocks": []}
        for b in sorted(bl, key=lambda b: (min(a["box"][1] for a in b), min(a["box"][0] for a in b))):
            b = sorted(b, key=lambda a: (round(a["box"][1] / UNIT), a["box"][0]))
            pics = [i for a in b for i in a["ids"]]
            node["blocks"].append({"id": nid(page, gid, "block", *sorted(pics)), "box": [round(v) for v in bbox([a["box"] for a in b])],
                                   "rows": [{"id": nid(page, gid, "row", *sorted(a["ids"])), "items": a["ids"]} for a in b]})
        node["unsure"] = why
        node["notes"] = sorted({t for i in ids for t in notes.get(items[i]["path"], [])})
        out.append(node)
    # titles: a big one heads a section (the groups under it and to its right, up to the next big title), a small one names what is right below it
    texts = [(k, v) for k, v in items.items() if v.get("type") == "text" and v.get("text", "").strip()]
    big = [(k, v) for k, v in texts if v.get("fs", 16) >= SECTION_FS * UNIT]
    sections = {k: {"id": k, "title": v["text"].strip(), "status": "inferred", "groups": []} for k, v in big}
    for n in out:
        x, y = n["box"][0], n["box"][1]
        above = [(k, v) for k, v in big if v["y"] + v.get("h", 0) <= y + UNIT and v["x"] <= x + UNIT]
        if above:
            k, v = min(above, key=lambda kv: ((x - kv[1]["x"]) / UNIT + (y - kv[1]["y"] - kv[1].get("h", 0)) / UNIT / 4, kv[0]))
            sections[k]["groups"].append(n["id"])
            if x > v["x"] + v.get("w", 0) + 2 * UNIT:   # far to the right of its title: probably a column without a title of its own
                sections[k].setdefault("far", []).append(n["id"])
    for k, v in texts:
        if (k, v) in big: continue
        tb = v["y"] + v.get("h", 0)
        near = [n for n in out if 0 <= (n["box"][1] - tb) / UNIT <= TITLE_REACH and n["box"][0] - UNIT <= v["x"] <= n["box"][0] + n["box"][2]]
        if near: min(near, key=lambda n: (n["box"][1] - tb, n["id"])).setdefault("captions", []).append(v["text"].strip())
    return {"board": page, "revision": board.get("revision"), "algorithm": VERSION, "code": CODE,
            "params": {"version_note": "open to question, see LAYOUT.md", "unit": UNIT, "row_overlap": ROW_OVERLAP, "cut": CUT, "unsure": UNSURE, "gutter": GUTTER, "title_reach": TITLE_REACH, "section_fs": SECTION_FS},
            "sections": [s for s in sections.values()], "groups": out}


def load(page):
    bp = os.path.join(BOARDS, page + ".json"); lp = os.path.join(BOARDS, page + ".layout.json")
    board = json.load(open(bp, encoding="utf-8"))
    try:
        L = json.load(open(lp, encoding="utf-8"))
        if L.get("revision") == board.get("revision") and L.get("code") == CODE: return L, board
    except (OSError, ValueError): pass
    L = build(board, page); tmp = lp + ".tmp"
    json.dump(L, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, lp)
    return L, board


def outline(L, board):
    items = board["items"]
    name = lambda i: items[i]["path"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
    def folders(ids):
        c = {}
        for i in ids: f = items[i]["path"].rsplit("/", 1)[0].replace("/cells", "").split("/")[-1]; c[f] = c.get(f, 0) + 1
        return ", ".join(f"{f}×{n}" for f, n in sorted(c.items(), key=lambda x: -x[1])[:2])
    by = {n["id"]: n for n in L["groups"]}; shown = set(); lines = [f"Доска {L['board']}, ревизия {L['revision']}, {L['algorithm']}"]
    def group(n, pad):
        total = sum(len(r["items"]) for b in n["blocks"] for r in b["rows"])
        lines.append(f"{pad}{'Группа' if n['kind'] == 'group' else 'Вне групп'} «{n['title'].splitlines()[0] if n['title'] else ''}», {total} кадров" + (f" · подпись: {'; '.join(n['captions'])}" if n.get("captions") else ""))
        for k, b in enumerate(n["blocks"], 1):
            rs = " + ".join(f"ряд {len(r['items'])}" if len(r["items"]) > 1 else "1 кадр" for r in b["rows"])
            ids = [i for r in b["rows"] for i in r["items"]]
            lines.append(f"{pad}  блок {k}: {rs}  ({folders(ids)})" + (f"  {name(ids[0])}…" if len(ids) <= 3 else ""))
        for u in n["unsure"]: lines.append(f"{pad}  ? {u}")
        for t in n["notes"]: lines.append(f"{pad}  заметка: {t}")
    for s in sorted(L["sections"], key=lambda s: (-len(s["groups"]), s["title"])):
        if not s["groups"]: continue
        lines.append(f"\nРаздел «{s['title']}»")
        if s.get("far"): lines.append("  ? без своего заголовка, отнесены сюда как ближайшие справа: " + ", ".join(f"«{by[g]['title'].splitlines()[0].strip()}»" for g in s["far"]))
        for g in s["groups"]: group(by[g], "  "); shown.add(g)
    rest = [n for n in L["groups"] if n["id"] not in shown]
    if rest: lines.append("\nБез раздела")
    for n in rest: group(n, "  ")
    return "\n".join(lines)


def draw(L, board, title, out):
    from PIL import Image, ImageDraw
    n = next(n for n in L["groups"] if n["title"].startswith(title))
    items = board["items"]; x0, y0, w, h = n["box"]; s = min(1600 / w, 1200 / h)
    im = Image.new("RGB", (int(w * s) + 40, int(h * s) + 40), (24, 24, 26)); d = ImageDraw.Draw(im)
    P = lambda x, y: (int((x - x0) * s) + 20, int((y - y0) * s) + 20)
    for b in n["blocks"]:
        for r in b["rows"]:
            for i in r["items"]:
                rx, ry, rw, rh = rect(items[i])
                try:
                    t = Image.open(os.path.join(W, items[i]["path"])).convert("RGB"); t.thumbnail((int(rw * s) + 1, int(rh * s) + 1)); im.paste(t, P(rx, ry))
                except OSError: pass
            rx, ry, rw, rh = bbox([rect(items[i]) for i in r["items"]]); d.rectangle([P(rx - 6, ry - 6), P(rx + rw + 6, ry + rh + 6)], outline=(80, 170, 230), width=2)
        bx, by, bw, bh = b["box"]; d.rectangle([P(bx - 20, by - 20), P(bx + bw + 20, by + bh + 20)], outline=(244, 196, 48), width=3)
    im.save(out, quality=85); print(out)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:]]
    page = a[0] if a and not a[0].startswith("--") else "main"
    L, board = load(page)
    if "--json" in a: print(json.dumps(L, ensure_ascii=False, indent=1))
    elif "--draw" in a:
        k = a.index("--draw"); draw(L, board, a[k + 1], a[k + 2] if len(a) > k + 2 else f"/tmp/layout-{nid(a[k + 1])}.jpg")
    else: print(outline(L, board))
