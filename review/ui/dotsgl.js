// The board's dots as one live WebGL layer (owner 2026-10-04: «one layer for the dots that works interactively, in sync with the
// movement»; «later effects like gravitational waves when we drop pictures there»; «a setting, WebGL or the ordinary dots, so I can
// compare»). It draws the same grid as the CSS dot layers in canvas.html renderBg: the same spacing, radii, alphas and offset, so the
// two look alike and the switch shows only what WebGL adds. A fragment shader paints every dot of the screen at once; it draws when
// the view changes or a wave runs, never on its own.
// A wave: a ring from a point (a drop), spreading 520 px a second for 2.4 s and fading; as it passes it pushes the dots out and back
// and lights them a little, like a ripple in the grid. Up to 8 at once.
//   const d = hyDotsGL(canvas); d.set({ ox, oy, small, big, bigR, smallR, bigA, smallA, rgb: [r, g, b] }); d.wave(x, y)
window.hyDotsGL = canvas => {
  const gl = canvas.getContext("webgl2", { alpha: true, premultipliedAlpha: true, antialias: false });
  if (!gl) return null;
  const VS = `#version 300 es
in vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
  const FS = `#version 300 es
precision highp float;
uniform vec2 uRes; uniform float uDpr; uniform vec2 uOff; uniform float uSmall, uBig; uniform vec2 uRad; uniform vec2 uA; uniform vec3 uC;
uniform float uT; uniform vec4 uW[8]; uniform int uN;
out vec4 o;
float dotA(vec2 q, float step, float r) {   // the dot of this grid nearest to q (css px): 1 inside its radius, a 0.7 px soft edge
  vec2 g = q - uOff; vec2 c = floor(g / step + 0.5) * step;
  return 1.0 - smoothstep(r, r + 0.7, length(g - c));
}
void main() {
  vec2 q = vec2(gl_FragCoord.x, uRes.y - gl_FragCoord.y) / uDpr;
  float lift = 0.0;
  for (int i = 0; i < 8; i++) {
    if (i >= uN) break;
    vec4 w = uW[i]; float age = uT - w.z; if (age < 0.0 || age > 2.4) continue;
    vec2 dv = q - w.xy; float r = length(dv), front = age * 520.0;
    float band = exp(-pow((r - front) / 70.0, 2.0)), fade = (1.0 - age / 2.4) * (1.0 - age / 2.4);
    float push = sin((r - front) / 70.0 * 3.14159) * band * fade * w.w * 9.0;
    q -= (r > 0.001 ? dv / r : vec2(0.0)) * push;
    lift += band * fade * w.w;
  }
  float ab = dotA(q, uBig, uRad.x) * uA.x;
  float as_ = uSmall > 0.0 ? dotA(q, uSmall, uRad.y) * uA.y : 0.0;
  float a = min(1.0, (ab + as_ * (1.0 - ab)) * (1.0 + lift * 1.8));
  o = vec4(uC * a, a);
}`;
  const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
  let prog;
  try { prog = gl.createProgram(); gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(prog); if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog)); }
  catch (e) { console.warn("dots WebGL:", e.message); return null; }
  const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = n => gl.getUniformLocation(prog, n), U = {}; ["uRes", "uDpr", "uOff", "uSmall", "uBig", "uRad", "uA", "uC", "uT", "uW", "uN"].forEach(n => U[n] = loc(n));
  const t0 = performance.now(); let P = null, waves = [], raf = 0, dead = false;
  const now = () => (performance.now() - t0) / 1000;
  function draw() {
    raf = 0; if (dead || !P) return;
    const dpr = devicePixelRatio || 1, W = Math.round(canvas.clientWidth * dpr), H = Math.round(canvas.clientHeight * dpr);
    if (!W || !H) return;
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    const t = now(); waves = waves.filter(w => t - w[2] < 2.4);
    gl.viewport(0, 0, W, H); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(prog); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    const a = gl.getAttribLocation(prog, "p"); gl.enableVertexAttribArray(a); gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
    gl.uniform2f(U.uRes, W, H); gl.uniform1f(U.uDpr, dpr); gl.uniform2f(U.uOff, P.ox, P.oy); gl.uniform1f(U.uSmall, P.small); gl.uniform1f(U.uBig, P.big);
    gl.uniform2f(U.uRad, P.bigR, P.smallR); gl.uniform2f(U.uA, P.bigA, P.smallA); gl.uniform3f(U.uC, P.rgb[0] / 255, P.rgb[1] / 255, P.rgb[2] / 255);
    gl.uniform1f(U.uT, t); const wv = new Float32Array(32); waves.forEach((w, i) => wv.set(w, i * 4)); gl.uniform4fv(U.uW, wv); gl.uniform1i(U.uN, waves.length);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    if (waves.length) raf = requestAnimationFrame(draw);   // a wave runs: the next frame too; otherwise only when asked
  }
  const ask = () => { if (!raf && !dead) raf = requestAnimationFrame(draw); };
  return {
    set(p) { P = p; ask(); },
    wave(x, y, strength = 1) { waves.push([x, y, now(), strength]); if (waves.length > 8) waves.shift(); ask(); },
    get waving() { return waves.length > 0; },
    destroy() { dead = true; cancelAnimationFrame(raf); const l = gl.getExtension("WEBGL_lose_context"); if (l) l.loseContext(); },
  };
};
