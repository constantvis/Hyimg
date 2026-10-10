// @ts-check
// The primitives' showcase (owner 2026-10-07: «разложи все примитивы как компоненты интерактивные на доске нашей Hyimg UI в их разных
// вариациях»): every element of ui/hy in its variants, sizes and states, in the four looks side by side (dark and light, round and pro),
// live: it imports ui/hy/index.js from the app's core, so the board shows the elements as they are now, never a copy. Each specimen is
// captioned with its own tag and attributes, read from the element itself. A page that loads this module (ui/hy/showcase.html, the
// board's html/hy-primitives/*.html frames) names its family on <body data-family="buttons|choices|marks|micro|hints|all">. A member that is
// specified but not built yet is a static picture in a dashed panel (spec: true), its look in showcase.css.
import * as HY from "./index.js";
import { icon, t } from "./base.js";
import { caps } from "./keyhint.js";

// cap: the caption instead of the tag; fixed: a position: fixed element (the key hint), drawn where it stands in the row
/** @typedef {{ tag: string, attrs?: Record<string, string>, html?: string, wrap?: string, cap?: string, fixed?: boolean }} Spec */
/** @typedef {{ title: string, sub?: string, items: Spec[], spec?: boolean }} Section */   // spec: specified, not built (a static picture of it)

/**
 * @param {string} tag
 * @param {Record<string, string>} [attrs]
 * @param {string} [html]
 * @returns {Spec}
 */
const S = (tag, attrs = {}, html = "") => ({ tag, attrs, html });
const esc = (/** @type {string} */ s) => s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] || c);
const opts = (/** @type {[string, string][]} */ list) => list.map(([v, w]) => `<button value="${v}">${w}</button>`).join("");
const ic = (/** @type {string} */ n, /** @type {string} */ label) => `<button value="${n}" aria-label="${esc(label)}">${window.hyIcon ? window.hyIcon(n, 15) : n}</button>`;
const ic12 = (/** @type {string} */ n, /** @type {string} */ label) => `<button value="${n}" aria-label="${esc(label)}">${window.hyIcon ? window.hyIcon(n, 12) : n}</button>`;
// a key hint's items as <hy-keyhint> fills them (keyhint.js fill): caps, «/» between keys of one item, the words; quiet: used 3 times
const kh = (/** @type {[string[], string, boolean?][]} */ items) => items.map(([keys, w, quiet]) => `<span class="kh-i"${quiet ? " quiet" : ""}>`
  + keys.map(k => `<hy-kbd size="s">${esc(caps(k))}</hy-kbd>`).join('<span class="kh-or">/</span>')
  + (w ? `<span class="kh-t">${esc(t("hint::" + w))}</span>` : "") + "</span>").join("");
// a tip as ui/hy/tip.js fills it: the bulb, its line (key words in <b>), the × that shows on hover
const tip = (/** @type {string} */ html) => `${icon("tip", 11)}<span class="tip-t">${html}</span>`
  + `<button type="button" class="tip-x" aria-label="${esc(t("Hide tips here"))}">${icon("close", 9, 2.2)}</button>`;
// a tip's title is always its whole text: its place may cut the line with an ellipsis (DESIGN.md «Семья подсказок»)
const tipTitle = (/** @type {string} */ html) => html.replace(/<[^>]+>/g, "");

