"""The server finds which agent writes by itself (owner 2026-10-07: «желательно, чтобы это работало без отдельного участия агентов, а то
агент что-то забудет и не впишет»): a write over loopback is traced to the client process and its parents. A script named codex that
runs curl or hy.py is Codex, one named claude is Claude, a plain client is the person by the app, and a Codex tree that says «Claude»
in the header is still Codex. macOS only (netstat names the socket's process, libproc the parents)."""
import json
import os
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_shortcuts import run_server

ROOT = Path(__file__).resolve().parents[1]
ME = str(uuid.uuid4())
pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="process lookup is macOS's")


def wrapper(folder, name):
    """an executable called name that runs its arguments as a child (not exec: the agent stays the parent, as a real CLI does)"""
    p = folder / name
    p.write_text('#!/bin/sh\n"$@"\nexit $?\n'); p.chmod(0o755)
    return str(p)


def last_by(port):
    d = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/notifications?limit=1", timeout=10))
    return d["items"][0]["by"]


def curl(port, title, header=None):
    cmd = ["curl", "-s", "-o", "/dev/null", "-X", "POST", "-H", "Content-Type: application/json", "--data", json.dumps({"action": "add", "title": title})]
    if header: cmd += ["-H", f"X-Hyimg-Agent: {header}"]
    return cmd + [f"http://127.0.0.1:{port}/api/notifications"]


def test_the_server_names_the_agent_from_the_process_tree(tmp_path):
    (tmp_path / "profile.json").write_text(json.dumps({"id": ME, "name": "Ann", "color": "green", "created": ""}))
    bins = tmp_path / "bin"; bins.mkdir()
    codex, claude = wrapper(bins, "codex"), wrapper(bins, "claude")
    servers = run_server(tmp_path); port = next(servers)
    try:
        subprocess.run([codex] + curl(port, "codex curl"), check=True, timeout=30)
        assert last_by(port) == {"person": ME, "via": "codex"}
        subprocess.run([claude] + curl(port, "claude curl"), check=True, timeout=30)
        assert last_by(port) == {"person": ME, "via": "claude"}
        subprocess.run(curl(port, "plain"), check=True, timeout=30)   # the test's own client: no agent between it and the server
        assert last_by(port) == {"person": ME, "via": "app"}
        subprocess.run([codex] + curl(port, "a lie", header="Claude"), check=True, timeout=30)
        assert last_by(port) == {"person": ME, "via": "codex"}
        env = {k: v for k, v in os.environ.items() if k != "HYIMG_AGENT"} | {"HYIMG_PORT": str(port), "PYTHONDONTWRITEBYTECODE": "1"}
        subprocess.run([codex, sys.executable, str(ROOT / "review/hy.py"), "notify", "from hy.py"], check=True, timeout=60, env=env, capture_output=True)
        assert last_by(port) == {"person": ME, "via": "codex"}
        subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "notify", "hy.py alone"], check=True, timeout=60, env=env | {"HYIMG_AGENT": "Gemini"},
                       capture_output=True)
        assert last_by(port) == {"person": ME, "via": "gemini"}   # no agent in the tree: what the client says, folded into the catalog
        # the agent seen goes on this Mac's card on the board, so the other Mac's Team lists it under this person
        card = json.loads((tmp_path / "state" / "people" / f"{ME}.json").read_text())
        assert {"codex", "claude"} <= set(card["agents"])
    finally:
        servers.close()
