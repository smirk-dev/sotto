# Sotto — Arch Linux packaging

An AUR-ready `PKGBUILD` that installs Sotto into `/opt/sotto` (a self-contained
Python venv) with a `/usr/bin/sotto` launcher, a `.desktop` entry, and an icon.

## Try it locally (no AUR account needed)

```bash
cd packaging/arch
makepkg -si            # builds the venv, installs deps, installs the package
```

`makepkg` downloads the release tarball named in `source=()` and pip-installs the
Python stack (PySide6, OpenVINO + openvino-genai, sounddevice, evdev, …) into the
vendored venv. Then:

```bash
sudo usermod -aG input "$USER"   # one-time: lets the hotkey read the keyboard
# log out / back in, then launch "Sotto" from your app menu
```

## Runtime dependencies (pulled in automatically)

| Purpose            | Package        | Notes                                             |
|--------------------|----------------|---------------------------------------------------|
| Audio capture      | `portaudio`    | via sounddevice                                   |
| Typing (X11)       | `xdotool`      | types arbitrary Unicode incl. Devanagari          |
| Typing (Wayland)   | `wtype`        | wlroots (Hyprland/Sway) and KDE/KWin              |
| Clipboard fallback | `wl-clipboard` | plus `xclip` on X11 if you want the X11 fallback  |
| Typing (GNOME-Wl)  | `ydotool` *(optdepend)* | fallback where `wtype` is unsupported     |

## Hotkey & typing — how it works on Linux

- **Global hotkey** is read from `/dev/input` via **evdev** (works on X11 *and*
  Wayland), which is why you must be in the `input` group. Injected text goes
  through the display server, not `/dev/input`, so it never re-triggers the hotkey.
- **Typing** is delegated to `xdotool` (X11) / `wtype` (Wayland) so Unicode —
  including **Hindi/Devanagari** — is emitted correctly.

### Known limitations (v1)

- The **toggle combo's** trigger key is *not* suppressed from the focused app on
  Linux (we don't grab the keyboard). Prefer the **hold chord** (default
  `Ctrl+Super`) or a function-key toggle like `F10`.
- **GNOME-Wayland** does not implement the virtual-keyboard protocol `wtype`
  needs. Use an **X11 session**, or install **`ydotool`** (run `ydotoold`) as a
  fallback.

## Publishing to the AUR

1. Tag a release on GitHub as `v<pkgver>` (so the `source=()` tarball exists).
2. Update `pkgver` in `PKGBUILD`, then compute checksums:
   ```bash
   updpkgsums
   makepkg --printsrcinfo > .SRCINFO
   ```
3. Push `PKGBUILD`, `.SRCINFO`, `sotto.desktop`, `sotto.install` to the
   `ssh://aur@aur.archlinux.org/sotto.git` repo.
4. Lint before submitting: `namcap PKGBUILD` and `namcap sotto-*.pkg.tar.zst`.

> Prefer a VCS package that always builds `main`? Copy this `PKGBUILD` to
> `sotto-git`, set `source=("git+$url.git")`, `sha256sums=('SKIP')`, drop the
> tarball `pkgver`, and add a `pkgver()` function.
