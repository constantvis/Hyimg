"""Arrows between anything on the board (owner 2026-10-09 on the page «Agent layouts», section 4 Structures, and the «Board structure»
card «Arrows between anything»: «реализуй это»; the recommendation st6 «A, then C»: arrows from any object now, Mermaid ↔ real objects
next, a Mermaid studio never). A note's arrow says what the note is about and lives in the note's "to"; a connector says how two things
relate, between any two of them: a picture, a card, a heading, a group, a note, a timeline.

  board["links"][<id>] = {"from": id, "to": id, "label": "brief for"?, "style": "dashed" | "dotted"?, "color": "blue"?}

from and to are ids of items or groups on the same page. No label, solid and grey are the defaults and are not written. The legend of
the concept (st1): solid «is», dashed «like», dotted «maybe», blue «picked». A pair has one connector each way. A connector whose end
left the page goes with it (prune: every hy.py do, every merge, every save of the board page). Drawn by ui/connectors.js as a note's
arrow is (a soft curve from the side facing the other end, under the cards it crosses, a × under the pointer removes it).

Here: the record, the hy.py do commands (connect, disconnect, structure), what map, find and md show, Mermaid out (`hy.py mermaid`,
`hy.py map --graph`) and in (`hy.py structure flow.mmd near=…`: nodes found by `%% hyimg: key = <id>` or by name, the rest new groups).
hook() wires it into hy.py with one line; nothing here reads the board's files."""
import random
import re
import shlex
import string

import grids
import notelinks

STYLES = ("solid", "dashed", "dotted")
COLORS = ("grey", "blue")
WORD = {"dashed": "пунктир", "dotted": "точки", "blue": "синяя"}
NODE = (640, 400)   # a new node of a structure: an empty group frame, two cards wide


def table(b): return b.get("links") or {}
def uid(): return "c" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(7))
def there(b, i): return i in (b.get("items") or {}) or i in (b.get("groups") or {})


def prune(b):
    """connectors whose end is gone from the page (or that point at themselves) go; an empty map goes too. Returns how many went"""
    L = table(b); gone = [k for k, c in L.items() if not isinstance(c, dict) or c.get("from") == c.get("to")
                          or not there(b, c.get("from")) or not there(b, c.get("to"))]
    for k in gone: del L[k]
    if "links" in b and not b["links"]: del b["links"]
    return len(gone)


def pair(b, a, z): return next((k for k, c in table(b).items() if c.get("from") == a and c.get("to") == z), None)


def put(b, a, z, label=None, style=None, color=None):
    """a connector a → z (the same pair again: its label, style and colour change). Returns (id, new)"""
    if a == z: raise SystemExit("стрелка из вещи в нее же не бывает")
    for e in (a, z):
        if not there(b, e): raise SystemExit(f"на странице нет {e}")
    if style is not None and style not in STYLES: raise SystemExit(f"style: {', '.join(STYLES)}, не «{style}»")
    if color is not None and color not in COLORS: raise SystemExit(f"color: {', '.join(COLORS)}, не «{color}»")
    cid = pair(b, a, z); new = cid is None
    if new: cid = uid(); b.setdefault("links", {})[cid] = {"from": a, "to": z}
    c = b["links"][cid]
    for k, v, empty in (("label", label, ""), ("style", style, "solid"), ("color", color, "grey")):
        if v is None: continue
        if v == empty: c.pop(k, None)
        else: c[k] = v
    return cid, new


# ---- names ------------------------------------------------------------------------------------------------------------------------
def name(b, i):
    """what the owner sees: a group's title, a note's first line, a heading's text, a picture's file name, a card's kind and file"""
    I, G = b.get("items") or {}, b.get("groups") or {}
    if i in G: return f"группа «{notelinks.first_line(G[i].get('title')) or 'группа'}»"
    it = I.get(i) or {}
    t = it.get("type")
    if t == "note": return f"заметка «{notelinks.first_line(it.get('text'))[:40]}»"
    if t == "timeline": return f"таймлайн «{notelinks.first_line(it.get('label')) or 'таймлайн'}»"
    return grids.name(b, i)


