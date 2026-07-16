# Sotto — build progress

Local dictation app (Wispr Flow clone) for this Windows 11 machine. Spec: `PROMPT.md`.

## Decisions

- **Name/identity:** "Sotto" (sotto voce). Palette: near-black `#101014`, surface `#17171D`,
  off-white text `#EAEAF0`, single muted-violet accent `#9D8CFF`, 12–16 px rounded corners.
- **Engine: OpenVINO (openvino-genai), int8, CPU.** Decided by on-machine benchmark
  (i7-1360P, 15.7 GB RAM, Intel Iris Xe, no CUDA; ~25% constant background CPU load).
  Measured on SAPI-TTS clips of 4.4 s / 13.7 s / 27.6 s (tests/bench_*.py):
  - faster-whisper (ctranslate2 4.8.0) small.en int8 CPU: 6.4 / 8.7 / 10.6 s — ~0.7x realtime,
    can't keep up with live speech. Thread count, affinity, compute type, VAD made no difference;
    numpy hits 353 GFLOPS so it's ctranslate2-specific. ct2 4.4.0 has no cp313 wheel.
  - OpenVINO whisper-small.en-int8 CPU: 2.7 / 3.7 / 5.7 s. GPU (Iris Xe): similar but 84 s first
    compile + high variance → CPU default, GPU offered in settings (compile cached via CACHE_DIR).
    **This verdict is model-specific — do not generalise it (see the device note below).**
  - **OpenVINO whisper-base.en-int8 CPU: 0.75 / 1.1 / 1.96 s — all under the 2 s target.**
    With `initial_prompt="Vocabulary: Suryansh."` the 13.7 s clip transcribed word-perfect
    including the name → default model, dictionary fed via initial_prompt.
  - whisper.cpp v1.9.1 BLAS (alderlake build) small.en-q5_1: 3.1 s wall including ~1.5-2 s model
    load — competitive per-utterance but needs a persistent server or per-call load; not worth a
    second engine given OV meets target in-process.
  - Parakeet-TDT 0.6B v2 int8 via onnx-asr CPU: 3.8 / 7.7 / 14.2 s — far below its reputation on
    this chip; rejected.
  Model picker offers official OpenVINO int8 conversions: tiny.en / base.en (default) / small.en /
  base / small / large-v3-turbo (multilingual → language selection + auto-detect).
- **Device: "Auto" per model, not a global choice** (tests/bench_accel.py, 4.4 s clip, same box).
  The small.en GPU result above is real but does not transfer, because the models have opposite
  shapes:
  | model | CPU | GPU | verdict |
  |---|---|---|---|
  | large-v3-turbo | 8.02 s | **2.12 s** | GPU, 3.8x |
  | small (multilingual) | 1.49 s | 1.31 s | CPU — a wash short, GPU *loses* long (2.63 vs 2.27 s) |

  Those are raw `pipe.generate`. **What the user actually feels is 2.6x**, not 3.8x: driving the
  packaged app (hotkey release → text in Notepad, 3 dictations in a row) gives CPU 5.01 s cold /
  4.60 s warm vs GPU 3.01 s cold / **1.79 s warm**. The raw figure overstates it because the
  engine caps `max_new_tokens` by clip length, which the bench does not. Quote the app number.

  large-v3-turbo is ~79% encoder (32 encoder layers vs 4 decoder — the "turbo" design), and
  Whisper's encoder is a single fixed-size parallel pass over a 30 s mel: on CPU it costs a flat
  ~8 s whether the clip is 4.4 s or 13.7 s. Dense, parallel, no autoregression — an iGPU eats it.
  Small models spend their time in the memory-bound decoder loop instead, where the iGPU adds
  nothing. Hence `engine._GPU_WORTH_IT`, not a blanket "use the GPU if present".
  - CPU scheduling hints are a dead end: LATENCY / PCORE_ONLY / no-HT bought ≤5% (8.02 → 7.64 s).
    The encoder saturates the chip regardless of which cores it lands on.
  - **Accuracy is unchanged**, which is the only reason this was worth taking: 10 Kokoro-TTS
    Hindi/Hinglish clips with ground truth (tests/eval_device_accuracy.py) score CER 15.3% on both
    devices, 9/10 byte-identical, while the GPU is 2.43x faster end-to-end. (The 15.3% is a TTS
    artifact — Kokoro says "plan finalize" with a Hindi accent and Whisper faithfully writes
    "प्लान फाइनलाईस"; what matters here is that the two devices tie.)
  - Costs: first GPU compile ~15 s (not the 84 s of the 2024-era OpenVINO), then ~5 s loads, and
    ~900 MB of cached kernels. `Engine.load` falls back to CPU if the GPU can't run the model.
  - Rejected: restricting the language slot to en+hi via `suppress_tokens` to kill the auto-path's
    second decode. It works and is text-identical, but the second pass only fires on a mis-tag,
    which doesn't reproduce (Whisper tags hinglish.wav "hi" first try), and repeated runs showed
    no speed win — 3.51-4.28 s either way. The first 4.57 → 3.91 s reading was noise.
