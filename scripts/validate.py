#!/usr/bin/env python3
"""The static design and code validator of Hyimg's four repositories (owner 2026-10-06: «делай юнит тесты, тесты ui, валидаторы,
консистентный design валидатор»). It reads the .html, .js and .css of hyimg, hyimg-image-studio, hyimg-3d-studio and hyimg-dev-studio
(vendor/, node_modules/, tests/, docs/, native/, dist/ and build/ are skipped) and checks them against the design contract
(design/contract.json, its words in design/CONTRACT.md). The file-size rule (scripts/validate_size.py) reads every source file of the
four repositories, .py, .swift and tests too: about 1000 lines and 160 characters a line, failing above 1100 and 200.

  python3 scripts/validate.py                      every file of the four repositories
  python3 scripts/validate.py ../hyimg-image-studio      one repository (a folder or files; from any of the four)
  python3 scripts/validate.py --update-baseline    today's violations become the known ones (design/baseline.json, "static")
  python3 scripts/validate.py --list RULE          every violation of a rule, known ones too
  python3 scripts/validate.py --list file-size     every file over 1000 lines or with lines over 160 characters
  python3 scripts/validate.py --rules              the rules with their reasons

A violation is printed as `file:line  rule  message`. The baseline counts what is known per rule, file and line text, so the check
passes today and fails only on a NEW violation (a ratchet: fixed ones leave the count, `--update-baseline` writes it down).
One line is let through with a comment on it or on the line above: `hy-allow: <rule> <reason>`.
Exit status: 0 nothing new, 1 something new, 2 the validator itself failed.
"""
import argparse, concurrent.futures, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HYIMG = HERE.parent
REPOS_DIR = HYIMG.parent
REPOS = ["hyimg", "hyimg-image-studio", "hyimg-3d-studio", "hyimg-dev-studio"]
CONTRACT = HYIMG / "design" / "contract.json"
BASELINE = HYIMG / "design" / "baseline.json"
SKIP_DIRS = {"vendor", "node_modules", ".git", "dist", "build", "__pycache__", "tests", "docs", "native", ".pytest_cache", "_review", ".venv"}
EXTS = (".html", ".htm", ".js", ".mjs", ".css")
sys.path.insert(0, str(HERE)); import validate_size as FS   # the file-size rule, a file of its own so this one stays under 1000 lines
import validate_row as ROW   # the row-plate rule (the top row), a file of its own for the same reason
import validate_prim as PRIM   # the hy-primitive rule (a control that has a primitive is not built again), the same reason

RULES = {
    "js-syntax": "every .js and every inline <script> parses (node --check); a `//` comment that swallowed code broke a page twice (2026-10-06)",
    "comment-swallow": "a `//` comment after code on a line whose rest is code, or a `//` inside CSS or HTML text, silently eats what follows",
    "easing": "transitions and animations use the contract's curves (owner: «везде easing-анимации», one curve cubic-bezier(.32,.72,0,1))",
    "focus-ring": "no outline or box-shadow ring on :focus / :focus-visible (owner 2026-10-05: «убери эти уебищные focus выделения»)",
    "range-input": "an <input type=range> lives only inside .hy-slider, mounted by ui/slider.js (owner 2026-10-06: «Свои ползунки не рисовать»)",
    "row-radius": "a row control (select, field, slider, chip, option) takes var(--hy-row-r), not a radius of its own (owner 2026-10-06: «одни круглые другие квадратные»)",
    "icon-stroke": "an icon's stroke-width is one of the contract's lines (the editors' family 1.85, menus 1.9, chevron 2.4 ...)",
    "cyrillic-code": "Russian words live in the lang files (ui/lang-*.js, a plugin's lang.js), the code writes English keys (owner 2026-10-06: «make 2 versions»)",
    "lang-period": "a short UI string has no period at its end (owner: «Без точек в коротких строках»)",
    "ru-style": "Russian UI text has no em dash and no ё (owner's style: ochelovech)",
    "z-layer": "z-index values sit in the contract's layers, so a panel never slides under another by accident (the selection bar under the library, 2026-10-06)",
    "file-size": ("a source file is about 1000 lines and a line about 160 characters (owner 2026-10-07: «чтобы файлы не содержали больше "
                  "тысячи строк на один файл»): above 1100 lines or 200 characters fails, the files over today are held in the baseline "
                  "and may only shrink (scripts/validate_size.py)"),
    "capsule-pad": "a capsule's words keep off its round ends (owner 2026-10-06: «Presets ⌄» flush against its capsule, «посмотри, где еще вот такие проблемы есть, где нет пэддинга по сторонам»): a pill with words has at least the contract's side padding, and a reset like `.panel button { padding: 0 }` is wrapped in :where() so it does not outweigh a button's own padding",
    "font-family": "the app's fonts are Geist and Geist Mono with system fallbacks; another family is a page drifting from the system",
    "row-plate": ROW.REASON,
    "hy-primitive": PRIM.REASON,
    "panel-prose": "a panel's, a popover's, an empty state's or a setting's explanation is a footnote or nothing (owner 2026-10-06: «Вот эти комментарии никто не читает ... Если текст не ключевой, то зачем он вообще нужен»): more than 14 words in body text fails, use .hy-hint (key words in <b>) or a ⓘ (.hy-info)",
    "icon-inline": "an icon is drawn only by ui/icons.js (owner 2026-10-07: «одно значение, одна иконка»): hyIcon(name, size, line), <svg data-ic=name> in static markup, hyIconPath(name) on a canvas, the --hy-ic-* CSS images; a page, a plugin or a stylesheet writes no <path>, <circle>, <rect> ... of its own; a drawing that is not an icon (the board's arrows, a cursor, a chart) says so with hy-allow: icon-inline <what it is>",
    "icon-registry": "the registry (ui/icons.js HY_TOOL_IC) has one glyph per name and one name per glyph, each with its meaning (the comment after it); every name a page asks for (hyIcon, data-ic, hyMarkIcon, a table marked hy-icon-names) is in it",
    "icon-color": "an icon is drawn in currentColor: a glyph's fill and stroke are none or currentColor, the colour comes from CSS; the one exception is Raw Editor's «on» disc (hyGradeIcon), outside the registry",
    "css-color": "colours only by tokens (owner 2026-10-07: «консистентные цвета»): a hex, rgb() or hsl() in a CSS declaration is written only as a token's value (--name: #...) or a var() fallback; a mask's alpha is not a colour (contract colors.not_colour_props)",
}

CYR = re.compile(r"[А-Яа-яЁё]")
ALLOW = re.compile(r"hy-allow:\s*([\w-]+(?:\s*,\s*[\w-]+)*)")
ALLOW_BEGIN = re.compile(r"hy-allow-begin:\s*([\w-]+(?:\s*,\s*[\w-]+)*)")