def short(b, i):
    """the bare words of a thing, for a Mermaid node"""
    I, G = b.get("items") or {}, b.get("groups") or {}
    if i in G: return notelinks.first_line(G[i].get("title")) or "группа"
    it = I.get(i) or {}
    if it.get("type") in ("note", "text"): return notelinks.first_line(it.get("text"))[:60] or it["type"]
    return grids.name(b, i).strip("«»")


def how(c):
    bits = [f"«{c['label']}»"] if c.get("label") else []
    bits += [WORD[c[k]] for k in ("style", "color") if c.get(k) in WORD]
    return (" · " + ", ".join(bits)) if bits else ""


def line(b, cid):
    c = table(b)[cid]; return f"↦ {name(b, c['from'])} → {name(b, c['to'])}{how(c)} [{cid}]"


def of(b, ids):
    """the connectors touching any of these ids"""
    S = set(ids); return [k for k, c in table(b).items() if c.get("from") in S or c.get("to") in S]


def inside(b, gid):
    """a group with what lies in its frame: its members, the groups whose frames it holds and theirs"""
    G = b.get("groups") or {}; g = G[gid]; out = {gid, *g.get("members", [])}
    for k, o in G.items():
        if k != gid and g["x"] <= o["x"] and g["y"] <= o["y"] and o["x"] + o["w"] <= g["x"] + g["w"] and o["y"] + o["h"] <= g["y"] + g["h"]:
            out |= {k, *o.get("members", [])}
    return out


# ---- Mermaid out ------------------------------------------------------------------------------------------------------------------
ARROW = {"solid": "-->", "dashed": "-.->", "dotted": "-.->"}


def mermaid(b, keep=None, direction="LR"):
    """the connectors (all, or those with both ends in keep) as a Mermaid flowchart that structure reads back: each node's board id in a
    %% hyimg comment; dotted and blue by linkStyle, as Mermaid has no words for them"""
    L = [(k, c) for k, c in table(b).items() if keep is None or (c["from"] in keep and c["to"] in keep)]
    ids = list(dict.fromkeys(e for _k, c in L for e in (c["from"], c["to"])))
    key, used = {}, set()
    for i in ids:
        base = re.sub(r"[^a-z0-9]+", "_", short(b, i).lower()).strip("_")[:24] or "n"
        if not base[0].isalpha(): base = "n" + base
        k, n = base, 2
        while k in used: k, n = f"{base}{n}", n + 1
        used.add(k); key[i] = k
    q = lambda s: '"' + s.replace('"', "'") + '"'
    out = [f"flowchart {direction}"] + [f"  {key[i]}[{q(short(b, i))}]" for i in ids]
    styles = []
    for n, (_k, c) in enumerate(L):
        a, z, st, blue = key[c["from"]], key[c["to"]], c.get("style", "solid"), c.get("color") == "blue"
        arrow = ARROW[st] if st != "solid" else "==>" if blue else "-->"
        out.append(f"  {a} -- {q(c['label'])} {arrow} {z}" if c.get("label") and arrow == "-->" else
                   f"  {a} {arrow}|{q(c['label'])}| {z}" if c.get("label") else f"  {a} {arrow} {z}")
        css = (["stroke:#3b82f6"] if blue and st != "solid" else []) + (["stroke-dasharray:2 6"] if st == "dotted" else [])
        if css: styles.append(f"  linkStyle {n} {','.join(css)}")
    return "\n".join(out + styles + [f"  %% hyimg: {key[i]} = {i}" for i in ids]) + "\n"


# ---- Mermaid in -------------------------------------------------------------------------------------------------------------------
NODE_RE = r"([A-Za-z_][\w-]*)\s*(?:\(\[(.+?)\]\)|\[\[(.+?)\]\]|\(\((.+?)\)\)|\[(.+?)\]|\((.+?)\)|\{(.+?)\}|>(.+?)\])?"
EDGE_RE = re.compile(r"\s*(?:--\s*(\"[^\"]*\"|[^->|]+?)\s*(-->|---)|(-\.->|-\.-|==>|-->|---)(?:\|(.*?)\|)?|-\.\s*(.+?)\s*\.->|==\s*(.+?)\s*==>)\s*")


