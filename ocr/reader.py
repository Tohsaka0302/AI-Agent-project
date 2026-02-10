import pytesseract
from PIL import Image
import os

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def read_text(image_path):
    if not image_path or not os.path.exists(image_path):
        print("Image not found")
        return ""

    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    return text
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def read_with_boxes(image_path):
    img = Image.open(image_path)

    data = pytesseract.image_to_data(
        img,
        output_type=pytesseract.Output.DICT
    )

    results = []

    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        if text == "":
            continue

        box = {
            "text": text,
            "x": data["left"][i],
            "y": data["top"][i],
            "w": data["width"][i],
            "h": data["height"][i],
            "conf": data["conf"][i]
        }

        results.append(box)

    return results