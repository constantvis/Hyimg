// Who did it, as a face (owner 2026-10-07: «Видно avatar того, кто сделал ... и чуть меньше поверх него в кружке справа внизу аватар
// Claude (или Codex)»). A person is a participant, an agent never is: an agent's action
// shows the person's avatar with a smaller round badge of the agent's kind on its bottom right corner.
//
//   <hy-avatar size="16|20|24|32" name="…" color="green|#hex" src="data:…" agent="claude" label="Claude · Name">
//   hyAvatarHTML({ name, color, src, agent, size, label })   the same markup filled in, for pages that write HTML strings
//   HY_AGENTS.kind("Claude Code") -> "claude"                 the catalog kind of any agent name ("" for the app, "agent" unknown)
//   HY_AGENTS.label("claude") -> "Claude"
//
//   hyAgentBadgeHTML("claude", 24)                             the badge alone (Settings › Profile › Agents)
//   HY_AGENTS.badges({claude: "data:…"})                       this Mac's own badge pictures; the companies' marks (ui/agents) by default
//
// The catalog and its aliases are review/agents.py's (tests/unit/test_agents.py checks that both fold names the same way). A classic
// script, not a module of ui/hy: Home is a file page and loads no modules, and it shows avatars too. Its look is ui/hy/avatar.css.
(() => {
  if (window.HY_AGENTS) return;
  const CATALOG = ["claude", "codex", "gemini", "kimi", "opencode", "agent"];
  const LABEL = { claude: "Claude", codex: "Codex", gemini: "Gemini", kimi: "Kimi", opencode: "OpenCode", agent: "Agent" };
  const GLYPH = { claude: "agentClaude", codex: "agentCodex", gemini: "agentGemini", kimi: "agentKimi", opencode: "agentOpencode", agent: "agent" };
  // first match wins; agents.py ALIASES
  const ALIASES = [
    ["opencode", /open[\s_-]?code/i],
    ["claude", /claude|anthropic|\bopus|\bsonnet|\bhaiku/i],
    ["codex", /codex|openai|chatgpt|\bgpt|\bo[134](\b|-)/i],
    ["gemini", /gemini|antigravity|\bagy\b|\bbard\b|google/i],
    ["kimi", /kimi|moonshot/i],
  ];
  const APP = new Set(["", "app", "owner", "human", "person", "you"]);
  function kind(v) {
    const s = String(v ?? "").split(/\s+/).filter(Boolean).join(" ").toLowerCase().slice(0, 120);
    if (APP.has(s)) return "";
    if (CATALOG.includes(s)) return s;
    const hit = ALIASES.find(([, rx]) => rx.test(s));
    return hit ? hit[0] : "agent";
  }
  const label = v => LABEL[kind(v)] || "";

  // The badge's picture (owner 2026-10-08: «для агентов возьми логотип Claude и логотип Codex»): the company's own mark for a kind that
  // has one in ui/agents (sources.json), else our glyph on the kind's colour; this Mac's own picture of a kind (Settings › Profile ›
  // Agents, people.py agent-badges.json) over both. A mark shows only once its file has loaded, so without the files (the public
  // repositories leave them out) every badge keeps its glyph. One <style> carries the pictures: a badge's markup never holds a URL.
  const LOGOS = {};
  const DOC = typeof document !== "undefined" ? document : null;   // tests/unit/test_agents.py runs this file in node, without a page
  const SRC = (DOC && DOC.currentScript && DOC.currentScript.src) || (typeof location !== "undefined" ? location.href : "");
  const logo = {}, own = {};   // kind -> the mark's address once loaded; kind -> this Mac's picture (a data URL)
  function paintLogos() {
    if (!DOC) return;
    let st = DOC.getElementById("hyAgentLogos");
    if (!st) { st = DOC.createElement("style"); st.id = "hyAgentLogos"; (DOC.head || DOC.documentElement).appendChild(st); }
    // doubled class: above ui/hy/avatar.css's colour of the kind whichever comes first; the glyph hides under the picture
    st.textContent = CATALOG.map(k => {
      const u = own[k] || logo[k], b = `.hya-b.hya-b[data-k=${k}]`;
      return u ? `${b}>svg{visibility:hidden}${b}::after{content:"";background-image:url("${u}")}${own[k] ? "" : `${b}{background:none}`}` : "";
    }).filter(Boolean).join("\n");
  }
  if (DOC && typeof Image === "function") for (const [k, f] of Object.entries(LOGOS)) {
    const u = new URL(f, SRC).href, im = new Image();
    im.onload = () => { logo[k] = u; paintLogos(); };
    im.src = u;
  }
  // {kind: data URL}: this Mac's pictures (people.js passes what the server or the app sends); a kind left out goes back to its default
  function badges(map) {
    for (const k of CATALOG) { const v = map && map[k]; if (/^data:image\/(png|jpeg|webp);base64,/.test(v || "")) own[k] = v; else delete own[k]; }
    paintLogos();
  }
  window.HY_AGENTS = { CATALOG, LABEL, kind, label, glyph: k => GLYPH[kind(k)] || "", badges, own: k => own[k] || "", logo: k => logo[k] || "" };

  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const PALETTE = { yellow: "#f4c430", orange: "#f59a3d", red: "#ef6a6a", pink: "#f08cc4", purple: "#b79cf2", blue: "#7dbbf5", green: "#7fd49b", grey: "#d9d9de" };
  const colour = c => (window.HY_COLORS && window.HY_COLORS[c]) || PALETTE[c] || (/^#[0-9a-f]{3,8}$/i.test(c || "") ? c : "");
  const SIZES = [16, 20, 24, 32];
  const size = v => SIZES.includes(+v) ? +v : 20;
  // «Ann Lee» -> «AL», «ann» -> «A»; a 16 px face has room for one letter
  function initials(name, px) {
    const w = String(name || "").trim().split(/\s+/).filter(Boolean);
    const s = w.length > 1 ? w[0][0] + w[w.length - 1][0] : (w[0] || "?").slice(0, 1);
    return (px <= 16 ? s.slice(0, 1) : s).toUpperCase();
  }
  function inner(o) {
    const px = size(o.size), k = o.agent ? kind(o.agent) : "", c = colour(o.color);
    const src = /^data:image\/(png|jpeg|webp);base64,/.test(o.src || "") ? o.src : "";
    // the initials are drawn by CSS (::before from data-i): they are not words of the line the avatar sits in (its label says who)
    // no picture and no name: the registry's person (owner 2026-10-08), not a «?»
    const anon = !src && !String(o.name || "").trim() && window.hyIcon ? window.hyIcon("person", null, 2.2) : "";
    const face = src ? `<img src="${esc(src)}" alt="" draggable="false">` : anon;
    const glyph = k && window.hyIcon ? window.hyIcon(GLYPH[k], null, 2.6) : "";
    return `<span class="hya-p"${src || anon ? "" : ` data-i="${esc(initials(o.name, px))}"`}${c ? ` style="--hya-c:${c}"` : ""}>${face}</span>`
      + (k ? `<span class="hya-b" data-k="${k}">${glyph}</span>` : "");
  }
  function words(o) {
    const k = o.agent ? kind(o.agent) : "";
    return o.label || (k ? `${LABEL[k]}${o.name ? " · " + o.name : ""}` : o.name || "");
  }
  // the whole element as a string, already filled: the page may write it with innerHTML before or without the element's class
  window.hyAvatarHTML = (o = {}) => {
    const k = o.agent ? kind(o.agent) : "", w = words(o);
    const attrs = [`size="${size(o.size)}"`, o.name ? `name="${esc(o.name)}"` : "", o.color ? `color="${esc(o.color)}"` : "", k ? `agent="${k}"` : "",
      w ? `title="${esc(w)}" aria-label="${esc(w)}"` : "", 'role="img"'].filter(Boolean).join(" ");
    return `<hy-avatar ${attrs}>${inner(o)}</hy-avatar>`;
  };
  // an agent kind's badge alone, as big as a face (Settings › Profile › Agents shows and changes it there)
  window.hyAgentBadgeHTML = (agent, px = 24) => {
    const k = kind(agent) || "agent", glyph = window.hyIcon ? window.hyIcon(GLYPH[k], null, 2.2) : "";
    return `<span class="hya-b hya-solo" data-k="${k}" style="--hya-bs:${size(px)}px" role="img" aria-label="${esc(LABEL[k])}">${glyph}</span>`;
  };
  if (!window.customElements || customElements.get("hy-avatar")) return;
  class HyAvatar extends HTMLElement {
    static observedAttributes = ["size", "name", "color", "src", "agent", "label"];
    // markup written already filled (hyAvatarHTML) is kept as it is: its picture is not an attribute; a change of an attribute redraws
    connectedCallback() { if (this._h === undefined && this.firstElementChild) { this._h = this.innerHTML; this.label(); } else this.sync(); }
    attributeChangedCallback() { if (this.isConnected && this._h !== undefined) this.sync(); }
    label() {
      const w = words({ name: this.getAttribute("name"), agent: this.getAttribute("agent"), label: this.getAttribute("label") });
      if (!this.hasAttribute("role")) this.setAttribute("role", "img");
      if (w) { this.setAttribute("aria-label", w); if (!this.title) this.title = w; }
    }
    sync() {
      const o = { size: this.getAttribute("size"), name: this.getAttribute("name"), color: this.getAttribute("color"), src: this.getAttribute("src") || this._src,
        agent: this.getAttribute("agent"), label: this.getAttribute("label") };
      const h = inner(o);
      if (this._h !== h) this.innerHTML = h;
      this._h = h; this.label();
    }
    set src(v) { this._src = v; this.sync(); }
  }
  customElements.define("hy-avatar", HyAvatar);
})();
