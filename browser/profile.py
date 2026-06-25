"""
browser/profile.py — Persistent Browser Profile Helpers

A persistent profile keeps cookies, localStorage, sessionStorage, and IndexedDB
on disk between runs — exactly like a real Chrome profile. This lets the recorder
and replayer start *already logged in* (e.g. to Misa AMIS) without re-entering
credentials every time.

Unlike `browser.new_context()` (ephemeral) or `context.storage_state()` (which
saves cookies + localStorage ONLY — not sessionStorage), a persistent context
preserves the full browser state automatically.

Note: `launch_persistent_context()` returns a BrowserContext directly — there is
no separate Browser object. Use `context.pages[0]` for the initial page and
`context.close()` to tear it down.
"""

import os
import shutil

# Profiles base directory (gitignored — contains cookies/tokens)
PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "profiles")

# Default viewport for persistent contexts
DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}


def profile_path(name: str) -> str:
    """Return the absolute user-data-dir path for a named profile."""
    return os.path.join(PROFILES_DIR, name)


def open_persistent_context(
    p,
    profile_name: str,
    *,
    browser_type: str = "chromium",
    headless: bool = False,
    viewport: dict = None,
):
    """
    Launch (or reuse) a persistent browser context for the given profile.

    Args:
        p:             Active sync_playwright() instance.
        profile_name:  Name of the profile (folder under profiles/).
        browser_type:  "chromium", "firefox", or "webkit".
        headless:      Run without a visible window.
        viewport:      Viewport dict (defaults to 1920x1080).

    Returns:
        A BrowserContext (already logged in if the profile holds a session).
    """
    user_data_dir = profile_path(profile_name)
    os.makedirs(user_data_dir, exist_ok=True)

    launcher = getattr(p, browser_type, p.chromium)
    context = launcher.launch_persistent_context(
        user_data_dir,
        headless=headless,
        viewport=viewport or DEFAULT_VIEWPORT,
        ignore_https_errors=True,
    )
    return context


def list_profiles() -> list:
    """List existing profile names."""
    if not os.path.isdir(PROFILES_DIR):
        return []
    return sorted(
        name for name in os.listdir(PROFILES_DIR)
        if os.path.isdir(os.path.join(PROFILES_DIR, name))
    )


def delete_profile(name: str) -> bool:
    """Delete a profile folder. Returns True if it existed and was removed."""
    path = profile_path(name)
    if not os.path.isdir(path):
        print(f"Profile không tồn tại: {path}")
        return False
    shutil.rmtree(path)
    print(f"🗑️  Đã xóa profile: {path}")
    return True
