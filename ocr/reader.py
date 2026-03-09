import pytesseract
from PIL import Image
import os

# Tự động tìm Tesseract ở các đường dẫn phổ biến
_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\ADMIN\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]

_TESSERACT_OK = False
_WARNED = False

def _init_tesseract():
    global _TESSERACT_OK, _WARNED
    for path in _TESSERACT_PATHS:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            _TESSERACT_OK = True
            return
    if not _WARNED:
        print("[OCR WARN] Tesseract chưa được cài hoặc không tìm thấy!")
        print("           Tải về tại: https://github.com/UB-Mannheim/tesseract/wiki")
        print("           OCR sẽ bị bỏ qua cho đến khi cài xong.\n")
        _WARNED = True

_init_tesseract()


def read_text(image_path):
    """OCR toàn bộ ảnh, trả về plain text."""
    if not _TESSERACT_OK:
        return ""
    if not image_path or not os.path.exists(image_path):
        print("Image not found:", image_path)
        return ""
    try:
        img = Image.open(image_path)
        return pytesseract.image_to_string(img)
    except Exception as e:
        print(f"[OCR] read_text error: {e}")
        return ""


def read_with_boxes(image_path):
    """OCR toàn bộ ảnh, trả về list các word kèm bounding box."""
    if not _TESSERACT_OK:
        return []
    if not image_path or not os.path.exists(image_path):
        print("Image not found:", image_path)
        return []
    try:
        img = Image.open(image_path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        results = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = int(data["conf"][i])
            if text == "" or conf < 0:
                continue
            results.append({
                "text": text,
                "x":    data["left"][i],
                "y":    data["top"][i],
                "w":    data["width"][i],
                "h":    data["height"][i],
                "conf": conf,
            })
        return results
    except Exception as e:
        print(f"[OCR] read_with_boxes error: {e}")
        return []


def read_region(image_path: str, bbox: dict) -> str:
    """OCR chỉ một vùng cụ thể trong ảnh (theo bbox từ YOLO)."""
    if not _TESSERACT_OK:
        return ""
    if not image_path or not os.path.exists(image_path):
        return ""
    try:
        img = Image.open(image_path)
        x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
        padding = 4
        left   = max(0, x - padding)
        top    = max(0, y - padding)
        right  = min(img.width,  x + w + padding)
        bottom = min(img.height, y + h + padding)
        region = img.crop((left, top, right, bottom))
        return pytesseract.image_to_string(region, config="--psm 7").strip()
    except Exception as e:
        return ""


def enrich_elements_with_ocr(image_path: str, elements: list) -> list:
    """Thêm field 'text' vào mỗi element bằng OCR bbox."""
    enriched = []
    for el in elements:
        text = read_region(image_path, el["bbox"])
        enriched.append({**el, "text": text})
    return enriched