- **UI stack:** PySide6-Essentials (LGPL) for overlay pill, tray, settings, history — one framework.
- **Hotkeys:** custom WH_KEYBOARD_LL hook via ctypes (no `keyboard` lib) — chord hold Ctrl+Win
  (either side), toggle default Ctrl+Alt+D, both configurable via preset dropdowns.
- **Injection:** SendInput KEYEVENTF_UNICODE primary; clipboard-paste (save/restore) fallback for
  long text. Wait for physical modifier release before injecting.
- **Data dir:** `%LOCALAPPDATA%\Sotto` (config.json, history.jsonl, models\, app.log).
- **Install target:** `%LOCALAPPDATA%\Programs\Sotto` (keeps the ~large dist out of OneDrive),
  Start-menu shortcut, optional Startup shortcut from settings.

## Done & verified (each item has tool output in the build session)

- [x] Hardware probe: i7-1360P, 15.7 GB RAM, no NVIDIA GPU, Iris Xe iGPU.
- [x] Deps installed in `.venv` (openvino-genai 2026.2, PySide6 6.11, sounddevice, numpy,
      pyinstaller, pillow, huggingface_hub).
- [x] Mic smoke test: default device "Microphone Array (Intel Smart Sound)", 1 s captured.
- [x] Engine benchmark & selection (see Decisions) — models base.en + small.en downloaded to
      `%LOCALAPPDATA%\Sotto\models`.
- [x] textproc: 11/11 unit cases (commands, fillers, fuzzy dictionary "Suryongsh/Siryanch"→
      "Suryansh", "at gmail dot com"→"@gmail.com", URL protection, capitalization).
- [x] Injection round-trip into a real console: typed unicode (em-dash, café, 日本語) exact match;
      clipboard-paste path exact match; clipboard saved & restored. Fix found: trailing newline
      must be typed, not pasted.
- [x] 64-bit ctypes prototypes fixed (GlobalAlloc/GlobalLock/hooks — access violation otherwise).
- [x] Hotkey hook: chord down/up + toggle verified (test mode accepts only Sotto-tagged injected
      events; Windows injects phantom Ctrl around Win which polluted naive test mode).
- [x] Overlay pill: never steals focus (foreground hwnd unchanged); states render correctly
      (screenshots in tests/).
- [x] Full pipeline on the 27.6 s clip: 3 incremental chunks committed while "speaking"
      (23.3 s pre-transcribed), tail landed 0.94 s after stop, content word-exact.
- [x] Live app test (real process, injected hotkeys): dictation starts 2 ms after chord thanks to
      warm mic stream (cold WASAPI open took ~1.2 s and clipped first words — fixed by persistent
      stream that discards frames unless dictating); full cycle start→transcribe→(noise guard)
      ran clean; single instance verified (second launch exits, focuses settings).
- [x] Telemetry audit: openvino_telemetry only used by unused ovc converter; excluded from the
      package; app makes zero runtime network calls (model downloads are user-initiated).

- [x] Cleanup: deleted unused ct2/parakeet model downloads (~1.5 GB freed); kept
      whisper-base.en-int8-ov (81 MB) + whisper-small.en-int8-ov (245 MB) + ov-cache.
- [x] README.md written (install, launch, hotkeys, settings, model switching, admin note).
- [x] install.ps1 written (copies dist → %LOCALAPPDATA%\Programs\Sotto, Start-menu shortcuts
      incl. "Sotto (administrator)" with RunAsAdmin flag for elevated targets like the user's
      admin VS Code).

- [x] PyInstaller build (onedir, windowed, 420 MB) — includes the feeder-join fix (releasing the
      hotkey mid-chunk would have duplicated text on long dictations).
- [x] Packaged exe verified: `--selftest` transcribed the 13.7 s clip in 1.41 s, word-perfect
      including "Suryansh"; app launches, stays in tray, second launch exits (single instance).
