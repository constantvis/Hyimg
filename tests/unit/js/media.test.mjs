// ui/video.js (which address a video plays from), ui/spin.js (the hover turn of a 3D file's sheet) and ui/paper.js (the board's paper)
import test from "node:test";
import assert from "node:assert/strict";
import { page } from "./load.mjs";

/* ---- video.js */
// CEF without proprietary codecs (no H.264, HEVC, AAC) and WebKit (plays them)
const CEF = t => (/avc1|hvc1|mp4a\.40|mp4a\.69/.test(t) ? "" : "probably");
const WEBKIT = () => "probably";
const video = (canPlay, fetch) => { const p = page({ scripts: ["ui/video.js"], canPlay, fetch }); return { p, V: p.window.hyVideo }; };

test("an engine without H.264 plays an H.264 file from the server's WebM copy", () => {
  const { V } = video(CEF);
  assert.equal(V.playable("a/clip.mp4", { vcodec: "h264", acodec: "aac" }), false);
  assert.equal(V.src("a/clip.mp4", { vcodec: "h264", acodec: "aac" }, "&v=3"), "/video?p=a%2Fclip.mp4&fmt=webm&v=3");
});

test("an engine that plays the codecs gets the original file", () => {
  const { V } = video(WEBKIT);
  assert.equal(V.src("a/clip.mp4", { vcodec: "h264", acodec: "aac" }), "/file?p=a%2Fclip.mp4");
});

test("a VP9 webm plays as it is where H.264 does not", () => {
  const { V } = video(CEF);
  assert.equal(V.src("a/clip.webm", { vcodec: "vp9", acodec: "opus" }), "/file?p=a%2Fclip.webm");
});

test("unknown codecs try the original first", () => {
  const { V } = video(CEF);
  assert.equal(V.playable("a/clip.mov", {}), null);
  assert.equal(V.playable("a/clip.mov", { vcodec: "prores" }), null);
  assert.equal(V.src("a/clip.mov", { vcodec: "prores" }), "/file?p=a%2Fclip.mov");
});

test("a decode or format error of the original switches the video to the copy and remembers it for the file", async () => {
  const { V, p } = video(WEBKIT, async () => ({ ok: true, json: async () => ({ state: "working" }) }));
  const v = { error: { code: 4 }, src: "/file?p=a.mov" };
  assert.equal(V.fallback(v, "a.mov", ""), true);
  assert.equal(v.src, "/video?p=a.mov&fmt=webm");
  assert.equal(V.src("a.mov", null), "/video?p=a.mov&fmt=webm", "the next card of that file asks for the copy at once");
  await p.flush();
});

test("a network error of the original is told, not answered with the copy", () => {
  const notes = [];
  const { V } = video(WEBKIT);
  V.note = (t, k) => notes.push([t, k]);
  const v = { error: { code: 2 }, src: "/file?p=a.mov" };
  assert.equal(V.fallback(v, "a.mov"), false);
  assert.deepEqual(notes, [["This video did not load", "error"]]);
});

test("the copy failing too says once that ffmpeg is missing", async () => {
  const notes = [];
  const { V, p } = video(CEF, async () => ({ ok: true, json: async () => ({ state: "noffmpeg" }) }));
  V.note = t => notes.push(t);
  V.fallback({ error: { code: 4 }, currentSrc: "/video?p=a.mp4&fmt=webm" }, "a.mp4");
  V.fallback({ error: { code: 4 }, currentSrc: "/video?p=b.mp4&fmt=webm" }, "b.mp4");
  await p.flush();
  assert.deepEqual(notes, ["This engine does not play H.264, ffmpeg is needed"]);
});

test("the copy is asked for once per file, and again after it failed", async () => {
  let state = "working";
  const { V, p } = video(CEF, async () => ({ ok: true, json: async () => ({ state }) }));
  await Promise.all([V.prep("a.mp4"), V.prep("a.mp4")]);
  assert.equal(p.calls.fetch.length, 1);
  state = "failed";
  assert.equal(await V.prep("b.mp4"), "failed");
  await V.prep("b.mp4");
  assert.equal(p.calls.fetch.length, 3);
});

/* ---- spin.js */
function spin(sp = { sheet: "/api/sprite?p=m.glb", n: 36, cols: 6 }) {
  const p = page({ scripts: ["ui/spin.js"] });
  const list = p.el("div", {}, p.document.body), host = p.el("div", { class: "tile" }, list), pic = p.el("i", {}, host);
  pic.dataset.spin = JSON.stringify(sp); pic.style.backgroundImage = 'url("still.png")'; pic.style.backgroundSize = "cover"; pic.style.backgroundPosition = "50% 50%";
  p.window.hySpin.bind(list, ".tile");
  return { p, host, pic, enter: () => p.fire(pic, "pointerover", { pointerType: "mouse", relatedTarget: null }), leave: () => p.fire(pic, "pointerout", { relatedTarget: null }) };
}

