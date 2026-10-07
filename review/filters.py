# The library's filter bar, one project's own data (owner 2026-10-06: «let's make one block with a filter where some default filters
# already are, and they can be pinned in the filter itself ... each new project can have its own set of tags besides the standard
# built-in ones»).
#   pins    which filters stand in the dock's capsule, a list of filter ids in the order shown; the file is <state root>/filters.json,
#           {"pins": [...]}. No file (or no "pins") means the page picks the defaults from what the project's frames hold.
#   tags    a project's own tag: a name, the words that find it and a group, appended to this board's "tags" rules (config.py RULES_FILE,
#           the board's key) as one more [group, tag, regex] entry; the built-in rules and the owner's own entries stay as they are.
# Both are written atomically (a temp file, then a rename), the rules file under a lock because every project's server shares it.
import fcntl
import json
import os
import re

import config

FILE = os.path.join(config.HERE, "filters.json")
MAX_PINS = 300


def _clean_id(x):
    return isinstance(x, str) and 0 < len(x) <= 200 and not re.search(r"[\x00-\x1f]", x)


def read():
    """{"pins": [ids] | None}: None when this project has not chosen yet"""
    try:
        d = json.load(open(FILE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"pins": None}
    pins = d.get("pins") if isinstance(d, dict) else None
    if not isinstance(pins, list):
        return {"pins": None}
    return {"pins": list(dict.fromkeys(p for p in pins if _clean_id(p)))[:MAX_PINS]}


def write(pins):
    """keeps the pinned ids (order kept, copies dropped); raises ValueError for anything but a list of ids"""
    if not isinstance(pins, list) or not all(_clean_id(p) for p in pins):
        raise ValueError("pins")
    out = list(dict.fromkeys(pins))[:MAX_PINS]
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"pins": out}, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, FILE)
    return {"pins": out}


def words_regex(words):
    """the words to find as one regex: each one where a word starts («bird» finds «birds», «birdcage»), any of them; punctuation is taken literally"""
    ws = [w.strip() for w in words if isinstance(w, str) and w.strip()]
    if not ws or len(ws) > 40 or any(len(w) > 60 for w in ws):
        raise ValueError("words")
    return "|".join("(?<!\\w)" + re.escape(w) for w in ws)


def add_tag(group, tag, words):
    """appends [group, tag, regex] to this board's tag rules in the rules file; returns the entry. ValueError: bad input; KeyError: the
    board already has a tag of this name"""
    group, tag = (group or "").strip(), (tag or "").strip()
    if isinstance(words, str):
        words = re.split(r"[,;\n]", words)
    if not tag or len(tag) > 60 or not group or len(group) > 40:
        raise ValueError("name")
    rx = words_regex(words)
    re.compile(rx, re.I)
    path = config.RULES_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            doc = {}
        if not isinstance(doc, dict):
            doc = {}
        key = next((k for k in doc if str(k).lower() == config.PROJECT_ID.lower()), config.PROJECT_ID)
        board = doc.get(key)
        if not isinstance(board, dict):
            board = doc[key] = {}
        rules = board.get("tags")
        if not isinstance(rules, list):
            rules = board["tags"] = []
        # the tags this board already gets: its own and the shared "*" ones
        known = {r[1] for part in (doc.get("*"), board) if isinstance(part, dict) for r in part.get("tags") or [] if isinstance(r, list) and len(r) == 3}
        if tag in known:
            raise KeyError(tag)
        rules.append([group, tag, rx])
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    return [group, tag, rx]


def reload_rules():
    """the rules file as it stands now (what tags.configure takes)"""
    return config._rules()
