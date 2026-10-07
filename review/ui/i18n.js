// The interface in English or Russian (owner 2026-10-06: «translate the whole interface to English», then «make 2 versions, Russian
// and English, switchable in settings»). English is the default; the choice is the app's setting cv.lang ("en" | "ru"), one for every
// project like the theme (server.py SETTINGS, ui/settings.js puts it into localStorage before this file runs). Home, opened by the
// Mac app from a file, gets it from the app (window.HY_LANG, set before the page's first line) or keeps it in its own localStorage.
//
// How a string is written: the English text is the key, the code says what it shows in English and the Russian dictionary says the rest.
//   T("Show in Finder")                    "Show in Finder" | «Показать в Finder»
//   T("Delete «{name}»?", { name })         {name} is filled in, in both languages; a number in the language's grouping (T.num)
//   T("{n} frames", { n })                  plural: the dictionary's value is a list of forms, picked by vars.n
//                                           (en: [one, other]; ru: [один, два-четыре, пять и больше], «1 кадр, 2 кадра, 5 кадров»)
//   T("page::Delete")                      a context before «::» when one English word needs two Russian ones; English drops it
// The dictionaries are files beside this one: ui/lang-common.js (the shared ui/*.js), ui/lang-home.js, ui/lang-library.js,
// ui/lang-board.js; each calls hyLang({ ru: {...}, en: {...} }). en: only for plurals and context keys whose English differs.
// Adding a string: write T("English") in the code, add "English": "Русский" to the page's lang-*.js. A key missing from the Russian
// dictionary shows its English and is listed in window.__tMiss (the tests check it stays empty).
// Static markup is written in English; T.dom() (called once right after a page's markup, before its scripts) puts its text nodes and
// title / aria-label / placeholder / alt into the chosen language, and an element with data-t="key" (data-th: its HTML) by its key.
// Switching (T.set) saves the setting and reloads the page after it is saved; other open pages take it as the settings sync arrives
// (hyimgSettingsChanged calls T.changed()), the Mac app rebuilds its menus.
(() => {
  if (window.T && window.T.dom) return;
  const D = { en: {}, ru: {} };
  const pick = v => v === "ru" ? "ru" : "en";
  const read = () => { try { const v = localStorage.getItem("cv.lang"); if (v) return pick(v); } catch {} return null; };
  const lang = typeof window.HY_LANG === "string" && window.HY_LANG ? pick(window.HY_LANG) : (read() || "en");
  const locale = lang === "ru" ? "ru-RU" : "en-US";
  document.documentElement.lang = lang;
  // the other language's words never show: until T.dom has put the static markup into Russian the body stays unpainted
  if (lang !== "en") {
    document.documentElement.classList.add("t-wait");
    const st = document.createElement("style"); st.textContent = "html.t-wait body{visibility:hidden}"; (document.head || document.documentElement).appendChild(st);
    document.addEventListener("DOMContentLoaded", () => document.documentElement.classList.remove("t-wait"));
  }
  const miss = window.__tMiss = [];
  const form = (n, forms) => {
    if (forms.length < 2) return forms[0];
    n = Math.abs(Number(n) || 0);
    if (lang === "ru" && forms.length >= 3) { const a = n % 10, b = n % 100; return Number.isInteger(n) ? (a === 1 && b !== 11 ? forms[0] : a >= 2 && a <= 4 && (b < 12 || b > 14) ? forms[1] : forms[2]) : forms[1]; }
    return n === 1 ? forms[0] : forms[1];
  };
  function T(key, vars) {
    key = String(key);
    let v = D[lang][key];
    if (v === undefined && lang !== "en") { v = D.en[key]; if (!miss.includes(key)) { miss.push(key); console.warn("[i18n] no " + lang + " for", key); } }
    if (v === undefined) { const k = key.indexOf("::"); v = k > 0 ? key.slice(k + 2) : key; }
    if (Array.isArray(v)) v = form(vars && vars.n, v);
    // a number is written in the language's own grouping (1,234 | 1 234); pass a string for one that must stay as it is (a year, a port)
    return vars ? String(v).replace(/\{(\w+)\}/g, (m, k) => (k in vars ? (typeof vars[k] === "number" ? T.num(vars[k]) : String(vars[k])) : m)) : String(v);
  }
  T.lang = lang;
  T.locale = locale;
  T.has = key => D[lang][key] !== undefined || lang === "en";
  T.dict = D;
  // numbers as digits in the language's own grouping: 1,234 | 1 234
  T.num = (n, opt) => Number(n).toLocaleString(locale, opt);
  T.date = (d, opt) => new Date(d).toLocaleDateString(locale, opt);
  T.time = (d, opt) => new Date(d).toLocaleTimeString(locale, opt || { hour: "2-digit", minute: "2-digit" });
  // «5 min ago» | «5 мин назад»
  T.ago = (t, now = Date.now()) => {
    const s = Math.max(0, Math.round((now - new Date(t).getTime()) / 1000));
    if (s < 45) return T("just now");
    if (s < 3600) return T("{n} min ago", { n: Math.max(1, Math.round(s / 60)) });
    if (s < 86400) return T("{n} h ago", { n: Math.round(s / 3600) });
    if (s < 86400 * 7) return T("{n} d ago", { n: Math.round(s / 86400) });
    return T.date(t, { day: "numeric", month: "short" });
  };
  // the static markup of a page, once, right after it is parsed (before scripts put the owner's data in it)
  const ATTRS = ["title", "aria-label", "placeholder", "alt", "data-tip"];
  T.dom = (root = document.documentElement) => {
    try {
      if (lang !== "en") {
        if (root === document.documentElement && document.title && D[lang][document.title.trim()] !== undefined) document.title = T(document.title.trim());
        const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => {
          const p = n.parentElement; if (!p || /^(SCRIPT|STYLE|TEXTAREA|TITLE)$/.test(p.tagName) || p.closest("[data-t],[data-th],[data-not]")) return NodeFilter.FILTER_REJECT;
          const s = n.nodeValue.trim(); return s && D[lang][s] !== undefined ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP; } });
        const L = []; while (w.nextNode()) L.push(w.currentNode);
        L.forEach(n => { const s = n.nodeValue, a = s.match(/^\s*/)[0], b = s.match(/\s*$/)[0]; n.nodeValue = a + T(s.trim()) + b; });
        root.querySelectorAll("[" + ATTRS.join("],[") + "]").forEach(el => ATTRS.forEach(at => {
          const v = el.getAttribute(at); if (v && D[lang][v.trim()] !== undefined) el.setAttribute(at, T(v.trim()));
        }));
      }
      root.querySelectorAll("[data-t]").forEach(el => { el.textContent = T(el.dataset.t); });
      root.querySelectorAll("[data-th]").forEach(el => { el.innerHTML = T(el.dataset.th); });
    } finally { if (root === document.documentElement || root === document.body) document.documentElement.classList.remove("t-wait"); }
  };
  // a page saves what it has (hyimgFlush, when it has one) before it reloads in the other language
  const reload = async () => {
    let top = window; try { while (top.parent !== top && top.parent.location.origin === location.origin) top = top.parent; } catch {}
    if (top !== window && top.T && top.T.reload) return top.T.reload();
    if (T.reloading) return; T.reloading = true;
    try { if (typeof window.hyimgFlush === "function") await window.hyimgFlush(); } catch {}
    location.reload();
  };
  T.reload = reload;
  // the switch in a page's settings: saved as the app's setting (ui/settings.js sends it to the server, the app's file), then reloaded
  T.set = v => {
    v = pick(v); if (v === lang) return;
    try { localStorage.setItem("cv.lang", v); } catch {}
    try { if (typeof window.hyLangChanged === "function") window.hyLangChanged(v); } catch {}
    setTimeout(reload, 350);   // the settings sync sends within 250 ms; the page also keeps the change and sends it again after a reload
  };
  // the settings came back from another page or the app: a different language reloads this page in it; true when it does
  T.changed = () => { const v = read(); if (v && v !== lang && !window.HY_LANG) { reload(); return true; } return false; };
  window.T = T;
  window.hyLang = d => { for (const l of Object.keys(d || {})) if (D[l]) Object.assign(D[l], d[l]); };
  // the words of this file
  window.hyLang({
    en: { "{n} min ago": ["{n} min ago", "{n} min ago"], "{n} h ago": ["{n} h ago", "{n} h ago"], "{n} d ago": ["{n} d ago", "{n} d ago"] },
    ru: { "just now": "только что", "{n} min ago": "{n} мин назад", "{n} h ago": "{n} ч назад", "{n} d ago": "{n} дн назад" },
  });
})();
