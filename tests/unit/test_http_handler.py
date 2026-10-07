"""The server's request handling (server.H) without a socket or a port: each request is written into an in-memory connection, the
handler answers into it, and the answer is parsed like a browser would. Covers the origin rules, the sandboxed library pages and their
key, HEAD and ranged reads of library files, and how bad requests are answered."""
import http.client
import io
import json
import re
import types

import pytest

import config
import server

PORT = 4180


class Conn:
    """a socket stand-in: the request to read, everything the handler sends collected"""
    def __init__(self, raw):
        self.inp, self.out = io.BytesIO(raw), bytearray()

    def makefile(self, mode, *a, **k):
        return self.inp if "r" in mode else io.BytesIO()

    def sendall(self, b):
        self.out += b


class Reply:
    def __init__(self, raw):
        sock = types.SimpleNamespace(makefile=lambda *a, **k: io.BytesIO(bytes(raw)))
        r = http.client.HTTPResponse(sock, method=Reply.method); r.begin()
        self.status, self.headers, self.body = r.status, r.headers, r.read()

    def json(self):
        return json.loads(self.body)


def ask(method, path, body=b"", headers=None, host=f"localhost:{PORT}"):
    """the handler's answer to one request; raises what the handler raised when it sent nothing (the real server would log it and
    close the connection without an answer)"""
    if isinstance(body, (dict, list)): body = json.dumps(body).encode()
    hs = [("Host", host)] if host is not None else []
    hs += headers if isinstance(headers, list) else list((headers or {}).items())
    hs += [("Content-Length", str(len(body))), ("Connection", "close")]
    raw = f"{method} {path} HTTP/1.1\r\n".encode() + b"".join(f"{k}: {v}\r\n".encode() for k, v in hs) + b"\r\n" + body
    conn = Conn(raw)
    server.H(conn, ("127.0.0.1", 50000), types.SimpleNamespace(server_port=PORT))
    Reply.method = method
    return Reply(conn.out)


@pytest.fixture
def key():
    return server.SANDBOX_KEY


class TestOrigin:
    @pytest.mark.parametrize("host", [f"localhost:{PORT}", f"127.0.0.1:{PORT}"])
    def test_the_apps_own_hosts_are_answered(self, lib, host):
        assert ask("GET", "/api/foldercolors", host=host).status == 200

    @pytest.mark.parametrize("host", ["evil.example:4180", f"localhost:{PORT + 1}", "localhost", None])
    def test_another_host_name_is_refused_against_dns_rebinding(self, lib, host):
        assert ask("GET", "/api/foldercolors", host=host).status == 403

    def test_two_host_headers_are_refused(self, lib):
        assert ask("GET", "/api/foldercolors", headers=[("Host", "evil.example")]).status == 403

    @pytest.mark.parametrize("origin,status", [(f"http://localhost:{PORT}", 200), (f"http://127.0.0.1:{PORT}", 200), ("https://evil.example", 403),
                                               ("null", 403), (f"http://localhost:{PORT + 1}", 403)])
    def test_a_request_from_another_origin_is_refused(self, lib, origin, status):
        assert ask("GET", "/api/foldercolors", headers={"Origin": origin}).status == status

    def test_a_cross_site_write_is_refused_but_a_cross_site_read_is_not(self, lib):
        assert ask("POST", "/api/foldercolors", {"path": "a", "color": "red"}, headers={"Sec-Fetch-Site": "cross-site"}).status == 403
        assert ask("GET", "/api/foldercolors", headers={"Sec-Fetch-Site": "cross-site"}).status == 200

    def test_a_write_from_a_sandboxed_page_is_refused(self, lib):
        assert ask("POST", "/api/foldercolors", {"path": "a", "color": "red"}, headers={"Origin": "null"}).status == 403


