"""The file-size rule of scripts/validate.py (owner 2026-10-07: «чтобы файлы не содержали больше тысячи строк на один файл»,
«допустимо, если будет 1050 или 1100, это окей»). A source file is about 1000 lines at most and fails above 1100; a line is about
160 characters at most and fails above 200 (canvas.html had lines of 884, which made a count of lines mean nothing).

Source: .py .js .mjs .cjs .ts .html .htm .css .swift .m .mm .h .sh of the four repositories, tests and native/ included.
Not counted: vendor/, node_modules/, dist/, build/, __pycache__/, .venv/, _review/ and every folder starting with a dot, *.min.js,
*.min.css, a file marked @generated in its first 5 lines, and anything else (json, md, svg, images, wasm: data, not code).
A line's length leaves out the URLs in it (http:// and https://), and the lang tables (lang.js, lang-*.js) have no line limit.

The files over the limits today sit in design/baseline.json, section "file_size", with their lines, their count of lines over 200
and their longest line. A baselined file fails when one of the three grows: it may only shrink. `validate.py --update-baseline`
lowers the numbers of a file that shrank and drops a file back under the limits; it never raises a number or adds a file
(it seeds the section only when there is none).
"""
import json, os, re, time
from pathlib import Path

RULE = "file-size"
SECTION = "file_size"
LINES, LINES_MAX = 1000, 1100      # the target and the ceiling of a file's lines
COLS, COLS_MAX = 160, 200          # the target and the ceiling of a line's characters
EXTS = (".py", ".js", ".mjs", ".cjs", ".ts", ".html", ".htm", ".css", ".swift", ".m", ".mm", ".h", ".sh")
SKIP_DIRS = {"vendor", "node_modules", "dist", "build", "__pycache__", ".venv", "_review"}
SKIP_SUFFIX = (".min.js", ".min.css")
LANG = re.compile(r"^lang(-[\w-]+)?\.js$")
URL = re.compile(r"https?://[^\s\"'<>`)\]]+")

HERE = Path(__file__).resolve().parent
REPOS_DIR = HERE.parent.parent
REPOS = ["hyimg", "hyimg-image-studio", "hyimg-3d-studio", "hyimg-dev-studio"]
last = {}   # the stats and baseline of the last check(), for summary() and listing()


def is_source(p):
    n = p.name.lower()
    return n.endswith(EXTS) and not n.endswith(SKIP_SUFFIX)


def files_of(args):
    out = []
    for t in [Path(a).resolve() for a in args] or [REPOS_DIR / r for r in REPOS]:
        if t.is_file():
            if is_source(t): out.append(t)
            continue
        for d, ds, fs in os.walk(t):
            ds[:] = sorted(x for x in ds if x not in SKIP_DIRS and not x.startswith("."))
            out += [Path(d) / f for f in sorted(fs) if is_source(Path(f))]
    return sorted(set(out))


def rel(p):
    try: return str(p.relative_to(REPOS_DIR))
    except ValueError: return str(p)


def stats(text, name=""):
    """{lines, long_lines (over COLS_MAX), max_line, longest, warn_lines (over COLS), first_long} of a file's text; None for a generated file"""
    lines = text.split("\n")
    if any("@generated" in l for l in lines[:5]): return None
    n = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    if LANG.match(name): widths = [0]
    else: widths = [len(URL.sub("", l.rstrip("\r"))) for l in lines]
    first = next((i + 1 for i, w in enumerate(widths) if w > COLS_MAX), 0)
    return {"lines": n, "long_lines": sum(w > COLS_MAX for w in widths), "max_line": max(widths), "longest": widths.index(max(widths)) + 1,
            "warn_lines": sum(w > COLS for w in widths), "first_long": first}


def held(s):
    """what the baseline keeps of a file's stats: lines over the ceiling, long lines and the longest line, or None"""
    e = {}
    if s["lines"] > LINES_MAX: e["lines"] = s["lines"]
    if s["long_lines"]: e["long_lines"], e["max_line"] = s["long_lines"], s["max_line"]
    return e or None


def scan(paths):
    out = {}
    for p in files_of(paths):
        try: s = stats(p.read_text(encoding="utf-8", errors="replace"), p.name)
        except OSError: continue
        if s: out[rel(p)] = s
    return out


