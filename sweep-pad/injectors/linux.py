"""X11 xdotool and Wayland ydotool backends (no shell invocation)."""
import os
import shutil
import subprocess

from . import validate

# Linux input-event key codes, shared by ydotool/uinput.
KEY_CODES = dict(zip("qwertyuiop", range(16, 26)))
KEY_CODES.update(zip("asdfghjkl", range(30, 39)))
KEY_CODES.update(zip("zxcvbnm", range(44, 51)))


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
    return ["xdotool", "key", "--clearmodifiers", "--delay", str(int(delay_ms))] + list(text)


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
