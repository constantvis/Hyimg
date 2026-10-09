"""The performance log's writer (review/perflog.py, owner 2026-10-08: a log written only when frames drop, «чтобы не было гигабайтов»):
nothing while it is off, one entry per 5 s per page, an entry at most 16 KB, files of 2 MB rotated within the day, all of them at most
20 MB with the oldest going first, «Clear» removes only its own files, never a folder in Dropbox. A throwaway cache folder only."""
import json
import os
import subprocess
import sys

import pytest

import perflog

ON = {"cv.perflog": "1"}


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("HYIMG_CACHE_ROOT", str(tmp_path / "cache"))
    perflog._LAST.clear()
    yield tmp_path / "cache" / "perf"
    perflog._LAST.clear()


def entry(page="main", pad=0, **kw):
    return {"board": "b1", "page": page, "action": "zoom", "zoom": 0.1, "frames": {"n": 30, "slow": 4, "worst": [120, 80, 60]}, "pad": "x" * pad, **kw}


def test_off_writes_nothing(cache):
    assert perflog.append(entry(), {"cv.perflog": "0"}) == {"skipped": "off"}
    assert perflog.enabled({}) and not perflog.enabled({"cv.perflog": "0"})   # on until turned off (owner 2026-10-08)
    assert not cache.exists() and perflog.size() == {"bytes": 0, "files": 0}


def test_one_entry_per_five_seconds_per_page(cache):
    assert "ok" in perflog.append(entry(), ON, now=1000.0)
    assert perflog.append(entry(), ON, now=1003.0) == {"skipped": "rate"}
    assert "ok" in perflog.append(entry(page="p2"), ON, now=1003.0), "another page has its own clock"
    assert "ok" in perflog.append(entry(), ON, now=1005.5)
    got = perflog.read(10)
    assert [e["page"] for e in got] == ["main", "p2", "main"] and all("at" in e for e in got)


def test_a_big_entry_and_a_bad_one_are_refused(cache):
    assert perflog.append(entry(pad=perflog.ENTRY_MAX), ON, now=1.0) == {"skipped": "big"}
    assert perflog.append(["not", "a", "dict"], ON, now=100.0) == {"skipped": "bad"}
    assert perflog.size()["bytes"] == 0


def test_files_rotate_and_the_total_stays_under_the_cap(cache, monkeypatch):
    monkeypatch.setattr(perflog, "FILE_MAX", 4000); monkeypatch.setattr(perflog, "CAP", 10000)
    day = 1791400000.0   # one day, entries 6 s apart: each ~1.5 KB
    for k in range(40): assert "ok" in perflog.append(entry(pad=1300), ON, now=day + 6 * k)
    names = sorted(os.listdir(cache))
    assert all(n == ".lock" or perflog.NAME.match(n) for n in names)
    s = perflog.size()
    assert s["bytes"] <= 10000 and s["files"] >= 3, s
    for f in perflog.files(): assert os.path.getsize(f) <= 4000
    names = [os.path.basename(f) for f in perflog.files()]
    assert int(names[-1].rsplit("-", 1)[1][:-6]) > len(names), names   # numbered on after the oldest of the day went
    newest = perflog.read(1)[0]
    assert newest["pad"] == "x" * 1300 and perflog.read(500)[-1] == newest, "the oldest went, the newest stayed"
    # a new day starts its own file
    assert "ok" in perflog.append(entry(), ON, now=day + 86400 * 2)
    assert os.path.basename(perflog.files()[-1]).count("-") == 3, perflog.files()


def test_clear_removes_only_the_log(cache):
    for k in range(3): perflog.append(entry(), ON, now=10.0 + 6 * k)
    other = cache / "notes.txt"; other.write_text("mine")
    got = perflog.clear()
    assert got["removed"] == 1 and got["freed"] > 0
    assert perflog.size() == {"bytes": 0, "files": 0} and other.read_text() == "mine"
    assert "ok" in perflog.append(entry(), ON, now=11.0), "the clock starts again after a clear"