def check(paths, base):
    """the file-size violations of the files under paths against the baseline section `base` (its "files")"""
    st, known = scan(paths), base.get("files", {})
    last.clear(); last.update(stats=st, known=known)
    items = []
    for f, s in st.items():
        b = known.get(f, {})
        cap, long_cap, max_cap = b.get("lines", LINES_MAX), b.get("long_lines", 0), max(b.get("max_line", 0), COLS_MAX)
        split = "split it by responsibility into modules, one concern per file"
        if s["lines"] > cap:
            was = f"the baseline holds it at {cap} and it may only shrink" if "lines" in b else f"over the ceiling of {LINES_MAX}"
            items.append(item(f, cap + 1, f"{s['lines']} lines, {was} (about {LINES} lines per file): {split}"))
        if s["long_lines"] > long_cap:
            was = f"the baseline holds {long_cap}" if long_cap else f"the ceiling is {COLS_MAX}"
            items.append(item(f, s["first_long"], f"{s['long_lines']} lines over {COLS_MAX} characters, {was} (about {COLS} per line, "
                                                    "URLs and lang tables aside): wrap them"))
        elif s["max_line"] > max_cap:
            items.append(item(f, s["longest"], f"a line of {s['max_line']} characters, the baseline's longest is {max_cap}: "
                                                    f"wrap it (about {COLS} per line)"))
    return items


def item(f, line, msg):
    return {"file": f, "line": line, "rule": RULE, "msg": msg, "text": msg}


def summary():
    """one or two lines for validate's table: what the baseline holds, what shrank, what is near the limit"""
    st, known = last.get("stats", {}), last.get("known", {})
    big = [f for f in st if "lines" in known.get(f, {})]
    wide = [f for f in st if known.get(f, {}).get("long_lines")]
    shrank = [f for f, b in known.items() if f in st and any(st[f][k] < v for k, v in b.items() if k in ("lines", "long_lines", "max_line"))]
    near = sorted(f for f, s in st.items() if LINES < s["lines"] <= LINES_MAX and "lines" not in known.get(f, {}))
    out = f"file-size: {len(big)} files over {LINES_MAX} lines and {len(wide)} with lines over {COLS_MAX} held by the baseline"
    if shrank: out += f"; {len(shrank)} shrank (--update-baseline lowers them)"
    if near: out += f"\nfile-size: over {LINES} lines, under the ceiling: " + ", ".join(f"{f} ({st[f]['lines']})" for f in near)
    return out


def listing():
    """every file over a target, baselined or not: lines, lines over 200, lines over 160, longest line"""
    st, known = last.get("stats", {}), last.get("known", {})
    rows = [(s["lines"], f, s) for f, s in st.items() if s["lines"] > LINES or s["warn_lines"]]
    out = [f"{'lines':>6} {'>200':>5} {'>160':>5} {'max':>5}  file"]
    for n, f, s in sorted(rows, key=lambda r: (-r[0], r[1])):
        out.append(f"{n:>6} {s['long_lines']:>5} {s['warn_lines']:>5} {s['max_line']:>5}  {f}{'  (baseline)' if f in known else ''}")
    return "\n".join(out)


def update(baseline_path, paths=()):
    """lower the section to what the files are now (never raise, never add); seed it when there is none. Returns a message."""
    try: data = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    except (OSError, ValueError): data = {}
    st, sec = scan(list(paths)), data.get(SECTION)
    files = {}
    if sec is None:
        files = {f: e for f, s in sorted(st.items()) for e in [held(s)] if e}
    else:
        for f, old in sorted(sec.get("files", {}).items()):
            if f not in st: files[f] = old; continue   # not here (another checkout, a file not written yet): kept as it was
            now = held(st[f]) or {}
            e = {k: min(v, now[k]) for k, v in old.items() if k in now}
            if e: files[f] = e
    data[SECTION] = {"note": f"files over {LINES_MAX} lines or with lines over {COLS_MAX} characters, as they were; "
                             "each number may only go down (scripts/validate_size.py)",
                     "updated": time.strftime("%Y-%m-%d"), "files": files}
    Path(baseline_path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return f"file-size baseline: {len(files)} files held"