/** @returns {Record<string, { title: string, sections: Section[] }>} */
function families() {
  const sizes = ["s", "m", "l", "row", "dock", "plate"], px = HY_PX();
  const colours = Object.entries(window.HY_COLORS || { yellow: "#f4c430", blue: "#7dbbf5" });
  const ALT = t("tip::<b>⌥-click</b> a filter excludes it at once");
  return {
    buttons: { title: t("Buttons"), sections: [
      { title: "hy-button", sub: t("variants"), items: [
        S("hy-button", { variant: "plain" }, t("Duplicate")), S("hy-button", { variant: "solid" }, t("Save")),
        S("hy-button", { variant: "ghost" }, t("Cancel")), S("hy-button", { variant: "danger", icon: "trash" }, t("Delete")),
        S("hy-button", { variant: "reset", icon: "reset" }, t("Reset")), S("hy-button", { variant: "reset", icon: "reset", disabled: "" }, t("Reset")),
      ] },
      { title: "hy-button", sub: t("sizes"), items: sizes.map(s => S("hy-button", { size: s }, `${t("Button")} ${px[s]}`)) },
      { title: "hy-button", sub: t("states"), items: [
        S("hy-button", { toggle: "", pressed: "", icon: "grid" }, t("Grid")), S("hy-button", { toggle: "", icon: "grid" }, t("Grid")),
        S("hy-button", { icon: "copy", kbd: "⌘C" }, t("Copy")), S("hy-button", { size: "dock", kbd: "⌥A" }, t("Arrange")),
        S("hy-button", { disabled: "" }, t("Duplicate")), S("hy-button", { variant: "solid", size: "plate" }, t("Save")),
      ] },
      { title: "hy-icon-button", sub: t("sizes"), items: ["xs", "s", "m", "l", "dock", "plate"].map(s => s === "plate"
        ? S("hy-icon-button", { icon: "settings", size: s, label: t("Settings") }) : S("hy-icon-button", { icon: "close", size: s, label: t("Close") })) },
      { title: "hy-icon-button", sub: t("variants"), items: [
        S("hy-icon-button", { icon: "copy", label: t("Copy") }), S("hy-icon-button", { icon: "copy", variant: "plain", label: t("Copy") }),
        S("hy-icon-button", { icon: "copy", variant: "solid", label: t("Copy") }), S("hy-icon-button", { icon: "trash", variant: "danger", label: t("Delete") }),
        S("hy-icon-button", { icon: "reset", variant: "reset", size: "dock", label: t("Reset") }), S("hy-icon-button", { icon: "history", size: "plate", label: t("History") }),
      ] },
      { title: "hy-icon-button", sub: t("states"), items: [
        S("hy-icon-button", { icon: "grid", toggle: "", pressed: "", size: "dock", variant: "plain", label: t("Grid") }),
        S("hy-icon-button", { icon: "history", toggle: "", pressed: "", size: "plate", label: t("History") }),
        S("hy-icon-button", { icon: "copy", disabled: "", label: t("Copy") }),
        S("hy-icon-button", { icon: "close", shape: "round", variant: "plain", label: t("Close") }),
        S("hy-icon-button", { icon: "close", shape: "square", variant: "plain", label: t("Close") }),
      ] },
    ] },
    choices: { title: t("Choices"), sections: [
      { title: "hy-segmented", sub: t("sizes"), items: [
        S("hy-segmented", { value: "dark", size: "s" }, opts([["dark", t("Dark")], ["light", t("Light")], ["auto", t("Auto")]])),
        S("hy-segmented", { value: "light" }, opts([["dark", t("Dark")], ["light", t("Light")], ["auto", t("Auto")]])),
        S("hy-segmented", { value: "auto", size: "l" }, opts([["dark", t("Dark")], ["light", t("Light")], ["auto", t("Auto")]])),
      ] },
      { title: "hy-segmented", sub: t("variants"), items: [
        Object.assign(S("hy-segmented", { value: "cards", full: "" }, opts([["cards", t("Cards")], ["list", t("List")]])), { wrap: "full" }),
        S("hy-segmented", { value: "ev", variant: "tabs" }, opts([["ev", t("Activity")], ["ver", t("Versions")]])),
        S("hy-segmented", { value: "dark", variant: "tint" }, opts([["dark", t("Dark")], ["light", t("Light")], ["auto", t("Auto")]])),
        S("hy-segmented", { value: "grid", label: t("Cards") }, ic("grid", t("Grid")) + ic("rows", t("Rows")) + ic("list", t("List"))),
      ] },
      { title: "hy-switch", items: [
        S("hy-switch", { label: t("Snap to grid") }), S("hy-switch", { checked: "", label: t("Snap to grid") }),
        S("hy-switch", { disabled: "", label: t("Locked") }), S("hy-switch", { checked: "", disabled: "", label: t("Locked") }),
        Object.assign(S("hy-switch", { checked: "" }), { wrap: "label:" + t("Snap to grid") }),
      ] },
      { title: "hy-check", items: [
        S("hy-check", {}, t("Show hidden layers")), S("hy-check", { checked: "" }, t("Show hidden layers")),
        S("hy-check", { indeterminate: "" }, t("Some layers")), S("hy-check", { checked: "", disabled: "" }, t("Locked")),
      ] },
      { title: "hy-chip", items: [
        S("hy-chip", { count: "24" }, t("Take")), S("hy-chip", { state: "include", count: "8" }, t("Idea")),
        S("hy-chip", { state: "exclude" }, t("No")), S("hy-chip", { pinned: "" }, t("Pinned")), S("hy-chip", { cycle: "two" }, t("Video")),
      ] },
      { title: "hy-swatch", items: [
        Object.assign(S("hy-swatches", { value: "" }, `<hy-swatch none label="${esc(t("No colour"))}"></hy-swatch>`
          + colours.map(([k, v]) => `<hy-swatch value="${k}" color="${v}" label="${esc(t(k))}"></hy-swatch>`).join("")), { wrap: "full" }),
        S("hy-swatch", { color: colours[0][1], label: t("Yellow") }), S("hy-swatch", { color: colours[0][1], size: "m", selected: "", label: t("Yellow") }),
        S("hy-swatch", { color: "--hy-sel", size: "m" }), S("hy-swatch", { none: "", size: "m", label: t("No colour") }),
      ] },
    ] },
    marks: { title: t("Marks and text"), sections: [
      { title: "hy-kbd", items: [S("hy-kbd", {}, "⌘"), S("hy-kbd", {}, "Esc"), S("hy-kbd", { size: "m" }, "⇧"), S("hy-kbd", { size: "s" }, "V"), S("hy-kbd", { quiet: "" }, "⌥")] },
      { title: "hy-badge", items: [
        S("hy-badge", { count: "3", label: `3 ${t("new")}` }), S("hy-badge", { count: "120" }), S("hy-badge", { count: "2", tone: "red" }),
        S("hy-badge", { count: "7", tone: "neutral" }), S("hy-badge", { dot: "", tone: "red" }), S("hy-badge", { count: "0" }),
      ] },
      { title: "hy-hint", items: [Object.assign(S("hy-hint", {}, t("A footnote, <b>key words</b> in ink")), { wrap: "full" })] },
      { title: "hy-info", items: [S("hy-info", { tip: t("Opens the frame in Image Studio") })] },
      { title: "hy-plate", items: [
        Object.assign(S("hy-plate", {}, esc(t("The group's long title stays in one line and ends in an ellipsis"))), { wrap: "full" }),
        S("hy-plate", { kind: "capsule" }, `<hy-icon-button icon="settings" size="l" label="${esc(t("Settings"))}"></hy-icon-button>`
          + `<hy-icon-button icon="history" size="l" toggle label="${esc(t("History"))}"></hy-icon-button>`
          + `<hy-icon-button icon="notifications" size="l" label="${esc(t("Notes"))}"></hy-icon-button>`),
        S("hy-plate", {}, "Hyimg App"),
      ] },
    ] },
    // round 15's micro UI (owner 2026-10-09 on r15-micro.html: «Все топ, все делай, кроме номера пять»), each at the sheet's size, and
    // control 5, the scrub, as round 16's version A (owner 2026-10-10 on r16-scrub.html: «отлично, беру»)
    micro: { title: t("Micro UI"), sections: [
      { title: "hy-minitoggle", sub: t("1 · mini toggle"), items: [
        S("hy-minitoggle", {}, t("All nodes")), S("hy-minitoggle", { checked: "" }, t("All nodes")),
        S("hy-minitoggle", { checked: "", label: t("Snap to grid") }), S("hy-minitoggle", { disabled: "" }, t("Locked")),
      ] },
      { title: "hy-scope", sub: t("2 · the count is the switch"), items: [
        S("hy-scope", { shown: "22", total: "87" }), S("hy-scope", { shown: "22", total: "87", all: "" }),
      ] },
      { title: 'hy-segmented variant="micro"', sub: t("3 · micro segments"), items: [
        S("hy-segmented", { variant: "micro", value: "local", label: t("Space") }, opts([["local", t("Local")], ["world", t("World")]])),
        S("hy-segmented", { variant: "micro", value: "cm", label: t("Units") }, opts([["cm", "cm"], ["m", "m"], ["in", "in"]])),
        S("hy-segmented", { variant: "micro", value: "sphere", label: t("Shading") }, ic12("primBox", t("Solid view")) + ic12("sphere", t("Material")) + ic12("light", t("Render"))),
      ] },
      { title: "hy-led", sub: t("4 · status, 6 px, no glow"), items: [
        S("hy-led", { label: t("The current camera") }), S("hy-led", { state: "ok", label: t("Running") }),
        S("hy-led", { state: "off", label: t("Not found") }), S("hy-led", { state: "idle", label: t("Nothing written yet") }),
        S("hy-led", { state: "busy", label: t("Working") }),
      ] },
      { title: "hy-scrub", sub: t("5 · drag the letter, ⇧ ×10, ⌥ ×0.1, a click types"), items: [
        S("hy-scrub", { label: "X", value: "24", unit: "px" }), S("hy-scrub", { label: "W", value: "160", min: "16" }),
        S("hy-scrub", { icon: "opacity", value: "100", min: "0", max: "100", unit: "%", "aria-label": t("Opacity") }),
        S("hy-scrub", { label: "Y", value: "30", min: "-720", max: "720", unit: "°" }),
      ] },
      { title: "hy-stepper", sub: t("6 · tiny stepper"), items: [
        S("hy-stepper", { value: "3", min: "1", max: "12", label: t("Columns") }), S("hy-stepper", { value: "24", min: "0", step: "4", label: t("Padding") }),
      ] },
      { title: ".hy-dot · .hy-tag", sub: t("7 · change dot, colour dot"), items: [
        Object.assign(S("span", { class: "hy-dot", title: t("Changed") }), { cap: '<span class="hy-dot">' }),
        ...colours.slice(0, 3).map(([k, v]) => Object.assign(S("span", { class: "hy-tag", style: `--hy-dot:${v}` }, `<i class="hy-dot"></i>${esc(t(k))}`),
          { cap: '<span class="hy-tag">' })),
        Object.assign(S("span", { class: "hy-tag off" }, `<i class="hy-dot"></i>${esc(t("Off"))}`), { cap: '<span class="hy-tag off">' }),
      ] },
      { title: ".hy-hovrow .hy-ri", sub: t("8 · icons on hover, a set one stays"), items: [
        Object.assign(S("div", { class: "hy-hovrow sc-lrow" }, `<span>${esc(t("Shadow"))}</span>`
          + `<button type="button" class="hy-ri" aria-label="${esc(t("Lock"))}">${icon("lock", 12)}</button>`
          + `<button type="button" class="hy-ri keep" aria-label="${esc(t("Hidden"))}">${icon("eyeoff", 12)}</button>`), { cap: '<div class="hy-hovrow"> <button class="hy-ri">', wrap: "full" }),
      ] },
    ] },
    // the Hints family (DESIGN.md «Семья подсказок», all three built 2026-10-09): the key hint bare on a surface and in glass where there
    // is none, its place "top" the Hint bar, and the tip (ui/hy/tip.js, round 12's version 9)
    hints: { title: t("Hints"), sections: [
      { title: "hy-keyhint", sub: t("Key hint · beside what you are doing"), items: [
        Object.assign(S("hy-keyhint", { shown: "", bare: "" }, kh([[["enter"], ""]])),   // a note's, a field's: the ↵ alone, in its ink
          { cap: 'hyKeyHint.show(field, "comment", items, { place: "end", bare: true })', fixed: true, wrap: "full" }),
        Object.assign(S("hy-keyhint", { shown: "" }, kh([[["shift"], "Keep proportions"], [["alt"], "From the centre", true]])),
          { cap: t("used 3 times: quieter, 5 times: gone"), fixed: true, wrap: "full" }),
      ] },
      { title: 'hy-keyhint place="top"', sub: t("Hint bar · a Studio or a tool just opened"), items: [
        Object.assign(S("hy-keyhint", { shown: "", place: "top" }, kh([[["alt", "space"], "Orbit"], [["mod+enter"], "Save"]])),   // 3D Studio's keys
          { cap: 'hyKeyHint.show(…, { place: "top" })', fixed: true, wrap: "full" }),
      ] },
      { title: "hy-tip", sub: t("Tip · for someone who is only looking"), items: [
        Object.assign(S("hy-tip", { title: tipTitle(ALT) }, tip(ALT)), { cap: 'hyTip.show(host, "library", items)', wrap: "full" }),
        Object.assign(S("hy-tip", { off: "", title: t("Tips are off here · click the bulb to bring them back") }, tip(ALT)),
          { cap: t("closed with ×: the bulb brings them back"), wrap: "full" }),
        Object.assign(S("hy-tip", { glass: "", title: tipTitle(t("tip::<b>⌃Tab</b> returns to the board you had before")) },
          tip(t("tip::<b>⌃Tab</b> returns to the board you had before"))), { wrap: "full" }),
      ] },
    ] },
  };
}

