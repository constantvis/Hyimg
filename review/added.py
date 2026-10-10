"""What the owner pastes (⌘V) or drops onto the board from outside (owner 2026-09-30: "to build moodboards and comment on them"; owner
2026-10-10: «я почему-то не могу перетащить видео на наш канвас. Или скопировать из буфера видео на канвас»). Moved here from server.py
with the videos (the file is at its size ceiling, AGENTS.md «Размер файлов»); server.add_image stays the name boardclip.py and the tests call.

One folder for everything added by hand, a subfolder per day: added/260930/174012-name.jpg, with a sidecar json saying where it came from
(a picture's <name>.json, a video's or a PDF's <name>.<ext>.json, as everywhere in the library). The same bytes added twice reuse the first file.

  POST /api/upload?name=<file name>   body: the file's bytes. A picture: jpeg, png and webp kept byte for byte, anything else Pillow can
                                      open stored as png, at most 80 MB (server.MAX_UPLOAD). A video, a PDF or a design file (server.py
                                      VIDEO_EXT, PDF_EXT, DOC_EXT) kept as it is, at most 4 GB: read a piece at a time into a hidden file in
                                      its day's folder, hashed on the way, then renamed; never held in memory whole
  POST /api/upload  {"url": ...}      a picture dragged off a web page, fetched by the server
Both answer {"path", "ar"} (and "again" for bytes the library already has); a file that is not a picture also says its "kind"."""
import hashlib
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
import uuid

from PIL import Image

ADDED = "added"
MAX_FILE = 4 << 30   # a video: a long 4K clip from a phone; a picture keeps server.MAX_UPLOAD
PIECE = 1 << 20
TXT = "text/plain; charset=utf-8"


def http(h, srv):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(h.path).query); name = q.get("name", [""])[0]
    n = int(h.headers.get("Content-Length", 0))
    url = (h.headers.get("Content-Type") or "").startswith("application/json")
    raw = not url and os.path.splitext(name)[1].lower() in srv.VIDEO_EXT + srv.PDF_EXT + srv.DOC_EXT
    if n > (MAX_FILE if raw else srv.MAX_UPLOAD):
        return h.send(413, (srv.tr("The file is over 4 GB", "Файл больше 4 ГБ") if raw else srv.tr("The file is over 80 MB", "Файл больше 80 МБ")).encode(), TXT)
    try:
        if url:
            link = json.loads(h.rfile.read(n) or b"{}").get("url", ""); res = add_image(srv, fetch_image(srv, link), url=link)
        else:
            res = add_file(srv, h.rfile, n, name) if raw else add_image(srv, h.rfile.read(n), name=name)
    except Exception as ex:
        h.close_connection = True   # a body read only in part: the connection cannot carry another request
        why = srv.tr("Couldn't add the file: ", "Не получилось добавить файл: ") if raw else srv.tr("Couldn't add the image: ", "Не получилось добавить картинку: ")
        return h.send(400, (why + str(ex)[:160]).encode(), TXT)
    return h.send(200, json.dumps(res, ensure_ascii=False).encode(), "application/json")


