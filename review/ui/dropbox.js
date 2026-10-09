// Boards in Dropbox not on this Mac (owner 2026-10-08: he and his partner use two Macs signed into the same Dropbox account, so every
// board folder reaches both Macs while each Mac's catalog lists only the boards added there). Home's side, a classic script (Home loads no
// modules):
//   hyDropbox.top()                 «Add this board from Dropbox»: a hyimg:// link named a board this Mac has not added (native
//                                   LinkRouting.swift, DropboxBoards.swift offerBoard → window.hyimgOffer(board)); «Add» adds and opens it
//   hyDropbox.section(data, tab, q) the list under Recent and All boards: what the app's background scan found (data.dropbox.boards,
//                                   review/boardid.py), each with «Add»; nothing when there is none
// A board is {id, name, path, rel}; «Add» sends {action: "dropboxAdd", path}, the app takes only a folder it offered or found itself.
(() => {
  if (window.hyDropbox) return;
  const T = (k, v) => (window.T ? window.T(k, v) : k);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const toApp = m => { try { webkit.messageHandlers.hyimg.postMessage(m); } catch { console.log("no native bridge", m.action); } };
  const button = (attrs, words, variant = "plain") => `<hy-button size="s" variant="${variant}" ${attrs}><button type="button">${esc(words)}</button></hy-button>`;
  const where = b => esc(b.rel ? "Dropbox/" + b.rel : b.path);
  let offer = null;
  const redraw = () => { if (typeof window.render === "function") window.render(); };

  function top() {
    if (!offer) return "";
    return `<div class="dbx-offer" role="region" aria-label="${esc(T("Add this board from Dropbox"))}">`
      + `<span class="dbx-ic" aria-hidden="true">${window.hyIcon ? hyIcon("board", 18, 1.8) : ""}</span>`
      + `<div class="dbx-t"><b>${esc(T("Add this board from Dropbox"))}</b><span title="${esc(offer.path)}">${esc(offer.name)} · ${where(offer)}</span></div>`
      + button(`data-dbx="add" data-path="${esc(offer.path)}"`, T("dropbox::Add"), "solid")
      + button('data-dbx="later"', T("Not now"), "ghost") + "</div>";
  }
  function section(data, tab, q) {
    if (tab !== "recent" && tab !== "all") return "";
    q = (q || "").toLowerCase();
    const list = ((data && data.dropbox && data.dropbox.boards) || [])
      .filter(b => !offer || b.path !== offer.path)
      .filter(b => !q || (b.name || "").toLowerCase().includes(q) || (b.rel || "").toLowerCase().includes(q));
    if (!list.length) return "";
    return `<section class="dbx" aria-label="${esc(T("Boards in Dropbox not on this Mac"))}"><h2>${esc(T("Boards in Dropbox not on this Mac"))}<span>${list.length}</span></h2>`
      + `<div class="dbx-list">${list.map(b => `<div class="dbx-row" data-dbx-path="${esc(b.path)}"><span class="dbx-ic" aria-hidden="true">`
        + `${window.hyIcon ? hyIcon("board", 16, 1.8) : ""}</span><span class="dbx-n">${esc(b.name)}</span><span class="dbx-p" title="${esc(b.path)}">${where(b)}</span>`
        + button(`data-dbx="add" data-path="${esc(b.path)}"`, T("dropbox::Add")) + "</div>").join("")}</div>`
      + `<p class="hy-hint">${T("Dropbox syncs these folders to this Mac: <b>Add</b> lists a board here")}</p></section>`;
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-dbx]"); if (!b) return;
    if (b.dataset.dbx === "later") { offer = null; redraw(); return; }
    const path = b.dataset.path || ""; if (!path) return;
    toApp({ action: "dropboxAdd", path });   // twice is harmless: the catalog adds a folder once
    if (offer && offer.path === path) offer = null;
    redraw();
  });
  // the app: a link's board to offer
  window.hyimgOffer = board => { if (board && typeof board.path === "string") { offer = board; redraw(); } };
  window.hyDropbox = { top, section, get offer() { return offer; } };
})();
