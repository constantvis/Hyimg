"""The stills of HTML pages for the board's cards zoomed in (owner 2026-10-08: «справа мазня, не видно что там»): /thumb hands out 2560
px, a plugin's PREVIEW_KEY names its pictures so the 1280 ones drawn before are drawn again, a thumbnail kept never draws its picture
again, and hy.py look crops a page card from its 2560 still (it asked for s=2048, which /thumb answered with 640 px)."""
import io
import os
import types

from PIL import Image

import hycomments as hc
import server


def plugin(monkeypatch, key="2x", w=2560):
    """a plugin kind "html" whose preview() draws a w-wide picture and counts its calls"""
    calls = []

    def preview(full, out):
        calls.append(full); Image.new("RGB", (w, w * 10 // 16), (20, 20, 24)).save(out)
    mod = types.SimpleNamespace(preview=preview, **({"PREVIEW_KEY": key} if key is not None else {}))
    monkeypatch.setattr(server, "plugin_kinds", lambda: {".html": ("html", "dev")})
    monkeypatch.setattr(server, "plugin_module", lambda name: mod)
    return calls


def page(lib):
    p = lib / "r6" / "c4.html"; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("<h1>c4</h1>"); return p


def test_a_page_still_comes_2560_wide_and_named_by_the_plugins_key(lib, monkeypatch):
    calls = plugin(monkeypatch)
    page(lib)
    with Image.open(server.thumb("r6/c4.html", 2560)) as im:
        assert im.size == (2560, 1600)
    with Image.open(server.thumb("r6/c4.html", 1280)) as im:
        assert im.size == (1280, 800)
    assert len(calls) == 1   # one picture for every size
    assert any(".prev.2x." in n for n in os.listdir(server.THUMBS)), os.listdir(server.THUMBS)


def test_a_thumbnail_kept_never_draws_the_page_again_and_an_old_picture_is_not_taken_for_a_new_one(lib, monkeypatch):
    page(lib)
    calls = plugin(monkeypatch, key=None, w=1280)   # the plugin before 2026-10-08: 1280 px pictures under the plain name
    server.thumb("r6/c4.html", 640)
    calls = plugin(monkeypatch)   # now it draws at twice the size, under its key
    server.thumb("r6/c4.html", 640)
    assert calls == []   # the 640 thumbnail kept: nothing drawn for it
    with Image.open(server.thumb("r6/c4.html", 2560)) as im:
        assert im.size == (2560, 1600)   # not the old 1280 picture
    assert len(calls) == 1


def test_a_key_is_letters_and_digits_only():
    m = types.SimpleNamespace(PREVIEW_KEY="../2x x")
    orig = server.plugin_module
    try:
        server.plugin_module = lambda name: m
        assert server._preview_key(("html", "dev")) == ".2xx"
        assert server._preview_key(None) == ""
        server.plugin_module = lambda name: (_ for _ in ()).throw(KeyError(name))   # a plugin turned off
        assert server._preview_key(("html", "dev")) == ""
    finally:
        server.plugin_module = orig


def test_look_crops_a_page_card_from_its_2560_still(monkeypatch, capsys):
    it = {"type": "html", "src": "r6/c4b.html", "x": 0, "y": 0, "w": 720, "h": 450}
    assert hc.picture_url(it) == "/thumb?s=2560&p=r6/c4b.html"
    assert hc.picture_url({"path": "a/b c.png"}) == "/img?p=a/b%20c.png"
    asked = []

    def got(api, path):
        asked.append(path); b = io.BytesIO(); Image.new("RGB", (2560, 1600), (40, 40, 40)).save(b, "PNG"); return 200, b.getvalue()
    monkeypatch.setattr(hc, "_bytes", got)
    thread = {"id": "t1", "anchor": {"obj": "d1"}, "region": {"u": [0.5, 0.6], "v": [0.25, 0.3]}, "describe": "slider row"}

    def api(path):
        if path.startswith("/api/annotations"): return 200, {"pages": {"main": {"items": [], "threads": [thread]}}}
        return 200, {"items": {"d1": it}}
    hc.look([], "main", api, None, None, {"comment": "t1"}, [])
    out = capsys.readouterr().out.splitlines()
    assert asked == ["/thumb?s=2560&p=r6/c4b.html"]
    with Image.open(out[0]) as im:
        assert im.size[0] >= 256   # a tenth of the page across at 2 device px per css px, and its margin
    assert "из 2560×1600" in out[1]


def test_a_card_of_its_own_viewport_gets_a_still_of_it_kept_apart(lib, monkeypatch):
    """a 1440 × 900 card's page laid out as its live page does (owner 2026-10-08: drawn at 1280 its text jumped when the page faded in)"""
    drawn = []

    def preview_at(full, out, w, h):
        drawn.append((w, h)); Image.new("RGB", (2 * w, 2 * h), (20, 20, 24)).save(out)
    mod = types.SimpleNamespace(preview=lambda full, out: preview_at(full, out, 1280, 800), preview_at=preview_at, PREVIEW_KEY="2x")
    monkeypatch.setattr(server, "plugin_kinds", lambda: {".html": ("html", "dev")})
    monkeypatch.setattr(server, "plugin_module", lambda name: mod)
    page(lib)
    view = server.view_of("r6/c4.html", "1440", "900")
    assert view == (1440, 900)
    with Image.open(server.thumb("r6/c4.html", 2560, 1, view)) as im:
        assert im.size == (2560, 1600)   # 2880 × 1800 drawn, handed out 2560 wide
    with Image.open(server.thumb("r6/c4.html", 640)) as im:
        assert im.size == (640, 400)
    server.thumb("r6/c4.html", 1280, 1, view)
    assert drawn == [(1440, 900), (1280, 800)]   # one drawing per viewport, the 1280 one of the grid apart
    assert any(".v1440x900." in n for n in os.listdir(server.THUMBS))
    assert server.view_of("r6/c4.html", "99999", "9") == (4000, 200)
    assert server.view_of("r6/c4.html", "wide", "900") is None


def test_a_viewport_is_for_a_plugin_that_can_draw_one(lib, monkeypatch):
    plugin(monkeypatch)   # preview only, no preview_at
    page(lib)
    assert server.view_of("r6/c4.html", "1440", "900") is None
    p = lib / "a.png"; p.write_bytes(b"")
    assert server.view_of("a.png", "1440", "900") is None


def test_look_asks_for_the_cards_own_viewport():
    it = {"type": "html", "src": "r6/c4b.html", "vw": 1440, "w": 720, "h": 450}
    assert hc.picture_url(it) == "/thumb?s=2560&p=r6/c4b.html&vw=1440&vh=900"
