// The chip of the selected card's Studio on the bar over it (owner 2026-10-10 on round 19, Concepts/html/editors-concepts/r19/switch-d.html,
// «Отличная идея, очень нравится, делаем»): one card selected that a Studio opens, and the bar over it starts with «Image Studio ↵»,
// «3D Studio ↵» or «Dev Studio ↵», in that Studio's colour (its `color` in HY.mode, the colour its switch segment wears), before Crop and
// Make frame. A click or ↵ opens it the way the dock's switch and a double click do: ui/modes.js enter. Nothing selected, several cards, a
// card no Studio opens or a Studio already open: no chip. The dock's switch stays as it is (the owner has not decided on round 19's A).
// It replaces 3D Studio's own «3D Studio ↵» button on that bar (2026-10-07), which only 3D cards had.
//   hyStudioChip.html(ids)   the chip and the hairline after it, or ""      hyStudioChip.enter()   ↵ on the board: true when it opened one
(() => {
  if (window.hyStudioChip) return;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const css = document.createElement("style"); css.id = "hy-studiochip-css";
  // the studio's colour as a tint under its name, its dot (ui/hy/micro.css .hy-dot) and key cap (<hy-kbd>) in front and behind
  css.textContent = `.tidy button.hy-schip { --hy-sel: var(--hy-mode-c, var(--sel)); gap: 8px; padding: 0 6px 0 12px;
  background: color-mix(in srgb, var(--hy-mode-c, var(--sel)) 22%, transparent); color: var(--ink); }
.tidy button.hy-schip:hover { background: color-mix(in srgb, var(--hy-mode-c, var(--sel)) 34%, transparent); }
.tidy button.hy-schip > .hy-dot { width: 8px; height: 8px; }
.tidy button.hy-schip > hy-kbd { margin-left: 2px; }`;
  (document.head || document.documentElement).appendChild(css);
  const studio = ids => (typeof MODES !== "undefined" && MODES && MODES.studioFor ? MODES.studioFor(ids) : null);
  function html(ids) {
    const s = studio(ids); if (!s) return "";
    const tip = T("Open {studio} · ↵ or a double click", { studio: s.name });
    return `<button data-studiochip="${esc(s.key)}" class="hy-schip" style="--hy-mode-c:${esc(s.color || "var(--sel)")}" title="${esc(tip)}" aria-label="${esc(tip)}">`
      + `<span class="hy-dot"></span>${esc(s.name)}<hy-kbd size="s">↵</hy-kbd></button><span class="sep"></span>`;
  }
  function enter() {
    if (typeof sel === "undefined") return false;
    const ids = [...sel].filter(id => board.items[id]), s = studio(ids); if (!s) return false;
    return MODES.enter(s.key, ids);
  }
  // on the press, as the bar's other buttons (canvas.html's stage pointerdown), and before the board's own handling of it; a click from the
  // keyboard (Space or ↵ on the focused chip) too
  const hit = e => e.target.closest && e.target.closest(".tidy [data-studiochip]");
  addEventListener("pointerdown", e => { if (e.button !== 0 || !hit(e)) return; e.preventDefault(); e.stopImmediatePropagation(); enter(); }, true);
  addEventListener("click", e => { if (!hit(e)) return; e.preventDefault(); e.stopImmediatePropagation(); if (e.detail === 0) enter(); }, true);
  window.hyStudioChip = { html, enter };
})();