# ---------------------------------------------------------------- the JavaScript scanner
# One pass over the code with a stack for template literals: strings, template text (with its ${} holes), regex literals, comments.
# Enough to know what is code, what is text and what is a comment; not a parser.
REGEX_AFTER_WORDS = {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case", "do", "else", "yield", "await"}
REGEX_AFTER_PUNCT = set("(,=:[!&|?{};+-*%<>~^")


class Tok:
    __slots__ = ("kind", "a", "b", "holes")

    def __init__(self, kind, a, b, holes=None):
        self.kind, self.a, self.b, self.holes = kind, a, b, holes or []

    def __repr__(self):
        return f"Tok({self.kind},{self.a},{self.b})"


def scan_js(s, a=0, b=None):
    """tokens of the code s[a:b]: 'str' (quotes included), 'tpl' (backticks included, holes = the ${} spans), 'regex', 'line', 'block'"""
    b = len(s) if b is None else b
    out, stack, i, last = [], [], a, None   # stack: ["tpl", start, holes] or ["expr", depth, hole_start]
    while i < b:
        if stack and stack[-1][0] == "tpl":
            fr = stack[-1]
            while i < b:
                c = s[i]
                if c == "\\": i += 2; continue
                if c == "`":
                    stack.pop(); out.append(Tok("tpl", fr[1], i + 1, fr[2])); i += 1; last = ")"; break
                if c == "$" and i + 1 < b and s[i + 1] == "{":
                    stack.append(["expr", 0, i]); i += 2; last = "{"; break
                i += 1
            else:
                out.append(Tok("tpl", fr[1], b, fr[2])); stack.pop()
            continue
        c = s[i]
        if c in " \t\r\n":
            i += 1; continue
        if c in "\"'":
            j = i + 1
            while j < b and s[j] != c and s[j] != "\n":
                j += 2 if s[j] == "\\" else 1
            out.append(Tok("str", i, min(j + 1, b))); i = j + 1; last = ")"; continue
        if c == "`":
            stack.append(["tpl", i, []]); i += 1; continue
        if c == "/" and i + 1 < b and s[i + 1] == "/":
            j = s.find("\n", i); j = b if j < 0 or j > b else j
            out.append(Tok("line", i, j)); i = j; continue
        if c == "/" and i + 1 < b and s[i + 1] == "*":
            j = s.find("*/", i + 2); j = b if j < 0 else j + 2
            out.append(Tok("block", i, j)); i = j; continue
        if c == "/" and (last is None or last in REGEX_AFTER_PUNCT or last in REGEX_AFTER_WORDS or last == "}"):
            j, cls = i + 1, False
            while j < b and s[j] != "\n":
                if s[j] == "\\": j += 2; continue
                if s[j] == "[": cls = True
                elif s[j] == "]": cls = False
                elif s[j] == "/" and not cls: break
                j += 1
            if j < b and s[j] == "/":
                j += 1
                while j < b and (s[j].isalpha()): j += 1
                out.append(Tok("regex", i, j)); i = j; last = ")"; continue
            i += 1; last = "/"; continue
        if c == "{":
            if stack and stack[-1][0] == "expr": stack[-1][1] += 1
            last = "{"; i += 1; continue
        if c == "}":
            if stack and stack[-1][0] == "expr":
                if stack[-1][1] == 0:
                    fr = stack.pop(); stack[-1][2].append((fr[2], i + 1)); i += 1; continue
                stack[-1][1] -= 1
            last = "}"; i += 1; continue
        if c.isalnum() or c in "_$":
            j = i
            while j < b and (s[j].isalnum() or s[j] in "_$."): j += 1
            w = s[i:j]; last = w if w in REGEX_AFTER_WORDS else ")"; i = j; continue
        last = c; i += 1
    return out


def masked(s, toks, kinds=("line", "block")):
    """s with the given token kinds blanked (newlines kept, so offsets and lines stay)"""
    parts, p = [], 0
    for t in toks:
        if t.kind in kinds:
            parts.append(s[p:t.a]); parts.append(re.sub(r"[^\n]", " ", s[t.a:t.b])); p = t.b
    parts.append(s[p:]); return "".join(parts)


def tpl_text(s, t):
    """a template literal's text with its ${} holes blanked to spaces (same length)"""
    txt = list(s[t.a:t.b])
    for h0, h1 in t.holes:
        for k in range(h0 - t.a, h1 - t.a):
            if txt[k] != "\n": txt[k] = " "
    return "".join(txt)


# ---------------------------------------------------------------- a file split into its languages
class Source:
    """one file: its text, line starts, and its parts: ('js', a, b, module?), ('css', a, b), ('html', a, b)"""

    def __init__(self, path, rel):
        self.path, self.rel = path, rel
        self.text = path.read_text(encoding="utf-8", errors="replace")
        self.nl = [0] + [m.end() for m in re.finditer("\n", self.text)]
        self.lines = self.text.split("\n")
        self.parts, ext = [], path.suffix.lower()
        if ext in (".js", ".mjs"):
            self.parts.append(("js", 0, len(self.text), ext == ".mjs" or bool(re.search(r"^\s*(import|export)\s[^(]", self.text, re.M))))
        elif ext == ".css":
            self.parts.append(("css", 0, len(self.text), False))
        else:
            self._html()
        self.js_toks = {}

    def _html(self):
        s, p = self.text, 0
        for m in re.finditer(r"<(script|style)\b([^>]*)>", s, re.I):
            if m.start() < p: continue
            end = s.lower().find(f"</{m.group(1).lower()}", m.end()); end = len(s) if end < 0 else end
            self.parts.append(("html", p, m.start(), False))
            attrs = m.group(2).lower()
            if m.group(1).lower() == "style":
                self.parts.append(("css", m.end(), end, False))
            elif "src=" not in attrs and not re.search(r"type\s*=\s*[\"']?(application/(ld\+)?json|importmap|text/(template|plain|x-))", attrs):
                self.parts.append(("js", m.end(), end, "module" in attrs))
            p = end
        self.parts.append(("html", p, len(s), False))

    def line(self, off):
        lo, hi = 0, len(self.nl) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.nl[mid] <= off: lo = mid
            else: hi = mid - 1
        return lo + 1

    def toks(self, a, b):
        if (a, b) not in self.js_toks: self.js_toks[(a, b)] = scan_js(self.text, a, b)
        return self.js_toks[(a, b)]

    def allowed(self, line, rule):
        for ln in (line, line - 1):
            if 1 <= ln <= len(self.lines):
                m = ALLOW.search(self.lines[ln - 1])
                if m and rule in [x.strip() for x in m.group(1).split(",")]: return True
        if not hasattr(self, "_blocks"):   # hy-allow-begin: <rule> <reason> ... hy-allow-end: a whole drawing let through at once
            self._blocks, open_ = [], None
            for i, l in enumerate(self.lines, 1):
                m = ALLOW_BEGIN.search(l)
                if m: open_ = (i, [x.strip() for x in m.group(1).split(",")])
                elif open_ and "hy-allow-end" in l: self._blocks.append((open_[0], i, open_[1])); open_ = None
        return any(a <= line <= b and rule in rs for a, b, rs in self._blocks)

    def css_texts(self):
        """(offset, text) of every piece of CSS: css files, <style>, and JS strings/templates that hold CSS rules"""
        for kind, a, b, _ in self.parts:
            if kind == "css":
                txt = self.text[a:b]
                yield a, re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), txt, flags=re.S)
            elif kind == "js":
                for t in self.toks(a, b):
                    if t.kind in ("str", "tpl"):
                        txt = (tpl_text(self.text, t) if t.kind == "tpl" else self.text[t.a:t.b])[1:-1]
                        if re.search(r"[\w\])*>-]\s*\{[^{}]*:[^{}]*\}", txt):
                            yield t.a + 1, re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), txt, flags=re.S)
            elif kind == "html":
                for m in re.finditer(r"\sstyle\s*=\s*(\"[^\"]*\"|'[^']*')", self.text[a:b]):
                    yield a + m.start(1), "x{" + m.group(1)[1:-1] + "}"   # an inline style: a rule of its own (the "x{" is 2 chars before)

    def decl_text(self):
        """the whole file with comments blanked (JS and CSS comments, HTML comments), for declaration-level checks"""
        if not hasattr(self, "_decl"):
            chars = list(self.text)
            def blank(a, b):
                for k in range(a, b):
                    if chars[k] != "\n": chars[k] = " "
            for kind, a, b, _ in self.parts:
                if kind == "js":
                    for t in self.toks(a, b):
                        if t.kind in ("line", "block"): blank(t.a, t.b)
                elif kind == "css":
                    for m in re.finditer(r"/\*.*?\*/", self.text[a:b], re.S): blank(a + m.start(), a + m.end())
                else:
                    for m in re.finditer(r"<!--.*?-->", self.text[a:b], re.S): blank(a + m.start(), a + m.end())
            self._decl = "".join(chars)
        return self._decl


