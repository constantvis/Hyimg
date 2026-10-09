"""Settings › Plugins on the server's side (review/plugins_admin.py, owner 2026-10-07: «В настройках включить, выключить и посмотреть»):
which plugins are served while some are turned off (no restart), a page's hold on the plugin whose editor is open, the list the settings
show, «Add plugin…» (a folder's manifest.json checked, a link made) and «Remove» (only the link goes). Temporary folders only: the plugins
folder is HYIMG_PLUGIN_DIR in tmp_path, never the person's."""
import json
import os

import pytest

from unit_env import SETTINGS, server

pa = server.plugins_admin


def plugin(folder, manifest, files=("canvas.js",)):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "manifest.json").write_text(json.dumps(manifest))
    for f in files: (folder / f).write_text("export function register() {}")
    return folder


@pytest.fixture
def pdir(lib, tmp_path, monkeypatch):
    """the managed plugins folder (empty) with the three plugins linked in, as on the owner's Mac"""
    d = tmp_path / "plugins"; d.mkdir()
    monkeypatch.setenv("HYIMG_PLUGIN_DIR", str(d))
    pa._HOLDS.clear()
    for name, repo, title in (("3d", "hyimg-3d-studio", "3D objects"), ("frames", "hyimg-image-studio", "Frames"), ("dev", "hyimg-dev-studio", "Dev studio")):
        r = plugin(tmp_path / "repos" / repo, {"title": title, "title_ru": title + " ru", "version": "0.1.0", "canvas": "canvas.js",
                                               "description": f"{title} does things", "description_ru": f"{title} делает"})
        os.symlink(r, d / name)
    yield d
    pa._HOLDS.clear()


def settings(**kv):
    SETTINGS.write_text(json.dumps({f"cv.{k}": v for k, v in kv.items()}))


def test_all_plugins_are_on_without_the_setting(pdir):
    assert sorted(server.plugins()) == ["3d", "dev", "frames"]


def test_a_plugin_turned_off_is_not_served_at_once_and_its_routes_say_off(pdir):
    settings(plugoff="dev")
    assert sorted(server.plugins()) == ["3d", "frames"] and sorted(server.plugins(every=True)) == ["3d", "dev", "frames"]
    assert pa.why_off("dev", server.settings_read()) == (409, "plugin off: dev")
    assert pa.why_off("frames", server.settings_read()) is None
    settings(plugoff="")
    assert "dev" in server.plugins()


def test_a_page_in_the_plugins_editor_holds_it_until_it_lets_go(pdir, monkeypatch):
    settings(plugoff="dev")
    pa.hold("dev", True)
    assert "dev" in server.plugins() and pa.why_off("dev", server.settings_read()) is None
    pa.hold("dev", False)
    assert "dev" not in server.plugins()
    pa.hold("dev", True)   # a page that went away without letting go: the hold ends by itself
    t = pa.time.time() + pa.HOLD_S + 1
    monkeypatch.setattr(pa.time, "time", lambda: t)
    assert "dev" not in server.plugins()


def test_the_list_has_names_versions_descriptions_folders_and_states_in_the_apps_language(pdir, tmp_path):
    settings(plugoff="3d", lang="ru")
    d = pa.listing(server.settings_read(), "ru")
    rows = {r["name"]: r for r in d["plugins"]}
    assert set(rows) == {"3d", "dev", "frames"} and d["root"] == str(pdir) and d["off"] == ["3d"]
    assert rows["dev"]["title"] == "Dev studio ru" and rows["dev"]["description"] == "Dev studio делает" and rows["dev"]["version"] == "0.1.0"
    assert rows["dev"]["folder"] == os.path.realpath(tmp_path / "repos" / "hyimg-dev-studio") and rows["dev"]["removable"]
    assert rows["3d"]["off"] and not rows["dev"]["off"] and rows["dev"]["canvas"]
    en = {r["name"]: r for r in pa.listing({}, "en")["plugins"]}
    assert en["dev"]["title"] == "Dev studio" and en["dev"]["description"] == "Dev studio does things"


def test_a_manifest_without_description_shows_its_about(pdir, tmp_path):
    plugin(tmp_path / "repos" / "old", {"title": "Old", "canvas": "canvas.js", "about": "the about line"})
    os.symlink(tmp_path / "repos" / "old", pdir / "old")
    assert {r["name"]: r for r in pa.listing({}, "en")["plugins"]}["old"]["description"] == "the about line"


def test_add_checks_the_manifest_and_links_the_folder(pdir, tmp_path):
    new = plugin(tmp_path / "repos" / "hyimg-notes-studio", {"title": "Notes", "canvas": "canvas.js", "server": "srv.py"}, files=("canvas.js", "srv.py"))
    assert pa.add(str(new)) == {"added": "notes", "title": "Notes"}
    assert os.path.islink(pdir / "notes") and os.path.realpath(pdir / "notes") == str(new.resolve())
    assert "notes" in server.plugins()
    with pytest.raises(ValueError, match="Already added as «notes»"): pa.add(str(new))


