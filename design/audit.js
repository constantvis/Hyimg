// The runtime design audit (owner 2026-10-06: «делай ... тесты ui, валидаторы, консистентный design валидатор»): injected into a page of
// the app, it measures the real elements and returns what breaks the design contract (design/contract.json, "runtime"). The tests
// (tests/test_design_audit.py) open every page in both themes and both shapes and keep the known findings in design/baseline.json.
//
//   hyAudit.run(contract.runtime, { page: "board" })  -> [{ check, key, msg }]   key: stable across runs (no coordinates), for the baseline
//   hyAudit.focused()                                -> the ring the focused element shows, or null
//
// What it checks (each a function below):
//   row-radius   the row controls of one panel (sliders, selects, fields, options) have one radius (min(r, h/2), a pill is a pill)
//   bar-height   the controls standing in one bar (dock, selection bar, crumb, editor rails) have one height
//                (Image Studio's foreground and background chips, Photoshop's two squares, stand in one 34 px cell, .ifcol: the cell counts)
//   font         every text is in the contract's families
//   viewport     bars, panels and menus lie inside the window
//   covered      the centre of every control of the chrome is that control (elementFromPoint), also through the board's frame into the
//                library page: «the selection bar under the library» (2026-10-06)
//   hint         key caps on buttons only while ⌘ is held; a label not cut by its button
//   target       what is clicked is at least 24 px both ways
//   marks        a board card's marks (♥, copy, crop, kind pills, note, plugin marks, the colour-grade mark): one height, inset and radius,
//                inside the card, never overlapping; at full size the contract's 24 px plate and 6 px inset
//   lib-pill     the library card's kind pill against the board's marks
//   prose        a paragraph of explanation in body text in a panel, popover, empty state or setting (footnote .hy-hint or ⓘ instead)
//   inset        (opt-in) a control's content off its rounded edges (tests/test_design_inset.py)
//   top-row      (opt-in) the top row across the window's frames: one top, height, gutter, gap, glass, corner and text size; the hint plate
//                and the side panels under it; nothing on a band drawn as the window's edge (tests/test_design_toprow.py)
(() => {
  const vis = el => {
    if (!el || !el.getClientRects().length) return false;
    const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return false;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.display === "none" || s.visibility === "hidden" || +s.opacity < 0.05 || s.scale === "0" || s.contentVisibility === "hidden") return false;
    }
    return true;
  };
  const name = el => {
    if (!el || el.nodeType !== 1) return "?";
    let s = el.tagName.toLowerCase();
    if (el.id) return s + "#" + el.id;
    const cls = [...el.classList].filter(c => !/^(on|sel|hover|open|active|shut|drag|now|jump|faved|dup|cropped|noted|vid|pdf|graded|hy-under)$/.test(c)).slice(0, 3);
    if (cls.length) s += "." + cls.join(".");
    for (const a of ["data-act", "data-tool", "data-mode", "data-a", "data-set", "data-v", "data-view", "data-tab", "data-s"]) if (el.hasAttribute(a)) { s += `[${a}=${el.getAttribute(a)}]`; break; }
    return s;
  };
  const path = el => {   // the element and its two nearest named ancestors: «div#dock > div.seg > button[data-mode=board]»
    const out = [name(el)]; let e = el.parentElement, n = 0;
    while (e && e !== document.body && n < 2) { if (e.id || e.classList.length) { out.unshift(name(e)); n++; if (e.id) break; } e = e.parentElement; }
    return out.join(" > ");
  };
  const R = el => el.getBoundingClientRect();
  const effR = el => { const s = getComputedStyle(el), r = R(el), v = parseFloat(s.borderTopLeftRadius) || 0; return Math.min(v, r.height / 2, r.width / 2); };
  const pill = el => { const r = R(el); return effR(el) >= Math.min(r.height, r.width) / 2 - 0.6; };
  const rkey = el => pill(el) ? "pill" : `${Math.round(effR(el) * 2) / 2}px`;
  const floating = el => {   // the panel a control lies in: the nearest positioned ancestor with a plate (a shadow, a blur or a solid ground)
    for (let e = el.parentElement; e && e !== document.body; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (!/(absolute|fixed|sticky)/.test(s.position)) continue;
      const bg = s.backgroundColor, solid = bg && bg !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(bg);
      if (s.boxShadow !== "none" || s.backdropFilter !== "none" || s.webkitBackdropFilter && s.webkitBackdropFilter !== "none" || solid) return e;
    }
    return null;
  };
  const out = [];
  const add = (check, key, msg) => out.push({ check, key, msg });
  const qa = (sel, root = document) => { try { return [...root.querySelectorAll(sel)]; } catch { return []; } };

  function rowRadius(C) {
    const groups = new Map();
    for (const el of qa(C.row_controls.join(","))) {
      if (!vis(el)) continue;
      const p = floating(el); if (!p) continue;
      if (!groups.has(p)) groups.set(p, []);
      groups.get(p).push(el);
    }
    for (const [p, els] of groups) {
      const by = new Map(); els.forEach(e => { const k = rkey(e); if (!by.has(k)) by.set(k, []); by.get(k).push(e); });
      if (by.size > 1) add("row-radius", path(p), `${by.size} radii in one panel: ` + [...by].map(([k, v]) => `${k} (${[...new Set(v.map(name))].slice(0, 3).join(", ")})`).join("; "));
    }
  }

  function barHeight(C) {
    for (const bar of qa(C.bars.join(","))) {
      if (!vis(bar)) continue;
      const ctl = qa("button, select, input:not([type=range]):not([type=checkbox]):not([type=color]), .seg, .hy-slider", bar)
        .filter(e => vis(e) && !e.parentElement.closest(".seg, .hy-slider, .mk, [role=menu], .menu, .ifcol") && e.closest(C.bars.join(",")) === bar && !e.matches(".sep, .mk, kbd, .hy-slider.sm"));
      const by = new Map(); ctl.forEach(e => { const h = Math.round(R(e).height * 2) / 2; if (!by.has(h)) by.set(h, []); by.get(h).push(e); });
      if (by.size > 1) add("bar-height", path(bar), `${by.size} heights in one bar: ` + [...by].sort((a, b) => b[1].length - a[1].length).map(([h, v]) => `${h}px (${[...new Set(v.map(name))].slice(0, 3).join(", ")})`).join("; "));
    }
  }

  function fonts(C) {
    const ok = new Set(C.font_families.map(f => f.toLowerCase())), seen = new Map();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n = 0;
    while (walker.nextNode() && n < 4000) {
      const t = walker.currentNode; if (!t.nodeValue.trim()) continue;
      const el = t.parentElement; if (!el || el.closest("script, style, iframe, svg, .plg iframe, .dvf")) continue;
      n++;
      const f = getComputedStyle(el).fontFamily.split(",")[0].trim().replace(/^["']|["']$/g, "");
      if (!ok.has(f.toLowerCase()) && !seen.has(f) && vis(el)) seen.set(f, el);
    }
    for (const [f, el] of seen) add("font", `${f} @ ${path(el)}`, `the font «${f}» is not the app's (${C.font_families.slice(0, 2).join(", ")}): ${path(el)}`);
  }

  function viewport(C) {
    const W = innerWidth, H = innerHeight;
    for (const el of qa(C.chrome.join(","))) {
      if (!vis(el)) continue;
      const r = R(el);
      if (r.left < -1 || r.top < -1 || r.right > W + 1 || r.bottom > H + 1)
        add("viewport", path(el), `out of the window by ${Math.round(Math.max(-r.left, -r.top, r.right - W, r.bottom - H))}px: ${path(el)}`);
    }
  }

  const controls = C => qa(C.chrome.join(",")).filter(vis).flatMap(p => qa("button, select, input:not([type=range]):not([type=hidden]), [role=button], [role=menuitem], .hy-slider, a[href]", p))
    .filter((e, i, a) => a.indexOf(e) === i && vis(e) && getComputedStyle(e).pointerEvents !== "none" && !e.disabled);

  // the centre is outside what its scrolling or clipping ancestors show (a chip scrolled out of the filter window): not a control on screen
  const clipped = (el, x, y) => {
    for (let e = el.parentElement; e && e !== document.body && e !== document.documentElement; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.overflow === "visible" && s.overflowX === "visible" && s.overflowY === "visible" && s.clipPath === "none") continue;
      const r = R(e);
      if (x < r.left || x > r.right || y < r.top || y > r.bottom) return true;
    }
    return false;
  };
  function covered(C) {
    const fe = (() => { try { return window.frameElement; } catch { return null; } })();
    const fr = fe ? fe.getBoundingClientRect() : null;
    const OV = C.overlays.join(",");
    for (const el of controls(C)) {
      const r = R(el), x = r.left + r.width / 2, y = r.top + r.height / 2;
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight || clipped(el, x, y)) continue;
      const hit = document.elementFromPoint(x, y);
      if (hit && hit !== el && !el.contains(hit) && !(hit.closest && hit.closest("kbd") && el.contains(hit.closest("kbd")))) {
        if (hit.contains(el) && getComputedStyle(el).pointerEvents === "none") continue;
        if (hit.closest(OV) && !el.closest(OV)) continue;   // an open menu or panel lies over the page's controls: that is what it is for
        add("covered", `${path(el)} under ${path(hit)}`, `${path(el)}: its centre is covered by ${path(hit)}`);
        continue;
      }
      if (fe && fr) {   // through the board's frame: the library page must not lie over it there
        const ph = fe.ownerDocument.elementFromPoint(fr.left + x, fr.top + y);
        if (ph && ph !== fe && !fe.contains(ph)) add("covered", `${path(el)} under (page) ${name(ph)}`, `${path(el)}: under the page's ${path(ph)} (outside the board's frame)`);
      }
    }
  }

  function hints(C) {
    const keys = document.documentElement.classList.contains("hy-keys");
    if (!keys) for (const k of qa("button > kbd")) if (vis(k) && +getComputedStyle(k).opacity > 0.05) add("hint", path(k.parentElement), `a key cap shows on ${path(k.parentElement)} without ⌘ held`);
    for (const el of controls(C)) {
      if (el.matches("input, select, .hy-slider") || !el.textContent.trim()) continue;
      const s = getComputedStyle(el);
      if (s.overflow === "visible" && s.textOverflow !== "ellipsis") {
        const lab = [...el.childNodes].some(n => n.nodeType === 3 && n.nodeValue.trim());
        if (lab && el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) add("hint", `clip ${path(el)}`, `the label of ${path(el)} is wider than its button (${el.scrollWidth} > ${el.clientWidth})`);
      } else if (el.scrollWidth > el.clientWidth + 1 && s.textOverflow !== "ellipsis" && ![...el.querySelectorAll("*")].some(c => getComputedStyle(c).textOverflow === "ellipsis")) {
        add("hint", `clip ${path(el)}`, `the label of ${path(el)} is cut (${el.scrollWidth} > ${el.clientWidth})`);
      }
    }
  }

  function targets(C) {
    for (const el of controls(C)) {
      if (el.closest(C.target_exempt.join(","))) continue;
      const r = R(el);
      if (Math.min(r.width, r.height) < C.target_min - 0.5) add("target", `${path(el)}`, `${path(el)} is ${Math.round(r.width)}×${Math.round(r.height)} px, less than ${C.target_min}`);
    }
  }

  const corner = (m, c) => {
    const r = R(m);
    return { l: r.left - c.left, t: r.top - c.top, r: c.right - r.right, b: c.bottom - r.bottom, w: r.width, h: r.height, rect: r };
  };
  function marks(C) {
    // the size law is the board's own (canvas.html MK): the contract's numbers are the fallback, so a deliberate redesign of the marks
    // moves the expected plate and inset with it, and what stays checked is that they agree, stay inside and never overlap
    const live = (() => { try { return typeof MK === "object" && MK && MK.px ? MK : null; } catch { return null; } })();
    const M = live ? { ...C.marks, height: live.px, inset: live.inset } : C.marks, cards = qa(".it, .plg").filter(vis);
    const kindOf = c => c.classList.contains("plg") ? "plg:" + (c.dataset.type || "?") : (["vid", "pdf"].find(k => c.classList.contains(k)) || (c.querySelector(".mk-kind:not(:empty)") ? "doc" : "pic"));
    for (const c of cards) {
      const cr = R(c); if (cr.right < 0 || cr.bottom < 0 || cr.left > innerWidth || cr.top > innerHeight) continue;
      const ms = [...c.querySelectorAll(".mk")].filter(m => vis(m) && +getComputedStyle(m).opacity > 0.5 && m.closest(".it, .plg") === c);
      if (!ms.length) continue;
      const k = `${kindOf(c)} ${Math.round(cr.width / 40) * 40}px`;
      const g = ms.map(m => ({ m, ...corner(m, cr), cls: [...m.classList].filter(x => x.startsWith("mk-") && !/^mk-(tl|tr|bl|br|on)$/.test(x)).join(".") || "mk" }));
      for (const a of g) if (a.l < -0.5 || a.t < -0.5 || a.r < -0.5 || a.b < -0.5) add("marks", `${k} ${a.cls} outside`, `${k}: the ${a.cls} mark leaves its card`);
      for (let i = 0; i < g.length; i++) for (let j = i + 1; j < g.length; j++) {
        const a = g[i].rect, b = g[j].rect, w = Math.min(a.right, b.right) - Math.max(a.left, b.left), h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (w > 0.5 && h > 0.5) add("marks", `${k} ${g[i].cls}×${g[j].cls} overlap`, `${k}: the ${g[i].cls} and ${g[j].cls} marks overlap (${Math.round(w)}×${Math.round(h)} px)`);
      }
      // the note is a plain dot of its own size (owner 2026-10-06: «before, like the blue dot, it worked perfectly»): it never overlaps,
      // but it is not a plate, so it is left out of the plates' one height, inset and radius
      const plates = g.filter(a => !M.dots.includes(a.cls));
      for (const a of g) if (M.dots.includes(a.cls) && a.h > M.dot + 1) add("marks", `${k} ${a.cls} dot`, `${k}: the ${a.cls} dot is ${Math.round(a.h)} px, the contract's dot is ${M.dot}`);
      if (!plates.length) continue;
      const hs = plates.map(a => a.h), ins = plates.map(a => Math.min(a.t, a.b)), rs = plates.map(a => rkey(a.m));
      if (Math.max(...hs) - Math.min(...hs) > 1) add("marks", `${k} heights`, `${k}: marks of ${[...new Set(hs.map(Math.round))].join(", ")} px on one card (${plates.map(a => a.cls).join(", ")})`);
      if (Math.max(...ins) - Math.min(...ins) > 1) add("marks", `${k} insets`, `${k}: marks ${[...new Set(ins.map(Math.round))].join(", ")} px from the edge on one card (${plates.map(a => a.cls).join(", ")})`);
      if (new Set(rs).size > 1) add("marks", `${k} radii`, `${k}: mark radii ${[...new Set(rs)].join(", ")} on one card`);
      const vbs = parseFloat(getComputedStyle(c).getPropertyValue("--vbs")) || 1;
      if (vbs >= 0.999 && cr.width >= M.full_from) {
        for (const a of plates) {
          if (Math.abs(a.h - M.height) > 1.5) add("marks", `${k} ${a.cls} size`, `${k}: the ${a.cls} mark is ${Math.round(a.h)} px tall, the contract's is ${M.height}`);
          if (Math.abs(Math.min(a.t, a.b) - M.inset) > 1.5 && !c.classList.contains("sel")) add("marks", `${k} ${a.cls} inset`, `${k}: the ${a.cls} mark is ${Math.round(Math.min(a.t, a.b))} px from the edge, the contract's is ${M.inset}`);
        }
      }
    }
  }

  function libPills(C) {
    const M = C.marks;
    const pills = qa(C.library_pills.join(",")).filter(vis);
    const seen = new Set();
    for (const p of pills) {
      const r = R(p), s = getComputedStyle(p), card = p.closest(".card, .it") || p.parentElement;
      const sig = `${Math.round(r.height)}|${rkey(p)}|${s.fontSize}`;
      if (seen.has(sig)) continue; seen.add(sig);
      const cr = R(card), inset = Math.min(r.top - cr.top, cr.bottom - r.bottom);
      const bad = [];
      if (Math.abs(r.height - M.height) > 1) bad.push(`${Math.round(r.height)} px tall (marks ${M.height})`);
      if (!pill(p) && rkey(p) !== `${M.radius_pro}px`) bad.push(`radius ${rkey(p)}`);
      if (s.fontSize !== `${M.font_px}px`) bad.push(`type ${s.fontSize} (marks ${M.font_px}px)`);
      if (Math.abs(inset - M.inset) > 1.5) bad.push(`${Math.round(inset)} px from the card's edge (marks ${M.inset})`);
      if (bad.length) add("lib-pill", `${name(p)} ${sig}`, `the library's ${name(p)} is not a board mark: ${bad.join(", ")}`);
    }
  }

  // inset: no text or icon touches the rounded edge of what holds it (owner 2026-10-06, two crops: «Presets ⌄» flush against its capsule's
  // left edge, «Colo…» cut into an icon: «посмотри, где еще вот такие проблемы есть, где нет пэддинга по сторонам»; the 3D studio's
  // «Off | On» whose chosen thumb touched its track). For every visible capsule, chip, button, select, field or tag with rounded corners:
  //   side    (an option of a choice: C.inset.option) the gap from its content (the text's own lines, its icons; a field's or a select's padding) to its left and right edges, at
  //           least C.inset.capsule px on a capsule (and radius × C.inset.share), C.inset.chip on one lower than C.inset.small_h, C.inset.rect
  //           on a rounded rectangle; an icon alone only has to sit in its middle
  //   cut     a label cut short (ellipsis or clip) that runs into an icon or the edge of its clipping box
  //   nested  a plate inside a plate (the chosen thumb in a choice, a button in a capsule): inset C.inset.nested px on all four sides, the
  //           same top and bottom, its radius the outer one less the inset (concentric)
  // It runs only when asked (opts.only: ["inset"]): tests/test_design_inset.py walks every page with it, strict, both themes, both
  // languages, both shapes
  const alpha = c => { const m = /rgba?\(([^)]+)\)/.exec(c || ""); if (!m) return c && c !== "transparent" ? 1 : 0; const v = m[1].split(/[ ,/]+/).filter(Boolean); return v.length > 3 ? +v[3] : 1; };
  const painted = s => alpha(s.backgroundColor) > 0.04 || s.backgroundImage !== "none" || (parseFloat(s.borderTopWidth) > 0 && alpha(s.borderTopColor) > 0.04 && s.borderTopStyle !== "none");
  const radius = (s, r) => Math.min(parseFloat(s.borderTopLeftRadius) || 0, r.height / 2, r.width / 2);
  const ACT = "button, select, [role=button], [role=menuitem], [role=tab], [role=option], a[href], label, summary, input:not([type=range]):not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=color]), textarea";
  // a content node belongs to the nearest plate above it: the text of a button inside a capsule is the button's, not the capsule's
  const isPlate = (el, s) => { const r = R(el); return radius(s, r) >= 3 && r.height >= 12 && r.height <= 72 && r.width <= 720 && (painted(s) || el.matches(ACT)); };
  function contentOf(plate) {
    const text = [], icons = [];
    const own = n => { for (let e = n.nodeType === 1 ? n.parentElement : n.parentElement; e && e !== plate; e = e.parentElement) { const s = getComputedStyle(e); if (isPlate(e, s) || /(absolute|fixed)/.test(s.position) || e.tagName === "KBD") return false; } return true; };
    const tw = document.createTreeWalker(plate, NodeFilter.SHOW_TEXT);
    while (tw.nextNode()) {
      const t = tw.currentNode, v = t.nodeValue, a = v.search(/\S/); if (a < 0 || !own(t)) continue;
      const host = t.parentElement; if (!vis(host) || host.closest("svg, style, script")) continue;
      const b = v.length - v.split("").reverse().join("").search(/\S/), rg = document.createRange(); rg.setStart(t, a); rg.setEnd(t, b);
      for (const q of rg.getClientRects()) if (q.width > 0.5 && q.height > 0.5) text.push({ q, host });
    }
    for (const e of plate.querySelectorAll("svg, img, canvas, i.ic, .ic:not(button)")) {
      if (e.parentElement && e.parentElement.closest("svg")) continue;
      if (!vis(e) || !own(e)) continue; const q = R(e), pr = R(plate);
      if (e.matches("img, canvas") && q.width >= pr.width * .7 && q.height >= pr.height * .7) continue;   // a thumbnail filling its plate is the plate's picture, not an icon
      if (q.width > 1 && q.height > 1) icons.push(q);
    }
    return { text, icons };
  }
  // the box a text is clipped to (its host or an ancestor up to the plate with overflow other than visible), so a cut label is measured where it shows
  const clipBox = (host, plate) => {
    let box = null;
    for (let e = host; e && e !== plate.parentElement; e = e.parentElement) {
      const s = getComputedStyle(e); if (s.overflowX === "visible" && s.overflow === "visible") continue;
      const r = R(e), b = { left: r.left + (parseFloat(s.borderLeftWidth) || 0), right: r.right - (parseFloat(s.borderRightWidth) || 0) };
      box = box ? { left: Math.max(box.left, b.left), right: Math.min(box.right, b.right) } : b;
    }
    return box;
  };
  const over = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0.5 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0.5;
  // a point inside a rounded box (its corners' circles), 0.5 px of slack
  const inRound = (x, y, r, rad) => {
    if (x < r.left - .5 || x > r.right + .5 || y < r.top - .5 || y > r.bottom + .5) return false;
    const cx = Math.min(Math.max(x, r.left + rad), r.right - rad), cy = Math.min(Math.max(y, r.top + rad), r.bottom - rad);
    return Math.hypot(x - cx, y - cy) <= rad + .5;
  };
  function inset(C) {
    const I = C.inset, seen = new Set();
    // the app's slider: its line stands inside the track's round ends at any value, 0 and the end too (owner 2026-10-06: at 0 a thin
    // crescent «(» stuck out of the row's rounded edge, the line cut by the curve)
    for (const w of qa(".hy-slider:not(.sm)")) {
      const t = w.querySelector(":scope > .hy-slider-t"); if (!t || !vis(w) || !vis(t)) continue;
      const r = R(w), q = R(t), rad = radius(getComputedStyle(w), r);
      if ([[q.left, q.top], [q.right, q.top], [q.left, q.bottom], [q.right, q.bottom]].some(([x, y]) => !inRound(x, y, r, rad)) && !seen.has("sl" + name(w))) {
        seen.add("sl" + name(w)); add("inset", `slider-line ${path(w)}`, `${path(w)}: its line at ${Math.round((q.left - r.left) * 10) / 10} px is cut by the round end (radius ${Math.round(rad)})`);
      }
    }
    for (const el of qa("body *")) {
      if (el.closest("svg, #items .it, #items .plg .ifr, iframe, canvas, .hy-slider, [data-hy-inset=off]")) continue;
      if (el.matches(".mk, .mk *, kbd, .st, .hy-slider *")) continue;
      const s = getComputedStyle(el); if (!isPlate(el, s) || !vis(el)) continue;
      const r = R(el); if (r.right < 0 || r.bottom < 0 || r.left > innerWidth || r.top > innerHeight) continue;
      const rad = radius(s, r), capsule = rad >= r.height / 2 - 0.6, h = r.height, key = name(el);
      // an option of a choice (a button beside others on a painted track) fills its share of the row: its words keep I.option px
      const par = el.parentElement, option = el.matches("button") && par && painted(getComputedStyle(par)) && [...par.children].filter(c => c.matches("button")).length >= 2;
      const need = option ? I.option : capsule ? Math.max(h < I.small_h ? I.chip : I.capsule, rad * I.share) : (h < I.small_h ? I.chip_rect : I.rect);
      const sig = `${key}|${Math.round(h)}|${capsule}`;
      // a field or a select: its text sits at its padding
      if (el.matches("input, select, textarea")) {
        if (r.width <= h + 2) continue;   // a round well or a search folded to its icon: no text to keep off the edge
        const pl = (parseFloat(s.paddingLeft) || 0) + (parseFloat(s.borderLeftWidth) || 0), pr = (parseFloat(s.paddingRight) || 0) + (parseFloat(s.borderRightWidth) || 0);
        if ((painted(s)) && Math.min(pl, el.matches("select") ? pl : pr) < need - 0.5 && !seen.has(sig)) { seen.add(sig); add("inset", `side ${path(el)}`, `${path(el)}: its text is ${Math.round(Math.min(pl, pr) * 10) / 10} px from its rounded edge, at least ${Math.round(need * 10) / 10} (${Math.round(r.width)}×${Math.round(h)}, radius ${Math.round(rad)})`); }
        continue;
      }
      const { text, icons } = contentOf(el);
      // a plate inside this one: the chosen thumb of a choice, a button in a capsule (only when this one shows: a track)
      if (painted(s)) for (const c of el.children) {
        const cs = getComputedStyle(c); if (!vis(c) || !(alpha(cs.backgroundColor) > 0.04 || cs.backgroundImage !== "none") || c.matches("kbd, .mk, .dot, .badge")) continue;
        const q = R(c); if (q.height < 12 || q.width < 12 || q.height < h * 0.5) continue;
        const t = q.top - r.top, b = r.bottom - q.bottom, l = q.left - r.left, rr = r.right - q.right;
        if (Math.min(t, b) < -0.5 || Math.min(l, rr) < -0.5) continue;   // sticking out on purpose (a pip, a handle)
        const crad = radius(cs, q), want = Math.max(0, rad - Math.min(t, b));
        if (Math.min(t, b, l, rr) < I.nested - 0.5 && !seen.has("n" + sig)) { seen.add("n" + sig); add("inset", `nested ${path(c)} in ${name(el)}`, `${path(c)} touches its track ${name(el)}: ${[t, rr, b, l].map(v => Math.round(v * 10) / 10).join(" / ")} px (top right bottom left), at least ${I.nested} on every side`); }
        else if (Math.abs(t - b) > 1.5 && !seen.has("v" + sig)) { seen.add("v" + sig); add("inset", `nested-v ${path(c)} in ${name(el)}`, `${path(c)} sits off the middle of ${name(el)}: ${Math.round(t)} px above, ${Math.round(b)} below`); }
        else if (crad > 0.5 && Math.abs(crad - want) > 2 && !seen.has("c" + sig)) { seen.add("c" + sig); add("inset", `concentric ${path(c)} in ${name(el)}`, `${path(c)}: radius ${Math.round(crad)}, concentric with ${name(el)} would be ${Math.round(want)} (its ${Math.round(rad)} less the ${Math.round(Math.min(t, b))} px inset)`); }
      }
      if (!text.length && !icons.length) continue;
      // a label cut short runs into an icon, or its clip is flush with the edge
      for (const { q, host } of text) {
        const cb = clipBox(host, el); if (!cb) continue;
        const shown = { left: Math.max(q.left, cb.left), right: Math.min(q.right, cb.right), top: q.top, bottom: q.bottom };
        if (q.right > cb.right + 0.5 || q.left < cb.left - 0.5) {
          if (icons.some(i => over(shown, i)) && !seen.has("x" + sig)) { seen.add("x" + sig); add("inset", `cut ${path(el)}`, `${path(el)}: its label «${host.textContent.trim().slice(0, 24)}» is cut and runs into an icon`); }
        }
      }
      for (const { q, host } of text) for (const i of icons) if (over(q, i) && !host.closest("svg") && !seen.has("o" + sig)) {
        const cb = clipBox(host, el), sq = cb ? { ...q, left: Math.max(q.left, cb.left), right: Math.min(q.right, cb.right) } : q;
        if (sq.right - sq.left > 0.5 && over(sq, i)) { seen.add("o" + sig); add("inset", `over ${path(el)}`, `${path(el)}: its label «${host.textContent.trim().slice(0, 24)}» lies over an icon`); }
      }
      const rects = text.map(t => { const cb = clipBox(t.host, el); return cb ? { left: Math.max(t.q.left, cb.left), right: Math.min(t.q.right, cb.right) } : t.q; }).concat(icons);
      const L = Math.min(...rects.map(q => q.left)) - r.left, Rr = r.right - Math.max(...rects.map(q => q.right));
      // an icon alone, or one glyph in a round chip («?»): in the middle, and not on the edge; several icons alone are a row of their own
      if (!text.length && (icons.length > 1 || !el.matches(ACT) || el.querySelector("input, select, textarea, button"))) continue;   // a bar of buttons (a label round a field) is measured by its controls
      if (!text.length || (capsule && r.width <= h + 2)) {
        if ((Math.abs(L - Rr) > 2.5 || Math.min(L, Rr) < 1.5) && !seen.has("i" + sig)) { seen.add("i" + sig); add("inset", `icon ${path(el)}`, `${path(el)}: its icon is ${Math.round(L * 10) / 10} px from the left edge, ${Math.round(Rr * 10) / 10} from the right`); }
        continue;
      }
      // the side the content starts from must keep its inset; a capsule or chip keeps both (its label is centred or the row is filled)
      const side = Math.min(L, Rr), fill = (r.width - (L + Rr)) / r.width;
      // a bare row (no ground, small corners: a folder's title line) lines its words up with the panel's column, it is not a capsule;
      // a button with a ground on hover (no ground now, corners from 6 px) is measured as the plate it becomes
      if (!capsule && !painted(s) && !(el.matches("button, select, [role=button]") && rad >= 6)) continue;
      const check = side;
      if (check < need - 0.5 && !seen.has(sig)) { seen.add(sig); add("inset", `side ${path(el)}`, `${path(el)}: content ${Math.round(L * 10) / 10} px from the left edge and ${Math.round(Rr * 10) / 10} from the right, at least ${Math.round(need * 10) / 10} (${Math.round(r.width)}×${Math.round(h)}, radius ${Math.round(rad)}${capsule ? ", a capsule" : ""}; fill ${Math.round(fill * 100)}%)`); }
    }
  }

  // top-row (owner 2026-10-07: «breadcrumb area тоже разношерстная»; in the image studio the library button, the crumb and the hint
  // under them crossed the ruler at the window's left edge, the group's title after the crumb was shorter and another shade, the 3D
  // scene's too): run from the window's page, it reads the row across the frames of one origin (the library page, the board in it, the
  // image studio in that) in the window's coordinates. The row: the plates (a blur, or a shadow over a ground) whose top is within
  // C.top_row.band px of the window's top and no taller than max_h, outermost ones only, on screen, outside the skipped layers (the
  // board's world, menus, notes). Each is top px down and height px tall, gutter px from the window's sides; neighbours (nearer than
  // near) gap px apart; one glass among the translucent ones, one shadow and one corner; a plate wider than tall has text px words. The
  // hint plate and the side panels start under px down, the hint gutter px in, as tall as the row and of its look. Nothing of the row
  // lies on a band a page draws as the window's edge (window.hyEdges(): the image studio's rulers).
  function topRow(C) {
    const T = C.top_row; if (!T) return;
    const tol = T.tol, skip = T.skip.join(","), docs = [], W = innerWidth, H = innerHeight;
    const shown = (el, win) => {
      if (!el.getClientRects().length) return false;
      for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
        const s = win.getComputedStyle(e);
        if (s.display === "none" || s.visibility === "hidden" || +s.opacity < 0.05 || s.contentVisibility === "hidden") return false;
      }
      return true;
    };
    (function walk(win, ox, oy) {
      let d; try { d = win.document; } catch { return; }
      if (!d || !d.body) return;
      docs.push({ win, d, ox, oy });
      for (const f of d.querySelectorAll("iframe")) {
        if (skip && f.closest(skip)) continue;
        const r = f.getBoundingClientRect(); if (r.width < W * 0.5 || !shown(f, win)) continue;
        let w; try { w = f.contentWindow; void w.document; } catch { continue; }
        walk(w, ox + r.left + f.clientLeft, oy + r.top + f.clientTop);
      }
    })(window, 0, 0);
    const alphaOf = c => {
      const m = /rgba?\(([^)]+)\)|color\(srgb ([^)]+)\)/.exec(c || ""); if (!m) return c && c !== "transparent" ? 1 : 0;
      const v = (m[1] || m[2]).split(/[ ,/]+/).filter(Boolean); return v.length > 3 ? +v[3] : 1;
    };
    const glassOf = s => s.backdropFilter && s.backdropFilter !== "none" || s.webkitBackdropFilter && s.webkitBackdropFilter !== "none";
    const plateLike = s => glassOf(s) || (s.boxShadow !== "none" && !/^inset/.test(s.boxShadow) && alphaOf(s.backgroundColor) > 0.3);
    const box = (el, D, r) => ({ el, D, s: D.win.getComputedStyle(el), x: r.left + D.ox, y: r.top + D.oy, w: r.width, h: r.height,
      r: r.right + D.ox, b: r.bottom + D.oy });
    const all = [];
    for (const D of docs) {
      for (const el of D.d.querySelectorAll("body *")) {
        if (el.tagName === "IFRAME" || el.tagName === "CANVAS" || (skip && el.closest(skip))) continue;
        const r = el.getBoundingClientRect(), p = box(el, D, r);
        if (p.y > T.band || p.h > T.max_h || p.h < 16 || p.w < 16) continue;
        if (p.b <= 0 || p.r <= 0 || p.x >= W || p.y >= H) continue;   // off the screen: nothing is seen
        if (!plateLike(p.s) || !shown(el, D.win)) continue;
        all.push(p);
      }
    }
    const row = all.filter(p => !all.some(q => q !== p && q.D === p.D && q.el.contains(p.el)));   // a plate's buttons are its parts
    const nm = p => path(p.el), near = (a, b) => Math.abs(a - b) <= tol, px = v => Math.round(v * 10) / 10;
    const radius = p => Math.min(parseFloat(p.s.borderTopLeftRadius) || 0, p.h / 2, p.w / 2);
    const rk = p => radius(p) >= Math.min(p.h, p.w) / 2 - 0.6 ? "pill" : `${Math.round(radius(p))}px`;
    const edges = [];
    for (const D of docs) {
      try {
        const f = D.win.hyEdges; if (typeof f !== "function") continue;
        for (const e of f() || []) edges.push({ x: e.left + D.ox, y: e.top + D.oy, r: e.right + D.ox, b: e.bottom + D.oy });
      } catch {}
    }
    const onEdge = p => edges.find(e => Math.min(p.r, e.r) - Math.max(p.x, e.x) > 0.5 && Math.min(p.b, e.b) - Math.max(p.y, e.y) > 0.5);
    const band = e => `${Math.round(e.x)}–${Math.round(e.r)} × ${Math.round(e.y)}–${Math.round(e.b)}`;
    const fail = (key, msg) => add("top-row", key, msg);
    for (const p of row) {
      if (!near(p.h, T.height)) fail(`height ${nm(p)}`, `${nm(p)} is ${px(p.h)} px tall, the row's plates ${T.height}`);
      if (!near(p.y, T.top)) fail(`top ${nm(p)}`, `${nm(p)} stands ${px(p.y)} px from the window's top, the row ${T.top}`);
      if (p.x < T.gutter - tol || p.r > W - T.gutter + tol)
        fail(`gutter ${nm(p)}`, `${nm(p)} at ${Math.round(p.x)}–${Math.round(p.r)} px: less than ${T.gutter} px from the window's side (${W} px)`);
      const e = onEdge(p); if (e) fail(`edge ${nm(p)}`, `${nm(p)} lies on the window's edge band ${band(e)} (a ruler)`);
      if (p.w > p.h * 1.2) {   // a plate of words (a round button's glyph is an icon)
        const sizes = new Set(), tw = p.D.d.createTreeWalker(p.el, NodeFilter.SHOW_TEXT);
        while (tw.nextNode()) {
          const t = tw.currentNode;
          if (t.nodeValue.trim() && t.parentElement && shown(t.parentElement, p.D.win)) sizes.add(parseFloat(p.D.win.getComputedStyle(t.parentElement).fontSize));
        }
        const main = sizes.size ? Math.max(...sizes) : null;
        if (main != null && Math.abs(main - T.text) > 0.25) fail(`text ${nm(p)}`, `${nm(p)}: its words are ${main} px, the row's ${T.text}`);
      }
    }
    // neighbours: the gap between two plates side by side
    const byX = [...row].sort((a, b) => a.x - b.x);
    for (let i = 1; i < byX.length; i++) {
      const a = byX[i - 1], b = byX[i], g = b.x - a.r;
      if (g < T.near && !near(g, T.gap)) fail(`gap ${nm(a)} | ${nm(b)}`, `${nm(a)} and ${nm(b)} are ${px(g)} px apart, the row's gap ${T.gap}`);
    }
    // one look: the translucent glass plates' ground and blur (a solid action, «Save» or «New board», and a pressed or open plate show
    // their state), every plate's shadow and corner
    const odd = (list, key, what) => {
      const by = new Map(); list.forEach(p => { const k = key(p); if (!by.has(k)) by.set(k, []); by.get(k).push(p); });
      if (by.size < 2) return;
      const most = [...by].sort((a, b) => b[1].length - a[1].length)[0][0], cut = v => String(v).slice(0, 70);
      for (const [k, ps] of by) if (k !== most) for (const p of ps) fail(`${what} ${nm(p)}`, `${nm(p)}: its ${what} «${cut(k)}» is not the row's «${cut(most)}»`);
    };
    const glass = row.filter(p => glassOf(p.s) && alphaOf(p.s.backgroundColor) < 0.99 && !p.el.matches("[aria-pressed=true], [aria-expanded=true]"));
    odd(glass, p => p.s.backgroundColor, "ground"); odd(glass, p => p.s.backdropFilter || p.s.webkitBackdropFilter, "blur");
    odd(row, p => p.s.boxShadow, "shadow"); odd(row, rk, "corner");
    // a note (ui/toasts.js) stands in the row at its centre, over a centred title for its few seconds (owner 2026-10-09: «на уровне
    // breadcrumbs, поверх них, по центру экрана»), never over the crumb or the plates at the sides
    const mid = q => Math.abs((q.x + q.r) / 2 - innerWidth / 2) < innerWidth / 4;   // a title in the middle half (the 3D scene's), not the sides' plates
    const meet = (p, q) => !mid(q) && Math.min(p.r, q.r) - Math.max(p.x, q.x) > 0.5 && Math.min(p.b, q.b) - Math.max(p.y, q.y) > 0.5;
    for (const D of docs) {
      for (const el of D.d.querySelectorAll(T.toasts.join(","))) {
        if (!shown(el, D.win)) continue;
        const t = box(el, D, el.getBoundingClientRect()), p = row.find(q => meet(t, q));
        if (p) fail(`toast over ${nm(p)}`, `a note at ${band(t)} covers ${nm(p)}: notes stand at the row's centre`);
      }
    }
    // the mode's hint plate under the row, and the side panels
    const look = glass[0] || row[0];
    for (const D of docs) {
      for (const el of D.d.querySelectorAll(T.hint.join(","))) {
        if (!shown(el, D.win)) continue;
        const p = box(el, D, el.getBoundingClientRect()), s = p.s;
        if (!near(p.y, T.under)) fail(`hint top ${nm(p)}`, `${nm(p)} stands ${Math.round(p.y)} px down, under the row ${T.under}`);
        if (!near(p.h, T.height)) fail(`hint height ${nm(p)}`, `${nm(p)} is ${Math.round(p.h)} px tall, the row's plates ${T.height}`);
        if (p.x < T.gutter - tol) fail(`hint gutter ${nm(p)}`, `${nm(p)} starts ${Math.round(p.x)} px from the window's left side, the row ${T.gutter}`);
        const e = onEdge(p); if (e) fail(`hint edge ${nm(p)}`, `${nm(p)} lies on the window's edge band ${band(e)} (a ruler)`);
        if (look && (s.backgroundColor !== look.s.backgroundColor || s.boxShadow !== look.s.boxShadow))
          fail(`hint look ${nm(p)}`, `${nm(p)}: its ground or shadow is not the row's (${nm(look)})`);
        if (look && rk(p) !== rk(look)) fail(`hint corner ${nm(p)}`, `${nm(p)}: its corner ${rk(p)} is not the row's ${rk(look)}`);
      }
      for (const el of D.d.querySelectorAll(T.panels.join(","))) {
        if (!shown(el, D.win) || (skip && el.closest(skip))) continue;
        const r = el.getBoundingClientRect(), y = r.top + D.oy;
        if (r.height > 40 && !near(y, T.under)) fail(`panel ${path(el)}`, `${path(el)} starts ${px(y)} px down, under the row ${T.under}`);
      }
    }
  }

  const CHECKS = { "row-radius": rowRadius, "bar-height": barHeight, font: fonts, viewport, covered, hint: hints, target: targets, marks,
    "lib-pill": libPills, inset, "top-row": topRow };
  const OPT_IN = new Set(["inset", "top-row"]);   // run only when asked by name
  // prose (owner 2026-10-06, the 3D studio's Scene panel: «Вот эти комментарии никто не читает ... микро шрифтом, как Apple обычно делает»):
  // a visible paragraph in the chrome or an overlay of more than C.prose.max_words words in body text (larger than C.prose.hint_px) that is
  // not a footnote (.hy-hint); a footnote of more than C.prose.hint_max_words (about two short lines). Key caps are not words; the
  // person's and the agents' own words (C.prose.skip) are content, not explanation. scripts/validate.py panel-prose is its static half.
  function prose(C) {
    const P = C.prose; if (!P) return;
    const skip = P.skip.join(","), hintSel = P.hint_classes.map(c => "." + c).join(","), seen = new Set();
    const INL = /^(B|STRONG|I|EM|A|CODE|BR|U|S|SPAN|SMALL|MARK)$/;
    for (const root of qa([...C.chrome, ...C.overlays].join(",")).filter(vis)) for (const el of [root, ...qa("*", root)]) {
      if (seen.has(el)) continue; seen.add(el);
      if (el.closest("svg, button, select, option, kbd, script, style, textarea") || (skip && el.closest(skip)) || !vis(el)) continue;
      const own = [...el.childNodes].filter(n => n.nodeType === 3 || (n.nodeType === 1 && INL.test(n.tagName) && getComputedStyle(n).display.startsWith("inline")));
      if (!own.some(n => n.nodeType === 3 && n.nodeValue.trim())) continue;
      const text = own.map(n => n.textContent).join(" "), words = text.split(/\s+/).filter(w => /[0-9A-Za-zА-Яа-яЁё]/.test(w)).length;
      if (words <= P.max_words) continue;
      const fs = parseFloat(getComputedStyle(el).fontSize), hint = el.closest(hintSel);
      if (hint ? words <= P.hint_max_words : fs <= P.hint_px) continue;
      add("prose", path(el), `${path(el)}: ${hint ? "a footnote" : `${fs} px body text`} of ${words} words «${text.trim().replace(/\s+/g, " ").slice(0, 60)}…»: not key, delete it; key, one .hy-hint line; unclear, a ⓘ (.hy-info)`);
    }
  }
  CHECKS.prose = prose;
  window.hyAudit = {
    run(C, opts = {}) {
      out.length = 0;
      for (const [k, f] of Object.entries(CHECKS)) {
        if (opts.only ? !opts.only.includes(k) : OPT_IN.has(k)) continue;
        try { f(C); } catch (e) { add("audit-error", k, `${k}: ${e && e.message}`); }
      }
      const seen = new Set();
      return out.filter(v => { const s = v.check + "|" + v.key; if (seen.has(s)) return false; seen.add(s); return true; });
    },
    focused() {
      const el = document.activeElement; if (!el || el === document.body) return null;
      const s = getComputedStyle(el);
      const ring = s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0 ? `outline ${s.outlineWidth} ${s.outlineStyle}` : null;
      return { el: path(el), ring, shadow: s.boxShadow, tag: el.tagName.toLowerCase(), type: el.type || "" };
    },
    shadowOf(el) { return getComputedStyle(el).boxShadow; },
    // what the inset check measures on one element: its insets to its content, for the before/after report
    insetOf(sel) { const el = typeof sel === "string" ? document.querySelector(sel) : sel; if (!el) return null; const r = R(el), { text, icons } = contentOf(el), q = text.map(t => t.q).concat(icons); if (!q.length) return null;
      return { l: Math.round((Math.min(...q.map(x => x.left)) - r.left) * 10) / 10, r: Math.round((r.right - Math.max(...q.map(x => x.right))) * 10) / 10, w: Math.round(r.width), h: Math.round(r.height) }; },
    path, name, vis,
  };
})();