def css_rules(txt):
    """(selector, body, body offset) of each innermost rule of a CSS text"""
    for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", txt):
        sel = m.group(1).strip()
        sel = re.split(r"[;`]", sel)[-1].strip()   # CSS in a JS string: the selector starts after the code before it
        yield sel, m.group(2), m.start(2)


# ---------------------------------------------------------------- the checks
class Report:
    def __init__(self):
        self.items = []

    def add(self, src, off_or_line, rule, msg, by_line=False):
        line = off_or_line if by_line else src.line(off_or_line)
        if src.allowed(line, rule): return
        text = src.lines[line - 1].strip() if 0 < line <= len(src.lines) else ""
        self.items.append({"file": src.rel, "line": line, "rule": rule, "msg": msg, "text": text})


def node_check(jobs, report):
    """node --check of every JS part, in parallel; a part of an HTML file keeps its lines (padded with empty lines)"""
    node = shutil.which("node")
    if not node:
        print("validate: no node on PATH, js-syntax skipped", file=sys.stderr); return
    tmp = Path(tempfile.mkdtemp(prefix="hyval-"))
    def one(job):
        src, a, b, module, n = job
        if a == 0 and b == len(src.text) and src.path.suffix in (".js", ".mjs") and not (module and src.path.suffix == ".js"):
            f = src.path
        else:
            ln = src.line(a); col = a - src.nl[ln - 1]
            f = tmp / f"p{n}{'.mjs' if module else '.cjs'}"
            f.write_text("\n" * (ln - 1) + " " * col + src.text[a:b], encoding="utf-8")
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        if r.returncode:
            m = re.search(r":(\d+)\s*$", r.stderr.splitlines()[0] if r.stderr else "")
            msg = next((l for l in r.stderr.splitlines() if re.match(r"\w*Error", l)), "syntax error")
            return src, int(m.group(1)) if m else src.line(a), msg
        return None
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for res in ex.map(one, jobs):
            if res: report.add(res[0], res[1], "js-syntax", res[2], by_line=True)
    shutil.rmtree(tmp, ignore_errors=True)


# code in a trailing comment: a call statement ending in «;» then more, an arrow, a ${, a declaration, an if/for with its block, closers
CODEISH = re.compile(r"[\w$]\([^()]*\)\s*;\s*(?:[\w$]+\s*[(.=]|$)|=>\s*[{(]|\$\{|\b(?:const|let|var)\s+[\w$]+\s*=[^=]|\b(?:if|for|while)\s*\([^)]*\)\s*\{|^\s*[)}\]]+\s*[;,)]|[}\]]\s*\)\s*;\s*$")
GLSL = re.compile(r"\b(uniform|varying|precision\s+\w+p\s+float|void\s+main|gl_\w+|#version)\b")


def check_js(src, report, C):
    lang_file = bool(re.match(r"lang(-[\w-]+)?\.js$", src.path.name))
    for kind, a, b, module in src.parts:
        if kind != "js": continue
        toks = src.toks(a, b)
        for t in toks:
            if t.kind == "line":
                ls = src.text.rfind("\n", 0, t.a) + 1
                before = src.text[ls:t.a]
                body = src.text[t.a + 2:t.b]
                if before.strip() and CODEISH.search(body) and "hy-allow" not in body:
                    report.add(src, t.a, "comment-swallow", "a `//` comment after code holds code: what follows it on this line never runs")
            elif t.kind in ("str", "tpl"):
                txt = tpl_text(src.text, t) if t.kind == "tpl" else src.text[t.a:t.b]
                if t.kind == "tpl" or len(txt) > 20:
                    looks_css = re.search(r"\{[^{}]*:[^{}]*;", txt)
                    looks_html = re.search(r"<[a-z][\w-]*[\s>]", txt)
                    if (looks_css or looks_html) and not GLSL.search(txt):
                        for m in re.finditer(r"(^|[\s;{}>])//(?=[\s\w«])", txt):
                            if re.search(r"(url\(|https?:|[\w-]:)\s*$", txt[max(0, m.start() - 12):m.start() + 1]): continue
                            report.add(src, t.a + m.start() + len(m.group(1)), "comment-swallow",
                                       "a `//` in CSS or HTML text of a template: CSS has no line comments, what follows is lost")
                if not lang_file:
                    bare = re.sub(r"/\*.*?\*/|<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), txt, flags=re.S)   # comments of CSS or HTML inside the text
                    check_text_ru(src, report, t.a, bare, is_code=True)
                else:
                    check_lang_string(src, report, t, txt, toks)
        if lang_file: continue
    if not lang_file:
        for kind, a, b, _ in src.parts:
            if kind == "html":
                body = re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src.text[a:b], flags=re.S)
                for m in re.finditer(r">([^<>]*[А-Яа-яЁё][^<>]*)<|=\s*\"([^\"]*[А-Яа-яЁё][^\"]*)\"", body):
                    txt = m.group(1) if m.group(1) is not None else m.group(2)
                    check_text_ru(src, report, a + m.start(), txt, is_code=False)


def check_text_ru(src, report, off, txt, is_code):
    if not CYR.search(txt): return
    if is_code and len(txt.strip().strip("\"'`")) <= 2: return   # a letter of the Russian keyboard («я» for z), not a word
    k = CYR.search(txt).start()
    report.add(src, off + k, "cyrillic-code", f"Russian text outside the lang files: «{' '.join(txt[max(0, k - 10):k + 40].split())}»; write the English key and the Russian in lang-*.js")
    ru_style(src, report, off, txt)


