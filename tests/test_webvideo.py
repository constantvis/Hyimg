"""The WebM copy for an engine without H.264 (owner 2026-10-05: the app's Chromium, a CEF build without proprietary codecs, gave
MEDIA_ERR_SRC_NOT_SUPPORTED on every phone mp4) and «Показать в Finder» (POST /api/reveal). Server only: a temp library, a temp
video cache, a recorder instead of `open`, so no test touches Finder or ~/Library/Caches."""
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(not (FFMPEG and FFPROBE), reason="no ffmpeg to make test videos")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    """an H.264 mp4 without sound (as the owner's clip), one with AAC sound, a mov"""
    d = tmp_path_factory.mktemp("clips")
    pic = ["-f", "lavfi", "-i", "testsrc2=size=540x960:rate=30"]
    tone = ["-f", "lavfi", "-i", "sine=frequency=440"]
    h264 = ["-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-t", "3"]
    subprocess.run([FFMPEG, "-v", "error", "-y", *pic, *h264, str(d / "mute.mp4")], check=True, timeout=120)
    subprocess.run([FFMPEG, "-v", "error", "-y", *pic, *tone, *h264, "-c:a", "aac", str(d / "sound.mp4")], check=True, timeout=120)
    subprocess.run([FFMPEG, "-v", "error", "-y", *pic, *h264, str(d / "c.mov")], check=True, timeout=120)
    return d


def start(tmp_path, clips, **extra):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    (lib / "v").mkdir(parents=True); plugins.mkdir(); (lib / "pic").mkdir()
    for f in clips.iterdir():
        shutil.copy(f, lib / "v" / f.name)
    (lib / "pic" / "a.txt").write_text("not a video")
    (state / "boards").mkdir(parents=True)
    items = {"m": {"path": "v/mute.mp4", "x": 0, "y": 0, "w": 300, "ar": 540 / 960, "crop": None},
             "c": {"path": "v/c.mov", "x": 340, "y": 0, "w": 300, "ar": 540 / 960, "crop": None}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "groups": {}, "removed": {}, "items": items}))
    (tmp_path / "outside.mp4").write_bytes((lib / "v" / "mute.mp4").read_bytes())
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    # the interface in Russian: these tests check its Russian words (owner 2026-10-06: English by default, Russian by the setting)
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "ru"}))
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"),
               HYIMG_PLUGINS=str(plugins), HYIMG_VIDEO_CACHE=str(tmp_path / "vcache"), PYTHONDONTWRITEBYTECODE="1", **extra)
    log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    return process, port, log


@pytest.fixture
def counting(tmp_path):
    """an ffmpeg that writes a line for every run, then is the real one"""
    runs = tmp_path / "runs.txt"
    w = tmp_path / "bin" / "ffmpeg"; w.parent.mkdir()
    w.write_text(f'#!/bin/sh\necho run >> "{runs}"\nexec "{FFMPEG}" "$@"\n'); w.chmod(0o755)
    return w, runs


@pytest.fixture
def server(tmp_path, clips, counting):
    rec = tmp_path / "reveal.txt"
    r = tmp_path / "bin" / "reveal"
    r.write_text(f'#!/bin/sh\nfor a in "$@"; do printf "%s\\t" "$a" >> "{rec}"; done\necho >> "{rec}"\n'); r.chmod(0o755)
    process, port, log = start(tmp_path, clips, HYIMG_FFMPEG=str(counting[0]), HYIMG_REVEAL_CMD=str(r))
    try:
        yield {"port": port, "runs": counting[1], "reveal": rec, "cache": tmp_path / "vcache", "lib": tmp_path / "lib"}
    finally:
        process.terminate(); process.wait(5); log.close()


