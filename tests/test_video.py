"""Video on the board (owner 2026-10-05): a video card plays muted under the pointer and goes back to its picture when the pointer
leaves, the round ▶ plays it with sound, the time line along its bottom edge scrubs, Space plays the one selected video while Space
and a drag still pan, at most 3 play at once, far out there are no <video> elements, ⤢ in the pill opens it large (a double click crops and trims it), and the server
gives the file in byte ranges (WebKit needs them for <video>). Runs in Chromium and WebKit where Playwright has them, with test
videos made by ffmpeg."""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not FFMPEG, reason="no ffmpeg to make test videos")
ENGINES = ["chromium", "webkit"]
W, AR = 260, 640 / 360


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    """6 s test pattern with a tone: mp4 (H.264 + AAC), mov, webm (VP8 + Opus), and a second mp4"""
    d = tmp_path_factory.mktemp("clips")
    src = ["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-f", "lavfi", "-i", "sine=frequency=440", "-t", "6"]
    jobs = {"a.mp4": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"], "b.mov": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"],
            "c.webm": ["-c:v", "libvpx", "-deadline", "realtime", "-cpu-used", "8", "-b:v", "800k", "-c:a", "libopus"],
            "d.mp4": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"]}
    for name, enc in jobs.items():
        subprocess.run([FFMPEG, "-v", "error", "-y", *src, *enc, str(d / name)], check=True, timeout=120)
    return d


BOARD = {"schema": 1, "revision": 1, "groups": {}, "removed": {}, "items": {
    "v0": {"path": "v/a.mp4", "x": 0, "y": 0, "w": W, "ar": AR, "crop": None},
    "v1": {"path": "v/b.mov", "x": 280, "y": 0, "w": W, "ar": AR, "crop": None},
    "v2": {"path": "v/c.webm", "x": 560, "y": 0, "w": W, "ar": AR, "crop": None},
    "v3": {"path": "v/d.mp4", "x": 840, "y": 0, "w": W, "ar": AR, "crop": None},
    "v4": {"path": "v/a.mp4", "x": 0, "y": 200, "w": W, "ar": AR, "crop": [0.25, 0, 0.75, 1]},   # a cropped copy of the first one
}}


def run_server(tmp_path, clips, **extra):
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    (lib / "v").mkdir(parents=True); plugins.mkdir()
    for f in clips.iterdir():
        shutil.copy(f, lib / "v" / f.name)
    (state / "boards").mkdir(parents=True)
    (state / "boards/main.json").write_text(json.dumps(BOARD))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    # the interface in Russian: these tests check its Russian words (owner 2026-10-06: English by default, Russian by the setting)
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "ru"}))
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"),
               HYIMG_PLUGINS=str(plugins), HYIMG_VIDEO_CACHE=str(tmp_path / "vcache"), PYTHONDONTWRITEBYTECODE="1", **extra)
    log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        yield port
    finally:
        process.terminate()
        process.wait(5)
        log.close()


@pytest.fixture
def server(tmp_path, clips):
    yield from run_server(tmp_path, clips)


@pytest.fixture
def server_noffmpeg(tmp_path, clips):
    yield from run_server(tmp_path, clips, HYIMG_FFMPEG=str(tmp_path / "no-ffmpeg"))