def ru_style(src, report, off, txt):
    if "—" in txt: report.add(src, off + txt.index("—"), "ru-style", "an em dash in Russian UI text: a comma, a colon or two sentences instead")
    if re.search("[ёЁ]", txt): report.add(src, off + re.search("[ёЁ]", txt).start(), "ru-style", "ё in Russian UI text: е")


ABBR = re.compile(r"(?:\b(?:кам|предм|стр|мин|сек|тыс|млн|шт|мм|см|ч|г|т\.е|т\.д|т\.п|etc|e\.g|i\.e|vs|p|pp|No|ок|св|эл|экз|изд|обл|ул|д|прим|англ|рус|руб|коп|св-в|см\.)\.)$")


def check_lang_string(src, report, t, txt, toks):
    """a key or a value of a lang dictionary: Russian style, and no period at the end of a short string"""
    s = txt[1:-1]
    if CYR.search(s): ru_style(src, report, t.a + 1, s)
    st = s.strip()
    if len(st) < 2 or len(st) > 48 or not st.endswith(".") or st.endswith(("..", "…")) or st.startswith(".") or re.search(r"[⌘⌥⇧⌃]\.$", st): return
    if re.search(r"[.!?]\s+\S", st[:-1]) or ABBR.search(st): return
    if not re.search(r"[A-Za-zА-Яа-яЁё]", st): return
    report.add(src, t.a, "lang-period", f"a short UI string ends with a period: «{st[:50]}»")


DECL_EASE = re.compile(r"(?<![\w-])(transition(?:-timing-function)?|animation(?:-timing-function)?)\s*:\s*([^;{}\"'`]+)|"
                       r"\b(?:style\.transition|style\.animation|easing)\s*[=:]\s*[\"'`]([^\"'`]+)[\"'`]")
TIMING = re.compile(r"cubic-bezier\([^)]*\)|steps\([^)]*\)|\b(?:ease-in-out|ease-in|ease-out|ease|linear)\b")


def norm_bezier(v):
    v = re.sub(r"\s+", "", v)
    return re.sub(r"(?<=[(,])0\.", ".", v)


def check_decls(src, report, C):
    d = src.decl_text()
    ease_ok = {norm_bezier(k) for k in C["easing"]["curves"]} | set(C["easing"]["keywords"])
    for m in DECL_EASE.finditer(d):
        val = m.group(2) if m.group(2) is not None else m.group(3)
        if m.group(1) and m.group(1).startswith("animation") and "timing" not in m.group(1) and "var(" in val: pass
        for t in TIMING.finditer(val):
            v = norm_bezier(t.group(0)) if t.group(0).startswith("cubic") else t.group(0)
            if v not in ease_ok and not (v in C["easing"].get("loops", []) and re.search(r"\binfinite\b", val)):
                report.add(src, m.start() + (m.start(2) - m.start() if m.group(2) is not None else 0) + t.start(), "easing",
                           f"{t.group(0)} is not a contract easing ({', '.join(C['easing']['curves'])}, {', '.join(C['easing']['keywords'])})")
    # an easing that is a keyframe's own (animation-timing-function inside @keyframes) is caught above too: the contract lists them
    sw_ok = {float(x) for x in C["icons"]["stroke_widths"]}
    for m in re.finditer(r"stroke-width\s*(?:=\s*[\"']?|:\s*)([\d.]+)", d):
        try: v = float(m.group(1))
        except ValueError: continue
        if m.group(0).lstrip().startswith("stroke-width=") or "=" in m.group(0):   # an attribute: an icon only inside an <svg> on the 24 grid
            ctx = d[max(0, m.start() - 600):m.start()]
            k = ctx.rfind("<svg")
            if k < 0 or "</svg>" in ctx[k:]: continue   # a drawing made of parts (annotations), not an icon
            vb = re.search(r"viewBox\s*=\s*[\"']([^\"']+)", ctx[k:])
            if vb and vb.group(1).split()[2:] != ["24", "24"]: continue   # another grid: a picture, not the icon family
        if v not in sw_ok:
            report.add(src, m.start(), "icon-stroke", f"stroke-width {m.group(1)} is not an icon line of the contract ({', '.join(C['icons']['stroke_widths'])})")
    layers = C["z_layers"]
    def zbad(v):
        return not any(L["min"] <= v <= L["max"] for L in layers)
    for m in re.finditer(r"z-index\s*:\s*(-?\d+)|zIndex\s*=\s*[\"'`]?(-?\d+)", d):
        v = int(m.group(1) or m.group(2))
        if zbad(v):
            report.add(src, m.start(), "z-layer", f"z-index {v} is in no layer of the contract ({', '.join(f'{L['name']} {L['min']}–{L['max']}' for L in layers)})")
    fams = {f.lower() for f in C["fonts"]["families"]}
    for m in re.finditer(r"(?:font-family|--sans|--mono)\s*:\s*([^;{}`]+)", d):
        for f in re.sub(r"var\([^()]*(?:\([^()]*\))?[^()]*\)", "", m.group(1)).split(","):
            f = f.strip().strip("\"'").replace("!important", "").strip()
            if not f or f.startswith("var(") or f.lower() in fams: continue
            report.add(src, m.start(), "font-family", f"the font «{f}» is not the app's ({', '.join(C['fonts']['families'][:2])} and system fallbacks)")
    # <input type=range> outside the slider
    for m in re.finditer(r"<input\b[^>]*\btype\s*=\s*[\"']?range\b", d, re.I):
        back = d[max(0, m.start() - 300):m.start()]
        k = back.rfind("hy-slider")
        if k < 0 or re.search(r"</(div|span|label)>", back[k:]):
            report.add(src, m.start(), "range-input", "an <input type=range> not inside .hy-slider: use ui/slider.js (hySlider.create / mount)")
    if src.path.name != "slider.js" and "hy-slider" not in d:
        for m in re.finditer(r"\.type\s*=\s*[\"']range[\"']|setAttribute\(\s*[\"']type[\"']\s*,\s*[\"']range", d):
            report.add(src, m.start(), "range-input", "a range input made in code: use hySlider.create()")


ROW_SEL = re.compile(r"(?<![\w-])(select|textarea|input(?!\[type=?[\"']?(?:color|checkbox|radio|range|file)))(?![\w-])|\.hy-slider(?![\w-])|\.opts\s+button|\.fchip\b|\.tfchip\b|\.hy-search\b")


PILL_R = re.compile(r"^(?:\d{3,}px|50%|var\(--hy-row-r[^)]*\)|var\(--hy-pill[^)]*\))$")
PAD_DECL = re.compile(r"(?<![\w-])(padding(?:-left|-right|-inline(?:-start|-end)?)?)\s*:\s*([^;]+)")
BUTTONISH = re.compile(r"btn|button|sel\b|-sel|pill|chip|cap(?!tion)|tag\b")


