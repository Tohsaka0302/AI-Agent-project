def detect_actions(text: str):
    text_lower = text.lower()

    actions = {
        "login": False,
        "submit": False,
        "username_field": False,
        "password_field": False,
        "search": False,
    }

    # buttons
    if "login" in text_lower or "log in" in text_lower or "sign in" in text_lower:
        actions["login"] = True

    # password
    if "password" in text_lower:
        actions["password_field"] = True

    # username/email field
    username_keywords = [
        "email",
        "email or phone",
        "phone",
        "username",
        "số điện thoại"
    ]

    for kw in username_keywords:
        if kw in text_lower:
            actions["username_field"] = True
            break

    return actions
