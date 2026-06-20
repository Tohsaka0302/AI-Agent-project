/**
 * injector.js — DOM Event Capture Script
 *
 * Injected into every page by the Playwright recorder.
 * Listens to user interactions and reports them back to Python
 * via the exposed __pw_record_action() function.
 *
 * Captures: click, input/change (fill), keydown, scroll, navigation
 */

(function () {
  "use strict";

  // Prevent double-injection
  if (window.__pw_injector_active) return;
  window.__pw_injector_active = true;

  // ── CSS Selector Generation ──────────────────────────────────

  /**
   * Generate a robust CSS selector for an element.
   * Fallback chain: id → data-testid → name → role+text → aria-label → nth-child path
   */
  function getSelector(el) {
    if (!el || el === document.body || el === document.documentElement) {
      return "body";
    }

    // Priority 1: unique ID
    if (el.id) {
      // Verify uniqueness
      if (document.querySelectorAll(`#${CSS.escape(el.id)}`).length === 1) {
        return `#${CSS.escape(el.id)}`;
      }
    }

    // Priority 2: data-testid
    const testId = el.getAttribute("data-testid") || el.getAttribute("data-test-id");
    if (testId) {
      return `[data-testid="${testId}"]`;
    }

    // Priority 3: name attribute (form fields)
    if (el.name && ["INPUT", "SELECT", "TEXTAREA"].includes(el.tagName)) {
      const sel = `${el.tagName.toLowerCase()}[name="${CSS.escape(el.name)}"]`;
      if (document.querySelectorAll(sel).length === 1) {
        return sel;
      }
    }

    // Priority 4: input type + placeholder
    if (el.tagName === "INPUT" && el.placeholder) {
      const sel = `input[placeholder="${CSS.escape(el.placeholder)}"]`;
      if (document.querySelectorAll(sel).length === 1) {
        return sel;
      }
    }

    // Priority 5: role + accessible text (buttons, links, labels)
    const text = getVisibleText(el);
    if (text && ["BUTTON", "A", "LABEL"].includes(el.tagName)) {
      // Use Playwright's text selector format
      const escapedText = text.replace(/"/g, '\\"');
      return `${el.tagName.toLowerCase()}:has-text("${escapedText}")`;
    }

    // Priority 6: type=submit buttons
    if (el.tagName === "INPUT" && el.type === "submit") {
      const val = el.value;
      if (val) {
        const sel = `input[type="submit"][value="${CSS.escape(val)}"]`;
        if (document.querySelectorAll(sel).length === 1) {
          return sel;
        }
      }
    }

    // Priority 7: aria-label
    const ariaLabel = el.getAttribute("aria-label");
    if (ariaLabel) {
      const sel = `[aria-label="${CSS.escape(ariaLabel)}"]`;
      if (document.querySelectorAll(sel).length === 1) {
        return sel;
      }
    }

    // Priority 8: role attribute
    const role = el.getAttribute("role");
    if (role && text) {
      const escapedText = text.replace(/"/g, '\\"');
      return `[role="${role}"]:has-text("${escapedText}")`;
    }

    // Fallback: nth-child path from closest identifiable ancestor
    return buildSelectorPath(el);
  }

  /**
   * Build a selector path using nth-of-type from the closest
   * ancestor that has an id or is the body.
   */
  function buildSelectorPath(el) {
    const parts = [];
    let current = el;

    while (current && current !== document.body && current !== document.documentElement) {
      // If we hit an element with an ID, use it as anchor
      if (current.id && document.querySelectorAll(`#${CSS.escape(current.id)}`).length === 1) {
        parts.unshift(`#${CSS.escape(current.id)}`);
        break;
      }

      const tag = current.tagName.toLowerCase();
      const parent = current.parentElement;

      if (parent) {
        const siblings = Array.from(parent.children).filter(
          (c) => c.tagName === current.tagName
        );
        if (siblings.length === 1) {
          parts.unshift(tag);
        } else {
          const index = siblings.indexOf(current) + 1;
          parts.unshift(`${tag}:nth-of-type(${index})`);
        }
      } else {
        parts.unshift(tag);
      }

      current = parent;
    }

    // If we didn't find an ID anchor, start from body
    if (parts.length > 0 && !parts[0].startsWith("#")) {
      parts.unshift("body");
    }

    return parts.join(" > ");
  }

  /**
   * Get visible text content of an element (first 80 chars).
   */
  function getVisibleText(el) {
    // For inputs, use value or placeholder
    if (el.tagName === "INPUT") {
      return (el.value || el.placeholder || "").trim().slice(0, 80);
    }
    // For other elements, use direct text (not children's text)
    const text = el.textContent || "";
    return text.trim().slice(0, 80);
  }

  /**
   * Generate a fallback selector as secondary option.
   */
  function getFallbackSelector(el) {
    // Try a different strategy than the primary selector
    if (el.className && typeof el.className === "string") {
      const classes = el.className
        .trim()
        .split(/\s+/)
        .filter((c) => c && !c.match(/^(active|hover|focus|selected|open|show|hidden)/i))
        .slice(0, 2);
      if (classes.length > 0) {
        const sel = `${el.tagName.toLowerCase()}.${classes.map(CSS.escape).join(".")}`;
        if (document.querySelectorAll(sel).length === 1) {
          return sel;
        }
      }
    }
    return null;
  }

  // ── Scroll Tracking ─────────────────────────────────────────

  let scrollTimer = null;
  let scrollStarted = false;
  let accumulatedDeltaX = 0;
  let accumulatedDeltaY = 0;
  const SCROLL_IDLE_MS = 400;

  function onWheel(e) {
    accumulatedDeltaX += e.deltaX;
    accumulatedDeltaY += e.deltaY;

    if (!scrollStarted) {
      scrollStarted = true;
      // Don't emit scroll_start — we'll emit a single scroll event on idle
    }

    // Reset idle timer
    if (scrollTimer) clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      // Scroll sequence ended — emit one consolidated scroll event
      if (scrollStarted) {
        window.__pw_record_action(
          JSON.stringify({
            type: "scroll",
            timestamp: Date.now() / 1000,
            deltaX: Math.round(accumulatedDeltaX),
            deltaY: Math.round(accumulatedDeltaY),
            url: location.href,
          })
        );
        accumulatedDeltaX = 0;
        accumulatedDeltaY = 0;
        scrollStarted = false;
      }
    }, SCROLL_IDLE_MS);
  }

  // ── Click Tracking ──────────────────────────────────────────

  function onClick(e) {
    const target = e.target;
    if (!target) return;

    const selector = getSelector(target);
    const fallback = getFallbackSelector(target);
    const text = getVisibleText(target);

    window.__pw_record_action(
      JSON.stringify({
        type: "click",
        timestamp: Date.now() / 1000,
        selector: selector,
        fallback_selector: fallback,
        tag: target.tagName,
        text: text,
        position: { x: e.clientX, y: e.clientY },
        url: location.href,
      })
    );
  }

  // ── Input/Change Tracking (Fill) ────────────────────────────

  // Debounce input events to capture final value (handles IME composition)
  const inputTimers = new WeakMap();

  function onInput(e) {
    const target = e.target;
    if (!target) return;
    if (!["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;

    // Ignore during IME composition
    if (e.isComposing) return;

    // Debounce: wait 300ms after last input to capture final value
    if (inputTimers.has(target)) {
      clearTimeout(inputTimers.get(target));
    }

    inputTimers.set(
      target,
      setTimeout(() => {
        const selector = getSelector(target);
        const value = target.value || "";

        window.__pw_record_action(
          JSON.stringify({
            type: "fill",
            timestamp: Date.now() / 1000,
            selector: selector,
            value: value,
            input_type: target.type || "text",
            url: location.href,
          })
        );

        inputTimers.delete(target);
      }, 300)
    );
  }

  // Handle composition end (IME — Vietnamese Telex, Chinese, Japanese, etc.)
  function onCompositionEnd(e) {
    const target = e.target;
    if (!target) return;

    // Small delay to let the final value settle
    setTimeout(() => {
      const selector = getSelector(target);
      const value = target.value || "";

      window.__pw_record_action(
        JSON.stringify({
          type: "fill",
          timestamp: Date.now() / 1000,
          selector: selector,
          value: value,
          input_type: target.type || "text",
          url: location.href,
        })
      );
    }, 50);
  }

  // ── Keyboard Tracking (special keys only) ───────────────────

  // We only track special keys (Enter, Tab, Escape, etc.)
  // Regular character input is handled by the input/fill events above
  const SPECIAL_KEYS = new Set([
    "Enter",
    "Tab",
    "Escape",
    "Backspace",
    "Delete",
    "ArrowUp",
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "Home",
    "End",
    "PageUp",
    "PageDown",
    "F1", "F2", "F3", "F4", "F5", "F6",
    "F7", "F8", "F9", "F10", "F11", "F12",
  ]);

  function onKeyDown(e) {
    // Capture hotkey combos (Ctrl+A, Ctrl+C, etc.)
    if (e.ctrlKey || e.metaKey) {
      if (e.key.length === 1) {
        // Single letter combo: Ctrl+A, Ctrl+C, etc.
        window.__pw_record_action(
          JSON.stringify({
            type: "hotkey",
            timestamp: Date.now() / 1000,
            modifiers: [
              ...(e.ctrlKey ? ["Control"] : []),
              ...(e.metaKey ? ["Meta"] : []),
              ...(e.shiftKey ? ["Shift"] : []),
              ...(e.altKey ? ["Alt"] : []),
            ],
            key: e.key,
            url: location.href,
          })
        );
        return;
      }
    }

    // Capture special keys
    if (SPECIAL_KEYS.has(e.key)) {
      window.__pw_record_action(
        JSON.stringify({
          type: "keyboard",
          timestamp: Date.now() / 1000,
          key: e.key,
          url: location.href,
        })
      );
    }
  }

  // ── Select/Dropdown Tracking ────────────────────────────────

  function onChange(e) {
    const target = e.target;
    if (!target) return;
    if (target.tagName !== "SELECT") return;

    const selector = getSelector(target);
    window.__pw_record_action(
      JSON.stringify({
        type: "select",
        timestamp: Date.now() / 1000,
        selector: selector,
        value: target.value,
        text: target.options[target.selectedIndex]?.text || "",
        url: location.href,
      })
    );
  }

  // ── Attach All Listeners ────────────────────────────────────

  document.addEventListener("click", onClick, true);
  document.addEventListener("input", onInput, true);
  document.addEventListener("compositionend", onCompositionEnd, true);
  document.addEventListener("change", onChange, true);
  document.addEventListener("keydown", onKeyDown, true);
  window.addEventListener("wheel", onWheel, { passive: true, capture: true });

  // Navigation tracking (SPA)
  window.addEventListener("popstate", () => {
    window.__pw_record_action(
      JSON.stringify({
        type: "navigate",
        timestamp: Date.now() / 1000,
        url: location.href,
      })
    );
  });

  // Track hashchange for hash-based routing
  window.addEventListener("hashchange", () => {
    window.__pw_record_action(
      JSON.stringify({
        type: "navigate",
        timestamp: Date.now() / 1000,
        url: location.href,
      })
    );
  });

  console.log("[PW-Recorder] Injector active ✅");
})();
