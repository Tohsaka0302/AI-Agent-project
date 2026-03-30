"""
agent/detector.py

Dùng YOLOv8 (ultralytics) để detect UI elements trong screenshot.
Model mặc định: yolov8n.pt (general), tự tải lần đầu tiên.
"""

import os
from pathlib import Path

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False
    print("[WARN] ultralytics not installed. Run: pip install ultralytics")

# Thư mục chứa model
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# Sử dụng model custom nếu có, không thì dùng yolov8n
CUSTOM_MODEL = os.path.join(MODEL_DIR, "best.pt")
DEFAULT_MODEL = "yolov8n.pt"

# Nhóm class COCO gần với UI elements nhất
# yolov8n nhận diện 80 class, ta map những class có thể là UI element
UI_LIKE_CLASSES = {
    "laptop", "keyboard", "mouse", "cell phone", "remote",
    "book", "clock",  # các vật thể hình chữ nhật / có thể kích hoạt
}

# Confidence threshold
CONF_THRESHOLD = 0.25


def load_model():
    if not HAS_YOLO:
        return None

    if os.path.exists(CUSTOM_MODEL):
        print(f"[YOLO] Loading custom model: {CUSTOM_MODEL}")
        return YOLO(CUSTOM_MODEL)
    else:
        print(f"[WARN] Custom model not found. Falling back to OpenCV detection.")
        return None


# Singleton model để không load lại mỗi lần
_model = None
_model_loaded = False


def get_model():
    global _model, _model_loaded
    if not _model_loaded:
        _model = load_model()
        _model_loaded = True
    return _model


def detect_elements(image_path: str) -> list:
    """
    Detect các phần tử trong ảnh bằng YOLO.

    Returns:
        List of dict:
        {
            "label":  str,   # tên class
            "conf":   float, # confidence score
            "bbox": {
                "x": int,    # top-left x
                "y": int,    # top-left y
                "w": int,    # width
                "h": int,    # height
                "cx": int,   # center x
                "cy": int,   # center y
            }
        }
    """
    if not HAS_YOLO:
        return _fallback_detect(image_path)

    model = get_model()
    if model is None:
        return _fallback_detect(image_path)

    results = model(image_path, conf=CONF_THRESHOLD, verbose=False)
    elements = []

    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            label = result.names[cls_id]
            conf = float(box.conf[0])
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
            w = x2 - x1
            h = y2 - y1

            elements.append({
                "label": label,
                "conf": round(conf, 3),
                "bbox": {
                    "x": x1, "y": y1,
                    "w": w,  "h": h,
                    "cx": x1 + w // 2,
                    "cy": y1 + h // 2,
                }
            })

    return elements


def _fallback_detect(image_path: str) -> list:
    """
    Fallback: dùng OpenCV detect rectangular contours (likely UI elements).
    """
    try:
        import cv2
        img = cv2.imread(image_path)
        if img is None:
            return []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        elements = []
        img_h, img_w = img.shape[:2]
        min_area = (img_w * img_h) * 0.001  # ít nhất 0.1% diện tích màn hình

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            aspect = w / h if h > 0 else 0

            # Heuristic: button thường rộng hơn cao (aspect 2~8), input có aspect lớn hơn
            if 1.5 <= aspect <= 10 and 20 <= h <= 80:
                label = "input" if aspect > 5 else "button"
                elements.append({
                    "label": label,
                    "conf": 0.5,
                    "bbox": {
                        "x": x, "y": y,
                        "w": w, "h": h,
                        "cx": x + w // 2,
                        "cy": y + h // 2,
                    }
                })

        return elements

    except ImportError:
        print("[WARN] cv2 not installed. No fallback detection available.")
        return []


def save_debug_image(image_path: str, elements: list, output_path: str,
                     clicked_element: dict = None, click_pos: tuple = None):
    """
    Vẽ bounding box + label + confidence lên bản copy của ảnh và lưu ra file.
    Dùng để debug xem YOLO nhận diện được gì.

    Args:
        clicked_element: element đã được click (vẽ nổi bật với viền đỏ dày)
        click_pos:       (x, y) tọa độ chuột khi click (vẽ crosshair)
    """
    try:
        import cv2
        img = cv2.imread(image_path)
        if img is None:
            print(f"[debug] Cannot read image: {image_path}")
            return

        for el in elements:
            bbox = el["bbox"]
            x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
            label = el.get("label", "?")
            conf  = el.get("conf", 0)
            text  = el.get("text", "")

            # Màu theo loại element
            color = (0, 255, 0)  # Xanh lá mặc định
            if label in ("button", "submit"):
                color = (0, 165, 255)  # Cam
            elif label == "input":
                color = (255, 200, 0)  # Xanh dương nhạt

            # Vẽ rectangle
            cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)

            # Label text
            disp = f"{label} {conf:.2f}"
            if text:
                disp += f" '{text[:20]}'"

            # Background cho text dễ đọc
            (tw, th), _ = cv2.getTextSize(disp, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(img, (x, y - th - 6), (x + tw + 4, y), color, -1)
            cv2.putText(img, disp, (x + 2, y - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        # ── Highlight clicked element ────────────────────────────
        if clicked_element:
            cb = clicked_element["bbox"]
            cx, cy, cw, ch = cb["x"], cb["y"], cb["w"], cb["h"]
            cl_label = clicked_element.get("label", "?")
            cl_text  = clicked_element.get("text", "")

            # Viền đỏ dày nổi bật
            RED = (0, 0, 255)
            cv2.rectangle(img, (cx, cy), (cx + cw, cy + ch), RED, 3)

            # Label "CLICKED" phía trên
            disp_c = f"CLICKED [{cl_label}]"
            if cl_text:
                disp_c += f" '{cl_text[:20]}'"
            (tw, th), _ = cv2.getTextSize(disp_c, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(img, (cx, cy - th - 8), (cx + tw + 6, cy), RED, -1)
            cv2.putText(img, disp_c, (cx + 3, cy - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # ── Crosshair tại vị trí click ───────────────────────────
        if click_pos:
            px, py = int(click_pos[0]), int(click_pos[1])
            YELLOW = (0, 255, 255)
            size = 18
            cv2.line(img, (px - size, py), (px + size, py), YELLOW, 2)
            cv2.line(img, (px, py - size), (px, py + size), YELLOW, 2)
            cv2.circle(img, (px, py), 6, YELLOW, 2)

        cv2.imwrite(output_path, img)
        print(f"  🖼️  Debug image saved: {os.path.basename(output_path)}")

    except ImportError:
        print("[debug] cv2 not installed, skipping debug image.")
    except Exception as e:
        print(f"[debug] Error saving debug image: {e}")
