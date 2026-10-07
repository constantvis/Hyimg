# A folder's colour in the library's tree, one project's own (owner 2026-10-06: «add ability to change color of folders ... so we can
# color some folders and they apply to everything underneath, but it's not object color, it's rather just color of the folder for
# navigating better»). Only a mark for finding your way: no file and no frame changes. The file is <state root>/folders.json,
#   {"colors": {"renderings": "blue", "renderings/261006-M17-grain": "pink"}}
# a folder's path in the library and one of the board's note colours (canvas.html NCOL, ui/menu.js HY_COLORS). The folders under a
# coloured one take its colour on the page unless they have their own. Written atomically (a temp file, then a rename).
import json
import os
import re

import config

FILE = os.path.join(config.HERE, "folders.json")
COLORS = ("yellow", "orange", "red", "pink", "purple", "blue", "green", "grey")
MAX = 5000


def _clean_path(x):
    return isinstance(x, str) and 0 < len(x) <= 1000 and not re.search(r"[\x00-\x1f]", x) and not x.startswith("/") and ".." not in x.split("/")


def read():
    """{"colors": {path: colour}}"""
    try:
        d = json.load(open(FILE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"colors": {}}
    c = d.get("colors") if isinstance(d, dict) else None
    if not isinstance(c, dict):
        return {"colors": {}}
    return {"colors": {p: v for p, v in c.items() if _clean_path(p) and v in COLORS}}


def write(path, color):
    """sets one folder's colour, or takes it off with None / ""; raises ValueError for a bad path or colour"""
    if not _clean_path(path) or (color and color not in COLORS):
        raise ValueError("folder colour")
    cur = read()["colors"]
    if color:
        cur[path] = color
    else:
        cur.pop(path, None)
    if len(cur) > MAX:
        raise ValueError("too many")
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"colors": cur}, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, FILE)
    return {"colors": cur}
