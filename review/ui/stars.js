// The stars of a board opening (owner 2026-10-04). Act 1, while the board loads: about 700 stars fly at the viewer, gathering speed,
// fast and then slower, each appearing on its own, one brighter, another dimmer («like stars from space»). Act 2, once it is loaded:
// the canvas is a flat plane at a certain depth; every star that has not reached it slows down until it stops on the plane, the ones
// that have passed it fly on and leave the screen («they do not just vanish»), and every other dot of the board's grid gets a star of
// its own from far away, so the whole grid arrives; then the board's own dot layer takes over.
// Every star flies on a straight line from the window's centre, and keeps it for its whole pass («a star flies on an arc, it changes
// its path»: the lines used to move onto the grid while the stars flew, and the near ones swung sideways). A line goes through the
// grid dot nearest the star's own place, for the grid known when the star's pass began (Home starts with a plain grid and gets the
// board's a moment later; a star takes it at its next pass, when it starts again far away, too small to see). Landing, a star eases
// the last bit onto the dot of the board's latest grid.
// The field is drawn in a worker on an OffscreenCanvas where the page allows it (its frames do not wait for the board's loading).
// One field for Home and the canvas: every star is a function of a seed, a start time (Date.now()) and the grids with the moments
// they came (specs), so the canvas carries Home's field on after the swap from the same moment.
// window.hyStars(canvas, {seed, t0, spec | specs, origin}); spec: {px, big, base: [x, y] (stage), ox, oy (stage in the window), w, h,
// rgb, bigR, smallR, bigA, smallA}; specs: [{s: spec, at: Date.now() it came}]; origin: where the drawing canvas sits in the window.
(() => {
  function FIELD(env) {
    const N = 700, V0 = .95, V1 = .14, TAU = .7, QP = .4, NEAR = .04;   // depth per second: fast, then a slow cruise; the plane's depth
    const travel0 = t => V1 * t + (V0 - V1) * TAU * (1 - Math.exp(-t / TAU));
    const RAMP = .5, warp = t => t - RAMP * (1 - Math.exp(-t / RAMP)), travel = t => travel0(warp(t));   // a soft start: from standstill
    const speed = t => (V1 + (V0 - V1) * Math.exp(-warp(t) / TAU)) * (1 - Math.exp(-t / RAMP));
    const timeAt = d => { let a = 0, b = 1; while (travel(b) < d) b *= 2; for (let k = 0; k < 40; k++) { const m = (a + b) / 2; if (travel(m) < d) a = m; else b = m; } return b; };
    const hash = (seed, i, k) => {
      let h = (seed ^ Math.imul(i + 1, 0x27d4eb2d) ^ Math.imul(k + 1, 0x9e3779b9)) >>> 0;
      h = Math.imul(h ^ (h >>> 15), 0x85ebca6b); h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35); return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
    };
    return (cv, o, post) => {
      let seed = o.seed >>> 0, t0 = o.t0, specs = o.specs || [{ s: o.spec, at: 0 }], origin = o.origin || [0, 0], C = o.C || [450, 300], R = o.R || 900;
      let W = o.w || 1, H = o.h || 1, dpr = o.dpr || 1, stars = [], landAt = 0, mul = 1, fadeAt = 0, fadeMs = 600, alive = true, raf = 0;
      const latest = () => specs[specs.length - 1].s;
      const specFor = abs => { let r = specs[0].s; for (const x of specs) if (x.at <= abs) r = x.s; return r; };
      const snap = (st, s) => {   // the grid dot nearest the star's own place, as a line from the window's centre
        const k = Math.max(1, Math.round((s.big || s.px * 4) / s.px));
        const i = Math.round((C[0] + st.rx - s.ox - s.base[0]) / s.px), j = Math.round((C[1] + st.ry - s.oy - s.base[1]) / s.px);
        const big = ((i % k) + k) % k === 0 && ((j % k) + k) % k === 0;
        return { x: s.ox + s.base[0] + i * s.px - C[0], y: s.oy + s.base[1] + j * s.px - C[1], r: big ? s.bigR : s.smallR, a: big ? s.bigA : s.smallA, key: i + "," + j };
      };
      const pass = (st, D) => {   // the star's present pass: when its count changes it has started again far away, and takes its line then
        const u = 1 - st.z + D, n = Math.floor(u);
        if (n !== st.n) {
          st.n = n; const d = snap(st, specFor(t0 + (n <= 0 ? 0 : timeAt(n - 1 + st.z)) * 1000));
          st.lx = d.x; st.ly = d.y; st.dotR = d.r; st.dotA = d.a; st.key = d.key;
        }
        return NEAR + (1 - (u - n));   // its depth: far 1.04 ... here .04
      };
      const build = () => {
        stars = [];
        for (let i = 0; i < N; i++) {
          const ang = hash(seed, i, 0) * 6.2832, rad = (.03 + Math.sqrt(hash(seed, i, 1)) * .97) * R;
          stars.push({ rx: Math.cos(ang) * rad, ry: Math.sin(ang) * rad, z: hash(seed, i, 2), b: .35 + hash(seed, i, 3) * .65, f: 1.2 + hash(seed, i, 4) * 2.8,
            p: hash(seed, i, 5) * 6.2832, s: .55 + hash(seed, i, 6) * .7, born: .1 + hash(seed, i, 7) * 1.0, n: null });   // each star appears at its own moment
        }
        landAt = 0;
      };
      const draw = () => {
        if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
        const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
        const now = Date.now(), t = Math.max(0, (now - t0) / 1000), cx = C[0] - origin[0], cy = C[1] - origin[1];
        const fade = fadeAt ? Math.max(0, 1 - (now - fadeAt) / fadeMs) : 1, all = fade * mul;
        if (all <= 0) return;
        const tl = landAt ? (landAt - t0) / 1000 : 0, vl = landAt ? speed(tl) : 0, D = travel(t);
        const buckets = new Map();
        for (const st of stars) {
          if (landAt && st.qb === undefined && st.born > tl) continue;   // not born before the plane came on: a star of the grid takes its dot
          const app = Math.min(1, Math.max(0, (t - st.born) / .5)); if (app <= 0) continue;   // not there yet; then it fades in on its own
          let q, w = 0, lx, ly;
          if (!landAt) { q = pass(st, D); lx = st.lx; ly = st.ly; }
          else if (st.qb >= QP && !st.past) {   // slows down onto the plane, onto its dot
            const u = Math.min(1, Math.max(0, (t - Math.max(tl, st.born)) / st.T)), e = u * u * (3 - 2 * u);
            q = QP + (st.qb - QP) * Math.pow(1 - u, 3); w = u * u; lx = st.lx + (st.tx - st.lx) * e; ly = st.ly + (st.ty - st.ly) * e;
          } else { q = st.qb - vl * (t - tl); if (q <= NEAR) continue; lx = st.lx; ly = st.ly; }   // it had passed the plane: on it goes, out of the screen
          if (lx === undefined) continue;
          const x = cx + lx * QP / q, y = cy + ly * QP / q;
          if (x < -4 || y < -4 || x > W + 4 || y > H + 4) continue;
          const near = 1.04 - q, tw = .55 + .45 * Math.sin(t * st.f + st.p), born = landAt ? 1 : Math.min(1, near / .12);
          const fa = st.dim ? Math.min(st.b * tw * (.25 + .75 * near), st.dotA * 2) : st.b * tw * born * (.25 + .75 * near);
          const fr = st.dim ? Math.min(st.s * (.5 + near * 1.3), st.dotR + .6) : st.s * (.5 + near * 1.3);   // the grid's own stars stay near its look
          const a = all * app * (fa + (st.dotA - fa) * w), r = fr + (st.dotR + .35 - fr) * w;   // as it lands it takes the look of its grid dot
          if (a < .008) continue;
          const key = Math.min(40, Math.round(a * 40)); let path = buckets.get(key); if (!path) buckets.set(key, path = new Path2D());
          if (r < 1.1) path.rect(x - r, y - r, r * 2, r * 2); else { path.moveTo(x + r, y); path.arc(x, y, r, 0, 6.2832); }
        }
        const [cr, cg, cb] = latest().rgb || [255, 255, 255];
        for (const [key, path] of buckets) { g.fillStyle = `rgba(${cr},${cg},${cb},${(key / 40).toFixed(3)})`; g.fill(path); }
      };
      const loop = () => { if (!alive) return; draw(); raf = env.raf(loop); };
      build(); loop();
      return {
        take(p) { seed = p.seed >>> 0; t0 = p.t0; if (p.specs) specs = p.specs; build(); },   // carry on Home's field, its grids and when they came
        setSpec(s, org, at) { specs.push({ s, at: at || Date.now() }); if (specs.length > 4) specs.splice(1, 1); if (org) origin = org; },   // stars take it at their next pass
        // the plane comes on (at the page's moment): the stars short of it will land on the latest grid; every other dot of it on the
        // screen gets a dim star of its own from far away, over 1.2 s, none for the faint small dots (the grid's fade brings those)
        land(at) {
          if (landAt) return; landAt = at || Date.now(); const tl = (landAt - t0) / 1000, Dl = travel(tl), taken = new Set(), sp = latest(); let landMax = 1;
          for (const st of stars) {
            if (st.born > tl) continue;
            st.qb = pass(st, Dl); st.T = 1 + 2.2 * Math.max(0, st.qb - QP);
            const d = snap(st, sp), onLine = d.key === st.key && Math.abs(d.x - st.lx) < .01 && Math.abs(d.y - st.ly) < .01;
            // only a star already on its line to a dot of this grid lands, exactly there; one still on an older grid's line flies past
            // and its dot gets a star from far away («wait for the right stars, once the coordinates are clear; no sharp transition»)
            if (st.qb >= QP && onLine) { st.tx = d.x; st.ty = d.y; st.dotR = d.r; st.dotA = d.a; taken.add(d.key); landMax = Math.max(landMax, st.T); }
            else st.past = true;
          }
          const k = Math.max(1, Math.round((sp.big || sp.px * 4) / sp.px));
          const i0 = Math.floor(-sp.base[0] / sp.px), i1 = Math.ceil((sp.w - sp.base[0]) / sp.px), j0 = Math.floor(-sp.base[1] / sp.px), j1 = Math.ceil((sp.h - sp.base[1]) / sp.px);
          let n = 0;
          for (let i = i0; i <= i1; i++) for (let j = j0; j <= j1; j++) {
            if (taken.has(i + "," + j)) continue;
            const big = ((i % k) + k) % k === 0 && ((j % k) + k) % k === 0, a = big ? sp.bigA : sp.smallA; if (a < .06) continue;
            const h = m => hash(seed, 100000 + n * 7 + m, 9), qb = .55 + h(0) * .49, born = tl + h(1) * 1.2, T = 1 + 2.2 * (qb - QP);
            const x = sp.ox + sp.base[0] + i * sp.px - C[0], y = sp.oy + sp.base[1] + j * sp.px - C[1]; n++;
            stars.push({ lx: x, ly: y, tx: x, ty: y, dotR: big ? sp.bigR : sp.smallR, dotA: a, key: i + "," + j, qb, T, born, z: 0, dim: true,
              b: .35 + h(2) * .65, f: 1.2 + h(3) * 2.8, p: h(4) * 6.2832, s: .55 + h(5) * .7 });
            landMax = Math.max(landMax, born - tl + T);
          }
          post({ landMax });
        },
        mul(v) { mul = v; },
        size(w, h, d) { W = w; H = h; dpr = d; },
        fadeOut(ms) { fadeAt = Date.now(); fadeMs = ms; },
        stop() { alive = false; env.caf(raf); },
      };
    };
  }
  window.hyStarsDefaultSpec = (w, h, rgb) => ({ px: 32, big: 128, base: [0, 0], ox: 0, oy: 0, w, h, rgb, bigR: 1.25, smallR: .65, bigA: .11, smallA: .21 });
  window.hyStars = (cv, o) => {
    const [TW, TH] = (() => { try { return [top.innerWidth, top.innerHeight]; } catch { return [innerWidth, innerHeight]; } })();   // the window's: the same on Home and in the canvas
    let specs = o.specs ? o.specs.slice() : [{ s: o.spec, at: 0 }];
    const opts = { seed: o.seed >>> 0, t0: o.t0, specs, origin: o.origin || [0, 0], C: [TW / 2, TH / 2], R: Math.hypot(TW, TH) / 2,
      w: cv.clientWidth || innerWidth, h: cv.clientHeight || innerHeight, dpr: devicePixelRatio || 1 };
    let params = { seed: opts.seed, t0: opts.t0 }, landAt = 0, landMax = 0, send, kill, dead = false, mode = "page", why = "";
    const got = d => { if (d && d.landMax) landMax = d.landMax; };
    try {
      if (typeof cv.transferControlToOffscreen !== "function" || typeof Worker === "undefined") throw 0;
      const src = `const FIELD = ${FIELD.toString()};
        const make = FIELD({ raf: f => self.requestAnimationFrame ? requestAnimationFrame(f) : setTimeout(f, 16), caf: id => self.cancelAnimationFrame ? cancelAnimationFrame(id) : clearTimeout(id) });
        let api; onmessage = e => { const m = e.data; if (m.cmd === "init") api = make(m.canvas, m.o, d => postMessage(d)); else if (api) api[m.cmd](...(m.args || [])); };`;
      // its size before it goes to the worker: a size the worker sets has to be shown by the page's own thread, which is busy laying the
      // board out, so the stars stayed unseen until the board was drawn (owner 2026-10-04: «on a reload it does not start from the start»)
      cv.width = Math.round(opts.w * opts.dpr); cv.height = Math.round(opts.h * opts.dpr);
      const url = URL.createObjectURL(new Blob([src], { type: "text/javascript" })), w = new Worker(url), off = cv.transferControlToOffscreen();
      w.onmessage = e => got(e.data);
      w.postMessage({ cmd: "init", canvas: off, o: opts }, [off]);
      send = (cmd, ...args) => w.postMessage({ cmd, args });
      kill = () => { w.terminate(); URL.revokeObjectURL(url); };
      w.onerror = e => { why = "worker error: " + (e.message || e.type); };
      mode = "worker";
    } catch (e) {   // no worker for it here: the same field on this page's own frames
      why = String(e && e.message || e);
      // a copy of the grids: the field keeps its own list, and with this one shared every setSpec pushed twice (unit test, 2026-10-06)
      const api = FIELD({ raf: requestAnimationFrame.bind(window), caf: cancelAnimationFrame.bind(window) })(cv, Object.assign({}, opts, { specs: specs.slice() }), got);
      send = (cmd, ...args) => api[cmd](...args); kill = () => api.stop();
    }
    const fit = () => { if (!dead) send("size", cv.clientWidth || innerWidth, cv.clientHeight || innerHeight, devicePixelRatio || 1); };
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(fit) : null; if (ro) ro.observe(cv);
    const stop = () => { if (dead) return; dead = true; if (ro) ro.disconnect(); send("stop"); kill(); cv.remove(); };
    return {
      get params() { return { seed: params.seed, t0: params.t0, specs }; },
      get mode() { return mode + (why ? " (" + why + ")" : ""); },   // where it draws: «worker» or «page», and why not in a worker
      same(s) { const l = specs[specs.length - 1].s, k = x => [x.px, x.big, x.base[0], x.base[1], x.ox, x.oy, x.w, x.h].map(v => Math.round(v * 100)).join(); return !!l && k(l) === k(s); },
      age() { return (Date.now() - params.t0) / 1000; },
      take(p) {
        if (p.seed >>> 0 === params.seed && p.t0 === params.t0) return;
        params = { seed: p.seed >>> 0, t0: p.t0 }; if (p.specs) specs = p.specs.slice(); send("take", { seed: params.seed, t0: params.t0, specs: specs.slice() });
      },
      setSpec(s, org) { const at = Date.now(); specs.push({ s, at }); if (specs.length > 4) specs.splice(1, 1); send("setSpec", s, org, at); },
      land() { if (landAt) return; landAt = Date.now(); send("land", landAt); },
      progress() { return landAt && landMax ? Math.min(1, (Date.now() - landAt) / 1000 / landMax) : 0; },   // 1: every star that could land has
      set mul(v) { send("mul", v); },
      fadeOut(ms) { send("fadeOut", ms); setTimeout(stop, ms + 60); },
      stop,
    };
  };
})();
