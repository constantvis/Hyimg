// One way to put the bar over a selection together (board audit B-17, round 20 «Мелочи», owner 2026-10-11: «да давай всё по максимум
// делать»). The groups stand in one order: the Studio (its chip) | the kind's actions (Crop, Split, Arrange, the plugins' buttons) | ♥ |
// opacity, and a hairline stands only between two groups that have something. Before, each kind of selection put its bar together by
// hand: an HTML card had two hairlines with nothing between them (the chip brought one, the opacity another), one picture had no ♥ while
// two had it. ♥ is on the bar wherever it works: pictures and HTML pages (ui/cardfav.js), one or several.
//   hySelBar.join(...groups)   the groups' markup, "" ones left out, a hairline between the others
//   hySelBar.fav(ids)          the ♥ button for these, or "" when none of them takes a ♥
(() => {
  if (window.hySelBar) return;
  const SEP = '<span class="sep"></span>';
  const join = (...groups) => groups.filter(g => g && String(g).trim()).join(SEP);
  function fav(ids) {
    if (!window.hyCardFav || !ids.some(id => board.items[id] && hyCardFav.path(board.items[id]))) return "";
    const on = hyCardFav.allOn(ids), one = ids.filter(id => board.items[id] && hyCardFav.path(board.items[id])).length === 1;
    const tip = one ? (on ? T("Remove ♥ · F") : T("♥ Like · F")) : (on ? T("Remove ♥ from the selected") : T("♥ on all selected")) + " · F";
    return `<button data-fav class="fv${on ? " on" : ""}" title="${tip}" aria-label="${T("Like")}">${hyIcon("heart", 15, 2.2)}<kbd>F</kbd></button>`;
  }
  window.hySelBar = { join, fav };
})();
