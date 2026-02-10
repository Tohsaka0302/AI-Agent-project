import os

def latest_screenshot(folder="screenshots"):
    if not os.path.exists(folder):
        return None

    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith(".png")
    ]

    if not files:
        return None

    return max(files, key=os.path.getctime)