def get(port, path, headers=None, timeout=60):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers={"Host": f"127.0.0.1:{port}", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, dict(r.headers), r.read()


def post(port, path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Host": f"127.0.0.1:{port}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, None


def probe(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=format_name:stream=codec_type,codec_name,width,height", "-of", "json", str(path)],
                         capture_output=True, text=True, timeout=30).stdout
    return json.loads(out)


def test_transcode_gives_a_vp9_webm_in_ranges_and_cached(server, tmp_path):
    port = server["port"]
    t0 = time.monotonic()
    code, h, body = get(port, "/video?p=v/mute.mp4&fmt=webm", {"Range": "bytes=0-"})
    first = time.monotonic() - t0
    assert code == 206 and h["Content-Type"] == "video/webm" and h["Accept-Ranges"] == "bytes"
    size = int(h["Content-Range"].split("/")[1]); assert len(body) == size > 1000
    out = tmp_path / "got.webm"; out.write_bytes(body)
    d = probe(out)
    assert "webm" in d["format"]["format_name"] or "matroska" in d["format"]["format_name"]
    assert [(s["codec_type"], s["codec_name"]) for s in d["streams"]] == [("video", "vp9")]   # no sound in the file: none in the copy
    assert (d["streams"][0]["width"], d["streams"][0]["height"]) == (540, 960)
    # a middle piece
    code, h, part = get(port, "/video?p=v/mute.mp4&fmt=webm", {"Range": "bytes=100-199"})
    assert code == 206 and h["Content-Range"] == f"bytes 100-199/{size}" and part == body[100:200]
    # the second time from the cache: no new ffmpeg, the same bytes
    t0 = time.monotonic(); code, _h, again = get(port, "/video?p=v/mute.mp4&fmt=webm"); hit = time.monotonic() - t0
    assert code == 200 and again == body
    assert server["runs"].read_text().count("run") == 1
    files = list(server["cache"].glob("*.webm")); assert len(files) == 1 and not list(server["cache"].glob("*.part"))
    assert hit < first
    print(f"transcode of a 3 s 540x960 clip: {first:.2f} s, cache hit {hit * 1000:.0f} ms")


def test_sound_becomes_opus(server, tmp_path):
    code, _h, body = get(server["port"], "/video?p=v/sound.mp4&fmt=webm")
    out = tmp_path / "s.webm"; out.write_bytes(body)
    assert code == 200 and sorted(s["codec_name"] for s in probe(out)["streams"]) == ["opus", "vp9"]


def test_concurrent_requests_run_ffmpeg_once(server):
    port, res = server["port"], []
    def one():
        try: res.append(get(port, "/video?p=v/c.mov&fmt=webm", {"Range": "bytes=0-"})[0])
        except Exception as ex: res.append(repr(ex))
    ts = [threading.Thread(target=one) for _ in range(5)]
    for t in ts: t.start()
    for t in ts: t.join(90)
    assert res == [206] * 5
    assert server["runs"].read_text().count("run") == 1


def test_prep_starts_in_the_background(server):
    port = server["port"]
    code, _h, body = get(port, "/video?p=v/sound.mp4&fmt=webm&prep=1")
    assert code == 200 and json.loads(body)["state"] in ("working", "ready")
    for _ in range(300):
        if json.loads(get(port, "/video?p=v/sound.mp4&fmt=webm&prep=1")[2])["state"] == "ready": break
        time.sleep(0.1)
    else:
        pytest.fail("the copy was never ready")
    get(port, "/video?p=v/sound.mp4&fmt=webm")
    assert server["runs"].read_text().count("run") == 1


def test_video_route_stays_inside_the_library(server):
    port = server["port"]
    for bad in ("../outside.mp4", "pic/a.txt", "v/none.mp4"):
        with pytest.raises(urllib.error.HTTPError) as e:
            get(port, "/video?p=" + urllib.request.quote(bad) + "&fmt=webm")
        assert e.value.code == 404
    assert not server["runs"].exists()


def test_no_ffmpeg_says_so(tmp_path, clips):
    process, port, log = start(tmp_path, clips, HYIMG_FFMPEG=str(tmp_path / "no-ffmpeg"))
    try:
        assert json.loads(get(port, "/video?p=v/mute.mp4&fmt=webm&prep=1")[2])["state"] == "noffmpeg"
        with pytest.raises(urllib.error.HTTPError) as e:
            get(port, "/video?p=v/mute.mp4&fmt=webm")
        assert e.value.code == 501 and json.loads(e.value.read())["error"] == "noffmpeg"
    finally:
        process.terminate(); process.wait(5); log.close()


def test_items_carry_codecs(server):
    items = json.loads(get(server["port"], "/api/items?all=1")[2])
    by = {i["path"]: i for i in items}
    assert by["v/mute.mp4"]["vcodec"] == "h264" and by["v/mute.mp4"]["acodec"] is None
    assert by["v/sound.mp4"]["acodec"] == "aac" and by["v/sound.mp4"]["vsize"] == [540, 960]


# ---------- «Показать в Finder» ----------
def test_reveal_refuses_paths_outside_the_library(server):
    port = server["port"]
    for bad in (["../outside.mp4"], ["v/../../outside.mp4"], [str(server["lib"] / "v" / "mute.mp4")], ["/etc/hosts"], ["~/x"], ["v/mute.mp4", "../outside.mp4"]):
        code, _ = post(port, "/api/reveal", {"paths": bad})
        assert code == 403, bad
    assert post(port, "/api/reveal", {"paths": "v/mute.mp4"})[0] == 400
    assert post(port, "/api/reveal", {"paths": []})[0] == 400
    assert post(port, "/api/reveal", {"paths": ["v/none.mp4"]})[0] == 404
    assert not server["reveal"].exists()   # nothing was shown


def test_reveal_shows_library_files_one_call_per_folder(server):
    port, lib = server["port"], os.path.realpath(server["lib"])
    code, res = post(port, "/api/reveal", {"paths": ["v/mute.mp4", "v/c.mov", "pic/a.txt", "v/mute.mp4"]})
    assert code == 200 and res == {"revealed": 3, "folders": 2, "skipped": 0}
    lines = [ln.rstrip("\t").split("\t") for ln in server["reveal"].read_text().splitlines()]
    assert lines == [["-R", f"{lib}/v/mute.mp4", f"{lib}/v/c.mov"], ["-R", f"{lib}/pic/a.txt"]]


def test_reveal_needs_the_app_origin(server):
    port = server["port"]
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/reveal", data=b'{"paths":["v/mute.mp4"]}', method="POST",
                                 headers={"Content-Type": "application/json", "Origin": "http://evil.example"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 403 and not server["reveal"].exists()


def reveal_calls(server):
    f = server["reveal"]
    return [ln.rstrip("\t").split("\t") for ln in f.read_text().splitlines()] if f.exists() else []


def browser_page(p):
    try:
        browser = p.chromium.launch()
    except Exception as error:
        pytest.skip(f"no chromium for Playwright: {error}")
    return browser, browser.new_page(viewport={"width": 1300, "height": 850})


def test_reveal_from_the_board_menu_and_the_info_card(server):
    sync = pytest.importorskip("playwright.sync_api")
    port, lib = server["port"], os.path.realpath(server["lib"])
    with sync.sync_playwright() as p:
        browser, page = browser_page(p)
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{port}/canvas.html?board=main"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.cam.main', JSON.stringify({x: -20, y: -60, z: 1})); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && EL.size === 2 && byPath.size >= 2")
        at = lambda id: page.evaluate("id => { const r = EL.get(id).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 3]; }", id)
        # both selected, right click: one item for both files
        page.evaluate("() => { sel = new Set(['m', 'c']); render(); }")
        page.mouse.click(*at("m"), button="right")
        item = page.locator("#ctx [data-act=reveal]")
        assert item.is_visible() and item.inner_text().strip() == "Показать в Finder"
        item.click()
        page.wait_for_function("() => !document.querySelector('#ctx').classList.contains('open')")
        for _ in range(50):
            if reveal_calls(server): break
            time.sleep(0.1)
        assert reveal_calls(server) == [["-R", f"{lib}/v/mute.mp4", f"{lib}/v/c.mov"]]
        # one selected: the info card has the button beside the path
        page.mouse.click(700, 760)   # the empty board: nothing selected
        page.mouse.click(*at("c"))
        btn = page.locator("#iNotes .prow .rv")
        btn.wait_for()
        assert btn.get_attribute("title") == "Показать в Finder"
        btn.click()
        for _ in range(50):
            if len(reveal_calls(server)) == 2: break
            time.sleep(0.1)
        assert reveal_calls(server)[1] == ["-R", f"{lib}/v/c.mov"]
        assert not errors, errors
        browser.close()


def test_reveal_from_the_library_menu(server):
    sync = pytest.importorskip("playwright.sync_api")
    port, lib = server["port"], os.path.realpath(server["lib"])
    with sync.sync_playwright() as p:
        browser, page = browser_page(p)
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/")
        page.evaluate("() => localStorage.setItem('view', 'lib')")   # the library open, as wide as the window
        page.reload()
        page.wait_for_function("() => document.querySelectorAll('#list .card').length >= 2")
        card = page.locator("#list .card").first
        card.scroll_into_view_if_needed()
        card.click(button="right")
        item = page.locator("#lctx [data-a=reveal]")
        assert item.is_visible() and item.inner_text().strip().startswith("Показать в Finder")
        path = page.evaluate("() => view[+document.querySelector('#list .card').dataset.i].path")
        item.click()
        for _ in range(50):
            if reveal_calls(server): break
            time.sleep(0.1)
        assert reveal_calls(server) == [["-R", f"{lib}/{path}"]]
        assert not errors, errors
        browser.close()


def test_cache_is_pruned_oldest_first(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "review"))
    import webvideo
    monkeypatch.setattr(webvideo, "CACHE", str(tmp_path)); monkeypatch.setattr(webvideo, "LIMIT", 2500)
    for i, name in enumerate(("a", "b", "c")):
        f = tmp_path / f"{name}.webm"; f.write_bytes(b"x" * 1000); os.utime(f, (1000 + i, 1000 + i))
    webvideo.prune(keep=str(tmp_path / "a.webm"))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.webm", "c.webm"]   # b was the oldest one not just made
