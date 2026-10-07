"""A WebM copy of a library video for an engine that cannot play the original (owner 2026-10-05: «не проигрывается видео когда
нажимаю на play»). The app's Chromium (the CEF build from cef-builds.spotifycdn.com) has no H.264 or AAC decoder: an mp4 or mov from
a phone or a generator gives MEDIA_ERR_SRC_NOT_SUPPORTED there, while VP9 and Opus play. The board asks for /video?p=..&fmt=webm
when its engine says it cannot play a file; this makes the copy once per version of the file with ffmpeg and keeps it in the app's
cache (~/Library/Caches/Hyimg/video), never next to the owner's files. WebKit and a full Chrome play the original and never ask.

One ffmpeg per file: a second request for the same file waits for the first one. At most SLOTS run at once (a board scrolled over
40 clips queues them)."""
import hashlib
import os
import shutil
import subprocess
import threading

CACHE = os.environ.get("HYIMG_VIDEO_CACHE") or os.path.join(os.environ.get("HYIMG_CACHE_ROOT") or os.path.expanduser("~/Library/Caches/Hyimg"), "video")
SLOTS = threading.BoundedSemaphore(2)
TIMEOUT = 600   # a long clip on a slow Mac; the job gives up after this many seconds
_GUARD = threading.Lock()
_JOBS = {}      # cache file -> {"done": Event, "error": str | None}


