"""Shared fixtures for the in-browser unit tests: one temporary Hyimg server for the whole folder and one Chromium per module.

The server follows run_server in tests/test_shortcuts.py: a temporary library and state, a free port, an environment without the
inherited HYIMG_* and REVIEW_* variables, its own settings file (English), terminated in the end. tests/conftest.py already sets
HY_TEST_ONLY_PLUGINS=1, so no plugin of this Mac is loaded. Nothing here touches the owner's running app, boards or library.

Playwright is started per module, not per session: the older tests open their own sync_playwright(), and two sync sessions cannot
be alive at once in one process."""
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request
import uuid
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# the library: folders chosen for the tree's order (A–Z, numbers in their order, a parent before its subfolders) and for a parent that
# holds no picture of its own (c, only c/d)
FOLDERS = ["a", "a/x", "a/y", "b", "img 10", "img 2", "Zed", "c/d"]


def png(w, h):   # a plain white picture; every folder gets its own size, equal files would count as one
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * w for _ in range(h))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def hy_server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("unit_browser")
    lib, state = tmp / "lib", tmp / "state"
    (state / "boards").mkdir(parents=True)
    for n, folder in enumerate(FOLDERS):
        (lib / folder).mkdir(parents=True, exist_ok=True)
        (lib / folder / "0.png").write_bytes(png(40 + 6 * n, 60))
    items = {"i0": {"path": "a/0.png", "x": 0, "y": 0, "w": 320, "ar": 40 / 60, "crop": None}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    (tmp / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    port = free_port()
    log = open(tmp / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    log.seek(0)
                    pytest.fail("the test server did not start:\n" + log.read()[-2000:])
                time.sleep(0.05)   # polling the health check, not waiting for time to pass
        yield f"http://127.0.0.1:{port}"
    finally:
        process.terminate(); process.wait(5); log.close()


@pytest.fixture(scope="module")
def hy_browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    p = sync_api.sync_playwright().start()
    try:
        browser = p.chromium.launch()
    except Exception as error:
        p.stop()
        pytest.skip(f"no Chromium for Playwright: {error}")
    yield browser
    browser.close(); p.stop()


def open_page(browser, url, ready):
    """A fresh page at url, returned once the JavaScript condition ready holds; page errors are collected on page.errors."""
    page = browser.new_page(viewport={"width": 1200, "height": 800})
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.goto(url)
    page.wait_for_function(ready, timeout=15000)
    return page


@pytest.fixture(scope="module")
def lib_page(hy_server, hy_browser):
    """The library (review/v2.html) alone, without the canvas beside it: its functions are globals of its one big inline script."""
    page = open_page(hy_browser, hy_server + "/?view=lib",
                     "() => typeof stepCollection === 'function' && typeof items !== 'undefined' && items.length > 0 && document.querySelectorAll('#coll option').length > 1")
    yield page
    page.close()


@pytest.fixture(scope="module")
def board_page(hy_server, hy_browser):
    """The board (review/canvas.html) as the library's iframe loads it (embed=1: no side library of its own, the breadcrumb shown),
    opened at the top level here so the module needs one page only. ?board=main would hide the breadcrumb (FIXED), which the titles'
    plates line up with."""
    page = open_page(hy_browser, hy_server + "/canvas.html?embed=1",
                     "() => typeof stickTitles === 'function' && typeof board !== 'undefined' && board.items && board.items.i0 && EL.get('i0')"
                     " && document.getElementById('crumb').getBoundingClientRect().width > 0")
    yield page
    page.close()
