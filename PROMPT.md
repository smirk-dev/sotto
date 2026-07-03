# Build prompt: local Wispr Flow clone for Windows

Copy everything below into a fresh Claude Code session (Fable 5, effort high) started in an empty
project folder. Fill nothing in — it is ready to run.

---

I'm building a personal, fully local dictation app for my own Windows 11 machine — a clone of
Wispr Flow. I use it all day to write by voice instead of typing, so it must be something I can
trust in the middle of real work: press a hotkey, speak, and have accurate text appear wherever my
cursor is — terminal, Word, PowerPoint, Excel, browser, chat apps, IDEs, anywhere. It replaces a
paid cloud subscription, so everything must run offline, cost nothing, and use only open-source
components. Build it end to end: design, implement, test on this machine, and package it so I can
launch it with one click like any other app.

## What it does

1. I press and hold a global hotkey (default: hold `Ctrl+Win`; also support a toggle mode with a
   configurable hotkey for long dictation). A small, elegant recording indicator appears near the
   bottom-center of the screen with a live waveform.
2. While I speak, audio is captured from my default microphone and transcribed locally in real time.
3. When I release the key (or toggle off), the finalized, cleaned-up text is inserted at the current
   cursor position in whatever application has focus, and the indicator disappears.

## Hard requirements

- **Windows 11 desktop app, 100% local and free.** No network calls at runtime, no accounts, no
  telemetry, no API keys. Open-source dependencies only (permissive or GPL-compatible licenses).
- **Accuracy comparable to Wispr Flow.** Use a state-of-the-art local Whisper implementation —
  evaluate `faster-whisper` (CTranslate2) and `whisper.cpp` and pick what performs best on this
  machine; probe my hardware first (GPU/CUDA availability, RAM, CPU) and choose model size and
  quantization accordingly, with a settings option to switch models. Target near-real-time latency:
  text should land well under ~2 seconds after I stop speaking for typical utterances.
- **Types anywhere.** Text insertion must work in elevated terminals, Office apps, Electron apps,
  and browsers. Prefer simulated keyboard input (e.g. `SendInput` with Unicode) as the primary path
  so it works even where paste is blocked; fall back to clipboard-paste (save and restore my
  clipboard) for large blocks or apps where typing is slow/unreliable. Handle focus correctly — the
  overlay must never steal focus from the target app.
- **UI: slick and minimal, Wispr Flow's look with a different identity.** Pick an original name
  (not "Wispr" anything) and use a matching dark, minimal palette in Wispr Flow's style: near-black
  background, soft off-white text, a single muted accent, generous rounded corners, subtle
  animations. Components: (a) the floating recording pill with waveform and state (listening /
  transcribing / inserted / error), (b) a system-tray icon with a menu (toggle mic, open settings,
  history, quit), (c) a settings window, (d) a dictation-history window. Frameless, smooth, no
  stock-widget look.
- **Single-click launch.** Package as a standalone executable with an installer or portable build,
  Start-menu shortcut, custom app icon, and an optional "start with Windows" setting. Launching must
  not open a console window.

## Features I want you to include beyond the basics

- **Smart formatting of the raw transcript**: automatic punctuation and capitalization; spoken
  commands like "new line", "new paragraph", "comma", "question mark"; strip filler words ("um",
  "uh") with a toggle; sensible handling of numbers, emails, and URLs.
- **Custom dictionary**: a user-editable list of names and jargon that biases or post-corrects
  transcription (my name is Suryansh — that's a good first test case).
- **Dictation history**: searchable local log of past transcriptions with one-click re-copy, plus a
  privacy option to disable history or clear it.
- **Per-session stats** (words dictated, time saved vs. typing) shown unobtrusively in settings.
- **Mic and model settings**: input-device picker with live level meter, model-size picker with
  download manager for model files (downloads happen once, at setup, from official open mirrors —
  this is the only permitted network use, and it must be user-initiated), language selection with
  auto-detect.
- **Robustness**: graceful behavior when the mic is busy or missing, when the model is still
  loading (show state in the tray), and when the foreground app rejects input (fall back and notify).
  A single instance only — relaunching focuses the running app.
- **Audio feedback**: subtle optional sounds on start/stop of recording.

## How to work

You are operating autonomously; I am not watching in real time. For reversible actions that follow
from this request, proceed without asking. Pause only for a destructive or irreversible action, a
real scope change, or input only I can provide. Before ending your turn, check your last paragraph —
if it is a plan or a promise about work you have not done, do that work now. End your turn only when
the app is built, tested, and packaged, or you are blocked on something only I can unblock.

Do the simplest thing that works well. Don't add features, abstractions, or error handling beyond
what this spec requires.

Verify as you build, not just at the end: after each major component (audio capture, transcription,
text injection, overlay UI, packaging), run it on this machine and confirm real behavior — e.g.
actually inject text into Notepad and a terminal, actually transcribe a recorded sample. Use
fresh-context subagents to check finished components against this spec. Before reporting progress,
audit each claim against a tool result from this session; only report work you can point to evidence
for, and report failures plainly with their output.

Keep a `PROGRESS.md` state file in the repo: what's done and verified, what's in progress, decisions
made and why, and anything blocked on me. Update it as you go so a future session can resume.

Finish with: the packaged app on disk, a `README.md` (install, launch, hotkeys, settings, how to
change models), and a final message that re-grounds me — what you built, where the executable is,
how to start dictating in one sentence, and anything that needs my input (e.g. a mic-permission
prompt or a model download confirmation).
