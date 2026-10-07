"""Unit tests of the server's Python modules: no browser, no server process, a few seconds for the whole folder.

config.py reads its settings from the environment once, when it is imported, and the other modules take its paths by name. So this
file points the environment at a throwaway library before anything is imported, imports every module once, then puts the
environment back as it was (the end-to-end tests start their own servers with their own variables). Each test gets the library
and the state folder empty again (fixture `lib`); modules that keep their own paths (filters, foldercolors, dedup, history, events)
are pointed at the test's tmp_path instead. Nothing here reads or writes the owner's files, settings, rules or plugins.
"""
import atexit
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
REVIEW = Path(__file__).resolve().parents[2] / "review"
sys.path.insert(0, str(REVIEW))

BASE = Path(os.path.realpath(tempfile.mkdtemp(prefix="hyimg-unit-")))
atexit.register(shutil.rmtree, BASE, True)
LIB = BASE / "lib"
OUTSIDE = BASE / "outside"          # a folder next to the library: never served
MOUNT = BASE / "mounted"            # an outside folder the rules show as a collection (ext/refs)
RULES_FILE = BASE / "library-rules.json"
SETTINGS = BASE / "app-settings.json"
PROJECT = "6f1c0d2e-3a4b-4c5d-8e9f-0a1b2c3d4e5f"
for d in (LIB, OUTSIDE, MOUNT):
    d.mkdir(parents=True)
# The board's library rules the server reads at import: every kind of rule once, so the scan's filters can be tested
RULES = {
    "*": {"tags": [["Theme", "Shared", r"\bshared\b"]]},
    PROJECT.upper(): {   # the board's key in any case
        "skip": ["_skipme"], "hide": ["hidden/deep"], "hideNamed": ["storyboard"], "hideFolderPrefixes": ["mask"],
        "skipFilePrefixes": ["raw-"], "titles": {"a": "Title A"},
        "tags": [["Who", "Bird", r"\bbirds?\b"], ["Who", "Broken", "("]],
        "tagCodes": {"cr": "Crash test"}, "pinnedTags": [["Who", "Bird"]],
        "mounts": [{"prefix": "ext/refs", "path": str(MOUNT), "title": "Refs", "model": "pinterest"},
                   {"prefix": "../bad", "path": str(OUTSIDE)}, {"prefix": "ext/rel", "path": "relative/needs-style-refs"}],
    },
}
RULES_FILE.write_text(json.dumps(RULES))

_ENV = {"HYIMG_LIBRARY_ROOT": str(LIB), "HYIMG_STATE_ROOT": str(LIB / "_review"), "HYIMG_PROJECT_ID": PROJECT,
        "HYIMG_LIBRARY_RULES": str(RULES_FILE), "HYIMG_SETTINGS": str(SETTINGS), "HYIMG_PLUGINS": "", "HY_TEST_ONLY_PLUGINS": "1",
        "HYIMG_VIDEO_CACHE": str(BASE / "video-cache")}
_saved = {k: os.environ.get(k) for k in list(_ENV) + ["HYIMG_STYLE_REFS"]}
os.environ.update(_ENV)
os.environ.pop("HYIMG_STYLE_REFS", None)
try:
    import config, tags, filters, foldercolors, dedup, history, events, pdfpages, foldersync, server  # noqa: E401,F401
finally:
    for k, v in _saved.items():
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v
assert config.W == str(LIB), "the modules must run on the throwaway library"
