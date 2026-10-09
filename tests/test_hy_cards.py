"""hy.py for every card and look of the board (2026-10-06, the «Playground» page of «Hyimg App»): pages, a 3D card from a glb, Dev
studio's HTML card, crop, time, opacity, PDF page, colour grade, master mask, presets of properties and the feature catalog, on a
temporary library through a throwaway server, as an agent runs them."""
import io
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HY = ROOT / "review/hy.py"
PLUGIN_3D = ROOT.parent / "hyimg-3d-studio"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


def glb():
    """one triangle 0.1 m wide, 0.2 m tall: a valid glb with POSITION min and max"""
    pos = struct.pack("<9f", -0.05, 0, 0, 0.05, 0, 0, 0, 0.2, 0)
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [-0.05, 0, 0], "max": [0.05, 0.2, 0]}],
           "bufferViews": [{"buffer": 0, "byteLength": len(pos)}], "buffers": [{"byteLength": len(pos)}]}
    js = json.dumps(doc).encode(); js += b" " * (-len(js) % 4); bin_ = pos + b"\0" * (-len(pos) % 4)
    body = struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(bin_), b"BIN\0") + bin_
    return b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body


@pytest.fixture
def hyimg(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "lib/_review"
    (lib / "pics").mkdir(parents=True)
    for n in range(3): Image.new("RGB", (60, 40), (40 + 60 * n, 90, 150)).save(lib / "pics" / f"{n}.png")
    a = Image.new("RGBA", (60, 40), (0, 0, 0, 0)); a.paste((220, 60, 60, 255), (15, 10, 45, 30)); a.save(lib / "pics" / "alpha.png")
    Image.new("RGB", (60, 80), (200, 200, 200)).save(lib / "doc.pdf", save_all=True, append_images=[Image.new("RGB", (60, 80), (90, 90, 90))] * 2)
    (lib / "3d").mkdir(); (lib / "3d" / "tri.glb").write_bytes(glb())
    (lib / "page.html").write_text("<!doctype html><title>t</title><p>test</p>")
    (state / "boards").mkdir(parents=True)
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "Главная"}]}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "ru"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    plugins = tmp_path / "plugins"; plugins.mkdir()   # only the 3D plugin, linked as the app links it
    if PLUGIN_3D.is_dir(): (plugins / "3d").symlink_to(PLUGIN_3D)
    env["HYIMG_PLUGINS"] = str(plugins)
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)

    def hy(*args, ok=True):
        r = subprocess.run([sys.executable, str(HY), "--page", "main", *args], env={**env, "HYIMG_PORT": str(port)}, capture_output=True, text=True, timeout=120)
        if ok: assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout + r.stderr

    def board(page="main"):
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/board?name={page}"))

    for _ in range(50):   # the library has listed the files
        if len(json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/items"))) >= 5: break
        time.sleep(0.2)
    hy("do", 'block "pics/*" x=0 y=0 note="# Пробы"', "--quiet")
    try:
        yield hy, board, lib
    finally:
        proc.terminate(); proc.wait(5); log.close()


def pic(board, name):
    return next(i for i, it in board()["items"].items() if it.get("path") == f"pics/{name}")


def test_pages_and_a_new_page(hyimg):
    hy, board, lib = hyimg
    out = hy("page", "new", "Песочница")
    pid = out.split("(")[1].split(")")[0]
    assert "«Песочница»" in hy("pages") and (lib / "_review/boards/pages.json").read_text().count(pid) == 1
    assert "уже есть" in hy("page", "new", "песочница", ok=False)


def test_looks_by_the_canvas_rules(hyimg):
    hy, board, lib = hyimg
    p0, p1, al = pic(board, "0.png"), pic(board, "1.png"), pic(board, "alpha.png")
    hy("do", f"crop {p0} box=0.1,0.2,0.9,0.8; opacity {p1} value=0.5", "--quiet")
    b = board()["items"]
    assert b[p0]["crop"] == [0.1, 0.2, 0.9, 0.8] and b[p1]["opacity"] == 0.5
    out = hy("do", f"trim {p0} in=1 out=2", "--quiet")
    assert "не подходит 1" in out and "trim" not in board()["items"][p0]
    hy("do", f"grade {p0} {p1} exposure=0.3 hue=20", "--quiet")
    assert board()["items"][p0]["grade"] == {"exposure": 0.3, "hs": {"master": {"hue": 20}}}
    hy("do", f"grade {p1} clear=1; crop {p0} clear=1", "--quiet")
    b = board()["items"]
    assert "grade" not in b[p1] and "crop" not in b[p0] and b[p0]["grade"]
    out = hy("do", f"mask {al} {p1} alpha=1", "--quiet")
    m = board()["items"][al]["mask"]["file"]
    assert m.startswith("frames/board-masks/masks/") and (lib / m).is_file() and "без прозрачных пикселей 1" in out
    assert Image.open(lib / m).getchannel("A").getextrema() == (0, 255)


def test_pdf_page_and_presets(hyimg):
    hy, board, lib = hyimg
    hy("do", 'block "doc.pdf" x=0 y=900', "--quiet")
    d = next(i for i, it in board()["items"].items() if it.get("path") == "doc.pdf")
    hy("do", f"pdfpage {d} n=3", "--quiet")
    assert board()["items"][d]["page"] == 3
    p0, p2 = pic(board, "0.png"), pic(board, "2.png")
    hy("do", f"grade {p0} saturation=-40; opacity {p0} value=0.8", "--quiet")
    assert "пресет «Тихий»" in hy("preset", "save", "Тихий", p0, "only=grade")
    assert "«Тихий»: цветокор" in hy("presets")
    hy("do", f'props preset=Тихий to={p2}', "--quiet")
    b = board()["items"]
    assert b[p2]["grade"] == {"saturation": -40} and "opacity" not in b[p2]
    hy("preset", "delete", "Тихий")
    assert "пресетов нет" in hy("presets")


def test_html_card_needs_dev_studio(hyimg):
    hy, board, lib = hyimg
    assert "Dev Studio" in hy("do", "html page.html x=0 y=2000", ok=False)
    hy("do", "html page.html x=0 y=2000 force=1", "--quiet")
    card = next(it for it in board()["items"].values() if it.get("type") == "html")
    assert card["src"] == "page.html" and card["pics"] == ["page.html"] and card["vw"] == 1280 and card["h"] == 300


@pytest.mark.skipif(not PLUGIN_3D.is_dir(), reason="the 3D plugin's working copy is not beside hyimg")
def test_model_card_from_a_glb(hyimg):
    hy, board, lib = hyimg
    out = hy("do", 'model 3d/tri.glb near="Пробы" side=below w=300', "--quiet")
    card = next(it for it in board()["items"].values() if it.get("type") == "model3d")
    doc = json.loads((lib / card["scene"]).read_text())
    assert doc["format"] == "hyimg-scene/1" and card["camera"] == doc["active_camera"] == doc["cameras"][0]["id"]
    obj = doc["objects"][0]
    assert obj["src"] == {"type": "file", "path": "3d/tri.glb"} and obj["scale"] == [1, 1, 1] and abs(obj["loc"][2] - 0.0005) < 1e-6
    assert card["w"] == 300 and card["h"] == 375 and "сцена 3d/scenes/" in out
    w, x, y, z = doc["cameras"][0]["rot"]
    assert abs(w * w + x * x + y * y + z * z - 1) < 1e-3


def test_save_takes_a_video_and_names_its_json(hyimg, tmp_path):
    hy, board, lib = hyimg
    (tmp_path / "dl").mkdir(); (tmp_path / "dl/clip.mp4").write_bytes(b"\0\0\0\x18ftypmp42" + b"\0" * 64)
    (tmp_path / "dl/clip.json").write_text(json.dumps({"prompt": "проба", "model": "veo"}))
    out = hy("save", str(tmp_path / "dl/clip.mp4"), "--to", "batch")
    assert "сохранил 1" in out and (lib / "batch/clip.mp4").is_file()
    assert json.loads((lib / "batch/clip.mp4.json").read_text())["model"] == "veo"
    assert "уже есть" in hy("save", str(tmp_path / "dl/clip.mp4"), "--to", "batch")


def test_features_command(hyimg):
    hy, board, lib = hyimg
    out = hy("features", "маска")
    assert "## Мастер-маска (mask)" in out and "mask <id> alpha=1" in out
