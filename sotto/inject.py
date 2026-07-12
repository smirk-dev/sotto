"""Text insertion dispatcher: selects the Windows or Linux backend at import.

Both backends expose the same surface used by the app:
  insert_text(text, mode="type", paste_threshold=400) -> bool
  foreground_injection_blocked() -> bool
  _set_clipboard_text(text) -> bool
See inject_win.py (SendInput/UIPI) and inject_linux.py (xdotool/wtype).
"""

import sys

if sys.platform == "win32":
    from .inject_win import (  # noqa: F401
        insert_text,
        foreground_injection_blocked,
        _set_clipboard_text,
    )
else:
    from .inject_linux import (  # noqa: F401
        insert_text,
        foreground_injection_blocked,
        _set_clipboard_text,
    )
