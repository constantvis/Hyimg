"""How long a file took to make, what it cost and where it ran (owner 2026-10-11 on the Info card of a LaMa clean-up in the Concepts library:
«вот тут нужно ещё обязательно затраченное время на генерацию или рендеринг, обязательный параметр, и количество токенов или кредитов
потраченных при возможности, либо compute power какой-то условный»; then «ну это для 3д генераций в том числе»).

- review/runmeta.py reads the spellings agents already write (seconds, params.seconds, time_s, render_seconds, ms, render.times; usage,
  credits, cost; compute, engine, device, samples) into one view; "duration" is a video's length and is not read
- the Info card's Generation: Time from top-level seconds, from params.seconds and from ms, «not recorded» quietly when a generated file has
  none, Total of the chain behind it, Cost (tokens, credits with the service, dollars), Compute; a 3D card names its model file's time
- POST /api/htmlstill writes the still's json with seconds and compute
- `hy.py undocumented` lists a generated file without seconds
Chromium, dark theme, a temporary library, the 3D plugin from its repository's last commit.
"""
import io
import json
import os
import struct
import subprocess
import sys
import tarfile
import time
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "review"))

PICS = {   # id: (file, its json)
    "t": ("a/top.png", {"model": "LaMa ONNX", "prompt": "a clean plate", "seconds": 892.7, "params": {"seconds": 892.7}, "inputs": ["a/sam.png"]}),
    "s": ("a/sam.png", {"model": "SAM 3", "prompt": "the phone's mask", "params": {"seconds": 60.9}}),
    "m": ("a/ms.png", {"model": "SAM 3", "prompt": "a word's masks", "ms": 800}),
    "n": ("a/none.png", {"model": "Gemini 3 Pro Image", "prompt": "a still life"}),
    "c": ("a/paid.png", {"model": "Firefly Image 4", "prompt": "a poster", "seconds": 4000, "compute": "Firefly web",
                         "cost": {"tokens": {"in": 1200, "out": 800}, "credits": {"n": 12, "service": "Firefly"}, "usd": 0.04}}),
    "u": ("a/usage.png", {"model": "Blender + Gemini", "prompt": "a render", "time_s": {"render": 8.37, "comp": 1.65}, "engine": "BLENDER_EEVEE",
                          "device": "mps", "samples": 64, "usage": {"promptTokenCount": 998, "candidatesTokenCount": 1391, "totalTokenCount": 2656}}),
    "v": ("a/clip.png", {"model": "Kling 2.5", "prompt": "a turn", "credits": 325, "duration": 30.1}),
}


