"""hy.py link (review/hylink.py, owner 2026-10-07: «ссылку, которую нажимаешь, и открывается приложение»): the app's link first, the
browser's second, the same parameters as the board's own links (ui/applink.js) and what native/Links.swift accepts."""
import unit_env  # noqa: F401  (review/ on the path, a throwaway library)
import hylink

PID = "6F1C2B9E-7D35-4C1B-9B7A-2E8D5A0C4F11"


def test_both_links_of_objects_a_page_and_a_view():
    assert hylink.links(PID, 4183, "main", ["i1", "g2"]) == (
        "hyimg://board/6f1c2b9e-7d35-4c1b-9b7a-2e8d5a0c4f11?page=main&obj=i1,g2", "http://127.0.0.1:4183/?view=canvas&page=main&obj=i1,g2")
    assert hylink.links(PID, 4180, "p2")[0] == "hyimg://board/6f1c2b9e-7d35-4c1b-9b7a-2e8d5a0c4f11?page=p2"
    assert hylink.links(PID, 4180, "main", at="-10,20.5,0.25")[0].endswith("?page=main&at=-10,20.5,0.25")


def test_nothing_outside_the_patterns():
    app, web = hylink.links(PID, 4180, "../x", ["ok", "a/b", "c d"], at="1,2")
    assert app == "hyimg://board/6f1c2b9e-7d35-4c1b-9b7a-2e8d5a0c4f11?obj=ok" and web == "http://127.0.0.1:4180/?view=canvas&obj=ok"
    assert hylink.links("", 4180, "main")[0] == "" and hylink.links("not-a-uuid", 4180, "main")[0] == ""   # a server outside the catalog


def test_main_prints_the_app_link_first(capsys):
    board = {"items": {"i1": {"path": "a.png"}}, "groups": {"g1": {"title": "Styles"}}}
    calls = []

    def api(path, body=None):
        calls.append(path)
        if path.startswith("/api/board"): return 200, board
        if path == "/api/health": return 200, {"projectId": PID, "port": 4181}
        return 404, {}

    def resolve(b, ref):
        if ref == "Styles": return ("group", "g1", "Styles", {})
        raise SystemExit(f"не нашел «{ref}»")

    hylink.main(["i1", "Styles"], "main", api, resolve, "http://localhost:4181")
    out = capsys.readouterr().out.splitlines()
    assert out == ["hyimg://board/6f1c2b9e-7d35-4c1b-9b7a-2e8d5a0c4f11?page=main&obj=i1,g1", "http://127.0.0.1:4181/?view=canvas&page=main&obj=i1,g1"]
    hylink.main([], "main", api, resolve, "http://localhost:4181")
    assert capsys.readouterr().out.splitlines()[0] == "hyimg://board/6f1c2b9e-7d35-4c1b-9b7a-2e8d5a0c4f11?page=main"