def _label(s):
    s = (s or "").strip()
    return s[1:-1] if len(s) >= 2 and s[0] == s[-1] == '"' else s


def parse(text):
    """a Mermaid flowchart: {direction, nodes {key: label}, order [keys], edges [(a, z, label, style, color)], ids {key: board id | "new"}}"""
    out = {"direction": "LR", "nodes": {}, "order": [], "edges": [], "ids": {}}
    node = re.compile(NODE_RE)

    def take(s, at):
        m = node.match(s, at)
        if not m: return None, at
        k = m.group(1); lab = next((g for g in m.groups()[1:] if g is not None), None)
        if k not in out["nodes"]: out["nodes"][k] = k; out["order"].append(k)
        if lab is not None: out["nodes"][k] = _label(lab)
        return k, m.end()
    styles = {}
    for raw in text.splitlines():
        s = raw.strip()
        m = re.match(r"%%\s*hyimg:\s*([\w-]+)\s*=\s*(\S+)", s)
        if m: out["ids"][m.group(1)] = m.group(2); continue
        if not s or s.startswith("%%"): continue
        m = re.match(r"(?:flowchart|graph)\s+(LR|RL|TB|TD|BT)\b", s)
        if m: out["direction"] = {"TD": "TB"}.get(m.group(1), m.group(1)); continue
        m = re.match(r"linkStyle\s+([\d,\s]+)\s+(.*)", s)
        if m:
            for n in re.findall(r"\d+", m.group(1)): styles[int(n)] = m.group(2)
            continue
        if re.match(r"(classDef|class|style|subgraph|end|click|direction)\b", s): continue
        a, at = take(s, 0)
        while a:
            e = EDGE_RE.match(s, at)
            if not e: break
            arrow = e.group(2) or e.group(3) or ("-.->" if e.group(5) is not None else "==>" if e.group(6) is not None else "-->")
            lab = _label(e.group(1) or e.group(4) or e.group(5) or e.group(6) or "")
            z, at = take(s, e.end())
            if not z: break
            st = "dashed" if arrow.startswith("-.") else "solid"
            out["edges"].append([a, z, lab, st, "blue" if arrow == "==>" else None]); a = z
    for n, e in enumerate(out["edges"]):
        st = styles.get(n, "")
        dash = re.search(r"stroke-dasharray\s*:\s*([\d.]+)", st)
        if dash: e[3] = "dotted" if float(dash.group(1)) <= 3 else "dashed"
        if re.search(r"stroke\s*:\s*#(3b82f6|2563eb|0a84ff)", st, re.I): e[4] = "blue"
    out["edges"] = [tuple(e) for e in out["edges"]]
    return out


def _match(b, label, norm):
    """a thing whose name is the node's words: a group's title, a heading's text, a note's first line (one, or none)"""
    I, G = b.get("items") or {}, b.get("groups") or {}
    hit = [k for k, g in G.items() if norm(g.get("title")) == norm(label)]
    hit += [k for k, it in I.items() if it.get("type") in ("text", "note") and norm(notelinks.first_line(it.get("text"))) == norm(label)]
    return hit[0] if len(hit) == 1 else None


def ranks(keys, edges):
    """a layer per node: the longest path from a node nothing points at (a circle stops where it closes)"""
    r = {k: 0 for k in keys}
    for _ in range(len(keys)):
        moved = False
        for a, z, *_ in edges:
            if a in r and z in r and r[z] < r[a] + 1 and r[a] + 1 < len(keys): r[z] = r[a] + 1; moved = True
        if not moved: break
    return r