/** The heights of the sizes, from the tokens (what the Playwright test measures). @returns {Record<string, number>} */
function HY_PX() { return { s: 24, m: 28, l: 30, row: 32, dock: 34, plate: 38 }; }

/**
 * The caption of a specimen: its tag and attributes as written.
 * @param {Spec} s
 */
function caption(s) {
  if (s.cap) return esc(s.cap);
  const a = Object.entries(s.attrs || {}).filter(([k]) => k !== "label" && k !== "tip" && k !== "title").map(([k, v]) => v === "" ? ` <i>${k}</i>` : ` <i>${k}</i>=<b>"${esc(v)}"</b>`).join("");
  return `&lt;${s.tag}${a}&gt;`;
}

/** @param {Spec} s */
function specimen(s) {
  const attrs = Object.entries(s.attrs || {}).map(([k, v]) => v === "" ? ` ${k}` : ` ${k}="${esc(v)}"`).join("");
  let el = `<${s.tag}${attrs}>${s.html || ""}</${s.tag}>`;
  if (s.wrap && s.wrap.startsWith("label:")) el = `<label class="sc-lbl">${el}<span>${esc(s.wrap.slice(6))}</span></label>`;
  const wide = s.wrap === "full" || (s.wrap || "").startsWith("label:");
  return `<figure class="sc-it${wide ? " wide" : ""}"><div class="sc-el${s.fixed ? " sc-fixed" : ""}">${el}</div>`
    + `<figcaption>${caption(s)}</figcaption></figure>`;
}

