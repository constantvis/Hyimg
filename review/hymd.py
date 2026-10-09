"""hy.py md: a page of the board as Markdown, read only, made when asked and never stored (owner 2026-10-08: the structure on the board
must be explicit, so an agent reads it without guessing). One pass over the page:

  # «Page»                     the page's title
  ## Heading / ### Heading     a heading by its size: a section (letters of 160 and more, LAYOUT.md) or a caption;
                               a text document's body under its title, its own headings below that level (textdocs.py)
  ## ▣ Group «Title» [id]      a group is a section; a group whose frame lies inside another's is a section under it
  > a note's text [id]         a note as a quote, in its group or where it stands; its arrows after it as → lines (a reply too)
  ▦ grid C × R [id]            a grid as a Markdown table (its heading row as the table's titles)
  Свободно:                    things in no grid, in gravity order: rows top to bottom, left to right (layout.py's rows)
  - Таймлайн «label»: dots     a timeline with its dots

Writing back: `hy.py md apply FILE` (mdapply.py); the first line of the view names the version it shows, comments and drawings come
after their [id]s and in a list at the end (mdmarks.py)."""
import sys

import grids
import notelinks
import textdocs

SECTION_FS = 160      # a heading with letters this tall heads a section (layout.py SECTION_FS × 320)
ROW_OVERLAP = 0.5     # a thing joins a row when half of the shorter one shares the row's height band (layout.py)
QUOTE = 600           # a note's text is quoted up to this many characters


def first(t): return (t or "").strip().split("\n")[0].lstrip("#").strip()


def box(it):
    try: return notelinks.rect(it)
    except (KeyError, TypeError, ValueError, ZeroDivisionError): return None


def gravity(entries):
    """entries [(rect, payload)] in reading order: rows by a shared height band, top to bottom, each row left to right"""
    rows = []
    for r, p in sorted(entries, key=lambda e: (e[0][1], e[0][0])):
        y0, y1 = r[1], r[1] + r[3]
        for row in rows:
            b0, b1 = max(row["band"][0], y0), min(row["band"][1], y1)
            if b1 - b0 >= ROW_OVERLAP * min(y1 - y0, row["band"][1] - row["band"][0]) and b1 > b0:
                row["e"].append((r, p)); row["band"] = (b0, b1); break
        else:
            rows.append({"e": [(r, p)], "band": (y0, y1)})
    return [p for row in rows for _r, p in sorted(row["e"], key=lambda e: e[0][0])]


def render(b, title="", page=""):
    I, G = b.get("items") or {}, b.get("groups") or {}
    in_group = {m: gid for gid, g in G.items() for m in g.get("members", [])}
    in_grid = {m: gid for gid, g in grids.table(b).items() for m in g.get("members", []) if m in I}
    grid_group = {gid: grids.group_of(b, gid) for gid in grids.table(b)}
    gbox = lambda g: (g["x"], g["y"], g["w"], g["h"])

    def parent(gid):   # the smallest other frame that holds this one
        g, best = G[gid], None
        for k, o in G.items():
            if k != gid and o["x"] <= g["x"] and o["y"] <= g["y"] and o["x"] + o["w"] >= g["x"] + g["w"] and o["y"] + o["h"] >= g["y"] + g["h"]:
                bigger = (o["w"] * o["h"], k) > (g["w"] * g["h"], gid)   # two equal frames: the one with the larger id holds the other, never a loop
                if bigger and (best is None or (o["w"] * o["h"], k) < (G[best]["w"] * G[best]["h"], best)): best = k
        return best
    up = {gid: parent(gid) for gid in G}

    def entries(gid):
        """what stands directly in a group (gid) or on the page (None): its things, its grids, the groups under it"""
        out = [(gbox(G[k]), ("group", k)) for k in G if up[k] == gid]
        out += [(tuple(grids.bbox(b, k).values()), ("grid", k)) for k in grids.table(b) if grid_group[k] == gid]
        for i, it in I.items():
            if in_group.get(i) != gid or i in in_grid: continue
            r = box(it)
            if r: out.append((r, ("item", i)))
        return gravity(out)

    L = [f"# «{title or page}»" + (f" ({page})" if page and title and title != page else ""), ""]

    def note(i):
        it = I[i]; text = (it.get("text") or "").strip()
        text = text[:QUOTE] + ("…" if len(text) > QUOTE else "")
        lines = text.split("\n") or [""]
        L.extend(f"> {ln}".rstrip() for ln in lines[:-1]); L.append(f"> {lines[-1]} [{i}]".replace(">  [", "> ["))
        to = [t for t in it.get("to") or [] if t in I or t in G]
        for t in to:
            if I.get(t, {}).get("type") == "note": L.append(f"→ ответ на «{first(I[t].get('text'))[:50]}» [{t}]")
            elif t in G: L.append(f"→ группа «{first(G[t].get('title'))}» [{t}]")
            else: L.append(f"→ {grids.cell(b, t)}")
        L.append("")

    def emit(gid, depth):
        free = []
        def flush():
            if free: L.extend(["Свободно:", *free, ""]); free.clear()
        for kind, k in entries(gid):
            it = I.get(k, {})
            if kind == "item" and it.get("type") not in ("note", "text", "timeline"):
                free.append(f"- {grids.cell(b, k)}"); continue
            if it.get("type") == "timeline":
                dots = " · ".join(first(p.get("text")) or "·" for p in sorted(it.get("points", []), key=lambda p: p.get("t", 0)))
                free.append(f"- Таймлайн «{first(it.get('label')) or 'таймлайн'}» [{k}]: {dots}"); continue
            flush()
            if kind == "group":
                L.extend([f"{'#' * min(6, 2 + depth)} ▣ Группа «{first(G[k].get('title')) or 'без названия'}» [{k}]", ""]); emit(k, depth + 1)
            elif kind == "grid":
                rws, cols = grids.grid_rows(b, k)
                L.extend([f"▦ сетка {cols} × {len(rws)} [{k}]", *grids.md_table(b, k, numbers=False), ""])
            elif it.get("type") == "note": note(k)
            elif it.get("type") == "text":
                lvl = 2 if (it.get("fs") or 0) >= SECTION_FS and depth == 0 else 3 + depth
                L.extend([f"{'#' * min(6, lvl)} {first(it.get('text'))} [{k}]", *textdocs.body_md(it.get("text"), min(6, lvl)), ""])   # a document
        flush()

    emit(None, 0)
    while L and not L[-1]: L.pop()
    return "\n".join(L) + "\n"


def main(args, page, api, hy=None):
    """hy.py md [page]: the page by its id or title (the owner's open page when none); md apply FILE: an edit back (mdapply.py)"""
    if args and args[0] == "apply": import mdapply; return mdapply.main(args[1:], page, hy)
    want = next((a for a in args if not a.startswith("--")), None) or page
    try: pages = api("/api/pages")[1].get("pages", [])
    except Exception: pages = []
    if want is None:
        try: want = (api("/api/live")[1].get("canvas") or {}).get("page") or "main"
        except Exception: want = "main"
    pg = next((p for p in pages if p["id"] == want), None) or next((p for p in pages if (p.get("title") or "").lower() == want.lower()), None)
    pid = pg["id"] if pg else want
    code, b = api(f"/api/board?name={pid}")
    if code != 200 or not isinstance(b, dict): raise SystemExit(f"нет страницы «{want}»: {code}")
    import mdapply, mdmarks   # the version it shows (a base for md apply); comments and drawings on what it lists
    sys.stdout.write(mdapply.stamp(b, pid) + mdmarks.add(render(b, (pg or {}).get("title", pid), pid), b, pid, api))
