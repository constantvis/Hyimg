"""Who made a change (owner 2026-10-07: two people, each on his own Mac, share boards through a shared Dropbox folder). There is no
login: the person on a Mac is a profile kept on that Mac, and everything Hyimg writes says who wrote it.

Files, all local to the Mac (the folder beside the app's catalog, ~/Library/Application Support/Hyimg; HYIMG_PROFILE_DIR names another,
a server started without the app keeps them beside its own settings, as tests do):
  profile.json   {"id": a random uuid made once, "name", "color": a note colour (ui/menu.js HY_COLORS), "created": ISO time}
  people.json    the address book: {id: {"name", "color", "alias"?, "seen"}}; alias is how this Mac shows that person (a local rename)
A board carries one card per person who wrote to it, <state>/people/<id>.json {"id", "name", "color", "updated"}: each Mac writes only
its own card, so a shared folder never gets two writers on one file. A Mac learns the others from these cards (learn()).

The stamp on every write: "by": {"person": <profile id>, "via": "app" | the agent's name (HYIMG_AGENT, hy.py sends it as the header
X-Hyimg-Agent)}. Agents running on a Mac act for that Mac's person («Codex · agent of <name>»). Without a profile the stamp has only "via".
Since 2026-10-07 via is a kind of the fixed catalog (agents.py: claude, codex, gemini, kimi, opencode, agent), never a free name, and
the server finds it by itself from the client's process tree; the header is only a fallback. An agent is no participant of its own:
the address book and the board cards list per person the kinds seen acting for him ("agents": {kind: last time}).
A person may carry a small picture ("avatar": a data URL of at most AVATAR_MAX characters, the page cuts a 256 px square), else the
pages draw his initials. An agent kind's badge is the company's mark (ui/agents) or our glyph; this Mac may put its own picture on a kind:
  agent-badges.json   {kind: data URL}, beside the profile, never on a board (owner 2026-10-08: each Mac shows the agents as it likes)
Writes that are not board saves (plugin files, snapshots, pasted pictures) go to <state>/boards/_events/_files.jsonl, one line each.
"""
import fcntl
import json
import os
import re
import time
import uuid

import agents
import boardid

COLORS = ("yellow", "orange", "red", "pink", "purple", "blue", "green", "grey")   # ui/menu.js HY_COLORS, canvas.html NCOL
FILES_KEEP = 3000
AVATAR_MAX = 80_000   # a 256 px JPEG is 15-40 KB (ui/crop.js steps its quality down to fit); the cards carry it to the other Mac
BADGES = "agent-badges.json"
SEEN_EVERY = 600      # an agent's last activity on a card is rewritten at most every 10 minutes


def root_dir(settings_file=""):
    """where profile.json and people.json live: HYIMG_PROFILE_DIR, else beside the app's settings file. Never in Dropbox (owner
    2026-10-08: two Macs share one Dropbox account, a profile there would be both Macs' person): a server started by hand on a board
    keeps its settings in the board's _review, its profile then is this Mac's, beside the app's catalog"""
    d = os.environ.get("HYIMG_PROFILE_DIR") or (os.path.dirname(os.path.abspath(settings_file)) if settings_file else "")
    if not d: raise ValueError("no folder for the profile")
    if not os.environ.get("HYIMG_PROFILE_DIR") and boardid.in_dropbox(d): d = os.path.expanduser("~/Library/Application Support/Hyimg")
    return os.path.realpath(d)


def _read(p, default=None):
    try:
        with open(p, encoding="utf-8") as fh: v = json.load(fh)
        return v if isinstance(v, dict) else default
    except (OSError, ValueError):
        return default


def _write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh: json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, p)


def _locked(root):
    """one writer at a time across the servers of every board and the app (a lock file beside the files)"""
    os.makedirs(root, exist_ok=True)
    fh = open(os.path.join(root, "people.json.lock"), "w")
    fcntl.flock(fh, fcntl.LOCK_EX)
    return fh


def clean_name(v):
    return " ".join(str(v or "").split())[:40]


def clean_color(v):
    return v if v in COLORS else ""


