// What comes onto the board from outside: a file dropped from Finder or pasted (⌘C on it in Finder), a copied picture, a picture dragged
// off a web page (owner 2026-09-30: build moodboards from anything and comment on them). The server saves it into added/<day>/ with a json
// (review/added.py) and it lands on the board like a frame from the library. A video, a PDF or a design file goes as it is and lies as its
// own card (owner 2026-10-10: «я почему-то не могу перетащить видео на наш канвас. Или скопировать из буфера видео на канвас»); until then
// only pictures passed. Moved here from canvas.html with the videos (the page is at its size ceiling, AGENTS.md «Размер файлов»).
//   hyOuter.is(dt)         a drag from outside: files, or an address that is not a frame of the library
//   hyOuter.of(dt)         what of a drop or a paste goes to the server: the files it takes, else the picture's address from a web page
//   hyOuter.add(srcs, at)  saved and placed centred at the board point at, one step of ⌘Z; a mixed drop adds them all
//   hyOuter.fromClip()     a picture from the async clipboard, for Safari, which sends no paste event without a text field: [File] or []
(() => {
  if (window.hyOuter) return;
  // kept byte for byte, up to 4 GB (server.py VIDEO_EXT, PDF_EXT, DOC_EXT); any other picture goes as before, up to 80 MB
  const RAW = /\.(mp4|mov|m4v|webm|pdf|psd|psb|ai|tiff?|heic|heif|svg)$/i, PIC = /\.(jpe?g|png|webp|gif|avif|bmp)$/i;
  const raw = f => RAW.test(f.name || "");
  const is = dt => { const t = [...dt.types]; return t.includes("Files") || (t.includes("text/uri-list") && !t.includes("text/x-frame")); };
  function of(dt) {   // files first; else the picture's address from a web page (dragged image or link)
    const files = [...(dt.files || [])].filter(f => raw(f) || f.type.startsWith("image/") || PIC.test(f.name));
    if (files.length) return files;
    const html = dt.getData("text/html"), m = html && html.match(/<img[^>]+src=["']([^"']+)["']/i);
    const url = (m && m[1]) || (dt.getData("text/uri-list") || "").split("\n").find(l => l && !l.startsWith("#"));
    return url && /^https?:/.test(url.trim()) ? [{ url: url.trim() }] : [];
  }
  async function toPng(file) {   // jpeg, png and webp go as they are; any other picture the browser can open (heic in Safari, avif, gif) goes as png
    if (/^image\/(jpeg|png|webp)$/.test(file.type)) return file;
    try {
      const bm = await createImageBitmap(file), c = document.createElement("canvas"); c.width = bm.width; c.height = bm.height; c.getContext("2d").drawImage(bm, 0, 0);
      return await new Promise(r => c.toBlob(b => r(b || file), "image/png"));
    } catch { return file; }
  }
  async function send(src) {   // src: a File/Blob, or {url}; a video's File goes from the disk as it is, the server reads it in pieces
    const r = src instanceof Blob
      ? await fetch("/api/upload?name=" + enc(src.name || "clipboard"), { method: "POST", body: raw(src) ? src : await toPng(src) })
      : await fetch("/api/upload", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: src.url }) });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }
  async function place(srcs, at) {
    srcs = srcs.filter(Boolean); if (!srcs.length) return false;
    const one = srcs.length === 1, file = one && srcs[0] instanceof Blob && raw(srcs[0]);
    status(one ? (file ? T("adding the file…") : T("adding the image…")) : T("adding {frames}…", { frames: frames(srcs.length) }));
    busy("upload", one ? (file ? T("saving the file…") : T("saving the image…")) : T("saving {frames}…", { frames: frames(srcs.length) }));
    const got = [], bad = [];
    for (const s of srcs) { try { got.push(await send(s)); } catch (ex) { bad.push(String(ex.message || ex).replace(/^Error: /, "")); } }
    if (got.length) {   // the library's word for it at once (a video card plays), the list itself comes after
      got.forEach(g => byPath.has(g.path) || byPath.set(g.path, { path: g.path, name: g.path.split("/").pop().replace(/\.[^.]+$/, ""),
        folder: g.path.split("/").slice(0, -1).join("/"), feedback: {}, ...(g.kind ? { kind: g.kind } : {}) }));
      const folder = got[0].path.split("/").slice(0, -1).join("/");
      placePaths(got.map(g => g.path), at, got.map(g => g.ar), T("Added: {frames}, the files are in the folder {folder}", { frames: frames(got.length), folder }));
      if (EMBED) parent.postMessage({ type: "itemsChanged" }, location.origin); else loadLib();
    }
    busy("upload");
    if (bad.length) { status(T("not added"), true); toast(bad[0], "error", { sticky: true }); }
    else { status(T("saved")); toast(one ? (file ? T("File added") : T("Image added")) : T("Added: {frames}", { frames: frames(srcs.length) }), "success"); }
    return true;
  }
  async function add(srcs, at) {
    canvasOperations++;
    try { return await place(srcs, at); }
    finally { canvasOperations--; }
  }
  async function fromClip() {
    try {
      for (const it of await navigator.clipboard.read()) {
        const t = it.types.find(t => t.startsWith("image/"));
        if (t) return [new File([await it.getType(t)], "clipboard." + t.split("/")[1], { type: t })];
      }
    } catch {}
    return [];
  }
  window.hyOuter = { is, of, add, fromClip };
})();