const LOOKS = [["dark", "round", "Dark · Round"], ["dark", "pro", "Dark · Pro"], ["light", "round", "Light · Round"], ["light", "pro", "Light · Pro"]];

/**
 * Builds the showcase of one family (or all) into root.
 * @param {HTMLElement} root
 * @param {string} which  buttons, choices, marks, hints or all
 */
export function mount(root, which = "all") {
  const F = families(), keys = which === "all" || !F[which] ? Object.keys(F) : [which];
  const live = Object.keys(HY).length;
  // short and visual (owner 2026-10-07: no paragraphs on the board): the family's name is the board's heading, the looks are the columns
  root.innerHTML = (which === "all" || !F[which] ? `<header class="sc-head"><h1>${esc(t("Hyimg UI · primitives"))}</h1>`
    + `<p>${esc(t("{n} live", { n: live }))} · ui/hy</p></header>` : "")
    + keys.map(k => `<section class="sc-fam" data-fam="${k}">${which === "all" ? `<h2>${esc(F[k].title)}</h2>` : ""}<div class="sc-looks">`
      + LOOKS.map(([th, sh, name]) => `<div class="sc-look" data-hy-theme="${th}" data-hy-shape="${sh}"><h3>${esc(t(name))}</h3>`
        + F[k].sections.map(sec => `<div class="sc-sec${sec.title === "hy-plate" ? " paper" : ""}${sec.spec ? " spec" : ""}">`
          + `<h4><code>${esc(sec.title)}</code>${sec.sub ? ` · ${esc(sec.sub)}` : ""}</h4>`
          + `<div class="sc-row">${sec.items.map(specimen).join("")}</div></div>`).join("")
        + `<div class="sc-ev"><span>${esc(t("Last event"))}</span><output>—</output></div></div>`).join("")
      + `</div></section>`).join("");
  root.querySelectorAll(".sc-look").forEach(look => {
    const out = /** @type {HTMLOutputElement} */ (look.querySelector(".sc-ev output"));
    /** @param {Event} e */
    const show = e => {
      const el = /** @type {Element} */ (e.target), d = /** @type {CustomEvent} */ (e).detail;
      out.textContent = `${e.type} · <${el.localName}>${d && typeof d === "object" ? " " + JSON.stringify(d) : ""}`;
    };
    for (const type of ["hy-change", "hy-toggle", "hy-info"]) look.addEventListener(type, show);
    look.addEventListener("click", e => {
      const host = /** @type {Element} */ (e.target).closest("hy-button, hy-icon-button");
      if (host && !host.hasAttribute("toggle")) out.textContent = `click · <${host.localName}>`;
    });
  });
}

const body = document.body;
if (body && body.dataset.family !== undefined) {
  mount(body, body.dataset.family || "all");
  document.documentElement.classList.add("sc-ready");
}