def clean_avatar(v):
    v = str(v or "")
    return v if len(v) <= AVATAR_MAX and re.fullmatch(r"data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/]+=*", v) else ""


def clean_agents(v):
    """{kind: last seen, unix seconds} with catalog kinds only"""
    out = {}
    for k, t in (v.items() if isinstance(v, dict) else ()):
        kk = agents.kind(k)
        if kk and isinstance(t, (int, float)): out[kk] = max(int(t), out.get(kk, 0))
    return out


def _is_id(v):
    try: return str(uuid.UUID(str(v))) == str(v).lower()
    except ValueError: return False


# ---- the profile of this Mac --------------------------------------------------------------------------------------------------------
def me(root):
    p = _read(os.path.join(root, "profile.json"))
    if not p or not _is_id(p.get("id")) or not clean_name(p.get("name")): return None
    out = {"id": p["id"], "name": clean_name(p["name"]), "color": clean_color(p.get("color")) or "blue", "created": str(p.get("created") or "")}
    if clean_avatar(p.get("avatar")): out["avatar"] = p["avatar"]
    return out


def save_me(root, name, color, avatar=None):
    """the first launch's answer, or a change in Settings › Profile: the id is made once and kept; avatar "" takes the picture off"""
    name, color = clean_name(name), clean_color(color)
    if not name: raise ValueError("a name is needed")
    if avatar and not clean_avatar(avatar): raise ValueError("the picture is not a small png, jpeg or webp")
    with _locked(root):
        cur = me(root) or {"id": str(uuid.uuid4()), "created": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        cur.update(name=name, color=color or cur.get("color") or "blue")
        if avatar is not None:
            if avatar: cur["avatar"] = avatar
            else: cur.pop("avatar", None)
        _write(os.path.join(root, "profile.json"), cur)
        book = _read(os.path.join(root, "people.json"), {})
        e = book.get(cur["id"]) if isinstance(book.get(cur["id"]), dict) else {}
        book[cur["id"]] = {**{k: v for k, v in e.items() if k != "avatar"}, "name": cur["name"], "color": cur["color"], "seen": int(time.time()),
                           **({"avatar": cur["avatar"]} if cur.get("avatar") else {})}
        _write(os.path.join(root, "people.json"), book)
    return cur


def sign_out(root):
    """«Sign out»: this Mac forgets its profile and asks again at the next start; nothing else is deleted (the address book keeps the
    name, so the changes made so far still show it)"""
    with _locked(root):
        p = os.path.join(root, "profile.json")
        if os.path.exists(p): os.remove(p)
    return {"signedOut": True}


# ---- this Mac's pictures of the agent kinds -------------------------------------------------------------------------------------------
def badges(root):
    """{kind: data URL} of the catalog's kinds this Mac gave a picture of its own (Settings › Profile › Agents)"""
    b = _read(os.path.join(root, BADGES), {})
    return {k: v for k, v in b.items() if k in agents.CATALOG and clean_avatar(v)}


def set_badge(root, kind, picture):
    """a kind's own picture on this Mac; "" takes it off (the company's mark or our glyph again)"""
    if kind not in agents.CATALOG: raise ValueError("unknown agent kind")
    if picture and not clean_avatar(picture): raise ValueError("the picture is not a small png, jpeg or webp")
    with _locked(root):
        b = badges(root)
        if picture: b[kind] = picture
        else: b.pop(kind, None)
        _write(os.path.join(root, BADGES), b)
    return b


# ---- the address book -----------------------------------------------------------------------------------------------------------------
def book(root):
    b = _read(os.path.join(root, "people.json"), {})
    return {k: v for k, v in b.items() if _is_id(k) and isinstance(v, dict)}


def alias(root, person, name):
    """how this Mac shows another person (owner: «the owner sees the partner as he wants»); an empty name takes it back"""
    if not _is_id(person): raise ValueError("bad person")
    with _locked(root):
        b = book(root); e = dict(b.get(person) or {})
        if clean_name(name): e["alias"] = clean_name(name)
        else: e.pop("alias", None)
        b[person] = e; _write(os.path.join(root, "people.json"), b)
    return b[person]


def hide(root, person, hidden=True):
    """Settings › Profile › Team: a person this Mac does not want in its lists (the mentions, the team); his changes still name him"""
    if not _is_id(person): raise ValueError("bad person")
    with _locked(root):
        b = book(root); e = dict(b.get(person) or {})
        if hidden: e["hidden"] = True
        else: e.pop("hidden", None)
        b[person] = e; _write(os.path.join(root, "people.json"), b)
    return b[person]


def cards(state_root):
    """the people who wrote to a board: their own cards in <state>/people"""
    d, out = os.path.join(state_root, "people"), {}
    try: names = os.listdir(d)
    except OSError: return out
    for n in names:
        c = _read(os.path.join(d, n)) if n.endswith(".json") else None
        if c and _is_id(c.get("id")) and n == c["id"] + ".json" and clean_name(c.get("name")):
            out[c["id"]] = {"name": clean_name(c["name"]), "color": clean_color(c.get("color")), "updated": c.get("updated", 0),
                            "avatar": clean_avatar(c.get("avatar")), "agents": clean_agents(c.get("agents"))}
    return out


def card_write(state_root, who, agent=""):
    """this Mac's person's card on a board, written only when it is missing or says something else; agent: a kind seen acting for him
    now (its time is rewritten at most every SEEN_EVERY seconds)"""
    if not who: return False
    p = os.path.join(state_root, "people", who["id"] + ".json")
    old = _read(p) or {}
    seen, now = clean_agents(old.get("agents")), int(time.time())
    fresh = not agent or now - seen.get(agent, 0) < SEEN_EVERY
    if old.get("name") == who["name"] and old.get("color") == who["color"] and (old.get("avatar") or "") == (who.get("avatar") or "") and fresh: return False
    if agent: seen[agent] = now
    card = {"id": who["id"], "name": who["name"], "color": who["color"], "updated": now}
    if who.get("avatar"): card["avatar"] = who["avatar"]
    if seen: card["agents"] = seen
    _write(p, card)
    return True


def learn(root, found):
    """the people a board's cards name, into the address book (their own name and colour; an alias set here stays)"""
    def merged(e, v):
        out = {**e, "name": v["name"], "color": v["color"]}
        if v.get("avatar"): out["avatar"] = v["avatar"]
        a = {**clean_agents(e.get("agents"))}
        for k, t in (v.get("agents") or {}).items(): a[k] = max(t, a.get(k, 0))
        if a: out["agents"] = a
        return out
    b = book(root)
    new = {k: v for k, v in found.items() if {**(b.get(k) or {}), "seen": 0} != {**merged(b.get(k) or {}, v), "seen": 0}}
    if not new: return b
    with _locked(root):
        b = book(root)
        for k, v in new.items(): b[k] = {**merged(b.get(k) or {}, v), "seen": int(time.time())}
        _write(os.path.join(root, "people.json"), b)
    return b


def view(root, state_root=None):
    """what a page needs: {me, people: {id: {name (as this Mac shows it), own (their own name), color, alias?}}}"""
    m, b = me(root), book(root)
    if state_root:
        b = learn(root, cards(state_root))
    people = {k: {"name": v.get("alias") or clean_name(v.get("name")) or "?", "own": clean_name(v.get("name")), "color": clean_color(v.get("color")),
                  **({"alias": v["alias"]} if v.get("alias") else {}), **({"hidden": True} if v.get("hidden") else {}),
                  **({"avatar": clean_avatar(v.get("avatar"))} if clean_avatar(v.get("avatar")) else {}),
                  **({"agents": clean_agents(v.get("agents"))} if clean_agents(v.get("agents")) else {})} for k, v in b.items()}
    if m:
        people[m["id"]] = {**{k: v for k, v in people.get(m["id"], {}).items() if k not in ("alias", "hidden", "avatar")}, "name": m["name"], "own": m["name"],
                           "color": m["color"], "me": True, **({"avatar": m["avatar"]} if m.get("avatar") else {})}
    return {"me": m, "people": people, "kinds": list(agents.CATALOG), "badges": badges(root)}


# ---- the stamp -------------------------------------------------------------------------------------------------------------------------
def clean_via(v):
    """an agent's name as a catalog kind (agents.py); "" for the app"""
    return agents.kind(v)


def by(root, agent="", who=""):
    """{"person", "via"} for a write: via is a catalog kind, "agent" for an AI write without one, else "app\""""
    via = clean_via(agent) or ("agent" if who in ("ai", "agent") else "app")
    m = me(root)
    return {"person": m["id"], "via": via} if m else {"via": via}


def request_by(root, handler, q=None, who=""):
    """the stamp of an HTTP request. The server's own look at the client's process tree comes first (agents.detect: a catalog kind,
    "" for a person's app or browser); the header X-Hyimg-Agent (hy.py), ?agent= (an older hy.py) and ?who=ai only when it cannot tell,
    or when it finds no known agent and the client says it is one"""
    header = handler.headers.get("X-Hyimg-Agent") or ((q or {}).get("agent") or [""])[0]
    found = agents.detect(handler)
    if found: return by(root, found)
    if found == "" and not header: return by(root, "")
    return by(root, header, who or ((q or {}).get("who") or [""])[0])


def who_of(stamp, q=None):
    """the old field who of an event: "ai" for an agent's write, else what the page said (owner, auto)"""
    return "ai" if (stamp or {}).get("via", "app") != "app" else ((q or {}).get("who") or ["owner"])[0][:20]


def agent_of(stamp):
    """the old field agent of an event: the kind's name (Home's news), "" for the app"""
    return agents.label((stamp or {}).get("via"))


_CARDS = {}


def stamp(root, state_root, handler, q=None, who=""):
    """request_by, and this Mac's person's card on the board (written once per server and change), so the other Mac learns the name"""
    s = request_by(root, handler, q, who)
    m = me(root) if s.get("person") else None
    via = s.get("via") if s.get("via") != "app" else ""
    key = (m["id"], m["name"], m["color"], len(m.get("avatar") or ""), via, int(time.time() // SEEN_EVERY) if via else 0) if m else None
    if m and _CARDS.get((state_root, via)) != key:
        try: card_write(state_root, m, via); _CARDS[(state_root, via)] = key
        except OSError: pass
    return s


_LOGGED = {}
FOLD_S = 60   # a 3D camera turned on the canvas writes its scene every few tenths of a second: one line a minute per file and person


def log_write(state_root, kind, path, stamp):
    """a write that is not a board save (a 3D scene, a frame, a plugin's snapshot, a pasted picture): one line, newest last"""
    k, now = (state_root, str(path)), time.time()
    last = _LOGGED.get(k)
    if last and last[0] == stamp and now - last[1] < FOLD_S: return
    _LOGGED[k] = (stamp, now)
    p = os.path.join(state_root, "boards", "_events", "_files.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    line = json.dumps({"kind": kind, "path": str(path)[:400], "by": stamp, "t": time.strftime("%Y-%m-%d %H:%M:%S"), "ts": time.time()}, ensure_ascii=False)
    with open(p, "a", encoding="utf-8") as fh: fh.write(line + "\n")
    if os.path.getsize(p) > FILES_KEEP * 600:
        lines = open(p, encoding="utf-8").read().splitlines()[-FILES_KEEP:]
        tmp = p + ".tmp"; open(tmp, "w", encoding="utf-8").write("\n".join(lines) + "\n"); os.replace(tmp, p)


def _tail(p, keep):
    try: lines = open(p, encoding="utf-8").read().splitlines()
    except OSError: return
    for line in reversed(lines):
        try: e = json.loads(line)
        except ValueError: continue
        if keep(e): return e


def edited(state_root, page, item=None, paths=()):
    """the newest change of a card: the page's event that names it, or a write of one of its files, whichever is newer"""
    ev = _tail(os.path.join(state_root, "boards", "_events", page + ".jsonl"), lambda e: item in (e.get("ids") or [])) if item else None
    fw = _tail(os.path.join(state_root, "boards", "_events", "_files.jsonl"), lambda e: e.get("path") in paths) if paths else None
    best = max((e for e in (ev, fw) if e), key=lambda e: e.get("ts", 0), default=None)
    if not best: return {}
    return {k: best[k] for k in ("t", "ts", "who", "agent", "by", "kind") if k in best}


# ---- HTTP, for server.py ------------------------------------------------------------------------------------------------------------
def http(handler, method, root, state_root, q=None):
    """GET /api/profile, GET /api/edited?name=&id=&p=, POST /api/profile {op: save | avatar | badge | hide | signout | alias | places}"""
    send = lambda code, body: handler.send(code, json.dumps(body, ensure_ascii=False).encode(), "application/json")
    path = handler.path.split("?", 1)[0]
    try:
        if method == "GET" and path == "/api/edited":
            q = q or {}
            page = (q.get("name") or ["main"])[0]
            if not re.fullmatch(r"[\w-]+", page): raise ValueError("bad page")
            return send(200, edited(state_root, page, (q.get("id") or [None])[0], tuple(q.get("p") or ())))
        if method == "GET":
            import places
            return send(200, {**view(root, state_root), "places": places.read(root), "board": places.of_board(root, state_root)})
        n = int(handler.headers.get("Content-Length", 0) or 0)
        req = json.loads(handler.rfile.read(n) or b"{}")
        op = req.get("op")
        if op == "save": res = {"me": save_me(root, req.get("name"), req.get("color"), req.get("avatar"))}
        elif op == "avatar":
            m = me(root) or {}
            res = {"me": save_me(root, m.get("name"), m.get("color"), req.get("avatar") or "")}
        elif op == "badge": res = {"badges": set_badge(root, str(req.get("kind") or ""), req.get("picture") or "")}
        elif op == "hide": res = {"person": hide(root, req.get("person"), bool(req.get("hidden", True)))}
        elif op == "signout": res = sign_out(root)
        elif op == "alias": res = {"person": alias(root, req.get("person"), req.get("name"))}
        elif op == "places":
            import places
            res = {"places": places.write(root, **{k: req[k] for k in ("shared", "private") if k in req})}
        else: raise ValueError("unknown op")
        if op in ("save", "avatar"): card_write(state_root, me(root))
        return send(200, {**res, **view(root, state_root)})
    except (ValueError, TypeError, AttributeError, OSError) as ex:
        return send(400, {"error": str(ex)[:200]})


if __name__ == "__main__":   # for the app: python3 people.py save NAME COLOR | signout | alias ID NAME | hide ID 1|0 | avatar FILE|"" | badge KIND FILE|"" | view
    import sys
    a, r = sys.argv[1:], root_dir()
    cmd = a[0] if a else "view"

    def avatar(arg):   # the picture's data URL in a file (the app writes it to a temporary file), "" takes it off
        m = me(r) or {}
        data = open(arg, encoding="ascii").read().strip() if arg else ""
        return {"me": save_me(r, m.get("name"), m.get("color"), data)}

    def badge(kind, arg):   # an agent kind's picture, the same way
        return {"badges": set_badge(r, kind, open(arg, encoding="ascii").read().strip() if arg else "")}
    try:
        out = {"me": save_me(r, a[1], a[2] if len(a) > 2 else "")} if cmd == "save" else sign_out(r) if cmd == "signout" \
            else {"person": alias(r, a[1], a[2] if len(a) > 2 else "")} if cmd == "alias" \
            else {"person": hide(r, a[1], (a[2] if len(a) > 2 else "1") != "0")} if cmd == "hide" \
            else avatar(a[1] if len(a) > 1 else "") if cmd == "avatar" else badge(a[1], a[2] if len(a) > 2 else "") if cmd == "badge" else view(r)
        if cmd in ("save", "signout", "alias", "hide", "avatar", "badge"): out = {**out, **view(r)}
    except (ValueError, IndexError, OSError) as ex:
        out = {"error": str(ex)[:200]}
    print(json.dumps(out, ensure_ascii=False))
