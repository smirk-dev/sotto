"""Global hotkey dispatcher: selects the Windows or Linux backend at import.

Both backends expose the same HotkeyHook(on_hold_down, on_hold_up, on_toggle)
with .set_bindings(hold_chord, toggle_combo), .start(), .stop() and an
.accept_injected attribute (tests). See hotkey_win.py (WH_KEYBOARD_LL) and
hotkey_linux.py (evdev).
"""

import sys

if sys.platform == "win32":
    from .hotkey_win import HotkeyHook  # noqa: F401
else:
    from .hotkey_linux import HotkeyHook  # noqa: F401