class TestSandbox:
    @pytest.fixture
    def site(self, lib):
        (lib / "site" / "css").mkdir(parents=True)
        (lib / "site" / "index.html").write_text("<html><head><title>x</title></head><body>hi</body></html>")
        (lib / "site" / "css" / "a.css").write_text("body{}")
        (lib / "site" / "f.woff").write_bytes(b"wOFF")
        return lib / "site"

    def test_the_app_learns_the_sandbox_address_from_the_api(self, lib, key):
        assert ask("GET", "/api/sandbox").json() == {"base": f"/sandbox/{key}/"}

    def test_a_page_is_served_sandboxed_with_no_sniffing(self, site, key):
        r = ask("GET", f"/sandbox/{key}/site/index.html")
        assert r.status == 200 and r.headers["Content-Security-Policy"] == "sandbox allow-scripts"
        assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["Vary"] == "Origin" and r.body.endswith(b"</html>")
        assert "Access-Control-Allow-Origin" not in r.headers

    def test_a_folder_serves_its_index_page(self, site, key):
        assert b"hi" in ask("GET", f"/sandbox/{key}/site").body

    def test_the_pages_files_come_with_their_types_and_no_sandbox_header(self, site, key):
        css, font = ask("GET", f"/sandbox/{key}/site/css/a.css"), ask("GET", f"/sandbox/{key}/site/f.woff", headers={"Origin": "null"})
        assert css.headers["Content-Type"] == "text/css" and "Content-Security-Policy" not in css.headers
        assert font.headers["Content-Type"] == "font/woff" and font.headers["Access-Control-Allow-Origin"] == "null"

    @pytest.mark.parametrize("k", ["wrong", "", "x" * 24])
    def test_a_wrong_key_finds_nothing(self, site, k):
        assert ask("GET", f"/sandbox/{k}/site/index.html").status == 404

    def test_another_sites_origin_is_refused(self, site, key):
        assert ask("GET", f"/sandbox/{key}/site/index.html", headers={"Origin": "https://evil.example"}).status == 403

    def test_a_foreign_host_is_refused(self, site, key):
        assert ask("GET", f"/sandbox/{key}/site/index.html", host="evil.example").status == 403

    @pytest.mark.parametrize("rel", ["../outside/secret.txt", "site/../../outside/secret.txt", "%2e%2e/outside/secret.txt", "/etc/hosts",
                                     "~/secret", "site\\..\\..\\x", "site/%00x", "", "site/none.html"])
    def test_a_path_out_of_the_library_or_odd_is_not_found(self, site, key, rel):
        from unit_env import OUTSIDE
        (OUTSIDE / "secret.txt").write_text("secret")
        r = ask("GET", f"/sandbox/{key}/{rel}")
        assert r.status == 404 and b"secret" not in r.body

    def test_a_page_asked_with_a_plugin_gets_its_script_first_in_the_head(self, site, key, plugin_root):
        plugin_root("dev", {"pageScript": "inspect.js"}, files={"inspect.js": "window.HYP = 1"})
        r = ask("GET", f"/sandbox/{key}/site/index.html?hyp=dev")
        assert r.body.startswith(f'<html><head><script src="/sandbox/{key}/~hyp/dev"></script><title>'.encode())
        js = ask("GET", f"/sandbox/{key}/~hyp/dev")
        assert js.status == 200 and js.body == b"window.HYP = 1" and js.headers["Content-Type"].startswith("text/javascript")

    def test_a_plugin_name_with_odd_characters_injects_nothing(self, site, key):
        assert b"~hyp" not in ask("GET", f"/sandbox/{key}/site/index.html?hyp=../x").body

    def test_a_plugin_without_a_page_script_has_none_to_serve(self, site, key, plugin_root):
        plugin_root("plain", {"title": "x"})
        assert ask("GET", f"/sandbox/{key}/~hyp/plain").status == 404
        assert ask("GET", f"/sandbox/{key}/~hyp/nobody").status == 404


class TestInject:
    @pytest.mark.parametrize("page,starts", [
        (b"<!doctype html><HTML lang=en><HEAD class=x><title>", b"<!doctype html><HTML lang=en><HEAD class=x><script"),
        (b"<html><body>x", b"<html><script"), (b"plain text", b"<script")])
    def test_the_plugin_script_goes_after_head_else_after_html_else_in_front(self, page, starts):
        assert server.sandbox_inject(page, "dev").startswith(starts)

    def test_a_header_tag_is_not_taken_for_head(self):
        assert server.sandbox_inject(b"<html><header>", "p").startswith(b"<html><script")


class TestLibraryFiles:
    def test_head_gives_a_library_files_size_and_type_without_its_bytes(self, lib):
        (lib / "3d").mkdir(); (lib / "3d" / "s.glb").write_bytes(b"x" * 1234)
        r = ask("HEAD", "/file?p=3d/s.glb")
        assert r.status == 200 and r.headers["Content-Length"] == "1234" and r.headers["Content-Type"] == "model/gltf-binary"

    @pytest.mark.parametrize("path", ["/file?p=../outside/x", "/file?p=none.glb", "/file", "/other?p=a.png"])
    def test_head_of_anything_else_is_not_found(self, lib, path):
        assert ask("HEAD", path).status == 404

    def test_a_json_file_is_never_cached_and_a_model_is(self, lib):
        (lib / "3d").mkdir(); (lib / "3d" / "s.json").write_text("{}"); (lib / "3d" / "m.glb").write_bytes(b"g")
        assert ask("GET", "/file?p=3d/s.json").headers["Cache-Control"] == "no-store"
        assert ask("GET", "/file?p=3d/m.glb").headers["Cache-Control"] == "max-age=86400"

    def test_a_file_outside_the_library_is_not_found(self, lib):
        from unit_env import OUTSIDE
        (OUTSIDE / "x.json").write_text('{"secret": 1}')
        assert ask("GET", "/file?p=../outside/x.json").status == 404


