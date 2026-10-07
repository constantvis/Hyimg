// Folders as on the board (owner 2026-10-05: «Разложить по папкам как на доске»). The library's path bar gets a ⋯ button with a menu:
// lay the files out once (a confirmation dialog with the counts and real examples from the plan), keep them laid out after every
// board change, undo the last run. While «always» is on, a small «Как на доске» plate in the path bar says so and opens the same menu.
// The server does the work (server.py layout_*, foldersync.py); this file is only the library's side. v2.html calls hyFsBar() when it
// draws the path bar and hyFsSeen(stamp) on each /api/changes answer.
(() => {
  if (window.hyFsBar) return;
  const css = `
.fbar .fsMore { margin-left: 2px; }
.fbar .fsPill { flex: none; height: 24px; margin: 0 4px 0 6px; padding: 0 10px 0 8px; border: 0; border-radius: 999px; display: inline-flex; align-items: center; gap: 6px;
  background: color-mix(in srgb, #30d158 16%, transparent); color: var(--ink); font: 500 12px var(--sans); cursor: pointer; white-space: nowrap; transition: background .2s cubic-bezier(.32,.72,0,1); }
.fbar .fsPill:hover { background: color-mix(in srgb, #30d158 26%, transparent); }
.fbar .fsPill i { width: 7px; height: 7px; border-radius: 50%; background: #30d158; box-shadow: 0 0 0 3px color-mix(in srgb, #30d158 25%, transparent); }
#fsMenu { position: fixed; z-index: 80; min-width: 260px; padding: 6px; border: 1px solid var(--line); border-radius: 14px; outline: none;
  background: color-mix(in srgb, var(--panel) 92%, transparent); backdrop-filter: blur(18px) saturate(1.4); -webkit-backdrop-filter: blur(18px) saturate(1.4);
  box-shadow: 0 12px 40px rgba(0,0,0,.35); opacity: 0; transform: translateY(-4px) scale(.98); transform-origin: top right; visibility: hidden;
  transition: opacity .18s cubic-bezier(.32,.72,0,1), transform .24s cubic-bezier(.32,.72,0,1), visibility 0s .24s; }
#fsMenu.open { opacity: 1; transform: none; visibility: visible; transition: opacity .18s cubic-bezier(.32,.72,0,1), transform .24s cubic-bezier(.32,.72,0,1), visibility 0s; }
#fsMenu button { display: flex; align-items: center; gap: 9px; width: 100%; height: 32px; padding: 0 10px; border: 0; border-radius: 9px; background: none; color: var(--sub);
  font: 500 13px var(--sans); text-align: left; cursor: default; white-space: nowrap; outline: none; transition: background .15s ease, color .15s ease; }
#fsMenu button:hover:not(:disabled) { background: var(--raise); color: var(--ink); }
#fsMenu button:disabled { color: var(--muted); }
#fsMenu button > svg { flex: none; opacity: .75; }
#fsMenu .ml { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
#fsMenu hr { border: 0; border-top: 1px solid var(--line); margin: 5px 4px; }
#fsDlg { position: fixed; inset: 0; z-index: 95; display: grid; place-items: center; padding: 16px; box-sizing: border-box; background: rgba(0,0,0,.34);
  opacity: 0; visibility: hidden; transition: opacity .28s cubic-bezier(.32,.72,0,1), visibility 0s .28s; }
#fsDlg.open { opacity: 1; visibility: visible; transition: opacity .28s cubic-bezier(.32,.72,0,1), visibility 0s; }
#fsDlg * { outline: none; }
#fsDlg { --fs-tile: color-mix(in srgb, var(--ink) 7%, transparent); }   /* the paper of either theme: --raise is the paper itself in the dark one */
#fsDlg .card { width: min(600px, 100%); max-height: calc(100vh - 32px); overflow: auto; box-sizing: border-box; padding: 22px 22px 18px; background: var(--paper, var(--panel));
  color: var(--ink); border: 1px solid var(--line); border-radius: var(--pl-r, 19px); box-shadow: var(--plate-sh, 0 14px 40px rgba(0,0,0,.5));
  font: 400 13px/1.5 var(--sans); transform: translateY(12px) scale(.97); transition: transform .4s cubic-bezier(.32,.72,0,1); }
#fsDlg.open .card { transform: none; }
#fsDlg h2 { margin: 0 0 12px; font: 600 17px/1.3 var(--sans); letter-spacing: -.01em; }
#fsDlg .warn { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border-radius: 12px; color: var(--ink);
  background: color-mix(in srgb, #ff9f0a 13%, transparent); border: 1px solid color-mix(in srgb, #ff9f0a 34%, transparent); }
#fsDlg .warn svg { flex: none; margin-top: 2px; color: #ff9f0a; }
#fsDlg .nums { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 14px 0; }
#fsDlg .nums div { padding: 10px 12px; border-radius: 12px; background: var(--fs-tile); }
#fsDlg .nums b { display: block; font: 600 20px/1.2 var(--sans); font-variant-numeric: tabular-nums; }
#fsDlg .nums span { color: var(--sub); font-size: 12px; }
#fsDlg .nums .hot b { color: #ff9f0a; }
#fsDlg h3 { margin: 4px 0 8px; font: 600 12px var(--sans); color: var(--sub); letter-spacing: .04em; text-transform: uppercase; }
#fsDlg .ex { display: grid; gap: 6px; margin: 0 0 14px; padding: 0; list-style: none; }
#fsDlg .ex li { padding: 8px 10px; border-radius: 10px; background: var(--fs-tile); font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace; }
#fsDlg .ex .r { display: flex; gap: 8px; white-space: nowrap; min-width: 0; }
#fsDlg .ex .r span:first-child { flex: none; width: 44px; color: var(--muted); font-family: var(--sans); }
#fsDlg .ex .r span:last-child { overflow: hidden; text-overflow: ellipsis; }
#fsDlg .ex .was span:last-child { color: var(--sub); }
#fsDlg .note { color: var(--sub); font-size: 12px; margin: -6px 0 14px; }
#fsDlg label.tg { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 12px; background: var(--fs-tile); cursor: pointer; }
#fsDlg label.tg b { display: block; font-weight: 600; } #fsDlg label.tg small { display: block; color: var(--sub); font-size: 12px; }
#fsDlg .act { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
#fsDlg .act button { height: 34px; padding: 0 16px; border: 0; border-radius: 999px; font: 500 13px var(--sans); cursor: pointer; display: inline-flex; align-items: center; gap: 8px;
  transition: background .2s cubic-bezier(.32,.72,0,1), opacity .2s ease, filter .2s ease; }
#fsDlg .act .no { background: var(--fs-tile); color: var(--ink); } #fsDlg .act .no:hover { filter: brightness(1.12); }
#fsDlg .act .go { background: #ff453a; color: #fff; } #fsDlg .act .go:hover:not(:disabled) { filter: brightness(1.08); }
#fsDlg .act button:disabled { opacity: .5; cursor: default; }
#fsDlg .spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: fsSpin .8s linear infinite; }
#fsDlg .wait { display: flex; align-items: center; gap: 10px; color: var(--sub); padding: 22px 0; }
@keyframes fsSpin { to { transform: rotate(360deg); } }
@media (max-width: 560px) { #fsDlg .nums { grid-template-columns: repeat(2, 1fr); } }
@media (prefers-reduced-motion: reduce) { #fsDlg, #fsDlg .card, #fsMenu { transition: opacity .15s; transform: none; } }`;
  const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
  const $ = q => document.querySelector(q);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // the words in the app's language (ui/i18n.js; its Russian in ui/lang-common.js, owner 2026-10-06), numbers in its grouping
  const t = (k, v) => window.T ? window.T(k, v) : String(k).replace(/^\w+::/, "").replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m));
  const num = n => window.T ? window.T.num(n) : Number(n).toLocaleString();
  const files = n => t("{n} files", { n });
  const mid = (s, n = 70) => s.length <= n ? s : s.slice(0, Math.ceil((n - 1) * .42)) + "…" + s.slice(-(n - 1 - Math.ceil((n - 1) * .42)));
  const toast = (t, k) => (window.hyToast || console.log)(t, k);
  const FS = { auto: false, last: null, stamp: null };
  const ICON = n => (window.hyIcon ? window.hyIcon(n, 15, 1.9) : "");   // a menu item's icon (ui/icons.js), the menus' 15 px and line

  // the path bar's end: the plate while «always» is on, and the ⋯ button
  window.hyFsBar = () => (FS.auto ? `<button class="fsPill" data-fsmenu title="${esc(t("Folders on disk follow the board: every board edit arranges the files again. Click for the menu, where you can turn it off"))}"><i></i>${esc(t("Like the board"))}</button>` : "")
    + `<button class="fticon fsMore" data-fsmenu aria-label="${esc(t("Folders like the board"))}" title="${esc(t("Folders like the board"))}">${window.hyIcon ? hyIcon("more", 16) : ""}</button>`;
  const redraw = () => { if (typeof window.renderFolders === "function") window.renderFolders(); };

  async function state() {
    try { const s = await (await fetch("/api/layout/state")).json(); FS.auto = !!s.auto; FS.last = s.last; FS.error = s.error; } catch {}
    return FS;
  }
  // a run the auto mode made, or a change of the mode in another window: the library hears of it through /api/changes
  window.hyFsSeen = async stamp => {
    if (stamp === undefined || stamp === FS.stamp) return;
    const first = FS.stamp === null; FS.stamp = stamp;
    const was = FS.last && FS.last.id, auto = FS.auto;
    await state();
    if (!first && FS.last && FS.last.id !== was && FS.last.who === "auto" && FS.last.status === "done" && FS.last.moved)
      toast(t("Folders arranged like the board: {files}", { files: files(FS.last.moved) }), "info");
    if (!first && FS.last && FS.last.who === "auto" && FS.last.status === "failed" && FS.last.id !== was) toast(t("Couldn't arrange the folders: ") + (FS.last.error || ""), "error");
    if (first || auto !== FS.auto) redraw();
  };

  // ---- the menu
  let menu = null;
  function closeMenu() { if (menu) menu.classList.remove("open"); }
  async function openMenu(btn) {
    await state();
    if (!menu) { menu = document.createElement("div"); menu.id = "fsMenu"; menu.setAttribute("role", "menu"); document.body.appendChild(menu); }
    const canUndo = FS.last && FS.last.status === "done";
    const item = (act, icon, label, extra = "", tail = "") => `<button role="menuitem" data-fs="${act}"${extra}>${icon}<span class="ml">${label}</span>${tail}</button>`;
    menu.innerHTML = item("plan", ICON("toFolders"), esc(t("Arrange folders like the board…")))
      + item("auto", ICON("sync"), esc(t("Always keep folders like the board")), "", `<hy-switch static${FS.auto ? " checked" : ""}></hy-switch>`)
      + "<hr>" + item("undo", ICON("undo"), esc(t("Undo the last layout")), canUndo ? "" : " disabled");
    const r = btn.getBoundingClientRect();
    menu.classList.add("open");
    const mw = menu.offsetWidth, mh = menu.offsetHeight;
    menu.style.left = Math.max(8, Math.min(r.right - mw, innerWidth - mw - 8)) + "px";
    menu.style.top = (r.bottom + 6 + mh > innerHeight - 8 ? Math.max(8, r.top - mh - 6) : r.bottom + 6) + "px";
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-fsmenu]");
    if (b) { e.preventDefault(); e.stopPropagation(); menu && menu.classList.contains("open") ? closeMenu() : openMenu(b); return; }
    const it = e.target.closest("#fsMenu [data-fs]");
    if (it && !it.disabled) { closeMenu(); ({ plan: openDialog, auto: toggleAuto, undo: undoLast })[it.dataset.fs](); }
  }, true);
  document.addEventListener("pointerdown", e => { if (menu && !e.target.closest("#fsMenu, [data-fsmenu]")) closeMenu(); }, true);
  addEventListener("blur", closeMenu);

  async function toggleAuto() {
    const on = !FS.auto;
    try {
      const r = await fetch("/api/layout/auto", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ on }) });
      if (!r.ok) throw new Error(r.status);
      FS.auto = (await r.json()).auto; redraw();
      toast(FS.auto ? t("Folders will follow the board: after every board edit the files arrange themselves") : t("Folders no longer follow the board"), FS.auto ? "success" : "info");
    } catch (ex) { toast(t("Couldn't switch the mode: ") + ex.message, "error"); }
  }

  async function undoLast() {
    try {
      const r = await fetch("/api/layout/undo", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      const d = await r.json(); if (!r.ok) throw new Error(d.error || r.status);
      const u = d.undo || {};
      toast(t("Layout undone: {files} back in place", { files: files(u.back || 0) }) + (u.missing && u.missing.length ? t(", {n} not found", { n: u.missing.length }) : "") + (d.auto_was ? t(". “Like the board” mode is off") : ""), "success");
      await state(); redraw();
    } catch (ex) { toast(t("Couldn't undo the layout: ") + ex.message, "error"); }
  }

  // ---- the dialog
  let dlg = null, busy = false;
  function shell() {
    if (dlg) return dlg;
    dlg = document.createElement("div"); dlg.id = "fsDlg"; dlg.setAttribute("role", "dialog"); dlg.setAttribute("aria-modal", "true"); dlg.setAttribute("aria-label", t("Arrange folders like the board"));
    dlg.innerHTML = `<div class="card"><h2>${esc(t("Arrange folders like the board"))}</h2><div class="body"></div></div>`;
    document.body.appendChild(dlg);
    dlg.addEventListener("pointerdown", e => { if (e.target === dlg && !busy) closeDialog(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape" && dlg.classList.contains("open") && !busy) { e.stopPropagation(); closeDialog(); } }, true);
    return dlg;
  }
  function closeDialog() { if (dlg) dlg.classList.remove("open"); }
  async function openDialog() {
    const d = shell(), body = d.querySelector(".body");
    body.innerHTML = `<div class="wait"><span class="spin"></span>${esc(t("Looking at the board and folders…"))}</div>`;
    void d.offsetWidth; d.classList.add("open");
    let p;
    try { const r = await fetch("/api/layout/plan"); p = await r.json(); if (!r.ok) throw new Error(p.error || r.status); }
    catch (ex) { body.innerHTML = `<div class="warn">${esc(t("Couldn't work out the layout: "))}${esc(ex.message)}</div><div class="act"><button class="no" data-x>${esc(t("Close"))}</button></div>`; body.querySelector("[data-x]").onclick = closeDialog; return; }
    const stay = p.stay + (p.off_board || 0);
    const ex = (p.examples || []).map(e => `<li title="${esc(e.from)} → ${esc(e.to)}"><div class="r was"><span>${esc(t("before"))}</span><span>${esc(mid(e.from))}</span></div><div class="r"><span>${esc(t("after"))}</span><span>${esc(mid(e.to))}</span></div></li>`).join("");
    const pages = (p.pages || []).map(x => t("“{name}”", { name: esc(x) })).join(", ");
    body.innerHTML = `
      <div class="warn">${window.hyIcon ? hyIcon("warn", 16, 2.2) : ""}
        <div>${t("The image files will move on disk into folders by the board's pages, groups and notes{pages}. New folders will appear, and old ones left without a single file will be deleted. The board, frames and old links will keep opening the images. You can undo it in this same menu.", { pages: pages ? t(" (pages {list})", { list: pages }) : "" })}</div></div><!-- hy-allow: panel-prose the warning before files move on disk: every word of it is key -->
      <div class="nums"><div class="hot"><b>${num(p.move)}</b><span>${esc(t("will move"))}</span></div><div><b>${num(p.make)}</b><span>${esc(t("new folders"))}</span></div>
        <div class="${p.remove ? "hot" : ""}"><b>${num(p.remove)}</b><span>${esc(t("empty folders deleted"))}</span></div><div><b>${num(stay)}</b><span>${esc(t("stay in place"))}</span></div></div>
      ${p.move ? `<h3>${esc(t("For example"))}</h3><ul class="ex">${ex}</ul>` : `<p class="note" style="margin:0 0 14px">${esc(t("Every image on the board is already in its folder."))}</p>`}
      ${p.move ? `<p class="note">${[t("Their json files move with the images ({files}).", { files: files(p.sidecars) }),
          p.renamed ? t("Matching names for {files}: the folder each came from is added to the name.", { files: files(p.renamed) }) : "",
          p.multi ? t("{n} images are in several places on the board", { n: p.multi }) + ", " + (p.multi === 1 ? t("it will go") : t("they will go")) + " "
            + (p.multi_dir ? t("into the folder “{name}” at the project root", { name: esc(p.multi_dir) }) : t("into the project root")) + "." : "",
          p.off_board ? t("Files not on any board ({n}) are left alone.", { n: p.off_board }) : ""].filter(Boolean).join(" ")}</p>` : ""}
      <label class="tg"><hy-switch id="fsAuto"${p.auto ? " checked" : ""}></hy-switch><span><b>${esc(t("Always keep folders like the board"))}</b><small>${esc(t("On: every board edit arranges the files again. Off: only now, once"))}</small></span></label>
      <div class="act"><button class="no" data-x>${esc(t("Cancel"))}</button><button class="go" data-go>${esc(t("folders::Arrange"))}</button></div>`;
    body.querySelector("[data-x]").onclick = closeDialog;
    body.querySelector("[data-go]").onclick = () => run(body);
  }
  async function run(body) {
    const go = body.querySelector("[data-go]"), no = body.querySelector("[data-x]"), auto = body.querySelector("#fsAuto").checked;
    busy = true; go.disabled = no.disabled = true; go.innerHTML = `<span class="spin"></span>${esc(t("Arranging…"))}`;
    try {
      const r = await fetch("/api/layout/apply", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ auto }) });
      const d = await r.json(); if (!r.ok) throw new Error(d.error || r.status);
      busy = false; closeDialog();
      if (d.status === "done") toast(t("Arranged: {files}", { files: files(d.moved) }) + (d.made ? t(", new folders: {n}", { n: d.made }) : "") + (d.removed ? t(", empty ones deleted: {n}", { n: d.removed }) : "") + (d.auto ? t(". Folders will follow the board") : ""), "success");
      else toast(d.auto ? t("Everything is already like the board. Folders will follow the board") : t("Everything is already like the board"), "success");
      await state(); redraw();
    } catch (ex) {
      busy = false; go.disabled = no.disabled = false; go.textContent = t("folders::Arrange");
      toast(t("run::Couldn't arrange the folders: ") + ex.message, "error");
    }
  }
  window.hyFsOpen = openDialog;   // for tests and agents' screenshots
  state().then(redraw);
})();
