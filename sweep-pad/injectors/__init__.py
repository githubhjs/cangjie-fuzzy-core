"""Standard-library keyboard injectors; importing this module never injects input."""
import math
import sys


def validate(text, delay_ms):
    if not isinstance(text, str) or any(c not in "abcdefghijklmnopqrstuvwxyz '" for c in text):
        raise ValueError("key injection accepts lowercase ASCII letters, space, and apostrophe")
    if isinstance(delay_ms, bool) or not isinstance(delay_ms, (int, float)) or not math.isfinite(delay_ms) or delay_ms < 0:
        raise ValueError("delay_ms must be a finite non-negative number")


def get_injector(platform=None):
    platform = platform or sys.platform
    if platform == "win32":
        from . import windows
        return windows
    if platform == "darwin":
        from . import macos
        return macos
    if platform.startswith("linux"):
        from . import linux
        return linux
    raise RuntimeError("Unsupported platform: " + platform)