class TestRanges:
    @pytest.fixture
    def clip(self, lib):
        (lib / "v.mp4").write_bytes(bytes(range(10)))

    def test_a_video_without_a_range_comes_whole(self, clip):
        r = ask("GET", "/file?p=v.mp4")
        assert r.status == 200 and r.body == bytes(range(10)) and r.headers["Accept-Ranges"] == "bytes"

    @pytest.mark.parametrize("rng,body,cr", [("bytes=2-4", bytes([2, 3, 4]), "bytes 2-4/10"), ("bytes=7-", bytes([7, 8, 9]), "bytes 7-9/10"),
                                             ("bytes=-3", bytes([7, 8, 9]), "bytes 7-9/10"), ("bytes=8-100", bytes([8, 9]), "bytes 8-9/10"),
                                             ("bytes=-50", bytes(range(10)), "bytes 0-9/10")])
    def test_a_range_gives_those_bytes(self, clip, rng, body, cr):
        r = ask("GET", "/file?p=v.mp4", headers={"Range": rng})
        assert r.status == 206 and r.body == body and r.headers["Content-Range"] == cr

    @pytest.mark.parametrize("rng", ["bytes=10-", "bytes=5-2"])
    def test_a_range_past_the_end_is_not_satisfiable(self, clip, rng):
        r = ask("GET", "/file?p=v.mp4", headers={"Range": rng})
        assert r.status == 416 and r.headers["Content-Range"] == "bytes */10"

    def test_a_range_is_served_8_mb_at_a_time(self, lib):
        (lib / "big.mp4").write_bytes(b"\0" * (8 * 1024 * 1024 + 10))
        r = ask("GET", "/file?p=big.mp4", headers={"Range": "bytes=0-"})
        assert r.status == 206 and len(r.body) == 8 * 1024 * 1024 and r.headers["Content-Range"].endswith(f"/{8 * 1024 * 1024 + 10}")


