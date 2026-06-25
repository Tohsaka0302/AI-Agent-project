import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ── New Playwright engine ───────────────────────────────────────
from browser.recorder import record_session, login_session
from browser.replayer import replay_session
from browser.utils import (
    list_sessions as list_pw_sessions,
    delete_session as delete_pw_session,
    delete_all_sessions as delete_all_pw_sessions,
)
from browser.profile import list_profiles, delete_profile

# ── Legacy OS-level engine (deprecated) ─────────────────────────
from screen.capture import capture_screen
from screen.utils import latest_screenshot, load_session, list_sessions, delete_session, delete_all_sessions
from ocr.reader import read_text, read_with_boxes
from agent.parser import detect_actions
from agent.locator import find_login_button
from agent.tracker import analyze_session
from agent.replayer import replay


HELP_TEXT = """
╔═══════════════════════════════════════════════════════════════════╗
║          AI Agent – Playwright Web Recorder & Replayer           ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  🚀 PLAYWRIGHT ENGINE                                             ║
║  ──────────────────────────────────────────────────────────────── ║
║  login [--profile misa] [--url <login_url>]                       ║
║    Log in ONCE by hand; saves session to a reusable profile       ║
║    Ví dụ: python main.py login --profile misa                     ║
║                                                                   ║
║  record <url> [duration] [--connect] [--profile name] [--browser type] ║
║    Opens browser, records actions with CSS selectors              ║
║    --connect  Record on YOUR OWN Chrome (needs debug port)        ║
║    --profile  Reuse a saved login session (see `login`)           ║
║                                                                   ║
║    Ví dụ: python main.py record https://example.com 120           ║
║    Ví dụ: python main.py record https://amisapp.misa.vn --profile misa ║
║                                                                   ║
║  replay [--speed 1.0] [--headless] [--dry-run] [--profile name]   ║
║    Replays latest session using Playwright                        ║
║    Ví dụ: python main.py replay --speed 2.0 --dry-run             ║
║                                                                   ║
║  sessions          List all recorded sessions                     ║
║  profiles          List saved login profiles                      ║
║  clean <id|all>    Delete session(s)                              ║
║  clean-profile <name|all>   Delete login profile(s)               ║
║                                                                   ║
║  🔧 LEGACY ENGINE (deprecated, OS-level)                          ║
║  ──────────────────────────────────────────────────────────────── ║
║  record-legacy [duration] [--periodic] [--window "T"]             ║
║  analyze-session    YOLO + OCR analysis                           ║
║  replay-legacy [url] [--speed] [--dry-run]                        ║
║  ocr-latest / analyze / locate                                    ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
"""


