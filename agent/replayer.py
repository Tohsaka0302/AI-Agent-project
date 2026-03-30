"""
agent/replayer.py

Đọc session_analysis.json và replay lại các thao tác chuột bằng pyautogui.
Phiên bản mới: dùng YOLO + OCR detect element trên màn hình HIỆN TẠI
để click chính xác, không phụ thuộc timing.
"""

import os
import json
import time
import tempfile
import webbrowser
import ctypes

try:
    import pyautogui
    pyautogui.FAILSAFE = True   # Di chuột vào góc trên-trái để dừng khẩn cấp
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    print("[WARN] pyautogui not installed. Run: pip install pyautogui")

try:
    from PIL import ImageGrab
    HAS_IMAGEGRAB = True
except ImportError:
    HAS_IMAGEGRAB = False

from agent.detector import detect_elements
from ocr.reader import enrich_elements_with_ocr
from screen.url_reader import get_browser_url


# Các label được coi là clickable
CLICKABLE_LABELS = {"button", "link", "checkbox", "submit", "icon"}

# Tốc độ di chuột (giây)
MOVE_DURATION = 0.4

# Visual-matching config
WAIT_POLL_INTERVAL = 0.5   # giây giữa mỗi lần poll
WAIT_MAX_TIMEOUT = 30      # giây tối đa đợi page ready

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


# ── Live detection helpers ──────────────────────────────────────

def _capture_current_screen() -> str:
    """Chụp screenshot màn hình hiện tại, lưu tạm, trả về path."""
    if not HAS_IMAGEGRAB:
        return None
    img = ImageGrab.grab()
    tmp_path = os.path.join(tempfile.gettempdir(), "_replayer_live.png")
    img.save(tmp_path)
    return tmp_path


def _detect_live_elements(tmp_path: str) -> list:
    """Detect elements trên screenshot hiện tại bằng YOLO + OCR."""
    if not tmp_path or not os.path.exists(tmp_path):
        return []
    elements = detect_elements(tmp_path)
    elements = enrich_elements_with_ocr(tmp_path, elements)
    return elements


def _normalize(text: str) -> str:
    """Chuẩn hóa text để so sánh: lowercase, strip, bỏ khoảng trắng thừa."""
    if not text:
        return ""
    return " ".join(text.lower().strip().split())


def _find_matching_element(target_el: dict, current_elements: list) -> dict | None:
    """
    Tìm element trên màn hình hiện tại khớp nhất với element đã ghi.
    So sánh theo label + text (fuzzy).
    Trả về element match tốt nhất hoặc None.
    """
    if not target_el or not current_elements:
        return None

    target_label = _normalize(target_el.get("label", ""))
    target_text  = _normalize(target_el.get("text", ""))

    best_match = None
    best_score = 0

    for el in current_elements:
        el_label = _normalize(el.get("label", ""))
        el_text  = _normalize(el.get("text", ""))
        score = 0

        # Label match (quan trọng)
        if el_label == target_label:
            score += 2

        # Text match
        if target_text and el_text:
            if el_text == target_text:
                score += 5  # Exact match
            elif target_text in el_text or el_text in target_text:
                score += 3  # Partial match
        elif not target_text and not el_text:
            score += 1  # Cả hai đều không có text (ví dụ icon) -> bonus thêm 1 điểm để đạt threshold >= 3

        if score > best_score:
            best_score = score
            best_match = el

    # Chỉ trả về nếu đủ confident (ít nhất match label + text partial)
    if best_score >= 3:
        return best_match
    return None


