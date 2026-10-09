"""hy.py link: the owner's links to things on a board (owner 2026-10-07: «Можно ли сделать ссылку, которую нажимаешь, и открывается
приложение? ... При этом чтобы оставалась возможность классической ссылки»).

  hy.py link REF... [at=x,y,z] [--page P]   two lines: the app's link first, then the browser's
      hyimg://board/<board id>?page=<page>&obj=<id,id>&dir=<folder in Dropbox>   opens Hyimg on that board, its page, the objects selected and centred
      http://127.0.0.1:<port>/?view=canvas&page=…&obj=…    the same in a browser (the port changes between runs, the board's id does not)
  hy.py link                                  the page itself;  hy.py link at=x,y,z  a view of it

REF is what hy.py names everywhere: an id from find or map, a group's title, a note's first line, a heading. Give the owner the hyimg://
link: a click opens the app (native/Links.swift checks it). The board's id is the one in its folder (<state>/board.json, GET /api/health
boardId, owner 2026-10-08: two Macs on one Dropbox account, each with its own catalog), else its id in this Mac's catalog (projectId);
dir is the board's folder relative to the Dropbox root, so the other Mac finds a board it has not added yet. A server with neither
(a test, one started by hand) gets only the browser's link.
"""
import re
import urllib.parse

ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
CAM = re.compile(r"-?[\d.]+,-?[\d.]+,[\d.]+")
# a folder relative to the Dropbox root as native/Links.swift accepts it: parts without «.», «..», empty ones or control characters
DIR = lambda s: bool(s) and len(s) <= 1024 and not any(p in ("", ".", "..") or any(ord(c) < 32 or c == "\x7f" for c in p) for p in s.split("/"))


def links(project, port, page, obj=(), at=None, folder=""):
    """(app link or "", browser link) of a page, its objects or a camera, as ui/applink.js writes them; folder: dir, the app's link only"""
    q = {"page": page} if page and ID.fullmatch(page) else {}
    obj = [i for i in obj if ID.fullmatch(i)]
    if obj: q["obj"] = ",".join(obj)
    if at and CAM.fullmatch(at): q["at"] = at
    qs = urllib.parse.urlencode({**q, **({"dir": folder} if DIR(folder) else {})}, safe=",/", quote_via=urllib.parse.quote)
    app = f"hyimg://board/{project.lower()}" + (f"?{qs}" if qs else "") if project and UUID.fullmatch(project) else ""
    return app, f"http://127.0.0.1:{port}/?" + urllib.parse.urlencode({"view": "canvas", **q}, safe=",")


def main(args, page, api, resolve, base):
    at = next((a[3:] for a in args if a.startswith("at=")), None)
    refs = [a for a in args if not a.startswith("at=")]
    if at is not None and not CAM.fullmatch(at): raise SystemExit("at=x,y,z: три числа, зум больше 0")
    if page is None:   # the page the owner is looking at
        try: page = (api("/api/live")[1].get("canvas") or {}).get("page") or "main"
        except Exception: page = "main"
    ids = []
    if refs:
        code, b = api(f"/api/board?name={urllib.parse.quote(page)}")
        if code != 200 or not isinstance(b, dict): raise SystemExit(f"нет страницы {page}")
        for ref in refs:
            ref = ref[1:] if ref.startswith("@") else ref
            if ref in b["items"] or ref in b["groups"]: ids.append(ref); continue
            k, id, _, _ = resolve(b, ref)
            ids.append(id.split("/")[0])   # a timeline's dot: the timeline
    code, h = api("/api/health")
    h = h if code == 200 and isinstance(h, dict) else {}
    port = h.get("port") or urllib.parse.urlparse(base).port
    app, web = links(h.get("boardId") or h.get("projectId") or "", port, page, list(dict.fromkeys(ids)), at, h.get("dir") or "")
    if app: print(app)
    print(web)
    if not app: print("(этой доски нет в каталоге приложения: ссылки hyimg:// нет, только браузер)")
