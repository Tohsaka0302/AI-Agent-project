"""
screen/url_reader.py – Đọc URL từ browser qua UI Automation (Windows)

Dùng uiautomation để truy cập accessibility tree của browser,
đọc giá trị address bar mà không cần OCR.
"""

import sys

try:
    import uiautomation as auto
    HAS_UIAUTOMATION = True
except ImportError:
    HAS_UIAUTOMATION = False


# ── Browser-specific config ─────────────────────────────────────
# Mỗi browser có cấu trúc accessibility tree khác nhau.
# Dưới đây là config cho các browser phổ biến trên Windows.

BROWSER_CONFIGS = {
    "chrome": {
        "class_name": "Chrome_WidgetWin_1",
        "address_bar_name": "Address and search bar",
    },
    "edge": {
        "class_name": "Chrome_WidgetWin_1",  # Edge dùng Chromium
        "address_bar_name": "Address and search bar",
    },
    "firefox": {
        "class_name": "MozillaWindowClass",
        "address_bar_name": "Search with Google or enter address",
    },
}

# Tên cửa sổ chứa keyword này → detect browser type
BROWSER_KEYWORDS = {
    "chrome":  ["google chrome", "chrome"],
    "edge":    ["microsoft edge", "edge"],
    "firefox": ["mozilla firefox", "firefox"],
}


def _detect_browser_type(window_title: str) -> str | None:
    """Detect browser type từ window title."""
    title_lower = window_title.lower()
    for browser, keywords in BROWSER_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                return browser
    return None


def get_browser_url(window_title: str = None) -> str | None:
    """
    Đọc URL từ address bar của browser đang active.

    Args:
        window_title: Tên cửa sổ browser (None = dùng cửa sổ active)

    Returns:
        URL string hoặc None nếu không đọc được.
    """
    if not HAS_UIAUTOMATION:
        return None

    try:
        # Lấy cửa sổ active
        if window_title:
            # Tìm cửa sổ theo tên
            try:
                window = auto.WindowControl(
                    searchDepth=1,
                    SubName=window_title,
                )
                if not window.Exists(0, 0):
                    return None
            except Exception:
                return None
        else:
            # Dùng foreground window
            window = auto.GetForegroundControl()
            if not window:
                return None

        # Lấy window title để detect browser type
        try:
            title = window.Name or ""
        except Exception:
            title = ""

        browser_type = _detect_browser_type(title)
        if not browser_type:
            return None

        config = BROWSER_CONFIGS.get(browser_type)
        if not config:
            return None

        # Tìm address bar qua accessibility tree
        try:
            address_bar = window.EditControl(
                searchDepth=8,
                Name=config["address_bar_name"],
            )
            if not address_bar.Exists(0, 0):
                # Fallback: tìm bất kỳ EditControl nào có URL pattern
                address_bar = window.EditControl(searchDepth=8)
                if not address_bar.Exists(0, 0):
                    return None
        except Exception:
            return None

        # Đọc giá trị
        try:
            value_pattern = address_bar.GetValuePattern()
            if value_pattern:
                url = value_pattern.Value
                if url:
                    # Một số browser không hiện "https://" prefix
                    if url and not url.startswith(("http://", "https://", "about:", "chrome:", "edge:")):
                        url = "https://" + url
                    return url
        except Exception:
            pass

        # Fallback: thử lấy Name của EditControl
        try:
            name = address_bar.Name
            if name and ("." in name or "/" in name):
                return name
        except Exception:
            pass

        return None

    except Exception as e:
        # Silent fail – không crash nếu UI Automation gặp lỗi
        if "--debug" in sys.argv:
            print(f"  [url_reader] Error: {e}")
        return None
