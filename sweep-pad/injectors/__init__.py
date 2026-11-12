"""Standard-library keyboard injectors; importing this module never injects input."""
import math
import sys


def validate(text, delay_ms):
    if not isinstance(text, str) or any(c not in "abcdefghijklmnopqrstuvwxyz '" for c in text):
        raise ValueError("key injection accepts lowercase ASCII letters, space, and apostrophe")
    if isinstance(delay_ms, bool) or not isinstance(delay_ms, (int, float)) or not math.isfinite(delay_ms) or delay_ms < 0:
        raise ValueError("delay_ms must be a finite non-negative number")


COMMIT_MAX = 256


def validate_commit(text, delay_ms):
    """Commit text is the chosen candidate: printable Unicode, no control characters."""
    validate("", delay_ms)
    if not isinstance(text, str):
        raise ValueError("commit text must be a string")
    if len(text) > COMMIT_MAX:
        raise ValueError("commit text is limited to %d characters" % COMMIT_MAX)
    if any(ord(c) < 0x20 or 0x7F <= ord(c) < 0xA0 or 0xD800 <= ord(c) < 0xE000 for c in text):
        raise ValueError("commit text must not contain control characters or lone surrogates")


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
