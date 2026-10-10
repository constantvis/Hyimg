// The Info card's body, round 18's «Spec sheet» (owner 2026-10-10 on r18-info.html, question 6, version 3 ★, no objection; his note of
// round 16: «у нас есть разные данные: 3д, html файлы, pdf, step, stl, psd, просто картинки, картинки сгенерированные одной моделью или
// двумя, и тут важно разные данные подавать в info; json точно мне как копия не нужен»). Every kind gets its sections in a fixed order, so
// switching between frames compares row by row; a section shows only when it has something. Under them «More · file, tags, path» opens the
// rest. No annotations here (owner 2026-10-10: «Аннотации нам тут точно не нужны»): they live on the board's pins and in the bell.
//   pic(root, id, it, m)    a picture, a video, a PDF, a PSD: Prompt (Copy), Generation or Made (model, batch, when), Sources (the pictures
//                           that went in, each with its own model: a video made from a picture of another model shows both), the owner's
//                           Rating, Notes, AI questions; More: the place on the board, tags, who changed it, the path
//   card(root, id, it, inf) a plugin's card: the plugin's own sections (info().spec: [{ title, rows: [[key, value]] }]) or, for a 3D scene
//                           and an HTML page, what the file says (objects, cameras, lights; the page's title and its pictures); Notes;
//                           More: the file and who changed it; the plugin's words (info().text) as the footnote under all of it
// The header (name, facts, ♥, Open ▾) is ui/infohead.js; canvas.html renderInfo calls both. The look: ui/infobody.css. Uses canvas.html's
// board, byPath, goTo, render, isNote, noteCol, mdHtml, linksOf, picIndex, linkify, copyText, toast, EMBED and T.
(() => {
  if (window.hyInfoBody) return;
  const css = document.createElement("link"); css.rel = "stylesheet"; css.href = "/ui/infobody.css"; (document.head || document.documentElement).appendChild(css);
  const enc = encodeURIComponent;
  // the owner's review words, the library's Russian ones turned English (canvas.html CRIT_RU, VERDICT_RU, USE_RU, oldTag, ENGINE_TAG: the
  // json keeps the Russian words, so they stay beside the other data words of the board)
  const FILES = new Map();   // a plugin card's file (a scene's json, a page's html) -> what it says, or null while it is read

  // ---------- the parts every kind is made of ----------
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  // a section: its caps title, on the right a count or a small action
  function sec(root, title, right) {
    const s = el("section", "isec"), h = el("div", "sh hy-sub", title); s.appendChild(h);
    if (right instanceof Node) h.appendChild(right); else if (right != null && right !== "") h.appendChild(el("em", "", String(right)));
    root.appendChild(s); return s;
  }
  // the spec sheet: a label column and the values, each row in its place, a hairline under it
  function spec(s, rows) {
    const dl = el("dl", "spec");
    rows.filter(r => r && r[1] != null && r[1] !== "").forEach(([k, v]) => {
      dl.appendChild(el("dt", "", k)); const d = el("dd"); if (v instanceof Node) d.appendChild(v); else d.textContent = v; dl.appendChild(d);
    });
    if (dl.childNodes.length) s.appendChild(dl); return dl;
  }
  const when = s => { if (!s) return ""; const d = new Date(s * 1000);
    return isNaN(d) ? "" : d.toLocaleString(T.lang === "ru" ? "ru-RU" : "en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }); };
  const baseName = p => String(p || "").split("/").pop();
  const view = p => EMBED ? parent.postMessage({ type: "openFrame", path: p }, location.origin) : open(`/img?p=${enc(p)}`, "_blank");
  // the path with «Show in Finder» beside it (owner 2026-10-05)
  function pathRow(s, p) {
    const pr = el("div", "prow"); pr.appendChild(el("div", "path", p)); s.appendChild(pr);
    const rv = el("button", "rv"); rv.title = T("Show in Finder"); rv.setAttribute("aria-label", T("Show in Finder")); rv.innerHTML = (window.HY_IC || {}).finder || "";
    rv.onclick = () => hyReveal([p], toast); pr.appendChild(rv); return pr;
  }
  // the pictures that went in: a small square each, its name and the model that made it (a second model shows here); a click opens it
  function sources(root, paths, title) {
    if (!paths.length) return;
    const s = sec(root, title, paths.length > 1 ? paths.length : ""), w = el("div", "srcs");
    paths.slice(0, 6).forEach(p => {
      const r = el("button", "src"), im = el("img"); im.src = `/thumb?p=${enc(p)}&s=160`; im.alt = ""; im.draggable = false; r.appendChild(im);
      const sm = byPath.get(p) || {}, lab = el("span", "lab"); lab.appendChild(el("span", "", baseName(p))); if (sm.model) lab.appendChild(el("em", "", sm.model));
      r.appendChild(lab); r.title = p + " · " + T("open"); r.onclick = () => view(p); w.appendChild(r);
    });
    if (paths.length > 6) w.appendChild(el("span", "lab more", `+${paths.length - 6}`));
    s.appendChild(w);
  }
  // the board's notes about it: the note's colour, its words; how it is linked in the tooltip, a click goes to it
  function notes(root, id, word) {
    const VIA = { zone: T("in the area"), arrow: T("by an arrow"), overlap: T(word), group: T("through the group"), reply: T("as a reply") };
    const NN = [], near = picIndex();
    for (const nid in board.items) { const n = board.items[nid]; if (!isNote(n) || !(n.text || "").trim()) continue; const v = linksOf(nid, near).get(id); if (v) NN.push([nid, n, v]); }
    if (!NN.length) return;
    const s = sec(root, T("Notes"), NN.length);
    NN.forEach(([nid, n, v]) => {
      const b = el("button", "inote nt"); b.style.setProperty("--nc", noteCol(n)[0]); b.title = `${T("Go to the note")} · ${[...v].map(x => VIA[x] || x).join(", ")}`;
      b.innerHTML = `<i></i><div class="t">${mdHtml(n.text)}</div>`; b.onclick = () => { goTo(nid); render(); }; s.appendChild(b);
    });
  }
  // «More · file, tags, path»: the rest, folded; open or folded is remembered for the next card (this viewer only)
  function more(root, what, build) {
    let shown = false; try { shown = localStorage.getItem("cv.infoMore") === "1"; } catch {}
    const b = el("button", "mrow"), box = el("div", "imore");
    b.innerHTML = `<span></span><em></em><span class="sp"></span>${window.hyIcon ? window.hyIcon("chevron", 12, 2.2, "mcv") : ""}`;
    b.querySelector("span").textContent = T("More"); b.querySelector("em").textContent = what; b.setAttribute("aria-expanded", shown);
    const set = o => { shown = o; b.setAttribute("aria-expanded", o); box.hidden = !o; if (o && !box.childNodes.length) build(box);
      try { localStorage.setItem("cv.infoMore", o ? "1" : "0"); } catch {} };
    b.onclick = () => set(!shown); root.append(b, box); set(shown);
  }
  const foot = root => { const f = el("p", "ifoot hy-hint"); f.innerHTML = T("<b>The AI reads</b> this: the frame's json and the board's notes"); root.appendChild(f); };

  // ---------- a picture, a video, a PDF ----------
  function pic(root, id, it, m) {
    root.textContent = "";
    const f = m.feedback || {}, vid = m.kind === "video";
    // what the frame is: the prompt of a generated frame (Copy), or the caption and link of a reference
    if (m.prompt) {
      const ref = (m.folder || "").startsWith("ext/"), cp = el("button", "act", T("Copy")); cp.title = T("Copy the prompt");
      cp.onclick = () => copyText(m.prompt, T("Prompt copied"));
      const s = sec(root, ref ? T("Source") : T("Prompt"), cp), p = el("div", "txt clamp"); linkify(p, m.prompt); s.appendChild(p);
      if (m.prompt.length > 260) {
        const mo = el("button", "more", T("Show in full")); s.appendChild(mo);
        mo.onclick = () => { const o = p.classList.toggle("clamp"); mo.textContent = o ? T("Show in full") : T("Collapse"); };
      }
    } else source(root, it);
    // how it was made: the model, the batch and its place in it, when
    const mates = m.folder != null ? [...byPath.values()].filter(x => x.folder === m.folder && x.start === m.start)
      .sort((a, b) => (a.born || 0) - (b.born || 0) || String(a.name).localeCompare(b.name)) : [];
    const k = mates.findIndex(x => x.path === it.path), made = sec(root, m.model || m.prompt ? T("Generation") : T("Made"));
    const nth = mates.length > 1 && k >= 0 ? T("{i} of {n}", { i: k + 1, n: mates.length }) : "";
    spec(made, [[vid ? T("Video") : T("Model"), m.model || ""], [T("Batch"), [m.start || "", nth].filter(Boolean).join(" · ")],
      [T("When"), when(m.born || m.mtime)], m.pages ? [T("Pages"), String(m.pages)] : null]);
    sources(root, m.refpaths || [], T("Sources"));
    review(root, f);
    notes(root, id, "lies on the frame");
    if ((m.questions || []).length) {
      const s = sec(root, T("AI questions"));
      m.questions.forEach(q => { const d = el("div", "qa"); d.appendChild(el("p", "txt", q.q)); d.appendChild(el("p", q.a ? "txt ans" : "muted", q.a || T("no answer"))); s.appendChild(d); });
    }
    more(root, T("file, tags, path"), box => {
      // its place on the board; the same picture inside image frames counts as a copy on the page (owner 2026-10-05)
      const gid = Object.keys(board.groups).find(g => board.groups[g].members.includes(id)), inFrames = Object.values(board.items).filter(x => !isPic(x) && picsOf(x).includes(it.path)).length;
      const copies = Object.values(board.items).filter(x => x.path === it.path).length + inFrames;
      const place = [gid ? T("Group “{name}”", { name: (board.groups[gid].title || "").split("\n")[0] }) : T("Outside groups"), it.crop ? T("cropped") : "",
        copies > 1 ? T("copies on the page: {n}", { n: copies }) + (inFrames ? T(", in frames {n}", { n: inFrames }) : "") : ""].filter(Boolean);
      sec(box, T("On the board")).appendChild(el("div", "txt", place.join(" · ")));
      if ((m.owner_tags || []).length || (m.tags || []).length) {
        const s = sec(box, T("Tags")), w = el("div", "chips");
        (m.owner_tags || []).forEach(x => w.appendChild(el("span", "chip own", x)));
        (m.tags || []).forEach(x => w.appendChild(el("span", "chip", ENGINE_TAG[x] ? T(ENGINE_TAG[x]) : x))); s.appendChild(w);
      }
      // the size, length, format and bytes are the header's (ui/infohead.js, owner 2026-10-09); here who changed it and where it lies
      const s = sec(box, T("File")), who = s.appendChild(el("div", "muted", "")); window.hyEdited?.(who, BOARD, id, [it.path]); pathRow(s, it.path);
      foot(box);
    });
  }
  // a frame the library has no prompt for (refs/ and frames outside the library, owner 2026-10-01: «the description must have a link I
  // can click»): source page, video with its timestamp, image address, Gemini chat
  function source(root, it) {
    const s = sec(root, T("Source")), box = el("div", "txt"); s.appendChild(box); box.textContent = "…";
    fetch("/api/meta?p=" + enc(it.path)).then(r => r.json()).then(d => {
      const lines = [], yt = d.source_url && d.timestamp && /youtube\.com|youtu\.be/.test(d.source_url);
      const secs = yt ? String(d.timestamp).split(":").reduce((a, v) => a * 60 + +v, 0) : 0;
      const vid = yt ? d.source_url + (d.source_url.includes("?") ? "&" : "?") + "t=" + secs : "";
      [vid || d.source_url, d.link, d.url, d.chat, d.image_url].filter(Boolean).forEach(u => lines.push(u));
      const head = [d.site || d.channel, d.timestamp ? T("frame {t}", { t: d.timestamp }) : "", d.colour, d.model].filter(Boolean).join(" · ");
      box.textContent = "";
      if (head) box.appendChild(el("div", "muted", head));
      const t = el("div", "txt"); box.appendChild(t);
      linkify(t, [...new Set(lines)].join("\n") + (d.what ? "\n" + d.what : "") + (d.caption ? "\n" + d.caption : ""));
      if (!lines.length && !d.what && !d.caption) box.textContent = T("The frame's json has no link to its source");
    }).catch(() => { box.textContent = T("Couldn't read the frame's json"); });
  }
  // the owner's review: verdict, use, scores, his words (marks on the frame are annotations: not here, owner 2026-10-10)
  function review(root, f) {
    const sc = f.scores || {}, keys = Object.keys(sc).filter(k => CRIT_RU[k]), use = (f.use || []).map(u => USE_RU[u] ? T(USE_RU[u]) : u);
    if (!(f.verdict || keys.length || f.comment || use.length || (f.good || []).length || (f.bad || []).length)) return;
    const s = sec(root, T("Rating")), top = el("div", "chips");
    if (f.verdict && VERDICT_RU[f.verdict]) top.appendChild(el("span", "chip v " + VERDICT_RU[f.verdict][1], T(VERDICT_RU[f.verdict][0])));
    use.forEach(u => top.appendChild(el("span", "chip", u)));
    if (top.childNodes.length) s.appendChild(top);
    if (keys.length) {
      const g = el("div", "scores");
      keys.forEach(k => { const v = sc[k], r = el("div", "srow"); r.appendChild(el("span", "sk", T(CRIT_RU[k][0]))); const d = el("span", "dots s" + v); d.innerHTML = "<i></i><i></i><i></i>";
        r.appendChild(d); r.appendChild(el("span", "sv", CRIT_RU[k][1][v - 1] ? T(CRIT_RU[k][1][v - 1]) : v)); g.appendChild(r); });
      s.appendChild(g);
    }
    // the old good / bad tags only when there are no scores: the scores were made from them and would say the same twice
    const tags = keys.length ? [] : [...(f.good || []).map(x => "+ " + oldTag(x)), ...(f.bad || []).map(x => "− " + oldTag(x))];
    if (tags.length) { const w = el("div", "chips"); tags.forEach(x => w.appendChild(el("span", "chip", x))); s.appendChild(w); }
    if (f.comment) s.appendChild(el("p", "txt", f.comment));
  }

  // ---------- a plugin's card ----------
  // the file a card stands for: a 3D scene's json, an HTML page (ui/cardfav.js knows the page's path)
  const fileOf = it => it.scene || (window.hyCardFav && hyCardFav.path(it)) || it.src || it.path || "";
  // what the file says, read once (a later render shows it): a scene's objects, lights and cameras; a page's title and pictures
  function read(p, kind) {
    if (FILES.has(p)) return FILES.get(p);
    FILES.set(p, null);
    const url = kind === "html" ? `/lib/${p.split("/").map(enc).join("/")}` : `/file?p=${enc(p)}`;
    fetch(url, { cache: "no-store" }).then(r => r.ok ? r.text() : Promise.reject(r.status)).then(text => {
      let got = {};
      if (kind === "html") {
        const d = new DOMParser().parseFromString(text, "text/html"), dir = p.includes("/") ? p.slice(0, p.lastIndexOf("/") + 1) : "";
        const pics = [...d.querySelectorAll("img[src]")].map(i => i.getAttribute("src")).filter(s => s && !/^(data:|https?:|\/\/)/.test(s))
          .map(s => { try { return decodeURIComponent(new URL(s, "http://x/" + dir).pathname.slice(1)); } catch { return ""; } }).filter(Boolean);
        got = { title: (d.title || "").trim(), elements: d.body ? d.body.querySelectorAll("*").length : 0, pics: [...new Set(pics)] };
      } else { const j = JSON.parse(text); got = j && typeof j === "object" ? j : {}; }
      FILES.set(p, got); render();
    }).catch(() => { FILES.set(p, {}); });
    return null;
  }
  function card(root, id, it, inf) {
    root.textContent = "";
    const kind = it.type === "model3d" ? "3d" : window.hyCardFav && hyCardFav.path(it) ? "html" : it.type, p = fileOf(it);
    if (Array.isArray(inf.spec) && inf.spec.length) inf.spec.forEach(x => x && spec(sec(root, x.title || ""), x.rows || []));   // the plugin's own sections
    else if (kind === "3d" && p) scene(root, read(p, "3d") || {}, it);
    else if (kind === "html" && p) page(root, read(p, "html") || {});
    notes(root, id, "lies on the card");
    more(root, T("file, path"), box => {
      const s = sec(box, T("File")), who = s.appendChild(el("div", "muted", "")); window.hyEdited?.(who, BOARD, id, Object.values(it)); if (p) pathRow(s, p);
    });
    // the plugin's own words (how to open it, what it is, «No plugin» on a stand-in): the body's quiet footnote, always shown, under More
    if (inf.text) { const f = el("p", "ifoot hy-hint pfoot", inf.text); root.appendChild(f); }
  }
  // a 3D scene: its objects (name, what it is made of), its cameras (the card's one marked), its lights; the files it uses
  function scene(root, d, it) {
    const obs = Array.isArray(d.objects) ? d.objects : [], cams = Array.isArray(d.cameras) ? d.cameras : [], lights = Array.isArray(d.lights) ? d.lights : [];
    if (!d.objects && !d.cameras) return;
    const what = o => { const s = o.src || {}; return s.model ? baseName(s.model) : s.path ? baseName(s.path) : s.shape ? String(s.shape) : ""; };
    if (obs.length) {
      const s = sec(root, T("Objects"), obs.length); spec(s, obs.slice(0, 8).map(o => [o.name || T("Object"), what(o) || "·"]));
      if (obs.length > 8) s.appendChild(el("div", "muted", `+${obs.length - 8}`));
    }
    const cur = it.camera || d.active_camera;
    if (cams.length) spec(sec(root, T("Camera"), cams.length > 1 ? cams.length : ""), cams.slice(0, 6).map(c => [c.name || T("Camera"),
      [Number.isFinite(+c.lens) ? T("{lens} mm", { lens: Math.round(c.lens) }) : "", c.id === cur ? T("on the card") : ""].filter(Boolean).join(" · ") || "·"]));
    if (lights.length) spec(sec(root, T("Lights"), lights.length), lights.slice(0, 6).map(l => [l.name || T("Lights"), String(l.type || "")]));
    const files = [...new Set(obs.map(o => { const s = o.src || {}; return s.model ? `3d/models/${s.model}` : s.path || ""; }).filter(Boolean))];   // the 3D plugin's LIB (scene.js)
    if (files.length) { const s = sec(root, T("Source")); files.slice(0, 4).forEach(f => pathRow(s, f)); }
  }
  // an HTML page: its title and size of tree; the library's pictures it shows (a click opens one)
  function page(root, d) {
    if (d.title || d.elements) spec(sec(root, T("Page")), [[T("Title"), d.title || ""], [T("Elements"), d.elements ? String(d.elements) : ""]]);
    sources(root, (d.pics || []).filter(x => byPath.has(x)), T("Uses"));
  }

  window.hyInfoBody = { pic, card };
})();
