import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from screen.capture import capture_screen
from screen.utils import latest_screenshot, load_session, list_sessions, delete_session, delete_all_sessions
from ocr.reader import read_text, read_with_boxes
from agent.parser import detect_actions
from agent.locator import find_login_button
from agent.tracker import analyze_session
from agent.replayer import replay


HELP_TEXT = """
╔══════════════════════════════════════════════════════════╗
║              AI Agent – Screen Recorder & Replayer       ║
╠══════════════════════════════════════════════════════════╣
║  RECORDING                                               ║
║    record [interval=1] [duration=60]                     ║
║      Ví dụ: python main.py record 1 60                   ║
║    record [interval] [duration] --window "Chrome"        ║
║      Ghi màn hình + click/scroll + ⌨️ bàn phím           ║
║                                                          ║
║  ANALYSIS                                                ║
║    analyze-session   YOLO + OCR phân tích session mới    ║
║                                                          ║
║  REPLAY                                                  ║
║    replay [url] [--speed 1.0] [--dry-run]                ║
║                                                          ║
║  QUẢN LÝ SESSION                                         ║
║    sessions                Liệt kê tất cả session        ║
║    clean <session_id>      Xóa 1 session                 ║
║    clean all               Xóa tất cả session            ║
║                                                          ║
║  UTILITIES                                               ║
║    ocr-latest / analyze / locate                         ║
╚══════════════════════════════════════════════════════════╝
"""


def main():
    if len(sys.argv) < 2:
        print(HELP_TEXT)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # record [interval] [duration] [--window "Title"]
    if cmd == "record":
        interval = 1
        duration = 60
        window_title = None

        positional = []
        i = 0
        while i < len(args):
            if args[i] == "--window" and i + 1 < len(args):
                window_title = args[i + 1]
                i += 2
            else:
                positional.append(args[i])
                i += 1

        if len(positional) >= 1:
            interval = int(positional[0])
        if len(positional) >= 2:
            duration = int(positional[1])

        print(f"▶️  Recording: interval={interval}s, duration={duration}s, window={window_title or 'any'}")
        log_path, session_id = capture_screen(
            interval=interval,
            duration=duration,
            window_title=window_title
        )
        print(f"\n💡 Tip: chạy lệnh tiếp theo để phân tích session này:")
        print(f"   python main.py analyze-session")

    # analyze-session

    elif cmd == "analyze-session":
        frames = load_session()
        if not frames:
            print("❌ Không tìm thấy session. Hãy chạy 'record' trước.")
            return
        print(f"📂 Loaded {len(frames)} frames")
        out = analyze_session(frames, output_dir="screenshots")
        if out:
            print(f"\n💡 Tip: replay thao tác với:")
            print(f"   python main.py replay")

    # replay [url] [--speed X] [--dry-run]
 
    elif cmd == "replay":
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

  
    # sessions – liệt kê session đã ghi
   
    elif cmd == "sessions":
        sessions = list_sessions()
        if not sessions:
            print("Chưa có session nào.")
            return
        print(f"{'SESSION ID':<15} {'📷':>5} {'🖱 CLICK':>8} {'↕ SCROLL':>8} {'⌨ KEYS':>7} {'SIZE':>7}  FOLDER")
        print("-" * 83)
        for s in sessions:
            keys = s.get('keys', 0)
            print(f"{s['session_id']:<15} {s['screenshots']:>5} {s['clicks']:>8} {s['scrolls']:>8} {keys:>7} {s['size_mb']:>6.1f}MB  {s['folder']}")


    # clean <session_id|all>
    elif cmd == "clean":
        if not args:
            print("❌ Dùng: python main.py clean <session_id>")
            print("         python main.py clean all")
            sessions = list_sessions()
            if sessions:
                print("\nCác session hiện có:")
                for s in sessions:
                    print(f"  {s['session_id']}  ({s['size_mb']}MB)  {s['folder']}")
            return

        target = args[0]
        if target == "all":
            confirm = input("⚠️  Xóa TẤT CẢ sessions? [y/N] ").strip().lower()
            if confirm == "y":
                delete_all_sessions()
            else:
                print("Hủy.")
        else:
            delete_session(session_id=target)

    # Legacy commands

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

    # Cũ: capture (giữ lại backward compat)
    elif cmd == "capture":
        interval = int(args[0]) if args else 2
        capture_screen(interval)

    else:
        print(f"❌ Unknown command: '{cmd}'")
        print(HELP_TEXT)


if __name__ == "__main__":
    main()
