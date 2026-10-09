<p align="center"><img src="docs/images/icon.png" width="128" height="128" alt="Hyimg icon"></p>

<h1 align="center">Hyimg</h1>

<p align="center"><b>A local Figma + Lightroom + Miro, built to work side by side with AI agents.</b><br>
A Mac app for people who make images at volume and sort them by eye.</p>

<p align="center"><a href="README.ru.md">Русская версия</a></p>

![A Hyimg board: groups, sticky notes, an image frame, a 3D card and the library on the left](docs/images/board.webp)

When you generate a lot, you end up with thousands of files in dozens of folders, and the agent that made them can't see which ones you liked. Hyimg puts a library and an infinite board on top of the folders you already have. You sort on the board. Your agent reads the same board, knows what you've selected, and puts its next batch right where you want it.

Nothing leaves your Mac. There is no account and no upload: each project is a folder on disk, and a small local server shows it in a native window.

## What's in it

**A library over your own folders** (the Lightroom part). Subfolders become collections. Hearts, verdicts, tags and filters, the prompt and sources from the json next to each file, previews for video, PSD, PSB, AI, TIFF, HEIC and SVG. Files stay where they are.

**An infinite board** (the Miro and Figma part). Groups, sticky notes that attach to the frames under them, titles, timelines, pages with dividers, crop, copies that point back to the original, version history with undo. Videos play right on the board. Paste or drop any image to add it.

**Made for agents.** Point an agent at `http://localhost:<port>/agent` and it gets the whole picture: what's open, the project's rules, the skills and the commands. `review/hy.py` edits the board by names instead of coordinates (`hy.py do 'block <folder> into=<group> note=…'`), `scripts/active.py` tells it what you have selected right now, and a right click gives you a link to any frame or group to paste into the chat. Skills for Claude Code, Codex, Gemini CLI and Antigravity live in `skills/`.

![A working board: about 7,000 frames in groups, at 1 % zoom](docs/images/big-board.webp)
<p align="center"><sub>A real working board: about 7,000 frames in groups, seen at 1 % zoom</sub></p>

## Plugins

Hyimg works without them. With them the board does more, and each one lives in its own repository:

