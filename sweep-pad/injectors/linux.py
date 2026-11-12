"""X11 xdotool and Wayland ydotool backends (no shell invocation)."""
import os
import shutil
import subprocess
import time

from . import validate, validate_commit

# Linux input-event key codes, shared by ydotool/uinput.
KEY_CODES = dict(zip("qwertyuiop", range(16, 26)))
KEY_CODES.update(zip("asdfghjkl", range(30, 39)))
KEY_CODES.update(zip("zxcvbnm", range(44, 51)))

KEY_CODES.update({" ": 57, "'": 40})

def is_wayland():
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


def availability():
    tool = "ydotool" if is_wayland() else "xdotool"
    if shutil.which(tool) is None:
        return False, "Missing %s; install it to inject keys." % tool
    if is_wayland():
        return True, "Wayland: ydotool requires a running ydotoold and uinput permission; the pad cannot guarantee non-activation."
    if not os.environ.get("DISPLAY"):
        return False, "X11 DISPLAY is unset; connect to an X11 desktop before injecting keys."
    return True, "X11 xdotool is available; live focus and injection still require a desktop test."


def build_command(text, delay_ms=8):
    validate(text, delay_ms)
    if is_wayland():
        events = [event for c in text for event in ("%d:1" % KEY_CODES[c], "%d:0" % KEY_CODES[c])]
        return ["ydotool", "key", "--key-delay", str(int(delay_ms))] + events
    return ["xdotool", "key", "--clearmodifiers", "--delay", str(int(delay_ms))] + [{" ": "space", "'": "apostrophe"}.get(c, c) for c in text]


def inject_keys(text: str, delay_ms=8):
    validate(text, delay_ms)
    if not text:
        return
    ok, message = availability()
    if not ok:
        raise RuntimeError(message)
    try:
        subprocess.run(build_command(text, delay_ms), check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        # Do not echo command output, which may contain unrelated desktop data.
        raise RuntimeError("Keyboard injection failed. On Wayland, check ydotoold/uinput permissions; on X11, check DISPLAY and desktop access.") from exc


# Commit mode: put the chosen text into the focused app directly, bypassing IME composition.
# X11: `xdotool type` temporarily maps each character's keysym to a spare keycode and presses it via
# XTEST. Measured in an isolated ibus-rime rig (GTK3, Qt5, Tk): exact text, no preedit, while Rime is
# idle or after a cancelled composition. Clipboard paste was equally exact when idle but is swallowed
# by Rime while it composes, depends on Ctrl+V meaning paste, and overwrites the clipboard.
# Wayland: ydotool cannot type non-ASCII, so the clipboard is used (wl-copy + Ctrl+V); UNVERIFIED.
COMMIT_DELAY_MS = 12  # xdotool's keysym remapping can race with very short delays
_PASTE_SETTLE_S = 0.3


def commit_availability():
    tools = ("wl-copy", "wl-paste", "ydotool") if is_wayland() else ("xdotool",)
    missing = [t for t in tools if shutil.which(t) is None]
    if missing:
        hint = ("install wl-clipboard and ydotool (with a running ydotoold)" if is_wayland()
                else "install xdotool")
        return False, "Commit mode is missing %s; %s." % (", ".join(missing), hint)
    if not is_wayland() and not os.environ.get("DISPLAY"):
        return False, "X11 DISPLAY is unset; connect to an X11 desktop before committing text."
    return True, "ok"


def build_commit_command(text, delay_ms=COMMIT_DELAY_MS):
    validate_commit(text, delay_ms)
    return ["xdotool", "type", "--clearmodifiers", "--delay", str(int(delay_ms)), "--", text]


def _wayland_commit(text):
    previous = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, timeout=2)
    # wl-copy forks a server that keeps the selection: never capture its pipes or run() would wait on it.
    subprocess.run(["wl-copy", "--", text], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
    # Ctrl (KEY_LEFTCTRL 29) + V (KEY_V 47)
    subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=True, capture_output=True, timeout=5)
    time.sleep(_PASTE_SETTLE_S)
    if previous.returncode == 0:
        subprocess.run(["wl-copy"], input=previous.stdout, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)


def commit_text(text: str, delay_ms=COMMIT_DELAY_MS):
    validate_commit(text, delay_ms)
    if not text:
        return
    ok, message = commit_availability()
    if not ok:
        raise RuntimeError(message)
    try:
        if is_wayland():
            _wayland_commit(text)
        else:
            subprocess.run(build_commit_command(text, delay_ms), check=True, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("Text commit failed. On X11 check DISPLAY and xdotool; on Wayland check wl-clipboard, ydotoold and uinput permissions.") from exc
