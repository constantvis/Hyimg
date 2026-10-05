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
#fsMenu .sw { flex: none; width: 28px; height: 16px; border-radius: 999px; background: color-mix(in srgb, var(--ink) 24%, transparent); position: relative; transition: background .22s cubic-bezier(.32,.72,0,1); }
#fsMenu .sw::after { content: ""; position: absolute; left: 2px; top: 2px; width: 12px; height: 12px; border-radius: 50%; background: #fff; transition: transform .22s cubic-bezier(.32,.72,0,1); }
#fsMenu .sw.on { background: #30d158; } #fsMenu .sw.on::after { transform: translateX(12px); }
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
#fsDlg label.tg input { position: absolute; opacity: 0; width: 0; height: 0; }
#fsDlg label.tg .sw { flex: none; width: 36px; height: 21px; border-radius: 999px; background: color-mix(in srgb, var(--ink) 24%, transparent); position: relative; transition: background .25s cubic-bezier(.32,.72,0,1); }
#fsDlg label.tg .sw::after { content: ""; position: absolute; left: 2px; top: 2px; width: 17px; height: 17px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.3); transition: transform .25s cubic-bezier(.32,.72,0,1); }
#fsDlg label.tg input:checked + .sw { background: #30d158; } #fsDlg label.tg input:checked + .sw::after { transform: translateX(15px); }
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
  const ru = (n, a, b, c) => { const m = n % 10, h = n % 100; return `${n.toLocaleString("ru-RU")} ${m === 1 && h !== 11 ? a : m >= 2 && m <= 4 && (h < 12 || h > 14) ? b : c}`; };
  const files = n => ru(n, "файл", "файла", "файлов"), dirs = n => ru(n, "папка", "папки", "папок");
  const mid = (s, n = 70) => s.length <= n ? s : s.slice(0, Math.ceil((n - 1) * .42)) + "…" + s.slice(-(n - 1 - Math.ceil((n - 1) * .42)));
  const toast = (t, k) => (window.hyToast || console.log)(t, k);
  const FS = { auto: false, last: null, stamp: null };
  const ICON = s => `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${s}</svg>`;
  const IC_LAY = ICON('<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M8 13h8M13 10l3 3-3 3"/>');
  const IC_UNDO = ICON('<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>');
  const IC_SYNC = ICON('<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"/><path d="M20 20v-4h-4"/>');

  // the path bar's end: the plate while «always» is on, and the ⋯ button
  window.hyFsBar = () => (FS.auto ? `<button class="fsPill" data-fsmenu title="Папки на диске повторяют доску: каждая правка доски раскладывает файлы заново. Клик: меню, там можно выключить"><i></i>Как на доске</button>` : "")
    + `<button class="fticon fsMore" data-fsmenu aria-label="Папки как на доске" title="Папки как на доске"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="5.5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="18.5" cy="12" r="1.7"/></svg></button>`;
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
      toast(`Папки разложены как на доске: ${files(FS.last.moved)}`, "info");
    if (!first && FS.last && FS.last.who === "auto" && FS.last.status === "failed" && FS.last.id !== was) toast("Не получилось разложить по папкам: " + (FS.last.error || ""), "error");
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
    menu.innerHTML = item("plan", IC_LAY, "Разложить по папкам как на доске…")
      + item("auto", IC_SYNC, "Всегда держать папки как на доске", "", `<span class="sw ${FS.auto ? "on" : ""}"></span>`)
      + "<hr>" + item("undo", IC_UNDO, "Отменить последнюю раскладку", canUndo ? "" : " disabled");
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
      toast(FS.auto ? "Папки будут повторять доску: после каждой правки доски файлы разложатся сами" : "Папки больше не следуют за доской", FS.auto ? "success" : "info");
    } catch (ex) { toast("Не удалось переключить режим: " + ex.message, "error"); }
  }

  async function undoLast() {
    try {
      const r = await fetch("/api/layout/undo", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      const d = await r.json(); if (!r.ok) throw new Error(d.error || r.status);
      const u = d.undo || {};
      toast(`Раскладка отменена: ${files(u.back || 0)} на прежних местах` + (u.missing && u.missing.length ? `, не нашлось ${u.missing.length}` : "") + (d.auto_was ? ". Режим «как на доске» выключен" : ""), "success");
      await state(); redraw();
    } catch (ex) { toast("Не удалось отменить раскладку: " + ex.message, "error"); }
  }

  // ---- the dialog
  let dlg = null, busy = false;
  function shell() {
    if (dlg) return dlg;
    dlg = document.createElement("div"); dlg.id = "fsDlg"; dlg.setAttribute("role", "dialog"); dlg.setAttribute("aria-modal", "true"); dlg.setAttribute("aria-label", "Разложить по папкам как на доске");
    dlg.innerHTML = `<div class="card"><h2>Разложить по папкам как на доске</h2><div class="body"></div></div>`;
    document.body.appendChild(dlg);
    dlg.addEventListener("pointerdown", e => { if (e.target === dlg && !busy) closeDialog(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape" && dlg.classList.contains("open") && !busy) { e.stopPropagation(); closeDialog(); } }, true);
    return dlg;
  }
  function closeDialog() { if (dlg) dlg.classList.remove("open"); }
  async function openDialog() {
    const d = shell(), body = d.querySelector(".body");
    body.innerHTML = `<div class="wait"><span class="spin"></span>Смотрю доску и папки…</div>`;
    void d.offsetWidth; d.classList.add("open");
    let p;
    try { const r = await fetch("/api/layout/plan"); p = await r.json(); if (!r.ok) throw new Error(p.error || r.status); }
    catch (ex) { body.innerHTML = `<div class="warn">Не удалось посчитать раскладку: ${esc(ex.message)}</div><div class="act"><button class="no" data-x>Закрыть</button></div>`; body.querySelector("[data-x]").onclick = closeDialog; return; }
    const stay = p.stay + (p.off_board || 0);
    const ex = (p.examples || []).map(e => `<li title="${esc(e.from)} → ${esc(e.to)}"><div class="r was"><span>было</span><span>${esc(mid(e.from))}</span></div><div class="r"><span>стало</span><span>${esc(mid(e.to))}</span></div></li>`).join("");
    const pages = (p.pages || []).map(t => `«${esc(t)}»`).join(", ");
    body.innerHTML = `
      <div class="warn"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5M12 17.5v.1"/></svg>
        <div>Файлы картинок переедут на диске в папки по страницам, группам и заметкам доски${pages ? ` (страницы ${pages})` : ""}. Появятся новые папки, а старые, в которых не останется ни одного файла, будут удалены. Доска, фреймы и старые ссылки продолжат открывать картинки. Отменить можно в этом же меню.</div></div>
      <div class="nums"><div class="hot"><b>${p.move.toLocaleString("ru-RU")}</b><span>переедут</span></div><div><b>${p.make.toLocaleString("ru-RU")}</b><span>новых папок</span></div>
        <div class="${p.remove ? "hot" : ""}"><b>${p.remove.toLocaleString("ru-RU")}</b><span>пустых папок удалим</span></div><div><b>${stay.toLocaleString("ru-RU")}</b><span>останутся на месте</span></div></div>
      ${p.move ? `<h3>Например</h3><ul class="ex">${ex}</ul>` : `<p class="note" style="margin:0 0 14px">Все картинки с доски уже лежат в своих папках.</p>`}
      ${p.move ? `<p class="note">Вместе с картинками едут их json (${files(p.sidecars)}). ${p.renamed ? `Совпали имена у ${files(p.renamed)}: к имени добавится папка, откуда файл пришел. ` : ""}${p.multi ? `${ru(p.multi, "картинка лежит", "картинки лежат", "картинок лежат")} в нескольких местах доски, ${p.multi === 1 ? "она ляжет" : "они лягут"} ${p.multi_dir ? `в папку «${esc(p.multi_dir)}» в корне проекта` : "в корень проекта"}. ` : ""}${p.off_board ? `Файлы, которых нет на досках (${p.off_board.toLocaleString("ru-RU")}), не трогаем.` : ""}</p>` : ""}
      <label class="tg"><input type="checkbox" id="fsAuto" ${p.auto ? "checked" : ""}><span class="sw"></span><span><b>Всегда держать папки как на доске</b><small>Включено: каждая правка доски раскладывает файлы заново. Выключено: только сейчас, один раз</small></span></label>
      <div class="act"><button class="no" data-x>Отмена</button><button class="go" data-go>Разложить</button></div>`;
    body.querySelector("[data-x]").onclick = closeDialog;
    body.querySelector("[data-go]").onclick = () => run(body);
  }
  async function run(body) {
    const go = body.querySelector("[data-go]"), no = body.querySelector("[data-x]"), auto = body.querySelector("#fsAuto").checked;
    busy = true; go.disabled = no.disabled = true; go.innerHTML = `<span class="spin"></span>Раскладываю…`;
    try {
      const r = await fetch("/api/layout/apply", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ auto }) });
      const d = await r.json(); if (!r.ok) throw new Error(d.error || r.status);
      busy = false; closeDialog();
      if (d.status === "done") toast(`Разложено: ${files(d.moved)}` + (d.made ? `, новых папок ${d.made}` : "") + (d.removed ? `, удалено пустых ${d.removed}` : "") + (d.auto ? ". Папки будут повторять доску" : ""), "success");
      else toast(d.auto ? "Все уже лежит как на доске. Папки будут повторять доску" : "Все уже лежит как на доске", "success");
      await state(); redraw();
    } catch (ex) {
      busy = false; go.disabled = no.disabled = false; go.textContent = "Разложить";
      toast("Не удалось разложить по папкам: " + ex.message, "error");
    }
  }
  window.hyFsOpen = openDialog;   // for tests and agents' screenshots
  state().then(redraw);
})();
