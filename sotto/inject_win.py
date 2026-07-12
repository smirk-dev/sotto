"""Insert text at the cursor of the foreground app.

Primary path: SendInput with KEYEVENTF_UNICODE (works where paste is blocked).
Fallback path: clipboard paste with save/restore, for long text.
Pure ctypes — no Qt dependency, usable from any thread.
"""

import ctypes
import ctypes.wintypes as wt
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

# 64-bit safety: handle/pointer returns must not be truncated to c_int
user32.GetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
kernel32.GlobalAlloc.restype = wt.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = wt.LPVOID
kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
kernel32.GlobalFree.argtypes = [wt.HGLOBAL]

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN, VK_TAB, VK_CONTROL, VK_V = 0x0D, 0x09, 0x11, 0x56
_MODIFIER_VKS = (0x10, 0x11, 0x12, 0x5B, 0x5C)  # shift, ctrl, alt, lwin, rwin

ULONG_PTR = wt.WPARAM


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("padding", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


INJECT_TAG = 0x534F5454  # "SOTT": marks our own SendInput events (see hotkey.py)


# ---------- integrity / UIPI ----------
# Windows forbids a normal-privilege process from sending input to (or hooking
# keys destined for) a higher-integrity window. When the focused app is elevated
# and Sotto is not, SendInput reports success but the keystrokes are silently
# dropped. We detect that up front so the app can fail loudly (and fall back to
# the clipboard) instead of appearing to type into thin air.

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
_TokenElevation = 20
ERROR_ACCESS_DENIED = 5

user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.GetCurrentProcess.restype = wt.HANDLE
kernel32.CloseHandle.argtypes = [wt.HANDLE]
advapi32.OpenProcessToken.argtypes = [wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.HANDLE)]
advapi32.GetTokenInformation.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                         wt.DWORD, ctypes.POINTER(wt.DWORD)]

_self_elevated = None


def _token_elevated(proc_handle):
    """Elevation (bool) for an open process handle, or None if its token is unreadable."""
    tok = wt.HANDLE()
    if not advapi32.OpenProcessToken(proc_handle, TOKEN_QUERY, ctypes.byref(tok)):
        return None
    try:
        elev = wt.DWORD(0)
        ret = wt.DWORD(0)
        if not advapi32.GetTokenInformation(tok, _TokenElevation, ctypes.byref(elev), 4,
                                            ctypes.byref(ret)):
            return None
        return bool(elev.value)
    finally:
        kernel32.CloseHandle(tok)


def self_elevated() -> bool:
    global _self_elevated
    if _self_elevated is None:
        _self_elevated = bool(_token_elevated(kernel32.GetCurrentProcess()))
    return _self_elevated


def foreground_injection_blocked() -> bool:
    """True when the focused window belongs to a higher-integrity (e.g. elevated)
    process that Windows UIPI will not let a normal Sotto type into. Always False
    when Sotto itself is elevated — it can type everywhere."""
    try:
        if self_elevated():
            return False
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = wt.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return False
        ctypes.set_last_error(0)
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h:
            # a same-user, same-integrity window opens fine; access-denied here
            # means the foreground sits at a higher integrity level (elevated).
            return ctypes.get_last_error() == ERROR_ACCESS_DENIED
        try:
            elevated = _token_elevated(h)
            return True if elevated is None else elevated
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        return False


def _key_event(vk=0, scan=0, flags=0):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.u.ki = KEYBDINPUT(vk, scan, flags, 0, INJECT_TAG)
    return inp


def wait_modifiers_released(timeout=1.5):
    """Block until no physical modifier key is held (so injected text isn't
    interpreted as a shortcut like Ctrl+letter)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in _MODIFIER_VKS):
            return True
        time.sleep(0.01)
    return False


def type_text(text: str):
    """Send text as unicode keystrokes via SendInput, in chunks."""
    events = []
    for ch in text:
        if ch == "\n":
            events.append(_key_event(vk=VK_RETURN))
            events.append(_key_event(vk=VK_RETURN, flags=KEYEVENTF_KEYUP))
        elif ch == "\t":
            events.append(_key_event(vk=VK_TAB))
            events.append(_key_event(vk=VK_TAB, flags=KEYEVENTF_KEYUP))
        elif ch == "\r":
            continue
        else:
            # utf-16 code units (handles surrogate pairs)
            raw = ch.encode("utf-16-le")
            units = [int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2)]
            for u in units:
                events.append(_key_event(scan=u, flags=KEYEVENTF_UNICODE))
                events.append(_key_event(scan=u, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    sent = 0
    CHUNK = 100  # events per SendInput call
    for i in range(0, len(events), CHUNK):
        chunk = events[i:i + CHUNK]
        arr = (INPUT * len(chunk))(*chunk)
        n = user32.SendInput(len(chunk), arr, ctypes.sizeof(INPUT))
        sent += n
        if n != len(chunk):
            return False
        time.sleep(0.005)
    return sent == len(events)


# ---------- clipboard fallback ----------

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


def _get_clipboard_text():
    if not user32.OpenClipboard(None):
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        ptr = kernel32.GlobalLock(h)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def _set_clipboard_text(text: str):
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        ptr = kernel32.GlobalLock(h)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h)
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            kernel32.GlobalFree(h)
            return False
        return True
    finally:
        user32.CloseClipboard()


def paste_text(text: str):
    """Clipboard-paste `text`, then restore the previous clipboard contents."""
    old = _get_clipboard_text()
    if not _set_clipboard_text(text):
        return False
    time.sleep(0.05)
    events = [
        _key_event(vk=VK_CONTROL),
        _key_event(vk=VK_V),
        _key_event(vk=VK_V, flags=KEYEVENTF_KEYUP),
        _key_event(vk=VK_CONTROL, flags=KEYEVENTF_KEYUP),
    ]
    arr = (INPUT * len(events))(*events)
    ok = user32.SendInput(len(events), arr, ctypes.sizeof(INPUT)) == len(events)
    time.sleep(0.3)  # let the target app read the clipboard before restoring
    if old is not None:
        _set_clipboard_text(old)
    return ok


def insert_text(text: str, mode: str = "type", paste_threshold: int = 400) -> bool:
    # UIPI would silently swallow our keystrokes (and the clipboard-paste Ctrl+V)
    # into an elevated window — report failure so the caller can copy to clipboard
    # and tell the user, instead of pretending the text was typed.
    if foreground_injection_blocked():
        return False
    wait_modifiers_released()
    if mode == "paste" or len(text) > paste_threshold:
        # trailing newlines must be real Enter presses (pasted \n doesn't submit)
        body = text.rstrip("\n")
        trail = text[len(body):]
        if paste_text(body):
            return type_text(trail) if trail else True
        return type_text(text)
    if type_text(text):
        return True
    return paste_text(text)
