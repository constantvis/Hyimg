#!/usr/bin/env python3
"""Hyimg as an MCP server (stdio, JSON-RPC 2.0, one message per line), so an agent sees Hyimg's operations as tools without being told
(owner 2026-10-06: «agents that come to our app must get this information about skills, so it doesn't happen that I work with an agent
and it doesn't see the skills or the functions and I have to explain things to it»).

The tools are review/hy.py and scripts/active.py run against the running app over HTTP, the same as an agent in a terminal: every board
edit goes through `hy.py do` (versions before and after, a retry when the owner saved in between, a notification). The resources are the
skills (skills/*/SKILL.md), the feature catalog (review/features.json) and /agent of a project; the prompts are the skills.

Which project: every tool takes `project` (its name, id or port). Without it: HYIMG_PORT when set, else the project open in the app's
front tab (active.json), else the only running one. The ports come from ~/Library/Application Support/Hyimg/projects.json (HYIMG_CATALOG_DIR
names another folder) and are checked with /api/health, so a port serving another project is never used.

  python3 mcp/server.py                      the server on stdin/stdout (an MCP client starts it)
  python3 mcp/server.py --list-tools         the tools with their descriptions, for a person

No package beyond Python's own library. Registering it with an agent is the person's decision: README, section «MCP».
"""
import json, os, re, shlex, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HY = os.path.join(REPO, "review", "hy.py")
ACTIVE = os.path.join(REPO, "scripts", "active.py")
SKILLS = os.path.join(REPO, "skills")
FEATURES = os.path.join(REPO, "review", "features.json")
VERSION = "0.1.0"
PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]
CLIENT = {"name": ""}

INSTRUCTIONS = ("Hyimg is the owner's Mac app: an image library and a Figma-like board per project, served on localhost. Start with "
                "hyimg_guide: it gives what the owner has open, the project's own rules (they win over everything else), the installed plugins, "
                "the skills and the feature catalog (hyimg_features searches it). Change a board only through hyimg_do (or hyimg_props, "
                "hyimg_topage): never write board JSON, never drag on the canvas. Read with hyimg_map and hyimg_find instead of screenshots, "
                "check with hyimg_check after a change. Pictures go into the library with hyimg_save. Write to the owner in his language "
                "(Russian by default). The skills are resources hyimg://skills/<name> and prompts of the same names.")


# ---------------------------------------------------------------- projects and ports
def catalog_dir():
    return os.environ.get("HYIMG_CATALOG_DIR") or os.path.expanduser("~/Library/Application Support/Hyimg")


def projects():
    try: L = json.load(open(os.path.join(catalog_dir(), "projects.json"), encoding="utf-8"))
    except (OSError, ValueError): return []
    return [p for p in L if isinstance(p, dict)] if isinstance(L, list) else []


