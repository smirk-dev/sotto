<div align="center">

<img src="docs/logo.png" alt="Sotto" width="112" />

# Sotto

### Free, private, local dictation for Windows — hold a hotkey, speak, and accurate text is typed wherever your cursor is.

A fully offline, open-source alternative to cloud dictation tools like Wispr Flow.
**No cloud. No account. No subscription. No telemetry.** Your voice never leaves your PC.

[![Download](https://img.shields.io/github/v/release/smirk-dev/sotto?label=Download&style=for-the-badge&color=9D8CFF)](https://github.com/smirk-dev/sotto/releases/latest)
&nbsp;
[![License: MIT](https://img.shields.io/badge/License-MIT-informational?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](#install-in-2-minutes)

![GitHub Repo stars](https://img.shields.io/github/stars/smirk-dev/sotto?style=social) &nbsp;
![GitHub all releases](https://img.shields.io/github/downloads/smirk-dev/sotto/total?label=downloads&color=7BC98A) &nbsp;
![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

<br>

<img src="docs/demo.gif" alt="Sotto live dictation demo" width="720" />

<em>Live dictation in English and Hindi — text appears at your cursor as you speak.</em>

</div>

---

## Why Sotto?

Paid dictation apps are fast and accurate, but they send your microphone to the cloud, cost a
monthly fee, and stop working offline. Sotto gives you the same **press-to-talk, type-anywhere**
workflow while keeping **100% of the audio on your own machine** — for free, forever.

- 🎙️ **Types into any app** — terminals, Word, Excel, browsers, chat, IDEs, even elevated
  windows. Uses simulated keystrokes (works where paste is blocked) with a clipboard-paste
  fallback that saves and restores your clipboard.
- 🌍 **English + Hindi + Hinglish** — auto-detected per phrase, so you can dictate a
  mixed-language meeting. Hindi that Whisper mistakes for Urdu is auto-corrected back to proper
  left-to-right Devanagari. One-click language switch from the tray.
- ⚡ **Live typing** — in toggle mode, text streams onto the page as you speak — great for
  hands-free meeting notes.
- 🧠 **Robust in the real world** — a voice-activity gate ignores static/background noise so it
  never invents phantom text when you're not speaking.
- 🔒 **Private & free** — OpenAI Whisper running locally on Intel **OpenVINO** (int8, CPU). The
  only time it touches the network is a one-time model download you trigger yourself.
- 🪶 **Runs on a normal laptop** — no GPU required.

## Install in 2 minutes

1. **[⬇️ Download the latest release](https://github.com/smirk-dev/sotto/releases/latest)**
   (`Sotto-windows-x64.zip`) and unzip it.
2. Run **`Sotto\Sotto.exe`**. Windows SmartScreen may warn about an unsigned app — click
   *More info → Run anyway*. (Optional: run `install.ps1` for Start-menu shortcuts.)
3. On first launch, open **Settings → Model & language → Download** (one-time, ~300 MB, from the
   official OpenVINO mirror).
4. **Hold `Ctrl + Win`, speak, release.** Your words appear at the cursor. 🎉

> Prefer to build it yourself? See [Build from source](#build-from-source). It's ~400 lines of
> readable Python.

## How it compares

| | **Sotto** | Wispr Flow | Windows Voice Access | Talon |
|---|:---:|:---:|:---:|:---:|
| Runs 100% offline | ✅ | ❌ | ✅ | ✅ |
| Free | ✅ | 💲 subscription | ✅ | ✅ (paid models) |
| Open source | ✅ | ❌ | ❌ | ❌ |
| Types into any app | ✅ | ✅ | ✅ | ✅ |
| Hindi / Hinglish | ✅ | ✅ | limited | ❌ |
| Live "type as you speak" | ✅ | ✅ | ⚠️ | ⚠️ |
| No account required | ✅ | ❌ | ✅ | ✅ |
| Whisper-grade accuracy | ✅ | ✅ | ⚠️ | ⚠️ |

## Using it

**Hold-to-talk** — hold `Ctrl + Win` (either side), speak, release. A pill with a live waveform
shows at the bottom of the screen and never steals focus. Text lands at your cursor, usually in
**under a second**.

**Toggle / live mode** — press `Ctrl + Alt + D` to start, again to stop. Text is typed **as you
speak**, so you can dictate for minutes or take meeting notes hands-free.

**Spoken commands:** “new line”, “new paragraph”, “comma”, “period”/“full stop”, “question mark”,
“exclamation mark”, “colon”, “semicolon”, “open/close quote”. Emails and URLs are formatted
automatically (“name at gmail dot com” → `name@gmail.com`), and filler words (um, uh) are removed.

### Languages (Hindi / Hinglish)

The default is a multilingual model set to **“Auto — English + Hindi.”** Switch any time from the
**tray → Language** menu:

- **Auto — English + Hindi** (default) — detects each phrase; best for mixed/Hinglish sessions.
- **English only** / **Hindi only** — force one language for the most reliable single-language
  results.
- **Auto — all languages** — unconstrained 99-language detection.
- For the fastest *pure-English* dictation, switch **Model** to `base.en` (sub-second).

> **Tip:** if accuracy disappoints, pick a single language instead of Auto, keep the mic close,
> and reduce background noise. Sotto runs a compact model on your CPU, so it trades a little
> accuracy for being fully private and free.

## Features

- **Hotkeys** — configurable hold chord (`Ctrl+Win`, `Alt+Win`, `Ctrl+Alt`, `F9`) and toggle
  combo (`Ctrl+Alt+D`, `Ctrl+Shift+Space`, …).
- **Microphone picker** with a live level meter.
- **Custom dictionary** — teach it names and jargon; they're fuzzy-corrected in the output.
- **Dictation history** — searchable local log, one-click re-copy; disable or clear anytime.
- **Session stats** — words dictated and estimated time saved vs. typing.
- **Start with Windows**, single-instance, subtle start/stop sounds, dark minimal UI.

## Models

Settings → *Model & language*. Downloaded models show a ✓; others show a **Download** button
(one-time, from the official OpenVINO mirrors on Hugging Face).

| Model | Size | Best for |
|---|---|---|
| `tiny.en` | ~60 MB | fastest, English only, lower accuracy |
| `base.en` | ~95 MB | fast, accurate English only — sub-second |
| `small.en` | ~300 MB | most accurate English only |
| `base (multilingual)` | ~95 MB | fast, any language, lower accuracy |
| **`small (multilingual)`** *(default)* | ~300 MB | English + Hindi + Hinglish |
| `large-v3-turbo` | ~1.7 GB | best accuracy, slow without a GPU |

Data lives in `%LOCALAPPDATA%\Sotto` (models, config, history, log).

## FAQ

**Is my audio uploaded anywhere?** No. Transcription runs entirely on your CPU. The only network
request is the one-time model download you start yourself.

**Does it need a GPU?** No — it's tuned for CPU. (You can optionally run on an Intel iGPU.)

**Why does it type into elevated apps sometimes fail?** Windows blocks normal apps from sending
keys to Administrator windows. Launch the **"Sotto (administrator)"** shortcut to type everywhere.

**Windows says "unknown publisher."** The app is unsigned (code-signing certificates cost money;
Sotto is free). Click *More info → Run anyway*, or build it yourself.

**Can it do languages other than English/Hindi?** Yes — set Language to *Auto — all languages* or
pick a specific one; Whisper supports ~99 languages.

## Dictating into apps that run as Administrator

Use the **"Sotto (administrator)"** Start-menu shortcut (one UAC prompt per launch) so Sotto can
type into elevated windows too.

## Build from source

```powershell
git clone https://github.com/smirk-dev/sotto
cd sotto
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install faster-whisper sounddevice PySide6-Essentials numpy pyinstaller pillow openvino-genai huggingface_hub
.\.venv\Scripts\python -m PyInstaller sotto.spec --noconfirm   # -> dist\Sotto\Sotto.exe
```

Run the app in dev with `.\.venv\Scripts\python -m sotto`. Tests are in `tests/`;
`PROGRESS.md` documents the engineering decisions and on-machine benchmarks.

## Contributing

Issues, ideas, and PRs are very welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). If Sotto is
useful to you, a ⭐ **star** helps others find it.

## License

[MIT](LICENSE) for Sotto's own code. Bundled components keep their own licenses (OpenVINO
Apache-2.0, Whisper weights MIT, PySide6/Qt LGPL, PortAudio MIT).

<div align="center"><sub>

Built for people who write by voice. Free and open-source forever.
<br>
<code>dictation · speech-to-text · voice typing · Whisper · offline · Windows · Wispr Flow alternative · Hindi</code>

</sub></div>
