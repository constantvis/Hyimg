// THE slider of the app (owner 2026-10-06: «why are the sliders everywhere not the same as in 3D»): the 3D editor's look, a track with its
// fill and one thin line at the fill's end, the label on the left and the number on the right, made once here for every page. Styles are
// ui/slider.css (loaded by this file when the page has not).
//
// MARKUP. A native <input type="range"> keeps the keyboard, the accessibility tree, the `input` and `change` events and the value, so code
// that already listens to the input goes on working. It lies invisible over the whole control; the picture is drawn from --p (0..1) on the
// wrapper, so the fill and the line are one geometry: the fill is p of the width, the line is centred on the fill's end and clamped to 1 px
// inside the track (the same math, no thumb of the browser's own).
//
//   <div class="hy-slider">                      add class "sm" for the compact one («◐ ——— 100%», no words inside, the number is yours)
//     <input type="range" min="0" max="100" step="1" value="70" aria-label="Lens">
//     <i class="hy-slider-f"></i><i class="hy-slider-t"></i>        (fill, line; made for you when missing)
//     <span class="hy-slider-l">Lens</span>      (label, left; optional)
//     <output class="hy-slider-v">70</output>    (number, right; a click types it; optional)
//   </div>
//
//   hySlider.mount(el)            makes a wrapper of that markup alive (an <input type=range> alone gets its wrapper): pointer, number field, --p
//   hySlider.create({label, value, min, max, step, unit, compact, onInput, onChange}) -> {el, input, set(v), destroy()}
//   hySlider.dial(host, props)    the same for DialKit (3D editor): returns {update(props), destroy()}; props as DialKit's mountSlider has them
//
// The pointer: a press and a drag move the value from where it was grabbed (no jump at the start), ⇧ ten times finer, ⌥ a hundred times;
// a click without a drag puts the value where the pointer is; a double click or a click on the number types it; the arrows move one step,
// ⇧ ten steps. The pointer is captured, so the drag goes on outside the control. Rounded in the default shape, square-ish in «pro»;
// easing cubic-bezier(.32,.72,0,1).
//
// For editors that need more (the frames editor, owner 2026-10-06): data-curve="sqrt" (finer near the start: the fill is the square root of the
// share), data-center="0" (a signed slider: the fill runs from that value to the value and a tick marks it, the line stays on the value),
// data-reset="0" (a double click puts that value back instead of typing), class "grad" with --hy-sl-grad set to a gradient (a colour strip along
// the bottom edge, no fill), and on the object mount() returns: format(v) -> the number's text («+10») and parse(text, current) -> the typed
// value or NaN («+10» adds, «*2», «50%»), which the typing field uses.
(() => {
  if (window.hySlider) return;
  if (!document.querySelector('link[href$="ui/slider.css"]')) { const l = document.createElement("link"); l.rel = "stylesheet"; l.href = new URL("slider.css", (document.currentScript && document.currentScript.src) || location.href).href; (document.head || document.documentElement).appendChild(l); }

  const num = (v, d) => (Number.isFinite(+v) ? +v : d);
  const decimals = (step, min, max) => Math.min(8, Math.max(...[step, min, max].map(v => { const [c, e = "0"] = String(v).toLowerCase().split("e"); return Math.max(0, (c.split(".")[1] || "").length - Number(e)); })));
  const snap = (v, min, max, step) => { v = Math.max(min, Math.min(max, v)); if (v === min || v === max || !(step > 0)) return v; return Math.max(min, Math.min(max, Number((min + Math.round((v - min) / step) * step).toPrecision(14)))); };
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

  function mount(root) {
    if (root.tagName === "INPUT") { const w = el("div", "hy-slider"); root.replaceWith(w); w.appendChild(root); root = w; }
    if (root._hy) return root._hy;
    const input = root.querySelector('input[type="range"]'); if (!input) return null;
    const fill = root.querySelector(".hy-slider-f") || root.appendChild(el("i", "hy-slider-f")), thumb = root.querySelector(".hy-slider-t") || root.appendChild(el("i", "hy-slider-t"));
    const label = root.querySelector(".hy-slider-l"), out = root.querySelector(".hy-slider-v");
    const range = () => { const min = num(input.min, 0), max = num(input.max, 100), step = num(input.step, 1); return { min, max: max > min ? max : min + 1, step }; };
    const fmt = v => { const { min, max, step } = range(); return v.toFixed(decimals(step, min, max)); };
    const sqrt = () => root.dataset.curve === "sqrt";
    const toP = v => { const { min, max } = range(), p = Math.max(0, Math.min(1, (v - min) / (max - min))); return sqrt() ? Math.sqrt(p) : p; };
    const fromP = p => { const { min, max } = range(); p = Math.max(0, Math.min(1, p)); return min + (sqrt() ? p * p : p) * (max - min); };
    const text = v => (api.format ? api.format(v) : fmt(v));
    const paint = () => {   // the one place that decides where the fill ends and where the line stands
      const { min } = range(), v = num(input.value, min), p = toP(v), c = root.dataset.center != null ? toP(num(root.dataset.center, 0)) : 0;
      root.style.setProperty("--p", String(p)); root.style.setProperty("--c", String(c));
      root.style.setProperty("--fl", String(Math.min(c, p))); root.style.setProperty("--fw", String(Math.abs(p - c)));   // the fill: from the centre (0 when not signed) to the value
      if (out && out.tagName !== "INPUT" && !out._edit) out.textContent = text(v) + (root.dataset.unit || "");
      input.setAttribute("aria-valuetext", text(v) + (root.dataset.unit || ""));
    };
    const emit = (type, v) => { input.value = String(v); paint(); input.dispatchEvent(new Event(type, { bubbles: true })); };
    const api = { el: root, input, paint, set(v) { input.value = String(snap(+v, range().min, range().max, range().step)); paint(); }, destroy() { root._hy = null; root.removeEventListener("pointerdown", down); } };
    let drag = null, jump = 0;
    // a typed number's ↵ at the field's end, bare in its ink, until learned (ui/hy/keyhint.js); a drag shows none (owner 2026-10-09 on
    // «Contrast ⇧ 10× finer ⌥ 100× … ↵ Apply»: «вот так точно не надо ... достаточно просто enter символа»)
    const TYPE_KEYS = [{ id: "done", keys: ["enter"], t: "" }];
    const hint = f => (window.hyKeyHint ? window.hyKeyHint.show(f, "number", TYPE_KEYS, { place: "end", bare: true, after: false, field: f }) : null);
    const at = x => { const r = root.getBoundingClientRect(); return fromP((x - r.left) / (r.width || 1)); };
    function down(e) {
      if (e.button !== 0 || e.target.closest(".hy-slider-ed") || input.disabled) return;
      e.preventDefault(); input.focus({ preventScroll: true });
      root.setPointerCapture(e.pointerId);
      drag = { id: e.pointerId, x: e.clientX, y: e.clientY, w: root.getBoundingClientRect().width || 1, v0: num(input.value, 0), x0: e.clientX, k: 1, moved: false };
      root.classList.add("drag");
    }
    function move(e) {
      if (!drag || drag.id !== e.pointerId) return;
      drag.moved = drag.moved || Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 3;
      if (!drag.moved) return;
      const { min, max, step } = range(), k = e.altKey ? 0.01 : e.shiftKey ? 0.1 : 1;
      if (k !== drag.k) { drag.v0 = num(input.value, min); drag.x0 = e.clientX; drag.k = k; }   // a modifier pressed mid-drag goes on from here, no jump
      const v = snap(fromP(toP(drag.v0) + (e.clientX - drag.x0) / drag.w * k), min, max, step);
      if (v !== num(input.value, NaN)) emit("input", v);
    }
    function up(e) {
      if (!drag || drag.id !== e.pointerId) return;
      const was = drag; drag = null; root.classList.remove("drag");
      if (root.hasPointerCapture(e.pointerId)) root.releasePointerCapture(e.pointerId);
      if (!was.moved) {   // a click: the value goes where the pointer is, gliding there
        const { min, max, step } = range(), raw = at(e.clientX), n = (max - min) / step, near = Math.round((raw - min) / (max - min) * 10) / 10;
        const v = n <= 10 || sqrt() ? snap(raw, min, max, step) : Math.abs((raw - min) / (max - min) - near) <= 0.03125 ? min + near * (max - min) : snap(raw, min, max, step);
        root.classList.add("jump"); clearTimeout(jump); jump = setTimeout(() => root.classList.remove("jump"), 300);
        emit("input", snap(v, min, max, step));
      }
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
    root.addEventListener("pointerdown", down);
    root.addEventListener("pointermove", move);
    root.addEventListener("pointerup", up);
    root.addEventListener("pointercancel", () => { drag = null; root.classList.remove("drag"); });
    // the number is a field: a click on it, or a double click on the track, types the value
    function edit() {
      if (!out || out._edit || input.disabled) return;
      const cur = num(input.value, 0), f = el("input", "hy-slider-ed"); f.type = "text"; f.inputMode = "decimal"; f.value = text(cur); const was = f.value; f.setAttribute("aria-label", (input.getAttribute("aria-label") || "") + " value");
      out._edit = true; out.hidden = true; out.after(f); f.focus(); f.select(); const kh = hint(f);
      const end = cancel => {
        if (!out._edit) return; out._edit = false; if (kh) kh.hide();
        const raw = f.value.trim(), v = raw === "" || raw === was ? NaN : api.parse ? api.parse(raw, cur) : Number(raw.replace(",", ".")); f.remove(); out.hidden = false;
        if (!cancel && Number.isFinite(v)) { const { min, max, step } = range(); emit("input", snap(v, min, max, step)); input.dispatchEvent(new Event("change", { bubbles: true })); }
        paint(); input.focus({ preventScroll: true });
      };
      // a value: ↵ and Tab apply, Esc gives the old one back (owner 2026-10-10, ui/typing.js on the board; a page without it, the same here)
      const keys = window.hyTyping ? window.hyTyping.keys : (f, o) => f.addEventListener("keydown", k => { k.stopPropagation();
        if (k.key === "Enter" || k.key === "Escape") { k.preventDefault(); (k.key === "Escape" ? o.cancel : o.apply)(k); } else o.key(k); });
      keys(f, { esc: "cancel", enter: "line", apply: () => end(false), cancel: () => end(true), key: k => {
        // ↑ ↓ in the typed number step it, ⇧ ten steps (owner 2026-10-06: «up and down change the number, with Shift by ten, everywhere
        // I clicked a number»): the picture follows at once, the field stays open with the new number selected
        const d = k.key === "ArrowUp" ? 1 : k.key === "ArrowDown" ? -1 : 0; if (!d || k.altKey || k.metaKey || k.ctrlKey) return;
        // from the value itself while the field still shows it (a shown «+26» typed would read as «add 26»), from the typed text otherwise
        k.preventDefault(); const { min, max, step } = range(), raw = f.value.trim(), now = num(input.value, cur);
        const base = raw === f._shown || raw === was ? now : api.parse ? api.parse(raw, now) : Number(raw.replace(",", "."));
        const v = snap((Number.isFinite(base) ? base : num(input.value, cur)) + d * (step > 0 ? step : 1) * (k.shiftKey ? 10 : 1), min, max, step);
        emit("input", v); f.value = f._shown = text(v); f.select();
      } });
      f.addEventListener("blur", () => end(false)); f.addEventListener("pointerdown", k => k.stopPropagation());
    }
    if (out) { out.addEventListener("pointerdown", e => e.stopPropagation()); out.addEventListener("click", e => { e.stopPropagation(); edit(); }); }
    root.addEventListener("dblclick", e => {
      e.preventDefault();
      if (root.dataset.reset == null) return edit();
      const { min, max, step } = range(); emit("input", snap(+root.dataset.reset, min, max, step)); input.dispatchEvent(new Event("change", { bubbles: true }));   // back to its default
    });
    input.addEventListener("keydown", e => {   // ⇧ and an arrow: ten steps (the native range moves one)
      const d = e.key === "ArrowRight" || e.key === "ArrowUp" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowDown" ? -1 : 0;
      if (!d || !e.shiftKey || e.altKey || e.metaKey || e.ctrlKey) return;
      e.preventDefault(); const { min, max, step } = range();
      emit("input", snap(num(input.value, min) + d * step * 10, min, max, step)); input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    input.addEventListener("input", paint); input.addEventListener("change", paint);
    new MutationObserver(paint).observe(input, { attributes: true, attributeFilter: ["min", "max", "step", "value"] });
    root._hy = api; paint();
    // the line never runs through the words (owner 2026-10-06: near 0 it crossed «Power, W» and «Size, cm»): while it stands over the label
    // or the number it fades out (.hy-under, slider.css), the fill's end still shows the value. Watched on --p, so every way of painting counts,
    // and on the slider's size (it is built before it is in the page, and a panel can change its width)
    const words = el => el && !el.hidden && el.offsetWidth > 0;
    const under = () => {
      const W = root.clientWidth, x = Math.max(1, Math.min(W - 1, (parseFloat(root.style.getPropertyValue("--p")) || 0) * W));
      const over = el => words(el) && x >= el.offsetLeft - 4 && x <= el.offsetLeft + el.offsetWidth + 4;
      root.classList.toggle("hy-under", W > 0 && (over(label) || over(out)));
    };
    new MutationObserver(under).observe(root, { attributes: true, attributeFilter: ["style"] }); if (window.ResizeObserver) new ResizeObserver(under).observe(root); under();
    return api;
  }

  function create(o = {}) {
    const root = el("div", "hy-slider" + (o.compact ? " sm" : "")), input = el("input"); input.type = "range";
    input.min = o.min ?? 0; input.max = o.max ?? 100; input.step = o.step ?? 1; input.value = o.value ?? 0; if (o.label) input.setAttribute("aria-label", o.label);
    root.appendChild(input);
    if (o.unit) root.dataset.unit = o.unit;
    if (!o.compact) { if (o.label) root.appendChild(el("span", "hy-slider-l", o.label)); root.appendChild(el("output", "hy-slider-v")); }
    const api = mount(root);
    if (o.onInput) input.addEventListener("input", () => o.onInput(+input.value));
    if (o.onChange) input.addEventListener("change", () => o.onChange(+input.value));
    return api;
  }

  // DialKit's mountSlider asks for this (vendor/dialkit/index.js, Hyimg patch): its controls get the app's slider
  function dial(host, props, helpers = {}) {
    let p = props, quiet = false;
    const wrap = el("div", "hy-slider-wrapper"), s = create({ label: p.label, min: p.min ?? 0, max: p.max ?? 1, step: p.step ?? 0.01, value: p.value, unit: p.unit ? " " + p.unit : "" });
    wrap.appendChild(s.el); host.appendChild(wrap);
    const lab = s.el.querySelector(".hy-slider-l");
    const sync = () => {
      s.input.min = p.min ?? 0; s.input.max = p.max ?? 1; s.input.step = p.step ?? 0.01; s.set(p.value);
      s.input.setAttribute("aria-label", p.label); lab.textContent = p.label; if (helpers.appendShortcut) helpers.appendShortcut(lab, p.shortcut, p.shortcutActive);
    };
    s.input.addEventListener("input", () => { if (!quiet) p.onChange(+s.input.value); });
    sync();
    return { update(next) { p = next; quiet = true; sync(); quiet = false; }, destroy() { s.destroy(); wrap.remove(); } };
  }

  // every other number field of the page the same way (owner 2026-10-06: «everywhere I clicked a number»): ↑ ↓ step it, ⇧ by ten.
  // Listened on the way up, so a field that steps itself (the image editor's fields) has done it and marked the event: it is left alone
  if (!window.__hyNumKeys) {
    window.__hyNumKeys = true;
    document.addEventListener("keydown", e => {
      const t = e.target, d = e.key === "ArrowUp" ? 1 : e.key === "ArrowDown" ? -1 : 0;
      if (!d || e.defaultPrevented || e.altKey || e.metaKey || e.ctrlKey || !(t instanceof HTMLInputElement) || t.type === "range" || t.classList.contains("hy-slider-ed")) return;
      if (!(t.type === "number" || /^(decimal|numeric)$/.test(t.inputMode) || t.dataset.num != null)) return;
      const m = /^\s*([-+]?\d*[.,]?\d+)(.*)$/.exec(t.value); if (!m) return;
      e.preventDefault();
      const st = parseFloat(t.step) > 0 ? parseFloat(t.step) : 1, mn = t.min !== "" ? +t.min : -Infinity, mx = t.max !== "" ? +t.max : Infinity;
      const v = Math.max(mn, Math.min(mx, Number((parseFloat(m[1].replace(",", ".")) + d * st * (e.shiftKey ? 10 : 1)).toPrecision(12))));
      t.value = t.type === "number" ? String(v) : String(v) + m[2];
      t.dispatchEvent(new Event("input", { bubbles: true })); t.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }
  const auto = () => document.querySelectorAll(".hy-slider").forEach(mount);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", auto); else auto();
  window.hySlider = { mount, create, dial };
})();
