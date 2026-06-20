"""
browser/recorder.py — Playwright CDP-based Recording Engine

Two modes:
  1. LAUNCH mode (default): Opens a new browser controlled by Playwright.
  2. CONNECT mode (--connect): Connects to an existing Chrome/Edge via CDP
     (Chrome DevTools Protocol). User must start Chrome with:
       chrome.exe --remote-debugging-port=9222
     This preserves cookies, extensions, and logged-in sessions.

Both modes inject DOM event listeners and capture user actions
with CSS selectors in real-time. No YOLO/OCR needed.
"""

import os
import sys
import json
import time
import threading
from datetime import datetime, timezone

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("[WARN] playwright not installed. Run: pip install playwright && playwright install chromium")


# Path to injector script
INJECTOR_JS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "injector.js")

# Sessions base directory
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sessions")

# Default CDP endpoint for --connect mode
DEFAULT_CDP_ENDPOINT = "http://localhost:9222"


def _load_injector_js() -> str:
    """Load the DOM event capture script."""
    with open(INJECTOR_JS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def record_session(
    url: str,
    duration: int = 120,
    browser_type: str = "chromium",
    take_screenshots: bool = True,
    enable_tracing: bool = False,
    connect_cdp: str = None,
):
    """
    Record user actions on a browser page using Playwright.

    Two modes:
      - Launch mode (default): Opens a new browser.
      - Connect mode (connect_cdp): Connects to an existing Chrome via CDP.
        User must start Chrome with: chrome.exe --remote-debugging-port=9222

    Args:
        url:               Starting URL to navigate to
        duration:          Max recording duration in seconds (0 = no limit)
        browser_type:      Browser engine: "chromium", "firefox", or "webkit"
        take_screenshots:  Capture a screenshot after each click event
        enable_tracing:    Enable Playwright tracing (generates trace.zip)
        connect_cdp:       CDP endpoint URL (e.g. "http://localhost:9222").
                           If set, connects to existing browser instead of launching.

    Returns:
        Tuple of (session_dir, session_id) or (None, None) on failure
    """
    if not HAS_PLAYWRIGHT:
        print("[recorder] ❌ playwright not installed.")
        print("   Run: pip install playwright && playwright install chromium")
        return None, None

    # Create session directory
    session_id = int(time.time())
    session_dir = os.path.join(SESSIONS_DIR, f"session_{session_id}")
    os.makedirs(session_dir, exist_ok=True)
    screenshots_dir = os.path.join(session_dir, "screenshots")
    if take_screenshots:
        os.makedirs(screenshots_dir, exist_ok=True)

    is_connect_mode = connect_cdp is not None

    print(f"📁 Session folder: {session_dir}")
    print(f"🌐 Start URL: {url}")
    print(f"🕐 Max duration: {duration}s {'(unlimited)' if duration <= 0 else ''}")
    if is_connect_mode:
        print(f"🔗 Mode: CONNECT (CDP → {connect_cdp})")
    else:
        print(f"🖥️  Mode: LAUNCH ({browser_type})")
    print()

    # Countdown
    for i in range(3, 0, -1):
        print(f"  ⏳ Launching browser in {i}...", end="\r")
        time.sleep(1)
    print("  🔴 Recording!                 ")
    print()

    actions = []
    action_lock = threading.Lock()
    screenshot_counter = [0]
    injector_js = _load_injector_js()

    # Track last known URL (for navigation detection)
    last_url = [url]

    def handle_action(action_json: str):
        """Callback from injected JS — receives action data as JSON string."""
        try:
            action = json.loads(action_json)
        except json.JSONDecodeError:
            return

        with action_lock:
            actions.append(action)

        action_type = action.get("type", "?")
        action_url = action.get("url", "")

        # Auto-detect navigation by URL change
        if action_url and action_url != last_url[0]:
            # Check if this isn't already a navigate event
            if action_type != "navigate":
                with action_lock:
                    actions.append({
                        "type": "navigate",
                        "timestamp": action["timestamp"],
                        "url": action_url,
                        "previous_url": last_url[0],
                    })
            last_url[0] = action_url

        # Print action to console
        if action_type == "click":
            selector = action.get("selector", "?")
            text = action.get("text", "")[:30]
            print(f"  🖱️  CLICK  → {selector}  {f'({text})' if text else ''}")
        elif action_type == "fill":
            selector = action.get("selector", "?")
            value = action.get("value", "")[:20]
            masked = "***" if action.get("input_type") == "password" else value
            print(f"  ⌨️  FILL   → {selector} = '{masked}'")
        elif action_type == "keyboard":
            key = action.get("key", "?")
            print(f"  ⌨️  KEY    → {key}")
        elif action_type == "hotkey":
            mods = action.get("modifiers", [])
            key = action.get("key", "?")
            combo = "+".join(mods + [key])
            print(f"  ⌨️  HOTKEY → {combo}")
        elif action_type == "scroll":
            dy = action.get("deltaY", 0)
            print(f"  🖱️  SCROLL {'↑' if dy < 0 else '↓'} ({dy}px)")
        elif action_type == "select":
            selector = action.get("selector", "?")
            text = action.get("text", "?")
            print(f"  📋 SELECT  → {selector} = '{text}'")
        elif action_type == "navigate":
            print(f"  🌐 NAV     → {action_url[:60]}")

    with sync_playwright() as p:
        # ── Connect or Launch ───────────────────────────────────
        if is_connect_mode:
            try:
                browser = p.chromium.connect_over_cdp(connect_cdp)
                print(f"  🔗 Connected to existing browser at {connect_cdp}")
            except Exception as e:
                print(f"  ❌ Cannot connect to browser at {connect_cdp}")
                print(f"     Error: {e}")
                print(f"")
                print(f"  💡 Make sure Chrome/Edge is running with:")
                print(f"     chrome.exe --remote-debugging-port=9222")
                print(f"     (Close ALL Chrome windows first, then run this command)")
                return None, None

            # Use the first existing context, or default context
            contexts = browser.contexts
            if contexts:
                context = contexts[0]
            else:
                context = browser.new_context()
        else:
            # Launch mode (original behavior)
            launcher = getattr(p, browser_type, p.chromium)
            browser = launcher.launch(headless=False)

            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
            )

        # Optional: Playwright tracing
        if enable_tracing:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)

        # ── Get or create page ──────────────────────────────────
        if is_connect_mode:
            # Use existing page or create new tab
            pages = context.pages
            if pages:
                page = pages[0]  # Use first existing tab
                current_url = page.url
                print(f"  📄 Using existing tab: {current_url[:60]}")
            else:
                page = context.new_page()
        else:
            page = context.new_page()

        # Expose callback function to JavaScript
        try:
            page.expose_function("__pw_record_action", handle_action)
        except Exception as e:
            # In connect mode, expose_function may fail if already exposed
            if not is_connect_mode:
                raise e

        # Inject the DOM event capture script on every page load
        # (handles SPA navigation and page reloads)
        try:
            context.add_init_script(injector_js)
        except Exception:
            # In connect mode, add_init_script may not work on existing contexts
            pass

        # Navigate to start URL (or re-inject if already on page)
        if is_connect_mode:
            # In connect mode, navigate to URL if not already there
            current_url = page.url
            target_norm = url.split("?")[0].split("://")[-1].rstrip("/").lower()
            current_norm = current_url.split("?")[0].split("://")[-1].rstrip("/").lower()
            if target_norm != current_norm:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                except Exception as e:
                    print(f"  ⚠️  Navigation warning: {e}")
            # Inject for the current page
            try:
                page.evaluate(injector_js)
            except Exception:
                pass
        else:
            # Launch mode: navigate then inject
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"  ⚠️  Navigation warning: {e}")
            # Re-inject for the initial page
            try:
                page.evaluate(injector_js)
            except Exception:
                pass

        # Handle new pages (popups, new tabs)
        def on_new_page(new_page):
            try:
                new_page.expose_function("__pw_record_action", handle_action)
            except Exception:
                pass

        context.on("page", on_new_page)

        # Screenshot helper
        def take_click_screenshot(page_ref, action_data):
            if not take_screenshots:
                return
            try:
                idx = screenshot_counter[0]
                screenshot_counter[0] += 1
                filename = f"{idx:04d}_click.png"
                filepath = os.path.join(screenshots_dir, filename)
                page_ref.screenshot(path=filepath)
                action_data["screenshot"] = f"screenshots/{filename}"
            except Exception:
                pass

        if is_connect_mode:
            print(f"  ✅ Connected! Recording your actions in real-time.")
            print(f"  📋 Interact with the page normally (your own browser!).")
            print(f"  🛑 Press Ctrl+C to stop recording.\n")
        else:
            print(f"  ✅ Browser launched. Interact with the page normally.")
            print(f"  📋 Actions are being recorded in real-time.")
            print(f"  🛑 Close the browser window or press Ctrl+C to stop.\n")

        # Wait for recording to complete
        deadline = time.time() + duration if duration > 0 else float("inf")
        try:
            while time.time() < deadline:
                # Check if browser/page is still open
                try:
                    if page.is_closed():
                        print("\n🛑 Page closed by user.")
                        break
                    # Ping the browser to check if it's still alive
                    page.evaluate("1")
                except Exception:
                    print("\n🛑 Browser closed by user.")
                    break

                # Take screenshots for click events that don't have one yet
                with action_lock:
                    for action in actions:
                        if (action.get("type") == "click"
                                and "screenshot" not in action
                                and take_screenshots):
                            take_click_screenshot(page, action)

                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n🛑 Stopped by user (Ctrl+C).")

        # Save tracing if enabled
        if enable_tracing:
            trace_path = os.path.join(session_dir, "trace.zip")
            try:
                context.tracing.stop(path=trace_path)
                print(f"  📦 Trace saved: {trace_path}")
            except Exception:
                pass

        # Close browser (only if we launched it — don't close user's browser!)
        if not is_connect_mode:
            try:
                browser.close()
            except Exception:
                pass
        else:
            print("  📌 Browser left open (connect mode — your browser stays running).")

    # ── Save session ────────────────────────────────────────────

    # De-duplicate consecutive fill events for the same selector (keep last)
    actions = _dedupe_fills(actions)

    # Build session data
    session_data = {
        "version": 2,
        "engine": "playwright",
        "mode": "connect" if is_connect_mode else "launch",
        "browser": browser_type,
        "start_url": url,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "viewport": {"width": 1920, "height": 1080},
        "actions": actions,
    }

    session_path = os.path.join(session_dir, "session.json")
    with open(session_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)

    # Stats
    clicks = sum(1 for a in actions if a["type"] == "click")
    fills = sum(1 for a in actions if a["type"] == "fill")
    keys = sum(1 for a in actions if a["type"] in ("keyboard", "hotkey"))
    scrolls = sum(1 for a in actions if a["type"] == "scroll")
    navs = sum(1 for a in actions if a["type"] == "navigate")

    print(f"\n💾 Session saved: {session_path}")
    print(f"📊 Actions: {len(actions)} total | "
          f"{clicks} clicks | {fills} fills | {keys} keys | "
          f"{scrolls} scrolls | {navs} navigations")
    print(f"🗑️  Để xóa: python main.py clean {session_id}")

    return session_dir, session_id


def _dedupe_fills(actions: list) -> list:
    """
    De-duplicate consecutive fill events for the same selector.
    Keep only the last fill value (represents the final input).
    """
    if not actions:
        return actions

    result = []
    i = 0
    while i < len(actions):
        action = actions[i]

        if action.get("type") == "fill":
            # Look ahead: if the next action is also a fill for the same selector, skip this one
            selector = action.get("selector")
            j = i + 1
            while (j < len(actions)
                   and actions[j].get("type") == "fill"
                   and actions[j].get("selector") == selector):
                j += 1
            # Keep only the last fill for this selector
            result.append(actions[j - 1])
            i = j
        else:
            result.append(action)
            i += 1

    n_deduped = len(actions) - len(result)
    if n_deduped > 0:
        print(f"  [DEDUP] Collapsed {n_deduped} intermediate fill events")
    return result
