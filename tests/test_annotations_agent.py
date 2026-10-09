"""An agent reads the drawings and the comments' areas without looking at the board (owner 2026-10-07: «как аннотации будут работать в
json? ... чтобы они всё понимали, не смотря на картинки»): every annotation and thread file carries `describe`, `region` and the links
between them; hy.py annotations, find, map and comments print them; hy.py look crops the marked region of the picture's own pixels."""
import io
import json
import os
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

from test_shortcuts import run_server

ROOT = Path(__file__).resolve().parents[1]
ME = str(uuid.uuid4())


def post(port, path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=10))


def hy(port, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("HYIMG_")} | {"HYIMG_PORT": str(port), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), *args, "--page", "main"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def picture(lib):
    im = Image.new("RGB", (400, 600), (240, 240, 240))
    im.paste((220, 30, 30), (200, 60, 360, 240))   # the red patch the marks point at
    im.save(lib / "a" / "1.png")


def test_marks_in_words_for_agents(tmp_path):
    (tmp_path / "profile.json").write_text(json.dumps({"id": ME, "name": "Ann Lee", "color": "green", "created": ""}))
    servers = run_server(tmp_path, more=picture); port = next(servers)
    try:
        a = post(port, "/api/annotations", {"op": "put", "name": "main", "item": {"kind": "ellipse", "color": "red", "w": .01, "pts": [[.5, .1], [.9, .4]],
                                                                                 "anchor": {"obj": "i1", "kind": "picture", "file": "a/1.png"}}})["items"][0]
        t = post(port, "/api/comments", {"op": "new", "name": "main", "anchor": {"obj": "i1", "kind": "picture", "file": "a/1.png"}, "at": [.9, .1],
                                         "area": [.5, .1, .4, .3], "text": "небо темнее"})["thread"]
        post(port, "/api/annotations", {"op": "put", "name": "main", "item": {"kind": "arrow", "color": "blue", "w": .01, "pts": [[.5, .9], [1.5, .5]],
                                                                            "anchor": {"obj": "i1", "kind": "picture", "file": "a/1.png"}}})
        # the files say it themselves: describe, region, the links both ways
        f = json.loads((tmp_path / "lib" / "annotations" / f"main__{a['id']}.json").read_text())
        assert f["describe"].startswith("красный овал вокруг области вверху справа: x 50–90 %, y 10–40 % = px 200–360 × 60–240 из 400×600, на кадре a/1.png")
        assert f["region"]["px"] == [200, 360, 60, 240] and f["about"] == [t["id"]] and "→ комментарий" in f["describe"]
        th = json.loads((tmp_path / "lib" / "comments" / f"main__{t['id']}.json").read_text())
        assert th["describe"].startswith("область вверху справа: x 50–90 %, y 10–40 % = px 200–360 × 60–240") and a["id"] in th["marks"]
        assert th["area"] == [.5, .1, .4, .3]
        out = hy(port, "annotations")
        assert f"✎ [{a['id']}] красный овал вокруг области вверху справа" in out and "синяя стрелка от кадра a/1.png" in out and "к кадру a/2.png" in out
        assert f"комментарий [{t['id']}] область вверху справа" in out and "«небо темнее»" in out, out
        assert "a/1.png [i1]" in out
        out = hy(port, "find", "i1")
        assert f"✎ красный овал" in out and f"[{a['id']}]" in out and f"[{t['id']}]" in out, out
        hy(port, "do", 'text "Небо" x=340 y=-200', "--quiet")
        out = hy(port, "map", "Небо")   # what lies around a heading: the things with marks, and the marks
        assert f"пометки на a/1.png [i1]:" in out and f"[{t['id']}]" in out, out
        out = hy(port, "comments")
        assert f"[{t['id']}] страница main, область вверху справа: x 50–90 %" in out and f"; рисунки: {a['id']}," in out, out   # the arrow is elsewhere
        for flag, mid in (("--ann", a["id"]), ("--comment", t["id"])):
            out = hy(port, "look", flag, mid)
            png = out.splitlines()[0]
            im = Image.open(png)
            assert im.size == (193, 213), im.size   # px 200–360 × 60–240 and 16 px around
            assert im.getpixel((96, 106))[0] > 200 and im.getpixel((96, 106))[1] < 60   # the red patch in the middle
            assert "px 184–377 × 44–257 из 400×600" in out
        assert hy(port, "annotations", "--author", "nobody").count("✎") == 0
    finally:
        servers.close()
