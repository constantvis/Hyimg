#!/usr/bin/env python3
"""What the owner has in front of him in Hyimg: which project tab, and what is selected there.

The app writes active.json next to projects.json on every tab switch; the pages of the project write <stateRoot>/live.json
on every selection. This joins the two, so an agent can act on "these pictures" in whatever project is open.
  python3 scripts/active.py            project + selection + what is on screen
  python3 scripts/active.py --paths    only the selected picture paths (canvas selection, else library picks)
  python3 scripts/active.py --json     raw state
  python3 scripts/active.py --link URL what a canvas link points at (http://: the project by the link's port; hyimg://board/<id>: by its id)
Options: --catalog-dir DIR (default ~/Library/Application Support/Hyimg)
"""
import json, os, subprocess, sys, time, urllib.parse

args = sys.argv[1:]
cat = os.path.expanduser("~/Library/Application Support/Hyimg")
if "--catalog-dir" in args:
    k = args.index("--catalog-dir"); cat = args[k + 1]; del args[k:k + 2]
try:
    active = json.load(open(os.path.join(cat, "active.json"), encoding="utf-8"))
except OSError:
    sys.exit("active.json нет: Hyimg еще не запускался с этой версией")
projects = {p["id"]: p for p in json.load(open(os.path.join(cat, "projects.json"), encoding="utf-8"))}
tabs = [projects[t]["name"] for t in active.get("tabs", []) if t in projects]
# how each open board is (native/Switcher.swift, 2026-10-08): in front, warm (its page kept), asleep (page gone, its server answers hy.py)
STATE = {"open": "открыта", "warm": "теплая", "sleeping": "спит, сервер работает", "waking": "просыпается", "loading": "открывается"}
if active.get("boards"): tabs = [f"{b['name']} ({STATE.get(b.get('state'), b.get('state'))})" for b in active["boards"]]
ago = int(time.time() - active.get("t", 0))
if "--json" in args and "--link" not in args and active.get("view") != "project":
    print(json.dumps(active, ensure_ascii=False, indent=1)); sys.exit()
if "--link" in args:   # the owner sent a link: the project is the one serving that port, or the board of a hyimg:// link, whatever tab is open
    u = urllib.parse.urlparse(args[args.index("--link") + 1])
    if u.scheme == "hyimg":   # hyimg://board/<board id>?page=…&obj=… (native/Links.swift)
        bid = u.path.strip("/").lower()
        # the catalog id, or the folder id (board.json, the same on both Macs of one Dropbox account, owner 2026-10-08)
        def ids(q):
            out = [q["id"].lower(), str(q.get("folderId") or "").lower()]
            try: out.append(str(json.load(open(os.path.join(q["stateRoot"], "board.json"), encoding="utf-8")).get("id", "")).lower())
            except (OSError, ValueError, AttributeError): pass
            return out
        hit = [q for q in projects.values() if u.netloc == "board" and bid in ids(q)]
        if not hit: sys.exit(f"в каталоге нет доски {bid or u.netloc}")
    else:
        hit = [q for q in projects.values() if u.port in (q.get("port"), q.get("compatibilityPort"))]
        if not hit: sys.exit(f"в каталоге нет проекта на порту {u.port}")
    active = {"view": "project", "project": hit[0], "t": time.time()}
if active.get("view") != "project":
    if "--paths" in args: sys.exit(0)
    print(f"Hyimg: открыта главная ({ago} с назад). Вкладки: {', '.join(tabs) or 'нет'}")
    sys.exit()
p = active["project"]
if "--paths" not in args and "--json" not in args and "--link" not in args:
    print(f"Hyimg: проект «{p['name']}» ({ago} с назад), вкладки: {', '.join(tabs)}")
    print(f"  папка: {p['libraryRoot']}")
sys.stdout.flush()
env = dict(os.environ, HYIMG_LIBRARY_ROOT=p["libraryRoot"], HYIMG_STATE_ROOT=p["stateRoot"], HYIMG_PROJECT_ID=p["id"])
if p.get("styleRefs"): env["HYIMG_STYLE_REFS"] = p["styleRefs"]
live = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "review", "live.py")
sys.exit(subprocess.call([sys.executable, live, *args], env=env))
