# 🤖 AI Agent – Ghi và Tái Tạo Thao Tác Web

Công cụ tự động ghi lại thao tác người dùng (chụp màn hình + click/scroll/⌨️ bàn phím real-time), phân tích bằng YOLO/OpenCV + OCR, và tái tạo lại chính xác các thao tác đó trên web.

---

## ✨ Tính năng nổi bật (Agentic RPA)

- **📸 Event-Driven Capture**: Không spam chụp ảnh theo dây chuyền tốn tài nguyên. Hệ thống chỉ chụp và lấy tọa độ con trỏ đúng vào tích tắc xảy ra thao tác Click hoặc Cuộn trang.
- **⏱️ Smart Replay Speed**: Tái tạo thao tác với tốc độ tùy chỉnh (nhanh/chậm) bằng tham số `--speed`, giải phóng bạn khỏi trục thời gian thô cứng khi ghi hình.
- **👁️ AI Visual-Matching**: 
  - Không click mù theo tọa độ gốc (rất dễ xịt nếu web load chậm/sai vị trí).
  - Tự động chụp lại màn hình khi Replay, dùng AI (YOLO/OpenCV + OCR) để tìm đúng nút bấm có chứa Label/Text khớp với lúc ghi, rồi mới click vào tâm.
  - Tự động nín thở đợi quá trình Load Web (tối đa 30s) bằng logic nhận diện Element mà không cần khai báo delay.
- **🌐 Trích xuất nguyên bản URL**: Bắt trực tiếp URL trình duyệt từ tầng native (OS) để so khớp bảo thực trang web đã chuyển hướng đúng mới bắt đầu thao tác, chính xác hơn ngàn lần so với việc dùng AI để đọc chữ trên thanh địa chỉ.

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
pip install pillow pytesseract pyautogui pygetwindow opencv-python pynput keyboard uiautomation
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
│   ├── detector.py       # YOLO detect UI elements + vẽ debug bbox (highlight clicked element)
│   ├── tracker.py        # Phân tích session frame-by-frame
│   ├── replayer.py       # Tái tạo thao tác (element-based, dùng live YOLO+OCR)
│   ├── parser.py         # Detect action từ text OCR
│   └── locator.py        # Tìm vị trí nút Login
├── models/               # Custom YOLO model (nếu có)
└── screenshots/          # Ảnh chụp + session log (tự tạo)
```

---

## 🚀 Hướng dẫn sử dụng

### Bước 1 – Ghi lại thao tác (Event-Driven Capture)

```bash
# Ghi ở chế độ mặc định (chỉ chụp ảnh khi click & scroll)
python main.py record 60

# Ghi ở chế độ cũ (chụp ảnh định kỳ mỗi 1s)
python main.py record 60 --periodic

# Chỉ ghi khi cửa sổ Chrome đang active
python main.py record 60 --window "Chrome"
```

Script chạy các luồng song song:
- 🖱️ Bắt click & scroll **real-time** bằng `pynput.mouse`. Chụp screenshot ngay trước mỗi cú click và lưu URL trình duyệt.
- ⌨️ Bắt **tất cả phím gõ** real-time bằng `pynput.keyboard`.
- (Tùy chọn) 📷 Chụp màn hình mỗi 1 giây nểu bật cờ `--periodic`.

> ⏳ Có đếm ngược 3 giây để bạn kịp chuyển sang browser trước khi bắt đầu.

Kết quả lưu vào `screenshots/session_<id>/`:
- `screenshot_xxxx.png` – các ảnh chụp kèm event
- `mouse.json` – log mọi thao (click + scroll + keypress + url)

---

### Bước 2 – Phân tích session

```bash
python main.py analyze-session
```

- Dùng YOLO (hoặc OpenCV fallback) để detect UI elements
- OCR text trong từng vùng detect được
- Map vị trí click → element gần nhất
- 🖼️ **Lưu ảnh debug** `screenshot_xxxx_yolo.png` với bounding box để xem YOLO nhận diện gì
- 🖱️ **Lưu ảnh debug click** `screenshot_xxxx_click_xxxx.png` — highlight element đã click bằng viền **đỏ** + crosshair **vàng** tại vị trí chuột
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

Replay dùng **visual-matching targeting** (không định thời) và **smart keyboard replay**:

**🖱️ Click**: 
1. `_wait_for_page_ready()`: Check URL hiện tại xem có khớp không (nếu có lưu URL). Sau đó chụp screenshot → YOLO+OCR lấy elements.
2. Tìm element khớp (label + text) → click vào tâm.
3. Nếu không tìm thấy → đợi tiếp (max 30s) tự động canh lúc trang web load xong. Fallback tọa độ gốc nếu timeout.

**⌨️ Phím gõ**:
- Tự động gộp chuỗi IME Tiếng Việt (Telex/UniKey) — không bị nhân đôi ký tự
- Hỗ trợ Unicode (ê, ề, á, ơ...) qua clipboard paste
- Tổ hợp phím cơ bản (Ctrl+A, Ctrl+C, Ctrl+V...) tự động nhận diện và replay bằng `hotkey()`
- Phím đặc biệt (Enter, Tab, F1–F12...): `pyautogui.press()`

> ⚠️ **Hạn chế của Record & Replay Bàn Phím**:
> - Khác với những phím thường, lệnh chuyển cửa sổ như **Alt+Tab** hoặc **Windows+D** không được hỗ trợ tái tạo chuẩn xác.
> - Phím **Tab** đứng một mình vẫn hoạt động bình thường. 
> - Các tổ hợp phím có từ 3 phím trở lên (vd: `Ctrl + Shift + T`) hoặc bấm phím Shift/Alt/Windows rời rạc sẽ bị hệ thống chủ động bỏ qua để tránh lỗi loạn phím.

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
