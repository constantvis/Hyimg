// A project's icon on Home (owner 2026-10-04: «change a project's icon as in ChatGPT, an emoji or an icon; the folder is off-topic
// now»). A project (Home's group of boards, home.json folders[]) keeps
//   icon   an icon's name from HY_PROJ.icons, or any emoji; none: the default «layers» (a stack of boards)
//   color  the icon's colour, one of HY_PROJ.colors; none: the text colour. An emoji keeps its own colours.
//   HY_PROJ.html(f, 16)  the icon as markup, for the sidebar, the head, the menus
//   HY_PROJ.picker(f)    the picker's markup: two tabs (Иконка, Эмодзи), colours, a grid, a field for any emoji
(() => {
  // the words in the app's language (ui/i18n.js; its Russian in ui/lang-common.js, owner 2026-10-06); a page without i18n.js: English
  const t = (k, v) => window.T ? window.T(k, v) : String(k).replace(/^\w+::/, "").replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m));
  const s = d => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const icons = {
    layers: s('<path d="m12 3.5 8.5 4.5-8.5 4.5L3.5 8z"/><path d="m3.5 12 8.5 4.5 8.5-4.5"/><path d="m3.5 16 8.5 4.5 8.5-4.5"/>'),
    sparkle: s('<path d="M12 3.5c.6 4.2 2.3 5.9 6.5 6.5-4.2.6-5.9 2.3-6.5 6.5-.6-4.2-2.3-5.9-6.5-6.5 4.2-.6 5.9-2.3 6.5-6.5z"/><path d="M18.5 16v4M16.5 18h4"/>'),
    camera: s('<path d="M4 8.5a2 2 0 0 1 2-2h2l1.5-2h5l1.5 2h2a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/><circle cx="12" cy="13" r="3.5"/>'),
    image: s('<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m20.5 16-5-5-8 8.5"/>'),
    film: s('<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M7.5 4.5v15M16.5 4.5v15M3.5 9.5h4M3.5 14.5h4M16.5 9.5h4M16.5 14.5h4"/>'),
    palette: s('<path d="M12 3.5a8.5 8.5 0 0 0 0 17c1.4 0 2-1 1.6-2.1-.5-1.3.4-2.4 1.7-2.4h2.2a3 3 0 0 0 3-3A8.5 8.5 0 0 0 12 3.5z"/><circle cx="7.8" cy="11" r="1"/><circle cx="10.5" cy="7.5" r="1"/><circle cx="15" cy="8" r="1"/>'),
    pen: s('<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>'),
    cube: s('<path d="m12 3.5 8 4.5v8l-8 4.5-8-4.5V8z"/><path d="m4 8 8 4.5L20 8M12 12.5v8"/>'),
    box: s('<path d="M3.5 8 12 4l8.5 4v8L12 20l-8.5-4z"/><path d="m3.5 8 8.5 4 8.5-4M12 12v8M7.8 6l8.5 4"/>'),
    phone: s('<rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M10.5 18.5h3"/>'),
    shirt: s('<path d="m8.5 4-5 3 2 4 2-1v10h9V10l2 1 2-4-5-3c-.5 1.5-1.8 2.5-3.5 2.5S9 5.5 8.5 4z"/>'),
    gem: s('<path d="M6.5 4h11l3.5 5-9 11L3 9z"/><path d="M3 9h18M9.5 4 8 9l4 11 4-11-1.5-5"/>'),
    star: s('<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.8l-5.2 2.8 1-5.8-4.3-4.1 5.9-.9z"/>'),
    heart: s('<path d="M12 19.5s-7.5-4.4-7.5-9.7A4.2 4.2 0 0 1 12 7.2a4.2 4.2 0 0 1 7.5 2.6c0 5.3-7.5 9.7-7.5 9.7z"/>'),
    flame: s('<path d="M12 20.5a6 6 0 0 0 6-6c0-4-3-5.5-3.5-9.5-2 1.5-3 3.5-3 5.5C10 9.5 9 8.5 9 7c-2 2-3 4.5-3 7.5a6 6 0 0 0 6 6z"/>'),
    bolt: s('<path d="M13 3.5 5 13.5h6l-1 7 8-10h-6z"/>'),
    leaf: s('<path d="M5 19c0-8 5-13.5 15-14.5C19 14.5 13.5 19.5 5.5 19.5"/><path d="M5 19.5c3-4.5 6-7 9.5-9"/>'),
    globe: s('<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.3 3.7 5.2 3.7 8.5s-1.2 6.2-3.7 8.5c-2.5-2.3-3.7-5.2-3.7-8.5S9.5 5.8 12 3.5z"/>'),
    home: s('<path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1z"/>'),
    briefcase: s('<rect x="3.5" y="7" width="17" height="12.5" rx="2"/><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M3.5 12.5h17"/>'),
    book: s('<path d="M4.5 5.5A1.5 1.5 0 0 1 6 4h13.5v13H6a1.5 1.5 0 0 0-1.5 1.5z"/><path d="M4.5 18.5A1.5 1.5 0 0 0 6 20h13.5v-3"/>'),
    music: s('<path d="M9 18V5.5l11-2V16"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>'),
    flag: s('<path d="M5 21V4.5M5 4.5h11.5l-2 4 2 4H5"/>'),
    rocket: s('<path d="M12 15.5 8.5 12c1.5-4.5 4.5-7.5 11-8.5-1 6.5-4 9.5-8.5 11z"/><path d="M8.5 12H5l2.5-3.5H11M12 15.5V19l3.5-2.5V13"/><path d="M6 15.5c-1.5 1-2 3-2 4.5 1.5 0 3.5-.5 4.5-2"/>'),
  };
  const colors = ["#e5484d", "#f76b15", "#e2a336", "#46a758", "#12a594", "#3e63dd", "#8e4ec6", "#d6409f"];
  const emoji = ["🗂️", "📌", "⭐️", "🔥", "✨", "💡", "🎯", "🚀", "🎨", "🖌️", "📷", "🎬", "🎞️", "🖼️", "🧊", "📱", "💎", "👕", "👟", "🕶️", "💄", "🛍️", "📦",
    "🏠", "🏢", "🌍", "🌿", "🌸", "🍋", "☕️", "🍷", "🎧", "🎵", "📚", "✏️", "🧪", "⚙️", "🤖", "👾", "❤️", "🖤", "💙", "💚", "💛", "🧡", "💜", "🤍"];
  const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const isIcon = v => !v || Object.prototype.hasOwnProperty.call(icons, v);
  const html = (f, size = 16) => {
    const v = f && f.icon;
    if (!isIcon(v)) return `<span class="pji emo" style="--pj:${size}px" aria-hidden="true">${esc(v)}</span>`;
    return `<span class="pji" style="--pj:${size}px${f && f.color ? `;color:${esc(f.color)}` : ""}" aria-hidden="true">${icons[v || "layers"]}</span>`;
  };
  const picker = (f, tab) => {
    tab = tab || (isIcon(f.icon) ? "icon" : "emoji");
    const cur = f.icon || "layers";
    const head = `<div class="pjt" role="tablist"><button role="tab" data-pjtab="icon" aria-selected="${tab === "icon"}">${esc(t("Icon"))}</button><button role="tab" data-pjtab="emoji" aria-selected="${tab === "emoji"}">${esc(t("Emoji"))}</button></div>`;
    if (tab === "icon") return head
      + `<div class="pjc"><button data-pjcolor="" aria-pressed="${!f.color}" title="${esc(t("Text color"))}" style="--c:var(--ink)"></button>${colors.map(c => `<button data-pjcolor="${c}" aria-pressed="${f.color === c}" style="--c:${c}"></button>`).join("")}</div>`
      + `<div class="pjg">${Object.keys(icons).map(k => `<button data-pjicon="${k}" aria-pressed="${isIcon(f.icon) && cur === k}" title="${k}" style="${f.color ? `color:${esc(f.color)}` : ""}">${icons[k]}</button>`).join("")}</div>`;
    return head
      + `<div class="pjg emo">${emoji.map(e => `<button data-pjemoji="${e}" aria-pressed="${f.icon === e}">${e}</button>`).join("")}</div>`
      + `<label class="pjin">${esc(t("Custom"))}<input data-pjown maxlength="16" placeholder="${esc(t("paste or ⌃⌘Space"))}" value="${isIcon(f.icon) ? "" : esc(f.icon)}"></label>`;
  };
  window.HY_PROJ = { icons, colors, emoji, html, picker, isIcon };
})();
