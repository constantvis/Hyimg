// The server's key on a board's card on Home. Until 2026-10-08 it was only in the card's «…» menu. The owner asked for it on the cover
// («когда я навожу на тамбнейл, кнопки запустить либо остановить», in the list «по правую сторону от тайтла»), then set its look:
// «Кнопки остановить и плей должны находиться в правом нижнем углу. И они должны быть тоже прозрачные. И кнопка сама не должна быть
// зеленой или красной, только сам символ. Плей можно сделать и не зеленым, а вот остановить — красным, сам символ». A classic script
// (Home loads no modules):
//   hyHomeServer.key(p, where)   the key's markup: "card" at the cover's bottom right, on the cover's dark glass; "row" in the list,
//                                right of the name. ▶ «Start server» on a stopped board, a red ■ «Stop server» on an open one, the key
//                                itself neutral; nothing when its folder is missing (look: ui/homeserver.css)
//   hyHomeServer.sync(id, st)    home.html's paintProg, with the board's steps (its PROG entry): while it loads or saves the key stands aside
// A click sends the menu's own message, {action: "startServer" | "stopServer", id} (native/main.swift warm, closeTab), never opens the
// board, and the key turns a ring until the app's next list shows the board open or stopped (the «Open» chip, the green dot), 8 s at most.
(() => {
  if (window.hyHomeServer) return;
  const T = (k, v) => (window.T ? window.T(k, v) : k);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const toApp = m => { try { webkit.messageHandlers.hyimg.postMessage(m); } catch { console.log("no native bridge", m.action); } };
  const WAIT_MS = 8000;
  const WAIT = new Map();   // id -> {open: the state it was asked to leave, timer}
  const BUSY = new Set();   // boards whose steps are running (opening, saving, moving the folder)
  let refocus = null;       // the board whose key had the keyboard when it was pressed: Home redraws, the new key gets it back

  const label = (open, wait) => wait ? T(open ? "Stopping the server" : "Starting the server") : T(open ? "Stop server" : "Start server");
  // the icon at the primitive's size for the key's height (ui/hy/button.js ICON_PX: l 30 and m 28 draw 16)
  const glyph = (open, wait) => wait ? '<span class="hs-spin" aria-hidden="true"></span>' : hyIcon(open ? "stop" : "play", 16, 0, "hy-i", { fill: true });
  const keys = id => document.querySelectorAll(`.hs-key[data-hs-key="${CSS.escape(id)}"]`);

  function key(p, where) {
    if (!p || !p.available) return "";
    const open = !!p.open, w = WAIT.get(p.id);
    if (w && w.open !== open) { clearTimeout(w.timer); WAIT.delete(p.id); }   // the list says it happened
    const wait = WAIT.has(p.id), l = esc(label(open, wait)), up = window.customElements && customElements.get("hy-icon-button");
    // on Home <hy-icon-button> is not upgraded (no modules): its real <button> is written here, as ui/people.js does
    // the cover's plates are dark glass in both themes: the key on it wears the dark tokens (ink white, the dark red)
    const attrs = `class="hs-key hs-${where === "row" ? "r" : "c"}" size="${where === "row" ? "m" : "l"}" shape="round" data-hs-key="${esc(p.id)}"`
      + (where === "row" ? "" : ' data-hy-theme="dark"')
      + ` data-open="${open ? 1 : 0}"${wait ? " data-wait" : ""}${BUSY.has(p.id) ? " data-busy" : ""} label="${l}"`;
    return up ? `<hy-icon-button ${attrs}>${glyph(open, wait)}</hy-icon-button>`
      : `<hy-icon-button ${attrs}><button type="button" aria-label="${l}" title="${l}"${wait ? ' aria-busy="true"' : ""}>${glyph(open, wait)}</button></hy-icon-button>`;
  }

  // the keys of one board drawn again in place (a wait that ran out, the steps starting or ending), without redrawing Home
  function paint(id) {
    keys(id).forEach(k => {
      const open = k.dataset.open === "1", wait = WAIT.has(id), b = k.querySelector("button"), l = label(open, wait);
      k.toggleAttribute("data-wait", wait); k.toggleAttribute("data-busy", BUSY.has(id)); k.setAttribute("label", l);
      if (!b) return;
      b.setAttribute("aria-label", l); b.title = l; b.toggleAttribute("aria-busy", wait);
      if (!!b.querySelector(".hs-spin") !== wait) b.innerHTML = glyph(open, wait);
    });
  }

  function sync(id, st) {
    const busy = !!st && !st.out && (st.queue.length > 0 || st.lines.some(l => l.cls === "now"));
    if (busy === BUSY.has(id)) return;
    if (busy) BUSY.add(id); else BUSY.delete(id);
    paint(id);
  }

  function press(k, byKeys) {
    const id = k.dataset.hsKey, open = k.dataset.open === "1";
    if (!id || WAIT.has(id)) return;   // asked already: one message per press until the app answers
    WAIT.set(id, { open, timer: setTimeout(() => { WAIT.delete(id); if (refocus === id) refocus = null; paint(id); }, WAIT_MS) });
    toApp({ action: open ? "stopServer" : "startServer", id });
    refocus = byKeys ? id : null;
    paint(id);
  }
  document.addEventListener("pointerdown", () => { refocus = null; }, true);   // the pointer took over: the focus is its own again

  // before home.html's own click (document, bubbling): the card under the key must not open its board, the menu stays shut
  document.addEventListener("click", e => {
    const k = e.target.closest && e.target.closest(".hs-key"); if (!k) return;
    e.stopPropagation(); e.preventDefault();
    press(k, e.detail === 0);
  }, true);
  // Home redraws its cards from each list the app sends: the key pressed from the keyboard keeps the focus
  new MutationObserver(() => {
    if (!refocus || (document.activeElement && document.activeElement !== document.body)) return;
    const b = document.querySelector(`.hs-key[data-hs-key="${CSS.escape(refocus)}"] button`);
    if (b) { b.focus({ preventScroll: true }); if (!WAIT.has(refocus)) refocus = null; }
  }).observe(document.documentElement, { childList: true, subtree: true });

  window.hyHomeServer = { key, sync, waiting: id => WAIT.has(id) };
})();