- [x] Installed to `%LOCALAPPDATA%\Programs\Sotto\Sotto.exe`; Start-menu shortcuts "Sotto" and
      "Sotto (administrator)" created and verified; installed exe launched and left running.
- [x] Missing-model first-run path verified graceful (tray error + settings open, no crash).
- [x] dist/build removed from the OneDrive-synced project (rebuild: PyInstaller + install.ps1).

## v1 status: COMPLETE (packaged, installed, verified)

## v1.1 enhancements (requested after v1): live typing + multilingual

Decisions:
- **Multilingual by default.** Downloaded OpenVINO/whisper-small-int8-ov. Benchmark on this
  machine: with language=auto it detects English correctly and transcribes it identically to
  small.en at the same speed (2.5/3.0/4.0 s for 4.4/13.7/27.6 s clips — faster than realtime,
  keeps up with streaming). New default model `small (multilingual)`, language `auto`.
  Migrated existing config via config_version bump (1→2).
  - Verified Indian-accented English (WinRT en-IN "Heera" voice): multilingual got the name
    "Suryansh" right where base.en produced "Suryanj".
  - Forced `<|hi|>` path emits correct Devanagari ("तो मने कल का प्लान" from the Hinglish clip).
  - CAVEAT: no Hindi TTS voice exists on this machine, so true native-Hindi accuracy could not be
    synthesized/verified here. Validation covers the code path + Whisper's known Hindi capability;
    real spoken-Hindi accuracy is for the user to confirm.
  - Added `_collapse_repeats` guard: Whisper repeat-loops on noise/odd audio are collapsed before
    insertion (found via the synthetic Hinglish clip; also protects real silence/noise cases).
- **Live typing (streaming).** In toggle mode with `live_typing` (default on), committed chunks
  are typed at the cursor as you speak; only the tail lands at stop. Hold mode stays batch —
  the chord keys are physically held, so mid-hold typing would fire Ctrl+<char> shortcuts.
  Chunk commit thresholds: streaming (4 s min / 16 s max forced cut for pause-less monologues),
  batch (12/24). `DictationSession.feed()`/`finish()` now return chunk text; `full_text()` joins.

Verified (tool output this session):
- [x] test_streaming: 3 chunks typed progressively at 3.6/6.4/9.7 s into a 9.2 s recording,
      concatenating to the exact transcript; repetition guard collapses loops, spares normal text.
- [x] test_app_live: live process, toggle cycle logged `mode=toggle streaming=True`, full
      record→transcribe→insert cycle clean; hold cycle still batch; single instance intact.
- [x] Full suite green (textproc 11/11, inject, hook/overlay, pipeline, streaming, app_live).
- [x] Settings UI: added "Type as I speak" toggle + language/Hinglish help text (screenshot).

- [x] Rebuilt package; packaged --selftest with the multilingual model: state=ready,
      model=small (multilingual), transcribed the 13.7 s clip word-perfect (incl. "Suryansh")
      in 3.9 s via auto-detect.
- [x] Reinstalled to %LOCALAPPDATA%\Programs\Sotto; both shortcuts recreated; app relaunched
      and running. Build artifacts removed from the OneDrive project.

## v1.1 status: COMPLETE (superseded by v1.2 robustness pass)

## v1.2 — robustness pass (after user feedback: noise->foreign lang, Hindi->Urdu RTL,
##        English word errors, "model is very basic")

Investigated the openvino Whisper API (tests/probe_*.py) and found the real levers:
- `WhisperDecodedResults.language` exposes the DETECTED language (e.g. 'en', 'ur', 'nn').
- `repetition_penalty` works (kills repeat-loops); `suppress_tokens`/`no_repeat_ngram_size`
  are IGNORED by openvino. `language` forcing works via the config object.
- **initial_prompt was actively harmful** — a carry-over-context prompt made Whisper truncate
  a 6 s chunk to 5 words (verified same chunk: full with no prompt, truncated with prompt).
  Removed initial_prompt entirely; names handled by textproc post-correction. This was a big
  hidden cause of the "words mistaken"/dropped-words problem.
- large-v3-turbo benchmarked: ~10-11 s per utterance on this CPU (0.4x realtime) and WORSE on
  the name — not viable, deleted the 1.6 GB download. small (multilingual) stays default.
- Silero VAD: the master onnx is broken with onnxruntime (LSTM shape errors) — abandoned.

