// The Text tool and a text's box, as Figma's text (owner 2026-10-11, with a screenshot of a pasted text running as one endless line across
// the board: «во-первых я хочу иметь выбор text tool по кнопке "T". А во-вторых хочу не просто возможность нажать и писать, а в том числе
// выбрать ширину и высоту блока, то есть нажать мышку и тянуть, пока не отпущу ... а также редактировать ширину и высоту, если нужно, и
// иметь настройку сбросить фиксирование, если нужно, в этом тултипе сверху, при этом фиксированность появляется, когда я тянуть начинаю»).
//   T         the Text tool (ui/boardkeys.js): a text cursor over the board and the Hint bar. A click on the empty board, or on a picture,
//             makes a text there in Auto width, as a double click does; a press and drag draws a box, and the text made on release is
//             a Fixed size box of exactly that width and height, its field open; a click on a text writes in it. One text made, the
//             tool is done and the board selects again, as in Figma. Esc or V leave it; any other key leaves it and does its own work
//   the bar   over one selected text (canvas.html renderHandles calls bar()): H1 H2 | A− A+ and the size's name | the box: Auto width,
//             Auto height, Fixed size (<hy-segmented variant=micro>) and Reset. Reset gives back what the text was before anyone
//             sized it: a heading Auto width, a document (a title and lines under it) Auto height at its width, because a document's
//             paragraphs in Auto width would each run as one endless line, the very thing the owner showed. The size's name and every
//             part keep their width, so the bar never changes width under the pointer (DESIGN.md «Полоса под указателем не двигается»)
//   steps     one undo step per switch, named by the box it gives («Auto width»); a strip's drag is «Text box size» (stepName, asked by
//             ui/boarddock.js)
// The box lives on the item (ui/textdoc.js mode: tm, tw, th); the strips and the drags are ui/textdoc.js resize and edges.
//   hyTextBox.tool(on = true)        the Text tool on or off; hyTextBox.on: is it on
//   hyTextBox.bar(h, id, r, it)      the bar of one selected text, with its strips
//   hyTextBox.set(id, m)             m "w", "h", "f" or "reset": that box, one undo step (nothing when it is that already)
//   hyTextBox.stepName(a, b)         a step's name between two states of one text, "" when it is not about its box
(() => {
  if (window.hyTextBox) return;
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/^step::/, ""));
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const KINDS = [["w", "textAutoW", "Auto width"], ["h", "textAutoH", "Auto height"], ["f", "textFixed", "Fixed size"]];
  const STEP = { w: "step::Auto width", h: "step::Auto height", f: "step::Fixed size" };
  const natural = it => (hyTextDoc.isDoc(it) ? "h" : "w");
  const HINT = [{ id: "make", keys: [], t: "Click: a text · drag: a text box", stay: true, auto: false }, { id: "done", keys: ["escape"], also: ["v"], t: "Done" }];
  let on = false, kh = null, draw = null;

  // ---- the tool -------------------------------------------------------------------------------------------------------------------
  function tool(want = true) {
    if (want ? on || (window.hyPrevNo && hyPrevNo()) : !on) return;   // a version being looked at takes no new work (ui/boardkeys.js)
    on = want; stage.classList.toggle("ttool", on);
    if (kh) { kh.hide(); kh = null; }
    if (draw) { draw.box.remove(); draw = null; }
    if (on && window.hyHint) kh = hyHint("texttool", document.getElementById("dock") || stage, { place: "top", items: HINT });
  }
  const busy = () => (typeof MODES !== "undefined" && MODES && MODES.open !== "board") || (typeof cropState !== "undefined" && !!cropState)
    || !!(window.hyAnnot && hyAnnot.state && hyAnnot.state.tool);
  // the bar's box buttons first: a press, as the bar's other buttons (the board's pointer capture would take their click)
  addEventListener("pointerdown", e => {
    const b = e.button === 0 && e.target.closest && e.target.closest("#handles .tidy [data-tmode]"); if (!b) return;
    e.preventDefault(); e.stopImmediatePropagation(); if (!b.disabled && sel.size === 1) set([...sel][0], b.dataset.tmode);
  }, true);
  document.addEventListener("hy-change", e => {   // the arrow keys on the focused segments
    if (e.target.matches && e.target.matches("#handles hy-segmented.tbox") && sel.size === 1) set([...sel][0], e.detail.value);
  });
  addEventListener("pointerdown", e => {
    if (!on) return;
    if (busy()) { tool(false); return; }
    if (e.button !== 0 || e.ctrlKey || (typeof space !== "undefined" && space)) return;   // the middle button and Space pan, ⌃ is the menu
    if (!e.target.closest || !e.target.closest("#stage")) return;
    if (onChrome(e)) { tool(false); return; }   // the dock, the top row: their own work, the tool is done
    if (e.target.closest(".tidy, textarea, input")) return;
    e.preventDefault(); e.stopImmediatePropagation();
    if (typeof openEditor !== "undefined" && openEditor) openEditor(true);
    if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
    const tx = e.target.closest(".tx:not(.editing)");
    if (tx && board.items[tx.dataset.id]) { tool(false); editText(tx.dataset.id, null, caretAt(e), e); return; }   // as Figma: write in it
    const box = document.createElement("div"); box.id = "ttbox"; box.style.display = "none"; document.body.appendChild(box);
    draw = { x: e.clientX, y: e.clientY, box, moved: false };
    try { stage.setPointerCapture(e.pointerId); } catch { /* the pointer is gone */ }
  }, true);
  addEventListener("pointermove", e => {
    const d = draw; if (!d) return; e.stopImmediatePropagation();
    const w = Math.abs(e.clientX - d.x), h = Math.abs(e.clientY - d.y); if (!d.moved && w < 4 && h < 4) return; d.moved = true;
    Object.assign(d.box.style, { display: "block", left: Math.min(d.x, e.clientX) + "px", top: Math.min(d.y, e.clientY) + "px", width: w + "px", height: h + "px" });
  }, true);
  addEventListener("pointerup", e => {
    const d = draw; if (!d) return; e.stopImmediatePropagation(); draw = null; d.box.remove(); tool(false);
    const a = toWorld(d.x, d.y); if (!d.moved) { hyTextDoc.create(a); return; }   // a click: Auto width, as a double click
    const b = toWorld(e.clientX, e.clientY);
    hyTextDoc.create({ x: Math.min(a.x, b.x), y: Math.min(a.y, b.y) }, { w: Math.abs(b.x - a.x), h: Math.abs(b.y - a.y) });
  }, true);
  addEventListener("pointercancel", () => { if (draw) { draw.box.remove(); draw = null; } }, true);
  addEventListener("keydown", e => {
    if (!on || hyTyping(e) || ["Shift", "Alt", "Meta", "Control", "CapsLock", " "].includes(e.key)) return;
    const k = (e.key || "").toLowerCase(), plain = !e.metaKey && !e.ctrlKey && !e.altKey;
    if (e.key === "Escape" || (plain && (e.code === "KeyV" || k === "v" || k === "м"))) { e.preventDefault(); e.stopImmediatePropagation(); tool(false); return; }
    if (plain && (e.code === "KeyT" || k === "t" || k === "е")) return;   // T again: the tool stays
    tool(false);   // any other key: the tool is done, the key does its own work on the board
  }, true);

  // ---- the bar over one text ------------------------------------------------------------------------------------------------------
  function bar(h, id, r, n) {
    hyTextDoc.edges(h, id, r, n, handlesOn(r.w * cam.z, r.h * cam.z));   // its strips: the sides its width, top and bottom its height
    const t = document.createElement("div"), cur = hyTextSize.cur(n), at = hyTextSize.near(n), m = hyTextDoc.mode(n); t.className = "tidy tsz";
    // H1 and H2 jump to the two headlines, the small and big A step one size down or up through all five, as on a note (owner
    // 2026-09-30), all in the text's own scale (ui/textsize.js, 2026-10-10); a size made by the corner lights no name (owner 2026-10-06)
    t.innerHTML = `<button class="hx ${cur === 4 ? "on" : ""}" data-tsize="4" title="${esc(T("Big heading"))}">H1</button>`
      + `<button class="hx ${cur === 3 ? "on" : ""}" data-tsize="3" title="${esc(T("Heading"))}">H2</button><span class="sep"></span>`
      + `<button class="fz" data-tsize="${Math.max(0, cur >= 0 ? at - 1 : at)}" title="${esc(T("Smaller text"))}" ${cur === 0 ? "disabled" : ""}><span style="font-size:11px">A</span></button>`
      + `<button class="fz" data-tsize="${Math.min(4, cur >= 0 ? at + 1 : at)}" title="${esc(T("Bigger text"))}" ${cur === 4 ? "disabled" : ""}><span style="font-size:18px">A</span></button>`
      + `<span class="tsl tsn">${TSIZE.map((z, i) => `<span${i === cur ? ' class="on"' : ""}>${esc(T(z.name))}</span>`).join("")}</span><span class="sep"></span>`
      + `<hy-segmented class="tbox" variant="micro" value="${m}" label="${esc(T("Text box"))}">`
      + KINDS.map(([v, ic, w]) => `<button value="${v}" data-tmode="${v}" title="${esc(T(w))}" aria-label="${esc(T(w))}">${hyIcon(ic, 12, 2)}</button>`).join("") + `</hy-segmented>`
      + `<button class="ic tbr" data-tmode="reset" title="${esc(T("Reset the box: a heading grows with its words, a document wraps at its width"))}"`
      + ` aria-label="${esc(T("Reset the box"))}" ${m === natural(n) ? "disabled" : ""}>${hyIcon("reset", 15, 2)}</button>`;
    const below = (r.y - cam.y) * cam.z < 56;
    Object.assign(t.style, { left: r.x + r.w / 2 + "px", top: (below ? r.y + r.h : r.y) + "px" });
    if (below) t.style.transform = "scale(calc(1 / var(--z))) translate(-50%, 12px)";
    h.appendChild(t);
  }

  // ---- switching the box, its undo step and the step's name ----------------------------------------------------------------------
  const NAMED = new Map(), key = (a, b) => JSON.stringify([a.tm, a.tw, a.th, b.tm, b.tw, b.th, b.fs]);
  function set(id, m) {
    const it = board.items[id]; if (!it || it.type !== "text") return;
    const before = snap(), was = hyTextDoc.mode(it), a = { ...it }, doc = hyTextDoc.isDoc(it);
    if (m === "reset") m = natural(it);
    // the width it shows now; a document out of Auto width wraps at a document's width, not at its longest line
    const width = () => Math.round(was !== "w" ? it.tw || hyTextDoc.autoW(it) : doc ? hyTextDoc.autoW(it, it.w) : it.w);
    if (m === "w") { delete it.tw; delete it.th; if (doc) it.tm = "w"; else delete it.tm; }
    else if (m === "h") { it.tw = width(); delete it.th; if (doc) delete it.tm; else it.tm = "h"; }
    else if (m === "f") { const w = width(); it.th = Math.round(it.h); it.tw = w; it.tm = "f"; }
    else return;
    if (JSON.stringify(a) === JSON.stringify(it)) return;
    NAMED.set(key(a, it), STEP[m]); if (NAMED.size > 200) NAMED.delete(NAMED.keys().next().value);
    commit(before);
  }
  function stepName(a, b) {
    if (!a || !b || a.type !== "text" || b.type !== "text" || a.text !== b.text) return "";
    const box = o => JSON.stringify([o.tm, o.tw, o.th]); if (box(a) === box(b)) return "";
    const n = NAMED.get(key(a, b)); if (n) return T(n);
    return a.fs === b.fs ? T("step::Text box size") : "";   // a strip's drag; a corner scales the type: the board's «Size»
  }
  window.hyTextBox = { tool, bar, set, stepName, get on() { return on; } };
})();
