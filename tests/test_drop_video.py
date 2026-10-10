"""A video from outside onto the board (owner 2026-10-10: «я почему-то не могу перетащить видео на наш канвас. Или скопировать из буфера
видео на канвас»). A video file dropped from Finder or pasted (⌘C on the file in Finder, ⌘V on the board) goes into added/<day>/ as it
is, with the json a pasted picture gets, and lies on the board as a video card at the drop point (the last pointer point for a paste) in
its own proportions; the same bytes again give the first file; a drop of pictures and a video adds them all. The server takes the
body a piece at a time into a hidden file next to the new one (review/added.py). Chromium, dark theme, a temporary library, videos made
by ffmpeg."""
import hashlib
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

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not FFMPEG, reason="no ffmpeg to make test videos")


def clip(d, name, w, h):   # 1 s of a test pattern, H.264 (mp4, mov) or VP8 (webm)
    enc = ["-c:v", "libvpx", "-deadline", "realtime"] if name.endswith(".webm") else ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=10", "-t", "1", *enc, str(d / name)], check=True, timeout=60)
    return (d / name).read_bytes()


@pytest.fixture
def board(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "a").mkdir(parents=True); (lib / "a" / "0.png").write_bytes(png())
    (state / "boards").mkdir(parents=True)
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"),
               HYIMG_VIDEO_CACHE=str(tmp_path / "vcache"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        yield port, lib
    finally:
        process.terminate(); process.wait(5); log.close()


# a DataTransfer with the files, as Finder gives it: a drop on #stage at the screen point, or a paste on the page
FILES = "fs => { const dt = new DataTransfer(); fs.forEach(([n, t, b]) => dt.items.add(new File([new Uint8Array(b)], n, { type: t }))); return dt; }"
DROP = f"""([fs, x, y]) => {{ const dt = ({FILES})(fs), s = document.querySelector('#stage');
  for (const t of ['dragover', 'drop']) s.dispatchEvent(new DragEvent(t, {{ dataTransfer: dt, clientX: x, clientY: y, bubbles: true, cancelable: true }})); }}"""
PASTE = f"""fs => document.dispatchEvent(new ClipboardEvent('paste', {{ clipboardData: ({FILES})(fs), bubbles: true, cancelable: true }}))"""
# what the person sees of a card of that file: where its middle is on the screen, its proportions, a video card or not
CARDS = """p => Object.keys(board.items).filter(id => board.items[id].path === p).map(id => { const el = EL.get(id), r = el.getBoundingClientRect();
  return { id, cx: r.left + r.width / 2, cy: r.top + r.height / 2, ar: r.width / r.height, vid: el.classList.contains('vid') }; })"""


def cards(page, path, n):
    page.wait_for_function(f"p => ({CARDS})(p).length === {n} && ({CARDS})(p).every(c => c.vid || !/\\.(mp4|mov|webm)$/.test(p))", arg=path, timeout=20000)
    return page.evaluate(CARDS, path)


def added(lib):   # the files in added/<day>/ by kind: the file and its json
    return sorted(str(p.relative_to(lib)) for p in (lib / "added").rglob("*") if p.is_file()) if (lib / "added").exists() else []


def test_a_video_dropped_or_pasted_from_finder_lands_in_added_and_on_the_board(board, tmp_path):
    port, lib = board
    src = tmp_path / "src"; src.mkdir()
    wide, tall, sq = clip(src, "clip.mp4", 64, 36), clip(src, "Tall Shot.mov", 36, 64), clip(src, "paste.webm", 48, 48)
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:   # Playwright installed without its browser
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{port}/canvas.html?board=main"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.cam.main', JSON.stringify({x: 0, y: 0, z: 1})); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && typeof board !== 'undefined' && byPath.size >= 1")
        assert page.evaluate("() => document.documentElement.dataset.theme") == "dark"

        # 1. one video dropped at a point: the file as it is in added/<day>/ with its json, a video card centred there, 64 × 36
        page.evaluate(DROP, [[["clip.mp4", "video/mp4", list(wide)]], 500, 400])
        page.wait_for_function("() => Object.values(board.items).some(it => /clip\\.mp4$/.test(it.path || ''))", timeout=20000)
        rel = page.evaluate("() => Object.values(board.items).find(it => /clip\\.mp4$/.test(it.path)).path")
        day = time.strftime("%y%m%d")
        assert rel.startswith(f"added/{day}/") and rel.endswith("-clip.mp4"), rel
        assert (lib / rel).read_bytes() == wide
        meta = json.loads((lib / (rel + ".json")).read_text())
        assert meta["sha1"] == hashlib.sha1(wide).hexdigest() and meta["path"] == rel and meta["size"] == [64, 36], meta
        assert meta["how"] == "file" and meta["original_name"] == "clip.mp4" and meta["source"] == "owner" and "from the file clip.mp4" in meta["prompt"], meta
        assert set(meta) >= {"added", "model", "url"}, meta
        [c] = cards(page, rel, 1)
        assert abs(c["cx"] - 500) < 3 and abs(c["cy"] - 400) < 3 and abs(c["ar"] - 64 / 36) < 0.02, c
        assert not [f for f in added(lib) if ".upload" in f or f.endswith(".part")], added(lib)   # no piece left behind

        # 2. the same bytes again: no second file, a second card of the first one
        files = added(lib)
        page.evaluate(DROP, [[["again.mp4", "video/mp4", list(wide)]], 900, 400])
        cards(page, rel, 2)
        assert added(lib) == files

        # 3. a picture and a video in one drop: both are added and placed
        page.evaluate(DROP, [[["pic.png", "image/png", list(png(30, 60))], ["Tall Shot.mov", "video/quicktime", list(tall)]], 700, 700])
        page.wait_for_function("() => Object.values(board.items).filter(it => /-(pic\\.png|tall-shot\\.mov)$/.test(it.path || '')).length === 2", timeout=20000)
        mov = page.evaluate("() => Object.values(board.items).find(it => /tall-shot\\.mov$/.test(it.path)).path")
        [m] = cards(page, mov, 1)
        assert abs(m["ar"] - 36 / 64) < 0.02, m
        assert json.loads((lib / (mov + ".json")).read_text())["size"] == [36, 64]

        # 4. ⌘V of a video file copied in Finder: at the last pointer point
        page.evaluate("() => { lastPt = { x: 300, y: -200 }; }")
        page.evaluate(PASTE, [["paste.webm", "video/webm", list(sq)]])
        page.wait_for_function("() => Object.values(board.items).some(it => /-paste\\.webm$/.test(it.path || ''))", timeout=20000)
        web = page.evaluate("() => Object.values(board.items).find(it => /-paste\\.webm$/.test(it.path)).path")
        [w] = cards(page, web, 1)
        it = page.evaluate("p => Object.values(board.items).find(it => it.path === p)", web)
        assert abs(it["x"] + it["w"] / 2 - 300) < 2 and abs(it["y"] + it["w"] / it["ar"] / 2 + 200) < 2 and abs(w["ar"] - 1) < 0.02, (it, w)
        assert (lib / web).read_bytes() == sq
        assert not errors, errors
        browser.close()