def side_pads(prop, v):
    """the left and right padding in px a declaration sets (None where it does not say or says it in another unit)"""
    v = v.replace("!important", "").strip()
    parts = re.split(r"\s+(?![^()]*\))", v)
    px = lambda x: float(x[:-2]) if re.fullmatch(r"-?[\d.]+px", x) else 0.0 if x == "0" else None
    if prop == "padding": parts = (parts * 4)[:4] if len(parts) == 1 else parts; return (px(parts[3 if len(parts) == 4 else 1]), px(parts[1]))
    if prop == "padding-inline": return (px(parts[0]), px(parts[-1]))
    return (px(parts[0]), None) if prop in ("padding-left", "padding-inline-start") else (None, px(parts[0]))


def check_capsule(src, report, C, off, txt):
    I = C["runtime"].get("inset", {}); cap, chip, small = I.get("capsule", 8), I.get("chip", 6), I.get("small_h", 22)
    rules = list(css_rules(txt))
    # a class's own padding: what a heavier reset of its panel in the same stylesheet would take away (.hcg button against .hcg-pbtn)
    padded = [sel.strip() for sel, body, _ in rules if re.fullmatch(r"\.[\w-]+", sel.strip())
              and any((side_pads(m.group(1), m.group(2))[0] or 0) > 0 for m in PAD_DECL.finditer(body))]
    for sel, body, boff in rules:
        if not sel or sel.startswith("@") or "::" in sel or ":where(" in sel: continue
        last = [re.split(r"\s*[\s>+~]\s*(?![^()]*\))", x.strip())[-1] for x in re.split(r",(?![^()]*\))", sel)]
        # (b) the reset: «.panel button { padding: 0 }» outweighs «.panel-btn { padding: 0 10px }» (one class against a class and a type)
        whole = re.fullmatch(r"\s*\.([\w-]+)\s+(button|input|select)\s*", sel)
        mine = [q for q in padded if whole and q.startswith("." + whole.group(1) + "-")]
        if mine:
            padded_here = mine
            for m in PAD_DECL.finditer(body):
                l, r = side_pads(m.group(1), m.group(2))
                if l == 0 or r == 0:
                    report.add(src, off + boff + m.start(), "capsule-pad", f"«{sel.strip()}» sets padding 0 and outweighs {', '.join(padded_here[:3])}: wrap the reset in :where()")
                    break
        # (a) a pill whose words sit closer than the contract to its round ends; an icon button (a set width or a square) is not one
        rad = next((m.group(1).replace("!important", "").strip() for m in re.finditer(r"(?<![\w-])border-radius\s*:\s*([^;]+)", body)), None)
        if not rad or not PILL_R.match(rad) or re.search(r"(?<![\w-])(width|inline-size|aspect-ratio)\s*:", body) or any(x.endswith((".st", "svg", "i", "img")) for x in last): continue
        hm = re.search(r"(?<![\w-])height\s*:\s*([\d.]+)px", body)
        if not hm or not any(re.search(r"(?<![\w-])(button|select|label)$|" + BUTTONISH.pattern, x) for x in last): continue   # a pill control by its height; a plate of buttons is measured by its buttons
        need = I.get("option", 5) if re.search(r"seg[\w-]*\s*>?\s*button\b", sel) else chip if float(hm.group(1)) < small else cap   # an option of a choice fills its share of the row
        for m in PAD_DECL.finditer(body):
            l, r = side_pads(m.group(1), m.group(2))
            low = [v for v in (l, r) if v is not None and v < need]
            if low:
                report.add(src, off + boff + m.start(), "capsule-pad", f"a pill ({sel[-40:]}, radius {rad}) with {min(low):g}px at its side: at least {need}px (var(--hy-cap-pad))")
                break


def check_css(src, report, C):
    for off, txt in src.css_texts(): check_capsule(src, report, C, off, txt)
    ROW.check(src, report, C, css_rules)
    PRIM.check(src, report, C, css_rules)
    pro = re.compile(r":root\[data-(shape|ui)")
    for off, txt in src.css_texts():
        for sel, body, boff in css_rules(txt):
            if not sel or sel.startswith("@"): continue
            lowered = sel.lower()
            if ":focus" in lowered and ":focus-within" not in lowered:
                for m in re.finditer(r"(?<![\w-])(outline(?:-width|-style|-color)?|box-shadow)\s*:\s*([^;]+)", body):
                    v = m.group(2).replace("!important", "").strip().lower()
                    if v in ("none", "0", "0px", "transparent", "inherit", "unset", "initial") or v.startswith("none") or (m.group(1) == "box-shadow" and "var(--hy-trow-ring)" in v):
                        continue
                    field = re.search(r"\b(input|textarea|select)\b|\.gta\b|search", lowered)
                    if m.group(1) == "box-shadow" and "inset" in v and "0 0 0 1px" in v.replace("  ", " ") and ("var(--line" in v or field):   # a field's border colour while typing (look.css), not a ring
                        continue
                    report.add(src, off + boff + m.start(), "focus-ring", f"a focus ring: {m.group(1)}: {v[:40]} on {sel[:60]}")
            subjects = [re.split(r"\s*[\s>+~]\s*(?![^()]*\))", x.strip())[-1] for x in re.split(r",(?![^()]*\))", lowered)]
            if any(ROW_SEL.search(x) and "::" not in x for x in subjects) and not pro.search(lowered):
                for m in re.finditer(r"(?<![\w-])border-radius\s*:\s*([^;]+)", body):
                    v = m.group(1).replace("!important", "").strip()
                    if "var(" in v or v in ("inherit", "0", "50%"): continue
                    report.add(src, off + boff + m.start(), "row-radius", f"border-radius {v} on a row control ({sel[-50:]}): var(--hy-row-r)")
            if src.path.suffix == ".css" or True:
                pass
        # `//` in a CSS text (a stylesheet or a <style>): no line comments in CSS
        if src.path.suffix == ".css" or any(k == "css" and a <= off < b for k, a, b, _ in src.parts):
            for m in re.finditer(r"(^|[\s;{}])//(?=[\s\w«])", txt):
                if re.search(r"(url\(|https?:|[\w-]:)\s*$", txt[max(0, m.start() - 12):m.start() + 1]): continue
                report.add(src, off + m.start() + len(m.group(1)), "comment-swallow", "a `//` in CSS: CSS has no line comments, the next rule is lost")


# ---------------------------------------------------------------- panel prose
# A paragraph of explanation in a panel, a popover, an empty state or a setting (owner 2026-10-06, about the 3D studio's Scene panel in white
# body text: «Вот эти комментарии никто не читает ... микро шрифтом, как Apple обычно делает ... Если текст не ключевой, то зачем он вообще
# нужен»). The text an element opens with is read where the code writes it: static markup, a template's text with its T("…") / t("…") holes
# read as their English keys (a frame editor's T.name from its own table), el("div", "cls", T("…")) and div("cls", T.name) calls. More than
# max_words in body text fails; a footnote (a hint class, ui/hy/hint.css .hy-hint) may hold hint_max_words, about two short lines.
PROSE_OPEN = re.compile(r"<(p|div|span|li|small|label|dd|td)\b([^<>]*)>", re.I)
PROSE_INLINE = re.compile(r"</?(?:b|strong|i|em|kbd|a|br|code|u|s|sup|sub|mark)\b[^<>]*>", re.I)
PROSE_CALL = re.compile(r"(?:\b(?:T|t|L|trF)\(\s*([\"'`])((?:(?!\1)[^\\]|\\.)*)\1)|(?:\bT\.(\w+)\b)")
PROSE_HOLE = re.compile(r"^\$\{\s*(?:(?:esc\w*|String)\(\s*)?(?:(?:T|t|L|trF)\(\s*([\"'`])((?:(?!\1)[^\\]|\\.)*)\1[^`]*|T\.(\w+)\s*)\)?\s*\}$", re.S)


