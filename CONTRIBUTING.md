# Contributing to Sotto

Thanks for your interest — Sotto is a small, friendly project and contributions of all sizes are
welcome.

## Ways to help

- ⭐ **Star the repo** — it genuinely helps others discover it.
- 🐛 **Report bugs** — open an [issue](https://github.com/smirk-dev/sotto/issues) with your
  Windows version, what you did, and what happened. Logs live at `%LOCALAPPDATA%\Sotto\app.log`.
- 💡 **Suggest features** — open an issue describing the use case.
- 🌍 **Test other languages** — Sotto uses multilingual Whisper; feedback on non-English
  accuracy (especially Indic languages) is valuable.
- 🔧 **Send a PR** — see below.

## Development setup

```powershell
git clone https://github.com/smirk-dev/sotto
cd sotto
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install faster-whisper sounddevice PySide6-Essentials numpy pyinstaller pillow openvino-genai huggingface_hub
.\.venv\Scripts\python -m sotto        # run in dev
```

Run the tests before opening a PR:

```powershell
.\.venv\Scripts\python tests\test_textproc.py
.\.venv\Scripts\python tests\test_robustness.py
.\.venv\Scripts\python tests\test_streaming.py
```

## Guidelines

- Keep it simple. Sotto deliberately does "the simplest thing that works well."
- Match the existing style (plain modules under `sotto/`, no heavy frameworks).
- The app must stay **100% local at runtime** — no new network calls except user-initiated
  model downloads, no telemetry.
- If you touch transcription, audio, hotkeys, or injection, verify on a real Windows machine and
  mention what you tested.

## Project layout

| Path | What |
|---|---|
| `sotto/engine.py` | Whisper/OpenVINO transcription, language detect-and-correct |
| `sotto/vad.py` | noise gate (energy + spectral flatness) |
| `sotto/audio.py` | microphone capture |
| `sotto/hotkey.py` | global low-level keyboard hook |
| `sotto/inject.py` | SendInput / clipboard text insertion |
| `sotto/textproc.py` | punctuation, spoken commands, dictionary |
| `sotto/app.py` + `*_ui.py` | tray, overlay pill, settings, history |

By contributing you agree your contributions are licensed under the project's [MIT License](LICENSE).
