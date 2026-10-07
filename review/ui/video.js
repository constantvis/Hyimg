// Which address a video plays from (owner 2026-10-05: «не проигрывается видео когда нажимаю на play»). The app's Chromium is a CEF
// build without proprietary codecs: it has no H.264, HEVC or AAC (measured in the bundled CEF 154: canPlayType of avc1 is "", an H.264
// mp4 fails with MEDIA_ERR_SRC_NOT_SUPPORTED, "FFmpegDemuxer: no supported streams"), while VP9, AV1 and Opus play. So a page asks
// here first: when its engine cannot play a file's codecs (the server reads them with ffprobe: vcodec, acodec in /api/items), it plays
// /video?p=..&fmt=webm, a VP9 copy the server makes once with ffmpeg (webvideo.py). WebKit and a full Chrome play the original as before.
// A file whose codecs are not known yet (a server not restarted) tries the original and comes here on its error (fallback).
//   hyVideo.src(path, meta, ver)   the address to give a <video>
//   hyVideo.prep(path)             start the copy in the background (a card came on screen), once per file
//   hyVideo.fallback(v, path, ver) after an error of the original: true when it switched v to the copy
//   hyVideo.note = fn              how the page shows a note (its toast)
(() => {
  const probe = document.createElement("video");
  const VC = { h264: "avc1.640028", hevc: "hvc1.1.6.L93.B0", vp9: "vp09.00.10.08", vp8: "vp8", av1: "av01.0.05M.08", mpeg4: "mp4v.20.9" };
  const AC = { aac: "mp4a.40.2", mp3: "mp4a.69", opus: "opus", vorbis: "vorbis", flac: "flac" };
  const enc = encodeURIComponent, WEB = new Set(), PREP = new Map();
  // the words in the app's language (ui/i18n.js; its Russian in ui/lang-common.js, owner 2026-10-06); a page without i18n.js: English
  const t = (k, v) => window.T ? window.T(k, v) : String(k).replace(/^\w+::/, "").replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m));
  let told = false;
  const support = {};   // for the live report: what this engine says it plays
  [["h264", 'video/mp4; codecs="avc1.640028"'], ["aac", 'audio/mp4; codecs="mp4a.40.2"'], ["hevc", 'video/mp4; codecs="hvc1.1.6.L93.B0"'],
   ["vp9", 'video/webm; codecs="vp9"'], ["opus", 'audio/webm; codecs="opus"']].forEach(([k, t]) => { support[k] = probe.canPlayType(t) || "no"; });
  // true: this engine cannot play the file, false: it can, null: not known (no codecs from the server, or a codec with no mime name)
  function playable(path, m) {
    const vc = m && m.vcodec; if (!vc) return null;
    if (!VC[vc]) return null;   // ProRes and the like: only the original's error tells
    const ext = (path.split(".").pop() || "").toLowerCase(), mime = ext === "webm" ? "video/webm" : "video/mp4";
    const codecs = [VC[vc], m.acodec && AC[m.acodec]].filter(Boolean).join(", ");
    return probe.canPlayType(`${mime}; codecs="${codecs}"`) !== "";
  }
  const needsWeb = (path, m) => WEB.has(path) || playable(path, m) === false;
  const webSrc = (path, ver) => `/video?p=${enc(path)}&fmt=webm${ver || ""}`;
  const note = text => { const f = window.hyVideo.note || window.hyToast || console.log; f(text, "error"); };
  function noFfmpeg() { if (!told) { told = true; note(t("This engine does not play H.264, ffmpeg is needed")); } }
  async function prep(path) {
    if (PREP.has(path)) return PREP.get(path);
    const p = fetch(`/video?p=${enc(path)}&fmt=webm&prep=1`).then(r => r.ok ? r.json() : { state: "failed" }).then(d => {
      if (d.state === "noffmpeg") noFfmpeg();
      if (d.state === "failed" || d.state === "noffmpeg") PREP.delete(path);   // asked again next time (ffmpeg may come)
      return d.state;
    }).catch(() => { PREP.delete(path); return "failed"; });
    PREP.set(path, p); return p;
  }
  window.hyVideo = {
    support, playable, needsWeb, webSrc, prep,
    isWeb: src => /\/video\?/.test(src || ""),
    src: (path, m, ver) => needsWeb(path, m) ? webSrc(path, ver) : `/file?p=${enc(path)}${ver || ""}`,
    // the original failed (MEDIA_ERR_DECODE 3, MEDIA_ERR_SRC_NOT_SUPPORTED 4): the copy, unless it was the copy that failed
    fallback(v, path, ver) {
      const code = v.error && v.error.code;
      if (window.hyVideo.isWeb(v.currentSrc || v.src)) { window.hyVideo.failed(path); return false; }
      if (code !== 3 && code !== 4) { note(t("This video did not load")); return false; }
      WEB.add(path); prep(path); v.src = webSrc(path, ver); return true;
    },
    // the copy failed too: say why once (no ffmpeg) or that this file does not play
    failed(path) {
      fetch(`/video?p=${enc(path)}&fmt=webm&prep=1`).then(r => r.json()).then(d => {
        if (d.state === "noffmpeg") noFfmpeg(); else note(t("This video does not play: ffmpeg could not read it"));
      }).catch(() => note(t("This video does not play in this browser: its format or codec")));
    },
  };
})();
