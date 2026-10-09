"""Fixtures of the unit tests; the throwaway library and the module imports are in unit_env.py (a module of its own name, so the
tests import its paths without mixing it up with tests/conftest.py)."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

# The guard of tests/procguard.py before anything is imported: pytest tests/unit does not load tests/conftest.py, and without it
# config.py took ~/Library/Caches/Hyimg, the thumbnails of the throwaway board went there (2026-10-08)
if "procguard" not in sys.modules:
    _spec = importlib.util.spec_from_file_location("procguard", Path(__file__).resolve().parents[1] / "procguard.py")
    sys.modules["procguard"] = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(sys.modules["procguard"])
procguard = sys.modules["procguard"]
procguard.install()

from unit_env import BASE, LIB, MOUNT, OUTSIDE, PROJECT, SETTINGS, dedup, history, server  # noqa: E402


def _empty(d):
    for p in Path(d).iterdir():
        if p.is_dir() and not p.is_symlink(): shutil.rmtree(p)
        else: p.unlink()


@pytest.fixture
def lib(monkeypatch):
    """the library root (Path), empty, with an empty state folder <lib>/_review/boards and an empty thumbnail folder in the session's
    cache (server.THUMBS, thumbcache.py); the server's caches forgotten"""
    _empty(LIB); _empty(MOUNT); _empty(OUTSIDE)
    (LIB / "_review" / "boards").mkdir(parents=True)
    shutil.rmtree(server.THUMBS, ignore_errors=True); Path(server.THUMBS).mkdir(parents=True)   # main() makes it before serving
    SETTINGS.unlink(missing_ok=True)
    monkeypatch.setenv("HY_TEST_ONLY_PLUGINS", "1")
    monkeypatch.delenv("HYIMG_PLUGINS", raising=False)
    server._PKINDS[:] = [0.0, {}]
    for cache in (server._SIDE, server._SIZES, server._STAMPS, server.DEFAULT_APPS, server.APP_ICONS, server._PLUGIN_SRV, server._SYNCED, server._NC, history._MISS):
        cache.clear()
    server._LIST.update(items=None, key=None, t=0, busy=False)
    monkeypatch.setattr(server, "SNAP", str(BASE / "snap" / "library.json"))
    monkeypatch.setattr(server, "snap_save", lambda items: None)   # the library list's disk copy lives in ~/Library/Caches: never written here
    monkeypatch.setattr(server, "snap_load", lambda: None)
    dedup._IDX = None
    yield LIB
    dedup._IDX = None


@pytest.fixture
def png_bytes():
    """a valid PNG of w x h"""
    import io
    from PIL import Image

    def make(w=8, h=6, color=(200, 30, 30)):
        buf = io.BytesIO(); Image.new("RGB", (w, h), color).save(buf, "PNG"); return buf.getvalue()
    return make


@pytest.fixture
def plugin_root(lib, tmp_path, monkeypatch):
    """a folder of plugins named in HYIMG_PLUGINS; add(name, manifest, files) makes one"""
    root = tmp_path / "plugins"; root.mkdir()
    monkeypatch.setenv("HYIMG_PLUGINS", str(root))
    server._PKINDS[:] = [0.0, {}]

    def add(name, manifest, files=None, raw=None):
        d = root / name; d.mkdir()
        (d / "manifest.json").write_text(raw if raw is not None else json.dumps(manifest))
        for rel, text in (files or {}).items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True); (d / rel).write_text(text)
        return d
    add.root = root
    return add


def pytest_sessionfinish(session, exitstatus):   # once a session, with tests/conftest.py or without it
    procguard.finish(session)
