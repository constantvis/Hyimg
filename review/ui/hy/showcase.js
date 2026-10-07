// @ts-check
// The primitives' showcase (owner 2026-10-07: «разложи все примитивы как компоненты интерактивные на доске нашей Hyimg UI в их разных
// вариациях»): every element of ui/hy in its variants, sizes and states, in the four looks side by side (dark and light, round and pro),
// live: it imports ui/hy/index.js from the app's core, so the board shows the elements as they are now, never a copy. Each specimen is
// captioned with its own tag and attributes, read from the element itself. A page that loads this module (ui/hy/showcase.html, the
// board's html/hy-primitives/*.html frames) names its family on <body data-family="buttons|choices|marks|all">.
import * as HY from "./index.js";
import { t } from "./base.js";

/** @typedef {{ tag: string, attrs?: Record<string, string>, html?: string, wrap?: string }} Spec */
/** @typedef {{ title: string, sub?: string, items: Spec[] }} Section */

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

/** @returns {Record<string, { title: string, sections: Section[] }>} */
function families() {
  const sizes = ["s", "m", "l", "row", "dock", "plate"], px = HY_PX();
  const colours = Object.entries(window.HY_COLORS || { yellow: "#f4c430", blue: "#7dbbf5" });
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
      { title: "hy-info", items: [S("hy-info", { tip: t("Opens the frame in the image studio") })] },
      { title: "hy-plate", items: [
        Object.assign(S("hy-plate", {}, esc(t("The group's long title stays in one line and ends in an ellipsis"))), { wrap: "full" }),
        S("hy-plate", { kind: "capsule" }, `<hy-icon-button icon="settings" size="l" label="${esc(t("Settings"))}"></hy-icon-button>`
          + `<hy-icon-button icon="history" size="l" toggle label="${esc(t("History"))}"></hy-icon-button>`
          + `<hy-icon-button icon="notifications" size="l" label="${esc(t("Notes"))}"></hy-icon-button>`),
        S("hy-plate", {}, "Hyimg App"),
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
  const a = Object.entries(s.attrs || {}).filter(([k]) => k !== "label" && k !== "tip").map(([k, v]) => v === "" ? ` <i>${k}</i>` : ` <i>${k}</i>=<b>"${esc(v)}"</b>`).join("");
  return `&lt;${s.tag}${a}&gt;`;
}

/** @param {Spec} s */
function specimen(s) {
  const attrs = Object.entries(s.attrs || {}).map(([k, v]) => v === "" ? ` ${k}` : ` ${k}="${esc(v)}"`).join("");
  let el = `<${s.tag}${attrs}>${s.html || ""}</${s.tag}>`;
  if (s.wrap && s.wrap.startsWith("label:")) el = `<label class="sc-lbl">${el}<span>${esc(s.wrap.slice(6))}</span></label>`;
  return `<figure class="sc-it${s.wrap === "full" || (s.wrap || "").startsWith("label:") ? " wide" : ""}"><div class="sc-el">${el}</div><figcaption>${caption(s)}</figcaption></figure>`;
}

const LOOKS = [["dark", "round", "Dark · Round"], ["dark", "pro", "Dark · Pro"], ["light", "round", "Light · Round"], ["light", "pro", "Light · Pro"]];

/**
 * Builds the showcase of one family (or all) into root.
 * @param {HTMLElement} root
 * @param {string} which  buttons, choices, marks or all
 */
export function mount(root, which = "all") {
  const F = families(), keys = which === "all" || !F[which] ? Object.keys(F) : [which];
  const live = Object.keys(HY).length;
  // short and visual (owner 2026-10-07: no paragraphs on the board): the family's name is the board's heading, the looks are the columns
  root.innerHTML = (which === "all" || !F[which] ? `<header class="sc-head"><h1>${esc(t("Hyimg UI · primitives"))}</h1>`
    + `<p>${esc(t("{n} live", { n: live }))} · ui/hy</p></header>` : "")
    + keys.map(k => `<section class="sc-fam" data-fam="${k}">${which === "all" ? `<h2>${esc(F[k].title)}</h2>` : ""}<div class="sc-looks">`
      + LOOKS.map(([th, sh, name]) => `<div class="sc-look" data-hy-theme="${th}" data-hy-shape="${sh}"><h3>${esc(t(name))}</h3>`
        + F[k].sections.map(sec => `<div class="sc-sec${sec.title === "hy-plate" ? " paper" : ""}"><h4><code>${sec.title}</code>${sec.sub ? ` · ${esc(sec.sub)}` : ""}</h4>`
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
