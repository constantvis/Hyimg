// Settings › Notifications (owner 2026-10-08: «В Mac эти нотификации просто топ»; then: one switch for all, one per event, «only when Hyimg
// is in the background»). The app shows what comes to a board's bell as macOS banners (native/MacNotifications.swift); these rows say
// which. One section of its own after the shared rows of ui/setpanel.js, which loads this file and hands over how the page reads and
// writes the app's settings (its api: get(key), set({key: value | null})), so the section moves as a whole when the panel is redone.
//   mac           «Mac notifications»: "0" off, nothing on; off, the app asks the boards nothing at all
//   mac.<type>    one switch per event, "0" off: agent (an agent placed something), comment, reply (to me), mention (me or my agent),
//                 note (a reply to my note)
//   mac.bg        «Only when Hyimg is in the background»: "1" on, nothing off
// All on by default, any time except the board in front with its bell open. Greyed under the master switch while it is off.
(() => {
  if (window.hyMacNotif) return;
  const SRC = (document.currentScript && document.currentScript.src) || location.href;
  if (!document.querySelector('link[href$="ui/macnotif.css"]')) {
    const l = document.createElement("link"); l.rel = "stylesheet"; l.href = new URL("macnotif.css", SRC).href; document.head.appendChild(l);
  }
  const T = k => (window.T ? window.T(k) : String(k).replace(/^\w+::/, ""));
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  // a board runs the primitives' module (ui/hy/index.js), maybe not yet when this draws: the element makes its own checkbox then. Home
  // only links their CSS: the checkbox is written here
  const UP = n => !!(window.customElements && customElements.get(n)) || !!document.querySelector('script[type="module"][src$="hy/index.js"]');
  const ROWS = [
    ["mac.agent", "An agent placed something on a board"],
    ["mac.comment", "A comment on a board"],
    ["mac.reply", "A reply to me"],
    ["mac.mention", "I or my agent was @mentioned"],
    ["mac.note", "A reply to my note"],
    ["mac.bg", "Only when Hyimg is in the background"],
  ];
  // a setting's state: the types and the master switch are on unless "0", «only in the background» off unless "1"
  const isOn = (api, k) => { const v = String(api.get(k) ?? ""); return k === "mac.bg" ? v === "1" : v !== "0"; };
  const sw = (k, label, on, off) => `<hy-switch variant="well" data-mn-sw="${k}"${on ? " checked" : ""}${off ? " disabled" : ""} label="${esc(label)}">`
    + (UP("hy-switch") ? "" : `<input type="checkbox" class="hy-in" role="switch" aria-label="${esc(label)}"${on ? " checked" : ""}${off ? " disabled" : ""}>`)
    + "</hy-switch>";
  const row = (k, words, on, off, cls) => `<label class="mn-row${cls}" data-mn="${k}"><span class="mn-l">${esc(T(words))}</span>${sw(k, T(words), on, off)}</label>`;

  function mount(el, api) {
    const box = document.createElement("section"); box.id = "hyMacNotif"; box.className = "sp-g mn"; box.setAttribute("aria-labelledby", "mn-h");
    // after the shared rows; Plugins (ui/plugins.js) puts itself right after them, so this comes after Plugins and before Storage
    const sp = el.querySelector(":scope > .sp"); if (sp) sp.after(box); else el.appendChild(box);
    // drawn once; later only the switches' states change, so the focus stays where it is (a keyboard user turning the master switch)
    function paint() {
      const master = isOn(api, "mac");
      if (!box.firstChild) {
        box.innerHTML = `<div class="sh" id="mn-h">${esc(T("set::Notifications"))}</div>` + row("mac", "Mac notifications", master, false, " mn-main")
          + `<div class="mn-sub">${ROWS.map(([k, w]) => row(k, w, isOn(api, k), !master, k === "mac.bg" ? " mn-bg" : "")).join("")}</div>`;
      }
      box.querySelector(".mn-sub").classList.toggle("mn-off", !master);
      box.querySelectorAll("hy-switch[data-mn-sw]").forEach(s => {
        const k = s.dataset.mnSw, on = isOn(api, k), off = k !== "mac" && !master, i = s.querySelector("input");
        s.toggleAttribute("checked", on); s.toggleAttribute("disabled", off);
        if (i) { i.checked = on; i.disabled = off; }
      });
    }
    function change(e) {
      const s = e.target.closest("hy-switch[data-mn-sw]"); if (!s || s.hasAttribute("disabled")) return;
      if (e.type === "change" && UP("hy-switch")) return;   // an upgraded switch says hy-change
      const on = e.type === "hy-change" ? !!(e.detail && e.detail.checked) : e.target.checked, k = s.dataset.mnSw;
      s.toggleAttribute("checked", on);
      // the defaults are not written: on (and «only in the background» off) is the setting taken away
      api.set({ [k]: k === "mac.bg" ? (on ? "1" : null) : (on ? null : "0") });
      paint();
    }
    box.addEventListener("change", change); box.addEventListener("hy-change", change);
    paint();
    return { el: box, paint };
  }
  let mounted = null;
  window.hyMacNotif = {
    mount(el, api) { mounted = mount(el, api); return mounted; },
    paint() { if (mounted) mounted.paint(); },
  };
})();
