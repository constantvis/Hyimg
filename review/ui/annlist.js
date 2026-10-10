// The Annotations list of a Studio, one for Image Studio and 3D Studio (owner 2026-10-10 on round 17 «Annotations list in Image Studio»,
// version 2: «Properties tab»; 3D Studio had its own since round 15): the threads of the open card grouped by their layer or object, Open |
// Resolved with their counts, «This layer» (only the picked one's), and a field that starts a thread on the picked layer. The field has the
// composer's keys (ui/comments.js, P4 S-33): ↵ sends, ⇧↵ a new line, Esc lets go and keeps the words, also after the Studio closes (kept
// by o.draftKey in this page's memory). A click on a thread opens it (o.open: the Studio picks its layer too). The threads are the
// board's (ui/comments.js); the words are the board's (window.T, the parent's in Image Studio's page, lang-common.js).
//   const A = hyAnnList.mount(host, { threads, picked, keyOf, nameOf, iconOf, open, send, draftKey, face, ago, who, cls })
//     threads()        the card's threads           picked()  the part a new thread goes on ({id, name}) or null
//     keyOf(part)      a part's key (its row's)     nameOf(part), iconOf(part)  its name and its icon's markup
//     open(id)         opens a thread               send(text) -> Promise<boolean>  starts one on the picked part
//   A.draw()   A.el   A.field   A.destroy()
(() => {
  if (window.hyAnnList) return;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const STYLE = `
    .hy-annlist { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; }
    .hy-annlist[hidden] { display: none; }
    .hy-annlist .af { flex: none; display: flex; flex-wrap: wrap; align-items: center; gap: 6px 4px; padding: 2px 0 8px; }
    .hy-annlist .af .sp { flex: 1; } .hy-annlist .af hy-minitoggle { flex: none; white-space: nowrap; }
    .hy-annlist .af hy-segmented button { padding: 0 7px; white-space: nowrap; } .hy-annlist .af hy-segmented em { margin-left: 4px; font-style: normal; color: var(--muted); }
    .hy-annlist .ab { flex: 1; min-height: 0; overflow: auto; scrollbar-width: none; display: flex; flex-direction: column; gap: 6px; }
    .hy-annlist .ab::-webkit-scrollbar { display: none; }
    .hy-annlist .at { padding: 4px 0 6px; border-radius: 10px; background: color-mix(in srgb, var(--panel) 40%, var(--card, var(--raise))); }
    .hy-annlist .at.on { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--sel) 55%, transparent); }
    .hy-annlist .ah { display: flex; align-items: center; gap: 7px; height: 28px; padding: 0 10px; color: var(--ink); font: 500 12px var(--sans, system-ui); }
    .hy-annlist .ah svg { width: 13px; height: 13px; color: var(--sub); flex: none; }
    .hy-annlist .ah b { font-weight: 500; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .hy-annlist .an { display: flex; gap: 8px; width: 100%; padding: 4px 10px; border: 0; background: none; color: inherit; text-align: left;
      font: 400 12px var(--sans, system-ui); border-radius: 8px; cursor: pointer; }
    .hy-annlist .an:hover { background: var(--tint, var(--raise)); }
    .hy-annlist .an > div { min-width: 0; } .hy-annlist .an b { font-weight: 500; color: var(--ink); }
    .hy-annlist .an time { margin-left: 6px; color: var(--muted); font-size: 11px; }
    .hy-annlist .an p { margin: 2px 0 0; color: var(--ink); line-height: 1.4; overflow-wrap: anywhere; } .hy-annlist .an i { color: var(--muted); font-style: normal; font-size: 11px; }
    .hy-annlist .none { padding: 14px 8px; color: var(--muted); font: 400 12px var(--sans, system-ui); }
    .hy-annlist .rp { flex: none; display: flex; align-items: center; gap: 6px; min-height: 32px; margin-top: 8px; padding: 0 10px; border-radius: 9px;
      border: 1px solid var(--line); background: var(--raise); }
    .hy-annlist .rp textarea { flex: 1; min-width: 0; max-height: 96px; padding: 7px 0; border: 0; outline: 0; background: none; color: var(--ink);
      font: 400 12px/1.4 var(--sans, system-ui); resize: none; field-sizing: content; }
    .hy-annlist .rp textarea::placeholder { color: var(--muted); } .hy-annlist .rp .ent { color: var(--muted); font: 600 12px var(--sans, system-ui); }
    .hy-annlist .rp:has(textarea:disabled) { opacity: .55; }`;
  const DRAFTS = new Map();   // the field's unsent words by o.draftKey: they outlive a Studio's session (P4 S-32)
  // the board's words: this page's T, else the board's around it (Image Studio's page)
  function words(doc) {
    const w = doc.defaultView || window;
    const T = typeof w.T === "function" ? w.T : (() => { try { return w.parent !== w && typeof w.parent.T === "function" ? w.parent.T : null; } catch { return null; } })();
    return (k, v) => T ? T(k, v) : String(k).replace(/\{(\w+)\}/g, (_, n) => (v || {})[n] ?? "");
  }
  function mount(host, o) {
    const doc = host.ownerDocument, w = doc.defaultView || window, t = o.t || words(doc);
    if (!doc.getElementById("hy-annlist-css")) { const s = doc.createElement("style"); s.id = "hy-annlist-css"; s.textContent = STYLE; doc.head.appendChild(s); }
    const el = doc.createElement("div"); el.className = "hy-annlist" + (o.cls ? " " + o.cls : "");
    el.innerHTML = `<div class="af"><hy-segmented size="s" value="open" label="${esc(t("Annotations"))}"><button value="open"></button><button value="done"></button></hy-segmented>`
      + `<span class="sp"></span><hy-minitoggle data-mine>${esc(t("This layer"))}</hy-minitoggle></div><div class="ab"></div>`
      + `<label class="rp"><textarea rows="1" maxlength="4000" autocomplete="off" spellcheck="false"></textarea><span class="ent">↵</span></label>`;
    host.appendChild(el);
    const S = { filter: "open", mine: false }, seg = el.querySelector("hy-segmented"), tog = el.querySelector("[data-mine]"), field = el.querySelector(".rp textarea"),
      list = el.querySelector(".ab"), ac = new AbortController(), on = { signal: ac.signal };
    seg.addEventListener("change", () => { S.filter = seg.value || seg.getAttribute("value") || "open"; draw(); }, on);
    seg.addEventListener("click", e => { const b = e.target.closest("button[value]"); if (b) { S.filter = b.value; draw(); } }, on);
    tog.addEventListener("change", () => { S.mine = tog.hasAttribute("checked") || !!tog.checked; draw(); }, on);
    tog.addEventListener("hy-change", e => { S.mine = !!(e.detail && e.detail.checked); draw(); }, on);
    // the field: its words kept by draftKey; the composer's keys by Hyimg's one helper (ui/typing.js), by hand without it
    field.value = (o.draftKey && DRAFTS.get(o.draftKey)) || "";
    field.addEventListener("input", () => { if (!o.draftKey) return; if (field.value) DRAFTS.set(o.draftKey, field.value); else DRAFTS.delete(o.draftKey); }, on);
    const send = async () => {
      const text = field.value.trim(); if (!text || !o.picked() || !o.send) return;
      if (await o.send(text)) { field.value = ""; if (o.draftKey) DRAFTS.delete(o.draftKey); }
    };
    const H = w.hyTyping && w.hyTyping.keys ? w.hyTyping : null;
    if (H) H.keys(field, { esc: "apply", enter: "shift", apply: e => { if (e.key === "Enter") send(); else field.blur(); } });
    else field.addEventListener("keydown", e => {
      e.stopPropagation(); if (e.key === "Escape") field.blur(); else if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
    }, on);
    list.addEventListener("click", e => { const b = e.target.closest("[data-th]"); if (b) o.open(b.dataset.th); }, on);
    function draw() {
      const all = o.threads(), open = all.filter(x => !x.resolved), done = all.length - open.length, pk = o.picked(), st = o.state ? o.state() || {} : {};
      const [bo, bd] = seg.querySelectorAll("button"); bo.innerHTML = `${esc(t("ann::Open"))}<em>${open.length}</em>`; bd.innerHTML = `${esc(t("ann::Resolved"))}<em>${done}</em>`;
      field.disabled = !pk; field.placeholder = pk ? t("Annotate {name}", { name: pk.name || pk.id }) : t("Pick a layer, then press C");
      const want = all.filter(x => (S.filter === "open" ? !x.resolved : !!x.resolved) && (!S.mine || (pk && x.anchor.part && o.keyOf(x.anchor.part) === o.keyOf(pk))));
      const groups = new Map();
      for (const th of want) { const p = th.anchor.part, k = p ? o.keyOf(p) : ""; if (!groups.has(k)) groups.set(k, { p, l: [] }); groups.get(k).l.push(th); }
      const ago = o.ago || (iso => (w.T && w.T.ago ? w.T.ago(iso) : iso || "")), face = o.face || (() => ""), who = o.who || (() => ""), pins = w.hyStudioPins;
      list.innerHTML = groups.size ? [...groups.values()].map(({ p, l }) => `<div class="at${l.some(x => x.id === st.open) ? " on" : ""}">`
        + `<div class="ah">${o.iconOf(p)}<b>${esc(p ? p.name || o.nameOf(p) : t("the card"))}</b>${pins ? pins.count(l.length, "") : ""}</div>`
        + l.map(th => { const m0 = th.messages[0] || {}, last = th.messages[th.messages.length - 1] || m0;
          return `<button class="an" data-th="${esc(th.id)}">${face(th.by)}<div><b>${esc(who(th))}</b><time>${esc(ago(last.created))}</time>`
            + `<p>${esc(m0.text || "")}</p>${th.messages.length > 1 ? `<i>${esc(t("{n} replies", { n: th.messages.length - 1 }))}</i>` : ""}</div></button>`; }).join("") + `</div>`).join("")
        : `<div class="none">${esc(S.filter === "open" ? t("No open annotations") : t("No resolved annotations"))}</div>`;
    }
    return { el, field, draw, get state() { return S; }, destroy() { ac.abort(); el.remove(); } };
  }
  window.hyAnnList = { mount, css: STYLE };
})();
