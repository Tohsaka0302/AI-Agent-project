"""
Quick smoke test: Record a few actions on example.com, then dry-run replay.
"""
import sys
import os
import io
import json
import time

# Fix Windows console encoding for emoji output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright

# Path setup
INJECTOR_JS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "injector.js")
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
TEST_SESSION_DIR = os.path.join(SESSIONS_DIR, "session_test")

def main():
    print("=" * 60)
    print("  SMOKE TEST: Playwright Record + Replay Pipeline")
    print("=" * 60)

    # 1. Test browser launch + injector
    print("\n[1/4] Testing browser launch + injector injection...")
    with open(INJECTOR_JS_PATH, "r", encoding="utf-8") as f:
        injector_js = f.read()
    print(f"  ✅ Injector loaded ({len(injector_js)} chars)")

    actions = []

    def handle_action(action_json):
        action = json.loads(action_json)
        actions.append(action)
        print(f"  📥 Captured: {action['type']} → {action.get('selector', action.get('key', ''))[:50]}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        # Expose callback
        page.expose_function("__pw_record_action", handle_action)

        # Add init script for future navigations
        context.add_init_script(injector_js)

        # Navigate
        print("\n[2/4] Navigating to https://example.com...")
        page.goto("https://example.com", wait_until="domcontentloaded")

        # Inject for current page
        page.evaluate(injector_js)
        print(f"  ✅ Page loaded: {page.url}")
        print(f"  ✅ Title: {page.title()}")

        # Simulate a click via JavaScript (since headless can't have real user input)
        print("\n[3/4] Simulating user actions via DOM...")

        # Click test: dispatch on a non-navigating element (the heading)
        try:
            page.evaluate("""
                const h1 = document.querySelector('h1');
                if (h1) {
                    h1.dispatchEvent(new MouseEvent('click', {
                        bubbles: true, cancelable: true, clientX: 100, clientY: 50
                    }));
                }
            """)
            time.sleep(0.3)
            print("  - Click dispatched on h1")
        except Exception as e:
            print(f"  - Click dispatch error: {e}")

        # Click test 2: dispatch on the <a> link but preventDefault to avoid navigation
        try:
            page.evaluate("""
                const link = document.querySelector('a');
                if (link) {
                    // Temporarily prevent navigation
                    const handler = (e) => e.preventDefault();
                    link.addEventListener('click', handler, {once: true});
                    link.dispatchEvent(new MouseEvent('click', {
                        bubbles: true, cancelable: true, clientX: 200, clientY: 300
                    }));
                }
            """)
            time.sleep(0.3)
            print("  - Click dispatched on link (no navigation)")
        except Exception as e:
            print(f"  - Link click error: {e}")

        # Simulate scroll
        try:
            page.evaluate("""
                window.dispatchEvent(new WheelEvent('wheel', {
                    deltaX: 0, deltaY: 300, bubbles: true
                }));
            """)
            time.sleep(0.6)  # Wait for scroll debounce
            print("  - Scroll dispatched")
        except Exception as e:
            print(f"  - Scroll error: {e}")

        # Simulate keyboard (use Playwright's built-in keyboard API)
        try:
            page.keyboard.press("Tab")
            time.sleep(0.2)
            print("  - Tab key pressed")
        except Exception as e:
            print(f"  - Keyboard error: {e}")

        browser.close()

    print(f"\n  📊 Total captured actions: {len(actions)}")
    for a in actions:
        print(f"    - {a['type']}: {json.dumps({k: v for k, v in a.items() if k != 'timestamp'}, ensure_ascii=False)[:80]}")

    # 4. Test replayer dry run
    print("\n[4/4] Testing replayer dry-run...")
    if actions:
        # Save a test session
        os.makedirs(TEST_SESSION_DIR, exist_ok=True)
        session_data = {
            "version": 2,
            "engine": "playwright",
            "browser": "chromium",
            "start_url": "https://example.com",
            "viewport": {"width": 1280, "height": 720},
            "actions": actions,
        }
        session_path = os.path.join(TEST_SESSION_DIR, "session.json")
        with open(session_path, "w") as f:
            json.dump(session_data, f, indent=2)
        print(f"  ✅ Test session saved: {session_path}")

        # Import and dry-run replay
        from browser.replayer import replay_session
        replay_session(session_path=session_path, dry_run=True)
    else:
        print("  ⚠️  No actions captured — injector may not have fired")
        print("  (This can happen in headless mode with synthetic events)")

    # Cleanup test session
    import shutil
    if os.path.exists(TEST_SESSION_DIR):
        shutil.rmtree(TEST_SESSION_DIR)
        print(f"\n  🗑️  Cleaned up test session")

    print("\n" + "=" * 60)
    print("  SMOKE TEST COMPLETE ✅")
    print("=" * 60)


if __name__ == "__main__":
    main()
