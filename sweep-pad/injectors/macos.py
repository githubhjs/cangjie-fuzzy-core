"""macOS Quartz keyboard events using ctypes, without PyObjC."""
import ctypes
import sys
import time

from . import validate

# ANSI virtual key positions, independent of a Python/Quartz dependency.
KEY_CODES = {"a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5,
             "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12,
             "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
             "o": 31, "u": 32, "i": 34, "p": 35, "l": 37,
             "j": 38, "k": 40, "n": 45, "m": 46}
PERMISSION_MESSAGE = ("macOS keyboard injection needs Accessibility permission: "
                      "System Settings > Privacy & Security > Accessibility; enable the terminal or Python app running Sweep Pad, then restart it. "
                      "If trusted events still have no effect, verify the focused app and this permission manually.")


def _api():
    if sys.platform != "darwin":
        raise RuntimeError("macOS Quartz injection requires macOS.")
    api = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
    api.AXIsProcessTrusted.argtypes = []
    api.AXIsProcessTrusted.restype = ctypes.c_bool
    api.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
    api.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
    api.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    api.CGEventSetFlags.restype = None
    api.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    api.CGEventPost.restype = None
    api.CFRelease.argtypes = [ctypes.c_void_p]
    api.CFRelease.restype = None
    return api


def availability():
    try:
        api = _api()
        if not api.AXIsProcessTrusted():
            return False, PERMISSION_MESSAGE
    except (OSError, RuntimeError) as exc:
        return False, str(exc)
    return True, "Quartz is available and Accessibility is trusted. " + PERMISSION_MESSAGE


def inject_keys(text: str, delay_ms=8):
    validate(text, delay_ms)
    if not text:
        return
    api = _api()
    if not api.AXIsProcessTrusted():
        print(PERMISSION_MESSAGE, file=sys.stderr)
        raise RuntimeError(PERMISSION_MESSAGE)
    for c in text:
        for down in (True, False):
            event = api.CGEventCreateKeyboardEvent(None, KEY_CODES[c], down)
            if not event:
                raise RuntimeError("Could not create Quartz keyboard event. " + PERMISSION_MESSAGE)
            try:
                api.CGEventSetFlags(event, 0)
                api.CGEventPost(0, event)  # kCGHIDEventTap
            finally:
                api.CFRelease(event)
        time.sleep(delay_ms / 1000.0)