def prose_words(txt):
    txt = re.sub(r"<[^>]*>", " ", txt); txt = re.sub(r"\{\w+\}", "x", txt); txt = re.sub(r"&\w+;", " ", txt)
    return len([w for w in txt.split() if re.search(r"[0-9A-Za-zА-Яа-яЁё]", w)])


def prose_table(src):
    """a frame editor's word table (const T = { name: 'text', ... }): T.name -> its text"""
    m = re.search(r"\bconst T = \{", src.text)
    if not m: return {}
    end = src.text.find("\n};", m.end()); body = src.text[m.end():end if end > 0 else len(src.text)]
    return {k: v.replace("\\'", "'") for k, v in re.findall(r"\b(\w+):\s*'((?:[^'\\\n]|\\.)*)'", body)}


def prose_run(s, i):
    """the text from i to the first tag that is not inline: what an element opens with"""
    out, j = [], i
    while j < len(s) and j - i < 4000:
        k = s.find("<", j)
        if k < 0: out.append(s[j:]); break
        out.append(s[j:k]); m = PROSE_INLINE.match(s, k)
        if not m: break
        j = m.end()
        if m.group(0)[:4].lower() == "<kbd":   # a key cap is not a word
            e = s.lower().find("</kbd>", j); j = e + 6 if e >= 0 else j
    return "".join(out)


def check_prose(src, report, C):
    P = (C.get("runtime") or {}).get("prose")
    if not P or re.match(r"lang(-[\w-]+)?\.js$", src.path.name): return
    hint = set(P["hint_classes"]) | set(P.get("hint_classes_by_file", {}).get(src.rel, []))
    table = prose_table(src)
    def judge(off, cls, text):
        n = prose_words(text)
        if n <= P["max_words"] or set(P.get("skip_classes", [])) & set(cls.split()): return
        quote = " ".join(re.sub(r"<[^>]*>", "", text).split())[:70]
        if hint & set(cls.split()):
            if n > P["hint_max_words"]:
                report.add(src, off, "panel-prose", f"a footnote of {n} words is more than two short lines: «{quote}…»; shorten it to the key words, or move it behind a ⓘ (.hy-info)")
            return
        report.add(src, off, "panel-prose", f"a paragraph of {n} words in body text: «{quote}…»; not key: delete it; key: one footnote line (.hy-hint, key words in <b>); unclear: a ⓘ (.hy-info) with the text in its tooltip")
    def scan(text, base, lines_of=None):
        for m in PROSE_OPEN.finditer(text):
            cm = re.search(r"\bclass\s*=\s*[\"']([^\"']*)", m.group(2))
            body = prose_run(text, m.end())
            if body.strip(): judge(base + m.start() if lines_of is None else lines_of(m.start()), cm.group(1) if cm else "", body)
    for kind, a, b, _ in src.parts:
        if kind == "html":
            scan(re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src.text[a:b], flags=re.S), a)
        elif kind == "js":
            toks = src.toks(a, b)
            for t in toks:
                if t.kind != "tpl" or "<" not in src.text[t.a:t.b] or re.match(r"`\s*<!doctype", src.text[t.a:t.b], re.I): continue   # a whole document: a file, not the interface
                parts, p = [], t.a
                for h0, h1 in t.holes:   # a hole is read as its text: T("…") its key, T.name the table's, anything else one word
                    parts.append(src.text[p:h0]); hole = src.text[h0:h1]; hm = PROSE_HOLE.match(hole)
                    txt = (hm.group(2) if hm.group(2) is not None else table.get(hm.group(3), "x")) if hm else "x"
                    parts.append(re.sub(r"<[^>]*>|[<>]", " ", txt) + "\n" * hole.count("\n")); p = h1
                parts.append(src.text[p:t.b]); res = "".join(parts)
                scan(res, 0, lines_of=lambda k, t=t, res=res: _off_of_line(src, t.a, res.count("\n", 0, k)))
            code = masked(src.text, toks)
            for m in re.finditer(r"\b(el|div)\(\s*(?:([\"'])\w*\2\s*,\s*)?([\"'])([\w -]*)\3\s*,", code[a:b]):
                if m.group(1) == "div" and m.group(2): continue
                if m.group(1) == "el" and not m.group(2): continue
                s0 = a + m.end(); depth, j = 0, s0
                while j < min(b, s0 + 600):
                    c = src.text[j]
                    if c in "([{": depth += 1
                    elif c in ")]}":
                        if depth == 0: break
                        depth -= 1
                    j += 1
                alts = [cm.group(2) if cm.group(2) is not None else table.get(cm.group(3), "") for cm in PROSE_CALL.finditer(src.text[s0:j])]
                alts = [x for x in alts if x]
                if alts: judge(a + m.start(), m.group(4), max(alts, key=prose_words))


def _off_of_line(src, start, k):
    """the offset of the k-th line after the one holding start"""
    off = start
    for _ in range(k):
        n = src.text.find("\n", off)
        if n < 0: break
        off = n + 1
    return off


# ---------------------------------------------------------------- icons and colours
# One meaning, one icon, only from ui/icons.js (owner 2026-10-07, the image studio's Adjustments tab wore the opacity's half circle: «Нужно,
# чтобы это было систематизировано ... консистентные иконки, консистентные стили, консистентные цвета»). icon-inline: a glyph's shapes
# written anywhere else; icon-registry: the registry itself (a glyph per name, a name per glyph, a meaning for each) and the names asked
# for; icon-color: a glyph drawn in a colour of its own; css-color: a colour in CSS that is not a token.
SHAPE = re.compile(r"<(?:path|circle|rect|line|polyline|polygon|ellipse)\b|%3C(?:path|circle|rect|line|polyline|polygon|ellipse)\b", re.I)
IC_ENTRY = re.compile(r"^\s+(\w+):\s*'(<[^'\n]*)',?[^\n]*$|^\s*IC\.(\w+)\s*=\s*'(<[^'\n]*)';[^\n]*$", re.M)
IC_ASK = re.compile(r"\b(?:hyIcon|hyToolIcon|hyIconPath|hyIconURL|hyMarkIcon)\(\s*([\"'])(\w+)\1|\bdata-ic\s*=\s*\\?[\"'](\w+)")
GLYPH_PAINT = re.compile(r"\b(fill|stroke|color|stop-color)\s*=\s*\"([^\"]*)\"")


