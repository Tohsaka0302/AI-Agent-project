# 🔄 Migration Plan: OS-Level → Playwright

> **Goal**: Replace the entire YOLO/OCR/pyautogui/pynput stack with Playwright for all 3 phases (Record → Analyze → Replay), making the agent browser-native, cross-platform, and dramatically more reliable.

---

## 📋 Table of Contents

1. [Why Migrate](#1-why-migrate)
2. [Architecture: Before vs After](#2-architecture-before-vs-after)
3. [New Directory Structure](#3-new-directory-structure)
4. [Phase 1 — Record (CDP Tracing)](#4-phase-1--record-cdp-tracing)
5. [Phase 2 — Analyze (Mostly Eliminated)](#5-phase-2--analyze-mostly-eliminated)
6. [Phase 3 — Replay (Playwright Actions)](#6-phase-3--replay-playwright-actions)
7. [CLI Changes (main.py)](#7-cli-changes-mainpy)
8. [Migration Per-File Breakdown](#8-migration-per-file-breakdown)
9. [Dependencies: Old vs New](#9-dependencies-old-vs-new)
10. [Implementation Order](#10-implementation-order)
11. [Risk & Rollback Strategy](#11-risk--rollback-strategy)

---

## 1. Why Migrate

| Problem (Current) | Solution (Playwright) |
|---|---|
| YOLO general model (`yolov8n.pt`) not trained for UI → inaccurate element detection | DOM-level selectors → 100% accurate |
| Tesseract OCR unreliable on low-res/styled text | No OCR needed — read text directly from DOM |
| `pyautogui` clicks blind pixel coords → breaks on layout shift | `page.click(selector)` → resilient to layout changes |
| `uiautomation` for URL reading is Windows-only and fragile | `page.url` — built-in, cross-platform |
| `PIL.ImageGrab` Windows/macOS only | `page.screenshot()` — cross-platform |
| `ctypes` clipboard hack for Unicode typing | `page.keyboard.type()` — handles Unicode natively |
| Complex IME collapsing logic for Vietnamese | Playwright types final composed text directly |
| ~12 dependencies, many Windows-specific | 1 dependency: `playwright` |

---

## 2. Architecture: Before vs After

### Before (OS-Level)
```
User actions on browser (any browser, any window)
        │
        ▼
  capture.py ── pynput (mouse+keyboard listeners)
  │              PIL.ImageGrab (screenshots)
  │              uiautomation (URL reading)
  │              pygetwindow (window filtering)
  │
  └──► screenshots/session_<id>/
       ├── screenshot_XXXX.png
       └── mouse.json (mixed events: click, scroll, keypress)
                │
                ▼
         tracker.py ── detector.py (YOLO/OpenCV → bounding boxes)
                       reader.py (Tesseract OCR → text)
                │
                └──► analysis.json
                        │
                        ▼
                  replayer.py ── pyautogui (mouse/keyboard automation)
                                 PIL.ImageGrab (live screenshots)
                                 YOLO+OCR (live element detection)
                                 ctypes (clipboard for Unicode)
```

### After (Playwright)
```
User actions on Playwright-controlled browser (Chromium/Firefox/WebKit)
        │
        ▼
  recorder.py ── CDP Protocol (automatic action capture)
  │               page.on('click'), page.on('input'), etc.
  │               Captures CSS selectors + action metadata
  │
  └──► sessions/session_<id>/
       ├── session.json (structured action log with selectors)
       ├── screenshots/ (optional, for debugging)
       └── trace.zip (optional Playwright trace)
                │
                ▼
         (No analyze step needed — selectors already captured)
                │
                ▼
           replayer.py ── playwright.sync_api
                          page.click(selector)
                          page.fill(selector, text)
                          page.keyboard.type(text)
                          page.mouse.wheel(dx, dy)
```

> **Key insight**: The "Analyze" phase (YOLO+OCR detection → element mapping) is almost entirely eliminated because Playwright captures DOM selectors directly during recording. The intermediate `analysis.json` step becomes unnecessary.

---

## 3. New Directory Structure

```
AI-Agent-project/
├── main.py                    # [MODIFY] New CLI commands
├── browser/                   # [NEW] Replaces screen/ + agent/
│   ├── __init__.py
│   ├── recorder.py            # [NEW] CDP-based recording
│   ├── replayer.py            # [NEW] Playwright-based replay
│   └── utils.py               # [NEW] Session I/O (simplified)
├── sessions/                  # [NEW] Replaces screenshots/
│   └── session_<id>/
│       ├── session.json       # Action log (selectors + metadata)
│       ├── screenshots/       # Optional debug screenshots
│       └── trace.zip          # Optional Playwright trace
├── injector.js                # [NEW] DOM event capture script
│
│── screen/                    # [KEEP for now, deprecated]
│   ├── capture.py             # Deprecated — replaced by browser/recorder.py
│   ├── url_reader.py          # Deprecated — replaced by page.url
│   └── utils.py               # Partially reused for legacy session listing
├── agent/                     # [KEEP for now, deprecated]
│   ├── detector.py            # Deprecated — no YOLO/OpenCV needed
│   ├── tracker.py             # Deprecated — no analysis step needed
│   ├── replayer.py            # Deprecated — replaced by browser/replayer.py
│   ├── parser.py              # Deprecated
│   └── locator.py             # Deprecated
├── ocr/                       # [KEEP for now, deprecated]
│   └── reader.py              # Deprecated — no Tesseract OCR needed
├── yolov8n.pt                 # Can be removed after migration
├── models/                    # Can be removed after migration
└── requirements.txt           # [NEW] Clean dependency list
```

---

## 4. Phase 1 — Record (CDP Tracing)

### Current Approach
- `pynput.mouse.Listener` + `pynput.keyboard.Listener` for events
- `PIL.ImageGrab.grab()` for screenshots
- `uiautomation` for URL reading
- Manual event log to `mouse.json`

### New Approach: `browser/recorder.py`

Playwright controls the browser via CDP (Chrome DevTools Protocol). We inject a JavaScript snippet into every page that listens to DOM events and reports them back to Python.

#### Core Strategy

```python
from playwright.sync_api import sync_playwright

def record_session(url: str, duration: int = 60, browser_type: str = "chromium"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Visible browser
        context = browser.new_context()

        # Optional: enable Playwright tracing for full replay
        context.tracing.start(screenshots=True, snapshots=True)

        page = context.new_page()
        page.goto(url)

        actions = []

        # Inject DOM event listeners via JavaScript
        page.evaluate(INJECTOR_JS)

        # Listen to events from injected script via page.expose_function
        page.expose_function("__pw_record_action", lambda action: actions.append(action))

        # Wait for user interaction (duration or manual stop)
        # ...

        context.tracing.stop(path="trace.zip")
        browser.close()

    return actions
```

#### What the Injector Script Captures

The injected JavaScript (`injector.js`) listens to these DOM events and reports back:

| DOM Event | Captured Data |
|---|---|
| `click` | CSS selector, element tag, text content, coordinates, timestamp |
| `input` / `change` | CSS selector, input value, input type |
| `keydown` | Key name, modifiers (ctrl/shift/alt), target selector |
| `scroll` | Scroll position (scrollTop, scrollLeft), target element |
| `submit` | Form selector, form data |
| Navigation | URL changes via `popstate` / `hashchange` |

#### CSS Selector Generation Strategy

For each interacted element, generate a **robust CSS selector** with fallback chain:

1. `#id` — if element has a unique ID
2. `[data-testid="..."]` — if test attributes exist
3. `[name="..."]` — for form fields
4. `button:has-text("Login")` — Playwright text selectors
5. `nth-child` path — as absolute fallback

```javascript
// injector.js — selector generation (simplified)
function getSelector(el) {
    // Priority 1: id
    if (el.id) return `#${CSS.escape(el.id)}`;

    // Priority 2: data-testid
    if (el.dataset.testid) return `[data-testid="${el.dataset.testid}"]`;

    // Priority 3: name attribute (inputs)
    if (el.name) return `${el.tagName.toLowerCase()}[name="${el.name}"]`;

    // Priority 4: role + text
    const text = el.textContent?.trim().slice(0, 50);
    if (text && ['BUTTON', 'A', 'LABEL'].includes(el.tagName)) {
        return `${el.tagName.toLowerCase()}:has-text("${text}")`;
    }

    // Priority 5: unique attribute combo
    // ... (aria-label, placeholder, type, class)

    // Fallback: nth-child path
    return buildNthChildPath(el);
}
```

#### Session Output Format (`session.json`)

```json
{
  "version": 2,
  "engine": "playwright",
  "browser": "chromium",
  "start_url": "https://example.com/login",
  "recorded_at": "2026-06-01T12:00:00Z",
  "viewport": { "width": 1920, "height": 1080 },
  "actions": [
    {
      "type": "click",
      "timestamp": 1717228800.123,
      "selector": "button:has-text('Login')",
      "fallback_selector": "#login-btn",
      "tag": "BUTTON",
      "text": "Login",
      "position": { "x": 500, "y": 300 },
      "url": "https://example.com/login",
      "screenshot": "screenshots/0001_click.png"
    },
    {
      "type": "fill",
      "timestamp": 1717228802.456,
      "selector": "input[name='email']",
      "value": "user@example.com",
      "url": "https://example.com/login"
    },
    {
      "type": "keyboard",
      "timestamp": 1717228803.789,
      "key": "Tab"
    },
    {
      "type": "fill",
      "timestamp": 1717228805.012,
      "selector": "input[name='password']",
      "value": "***",
      "url": "https://example.com/login"
    },
    {
      "type": "keyboard",
      "timestamp": 1717228806.345,
      "key": "Enter"
    },
    {
      "type": "scroll",
      "timestamp": 1717228810.678,
      "deltaX": 0,
      "deltaY": -300,
      "url": "https://example.com/dashboard"
    },
    {
      "type": "navigate",
      "timestamp": 1717228815.901,
      "url": "https://example.com/dashboard",
      "previous_url": "https://example.com/login"
    }
  ]
}
```

> **Key difference**: Actions now carry **CSS selectors** instead of pixel coordinates + YOLO-detected labels. This is the fundamental shift that eliminates the entire Analyze phase.

#### Keyboard Recording — Simplified

| Current Problem | Playwright Solution |
|---|---|
| IME composition (UniKey/Telex) creates `·` markers + backspaces | Playwright captures the **final composed text** from `input`/`change` events via DOM — no IME artifacts |
| Control chars `\x01-\x1a` need manual mapping | Playwright reports `Ctrl+A` etc. directly via `keydown` event with `event.ctrlKey` |
| Standalone modifier keys need filtering | Injector only reports key events with actual character output or known special keys |

So `_collapse_ime_sequences()` and `_process_modifiers_and_combos()` from the old `replayer.py` are **completely eliminated**.

#### Screenshot Strategy (Optional)

Screenshots become optional debugging artifacts, not required for element detection:
- Take a screenshot after each click (for visual verification)
- Save to `sessions/session_<id>/screenshots/`
- Not used during replay (selectors replace visual matching)

---

## 5. Phase 2 — Analyze (Mostly Eliminated)

### Current Approach
- `tracker.py` loops through `mouse.json` events
- For each click: find nearest screenshot → YOLO detect → OCR text → map click to element
- Output: `analysis.json` with `nearest_element` for each event

### New Approach: **No separate analyze step needed**

Because the recording phase already captures CSS selectors, the data is immediately ready for replay. The `analysis.json` intermediate format is **eliminated**.

However, we add a lightweight **validation** command that:
1. Opens the target URL
2. Checks if each selector from `session.json` still resolves to an element
3. Reports which actions might fail during replay

```python
# browser/validator.py (optional)
def validate_session(session_path: str, url: str):
    """Check if recorded selectors still exist on the page."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        for action in session["actions"]:
            if "selector" in action:
                exists = page.locator(action["selector"]).count() > 0
                status = "✅" if exists else "❌"
                print(f"  {status} {action['type']} → {action['selector']}")

        browser.close()
```

---

## 6. Phase 3 — Replay (Playwright Actions)

### Current Approach (`agent/replayer.py` — 654 lines)
1. Load `analysis.json`
2. For each click: `_wait_for_page_ready()` → screenshot → YOLO+OCR → match element → `pyautogui.click()`
3. For keyboard: IME collapse → modifier processing → `pyautogui.typewrite()` / clipboard hack
4. For scroll: `pyautogui.scroll()` at pixel coordinates

### New Approach: `browser/replayer.py` (~150 lines)

```python
from playwright.sync_api import sync_playwright
import time

def replay_session(
    session_path: str,
    url: str = None,
    speed: float = 1.0,
    headless: bool = False,
    dry_run: bool = False,
):
    session = load_session(session_path)
    actions = session["actions"]
    start_url = url or session.get("start_url")

    if dry_run:
        _dry_run_report(actions, start_url)
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport=session.get("viewport", {"width": 1920, "height": 1080})
        )
        page = context.new_page()
        page.goto(start_url, wait_until="domcontentloaded")

        prev_timestamp = None

        for i, action in enumerate(actions):
            # Delay between actions (respects original timing)
            if prev_timestamp and speed > 0:
                delay = (action["timestamp"] - prev_timestamp) / speed
                delay = max(0.05, min(delay, 10.0))
                time.sleep(delay)

            action_type = action["type"]

            if action_type == "click":
                selector = action["selector"]
                print(f"  [{i+1:03d}] 🖱️  CLICK → {selector}")
                page.locator(selector).first.click(timeout=30000)

            elif action_type == "fill":
                selector = action["selector"]
                value = action["value"]
                print(f"  [{i+1:03d}] ⌨️  FILL  → {selector} = '{value[:20]}'")
                page.locator(selector).first.fill(value, timeout=30000)

            elif action_type == "keyboard":
                key = action["key"]
                print(f"  [{i+1:03d}] ⌨️  KEY   → {key}")
                page.keyboard.press(key)

            elif action_type == "scroll":
                dy = action.get("deltaY", 0)
                dx = action.get("deltaX", 0)
                print(f"  [{i+1:03d}] 🖱️  SCROLL {'↑' if dy < 0 else '↓'}")
                page.mouse.wheel(dx, dy)

            elif action_type == "navigate":
                target_url = action["url"]
                print(f"  [{i+1:03d}] 🌐 NAV  → {target_url[:60]}")
                page.goto(target_url, wait_until="domcontentloaded")

            prev_timestamp = action["timestamp"]

        print("\n✅ Replay complete!")
        browser.close()
```

### What Gets Eliminated

| Old Code | Lines | Replaced By |
|---|---|---|
| `_wait_for_page_ready()` polling loop | ~60 lines | `page.locator(selector).click(timeout=30000)` — Playwright auto-waits |
| `_capture_current_screen()` + `_detect_live_elements()` | ~20 lines | Not needed — selectors, not visual matching |
| `_find_matching_element()` fuzzy scoring | ~40 lines | Exact selector matching |
| `_clipboard_type()` Windows ctypes hack | ~40 lines | `page.keyboard.type()` |
| `_collapse_ime_sequences()` | ~60 lines | Not needed — recording captures final text |
| `_process_modifiers_and_combos()` | ~50 lines | Not needed — recording captures proper key names |
| `KEY_MAP` (pynput → pyautogui) | ~25 lines | Playwright uses standard key names directly |

**Old replayer**: 654 lines → **New replayer**: ~150 lines

---

## 7. CLI Changes (`main.py`)

### New Commands

```
╔══════════════════════════════════════════════════════════════╗
║              AI Agent – Playwright Web Recorder & Replayer  ║
╠══════════════════════════════════════════════════════════════╣
║  RECORDING                                                   ║
║    record <url> [duration] [--browser chromium|firefox]       ║
║      Opens browser, records all actions until duration/Ctrl+C ║
║      Ví dụ: python main.py record https://example.com 60     ║
║                                                               ║
║  REPLAY                                                       ║
║    replay [--speed 1.0] [--headless] [--dry-run]              ║
║      Replays latest session                                   ║
║      Ví dụ: python main.py replay --speed 2.0                 ║
║                                                               ║
║  VALIDATION (optional)                                        ║
║    validate [url]                                             ║
║      Checks if selectors from latest session are still valid  ║
║                                                               ║
║  SESSION MANAGEMENT                                           ║
║    sessions              List all sessions                    ║
║    clean <id|all>         Delete sessions                     ║
║                                                               ║
║  LEGACY (old OS-level engine, deprecated)                     ║
║    record-legacy [duration] [--periodic] [--window "T"]       ║
║    analyze-session                                            ║
║    replay-legacy [url] [--speed] [--dry-run]                  ║
╚══════════════════════════════════════════════════════════════╝
```

### Argument Changes

| Old Command | New Command | Notes |
|---|---|---|
| `record 60` | `record https://example.com 60` | URL is now required (Playwright needs to open the page) |
| `analyze-session` | *(removed)* | No longer needed |
| `replay [url]` | `replay` | URL auto-read from `session.json` |
| `replay --dry-run` | `replay --dry-run` | Same |
| `replay --speed 2.0` | `replay --speed 2.0` | Same |
| *(new)* | `replay --headless` | Run replay in headless browser (for CI/testing) |
| *(new)* | `validate` | Check selector validity |
| `record 60 --window "Chrome"` | *(removed)* | Not needed — Playwright controls its own browser |
| `record 60 --periodic` | *(removed)* | Not needed — event-driven by default via DOM |

---

## 8. Migration Per-File Breakdown

### Files to CREATE

| File | Purpose | Est. Lines |
|---|---|---|
| `browser/__init__.py` | Package init | 1 |
| `browser/recorder.py` | CDP-based recording engine | ~200 |
| `browser/replayer.py` | Playwright action replay | ~150 |
| `browser/utils.py` | Session I/O (load, list, delete) | ~80 |
| `injector.js` | DOM event capture script | ~200 |
| `requirements.txt` | New dependency list | ~5 |

### Files to MODIFY

| File | Changes |
|---|---|
| `main.py` | New CLI commands, import `browser/` modules, keep legacy commands with `-legacy` suffix |

### Files to DEPRECATE (keep but don't use)

| File | Why Deprecated |
|---|---|
| `screen/capture.py` | Replaced by `browser/recorder.py` |
| `screen/url_reader.py` | Replaced by `page.url` |
| `screen/utils.py` | Replaced by `browser/utils.py` (for new sessions) |
| `agent/detector.py` | YOLO/OpenCV no longer needed |
| `agent/tracker.py` | Analysis step eliminated |
| `agent/replayer.py` | Replaced by `browser/replayer.py` |
| `agent/parser.py` | Keyword detection no longer needed |
| `agent/locator.py` | Login button locator no longer needed |
| `ocr/reader.py` | Tesseract OCR no longer needed |
| `yolov8n.pt` | YOLO model no longer needed |

---

## 9. Dependencies: Old vs New

### Old (`pip install`)
```
pillow              # Screenshots (ImageGrab)
pytesseract         # OCR
pyautogui           # Mouse/keyboard automation
pygetwindow         # Window title detection
pynput              # Real-time input listeners
opencv-python       # Fallback element detection
uiautomation        # Windows URL reading
ultralytics         # YOLOv8 (~300MB with PyTorch)
keyboard            # (listed in README, used for hotkeys)
```

**Total installed footprint**: ~1.5GB+ (PyTorch alone is ~800MB)

### New (`pip install`)
```
playwright          # Everything: browser control, selectors, screenshots, keyboard, mouse
```

**Total installed footprint**: ~150MB (browser binaries downloaded separately via `playwright install`)

### Setup
```bash
pip install playwright
playwright install chromium    # Download Chromium browser (~150MB)
# Optional:
playwright install firefox
playwright install webkit
```

---

## 10. Implementation Order

### Step 1: Setup & Skeleton (30 min)
- [ ] Create `browser/` package with `__init__.py`
- [ ] Create `requirements.txt` with `playwright`
- [ ] Install playwright and browser binaries
- [ ] Verify basic Playwright works: open a page, take screenshot

### Step 2: Injector Script (1-2 hours)
- [ ] Write `injector.js` — DOM event listeners for click, input, keydown, scroll
- [ ] Implement CSS selector generation with fallback chain
- [ ] Test injector on various websites (forms, SPAs, multi-page)

### Step 3: Recorder (1-2 hours)
- [ ] Implement `browser/recorder.py`
- [ ] Launch browser, inject script, capture events via `page.expose_function()`
- [ ] Save session to `sessions/session_<id>/session.json`
- [ ] Optional: screenshot capture after each click
- [ ] Optional: Playwright tracing

### Step 4: Replayer (1 hour)
- [ ] Implement `browser/replayer.py`
- [ ] Map action types to Playwright API calls
- [ ] Handle auto-wait (Playwright's built-in selector waiting)
- [ ] Handle navigation events
- [ ] Support `--speed`, `--dry-run`, `--headless`

### Step 5: Session Utils (30 min)
- [ ] Implement `browser/utils.py` — load, list, delete sessions
- [ ] Support both old (`screenshots/`) and new (`sessions/`) directories

### Step 6: CLI Integration (30 min)
- [ ] Update `main.py` with new commands
- [ ] Keep legacy commands under `-legacy` suffix
- [ ] Update help text

### Step 7: Validation & Testing (1 hour)
- [ ] Test record+replay on a login form
- [ ] Test record+replay on a scrollable page
- [ ] Test Vietnamese IME input (should work without any special handling)
- [ ] Test cross-page navigation
- [ ] Implement optional `validate` command

### Step 8: Documentation (30 min)
- [ ] Update `README.md`
- [ ] Update `MEMORY.md`
- [ ] Add migration notes

**Estimated total effort: 6-8 hours**

---

## 11. Risk & Rollback Strategy

### Risks

| Risk | Mitigation |
|---|---|
| Playwright can't record actions on already-open browser | User must start recording first, then navigate. Alternatively, connect to existing browser via `connect_over_cdp()` |
| CSS selectors may break across website updates | Fallback selector chain (id → data-testid → text → nth-child) |
| Some websites block Playwright (bot detection) | Use `playwright-stealth` plugin or launch with `--disable-blink-features=AutomationControlled` |
| User is used to recording any window (not just browser) | Keep legacy commands available. Document trade-off clearly |
| Playwright tracing generates large files | Make tracing optional (off by default) |

### Rollback

All old code is **kept in place** (deprecated but functional). Users can always fall back to:
```bash
python main.py record-legacy 60
python main.py analyze-session
python main.py replay-legacy
```

The old modules (`screen/`, `agent/`, `ocr/`) are not deleted. They can be removed in a future cleanup pass once the Playwright engine is proven stable.

---

## Appendix: Playwright API Cheatsheet (for this project)

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Launch visible browser
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    # Navigate
    page.goto("https://example.com")
    print(page.url)                           # ← replaces uiautomation

    # Click (auto-waits for element)
    page.click("button:has-text('Login')")     # ← replaces YOLO+OCR+pyautogui

    # Fill input
    page.fill("input[name='email']", "user@example.com")  # ← replaces pyautogui.typewrite

    # Keyboard
    page.keyboard.press("Enter")              # ← replaces KEY_MAP + pyautogui.press
    page.keyboard.type("Xin chào")            # ← replaces _clipboard_type (Unicode)

    # Scroll
    page.mouse.wheel(0, -300)                 # ← replaces pyautogui.scroll

    # Screenshot
    page.screenshot(path="debug.png")          # ← replaces PIL.ImageGrab

    # Wait for element (replaces _wait_for_page_ready)
    page.wait_for_selector("#dashboard", timeout=30000)

    # Expose function (for recording)
    page.expose_function("callback", lambda data: print(data))
    page.evaluate("document.addEventListener('click', e => callback(e.target.tagName))")

    browser.close()
```