def test_the_server_takes_a_video_in_pieces_and_keeps_its_caps(board):
    """the body is read in pieces into a hidden file and renamed (a video of gigabytes is never held in memory); a body cut short leaves
    nothing behind; a video over the cap and a picture over 80 MB are refused before a byte is read"""
    port, lib = board

    def post(path, body, length=None):
        size = str(len(body) if length is None else length)
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, method="POST", headers={"Content-Length": size})
        try:
            with urllib.request.urlopen(req, timeout=20) as r: return r.status, r.read().decode()
        except urllib.error.HTTPError as e: return e.code, e.read().decode()
    pdf = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
           b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
    code, body = post("/api/upload?name=Brief.pdf", pdf)
    assert code == 200, body
    res = json.loads(body)
    assert res["path"].endswith("-brief.pdf") and res["kind"] == "pdf" and (lib / res["path"]).read_bytes() == pdf, res
    assert json.loads((lib / (res["path"] + ".json")).read_text())["sha1"] == hashlib.sha1(pdf).hexdigest()
    with socket.create_connection(("127.0.0.1", port), timeout=20) as s:   # 1000 bytes said, 10 sent, then the sender is gone
        s.sendall(f"POST /api/upload?name=cut.mp4 HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Length: 1000\r\n\r\n".encode() + b"0123456789")
        s.shutdown(socket.SHUT_WR)
        assert b" 400 " in s.recv(4096).split(b"\r\n")[0]
    assert not [f for f in added(lib) if "cut" in f or ".upload" in f or f.endswith(".part")], added(lib)
    code, body = post("/api/upload?name=huge.mp4", b"", 5 << 30)   # 5 GB said, nothing sent: refused at once
    assert code == 413 and "4 GB" in body, (code, body)
    code, body = post("/api/upload?name=huge.png", b"", 81 << 20)
    assert code == 413 and "80 MB" in body, (code, body)
