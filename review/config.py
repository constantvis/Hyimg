"""Paths shared by the server and its command-line helpers."""
import json
import os
import re
import uuid
from typing import Final

CODE_DIR: Final = os.path.dirname(os.path.abspath(__file__))


def absolute_setting(name: str, default: str = "") -> str:
    value = os.environ.get(name, default)
    if not value or not os.path.isabs(value):
        raise SystemExit(f"{name} must be an absolute path")
    return os.path.realpath(value)


W: Final = absolute_setting("HYIMG_LIBRARY_ROOT")
HERE: Final = absolute_setting("HYIMG_STATE_ROOT", os.path.join(W, "_review"))
BOARDS: Final = os.path.join(HERE, "boards")
NOTES: Final = os.path.join(W, "notes")
STYLE_REFS: Final = absolute_setting("HYIMG_STYLE_REFS") if os.environ.get("HYIMG_STYLE_REFS") else ""
PROJECT_ID: Final = os.environ.get("HYIMG_PROJECT_ID", "")
try:
    uuid.UUID(PROJECT_ID)
except ValueError as exc:
    raise SystemExit("HYIMG_PROJECT_ID must be a UUID") from exc
if not os.path.isdir(W):
    raise SystemExit("HYIMG_LIBRARY_ROOT must be an existing directory")

# A board's own library rules (owner 2026-10-05: «the public version is an empty app without projects»): folders taken out of the
# library, outside folders shown as collections, collection titles, theme tags. They are the person's data, not code. The file
# ~/Library/Application Support/Hyimg/library-rules.json (HYIMG_LIBRARY_RULES names another) maps a board's id to its rules; "*" holds
# rules for every board, a board's own keys win. Without the file the library shows every picture under the board's folder.
#
# {"<board id>": {"skip": [folder names never scanned, at any depth], "hide": [folder paths hidden with what is in them],
#                 "hideNamed": [folder names hidden at any depth], "hideFolderPrefixes": [a folder whose name starts so shows no files],
#                 "skipFilePrefixes": [file names that are intermediates, not frames], "rootFiles": false (files right in the folder
#                 are not frames), "mounts": [{"prefix": "ext/<name>", "path": absolute or inside the board's reference folder,
#                 "title", "model", "sets": true (each subfolder its own collection, titles from sources.json)}],
#                 "titles": {folder: title}, "titlesFrom": "<file in the library with ("folder", "title") pairs>",
#                 "tags": [[group, tag, regex]], "tagCodes": {name part: tag}, "pinnedTags": [[group, tag]]}}
RULES_FILE: Final = os.environ.get("HYIMG_LIBRARY_RULES") or os.path.expanduser("~/Library/Application Support/Hyimg/library-rules.json")


def _rules() -> dict:
    try:
        data = json.load(open(RULES_FILE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    by_id = {str(k).lower(): v for k, v in data.items()}
    out = {}
    for part in (by_id.get("*"), by_id.get(PROJECT_ID.lower())):
        if isinstance(part, dict):
            out.update(part)
    return out


RULES: Final = _rules()


def _mounts() -> dict:
    """outside folders shown as collections: {"ext/<name>": (folder, title, model)}"""
    out = {}
    for m in RULES.get("mounts") or []:
        prefix, path = (m.get("prefix"), m.get("path")) if isinstance(m, dict) else (None, None)
        if not isinstance(prefix, str) or not re.fullmatch(r"ext/[A-Za-z0-9_.-]+", prefix) or not isinstance(path, str) or not path:
            continue
        if not os.path.isabs(path):
            if not STYLE_REFS:
                continue
            path = os.path.join(STYLE_REFS, path)
        out[prefix] = (os.path.normpath(path), m.get("title") or prefix[4:], m.get("model") or "")
    if "mounts" not in RULES and STYLE_REFS and os.path.isdir(STYLE_REFS):
        # a board registered with a reference folder and no rules of its own: each folder in it is a collection
        for d in sorted(os.listdir(STYLE_REFS)):
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", d) and os.path.isdir(os.path.join(STYLE_REFS, d)):
                out["ext/" + d] = (os.path.join(STYLE_REFS, d), d, "")
    return out


MOUNTS: Final = _mounts()
MOUNT_SETS: Final = {m["prefix"] for m in RULES.get("mounts") or [] if isinstance(m, dict) and m.get("sets") and m.get("prefix") in MOUNTS}


def real(rel: str) -> str:
    """the file behind a library path: a mount's folder for "ext/<name>/...", the library otherwise"""
    for pre, (root, _t, _m) in MOUNTS.items():
        if rel.startswith(pre + "/"):
            return os.path.join(root, rel[len(pre) + 1:])
    return os.path.join(W, rel)
