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
        print(f"[YOLO] Loading default model: {DEFAULT_MODEL}")
        return YOLO(DEFAULT_MODEL)


# Singleton model để không load lại mỗi lần
_model = None


def get_model():
    global _model
    if _model is None:
        _model = load_model()
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
