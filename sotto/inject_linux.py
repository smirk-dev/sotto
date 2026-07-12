"""Insert text at the cursor of the focused app on Linux (X11 and Wayland).

Typing is delegated to mature tools that correctly emit *arbitrary Unicode*
(needed for Hindi/Devanagari) by remapping keysyms:
  - X11:     xdotool type
  - Wayland: wtype   (needs the virtual-keyboard protocol: wlroots/Hyprland/Sway,
             KDE/KWin; GNOME/Mutter does not implement it — see README)
  - fallback (incl. GNOME-Wayland): ydotool, if installed and running

These run through the display server, not /dev/input, so the evdev hotkey
listener never sees our own keystrokes (no echo/self-trigger).

Clipboard fallback (long text) uses wl-clipboard on Wayland or xclip on X11.
There is no Windows-style UIPI concept here, so foreground_injection_blocked()
is always False.
"""

import os
import shutil
import subprocess
import time


def _is_wayland() -> bool:
    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


# ---------- typing backends ----------

def _run(cmd, data: bytes | None = None) -> bool:
    """Run cmd (optionally feeding `data` on stdin); True on exit 0."""
    try:
        r = subprocess.run(cmd, input=data,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=20)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _type_xdotool(text: str) -> bool:
    if not shutil.which("xdotool"):
        return False
    # --file - reads the string from stdin: no shell-escaping, any length, unicode.
    return _run(["xdotool", "type", "--clearmodifiers", "--file", "-"],
                text.encode("utf-8"))


def _type_wtype(text: str) -> bool:
    if not shutil.which("wtype"):
        return False
    # wtype takes text as positional args (no stdin). Build args so that:
    #   - newlines become real Return key presses (a typed U+000A won't submit), and
    #   - a leading '-' is emitted via its keysym (wtype reads a '-'-prefixed arg as
    #     an option, not text).
    args = ["wtype"]
    for idx, line in enumerate(text.split("\n")):
        if idx:
            args += ["-k", "Return"]
        if not line:
            continue
        dashes = len(line) - len(line.lstrip("-"))
        args += ["-k", "minus"] * dashes
        rest = line[dashes:]
        if rest:
            args.append(rest)
    return _run(args)


def _type_ydotool(text: str) -> bool:
    # Universal fallback (works on GNOME-Wayland). Needs ydotoold running and
    # access to /dev/uinput; degrades to False otherwise.
    if not shutil.which("ydotool"):
        return False
    return _run(["ydotool", "type", "--file", "-"], text.encode("utf-8"))


def type_text(text: str) -> bool:
    """Type `text` as keystrokes via the best available backend for this session."""
    if not text:
        return True
    if _is_wayland():
        return _type_wtype(text) or _type_ydotool(text)
    return _type_xdotool(text) or _type_ydotool(text)


# ---------- clipboard ----------

def _clip_get() -> str | None:
    if _is_wayland() and shutil.which("wl-paste"):
        cmd = ["wl-paste", "--no-newline"]
    elif shutil.which("xclip"):
        cmd = ["xclip", "-selection", "clipboard", "-o"]
    else:
        return None
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=5)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _set_clipboard_text(text: str) -> bool:
    if _is_wayland() and shutil.which("wl-copy"):
        cmd = ["wl-copy"]
    elif shutil.which("xclip"):
        cmd = ["xclip", "-selection", "clipboard"]
    else:
        return False
    return _run(cmd, text.encode("utf-8"))


def _send_paste() -> bool:
    """Send Ctrl+V through the active display server."""
    if _is_wayland():
        if shutil.which("wtype"):
            return _run(["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"])
        return _run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])  # ctrl v
    if shutil.which("xdotool"):
        return _run(["xdotool", "key", "--clearmodifiers", "ctrl+v"])
    return _run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])


def paste_text(text: str) -> bool:
    """Clipboard-paste `text`, restoring the previous clipboard afterward."""
    old = _clip_get()
    if not _set_clipboard_text(text):
        return False
    time.sleep(0.05)
    ok = _send_paste()
    time.sleep(0.3)  # let the target read the clipboard before we restore it
    if old is not None:
        _set_clipboard_text(old)
    return ok


# ---------- public API (mirrors inject_win) ----------

def foreground_injection_blocked() -> bool:
    """No UIPI/integrity concept on Linux — injection is never pre-emptively blocked."""
    return False


def insert_text(text: str, mode: str = "type", paste_threshold: int = 400) -> bool:
    if mode == "paste" or len(text) > paste_threshold:
        # trailing newlines must be real Enter presses (a pasted \n doesn't submit)
        body = text.rstrip("\n")
        trail = text[len(body):]
        if paste_text(body):
            return type_text(trail) if trail else True
        return type_text(text)
    if type_text(text):
        return True
    return paste_text(text)