def _wait_for_page_ready(
    target_element: dict,
    target_url: str = None,
    max_wait: float = WAIT_MAX_TIMEOUT,
    poll_interval: float = WAIT_POLL_INTERVAL,
) -> dict | None:
    """
    Đợi cho đến khi trang web sẵn sàng (visual matching + optional URL).
    Nếu có target_url, ưu tiên kiểm tra xem đã đến đúng trang chưa.
    Sau đó chụp screenshot hiện tại → YOLO+OCR detect → tìm element khớp.
    Nếu tìm thấy → trả về matched element.
    Nếu timeout → trả về None (fallback về tọa độ gốc).
    """
    if not target_element or not HAS_IMAGEGRAB:
        return None

    start_time = time.time()
    attempt = 0

    while time.time() - start_time < max_wait:
        attempt += 1

        # 1. URL check (nếu có base url hoặc url pattern)
        if target_url:
            current_url = get_browser_url()
            # So sánh lỏng lẻo: chỉ cần path và domain khớp
            if current_url:
                # Bỏ qua protocol (http/https), query parameters (?)
                norm_target = target_url.split("?")[0].split("://")[-1].rstrip("/")
                norm_current = current_url.split("?")[0].split("://")[-1].rstrip("/")
                if norm_target and norm_current and norm_target != norm_current:
                    # Chua đen trang → doi
                    time.sleep(poll_interval)
                    continue

        # 2. Visual checking
        tmp_path = _capture_current_screen()
        if not tmp_path:
            time.sleep(poll_interval)
            continue

        live_elements = _detect_live_elements(tmp_path)
        matched = _find_matching_element(target_element, live_elements)

        if matched:
            elapsed = time.time() - start_time
            print(f"      ✅ Page ready (attempt {attempt}, {elapsed:.1f}s) "
                  f"[{matched['label']}] '{matched.get('text', '')[:20]}'")
            return matched

        time.sleep(poll_interval)

    elapsed = time.time() - start_time
    print(f"      ⚠️  Timeout sau {elapsed:.1f}s ({attempt} attempts) – fallback tọa độ gốc")
    return None


def _clipboard_type(text: str):
    """
    Gõ text Unicode bằng cách copy vào clipboard rồi Ctrl+V.
    Dùng Windows API (ctypes) để set clipboard.
    """
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # QUAN TRỌNG: set restype và argtypes cho 64-bit Windows (tránh truncate pointer/overflow)
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

    data = text.encode('utf-16-le') + b'\x00\x00'

    if not user32.OpenClipboard(0):
        return
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            return
        p = kernel32.GlobalLock(h)
        if not p:
            kernel32.GlobalFree(h)
            return
        ctypes.memmove(p, data, len(data))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        user32.CloseClipboard()

    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.05)


def _collapse_ime_sequences(events: list) -> list:
    """
    Collapse Vietnamese IME (UniKey/Telex) composition sequences.

    Pattern: ... [char₁] [char₂] [·] [bs]×N [composed_char] ...
    → Remove N chars trước ·, xóa · và backspaces, giữ composed_char.

    The middle dot · (U+00B7) is the IME composition marker.
    N backspaces after · = N chars before · cần bị xóa.
    """
    IME_MARKER = "\u00b7"  # · Middle Dot
    result = list(events)

    changed = True
    while changed:
        changed = False
        for i, ev in enumerate(result):
            if ev.get("type") != "keypress" or ev.get("key") != IME_MARKER:
                continue

            # Đếm backspaces liên tiếp sau ·
            bs_count = 0
            j = i + 1
            while (j < len(result)
                   and result[j].get("type") == "keypress"
                   and result[j].get("key") == "Key.backspace"):
                bs_count += 1
                j += 1

            if bs_count == 0 or j >= len(result):
                continue
            if result[j].get("type") != "keypress":
                continue

            # j = index of composed char (giữ lại)
            # Tìm bs_count keypress events trước · để xóa
            to_remove = set()
            to_remove.add(i)  # · marker
            for bi in range(i + 1, j):  # backspaces
                to_remove.add(bi)

            k = i - 1
            removed = 0
            while k >= 0 and removed < bs_count:
                if result[k].get("type") == "keypress":
                    to_remove.add(k)
                    removed += 1
                else:
                    break  # Không xóa qua click/scroll
                k -= 1

            result = [e for idx, e in enumerate(result) if idx not in to_remove]
            changed = True
            break  # Restart scan

    n_removed = len(events) - len(result)
    if n_removed > 0:
        print(f"  [IME] Collapsed {n_removed} IME intermediate events")
    return result


