import os
import json
import glob
import shutil


def _session_dir(base: str, session_id) -> str:
    return os.path.join(base, f"session_{session_id}")


def latest_screenshot(base: str = "screenshots"):
    """Trả về ảnh mới nhất trong tất cả session folders."""
    files = glob.glob(os.path.join(base, "session_*", "*.png"))
    if not files:
        return None
    return max(files, key=os.path.getctime)


def load_session(base: str = "screenshots", session_id=None) -> list:
    """
    Đọc mouse.json của session mới nhất (hoặc theo session_id).
    Trả về list events với screenshot path đã được resolve đầy đủ.
    """
    if session_id:
        session_path = _session_dir(base, session_id)
    else:
        folders = sorted(
            glob.glob(os.path.join(base, "session_*")),
            key=os.path.getmtime
        )
        if not folders:
            print("No session found.")
            return []
        session_path = folders[-1]

    log_path = os.path.join(session_path, "mouse.json")
    if not os.path.exists(log_path):
        print(f"No mouse.json in: {session_path}")
        return []

    print(f"📂 Loading session: {session_path}")
    with open(log_path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    # Resolve full path cho screenshot
    for entry in entries:
        if "screenshot" in entry and entry["screenshot"]:
            entry["screenshot"] = os.path.join(session_path, entry["screenshot"])

    return entries


def list_sessions(base: str = "screenshots") -> list:
    """Liệt kê tất cả sessions, thông tin tóm tắt."""
    folders = sorted(glob.glob(os.path.join(base, "session_*")), key=os.path.getmtime)
    sessions = []
    for folder in folders:
        session_id = os.path.basename(folder).replace("session_", "")
        log_path = os.path.join(folder, "mouse.json")

        if not os.path.exists(log_path):
            continue

        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Count screenshots (periodic + event-driven)
        shots   = sum(1 for e in data if e.get("screenshot"))
        clicks  = sum(1 for e in data if e.get("type") == "click")
        scrolls = sum(1 for e in data if e.get("type") in ("scroll", "scroll_start", "scroll_end"))
        keys    = sum(1 for e in data if e.get("type") == "keypress")

        # Tính dung lượng folder
        total_size = sum(
            os.path.getsize(os.path.join(folder, f))
            for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))
        )

        sessions.append({
            "session_id":  session_id,
            "folder":      folder,
            "screenshots": shots,
            "clicks":      clicks,
            "scrolls":     scrolls,
            "keys":        keys,
            "size_mb":     round(total_size / 1024 / 1024, 1),
        })

    return sessions


def delete_session(base: str = "screenshots", session_id=None) -> bool:
    """Xóa toàn bộ folder của session. Trả về True nếu thành công."""
    if not session_id:
        print("Cần truyền session_id.")
        return False

    folder = _session_dir(base, session_id)
    if not os.path.exists(folder):
        print(f"Session không tồn tại: {folder}")
        return False

    shutil.rmtree(folder)
    print(f"🗑️  Đã xóa: {folder}")
    return True


def delete_all_sessions(base: str = "screenshots") -> int:
    """Xóa tất cả sessions. Trả về số lượng đã xóa."""
    folders = glob.glob(os.path.join(base, "session_*"))
    for folder in folders:
        shutil.rmtree(folder)
    print(f"🗑️  Đã xóa {len(folders)} session(s).")
    return len(folders)
