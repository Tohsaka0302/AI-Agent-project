"""
screen/capture.py – mỗi session lưu vào subfolder screenshots/session_<id>/
"""

from PIL import ImageGrab
import pyautogui
import time
import os
import json
import threading

from pynput import mouse as pynput_mouse
from pynput import keyboard as pynput_keyboard

try:
    import pygetwindow as gw
    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False


def capture_screen(interval: int = 1, duration: int = 60, window_title: str = None):
    """
    Ghi session: chụp màn hình định kỳ + bắt click/scroll real-time.
    Mỗi session lưu vào thư mục con riêng: screenshots/session_<id>/
    """
    project_root = os.path.abspath(os.path.join(__file__, "../../"))
    base_dir = os.path.join(project_root, "screenshots")

    session_id = int(time.time())
    session_dir = os.path.join(base_dir, f"session_{session_id}")
    os.makedirs(session_dir, exist_ok=True)
    print(f"📁 Session folder: {session_dir}")

    log_path = os.path.join(session_dir, "mouse.json")
    keyboard_log_path = os.path.join(session_dir, "keyboard.json")

    event_log = []
    frame_counter = [0]
    stop_event = threading.Event()
    lock = threading.Lock()
    deadline = time.time() + duration

    print(f"\n📸 Ghi mỗi {interval}s trong {duration}s | Click/Scroll: real-time")
    if window_title:
        print(f"   Chỉ ghi khi '{window_title}' đang active")
    print("Press CTRL+C để dừng sớm\n")

    for i in range(3, 0, -1):
        print(f"  ⏳ Bắt đầu sau {i} giây...", end="\r")
        time.sleep(1)
    print("  🔴 Đang ghi!                \n")

    # ── Thread 1: Screenshot định kỳ ────────────────────────────
    def screenshot_loop():
        while not stop_event.is_set():
            if time.time() >= deadline:
                stop_event.set()
                break
            if window_title and HAS_PYGETWINDOW:
                active = gw.getActiveWindow()
                if active is None or window_title.lower() not in active.title.lower():
                    time.sleep(0.3)
                    continue

            idx = frame_counter[0]
            frame_counter[0] += 1
            filename = f"screenshot_{idx:04d}.png"
            filepath = os.path.join(session_dir, filename)

            img = ImageGrab.grab()
            img.save(filepath)

            mx, my = pyautogui.position()
            with lock:
                event_log.append({
                    "type": "screenshot",
                    "frame": idx,
                    "timestamp": time.time(),
                    "screenshot": filename,
                    "mouse_x": mx,
                    "mouse_y": my,
                })
            print(f"  📷 [{idx:03d}] ({mx:4d},{my:4d})  {filename}")
            time.sleep(interval)

    # ── Thread 2: pynput mouse listener ─────────────────────────
    def on_click(x, y, button, pressed):
        if stop_event.is_set():
            return False
        if pressed:
            with lock:
                event_log.append({
                    "type": "click",
                    "timestamp": time.time(),
                    "mouse_x": x, "mouse_y": y,
                    "button": str(button),
                })
            print(f"  🖱️  CLICK ({x:4d},{y:4d})")

    def on_scroll(x, y, dx, dy):
        if stop_event.is_set():
            return False
        with lock:
            event_log.append({
                "type": "scroll",
                "timestamp": time.time(),
                "mouse_x": x, "mouse_y": y,
                "dx": dx, "dy": dy,
            })
        print(f"  🖱️  SCROLL {'↑' if dy > 0 else '↓'} ({x:4d},{y:4d})")

    # ── Thread 3: pynput keyboard listener ───────────────────────
    def _key_str(key):
        """Convert a pynput Key to a loggable string."""
        try:
            # Printable character (e.g. 'a', '1', '@')
            return key.char
        except AttributeError:
            # Special key (e.g. Key.enter, Key.space)
            return str(key)

    def on_key_press(key):
        if stop_event.is_set():
            return False
        k = _key_str(key)
        with lock:
            event_log.append({
                "type": "keypress",
                "timestamp": time.time(),
                "key": k,
            })
        print(f"  ⌨️  KEY  {k}")

    def on_key_release(key):
        if stop_event.is_set():
            return False
        k = _key_str(key)
        with lock:
            event_log.append({
                "type": "keyrelease",
                "timestamp": time.time(),
                "key": k,
            })

    ss_thread = threading.Thread(target=screenshot_loop, daemon=True)
    ss_thread.start()
    listener = pynput_mouse.Listener(on_click=on_click, on_scroll=on_scroll)
    listener.start()
    kb_listener = pynput_keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
    kb_listener.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n🛑 Dừng sớm bởi người dùng.")
        stop_event.set()

    listener.stop()
    kb_listener.stop()
    ss_thread.join(timeout=3)

    with lock:
        sorted_log = sorted(event_log, key=lambda e: e["timestamp"])

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(sorted_log, f, indent=2, ensure_ascii=False)

    shots   = sum(1 for e in sorted_log if e["type"] == "screenshot")
    clicks  = sum(1 for e in sorted_log if e["type"] == "click")
    scrolls = sum(1 for e in sorted_log if e["type"] == "scroll")
    keys    = sum(1 for e in sorted_log if e["type"] == "keypress")

    print(f"\n💾 Log: {log_path}")
    print(f"📊 Screenshots: {shots} | Clicks: {clicks} | Scrolls: {scrolls} | Keys: {keys}")
    print(f"🗑️  Để xóa session này: python main.py clean {session_id}")

    return log_path, session_id
