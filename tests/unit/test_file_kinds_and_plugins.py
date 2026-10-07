"""What kind of library file a name is (server.kind_of, plugin_kinds) and which plugins the server finds (server.plugins,
plugin_file, plugin_module, plugin_routes)."""
import json
import os

import pytest

import server


@pytest.mark.parametrize("name,kind", [
    ("a.png", "image"), ("A.JPG", "image"), ("a.webp", "image"), ("a.jpeg", "image"),
    ("a.mp4", "video"), ("a.MOV", "video"), ("a.m4v", "video"), ("a.webm", "video"),
    ("a.pdf", "pdf"), ("A.PDF", "pdf"),
    ("a.psd", "doc"), ("a.psb", "doc"), ("a.ai", "doc"), ("a.tif", "doc"), ("a.tiff", "doc"), ("a.heic", "doc"), ("a.svg", "doc"),
    ("dir.v2/a.png", "image"), ("noext", "image"),
])
def test_a_file_kind_follows_its_extension_in_any_case(lib, name, kind):
    assert server.kind_of(name) == kind


def test_a_files_sidecar_is_name_json_for_a_picture_and_name_ext_json_for_anything_else(lib):
    assert server.sidecar("a/IMG_1.JPG").endswith("/a/IMG_1.json")
    assert server.sidecar("a/IMG_1.psd").endswith("/a/IMG_1.psd.json")
    assert server.sidecar("a/doc.pdf").endswith("/a/doc.pdf.json")


class TestPlugins:
    def test_the_installed_plugins_are_not_seen_while_tests_run(self, lib, monkeypatch):
        seen = []
        real_isdir = os.path.isdir
        monkeypatch.setattr(server.os.path, "isdir", lambda p: seen.append(p) or real_isdir(p))
        server.plugins()
        assert not any("Application Support/Hyimg/plugins" in p for p in seen)

    def test_without_the_test_switch_the_users_plugin_folder_is_looked_at(self, lib, monkeypatch):
        monkeypatch.delenv("HY_TEST_ONLY_PLUGINS")
        seen = []
        monkeypatch.setattr(server.os.path, "isdir", lambda p: seen.append(p) or False)
        assert server.plugins() == {}
        assert seen == [os.path.expanduser("~/Library/Application Support/Hyimg/plugins")]

    def test_a_plugin_is_a_folder_with_a_manifest(self, plugin_root):
        d = plugin_root("frames", {"title": "Frames"})
        assert server.plugins() == {"frames": (str(d), {"title": "Frames"})}

    def test_names_outside_lowercase_letters_digits_dash_underscore_are_left_out(self, plugin_root):
        for n in ("Frames", "_x", "-x", "a.b", "a b"):
            plugin_root(n, {"title": n})
        plugin_root("ok_1-x", {"title": "ok"})
        assert list(server.plugins()) == ["ok_1-x"]

    def test_a_manifest_that_is_broken_or_not_an_object_is_left_out(self, plugin_root):
        plugin_root("broken", None, raw="{nope")
        plugin_root("list", None, raw="[1]")
        (plugin_root.root / "nomanifest").mkdir()
        assert server.plugins() == {}

    def test_the_first_folder_in_hyimg_plugins_wins_a_name(self, plugin_root, tmp_path, monkeypatch):
        plugin_root("dev", {"title": "first"})
        second = tmp_path / "second"; (second / "dev").mkdir(parents=True); (second / "dev" / "manifest.json").write_text('{"title": "second"}')
        (second / "more").mkdir(); (second / "more" / "manifest.json").write_text('{"title": "more"}')
        monkeypatch.setenv("HYIMG_PLUGINS", os.pathsep.join([str(plugin_root.root), str(tmp_path / "missing"), str(second)]))
        got = server.plugins()
        assert got["dev"][1]["title"] == "first" and got["more"][1]["title"] == "more"

    def test_a_linked_plugin_folder_is_reported_by_its_real_path(self, plugin_root, tmp_path):
        real = tmp_path / "repo"; real.mkdir(); (real / "manifest.json").write_text("{}")
        os.symlink(real, plugin_root.root / "linked")
        assert server.plugins()["linked"][0] == str(real)

    def test_a_plugin_file_must_stay_inside_its_folder(self, plugin_root, tmp_path):
        plugin_root("p", {}, files={"canvas.js": "x", "sub/a.js": "y"})
        (tmp_path / "secret.js").write_text("no")
        assert server.plugin_file("p", "sub/a.js").endswith("/p/sub/a.js")
        for rel in ("../../secret.js", "/etc/hosts", "sub", "none.js"):
            with pytest.raises(PermissionError):
                server.plugin_file("p", rel)
        with pytest.raises(KeyError):
            server.plugin_file("nobody", "canvas.js")

    def test_a_plugins_server_module_gives_its_routes_and_loads_again_when_it_changes(self, plugin_root):
        d = plugin_root("srv", {"server": "srv.py"}, files={"srv.py": "N = 1\nROUTES = {'ping': lambda b, q: ('text/plain', b'1')}\n"})
        assert set(server.plugin_routes("srv")) == {"ping"}
        assert server.plugin_module("srv") is server.plugin_module("srv")
        (d / "srv.py").write_text("N = 2\nROUTES = {}\n")
        os.utime(d / "srv.py", (1, 1))
        assert server.plugin_module("srv").N == 2

    def test_a_plugin_without_a_server_or_routes_has_no_routes(self, plugin_root):
        plugin_root("plain", {"title": "x"})
        plugin_root("noroutes", {"server": "s.py"}, files={"s.py": "ROUTES = None\n"})
        for n in ("plain", "noroutes"):
            with pytest.raises(KeyError):
                server.plugin_routes(n)


class TestPluginKinds:
    def test_a_plugin_kind_lists_its_extensions_in_the_library(self, plugin_root):
        plugin_root("dev", {"kinds": {"html": [".html", ".htm"]}})
        assert server.plugin_kinds() == {".html": ("html", "dev"), ".htm": ("html", "dev")}
        assert server.kind_of("site/index.HTML") == "html"

    def test_a_plugin_cannot_take_the_apps_own_kinds_or_extensions(self, plugin_root):
        plugin_root("greedy", {"kinds": {"image": [".foo"], "pic": [".png", ".pdf", ".glb", ".step"], "Bad": [".bar"], "ok": [".OK", "x", ".toolongext", ".ok2"]}})
        assert server.plugin_kinds() == {".ok2": ("ok", "greedy")}
        assert server.kind_of("a.png") == "image" and server.kind_of("a.pdf") == "pdf"

    def test_the_first_plugin_keeps_an_extension_both_claim(self, plugin_root):
        plugin_root("a", {"kinds": {"html": [".html"]}})
        plugin_root("b", {"kinds": {"web": [".html"]}})
        assert server.plugin_kinds()[".html"] == ("html", "a")

    def test_plugin_kinds_are_read_again_only_after_ten_seconds(self, plugin_root, monkeypatch):
        plugin_root("a", {"kinds": {"html": [".html"]}})
        now = [1000.0]
        monkeypatch.setattr(server.time, "time", lambda: now[0])
        assert ".html" in server.plugin_kinds()
        plugin_root("b", {"kinds": {"txt": [".txt"]}})
        now[0] += 5
        assert ".txt" not in server.plugin_kinds()
        now[0] += 6
        assert ".txt" in server.plugin_kinds()

    def test_a_kinds_entry_that_is_not_an_object_is_ignored(self, plugin_root):
        plugin_root("a", {"kinds": [".html"]})
        plugin_root("b", {"kinds": {"web": ".html"}})
        assert server.plugin_kinds() == {}
