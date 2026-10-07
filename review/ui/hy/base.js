// @ts-check
// The base of the app's primitives (docs/ui-inventory.md §4, owner 2026-10-07: build them). A primitive is an autonomous custom element
// in the light DOM: no shadow root, because the look follows the root's data-theme and data-shape and the tests, the design audit, menu.js,
// keyhints.js and eyedrag.js find controls by plain selectors. State is an attribute mirrored to ARIA, the look is ui/hy/<name>.css read
// from tokens only (ui/tokens.css), events carry the hy- prefix. Each element registers once per document: a page and a plugin may both
// import ui/hy/index.js.

/** The app's curve for new work (design/contract.json easing). */
export const EASE = "cubic-bezier(.32,.72,0,1)";

/**
 * Registers a primitive unless this document already has the tag (a page and a plugin importing the module twice is harmless).
 * @param {string} tag
 * @param {CustomElementConstructor} cls
 * @returns {CustomElementConstructor}
 */
export function define(tag, cls) {
  const had = customElements.get(tag);
  if (had) return had;
  customElements.define(tag, cls);
  return cls;
}

/**
 * One of the allowed words, or the default.
 * @template {string} V
 * @param {string | null | undefined} v
 * @param {readonly V[]} allowed
 * @param {V} fallback
 * @returns {V}
 */
export function oneOf(v, allowed, fallback) {
  return /** @type {V} */ (allowed.find(a => a === v) ?? fallback);
}

/**
 * A word in the interface's language (ui/i18n.js T, its Russian in ui/lang-*.js); the English key when the page has no T.
 * @param {string} key
 * @param {Record<string, string | number>} [vars]
 * @returns {string}
 */
export function t(key, vars) {
  const T = window.T;
  if (typeof T === "function") return T(key, vars);
  return vars ? key.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : key;
}

/**
 * An icon of the registry (ui/icons.js hyIcon), or nothing when the page has not loaded the registry.
 * @param {string} name
 * @param {number} size
 * @param {number} [line]
 * @returns {string}
 */
export function icon(name, size, line = 1.85) {
  return typeof window.hyIcon === "function" ? window.hyIcon(name, size, line) : "";
}

/** The base class: attribute helpers and the hy- events. */
export class HyElement extends HTMLElement {
  /**
   * @param {string} name
   * @returns {boolean}
   */
  flag(name) { return this.hasAttribute(name); }

  /**
   * @param {string} name
   * @param {boolean} on
   */
  setFlag(name, on) { this.toggleAttribute(name, !!on); }

  /**
   * @param {string} name
   * @param {string} [fallback]
   * @returns {string}
   */
  word(name, fallback = "") { return this.getAttribute(name) ?? fallback; }

  /**
   * @param {string} name
   * @param {string | null} v
   */
  setWord(name, v) { if (v === null || v === undefined) this.removeAttribute(name); else this.setAttribute(name, String(v)); }

  /**
   * A property a page set on the element before its class was defined (a plain object property then) goes through the setter now.
   * @param {...string} names
   */
  upgrade(...names) {
    for (const n of names) {
      if (!Object.prototype.hasOwnProperty.call(this, n)) continue;
      const v = /** @type {any} */ (this)[n];
      delete (/** @type {any} */ (this))[n];
      /** @type {any} */ (this)[n] = v;
    }
  }

  /**
   * Sends an event from the element; it bubbles, as the page's own events do.
   * @param {string} type
   * @param {any} [detail]
   * @returns {boolean} false when a listener called preventDefault()
   */
  emit(type, detail) {
    return this.dispatchEvent(new CustomEvent(type, { detail, bubbles: true, cancelable: true }));
  }
}