def health(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{int(port)}/api/health", timeout=0.8) as r: return json.load(r)
    except Exception: return None


def running_port(p):
    """the port this project answers on now, or None"""
    for port in (p.get("port"), p.get("compatibilityPort")):
        if port:
            h = health(port)
            if h and str(h.get("projectId", "")).lower() == str(p.get("id", "")).lower(): return int(port)
    return None


class Pick(Exception):
    pass


def pick(project=None):
    """(port, name) of the project a tool works on"""
    if project in (None, "") and os.environ.get("HYIMG_PORT"): project = os.environ["HYIMG_PORT"]
    if project not in (None, ""):
        q = str(project).strip()
        if q.isdigit():
            h = health(q)
            if not h: raise Pick(f"на порту {q} Hyimg не отвечает")
            name = next((p.get("name") for p in projects() if str(p.get("id", "")).lower() == str(h.get("projectId", "")).lower()), "") or h.get("libraryRoot", "")
            return int(q), name
        P = projects()
        hit = [p for p in P if str(p.get("id", "")).lower() == q.lower() or (p.get("name") or "").lower() == q.lower()] or \
              [p for p in P if q.lower() in (p.get("name") or "").lower()]
        if len(hit) != 1: raise Pick((f"проект «{q}» неоднозначен: " if hit else f"нет проекта «{q}». Есть: ") + ", ".join(f"«{p.get('name')}»" for p in (hit or P)))
        port = running_port(hit[0])
        if not port: raise Pick(f"проект «{hit[0].get('name')}» не запущен: владелец открывает его в приложении Hyimg")
        return port, hit[0].get("name", "")
    try:
        act = json.load(open(os.path.join(catalog_dir(), "active.json"), encoding="utf-8"))
        if act.get("view") == "project" and isinstance(act.get("project"), dict):
            port = running_port(act["project"])
            if port: return port, act["project"].get("name", "")
    except (OSError, ValueError): pass
    up = [(running_port(p), p) for p in projects()]
    up = [(port, p) for port, p in up if port]
    if len(up) == 1: return up[0][0], up[0][1].get("name", "")
    if not up: raise Pick("ни один проект Hyimg не запущен: владелец открывает проект в приложении")
    raise Pick("запущено несколько проектов, назови нужный в project: " + ", ".join(f"«{p.get('name')}» (порт {port})" for port, p in up))


def run(argv, port=None, timeout=600):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    if CLIENT["name"] and not env.get("HYIMG_AGENT"): env["HYIMG_AGENT"] = CLIENT["name"]
    if port: env["HYIMG_PORT"] = str(port)
    try: r = subprocess.run([sys.executable, *argv], env=env, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired: return f"не закончилось за {timeout} с", True
    out = (r.stdout or "").rstrip()
    if r.returncode != 0: return (out + "\n" + (r.stderr or "").strip()).strip() or f"код выхода {r.returncode}", True
    err = (r.stderr or "").strip()
    return (out + ("\n" + err if err else "")).strip() or "готово", False


def page_id(port, page):
    """a page by its id or its title (the agent sees titles, hy.py takes ids)"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/pages", timeout=10) as r: L = json.load(r).get("pages", [])
    except Exception: return page
    if any(p.get("id") == page for p in L): return page
    hit = [p["id"] for p in L if (p.get("title") or "").strip().lower() == page.strip().lower()]
    return hit[0] if len(hit) == 1 else page


def hy(args, a, port):
    pg = ["--page", page_id(port, str(a["page"]))] if a.get("page") else []
    return run([HY, "--port", str(port), *pg, *args], port)


def get_text(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=30) as r: return r.read().decode("utf-8")


# ---------------------------------------------------------------- tools
P_PROJECT = {"type": "string", "description": "Hyimg project: its name, id or port. Default: the project open in the app's front tab, or the only running one"}
P_PAGE = {"type": "string", "description": "Board page id or title (hyimg_pages). Default: the page the owner has open on the canvas"}


def schema(props, required=()):
    return {"type": "object", "properties": {"project": P_PROJECT, **props}, "required": list(required), "additionalProperties": False}


def t_projects(a):
    out, act = [], {}
    try: act = json.load(open(os.path.join(catalog_dir(), "active.json"), encoding="utf-8"))
    except (OSError, ValueError): pass
    front = (act.get("project") or {}).get("id") if act.get("view") == "project" else None
    for p in projects():
        port = running_port(p)
        out.append(f"«{p.get('name')}» id {p.get('id')} · " + (f"запущен на порту {port}" if port else "не запущен") + (" · открыт у владельца" if p.get("id") == front else "")
                   + f" · папка {p.get('libraryRoot')}")
    return "\n".join(out) or "в каталоге нет проектов", False


def t_guide(a):
    port, _ = pick(a.get("project"))
    return get_text(port, "/agent"), False


def t_features(a):
    return run([HY, "features", *([a["query"]] if a.get("query") else [])])


def t_active(a):
    return run([ACTIVE, *(["--link", a["link"]] if a.get("link") else []), *(["--paths"] if a.get("paths_only") else [])])


def t_map(a):
    port, _ = pick(a.get("project"))
    return hy(["map", *([a["ref"]] if a.get("ref") else []), *(["--groups"] if a.get("groups") else [])], a, port)


def t_find(a):
    port, _ = pick(a.get("project")); return hy(["find", a["query"]], a, port)


def t_check(a):
    port, _ = pick(a.get("project")); return hy(["check", *([a["ref"]] if a.get("ref") else [])], a, port)


def t_pages(a):
    port, _ = pick(a.get("project")); return run([HY, "--port", str(port), "pages"], port)


def t_page_new(a):
    port, _ = pick(a.get("project")); return run([HY, "--port", str(port), "page", "new", a["title"]], port)


def t_do(a):
    port, _ = pick(a.get("project"))
    extra = (["--label", a["label"]] if a.get("label") else []) + (["--say", a["say"]] if a.get("say") else []) \
        + (["--dry"] if a.get("dry") else []) + (["--quiet"] if a.get("quiet") else [])
    return hy(["do", a["script"], *extra], a, port)


def t_notify(a):
    port, _ = pick(a.get("project"))
    return hy(["notify", a["title"], *(["--text", a["text"]] if a.get("text") else []), *(["--ids", ",".join(a["ids"])] if a.get("ids") else [])], a, port)


def _q(s): return shlex.quote(s)


def t_props(a):
    port, _ = pick(a.get("project"))
    if bool(a.get("source")) == bool(a.get("preset")): return "нужен ровно один из source (откуда) или preset (имя пресета)", True
    parts = ["props", _q(("from=" + a["source"]) if a.get("source") else ("preset=" + a["preset"])), _q("to=" + ",".join(a["targets"]))]
    if a.get("only"): parts.append(_q("only=" + ",".join(a["only"])))
    return hy(["do", " ".join(parts), "--label", a.get("label") or "свойства", "--quiet"], a, port)


def t_presets(a):
    port, _ = pick(a.get("project")); act = a.get("action", "list")
    if act == "list": return run([HY, "--port", str(port), "presets"], port)
    if not a.get("name"): return "нужно name", True
    if act == "delete": return hy(["preset", "delete", a["name"]], a, port)
    if not a.get("source"): return "для save нужно source (id или имя вещи)", True
    return hy(["preset", "save", a["name"], a["source"], *(["only=" + ",".join(a["only"])] if a.get("only") else [])], a, port)


def t_topage(a):
    port, _ = pick(a.get("project"))
    return hy(["do", " ".join(["topage", _q(a["to_page"]), *(_q(r) for r in a["refs"])]), "--label", a.get("label") or "перенос на страницу", "--quiet"], a, port)


def t_hist(a):
    port, _ = pick(a.get("project")); return hy(["hist", str(int(a.get("n") or 8))], a, port)


def t_restore(a):
    port, _ = pick(a.get("project")); return hy(["restore", a["id"]], a, port)


def t_save(a):
    port, _ = pick(a.get("project"))
    return run([HY, "--port", str(port), "save", *a["files"], "--to", a["to"], *(["--move"] if a.get("move") else [])], port)


TOOLS = [
    ("hyimg_projects", "List the Hyimg projects (boards) on this Mac: name, id, folder, whether running and on which port, which one the owner has open. Use when unsure which project is meant.",
     {"type": "object", "properties": {}, "additionalProperties": False}, t_projects),
    ("hyimg_guide", "START HERE. The project's agent guide (= GET /agent, `hy.py guide`): what the owner has open and selected, the pages, the project's own rules (AGENTS.md, they override general rules), the installed plugins, the skills and the catalog «Что умеет Hyimg» with the exact command for each feature.",
     schema({}), t_guide),
    ("hyimg_features", "Search Hyimg's feature catalog (review/features.json): how the owner uses a feature (keys, right click) and how an agent does it (exact hy.py command or HTTP route), plus the skill that explains it. No query lists all features.",
     {"type": "object", "properties": {"query": {"type": "string", "description": "a word: цветокор, grade, pdf, 3d, props, topage, mask, video, ..."}}, "additionalProperties": False}, t_features),
    ("hyimg_active", "What the owner has selected and sees right now in the front project (canvas and library): «these pictures», «the selected ones». With link: what a board link (?obj= or &at=) points at.",
     {"type": "object", "properties": {"link": {"type": "string", "description": "a board link the owner sent, hyimg://board/<id>?page=…&obj=… or http://localhost:41xx/?view=canvas&page=…&obj=…"},
                                       "paths_only": {"type": "boolean", "description": "only the selected pictures' library paths"}}, "additionalProperties": False}, t_active),
    ("hyimg_map", "Read a board page without screenshots: headings, groups (with picture counts), timelines, image frames; with ref, everything around one thing including notes.",
     schema({"page": P_PAGE, "ref": {"type": "string", "description": "a group, note, heading or id to look around"}, "groups": {"type": "boolean", "description": "also near-misses in group alignment"}}), t_map),
    ("hyimg_find", "Find things on a board page by a word of their name or path: groups, notes, headings, timeline dots, pictures (by path), image frames. Prints ids and boxes for hyimg_do.",
     schema({"page": P_PAGE, "query": {"type": "string"}}, ["query"]), t_find),
    ("hyimg_check", "Check a board page (or the area of one thing) for pictures over pictures, crooked rows and columns, pictures sticking out of group frames, staircase notes. Run after a change.",
     schema({"page": P_PAGE, "ref": {"type": "string"}}), t_check),
    ("hyimg_pages", "The project's board pages with their ids and picture counts.", schema({}), t_pages),
    ("hyimg_page_new", "Add a page to the project's board (as «+» on the canvas); prints its id.", schema({"title": {"type": "string"}}, ["title"]), t_page_new),
    ("hyimg_do", "Change a board page: one or more hy.py do commands separated by ';'. Saves versions before and after, retries when the owner saved in between, reports "
     "new layout problems and notifies the owner of what was added. Commands: block, arrange, move, fit, set, point, note, text, group, remove, frame, "
     "htmlframe, model, html, link, topage, props, clearprops, front, forward, backward, back, crop, trim, opacity, pdfpage, grade, mask, card3d, cards3d, camera3d, "
     "variant3d (hyimg_features or `hy.py` without arguments for their syntax). Example: block \"batch/*\" into=\"Theme\" note=\"# Batch name\". Use dry "
     "first for big changes.",
     schema({"page": P_PAGE, "script": {"type": "string", "description": "e.g. block \"arc/2610061200-p7/*\" into=\"Тема\" note=\"# P7\""},
             "label": {"type": "string", "description": "what the change is, for the version history"},
             "say": {"type": "string", "description": "one sentence for the owner's notification, in his language"},
             "dry": {"type": "boolean", "description": "show what would happen, save nothing"},
             "quiet": {"type": "boolean", "description": "no notification (only for rearranging what is there)"}}, ["script"]), t_do),
    ("hyimg_notify", "A notification for the owner (the bell on the canvas): something worth knowing that is not an addition (a batch checked, a decision needed).",
     schema({"page": P_PAGE, "title": {"type": "string"}, "text": {"type": "string"}, "ids": {"type": "array", "items": {"type": "string"}, "description": "board ids to jump to"}}, ["title"]), t_notify),
    ("hyimg_props", "Paste properties, as «Paste properties ›» on the canvas: crop, trim, size, opacity, PDF page, colour grade, mask from one object (source) or a saved preset onto targets. Kinds that do not apply to a target are skipped and counted.",
     schema({"page": P_PAGE, "source": {"type": "string", "description": "id or name of the object to copy from"}, "preset": {"type": "string", "description": "a saved preset's name instead of source"},
             "targets": {"type": "array", "items": {"type": "string"}, "description": "ids, names, groups or path globs"},
             "only": {"type": "array", "items": {"type": "string", "enum": ["grade", "mask", "crop", "trim", "size", "opacity", "page"]}},
             "label": {"type": "string"}}, ["targets"]), t_props),
    ("hyimg_presets", "The project's presets of properties: list them, save one from an object (as «Save as preset…»), or delete one.",
     schema({"page": P_PAGE, "action": {"type": "string", "enum": ["list", "save", "delete"]}, "name": {"type": "string"}, "source": {"type": "string"},
             "only": {"type": "array", "items": {"type": "string", "enum": ["grade", "mask", "crop", "trim", "size", "opacity", "page"]}}}), t_presets),
    ("hyimg_topage", "Move things to another page, as «Move to page ›»: a group with everything in it, a note with its zone; the layout kept, versions on both pages.",
     schema({"page": P_PAGE, "to_page": {"type": "string", "description": "the other page's title or id"}, "refs": {"type": "array", "items": {"type": "string"}}, "label": {"type": "string"}}, ["to_page", "refs"]), t_topage),
    ("hyimg_hist", "The last saved versions of a page (id, who, label). hyimg_restore takes an id.", schema({"page": P_PAGE, "n": {"type": "integer", "minimum": 1, "maximum": 100}}), t_hist),
    ("hyimg_restore", "Put a page back to a saved version. Check first that the owner changed nothing since, or his edit is lost too.", schema({"page": P_PAGE, "id": {"type": "string"}}, ["id"]), t_restore),
    ("hyimg_save", "Copy (or move) image files into a library folder of the project, leaving out every picture the library already has (same bytes) and bringing each file's json sidecar.",
     schema({"files": {"type": "array", "items": {"type": "string"}, "description": "absolute paths"}, "to": {"type": "string", "description": "a folder inside the library, e.g. arc/2610061200-p7"},
             "move": {"type": "boolean"}}, ["files", "to"]), t_save),
]
BY_NAME = {t[0]: t for t in TOOLS}


# ---------------------------------------------------------------- skills: resources and prompts
def skills():
    out = []
    for n in sorted(os.listdir(SKILLS)) if os.path.isdir(SKILLS) else []:
        f = os.path.join(SKILLS, n, "SKILL.md")
        if not os.path.isfile(f): continue
        text = open(f, encoding="utf-8").read()
        m = re.match(r"---\n(.*?)\n---", text, re.S); desc = ""
        if m:
            d = re.search(r"^description:\s*(.+)$", m.group(1), re.M); desc = d.group(1).strip() if d else ""
        out.append({"name": n, "description": desc, "path": f})
    return out


def resources():
    L = [{"uri": "hyimg://features", "name": "features", "title": "Что умеет Hyimg (feature catalog)", "mimeType": "application/json",
          "description": "Every Hyimg feature: how the owner uses it, how an agent does it, which skill explains it"},
         {"uri": "hyimg://agent", "name": "agent", "title": "Agent guide of the current project (/agent)", "mimeType": "text/markdown",
          "description": "What is open, the project's rules, plugins, skills, the catalog: the same as hyimg_guide"}]
    L += [{"uri": f"hyimg://skills/{s['name']}", "name": s["name"], "title": f"Skill {s['name']}", "mimeType": "text/markdown", "description": s["description"][:400]} for s in skills()]
    return L


def read_resource(uri):
    if uri == "hyimg://features": return open(FEATURES, encoding="utf-8").read(), "application/json"
    if uri == "hyimg://agent" or uri.startswith("hyimg://agent/"):
        port, _ = pick(urllib.request.unquote(uri[len("hyimg://agent/"):]) if uri.startswith("hyimg://agent/") else None)
        return get_text(port, "/agent"), "text/markdown"
    m = re.fullmatch(r"hyimg://skills/([a-z0-9-]+)", uri)
    if m:
        f = os.path.join(SKILLS, m.group(1), "SKILL.md")
        if os.path.isfile(f): return open(f, encoding="utf-8").read(), "text/markdown"
    raise KeyError(uri)


def prompts():
    L = [{"name": "hyimg-start", "title": "Start work in a Hyimg project", "description": "Orient in a Hyimg project before doing anything: guide, rules, skills, catalog",
          "arguments": [{"name": "project", "description": "project name, id or port", "required": False}]}]
    L += [{"name": s["name"], "title": f"Skill {s['name']}", "description": s["description"][:400], "arguments": []} for s in skills()]
    return L


def get_prompt(name, args):
    if name == "hyimg-start":
        text = ("You work in the owner's Hyimg project" + (f" «{args.get('project')}»" if args.get("project") else "") + ". First call hyimg_guide"
                + (f" with project={args.get('project')}" if args.get("project") else "") + " and read it whole: the project's rules win over"
                " general ones. Pick the skill for the task from its list (hyimg, hyimg-board, hyimg-generate) and read it"
                " (resource hyimg://skills/<name>). Look a feature up with hyimg_features before guessing. Change boards only with hyimg_do,"
                " hyimg_props, hyimg_topage, then hyimg_check.")
        return {"description": "Start in a Hyimg project", "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
    s = next((s for s in skills() if s["name"] == name), None)
    if not s: raise KeyError(name)
    text = f"Follow the Hyimg skill «{name}» below for this task.\n\n" + open(s["path"], encoding="utf-8").read()
    return {"description": s["description"][:400], "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}


# ---------------------------------------------------------------- JSON-RPC over stdio
def handle(msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if method is None or mid is None and method.startswith("notifications/"): return None
    try:
        if method == "initialize":
            CLIENT["name"] = ((params.get("clientInfo") or {}).get("name") or "")[:40]
            want = params.get("protocolVersion")
            return {"protocolVersion": want if want in PROTOCOLS else PROTOCOLS[0],
                    "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False, "subscribe": False}, "prompts": {"listChanged": False}},
                    "serverInfo": {"name": "hyimg", "title": "Hyimg", "version": VERSION}, "instructions": INSTRUCTIONS}
        if method == "ping": return {}
        if method == "tools/list":
            return {"tools": [{"name": n, "description": d, "inputSchema": s} for n, d, s, _ in TOOLS]}
        if method == "tools/call":
            t = BY_NAME.get(params.get("name"))
            if not t: raise LookupError(f"unknown tool {params.get('name')}")
            a = params.get("arguments") or {}
            miss = [k for k in t[2].get("required", []) if a.get(k) in (None, "", [])]
            if miss: return {"content": [{"type": "text", "text": "нужно: " + ", ".join(miss)}], "isError": True}
            try: text, bad = t[3](a)
            except Pick as e: text, bad = str(e), True
            except Exception as e: text, bad = f"{type(e).__name__}: {e}", True
            return {"content": [{"type": "text", "text": text}], "isError": bool(bad)}
        if method == "resources/list": return {"resources": resources()}
        if method == "resources/templates/list":
            return {"resourceTemplates": [{"uriTemplate": "hyimg://agent/{project}", "name": "agent-of-project", "title": "Agent guide of a named project", "mimeType": "text/markdown"}]}
        if method == "resources/read":
            uri = params.get("uri", "")
            try: text, mime = read_resource(uri)
            except KeyError: raise LookupError(f"no resource {uri}")
            except Pick as e: text, mime = str(e), "text/plain"
            return {"contents": [{"uri": uri, "mimeType": mime, "text": text}]}
        if method == "prompts/list": return {"prompts": prompts()}
        if method == "prompts/get":
            try: return get_prompt(params.get("name"), params.get("arguments") or {})
            except KeyError: raise LookupError(f"no prompt {params.get('name')}")
        if method == "logging/setLevel": return {}
        return {"__error": (-32601, f"method not found: {method}")}
    except LookupError as e:
        return {"__error": (-32602, str(e))}
    except Exception as e:
        return {"__error": (-32603, f"{type(e).__name__}: {e}")}


def main():
    if "--list-tools" in sys.argv:
        for n, d, s, _ in TOOLS: print(f"{n}: {d}\n")
        return
    out = sys.stdout.buffer
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", "replace").strip()
        if not line: continue
        try: msg = json.loads(line)
        except ValueError:
            out.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}).encode() + b"\n"); out.flush(); continue
        batch = msg if isinstance(msg, list) else [msg]
        replies = []
        for m in batch:
            if not isinstance(m, dict): continue
            res = handle(m)
            if res is None or m.get("id") is None: continue
            if "__error" in res: replies.append({"jsonrpc": "2.0", "id": m["id"], "error": {"code": res["__error"][0], "message": res["__error"][1]}})
            else: replies.append({"jsonrpc": "2.0", "id": m["id"], "result": res})
        if replies:
            out.write(json.dumps(replies if isinstance(msg, list) else replies[0], ensure_ascii=False).encode("utf-8") + b"\n"); out.flush()


if __name__ == "__main__":
    main()