def fetch_image(srv, url):
    if not url.startswith(("http://", "https://")):
        raise ValueError("not a web address")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) review-board", "Accept": "image/*"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read(srv.MAX_UPLOAD + 1)
    if len(data) > srv.MAX_UPLOAD:
        raise ValueError("too big")
    return data


def _added_sha(srv):
    out = {}
    for root, _d, files in os.walk(os.path.join(srv.W, ADDED)):
        for f in files:
            if f.endswith(".json"):
                try:
                    m = json.load(open(os.path.join(root, f), encoding="utf-8")); out[m["sha1"]] = m["path"]
                except (OSError, ValueError, KeyError, TypeError):
                    pass
    return out


def _known(srv, sha):   # anywhere in the library, not only among pasted pictures
    known = _added_sha(srv).get(sha) or srv.dedup.known([sha]).get(sha)
    return known if known and os.path.exists(srv.real(known)) else None


def _free(d, stem, ext):   # <HHMMSS>-<stem>, ~2, ~3 for more in the same second
    base = time.strftime("%H%M%S") + "-" + stem; n = 2
    while os.path.exists(os.path.join(d, base + ext)): base = base.rsplit("~", 1)[0] + f"~{n}"; n += 1
    return base


def _stem(name, url, empty):
    return re.sub(r"[^a-z0-9а-яё_-]+", "-", os.path.splitext(os.path.basename(name or url.split("?")[0]))[0].lower()).strip("-")[:40] or empty


def _meta(srv, sha, rel, size, name, url):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    # what is known about a pasted picture is said in "prompt" and "model", so its card is not empty (owner 2026-10-03); the owner
    # knows the rest and may add it
    # written in the app's language at the moment of pasting (owner 2026-10-06: two languages); the owner's data from then on
    if srv.lang() == "ru":
        what = f"вставлено владельцем на холст {now[:16]}" + (f" со страницы {url}" if url else f" из файла {name}" if name and name != "image.png" else " из буфера обмена")
    else:
        what = f"pasted on the canvas by the owner {now[:16]}" + (f" from the page {url}" if url else f" from the file {name}" if name and name != "image.png" else " from the clipboard")
    return {"source": "owner", "how": "url" if url else "file", "added": now, "original_name": name, "url": url,
            "sha1": sha, "path": rel, "size": size, "model": srv.tr("pasted by the owner", "вставлено владельцем"), "prompt": what}


def add_image(srv, data, name="", url=""):
    if not data:
        raise ValueError("empty")
    sha = hashlib.sha1(data).hexdigest()
    with srv.LOCK:
        known = _known(srv, sha)
        if known:
            im = Image.open(srv.real(known)); return {"path": known, "ar": im.width / im.height, "again": True}
        try:
            im = Image.open(io.BytesIO(data)); im.load()
        except Exception:
            raise ValueError(srv.tr("not an image, or a format that does not open (jpg, png, webp, gif and tiff work)",
                                    "это не картинка или формат не открывается (подходят jpg, png, webp, gif, tiff)"))
        fmt = (im.format or "").upper()
        ext = {"JPEG": ".jpg", "MPO": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(fmt)
        if not ext:   # gif, tiff, bmp, heic (if a plugin is there): store the first frame as png
            buf = io.BytesIO(); (im if im.mode in ("RGB", "RGBA", "L", "LA") else im.convert("RGBA")).save(buf, "PNG"); data, ext = buf.getvalue(), ".png"
        day = time.strftime("%y%m%d"); d = os.path.join(srv.W, ADDED, day); os.makedirs(d, exist_ok=True)
        base = _free(d, _stem(name, url, "image"), ext)
        open(os.path.join(d, base + ext), "wb").write(data)
        rel = f"{ADDED}/{day}/{base}{ext}"
        srv._write_json(os.path.join(d, base + ".json"), _meta(srv, sha, rel, [im.width, im.height], name, url))
        return {"path": rel, "ar": im.width / im.height}


def _size(srv, rel):   # [w, h] as the board shows it: a video's picture (turned as it plays), else the library's own size of the file
    try: wh = srv.video_probe(srv.real(rel))[1] if srv.kind_of(rel) == "video" else srv.image_sizes([rel]).get(rel)
    except (OSError, ValueError): wh = None
    return wh if wh and wh[0] and wh[1] else None


def add_file(srv, body, n, name):
    """a video, a PDF or a design file as it is, from a stream of n bytes (the request's body)"""
    if not n: raise ValueError("empty")
    ext = os.path.splitext(name)[1].lower(); kind = srv.kind_of("x" + ext)
    day = time.strftime("%y%m%d"); d = os.path.join(srv.W, ADDED, day); os.makedirs(d, exist_ok=True)
    part, sha, got = os.path.join(d, f".upload-{uuid.uuid4().hex}.part"), hashlib.sha1(), 0   # hidden, not a library file
    try:
        with open(part, "wb") as f:
            while got < n:
                b = body.read(min(PIECE, n - got))
                if not b: break
                sha.update(b); f.write(b); got += len(b)
        if got < n: raise ValueError(srv.tr(f"only {got} of {n} bytes came", f"пришло только {got} из {n} байт"))
        sha = sha.hexdigest()
        with srv.LOCK:
            known = _known(srv, sha)
            if not known:
                base = _free(d, _stem(name, "", "file"), ext); rel = f"{ADDED}/{day}/{base}{ext}"; os.replace(part, os.path.join(d, base + ext))
    finally:
        if os.path.exists(part): os.remove(part)
    wh = _size(srv, known or rel)   # ffprobe or Quick Look: outside the server's lock
    ar = wh[0] / wh[1] if wh else 16 / 9 if kind == "video" else 1
    if known: return {"path": known, "ar": ar, "kind": srv.kind_of(known), "again": True}
    with srv.LOCK: srv._write_json(os.path.join(d, base + ext + ".json"), _meta(srv, sha, rel, wh, name, ""))
    return {"path": rel, "ar": ar, "kind": kind}
