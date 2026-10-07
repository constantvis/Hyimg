"""Photoshop, Illustrator, TIFF, SVG and video files in the library (owner 2026-10-04, project «Lookbook FW27»: «add video and Photoshop
files; even if we do not open them, there must be a preview»). On disposable libraries only."""
import io
import json
import shutil
import struct
import subprocess

from PIL import Image
import pytest

from test_server_integration import get, request, servers  # noqa: F401  (servers is the fixture)


def psd(w, h, rgb):
    # the smallest PSD: header, three empty sections, the composite as raw planes (what Photoshop keeps for «maximize compatibility»)
    head = b"8BPS" + struct.pack(">H6xHIIHH", 1, 3, h, w, 8, 3)
    body = struct.pack(">III", 0, 0, 0) + struct.pack(">H", 0) + b"".join(bytes([c]) * (w * h) for c in rgb)
    return head + body


def jpeg_size(body):
    return Image.open(io.BytesIO(body)).size


def test_previews_sizes_own_json_and_video(servers, tmp_path):
    lib = tmp_path / "media"
    (lib / "set").mkdir(parents=True)
    Image.new("RGB", (40, 30), "red").save(lib / "set/IMG_1.png")
    (lib / "set/IMG_1.psd").write_bytes(psd(64, 32, (0, 120, 255)))
    Image.new("RGB", (30, 60), "green").save(lib / "set/scan.tif")
    (lib / "set/empty.psd").write_bytes(b"")   # a 0-byte file: a grey card, never a hung request
    (lib / "set/logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="200" height="100" fill="#f60"/></svg>')
    ff = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    video = shutil.which("ffmpeg") is not None or __import__("os").path.exists(ff)
    if video:
        subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=2", "-pix_fmt", "yuv420p", str(lib / "set/clip.mp4")], check=True)
    _, port, _, _ = servers("media", root=lib)

    items = {i["path"]: i for i in get(port, "/api/items")}
    assert "kind" not in items["set/IMG_1.png"]
    assert items["set/IMG_1.psd"]["kind"] == "doc" and items["set/IMG_1.psd"]["ext"] == "PSD"
    assert items["set/scan.tif"]["kind"] == "doc" and items["set/logo.svg"]["kind"] == "doc"

    # a preview at every size the pages ask for, in the file's own shape
    status, body = request(port, "/thumb?p=set/IMG_1.psd&s=320")
    assert status == 200 and abs(jpeg_size(body)[0] / jpeg_size(body)[1] - 2) < 0.05
    status, body = request(port, "/img?p=set/IMG_1.psd")
    px = Image.open(io.BytesIO(body)).convert("RGB").getpixel((5, 5))
    assert status == 200 and all(abs(a - b) < 6 for a, b in zip(px, (0, 120, 255))), px
    for p in ("set/scan.tif", "set/logo.svg", "set/empty.psd"):
        status, body = request(port, f"/thumb?p={p}&s=96")
        assert status == 200 and jpeg_size(body)[0] > 0, p
    status, body = request(port, "/api/sizes", {"paths": ["set/IMG_1.psd", "set/scan.tif"]})
    sizes = json.loads(body)
    assert sizes["set/IMG_1.psd"] == [64, 32] and sizes["set/scan.tif"][0] / sizes["set/scan.tif"][1] == 0.5

    # IMG_1.psd and IMG_1.png lie side by side: each keeps its own rating
    assert request(port, "/api/feedback", {"path": "set/IMG_1.psd", "fav": True, "comment": "the layered one"})[0] == 200
    assert (lib / "set/IMG_1.psd.json").is_file() and not (lib / "set/IMG_1.json").exists()
    items = {i["path"]: i for i in get(port, "/api/items")}
    assert items["set/IMG_1.psd"]["feedback"]["comment"] == "the layered one" and not items["set/IMG_1.png"]["feedback"]

    if not video:
        pytest.skip("no ffmpeg for the video half")
    clip = items["set/clip.mp4"]
    assert clip["kind"] == "video" and abs(clip["duration"] - 2) < 0.3
    status, body = request(port, "/thumb?p=set/clip.mp4&s=320")
    assert status == 200 and jpeg_size(body) == (320, 180)
    size = (lib / "set/clip.mp4").stat().st_size
    status, body = request(port, "/file?p=set/clip.mp4", headers={"Range": "bytes=0-99"})
    assert status == 206 and len(body) == 100 and body == (lib / "set/clip.mp4").read_bytes()[:100]
    status, body = request(port, "/file?p=set/clip.mp4", headers={"Range": f"bytes=-10"})
    assert status == 206 and body == (lib / "set/clip.mp4").read_bytes()[size - 10:]


def test_library_and_canvas_show_the_format_and_play_a_video(servers, tmp_path):
    from playwright.sync_api import sync_playwright
    ff = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    if not __import__("os").path.exists(ff):
        pytest.skip("no ffmpeg")
    lib = tmp_path / "ui"
    (lib / "s").mkdir(parents=True)
    (lib / "s/layered.psd").write_bytes(psd(80, 40, (200, 30, 30)))
    subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=75", "-pix_fmt", "yuv420p", str(lib / "s/clip.mp4")], check=True)
    (lib / "_review/boards").mkdir(parents=True)
    (lib / "_review/boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "groups": {}, "items": {
        "a": {"path": "s/layered.psd", "x": 0, "y": 0, "w": 320, "ar": 2}, "b": {"path": "s/clip.mp4", "x": 360, "y": 0, "w": 320, "ar": 16 / 9}}}))
    _, port, _, _ = servers("ui", root=lib)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/?view=lib")
        page.wait_for_selector(".card .pill.kd")
        assert sorted(page.locator(".card .pill.kd").all_inner_texts()) == ["PSD", "▶ 1:15"]
        assert page.evaluate("() => [...document.querySelectorAll('.card img')].every(i => i.complete && i.naturalWidth > 0)")
        page.locator(".card", has_text="clip").first.click()
        page.wait_for_selector("#vid:not([hidden])")
        page.wait_for_function("() => document.querySelector('#vid').readyState >= 1", timeout=10000)
        assert page.evaluate("() => Math.round(document.querySelector('#vid').duration)") == 75
        page.keyboard.press("Escape")
        page.goto(f"http://127.0.0.1:{port}/canvas.html")
        page.wait_for_function("() => document.querySelectorAll('.it .kd:not(:empty)').length === 2 && document.querySelector('.it.vid.vok')", timeout=10000)
        # a video card big enough to play has its round ▶ beside the length (owner 2026-10-05), a small one keeps «▶ 1:15»
        assert sorted(page.locator(".it .kd").all_inner_texts()) == ["1:15", "PSD"] and page.locator(".it.vid.vok .vp").count() == 1
        page.wait_for_function("() => [...document.querySelectorAll('.it img')].every(i => i.complete && i.naturalWidth > 0)", timeout=10000)
        assert not errors, errors
        browser.close()


