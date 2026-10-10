// Actions, ⌘K, in every Studio (owner 2026-10-10 on round 18, r18-dock.html question 4, ★ yes: «⌘K Actions во всех студиях, сейчас
// только в Image Studio»). Image Studio's palette (hyimg-image-studio editor/index.html «Actions»: the menu's content in a popover from the
// dock, like Figma's Actions) as one element for the Studios that live on the board's page, 3D Studio and Dev Studio: a search field, the
// last five used, then every command under its group's head; the search matches the words, the group and the Russian synonyms. It rises
// over the dock's middle, the dock moves with the library's edge and the palette with it.
//   const P = hyPalette({ id, items, primary, anchor })
//     id         the Studio's key: its last five commands are kept under it (localStorage, a convenience; nothing breaks without it)
//     items()    the commands now: { label, group, icon (svg markup), keys: ["⌘", "Z"], fn, syn ("other words"), dis (grey, with its reason), hint }
//     primary()  ⌘↵ in the palette: the Studio's primary action (Save, Done; P4 S-28)
//     anchor()   the rectangle to stand over (the dock), else the window's middle
//   P.open() P.close() P.toggle() P.isOpen P.el          the dock's Actions button (hyDock.acts) and ⌘K call toggle
// Keys in it: ↑ ↓ choose, ↵ runs, Esc and ⌘K close, ⌘↵ the primary action; a click elsewhere closes it. Its field is a text field, so no key
// of the board or the Studio fires while it is open (ui/typing.js)
(() => {
  if (window.hyPalette) return;
  const t = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m)));
  const EASE = "cubic-bezier(.32,.72,0,1)";
  const css = `
.hy-pal { position: fixed; bottom: 70px; left: var(--palx, 50%); width: 420px; max-width: calc(100vw - 24px); height: min(60vh, 520px); z-index: 1220; display: flex; flex-direction: column;
  overflow: hidden; box-sizing: border-box; border: 1px solid var(--line); border-radius: 14px; background: color-mix(in srgb, var(--panel) 92%, transparent);
  -webkit-backdrop-filter: blur(18px) saturate(1.4); backdrop-filter: blur(18px) saturate(1.4); box-shadow: var(--hy-sh-pop, 0 16px 40px rgba(0,0,0,.45));
  opacity: 0; transform: translate(-50%, 12px) scale(.98); transform-origin: 50% 100%; pointer-events: none; transition: opacity .2s ${EASE}, transform .2s ${EASE};
  color: var(--ink); font: 13px var(--sans); }
.hy-pal.on { opacity: 1; transform: translate(-50%, 0); pointer-events: auto; }
.hy-pal .psr { display: flex; align-items: center; gap: 8px; height: 46px; padding: 0 12px 0 14px; border-bottom: 1px solid var(--line); flex: none; color: var(--muted); }
.hy-pal input { flex: 1; min-width: 0; height: 30px; background: transparent; border: 0; outline: 0; color: var(--ink); font: 500 14px var(--sans); }
.hy-pal input::placeholder { color: var(--muted); }
.hy-pal .pesc { font: 600 10px var(--sans); color: var(--muted); border: 1px solid var(--line); border-radius: 5px; padding: 2px 5px; }
.hy-pal .plist { flex: 1; min-height: 0; overflow-y: auto; padding: 4px 6px 8px; scrollbar-width: none; overscroll-behavior: contain; }
.hy-pal .plist::-webkit-scrollbar { display: none; }
.hy-pal .ph { padding: 10px 8px 4px; color: var(--muted); font: 500 11px var(--sans); letter-spacing: .06em; text-transform: uppercase; }
.hy-pal .pi { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 34px; padding: 4px 8px; border: 0; border-radius: var(--hy-row-r, 9px); background: none;
  text-align: left; color: var(--ink); font: 13px var(--sans); cursor: default; }
.hy-pal .pi > svg { color: var(--sub); flex: none; width: 16px; height: 16px; }
.hy-pal .pi.hot { background: var(--raise); }
.hy-pal .pi.dis { opacity: .4; }
.hy-pal .pl { flex: 1; min-width: 0; display: flex; flex-direction: column; line-height: 1.25; }
.hy-pal .pl > span:first-child { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hy-pal .pp, .hy-pal .mh { color: var(--muted); font-size: 11px; }
.hy-pal .mh { margin-left: 6px; font-size: 12px; }
.hy-pal .mk { margin-left: 8px; }
.hy-pal .mi0 { width: 16px; flex: none; }
.hy-pal .pnone { padding: 18px 10px; color: var(--muted); }
:root[data-shape=pro] .hy-pal { border-radius: 11px; }
@media (prefers-reduced-motion: reduce) { .hy-pal { transition: none; } }`;
  let styled = false;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const norm = s => String(s).toLowerCase().replace(/ё/g, "е").replace(/[…«»"]/g, "").trim();
  // Image Studio's scoring: a word at the label's start counts most, inside it less, in the group or the synonyms least; the letters of a
  // longer word in order still find it
  function score(c, q) {
    const label = norm(c.label), hay = [label, norm(c.syn || ""), norm(c.group || "")].join(" | ");
    let sc = 0;
    for (const w of q.split(/\s+/).filter(Boolean)) {
      const i = hay.indexOf(w);
      if (i >= 0) { sc += (label.startsWith(w) ? 60 : label.includes(" " + w) ? 50 : 40) - Math.min(20, i / 10); continue; }
      let k = 0; for (const ch of label) if (k < w.length && ch === w[k]) k++;
      if (k === w.length && w.length > 2) { sc += 12; continue; }
      return -1;
    }
    return sc - (c.dis ? 15 : 0);
  }
  window.hyPalette = function ({ id = "studio", items, primary = null, anchor = null }) {
    if (!styled) { const st = document.createElement("style"); st.id = "hy-palette-css"; st.textContent = css; document.head.appendChild(st); styled = true; }
    const el = document.createElement("div"); el.className = "hy-pal"; el.setAttribute("role", "dialog"); el.setAttribute("aria-label", t("Actions"));
    el.innerHTML = `<div class="psr">${window.hyIcon ? window.hyIcon("search", 15, 1.9) : ""}<input type="search" spellcheck="false" autocomplete="off"
      aria-label="${esc(t("Search actions"))}" placeholder="${esc(t("Search actions"))}"><span class="pesc">esc</span></div><div class="plist" role="listbox"></div>`;
    document.body.appendChild(el);
    const inp = el.querySelector("input"), list = el.querySelector(".plist"), KEY = "hy-pal-recent:" + id;
    let rows = [], idx = 0, back = null;
    const all = () => { let l = []; try { l = (items() || []).filter(c => c && c.label); } catch (e) { console.error("actions", e); } return l; };
    const keyOf = c => (c.group || "") + "›" + c.label;
    const recent = () => { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; } };
    const remember = c => { try { localStorage.setItem(KEY, JSON.stringify([keyOf(c), ...recent().filter(k => k !== keyOf(c))].slice(0, 5))); } catch { /* a convenience */ } };
    function build() {
      const q = norm(inp.value), cs = all(), out = [];
      if (q) cs.map(c => ({ c, s: score(c, q) })).filter(x => x.s >= 0).sort((a, b) => b.s - a.s).slice(0, 40).forEach(x => out.push({ cmd: x.c, path: true }));
      else {
        const rc = recent().map(k => cs.find(c => keyOf(c) === k)).filter(Boolean);
        if (rc.length) { out.push({ head: t("Recent") }); rc.forEach(c => out.push({ cmd: c, path: true })); }
        const groups = [...new Set(cs.map(c => c.group || ""))];
        for (const g of groups) { if (g) out.push({ head: g }); cs.filter(c => (c.group || "") === g).forEach(c => out.push({ cmd: c })); }
      }
      return out;
    }
    function render() {
      const all2 = build(); rows = all2.filter(r => r.cmd).map(r => r.cmd); idx = Math.max(0, Math.min(idx, rows.length - 1));
      let i = 0;
      list.innerHTML = all2.map(r => {
        if (r.head) return `<div class="ph">${esc(r.head)}</div>`;
        const c = r.cmd, k = i++;
        const keys = c.keys && c.keys.length ? `<span class="mk">${c.keys.map(x => `<kbd>${esc(x)}</kbd>`).join("")}</span>` : "";
        return `<button type="button" role="option" class="pi${k === idx ? " hot" : ""}${c.dis ? " dis" : ""}" data-k="${k}"${c.dis && typeof c.dis === "string" ? ` title="${esc(c.dis)}"` : ""}>`
          + `${c.icon || '<span class="mi0"></span>'}<span class="pl"><span>${esc(c.label)}${c.hint ? `<span class="mh">${esc(c.hint)}</span>` : ""}</span>`
          + `${r.path && c.group ? `<span class="pp">${esc(c.group)}</span>` : ""}</span>${keys}</button>`;
      }).join("") || `<div class="pnone">${esc(t("Nothing found"))}</div>`;
      const h = list.querySelector(".hot"); if (h) h.scrollIntoView({ block: "nearest" });
    }
    function place() {
      const r = anchor ? anchor() : null, w = Math.min(420, innerWidth - 24);
      el.style.setProperty("--palx", (r && r.width ? Math.max(12 + w / 2, Math.min(innerWidth - 12 - w / 2, r.left + r.width / 2)) : innerWidth / 2) + "px");
      if (r && r.top) el.style.bottom = Math.max(12, innerHeight - r.top + 10) + "px";
    }
    const P = {
      el,
      get isOpen() { return el.classList.contains("on"); },
      open() {
        if (P.isOpen) return; back = document.activeElement; inp.value = ""; idx = 0; place(); el.classList.add("on"); render();
        document.querySelectorAll(".dkacts").forEach(b => b.setAttribute("aria-pressed", "true"));
        inp.focus({ preventScroll: true });   // at once: the first letters typed land in the field, not on the tools
      },
      close() {
        if (!P.isOpen) return; el.classList.remove("on"); inp.blur();
        document.querySelectorAll(".dkacts").forEach(b => b.setAttribute("aria-pressed", "false"));
        try { if (back && back.isConnected && back !== document.body) back.focus({ preventScroll: true }); else window.focus(); } catch { /* gone */ }
        back = null;
      },
      toggle() { P.isOpen ? P.close() : P.open(); },
      destroy() { P.close(); el.remove(); },
    };
    function run(k) {
      const c = rows[k]; if (!c || c.dis) return;
      remember(c); P.close();
      try { c.fn && c.fn(); } catch (e) { console.error("action", c.label, e); }
    }
    inp.addEventListener("input", () => { idx = 0; render(); });
    inp.addEventListener("keydown", e => {
      e.stopPropagation(); const n = rows.length, mod = e.metaKey || e.ctrlKey;
      if (e.key === "ArrowDown") { e.preventDefault(); idx = Math.min(n - 1, idx + 1); render(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); idx = Math.max(0, idx - 1); render(); }
      else if (e.key === "Enter" && mod) { e.preventDefault(); P.close(); if (primary) primary(); }   // ⌘↵ the primary action, as everywhere (P4 S-28)
      else if (e.key === "Enter") { e.preventDefault(); run(idx); }
      else if (e.key === "Escape" || (mod && (e.code === "KeyK" || /^[kл]$/i.test(e.key)))) { e.preventDefault(); P.close(); }
    });
    list.addEventListener("click", e => { const b = e.target.closest(".pi"); if (b) run(+b.dataset.k); });
    list.addEventListener("pointermove", e => {
      const b = e.target.closest(".pi"); if (!b || +b.dataset.k === idx) return;
      idx = +b.dataset.k; list.querySelectorAll(".pi").forEach(x => x.classList.toggle("hot", x === b));
    });
    el.addEventListener("pointerdown", e => e.stopPropagation());
    addEventListener("pointerdown", e => { if (P.isOpen && !el.contains(e.target) && !(e.target.closest && e.target.closest(".dkacts"))) P.close(); }, true);
    addEventListener("resize", () => { if (P.isOpen) place(); });
    return P;
  };
})();
