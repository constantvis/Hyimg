"""The feature catalog cannot go stale (owner 2026-10-06: «agents that come to our app must get this information about skills, so it
doesn't happen that I work with an agent and it doesn't see the skills or the functions»). review/features.json is what /agent, `hy.py
guide`, `hy.py features` and the MCP server tell an agent; these tests fail when the code gains a hy.py command, a command inside
`hy.py do`, a server route, a kind of HY.props, a mode of the dock or an MCP tool that no catalog entry names. Add an entry (or the name to
the entry it belongs to): what it is, how the owner uses it, the agent's exact command, its skill.

A name the catalog keeps after the code dropped it does no harm and is not checked: entries of plugins (optional) name code of other
repositories, and work of several agents lands in pieces."""
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPOS = ROOT.parent
CAT = json.loads((ROOT / "review" / "features.json").read_text(encoding="utf-8"))
F = CAT["features"]
PLUGIN_REPOS = ["hyimg-frames", "hyimg-3d-studio", "hyimg-dev-studio"]


def named(field):
    return {x for f in F for x in f.get(field, [])}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def hy_commands():
    src = (ROOT / "review" / "hy.py").read_text(encoding="utf-8")
    body = src[src.index("def main(argv):"):]
    return set(re.findall(r'\bc == "([a-z0-9-]+)"', body))


def server_routes():
    src = (ROOT / "review" / "server.py").read_text(encoding="utf-8")
    out = set()
    for m in re.finditer(r'(?:u\.path|self\.path)\s*(?:==|in|\.startswith)\s*\(?\s*((?:"[^"]*"\s*,?\s*)+)\)?', src):
        out |= set(re.findall(r'"([^"]*)"', m.group(1)))
    return out


def js_sources():
    files = [ROOT / "review" / "canvas.html", *sorted((ROOT / "review" / "ui").glob("*.js"))]
    for r in PLUGIN_REPOS:
        d = REPOS / r
        if d.is_dir(): files += [p for p in d.glob("*.js")]
    return [(p, p.read_text(encoding="utf-8", errors="replace")) for p in files]


def prop_kinds():
    out = set()
    for _p, s in js_sources():
        out |= set(re.findall(r'(?:props\.register\(\s*\{|Prop\s*=\s*\{)\s*id:\s*"([\w-]+)"', s))
    return out


def dock_modes():
    out = {"board"}
    for _p, s in js_sources():
        out |= set(re.findall(r'\b(?:hy|HY)\.mode\(\s*"([\w-]+)"', s))
    return out


def test_every_entry_is_complete():
    ids = [f["id"] for f in F]
    assert len(ids) == len(set(ids)), "two entries with one id"
    for f in F:
        for k in ("id", "title", "what", "agent"):
            assert f.get(k), f"{f.get('id')}: no {k}"
        assert isinstance(f["agent"], list) and all(isinstance(a, str) and a for a in f["agent"]), f["id"]


def test_skills_and_plugins_exist():
    skills = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
    for f in F:
        if f.get("skill"): assert f["skill"] in skills, f"{f['id']}: no skill {f['skill']}"
        if f.get("plugin"): assert f["plugin"] in ("frames", "3d", "dev"), f"{f['id']}: unknown plugin {f['plugin']}"


def test_every_hy_command_is_in_the_catalog():
    missing = hy_commands() - named("commands")
    assert not missing, f"hy.py commands without a catalog entry (review/features.json, field commands): {sorted(missing)}"


def test_every_do_command_is_in_the_catalog():
    hy = load(ROOT / "review" / "hy.py", "hy_for_catalog")
    missing = set(hy.OPS) - named("ops")
    assert not missing, f"hy.py do commands without a catalog entry (review/features.json, field ops): {sorted(missing)}"


def test_every_route_is_in_the_catalog():
    missing = server_routes() - named("routes")
    assert not missing, f"server routes without a catalog entry (review/features.json, field routes): {sorted(missing)}"


def test_every_props_kind_is_in_the_catalog():
    kinds = prop_kinds()
    assert {"crop", "trim", "size", "opacity", "page"} <= kinds, f"the core's kinds not found: {sorted(kinds)}"
    missing = kinds - named("props")
    assert not missing, f"HY.props kinds without a catalog entry (review/features.json, field props): {sorted(missing)}"


def test_every_dock_mode_is_in_the_catalog():
    missing = dock_modes() - named("modes")
    assert not missing, f"dock modes (HY.mode) without a catalog entry (review/features.json, field modes): {sorted(missing)}"


def test_every_mcp_tool_is_in_the_catalog():
    mcp = load(ROOT / "mcp" / "server.py", "hyimg_mcp_for_catalog")
    tools = {t[0] for t in mcp.TOOLS}
    missing = tools - named("mcp")
    assert not missing, f"MCP tools without a catalog entry (review/features.json, field mcp): {sorted(missing)}"
    stale = named("mcp") - tools
    assert not stale, f"the catalog names MCP tools the server does not have: {sorted(stale)}"


def test_hy_props_kinds_match_the_canvas():
    """hy.py's props command knows every kind the canvas and the plugins register (a new kind needs its rule in hy.py too)"""
    hy = load(ROOT / "review" / "hy.py", "hy_for_props")
    missing = prop_kinds() - set(hy.PROP_ORDER)
    assert not missing, f"HY.props kinds hy.py's props does not order: {sorted(missing)}"
