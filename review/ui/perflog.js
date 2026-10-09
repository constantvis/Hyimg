// The performance log on the board (owner 2026-10-08: «нужен механизм дебага: лог, который пишется, только когда падает частота кадров,
// с тем, что было на экране»). On by default (owner 2026-10-08), Settings › Diagnostics › Performance log (cv.perflog "0" turns it off). On, the board watches its
// frames only while the person works (a wheel, a pinch, a drag, a key, and 1.5 s after) and, in Chromium, long tasks at rest; when frames
// drop (3 frames over 50 ms within a second, or one over 250 ms) it sends the server one entry with what was on screen
// (review/perflog.py writes it into the app's cache, ~/Library/Caches/Hyimg/perf). One entry per 5 s at most; the ones held back are
// counted in the next («dropped»). Nothing runs while the log is off but one cheap check on input.
//   hyPerfLog.snapshot()   what an entry says about the board now      hyPerfLog.on()   whether the log is on
(() => {
  if (window.hyPerfLog) return;
  const SLOW = 50, MANY = 3, FREEZE = 250, WIN = 1000, QUIET = 500, IDLE = 1500, GAP = 5000, LONGEST = 3000, CALM = 5000;   // ms
  const on = () => { try { return localStorage.getItem("cv.perflog") !== "0"; } catch { return true; } };
  const G = name => { try { return window.eval(`typeof ${name} === "undefined" ? undefined : ${name}`); } catch { return undefined; } };   // the board's own (let) state
  let act = { kind: "idle", t: 0 }, raf = 0, last = 0, lastInput = 0, ep = null, sentAt = -1e9, dropped = 0;
  const recent = [];   // [time, ms] of slow frames in the last second

  // what the person is doing: a pinch or ⌘ wheel zooms, a wheel pans, a press and move drags, a key
  function input(kind) {
    if (!on()) return;
    act = { kind, t: performance.now() }; lastInput = act.t;
    if (!raf) { last = performance.now(); raf = requestAnimationFrame(tick); }
  }
  addEventListener("wheel", e => input(e.ctrlKey || e.metaKey ? "zoom" : "pan"), { capture: true, passive: true });
  addEventListener("pointerdown", () => input("press"), { capture: true, passive: true });
  addEventListener("pointermove", e => { if (e.buttons) input("drag"); }, { capture: true, passive: true });
  addEventListener("keydown", () => input("key"), { capture: true, passive: true });

  function action() {
    const d = G("drag"), z = act.kind;
    if (d && d.mode) return "drag:" + d.mode;
    if (G("gesture") && (z === "zoom" || z === "pan")) return z;
    return performance.now() - act.t < IDLE ? z : "idle";
  }
  function tick(now) {
    const dt = now - last; last = now;
    if (dt > SLOW) { recent.push([now, dt]); if (ep) { ep.slow++; ep.worst.push(dt); } }
    while (recent.length && now - recent[0][0] > WIN) recent.shift();
    if (ep) { ep.n++; ep.all.push(dt); ep.end = now; }
    if (!ep && (recent.length >= MANY || dt >= FREEZE)) begin(now, recent.map(r => r[1]));
    if (ep && (now - (recent.length ? recent[recent.length - 1][0] : 0) > QUIET || now - ep.t0 > LONGEST)) finish();   // 3 s at most: a long lag is several
    if (now - lastInput > IDLE && !ep) { raf = 0; recent.length = 0; return; }
    raf = requestAnimationFrame(tick);
  }
  function begin(now, slow) {
    ep = { t0: now, end: now, n: slow.length, slow: slow.length, worst: [...slow], all: [...slow], action: action(), snap: null };
    if (performance.now() - sentAt >= GAP) { try { ep.snap = snapshot(); } catch (e) { ep.snap = { error: String(e).slice(0, 200) }; } }
  }
  function finish() {
    const e = ep; ep = null; recent.length = 0; if (!e) return;
    if (!e.snap) { dropped++; return; }   // held back by the 5 s rule
    const all = e.all.slice().sort((a, b) => a - b), r = x => Math.round(x * 10) / 10;
    send({ ...e.snap, action: e.action, frames: { n: e.n, slow: e.slow, ms: Math.round(e.end - e.t0), median: r(all[all.length >> 1] || 0),
      worst: e.worst.sort((a, b) => b - a).slice(0, 6).map(r) } });
  }
  function send(entry) {
    if (!on()) return;   // turned off mid-episode: nothing goes, and the next one is not held back by it
    sentAt = performance.now(); entry.dropped = dropped; dropped = 0;
    const body = JSON.stringify(entry);
    if (body.length > 15000) return;
    fetch("/api/perflog", { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true }).catch(() => {});
  }
  // at rest: a long task (Chromium only) over the freeze line is an episode of its own
  try {
    new PerformanceObserver(l => {
      if (!on() || raf || ep || performance.now() < CALM) return;   // the board's own start is not a lag
      for (const t of l.getEntries()) {
        if (t.duration < FREEZE || performance.now() - sentAt < GAP) { if (t.duration >= FREEZE) dropped++; continue; }
        act = { kind: "idle", t: 0 }; begin(performance.now(), [t.duration]); finish();
      }
    }).observe({ type: "longtask", buffered: false });
  } catch {}

  // what was on screen -----------------------------------------------------------------------------------------------------------------
  function engine() {
    const ua = navigator.userAgent;
    if (/HyimgCEF/.test(ua)) return "chromium (app)";
    let wk = false; try { wk = !!(window.top.webkit && window.top.webkit.messageHandlers); } catch {}
    return wk ? "webkit (app)" : /Chrome\//.test(ua) ? "chrome" : /Safari\//.test(ua) ? "safari" : "other";
  }
  function snapshot() {
    const board = G("board") || { items: {}, groups: {} }, EL = G("EL"), cam = G("cam") || {}, LOD = G("LOD") || {};
    const kindOf = it => it.type || (it.path ? "pic" : "other");
    const items = {}; for (const it of Object.values(board.items || {})) items[kindOf(it)] = (items[kindOf(it)] || 0) + 1;
    const visible = {};
    const lod = !!LOD.on;
    if (EL) for (const [id, el] of EL) {
      const it = board.items[id]; if (!it || el.hidden) continue;
      if (lod && !it.type) continue;   // far out the pictures are drawn into one canvas, their elements are hidden by the class
      visible[kindOf(it)] = (visible[kindOf(it)] || 0) + 1;
    }
    if (lod) {   // far out the pictures are drawn into one canvas: the ones in the view
      const st = document.getElementById("stage"), w = (st ? st.clientWidth : innerWidth) / cam.z, h = (st ? st.clientHeight : innerHeight) / cam.z;
      visible["pic (canvas)"] = Object.values(board.items || {}).filter(it => !it.type && it.path && it.x < cam.x + w && it.x + it.w > cam.x
        && it.y < cam.y + h && it.y + it.w / (it.ar || 1) > cam.y).length;
    }
    let px = 0, imgs = 0;
    for (const im of document.querySelectorAll("#world img, #ntf img")) {
      if (!im.complete || !im.naturalWidth || !im.getClientRects().length) continue;
      imgs++; px += im.naturalWidth * im.naturalHeight;
    }
    const q = s => document.querySelectorAll(s).length, has = s => !!document.querySelector(s);
    const setOf = G("setOf"), mode = setOf ? String(setOf("lod")) : "";
    const mem = performance.memory;
    return {
      v: 1, board: (window.hyLink && hyLink.project) || "", title: document.title, page: G("BOARD") || "",
      pageTitle: ((G("pages") || []).find?.(p => p.id === G("BOARD")) || {}).title || "",
      zoom: Math.round((cam.z || 0) * 1000) / 1000, engine: engine(), window: [innerWidth, innerHeight, devicePixelRatio || 1],
      lod: { mode: { 0: "standard", 1: "canvas", 2: "webgl" }[mode] || mode || "?", far: lod, gl: has("#world.gl") },
      counts: {
        items, visible, groups: Object.keys(board.groups || {}).length, notes: items.note || 0,
        iframes: q("iframe"), liveFrames: q("#world iframe"), pins: q(".cmpin"), areas: q(".cmarea"), dots: q(".mk-note i"),
        imgs, decodedMB: Math.round(px * 4 / 1e6), nodes: document.getElementsByTagName("*").length,
      },
      panels: { bell: has("#ntf.open"), bellRows: q("#ntf.open .nt"), library: (G("INSET") || 0) > 0, settings: has("#sets.open"),
        history: has("#hist.open"), studio: has("body.dvedit") || has(".plg-live"), selected: (G("sel") || new Set()).size },
      heapMB: mem ? Math.round(mem.usedJSHeapSize / 1e6) : null, glass: has("#stage.glass"), theme: document.documentElement.dataset.theme || "",
    };
  }
  window.hyPerfLog = { on, snapshot, get state() { return { running: !!raf, episode: !!ep, dropped, sentAt }; } };
})();
