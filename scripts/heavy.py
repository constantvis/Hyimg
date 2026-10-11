#!/usr/bin/env python3
"""Run a heavy job (Blender, a model, a big script) without killing the Mac.

    python3 scripts/heavy.py [--slots 1] [--max-gb 3] [--min-free 12] [--wait-free 20] -- <command ...>

- One shared queue for every agent on this machine: at most --slots heavy jobs at once, the rest wait their turn.
- Waits to start until free memory is at least --wait-free percent.
- Watches the whole process tree every second. It stops the job when the tree goes over --max-gb of resident memory
  or free memory falls under --min-free percent. Exit code 137, the reason on stderr and in the log.
- Log: ~/Library/Caches/Hyimg/heavy/log.txt (start, end, peak memory, time, stops).

Why (2026-10-11): 9 agents ran renders and models side by side. One Blender grew to 48 GB on a 16 GB Mac,
and the owner had to force-quit everything. The same guard now protects every agent that goes through here.
"""
import argparse, fcntl, os, signal, subprocess, sys, time

DIR = os.environ.get("HYIMG_HEAVY_DIR") or os.path.expanduser("~/Library/Caches/Hyimg/heavy")
LOG = os.path.join(DIR, "log.txt")


def free_percent():
    """Free memory in percent, as macOS memory_pressure reports it. None if unknown (then no memory gate)."""
    if os.environ.get("HYIMG_HEAVY_FREE"):   # tests
        return float(os.environ["HYIMG_HEAVY_FREE"])
    try:
        out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            if "free percentage" in line:
                return float(line.split(":")[1].strip().rstrip("%"))
    except Exception:
        pass
    return None


def tree_rss_kb(root):
    """Resident memory of a process and all its children, in KB."""
    try:
        out = subprocess.run(["ps", "-axo", "pid=,ppid=,rss="], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return 0
    kids, rss = {}, {}
    for line in out.splitlines():
        p = line.split()
        if len(p) == 3:
            pid, ppid, r = map(int, p)
            kids.setdefault(ppid, []).append(pid); rss[pid] = r
    total, todo = 0, [root]
    while todo:
        p = todo.pop(); total += rss.get(p, 0); todo += kids.get(p, [])
    return total


def log(msg):
    os.makedirs(DIR, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def alive(pid):
    try:
        os.kill(pid, 0); return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def my_turn(ticket, n):
    """First come, first served: only the n oldest live tickets may take a slot.
    Without this a 5-second render waited over an hour while long jobs kept winning the 2-second race (2026-10-11)."""
    q = os.path.join(DIR, "queue"); live = []
    for t in sorted(os.listdir(q)):
        try: pid = int(t.split("-")[1])
        except (IndexError, ValueError): continue
        if alive(pid): live.append(t)
        else:
            try: os.remove(os.path.join(q, t))
            except FileNotFoundError: pass
    return ticket in live[:n]


def take_slot(n):
    """Block until it's this job's turn and one of n slots is free; return the open locked file (the lock lives as long as the file)."""
    q = os.path.join(DIR, "queue"); os.makedirs(q, exist_ok=True)
    ticket = f"{time.time_ns():020d}-{os.getpid()}"
    open(os.path.join(q, ticket), "w").close()
    try:
        while True:
            if my_turn(ticket, n):
                f = grab(n)
                if f: return f
            time.sleep(0.5)
    finally:
        try: os.remove(os.path.join(q, ticket))
        except FileNotFoundError: pass


def grab(n):
    for i in range(n):
        f = open(os.path.join(DIR, f"slot{i}.lock"), "w")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            f.write(str(os.getpid())); f.flush()
            return f
        except OSError:
            f.close()
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slots", type=int, default=int(os.environ.get("HYIMG_HEAVY_SLOTS", 1)))
    ap.add_argument("--max-gb", type=float, default=3.0)
    ap.add_argument("--min-free", type=float, default=12.0)
    ap.add_argument("--wait-free", type=float, default=20.0)
    ap.add_argument("--poll", type=float, default=1.0)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not cmd:
        ap.error("no command after --")
    name = os.path.basename(cmd[0])
    slot = take_slot(max(1, a.slots))
    waited = time.time()
    while (fr := free_percent()) is not None and fr < a.wait_free:
        if time.time() - waited > 600:
            log(f"gave up {name}: free {fr:.0f}% under {a.wait_free:.0f}% for 10 min"); print(f"heavy: free memory {fr:.0f}% for 10 min, not starting", file=sys.stderr)
            return 75
        time.sleep(3)
    t0 = time.time(); peak = 0
    p = subprocess.Popen(cmd, start_new_session=True)
    log(f"start {name} pid {p.pid} slot {slot.name.rsplit('slot', 1)[1].split('.')[0]}")
    reason = None
    while p.poll() is None:
        kb = tree_rss_kb(p.pid); peak = max(peak, kb)
        fr = free_percent()
        if kb > a.max_gb * 1048576:
            reason = f"used {kb / 1048576:.1f} GB, limit {a.max_gb:g} GB"
        elif fr is not None and fr < a.min_free:
            reason = f"free memory {fr:.0f}%, under {a.min_free:g}%"
        if reason:
            try: os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            p.wait(); break
        time.sleep(a.poll)
    dt = time.time() - t0
    if reason:
        log(f"STOPPED {name} after {dt:.0f}s: {reason}")
        print(f"heavy: stopped {name}: {reason}. Make the job smaller (resolution, samples, batch) instead of retrying it as is", file=sys.stderr)
        return 137
    log(f"end {name} code {p.returncode} {dt:.0f}s peak {peak / 1048576:.2f} GB")
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
