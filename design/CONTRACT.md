# Hyimg design contract

The machine-readable contract is `design/contract.json`. This page says what it holds and how the checks use it. The values come from the code as of 2026-10-06 (`review/ui/look.css`, `slider.css`, `menu.js`, `icons.js`, the pages' `:root`, `DESIGN.md` and the owner's dated quotes in comments). Where the code disagreed with itself, the contract takes the majority or the value the owner stated, and the disagreement is listed in `contract.json` under `disagreements`.

## Values

| What | Contract | Source |
|---|---|---|
| Easing | `cubic-bezier(.32,.72,0,1)` for new work; also `(.3,.8,.25,1)` for big moves (DESIGN.md), `hyPop` `(.2,.9,.3,1.15)`, the `hyGrow` segments, the loading lines' `(.16,1,.3,1)`, `hyLay` `(.45,0,.15,1)`; `ease` for opacity and colour, `linear` for keyframes with their own timing, `ease-in-out` only in endless breathing loops | 114 uses of `.32,.72,0,1`; DESIGN.md «Движение» |
| Row control radius | `var(--hy-row-r)`: 999px round, 8px pro. Slider, select, field, option, chip, search | look.css, owner 2026-10-06 «одни круглые другие квадратные» |
| Tree row | 28px tall, `--hy-trow-r` 8px | look.css |
| Plates, bars, buttons in pro | plate 11px, bar 14px, button inside a plate 8px, `.seg` button 6px | DESIGN.md «Вид элементов» |
| Heights | plate 38, its buttons 30, dock button 34, panel row 32, menu row 32, `.seg` option 28, slider 34, kbd 20 | the pages' CSS |
| Icons | one registry, `ui/icons.js` (`HY_TOOL_IC`), one glyph per meaning; family line 1.85 on a 24 grid, menus 1.9 at 15px, chevron 2.4 at 12px; heavier small glyphs 2 to 2.2 | icons.js, menu.js |
| Card marks | 24px plate, 6px inset (20px on a selected card), 12px icon, 11px type, 4px gap, radius 999px or 5px pro, full size from 96px cards | canvas.html `.mk`, `MK` |
| Fonts | Geist and Geist Mono with system fallbacks; «SF Pro Text» only in the studio look. Served from `review/ui/fonts/` through `ui/fonts.css` (imported by `ui/tokens.css`), never from Google Fonts | the pages' `--sans` |
| Colours | dark and light token sets (`--bg --panel --raise --ink --sub --muted --line --sel --paper`), eight marking colours, the danger reds; CSS takes them by `var()` only | canvas.html, v2.html, look.css, menu.js |
| z-index layers | local −1–9, content 10–29, chrome 30–39, overlay 40–59, menu 60–79, dialog 80–99, toast 1000, takeover 1100–1299, Dev studio's inspector 2147483647 | every z-index in the four repositories |
| Focus | no ring: no outline or box-shadow on `:focus` and `:focus-visible` | owner 2026-10-05 «убери эти уебищные focus выделения» |
| Hints | an explanation is not written when it is not key, one footnote line `.hy-hint` (11px, line 1.35, `--hy-hint`, key words in `<b>`) when it is, a ⓘ `.hy-info` with the text in its tooltip when something is really unclear; more than 14 words in body text fails, a footnote holds 20 (`runtime.prose`) | ui/hy/hint.css, owner 2026-10-06 «Вот эти комментарии никто не читает ... микро шрифтом» |

## Icons and colours

«Одно значение, одна иконка, только из ui/icons.js; цвета только токенами» (owner 2026-10-07, after the image studio's Adjustments tab wore the opacity's half circle).

