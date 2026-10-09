// @ts-check
// The app's primitives, one module (docs/ui-inventory.md §4, DESIGN.md «Примитивы»). A page links ui/tokens.css and ui/hy/hy.css and
// loads this file as a module; the image studio (an iframe, its own registry) loads it itself; the 3D and Dev studios run in the board's
// document and find the elements defined (customElements.whenDefined("hy-button") before their first use). Each file defines its element
// only when this document has not yet, so a second import is harmless.
export { HySwitch } from "./switch.js";
export { HyCheck } from "./check.js";
export { HyKbd } from "./kbd.js";
export { HyBadge } from "./badge.js";
export { HyChip } from "./chip.js";
export { HyHint, HyInfo } from "./hint.js";
export { HySwatch, HySwatches } from "./swatch.js";
export { HyButton, HyIconButton } from "./button.js";
export { HyPlate } from "./plate.js";
export { HySegmented } from "./segmented.js";
export { HyKeyHint } from "./keyhint.js";   // also window.hyKeyHint for the classic scripts
export { HyTip } from "./tip.js";   // also window.hyTip for the classic scripts
export { HyStudioActions } from "./actions.js";   // a Studio's session actions, top right (owner 2026-10-09)
export { HyOpenIn } from "./openin.js";   // «Open in <Browser>»; its way to the app is window.hyBrowsers
