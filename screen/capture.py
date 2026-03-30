"""
screen/capture.py – Event-driven recording engine

Mặc định: chỉ chụp screenshot khi có click hoặc scroll (event-driven).
Tùy chọn --periodic: chụp thêm screenshot định kỳ (backward compatible).

Mỗi session lưu vào subfolder screenshots/session_<id>/
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

from screen.url_reader import get_browser_url


# ── Scroll debounce config ──────────────────────────────────────
SCROLL_IDLE_THRESHOLD = 0.4  # giây – nếu không scroll thêm sau khoảng này → coi là dừng


def capture_screen(
    interval: int = 1,
    duration: int = 60,
    window_title: str = None,
    periodic: bool = False,
):
    """
    Ghi session: bắt click/scroll/keyboard real-time.
    
    Mặc định (event-driven):
      - Chụp screenshot khi có click (trước khi click xảy ra)
      - Chụp screenshot khi bắt đầu scroll và khi dừng scroll
      - KHÔNG chụp định kỳ
      
    periodic=True:
      - Thêm thread chụp screenshot định kỳ (interval giây)
      - Backward compatible với cách hoạt động cũ

    Mỗi session lưu vào thư mục con riêng: screenshots/session_<id>/
    """
    project_root = os.path.abspath(os.path.join(__file__, "../../"))
    base_dir = os.path.join(project_root, "screenshots")

    session_id = int(time.time())
    session_dir = os.path.join(base_dir, f"session_{session_id}")
    os.makedirs(session_dir, exist_ok=True)
    print(f"📁 Session folder: {session_dir}")

    log_path = os.path.join(session_dir, "mouse.json")

    event_log = []
    frame_counter = [0]
    stop_event = threading.Event()
    lock = threading.Lock()
    deadline = time.time() + duration

    # ── Scroll state tracking ───────────────────────────────────
    scroll_state = {
        "active": False,       # đang trong chuỗi scroll?
        "last_time": 0.0,      # timestamp scroll gần nhất
        "start_screenshot": None,  # filename screenshot đầu scroll
    }

    mode_str = "EVENT-DRIVEN" if not periodic else "EVENT-DRIVEN + PERIODIC"
    print(f"\n📸 Recording mode: {mode_str} | Duration: {duration}s")
    if periodic:
        print(f"   Periodic interval: {interval}s")
    if window_title:
        print(f"   Chỉ ghi khi '{window_title}' đang active")
    print("Press CTRL+C để dừng sớm\n")

    for i in range(3, 0, -1):
        print(f"  ⏳ Bắt đầu sau {i} giây...", end="\r")
        time.sleep(1)
    print("  🔴 Đang ghi!                \n")

    # ── Helper: chụp screenshot ─────────────────────────────────
    def _take_screenshot(tag: str = "") -> str:
        """Chụp screenshot, lưu file, trả về filename."""
        if window_title and HAS_PYGETWINDOW:
            active = gw.getActiveWindow()
            if active is None or window_title.lower() not in active.title.lower():
                return None

        idx = frame_counter[0]
        frame_counter[0] += 1
        filename = f"screenshot_{idx:04d}.png"
        filepath = os.path.join(session_dir, filename)

        img = ImageGrab.grab()
        img.save(filepath)

        if tag:
            print(f"  📷 [{idx:03d}] {tag} → {filename}")
        else:
            print(f"  📷 [{idx:03d}] {filename}")
        return filename

    # ── Helper: kết thúc scroll sequence ────────────────────────
    def _finalize_scroll():
        """Chụp screenshot khi scroll dừng lại."""
        if not scroll_state["active"]:
            return
        scroll_state["active"] = False
        filename = _take_screenshot("SCROLL_END")
        if filename:
            mx, my = pyautogui.position()
            with lock:
                event_log.append({
                    "type": "scroll_end",
                    "timestamp": time.time(),
                    "mouse_x": mx,
                    "mouse_y": my,
                    "screenshot": filename,
                })

    # ── Thread: Scroll idle detector ────────────────────────────
    def scroll_idle_watcher():
        """Phát hiện khi scroll dừng (idle) để chụp screenshot end."""
        while not stop_event.is_set():
            time.sleep(0.1)
            if time.time() >= deadline:
                stop_event.set()
                break
            with lock:
                if (scroll_state["active"]
                        and time.time() - scroll_state["last_time"] > SCROLL_IDLE_THRESHOLD):
                    _finalize_scroll()

    # ── Thread: Periodic screenshot (optional) ──────────────────
    def screenshot_loop():
        """Chụp screenshot định kỳ (chỉ khi periodic=True)."""
        while not stop_event.is_set():
            if time.time() >= deadline:
                stop_event.set()
                break
            filename = _take_screenshot("PERIODIC")
            if filename:
                mx, my = pyautogui.position()
                with lock:
                    event_log.append({
                        "type": "screenshot",
                        "frame": frame_counter[0] - 1,
                        "timestamp": time.time(),
                        "screenshot": filename,
                        "mouse_x": mx,
                        "mouse_y": my,
                    })
            time.sleep(interval)

    # ── Mouse callback: click ───────────────────────────────────
    def on_click(x, y, button, pressed):
        if stop_event.is_set():
            return False
        if pressed:
            # Kết thúc scroll sequence nếu đang scroll
            with lock:
                if scroll_state["active"]:
                    _finalize_scroll()

            # Chụp screenshot TRƯỚC khi click (trạng thái UI lúc click)
            filename = _take_screenshot("CLICK")

            # Đọc URL từ browser
            current_url = get_browser_url(window_title)

            with lock:
                event_log.append({
                    "type": "click",
                    "timestamp": time.time(),
                    "mouse_x": x, "mouse_y": y,
                    "button": str(button),
                    "screenshot": filename,
                    "url": current_url,
                })
            url_info = f" 🌐 {current_url[:40]}" if current_url else ""
            print(f"  🖱️  CLICK ({x:4d},{y:4d}){url_info}")

    # ── Mouse callback: scroll ──────────────────────────────────
    def on_scroll(x, y, dx, dy):
        if stop_event.is_set():
            return False

        with lock:
            now = time.time()

            # Bắt đầu scroll sequence mới → chụp screenshot
            if not scroll_state["active"]:
                scroll_state["active"] = True
                filename = _take_screenshot("SCROLL_START")
                scroll_state["start_screenshot"] = filename

                # Đọc URL từ browser
                current_url = get_browser_url(window_title)

                if filename:
                    event_log.append({
                        "type": "scroll_start",
                        "timestamp": now,
                        "mouse_x": x, "mouse_y": y,
                        "screenshot": filename,
                        "url": current_url,
                    })

            scroll_state["last_time"] = now

            # Ghi scroll event (không chụp ảnh)
            event_log.append({
                "type": "scroll",
                "timestamp": now,
                "mouse_x": x, "mouse_y": y,
                "dx": dx, "dy": dy,
            })
        print(f"  🖱️  SCROLL {'↑' if dy > 0 else '↓'} ({x:4d},{y:4d})")

    # ── Keyboard callbacks ──────────────────────────────────────
    def _key_str(key):
        """Convert a pynput Key to a loggable string."""
        try:
            return key.char
        except AttributeError:
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

    # ── Start threads & listeners ───────────────────────────────
    # Scroll idle watcher (luôn chạy)
    scroll_watcher = threading.Thread(target=scroll_idle_watcher, daemon=True)
    scroll_watcher.start()

    # Periodic screenshot (only if --periodic)
    ss_thread = None
    if periodic:
        ss_thread = threading.Thread(target=screenshot_loop, daemon=True)
        ss_thread.start()

    # Mouse listener
    listener = pynput_mouse.Listener(on_click=on_click, on_scroll=on_scroll)
    listener.start()

    # Keyboard listener
    kb_listener = pynput_keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
    kb_listener.start()

    try:
        while not stop_event.is_set():
            if time.time() >= deadline:
                stop_event.set()
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n🛑 Dừng sớm bởi người dùng.")
        stop_event.set()

    # Kết thúc scroll nếu đang scroll
    with lock:
        if scroll_state["active"]:
            _finalize_scroll()

    listener.stop()
    kb_listener.stop()
    scroll_watcher.join(timeout=3)
    if ss_thread:
        ss_thread.join(timeout=3)

    with lock:
        sorted_log = sorted(event_log, key=lambda e: e["timestamp"])

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(sorted_log, f, indent=2, ensure_ascii=False)

    shots   = sum(1 for e in sorted_log if e.get("screenshot"))
    clicks  = sum(1 for e in sorted_log if e["type"] == "click")
    scrolls = sum(1 for e in sorted_log if e["type"] == "scroll")
    keys    = sum(1 for e in sorted_log if e["type"] == "keypress")
    scroll_starts = sum(1 for e in sorted_log if e["type"] == "scroll_start")
    scroll_ends   = sum(1 for e in sorted_log if e["type"] == "scroll_end")

    print(f"\n💾 Log: {log_path}")
    print(f"📊 Screenshots: {shots} | Clicks: {clicks} | Scrolls: {scrolls} | Keys: {keys}")
    print(f"   Scroll sequences: {scroll_starts} start → {scroll_ends} end")
    print(f"🗑️  Để xóa session này: python main.py clean {session_id}")

    return log_path, session_id
