"""Hyimg's MCP server (mcp/server.py, 2026-10-06): an agent that only connects to it sees the operations as tools, the skills and the
feature catalog as resources and prompts. These tests start a throwaway Hyimg server on a temporary library, then the MCP server as a
client would (stdio, one JSON-RPC message per line), list its tools and call them against that library."""
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

ROOT = Path(__file__).resolve().parents[1]


def png(c):
    raw = b"".join(b"\x00" + bytes(c) * 40 for _ in range(60))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 40, 60, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


@pytest.fixture
def app(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "lib/_review"
    (lib / "batch").mkdir(parents=True)
    for n in range(4): (lib / "batch" / f"{n}.png").write_bytes(png((30 + 50 * n, 90, 140)))
    (state / "boards").mkdir(parents=True)
    items = {f"o{n}": {"path": f"batch/{n}.png", "x": n * 344, "y": 0, "w": 320, "ar": 2 / 3} for n in range(2)}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "removed": {},
        "groups": {"g1": {"title": "Старые", "x": -480, "y": -480, "w": 2 * 344 - 24 + 960, "h": 480 + 960, "members": list(items)}}}))
    (state / "boards/p2.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "Главная"}, {"id": "p2", "title": "Вторая"}]}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "ru"}))
    port, pid = free_port(), str(uuid.uuid4())
    cat = tmp_path / "catalog"; cat.mkdir()
    (cat / "projects.json").write_text(json.dumps([{"id": pid, "name": "Тестовая доска", "libraryRoot": str(lib), "stateRoot": str(state), "port": port}]))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_PROJECT_ID=pid, HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    mcp_env = {k: v for k, v in os.environ.items() if not k.startswith("HYIMG_")}
    mcp_env.update(HYIMG_CATALOG_DIR=str(cat), PYTHONDONTWRITEBYTECODE="1")
    try:
        yield port, mcp_env, lambda page="main": json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/board?name={page}"))
    finally:
        proc.terminate(); proc.wait(5); log.close()


class Client:
    def __init__(self, env):
        self.p = subprocess.Popen([sys.executable, str(ROOT / "mcp/server.py")], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.n = 0

    def send(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method, **({"params": params} if params is not None else {})}
        if not notify: self.n += 1; msg["id"] = self.n
        self.p.stdin.write((json.dumps(msg) + "\n").encode()); self.p.stdin.flush()
        if notify: return None
        r = json.loads(self.p.stdout.readline())
        assert r["id"] == self.n and r["jsonrpc"] == "2.0"
        return r

    def call(self, name, **args):
        r = self.send("tools/call", {"name": name, "arguments": args})
        res = r["result"]; return res["content"][0]["text"], res["isError"]

    def close(self):
        self.p.stdin.close(); self.p.wait(5)


@pytest.fixture
def client(app):
    c = Client(app[1])
    r = c.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1"}})
    assert r["result"]["protocolVersion"] == "2025-06-18" and r["result"]["serverInfo"]["name"] == "hyimg"
    assert "hyimg_guide" in r["result"]["instructions"]
    c.send("notifications/initialized", notify=True)
    yield c
    c.close()


def test_tools_are_listed_with_schemas(client):
    tools = client.send("tools/list")["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"hyimg_guide", "hyimg_features", "hyimg_map", "hyimg_find", "hyimg_check", "hyimg_do", "hyimg_notify", "hyimg_props", "hyimg_topage",
            "hyimg_hist", "hyimg_restore", "hyimg_save", "hyimg_active", "hyimg_pages", "hyimg_projects"} <= names
    for t in tools:
        assert t["description"] and t["inputSchema"]["type"] == "object", t["name"]


def test_map_find_and_guide_by_project_name(client):
    text, bad = client.call("hyimg_map", project="Тестовая доска")
    assert not bad and "Старые" in text, text
    text, bad = client.call("hyimg_find", project="Тестовая", query="batch/1")
    assert not bad and "batch/1.png" in text, text
    text, bad = client.call("hyimg_guide", project="тестовая доска")
    assert not bad and "Что умеет Hyimg" in text and "hy.py" in text


def test_the_only_running_project_is_the_default(client):
    text, bad = client.call("hyimg_pages")
    assert not bad and "«Вторая» (p2)" in text, text


def test_do_changes_the_board_and_pages_by_title(client, app):
    text, bad = client.call("hyimg_do", page="Вторая", script='note "# Проба MCP" x=0 y=0', label="проба", quiet=True)
    assert not bad, text
    assert any(it.get("type") == "note" and "Проба MCP" in it["text"] for it in app[2]("p2")["items"].values())
    text, bad = client.call("hyimg_hist", page="p2")
    assert not bad and "проба" in text


def test_errors_are_tool_errors_not_crashes(client):
    text, bad = client.call("hyimg_map", project="Нет такой")
    assert bad and "нет проекта" in text
    text, bad = client.call("hyimg_find")
    assert bad and "query" in text
    r = client.send("tools/call", {"name": "hyimg_nothing", "arguments": {}})
    assert r["error"]["code"] == -32602


def test_features_skills_and_prompts(client):
    text, bad = client.call("hyimg_features", query="pdf")
    assert not bad and "pdfpage" in text
    res = client.send("resources/list")["result"]["resources"]
    uris = {r["uri"] for r in res}
    assert {"hyimg://features", "hyimg://agent", "hyimg://skills/hyimg", "hyimg://skills/hyimg-board"} <= uris
    body = client.send("resources/read", {"uri": "hyimg://features"})["result"]["contents"][0]["text"]
    assert json.loads(body)["features"]
    body = client.send("resources/read", {"uri": "hyimg://skills/hyimg-board"})["result"]["contents"][0]["text"]
    assert body.startswith("---\nname: hyimg-board")
    prompts = {p["name"] for p in client.send("prompts/list")["result"]["prompts"]}
    assert {"hyimg-start", "hyimg", "hyimg-board"} <= prompts
    msg = client.send("prompts/get", {"name": "hyimg-start", "arguments": {"project": "Тестовая доска"}})["result"]["messages"][0]
    assert "hyimg_guide" in msg["content"]["text"]