@pytest.mark.parametrize("manifest,files,why", [
    (None, (), "No manifest.json in the folder"),
    ("{nope", (), "manifest.json is broken"),
    ({"canvas": "canvas.js"}, ("canvas.js",), "manifest.json has no title"),
    ({"title": "X"}, (), "manifest.json names no canvas, server or kinds"),
    ({"title": "X", "canvas": "missing.js"}, (), "The manifest's canvas file is missing: missing.js"),
    ({"title": "X", "canvas": "../outside.js"}, (), "The manifest's canvas file is missing: ../outside.js"),
])
def test_add_refuses_a_folder_that_is_not_a_plugin_and_links_nothing(pdir, tmp_path, manifest, files, why):
    d = tmp_path / "repos" / "bad"; d.mkdir(parents=True)
    (tmp_path / "repos" / "outside.js").write_text("")
    if manifest is not None: (d / "manifest.json").write_text(manifest if isinstance(manifest, str) else json.dumps(manifest))
    for f in files: (d / f).write_text("")
    with pytest.raises(ValueError, match=why.replace(".", r"\.")): pa.add(str(d))
    assert sorted(os.listdir(pdir)) == ["3d", "dev", "frames"]


def test_add_refuses_a_name_already_taken_and_says_it_in_russian(pdir, tmp_path):
    other = plugin(tmp_path / "elsewhere" / "dev", {"title": "Another dev", "canvas": "canvas.js"})
    with pytest.raises(ValueError, match="Плагин с именем «dev» уже есть"): pa.add(str(other), "ru")


def test_remove_takes_only_the_link_the_folder_stays(pdir, tmp_path):
    repo = tmp_path / "repos" / "hyimg-dev-studio"
    assert pa.remove("dev") == {"removed": "dev"}
    assert not os.path.lexists(pdir / "dev") and (repo / "manifest.json").is_file() and (repo / "canvas.js").is_file()
    assert "dev" not in server.plugins(every=True)


def test_remove_refuses_a_real_folder_and_a_name_that_is_not_there(pdir):
    plugin(pdir / "copied", {"title": "Copied", "canvas": "canvas.js"})
    with pytest.raises(ValueError, match="not a link"): pa.remove("copied")
    assert (pdir / "copied" / "manifest.json").is_file()
    for n in ("nothing", "../x", ""):
        with pytest.raises(ValueError): pa.remove(n)


def test_a_plugin_from_hyimg_plugins_is_listed_but_not_removable(pdir, tmp_path, monkeypatch):
    extra = tmp_path / "extra"; plugin(extra / "solo", {"title": "Solo", "canvas": "canvas.js"})
    monkeypatch.setenv("HYIMG_PLUGINS", str(extra))
    rows = {r["name"]: r for r in pa.listing({}, "en")["plugins"]}
    assert not rows["solo"]["own"] and not rows["solo"]["removable"] and rows["dev"]["removable"]


def test_a_broken_link_is_listed_with_its_reason_so_it_can_be_removed(pdir, tmp_path):
    os.symlink(tmp_path / "gone", pdir / "gone")
    rows = {r["name"]: r for r in pa.listing({}, "en")["plugins"]}
    assert rows["gone"]["error"] == "no manifest.json" and rows["gone"]["removable"] and "gone" not in server.plugins(every=True)
    pa.remove("gone")
    assert not os.path.lexists(pdir / "gone")


def test_the_routes(pdir):
    st, body, ctype = pa.http("GET", "/api/plugins/all", b"", {}, "en")
    assert st == 200 and ctype == "application/json" and len(json.loads(body)["plugins"]) == 3
    st, body, _ = pa.http("POST", "/api/plugins/hold", b'{"name": "dev", "on": true}', {}, "en")
    assert json.loads(body)["held"] == ["dev"]
    st, body, _ = pa.http("POST", "/api/plugins/remove", b'{"name": "frames"}', {}, "en")
    assert st == 200 and json.loads(body)["removed"] == "frames" and not os.path.lexists(pdir / "frames")
    assert pa.http("POST", "/api/plugins/remove", b'{"name": "frames"}', {}, "en")[0] == 400
    assert pa.http("POST", "/api/plugins/nothing", b"{}", {}, "en")[0] == 404


def test_the_apps_command_lists_adds_and_removes_with_json(pdir, tmp_path):
    """what the Mac app runs for Home (native/Plugins.swift): the settings file beside its catalog gives the language and what is off"""
    import subprocess, sys
    prof = tmp_path / "support"; prof.mkdir()
    (prof / "settings.json").write_text(json.dumps({"cv.lang": "ru", "cv.plugoff": "dev"}))
    env = {k: v for k, v in os.environ.items() if not k.startswith("HYIMG_")}
    env.update(HYIMG_PLUGIN_DIR=str(pdir), HYIMG_PROFILE_DIR=str(prof))
    run = lambda *a: json.loads(subprocess.run([sys.executable, str(server.plugins_admin.__file__), *a], env=env, capture_output=True, text=True, check=True).stdout)
    d = run("list")
    assert {r["name"]: r["off"] for r in d["plugins"]} == {"3d": False, "dev": True, "frames": False} and d["plugins"][1]["title"].endswith(" ru")
    new = plugin(tmp_path / "repos" / "x-plugin", {"title": "X", "canvas": "canvas.js"})
    assert run("add", str(new))["added"] == "x" and os.path.islink(pdir / "x")
    assert run("add", str(tmp_path / "repos"))["error"] == "В папке нет manifest.json"
    assert run("remove", "x")["removed"] == "x" and not os.path.lexists(pdir / "x") and new.is_dir()
