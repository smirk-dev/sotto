"""Global hotkeys on Linux via evdev (reads /dev/input/event*).

Works under both X11 and Wayland — unlike X11-only grabs — because it reads the
kernel input layer directly. Requires the user to be in the `input` group (the
package's post-install note explains this).

Mirrors hotkey_win.HotkeyHook: a hold chord (push-to-talk) fires on_hold_down /
on_hold_up, and a toggle combo fires on_toggle on the trigger key-down while its
modifiers are held.

Unlike the Windows hook we do NOT grab the keyboard, so trigger keys are not
suppressed from the focused app (a letter-based toggle also types the letter).
The hold chord is unaffected. Injected text (xdotool/wtype) goes through the
display server, not /dev/input, so it never echoes back into this listener.
"""

import logging
import select
import threading

import evdev
from evdev import ecodes as e

log = logging.getLogger("sotto")

# chord name -> tuple of evdev keycodes that satisfy it (either side counts)
VK = {
    "Ctrl": (e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL),
    "Alt": (e.KEY_LEFTALT, e.KEY_RIGHTALT),
    "Shift": (e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT),
    "Win": (e.KEY_LEFTMETA, e.KEY_RIGHTMETA),
    "Space": (e.KEY_SPACE,),
    "D": (e.KEY_D,),
    "F9": (e.KEY_F9,),
    "F10": (e.KEY_F10,),
}
_MODIFIER_NAMES = ("Ctrl", "Alt", "Shift", "Win")

# keys that mark a device as a real keyboard (mice also expose EV_KEY via BTN_*)
_KEYBOARD_MARKERS = (e.KEY_A, e.KEY_SPACE, e.KEY_ENTER, e.KEY_LEFTCTRL)


def _parse(combo: str):
    """'Ctrl+Alt+D' -> (modifier-name tuple, trigger keycode tuple or None).

    A modifiers-only combo ('Ctrl+Win') has trigger None: it is a chord.
    'F9 (hold)' -> single-key chord.
    """
    name = combo.replace(" (hold)", "")
    parts = [p.strip() for p in name.split("+")]
    mods = tuple(p for p in parts if p in _MODIFIER_NAMES)
    rest = [p for p in parts if p not in _MODIFIER_NAMES]
    trigger = VK.get(rest[0]) if rest else None
    return mods, trigger


def _keyboard_devices():
    devs = []
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue  # unreadable (permissions) or vanished
        keys = dev.capabilities().get(e.EV_KEY, [])
        if any(k in keys for k in _KEYBOARD_MARKERS):
            devs.append(dev)
        else:
            dev.close()
    return devs


class HotkeyHook:
    def __init__(self, on_hold_down, on_hold_up, on_toggle):
        self.on_hold_down = on_hold_down
        self.on_hold_up = on_hold_up
        self.on_toggle = on_toggle
        self._down = set()          # currently-pressed keycodes (across all keyboards)
        self._hold_active = False
        self._lock = threading.Lock()
        self._hold_mods, self._hold_trigger = _parse("Ctrl+Win")
        self._tog_mods, self._tog_trigger = _parse("Ctrl+Alt+D")
        self._stop = threading.Event()
        self._devices = []
        self.accept_injected = False  # parity with hotkey_win (unused on Linux)

    def set_bindings(self, hold_chord: str, toggle_combo: str):
        with self._lock:
            self._hold_mods, self._hold_trigger = _parse(hold_chord)
            if toggle_combo == "Disabled":
                self._tog_mods, self._tog_trigger = (), None
            else:
                self._tog_mods, self._tog_trigger = _parse(toggle_combo)

    # ---- state helpers (call with lock held) ----
    def _group_down(self, name):
        return any(vk in self._down for vk in VK[name])

    def _hold_chord_down(self):
        if not all(self._group_down(m) for m in self._hold_mods):
            return False
        if self._hold_trigger is not None:
            return any(vk in self._down for vk in self._hold_trigger)
        return bool(self._hold_mods)

    def _handle(self, code, is_down):
        fire = None
        with self._lock:
            if is_down:
                self._down.add(code)
            else:
                self._down.discard(code)

            # toggle combo (not suppressed — see module docstring)
            if (is_down and self._tog_trigger and code in self._tog_trigger
                    and all(self._group_down(m) for m in self._tog_mods)):
                fire = "toggle"

            # hold chord
            chord = self._hold_chord_down()
            if chord and not self._hold_active:
                self._hold_active = True
                fire = fire or "down"
            elif not chord and self._hold_active:
                self._hold_active = False
                fire = fire or "up"

        if fire == "down":
            self.on_hold_down()
        elif fire == "up":
            self.on_hold_up()
        elif fire == "toggle":
            self.on_toggle()

    def start(self):
        threading.Thread(target=self._run, name="hotkey-evdev", daemon=True).start()

    def _run(self):
        self._devices = _keyboard_devices()
        if not self._devices:
            log.error("no readable keyboard devices — add your user to the 'input' "
                      "group (sudo usermod -aG input $USER) and re-login")
            return
        fd_map = {d.fd: d for d in self._devices}
        while not self._stop.is_set():
            try:
                r, _, _ = select.select(fd_map, [], [], 0.2)
            except OSError:
                break
            for fd in r:
                dev = fd_map.get(fd)
                if dev is None:
                    continue
                try:
                    for ev in dev.read():
                        if ev.type == e.EV_KEY and ev.value in (0, 1):  # ignore autorepeat (2)
                            self._handle(ev.code, ev.value == 1)
                except OSError:
                    # device unplugged — drop it
                    fd_map.pop(fd, None)
                    try:
                        dev.close()
                    except OSError:
                        pass

    def stop(self):
        self._stop.set()
        for d in self._devices:
            try:
                d.close()
            except OSError:
                pass
        self._devices = []