def registry_of(C):
    """{name: (glyph, line, has meaning)} of ui/icons.js, with the names written twice"""
    p = REPOS_DIR / C["icons"].get("registry", "hyimg/review/ui/icons.js")
    try: s = p.read_text(encoding="utf-8")
    except OSError: return {}, [], p
    out, twice, lines = {}, [], s.split("\n")
    for m in IC_ENTRY.finditer(s):
        name, glyph = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        ln = s.count("\n", 0, m.start()) + 1
        tail = m.group(0)[m.group(0).index(glyph) + len(glyph):]
        meant = "//" in tail or (ln > 1 and lines[ln - 2].strip().startswith("//"))
        if name in out: twice.append((name, ln))
        out[name] = (glyph, ln, meant)
    return out, twice, p


def glyph_key(g):
    """a glyph's drawing: its shapes with their geometry and paint, in a stable order (the same picture written alike is one key)"""
    shapes = []
    for m in re.finditer(r"<(\w+)\b([^>]*?)/?>", g):
        a = dict(re.findall(r"([\w-]+)=\"([^\"]*)\"", m.group(2))); a.pop("class", None)
        if "d" in a: a["d"] = " ".join(a["d"].split())
        shapes.append(m.group(1) + json.dumps(a, sort_keys=True))
    return "|".join(sorted(shapes))


def check_icons(src, report, C, reg):
    """icon-inline and icon-color in a page, a plugin or a stylesheet; the names it asks the registry for"""
    I = C["icons"]
    is_reg = src.rel == I.get("registry", "hyimg/review/ui/icons.js")
    d = src.decl_text()
    if not is_reg and src.rel not in I.get("allow_files", {}):
        seen = set()
        for m in SHAPE.finditer(d):
            ln = src.line(m.start())
            if ln in seen: continue
            seen.add(ln)
            report.add(src, m.start(), "icon-inline", "an icon's shapes written here: draw it from ui/icons.js (hyIcon(name, size, line), <svg data-ic=name>, hyIconPath, the --hy-ic-* images); a drawing that is not an icon says so with hy-allow: icon-inline <what it is>")
    names = reg[0] if reg else {}
    if names:
        for m in IC_ASK.finditer(d):
            n = m.group(2) or m.group(3)
            if n not in names:
                report.add(src, m.start(), "icon-registry", f"«{n}» is not an icon of ui/icons.js: use the registry's name for this meaning, or add the glyph there with its meaning")
        # a table of older names (hy-icon-names on its opening line or the one above): every value is a registry name
        for m in re.finditer(r"hy-icon-names", src.text):
            ln = src.line(m.start()); start = src.nl[ln - 1]
            k = src.text.find("{", start)
            if k < 0 or src.line(k) > ln + 1: continue
            depth, j = 0, k
            while j < len(src.text):
                if src.text[j] == "{": depth += 1
                elif src.text[j] == "}":
                    depth -= 1
                    if depth == 0: break
                j += 1
            for v in re.finditer(r":\s*([\"'])(\w+)\1", src.text[k:j]):
                if v.group(2) not in names:
                    report.add(src, k + v.start(), "icon-registry", f"the name table points at «{v.group(2)}», which is not an icon of ui/icons.js")
    # the line an icon is drawn in: hyIcon(name, size, line) with a literal line takes the contract's (0: a filled icon)
    sw_ok = {float(x) for x in I["stroke_widths"]}
    for m in re.finditer(r"\bhyIcon\(\s*[\"']\w+[\"']\s*,\s*[\w.]+\s*,\s*([\d.]+)\b", d):
        if float(m.group(1)) and float(m.group(1)) not in sw_ok:
            report.add(src, m.start(), "icon-stroke", f"an icon drawn in a {m.group(1)} line: the contract's lines are {', '.join(I['stroke_widths'])}")
    # a placeholder or a whole svg in a colour of its own
    for m in re.finditer(r"<svg\b[^>]*\bdata-ic\b[^>]*>", d):
        for p in GLYPH_PAINT.finditer(m.group(0)):
            if p.group(2) not in ("none", "currentColor"):
                report.add(src, m.start(), "icon-color", f"{p.group(1)}=\"{p.group(2)}\" on an icon: icons are drawn in currentColor, the colour comes from the CSS color")


def check_registry(report, C, reg, checked):
    """the registry itself: one glyph per name, one name per glyph, each with its meaning, each in currentColor"""
    names, twice, p = reg
    rel_ = rel(p)
    if rel_ not in checked or not names: return
    src = Source(p, rel_)
    for n, ln in twice:
        report.add(src, ln, "icon-registry", f"«{n}» is written twice in the registry: one name, one glyph", by_line=True)
    by = defaultdict(list)
    for n, (g, ln, meant) in names.items():
        by[glyph_key(g)].append((n, ln))
        if not meant:
            report.add(src, ln, "icon-registry", f"«{n}» has no meaning: say after it (// ...) or on the line above what it means, so no other meaning borrows it", by_line=True)
        for m in GLYPH_PAINT.finditer(g):
            if m.group(2) not in ("none", "currentColor"):
                report.add(src, ln, "icon-color", f"«{n}» is drawn in {m.group(1)}=\"{m.group(2)}\": a glyph takes currentColor (only Raw Editor's «on» disc, hyGradeIcon, has colours of its own)", by_line=True)
    for k, ns in by.items():
        for n, ln in ns[1:]:
            report.add(src, ln, "icon-registry", f"«{n}» draws the same glyph as «{ns[0][0]}»: one glyph serves one meaning (use «{ns[0][0]}» if it is the same meaning, or draw another)", by_line=True)


