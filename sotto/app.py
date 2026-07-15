"""Sotto application: tray, dictation flow, wiring between hook/audio/engine/UI."""

import logging
import os
import threading
import time

import numpy as np
from PySide6.QtCore import QObject, Qt, Signal, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction, QActionGroup
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from . import APP_NAME, APP_VERSION, theme, history, inject, sounds, textproc
from .audio import Recorder, resolve_device, SILENCE_PEAK
from .config import Config, LOG_PATH
from .engine import Engine, DictationSession, is_downloaded
from .hotkey import HotkeyHook
from .overlay import OverlayPill
from .settings_ui import SettingsWindow
from .history_ui import HistoryWindow

log = logging.getLogger("sotto")
INSTANCE_KEY = "sotto-single-instance"
MIN_UTTERANCE_S = 0.35
# live-typing (toggle) commits at each speech pause for responsiveness; the max is
# the forced-cut ceiling for pause-less speech, kept near Whisper's 30 s window so
# forced mid-speech cuts (which can drop a word at the seam) stay rare.
# (min seconds before a commit, max before a forced cut)
STREAM_MIN_S, STREAM_MAX_S = 4, 24
BATCH_MIN_S, BATCH_MAX_S = 14, 26
# Safety net: if a session's stop event is missed (e.g. the stop key was pressed
# while an elevated window had focus, so our hook never saw it), the app would
# record forever and every later hotkey would no-op on the `recording` guard.
# Auto-stop any session that runs past this.
MAX_SESSION_S = 20 * 60