def test_folders_docked_on_the_left_with_a_filter(servers, tmp_path):
    """Owner 2026-10-04: «a file system like the layers in the 3D studio, pinned on the left, only folders, and it can fold away»."""
    from playwright.sync_api import sync_playwright
    lib = tmp_path / "tree"
    for d in ("iPhone 17 for AI/untitled folder", "iPhone 17 for AI/_", "wallpaper"):
        (lib / d).mkdir(parents=True)
        Image.new("RGB", (20, 20), (len(d) * 7 % 256, 40, 90)).save(lib / d / f"{len(d)}.png")   # all different: copies fold into one
    Image.new("RGB", (20, 20), "red").save(lib / "loose.png")
    _, port, _, _ = servers("tree", root=lib)
    assert any(i["path"] == "loose.png" and i["title"] == "В корне доски" for i in get(port, "/api/items"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/?view=lib")
        page.wait_for_selector("body.fdock .fdrawer .frow")
        names = page.locator(".fdrawer .frow .fn").all_inner_texts()
        assert "В корне доски" in names and "iPhone 17 for AI" in names and not any(n.endswith(".png") for n in names)
        side, grid = page.locator(".fdrawer").bounding_box(), page.locator("main").bounding_box()
        assert side["x"] + side["width"] <= grid["x"] + 1, "the tree sits beside the frames, not over them"
        # the dock stands over the frames, never over the folders; the folders' edge drags wider, and stays so
        head = page.locator("header").bounding_box()
        assert head["x"] >= side["x"] + side["width"], (head, side)
        g = page.locator("#fgrip").bounding_box(); gx, gy = g["x"] + g["width"] / 2, g["y"] + 300
        page.mouse.move(gx, gy); page.mouse.down(); page.mouse.move(gx + 120, gy, steps=6); page.mouse.up()
        wide = page.locator(".fdrawer").bounding_box()["width"]
        assert abs(wide - side["width"] - 120) <= 3, (wide, side["width"])
        page.goto(f"http://127.0.0.1:{port}/?view=panel"); page.wait_for_selector("body.fdock.cv-on .fdrawer .frow")
        side, head = page.locator(".fdrawer").bounding_box(), page.locator("header").bounding_box()
        assert head["x"] >= side["x"] + side["width"] - 1, (head, side)
        page.goto(f"http://127.0.0.1:{port}/?view=lib"); page.wait_for_selector("body.fdock .fdrawer .frow")
        assert abs(page.locator(".fdrawer").bounding_box()["width"] - wide) <= 2, "the width is kept"
        page.fill("#ffilt", "untitled")
        assert page.locator(".fdrawer .frow .fn").all_inner_texts() == ["Все папки", "iPhone 17 for AI", "untitled folder"]
        page.fill("#ffilt", "")
        page.click(".fbar .fticon")   # the folders' toggle lives in the path bar (owner 2026-10-04)
        page.wait_for_function("() => !document.body.classList.contains('fdock')")
        page.wait_for_selector(".fdrawer", state="hidden")
        page.reload(); page.wait_for_selector(".fbar [data-ftree]")
        assert not page.evaluate("() => document.body.classList.contains('fdock')"), "folded stays folded"
        page.click(".fbar [data-ftree]"); page.wait_for_selector("body.fdock")
        assert not errors, errors
        browser.close()


def test_server_words_follow_the_app_language(servers, tmp_path):
    """Two languages (owner 2026-10-06: «make 2 versions, Russian and English, switchable in settings»): what the server writes for
    the interface (collection names, errors, default names, labels) follows the app's setting cv.lang, read on each request."""
    lib = tmp_path / "lang"; lib.mkdir()
    Image.new("RGB", (20, 20), "red").save(lib / "loose.png")
    _, port, _, _ = servers("lang", root=lib)
    settings = tmp_path / "lang-settings.json"
    assert any(i["title"] == "В корне доски" for i in get(port, "/api/items"))
    settings.write_text("{}")   # English, the default
    assert any(i["path"] == "loose.png" and i["title"] == "Board root" for i in get(port, "/api/items"))
    assert get(port, "/api/pages")["pages"][0]["title"] == "Page 1"
    status, body = request(port, "/api/upload?name=x.png", b"not an image", "application/octet-stream")
    assert status == 400 and body.decode().startswith("Couldn't add the image: not an image"), body
    status, body = request(port, "/api/upload?name=ref.png", _png(), "application/octet-stream")
    assert status == 200, body
    meta = json.loads((lib / (json.loads(body)["path"].rsplit(".", 1)[0] + ".json")).read_text())
    assert meta["model"] == "pasted by the owner" and meta["prompt"].startswith("pasted on the canvas by the owner") and "from the file ref.png" in meta["prompt"], meta
    (lib / "_review/boards").mkdir(parents=True, exist_ok=True); (lib / "_review/boards/main.json").write_text('{"schema": 1, "items": {}, "groups": {}}')
    status, body = request(port, "/api/history", {"action": "save", "name": "main"})
    assert status == 200 and json.loads(body)["label"] == "version", body
    settings.write_text(json.dumps({"cv.lang": "ru"}))
    status, body = request(port, "/api/upload?name=x.png", b"not an image", "application/octet-stream")
    assert status == 400 and body.decode().startswith("Не получилось добавить картинку: это не картинка"), body.decode()


def _png():
    out = io.BytesIO(); Image.new("RGB", (8, 8), "blue").save(out, "PNG"); return out.getvalue()
