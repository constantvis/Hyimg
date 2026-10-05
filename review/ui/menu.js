// One kind of menu item for the whole app (owner 2026-10-04: «the right-click elements must be standardised everywhere in the app
// in one style»): an icon on the left, the label, the shortcut on the right in key caps like the shortcuts panel (canvas #keys).
// The board's right-click menu, the pages menu, the library's card menu and Home's menus build their items with hyMenuItem;
// the look is in ui/look.css (.ml, .mk).
//   hyMenuItem('data-act="group"', "group", "Сгруппировать", ["⌘", "G"], ' class="danger"')
// the icon is a name from HY_IC, or markup of its own (a project's icon on Home, ui/projicon.js)
(() => {
  const s = d => `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const IC = {
    group: s('<rect x="3.5" y="3.5" width="17" height="17" rx="3" stroke-dasharray="3 2.4"/><rect x="7.5" y="7.5" width="4" height="4" rx="1"/><rect x="12.5" y="12.5" width="4" height="4" rx="1"/>'),
    ungroup: s('<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/><path d="M14 6.5h3.5V10M10 17.5H6.5V14"/>'),
    link: s('<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>'),
    image: s('<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m20.5 16-5-5-8 8.5"/>'),
    file: s('<path d="M14 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-10z"/><path d="M14 3.5v5h5"/>'),
    view: s('<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>'),
    show: s('<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3"/><path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3"/>'),
    open: s('<path d="M14 4.5h5.5V10"/><path d="m19.5 4.5-8 8"/><path d="M18 14v4.5a1 1 0 0 1-1 1H5.5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1H10"/>'),
    rename: s('<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>'),
    del: s('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>'),
    folder: s('<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>'),
    unfile: s('<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M9.5 13.5h5"/>'),
    finder: s('<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><path d="M12 4.5c-1.5 4-1.5 9 0 15M8 10v1.5M16 10v1.5M8.5 15.5c2.2 1.3 4.8 1.3 7 0"/>'),
    relink: s('<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M12 10.5v5M9.5 13H14.5"/>'),
    plus: s('<path d="M12 5v14M5 12h14"/>'),
    play: s('<path d="M8 5.5v13l10.5-6.5z"/>'),
    stop: s('<rect x="6.5" y="6.5" width="11" height="11" rx="2"/>'),
    heart: s('<path d="M12 19.5s-7.5-4.4-7.5-9.7A4.2 4.2 0 0 1 12 7.2a4.2 4.2 0 0 1 7.5 2.6c0 5.3-7.5 9.7-7.5 9.7z"/>'),
  };
  window.HY_IC = IC;
  // the one chevron of the app (owner 2026-10-04: «the arrow must be the same everywhere»): between the crumb's steps, the library's
  // path, its folder tree, the pages button (turned down, .dn); ui/look.css .hy-chev
  window.HY_CHEV = '<svg class="hy-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>';
  window.hyMenuItem = (attrs, icon, label, keys, extra = "") =>
    `<button role="menuitem" ${attrs}${extra}>${icon && icon[0] === "<" ? icon : IC[icon] || '<span class="mi0"></span>'}<span class="ml">${label}</span>` +
    (keys && keys.length ? `<span class="mk">${keys.map(k => `<kbd>${k}</kbd>`).join("")}</span>` : "") + `</button>`;
})();