def test_cli_clear_prints_what_the_http_clear_answers(cache, tmp_path):
    """python3 perflog.py clear: Home's «Clear» through the app (native/StorageBridge.swift op "perflog"), in the folder perflog.py
    computes from HYIMG_CACHE_ROOT; the JSON on stdout is the HTTP answer's, {"freed", "removed"}"""
    perflog.append(entry(), ON, now=1791400000.0); perflog.append(entry(page="p2"), ON, now=1791400000.0 + 86400)
    other = cache / "notes.txt"; other.write_text("mine")
    want = perflog.size()
    run = lambda env: subprocess.run([sys.executable, perflog.__file__, "clear"], env={**os.environ, **env}, capture_output=True, text=True, timeout=30)
    out = run({})
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == {"freed": want["bytes"], "removed": 2} and want["files"] == 2
    assert perflog.size() == {"bytes": 0, "files": 0} and other.read_text() == "mine"
    assert json.loads(run({}).stdout) == {"freed": 0, "removed": 0}
    # a cache without the log's folder: nothing to clear and no folder made
    out = run({"HYIMG_CACHE_ROOT": str(tmp_path / "fresh")})
    assert json.loads(out.stdout) == {"freed": 0, "removed": 0} and not (tmp_path / "fresh").exists()


def test_never_in_dropbox(tmp_path, monkeypatch):
    home = tmp_path / "home"; (home / "Dropbox" / "c").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home)); monkeypatch.setenv("HYIMG_CACHE_ROOT", str(home / "Dropbox" / "c"))
    perflog._LAST.clear()
    assert perflog.append(entry(), ON, now=5.0) == {"skipped": "dropbox"}
    assert not (home / "Dropbox" / "c" / "perf").exists()


def test_summary_names_the_worst_and_what_was_on_screen(cache):
    a = entry(frames={"n": 20, "slow": 3, "median": 40, "worst": [90, 70]}, counts={"visible": {"html": 48}, "pins": 47, "liveFrames": 0})
    b = entry(page="p2", action="pan", frames={"n": 50, "slow": 9, "median": 60, "worst": [700, 300]}, counts={"visible": {"htmlframe": 21}, "pins": 3},
              panels={"bell": True, "library": False})
    perflog.append(a, ON, now=1.0); perflog.append(b, ON, now=2.0)
    text = "\n".join(perflog.summary(perflog.read(10)))
    assert "Эпизодов: 2" in text and "zoom 1" in text and "pan 1" in text
    assert text.index("[700, 300]") < text.index("[90, 70]"), "the worst first"
    assert "htmlframe 21" in text and "пинов 47" in text and "bell" in text
    assert "пуст" in perflog.summary([])[0]


def test_http_get_and_clear(cache):
    class H:
        def __init__(self, path, body=b""):
            import io
            self.path, self.headers, self.rfile, self.out = path, {"Content-Length": str(len(body))}, io.BytesIO(body), None
        def send(self, code, body, ctype): self.out = (code, json.loads(body) if ctype == "application/json" else body)
    h = H("/api/perflog", json.dumps(entry()).encode()); perflog.http(h, "POST", lambda: {"cv.perflog": "0"})
    assert h.out == (200, {"skipped": "off"})
    h = H("/api/perflog", json.dumps(entry()).encode()); perflog.http(h, "POST", lambda: ON)
    assert h.out[0] == 200 and "ok" in h.out[1]
    h = H("/api/perflog?last=5"); perflog.http(h, "GET", lambda: ON)
    assert h.out[1]["on"] is True and h.out[1]["files"] == 1 and len(h.out[1]["entries"]) == 1
    h = H("/api/perflog/clear", b"{}"); perflog.http(h, "POST", lambda: ON)
    assert h.out[1]["removed"] == 1 and perflog.size()["files"] == 0