def main():
    if len(sys.argv) < 2:
        print(HELP_TEXT)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # ════════════════════════════════════════════════════════════
    #  NEW PLAYWRIGHT COMMANDS
    # ════════════════════════════════════════════════════════════

    # login [--profile name] [--url login_url] [--browser type]
    if cmd == "login":
        profile = "misa"
        login_url = None
        browser_type = "chromium"

        i = 0
        while i < len(args):
            if args[i] == "--profile" and i + 1 < len(args):
                profile = args[i + 1]
                i += 2
            elif args[i] == "--url" and i + 1 < len(args):
                login_url = args[i + 1]
                i += 2
            elif args[i] == "--browser" and i + 1 < len(args):
                browser_type = args[i + 1]
                i += 2
            elif args[i].startswith("http"):
                login_url = args[i]
                i += 1
            else:
                i += 1

        login_session(profile=profile, url=login_url, browser_type=browser_type)
        return

    # record <url> [duration] [--connect] [--profile name] [--browser type]
    if cmd == "record":
        if not args or not args[0].startswith("http"):
            print("❌ Usage: python main.py record <url> [duration] [--connect] [--browser type]")
            print("")
            print("   Launch mode (default):")
            print("     python main.py record https://example.com 120")
            print("")
            print("   Connect mode (your own browser):")
            print("     1. Start Chrome: chrome.exe --remote-debugging-port=9222")
            print("     2. python main.py record https://facebook.com --connect")
            return

        url = args[0]
        duration = 120
        browser_type = "chromium"
        screenshots = True
        tracing = False
        connect_cdp = None
        profile = None

        i = 1
        while i < len(args):
            if args[i] == "--browser" and i + 1 < len(args):
                browser_type = args[i + 1]
                i += 2
            elif args[i] == "--profile" and i + 1 < len(args):
                profile = args[i + 1]
                i += 2
            elif args[i] == "--connect":
                connect_cdp = "http://localhost:9222"
                i += 1
            elif args[i].startswith("--connect="):
                connect_cdp = args[i].split("=", 1)[1]
                i += 1
            elif args[i] == "--no-screenshots":
                screenshots = False
                i += 1
            elif args[i] == "--trace":
                tracing = True
                i += 1
            elif args[i].isdigit():
                duration = int(args[i])
                i += 1
            else:
                i += 1

        if connect_cdp:
            mode_str = f"CONNECT ({connect_cdp})"
        elif profile:
            mode_str = f"PROFILE ({profile})"
        else:
            mode_str = f"LAUNCH ({browser_type})"
        print(f"▶️  Recording: url={url}, duration={duration}s, mode={mode_str}")
        result = record_session(
            url=url,
            duration=duration,
            browser_type=browser_type,
            take_screenshots=screenshots,
            enable_tracing=tracing,
            connect_cdp=connect_cdp,
            profile=profile,
        )
        if result and result[0]:
            print(f"\n💡 Tip: replay this session:")
            print(f"   python main.py replay{f' --profile {profile}' if profile else ''}")

    # replay [--speed X] [--headless] [--dry-run] [--browser type]
    elif cmd == "replay":
        speed = 1.0
        headless = False
        dry_run = False
        browser_type = "chromium"
        profile = None

        i = 0
        while i < len(args):
            if args[i] == "--dry-run":
                dry_run = True
            elif args[i] == "--headless":
                headless = True
            elif args[i] == "--speed" and i + 1 < len(args):
                speed = float(args[i + 1])
                i += 1
            elif args[i] == "--browser" and i + 1 < len(args):
                browser_type = args[i + 1]
                i += 1
            elif args[i] == "--profile" and i + 1 < len(args):
                profile = args[i + 1]
                i += 1
            i += 1

        replay_session(
            speed=speed,
            headless=headless,
            dry_run=dry_run,
            browser_type=browser_type,
            profile=profile,
        )

    # sessions – list all sessions (both new and legacy)
    elif cmd == "sessions":
        # New Playwright sessions
        pw_sessions = list_pw_sessions()
        # Legacy sessions
        legacy_sessions = list_sessions()

        if not pw_sessions and not legacy_sessions:
            print("Chưa có session nào.")
            return

        if pw_sessions:
            print(f"\n🚀 Playwright Sessions ({len(pw_sessions)}):")
            print(f"  {'SESSION ID':<15} {'ACTIONS':>8} {'🖱 CLICK':>8} {'⌨ FILL':>6} {'🔑 KEY':>6} {'↕ SCROLL':>8} {'SIZE':>7}  URL")
            print("  " + "-" * 95)
            for s in pw_sessions:
                url_short = s['start_url'][:35] if s.get('start_url') else ''
                print(f"  {s['session_id']:<15} {s['total_actions']:>8} {s['clicks']:>8} "
                      f"{s['fills']:>6} {s['keys']:>6} {s['scrolls']:>8} "
                      f"{s['size_mb']:>6.1f}MB  {url_short}")

        if legacy_sessions:
            print(f"\n🔧 Legacy Sessions ({len(legacy_sessions)}):")
            print(f"  {'SESSION ID':<15} {'📷':>5} {'🖱 CLICK':>8} {'↕ SCROLL':>8} {'⌨ KEYS':>7} {'SIZE':>7}  FOLDER")
            print("  " + "-" * 83)
            for s in legacy_sessions:
                keys = s.get('keys', 0)
                print(f"  {s['session_id']:<15} {s['screenshots']:>5} {s['clicks']:>8} "
                      f"{s['scrolls']:>8} {keys:>7} {s['size_mb']:>6.1f}MB  {s['folder']}")

    # profiles – list saved login profiles
    elif cmd == "profiles":
        profiles = list_profiles()
        if not profiles:
            print("Chưa có profile nào. Tạo bằng: python main.py login --profile misa")
            return
        print(f"\n👤 Login Profiles ({len(profiles)}):")
        for name in profiles:
            print(f"  • {name}")

    # clean-profile <name|all>
    elif cmd == "clean-profile":
        if not args:
            print("❌ Usage: python main.py clean-profile <name>")
            print("         python main.py clean-profile all")
            profiles = list_profiles()
            if profiles:
                print("\n👤 Profiles:")
                for name in profiles:
                    print(f"  • {name}")
            return
        target = args[0]
        if target == "all":
            confirm = input("⚠️  Xóa TẤT CẢ login profiles? [y/N] ").strip().lower()
            if confirm == "y":
                for name in list_profiles():
                    delete_profile(name)
            else:
                print("Hủy.")
        else:
            delete_profile(target)

    # clean <session_id|all>
    elif cmd == "clean":
        if not args:
            print("❌ Usage: python main.py clean <session_id>")
            print("         python main.py clean all")
            # Show existing sessions
            pw_sessions = list_pw_sessions()
            legacy_sessions = list_sessions()
            if pw_sessions:
                print("\n🚀 Playwright sessions:")
                for s in pw_sessions:
                    print(f"  {s['session_id']}  ({s['size_mb']}MB)  {s['folder']}")
            if legacy_sessions:
                print("\n🔧 Legacy sessions:")
                for s in legacy_sessions:
                    print(f"  {s['session_id']}  ({s['size_mb']}MB)  {s['folder']}")
            return

        target = args[0]
        if target == "all":
            confirm = input("⚠️  Xóa TẤT CẢ sessions (Playwright + Legacy)? [y/N] ").strip().lower()
            if confirm == "y":
                delete_all_pw_sessions()
                delete_all_sessions()
            else:
                print("Hủy.")
        else:
            # Try Playwright session first, then legacy
            pw_deleted = delete_pw_session(session_id=target)
            if not pw_deleted:
                delete_session(session_id=target)

    # ════════════════════════════════════════════════════════════
    #  LEGACY COMMANDS (deprecated)
    # ════════════════════════════════════════════════════════════

    # record-legacy [interval] [duration] [--window "Title"] [--periodic]
    elif cmd == "record-legacy":
        interval = 1
        duration = 60
        window_title = None
        periodic = False

        positional = []
        i = 0
        while i < len(args):
            if args[i] == "--window" and i + 1 < len(args):
                window_title = args[i + 1]
                i += 2
            elif args[i] == "--periodic":
                periodic = True
                i += 1
            else:
                positional.append(args[i])
                i += 1

        if len(positional) >= 1:
            interval = int(positional[0])
        if len(positional) >= 2:
            duration = int(positional[1])

        mode_str = "EVENT-DRIVEN" + (" + PERIODIC" if periodic else "")
        print(f"▶️  [LEGACY] Recording: mode={mode_str}, duration={duration}s, window={window_title or 'any'}")
        log_path, session_id = capture_screen(
            interval=interval,
            duration=duration,
            window_title=window_title,
            periodic=periodic,
        )
        print(f"\n💡 Tip: analyze then replay:")
        print(f"   python main.py analyze-session")
        print(f"   python main.py replay-legacy")

    # analyze-session (legacy)
    elif cmd == "analyze-session":
        frames = load_session()
        if not frames:
            print("❌ Không tìm thấy session. Hãy chạy 'record-legacy' trước.")
            return
        print(f"📂 Loaded {len(frames)} frames")
        out = analyze_session(frames, output_dir="screenshots")
        if out:
            print(f"\n💡 Tip: replay thao tác với:")
            print(f"   python main.py replay-legacy")

    # replay-legacy [url] [--speed X] [--dry-run]
    elif cmd == "replay-legacy":
        url = None
        speed = 1.0
        dry_run = False

        i = 0
        while i < len(args):
            if args[i] == "--dry-run":
                dry_run = True
            elif args[i] == "--speed" and i + 1 < len(args):
                speed = float(args[i + 1])
                i += 1
            elif args[i].startswith("http"):
                url = args[i]
            i += 1

        replay(url=url, dry_run=dry_run, speed=speed)

    # Legacy utility commands
    elif cmd == "ocr-latest":
        img = latest_screenshot()
        print("Latest image:", img)
        text = read_text(img)
        print("===== OCR RESULT =====")
        print(text)
        actions = detect_actions(text)
        print("===== DETECTED ACTIONS =====")
        for k, v in actions.items():
            print(f"  {k}: {v}")

    elif cmd == "analyze":
        img = latest_screenshot()
        print("Analyzing:", img)
        text = read_text(img)
        print("===== OCR TEXT =====")
        print(text)
        actions = detect_actions(text)
        print("===== DETECTED ACTIONS =====")
        for k, v in actions.items():
            print(f"  {k}: {v}")

    elif cmd == "locate":
        img = latest_screenshot()
        print("Image:", img)
        boxes = read_with_boxes(img)
        login_box = find_login_button(boxes)
        if login_box:
            print("LOGIN FOUND AT:")
            print(login_box)
            cx = login_box["x"] + login_box["w"] // 2
            cy = login_box["y"] + login_box["h"] // 2
            print("CENTER:", cx, cy)
        else:
            print("Login not found")

    # Backward compat: old 'capture' command
    elif cmd == "capture":
        interval = int(args[0]) if args else 2
        capture_screen(interval)

    else:
        print(f"❌ Unknown command: '{cmd}'")
        print(HELP_TEXT)


if __name__ == "__main__":
    main()
