"""Windows SendInput: physical letter scancodes and optional UTF-16 commit."""
import ctypes
from ctypes import wintypes
import sys
import time

from . import validate, validate_commit

# Explicit Windows-width fields also make structure tests meaningful on Linux.
DWORD = ctypes.c_uint32
WORD = ctypes.c_uint16
LONG = ctypes.c_int32
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", WORD), ("wScan", WORD), ("dwFlags", DWORD),
                ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", LONG), ("dy", LONG), ("mouseData", DWORD),
                ("dwFlags", DWORD), ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", DWORD), ("wParamL", WORD), ("wParamH", WORD)]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("payload",)
    _fields_ = [("type", DWORD), ("payload", INPUTUNION)]


def _api():
    if sys.platform != "win32":
        raise RuntimeError("Windows SendInput requires Windows.")
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    api.SendInput.restype = wintypes.UINT
    api.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    api.MapVirtualKeyW.restype = wintypes.UINT
    return api


def availability():
    try:
        _api()
    except (OSError, RuntimeError) as exc:
        return False, str(exc)
    return True, "Windows SendInput is available. Elevated targets require matching privilege."


def _send_pair(api, scan, flags):
    for extra in (0, 0x0002):  # KEYEVENTF_KEYUP
        event = INPUT(type=1, ki=KEYBDINPUT(0, scan, flags | extra, 0, 0))
        if api.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
            raise RuntimeError("SendInput failed; check target focus and matching privilege level.")


def inject_keys(text: str, delay_ms=8):
    validate(text, delay_ms)
    if not text:
        return
    api = _api()
    for c in text:
        scan = api.MapVirtualKeyW(0xDE if c == "'" else ord(c.upper()), 0)
        if not scan:
            raise RuntimeError("No Windows scancode for letter " + c)
        _send_pair(api, scan, 0x0008)  # KEYEVENTF_SCANCODE
        time.sleep(delay_ms / 1000.0)


def commit_text(text: str, delay_ms=8):
    """Commit mode: send the chosen text as KEYEVENTF_UNICODE UTF-16 units (bypasses IME composition)."""
    validate_commit(text, delay_ms)
    if not text:
        return
    api = _api()
    encoded = text.encode("utf-16-le")
    for i in range(0, len(encoded), 2):
        _send_pair(api, int.from_bytes(encoded[i:i + 2], "little"), 0x0004)
        time.sleep(delay_ms / 1000.0)


# Backward-compatible name used by earlier Windows releases.
inject_unicode = commit_text