# ---- hy.py do -------------------------------------------------------------------------------------------------------------------
HELP = """
  connect A B [C...] [label="…"] [style=solid|dashed|dotted] [color=grey|blue]   an arrow between any two things (pictures, cards,
                                      headings, groups, notes, timelines; by id, a name or a file); C... chains A → B → C; the same pair
                                      again changes its label, style and colour (solid «is», dashed «like», dotted «maybe», blue «picked»)
  disconnect ID | A B | A             a connector by its id, the arrow A → B, or every connector of A
  structure FILE.mmd | text="…" [near=REF side=right | x= y=] [sync=1]   Mermaid in: nodes found by «%% hyimg: key = id» or by name,
                                      the others new group frames laid out by the flow; the arrows made or updated (sync=1 also takes off
                                      the arrows between those nodes the text no longer has). Out: hy.py mermaid [GROUP], hy.py map --graph
"""
_hy = {}


def ref(b, s):
    """an id of an item or a group, else a name hy.py knows (a group, heading, note, timeline), else a picture or a card by its file"""
    import fnmatch
    I, G = b.get("items") or {}, b.get("groups") or {}
    if s in I or s in G: return s
    try:
        k, i, _nm, _r = _hy["resolve"](b, s)
        if k == "dot": raise SystemExit(f"«{s}»: точка таймлайна, стрелку веди к самому таймлайну")
        return i
    except SystemExit as e:
        if "точка" in str(e): raise
        why = e
    files = [k for k, it in I.items() if notelinks.file_of(it) and (notelinks.file_of(it) == s or notelinks.file_of(it).rsplit("/", 1)[-1] == s
                                                                      or fnmatch.fnmatch(notelinks.file_of(it), s))]
    if len(files) == 1: return files[0]
    if len(files) > 1: raise SystemExit(f"«{s}»: таких файлов на странице {len(files)}, назови по id: " + ", ".join(files[:6]))
    raise why


def _text(v):
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return None if v is None else str(v)


def op_connect(b, args, kv):
    if len(args) < 2: raise SystemExit('connect A B [C...] [label="…"] [style=dashed] [color=blue]')
    ends = [ref(b, a) for a in args]; out = []
    for a, z in zip(ends, ends[1:]):
        cid, new = put(b, a, z, _text(kv.get("label")), _text(kv.get("style")), _text(kv.get("color")))
        out.append(("connect " if new else "connect (уже была, обновил) ") + line(b, cid)[2:])
    return "\n".join(out)


def op_disconnect(b, args, kv):
    if not args: raise SystemExit("disconnect ID | A B | A")
    if len(args) == 1 and args[0] in table(b): ids = [args[0]]
    elif len(args) == 2:
        k = pair(b, ref(b, args[0]), ref(b, args[1]))
        if not k: raise SystemExit(f"стрелки {args[0]} → {args[1]} нет")
        ids = [k]
    else: ids = of(b, [ref(b, args[0])])
    if not ids: raise SystemExit(f"у «{args[0]}» стрелок нет")
    out = [line(b, k)[2:] for k in ids]
    for k in ids: del b["links"][k]
    prune(b)
    return "disconnect " + "; ".join(out)