def open_board(p, engine, port, init=None):
    try:
        browser = getattr(p, engine).launch()
    except Exception as error:   # Playwright installed without this browser
        pytest.skip(f"no {engine} for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1200, "height": 800})
    if init: page.add_init_script(init)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html?board=main"
    page.goto(url)
    page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.cam.main', JSON.stringify({x: -20, y: -60, z: 1})); }")
    page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 5 && byPath.size >= 4 && document.querySelectorAll('.it.vid.vok').length === 5")
    # the pills have grown in (a mark comes by scaling up from 0, owner 2026-10-06): a click aims at their full size
    page.wait_for_function("() => [...document.querySelectorAll('.it.vid .kd')].every(k => k.querySelector('.kt') && getComputedStyle(k).scale === '1' && getComputedStyle(k).opacity === '1')")
    return browser, page, errors


def open_large(page, id):
    """the large player opens from ⤢ in the grey pill, which grows in under the pointer (owner 2026-10-06; a double click crops now)"""
    page.mouse.move(*center(page, id))
    page.wait_for_function("id => { const f = EL.get(id).querySelector('.kd .kf'); return f && f.getBoundingClientRect().width > 8; }", arg=id)
    page.mouse.click(*page.evaluate("id => { const r = EL.get(id).querySelector('.kd .kf').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", id))


def center(page, id, fx=0.5, fy=0.5):
    return page.evaluate("([id, fx, fy]) => { const r = EL.get(id).getBoundingClientRect(); return [r.left + r.width * fx, r.top + r.height * fy]; }", [id, fx, fy])


VST = """id => { const s = VS.get(id), v = s && s.v, el = EL.get(id);
  return { mode: s ? s.mode : null, el: !!v, paused: v ? v.paused : null, muted: v ? v.muted : null, t: v ? v.currentTime : (s ? s.t : 0),
           show: el.classList.contains('vshow'), sound: el.classList.contains('vsound') }; }"""


def vst(page, id):
    return page.evaluate(VST, id)


def playing(page, id, sound=None):   # its time moves forward
    t0 = vst(page, id)["t"]
    page.wait_for_function(f"([id, t0, sound]) => {{ const s = VS.get(id), v = s && s.v; return v && !v.paused && v.currentTime > t0 + 0.2 && (sound === null || v.muted === !sound); }}",
                           arg=[id, t0, sound], timeout=15000)


def test_server_gives_videos_in_byte_ranges(server):
    url = f"http://127.0.0.1:{server}/file?p=v/a.mp4"
    whole = urllib.request.urlopen(url).read()
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=0-1"}))   # Safari's first probe
    assert r.status == 206 and r.headers["Content-Range"] == f"bytes 0-1/{len(whole)}" and r.headers["Accept-Ranges"] == "bytes" and r.read() == whole[:2]
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=100-"}))
    assert r.status == 206 and r.read() == whole[100:]
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=-50"}))
    assert r.status == 206 and r.read() == whole[-50:]
    with pytest.raises(urllib.error.HTTPError) as no:
        urllib.request.urlopen(urllib.request.Request(url, headers={"Range": f"bytes={len(whole) + 10}-"}))
    assert no.value.code == 416
    item = next(i for i in json.load(urllib.request.urlopen(f"http://127.0.0.1:{server}/api/items?all=1")) if i["path"] == "v/a.mp4")
    assert item["kind"] == "video" and item["duration"] == 6.0 and item["vsize"] == [640, 360], item


@pytest.mark.parametrize("engine", ENGINES)
def test_hover_plays_muted_and_leaving_shows_the_picture(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        assert page.evaluate("() => document.querySelectorAll('#items video').length") == 0   # nothing is loaded before it plays
        for id in ("v0", "v1", "v2"):   # mp4, mov, webm
            page.mouse.move(*center(page, id))
            playing(page, id, sound=False)
            page.wait_for_function("id => EL.get(id).classList.contains('vshow')", arg=id)
        page.mouse.move(*center(page, "v0"))
        playing(page, "v0", sound=False)
        page.mouse.move(600, 700)   # empty board
        s = vst(page, "v0")
        assert s["paused"] and not s["show"] and s["mode"] is None and s["t"] > 0.2, s   # back to the picture, the place is kept
        page.mouse.move(*center(page, "v0"))
        playing(page, "v0", sound=False)
        assert vst(page, "v0")["t"] >= s["t"], "the next hover goes on from where it stopped"
        # the cropped copy plays inside its crop: the video is as big as the whole picture and shifted like it
        page.mouse.move(*center(page, "v4"))
        playing(page, "v4", sound=False)
        box = page.evaluate("() => { const e = EL.get('v4'), v = e.querySelector('video'), i = e.querySelector('img'); return [v.style.width, v.style.left, i.style.width, i.style.left, e.classList.contains('dup')]; }")
        assert box[0] == box[2] and box[1] == box[3] and box[1].startswith("-") and box[4], box   # and it keeps its copy mark
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_play_button_with_sound_time_line_scrubs_and_pauses(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        page.mouse.click(*page.evaluate("() => { const r = EL.get('v0').querySelector('.kd').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }"))
        playing(page, "v0", sound=True)
        s = vst(page, "v0")
        assert s["mode"] == "sound" and s["sound"] and not page.evaluate("() => sel.size"), s   # the ▶ does not select the card
        # scrub: press on the time line at three quarters
        x, y = center(page, "v0", 0.75, 0.985)
        page.mouse.move(x, y); page.mouse.down()
        t = vst(page, "v0")["t"]
        assert 4.0 < t < 5.0, t
        page.mouse.move(*center(page, "v0", 0.25, 0.985), steps=4)
        page.wait_for_function("() => VS.get('v0').v.currentTime < 2")
        page.mouse.up()
        playing(page, "v0", sound=True)   # it plays on from there
        # ❚❚
        page.mouse.click(*page.evaluate("() => { const r = EL.get('v0').querySelector('.kd').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }"))
        s = vst(page, "v0")
        assert s["paused"] and s["mode"] == "held" and s["show"], s   # under the pointer it stays on its frame with the time line
        page.mouse.move(600, 700)
        assert not vst(page, "v0")["show"]
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_space_plays_the_selected_video_and_space_drag_still_pans(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        page.mouse.click(*center(page, "v3"))
        assert page.evaluate("() => [...sel]") == ["v3"]
        page.mouse.move(600, 700)   # the pointer off the card: Space alone plays it
        page.keyboard.press(" ")
        playing(page, "v3", sound=True)
        page.keyboard.press(" ")
        s = vst(page, "v3")
        assert s["paused"] and not s["show"], s
        # Space held and a drag: the board moves, the video does not start
        cam0 = page.evaluate("() => [cam.x, cam.y]")
        page.keyboard.down(" ")
        page.mouse.move(600, 700); page.mouse.down(); page.mouse.move(500, 650, steps=6); page.mouse.up()
        page.keyboard.up(" ")
        cam1 = page.evaluate("() => [cam.x, cam.y]")
        assert cam1[0] - cam0[0] > 50 and cam1[1] - cam0[1] > 30, (cam0, cam1)
        page.wait_for_timeout(300)
        assert vst(page, "v3")["paused"]
        # two selected: Space does nothing to them
        page.evaluate("() => { sel = new Set(['v0', 'v1']); render(); }")
        page.keyboard.press(" ")
        page.wait_for_timeout(200)
        assert not page.evaluate("() => VPLAY.length")
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_three_play_at_most_and_far_out_there_are_no_videos(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        for id in ("v0", "v1", "v2", "v3"):
            page.mouse.click(*page.evaluate("id => { const r = EL.get(id).querySelector('.kd').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", id))
            playing(page, id)
        assert page.evaluate("() => VPLAY") == ["v1", "v2", "v3"]
        assert vst(page, "v0")["paused"]   # the oldest stopped
        # small on screen (114 px: under 120, not yet the far view): no element, no ▶
        page.evaluate("() => { cam.z = 0.44; renderCam(); }")
        page.wait_for_function("() => !LOD.on && !document.querySelector('#items video') && !document.querySelector('.it.vok')")
        # far out (the drawn canvas): still none, and hovering one starts nothing
        page.evaluate("() => { cam.z = 0.05; renderCam(); }")
        page.wait_for_function("() => LOD.on")
        page.mouse.move(*page.evaluate("() => { const r = stage.getBoundingClientRect(); return [r.left + (20 - cam.x) * cam.z, r.top + (20 - cam.y) * cam.z]; }"))
        page.wait_for_timeout(300)
        assert page.evaluate("() => document.querySelectorAll('#items video').length") == 0   # the large player's own stays empty
        # back in close: the card under the pointer plays again
        page.evaluate("() => { cam.x = -20; cam.y = -60; cam.z = 1; renderCam(); render(); }")
        page.mouse.move(*center(page, "v2"))
        playing(page, "v2", sound=False)
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_fullscreen_button_opens_it_large_and_esc_closes(server, engine):
    """the board opened alone (no library page around it, so no library viewer): ⤢ falls back to the board's own full-screen player"""
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        open_large(page, "v1")
        page.wait_for_function("() => VBIG === 'v1' && document.querySelector('#vbig').classList.contains('open')")
        page.wait_for_function("() => { const v = document.querySelector('#vbV'); return v.videoWidth === 640 && v.controls; }", timeout=15000)
        assert page.evaluate("() => !cropState")   # a video opens, it is not cropped
        # true full screen where the engine grants it, else over the board (dimmed to 70 %)
        assert page.evaluate("() => getComputedStyle(document.querySelector('#vbig')).backgroundColor") == "rgba(0, 0, 0, 0.7)"
        assert "0:06" in page.inner_text("#vbMeta") and "640 × 360" in page.inner_text("#vbMeta")
        page.keyboard.press("Escape")
        page.wait_for_function("() => !VBIG && !document.querySelector('#vbig').classList.contains('open')")
        assert page.evaluate("() => [...sel]") == ["v1"], "Esc closed the player, not the selection"
        # the card on the right says its length and size
        info = page.inner_text("#info")
        assert "видео 0:06" in info and "640 × 360 px" in info, info
        assert not errors, errors
        browser.close()


def open_library(p, engine, port):
    """the library page with the board in its iframe (the embedded canvas): returns (browser, page, canvas frame, errors)"""
    try:
        browser = getattr(p, engine).launch()
    except Exception as error:
        pytest.skip(f"no {engine} for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1300, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{port}/?view=canvas")
    page.evaluate("() => { localStorage.clear(); localStorage.setItem('view', 'canvas'); }")
    page.goto(f"http://127.0.0.1:{port}/?view=canvas")
    page.wait_for_selector("#cvFrame")
    cv = next(f for f in page.frames if "/canvas" in f.url)
    cv.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 5 && byPath.size >= 4 && document.querySelectorAll('.it.vid.vok').length === 5", timeout=20000)
    return browser, page, cv, errors


def open_large_embedded(page, cv, id):
    """⤢ in the pill of a card inside the library's iframe: the mouse works in the page's coordinates, the card's are the frame's"""
    off = page.evaluate("() => { const r = document.getElementById('cvFrame').getBoundingClientRect(); return [r.left, r.top]; }")
    c = cv.evaluate("id => { const r = EL.get(id).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", id)
    page.mouse.move(off[0] + c[0], off[1] + c[1])
    cv.wait_for_function("id => { const f = EL.get(id).querySelector('.kd .kf'); return f && f.getBoundingClientRect().width > 8; }", arg=id)
    k = cv.evaluate("id => { const r = EL.get(id).querySelector('.kd .kf').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", id)
    page.mouse.click(off[0] + k[0], off[1] + k[1])


@pytest.mark.parametrize("engine", ENGINES)
def test_fullscreen_button_opens_the_librarys_viewer_when_embedded(server, engine):
    """Owner 2026-10-06 (two screenshots): «the full-screen preview we have is THIS, the library's big viewer with the rating panel, not
    the board's own window». ⤢ on a card inside the library opens that viewer on the file, playing; the board's #vbig stays shut. A trimmed
    card starts the viewer at its trim and loops the piece."""
    with playwright.sync_playwright() as p:
        browser, page, cv, errors = open_library(p, engine, server)
        open_large_embedded(page, cv, "v1")
        page.wait_for_function("() => document.getElementById('viewer').classList.contains('open')", timeout=15000)
        page.wait_for_function("() => { const v = document.getElementById('vid'); return !v.hidden && /b\\.mov/.test(decodeURIComponent(v.getAttribute('src') || '')); }")
        assert page.evaluate("() => document.getElementById('vName').textContent") == "b"
        assert page.locator("#viewer #verdicts").count() == 1, "the viewer with the rating panel"
        assert cv.evaluate("() => !VBIG && !document.querySelector('#vbig').classList.contains('open') && !document.fullscreenElement && !document.webkitFullscreenElement")
        page.wait_for_function("() => { const v = document.getElementById('vid'); return !v.paused && v.currentTime > 0.3 && v.loop; }", timeout=15000)
        assert cv.evaluate("() => [...sel]") == ["v1"]
        page.keyboard.press("Escape")
        page.wait_for_function("() => !document.getElementById('viewer').classList.contains('open')")
        assert page.evaluate("() => document.getElementById('vid').paused")
        # a trimmed card: the viewer starts at the trim's start and goes back to it at the piece's end
        cv.evaluate("() => { board.items.v0.trim = [2, 3.2]; render(); }")
        open_large_embedded(page, cv, "v0")
        page.wait_for_function("() => document.getElementById('viewer').classList.contains('open') && /a\\.mp4/.test(decodeURIComponent(document.getElementById('vid').getAttribute('src') || ''))", timeout=15000)
        page.wait_for_function("() => { const v = document.getElementById('vid'); return !v.paused && v.currentTime >= 1.8; }", timeout=15000)
        seen = []
        for _ in range(24):
            seen.append(page.evaluate("() => document.getElementById('vid').currentTime")); page.wait_for_timeout(250)
        assert min(seen) >= 1.8 and max(seen) <= 3.6 and max(seen) - min(seen) > 0.5, seen   # 6 s of watching a 1.2 s piece: it looped
        assert not errors, errors
        browser.close()


# An engine without H.264 and AAC (owner 2026-10-05: the app's Chromium, a CEF build without proprietary codecs, measured: canPlayType
# of avc1 is "" and an H.264 mp4 fails with MEDIA_ERR_SRC_NOT_SUPPORTED). Playwright's Chromium has them, so the page is told it has
# not: canPlayType answers "" for the mp4 codecs, and the board must ask the server for the WebM copy.
NO_H264 = """(() => { const o = HTMLMediaElement.prototype.canPlayType;
  HTMLMediaElement.prototype.canPlayType = function (t) { return /avc1|mp4a|hvc1|quicktime/.test(t) ? "" : o.call(this, t); }; })();"""


def src_of(page, id):
    return page.evaluate("id => { const s = VS.get(id); return s && s.v ? s.v.currentSrc || s.v.src : ''; }", id)


def test_engine_without_h264_plays_the_webm_copy(server):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, "chromium", server, NO_H264)
        assert page.evaluate("() => hyVideo.support.h264") == "no"
        # the cards on screen started their copies in the background: d.mp4 gets ready without being touched
        page.wait_for_function("() => fetch('/video?p=v%2Fd.mp4&fmt=webm&prep=1').then(r => r.json()).then(d => d.state === 'ready')", timeout=30000)
        page.mouse.move(*center(page, "v0"))   # hover: muted, from the copy
        playing(page, "v0", sound=False)
        assert "/video?p=v%2Fa.mp4&fmt=webm" in src_of(page, "v0") and not page.evaluate("() => EL.get('v0').classList.contains('vwait')")
        page.mouse.move(600, 700)
        page.mouse.click(*page.evaluate("() => { const r = EL.get('v1').querySelector('.kd').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }"))
        playing(page, "v1", sound=True)   # ▶ on the mov: with sound (Opus in the copy)
        assert "/video?p=v%2Fb.mov&fmt=webm" in src_of(page, "v1")
        page.mouse.move(*center(page, "v2"))   # a webm plays from the file itself
        playing(page, "v2", sound=False)
        assert "/file?p=v%2Fc.webm" in src_of(page, "v2")
        page.mouse.move(600, 700)
        open_large(page, "v0")   # the large player too
        page.wait_for_function("() => { const v = document.querySelector('#vbV'); return VBIG === 'v0' && v.videoWidth === 640 && /fmt=webm/.test(v.currentSrc); }", timeout=20000)
        page.keyboard.press("Escape")
        assert not errors, errors
        browser.close()


def test_original_failing_falls_back_to_the_copy(server):
    """codecs not known (a server not restarted) and the original fails in the engine: the same card goes on from the copy"""
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, "chromium", server)
        page.route("**/file?p=v%2Fa.mp4*", lambda route: route.fulfill(status=200, body=b"\\0" * 4096, content_type="video/mp4"))
        page.evaluate("() => byPath.forEach(m => { delete m.vcodec; delete m.acodec; })")
        page.mouse.move(*center(page, "v0"))
        playing(page, "v0", sound=False)
        assert "/video?p=v%2Fa.mp4&fmt=webm" in src_of(page, "v0")
        assert not errors, errors
        browser.close()


def test_no_ffmpeg_says_so_once(server_noffmpeg):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, "chromium", server_noffmpeg, NO_H264)
        page.mouse.move(*center(page, "v0")); page.wait_for_timeout(600)
        page.mouse.move(*center(page, "v1")); page.wait_for_timeout(600)
        text = "Этот движок не проигрывает H.264, нужен ffmpeg"
        page.wait_for_function("t => document.body.innerText.includes(t)", arg=text)
        assert page.evaluate("t => document.body.innerText.split(t).length - 1", text) == 1
        assert not errors, errors
        browser.close()


def test_video_in_english_has_no_russian(tmp_path, clips):
    """English, the default (owner 2026-10-06: «translate the interface entirely»): the video cards, their ▶ and time line, the large
    player, the card on the right and the no-ffmpeg message say nothing in Russian"""
    from test_i18n import CRAWL
    gen = run_server(tmp_path, clips, HYIMG_FFMPEG=str(tmp_path / "no-ffmpeg")); port = next(gen)
    (tmp_path / "settings.json").write_text("{}")   # no cv.lang: English
    try:
        with playwright.sync_playwright() as p:
            browser, page, errors = open_board(p, "chromium", port, NO_H264)
            assert page.evaluate("T.lang") == "en"
            leaks = {}
            def check(where):
                found = page.evaluate(CRAWL)
                if found: leaks[where] = found
            check("cards")
            page.mouse.move(*center(page, "v0")); page.wait_for_timeout(600); check("hover")
            page.wait_for_function("t => document.body.innerText.includes(t)", arg="This engine does not play H.264, ffmpeg is needed")
            check("no ffmpeg")
            page.mouse.click(*center(page, "v2")); page.wait_for_timeout(300); check("a video selected")
            page.mouse.move(600, 700); open_large(page, "v2"); page.wait_for_function("() => document.querySelector('#vbig').classList.contains('open')"); check("large")
            assert "video" in page.inner_text("#info").lower()
            page.keyboard.press("Escape")
            assert not leaks, json.dumps(leaks, ensure_ascii=False, indent=1)
            assert not errors, errors
            browser.close()
    finally:
        gen.close()


# ---- crop & trim of a video (owner 2026-10-05/06): non-destructive, the card keeps trim: [in, out] seconds ----

def strip_box(page):
    return page.evaluate("() => { const r = document.querySelector('#crop .vtin').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")


def handle(page, kind):
    return page.evaluate("k => { const r = document.querySelector('#crop .vtin .hd.' + k).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", kind)


def drag_handle(page, kind, frac):
    """the in or out handle taken where it is and let go at frac of the strip's width (the grip keeps its distance, so the cut lands on frac)"""
    x0, y0 = handle(page, kind); left, top, w, h = strip_box(page)
    edge = -6 if kind == "in" else 6   # the grip's centre is 6 px outside the cut it sets: the pointer stands that far from the cut
    page.mouse.move(x0, y0); page.mouse.down()
    page.mouse.move((x0 + left + w * frac + edge) / 2, y0, steps=4); page.mouse.move(left + w * frac + edge, y0, steps=4)
    return lambda: page.mouse.up()


def open_trim(page, id):
    page.mouse.dblclick(*center(page, id))
    try:
        page.wait_for_function("id => cropState && cropState.id === id && cropState.vid && document.querySelectorAll('#crop .vtin .fs img.on').length === 10 && document.querySelector('#crop').classList.contains('vready')", arg=id, timeout=20000)
    except Exception:
        raise AssertionError(page.evaluate("pt => [!!cropState, cropState && cropState.vid, document.querySelectorAll('#crop .vtin .fs img.on').length, document.querySelector('#crop').className, cropState && cropState.v && [cropState.v.readyState, cropState.v.paused, cropState.v.error && cropState.v.error.message], [...sel], VBIG, document.elementsFromPoint(...pt).map(e => e.tagName + '.' + e.className).slice(0, 8)]", center(page, id)))


def test_server_makes_the_trim_strip_frames(server):
    for i in (0, 9):
        r = urllib.request.urlopen(f"http://127.0.0.1:{server}/api/vstrip?p=v%2Fa.mp4&n=10&i={i}", timeout=60)
        body = r.read(); assert r.headers["Content-Type"] == "image/jpeg" and body[:2] == b"\xff\xd8", i
    for q in ("n=10&i=10", "n=10&i=-1", "n=x&i=0"):
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"http://127.0.0.1:{server}/api/vstrip?p=v%2Fa.mp4&{q}", timeout=10)
        assert e.value.code == 400, q
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(f"http://127.0.0.1:{server}/api/vstrip?p=v%2Fmissing.mp4&n=10&i=0", timeout=10)
    assert e.value.code == 404


@pytest.mark.parametrize("engine", ENGINES)
def test_crop_and_trim_a_video(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        open_trim(page, "v0")
        # the crop mode of a picture, with the bar of ratios above the whole clip and the strip over its bottom
        assert page.evaluate("() => !!document.querySelector('#crop .win') && !!document.querySelector('#crop .cratio') && document.querySelectorAll('#crop .vtin .hd').length === 2")
        assert page.evaluate("() => cropState.trim.map(Math.round)") == [0, 6] and "6,0" in page.inner_text("#crop .vtin .tl")
        # the in handle to 1/3: the card shows the frame it will start on
        up = drag_handle(page, "in", 1 / 3)
        page.wait_for_function("() => Math.abs(cropState.trim[0] - 2) < 0.15")
        page.wait_for_function("() => cropState.v && Math.abs(cropState.v.currentTime - cropState.trim[0]) < 0.2 && cropState.v.paused", timeout=10000)
        assert "0:02" in page.inner_text("#crop .vtin .tl") or "2,0" in page.inner_text("#crop .vtin .tl")
        up()
        up = drag_handle(page, "out", 2 / 3); page.wait_for_function("() => Math.abs(cropState.trim[1] - 4) < 0.15"); up()
        # between drags it plays its piece in a loop
        page.wait_for_function("() => !cropState.v.paused && !cropState.v.seeking && cropState.v.currentTime >= 1.8 && cropState.v.currentTime <= 4.1")
        seen = []
        for _ in range(12):
            seen.append(page.evaluate("() => cropState.v.currentTime")); page.wait_for_timeout(250)
        assert min(seen) >= 1.8 and max(seen) <= 4.2 and max(seen) - min(seen) > 0.3, seen
        # Esc cancels: nothing stored
        page.keyboard.press("Escape")
        assert page.evaluate("() => !cropState && !board.items.v0.trim")
        # again, and Enter applies; the file is untouched
        open_trim(page, "v0")
        up = drag_handle(page, "in", 1 / 3); page.wait_for_function("() => Math.abs(cropState.trim[0] - 2) < 0.15"); up()
        up = drag_handle(page, "out", 2 / 3); page.wait_for_function("() => Math.abs(cropState.trim[1] - 4) < 0.15"); up()
        page.keyboard.press("Enter")
        page.wait_for_function("() => !cropState")
        t = page.evaluate("() => board.items.v0.trim"); assert abs(t[0] - 2) < 0.15 and abs(t[1] - 4) < 0.15, t
        assert page.evaluate("() => byPath.get(board.items.v0.path).duration") == 6.0
        # the card then plays only that piece, looping; its pill counts down from the piece's length
        page.mouse.move(600, 700)
        assert page.inner_text("#items [data-id=v0] .kd .kt") == "0:02"
        page.mouse.move(*center(page, "v0"))
        playing(page, "v0", sound=False)
        seen = []
        for _ in range(24):
            seen.append(vst(page, "v0")["t"]); page.wait_for_timeout(250)
        assert min(seen) >= 1.8 and max(seen) <= 4.2 and max(seen) - min(seen) > 0.5, seen   # 6 s of watching a 2 s piece: it looped
        # the large player (⤢) plays the same piece
        page.mouse.move(600, 700); open_large(page, "v0")
        page.wait_for_function("() => VBIG === 'v0'")
        assert "0:02" in page.inner_text("#vbMeta"), page.inner_text("#vbMeta")
        page.wait_for_function("() => { const v = document.querySelector('#vbV'); return !v.paused && v.currentTime >= 1.8; }", timeout=15000)
        seen = []
        for _ in range(16):
            seen.append(page.evaluate("() => document.querySelector('#vbV').currentTime")); page.wait_for_timeout(250)
        assert min(seen) >= 1.8 and max(seen) <= 4.2, seen
        page.keyboard.press("Escape")
        page.wait_for_function("() => !VBIG && !document.fullscreenElement && !document.webkitFullscreenElement")
        page.wait_for_timeout(800)   # the window comes back from full screen
        # undo takes the trim off, and the whole clip back to the ends removes it for good
        page.evaluate("() => { sel = new Set(['v0']); render(); }")
        open_trim(page, "v0")
        assert page.evaluate("() => cropState.trim.map(v => Math.round(v * 10) / 10)") == [2, 4] or page.evaluate("() => Math.abs(cropState.trim[0] - 2) < 0.15")
        up = drag_handle(page, "in", 0.0); page.wait_for_function("() => cropState.trim[0] < 0.1"); up()
        up = drag_handle(page, "out", 1.0); page.wait_for_function("() => cropState.trim[1] > 5.9"); up()
        page.keyboard.press("Enter"); page.wait_for_function("() => !cropState")
        assert page.evaluate("() => 'trim' in board.items.v0") is False
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_crop_bar_buttons_and_the_key_for_a_video(server, engine):
    """«Crop & Trim» on the bar over one selected video, C and the double click do the same; a copy of it keeps its own trim"""
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        page.mouse.click(*center(page, "v1"))
        b = page.locator(".tidy > button[data-crop]")
        assert b.count() == 1 and b.inner_text().strip().startswith("Кроп и обрезка") and b.locator("> kbd").inner_text() == "C"
        b.click()
        page.wait_for_function("() => cropState && cropState.id === 'v1' && cropState.vid")
        assert page.evaluate("() => document.querySelector('#hint').classList.contains('vid')")
        page.keyboard.press("Escape"); page.wait_for_function("() => !cropState")
        page.keyboard.press("c"); page.wait_for_function("() => cropState && cropState.id === 'v1'")
        page.keyboard.press("Escape")
        # a duplicate carries its trim as its own copy
        page.evaluate("() => { board.items.v1.trim = [1, 3]; sel = new Set(['v1']); render(); duplicate(); }")
        pair = page.evaluate("() => Object.values(board.items).filter(i => i.path === 'v/b.mov').map(i => i.trim)")
        assert pair == [[1, 3], [1, 3]]
        page.evaluate("() => { const k = Object.keys(board.items).filter(i => board.items[i].path === 'v/b.mov'); board.items[k[1]].trim[0] = 2; }")
        assert page.evaluate("() => board.items.v1.trim[0]") == 1
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_pill_folds_into_a_circle_smoothly(server, engine):
    """narrow cards (owner 2026-10-06: «why does it jump, it should narrow to a circle like the menu on top»): the capsule ▶ 0:06
    narrows through in-between widths into a round ▶ and grows back, never in one step"""
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        W0 = "() => EL.get('v0').querySelector('.kd').getBoundingClientRect()"
        page.wait_for_function("() => EL.get('v0').querySelector('.kd .kt').textContent.length > 2")
        wide = page.evaluate(W0)
        assert wide["width"] > wide["height"] * 1.6   # ▶ and the time
        # the card goes under 104 px on screen while the camera stays: the pill alone animates
        page.evaluate("() => { board.items.v0.w = 90; render(); }")
        # the folding column's own width (the whole pill also shrinks by the marks' size law on a smaller card, 2026-10-06)
        kw0 = page.evaluate("() => EL.get('v0').querySelector('.kd .kw').offsetWidth")
        mids = page.evaluate("""() => new Promise(done => { const out = [], t0 = performance.now(), k = EL.get('v0').querySelector('.kd .kw');
          const step = () => { out.push(k.getBoundingClientRect().width / (EL.get('v0').querySelector('.kd').getBoundingClientRect().height / k.closest('.kd').offsetHeight)); performance.now() - t0 < 500 ? requestAnimationFrame(step) : done(out); };
          requestAnimationFrame(step); })""")
        end = page.evaluate(W0)
        assert abs(end["width"] - end["height"]) < 1.5, end   # a circle
        between = [w for w in mids if 0.5 < w < kw0 - 0.5]
        assert len(between) >= 3, (kw0, mids)   # it passed through in-between widths
        # and back
        page.evaluate("() => { board.items.v0.w = 260; render(); }")
        page.wait_for_function("w => Math.abs(EL.get('v0').querySelector('.kd').getBoundingClientRect().width - w) < 1", arg=wide["width"])
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_hover_play_has_slack_at_the_edge(server, engine):
    """(owner 2026-10-06) a few px off the playing card it keeps playing; clearly away, or onto another video, it stops"""
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        r = page.evaluate("() => { const r = EL.get('v0').getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom}; }")
        page.mouse.move((r["l"] + r["r"]) / 2, r["b"] - 4)
        playing(page, "v0", sound=False)
        page.mouse.move((r["l"] + r["r"]) / 2, r["b"] + 5, steps=3)   # just under the bottom edge, aiming for the time line
        page.wait_for_timeout(250)
        assert page.evaluate("() => VHOV") == "v0" and not vst(page, "v0")["paused"]
        page.mouse.move(r["r"] + 11, (r["t"] + r["b"]) / 2, steps=4)   # clearly away: the middle of the 20 px gap to the next card
        page.wait_for_function("() => VHOV === null")
        assert vst(page, "v0")["paused"]
        # from the slack straight onto the next video: that one plays
        page.mouse.move(r["r"] - 4, (r["t"] + r["b"]) / 2)
        playing(page, "v0", sound=False)
        page.mouse.move(*center(page, "v1"), steps=6)
        playing(page, "v1", sound=False)
        assert vst(page, "v0")["paused"]
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_time_line_has_slack_under_the_card(server, engine):
    """(owner 2026-10-06) a press a few px under the playing card's bottom edge scrubs as if it hit the line"""
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        r = page.evaluate("() => { const r = EL.get('v0').getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom}; }")
        page.mouse.move((r["l"] + r["r"]) / 2, r["b"] - 20)
        playing(page, "v0", sound=False)
        x = r["l"] + (r["r"] - r["l"]) * 0.75
        page.mouse.move(x, r["b"] + 5, steps=3)   # in the gap under it
        page.wait_for_function("() => EL.get('v0').querySelector('.vbar').classList.contains('near')")
        page.mouse.down(); page.mouse.up()
        t = vst(page, "v0")["t"]
        assert 4.0 < t < 5.2, t   # 75 % of 6 s
        assert page.evaluate("() => board.items.v0.x") == 0   # the card did not move
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_the_far_view_draws_the_same_pill(server, engine):
    """(owner 2026-10-06: «it still switches with a jump»; then «пропадают кнопки несмотря на то что объект то [большой]»: a mark depends
    only on its card's size on screen): a 120 px card keeps its wide pill near the far view, and the far view's canvas draws that pill in
    the same place and width, so the swap does not show"""
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        page.evaluate("() => localStorage.setItem('cv.lod', '1')")
        page.evaluate("() => { cam.x = -20; cam.y = -60; cam.z = 120 / 260; renderCam(); render(); }")
        page.wait_for_function("() => !LOD.on && !EL.get('v0').classList.contains('vnarrow')")
        page.wait_for_timeout(450)
        kd = page.evaluate("() => { const a = EL.get('v0').querySelector('.kd').getBoundingClientRect(); return {w: a.width, h: a.height, k: +getComputedStyle(EL.get('v0')).getPropertyValue('--vbs')}; }")
        assert kd["w"] > kd["h"] * 1.6 and abs(kd["h"] - 26 * kd["k"]) < 0.6, kd   # the board's plate, 26 px × the card's k (owner's lab, 2026-10-06)
        # a touch further out the far view takes over: its canvas has the same pill, its left end where the element's would be at that k
        page.evaluate("() => { cam.z = 108 / 260; renderCam(); render(); }")
        page.wait_for_function("() => LOD.on")
        page.wait_for_timeout(200)
        px = page.evaluate("""w1 => { const c = document.getElementById('lodd'), d = c.width / stage.getBoundingClientRect().width, g = c.getContext('2d'), it = board.items.v0;
          const k = mkFit(it.w * cam.z, itemH(it) * cam.z, { kind: true, kindW: mkPillW(EL.get('v0')), fav: true }).k, I = MK.inset * k;   // the card's factor there
          const x1 = (it.x + it.w - cam.x) * cam.z, y = (it.y + itemH(it) - cam.y) * cam.z - I - MK.px * k / 2, a = x => g.getImageData(Math.round(x * d), Math.round(y * d), 1, 1).data[3];
          let left = null; for (let x = x1 - I - w1 * k - 8; x < x1; x += .25) if (a(x) > 100) { left = x; break; }
          return { left, want: x1 - I - w1 * k, mid: a(x1 - I - w1 * k / 2), k }; }""", kd["w"] / kd["k"])
        # within 2 px: the scan reads whole canvas pixels at this test's pixel ratio, and a canvas has no tabular digits (the element's time has)
        assert px["left"] is not None and abs(px["left"] - px["want"]) < 2, px
        assert px["mid"] > 100, px
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_library_card_plays_under_the_pointer_and_the_opened_video_loops(server, engine):
    """(owner 2026-10-06) in the media library a video card plays muted under the pointer and goes back to its picture on leave;
    opened, a video loops instead of stopping at its end (the board's large player too)"""
    with playwright.sync_playwright() as p:
        try:
            browser = getattr(p, engine).launch()
        except Exception as error:
            pytest.skip(f"no {engine} for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/?view=lib")
        page.wait_for_function("() => [...document.querySelectorAll('.card[data-i]')].some(c => (view[+c.dataset.i] || {}).path === 'v/c.webm')")
        page.evaluate("() => [...document.querySelectorAll('.card[data-i]')].find(c => view[+c.dataset.i].path === 'v/c.webm').id = 'tcard'")
        card = page.locator("#tcard")
        page.mouse.move(5, 5); b = card.bounding_box()
        page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        page.wait_for_function("""() => { const v = document.querySelector('.card > video.lvid'); return v && !v.paused && v.currentTime > 0.3 && v.muted && v.loop && v.classList.contains('on'); }""", timeout=15000)
        page.mouse.move(5, 5)
        page.wait_for_function("() => !document.querySelector('.card > video.lvid')")
        assert page.evaluate("() => document.querySelector('#vid').loop")
        card.click(); page.wait_for_selector("#vid:not([hidden])")
        assert page.evaluate("() => document.querySelector('#vid').loop")
        assert not errors, errors
        browser.close()
