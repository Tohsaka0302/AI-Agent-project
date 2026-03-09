"""
agent/replayer.py

Đọc session_analysis.json và replay lại các thao tác chuột bằng pyautogui.
"""

import os
import json
import time
import webbrowser

try:
    import pyautogui
    pyautogui.FAILSAFE = True   # Di chuột vào góc trên-trái để dừng khẩn cấp
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    print("[WARN] pyautogui not installed. Run: pip install pyautogui")


# Các label được coi là clickable
CLICKABLE_LABELS = {"button", "link", "checkbox", "submit", "icon"}

# Tốc độ di chuột (giây)
MOVE_DURATION = 0.4

# Map pynput special key names → pyautogui key names
KEY_MAP = {
    "Key.enter":     "enter",
    "Key.space":     "space",
    "Key.backspace": "backspace",
    "Key.tab":       "tab",
    "Key.esc":       "escape",
    "Key.escape":    "escape",
    "Key.shift":     "shift",
    "Key.shift_l":   "shiftleft",
    "Key.shift_r":   "shiftright",
    "Key.ctrl_l":    "ctrlleft",
    "Key.ctrl_r":    "ctrlright",
    "Key.alt_l":     "altleft",
    "Key.alt_r":     "altright",
    "Key.delete":    "delete",
    "Key.home":      "home",
    "Key.end":       "end",
    "Key.page_up":   "pageup",
    "Key.page_down": "pagedown",
    "Key.up":        "up",
    "Key.down":      "down",
    "Key.left":      "left",
    "Key.right":     "right",
    "Key.f1":  "f1",  "Key.f2":  "f2",  "Key.f3":  "f3",  "Key.f4":  "f4",
    "Key.f5":  "f5",  "Key.f6":  "f6",  "Key.f7":  "f7",  "Key.f8":  "f8",
    "Key.f9":  "f9",  "Key.f10": "f10", "Key.f11": "f11", "Key.f12": "f12",
}


def load_analysis(analysis_path: str) -> list:
    """Đọc file session_analysis.json."""
    if not os.path.exists(analysis_path):
        print(f"[replayer] File not found: {analysis_path}")
        return []
    with open(analysis_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_latest_analysis(folder: str = "screenshots") -> str:
    """Tìm file analysis.json mới nhất trong các session subfolders."""
    import glob
    files = glob.glob(os.path.join(folder, "session_*", "analysis.json"))
    if not files:
        # Fallback: tìm kiểu cũ
        files = glob.glob(os.path.join(folder, "*_analysis.json"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def replay(
    analysis_path: str = None,
    url: str = None,
    dry_run: bool = False,
    speed: float = 1.0,
    folder: str = "screenshots"
):
    """
    Replay lại session thao tác.

    Args:
        analysis_path : đường dẫn file *_analysis.json (None = lấy mới nhất)
        url           : URL để mở trước khi replay (None = không mở)
        dry_run       : True = chỉ in ra không di chuột thật
        speed         : hệ số tốc độ (1.0 = bình thường, 2.0 = nhanh gấp đôi)
        folder        : thư mục chứa session files
    """
    if analysis_path is None:
        analysis_path = find_latest_analysis(folder)
        if not analysis_path:
            print("[replayer] No analysis file found. Run 'analyze-session' first.")
            return

    frames = load_analysis(analysis_path)
    if not frames:
        print("[replayer] Analysis is empty.")
        return

    # Chỉ replay các action thật (click, scroll, keypress) – bỏ qua frame thuần screenshot và keyrelease
    action_frames = [e for e in frames if e.get("type") in ("click", "scroll", "keypress")]
    all_frames    = frames  # dùng nếu không có click nào (session cũ)

    replay_list = action_frames if action_frames else all_frames

    print(f"[replayer] {len(replay_list)} actions để replay | Mode: {'DRY RUN' if dry_run else 'LIVE'} | Speed: {speed}x")
    print("-" * 50)

    # Mở URL nếu có
    if url:
        print(f"\n🌐 Opening: {url}")
        if not dry_run:
            webbrowser.open(url)
            time.sleep(3)
        else:
            print(f"  [DRY] Would open: {url}")

    if not dry_run and not HAS_PYAUTOGUI:
        print("[replayer] pyautogui not available. Use --dry-run or install pyautogui.")
        return

    print(f"\n▶️  Starting replay in 3 seconds...")
    if not dry_run:
        time.sleep(3)

    prev_timestamp = None

    for i, event in enumerate(replay_list):
        ev_type   = event.get("type", "screenshot")
        mouse_x   = event["mouse"]["x"]
        mouse_y   = event["mouse"]["y"]
        timestamp = event["timestamp"]
        nearest   = event.get("nearest_element")

        # Delay giữa các action
        if prev_timestamp is not None:
            delay = (timestamp - prev_timestamp) / speed
            delay = max(0.05, min(delay, 5.0))
        else:
            delay = 0

        # Mô tả element
        el_desc = ""
        if nearest:
            el_desc = f"[{nearest['label']}] '{nearest.get('text', '')}'"

        # Icon theo loại event
        if ev_type == "click":
            icon = "🖱️  CLICK"
        elif ev_type == "scroll":
            dy = event.get("dy", 0)
            icon = f"🖱️  SCROLL {'↑' if dy > 0 else '↓'}"
        elif ev_type == "keypress":
            icon = "⌨️  KEY  "
        else:
            icon = "📷 MOVE "

        # Build display coordinate string (keys have no mouse position)
        if ev_type == "keypress":
            coord_str = event.get("key", "")
        else:
            coord_str = f"({mouse_x:4d},{mouse_y:4d})"

        print(f"  [{i+1:03d}] ⏱ {delay:.2f}s  {icon} {coord_str}  {el_desc}")

        if not dry_run:
            time.sleep(delay)

            if ev_type == "click":
                pyautogui.moveTo(mouse_x, mouse_y, duration=MOVE_DURATION)
                pyautogui.click()

            elif ev_type == "scroll":
                pyautogui.moveTo(mouse_x, mouse_y, duration=MOVE_DURATION)
                dy = event.get("dy", 0)
                pyautogui.scroll(int(dy * 3))

            elif ev_type == "keypress":
                raw_key = event.get("key", "")
                mapped  = KEY_MAP.get(raw_key)
                if mapped:
                    pyautogui.press(mapped)
                elif raw_key and len(raw_key) == 1:
                    pyautogui.typewrite(raw_key, interval=0.05)
                # else: unknown special key – skip silently

            else:
                pyautogui.moveTo(mouse_x, mouse_y, duration=MOVE_DURATION)

        prev_timestamp = timestamp

    print("\n✅ Replay complete!")
