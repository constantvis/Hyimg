// The window helpers the primitives call, written by the classic scripts of review/ui (icons.js, i18n.js, seg.js), and the tags they
// define, for `tsc --noEmit --checkJs` over review/ui/hy (jsconfig.json). Only what review/ui/hy uses is declared here.
import type { HySwitch } from "./switch.js";
import type { HyCheck } from "./check.js";
import type { HyKbd } from "./kbd.js";
import type { HyBadge } from "./badge.js";
import type { HyChip } from "./chip.js";
import type { HyHint, HyInfo } from "./hint.js";
import type { HySwatch, HySwatches } from "./swatch.js";
import type { HyButton, HyIconButton } from "./button.js";
import type { HyPlate } from "./plate.js";
import type { HySegmented } from "./segmented.js";
import type { HyKeyHint } from "./keyhint.js";
import type { HyStudioActions } from "./actions.js";
import type { HyOpenIn } from "./openin.js";
import type { HyMiniToggle } from "./minitoggle.js";
import type { HyScope } from "./scope.js";
import type { HyLed } from "./led.js";
import type { HyStepper } from "./stepper.js";
import type { HyScrub } from "./scrub.js";

declare global {
  interface HyT {
    (key: string, vars?: Record<string, string | number>): string;
    lang: "en" | "ru";
    dom(root?: Element): void;
  }
  interface Window {
    T?: HyT;
    hyLang?: (dict: { en?: Record<string, unknown>; ru?: Record<string, unknown> }) => void;
    hyIcon?: (name: string, size?: number, line?: number, cls?: string, o?: { fill?: boolean; attrs?: string }) => string;
    hyIconURL?: (name: string, colour?: string, line?: number) => string;
    hyIconHydrate?: (root?: ParentNode) => void;
    hySeg?: (root?: ParentNode) => void;
    HY_SEG_MANUAL?: boolean;
    HY_COLORS?: Record<string, string>;
    /** the one rule for keys while typing (ui/typing.js): true while a key goes into a field that takes text */
    hyTyping?: ((e?: Event) => boolean) & { field(el: Element | null): boolean; active(doc?: Document): Element | null };
  }
  interface HTMLElementTagNameMap {
    "hy-switch": HySwitch;
    "hy-check": HyCheck;
    "hy-kbd": HyKbd;
    "hy-badge": HyBadge;
    "hy-chip": HyChip;
    "hy-hint": HyHint;
    "hy-info": HyInfo;
    "hy-swatch": HySwatch;
    "hy-swatches": HySwatches;
    "hy-button": HyButton;
    "hy-icon-button": HyIconButton;
    "hy-plate": HyPlate;
    "hy-segmented": HySegmented;
    "hy-keyhint": HyKeyHint;
    "hy-studio-actions": HyStudioActions;
    "hy-open-in": HyOpenIn;
    "hy-minitoggle": HyMiniToggle;
    "hy-scope": HyScope;
    "hy-led": HyLed;
    "hy-stepper": HyStepper;
    "hy-scrub": HyScrub;
  }
}
export {};
