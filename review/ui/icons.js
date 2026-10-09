// One icon family for the app's two editors (owner 2026-10-06: the 3D studio's tools must be drawn like the frame editor's, and its
// select arrow «какой есть сейчас не в стиле остальных иконок наших»). The frame editor's set is the family: Lucide's geometry on a 24 grid,
// a 1.85 line, round ends and joins. What both editors show comes from here, so a tool looks the same in either: the select arrow (V), move,
// rotate, scale, the 3D pull (a point pulled along a curve), the hand, and the eye, lock, search, camera, folder and file of their layer lists.
//   window.HY_TOOL_IC.select            the paths of one icon (inside <svg viewBox="0 0 24 24">)
//   hyToolIcon("select", 18, "ic")      a whole <svg> in the family's line, at a size, with a class
// The frame editor's ICON takes these over its own (editor/index.html), the 3D editor's ico() uses them (hyimg-3d-studio engine.js).
(() => {
  if (window.HY_TOOL_IC) return;
  const IC = {
    // the select arrow: a pointer's head, no tail, the 3D editor's V and the frame editor's V
    select: '<path d="M4.04 4.69a.5.5 0 0 1 .65-.65l16 6.5a.5.5 0 0 1-.06.95l-6.13 1.58a2 2 0 0 0-1.44 1.44l-1.58 6.12a.5.5 0 0 1-.94.06z"/>',
    move: '<path d="m5 9-3 3 3 3"/><path d="m9 5 3-3 3 3"/><path d="m15 19-3 3-3-3"/><path d="m19 9 3 3-3 3"/><path d="M2 12h20"/><path d="M12 2v20"/>',   // the move tool (the 3D studio's Move)
    rotate: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',   // the rotate tool, rotate 90°
    // scale: a corner pulled out of its frame
    scale: '<path d="M5 7v11a1 1 0 0 0 1 1h11"/><path d="M5.3 18.7 11 13"/><circle cx="19" cy="19" r="2"/><circle cx="5" cy="5" r="2"/>',
    // the 3D pull: a point taken by the pointer and drawn along a curve, «as on a string in thick gel»
    pull: '<path d="M12.03 12.68a.5.5 0 0 1 .65-.65l9 3.5a.5.5 0 0 1-.03.94l-3.45 1.07a1 1 0 0 0-.66.66l-1.07 3.44a.5.5 0 0 1-.94.03z"/><path d="M5 17A12 12 0 0 1 17 5"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/>',
    hand: '<path d="M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2"/><path d="M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2"/><path d="M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/>',   // the hand: pan the view
    plus: '<path d="M5 12h14M12 5v14"/>',   // add, new
    eye: '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/>',   // shown (a layer, a section)
    eyeoff: '<path d="M10.73 5.08a10.74 10.74 0 0 1 11.2 6.57 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-1.44 2.49"/><path d="M14.08 14.16a3 3 0 0 1-4.24-4.24"/><path d="M17.48 17.5a10.75 10.75 0 0 1-15.42-5.15 1 1 0 0 1 0-.7 10.75 10.75 0 0 1 4.45-5.14"/><path d="m2 2 20 20"/>',   // hidden
    // the padlock (owner 2026-10-07: «можно эту иконку более явной сделать и в идеале анимированной, чтобы поворачивалась эта дуга, когда
    // открывается»): a tinted body with a keyhole, the shackle a full arch; open, the shackle is lifted 1.5 and swung 30° about its right
    // leg, as a real padlock opens. The same geometry as hyLockIcon below, still (menus, toasts)
    lock: '<path d="M8 11V7.5a4 4 0 0 1 8 0V11"/><rect x="4.5" y="11" width="15" height="10" rx="2.5" fill="currentColor" fill-opacity=".2"/><path d="M12 15v2.2"/>',
    lockOpen: '<path d="M8 11V7.5a4 4 0 0 1 8 0V11" transform="translate(0 -1.5) rotate(30 16 11)"/><rect x="4.5" y="11" width="15" height="10" rx="2.5" fill="currentColor" fill-opacity=".2"/><path d="M12 15v2.2"/>',   // unlocked (the padlock open; hyLockIcon swings between the two)
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',   // search, find
    // a camera of a 3D scene (the outliner's cameras, the camera panel); taking a picture is snapshot
    camera: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3z"/>',
    // take a picture: the 3D studio's Snapshot, the image studio's history snapshots
    snapshot: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z"/><circle cx="12" cy="13" r="3"/>',
    folder: '<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',   // a folder (a Finder folder; a group is group)
    doc: '<path d="M14 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-10z"/><path d="M14 3.5v5h5"/>',   // a file, a document (a PDF, an HTML page)
    // the link between two fields side by side, W and H (owner 2026-10-07: «вот это горизонтально должно быть, а не вертикально»): two
    // halves and the bar between them, Lucide's link-2. Drawn with the class hy-link, look.css closes the halves on the bar while its
    // button is .on and opens them apart, the bar gone, while it is off
    linkWH: '<path class="la" d="M9 17H7A5 5 0 0 1 7 7h2"/><path class="lb" d="M15 7h2a5 5 0 1 1 0 10h-2"/><path class="lm" d="M8 12h8"/>',
    // ⓘ beside a title whose explanation is its tooltip (look.css .hy-info draws the same geometry as a mask)
    info: '<circle cx="12" cy="12" r="9.5"/><path d="M12 16.5v-5M12 7.5h.01"/>',
    // a tip: the bulb in front of the line that teaches one thing you can do here (the Hints family, DESIGN.md «Семья подсказок», 2026-10-08)
    tip: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    // ---- the rest of the app's icons, one per meaning (owner 2026-10-07, the image studio's Adjustments tab wore the opacity's half
    // circle: «Нужно, чтобы это было систематизировано ... консистентные иконки, консистентные стили, консистентные цвета»). Every icon of
    // the board, the library, Home and the plugins is drawn from here by its name (hyIcon below); a page or a plugin writes no <path> of its
    // own (scripts/validate.py icon-inline), a name is one glyph and a glyph is one name (icon-registry). The comment after each one is its
    // meaning: an icon is never borrowed for another meaning because it looks close, a new meaning gets a new glyph here.
    // the chrome
    chevron: '<path d="m9 6 6 6-6 6"/>',   // a fold that opens, a step of the path, a submenu (HY_CHEV; turned down by .hy-chev.dn)
    back: '<path d="m15 6-6 6 6 6"/>',   // back to the list before
    prev: '<path d="M15 5l-7 7 7 7"/>',   // the previous page or picture
    next: '<path d="M9 5l7 7-7 7"/>',   // the next page or picture
    up: '<path d="m6 15 6-6 6 6"/>',   // one step up a vertical list (the previous collection)
    down: '<path d="m6 9 6 6 6-6"/>',   // one step down a vertical list (the next collection)
    popup: '<path d="m7 15 5 5 5-5M7 9l5-5 5 5"/>',   // opens a list to choose from (the pages button)
    close: '<path d="M6 6l12 12M18 6 6 18"/>',   // close, dismiss, clear
    minus: '<path d="M5 12h14"/>',   // less, remove one
    check: '<path d="M20 6 9 17l-5-5"/>',   // done, on, chosen
    more: '<circle cx="5.5" cy="12" r="1.6" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/><circle cx="18.5" cy="12" r="1.6" fill="currentColor" stroke="none"/>',   // more actions
    // Home: all boards; the ⌂ pentagon, H5 of Concepts/html/icons-redesign (owner 2026-10-08: «вот это больше всего нравится»)
    home: '<path d="M4.5 10.2 12 4l7.5 6.2v10.3h-15z"/>',
    // the app's settings: a knob, S4 of icons-redesign, picked on its round 2 (owner 2026-10-08: «вот этот берем»), the gear was «outdated»
    settings: '<circle cx="12" cy="12" r="8.5"/><path d="M17.3 6.7 14.6 9.4"/>',
    // what agents put on the boards: a square with its dot, B4 «Badge» of round 2 (owner 2026-10-08: «давай этот пока берем»); the dot
    // turns red while there is news (canvas.html #bntf.dot), so the button wears no second dot
    notifications: '<path d="M12.5 5.5H8a4 4 0 0 0-4 4V16a4 4 0 0 0 4 4h6.5a4 4 0 0 0 4-4v-4.5"/><circle cx="18" cy="6" r="2.5"/>',
    history: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/>',   // the history of versions and steps
    recent: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',   // the boards opened last
    sleep: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/>',   // a board asleep: its page gave its memory back, its server runs (⌃Tab, the crumb's list)
    reset: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',   // back to the start: filters, a section, the whole scene
    undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',   // undo one step
    redo: '<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',   // redo one step
    sync: '<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"/><path d="M20 20v-4h-4"/>',   // keep the library's folders like the board
    warn: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',   // something is missing or wrong
    fit: '<path d="M4 9V5.5A1.5 1.5 0 0 1 5.5 4H9M15 4h3.5A1.5 1.5 0 0 1 20 5.5V9M20 15v3.5a1.5 1.5 0 0 1-1.5 1.5H15M9 20H5.5A1.5 1.5 0 0 1 4 18.5V15"/>',   // zoom so that everything shows (Show all, Fit on screen)
    expand: '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',   // full screen, the library full width
    collapse: '<path d="M14 4v6h6M10 20v-6H4M14 10l6-6M10 14l-6 6"/>',   // back from full screen or full width
    library: '<rect x="3" y="4" width="18" height="16" rx="2"/><rect class="pane" x="5.5" y="6.5" width="6" height="11" rx="1" fill="currentColor" stroke="none"/>',   // show or hide the library beside the board
    sidebar: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/><path class="ar" d="M15.5 10 13 12l2.5 2"/>',   // show or hide the library's folder tree
    dockSide: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M14.5 4v16"/><path d="M17 8.5h1.5M17 11.5h1.5"/>',   // a panel docked at the window's side (Settings)
    asWindow: '<rect x="3" y="4" width="18" height="16" rx="3"/><rect x="7.5" y="8.5" width="9" height="7" rx="1.5"/>',   // a panel as a window in the middle (Settings)
    grid: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',   // all of them as cards in a grid (all boards, all folders, the grid view)
    rows: '<rect x="3.5" y="5" width="6" height="6" rx="1.5"/><rect x="11.5" y="5" width="9" height="6" rx="1.5"/><rect x="3.5" y="13" width="10" height="6" rx="1.5"/><rect x="15.5" y="13" width="5" height="6" rx="1.5"/>',   // the view of rows of one height
    list: '<path d="M8.5 6.5h12M8.5 12h12M8.5 17.5h12"/><circle cx="4.5" cy="6.5" r=".9" fill="currentColor"/><circle cx="4.5" cy="12" r=".9" fill="currentColor"/><circle cx="4.5" cy="17.5" r=".9" fill="currentColor"/>',   // the view of a list
    filter: '<path d="M3 5h18l-7 8.5V19l-4 2v-7.5z"/>',   // filters
    rejected: '<circle cx="12" cy="12" r="8.5"/><path d="m6 6 12 12"/>',   // the rejected pictures
    pin: '<path d="M9 4h6l-1 5.5 3 3V15H7v-2.5l3-3z"/><path d="M12 15v5"/>',   // pinned: stays first or on top
    onBoard: '<rect x="3" y="3" width="18" height="18" rx="3"/><rect x="7" y="7" width="4" height="4" fill="currentColor"/><rect x="13" y="12" width="4" height="5" fill="currentColor"/>',   // a picture that is on the board
    archived: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M4 20 20 4"/>',   // taken off the board, left out of the work
    noProject: '<rect x="4" y="4" width="16" height="16" rx="3.5" stroke-dasharray="3.2 2.6"/>',   // the boards in no project
    // Home's standard Archive (ui/homearchive.js, owner 2026-10-08): a box with its lid, Lucide's archive
    archive: '<rect x="3" y="4" width="18" height="4.5" rx="1"/><path d="M4.5 8.5V18a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V8.5"/><path d="M10 12.5h4"/>',
    // out of the Archive, back to its project («Restore»): the same box, an arrow up out of it
    unarchive: '<rect x="3" y="4" width="18" height="4.5" rx="1"/><path d="M4.5 8.5V18a2 2 0 0 0 2 2h1.5M19.5 8.5V18a2 2 0 0 1-2 2H16"/><path d="m9 14.5 3-3 3 3M12 11.5V21"/>',
    // things
    image: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m20.5 16-5-5-8 8.5"/>',   // a picture (a file kind, Image mode, a board without covers)
    board: '<rect x="3.5" y="3.5" width="17" height="17" rx="3"/><path d="M3.5 9h17M9 9v11.5"/>',   // a board (Board mode, a board in Home's list)
    scene3d: '<path d="M12 3 4 7.5v9L12 21l8-4.5v-9z"/><path d="M4 7.5 12 12l8-4.5M12 12v9"/>',   // a 3D scene (a 3D card, 3D mode, the board's own 3D engine)
    htmlFrame: '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M3 8.5h18"/><path d="m9.5 12.5-2 2 2 2M14.5 12.5l2 2-2 2"/>',   // an HTML frame: a live page on the board
    code: '<path d="m8.5 7-5 5 5 5"/><path d="m15.5 7 5 5-5 5"/><path d="m13.5 4.5-3 15"/>',   // a page's code (Dev mode)
    tag: '<path d="M8 6 3 12l5 6"/><path d="m16 6 5 6-5 6"/>',   // an element of a page
    plugin: '<path d="M9 3v4.5M15 3v4.5"/><path d="M6.5 7.5h11V11a5.5 5.5 0 0 1-11 0z"/><path d="M12 16.5V21"/>',   // a plugin (a plug): Settings › Plugins, a card whose plugin is off
    heart: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',   // like (♥)
    play: '<path d="M8 5.6v12.8a.8.8 0 0 0 1.2.7l10.2-6.4a.8.8 0 0 0 0-1.4L9.2 4.9A.8.8 0 0 0 8 5.6z"/>',   // play (drawn filled on a video)
    pause: '<rect x="6" y="5" width="4.2" height="14" rx="1.2"/><rect x="13.8" y="5" width="4.2" height="14" rx="1.2"/>',   // pause
    stop: '<rect x="6.5" y="6.5" width="11" height="11" rx="2"/>',   // stop
    note: '<path d="M5 4h14a1 1 0 0 1 1 1v9l-6 6H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/><path d="M14 20v-5a1 1 0 0 1 1-1h5"/>',   // a sticky note
    timeline: '<path d="M3 14h18"/><circle cx="5" cy="14" r="2" fill="currentColor"/><circle cx="12" cy="14" r="2"/><circle cx="19" cy="14" r="2"/><path d="M9.5 9h5"/>',   // a timeline
    heading: '<path d="M6 4.5v15M18 4.5v15M6 12h12"/>',   // a heading: big text over a column of groups (docs/glossary.md)
    // a component (docs/glossary.md): made once, used many times; one solid diamond, K1 of icons-redesign round 2 (owner 2026-10-08: «да вот
    // так отлично»), it replaced Figma's four diamonds
    component: '<path d="M12 4.3 19.7 12 12 19.7 4.3 12z" fill="currentColor"/>',
    instance: '<path d="M12 4.3 19.7 12 12 19.7 4.3 12z"/>',   // an instance: one placement of a component, the same diamond hollow (K2)
    // the agents that act for a person (ui/avatar.js, the badge on his avatar; owner 2026-10-07): neutral glyphs; since 2026-10-08 the companies'
    // marks (ui/agents) cover claude, codex and gemini in the owner's app, these stay for the others and for the public repositories
    agentClaude: '<path d="M5 19 14.5 9.5"/><path d="M19.5 4.5c-6 0-10.5 4-12 11l1.5 1.5c7-1.5 10.5-6 10.5-12.5z"/>',   // Claude: a quill
    // Codex: braces
    agentCodex: '<path d="M9 4.5c-2 0-3 1-3 3v2c0 1.3-.8 2.5-2 2.5 1.2 0 2 1.2 2 2.5v2c0 2 1 3 3 3"/>'
      + '<path d="M15 4.5c2 0 3 1 3 3v2c0 1.3.8 2.5 2 2.5-1.2 0-2 1.2-2 2.5v2c0 2-1 3-3 3"/>',
    agentGemini: '<circle cx="9" cy="12" r="5"/><circle cx="15" cy="12" r="5"/>',   // Gemini: two rings, the twins
    agentKimi: '<path d="M19.5 14.5A8 8 0 1 1 9.5 4.5a6.5 6.5 0 0 0 10 10z"/>',   // Kimi: a crescent
    agentOpencode: '<path d="m5 7 5 5-5 5"/><path d="M12.5 17.5h6.5"/>',   // OpenCode: a prompt
    agent: '<rect x="5" y="8.5" width="14" height="11" rx="3"/><path d="M12 4.5v4"/><path d="M9.5 14h.01M14.5 14h.01"/>',   // an agent (docs/glossary.md), the badge of one the catalog does not know
    // a person who works on the board (docs/glossary.md, owner 2026-10-08): head and shoulders; a face with no name and no picture
    person: '<circle cx="12" cy="7.5" r="4"/><path d="M4.5 20.5a7.5 6.5 0 0 1 15 0"/>',
    // the sections of Settings (ui/settings-win.js, owner 2026-10-08: E1 «Rail popover» of Concepts/html/settings-concepts), each its own
    team: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 5.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M21.5 20a6.5 5.5 0 0 0-4-5.1"/>',   // Team & agents
    // Appearance: a painter's palette (theme, corners, shadows, notes)
    palette: '<circle cx="13.5" cy="6.5" r="1"/><circle cx="17.5" cy="10.5" r="1"/><circle cx="8.5" cy="7.5" r="1"/><circle cx="6.5" cy="12.5" r="1"/>'
      + '<path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.65-.75 1.65-1.69 0-.44-.18-.84-.44-1.13-.29-.29-.44-.65-.44-1.13a1.64 1.64 0 0 1 1.67-1.67h2'
      + 'c3.05 0 5.56-2.5 5.56-5.55C21.97 6.01 17.46 2 12 2z"/>',
    // Storage: a disk (the boards' folders, the cache, the memory)
    drive: '<path d="M22 12H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>'
      + '<path d="M6 16h.01M10 16h.01"/>',
    keyboard: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M7 15h10"/>',   // Interface: keys, hiding it
    gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',   // Performance: the engine, the drawing, the log of frame drops
    // annotations and comments on the board (ui/annotate.js, ui/comments.js; owner 2026-10-07: «как в Figma»)
    annotate: '<path d="M4 20c3-1 4-4 7-4s3 2 5 2"/><path d="m13.5 11.5 6-6a1.8 1.8 0 0 0-2.5-2.5l-6 6-1 3.5z"/>',   // the Annotate tool: draw and comment
    comment: '<path d="M4.5 12a7.5 7.5 0 1 1 3.4 6.3L4 19.5l1.3-3.6A7.4 7.4 0 0 1 4.5 12z"/>',   // a comment, a pin with a thread
    marker: '<path d="m15 5 4 4"/><path d="M5.5 18.5 4 20l1.5-.3 3-.7L18 9.5 14.5 6 5 15.5z"/>',   // freehand drawing on the board
    drawArrow: '<path d="M5 19 19 5"/><path d="M10 5h9v9"/>',   // an arrow drawn on the board
    drawRect: '<rect x="4" y="5.5" width="16" height="13" rx="1.5"/>',   // a rectangle drawn on the board
    drawEllipse: '<ellipse cx="12" cy="12" rx="8.5" ry="6.5"/>',   // an ellipse drawn on the board
    drawText: '<path d="M5.5 6.5V5h13v1.5"/><path d="M12 5v14"/><path d="M9.5 19h5"/>',   // a short text label on the board
    eraser: '<path d="m7 20-3.3-3.3a1.5 1.5 0 0 1 0-2.1L13.6 4.7a1.5 1.5 0 0 1 2.1 0l4.6 4.6a1.5 1.5 0 0 1 0 2.1L11.5 20z"/><path d="M8.5 9.5 15 16M7 20h13"/>',   // erase
    resolve: '<circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.2 2.4 2.4 4.6-4.8"/>',   // resolve a comment thread
    reply: '<path d="M10 8 5 12.5l5 4.5"/><path d="M5 12.5h9a5 5 0 0 1 5 5V19"/>',   // reply in a thread
    mention: '<circle cx="12" cy="12" r="3.5"/><path d="M15.5 9v4.3a2.2 2.2 0 0 0 4.4 0V12a8 8 0 1 0-3.2 6.4"/>',   // @ someone
    editText: '<path d="M4.5 19.5h4l10-10-4-4-10 10z"/><path d="m13 7 4 4"/>',   // change what one wrote (a comment)
    send: '<path d="M12 19V5"/><path d="m6 11 6-6 6 6"/>',   // send a comment or a reply
    // the board's and the library's actions (the menus: ui/menu.js hyMenuItem)
    // a group, on the Board and in 3D Studio alike (owner 2026-10-09 on Figma's, his screenshot on r12/3d-group.html: «let's make same as in
    // figma and apply it»): Figma's dashed square, four round corners and a dash in each side's middle, in our line
    group: '<path d="M3.5 6.2V5A1.5 1.5 0 0 1 5 3.5h1.2M17.8 3.5H19a1.5 1.5 0 0 1 1.5 1.5v1.2M20.5 17.8V19a1.5 1.5 0 0 1-1.5 1.5h-1.2M6.2 20.5H5A1.5 1.5 0 0 1 3.5 19v-1.2"/><path d="M10.5 3.5h3M10.5 20.5h3M3.5 10.5v3M20.5 10.5v3"/>',
    ungroup: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/><path d="M14 6.5h3.5V10M10 17.5H6.5V14"/>',   // ungroup, take the pictures out of a frame
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',   // link things together (layers)
    view: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',   // look at it big (the viewer)
    show: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3"/><path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3"/>',   // show where it is
    open: '<path d="M14 4.5h5.5V10"/><path d="m19.5 4.5-8 8"/><path d="M18 14v4.5a1 1 0 0 1-1 1H5.5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1H10"/>',   // open in its own app
    rename: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',   // rename
    trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',   // delete
    unfile: '<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M9.5 13.5h5"/>',   // take out of a project
    relink: '<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M12 10.5v5M9.5 13H14.5"/>',   // choose the board's folder again
    toFolders: '<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M8 13h8M13 10l3 3-3 3"/>',   // lay the library's folders out as on the board
    split: '<rect x="3.5" y="4.5" width="7" height="15" rx="1.6"/><rect x="13.5" y="4.5" width="7" height="15" rx="1.6"/>',   // split into pages
    cut: '<circle cx="6.5" cy="17.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/><path d="M8.3 15.7 18 4M15.7 15.7 6 4"/>',   // cut
    copy: '<rect x="8.5" y="8.5" width="12" height="12" rx="2"/><path d="M15.5 8.5V5.5a2 2 0 0 0-2-2h-8a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h3"/>',   // copy; a card that is a copy
    paste: '<rect x="4.5" y="4.5" width="15" height="16" rx="2"/><path d="M9 3.5h6v2.5H9z"/>',   // paste
    duplicate: '<rect x="3.5" y="3.5" width="12" height="12" rx="2"/><path d="M8.5 20.5h10a2 2 0 0 0 2-2v-10M9.5 9.5h0"/><path d="M9.5 7v5M7 9.5h5"/>',   // duplicate
    order: '<rect x="3.5" y="3.5" width="11" height="11" rx="2"/><path d="M9.5 18.5v.5a1.5 1.5 0 0 0 1.5 1.5h7.5a1.5 1.5 0 0 0 1.5-1.5V11a1.5 1.5 0 0 0-1.5-1.5H18"/>',   // the order of cards ›
    orderFront: '<path d="M5 4.5h14"/><path d="M12 20V9M7.5 13.5 12 9l4.5 4.5"/>',   // bring to front
    orderForward: '<path d="M12 19V6M7.5 10.5 12 6l4.5 4.5"/>',   // bring forward
    orderBackward: '<path d="M12 5v13M7.5 13.5 12 18l4.5-4.5"/>',   // send backward
    orderBack: '<path d="M5 19.5h14"/><path d="M12 4v11M7.5 10.5 12 15l4.5-4.5"/>',   // send to back
    copyProps: '<path d="M4 7h8M16 7h4M4 17h4M12 17h8"/><circle cx="14" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',   // copy the properties
    clearProps: '<path d="M4 7h8M16 7h4M4 17h6"/><circle cx="14" cy="7" r="2"/><path d="m14 14 6 6M20 14l-6 6"/>',   // clear the properties: the sliders, a cross
    pasteProps: '<rect x="4.5" y="4.5" width="15" height="16" rx="2"/><path d="M9 3.5h6v2.5H9z"/><path d="M8 11h3.5M14.5 11H16M8 15.5h1.5M12.5 15.5H16"/><circle cx="13" cy="11" r="1.5"/><circle cx="11" cy="15.5" r="1.5"/>',   // paste the properties
    toPage: '<rect x="3.5" y="4.5" width="10" height="15" rx="2"/><path d="M10 12h10.5M17 8.5l3.5 3.5-3.5 3.5"/>',   // move to another page
    goTo: '<path d="M5 12h14M13 6l6 6-6 6"/>',   // go to the original of a copy
    goBack: '<path d="M19 12H5M11 6l-6 6 6 6"/>',   // back to the copy it came from
    tidyBlock: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.2"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.2"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.2"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.2"/>',   // arrange as a square block
    tidyRow: '<path d="M3 4h18"/><rect x="4" y="7" width="4.5" height="10" rx="1"/><rect x="10" y="7" width="4.5" height="7" rx="1"/><rect x="16" y="7" width="4" height="12" rx="1"/>',   // arrange in one row, aligned at the top
    gridMake: '<rect x="3.5" y="3.5" width="17" height="17" rx="2"/><path d="M3.5 9.5h17M3.5 14.5h17M9.5 3.5v17M14.5 3.5v17"/>',   // make a grid (Arrange ›)
    gridRemove: '<path d="M9.5 3.5v3M3.5 9.5h3M20.5 14.5h-3M14.5 20.5v-3M4 4l16 16"/><path d="M8 3.5h10.5a2 2 0 0 1 2 2V16M16 20.5H5.5a2 2 0 0 1-2-2V8"/>',   // remove a grid
    // Arrange › Make table, Layout patterns › (owner 2026-10-09: «Почему у меня нет кнопок для Arrange новых?»): a picture of each layout
    table: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 6.5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2v3h-17z" fill="currentColor"/><path d="M9 9.5v10M3.5 14.5h17"/>',   // a table
    layouts: '<path d="M3.5 3.5h8v17h-8zM14.5 3.5h6v7h-6zM14.5 13.5h6v7h-6z"/>',   // the layout patterns › (Arrange)
    layoutVariants: '<path d="M3 5h5v5H3zM9.5 5h5v5h-5zM16 5h5v5h-5zM3 14h5v5H3zM9.5 14h5v5h-5zM16 14h5v5h-5z"/>',   // variants grid: one idea, many tries, numbered
    layoutAB: '<path d="M5 4.5h3M16 4.5h3M3.5 8h7v5h-7zM13.5 8h7v5h-7zM3.5 15h7v5h-7zM13.5 15h7v5h-7z"/>',   // A / B: two columns under their letters
    layoutTimeline: '<path d="M3 5.5h18M11 10.5h9v4h-9zM11 16.5h9v4h-9z"/><circle cx="6" cy="5.5" r="1.5"/><circle cx="15.5" cy="5.5" r="1.5"/>',   // a batch under its phase
    layoutDirections: '<path d="M3 6.5h2M3 12h2M3 17.5h2M8 5h5v3H8zM15 5h5v3h-5zM8 10.5h5v3H8zM15 10.5h5v3h-5zM8 16h5v3H8zM15 16h5v3h-5z"/>',   // direction rows, a label each
    layoutDocs: '<path d="M3.5 4.5h11M3.5 9.5h5v10h-5zM10.5 9.5h5v10h-5zM17.5 9.5h3v10h-3z"/>',   // documentation: a heading over big cards
    layoutBeforeAfter: '<path d="M3.5 6.5h6v11h-6zM14.5 6.5h6v11h-6zM10.8 12h2.4M12 10.6l1.4 1.4-1.4 1.4"/>',   // before / after: a pair, a row each
    layoutMoodboard: '<path d="M3.5 3.5h7v9h-7zM13.5 3.5h7v5h-7zM13.5 11.5h7v9h-7zM3.5 15.5h7v5h-7z"/>',   // moodboard cluster: references, no numbers
    layoutReview: '<path d="M3.5 4.5h4M10 4.5h4M16.5 4.5h4M3.5 8h4v5h-4zM10 8h4v5h-4zM10 15h4v5h-4zM16.5 8h4v5h-4z"/>',   // review board: picked, to decide, rejected
    layoutFlow: '<path d="M2.5 9.5h5v5h-5zM16.5 9.5h5v5h-5zM7.5 12h8.5M13.8 9.8 16 12l-2.2 2.2"/>',   // process / flow: steps joined by arrows
    layoutGlossary: '<path d="M3.5 4.5h7v6h-7zM13.5 4.5h7v6h-7zM3.5 13.5h7v6h-7zM13.5 13.5h7v6h-7zM5.5 8h3M15.5 8h3M5.5 17h3M15.5 17h3"/>',   // glossary cards: a term each
    tidy: '<rect x="3" y="4" width="4" height="5" rx="1"/><rect x="9" y="4" width="4" height="5" rx="1"/><rect x="15" y="4" width="4" height="5" rx="1"/><rect x="3" y="15" width="4" height="5" rx="1"/><rect x="9" y="15" width="4" height="5" rx="1"/><path d="M21 9.5v5M19.5 11l1.5-1.5 1.5 1.5M19.5 13l1.5 1.5 1.5-1.5"/>',   // tidy: rows and blocks stay, the gaps become even
    opacity: '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/>',   // opacity (only that: never an adjustment)
    orientation: '<rect x="7" y="3.5" width="10" height="17" rx="2.6"/>',   // turn a frame or a ratio between portrait and landscape
    actions: '<path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z"/>',   // Actions, ⌘K
    // the image studio (hyimg-image-studio): tools, layers, panels
    brush: '<path d="m9.06 11.9 8.07-8.06a2.85 2.85 0 1 1 4.03 4.03l-8.06 8.08"/><path d="M7.07 14.94c-1.66 0-3 1.35-3 3.02 0 1.33-2.5 1.52-2 2.02 1.08 1.1 2.49 2.02 4 2.02 2.2 0 4-1.8 4-4.04a3.01 3.01 0 0 0-3-3.02z"/>',   // the brush
    eyedropper: '<path d="m2 22 1-1h3l9-9"/><path d="M3 21v-3l9-9"/><path d="m15 6 3.4-3.4a2.1 2.1 0 1 1 3 3L18 9l.4.4a2.1 2.1 0 1 1-3 3l-3.8-3.8a2.1 2.1 0 1 1 3-3l.4.4Z"/>',   // pick a colour
    eyedropperAdd: '<path d="m2 22 1-1h3l9-9"/><path d="M3 21v-3l9-9"/><path d="m15 6 3.4-3.4a2.1 2.1 0 1 1 3 3L18 9l.4.4a2.1 2.1 0 1 1-3 3l-3.8-3.8a2.1 2.1 0 1 1 3-3l.4.4Z"/><path d="M18.5 15v6M15.5 18h6"/>',   // add to a colour range
    eyedropperSub: '<path d="m2 22 1-1h3l9-9"/><path d="M3 21v-3l9-9"/><path d="m15 6 3.4-3.4a2.1 2.1 0 1 1 3 3L18 9l.4.4a2.1 2.1 0 1 1-3 3l-3.8-3.8a2.1 2.1 0 1 1 3-3l.4.4Z"/><path d="M15.5 18h6"/>',   // subtract from a colour range
    marquee: '<path d="M5 3a2 2 0 0 0-2 2"/><path d="M19 3a2 2 0 0 1 2 2"/><path d="M21 19a2 2 0 0 1-2 2"/><path d="M5 21a2 2 0 0 1-2-2"/><path d="M9 3h1"/><path d="M9 21h1"/><path d="M14 3h1"/><path d="M14 21h1"/><path d="M3 9v1"/><path d="M21 9v1"/><path d="M3 14v1"/><path d="M21 14v1"/>',   // the rectangle selection
    ellipse: '<ellipse cx="12" cy="12" rx="9" ry="7" stroke-dasharray="3 2.4"/>',   // the ellipse selection
    lasso: '<path d="M7 22a5 5 0 0 1-2-4"/><path d="M3.3 14A6.8 6.8 0 0 1 2 10c0-4.4 4.5-8 10-8s10 3.6 10 8-4.5 8-10 8a12 12 0 0 1-5-1"/><path d="M5 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/>',   // the lasso
    wand: '<path d="m15 4-1 2-2 1 2 1 1 2 1-2 2-1-2-1z"/><path d="M14 10 4 20"/>',   // the magic wand
    subject: '<rect x="3" y="3" width="18" height="18" rx="3" stroke-dasharray="3 2.4"/><circle cx="12" cy="10" r="3"/><path d="M7 19c.8-3 2.7-4.5 5-4.5s4.2 1.5 5 4.5"/>',   // select the subject
    removeBg: '<path d="M4 4h4M4 4v4M20 4h-4M20 4v4M4 20h4M4 20v-4M20 20h-4M20 20v-4"/><circle cx="12" cy="10" r="3"/><path d="M7 18c.8-2.6 2.7-4 5-4s4.2 1.4 5 4"/>',   // remove the background
    pen: '<path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.6 7.6"/><circle cx="11" cy="11" r="2"/>',   // the vector pen; a vector file (AI, SVG)
    patch: '<path d="M10 10.01h.01M10 14.01h.01M14 10.01h.01M14 14.01h.01"/><path d="M18 6v12M6 6v12"/><rect x="2" y="6" width="20" height="12" rx="2"/>',   // the healing patch
    contentFill: '<path d="m19 11-8-8-8.6 8.6a2 2 0 0 0 0 2.8l5.2 5.2c.8.8 2 .8 2.8 0L19 11Z"/><path d="m5 2 5 5"/><path d="M2 13h15"/><path d="M22 20a2 2 0 1 1-4 0c0-1.6 1.7-2.4 2-4 .3 1.6 2 2.4 2 4Z"/>',   // content-aware fill
    transform: '<rect x="5" y="5" width="14" height="14"/><rect x="3" y="3" width="4" height="4" fill="currentColor"/><rect x="17" y="3" width="4" height="4" fill="currentColor"/><rect x="3" y="17" width="4" height="4" fill="currentColor"/><rect x="17" y="17" width="4" height="4" fill="currentColor"/>',   // free transform
    crop: '<path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/>',   // crop; a cropped card
    frame: '<path d="M7 3v18M17 3v18M3 7h18M3 17h18"/>',   // a frame
    frameEach: '<path d="M6 3v18M12 3v18M18 3v18M3 6h18M3 12h18M3 18h18"/>',   // a frame for each picture
    canvasSize: '<rect x="5" y="5" width="14" height="14" rx="1.5"/><path d="M2 9V3h6M22 15v6h-6"/>',   // the canvas size
    resize: '<rect x="3.5" y="9.5" width="11" height="11" rx="2"/><path d="M13.5 3.5h7v7M20.5 3.5l-7 7"/>',   // the image size
    layers: '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"/><path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"/><path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"/>',   // layers (the panel, a PSD)
    newLayer: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M12 8v8M8 12h8"/>',   // a new layer
    properties: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',   // properties (the panel, the library's card view)
    channels: '<circle cx="9" cy="9" r="5.5"/><circle cx="15" cy="9" r="5.5"/><circle cx="12" cy="14.5" r="5.5"/>',   // the red, green and blue channels
    generate: '<path d="M9.94 15.5A2 2 0 0 0 8.5 14.06l-6.14-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.14a.5.5 0 0 1 .96 0l1.58 6.14a2 2 0 0 0 1.44 1.44l6.14 1.58a.5.5 0 0 1 0 .96l-6.14 1.58a2 2 0 0 0-1.44 1.44l-1.58 6.14a.5.5 0 0 1-.96 0z"/>',   // generative (AI)
    layerStyle: '<path d="M10 4.5C8.5 4.5 7.5 5.5 7.5 7v13"/><path d="M5 10h5.5"/><path d="m13.5 10 6 9"/><path d="m19.5 10-6 9"/>',   // a layer style (fx)
    mask: '<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="12" cy="12" r="4.6"/>',   // a mask
    maskOverlay: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M3 14c4-4 8 3 18-4v6a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4z" fill="currentColor" stroke="none" opacity=".5"/>',   // show the mask as a coloured film
    clip: '<path d="M5 4v7a4 4 0 0 0 4 4h10"/><path d="m15 11 4 4-4 4"/>',   // a clipping mask
    // a clipped layer's mark in a layer list, Photoshop's: the arrow comes in from the right and points down to the base under it
    clipped: '<path d="M20 4h-7a4 4 0 0 0-4 4v12"/><path d="m14 15-5 5-5-5"/>',
    // a master layer (the image studio's Raw Editor and Mask pinned on top, owner 2026-10-07): it acts on the whole frame on the board
    master: '<path d="M11.56 3.27a.5.5 0 0 1 .88 0l2.95 5.6a1 1 0 0 0 1.52.3l4.27-3.67a.5.5 0 0 1 .8.52l-2.84 10.25a1 1 0 0 1-.95.73H5.81'
      + 'a1 1 0 0 1-.96-.73L2.02 6.02a.5.5 0 0 1 .8-.52l4.27 3.67a1 1 0 0 0 1.52-.3z"/><path d="M5 21h14"/>',
    merge: '<path d="M12 3v7"/><path d="m8 6 4 4 4-4"/><rect x="4" y="13" width="16" height="8" rx="2"/>',   // merge down
    flatten: '<rect x="4" y="3" width="16" height="5" rx="1.5"/><rect x="4" y="10" width="16" height="5" rx="1.5"/><path d="M4 19h16"/>',   // merge all, flatten
    mergeNew: '<rect x="4" y="3" width="16" height="5" rx="1.5"/><rect x="4" y="10" width="16" height="5" rx="1.5"/><path d="M12 17.5v4M10 19.5h4"/>',   // merge the visible ones into a new layer
    flipH: '<path d="M12 3v18" stroke-dasharray="2 2.5"/><path d="M9 7 4 17h5z"/><path d="m15 7 5 10h-5z"/>',   // flip horizontally
    flipV: '<path d="M3 12h18" stroke-dasharray="2 2.5"/><path d="M7 9 17 4v5z"/><path d="m7 15 10 5v-5z"/>',   // flip vertically
    swapColors: '<path d="M7 4h7a4 4 0 0 1 4 4v7"/><path d="m15 12 3 3 3-3"/><path d="m10 1-3 3 3 3"/>',   // swap the two colours
    selectAll: '<rect x="4" y="4" width="16" height="16" rx="2" stroke-dasharray="3 2.6"/><path d="m8 12 3 3 5-6"/>',   // select all
    deselect: '<rect x="4" y="4" width="16" height="16" rx="2" stroke-dasharray="3 2.6"/><path d="m9 9 6 6M15 9l-6 6"/>',   // deselect
    invertSelection: '<rect x="4" y="4" width="16" height="16" rx="2" stroke-dasharray="3 2.6"/><path d="M12 4v16"/><path d="M12 4h8v16h-8z" fill="currentColor" stroke="none" opacity=".4"/>',   // invert the selection or a mask
    selNew: '<rect x="5" y="5" width="14" height="14" rx="1.5"/>',   // a new selection
    selAdd: '<path d="M3 3h12v6h6v12H9v-6H3z" fill="currentColor" fill-opacity=".3"/>',   // add to the selection
    selSub: '<path d="M3 3h12v6H9v6H3z" fill="currentColor" fill-opacity=".3"/><path d="M9 9h12v12H9z" stroke-dasharray="2 2"/>',   // subtract from the selection
    selIntersect: '<path d="M3 3h12v12H3z" stroke-dasharray="2 2"/><path d="M9 9h12v12H9z" stroke-dasharray="2 2"/><path d="M9 9h6v6H9z" fill="currentColor" fill-opacity=".5"/>',   // intersect with the selection
    colorToAlpha: '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',   // Color to Alpha: a colour becomes see-through
    feather: '<path d="M12.67 19a2 2 0 0 0 1.41-.59l6.33-6.34a6 6 0 0 0-8.49-8.49L5.59 9.91A2 2 0 0 0 5 11.33V19z"/><path d="M16 8 2 22"/><path d="M17.5 15H9"/>',   // feather the edge
    grow: '<rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M3 3l3 3M21 3l-3 3M3 21l3-3M21 21l-3-3"/>',   // grow the selection
    blur: '<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="7" stroke-dasharray="2 3"/><circle cx="12" cy="12" r="10.5" stroke-dasharray="1 4" opacity=".6"/>',   // blur
    sharpen: '<path d="M12 3 21 20H3z"/><path d="M12 10v5"/>',   // sharpen
    zoomIn: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4M11 8v6M8 11h6"/>',   // zoom in
    zoomOut: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4M8 11h6"/>',   // zoom out
    zoom100: '<rect x="3.5" y="3.5" width="17" height="17" rx="3"/><path d="M11 9l2-1.5V16"/>',   // 100 %
    guide: '<path d="M3 12h18" stroke-dasharray="3 2.5"/><path d="M12 3v18"/>',   // a guide
    alignLeft: '<path d="M4 3v18"/><rect x="7" y="6" width="12" height="4" rx="1"/><rect x="7" y="14" width="7" height="4" rx="1"/>',   // align the left edges
    alignCenter: '<path d="M12 3v18"/><rect x="5" y="6" width="14" height="4" rx="1"/><rect x="8" y="14" width="8" height="4" rx="1"/>',   // align the centres across
    alignRight: '<path d="M20 3v18"/><rect x="5" y="6" width="12" height="4" rx="1"/><rect x="10" y="14" width="7" height="4" rx="1"/>',   // align the right edges
    alignTop: '<path d="M3 4h18"/><rect x="6" y="7" width="4" height="12" rx="1"/><rect x="14" y="7" width="4" height="7" rx="1"/>',   // align the tops
    alignMiddle: '<path d="M3 12h18"/><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="8" width="4" height="8" rx="1"/>',   // align the middles
    alignBottom: '<path d="M3 20h18"/><rect x="6" y="5" width="4" height="12" rx="1"/><rect x="14" y="10" width="4" height="7" rx="1"/>',   // align the bottoms
    // Raw Editor's sections (hyimg-image-studio editor/colorgrade.js); Raw Editor itself is rawEditor below
    rawLight: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',   // Light: exposure, contrast, tones
    rawCurve: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M6 18C10 18 9 6 18 6"/>',   // Curves
    rawDetail: '<path d="M12 3 3 19h18z"/><path d="M8.5 13h7"/>',   // Detail: sharpening, noise
    rawMixer: '<path d="M6 4v16M12 4v16M18 4v16"/><circle cx="6" cy="14" r="2" fill="currentColor"/><circle cx="12" cy="8" r="2" fill="currentColor"/><circle cx="18" cy="16" r="2" fill="currentColor"/>',   // Color Mixer: hue, saturation, luminance per colour
    rawHueSat: '<path d="M4 7h16M4 12h16M4 17h16"/><circle cx="9" cy="7" r="1.9" fill="currentColor"/><circle cx="15.5" cy="12" r="1.9" fill="currentColor"/><circle cx="7" cy="17" r="1.9" fill="currentColor"/>',   // Hue/Saturation
    // Selective Color (Photoshop's, hyimg-image-studio editor/selcolor.js): one colour range of the nine picked, the swatch ringed as in its row
    rawSelColor: '<circle cx="4" cy="12" r="2"/><circle cx="20" cy="12" r="2"/><circle cx="12" cy="12" r="2.6" fill="currentColor"/><circle cx="12" cy="12" r="5.2"/>',
    rawGrading: '<circle cx="12" cy="7.5" r="4"/><circle cx="6.5" cy="16" r="4"/><circle cx="17.5" cy="16" r="4"/>',   // Color Grading: the shadows', midtones' and highlights' wheels
    rawEffects: '<rect x="3" y="4" width="18" height="16" rx="3"/><ellipse cx="12" cy="12" rx="5" ry="4"/>',   // Effects: vignette, grain
    compare: '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M12 4v16"/><path d="M12 4h6.5A2.5 2.5 0 0 1 21 6.5v11a2.5 2.5 0 0 1-2.5 2.5H12z" fill="currentColor" stroke="none" opacity=".35"/>',   // before and after
    // the 3D studio (hyimg-3d-studio)
    model: '<path d="M8 3h8a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>',   // a model from the board's folder
    mesh: '<path d="M12 3.5 3.5 19h17z"/><path d="m7.75 11.25 4.25 7.75 4.25-7.75z"/>',   // a mesh: a part of an object
    light: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2"/>',   // a light of the scene
    primBox: '<path d="M4 8.5h11.5V20H4z"/><path d="M4 8.5 8.5 4H20v11.5L15.5 20M15.5 8.5 20 4"/>',   // a box
    sphere: '<circle cx="12" cy="12" r="8"/><path d="M4 12c3 3 13 3 16 0"/>',   // a sphere
    cylinder: '<ellipse cx="12" cy="6" rx="7" ry="2.5"/><path d="M5 6v12c0 1.4 3 2.5 7 2.5s7-1.1 7-2.5V6"/>',   // a cylinder
    plane: '<path d="M3 15l6-6h12l-6 6z"/>',   // a plane, the floor
    eevee: '<path d="M13 3 5 13.5h6L10 21l8-10.5h-6z"/>',   // Blender's EEVEE: fast
    cycles: '<path d="M3.5 19.5 10 5l4.5 10.5L20.5 7"/><circle cx="20.5" cy="7" r="1.6" fill="currentColor"/>',   // Blender's Cycles: traced rays
  };
  window.HY_TOOL_IC = IC;
  // Every lock toggle of the app draws this one padlock (the image studio's layers, the 3D studio's outliner and its cameras): locked, the
  // shackle closed in the body at full contrast; open, the shackle lifted and swung about its right leg, dimmer. look.css .hy-lock moves the
  // shackle between the two along the app's curve in 260 ms when the class «locked» changes on a drawn icon; go: a freshly drawn icon plays
  // its last move once (a list that redraws its rows). Reduced motion: no move.
  //   hyLockIcon(locked, size, { go, cls })   a whole <svg>
  window.hyLockIcon = (locked, size = 14, o = {}) => `<svg class="hy-lock${locked ? " locked" : ""}${o.go ? " go" : ""}${o.cls ? " " + o.cls : ""}" viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">`
    + IC.lock.replace("<path ", '<path class="sh" ') + "</svg>";   // the registry's padlock, its shackle (the first path) the part that swings
  window.HY_IC_LINE = 1.85;   // the family's line on the 24 grid
  window.hyToolIcon = (name, size = 18, cls = "") => hyIcon(name, size, 1.85, cls);
  // Any icon of the app by its meaning, the one way to draw one (a page or a plugin writes no glyph of its own):
  //   hyIcon(name, size, line, cls, { fill, attrs })   a whole <svg>: size in px (0 or null: none, the CSS sizes it), line: the stroke on
  //                                                    the 24 grid (the family 1.85, menus 1.9, chevrons 2.4, small marks 2 to 2.2), fill:
  //                                                    drawn filled in currentColor (a liked ♥, ▶ on a video), attrs: more attributes
  //   <svg data-ic="note" width="18" height="18" stroke-width="1.8"></svg>   in static markup: filled in as the page is parsed
  //   hyIconPath(name)     the icon as one path's d, for a canvas (Path2D: the far view's card marks)
  //   hyIconURL(name, colour, line)   the icon as a CSS url() (a mask, or a check on a coloured box): look.css takes --hy-ic-* from here
  window.hyIcon = (name, size = 18, line = 1.85, cls = "", o = {}) => {
    const g = IC[name]; if (!g) return "";
    const wh = size ? ` width="${size}" height="${size}"` : "";
    const paint = o.fill ? `fill="currentColor" stroke="none"` : `fill="none" stroke="currentColor" stroke-width="${line}" stroke-linecap="round" stroke-linejoin="round"`;
    return `<svg${cls ? ` class="${cls}"` : ""} viewBox="0 0 24 24"${wh} ${paint}${o.attrs ? " " + o.attrs : ""} aria-hidden="true">${g}</svg>`;
  };
  const num = (a, k, d = 0) => { const m = a.match(new RegExp(`\\b${k}="([-\\d.]+)"`)); return m ? +m[1] : d; };
  window.hyIconPath = name => (IC[name] || "").replace(/<(\w+)\b([^>]*?)\/?>/g, (m, tag, a) => {
    if (tag === "path") { const d = a.match(/\bd="([^"]*)"/); return d ? d[1] + " " : ""; }
    if (tag === "circle" || tag === "ellipse") { const cx = num(a, "cx"), cy = num(a, "cy"), rx = num(a, tag === "circle" ? "r" : "rx"), ry = num(a, tag === "circle" ? "r" : "ry");
      return `M${cx - rx} ${cy}a${rx} ${ry} 0 1 0 ${2 * rx} 0a${rx} ${ry} 0 1 0 ${-2 * rx} 0z `; }
    if (tag === "rect") { const x = num(a, "x"), y = num(a, "y"), w = num(a, "width"), h = num(a, "height"), r = Math.min(num(a, "rx"), w / 2, h / 2);
      return r ? `M${x + r} ${y}h${w - 2 * r}a${r} ${r} 0 0 1 ${r} ${r}v${h - 2 * r}a${r} ${r} 0 0 1 ${-r} ${r}h${2 * r - w}a${r} ${r} 0 0 1 ${-r} ${-r}v${2 * r - h}a${r} ${r} 0 0 1 ${r} ${-r}z ` : `M${x} ${y}h${w}v${h}h${-w}z `; }
    if (tag === "line") return `M${num(a, "x1")} ${num(a, "y1")}L${num(a, "x2")} ${num(a, "y2")} `;
    return "";
  }).trim();
  window.hyIconURL = (name, colour = "black", line = 2) => `url("data:image/svg+xml,${encodeURIComponent(hyIcon(name, 0, line).replace("<svg ", `<svg xmlns="http://www.w3.org/2000/svg" color="${colour}" `))}")`;
  // the app's one chevron (owner 2026-10-04: «the arrow must be the same everywhere»): between the crumb's steps, the library's path, its
  // folder tree, the pages button (turned down, .dn); ui/look.css .hy-chev
  window.HY_CHEV = hyIcon("chevron", 0, 2.4, "hy-chev");
  // static markup: <svg data-ic="name"> gets its glyph and the family's attributes (its own width, height, stroke-width and class stay); the
  // page's elements are filled in while the parser adds them, so the page's own scripts already find them drawn
  window.hyIconHydrate = (root = document) => {
    const one = el => { const g = IC[el.getAttribute("data-ic")]; if (!g || el.dataset.icDone) return; el.dataset.icDone = "1";
      el.setAttribute("viewBox", "0 0 24 24"); if (!el.hasAttribute("aria-hidden")) el.setAttribute("aria-hidden", "true");
      if (el.hasAttribute("data-fill")) { el.setAttribute("fill", "currentColor"); el.setAttribute("stroke", "none"); }
      else { el.setAttribute("fill", "none"); el.setAttribute("stroke", "currentColor"); if (!el.hasAttribute("stroke-width")) el.setAttribute("stroke-width", "1.85");
        el.setAttribute("stroke-linecap", "round"); el.setAttribute("stroke-linejoin", "round"); }
      el.innerHTML = g; };
    if (root.matches && root.matches("svg[data-ic]")) one(root);
    if (root.querySelectorAll) root.querySelectorAll("svg[data-ic]").forEach(one);
  };
  if (typeof document !== "undefined" && document.documentElement) {
    if (document.readyState === "loading" && typeof MutationObserver === "function") {
      const mo = new MutationObserver(rs => { for (const r of rs) for (const n of r.addedNodes) if (n.nodeType === 1) hyIconHydrate(n); });
      mo.observe(document.documentElement, { childList: true, subtree: true });
      document.addEventListener("DOMContentLoaded", () => { mo.disconnect(); hyIconHydrate(); }, { once: true });
    } else hyIconHydrate();
    // the icons CSS draws (a mask, a check on a coloured box): look.css and the pages use these, no glyph is written in a stylesheet
    const st = document.createElement("style"); st.id = "hy-ic-css";
    st.textContent = `:root { --hy-ic-info: ${hyIconURL("info", "black", 2)}; --hy-ic-check-on: ${hyIconURL("check", "white", 3.4)}; --hy-ic-search-sub: ${hyIconURL("search", "#a1a1aa", 2)}; }`;   // the last: the library's search field, an <input> takes no mask, so its magnifier is drawn in --sub's grey
    (document.head || document.documentElement).appendChild(st);
  }
  // Raw Editor's icon (owner 2026-10-08, C1 «RGB» of Concepts/html/icons-redesign round 2: «вот этот берем для цветкора»; the colour
  // wheel with its puck before it stood too close to the settings knob): three circles of light, red, green and blue. Normal, their lines
  // in currentColor; on (a picture with a working grade), filled in their colours and added as light adds (screen, inside their own
  // group): where two meet they mix, the middle is white, on a card's dark plate and on a light panel alike.
  //   hyGradeIcon(on, size, line, cls)   a whole <svg>; line: the circles' stroke on the 24 grid (the bar 1.9, a card's mark 2.2)
  IC.rawEditor = '<circle cx="12" cy="8.7" r="5.1"/><circle cx="8.95" cy="13.9" r="5.1"/><circle cx="15.05" cy="13.9" r="5.1"/>';   // Raw Editor: the colour grade
  const RGB = [[12, 8.7, "#ff3b30"], [8.95, 13.9, "#34c759"], [15.05, 13.9, "#0a84ff"]];
  window.hyGradeIcon = (on, size = 15, line = 1.9, cls = "") => {
    const open = `<svg${cls ? ` class="${cls}"` : ""} viewBox="0 0 24 24" width="${size}" height="${size}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">`;
    if (!on) return open + `<g fill="none" stroke="currentColor" stroke-width="${line}">${IC.rawEditor}</g></svg>`;
    const r = 5.1 + line / 2;   // filled, as wide as an outlined circle with its line
    return open + '<g style="isolation:isolate">' + RGB.map(([x, y, c]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${c}" style="mix-blend-mode:screen"/>`).join("") + "</g></svg>";
  };
})();
