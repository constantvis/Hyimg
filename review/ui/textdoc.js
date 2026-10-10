// A text on the board is a small Markdown document, as a note in Apple Notes (owner 2026-10-09: «нужно, чтобы мы могли не только title
// писать, а как в Notes Apple: когда сверху пишешь — это title, далее обычный текст. И чтобы это была Markdown-структура»).
//   it.text   the whole document, Markdown: the first line is the title (the item's size and weight, as a heading always was), the lines
//             after it are the body: half the title's size, regular, with # ## ### headings, - and 1. lists, - [ ] checklists (a click
//             ticks them), > quotes, --- rules, **bold**, *italic*, ~~struck~~, `code` and links ([text](url) or a bare https://…)
//   it.tw     the width a document wraps at, board units; set when a body first appears, dragged by the side strips, scaled by a corner
// A text with no body is a heading and is drawn exactly as before: its text as it is, one weight, auto width, no tw. Nothing is migrated.
// Writing: the title is one field (↵ done, as a heading's; ⇧↵ or ↓ goes on into the body), the body another under it where ↵ is a new
// line, as in Apple Notes, Bear and Obsidian (a list, a checklist and a quote go on, an empty item ends them); ⌘↵, Esc or a click outside
// apply. The body is written as Markdown with its marks dimmed and the bold, headings, code and links lit as you type (a mirror under a
// clear field: the field keeps the browser's own undo, IME and spelling); seen, it is drawn rendered.
// canvas.html calls: hyTextDoc.paint(el, it) in render, editText(id, before, at, event) on a double click, hyTextDoc.resize in a resize
// drag, hyTextDoc.edges for the side strips, hyTextDoc.paste for text pasted on the board. review/textdocs.py is the same model for hy.py.
(() => {
  if (window.hyTextDoc) return;
  const T = (k, v) => (window.T ? window.T(k, v) : k);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const split = text => { const s = String(text || ""), i = s.indexOf("\n"); return i < 0 ? { title: s, body: "" } : { title: s.slice(0, i), body: s.slice(i + 1) }; };
  const isDoc = it => !!it && split(it.text).body.trim() !== "";
  // a new document's width: about 14 letters of its title, at least its title's own width, at most twice the 14 (fs × 14: 560 at Regular)
  const autoW = (it, now) => Math.round(Math.min(Math.max(it.fs * 14, now || 0), it.fs * 28));

  // ---- the body, rendered: one block per source line, data-l its line in it.text (the title is line 0)
  const RE = { h: /^(#{1,3})\s+(.*)$/, hr: /^\s*([-*_])(?:\s*\1){2,}\s*$/, ck: /^(\s*)[-*+•]\s+\[([ xX])\](?:\s+(.*))?$/,
    ul: /^(\s*)[-*+•]\s+(.*)$/, ol: /^(\s*)(\d+)([.)])\s+(.*)$/, q: /^\s*>\s?(.*)$/ };
  const SAFE = /^(https?:|mailto:|hyimg:)/i;
  const TOK = /`([^`\n]+)`|\[([^\]\n]+)\]\(([^)\s]+)\)|(https?:\/\/[^\s<>()]*[^\s<>().,;:!?'"])/g;
  const marks = s => s.replace(/\*\*\*(.+?)\*\*\*/g, "<b><i>$1</i></b>").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/\*([^*\s][^*]*?)\*/g, "<i>$1</i>").replace(/~~(.+?)~~/g, "<s>$1</s>");
  function inline(src) {
    let out = "", last = 0, m; TOK.lastIndex = 0;
    while ((m = TOK.exec(src))) {
      out += marks(esc(src.slice(last, m.index))); last = TOK.lastIndex;
      if (m[1] != null) { out += `<code>${esc(m[1])}</code>`; continue; }
      const href = m[3] || m[4], label = m[2] != null ? marks(esc(m[2])) : esc(m[4]);
      out += SAFE.test(href) ? `<a href="${esc(href)}" target="_blank" rel="noopener">${label}</a>` : esc(m[0]);
    }
    return out + marks(esc(src.slice(last)));
  }
  const ind = s => Math.min(4, Math.floor(s.replace(/\t/g, "  ").length / 2));
  function bodyHtml(src, from) {
    return src.split("\n").map((l, k) => {
      const i = from + k;
      const li = (cls, sp, mk, rest) => `<div class="td-li${cls}" data-l="${i}" style="--ind:${ind(sp)}">${mk}<span class="td-lt">${inline(rest)}</span></div>`;
      let m;
      if (!l.trim()) return `<div class="td-bl" data-l="${i}"></div>`;
      if (RE.hr.test(l)) return `<hr data-l="${i}">`;
      if ((m = l.match(RE.h))) return `<div class="td-h td-h${m[1].length}" data-l="${i}">${inline(m[2])}</div>`;
      if ((m = l.match(RE.ck))) {
        const on = m[2] !== " "; return li(` td-ck${on ? " td-on" : ""}`, m[1], `<span class="td-box" role="checkbox" aria-checked="${on}"></span>`, m[3] || ""); }
      if ((m = l.match(RE.ul))) return li("", m[1], `<span class="td-bu"></span>`, m[2]);
      if ((m = l.match(RE.ol))) return li(" td-ol", m[1], `<span class="td-nu">${esc(m[2] + m[3])}</span>`, m[4]);
      if ((m = l.match(RE.q))) return `<div class="td-q" data-l="${i}">${inline(m[1]) || "&#8203;"}</div>`;
      return `<div class="td-p" data-l="${i}">${inline(l)}</div>`;
    }).join("");
  }
  // the item drawn when it is not being written: a heading as before, a document as title and body at its width
  function paint(el, it) {
    const { title, body } = split(it.text);
    if (!body.trim()) { el.classList.remove("doc"); el.style.width = ""; el.textContent = it.text; return; }
    el.classList.add("doc"); el.style.width = (it.tw || autoW(it)) + "px";
    el.innerHTML = `<div class="td-t" data-l="0">${esc(title) || "&#8203;"}</div><div class="td-b">${bodyHtml(body.replace(/\s+$/, ""), 1)}</div>`;
  }

  // ---- the body while it is written: the same text with its marks dimmed, under a clear field of the same metrics
  const HTOK = /`[^`\n]+`|\[[^\]\n]+\]\([^)\s]+\)|\*\*\*[^*\n]+?\*\*\*|\*\*[^*\n][^\n]*?\*\*|\*[^*\s][^*\n]*?\*|~~[^\n]+?~~|https?:\/\/[^\s<>()]+/g;
  const mk = s => `<span class="td-k">${esc(s)}</span>`;
  function hlIn(src) {
    let out = "", last = 0, m; HTOK.lastIndex = 0;
    while ((m = HTOK.exec(src))) {
      const t = m[0]; out += esc(src.slice(last, m.index)); last = HTOK.lastIndex;
      if (t[0] === "`") out += `<span class="td-cd">${mk("`")}${esc(t.slice(1, -1))}${mk("`")}</span>`;
      else if (t[0] === "[") { const j = t.indexOf("]("); out += `${mk("[")}<span class="td-ln">${esc(t.slice(1, j))}</span>${mk(t.slice(j))}`; }
      else if (t.startsWith("http")) out += `<span class="td-ln">${esc(t)}</span>`;
      else { const k = t.startsWith("***") ? 3 : t.startsWith("**") || t.startsWith("~~") ? 2 : 1;
        const cls = t[0] === "~" ? "td-s" : k === 1 ? "td-it" : k === 2 ? "td-bd" : "td-bd td-it";
        out += `${mk(t.slice(0, k))}<span class="${cls}">${esc(t.slice(k, -k))}</span>${mk(t.slice(-k))}`; }
    }
    return out + esc(src.slice(last));
  }
  function hl(src) {
    return src.split("\n").map(l => {
      let m;
      if ((m = l.match(/^(#{1,3}\s+)(.*)$/))) return `${mk(m[1])}<span class="td-hh">${hlIn(m[2])}</span>`;
      if (RE.hr.test(l)) return mk(l);
      if ((m = l.match(/^(\s*[-*+•]\s+)(\[[ xX]\])(.*)$/)))
        return `${mk(m[1])}<span class="td-cb">${esc(m[2])}</span><span class="${m[2] === "[ ]" ? "" : "td-dn"}">${hlIn(m[3])}</span>`;
      if ((m = l.match(/^(\s*(?:[-*+•]|\d+[.)])\s+)(.*)$/))) return mk(m[1]) + hlIn(m[2]);
      if ((m = l.match(/^(\s*>\s?)(.*)$/))) return `${mk(m[1])}<span class="td-qq">${hlIn(m[2])}</span>`;
      return hlIn(l);
    }).join("\n") + " ";   // the space keeps a last empty line as tall as the field's
  }

  // ---- keys inside the body
  const LIST = /^(\s*)(?:([-*+•])\s+(\[[ xX]\]\s?)?|(\d+)([.)])\s+|(>)\s?)/;
  function lines(ta) {   // the lines the selection touches: [start of the first, end of the last]
    const v = ta.value, a = v.lastIndexOf("\n", ta.selectionStart - 1) + 1, e = v.indexOf("\n", ta.selectionEnd), b = e < 0 ? v.length : e;
    return [a, b];
  }
  function goOn(ta) {   // ↵ in a list item, a checklist item or a quote starts the next one; on an empty one it ends them
    const v = ta.value, a = ta.selectionStart; if (a !== ta.selectionEnd) return false;
    const ls = v.lastIndexOf("\n", a - 1) + 1, line = v.slice(ls, a), m = line.match(LIST); if (!m || !m[0].trim()) return false;
    if (!line.slice(m[0].length).trim() && v.slice(a, (v.indexOf("\n", a) + 1 || v.length + 1) - 1).trim() === "") {
      ta.setSelectionRange(ls, a); typeIn(ta, ""); return true; }
    const next = m[6] ? "> " : m[4] ? `${+m[4] + 1}${m[5]} ` : `${m[2]} ${m[3] ? "[ ] " : ""}`;
    typeIn(ta, "\n" + m[1] + next); return true;
  }
  function indent(ta, out) {   // Tab / ⇧Tab: the touched lines two spaces in or out
    const [a, b] = lines(ta), src = ta.value.slice(a, b);
    const to = src.split("\n").map(l => out ? l.replace(/^( {1,2}|\t)/, "") : "  " + l).join("\n"); if (to === src) return;
    ta.setSelectionRange(a, b); typeIn(ta, to); ta.setSelectionRange(a, a + to.length);
  }
  function checklist(ta) {   // ⇧⌘L, as in Apple Notes: the touched lines become a checklist, or stop being one
    const [a, b] = lines(ta), src = ta.value.slice(a, b), L = src.split("\n"), all = L.every(l => !l.trim() || RE.ck.test(l));
    const to = L.map(l => !l.trim() ? l : all ? l.replace(/^(\s*)[-*+•]\s+\[[ xX]\]\s?/, "$1")
      : l.replace(/^(\s*)(?:[-*+•]\s+|\d+[.)]\s+)?/, "$1- [ ] ")).join("\n");
    ta.setSelectionRange(a, b); typeIn(ta, to); ta.setSelectionRange(a + to.length, a + to.length);
  }

  // ---- where a double click landed in a drawn document: the title or the body, and the place in its source
  function caretOf(el, it, e) {
    const r = e && document.caretRangeFromPoint ? document.caretRangeFromPoint(e.clientX, e.clientY) : null; if (!r) return null;
    const node = r.startContainer, host = (node.nodeType === 3 ? node.parentElement : node).closest("[data-l]"); if (!host || !el.contains(host)) return null;
    const w = document.createTreeWalker(host, NodeFilter.SHOW_TEXT); let n, off = 0;
    while ((n = w.nextNode())) { if (n === node) { off += r.startOffset; break; } off += n.length; }
    const L = it.text.split("\n"), l = +host.dataset.l, line = L[l] || "";
    if (l === 0) return { body: false, at: Math.min(off, line.length) };
    const pre = (line.match(/^\s*(?:#{1,3}\s+|>\s?|[-*+•]\s+(?:\[[ xX]\]\s?)?|\d+[.)]\s+)?/) || [""])[0].length;
    return { body: true, at: L.slice(1, l).reduce((s, x) => s + x.length + 1, 0) + Math.min(pre + off, line.length) };
  }

  // ---- the editor (a global, as canvas.html's other editors: tests and the board call editText(id))
  window.editText = function editText(id, before0, at, ev) {
    const it = board.items[id], el = document.querySelector(`.tx[data-id="${id}"]`); if (!el) return;
    const before = before0 || snap(), s0 = split(it.text), where = isDoc(it) && ev ? caretOf(el, it, ev) : null;
    const box = document.createElement("div"), ta = document.createElement("textarea"); box.className = "td-ed";
    ta.rows = 1; ta.className = "td-t"; ta.value = s0.title; ta.placeholder = T("Heading"); box.appendChild(ta);
    el.textContent = ""; el.appendChild(box); el.classList.add("editing");
    let B = null, kh = { hide() {} }, ctx = "";
    const full = () => ta.value + (B ? "\n" + B.ta.value : "");
    const fit = () => {
      const doc = !!B; el.classList.toggle("doc", doc);
      if (doc) { if (!it.tw) it.tw = autoW(it, el.offsetWidth); el.style.width = it.tw + "px"; ta.style.width = "100%"; B.m.innerHTML = hl(B.ta.value); }
      else { el.style.width = ""; ta.style.width = "0"; }
      ta.style.height = "0";
      if (!doc) ta.style.width = Math.max(ta.scrollWidth, it.fs * 4) + 4 + "px";
      ta.style.height = ta.scrollHeight + "px";
    };
    const hint = body => {   // the title's: the heading's ↵; the body's: ⌘↵ at the document's corner, bare, as on a note
      const want = body ? "body" : "title"; if (ctx === want) return; ctx = want; kh.hide();
      const done = [{ id: "done", keys: ["mod+enter"], t: "", also: ["escape"], stay: true }];
      kh = body ? hyHint("textdoc", el, { items: done, place: "inside", bare: true, field: null }) : hyHint("heading", el);   // field null: the text's ink
    };
    const openBody = (text = "") => {
      if (B) return B;
      const w = document.createElement("div"), m = document.createElement("div"), t = document.createElement("textarea");
      w.className = "td-w"; m.className = "td-m"; m.setAttribute("aria-hidden", "true"); t.className = "td-in"; t.rows = 1; t.value = text;
      w.append(m, t); box.appendChild(w); B = { w, m, ta: t }; bodyKeys(t); fit(); return B;
    };
    const closeBody = () => { if (!B) return; const w = B.w; B = null; ta.focus(); w.remove(); fit(); };
    let closed = false;
    const done = ok => {
      if (closed) return; closed = true; openEditor = null; kh.hide();
      const v = full().replace(/\s+$/, "").replace(/^(?:[ \t]*\n)+/, "");   // a document begins with its first written line: that is its title
      box.remove(); el.classList.remove("editing"); el._k = null;
      if (!ok) { if (!it.text) { delete board.items[id]; } render(); return; }
      if (!v.trim()) { delete board.items[id]; sel.delete(id); if (before0) { render(); return; } commit(before); return; }   // an empty title disappears
      it.text = v; if (!isDoc(it)) delete it.tw; else if (!it.tw) it.tw = autoW(it);
      render(); regroup([id]); commit(before);
    };
    // the title: ↵ done as a heading always was, ⇧↵ carries what is after the caret down into the body, ↓ at its end goes there
    hyTyping.keys(ta, { esc: "apply", apply: () => done(true), key: e => {   // Esc, ↵ and Tab apply (owner 2026-10-10, ui/typing.js)
      if (e.key === "Enter" || (e.key === "ArrowDown" && B && ta.selectionStart === ta.value.length)) {
        e.preventDefault(); const had = !!B, cut = e.key === "Enter" ? ta.value.slice(ta.selectionEnd) : "";
        if (cut) { ta.setSelectionRange(ta.selectionStart, ta.value.length); typeIn(ta, ""); }
        const b = openBody(); b.ta.focus(); b.ta.setSelectionRange(0, 0);
        if (e.key === "Enter" && (cut || had)) { typeIn(b.ta, cut + (had ? "\n" : "")); b.ta.setSelectionRange(0, 0); }
        fit();
      }
    } });
    ta.addEventListener("paste", e => {   // several lines pasted into the title: the first stays in it, the rest opens the body
      const t = (e.clipboardData && e.clipboardData.getData("text/plain") || "").replace(/\r\n?/g, "\n"); if (!t.includes("\n")) return;
      e.preventDefault(); const i = t.indexOf("\n"), tail = ta.value.slice(ta.selectionEnd), had = !!B;
      ta.setSelectionRange(ta.selectionStart, ta.value.length); typeIn(ta, t.slice(0, i));
      const b = openBody(), rest = t.slice(i + 1) + tail; b.ta.focus(); b.ta.setSelectionRange(0, 0); typeIn(b.ta, rest + (had ? "\n" : ""));
      b.ta.setSelectionRange(rest.length, rest.length); fit();
    });
    function bodyKeys(t) {
      hyTyping.keys(t, { esc: "apply", enter: "mod", tab: "own", apply: () => done(true), key: e => {   // Esc and ⌘↵ apply, Tab indents
        const mod = e.metaKey || e.ctrlKey, k = e.key.toLowerCase(), a = t.selectionStart, none = a === t.selectionEnd;
        if (e.key === "Enter") { if (goOn(t)) { e.preventDefault(); fit(); } return; }   // ↵ and ⇧↵: a new line, a list goes on
        if (e.key === "Tab") { e.preventDefault(); indent(t, e.shiftKey); fit(); return; }
        if (mod && e.shiftKey && (k === "l" || k === "д")) { e.preventDefault(); checklist(t); fit(); return; }
        if (mod && !e.shiftKey && (k === "b" || k === "и")) { e.preventDefault(); toggleMark(t, "**"); fit(); return; }
        if (mod && !e.shiftKey && (k === "i" || k === "ш")) { e.preventDefault(); toggleMark(t, "*"); fit(); return; }
        if (!none || a !== 0) return;
        if (e.key === "ArrowUp" || e.key === "ArrowLeft") { e.preventDefault(); ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); return; }
        if (e.key === "Backspace") {   // at the body's start: its first line joins the title, as in Apple Notes
          e.preventDefault(); const v = t.value, n = v.indexOf("\n"), first = n < 0 ? v : v.slice(0, n), at0 = ta.value.length;
          t.setSelectionRange(0, n < 0 ? v.length : n + 1); typeIn(t, "");
          ta.focus(); ta.setSelectionRange(at0, at0); if (first) { typeIn(ta, first); ta.setSelectionRange(at0, at0); }
          if (!t.value.trim()) closeBody(); else fit();
        }
      } });
      t.addEventListener("input", fit);
    }
    ta.addEventListener("input", fit);
    box.addEventListener("focusin", e => hint(!!B && e.target === B.ta));
    box.addEventListener("focusout", e => { if (!box.contains(e.relatedTarget)) done(true); });   // a click outside, another window
    box.addEventListener("pointerdown", e => {   // between the fields: the nearer one, the board does not take it as a click outside
      if (e.target.tagName === "TEXTAREA") return; e.preventDefault(); e.stopPropagation();
      const f = B && e.clientY > B.w.getBoundingClientRect().top ? B.ta : ta; f.focus(); f.setSelectionRange(f.value.length, f.value.length);
    });
    if (s0.body.trim()) openBody(s0.body.replace(/\s+$/, ""));
    fit();
    if (where && where.body && B) { B.ta.focus(); selectWordAt(B.ta, where.at); }
    else { ta.focus(); selectWordAt(ta, where ? where.at : at); }
    sel = new Set([id]); hint(!!B && document.activeElement === B.ta);
    Object.defineProperty(box, "value", { get: full });   // ⌘Z sees the whole document: a new text goes at once, an old one undoes its typing first
    openEditor = done; hyUndoNew.watch(box, !!before0, done);
  };

  // ---- a checklist ticked on the board, a link opened: a click, the board's own click (select, drag) does not happen
  let down = null;
  document.addEventListener("pointerdown", e => {
    const on = s => e.button === 0 && e.target.closest && e.target.closest(".tx:not(.editing) " + s), bx = on(".td-ck .td-box"), a = !bx && on("a[href]");
    down = a ? { a, x: e.clientX, y: e.clientY } : null;
    if (!bx) return;
    e.preventDefault(); e.stopPropagation();
    const el = bx.closest(".tx"), id = el.dataset.id, it = board.items[id], l = +bx.closest("[data-l]").dataset.l; if (!it) return;
    const L = it.text.split("\n"), m = (L[l] || "").match(RE.ck); if (!m) return;
    const before = snap(); L[l] = L[l].replace(/\[([ xX])\]/, m[2] === " " ? "[x]" : "[ ]"); it.text = L.join("\n"); commit(before);
  }, true);
  let go = 0;   // a link waits a double click's time: a double click on it opens the text for writing, not the link twice
  document.addEventListener("dblclick", e => {
    clearTimeout(go); if (e.target.closest && e.target.closest(".tx:not(.editing) .td-ck .td-box")) e.stopPropagation(); }, true);
  document.addEventListener("pointerup", e => {   // a link: a click without a drag opens it; the text is selected as by any click
    const d = down; down = null; if (!d || Math.hypot(e.clientX - d.x, e.clientY - d.y) > 4) return;
    const href = d.a.getAttribute("href"); clearTimeout(go); if (SAFE.test(href)) go = setTimeout(() => window.open(href, "_blank", "noopener"), 320);
  }, true);

  window.hyTextDoc = {
    split, isDoc, html: bodyHtml, paint,
    // a new text, its field open: at p (board units; a double click on the empty board) or in the middle of what is on screen («+» › Text
    // in the dock, owner 2026-10-10). "Обычный" size; zoomed far out, where that would be under 12 px on screen, the smallest one still
    // read and edited; zoomed in, no bigger on screen than at 100 % (ui/newsize.js)
    create(p) {
      if (!p && window.hyPrevNo && hyPrevNo()) return null;
      const r = stage.getBoundingClientRect(), at = p || toWorld(r.left + INSET + (r.width - INSET) / 2, r.top + r.height / 2), id = uid("t"), before = snap();
      let size = 1; while (size < TSIZE.length - 1 && TSIZE[size].fs * cam.z < 12) size++;
      const ts = hyTextSize.make(size, cam.z);   // its own scale kept: H1, H2 and the A's stay in it (ui/textsize.js)
      board.items[id] = { type: "text", text: "", x: at.x, y: at.y - ts.fs * .6, ...ts, w: 0, h: 0 };
      render(); editText(id, before); return id;
    },
    // a resize drag on a text: a side strip (e, w) sets a document's width; a corner scales the type, and a document's width with it
    resize(it, it0, c, k, d) {
      if ((c === "e" || c === "w") && isDoc(it)) { it.tw = Math.round(Math.max(it.fs * 4, (it0.tw || autoW(it0)) + d)); return; }
      it.fs = Math.max(8, it0.fs * k); if (it0.tw) it.tw = it0.tw * it.fs / it0.fs;
    },
    // the side strips of a selected document, under its corner squares (canvas.html box() draws those); on, when the handles show at all
    edges(h, id, r, it, on) {
      if (!on || !isDoc(it)) return;
      [["w", r.x], ["e", r.x + r.w]].forEach(([c, x]) => {
        const e = document.createElement("div"); e.className = "he"; e.dataset.resize = id; e.dataset.rc = c; e.title = T("Drag: the text's width");
        Object.assign(e.style, { left: x + "px", top: r.y + "px", width: "calc(14px / var(--z))", height: r.h + "px", transform: "translate(-50%, 0)", cursor: "ew-resize" });
        h.appendChild(e);
      });
    },
    // text pasted on the board (not a picture, not a link to the board's own things): a text at the pointer, its first line the title
    paste(txt, at) {
      const t = String(txt || "").replace(/\r\n?/g, "\n").replace(/\s+$/, "").replace(/^(?:[ \t]*\n)+/, "");
      const own = () => { try { return new URL(t).origin === location.origin; } catch { return false; } };
      if (!t.trim() || /^(hyimg:\/\/|hyimg-canvas-frames-v0:)/.test(t) || (/^https?:\/\/\S+$/.test(t) && own())) return false;
      const r = stage.getBoundingClientRect(), p = at || { x: cam.x + r.width / 2 / cam.z, y: cam.y + r.height / 2 / cam.z };
      let size = 1; while (size < TSIZE.length - 1 && TSIZE[size].fs * cam.z < 12) size++;
      const ts = hyTextSize.make(size, cam.z), fs = ts.fs, id = uid("t"), before = snap();
      board.items[id] = { type: "text", text: t, x: p.x, y: p.y, ...ts, w: 0, h: 0 };
      if (isDoc(board.items[id])) board.items[id].tw = Math.round(fs * 14);
      sel = new Set([id]); render(); regroup([id]); commit(before, T("Pasted: text")); return true;
    },
  };
})();
