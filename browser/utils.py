"""
browser/utils.py — Session I/O Utilities for Playwright Engine

Handles loading, listing, and deleting Playwright-recorded sessions
stored in the sessions/ directory.
"""

import os
import json
import glob
import shutil


# Default sessions directory
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sessions")


def _session_dir(session_id) -> str:
    return os.path.join(SESSIONS_DIR, f"session_{session_id}")


def find_latest_session() -> str | None:
    """Find the most recent session.json file."""
    pattern = os.path.join(SESSIONS_DIR, "session_*", "session.json")
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load_session(session_path: str = None) -> dict | None:
    """
    Load a session.json file.

    Args:
        session_path: Path to session.json (None = find latest)

    Returns:
        Session dict or None
    """
    if session_path is None:
        session_path = find_latest_session()
        if not session_path:
            print("[utils] No session found.")
            return None

    if not os.path.exists(session_path):
        print(f"[utils] File not found: {session_path}")
        return None

    with open(session_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_sessions() -> list:
    """
    List all Playwright sessions with summary stats.

    Returns:
        List of dicts with session info
    """
    pattern = os.path.join(SESSIONS_DIR, "session_*")
    folders = sorted(glob.glob(pattern), key=os.path.getmtime)
    sessions = []

    for folder in folders:
        session_id = os.path.basename(folder).replace("session_", "")
        session_path = os.path.join(folder, "session.json")

        if not os.path.exists(session_path):
            continue

        try:
            with open(session_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        actions = data.get("actions", [])
        clicks = sum(1 for a in actions if a.get("type") == "click")
        fills = sum(1 for a in actions if a.get("type") == "fill")
        keys = sum(1 for a in actions if a.get("type") in ("keyboard", "hotkey"))
        scrolls = sum(1 for a in actions if a.get("type") == "scroll")
        navs = sum(1 for a in actions if a.get("type") == "navigate")

        # Calculate folder size
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    pass

        sessions.append({
            "session_id": session_id,
            "folder": folder,
            "engine": data.get("engine", "unknown"),
            "browser": data.get("browser", "?"),
            "start_url": data.get("start_url", ""),
            "recorded_at": data.get("recorded_at", ""),
            "total_actions": len(actions),
            "clicks": clicks,
            "fills": fills,
            "keys": keys,
            "scrolls": scrolls,
            "navigations": navs,
            "size_mb": round(total_size / 1024 / 1024, 1),
        })

    return sessions


def delete_session(session_id=None) -> bool:
    """Delete a session folder. Returns True if successful."""
    if not session_id:
        print("Cần truyền session_id.")
        return False

    folder = _session_dir(session_id)
    if not os.path.exists(folder):
        print(f"Session không tồn tại: {folder}")
        return False

    shutil.rmtree(folder)
    print(f"🗑️  Đã xóa: {folder}")
    return True


def delete_all_sessions() -> int:
    """Delete all sessions. Returns count of deleted sessions."""
    pattern = os.path.join(SESSIONS_DIR, "session_*")
    folders = glob.glob(pattern)
    for folder in folders:
        shutil.rmtree(folder)
    print(f"🗑️  Đã xóa {len(folders)} session(s).")
    return len(folders)
