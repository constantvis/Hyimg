"""scripts/heavy.py: the shared queue and memory guard for agents' heavy jobs (2026-10-11, a 48 GB Blender froze the Mac)."""
import os, subprocess, sys, threading, time
from pathlib import Path

HEAVY = Path(__file__).resolve().parents[2] / "scripts" / "heavy.py"


def run(tmp_path, *args, free="80", timeout=30):
    env = dict(os.environ, HYIMG_HEAVY_DIR=str(tmp_path), HYIMG_HEAVY_FREE=free)
    return subprocess.run([sys.executable, str(HEAVY), *args], capture_output=True, text=True, env=env, timeout=timeout)


def test_a_normal_job_runs_and_is_logged(tmp_path):
    r = run(tmp_path, "--", sys.executable, "-c", "print('ok')")
    assert r.returncode == 0 and "ok" in r.stdout
    assert "code 0" in (tmp_path / "log.txt").read_text()


def test_a_job_over_the_memory_limit_is_stopped(tmp_path):
    hog = "import time; b = bytearray(400 * 1024 * 1024); b[::4096] = b'x' * len(b[::4096]); time.sleep(20)"
    t = time.time()
    r = run(tmp_path, "--max-gb", "0.2", "--poll", "0.2", "--", sys.executable, "-c", hog)
    assert r.returncode == 137 and "limit" in r.stderr
    assert time.time() - t < 15
    assert "STOPPED" in (tmp_path / "log.txt").read_text()


def test_low_free_memory_stops_the_job(tmp_path):
    r = run(tmp_path, "--min-free", "25", "--wait-free", "10", "--poll", "0.2", "--", sys.executable, "-c", "import time; time.sleep(20)", free="20")
    assert r.returncode == 137 and "free memory" in r.stderr


def test_jobs_run_in_the_order_they_arrived(tmp_path):
    # 2026-10-11: a 5-second render waited over an hour while other agents' jobs kept winning the race for the slot
    marks = tmp_path / "marks.txt"
    def job(tag, sec):
        return f"import time; open({str(marks)!r}, 'a').write('{tag}'); time.sleep({sec})"
    first = threading.Thread(target=run, args=(tmp_path, "--", sys.executable, "-c", job("A", 2)))
    first.start(); time.sleep(0.8)
    later = []
    for tag in "BCDE":   # queued in this order while A holds the slot
        th = threading.Thread(target=run, args=(tmp_path, "--", sys.executable, "-c", job(tag, 0.3)))
        th.start(); later.append(th); time.sleep(0.4)
    for th in [first, *later]: th.join()
    assert marks.read_text() == "ABCDE"


def test_one_slot_means_jobs_wait_their_turn(tmp_path):
    marks = tmp_path / "marks.txt"
    job = f"import time; open({str(marks)!r}, 'a').write('s'); time.sleep(1.5); open({str(marks)!r}, 'a').write('e')"
    ths = [threading.Thread(target=run, args=(tmp_path, "--slots", "1", "--", sys.executable, "-c", job)) for _ in range(2)]
    for th in ths: th.start(); time.sleep(0.3)
    for th in ths: th.join()
    assert marks.read_text() == "sese"