- **[Frames](https://github.com/constantvis/hyimg-frames)**: Image Studio, which opens in place on the board, with layers, masks, a brush, Raw Editor (Camera Raw style grading, also on any picture of the board), subject selection through macOS Vision and content-aware fill with LaMa. The originals are never touched: a frame keeps its own layers and renders to its own file. The same plugin adds HTML frames, live web pages as cards.
- **[3D objects](https://github.com/constantvis/hyimg-3d-studio)**: a 3D scene as a card on the board, 3D Studio on three.js, snapshots to images, and a bridge to Blender and back.
- **[Dev Studio](https://github.com/constantvis/hyimg-dev-studio)**: HTML files of the library as cards on the board, and Dev Studio, where you work on a page the way you work on a frame in Figma: its element tree, the live page, an inspector whose changes go into the `.html` file itself.

![Image Studio open in place on the board](docs/images/frame-editor.webp)

```sh
./scripts/install_plugins.sh                             # asks about each plugin
./scripts/install_plugins.sh --frames --3d --dev --yes   # no questions, for an agent after the person said yes
```

The script uses checkouts next to this repository or clones them there and links them into `~/Library/Application Support/Hyimg/plugins`. Then View › Restart server (⇧⌘R). The LaMa model for content-aware fill (about 208 MB) is downloaded only with `--lama`.

**For agents:** before you install Hyimg or start working with it, ask the person about each plugin by name, say in one line what it gives and what it needs, and install it only after a yes. Details in `AGENTS.md`.

## Install

You need macOS 14 or later, the Xcode Command Line Tools and Python 3.10+ with Pillow. Tests also need pytest and Node.js.

```sh
./build.sh
./scripts/install.sh
```

The app goes to `~/Applications/Hyimg.app`; the code stays in this repository, so ⌘R picks up HTML changes and ⇧⌘R restarts the server after Python changes. Swift changes need a rebuild. Open Hyimg, then connect an existing folder or create a new one: each project gets its own boards, history, ratings and settings.

### Rendering engine

By default the boards are drawn by Chromium (CEF) inside the Hyimg window, on the GPU, which stays smooth with hundreds of pictures. View › Chromium engine (or ⚙ on the board) switches to WebKit. `./build.sh` takes the CEF SDK from `~/Library/Caches/Hyimg/cef_binary_*_macosarm64_minimal` (the minimal build from https://cef-builds.spotifycdn.com; build its wrapper with `cmake -G "Unix Makefiles" -DPROJECT_ARCH=arm64 -DCMAKE_BUILD_TYPE=Release .. && make libcef_dll_wrapper`). Without the SDK, or with `HYIMG_NO_CEF=1`, you get a WebKit-only app of about 1 MB instead of 330 MB. That CEF build has no H.264 decoder, so Hyimg plays such videos from a WebM copy it makes once with ffmpeg.

## For agents: where to look

- `http://localhost:<port>/agent` (also `/llms.txt` and `python3 review/hy.py guide`): what's open, the board's pages, the project's own `AGENTS.md`, skills and commands.
- `python3 scripts/active.py`: the open project, its tabs and what's selected on the board or in the library. `--paths` prints just the selected files, `--link "<link>"` resolves a link the person pasted.
- `skills/`: `hyimg` (start here), `hyimg-board` (the board through `hy.py`), `hyimg-generate` (batches: five tries per prompt, a json next to every image). `scripts/install_skills.sh` links them for Claude Code, Codex, Gemini CLI and Antigravity.
- `python3 review/hy.py features [word]`: the feature catalog (`review/features.json`). For every feature: how the person uses it, the agent's exact command or route, the skill that covers it. `/agent` prints it as «Что умеет Hyimg». A test fails when a new `hy.py` command, server route, kind of copied property, dock mode or MCP tool has no entry.
- The board's «Playground» page in the Hyimg App project shows every feature on test files, with a note on how to try each one.

## MCP

`mcp/server.py` exposes the same operations to any MCP client over stdio, using only the Python standard library. Tools: `hyimg_guide` (start here), `hyimg_features`, `hyimg_projects`, `hyimg_active`, `hyimg_map`, `hyimg_find`, `hyimg_check`, `hyimg_pages`, `hyimg_page_new`, `hyimg_do`, `hyimg_notify`, `hyimg_props`, `hyimg_presets`, `hyimg_topage`, `hyimg_hist`, `hyimg_restore`, `hyimg_save`. The skills, the catalog and `/agent` are available as resources (`hyimg://skills/<name>`, `hyimg://features`, `hyimg://agent`) and as prompts. Each tool takes a `project` (name, id or port). By default it uses the project in Hyimg's front tab, or the only running one. Ports come from `~/Library/Application Support/Hyimg/projects.json` and are checked against `/api/health`. Hyimg itself has to be running: the server talks to it over HTTP like `hy.py`.

Nothing is registered automatically. To add it (replace the path with your clone):

```sh
# Claude Code, for every project of this user
claude mcp add -s user hyimg -- python3 /path/to/hyimg/mcp/server.py
# Codex
codex mcp add hyimg -- python3 /path/to/hyimg/mcp/server.py
```

Claude Desktop: add to `~/Library/Application Support/Claude/claude_desktop_config.json` and restart it:

```json
{ "mcpServers": { "hyimg": { "command": "/usr/bin/python3", "args": ["/path/to/hyimg/mcp/server.py"] } } }
```

`python3 mcp/server.py --list-tools` prints the tools with their descriptions. Tests: `tests/test_mcp_server.py`.

## Tests

```sh
python3 -m pytest -q tests/
node --test tests/test_canvas_save.mjs
tests/test_native.sh && ./build.sh && tests/test_native_cli.sh && tests/test_webkit.sh
```

Tests work in temporary folders and never write to your projects. Data layout: `docs/data.md`. Development rules: `AGENTS.md`. Interface decisions: `DESIGN.md`.

## License

[PolyForm Noncommercial 1.0.0](LICENSE): free to use, study and change for yourself and for noncommercial purposes. Commercial use only with the author's permission; get in touch through GitHub. Third-party code keeps its own licenses.
