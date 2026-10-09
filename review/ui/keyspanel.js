// The shortcuts panel (? in the top row, canvas.html #keys): a row of an action that has a button or a menu item shows that action's
// icon in front of its keys, the same icon the menus and the dock wear (ui/icons.js through HY_IC, ui/menu.js), 15 px in the menus' line.
// Owner 2026-10-09 on round 14's Tips: «Почему здесь у нас нет иконок этих кнопок? И у нас же есть шорткат-символы». The keys stay
// the app's key caps (<kbd>, ui/hy/kbd.css), as in the menus. A row of a gesture (scroll, a drag, a double click) has no button: its place
// stays empty, so the keys and the words of every row stand in one column.
// The row is found by its keys, which do not change with the language: the joined <kbd> of its .k. Rows other modules add later
// (ui/anncore.js C, ui/arrange.js after ⌥D) get theirs as they come in.
(() => {
  if (window.hyKeysPanel) return;
  const ICON = { "N": "note", "C": "comment", "⌘M": "library", "⌘G": "group", "⇧⌘G": "ungroup", "⌘]⌘[": "orderForward",
    "⌥⌘]⌥⌘[": "orderFront", "⇧C": "crop", "⌘C⌘X": "copy", "⌘V": "paste", "⌘D": "duplicate", "⌥A": "tidyBlock", "⌥S": "tidyRow",
    "⌥D": "tidy", "⌫": "trash", "⌘Z⌘⇧Z": "undo", "⇧1": "fit", "⌘X⌘V": "toPage" };
  const ARRANGE = ["tidyBlock", "layouts"];   // Arrange's rows have no keys: its menu's icon, then the layout patterns'
  const keysOf = row => [...(row.querySelector(".k")?.querySelectorAll("kbd") || [])].map(k => k.textContent.trim()).join("");
  function iconOf(row) {
    if (row.hasAttribute("data-arrange-keys")) {
      const own = row.querySelector(".k svg"); if (own) return "";   // the row that draws its button itself
      return ARRANGE[[...row.parentElement.querySelectorAll("[data-arrange-keys]")].indexOf(row)] || "";
    }
    return ICON[keysOf(row)] || "";
  }
  function dress(panel) {
    for (const row of panel.children) {
      if (row.tagName !== "DIV" || !row.querySelector(".k") || row.querySelector(":scope > .kpi")) continue;
      const name = iconOf(row), i = document.createElement("span");
      i.className = "kpi"; i.setAttribute("aria-hidden", "true"); if (name) i.dataset.icon = name;
      i.innerHTML = name && window.HY_IC ? window.HY_IC[name] || "" : "";
      row.prepend(i);
    }
  }
  const st = document.createElement("style");
  st.textContent = "#keys > div > .kpi { flex: none; display: grid; place-items: center; width: 16px; height: 16px; margin-right: -2px; color: var(--sub); }"
    + " #keys > div > .kpi > svg { width: 15px; height: 15px; display: block; }";
  (document.head || document.documentElement).appendChild(st);
  function start() {
    const panel = document.getElementById("keys"); if (!panel) return;
    dress(panel);
    new MutationObserver(() => dress(panel)).observe(panel, { childList: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
  window.hyKeysPanel = { ICON, dress };
})();
