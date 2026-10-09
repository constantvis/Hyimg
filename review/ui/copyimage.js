// ⇧⌘C and right click › Copy as › Image for every card that is a picture on the board (owner 2026-10-09: «Я хочу любой объект скопировать
// по нажатию ⌘⇧C. Именно имею в виду video, photo, HTML — в виде картинки, или PDF в виде картинки»). Until then only a picture file could.
// A PNG goes on the system clipboard, so it pastes into Telegram, Figma, Mail, Photoshop:
//   a picture   the file at full size, its crop applied (as before)
//   a video     the frame the card shows: where it stands while it plays or holds, else its poster's (1 s in), at the video's own size,
//               drawn by the server's ffmpeg (copyimg.py); without ffmpeg the <video> on the card or the poster
//   a PDF       the card's page as the large preview draws it (2048 px), its crop applied
//   an HTML page (Dev Studio's card, the frames plugin's HTML frame) the page at the card's viewport (vw × vh css px) at 2×, drawn on demand
//               by the renderer of HTML stills (render_html.py through copyimg.py); if that fails, the still the card shows
//   a plugin's other card (a 3D scene, an image frame) its still: the picture the card shows (HY.surface or its biggest <img>), at full size
// Notes and texts are not pictures: no Image row, ⇧⌘C says so. With several selected the one clicked is copied (the menu) or the first
// selected that can be (⇧⌘C), and the note says it was the first; Figma's Copy as PNG makes one picture of the whole selection, not done.
// The clipboard is the page's (ClipboardItem with a promise, made at once inside the key press or the click, as WebKit wants); the app's
// Chromium and WebKit both take image/png from it, so no native call is needed.
(() => {
  const enc = encodeURIComponent, HTML = new Set(["html", "htmlframe"]), PDF_PX = 2048;
  const T_ = (k, v) => (window.T ? window.T(k, v) : k);
  // what the card is for its picture: "image", "video", "pdf", "html", "card" (a plugin's), or "" (a note, a text, a timeline, a group)
  function kindOf(it) {
    if (!it) return "";
    if (isPic(it)) return isPdf(it) ? "pdf" : isVid(it) ? "video" : "image";
    if (HTML.has(it.type) && typeof it.src === "string") return "html";
    return isNote(it) || isText(it) || isTl(it) ? "" : "card";
  }
  // the element a plugin's card shows its picture in, once something is drawn there: its own surface, else its biggest <img>
  const drawn = s => !!s && (s.tagName === "IMG" ? s.complete && s.naturalWidth > 0 : s.tagName === "VIDEO" ? s.readyState >= 2 : s.width > 0 && s.height > 0);
  function surfaceOf(id) {
    const el = EL.get(id); if (!el) return null;
    const s = HY.surface(el); if (drawn(s)) return s;
    const imgs = [...el.querySelectorAll("img")].filter(i => i.naturalWidth && i.isConnected), area = i => i.naturalWidth * i.naturalHeight;
    return imgs.sort((a, b) => area(b) - area(a))[0] || null;
  }
  // "" when the card can be copied as a picture, else why not
  function why(id) {
    const it = board.items[id], k = kindOf(it);
    if (!k) return board.groups[id] ? T_("Select a card in the group") : T_("Only a picture, a video, a PDF, an HTML page or a 3D scene");
    return k === "card" && !surfaceOf(id) ? T_("This card has no picture yet") : "";
  }
  const get = async url => { const r = await fetch(url); if (!r.ok) throw new Error((await r.text()).slice(0, 120) || r.status); return r.blob(); };
  // a picture (an ImageBitmap, a <video>, a <canvas>, an <img>) as a PNG, its crop [x0, y0, x1, y1] applied
  async function png(src, crop, blob) {
    const img = src.tagName === "IMG", c = crop || [0, 0, 1, 1];
    const W = img ? src.naturalWidth : src.videoWidth || src.width, H = img ? src.naturalHeight : src.videoHeight || src.height;
    if (!W || !H) throw new Error(T_("nothing drawn yet"));
    const sx = Math.round(c[0] * W), sy = Math.round(c[1] * H), w = Math.round((c[2] - c[0]) * W), h = Math.round((c[3] - c[1]) * H);
    if (blob && !crop) return { blob, w, h };   // a PNG from the server as it came
    const cv = document.createElement("canvas"); cv.width = w; cv.height = h; cv.getContext("2d").drawImage(src, sx, sy, w, h, 0, 0, w, h);
    return { blob: await new Promise((ok, no) => cv.toBlob(b => (b ? ok(b) : no(new Error("png"))), "image/png")), w, h };
  }
  const fromUrl = async (url, crop) => { const b = await get(url); return png(await createImageBitmap(b), crop, b.type === "image/png" ? b : null); };
  // the full-size file behind a picture the card shows: /thumb?p=X (a step of it) becomes /img?p=X
  function full(img) {
    const u = new URL(img.currentSrc || img.src, location.href);
    return u.pathname === "/thumb" && u.searchParams.get("p") ? `/img?p=${enc(u.searchParams.get("p"))}${u.searchParams.get("v") ? "&v=" + u.searchParams.get("v") : ""}` : u.href;
  }
  async function still(id) {
    const s = surfaceOf(id); if (!s) throw new Error(T_("This card has no picture yet"));
    if (s.tagName === "IMG") { try { return await fromUrl(full(s)); } catch { return png(s); } }
    return png(s);
  }
  async function video(id, it) {
    const s = VS.get(id), el = EL.get(id), v = s && s.v, live = !!(v && el && el.classList.contains("vshow") && v.readyState >= 2);
    const dur = (byPath.get(it.path) || {}).duration || 0, t = live ? v.currentTime : dur && dur <= 1 ? 0 : 1;   // the poster is 1 s in (server preview)
    try { return await fromUrl(`/api/copyimage?p=${enc(it.path)}&t=${t.toFixed(3)}`, it.crop); }
    catch (e) { if (live) return png(v, it.crop); return fromUrl(`/img?p=${enc(it.path)}${verOf(it.path)}`, it.crop); }
  }
  async function page(id, it) {
    const vw = it.vw || 1280, vh = Math.max(1, Math.round(vw * it.h / it.w));
    try { return await fromUrl(`/api/copyimage?p=${enc(it.src)}&w=${vw}&h=${vh}&s=2`); } catch (e) { console.warn("copy as image: the page", e); return still(id); }
  }
  function make(id) {
    const it = board.items[id], k = kindOf(it);
    if (k === "image") return fromUrl(`/img?p=${enc(it.path)}${verOf(it.path)}`, it.crop);
    if (k === "pdf") return fromUrl(thumbUrl(pgKey(it), PDF_PX), it.crop);
    if (k === "video") return video(id, it);
    if (k === "html") return page(id, it);
    return still(id);
  }
  // the picture of card id on the clipboard; of: how many were selected (the note says the first of them was copied)
  function copy(id, of = 1) {
    const no = why(id); if (no) { toast(no); return false; }
    const job = make(id);
    toast(T_("Copying the image…"));
    navigator.clipboard.write([new ClipboardItem({ "image/png": job.then(r => r.blob) })]).then(() => job)
      .then(r => { const size = `${r.w}×${r.h}`;
        toast(of > 1 ? T_("Copied the first of {n} as an image · {size}", { n: of, size }) : T_("Copied as image · {size}", { size }), "success"); })
      .catch(err => toast(T_("Couldn't copy the image: {why}", { why: (err && err.message) || err }), "error"));
    return true;
  }
  window.hyCopyImage = {
    kindOf, why, make, copy,
    // ⇧⌘C: the first selected card that has a picture
    key(ids) {
      const ok = ids.filter(i => board.items[i] && !why(i));
      if (ok.length) return copy(ok[0], ids.filter(i => kindOf(board.items[i])).length);
      toast(ids.length ? why(ids[0]) : T_("Select an image")); return false;
    },
    // the menu's «Copy as › Image» row for the card clicked
    row: id => hyMenuItem('data-act="image"', "image", T_("Image"), ["⇧", "⌘", "C"], why(id) ? hyMenuOff(why(id)) : ""),
  };
})();