def op_structure(b, args, kv):
    """Mermaid text in: its nodes as the board's things (by %% hyimg ids, else by name, else new group frames laid out along the flow
    near= a thing), its arrows as connectors"""
    if kv.get("text") is not None: src = str(kv["text"]).replace("\\n", "\n")
    elif args:
        try: src = open(args[0], encoding="utf-8").read()
        except OSError as e: raise SystemExit(f"structure: не прочитал {args[0]}: {e}")
    else: raise SystemExit('structure FILE.mmd | text="flowchart LR\\n a --> b" [near=REF]')
    m = parse(src); norm = _hy["norm"]
    if not m["edges"] and not m["nodes"]: raise SystemExit("structure: в тексте нет ни узлов, ни стрелок")
    I, G = b["items"], b["groups"]; found, new = {}, []
    for k in m["order"]:
        want = m["ids"].get(k)
        if want and want != "new":
            if want not in I and want not in G: raise SystemExit(f"structure: {k} = {want}, такого на странице нет")
            found[k] = want
        elif not want and _match(b, m["nodes"][k], norm): found[k] = _match(b, m["nodes"][k], norm)
        else: new.append(k)
    log = []
    if new:
        r = ranks(m["order"], m["edges"]); horiz = m["direction"] in ("LR", "RL")
        layers = {}
        for k in new: layers.setdefault(r[k], []).append(k)
        gap, (w, h) = 240, NODE
        pos = {k: ((L * (w + gap), j * (h + gap)) if horiz else (j * (w + gap), L * (h + gap))) for L, ks in layers.items() for j, k in enumerate(ks)}
        x0, y0 = min(p[0] for p in pos.values()), min(p[1] for p in pos.values())
        box = {"x": 0, "y": 0, "w": max(p[0] for p in pos.values()) - x0 + w, "h": max(p[1] for p in pos.values()) - y0 + h}
        if "x" in kv and "y" in kv: dx, dy = kv["x"], kv["y"]
        else:
            first = new[0]   # beside the step before the first new node (pattern flow's «Release» after «Picks»), else any node it touches
            near = kv.get("near") or next((found[a] for a, z, *_ in m["edges"] if z == first and a in found), None) \
                or next((found[z] for a, z, *_ in m["edges"] if a == first and z in found), None) or next(iter(found.values()), None)
            if near is None: raise SystemExit("structure: все узлы новые, укажи near=<что рядом> или x= y=")
            nr = _hy["rect"](b, ref(b, str(near)))
            sp = _hy["free_spot"](b, nr, box, kv.get("side", "right" if horiz else "below"), 480); dx, dy = sp["x"], sp["y"]
        for k in new:
            gid = _hy["uid"]("g"); x, y = pos[k]
            G[gid] = {"title": m["nodes"][k], "x": round(dx + x - x0), "y": round(dy + y - y0), "w": w, "h": h, "members": []}
            found[k] = gid; log.append(f"узел «{m['nodes'][k]}» новой группой [{gid}]")
    made = upd = 0; want = set()
    keep = kv.get("keep")   # pattern flow: an arrow that is there keeps the words, line and colour the text does not name
    for a, z, lab, st, col in m["edges"]:
        cid, fresh = put(b, found[a], found[z], *((lab or None, None if st == "solid" else st, col) if keep else (lab, st, col or "grey")))
        want.add(cid); made += fresh; upd += not fresh
    gone = 0
    if kv.get("sync"):
        S = set(found.values())
        for k in [k for k, c in table(b).items() if c["from"] in S and c["to"] in S and k not in want]: del b["links"][k]; gone += 1
    log.append(f"structure: узлов {len(found)} (новых {len(new)}), стрелок новых {made}, обновил {upd}" + (f", убрал {gone}" if gone else ""))
    return "\n".join(log)


# ---- what hy.py shows -----------------------------------------------------------------------------------------------------------
def show_map(b, area_ids=None, pad=""):
    ks = list(table(b)) if area_ids is None else of(b, area_ids)
    if ks: print(f"{pad}стрелки: {len(ks)}"); [print(pad + "  " + line(b, k)) for k in ks[:60]]


def show_find(b, ids):
    for k in of(b, ids): print("  " + line(b, k))


def graph(b, keep=None):
    """map --graph: the board as nodes and edges, one line an arrow (st4: «40 lines, not 90 KB»)"""
    ks = [k for k, c in table(b).items() if keep is None or (c["from"] in keep and c["to"] in keep)]
    if not ks: return "стрелок нет"
    return "\n".join(f"{short(b, c['from'])} {'⇒' if c.get('color') == 'blue' else '┄>' if c.get('style') in ('dashed', 'dotted') else '→'} "
                     f"{short(b, c['to'])}" + (f" [{c['label']}]" if c.get("label") else "") for c in (table(b)[k] for k in ks))


