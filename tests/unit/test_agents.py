"""Agents are no participants of their own (owner 2026-10-07: «чтобы Claude или Codex не наплодили 2000 участников»): any agent name folds
into a kind of a fixed catalog before anything is stored, the same in review/agents.py and review/ui/avatar.js, and the stamp of a write
takes the server's own look at the client's process tree before the header the client sends."""
import json
import random
import shutil
import string
import subprocess
from pathlib import Path

import pytest

import unit_env  # noqa: F401  (review/ on the path, a throwaway library)
import agents
import people

ROOT = Path(__file__).resolve().parents[2]
NAMES = ["Claude Code", "claude-opus-4-1-20250805", "Opus", "Sonnet 4.5", "claude.app", "ANTHROPIC", "Codex", "codex-cli 0.159", "gpt-6-astra",
         "GPT-5", "openai", "ChatGPT", "o3-mini", "Gemini", "gemini-2.5-pro", "agy", "Antigravity", "Kimi", "kimi-k2", "Moonshot", "OpenCode",
         "open-code", "opencode 1.2", "Cursor", "aider", "agent", "Agent", "ai", "my bot", "app", "", "owner", "  Claude  ", "Codex (Renderer)"]


def test_a_thousand_names_fold_into_the_catalog():
    rnd = random.Random(7)
    pool = NAMES + ["".join(rnd.choice(string.ascii_letters + string.digits + " -_.") for _ in range(rnd.randint(1, 30))) for _ in range(1000)]
    pool += [f"{rnd.choice(NAMES)} {rnd.randint(1, 999)}.{rnd.randint(0, 9)} session {n}" for n in range(1000)]
    kinds = {agents.kind(v) for v in pool}
    assert kinds <= set(agents.CATALOG) | {""}, kinds
    assert len(kinds - {""}) <= len(agents.CATALOG)
    assert agents.kind("Claude Code") == agents.kind("claude-opus-4") == agents.kind("Opus") == agents.kind("Sonnet") == "claude"
    assert agents.kind("gpt-5.1") == agents.kind("openai") == agents.kind("Codex") == "codex"
    assert agents.kind("agy") == "gemini" and agents.kind("OpenCode") == "opencode" and agents.kind("Kimi K2") == "kimi"
    assert agents.kind("Cursor") == "agent" and agents.kind("app") == "" and agents.kind("") == ""


def test_the_page_folds_names_the_same_way():
    if not shutil.which("node"): pytest.skip("no node")
    rnd = random.Random(3)
    pool = NAMES + ["".join(rnd.choice(string.ascii_letters + " -.") for _ in range(rnd.randint(1, 20))) for _ in range(300)]
    script = ("const vm = require('vm'), fs = require('fs'); const w = {}; w.window = w; vm.createContext(w);"
              f"vm.runInContext(fs.readFileSync({json.dumps(str(ROOT / 'review/ui/avatar.js'))}, 'utf8'), w);"
              f"const names = {json.dumps(pool)}; console.log(JSON.stringify(names.map(n => w.HY_AGENTS.kind(n))));")
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out == [agents.kind(n) for n in pool]


def test_process_names():
    assert agents.of_names(["/Volumes/x/Library/Application Support/Claude/claude-code/2.1/claude.app/Contents/MacOS/claude"]) == "claude"
    assert agents.of_names(["/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"]) == "codex"
    assert agents.of_names(["/usr/local/bin/node", "node", "/usr/local/lib/node_modules/@google/gemini-cli/dist/gemini.js"]) == "gemini"
    assert agents.of_names(["/bin/sh", "sh", "/tmp/x/codex"]) == "codex"
    assert agents.of_names(["/opt/homebrew/bin/opencode"]) == "opencode" and agents.of_names(["/usr/local/bin/agy"]) == "gemini"
    assert agents.of_names(["/usr/bin/python3", "python3", "hy.py"]) == ""
    assert agents.of_names(["/Applications/Hyimg.app/Contents/MacOS/Hyimg", "/bin/zsh", "/usr/bin/curl"]) == ""


class Req:
    def __init__(self, header=""):
        self.headers = {"X-Hyimg-Agent": header} if header else {}


@pytest.mark.parametrize("found, header, who, via", [
    ("codex", "Claude", "", "codex"),        # the process tree wins over what the client says
    ("claude", "", "", "claude"),            # no header: the tree alone
    ("", "", "", "app"),                     # a person's app or browser
    ("", "Cursor", "", "agent"),             # no known agent in the tree, the client says it is one
    (None, "claude-sonnet-4", "", "claude"),  # the tree could not be read (another machine): the header, folded
    (None, "", "ai", "agent"),
    (None, "", "", "app"),
])
def test_the_stamp_prefers_the_tree(monkeypatch, tmp_path, found, header, who, via):
    people.save_me(tmp_path, "Ann", "green")
    monkeypatch.setattr(agents, "detect", lambda handler, wait=0: found)
    s = people.request_by(tmp_path, Req(header), {"who": [who]} if who else None)
    assert s["via"] == via and s["person"] == people.me(tmp_path)["id"]
    assert people.who_of(s) == ("ai" if via != "app" else "owner") and people.agent_of(s) == agents.LABEL.get(via, "")


def test_agents_seen_go_on_the_card_and_into_the_address_book(monkeypatch, tmp_path):
    state = tmp_path / "state"; root = tmp_path / "root"; root.mkdir()
    me = people.save_me(root, "Ann", "green")
    monkeypatch.setattr(agents, "detect", lambda handler, wait=0: "claude")
    people._CARDS.clear()
    assert people.stamp(root, str(state), Req(""))["via"] == "claude"
    card = json.loads((state / "people" / f"{me['id']}.json").read_text())
    assert set(card["agents"]) == {"claude"}
    # another Mac reads the card: the person, his agents, his picture
    other = tmp_path / "other"; other.mkdir()
    pic = "data:image/jpeg;base64," + "A" * 40
    people.save_me(root, "Ann", "green", pic); people.card_write(str(state), people.me(root))
    v = people.view(other, str(state))["people"][me["id"]]
    assert v["agents"].keys() == {"claude"} and v["avatar"] == pic and v["name"] == "Ann"
    people.hide(other, me["id"]); assert people.view(other)["people"][me["id"]]["hidden"] is True
    people.hide(other, me["id"], False); assert "hidden" not in people.view(other)["people"][me["id"]]
    with pytest.raises(ValueError): people.save_me(root, "Ann", "green", "data:text/html;base64,AAAA")


def test_only_stamped_writes_look_up_the_client_on_arrival(monkeypatch):
    """/api/live comes on every camera move: it never starts a netstat; a board save does, and a stamp elsewhere starts it itself"""
    started = []
    monkeypatch.setattr(agents, "_lookup", lambda handler, since: started.append(handler.path) or "")

    class H:
        client_address = ("127.0.0.1", 50000)
        def __init__(self, path): self.path = path
    for path in ("/api/live", "/api/stat", "/api/plugins/hold", "/api/board?name=main", "/api/plugin/dev/edit"):
        agents.start(H(path))
    assert agents.detect(H("/api/somewhere")) == ""
    import time; time.sleep(0.05)
    assert sorted(started) == ["/api/board?name=main", "/api/plugin/dev/edit", "/api/somewhere"]