def ffmpeg():
    # the app starts the server without the shell's PATH, Homebrew's tools are looked for where they live
    own = os.environ.get("HYIMG_FFMPEG")   # tests: a counting wrapper, or a missing path for "no ffmpeg"
    if own is not None: return own if own and os.path.exists(own) else None
    return shutil.which("ffmpeg") or next((p for p in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg") if os.path.exists(p)), None)


def target(full):
    """where the copy of this version of the file lives"""
    key = f"{full}\0{os.path.getmtime(full)}\0{os.path.getsize(full)}"
    return os.path.join(CACHE, hashlib.sha1(key.encode()).hexdigest() + ".webm")


def has_audio(exe, full):
    probe = os.path.join(os.path.dirname(exe), "ffprobe")
    if not os.path.exists(probe):
        probe = shutil.which("ffprobe") or next((p for p in ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe") if os.path.exists(p)), "")
    if not probe: return True   # unknown: ask ffmpeg for audio, -map 0:a? leaves it out when there is none
    try:
        out = subprocess.run([probe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", full],
                             capture_output=True, text=True, timeout=20).stdout
        return bool(out.strip())
    except (OSError, subprocess.SubprocessError):
        return True


def command(exe, full, out, audio):
    # VP9 in realtime mode (owner's spec 2026-10-05): a 10 s phone clip takes a few seconds; the long side at most 1920, even sizes
    scale = "scale='if(gte(iw,ih),min(1920,iw),-2)':'if(gte(iw,ih),-2,min(1920,ih))'"
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", full, "-map", "0:v:0", "-vf", scale,
           "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "33", "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1", "-pix_fmt", "yuv420p"]
    cmd += ["-map", "0:a:0?", "-c:a", "libopus", "-b:a", "128k"] if audio else ["-an"]
    return cmd + ["-f", "webm", out]


def state(full):
    """"ready" | "working" | "failed" | "noffmpeg" | "none" for this file, without starting anything"""
    out = target(full)
    if os.path.exists(out): return "ready"
    with _GUARD:
        j = _JOBS.get(out)
    if j: return "failed" if j["done"].is_set() and j["error"] else "working"
    return "none" if ffmpeg() else "noffmpeg"


LIMIT = int(os.environ.get("HYIMG_VIDEO_CACHE_MB") or 4096) << 20   # the cache stays under 4 GB: the copies used longest ago go first


def prune(keep=None):
    try:
        files = [os.path.join(CACHE, f) for f in os.listdir(CACHE) if f.endswith(".webm")]
        files = sorted(((os.stat(f), f) for f in files), key=lambda x: max(x[0].st_atime, x[0].st_mtime))
        total = sum(st.st_size for st, _f in files)
        for st, f in files:
            if total <= LIMIT: break
            if f == keep: continue
            os.remove(f); total -= st.st_size
    except OSError:
        pass


def _run(full, out, job):
    exe = ffmpeg()
    try:
        if not exe:
            job["error"] = "noffmpeg"; return
        os.makedirs(CACHE, exist_ok=True)
        tmp = out + f".{os.getpid()}.{threading.get_ident()}.part"
        with SLOTS:
            r = subprocess.run(command(exe, full, tmp, has_audio(exe, full)), capture_output=True, text=True, timeout=TIMEOUT)
        if r.returncode or not os.path.exists(tmp) or not os.path.getsize(tmp):
            job["error"] = (r.stderr or "ffmpeg failed").strip()[-300:]
            try: os.remove(tmp)
            except OSError: pass
            return
        os.replace(tmp, out)   # whole or nothing: a half-written copy is never served
        prune(keep=out)
    except (OSError, subprocess.SubprocessError) as ex:
        job["error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
    finally:
        job["done"].set()
        if not job["error"]:
            with _GUARD: _JOBS.pop(out, None)


def start(full):
    """starts making the copy in the background if it is not there and not being made; returns the job (None when it is ready)"""
    out = target(full)
    if os.path.exists(out): return None
    with _GUARD:
        j = _JOBS.get(out)
        if j and j["done"].is_set() and j["error"] and j["error"] != "noffmpeg":
            return j   # failed once for this version: not again on every hover (a new version of the file gets a new name)
        if j and not (j["done"].is_set() and j["error"] == "noffmpeg" and ffmpeg()):
            return j
        j = _JOBS[out] = {"done": threading.Event(), "error": None}
    threading.Thread(target=_run, args=(full, out, j), daemon=True, name="webvideo").start()
    return j


# The trim strip's frames (owner 2026-10-06: «a filmstrip of frames over the bottom of the video, two handles for in and out»): n
# pictures evenly along the clip, made once per version of the file and per n with one ffmpeg (one input seek per frame, so a long
# clip is never decoded whole), kept in the app's cache (~/Library/Caches/Hyimg/video/strip), never next to the owner's files.
_STRIPS = {}    # cache folder -> Lock: a second request for the same strip waits for the first one


def strip(full, n, dur, height=144):
    """the paths of n JPEG frames along the clip (dur seconds long), made now if needed; raises RuntimeError("noffmpeg" or ffmpeg's words)"""
    key = f"{full}\0{os.path.getmtime(full)}\0{os.path.getsize(full)}\0{n}\0{height}"
    d = os.path.join(CACHE, "strip", hashlib.sha1(key.encode()).hexdigest())
    outs = [os.path.join(d, f"{i:02d}.jpg") for i in range(n)]
    if all(os.path.exists(o) for o in outs): return outs
    with _GUARD:
        lock = _STRIPS.setdefault(d, threading.Lock())
    with lock:
        if all(os.path.exists(o) for o in outs): return outs
        exe = ffmpeg()
        if not exe: raise RuntimeError("noffmpeg")
        tmp = f"{d}.{os.getpid()}.{threading.get_ident()}.part"
        os.makedirs(tmp, exist_ok=True)
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
        for i in range(n): cmd += ["-ss", f"{dur * (i + 0.5) / n:.3f}", "-i", full]
        for i in range(n): cmd += ["-map", f"{i}:v:0", "-frames:v", "1", "-vf", f"scale=-2:{height}", "-q:v", "5", os.path.join(tmp, f"{i:02d}.jpg")]
        try:
            with SLOTS:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as ex:
            shutil.rmtree(tmp, ignore_errors=True); raise RuntimeError(f"{type(ex).__name__}: {str(ex)[:200]}")
        made = [os.path.join(tmp, f"{i:02d}.jpg") for i in range(n)]
        if not any(os.path.exists(m) and os.path.getsize(m) for m in made):
            shutil.rmtree(tmp, ignore_errors=True); raise RuntimeError((r.stderr or "ffmpeg failed").strip()[-300:])
        last = next(m for m in made if os.path.exists(m) and os.path.getsize(m))
        for m in made:   # a seek past the last frame of a clip with a rounded length gives nothing: the frame before stands in
            if os.path.exists(m) and os.path.getsize(m): last = m
            else: shutil.copyfile(last, m)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if os.path.isdir(d): shutil.rmtree(d, ignore_errors=True)
        os.replace(tmp, d)   # whole or nothing
    return outs


def ensure(full, wait=TIMEOUT + 30):
    """the path of the ready copy, made now if needed (the caller waits); raises RuntimeError("noffmpeg" or ffmpeg's words)"""
    j = start(full)
    out = target(full)
    if j is None: return out
    j["done"].wait(wait)
    if os.path.exists(out): return out
    raise RuntimeError(j["error"] or "timeout")