test("hovering a 3D tile steps through the views of its sheet, a turn in three seconds", async () => {
  const { p, pic, enter } = spin();
  enter(); await p.flush();
  assert.equal(pic.dataset.view, "0");
  assert.equal(pic.style.backgroundImage, 'url("/api/sprite?p=m.glb")');
  assert.equal(pic.style.backgroundSize, "600% 600%");
  // the frames come every 16 ms: look in the middle of a view's 83 ms
  const per = 3000 / 36, t0 = p.clock.now, to = k => p.tick(t0 + per * (k + 0.5) - p.clock.now);
  to(7);    // the 8th view: row 1, column 1
  assert.equal(pic.dataset.view, "7");
  assert.equal(pic.style.backgroundPosition, "20% 20%");
  to(35);   // the last view: row 5, column 5
  assert.equal(pic.dataset.view, "35");
  assert.equal(pic.style.backgroundPosition, "100% 100%");
});

test("leaving finishes the turn at three times the speed and puts the still picture back", async () => {
  const { p, pic, enter, leave } = spin();
  enter(); await p.flush();
  p.tick(3000 / 36 * 30.5); assert.equal(pic.dataset.view, "30");
  leave();
  p.tick(100); assert.equal(pic.dataset.view, "33", "on at a view each 28 ms, not snapped back");
  p.tick(120);
  assert.equal(pic.dataset.view, "0");
  assert.equal(pic.style.backgroundImage, 'url("still.png")');
  assert.equal(pic.style.backgroundSize, "cover");
  assert.equal(pic.classList.contains("spinning"), false);
});

test("a touch does not start a turn, nor does a tile without a sheet or with one view", async () => {
  const a = spin();
  a.p.fire(a.pic, "pointerover", { pointerType: "touch" }); await a.p.flush();
  assert.equal(a.pic.dataset.view, undefined);
  const b = spin({ sheet: "s.png", n: 1, cols: 1 });
  b.enter(); await b.p.flush();
  assert.equal(b.pic.dataset.view, undefined);
});

test("a one-row sheet keeps its views at the top", async () => {
  const { p, pic, enter } = spin({ sheet: "s.png", n: 4, cols: 4 });
  enter(); await p.flush(); p.tick(3000 / 4 * 2.5);
  assert.equal(pic.style.backgroundPosition, "66.66666666666666% 0%");
});

/* ---- paper.js */
function paper(storage) {
  const p = page({ scripts: ["ui/paper.js"], storage });
  let canvases = 0; const make = p.document.createElement;
  p.document.createElement = t => { if (t === "canvas") canvases++; return make(t); };
  return { p, P: p.window.hyPaper, canvases: () => canvases };
}

test("the paper is a grain tile over the paper colour, the owner's own colour when given", () => {
  const { P } = paper();
  assert.match(P.css("graphite", 2), /^url\(data:image\/png;base64,FAKE\) 0 0 \/ 256px 256px repeat, #17171a$/);
  assert.match(P.css("light", 1, "#fff8ee"), /, #fff8ee$/);
});

test("a grain level past either end is the nearest level, a fractional one is cut to a whole one", () => {
  const { P, canvases } = paper();
  P.css("graphite", 3); const n = canvases();
  P.css("graphite", 99); P.css("graphite", 3.9);
  assert.equal(canvases(), n, "the strongest tile again, from the cache");
  P.css("graphite", 0); const m = canvases();
  P.css("graphite", -4);
  assert.equal(canvases(), m, "the finest tile again, from the cache");
});

test("the dark and the light paper at the same strength are two tiles", () => {
  const { P, canvases } = paper();
  P.grainTile(0.1, false); const n = canvases();
  P.grainTile(0.1, true);
  assert.ok(canvases() > n);
});

test("the paper colours come from the settings, the defaults when there are none", () => {
  const a = paper({ "cv.paperDark": "#101010" });
  assert.deepEqual([...a.P.fromStorage()], ["#101010", "#ebe6dc"]);
  assert.equal(a.p.document.documentElement.style.getPropertyValue("--paper-d"), "#101010");
  assert.equal(a.p.document.documentElement.style.getPropertyValue("--paper-l"), "#ebe6dc");
  const b = paper();
  assert.deepEqual([...b.P.fromStorage()], ["#17171a", "#ebe6dc"]);
});
