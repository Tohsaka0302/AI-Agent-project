def find_login_button(boxes):
    for box in boxes:
        text = box["text"].lower()
        if text in ["login", "log", "in", "log in", "sign in"]:
            return box
    return None
