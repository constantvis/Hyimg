// The paper of the board (owner's numbers, tuned in the sandbox 2026-09-30): one file for every page that shows it, the canvas and
// Home (owner 2026-10-04: «Home like the canvas, the same background but without dots»). A plain script: window.hyPaper.
(() => {
  const PAPER = { bg: "#17171a", step: 35, bigEvery: 4, minPx: 17, maxPx: 64, bigR: 1.25, bigA: .11, smallR: .65, smallA: .21,
    grainAmp: .065, grainSize: 1.5, fibres: 26, fibreLen: 8, fibreA: .25 };
  const GRAIN_CACHE = {}, TILE = 256;
  function grainTile(amp, light) {
    const key = amp + "|" + light; if (GRAIN_CACHE[key]) return GRAIN_CACHE[key];
    const DPR = Math.min(2, devicePixelRatio || 1), N = TILE * DPR, c = document.createElement("canvas"); c.width = c.height = N; const g = c.getContext("2d");
    const n = Math.max(8, Math.round(N / (PAPER.grainSize * DPR))), sc = document.createElement("canvas"); sc.width = sc.height = n;
    const sg = sc.getContext("2d"), d = sg.createImageData(n, n), px = d.data;
    for (let i = 0; i < n * n; i++) {
      const v = Math.max(-1, Math.min(1, (Math.random() + Math.random() + Math.random() - 1.5) / 1.5)), white = v > 0, a = Math.abs(v) * amp;
      px[i * 4] = px[i * 4 + 1] = px[i * 4 + 2] = white ? 255 : (light ? 40 : 0); px[i * 4 + 3] = Math.round(Math.min(1, light && white ? a * .6 : a) * 255);
    }
    sg.putImageData(d, 0, 0); g.imageSmoothingEnabled = false; g.drawImage(sc, 0, 0, N, N);
    g.lineCap = "round";
    const tone = light ? [70, 55, 30] : [255, 255, 255];
    for (let k = 0; k < PAPER.fibres; k++) {   // short curved fibres, drawn across the edges so they wrap
      const x = Math.random() * N, y = Math.random() * N, l = PAPER.fibreLen * (.5 + Math.random()) * DPR, t = Math.random() * Math.PI, bend = (Math.random() - .5) * l * .6;
      g.strokeStyle = `rgba(${tone},${Math.min(1, amp * PAPER.fibreA * (.6 + Math.random() * .6))})`; g.lineWidth = (.5 + Math.random() * .5) * DPR;
      for (const ox of [-N, 0, N]) for (const oy of [-N, 0, N]) {
        g.beginPath(); g.moveTo(x + ox, y + oy);
        g.quadraticCurveTo(x + ox + Math.cos(t) * l / 2 - Math.sin(t) * bend, y + oy + Math.sin(t) * l / 2 + Math.cos(t) * bend, x + ox + Math.cos(t) * l, y + oy + Math.sin(t) * l); g.stroke();
      }
    }
    return (GRAIN_CACHE[key] = `url(${c.toDataURL("image/png")})`);
  }
  // grain strength: the middle one is the owner's .065, the others a notch softer and stronger; the light paper needs a bit more to show
  const GRAINS = { graphite: [.025, .045, PAPER.grainAmp, .1], light: [.05, .09, .15, .22] };   // очень тонкое, тонкое, заметное (the owner's), сильное
  const DOTC = { graphite: [255, 255, 255], light: [70, 55, 30] };
  // the paper itself, as a CSS background: its colour and its grain tile; dots stay the canvas's own
  const BOARD = { graphite: "#17171a", light: "#ebe6dc" };
  // the colour may be the owner's own (settings cv.paperDark / cv.paperLight, ui/look.css --paper); BOARD is the default
  const css = (kind, level, color) => `${grainTile(GRAINS[kind][Math.min(3, Math.max(0, level | 0))], kind === "light")} 0 0 / ${TILE}px ${TILE}px repeat, ${color || BOARD[kind]}`;
  // the paper colours as a page has them: put on its root as --paper-d / --paper-l (from the settings, or what is given)
  const apply = (dark, light) => { const st = document.documentElement.style; st.setProperty("--paper-d", dark || BOARD.graphite); st.setProperty("--paper-l", light || BOARD.light); };
  const fromStorage = () => { let d = "", l = ""; try { d = localStorage.getItem("cv.paperDark") || ""; l = localStorage.getItem("cv.paperLight") || ""; } catch {} apply(d, l); return [d || BOARD.graphite, l || BOARD.light]; };
  window.hyPaper = { PAPER, TILE, GRAINS, DOTC, BOARD, grainTile, css, apply, fromStorage };
})();
