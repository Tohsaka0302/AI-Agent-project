# 🤖 AI Agent – Ghi và Tái Tạo Thao Tác Web

Công cụ tự động ghi lại thao tác người dùng trên trình duyệt web và tái tạo lại chính xác các thao tác đó.

**Hai engine có sẵn:**
- 🚀 **Playwright Engine** (mới, khuyến nghị) — Ghi và replay bằng CSS selectors, chính xác 100%, cross-platform
- 🔧 **Legacy Engine** (cũ) — Ghi bằng screenshot + YOLO/OCR, replay bằng pyautogui

---

## ✨ Tính năng — Playwright Engine

- **🎯 CSS Selector Recording**: Ghi lại mọi thao tác (click, fill, keyboard, scroll) kèm CSS selector tự động — không cần YOLO/OCR
- **⌨️ Smart Input Capture**: Tự động bắt giá trị cuối cùng của input field (xử lý IME Tiếng Việt/Telex tự nhiên)
- **🖱️ Click với Fallback**: Mỗi click được ghi với selector chính + fallback selector phòng trường hợp DOM thay đổi
- **⏱️ Auto-Wait**: Playwright tự động đợi element xuất hiện trước khi thao tác — không cần polling thủ công
- **🌐 Cross-Platform**: Chạy trên Windows, macOS, Linux
- **📦 Nhẹ**: Chỉ cần 1 dependency (`playwright`) thay vì ~12 packages

---

## 📋 Yêu cầu hệ thống

- Python 3.9+
- Windows / macOS / Linux

---

## 📦 Cài đặt

```bash
# Cài playwright
pip install playwright

# Tải browser (Chromium)
playwright install chromium

# Tùy chọn: tải thêm Firefox hoặc WebKit
playwright install firefox
playwright install webkit
```

---

## 🗂️ Cấu trúc thư mục

```
AI-Agent-project/
├── main.py               # CLI chính (Playwright + Legacy)
├── injector.js            # DOM event capture script
├── browser/               # 🚀 Playwright engine
│   ├── recorder.py        # CDP-based recording
│   ├── replayer.py        # Playwright action replay
│   └── utils.py           # Session I/O
├── sessions/              # Session data (Playwright)
│   └── session_<id>/
│       ├── session.json   # Action log (CSS selectors)
│       └── screenshots/   # Optional debug screenshots
│
├── screen/                # 🔧 Legacy engine (deprecated)
│   ├── capture.py         # pynput-based recording
│   ├── url_reader.py      # uiautomation URL reading
│   └── utils.py           # Legacy session I/O
├── agent/                 # 🔧 Legacy engine (deprecated)
│   ├── detector.py        # YOLO/OpenCV detection
│   ├── tracker.py         # Session analysis
│   ├── replayer.py        # pyautogui replay
│   ├── parser.py          # Keyword action detection
│   └── locator.py         # Login button locator
├── ocr/                   # 🔧 Legacy engine (deprecated)
│   └── reader.py          # Tesseract OCR
└── screenshots/           # Session data (Legacy)
```

---

## 🚀 Hướng dẫn sử dụng — Playwright Engine

### Bước 1 – Ghi lại thao tác

```bash
# Ghi thao tác trên trang web (mặc định 120 giây)
python main.py record https://example.com

# Ghi với thời gian tùy chỉnh
python main.py record https://example.com 60

# Dùng Firefox thay vì Chromium
python main.py record https://example.com --browser firefox
```

Khi chạy:
- 🖥️ Browser tự động mở và điều hướng đến URL
- 🖱️ Bạn thao tác bình thường (click, gõ chữ, scroll, ...)
- 📋 Mọi thao tác được ghi lại real-time với CSS selectors
- 🛑 Đóng browser hoặc nhấn `Ctrl+C` để dừng

Kết quả lưu vào `sessions/session_<id>/session.json`

---

### Bước 2 – Tái tạo thao tác

```bash
# Replay session mới nhất
python main.py replay

# Xem trước (không thực thi)
python main.py replay --dry-run

# Replay nhanh gấp đôi
python main.py replay --speed 2.0

# Replay trong headless mode (không hiện browser)
python main.py replay --headless
```

Replay sử dụng CSS selectors — Playwright tự động đợi element xuất hiện trước khi thao tác:

