"""
browser/replayer.py — Playwright Action Replay Engine

Reads session.json and replays all recorded actions using Playwright.
No YOLO/OCR/pyautogui needed — uses CSS selectors directly.
"""

import os
import json
import time

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from browser.utils import find_latest_session, load_session
from browser.profile import open_persistent_context, profile_path


# Default timeout for selector-based actions (ms)
ACTION_TIMEOUT = 30000


def replay_session(
    session_path: str = None,
    url: str = None,
    speed: float = 1.0,
    headless: bool = False,
    dry_run: bool = False,
    browser_type: str = "chromium",
    profile: str = None,
):
    """
    Replay a recorded session using Playwright.

    Args:
        session_path: Path to session.json (None = find latest)
        url:          Override start URL (None = use session's start_url)
        speed:        Replay speed multiplier (1.0 = original, 2.0 = 2x faster)
        headless:     Run browser in headless mode
        dry_run:      Print actions without executing
        browser_type: Browser engine: "chromium", "firefox", or "webkit"
        profile:      Persistent profile name to reuse a saved login session.
                      Defaults to the profile recorded in the session (if any).
    """
    if not dry_run and not HAS_PLAYWRIGHT:
        print("[replayer] ❌ playwright not installed.")
        print("   Run: pip install playwright && playwright install chromium")
        return

    # ── Load session ────────────────────────────────────────────
    if session_path is None:
        session_path = find_latest_session()
        if not session_path:
            print("[replayer] ❌ No session found. Run 'record' first.")
            return

    session = load_session(session_path)
    if not session:
        print(f"[replayer] ❌ Failed to load session: {session_path}")
        return

    actions = session.get("actions", [])
    if not actions:
        print("[replayer] ❌ Session has no actions.")
        return

    start_url = url or session.get("start_url")
    if not start_url:
        print("[replayer] ❌ No start URL found.")
        return

    viewport = session.get("viewport", {"width": 1920, "height": 1080})

    # Default to the profile the session was recorded with, unless overridden.
    if profile is None:
        profile = session.get("profile")
    use_profile = bool(profile)

    print(f"[replayer] {len(actions)} actions | "
          f"Mode: {'DRY RUN' if dry_run else 'LIVE'} | "
          f"Speed: {speed}x | Browser: {browser_type}"
          f"{f' | Profile: {profile}' if use_profile else ''}")
    print(f"🎯 Start URL: {start_url}")
    print("-" * 60)

    # ── Dry run: just print actions ─────────────────────────────
    if dry_run:
        _dry_run_report(actions, start_url)
        return

    # ── Live replay ─────────────────────────────────────────────
    with sync_playwright() as p:
        if use_profile:
            # Persistent context reuses a saved login session (already logged in).
            print(f"👤 Using profile: {profile_path(profile)}")
            browser = None
            context = open_persistent_context(
                p,
                profile,
                browser_type=browser_type,
                headless=headless,
                viewport=viewport,
            )
            page = context.pages[0] if context.pages else context.new_page()
        else:
            launcher = getattr(p, browser_type, p.chromium)
            browser = launcher.launch(headless=headless)
            context = browser.new_context(
                viewport=viewport,
                ignore_https_errors=True,
            )
            page = context.new_page()

        # Navigate to start URL
        print(f"\n🌐 Navigating to: {start_url}")
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"  ⚠️  Navigation warning: {e}")

        # Countdown
        print()
        for i in range(3, 0, -1):
            print(f"  ⏳ Replaying in {i}...", end="\r")
            time.sleep(1)
        print(f"\n▶️  Bắt đầu replay!\n")

        prev_timestamp = None
        success_count = 0
        fail_count = 0

        for i, action in enumerate(actions):
            action_type = action.get("type", "?")
            timestamp = action.get("timestamp", 0)

            # ── Delay between actions (respect original timing) ──
            if prev_timestamp and speed > 0:
                delay = (timestamp - prev_timestamp) / speed
                delay = max(0.05, min(delay, 10.0))
                time.sleep(delay)

            try:
                # ── CLICK ────────────────────────────────────────
                if action_type == "click":
                    selector = action.get("selector", "")
                    fallback = action.get("fallback_selector")
                    text = action.get("text", "")[:30]

                    print(f"  [{i+1:03d}] 🖱️  CLICK  → {selector}  "
                          f"{f'({text})' if text else ''}", end="")

                    try:
                        _click_with_fallback(page, selector, fallback)
                        print("  ✅")
                        success_count += 1
                    except Exception as e:
                        print(f"  ❌ {e}")
                        fail_count += 1

                # ── FILL ─────────────────────────────────────────
                elif action_type == "fill":
                    selector = action.get("selector", "")
                    value = action.get("value", "")
                    input_type = action.get("input_type", "text")
                    display_val = "***" if input_type == "password" else value[:20]

                    print(f"  [{i+1:03d}] ⌨️  FILL   → {selector} = '{display_val}'", end="")

                    try:
                        locator = page.locator(selector).first
                        locator.wait_for(state="visible", timeout=ACTION_TIMEOUT)
                        # Clear existing value first, then fill
                        locator.fill(value, timeout=ACTION_TIMEOUT)
                        print("  ✅")
                        success_count += 1
                    except Exception as e:
                        print(f"  ❌ {e}")
                        fail_count += 1

                # ── KEYBOARD (special keys) ──────────────────────
                elif action_type == "keyboard":
                    key = action.get("key", "")
                    print(f"  [{i+1:03d}] ⌨️  KEY    → {key}", end="")

                    try:
                        page.keyboard.press(key)
                        print("  ✅")
                        success_count += 1
                    except Exception as e:
                        print(f"  ❌ {e}")
                        fail_count += 1

                # ── PASTE (Ctrl+V captured with clipboard content) ───
                elif action_type == "paste":
                    value = action.get("value", "")
                    print(f"  [{i+1:03d}] 📋 PASTE  → '{value[:20]}'", end="")

                    try:
                        page.keyboard.type(value)
                        print("  ✅")
                        success_count += 1
                    except Exception as e:
                        print(f"  ❌ {e}")
                        fail_count += 1

                # ── HOTKEY (Ctrl+A, etc.) ────────────────────────
                elif action_type == "hotkey":
                    mods = action.get("modifiers", [])
                    key = action.get("key", "")
                    combo = "+".join(mods + [key])
                    print(f"  [{i+1:03d}] ⌨️  HOTKEY → {combo}", end="")

                    try:
                        # Build Playwright key combo string
                        pw_combo = "+".join(mods + [key])
                        page.keyboard.press(pw_combo)
                        print("  ✅")
                        success_count += 1
                    except Exception as e:
                        print(f"  ❌ {e}")
                        fail_count += 1

                # ── SCROLL ───────────────────────────────────────
                elif action_type == "scroll":
                    dx = action.get("deltaX", 0)
                    dy = action.get("deltaY", 0)
                    direction = "↑" if dy < 0 else "↓"
                    print(f"  [{i+1:03d}] 🖱️  SCROLL {direction} ({dy}px)", end="")

                    try:
                        page.mouse.wheel(dx, dy)
                        print("  ✅")
                        success_count += 1
                    except Exception as e:
                        print(f"  ❌ {e}")
                        fail_count += 1

                # ── SELECT (dropdown) ────────────────────────────
                elif action_type == "select":
                    selector = action.get("selector", "")
                    value = action.get("value", "")
                    text = action.get("text", "")
                    print(f"  [{i+1:03d}] 📋 SELECT → {selector} = '{text}'", end="")

                    try:
                        locator = page.locator(selector).first
                        try:
                            locator.select_option(value=value, timeout=ACTION_TIMEOUT)
                        except Exception:
                            if text:
                                locator.select_option(label=text, timeout=ACTION_TIMEOUT)
                            else:
                                raise
                        print("  ✅")
                        success_count += 1
                    except Exception as e:
                        print(f"  ❌ {e}")
                        fail_count += 1

                # ── NAVIGATE ─────────────────────────────────────
                elif action_type == "navigate":
                    nav_url = action.get("url", "")
                    print(f"  [{i+1:03d}] 🌐 NAV    → {nav_url[:60]}", end="")

                    try:
                        # Only navigate if we're not already on this URL
                        current_url = page.url
                        if _normalize_url(current_url) != _normalize_url(nav_url):
                            page.goto(nav_url, wait_until="domcontentloaded", timeout=30000)
                        print("  ✅")
                        success_count += 1
                    except Exception as e:
                        print(f"  ❌ {e}")
                        fail_count += 1

                else:
                    print(f"  [{i+1:03d}] ❓ UNKNOWN type: {action_type}")

            except Exception as e:
                print(f"  [{i+1:03d}] 💥 Unexpected error: {e}")
                fail_count += 1

            prev_timestamp = timestamp

        # ── Summary ─────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print(f"✅ Replay complete!")
        print(f"   Success: {success_count} | Failed: {fail_count} | "
              f"Total: {success_count + fail_count}")

        if fail_count > 0:
            print(f"   ⚠️  {fail_count} actions failed — selectors may have changed")

        # Keep browser open for a moment so user can see final state
        try:
            print(f"\n   Browser will close in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            pass

        if use_profile:
            context.close()
        else:
            browser.close()


def _click_with_fallback(page, selector: str, fallback_selector: str = None):
    """
    Try clicking with primary selector, fall back to secondary if it fails.
    """
    try:
        locator = page.locator(selector).first
        locator.wait_for(state="visible", timeout=ACTION_TIMEOUT)
        locator.click(timeout=ACTION_TIMEOUT)
    except Exception as primary_err:
        if fallback_selector:
            try:
                locator = page.locator(fallback_selector).first
                locator.wait_for(state="visible", timeout=5000)
                locator.click(timeout=5000)
                return  # Fallback succeeded
            except Exception:
                pass
        raise primary_err


def _normalize_url(url: str) -> str:
    """Normalize URL for comparison (strip protocol, query, trailing slash)."""
    if not url:
        return ""
    return url.split("?")[0].split("://")[-1].rstrip("/").lower()


def _dry_run_report(actions: list, start_url: str):
    """Print a dry-run report of all actions."""
    print(f"\n🌐 [DRY] Would navigate to: {start_url}\n")

    for i, action in enumerate(actions):
        action_type = action.get("type", "?")

        if action_type == "click":
            selector = action.get("selector", "?")
            text = action.get("text", "")[:30]
            print(f"  [{i+1:03d}] 🖱️  CLICK  → {selector}  {f'({text})' if text else ''}")

        elif action_type == "fill":
            selector = action.get("selector", "?")
            value = action.get("value", "")[:20]
            input_type = action.get("input_type", "text")
            display_val = "***" if input_type == "password" else value
            print(f"  [{i+1:03d}] ⌨️  FILL   → {selector} = '{display_val}'")

        elif action_type == "keyboard":
            key = action.get("key", "?")
            print(f"  [{i+1:03d}] ⌨️  KEY    → {key}")

        elif action_type == "hotkey":
            mods = action.get("modifiers", [])
            key = action.get("key", "?")
            combo = "+".join(mods + [key])
            print(f"  [{i+1:03d}] ⌨️  HOTKEY → {combo}")

        elif action_type == "scroll":
            dy = action.get("deltaY", 0)
            direction = "↑" if dy < 0 else "↓"
            print(f"  [{i+1:03d}] 🖱️  SCROLL {direction} ({dy}px)")

        elif action_type == "select":
            selector = action.get("selector", "?")
            text = action.get("text", "?")
            print(f"  [{i+1:03d}] 📋 SELECT → {selector} = '{text}'")

        elif action_type == "navigate":
            nav_url = action.get("url", "?")
            print(f"  [{i+1:03d}] 🌐 NAV    → {nav_url[:60]}")

    print(f"\n📊 Total: {len(actions)} actions (dry run — nothing executed)")
