import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from screen.capture import capture_screen
from screen.utils import latest_screenshot
from ocr.reader import read_text, read_with_boxes
from agent.parser import detect_actions
from agent.locator import find_login_button


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(" python main.py capture [interval]")
        print(" python main.py ocr-latest")
        print(" python main.py analyze")
        print(" python main.py locate")
        return

    cmd = sys.argv[1]

    if cmd == "capture":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 2
        capture_screen(interval)

    elif cmd == "ocr-latest":
        img = latest_screenshot()
        print("Latest image:", img)

        text = read_text(img)
        print("===== OCR RESULT =====")
        print(text)

        actions = detect_actions(text)
        print("===== DETECTED ACTIONS =====")
        for k, v in actions.items():
            print(f"{k}: {v}")

    elif cmd == "analyze":
        img = latest_screenshot()
        print("Analyzing:", img)

        text = read_text(img)
        print("===== OCR TEXT =====")
        print(text)

        actions = detect_actions(text)
        print("===== DETECTED ACTIONS =====")
        for k, v in actions.items():
            print(f"{k}: {v}")

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

    else:
        print("Unknown command")


if __name__ == "__main__":
    main()
