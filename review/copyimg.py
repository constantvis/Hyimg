"""The picture of a card for ⇧⌘C and right click › Copy as › Image (owner 2026-10-09: «Я хочу любой объект скопировать по нажатию ⌘⇧C.
Именно имею в виду video, photo, HTML — в виде картинки, или PDF в виде картинки»). The page (ui/copyimage.js) puts it on the clipboard;
these are the two pictures it cannot draw itself:

  GET /api/copyimage?p=<video>&t=<s>        the video's frame at t seconds at its own size, drawn by ffmpeg: the app's Chromium has no
                                            H.264 and its WebM copy (webvideo.py) is at most 1920 px; the first frame when t is past the end
  GET /api/copyimage?p=<page.html>&w=&h=&s= the page at its viewport (w × h css px) and scale s (1 or 2, at most 8192 px a side), drawn by
                                            render_html.py, the renderer of the HTML frames' stills (Chromium from Playwright, the page's
                                            scripts run); one browser at a time with the stills (server._STILL)

Both answer a PNG and keep nothing: the picture goes to the clipboard, the library and the cache stay as they were."""
import os
import subprocess
import sys
import tempfile
import urllib.parse

MAX_SIDE = 8192


def http(srv, q, port):
    """(code, body, content type) for the server's send()"""
    try:
        rel = srv.resolve(q["p"][0]); full = srv.safe(rel)
        if rel.lower().endswith((".html", ".htm")):
            png = page(srv, rel, port, q)
        elif srv.kind_of(rel) == "video":
            png = frame(srv, full, q)
        else:
            return 400, b"not a video or an html page", "text/plain"
    except (KeyError, ValueError, PermissionError, FileNotFoundError) as ex:
        return 400, str(ex)[:200].encode(), "text/plain; charset=utf-8"
    except (OSError, subprocess.SubprocessError) as ex:
        return 502, str(ex)[:200].encode(), "text/plain; charset=utf-8"
    return 200, png, "image/png"


def frame(srv, full, q):
    ff = srv._tool("ffmpeg")
    if not ff: raise OSError("no ffmpeg")
    t = max(0.0, float(q.get("t", ["0"])[0]))
    for at in dict.fromkeys((f"{t:.3f}", "0")):   # a time past the end gives nothing: the first frame then
        r = subprocess.run([ff, "-v", "error", "-ss", at, "-i", full, "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"], capture_output=True, timeout=60)
        if r.stdout: return r.stdout
    raise OSError("ffmpeg gave no frame")


def page(srv, rel, port, q):
    w, h = max(200, min(4000, int(q.get("w", ["1440"])[0]))), max(200, min(8000, int(q.get("h", ["900"])[0])))
    s = max(1.0, min(2.0, float(q.get("s", ["2"])[0]), MAX_SIDE / max(w, h)))
    fd, out = tempfile.mkstemp(suffix=".png"); os.close(fd)
    try:
        with srv._STILL:
            subprocess.run([sys.executable, os.path.join(srv.CODE_DIR, "render_html.py"), f"http://127.0.0.1:{port}/lib/" + urllib.parse.quote(rel),
                            str(w), str(h), out, f"{s:g}"], capture_output=True, timeout=90, check=True)
        with open(out, "rb") as fh: png = fh.read()
        if not png: raise OSError("no picture of the page")
        return png
    finally:
        os.remove(out)
