# 🤖 AI Agent – Ghi và Tái Tạo Thao Tác Web

Công cụ tự động ghi lại thao tác người dùng trên trình duyệt (chụp màn hình + bắt click/scroll/⌨️ bàn phím real-time), phân tích bằng YOLO + OCR, và tái tạo lại các thao tác đó bằng Python.

---

## 📋 Yêu cầu hệ thống

- Python 3.9+
- Windows (khuyến nghị) / macOS / Linux
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) đã được cài đặt

### Cài đặt Tesseract (Windows)
1. Tải về tại: https://github.com/UB-Mannheim/tesseract/wiki
2. Cài đặt → tích chọn **"Add to PATH"** trong installer

---

## 📦 Cài đặt Python packages

```bash
pip install pillow pytesseract pyautogui pygetwindow opencv-python pynput keyboard
```

Nếu muốn dùng YOLO thật (chính xác hơn):
```bash
pip install ultralytics
```

---

## 🗂️ Cấu trúc thư mục

```
AI-Agent-project/
├── main.py               # CLI chính
├── yolov8n.pt            # YOLOv8 nano model
├── screen/
│   ├── capture.py        # Ghi session (3 thread: ảnh + mouse + ⌨️ bàn phím)
│   └── utils.py          # Load/list session
├── ocr/
│   └── reader.py         # Tesseract OCR theo vùng
├── agent/
│   ├── detector.py       # YOLO detect UI elements + vẽ debug bbox
│   ├── tracker.py        # Phân tích session frame-by-frame
│   ├── replayer.py       # Tái tạo thao tác (element-based, dùng live YOLO+OCR)
│   ├── parser.py         # Detect action từ text OCR
│   └── locator.py        # Tìm vị trí nút Login
├── models/               # Custom YOLO model (nếu có)
└── screenshots/          # Ảnh chụp + session log (tự tạo)
```

---

## 🚀 Hướng dẫn sử dụng

### Bước 1 – Ghi lại thao tác

```bash
# Ghi 1 giây/lần trong 60 giây
python main.py record 1 60

# Chỉ ghi khi cửa sổ Chrome đang active
python main.py record 1 60 --window "Chrome"
```

Script chạy **3 luồng song song**:
- 📷 Chụp màn hình mỗi 1 giây (để nhận diện UI)
- 🖱️ Bắt click & scroll **real-time** bằng `pynput.mouse`
- ⌨️ Bắt **tất cả phím gõ** real-time bằng `pynput.keyboard`

> ⏳ Có đếm ngược 3 giây để bạn kịp chuyển sang browser trước khi bắt đầu.

Kết quả lưu vào `screenshots/session_<id>/`:
- `screenshot_xxxx.png` – ảnh chụp mỗi giây
- `mouse.json` – tất cả events (screenshot + click + scroll + **keypress**)

---

### Bước 2 – Phân tích session

```bash
python main.py analyze-session
```

- Dùng YOLO (hoặc OpenCV fallback) để detect UI elements
- OCR text trong từng vùng detect được
- Map vị trí click → element gần nhất
- 🖼️ **Lưu ảnh debug** `screenshot_xxxx_yolo.png` với bounding box để xem YOLO nhận diện gì
- Lưu kết quả phân tích ra `analysis.json`

---

### Bước 3 – Tái tạo thao tác

```bash
# Tái tạo thao tác từ session mới nhất
python main.py replay

# Xem trước (không di chuột thật)
python main.py replay --dry-run

# Tái tạo thật, mở URL trước
python main.py replay https://example.com

# Tái tạo nhanh gấp đôi
python main.py replay --speed 2.0
```

Replay dùng **element-based targeting** và **smart keyboard replay**:

**🖱️ Click**: Chụp screenshot hiện tại → YOLO+OCR detect elements → tìm element khớp (label + text) → click vào vị trí element mới. Nếu không tìm thấy → fallback tọa độ gốc.

**⌨️ Phím gõ**:
- Tự động gộp chuỗi IME Tiếng Việt (Telex/UniKey) — không bị nhân đôi ký tự
- Hỗ trợ Unicode (ê, ề, á, ơ...) qua clipboard paste
- Tổ hợp phím (Ctrl+A, Ctrl+C, Ctrl+V...) tự động nhận diện và replay bằng `hotkey()`
- Phím đặc biệt (Enter, Tab, F1–F12...): `pyautogui.press()`

**↕️ Scroll**: replay theo tọa độ gốc

Console sẽ hiển thị:
- `[IME] Collapsed X IME intermediate events` — đã gộp chuỗi IME
- `[MODS] X hotkey combos detected` — đã nhận diện tổ hợp phím
- `✅ LIVE [button] 'Login'` — click vào element trên màn hình hiện tại
- `⚠️ FALLBACK` — dùng tọa độ gốc
- `⌨️ HOTKEY ctrl+a` — replay tổ hợp phím

> ⚠️ Di chuột vào **góc trên-trái** màn hình để dừng khẩn cấp.

---

## 🛠️ Các lệnh khác

```bash
python main.py sessions      # Liệt kê tất cả session đã ghi
python main.py ocr-latest    # OCR ảnh mới nhất
python main.py analyze       # Phân tích action từ ảnh mới nhất
python main.py locate        # Tìm nút Login trong ảnh mới nhất
```
