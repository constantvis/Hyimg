#!/usr/bin/env python3
"""What the owner has in front of him in Hyimg: which project tab, and what is selected there.

The app writes active.json next to projects.json on every tab switch; the pages of the project write <stateRoot>/live.json
on every selection. This joins the two, so an agent can act on "these pictures" in whatever project is open.
  python3 scripts/active.py            project + selection + what is on screen
  python3 scripts/active.py --paths    only the selected picture paths (canvas selection, else library picks)
  python3 scripts/active.py --json     raw state
  python3 scripts/active.py --link URL what a canvas link points at (the project is found by the link's port)
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
ago = int(time.time() - active.get("t", 0))
if "--json" in args and "--link" not in args and active.get("view") != "project":
    print(json.dumps(active, ensure_ascii=False, indent=1)); sys.exit()
if "--link" in args:   # the owner sent a link: the project is the one serving that port, whatever tab is open
    port = urllib.parse.urlparse(args[args.index("--link") + 1]).port
    hit = [q for q in projects.values() if port in (q.get("port"), q.get("compatibilityPort"))]
    if not hit: sys.exit(f"в каталоге нет проекта на порту {port}")
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