def glb():
    """a glb with one triangle: what a 3D service hands back, small"""
    pos = struct.pack("<9f", 0, 0, 0, 0.1, 0, 0, 0, 0.1, 0)
    j = json.dumps({"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
                    "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}], "buffers": [{"byteLength": 36}],
                    "bufferViews": [{"buffer": 0, "byteLength": 36}],
                    "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [0, 0, 0], "max": [0.1, 0.1, 0]}]}).encode()
    j += b" " * (-len(j) % 4)
    return b"glTF" + struct.pack("<II", 2, 12 + 8 + len(j) + 8 + 36) + struct.pack("<II", len(j), 0x4E4F534A) + j + struct.pack("<II", 36, 0x004E4942) + pos


@contextmanager
def world(tmp):
    """a temporary library and its server with the 3D plugin: (port, lib)"""
    lib, state, plugins = tmp / "lib", tmp / "state", tmp / "plugins"
    for d in (lib / "a", lib / "site", lib / "models", lib / "3d/scenes/s1", state / "boards", plugins, tmp / "home"): d.mkdir(parents=True)
    items = {}
    for k, (id_, (path, meta)) in enumerate(PICS.items()):
        (lib / path).write_bytes(png(40 + k, 60)); (lib / path).with_suffix(".json").write_text(json.dumps(meta))
        items[id_] = {"path": path, "x": k * 220, "y": 0, "w": 180, "ar": (40 + k) / 60, "crop": None}
    (lib / "models/gen.glb").write_bytes(glb())   # an image-to-3D model with its credits and time, in a scene of its own
    (lib / "models/gen.glb.json").write_text(json.dumps({"model": "Meshy 5", "seconds": 95, "cost": {"credits": {"n": 20, "service": "Meshy"}}}))
    cam = {"id": "c1", "name": "Front", "lens": 50, "sensor": 36, "sensor_h": 24, "fit": "AUTO", "shift": [0, 0], "clip": [0.01, 100],
           "loc": [0.3, -0.5, 0.2], "rot": [1, 0, 0, 0]}
    (lib / "3d/scenes/s1/scene.json").write_text(json.dumps({"format": "hyimg-scene/1", "rev": 1, "lights": [], "cameras": [cam], "active_camera": "c1",
        "objects": [{"id": "o1", "name": "Gen", "src": {"type": "file", "path": "models/gen.glb"}, "loc": [0, 0, 0], "rot": [1, 0, 0, 0], "scale": [1, 1, 1]}]}))
    items["s3"] = {"type": "model3d", "scene": "3d/scenes/s1/scene.json", "camera": "c1", "x": 0, "y": 300, "w": 300, "h": 225}
    (lib / "site/index.html").write_text("<!doctype html><html><head><title>Site</title></head><body><h1>A page</h1></body></html>")
    src = ROOT.parent / "hyimg-3d-studio"
    if not (src / "manifest.json").is_file(): pytest.skip("hyimg-3d-studio is not beside this repository")
    raw = subprocess.run(["git", "-C", str(src), "archive", "HEAD"], capture_output=True, check=True).stdout
    (plugins / "3d").mkdir(); tarfile.open(fileobj=io.BytesIO(raw)).extractall(plugins / "3d", filter="data")
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    (tmp / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()),
               HYIMG_SETTINGS=str(tmp / "settings.json"), HYIMG_PLUGINS=str(plugins), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(150):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError: time.sleep(0.1)
        yield port, lib
    finally:
        proc.terminate(); proc.wait(5); log.close()


def get(port, path):
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=60))