Fixes shipped:
1. **VAD noise gate** (sotto/vad.py, pure numpy): energy + spectral flatness. Static/white
   noise has flat spectrum (~0.85) vs speech (~0.2); gated before transcription. Verified:
   white noise / near-silence -> empty; real + Indian-accent speech pass.
2. **Language: detect-then-correct** (default "auto" = English+Hindi). Transcribe auto, read
   detected language + output script: Devanagari->keep; Arabic or Urdu/Indic->re-transcribe
   forcing Hindi (fixes Hindi rendered as right-to-left Urdu); Latin/en->keep; exotic script +
   exotic language->drop as noise. Modes: English / Hindi / Auto(en+hi) / Auto(all) / others.
   Tray "Language" submenu for one-click switching + settings dropdown.
3. **repetition_penalty=1.2** backstop for repeat-loops (1.3 clipped trailing words).
4. **Streaming word-loss fix**: forced mid-speech cuts drop words at hard seams; raised the
   forced-cut ceiling to ~24 s (near Whisper's 30 s window) so cuts happen at real pauses,
   plus overlap+dedup as best-effort for the rare forced case. `.en` models skip task/language
   (openvino rejects them).

Verified (tests/test_robustness.py, test_streaming.py, full suite all pass):
- Static noise (3 amplitudes) -> empty output (was: Japanese/Georgian/Khmer garbage).
- Plain English -> stays English/Latin, correct.
- Forced Hindi -> Devanagari left-to-right (was: Urdu right-to-left).
- Streaming -> complete transcript, all key phrases incl. the tail clause.

- [x] Rebuilt; packaged --selftest: word-perfect incl. "Suryansh" (no prompt needed), 3.68 s.
- [x] Reinstalled to %LOCALAPPDATA%\Programs\Sotto; both shortcuts; app running. Artifacts removed.

## v1.2 status: COMPLETE

CAVEAT unchanged: no Hindi TTS voice on this machine, so native-Hindi accuracy is validated by
the code path (Devanagari output, Urdu correction) + Whisper's known Hindi ability, not by a
real Hindi recording. The user should confirm with actual spoken Hindi.

## v1.3 — elevated-target (UIPI) edge case

Reported: inside an **elevated** app (a VS Code integrated terminal started as Administrator) the
hotkey showed no overlay and nothing was typed, while every normal-privilege app (Obsidian, Claude
Desktop, browsers) worked. Confirmed on-machine via process-token elevation + parent-chain walk:
`Sotto.exe` was non-elevated; the terminal's host chain (`Code.exe → … → powershell`) was elevated.
Windows **UIPI** blocks a normal-privilege process from *both* injecting input into and receiving
low-level keyboard-hook events for a higher-integrity window — so `WH_KEYBOARD_LL` never delivered
the chord while the terminal was focused (no `start_dictation`), and `SendInput` was silently
dropped (it still reports success, so no error surfaced — the app thought it had typed). A
toggle-stop pressed while the elevated terminal had focus was likewise missed, wedging the running
instance in `recording=True`, which then no-ops every later hotkey on the guard in `start_dictation`
(the log showed an unpaired `dictation started` as the last line).

Fixes shipped:
1. **UIPI detection** (sotto/inject.py): `foreground_injection_blocked()` compares the foreground
   window's process elevation to Sotto's (OpenProcess `PROCESS_QUERY_LIMITED_INFORMATION` +
   `GetTokenInformation`/`TokenElevation`; an unreadable/access-denied token is treated as
   higher-integrity). `insert_text()` returns False when blocked instead of pretending success, so
   the existing clipboard fallback fires and the pill shows "run Sotto as admin — text copied".
   Short-circuits to False when Sotto is itself elevated (it can type everywhere).
2. **Session watchdog** (sotto/app.py, `MAX_SESSION_S` = 20 min): a single-shot QTimer started with
   each session and cleared in `stop_dictation` auto-stops any session whose stop event was missed,
   so a wedged recording can no longer block all hotkeys indefinitely.
3. **Docs**: README FAQ + "Dictating into apps that run as Administrator" now cover the hotkey (not
   just typing) symptom, name the elevated-terminal case, and give a Task Scheduler recipe for
   silent elevated autostart at logon.

CAVEAT: the elevation check + watchdog only take effect once the packaged build is rebuilt
(PyInstaller) and reinstalled over `%LOCALAPPDATA%\Programs\Sotto`; the scheduled-task autostart
works independently of the rebuild.

## v1.3 status: COMPLETE (source + docs; rebuild pending on the user's machine)