class TestBadRequests:
    def test_an_unknown_address_is_not_found(self, lib):
        assert ask("GET", "/nothing").status == 404 and ask("POST", "/nothing", {}).status == 404

    @pytest.mark.parametrize("name", ["../x", "a/b", "x" * 41])
    def test_a_bad_page_name_is_not_found(self, lib, name):
        assert ask("GET", f"/api/events?name={name}").status == 404
        assert ask("GET", f"/api/history?name={name}").status == 404

    @pytest.mark.parametrize("path", ["/ui/../server.py", "/ui/Menu.js", "/ui/none.js", "/agent/../x", "/agent/BAD"])
    def test_only_the_shared_ui_files_and_skills_by_plain_name_are_served(self, lib, path):
        assert ask("GET", path).status == 404

    def test_a_shared_ui_file_is_served(self, lib):
        r = ask("GET", "/ui/icons.js")
        assert r.status == 200 and r.headers["Content-Type"].startswith("text/javascript")

    def test_health_names_the_project_and_the_port(self, lib):
        d = ask("GET", "/api/health").json()
        assert d["projectId"] == config.PROJECT_ID and d["port"] == PORT and d["libraryRoot"] == config.W

    @pytest.mark.parametrize("body", [b"[1]", b'"x"', b'{"path": "../x", "color": "red"}', b'{"path": "a", "color": "teal"}'])
    def test_a_bad_folder_colour_is_a_400(self, lib, body):
        assert ask("POST", "/api/foldercolors", body).status == 400

    def test_a_folder_colour_is_set(self, lib):
        assert ask("POST", "/api/foldercolors", {"path": "a", "color": "red"}).json() == {"colors": {"a": "red"}}

    def test_pins_and_a_projects_tag_are_saved_and_a_bad_one_is_a_400(self, lib, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RULES_FILE", str(tmp_path / "rules.json"))
        monkeypatch.setattr(server.filters, "FILE", str(tmp_path / "filters.json"))
        assert ask("POST", "/api/filters", {"pins": ["fav"]}).json() == {"pins": ["fav"]}
        assert ask("POST", "/api/filters", {"pins": "fav"}).status == 400
        assert ask("POST", "/api/tagrule", {"group": "", "tag": "x", "words": "x"}).status == 400

    def test_a_tag_the_project_has_already_is_a_409(self, lib, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RULES_FILE", str(tmp_path / "rules.json"))
        (tmp_path / "rules.json").write_text(json.dumps({config.PROJECT_ID: {"tags": [["G", "Bird", "b"]]}}))
        assert ask("POST", "/api/tagrule", {"group": "G", "tag": "Bird", "words": "bird"}).status == 409

    def test_feedback_without_a_path_or_outside_the_library_is_a_400(self, lib):
        assert ask("POST", "/api/feedback", {"verdict": "take"}).status == 400
        assert ask("POST", "/api/feedback", {"path": "../outside/x.png", "verdict": "take"}).status == 400
        assert ask("POST", "/api/fav", {"paths": []}).status == 400
        assert ask("POST", "/api/fav", {"paths": ["../x.png"], "fav": True}).status == 400

    def test_a_plugin_route_answers_and_its_failures_are_reported(self, lib, plugin_root):
        plugin_root("srv", {"server": "s.py"}, files={"s.py": "def boom(b, q): raise RuntimeError('x')\n"
                                                           "ROUTES = {'echo': lambda b, q: (201, 'text/plain', b + q['n'][0].encode()), 'two': lambda b, q: ('text/plain', b'2'), 'boom': boom}\n"})
        r = ask("POST", "/api/plugin/srv/echo?n=7", b"hi")
        assert r.status == 201 and r.body == b"hi7"
        assert ask("POST", "/api/plugin/srv/two").body == b"2"
        assert ask("POST", "/api/plugin/srv/boom").status == 500 and "RuntimeError" in ask("POST", "/api/plugin/srv/boom").json()["error"]
        assert ask("POST", "/api/plugin/srv/none").status == 404 and ask("POST", "/api/plugin/nobody/echo").status == 404
        assert ask("POST", "/api/plugin/srv").status == 404

    def test_the_plugin_list_names_each_plugins_module_and_title_in_the_apps_language(self, lib, plugin_root):
        plugin_root("p", {"title": "Frames", "title_ru": "Рамки", "canvas": "c.js", "version": "1"}, files={"c.js": "x"})
        plugin_root("q", {"sprites": "s.js"})
        assert ask("GET", "/api/plugins").json() == [{"name": "p", "title": "Frames", "version": "1", "canvas": "/plugins/p/c.js", "sprites": None},
                                                     {"name": "q", "title": "q", "version": "", "canvas": None, "sprites": "/plugins/q/s.js"}]
        server.settings_write({"cv.lang": "ru"})
        assert ask("GET", "/api/plugins").json()[0]["title"] == "Рамки"

    def test_a_plugin_file_is_served_only_from_inside_its_folder(self, lib, plugin_root, tmp_path):
        plugin_root("p", {"canvas": "c.js"}, files={"c.js": "x = 1"})
        (tmp_path / "secret.js").write_text("secret")
        r = ask("GET", "/plugins/p/c.js")
        assert r.status == 200 and r.body == b"x = 1" and r.headers["Content-Type"].startswith("text/javascript")
        for path in ("/plugins/p/..%2F..%2Fsecret.js", "/plugins/p", "/plugins/nobody/c.js", "/plugins/p/none.js"):
            assert ask("GET", path).status == 404

    # These requests made the handler raise instead of answering: the server dropped the connection and the page's fetch failed with a
    # network error instead of a status it can show (found by these tests 2026-10-06); server.py's one guard (_guarded) answers them now
    def test_a_limit_that_is_not_a_number_is_a_400(self, lib):
        assert ask("GET", "/api/events?limit=abc").status == 400

    def test_a_thumbnail_size_that_is_not_a_number_is_a_400(self, lib):
        (lib / "a.png").write_bytes(b"x")
        assert ask("GET", "/thumb?p=a.png&s=big").status == 400

    def test_feedback_for_a_file_that_is_gone_is_a_400(self, lib):
        assert ask("POST", "/api/feedback", {"path": "gone.png", "verdict": "take"}).status in (400, 404)

    def test_an_answer_for_a_picture_without_questions_is_a_400(self, lib):
        (lib / "a.png").write_bytes(b"x")
        assert ask("POST", "/api/answer", {"path": "a.png", "id": "q1", "a": "yes"}).status in (400, 404)

    def test_a_feedback_body_that_is_not_json_is_a_400(self, lib):
        assert ask("POST", "/api/feedback", b"{nope").status == 400


class TestBoardEvents:
    def test_a_save_carries_its_author_and_agent_into_the_pages_events(self, lib):
        """Home's news names the agent (owner 2026-10-06): hy.py saves with who=ai&agent=<HYIMG_AGENT>, the owner's canvas with who=owner"""
        import events
        r = ask("POST", "/api/board?name=main&who=ai&agent=Codex", {"items": {"a": {"path": "1.png", "x": 0, "y": 0}}})
        assert r.status == 200, r.body
        rev = r.json().get("revision")
        r = ask("POST", "/api/board?name=main&who=owner", {"revision": rev, "items": {"a": {"path": "1.png", "x": 0, "y": 0}, "n": {"type": "note", "text": "hi"}}})
        assert r.status == 200, r.body
        got = events.read("main")
        assert [(e["kind"], e["who"], e.get("agent")) for e in got] == [("note", "owner", None), ("add", "ai", "Codex")]