def make_icon(state="idle") -> QIcon:
    """Rounded dark square with 5 waveform bars (accent when active)."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#101014"))
    p.drawRoundedRect(2, 2, 60, 60, 16, 16)
    color = {"idle": theme.ACCENT, "recording": "#FF6B63",
             "loading": theme.MUTED, "error": theme.ERROR}.get(state, theme.ACCENT)
    p.setBrush(QColor(color))
    heights = [18, 30, 42, 30, 18] if state != "loading" else [10, 10, 10, 10, 10]
    for i, h in enumerate(heights):
        x = 12 + i * 9
        p.drawRoundedRect(x, 32 - h // 2, 5, h, 2.5, 2.5)
    p.end()
    return QIcon(pm)


class SottoApp(QObject):
    sig_hold_down = Signal()
    sig_hold_up = Signal()
    sig_toggle = Signal()
    sig_level = Signal(float)
    sig_engine_state = Signal(str)
    sig_finished = Signal(str, float, bool)   # cleaned text, seconds, inserted-ok

    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.cfg = Config()
        self.recording = False
        self.busy = False
        self.enabled = True
        self.session = None
        self._feeder = None
        self._streaming = False
        self._stream_full = ""
        self._stream_any_ok = False
        self._last_peak = 0.0

        self.overlay = OverlayPill()
        self.settings = SettingsWindow(self.cfg)
        self.historyw = HistoryWindow()

        # auto-stop a session whose stop event was missed (see MAX_SESSION_S)
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._on_watchdog)

        self.engine = Engine(on_state=self.sig_engine_state.emit)
        self.recorder = Recorder(on_level=self.sig_level.emit)
        self.hook = HotkeyHook(self.sig_hold_down.emit, self.sig_hold_up.emit,
                               self.sig_toggle.emit)
        if os.environ.get("SOTTO_ACCEPT_INJECTED") == "1":  # automated tests only
            self.hook.accept_injected = True
        self.hook.set_bindings(self.cfg.get("hold_chord"), self.cfg.get("toggle_combo"))
        self.hook.start()

        # tray
        self.tray = QSystemTrayIcon(make_icon("loading"))
        self.menu = QMenu()
        self.status_action = QAction("Loading model…")
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        self.menu.addSeparator()
        self.enable_action = QAction("Pause hotkeys")
        self.enable_action.setCheckable(True)
        self.enable_action.toggled.connect(self._toggle_enabled)
        self.menu.addAction(self.enable_action)
        # language quick-switch (no need to open Settings)
        self.lang_menu = self.menu.addMenu("Language")
        self.lang_group = QActionGroup(self.menu)
        self.lang_group.setExclusive(True)
        for label, code in (("Auto — English + Hindi", "auto"), ("English only", "en"),
                            ("Hindi only", "hi"), ("Auto — all languages", "auto-all")):
            a = QAction(label, checkable=True)
            a.setChecked(self.cfg.get("language") == code)
            a.triggered.connect(lambda _c=False, code=code: self._set_language(code))
            self.lang_group.addAction(a)
            self.lang_menu.addAction(a)
        act = QAction("Settings")
        act.triggered.connect(self.show_settings)
        self.menu.addAction(act)
        self._settings_action = act
        act2 = QAction("History")
        act2.triggered.connect(lambda: (self.historyw.show(), self.historyw.raise_()))
        self.menu.addAction(act2)
        self.menu.addSeparator()
        quit_action = QAction("Quit")
        quit_action.triggered.connect(self.quit)
        self.menu.addAction(quit_action)
        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip(f"{APP_NAME} — loading model…")
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        # wiring (queued to GUI thread where needed)
        self.sig_hold_down.connect(self._on_hold_down)
        self.sig_hold_up.connect(self.stop_dictation)
        self.sig_toggle.connect(self.toggle_dictation)
        self.sig_level.connect(self.overlay.push_level)
        self.sig_engine_state.connect(self._on_engine_state)
        self.sig_finished.connect(self._on_finished)
        self.settings.bindings_changed.connect(
            lambda: self.hook.set_bindings(self.cfg.get("hold_chord"),
                                           self.cfg.get("toggle_combo")))
        self.settings.model_change.connect(self._load_model)

        # single instance server: focus settings when relaunched
        self.server = QLocalServer()
        QLocalServer.removeServer(INSTANCE_KEY)
        self.server.listen(INSTANCE_KEY)
        self.server.newConnection.connect(self._on_second_instance)

        self._load_model(self.cfg.get("model"), self.cfg.get("compute_device"))
        self._warm_mic()

    def _warm_mic(self):
        """Open the persistent input stream off the GUI thread (takes ~1 s)."""
        def work():
            try:
                self.recorder.open(resolve_device(self.cfg.get("input_device")))
            except Exception as e:
                log.error("mic warm-open failed: %s", e)
        threading.Thread(target=work, name="mic-open", daemon=True).start()

    # ---------- model ----------

    def _load_model(self, name, device):
        if not is_downloaded(name):
            self.tray.setIcon(make_icon("error"))
            self._set_status(f"Model {name} not downloaded — open Settings")
            self.show_settings()
            return
        self.engine.load(name, device)

    def _on_engine_state(self, state):
        if state == "loading":
            self.tray.setIcon(make_icon("loading"))
            self._set_status("Loading model…")
        elif state == "ready":
            self.tray.setIcon(make_icon("idle"))
            hold = self.cfg.get("hold_chord")
            self._set_status(f"Ready — hold {hold} and speak")
        elif state == "error":
            self.tray.setIcon(make_icon("error"))
            self._set_status(f"Model error: {self.engine.error[:80]}")
            log.error("model load failed: %s", self.engine.error)

    def _set_status(self, text):
        self.status_action.setText(text)
        self.tray.setToolTip(f"{APP_NAME} — {text}")

    # ---------- dictation ----------

    def _on_hold_down(self):
        self.start_dictation("hold")

    def start_dictation(self, mode="hold"):
        if self.recording or self.busy or not self.enabled:
            return
        if self.engine.state != "ready":
            msg = "model still loading…" if self.engine.state == "loading" else "no model — open settings"
            self.overlay.show_state("error", msg)
            return
        try:
            self.recorder.begin(resolve_device(self.cfg.get("input_device")))
        except Exception as e:
            log.error("mic open failed: %s", e)
            self.overlay.show_state("error", "microphone unavailable")
            return
        # Live typing only in toggle mode: in hold mode the chord keys are still
        # physically down, so typing mid-hold would fire shortcuts (Ctrl+letter).
        self._streaming = mode == "toggle" and self.cfg.get("live_typing")
        self._stream_full = ""
        self._stream_any_ok = False
        min_s, max_s = (STREAM_MIN_S, STREAM_MAX_S) if self._streaming else (BATCH_MIN_S, BATCH_MAX_S)
        self.recording = True
        self._watchdog.start(MAX_SESSION_S * 1000)
        log.info("dictation started (mode=%s streaming=%s)", mode, self._streaming)
        self._t0 = time.monotonic()
        self.session = DictationSession(self.engine, self.recorder,
                                        self.cfg.get("language"),
                                        self.cfg.get("dictionary"), min_s, max_s)
        self._feeder_stop = threading.Event()
        self._feeder = threading.Thread(target=self._feed_loop, daemon=True)
        self._feeder.start()
        if self.cfg.get("sounds"):
            sounds.play("start")
        self.tray.setIcon(make_icon("recording"))
        self.overlay.show_state("listening")

    def _feed_loop(self):
        while not self._feeder_stop.wait(0.25):
            try:
                raw = self.session.feed()
                if raw and self._streaming:
                    chunk = textproc.clean(raw, self.cfg.get("strip_fillers"),
                                           self.cfg.get("dictionary"))
                    if any(c.isalnum() for c in chunk):
                        self._emit_chunk(chunk)
            except Exception:
                log.exception("feed failed")

    def _emit_chunk(self, chunk):
        """Type one streamed chunk at the cursor, managing spacing between chunks."""
        sep = ""
        if (self._stream_full and not self._stream_full.endswith((" ", "\n"))
                and not chunk.startswith(("\n", " "))):
            sep = " "
        ok = inject.insert_text(sep + chunk, self.cfg.get("injection"),
                                self.cfg.get("paste_threshold"))
        self._stream_full += sep + chunk
        self._stream_any_ok = self._stream_any_ok or ok

    def stop_dictation(self):
        self._watchdog.stop()
        log.info("stop_dictation (recording=%s)", self.recording)
        if not self.recording:
            return
        self.recording = False
        self._feeder_stop.set()
        duration = time.monotonic() - self._t0
        audio = self.recorder.end()
        # peak drives the muted-vs-quiet distinction in _on_finished, and is logged
        # so a dead mic is visible in app.log without reproducing it live
        self._last_peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        log.info("recorder stopped, %.1fs audio, peak=%.6f", len(audio) / 16000,
                 self._last_peak)
        if self.cfg.get("sounds"):
            sounds.play("stop")
        self.tray.setIcon(make_icon("idle"))
        if duration < MIN_UTTERANCE_S:
            self.overlay.dismiss()
            return
        self.busy = True
        self.overlay.show_state("transcribing")
        session = self.session
        threading.Thread(target=self._finish_worker,
                         args=(session, audio, duration, self._feeder),
                         daemon=True).start()

    def _on_watchdog(self):
        """A session outlived MAX_SESSION_S — its stop event was almost certainly
        missed (e.g. released over an elevated window). Commit and stop so hotkeys
        aren't wedged on the `recording` guard forever."""
        if not self.recording:
            return
        log.warning("session auto-stopped after %ds (stop event missed?)", MAX_SESSION_S)
        self.tray.showMessage(APP_NAME, "Dictation auto-stopped (was left running)",
                              make_icon("idle"), 2500)
        self.stop_dictation()

    def _finish_worker(self, session, audio, duration, feeder):
        try:
            # a feed() may still be mid-transcription; finishing before it lands
            # would slice the tail at a stale offset and duplicate that chunk
            if feeder is not None:
                feeder.join(timeout=60)
            tail_raw = session.finish(audio)
            if self._streaming:
                # committed chunks were already typed live; only the tail remains
                tail = textproc.clean(tail_raw, self.cfg.get("strip_fillers"),
                                      self.cfg.get("dictionary"))
                if any(c.isalnum() for c in tail):
                    self._emit_chunk(tail)
                full = self._stream_full.strip()
                self.sig_finished.emit(full, duration, self._stream_any_ok)
            else:
                text = textproc.clean(session.full_text(), self.cfg.get("strip_fillers"),
                                      self.cfg.get("dictionary"))
                if not any(c.isalnum() for c in text):  # noise -> punctuation-only output
                    text = ""
                ok = False
                if text:
                    ok = inject.insert_text(text, self.cfg.get("injection"),
                                            self.cfg.get("paste_threshold"))
                self.sig_finished.emit(text, duration, ok)
        except Exception:
            log.exception("transcription failed")
            self.sig_finished.emit("", duration, False)

    def _on_finished(self, text, duration, ok):
        self.busy = False
        log.info("dictation finished: %d chars, %.1fs, inserted=%s", len(text), duration, ok)
        if not text:
            # A muted mic still delivers frames, so an empty transcript alone can't
            # tell "you said nothing" from "nothing ever reached the mic" — the
            # peak can, and only the latter needs the user to go fix something.
            if self._last_peak < SILENCE_PEAK:
                log.warning("mic delivered silence (peak=%.6f) — muted or dead device",
                            self._last_peak)
                self.overlay.show_state("error", "no mic signal — check mic mute")
            else:
                self.overlay.show_state("error", "no speech detected")
            return
        if not ok:
            if inject.foreground_injection_blocked():
                msg = "run Sotto as admin — text copied"
            else:
                msg = "couldn't type — copied to clipboard"
            self.overlay.show_state("error", msg)
            inject._set_clipboard_text(text)
        else:
            self.overlay.show_state("inserted")
        if self.cfg.get("history_enabled"):
            history.append(text, duration)
        self.cfg.add_stats(textproc.word_count(text), duration)

    def toggle_dictation(self):
        if self.recording:
            self.stop_dictation()
        else:
            self.start_dictation("toggle")

    # ---------- misc ----------

    def _set_language(self, code):
        self.cfg.set("language", code)   # exclusive group handles the checkmark
        labels = {"auto": "English + Hindi", "en": "English", "hi": "Hindi",
                  "auto-all": "all languages"}
        self.tray.showMessage(APP_NAME, f"Language: {labels.get(code, code)}",
                              make_icon("idle"), 1500)

    def _toggle_enabled(self, paused):
        self.enabled = not paused
        self._set_status("Hotkeys paused" if paused else
                         f"Ready — hold {self.cfg.get('hold_chord')} and speak")

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_settings()

    def show_settings(self):
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def _on_second_instance(self):
        sock = self.server.nextPendingConnection()
        if sock:
            sock.disconnectFromServer()
        self.show_settings()

    def quit(self):
        self.hook.stop()
        self.recorder.end()
        self.recorder.close()
        self.tray.hide()
        self.qapp.quit()


def already_running() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.disconnectFromServer()
        return True
    return False