- The registry is `review/ui/icons.js` (`HY_TOOL_IC`). Each glyph has one name, and the comment after it says what it means. A new meaning gets its own glyph there; a glyph that only looks close is not reused.
- Pages and plugins draw icons only through the registry: `hyIcon(name, size, line, cls)` in code, `<svg data-ic="name" width height stroke-width>` in static markup (filled in while the page is parsed), `hyIconPath(name)` on a canvas, and the `--hy-ic-*` images in CSS. Older names a page still passes sit in one table marked `hy-icon-names` (ui/menu.js `NAME`, the image studio's `ICON_NAME`, the 3D studio's `FAMILY`).
- Icons are drawn in `currentColor`. Raw Editor's «on» disc (`hyGradeIcon`) is the only icon with colours of its own.
- A drawing that is not an icon (the board's arrows, the marks drawn on a frame, the axes gizmo, a cursor) carries `hy-allow: icon-inline <what it is>` on its line, or sits between `hy-allow-begin: icon-inline <what it is>` and `hy-allow-end`.
- In CSS a colour is a token: a hex, `rgb()` or `hsl()` is written once, as a token's value (`--sel: #3b82f6`) or a `var()` fallback. The colours written before the rule are in the baseline (`css-color`); a new one fails.

## Primitives

Owner 2026-10-07, after the inventory (`docs/ui-inventory.md`): a control that has a primitive is built only from it. A hand-built switch, checkbox, key cap, badge or plate is a defect; a missing variant goes into the primitive.

- What exists, in `review/ui/hy/` (one file per element): `hy-button` (variant plain, solid, ghost, danger, reset; size s 24, m 28, l 30, row 32, dock 34, plate 38; pressed, toggle, disabled, icon, kbd), `hy-icon-button` (registry icon, xs 20 to plate 38, label, shape), `hy-switch` (30 × 18), `hy-check`, `hy-chip`, `hy-swatch` and `hy-swatches`, `hy-segmented` (on `ui/seg.js`, tabs variant), `hy-kbd` (20, 18, 15), `hy-badge`, `hy-hint`, `hy-info`, `hy-plate`.
- How they are built: autonomous custom elements in the light DOM, state as attributes mirrored to ARIA, a real `<button>` or `<input>` inside, events prefixed `hy-`, each defined once per document. Their CSS reads tokens only, so `<hy-*>` markup is drawn right before the module upgrades it.
- Tokens: `review/ui/tokens.css`, the one palette (it was written four times), the heights `--hy-h-*`, the corners by shape (`--hy-row-r`, `--hy-plate-r`, `--hy-bar-r`, `--hy-btn-r`, `--hy-seg-r`, `--hy-chip-r`, `--hy-switch-r`). `data-hy-theme` and `data-hy-shape` on an element switch the tokens under it (the showcase puts the four looks side by side).
- Loading: `ui/tokens.css`, `ui/hy/hy.css` and the module `ui/hy/index.js`. The image studio loads them itself (an iframe has its own registry); the 3D and Dev studios run in the board's document.
- Types: JSDoc, `tsc -p jsconfig.json` over `review/ui/hy` (scripts/check.sh runs it when `tsc` is on the machine).
- Showcase: `review/ui/hy/showcase.html`, live on the Hyimg App board (page «UI», cards `html/hy-primitives/*.html`).

## Checks

**Static**, `scripts/validate.py` (about 1 second for the four repositories). Rules: `js-syntax` (node --check of every .js and inline script), `comment-swallow`, `easing`, `focus-ring`, `range-input`, `row-radius`, `icon-stroke`, `cyrillic-code`, `lang-period`, `ru-style`, `z-layer`, `font-family`, `panel-prose` (an explanation in a panel is a footnote or a ⓘ, see below), `row-plate` (a title plate of the top row is made with `.hy-plate` and sets none of its look; a rule for a plate of the row keeps the row's height, glass and shadow tokens), `icon-inline`, `icon-registry`, `icon-color` and `css-color` (the section above; their tests are `tests/test_validate_icons.py`), `hy-primitive` (a control that has a primitive is not built by hand again, `scripts/validate_prim.py`; warn mode: today's copies are in the baseline and may only go down, `--list hy-primitive` names them), `capsule-pad` (a pill control's words at least 8 px from its round ends, 6 on a chip under 22 px, 5 on an option of a choice; a panel's `button { padding: 0 }` reset goes under `:where()` so it never outweighs a button's own padding). `--rules` prints each rule's reason.

**Runtime**, `tests/test_design_audit.py` with `design/audit.js`. It opens the board, the library (panel and wide), Home, the image studio, the 3D studio and Dev studio in dark and light, round and pro, at 1000 and 1600px, on a temporary library with every kind of card. Checks: `row-radius` (one radius per panel), `bar-height` (one height per bar), `font`, `viewport`, `covered` (the centre of each control is that control, through the board's frame into the library page too), `hint` (key caps only under ⌘, labels not cut), `target` (24px or more), `marks` (one height, inset and radius per card, inside the card, no overlap, at three zooms), `lib-pill` (the library's pills against the board's marks), `focus` (a keyboard-focused control shows no ring), `prose` (no paragraph of explanation in body text).

**Inset**, `tests/test_design_inset.py` with `design/audit.js` `inset` (opt-in, strict, no baseline; owner 2026-10-06: «Presets ⌄» flush against its capsule, «посмотри, где еще вот такие проблемы есть»). Every page and panel (the board with its selection bar, right click and Raw Editor with its presets, the library and its filters, Home and its settings, the image studio, the 3D studio, Dev studio) in both themes, both shapes, Russian and English. A capsule, chip, button, select, field or tag keeps its content `inset.capsule` 8 px from its round ends (radius × `share` if more), a chip under `small_h` 22 px 6, a rounded rectangle 6, an option of a choice 5; a label cut short never runs into an icon; a plate inside a plate (a choice's thumb) sits `nested` px in on all four sides, centred, its radius the outer one less that inset; the app's slider keeps its line inside its round ends at any value. The tokens: `--hy-cap-pad` 10 px (a capsule's words) and `--hy-seg-pad` 3 px (a thumb in its track), `ui/look.css`.

**Top row**, `tests/test_design_toprow.py` with `design/audit.js` `top-row` (opt-in, strict, no baseline; owner 2026-10-07: «breadcrumb area тоже разношерстная»). Run from the window's page, it reads the row across the frames of one origin (the library page, the board, the image studio) in the window's coordinates: every plate of the row (`top_row`: within 30 px of the top, at most 60 px tall) stands 12 px down, is 38 px tall, 12 px from the window's sides, 8 px from a neighbour, with one glass, shadow and corner and 13 px words; the mode's hint plate (`#obar`) and the side panels start 58 px down; nothing lies on a band a page draws as the window's edge (`window.hyEdges()`, the image studio's rulers); no note (`ui/toasts.js`, standing on the 58 px line) covers a plate of the row. The board with a group's title stuck after the crumb, the library, the image, 3D and Dev studios and Home, in both themes, both shapes, Russian and English, and the Mac app's window. The tokens: `--hy-row-top`, `--hy-row-gut`, `--hy-plate-h`, `--hy-row-gap`, `--hy-row-under` and the look `.hy-plate` (`ui/hy/plate.css`), `ui/tokens.css`.

**Baseline.** `design/baseline.json` holds what is known today: `static` by rule, file and line text, `runtime` by page, check and key (no coordinates). A check fails only on something new. When a known violation is fixed, the count drops: `validate.py --update-baseline` writes it down, and the audit is rewritten with `HY_AUDIT_UPDATE=1`.

**Silencing one line.** Put `hy-allow: <rule> <reason>` in a comment on the line or the line above it.

## File size

Owner 2026-10-07: «чтобы файлы не содержали больше тысячи строк на один файл», «допустимо, если будет 1050 или 1100, это окей». The rule is `file-size` in `scripts/validate.py` (its code is `scripts/validate_size.py`), so `check.sh --fast` and the pre-commit hook run it on the four repositories.

- A source file is about 1000 lines and fails above 1100. Source means .py, .js, .mjs, .cjs, .ts, .html and .htm with their inline script and style, .css, .swift, .m, .mm, .h and .sh, tests and `native/` included.
- A line is about 160 characters and fails above 200. Without this the line count says little: `review/canvas.html` had lines of 884 characters.
- Not counted: data and generated files (json, md, svg, images, a file with `@generated` in its first 5 lines), vendored code (`vendor/`, `node_modules/`, `*.min.js`, `*.min.css`), builds and caches (`dist/`, `build/`, `__pycache__/`, `.venv/`, `_review/`, folders whose name starts with a dot). URLs do not count towards a line's length, and the lang tables (`lang.js`, `lang-*.js`) have no line limit.
- A file near the limit is split by responsibility, one concern per module, not cut into chunks of 1000 lines. The split is a change of its own with no change in behaviour, the full suites run before and after.

Files over the limits today are listed in `design/baseline.json` under `file_size` with their lines (when over 1100), their count of lines over 200 and their longest line. If any of the three grows, the check fails and names the file, its size and the limit, so these files can only shrink. `--update-baseline` lowers the numbers of a file that shrank and drops a file that is back under the limits. It never raises a number and never adds a file. Between 1000 and 1100 lines a new file only gets a warning in the summary.

## Commands

```
scripts/check.sh --fast        validator and unit tests of the four repositories, about 10 s
scripts/check.sh --full        and every Playwright suite, the design audit among them
scripts/validate.py --list row-radius
scripts/validate.py --list file-size    every file over 1000 lines or with lines over 160 characters
HY_AUDIT_QUICK=1 python3 -m pytest tests/test_design_audit.py    one look per page, about 1 minute
scripts/install_hooks.sh       pre-commit hooks running check.sh --staged in the four repositories
```