def test_runmeta_reads_the_spellings_agents_write():
    import runmeta
    of = runmeta.of
    assert of({"seconds": 892.7, "model": "LaMa"}) == {"seconds": 892.7, "made": True}
    assert of({"params": {"seconds": 60.9}})["seconds"] == 60.9 and of({"ms": 800})["seconds"] == 0.8
    assert of({"metrics": {"time_s": 46.1}})["seconds"] == 46.1 and of({"render_seconds": 62.8})["seconds"] == 62.8
    assert of({"time_s": {"render": 8.37, "estimate": None, "comp": 1.65}})["seconds"] == 10.02
    assert of({"render": {"times": {"mesh": 0.39, "render": 1.74, "total": 2.14}, "engine": "EEVEE"}})["seconds"] == 2.14
    assert "seconds" not in of({"model": "Kling", "duration": 30.1, "duration_s": 34})   # a video's length is not the time it took
    assert of({"cost": "подписка ChatGPT"})["cost"] == {"note": "подписка ChatGPT"}
    assert of({"credits": 325})["cost"] == {"credits": {"n": 325}}
    assert of({"usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}})["cost"] == {"tokens": {"in": 10, "out": 20, "total": 30}}
    assert of({"total": 18, "model": "x"}) == {"made": True}   # «total» alone is not tokens
    assert of({"cost_usd": 0.04})["cost"] == {"usd": 0.04}
    assert of({"engine": "Cycles", "device": "GPU", "samples": 128})["compute"] == "Cycles · GPU · 128 samples"
    assert of({"compute": "Codex CLI", "engine": "x"})["compute"] == "Codex CLI"
    assert of({"model": "Pinterest", "source_url": "https://example.com/p"}) == {}   # a downloaded reference: nobody here made it


def test_items_and_meta_carry_the_run_and_the_chain(tmp_path):
    with world(tmp_path) as (port, lib):
        items = {i["path"]: i for i in get(port, "/api/items")}
        assert items["a/top.png"]["run"] == {"seconds": 892.7, "made": True}
        assert items["a/none.png"]["run"] == {"made": True}
        assert items["models/gen.glb"]["run"]["seconds"] == 95   # a 3D file of the library: its own json (<file>.glb.json)
        meta = get(port, "/api/meta?p=a/top.png")["run"]
        assert meta["seconds"] == 892.7 and meta["chain"]["seconds"] == round(892.7 + 60.9, 3) and meta["chain"]["steps"] == 2, meta
        scene = get(port, "/api/meta?p=3d/scenes/s1/scene.json")["run"]
        assert scene["chain"]["parts"] == [{"path": "models/gen.glb", "run": {"seconds": 95, "cost": {"credits": {"n": 20, "service": "Meshy"}}, "made": True}}]


def test_an_html_still_records_its_seconds(tmp_path):
    with world(tmp_path) as (port, lib):   # the json beside the still says how long and by what
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/htmlstill?p=site/index.html&w=400&h=300", data=b"", method="POST")
        res = json.load(urllib.request.urlopen(req, timeout=180))
        side = json.loads((lib / res["path"]).with_suffix(".json").read_text())
        assert res["seconds"] > 0 and res["compute"].startswith("local · ") and side["seconds"] == res["seconds"], (res, side)
        assert side["inputs"] == ["../index.html"] and side["compute"] == res["compute"]


def test_undocumented_lists_generated_files_without_seconds(tmp_path):
    with world(tmp_path) as (port, lib):   # the check agents run: a generated file without a time by name, the timed ones not
        env = {k: v for k, v in os.environ.items() if not k.startswith("HYIMG_")} | {"HYIMG_PORT": str(port), "PYTHONDONTWRITEBYTECODE": "1"}
        out = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "undocumented", "a"], env=env, capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stderr
        tail = out.stdout.split("без времени", 1)
        assert len(tail) == 2 and "none.png" in tail[1] and "clip.png" in tail[1] and "top.png" not in tail[1], out.stdout
        assert "2 кадров сделанных без времени" in out.stdout, out.stdout


ROWS = """() => Object.fromEntries([...document.querySelectorAll('#iNotes dl.spec dt')].map(dt => [dt.textContent,
  [dt.nextElementSibling.textContent, !!dt.nextElementSibling.querySelector('.muted')]]))"""


def test_info_shows_time_cost_and_compute(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    with world(tmp_path) as (port, lib), playwright.sync_playwright() as p:
        try: browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1500, "height": 900}, color_scheme="dark")
        page.errors = []; page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/canvas.html")
        page.evaluate("""() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0');
          localStorage.setItem('cv.cam.main', JSON.stringify({ x: -60, y: -80, z: .8 })); }""")
        page.reload()
        page.wait_for_function("() => typeof BOARD !== 'undefined' && PLG.model3d && ['t', 'n', 's3'].every(i => EL.get(i))", timeout=30000)
        page.wait_for_function("() => typeof byPath !== 'undefined' && byPath.get('a/top.png')", timeout=20000)

        def pick(id_, want):
            """the card clicked with the mouse; the Info card's spec rows once they show `want`"""
            box = page.evaluate("id => { const r = EL.get(id).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", id_)
            page.mouse.click(*box)
            page.wait_for_function(f"() => sel.size === 1 && sel.has({json.dumps(id_)}) && ({ROWS})()[{json.dumps(want)}]", timeout=15000)
            return page.evaluate(ROWS)

        r = pick("t", "Total")
        assert r["Time"] == ["14 min 53 s", False] and r["Total"][0] == "15 min 54 s · 2 steps" and r["Model"][0] == "LaMa ONNX", r
        assert pick("s", "Time")["Time"] == ["1 min 1 s", False]   # from params.seconds
        assert pick("m", "Time")["Time"] == ["0.8 s", False]
        r = pick("n", "Time")
        assert r["Time"] == ["not recorded", True] and "Cost" not in r and "Compute" not in r, r   # missing, and seen: quietly
        r = pick("c", "Cost")
        assert r["Time"][0] == "1 h 06 min" and r["Cost"][0] == "1,200 in / 800 out tokens · 12 credits · Firefly · $0.04", r
        assert r["Compute"][0] == "Firefly web", r
        r = pick("u", "Compute")
        assert r["Time"][0] == "10 s" and r["Cost"][0] == "998 in / 1,391 out tokens" and r["Compute"][0] == "EEVEE · mps · 64 samples", r
        r = pick("v", "Cost")
        assert r["Time"] == ["not recorded", True] and r["Cost"][0] == "325 credits", r   # its «duration» is the clip's length
        r = pick("s3", "gen.glb")   # a 3D card: its model file's time and credits
        assert r["gen.glb"][0] == "1 min 35 s · 20 credits · Meshy", r
        assert not page.errors, page.errors
        browser.close()
