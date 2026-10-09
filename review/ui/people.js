// Who made a change (owner 2026-10-07: two people, each on his own Mac, share boards through a shared Dropbox folder). No login: the
// person on a Mac is a profile kept on that Mac (review/people.py). This file is its face on Home and on a board:
// - the first launch asks for a name and a colour (Home, in the app);
// - Settings › Profile: the name, the colour, «Sign out», the shared and the private folder, and how this Mac shows the others;
// - who wrote an entry: hyWho(e) is a dot in the person's colour and «Name» or «Codex · Name», from e.by {person, via} and the address
//   book; an entry without by gives "" and the page shows it as before;
// - Home: a lock on private boards, the filter All · Shared · Only mine, «Visibility» in a board's menu (the app moves its folder).
// A board's page asks its server (GET/POST /api/profile), Home the app ({action: "profile", op}); the app answers with hyimgProfile(d).
(() => {
  if (window.hyPeople) return;
  const SRC = (document.currentScript && document.currentScript.src) || location.href;
  const FILE = location.protocol === "file:";
  const wk = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.hyimg;
  const cef = /HyimgCEF/.test(navigator.userAgent);
  const IN_APP = !!wk || cef;
  const toApp = m => { if (wk) { wk.postMessage(m); return true; } if (cef) { console.log("HYIMG_MSG:" + JSON.stringify(m)); return true; } return false; };
  const T = (k, v) => window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m));
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const COLORS = () => window.HY_COLORS || { yellow: "#f4c430", orange: "#f59a3d", red: "#ef6a6a", pink: "#f08cc4", purple: "#b79cf2",
    blue: "#7dbbf5", green: "#7fd49b", grey: "#d9d9de" };
  const S = { me: null, people: {}, places: { shared: "", private: "" }, vis: "", known: false, out: false, draft: { name: "", color: "blue" }, badges: {} };
  const css = document.createElement("link"); css.rel = "stylesheet"; css.href = new URL("people.css", SRC).href; document.head.appendChild(css);

  // the data: Home gets it with the projects (hyimgHome), a board from its server; the app's answers come through hyimgProfile ------
  function got(d) {
    if (!d || d.error) { if (d && d.error && window.hyToast) window.hyToast(T("Not saved: {why}", { why: d.error }), "error"); return; }
    if ("me" in d) { S.me = d.me || null; S.known = true; }
    if ("profile" in d) { S.me = d.profile || null; S.known = true; }
    if (d.people) S.people = d.people;
    if (d.badges && typeof d.badges === "object") { S.badges = d.badges; ownBadges(); }   // this Mac's own pictures of the agent kinds
    if (d.places) S.places = { shared: d.places.shared || "", private: d.places.private || "" };
    if (d.board) S.vis = d.board.vis || "";
    if (d.vis && Array.isArray(d.projects)) d.projects.forEach(p => { p.vis = d.vis[p.id] || ""; });   // Home: each board's place, from the app
    paint(); welcome();
    try { window.dispatchEvent(new CustomEvent("hy-people")); } catch {}
  }
  window.hyimgProfile = got;
  function load() { if (!FILE) fetch("/api/profile", { cache: "no-store" }).then(r => r.ok ? r.json() : null).then(got).catch(() => {}); }
  function post(body) {
    if (FILE) { toApp({ action: "profile", ...body }); return; }
    fetch("/api/profile", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(r => r.json()).then(got).catch(() => got({ error: "network" }));
  }

  // where the settings' sections stand: the settings window's body (ui/settings-win.js, hySetPanel.body()), else the page's #sets
  const host = () => (window.hySetPanel && window.hySetPanel.body()) || document.getElementById("sets");
  const ownBadges = () => { if (window.HY_AGENTS && window.HY_AGENTS.badges) window.HY_AGENTS.badges(S.badges); };

  // who wrote an entry: the person's face, an agent's badge on it (ui/avatar.js); an agent's name of any spelling folds into its kind --
  const person = id => (id && S.people[id]) || null;
  const AG = () => window.HY_AGENTS || { kind: v => (v && v !== "app" ? "agent" : ""), label: () => "Agent" };
  function who(e) {
    const b = e && e.by; if (!b || typeof b !== "object") return null;
    // an entry whose tree showed no agent but which names one in «who» (news stored before 2026-10-08) shows that agent, not «Someone»
    const p = person(b.person), name = p ? p.name : b.person ? T("Someone") : "", kw = AG().kind(e.who), k = AG().kind(b.via) || (kw !== "agent" ? kw : "");
    const via = k ? (k === "agent" ? T("Agent") : AG().label(k)) : "";
    return { text: via ? (name ? `${via} · ${name}` : via) : name || T("Someone"), color: (p && COLORS()[p.color]) || "", name, via, kind: k, me: !!(p && p.me),
      person: b.person || "", src: (p && p.avatar) || "", key: p ? p.color : "" };
  }
  const dot = c => `<i class="hy-pdot" style="${c ? `background:${c}` : ""}"></i>`;
  // a face for {person, via}: the person's picture or initials on his colour, the agent's badge
  const face = (w, size = 16) => window.hyAvatarHTML ? window.hyAvatarHTML({ name: w.name || w.text, color: w.key || w.color, src: w.src, agent: w.kind, size, label: w.text })
    : dot(w.color);
  window.hyWhoText = e => (who(e) || {}).text || "";
  window.hyWho = (e, cls = "who", size = 16) => { const w = who(e); return w ? `<span class="${cls} hy-by" title="${esc(w.text)}">${face(w, size)}${esc(w.text)}</span>` : ""; };
  // the bell's line: the face and the words, without a wrapper of its own (the notification's span keeps its class)
  window.hyWhoIn = e => { const w = who(e); return w ? `${face(w, 16)}${esc(w.text)}` : ""; };
  window.hyAvatarOf = (by, size = 20) => { const w = who({ by }); return w ? face(w, size) : ""; };
  window.hyWhoOf = by => who({ by });   // {text, color, name, via, kind, …} of a writer (ui/merge.js: a merged save in its author's colour)
  // the info panel's «edited by»: the newest change of a card, its page's events or its files (GET /api/edited)
  let EDIT_ASK = 0;
  window.hyEdited = (el, page, id, paths) => {
    if (FILE || !el) return;
    const k = ++EDIT_ASK, qs = new URLSearchParams({ name: page || "main" }); if (id) qs.set("id", id);
    (paths || []).filter(p => typeof p === "string" && /\.\w+$/.test(p)).forEach(p => qs.append("p", p));   // a card's files: its path, a 3D scene
    fetch("/api/edited?" + qs, { cache: "no-store" }).then(r => r.ok ? r.json() : null).then(e => {
      if (k !== EDIT_ASK || !e || !e.by || !el.isConnected) return;
      el.querySelectorAll(".hy-edited").forEach(x => x.remove());
      el.insertAdjacentHTML("beforeend", `<span class="hy-edited">${esc(T("edited by"))} ${window.hyWho(e, "hy-ew")} · ${esc((e.t || "").slice(11, 16))}</span>`);
    }).catch(() => {});
  };

  // the first launch: a name and a colour (Home, in the app; a board never asks, the app always starts on Home) --------------------
  const swatches = (cur, attr) => `<hy-swatches ${attr} value="${esc(cur)}" label="${esc(T("Colour"))}">` + Object.entries(COLORS()).map(([k, v]) =>
    `<hy-swatch size="m" color="${v}" style="--hy-sw:${v}" value="${k}" label="${esc(T(k))}" role="radio" aria-checked="${k === cur}"`
    + `${k === cur ? " selected" : ""}></hy-swatch>`).join("") + "</hy-swatches>";
  const button = (attrs, words, variant = "plain", size = "s") => `<hy-button size="${size}" variant="${variant}" ${attrs}>`
    + (window.customElements && customElements.get("hy-button") ? esc(words) : `<button type="button">${esc(words)}</button>`) + "</hy-button>";
  // a small icon button: the primitive where the module runs (a board), its plain markup on Home (a file page loads no modules)
  const iconButton = (attrs, icon, label) => window.customElements && customElements.get("hy-icon-button")
    ? `<hy-icon-button icon="${icon}" size="s" label="${esc(label)}" ${attrs}></hy-icon-button>`
    : `<hy-icon-button icon="${icon}" size="s" label="${esc(label)}" ${attrs}><button type="button" aria-label="${esc(label)}" title="${esc(label)}">`
      + `${window.hyIcon ? hyIcon(icon, 14, 1.9, "hy-i") : ""}</button></hy-icon-button>`;
  function welcome() {
    let el = document.getElementById("hyWelcome");
    const want = FILE && S.known && !S.me && !S.out;
    if (!want) { if (el) { el.classList.remove("in"); setTimeout(() => { if (!el.classList.contains("in")) el.remove(); }, 320); } return; }
    if (el) return;
    el = document.createElement("div"); el.id = "hyWelcome"; el.className = "hy-welcome"; el.setAttribute("role", "dialog"); el.setAttribute("aria-modal", "true");
    el.setAttribute("aria-labelledby", "hyWelcomeT");
    el.innerHTML = `<form class="hw-card"><h2 id="hyWelcomeT">${esc(T("What's your name?"))}</h2>`
      + `<p class="hy-hint">${T("Your name and colour mark <b>your changes</b> on shared boards")}</p>`
      + `<input id="hwName" maxlength="40" autocomplete="name" placeholder="${esc(T("person::Name"))}" aria-label="${esc(T("person::Name"))}">`
      + swatches(S.draft.color, "data-hw-color") + `<div class="hw-row">${button("data-hw-ok", T("Continue"), "solid", "l")}</div></form>`;
    document.body.appendChild(el);
    requestAnimationFrame(() => { el.classList.add("in"); el.querySelector("#hwName").focus(); });
    const ok = () => {
      const name = el.querySelector("#hwName").value.trim(); if (!name) { el.querySelector("#hwName").focus(); el.classList.add("need"); return; }
      S.me = { id: "", name, color: S.draft.color }; post({ op: "save", name, color: S.draft.color }); welcome(); paint();
    };
    el.querySelector("form").addEventListener("submit", e => { e.preventDefault(); ok(); });
    el.addEventListener("click", e => { if (e.target.closest("[data-hw-ok]")) ok(); });
  }

  // Settings › Profile: the first section of the settings panel, the same on Home and on a board ------------------------------------
  const tail = p => { const s = String(p || ""); return s.replace(/^\/Users\/[^/]+/, "~"); };
  function placeRow(k, label) {
    const p = S.places[k], pick = IN_APP || FILE;
    return `<div class="sp-row hp-place" data-row="${k}"><span class="sp-l">${esc(T(label))}</span><span class="sp-c hp-pc">`
      + `<span class="hp-path" title="${esc(p)}">${p ? esc(tail(p).split("/").pop() || p) : esc(T("not chosen"))}</span>`
      + button(`data-hp-pick="${k}"${pick ? "" : ` disabled title="${esc(T("Only in the Mac app"))}"`}`, p ? T("Change…") : T("Choose…")) + "</span></div>";
  }
  function section() {
    const sets = host(); if (!sets) return null;
    let el = document.getElementById("hyPeopleSet");
    if (!el) {
      el = document.createElement("section"); el.id = "hyPeopleSet"; el.className = "sp-g hp"; el.setAttribute("aria-label", T("Profile"));
      el.addEventListener("click", click); el.addEventListener("change", change); el.addEventListener("keydown", e => { if (e.key === "Enter" && e.target.matches("input")) e.target.blur(); });
    }
    const sp = sets.querySelector(":scope > .sp");   // the shared rows (ui/setpanel.js): the profile comes first, above them
    if (sp ? el.nextElementSibling !== sp : sets.firstElementChild !== el) { if (sp) sets.insertBefore(el, sp); else sets.prepend(el); }
    return el;
  }
  // Team (owner 2026-10-07: «чтобы я видел своих "сотрудников" в настройках и их аватары»): the people this Mac knows (the address book,
  // with this Mac's names for them) and, under each, the agents seen acting for him, with their badge and when; this Mac's own agents
  // first, under «Agents». No accounts, nothing leaves the Mac; a person can be hidden from the lists (his changes still name him).
  const av = (p, id, size, agent) => window.hyAvatarHTML ? window.hyAvatarHTML({ name: p.name, color: p.color, src: p.avatar, agent, size }) : dot(COLORS()[p.color]);
  const ago = t => window.T && window.T.ago ? window.T.ago(t * 1000) : new Date(t * 1000).toLocaleString();
  const agentRows = (p, id) => Object.entries(p.agents || {}).sort((a, b) => b[1] - a[1]).map(([k, t]) =>
    `<div class="sp-row hp-agent" data-agent="${esc(k)}"><span class="sp-l">${av(p, id, 20, k)}<span class="hp-an">${esc(AG().label(k) || k)}</span></span>`
    + `<span class="hp-when">${esc(ago(t))}</span></div>`).join("");
  // this Mac's agents (owner 2026-10-08: «аватар можно было менять»): every kind of the catalog, the ones that acted first, newest first;
  // each with its badge alone (a click or the picture button changes it: the company's mark by default, or one of this Mac's), and when
  // it last acted
  const KINDS = () => (window.HY_AGENTS && window.HY_AGENTS.CATALOG) || ["claude", "codex", "gemini", "kimi", "opencode", "agent"];
  const solo = (k, px) => window.hyAgentBadgeHTML ? window.hyAgentBadgeHTML(k, px) : dot("");
  function myAgents(p) {
    const seen = p.agents || {}, kinds = KINDS().slice().sort((a, b) => (seen[b] || 0) - (seen[a] || 0));
    return kinds.map(k => {
      const name = AG().label(k) || k, own = !!S.badges[k], change = T("Change the {name} badge", { name });
      return `<div class="sp-row hp-agent hp-mine${seen[k] ? "" : " hp-idle"}" data-agent="${esc(k)}"><span class="sp-l">`
        + `<button type="button" class="hp-badge" data-hp-badge="${esc(k)}" title="${esc(change)}" aria-label="${esc(change)}">${solo(k, 20)}</button>`
        + `<span class="hp-an">${esc(name)}</span></span><span class="hp-pc"><span class="hp-when">${esc(seen[k] ? ago(seen[k]) : T("not yet"))}</span>`
        + iconButton(`data-hp-badge="${esc(k)}"`, "image", change)
        + (own ? iconButton(`data-hp-badge-reset="${esc(k)}"`, "reset", T("The default {name} badge", { name })) : "") + "</span></div>";
    }).join("") + `<input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml,image/heic" data-hp-bfile hidden>`;
  }
  function team() {
    const m = S.me, list = Object.entries(S.people).filter(([, p]) => !p.me).sort((a, b) => a[1].name.localeCompare(b[1].name));
    const shown = list.filter(([, p]) => !p.hidden), hidden = list.filter(([, p]) => p.hidden), mine = m && S.people[m.id];
    let h = `<div class="sp-row hp-sub"><span class="sp-l">${esc(T("Agents"))}</span></div>`;
    h += myAgents(mine || m || {});   // this Mac's agents, a profile or not
    if (!shown.length && !hidden.length) return h;
    h += `<div class="sp-row hp-sub"><span class="sp-l">${esc(T("Team"))}</span></div>` + shown.map(([id, p]) =>
      `<div class="sp-row hp-person" data-person="${esc(id)}"><span class="sp-l">${av(p, id, 24)}</span><input class="sp-c hp-name" data-hp-alias="${esc(id)}" maxlength="40"`
      + ` value="${esc(p.alias || "")}" placeholder="${esc(p.own || p.name)}" aria-label="${esc(T("How {name} shows on this Mac", { name: p.own || p.name }))}">`
      + iconButton(`data-hp-hide="${esc(id)}"`, "eyeoff", T("Hide {name}", { name: p.name })) + "</div>"
      + agentRows(p, id)).join("");
    if (hidden.length) h += `<div class="sp-row hp-sub hp-hidden"><span class="sp-l">${esc(T("Hidden"))}</span></div>` + hidden.map(([id, p]) =>
      `<div class="sp-row hp-person hp-off" data-person="${esc(id)}"><span class="sp-l">${av(p, id, 20)}<span class="hp-an">${esc(p.name)}</span></span>`
      + button(`data-hp-show="${esc(id)}"`, T("Show")) + "</div>").join("");
    return h;
  }
  // two sections of the settings window: Profile (the person, his folders) and Team & agents (data-sec, ui/settings-win.js)
  function paint() {
    const el = section(); if (!el) return;
    const m = S.me;
    let h = `<div class="sh">${esc(T("Profile"))}</div><div class="hp-prof" data-sec="profile">`;
    if (m) {
      const pic = (S.people[m.id] || {}).avatar || m.avatar || "";
      h += `<div class="sp-row hp-me"><button type="button" class="hp-pic" data-hp-pic title="${esc(T("Your picture"))}" aria-label="${esc(T("Your picture"))}">`
        + `${av({ ...m, avatar: pic }, m.id, 32)}</button><input class="sp-c hp-name" data-hp-name maxlength="40" value="${esc(m.name)}" aria-label="${esc(T("person::Name"))}">`
        + `<input type="file" accept="image/png,image/jpeg,image/webp,image/heic" data-hp-file hidden></div>`;
      h += `<div class="sp-row"><span class="sp-l">${esc(T("Colour"))}</span><span class="sp-c">${swatches(m.color, "data-hp-color")}</span></div>`;
      h += `<div class="sp-row"><span class="sp-l">${esc(T("Picture"))}</span><span class="sp-c hp-pc">${button("data-hp=pic", pic ? T("Change…") : T("Choose…"))}`
        + `${pic ? button("data-hp=nopic", T("Remove"), "ghost") : ""}</span></div>`;
    } else h += `<div class="sp-row"><span class="sp-l">${esc(T("No profile on this Mac"))}</span>${FILE ? button("data-hp=signin", T("Introduce yourself…")) : ""}</div>`;
    h += placeRow("shared", "Shared folder") + placeRow("private", "Private folder");
    if (m) h += `<div class="sp-row">${button("data-hp=signout", T("Sign out of the profile"), "ghost")}</div>`;
    // owner 2026-10-08: two Macs on one Dropbox account get every folder, the private one too; the place is a label and a filter
    h += `<div class="hy-hint hp-label">${T("“Only for me” is <b>a label, not privacy</b>: on one Dropbox account the files reach both Macs")}</div></div>`;
    h += `<div class="hp-team" data-sec="team">${team()}</div>`;
    const typing = el.contains(document.activeElement) && document.activeElement.matches("input");   // a name being typed is not redrawn
    if (el._h !== h && !typing) { el.innerHTML = h; el._h = h; }
  }
  // a picture the person picks, placed and zoomed in a round window (ui/crop.js, loaded the first time), then kept as a small square:
  // his own at 256 px (a JPEG of 15-40 KB; the boards' cards carry it to the other Mac), an agent kind's badge at 96 px (only this Mac)
  const MAX = 80000;   // people.py AVATAR_MAX
  let cropLoad = null;
  function crop(file, o) {
    if (!cropLoad) cropLoad = window.hyCrop ? Promise.resolve() : new Promise((ok, no) => {
      const sc = document.createElement("script"); sc.src = new URL("crop.js", SRC).href; sc.onload = ok; sc.onerror = () => { cropLoad = null; no(new Error("crop.js")); };
      document.head.appendChild(sc);
    });
    return cropLoad.then(() => window.hyCrop(file, { max: MAX, ...o })).catch(() => { got({ error: T("not a picture") }); return null; });
  }
  function picture(file) {
    if (!file) return;
    crop(file, { size: 256, title: T("Your picture") }).then(data => {
      if (!data) return;
      if (S.me) { S.people[S.me.id] = { ...(S.people[S.me.id] || {}), avatar: data }; paint(); }
      post({ op: "avatar", avatar: data });
    });
  }
  let badgeKind = "";
  function badge(kind, file) {
    if (!file || !kind) return;
    crop(file, { size: 96, type: "image/png", title: T("The {name} badge", { name: AG().label(kind) || kind }) }).then(data => {
      if (!data) return;
      S.badges = { ...S.badges, [kind]: data }; ownBadges(); paint();
      post({ op: "badge", kind, picture: data });
    });
  }
  function click(e) {
    const sw = e.target.closest("hy-swatch"); if (sw) { pickColor(sw); return; }
    const pk = e.target.closest("[data-hp-pick]"); if (pk && !pk.hasAttribute("disabled")) { toApp({ action: "profile", op: "pick", which: pk.dataset.hpPick }); return; }
    const hd = e.target.closest("[data-hp-hide]"); if (hd) { post({ op: "hide", person: hd.dataset.hpHide, hidden: true }); return; }
    const sh = e.target.closest("[data-hp-show]"); if (sh) { post({ op: "hide", person: sh.dataset.hpShow, hidden: false }); return; }
    if (e.target.closest("[data-hp-pic]")) { const f = document.querySelector("#hyPeopleSet [data-hp-file]"); if (f) f.click(); return; }
    const bd = e.target.closest("[data-hp-badge]");
    if (bd) { badgeKind = bd.dataset.hpBadge; const f = document.querySelector("#hyPeopleSet [data-hp-bfile]"); if (f) f.click(); return; }
    const br = e.target.closest("[data-hp-badge-reset]");
    if (br) { const k = br.dataset.hpBadgeReset, b = { ...S.badges }; delete b[k]; S.badges = b; ownBadges(); paint(); post({ op: "badge", kind: k, picture: "" }); return; }
    const b = e.target.closest("[data-hp]"); if (!b) return;
    if (b.dataset.hp === "signout") { S.out = true; S.me = null; post({ op: "signout" }); paint(); }
    else if (b.dataset.hp === "signin") { S.out = false; welcome(); }
    else if (b.dataset.hp === "pic") { const f = document.querySelector("#hyPeopleSet [data-hp-file]"); if (f) f.click(); }
    else if (b.dataset.hp === "nopic" && S.me) { const p = S.people[S.me.id]; if (p) delete p.avatar; delete S.me.avatar; paint(); post({ op: "avatar", avatar: "" }); }
  }
  function pickColor(sw) {
    const row = sw.closest("hy-swatches"), v = sw.getAttribute("value");
    row.setAttribute("value", v);
    row.querySelectorAll("hy-swatch").forEach(s => { const on = s === sw; s.toggleAttribute("selected", on); s.setAttribute("aria-checked", String(on)); });
    if (row.hasAttribute("data-hw-color")) { S.draft.color = v; return; }
    if (row.hasAttribute("data-hp-color") && S.me) { S.me = { ...S.me, color: v }; post({ op: "save", name: S.me.name, color: v }); }
  }
  document.addEventListener("click", e => { const sw = e.target.closest("#hyWelcome hy-swatch"); if (sw) pickColor(sw); });
  function change(e) {
    const t = e.target;
    if (t.matches("[data-hp-file]")) { picture(t.files && t.files[0]); t.value = ""; return; }
    if (t.matches("[data-hp-bfile]")) { badge(badgeKind, t.files && t.files[0]); t.value = ""; return; }
    if (t.matches("[data-hp-name]") && S.me && t.value.trim() && t.value.trim() !== S.me.name) { S.me = { ...S.me, name: t.value.trim() }; post({ op: "save", name: S.me.name, color: S.me.color }); }
    else if (t.matches("[data-hp-alias]")) post({ op: "alias", person: t.dataset.hpAlias, name: t.value.trim() });
  }

  // Home: a lock on private boards, the filter, «Visibility» in a board's menu ------------------------------------------------------
  const placesSet = () => !!(S.places.shared && S.places.private);
  const lock = p => p && p.vis === "private" ? `<span class="hp-lock" title="${esc(T("Only for me"))}" aria-label="${esc(T("Only for me"))}">`
    + `${window.hyIcon ? hyIcon("lock", 12, 2.2) : ""}</span>` : "";
  const filter = (list, home) => home && (home.vis === "shared" || home.vis === "private") ? list.filter(p => p.vis === home.vis) : list;
  const visSeg = (home, all) => !(all || []).some(p => p.vis) ? "" : `<div class="seg hp-vis" role="group" aria-label="${esc(T("Visibility"))}">`
    + [["", "vis::All"], ["shared", "filter::Shared"], ["private", "Only mine"]]
      .map(([v, w]) => `<button data-hpvis="${v}" aria-pressed="${(home.vis || "") === v}">${esc(T(w))}</button>`).join("") + "</div>";
  function menu(p) {
    const off = !placesSet(), why = T("Choose the shared and the private folder in Settings › Profile first");
    const item = (to, icon, words) => window.hyMenuItem(`data-hpto="${to}" data-id="${esc(p.id)}"`, p.vis === to ? "check" : icon, esc(T(words)),
      null, off ? window.hyMenuOff(why) : p.vis === to ? window.hyMenuOff(T("The board is already there")) : "");
    return "<hr>" + item("shared", "lockOpen", "vis::Shared") + item("private", "lock", "Only for me");
  }
  document.addEventListener("click", e => {
    const v = e.target.closest("[data-hpvis]");
    if (v && typeof HOME === "object") {
      if (v.dataset.hpvis) HOME.vis = v.dataset.hpvis; else delete HOME.vis;
      if (typeof saveHome === "function") saveHome();
      if (typeof render === "function") render();
      return;
    }
    const to = e.target.closest("[data-hpto]"); if (!to) return;
    e.stopPropagation(); if (typeof closeMenu === "function") closeMenu();
    if (to.getAttribute("aria-disabled") === "true") return;
    toApp({ action: "profile", op: "visibility", id: to.dataset.id, to: to.dataset.hpto });
  }, true);
  // Home's news: «Codex (Name)» for another person's agent, «Name» for their own edits, as before for this Mac's
  const newsAgent = w => w === "ai" ? T("AI") : w === "owner" || !w ? "" : AG().kind(w) === "agent" ? T("Agent") : AG().label(w) || w;
  function newsWho(r) {
    const p = r.u && r.u !== (S.me && S.me.id) ? person(r.u) : null, w = newsAgent(r.w);
    if (!p) return w || (r.w === "owner" ? T("Someone") : "");
    return w ? `${w} (${p.name})` : p.name;
  }
  // Home's news: the faces of who did it, up to three, before the count (another person, his agents, this Mac's agents)
  function newsFaces(nw) {
    const seen = new Set(), out = [];
    for (const r of (nw && nw.rows) || []) {
      const k = r.w === "ai" ? "agent" : r.w === "owner" ? "" : AG().kind(r.w), id = r.u || (S.me && S.me.id) || "", key = id + "|" + k;
      if (seen.has(key) || (!k && (!r.u || r.u === (S.me && S.me.id)))) continue;
      seen.add(key); out.push(window.hyAvatarOf ? window.hyAvatarOf({ person: id, via: k || "app" }, 16) : "");
      if (out.length === 3) break;
    }
    return out.length ? `<span class="hy-faces nb-who" aria-hidden="true">${out.join("")}</span>` : "";
  }

  window.hyPeople = { set: got, who, lock, filter, visSeg, menu, newsWho, newsFaces, me: () => S.me, places: () => S.places, people: () => S.people,
    badges: () => S.badges, load, post };
  function watch() {
    ownBadges(); paint(); load();
    const sets = host();
    if (sets) new MutationObserver(() => { const el = document.getElementById("hyPeopleSet"), sp = sets.querySelector(":scope > .sp");
      if (!el || (sp ? el.nextElementSibling !== sp : sets.firstElementChild !== el)) paint(); }).observe(sets, { childList: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch); else watch();
})();