def _process_modifiers_and_combos(events: list) -> list:
    """
    Xử lý modifier keys và tổ hợp phím:
    1. Control characters (\x01-\x1a) → hotkey Ctrl+letter
    2. Skip standalone modifier keypresses (Shift, Ctrl, Alt, Win)
    """
    MODIFIER_KEYS = {
        "Key.ctrl_l", "Key.ctrl_r", "Key.alt_l", "Key.alt_r",
        "Key.shift", "Key.shift_l", "Key.shift_r",
        "Key.cmd", "Key.cmd_l", "Key.cmd_r",
    }

    result = []
    n_hotkeys = 0
    n_skipped = 0

    for ev in events:
        if ev.get("type") != "keypress":
            result.append(ev)
            continue

        raw_key = ev.get("key", "")

        # Skip standalone modifier keypresses
        if raw_key in MODIFIER_KEYS:
            n_skipped += 1
            continue

        # Control character \x01-\x1a → Ctrl+letter hotkey
        if raw_key and len(raw_key) == 1 and 1 <= ord(raw_key) <= 26:
            letter = chr(ord(raw_key) + 96)  # \x01 → 'a'
            result.append({
                **ev,
                "type": "hotkey",
                "modifiers": ["ctrl"],
                "target_key": letter,
            })
            n_hotkeys += 1
            continue

        # Skip empty/null keys
        if not raw_key or raw_key == "\x00":
            n_skipped += 1
            continue

        result.append(ev)

    if n_hotkeys > 0 or n_skipped > 0:
        print(f"  [MODS] {n_hotkeys} hotkey combos detected, {n_skipped} modifier events skipped")
    return result


# ── Main replay function ────────────────────────────────────────