HEXRGB = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(")


def strip_var_fallbacks(v):
    """a value without the fallbacks of its var()s (var(--line, rgba(...)) is the token; its fallback is for an older page)"""
    out, i = [], 0
    while True:
        k = v.find("var(", i)
        if k < 0: out.append(v[i:]); break
        out.append(v[i:k]); depth, j = 0, k + 3
        while j < len(v):
            if v[j] == "(": depth += 1
            elif v[j] == ")":
                depth -= 1
                if depth == 0: break
            j += 1
        inner = v[k + 4:j]; comma = inner.find(",")
        out.append("var(" + (inner[:comma] if comma >= 0 else inner) + ")"); i = j + 1
    return "".join(out)


def check_colors(src, report, C):
    """css-color: a colour in a CSS declaration that is not a token"""
    skip = set(C["colors"].get("not_colour_props", []))
    for off, txt in src.css_texts():
        for sel, body, boff in css_rules(txt):
            for m in re.finditer(r"(?<![\w-])(-{0,2}[a-zA-Z][\w-]*)\s*:\s*([^;]+)", body):
                prop = m.group(1)
                if prop.startswith("--") or prop in skip: continue
                v = strip_var_fallbacks(m.group(2))
                h = HEXRGB.search(v)
                if h:
                    report.add(src, off + boff + m.start(), "css-color", f"{prop}: {m.group(2).strip()[:48]}: a colour that is not a token, var(--ink), var(--sel) ... (a token's value is written once, --name: #...)")


# ---------------------------------------------------------------- files, baseline, report
def files_of(args):
    out = []
    targets = [Path(a).resolve() for a in args] or [REPOS_DIR / r for r in REPOS]
    for t in targets:
        if t.is_file():
            if t.suffix.lower() in EXTS: out.append(t)
            continue
        for d, ds, fs in os.walk(t):
            ds[:] = sorted(x for x in ds if x not in SKIP_DIRS and not x.startswith("."))
            out += [Path(d) / f for f in sorted(fs) if f.lower().endswith(EXTS) and not f.endswith(".min.js")]
    return sorted(set(out))


def rel(p):
    try: return str(p.relative_to(REPOS_DIR))
    except ValueError: return str(p)


def fingerprint(item):
    return hashlib.sha1(f"{item['rule']}|{item['file']}|{re.sub(r'\s+', ' ', item['text'])[:300]}".encode()).hexdigest()[:12]


def run(paths, contract=None):
    C = contract or json.loads(CONTRACT.read_text(encoding="utf-8"))
    report, jobs = Report(), []
    srcs, skip = [], set(C.get("skip_files", {}))
    reg = registry_of(C)
    for n, p in enumerate(files_of(paths)):
        if rel(p) in skip: continue
        if any(part in SKIP_DIRS for part in p.relative_to(REPOS_DIR).parts[:-1]) if str(p).startswith(str(REPOS_DIR)) else False:
            continue
        src = Source(p, rel(p)); srcs.append(src)
        for kind, a, b, module in src.parts:
            if kind == "js" and src.text[a:b].strip(): jobs.append((src, a, b, module, len(jobs)))
        check_js(src, report, C); check_decls(src, report, C); check_css(src, report, C); check_prose(src, report, C)
        check_icons(src, report, C, reg); check_colors(src, report, C)
    check_registry(report, C, reg, {s.rel for s in srcs})
    node_check(jobs, report)
    return report.items + FS.check(paths, load_baseline().get(FS.SECTION, {})), [s.rel for s in srcs]


def load_baseline():
    try: return json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, ValueError): return {}


def compare(items, files, section="static"):
    """(new items, known count per rule, fixed count per rule) against the baseline of the files that were checked"""
    base = load_baseline().get(section, {})
    files = set(files)
    known = Counter({k: v for k, v in base.get("counts", {}).items()})
    have = Counter()
    for it in items: it["fp"] = fingerprint(it); have[it["fp"]] += 1
    seen, new = Counter(), []
    for it in items:
        if it["rule"] == FS.RULE: new.append(it); continue   # held by numbers of its own (baseline "file_size"): always new
        seen[it["fp"]] += 1
        if seen[it["fp"]] > known.get(it["fp"], 0): new.append(it)
    per_rule_known, per_rule_fixed = Counter(), Counter()
    meta = base.get("where", {})
    for fp, n in known.items():
        w = meta.get(fp, {})
        if w.get("file") not in files: continue
        per_rule_known[w.get("rule", "?")] += n
        per_rule_fixed[w.get("rule", "?")] += max(0, n - have.get(fp, 0))
    return new, per_rule_known, per_rule_fixed


def write_baseline(items, section="static"):
    items = [it for it in items if it["rule"] != FS.RULE]   # file-size keeps numbers of its own (FS.update)
    data = load_baseline()
    counts, where = Counter(), {}
    for it in items:
        fp = it.get("fp") or fingerprint(it); counts[fp] += 1
        where[fp] = {"rule": it["rule"], "file": it["file"], "text": it["text"][:160]}
    data[section] = {"note": "known violations: rule, file and line text hashed (lines move, the text stays); counts may only go down",
                     "updated": time.strftime("%Y-%m-%d"), "counts": dict(sorted(counts.items())), "where": dict(sorted(where.items())),
                     "by_rule": dict(sorted(Counter(it["rule"] for it in items).items()))}
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*", help="repositories, folders or files (default: the four repositories)")
    ap.add_argument("--update-baseline", action="store_true", help="write today's violations as the known ones")
    ap.add_argument("--rule", metavar="RULES", help="with --update-baseline: only these rules (comma separated) are written, the others' known ones stay")
    ap.add_argument("--list", metavar="RULE", help="print every violation of RULE (or 'all'), known ones too")
    ap.add_argument("--rules", action="store_true", help="the rules and their reasons")
    ap.add_argument("--json", action="store_true", help="the result as JSON")
    ap.add_argument("-q", "--quiet", action="store_true", help="only new violations and the one-line result")
    a = ap.parse_args()
    if a.rules:
        for k, v in RULES.items(): print(f"{k:16} {v}")
        return 0
    t0 = time.time()
    items, files = run(a.paths)
    if a.update_baseline:
        if a.paths: print("validate: --update-baseline takes no paths (the baseline is of all four repositories)", file=sys.stderr); return 2
        only = {r.strip() for r in (getattr(a, "rule", None) or "").split(",") if r.strip()}
        if not only or FS.RULE in only: print(FS.update(BASELINE))   # file-size: numbers only go down, no file is added
        if only == {FS.RULE}: return 0
        if a.rule:   # only these rules: the other rules' known violations stay as they are
            only = {r.strip() for r in a.rule.split(",")}
            base = load_baseline().get("static", {}); where = base.get("where", {})
            keep = [{"rule": w["rule"], "file": w["file"], "text": w["text"], "fp": fp} for fp, n in base.get("counts", {}).items() for w in [where.get(fp, {})] if w.get("rule") not in only for _ in range(n)]
            items = keep + [it for it in items if it["rule"] in only]
        write_baseline(items); print(f"baseline written: {len(items)} known violations in {BASELINE}"); return 0
    new, known, fixed = compare(items, files)
    if a.list:
        for it in sorted(items, key=lambda x: (x["file"], x["line"])):
            if a.list in ("all", it["rule"]): print(f"{it['file']}:{it['line']}  {it['rule']}  {it['msg']}")
        if a.list in ("all", FS.RULE): print(FS.listing())
        return 0
    if a.json:
        print(json.dumps({"new": new, "known": known, "fixed": fixed, "files": len(files)}, ensure_ascii=False, indent=1)); return 1 if new else 0
    for it in sorted(new, key=lambda x: (x["file"], x["line"])):
        print(f"{it['file']}:{it['line']}  {it['rule']}  {it['msg']}")
    if not a.quiet:
        found = Counter(it["rule"] for it in items)
        newc = Counter(it["rule"] for it in new)
        print(f"\n{'rule':16} {'known':>6} {'fixed':>6} {'new':>5}")
        for r in RULES:
            if known[r] or newc[r] or found[r]:
                print(f"{r:16} {known[r] - fixed[r]:>6} {fixed[r]:>6} {newc[r]:>5}")
    if not a.quiet: print(FS.summary())
    print(f"validate: {len(files)} files, {len(new)} new, {sum(known.values()) - sum(fixed.values())} known left, {sum(fixed.values())} fixed, {time.time() - t0:.1f} s")
    if sum(fixed.values()) and not a.paths: print("validate: violations were fixed: run with --update-baseline to lower the ratchet")
    return 1 if new else 0


if __name__ == "__main__":
    try: sys.exit(main())
    except KeyboardInterrupt: sys.exit(2)
