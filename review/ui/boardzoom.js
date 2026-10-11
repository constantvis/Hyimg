// The board's zoom (owner 2026-10-11 on round 20, question 15, ♥ A «Меню зума у процента»: «идеально»; board audit B-16, B-21, P-14).
// One table of the zoom's actions, as Figma has them, and everything is built from it: the keys on the board (ui/boardkeys.js calls
// key()), the menu under the view % of the dock (a click on the percent; in a Studio the percent still fits that Studio's card), and the
// rows of the «?» panel's All keys and Keys here (ui/keyspanel.js reads ROWS: the same words, keys and icons, so no row goes stale).
//   ⇧1 Zoom to fit   ⇧2 Zoom to selection   ⇧0 Zoom to 100 %   ⌘+ Zoom in   ⌘− Zoom out   and 50 %, 200 % in the menu
// Before this the percent did ⇧1 and the board had no other zoom key (round 18 made the percent «show all», 2026-10-10).
// canvas.html's camera does the work: fit(ids), zoomAt(x, y, factor), the selection sel, INSET (the library's part of the window).
(() => {
  if (window.hyBoardZoom) return;
  const T = (k, v) => (window.T ? window.T(k, v) : k);
  // [id, icon (ui/icons.js), words, keys as the menus show them, the «?» panel's caps]
  const ROWS = [
    ["fit", "fit", "Zoom to fit", ["⇧", "1"]],
    ["sel", "view", "Zoom to selection", ["⇧", "2"]],
    ["100", "zoom100", "Zoom to 100 %", ["⇧", "0"]],
    ["in", "zoomIn", "Zoom in", ["⌘", "+"]],
    ["out", "zoomOut", "Zoom out", ["⌘", "−"]],
  ];
  const PRESETS = [0.5, 2];   // 50 %, 200 %, in the menu only
  const css = document.createElement("style"); css.id = "hy-zoom-css";
  css.textContent = "#bzoomm .sep { height: 1px; margin: 4px 8px; background: var(--line); }";
  (document.head || document.documentElement).appendChild(css);

  const ready = () => typeof cam !== "undefined" && typeof stage !== "undefined";
  const selIds = () => (typeof sel !== "undefined" && typeof board !== "undefined" ? [...sel].filter(id => board.items[id] || board.groups[id]) : []);
  // the middle of the board's free part: the library covers the left of the window (INSET)
  const mid = () => { const r = stage.getBoundingClientRect(), i = typeof INSET === "number" ? INSET : 0; return [r.left + i + (r.width - i) / 2, r.top + r.height / 2]; };
  // the camera at z exactly, the point in the middle staying where it is (zoomAt's limits, 0.5 % to 800 %)
  const to = z => {
    const [x, y] = mid(), w = toWorld(x, y), r = stage.getBoundingClientRect();
    cam.z = Math.min(8, Math.max(0.005, z)); cam.x = w.x - (x - r.left) / cam.z; cam.y = w.y - (y - r.top) / cam.z; saveCam(); renderCam(); render();
  };
  function run(id) {
    if (!ready()) return false;
    if (id === "fit") fit();
    else if (id === "sel") { const ids = selIds(); if (!ids.length) return false; fit(ids); }
    else if (id === "100") to(1);
    else if (id === "in") to(cam.z * 2);
    else if (id === "out") to(cam.z / 2);
    else if (/^z[\d.]+$/.test(id)) to(+id.slice(1));
    else return false;
    return true;
  }
  // the keys, by the physical key: ⇧2 is «@» or «"» and ⇧0 «)» by the layout; ⌘= is ⌘+ without ⇧, the keypad's + and − too
  function key(e) {
    const mod = e.metaKey || e.ctrlKey, c = e.code;
    let id = "";
    if (e.shiftKey && !mod && !e.altKey) id = c === "Digit1" || e.key === "!" ? "fit" : c === "Digit2" ? "sel" : c === "Digit0" ? "100" : "";
    else if (mod && !e.altKey) id = c === "Equal" || c === "NumpadAdd" || e.key === "+" || e.key === "=" ? "in" : c === "Minus" || c === "NumpadSubtract" || e.key === "-" ? "out" : "";
    if (!id) return false;
    e.preventDefault();   // ⌘+ and ⌘− never zoom the page itself (DESIGN.md «Без зума страницы»)
    run(id); return true;
  }
  function fill(m) {
    const has = selIds().length > 0, item = ([id, ic, w, keys]) => window.hyMenuItem(`data-zoom="${id}"`, ic, T(w), keys,
      id === "sel" && !has ? window.hyMenuOff(T("Select something first")) : "");
    m.innerHTML = ROWS.slice(0, 3).map(item).join("") + `<div class="sep" role="separator"></div>` + ROWS.slice(3).map(item).join("")
      + `<div class="sep" role="separator"></div>` + PRESETS.map(z => item([`z${z}`, "", `${Math.round(z * 100)} %`, []])).join("");
  }
  let MENU = null;
  function init() {
    const b = document.getElementById("bfit");
    if (!b || !window.hyDock || !window.hyMenuItem) return void setTimeout(init, 50);
    const el = document.createElement("div"); el.id = "bzoomm"; el.setAttribute("aria-label", T("Zoom"));
    MENU = hyDock.menu(b, el, { fill, pick: it => run(it.dataset.zoom) });
  }
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", init); else init();
  window.hyBoardZoom = { ROWS, key, run, get menu() { return MENU; } };
})();