def md(b):
    """the md view's section: every connector as a line, after the page"""
    if not table(b): return ""
    return "\n## ↦ Стрелки (только чтение: connect, disconnect)\n\n" + "\n".join(line(b, k) for k in table(b)) + "\n"   # md apply stops here


def _keep(f):
    def run(b, args, kv):
        res = f(b, args, kv); n = prune(b)
        return res + (f" · стрелок убрано вместе с вещами: {n}" if n and isinstance(res, str) else "")
    return run


def hook(g):
    """hy.py, one line at its end: the do commands keep the connectors right, connect/disconnect/structure and the patterns join them,
    map, find, md, check show them; hy.py mermaid, hy.py structure, map --graph, check --pattern (patterns.py)"""
    import patterns
    _hy.update(resolve=g["resolve"], rect=g["rect"], free_spot=g["free_spot"], uid=g["uid"], norm=g["norm"], api=g["api"])
    OPS = g["OPS"]
    for k in list(OPS): OPS[k] = _keep(OPS[k])
    OPS.update(connect=op_connect, disconnect=_keep(op_disconnect), structure=op_structure)
    patterns.register(g)
    import imageops; imageops.register(g)   # hy.py image: Image Studio's tools for an agent (imageops.py)
    cmd_map, cmd_find, main = g["cmd_map"], g["cmd_find"], g["main"]

    def map_(b, ref_, tol, groups):
        if ref_ and ref_.split()[0] == "--graph":
            rest = ref_.split(None, 1)[1] if len(ref_.split()) > 1 else None
            print(graph(b, inside(b, g["resolve"](b, rest, {"group"})[1]) if rest else None)); return
        cmd_map(b, ref_, tol, groups)
        if ref_:
            k, i, _n, _r = g["resolve"](b, ref_)
            show_map(b, inside(b, i) if k == "group" else {i})
        else: show_map(b)

    def find_(b, q):
        cmd_find(b, q)
        I = b.get("items") or {}; G = b.get("groups") or {}
        hit = [i for i in list(I) + list(G) if q == i or (q and g["norm"](q) in g["norm"](name(b, i)))]
        if q in table(b): print(line(b, q))
        show_find(b, hit[:40])

    def main_(argv):
        val = ("--page", "--port", "--label", "--say", "--text", "--ids", "--to", "--tol")
        flags = [a for k, a in enumerate(argv) if a.startswith("--") or (k and argv[k - 1] in val)]
        pos = [a for a in argv if a not in flags]
        if pos and pos[0] == "structure":   # hy.py structure FILE.mmd near=… : a do, with its versions and the owner's notification
            return main(["do", "structure " + " ".join(shlex.quote(a) for a in pos[1:])] + flags)
        if pos and pos[0] == "mermaid": return mermaid_cli(g, argv)
        if pos and pos[0] == "patterns": print(patterns.catalogue()); return
        if pos and pos[0] == "md":   # the md view ends with the page's connectors
            import hymd
            render = hymd.render
            hymd.render = lambda b, *a, **k: render(b, *a, **k) + md(b)
            try: return main(argv)
            finally: hymd.render = render
        return main(argv)
    g["cmd_map"], g["cmd_find"], g["main"] = map_, find_, main_


def mermaid_cli(g, argv):
    """hy.py mermaid [GROUP] [--page P] [--dir TB]: the connectors of the page, or of what lies in one group, as Mermaid"""
    page, it, rest, d = None, iter(argv), [], "LR"
    for a in it:
        if a == "--page": page = next(it)
        elif a == "--port": g["BASE"] = f"http://localhost:{int(next(it))}"
        elif a == "--dir": d = next(it)
        elif a != "mermaid": rest.append(a)
    if page is None:
        try: page = (g["api"]("/api/live")[1].get("canvas") or {}).get("page") or "main"
        except Exception: page = "main"
    _, b = g["api"](f"/api/board?name={page}")
    keep = inside(b, g["resolve"](b, " ".join(rest), {"group"})[1]) if rest else None
    print(mermaid(b, keep, d), end="")