def replay(
    analysis_path: str = None,
    url: str = None,
    dry_run: bool = False,
    speed: float = 1.0,
    folder: str = "screenshots"
):
    """
    Replay lại session thao tác.
    Click events: dùng YOLO+OCR detect element trên màn hình HIỆN TẠI,
    di chuột đến element khớp rồi click (không phụ thuộc timing).
    Fallback về tọa độ gốc nếu không tìm được element.

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

    # Chỉ replay các action thật (click, scroll, scroll_start, scroll_end, keypress) – bỏ qua frame thuần screenshot và keyrelease
    action_frames = [e for e in frames if e.get("type") in ("click", "scroll", "scroll_start", "scroll_end", "keypress")]
    all_frames    = frames  # dùng nếu không có click nào (session cũ)

    replay_list = action_frames if action_frames else all_frames

    # Collapse Vietnamese IME sequences (·, backspace, composed char)
    replay_list = _collapse_ime_sequences(replay_list)

    # Process modifier combos (Ctrl+A, etc.)
    replay_list = _process_modifiers_and_combos(replay_list)

    print(f"[replayer] {len(replay_list)} actions để replay | Mode: {'DRY RUN' if dry_run else 'LIVE'} | Speed: {speed}x")
    print("-" * 60)

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
    live_detect_ok = HAS_IMAGEGRAB  # có thể chụp màn hình để detect live không

    for i, event in enumerate(replay_list):
        ev_type   = event.get("type", "screenshot")
        timestamp = event["timestamp"]
        nearest   = event.get("nearest_element")

        # Mouse coordinates (keypress events không có)
        mouse_info = event.get("mouse", {})
        mouse_x = mouse_info.get("x", 0)
        mouse_y = mouse_info.get("y", 0)

        # ── CLICK: Visual-matching targeting ────────────────────
        if ev_type == "click":
            target_x, target_y = mouse_x, mouse_y
            match_info = ""
            target_url = event.get("url")

            if nearest and not dry_run:
                if live_detect_ok:
                    # Visual matching: đợi page sẵn sàng rồi mới click
                    print(f"  [{i+1:03d}] 🖥️  Waiting for page ready...")
                    matched = _wait_for_page_ready(nearest, target_url)

                    if matched:
                        target_x = matched["bbox"]["cx"]
                        target_y = matched["bbox"]["cy"]
                        match_info = f"✅ MATCHED [{matched['label']}] '{matched.get('text', '')[:20]}' → ({target_x},{target_y})"
                    else:
                        match_info = f"⚠️  FALLBACK tọa độ gốc ({mouse_x},{mouse_y})"
                else:
                    match_info = f"[{nearest['label']}] '{nearest.get('text', '')}'"
            elif nearest:
                match_info = f"[{nearest['label']}] '{nearest.get('text', '')}'"

            print(f"  [{i+1:03d}] 🖱️  CLICK ({target_x:4d},{target_y:4d})  {match_info}")

            if not dry_run:
                pyautogui.moveTo(target_x, target_y, duration=MOVE_DURATION)
                pyautogui.click()

        # ── SCROLL_START: nhận biết vùng cần scroll ─────────────
        elif ev_type == "scroll_start":
            print(f"  [{i+1:03d}] 🖱️  SCROLL START ({mouse_x:4d},{mouse_y:4d})")
            if not dry_run:
                pyautogui.moveTo(mouse_x, mouse_y, duration=MOVE_DURATION)

        # ── SCROLL: giữ nguyên tọa độ gốc ──────────────────────
        elif ev_type == "scroll":
            dy = event.get("dy", 0)
            icon = f"🖱️  SCROLL {'↑' if dy > 0 else '↓'}"
            print(f"  [{i+1:03d}] {icon} ({mouse_x:4d},{mouse_y:4d})")

            if not dry_run:
                # Delay nhỏ giữa các scroll events (giữ tốc độ hợp lý)
                if prev_timestamp is not None:
                    scroll_delay = (timestamp - prev_timestamp) / speed
                    scroll_delay = max(0.02, min(scroll_delay, 0.5))
                    time.sleep(scroll_delay)
                pyautogui.moveTo(mouse_x, mouse_y, duration=0.05)
                pyautogui.scroll(int(dy * 3))

        # ── SCROLL_END: kết thúc scroll ─────────────────────────
        elif ev_type == "scroll_end":
            print(f"  [{i+1:03d}] 🖱️  SCROLL END ({mouse_x:4d},{mouse_y:4d})")
            if not dry_run:
                time.sleep(0.3)  # nhỏ nghỉ sau scroll

        # ── KEYPRESS: hỗ trợ Unicode ─────────────────────────────
        elif ev_type == "keypress":
            raw_key = event.get("key", "")
            # Delay nhỏ giữa các key events (giữ tốc độ gõ hợp lý)
            if prev_timestamp is not None:
                key_delay = (timestamp - prev_timestamp) / speed
                key_delay = max(0.02, min(key_delay, 2.0))
            else:
                key_delay = 0.05
            print(f"  [{i+1:03d}] ⌨️  KEY   {raw_key}")

            if not dry_run:
                time.sleep(key_delay)
                mapped = KEY_MAP.get(raw_key)
                if mapped:
                    pyautogui.press(mapped)
                elif raw_key and len(raw_key) == 1:
                    if raw_key.isascii():
                        pyautogui.typewrite(raw_key, interval=0.02)
                    else:
                        _clipboard_type(raw_key)

        # ── HOTKEY: tổ hợp phím (Ctrl+A, etc.) ───────────────
        elif ev_type == "hotkey":
            mods = event.get("modifiers", [])
            target = event.get("target_key", "")
            combo_str = "+".join(mods + [target])
            print(f"  [{i+1:03d}] ⌨️  HOTKEY {combo_str}")

            if not dry_run:
                time.sleep(0.1)
                pyautogui.hotkey(*mods, target)

        # ── Screenshot (fallback for old sessions) ──────────────
        else:
            if prev_timestamp is not None:
                delay = (timestamp - prev_timestamp) / speed
                delay = max(0.05, min(delay, 5.0))
            else:
                delay = 0
            print(f"  [{i+1:03d}] ⏱ {delay:.2f}s  📷 MOVE  ({mouse_x:4d},{mouse_y:4d})")
            if not dry_run:
                time.sleep(delay)
                pyautogui.moveTo(mouse_x, mouse_y, duration=MOVE_DURATION)

        prev_timestamp = timestamp

    # Cleanup temp file
    tmp_cleanup = os.path.join(tempfile.gettempdir(), "_replayer_live.png")
    if os.path.exists(tmp_cleanup):
        os.remove(tmp_cleanup)

    print("\n✅ Replay complete!")
