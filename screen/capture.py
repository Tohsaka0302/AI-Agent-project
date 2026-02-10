from PIL import ImageGrab
import time
import os

def capture_screen(interval=2):
    project_root = os.path.abspath(os.path.join(__file__, "../../"))
    screenshots_dir = os.path.join(project_root, "screenshots")

    if not os.path.exists(screenshots_dir):
        os.makedirs(screenshots_dir)
        print("Created folder:", screenshots_dir)

    print("📸 Start capturing screen every", interval, "seconds...")
    print("Press CTRL + C to stop")

    while True:
        filename = f"screenshot_{int(time.time())}.png"
        filepath = os.path.join(screenshots_dir, filename)

        img = ImageGrab.grab()
        img.save(filepath)

        print("Saved:", filepath)
        time.sleep(interval)
