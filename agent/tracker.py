"""
agent/tracker.py

Phân tích session log (mixed events: screenshot + click + scroll):
  - Với mỗi click: tìm screenshot gần nhất → detect UI → map element
  - Ghi kết quả ra session_analysis.json
"""

import os
import json
import math
import bisect

from agent.detector import detect_elements, save_debug_image
from ocr.reader import enrich_elements_with_ocr


def _distance(x1, y1, x2, y2) -> float:
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def find_nearest_element(elements: list, mouse_x: int, mouse_y: int, max_dist: int = 150):
    """Tìm element gần với tọa độ chuột nhất."""
    best = None
    best_dist = float("inf")
    for el in elements:
        cx = el["bbox"]["cx"]
        cy = el["bbox"]["cy"]
        dist = _distance(cx, cy, mouse_x, mouse_y)
        if dist < best_dist and dist <= max_dist:
            best_dist = dist
            best = {**el, "_dist_to_mouse": round(dist, 1)}
    return best


def _find_nearest_screenshot(screenshots: list, timestamp: float) -> dict | None:
    """
    Tìm screenshot gần nhất với timestamp của event.
    screenshots: list of {timestamp, screenshot, ...} đã sort theo timestamp
    """
    if not screenshots:
        return None
    timestamps = [s["timestamp"] for s in screenshots]
    idx = bisect.bisect_left(timestamps, timestamp)
    # Lấy screenshot liền trước hoặc liền sau
    candidates = []
    if idx > 0:
        candidates.append(screenshots[idx - 1])
    if idx < len(screenshots):
        candidates.append(screenshots[idx])
    return min(candidates, key=lambda s: abs(s["timestamp"] - timestamp))