- `🖱️ CLICK` → `page.click(selector)` — click bằng selector, không click mù theo tọa độ
- `⌨️ FILL` → `page.fill(selector, value)` — điền giá trị vào input
- `⌨️ KEY` → `page.keyboard.press(key)` — nhấn phím đặc biệt (Enter, Tab, ...)
- `⌨️ HOTKEY` → `page.keyboard.press("Control+a")` — tổ hợp phím
- `🖱️ SCROLL` → `page.mouse.wheel(dx, dy)` — cuộn trang
- `📋 SELECT` → `page.select_option(value)` — chọn dropdown
- `🌐 NAV` → `page.goto(url)` — điều hướng trang

---

## 🔐 Giữ phiên đăng nhập (Misa AMIS, ...)

Để tự động hoá trên một **tài khoản đã đăng nhập** (ví dụ Misa AMIS) mà không phải
đăng nhập lại mỗi lần, dùng **persistent profile**. Profile lưu cookies, localStorage,
sessionStorage trên đĩa giống hệt một profile Chrome thật.

> ⚠️ `storage_state()` của Playwright **chỉ** lưu cookies + localStorage, **không** lưu
> sessionStorage. Persistent profile thì lưu đầy đủ — nên tin cậy hơn cho app SSO/kế toán.

### Bước 1 – Đăng nhập một lần
```bash
# Mở browser, bạn tự đăng nhập (kể cả OTP/captcha), rồi nhấn Enter để lưu
python main.py login --profile misa
# Tuỳ chọn URL đăng nhập khác:
python main.py login --profile misa --url https://amisapp.misa.vn/
```

### Bước 2 – Ghi / replay khi đã đăng nhập
```bash
# Ghi thao tác — trang mở ra đã đăng nhập sẵn
python main.py record https://amisapp.misa.vn --profile misa

# Replay — dùng lại đúng phiên đăng nhập đó
python main.py replay --profile misa
```

Session ghi với `--profile` sẽ tự nhớ profile, nên `python main.py replay` (không cờ)
cũng tự dùng lại profile đã ghi.

> Khi phiên trên server của Misa hết hạn, trang sẽ quay về màn hình đăng nhập —
> chỉ cần chạy lại `python main.py login --profile misa`.

---

## 🛠️ Các lệnh

### Playwright Engine (mới)
```bash
python main.py login [--profile name] [--url login_url]   # Đăng nhập 1 lần, lưu profile
python main.py record <url> [duration] [--profile name] [--browser chromium|firefox|webkit]
python main.py replay [--speed X] [--headless] [--dry-run] [--profile name]
python main.py sessions          # Liệt kê tất cả sessions
python main.py profiles          # Liệt kê login profiles
python main.py clean <id|all>            # Xóa sessions
python main.py clean-profile <name|all>  # Xóa login profile(s)
```

### Legacy Engine (cũ)
```bash
python main.py record-legacy [duration] [--periodic] [--window "Title"]
python main.py analyze-session   # YOLO + OCR analysis
python main.py replay-legacy [url] [--speed X] [--dry-run]
python main.py ocr-latest        # OCR ảnh mới nhất
python main.py sessions          # Cũng liệt kê legacy sessions
```

---

## 📊 So sánh hai Engine

| Tính năng | Playwright (mới) | Legacy (cũ) |
|---|---|---|
| Element detection | CSS selectors (100% chính xác) | YOLO + OCR (không ổn định) |
| Click targeting | Selector-based | Pixel coordinates + visual matching |
| Keyboard input | Native Unicode | Clipboard hack (Windows only) |
| URL detection | `page.url` | `uiautomation` (Windows only) |
| Vietnamese IME | Tự động xử lý | IME collapsing logic phức tạp |
| Page wait | Auto-wait built-in | Custom polling 0.5s × 60s |
| Dependencies | 1 package | ~12 packages (~1.5GB) |
| Cross-platform | ✅ | Windows chính, macOS hạn chế |
| Scope | Browser only | Mọi app trên màn hình |

---

## ⚠️ Lưu ý

- **Playwright Engine** chỉ hoạt động trong browser do Playwright kiểm soát. Nếu cần ghi thao tác trên ứng dụng desktop khác, dùng Legacy Engine.
- Khi ghi, browser do Playwright mở — bạn thao tác trực tiếp trên browser đó.
- CSS selectors được tạo tự động với fallback chain: `id → data-testid → name → text → aria-label → nth-child`