def analyze_session(session_frames: list, output_dir: str = "screenshots") -> str:
    """
    Phân tích session log (có thể chứa cả screenshot, click, scroll events).

    Args:
        session_frames : output của load_session()
        output_dir     : thư mục lưu kết quả

    Returns:
        Đường dẫn file session_analysis.json
    """
    if not session_frames:
        print("[tracker] No events to analyze.")
        return None

    # Phân loại events
    screenshots  = [e for e in session_frames if e.get("type") == "screenshot"]
    actions      = [e for e in session_frames if e.get("type") in ("click", "scroll", "scroll_start", "scroll_end")]
    key_events   = [e for e in session_frames if e.get("type") in ("keypress", "keyrelease")]

    # Event-driven mode: click/scroll_start/scroll_end cũng có screenshot
    # → thêm vào danh sách screenshots để dùng cho context lookup
    for e in session_frames:
        if e.get("type") in ("click", "scroll_start", "scroll_end") and e.get("screenshot"):
            screenshots.append(e)

    # Fallback: nếu log cũ (không có type) thì coi tất cả là screenshot
    if not screenshots and not actions:
        screenshots = session_frames
        for s in screenshots:
            s.setdefault("type", "screenshot")

    screenshots.sort(key=lambda e: e["timestamp"])

    # Cache YOLO results theo tên file (tránh detect lại cùng 1 ảnh)
    _detect_cache = {}

    def get_elements_for_screenshot(ss_entry):
        fname = ss_entry.get("screenshot", "")
        if fname in _detect_cache:
            return _detect_cache[fname]
        path = ss_entry.get("screenshot", "")
        if not os.path.exists(path):
            # Thử thêm output_dir vào phía trước
            path = os.path.join(output_dir, os.path.basename(path))
        if not os.path.exists(path):
            _detect_cache[fname] = []
            return []
        els = detect_elements(path)
        els = enrich_elements_with_ocr(path, els)

        # Lưu ảnh debug với bounding box
        if els:
            base, ext = os.path.splitext(path)
            debug_path = f"{base}_yolo{ext}"
            save_debug_image(path, els, debug_path)

        _detect_cache[fname] = els
        return els

    results = []
    total_events = len(screenshots) + len(actions) + len(key_events)
    print(f"[tracker] {len(screenshots)} screenshots | {len(actions)} click/scroll events | {len(key_events)} key events")
    processed = 0

    # ── Analyze click/scroll events (ưu tiên vì đây là action thật) ──
    click_debug_counter = 0
    for event in actions:
        processed += 1
        mx = event["mouse_x"]
        my = event["mouse_y"]
        ts = event["timestamp"]
        ev_type = event["type"]

        # Event-driven mode: event tự có screenshot → dùng trực tiếp
        # Legacy mode: tìm screenshot gần nhất
        if event.get("screenshot"):
            nearest_ss = event
        else:
            nearest_ss = _find_nearest_screenshot(screenshots, ts)

        nearest_el = None
        n_elements = 0

        if nearest_ss:
            elements = get_elements_for_screenshot(nearest_ss)
            n_elements = len(elements)
            nearest_el = find_nearest_element(elements, mx, my)

            # Lưu debug image cho click event (highlight element đã click)
            if ev_type == "click" and elements:
                click_debug_counter += 1
                ss_path = nearest_ss.get("screenshot", "")
                if not os.path.exists(ss_path):
                    ss_path = os.path.join(output_dir, os.path.basename(ss_path))
                if os.path.exists(ss_path):
                    base, ext = os.path.splitext(ss_path)
                    debug_path = f"{base}_click_{click_debug_counter:04d}{ext}"
                    save_debug_image(
                        ss_path, elements, debug_path,
                        clicked_element=nearest_el,
                        click_pos=(mx, my),
                    )

        label = f"[{ev_type}]"
        el_info = f"→ [{nearest_el['label']}] '{nearest_el['text']}' dist={nearest_el['_dist_to_mouse']}" if nearest_el else "→ no element nearby"
        print(f"  [{processed:03d}/{total_events}] {label} ({mx},{my}) {el_info}")

        results.append({
            "type":      ev_type,
            "timestamp": ts,
            "mouse": {"x": mx, "y": my},
            "button":    event.get("button"),
            "dx":        event.get("dx"),
            "dy":        event.get("dy"),
            "context_screenshot": nearest_ss.get("screenshot", "") if nearest_ss else "",
            "screenshot": event.get("screenshot", ""),
            "url":       event.get("url"),
            "elements_detected": n_elements,
            "nearest_element": nearest_el,
        })

    # ── Pass-through keyboard events ────────────────────────────
    for event in key_events:
        processed += 1
        ev_type = event["type"]
        k = event.get("key", "")
        print(f"  [{processed:03d}/{total_events}] [{ev_type}] {k}")
        results.append({
            "type":      ev_type,
            "timestamp": event["timestamp"],
            "key":       k,
        })

    # ── Analyze screenshot frames ────────────────────────────────
    for i, ss in enumerate(screenshots):
        processed += 1
        mx = ss.get("mouse_x", 0)
        my = ss.get("mouse_y", 0)
        fname = ss.get("screenshot", "")

        elements = get_elements_for_screenshot(ss)
        nearest_el = find_nearest_element(elements, mx, my)
        el_info = f"→ [{nearest_el['label']}] '{nearest_el['text']}'" if nearest_el else "→ no element"
        print(f"  [{processed:03d}/{total_events}] [frame {i:03d}] ({mx},{my}) {el_info}")

        results.append({
            "type":      "screenshot",
            "frame":     ss.get("frame", i),
            "timestamp": ss["timestamp"],
            "screenshot": os.path.basename(fname),
            "mouse": {"x": mx, "y": my},
            "elements_detected": len(elements),
            "nearest_element": nearest_el,
        })

    # Sắp xếp toàn bộ kết quả theo thời gian
    results.sort(key=lambda r: r["timestamp"])

    # Xác định session folder từ path của screenshot đầu tiên
    if screenshots:
        first_ss_path = screenshots[0].get("screenshot", "")
        session_folder = os.path.dirname(first_ss_path)
        if not session_folder or not os.path.exists(session_folder):
            session_folder = output_dir
    else:
        session_folder = output_dir

    out_path = os.path.join(session_folder, "analysis.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    click_count = sum(1 for r in results if r["type"] == "click")
    key_count   = sum(1 for r in results if r["type"] == "keypress")
    print(f"\n✅ Analysis saved: {out_path}")
    print(f"   Tổng: {len(results)} events | {click_count} clicks | {key_count} key presses")
    return out_path
