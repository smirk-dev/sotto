"""Settings window: frameless dark card, single scrolling column of sections."""

import logging
import os
import shutil
import subprocess
import sys
import threading

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QPushButton,
    QLineEdit, QListWidget, QScrollArea, QFrame, QProgressBar, QSpinBox,
)

from . import theme, history, engine
from .config import MODELS, HOLD_CHORDS, TOGGLE_COMBOS, APP_DIR
from .audio import list_input_devices
from . import APP_NAME, APP_VERSION

log = logging.getLogger("sotto")

# (label, code) — code is what the engine gets. "auto" = English+Hindi (constrained,
# the robust default); "auto-all" = unconstrained 99-language detection.
LANGS = [
    ("Auto — English + Hindi", "auto"),
    ("English only", "en"),
    ("Hindi only (हिन्दी)", "hi"),
    ("Auto — all languages", "auto-all"),
    ("Spanish", "es"), ("French", "fr"), ("German", "de"), ("Portuguese", "pt"),
    ("Japanese", "ja"), ("Chinese", "zh"), ("Arabic", "ar"), ("Russian", "ru"),
]

# (label, code). "Auto" picks per model — the iGPU is a big win for the encoder-heavy
# large model and a slight loss for the small ones, so it is not a blanket choice;
# see engine.resolve_compute_device. The explicit options stay for troubleshooting.
COMPUTE_DEVICES = [
    ("Auto (recommended)", "Auto"),
    ("CPU", "CPU"),
    ("GPU (Intel graphics)", "GPU"),
]

STARTUP_DIR = os.path.join(os.environ.get("APPDATA", ""),
                           "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
STARTUP_LNK = os.path.join(STARTUP_DIR, "Sotto.lnk")


def _make_shortcut(lnk_path, target, workdir):
    ps = (f"$ws = New-Object -ComObject WScript.Shell; "
          f"$s = $ws.CreateShortcut('{lnk_path}'); "
          f"$s.TargetPath = '{target}'; $s.WorkingDirectory = '{workdir}'; $s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   creationflags=subprocess.CREATE_NO_WINDOW, check=False)


def _set_autostart_windows(enable: bool):
    if enable:
        exe = sys.executable
        # packaged: Sotto.exe itself; dev: pythonw + -m sotto
        if exe.lower().endswith(("python.exe", "pythonw.exe")):
            return  # dev mode — skip silently
        _make_shortcut(STARTUP_LNK, exe, os.path.dirname(exe))
    else:
        try:
            os.remove(STARTUP_LNK)
        except OSError:
            pass


# freedesktop autostart: a .desktop dropped here is launched at login.
AUTOSTART_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config"),
    "autostart")
AUTOSTART_DESKTOP = os.path.join(AUTOSTART_DIR, "sotto.desktop")


def _set_autostart_linux(enable: bool):
    if enable:
        # Prefer the installed launcher (AUR: /usr/bin/sotto); fall back to running
        # this interpreter with -m sotto when developing from source.
        exec_cmd = shutil.which("sotto") or f"{sys.executable} -m sotto"
        os.makedirs(AUTOSTART_DIR, exist_ok=True)
        with open(AUTOSTART_DESKTOP, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\n"
                    "Type=Application\n"
                    f"Name={APP_NAME}\n"
                    f"Exec={exec_cmd}\n"
                    "Icon=sotto\n"
                    "Terminal=false\n"
                    "X-GNOME-Autostart-enabled=true\n")
    else:
        try:
            os.remove(AUTOSTART_DESKTOP)
        except OSError:
            pass


def set_autostart(enable: bool):
    if sys.platform == "win32":
        _set_autostart_windows(enable)
    else:
        _set_autostart_linux(enable)


class TitleBar(QWidget):
    def __init__(self, title, window):
        super().__init__()
        self._window = window
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 12, 12, 8)
        lbl = QLabel(title)
        lbl.setProperty("h1", True)
        lay.addWidget(lbl)
        lay.addStretch()
        close = QPushButton("×")
        close.setFixedSize(30, 30)
        close.setStyleSheet("QPushButton { border: none; background: transparent; color: #8A8A96;"
                            "  font-size: 20px; }"
                            "QPushButton:hover { color: #EAEAF0; background: #26262E; border-radius: 8px; }")
        close.clicked.connect(window.hide)
        lay.addWidget(close)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._window.windowHandle().startSystemMove()


class LevelBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(10)
        self.level = 0.0

    def set_level(self, v):
        self.level = v
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.SURFACE))
        p.drawRoundedRect(self.rect(), 5, 5)
        w = int(self.width() * min(1.0, self.level))
        if w > 4:
            p.setBrush(QColor(theme.ACCENT))
            p.drawRoundedRect(0, 0, w, self.height(), 5, 5)
        p.end()


def section(title):
    box = QFrame()
    box.setStyleSheet(f"QFrame {{ background: {theme.SURFACE}; border-radius: {theme.RADIUS}px; }}")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(10)
    lbl = QLabel(title)
    lbl.setStyleSheet(f"color: {theme.MUTED}; font-weight: 600; font-size: 11px;"
                      "letter-spacing: 1px; background: transparent;")
    lay.addWidget(lbl)
    return box, lay


def row(label, widget):
    r = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setStyleSheet("background: transparent;")
    r.addWidget(lbl)
    r.addStretch()
    widget.setMinimumWidth(220)
    r.addWidget(widget)
    return r


class SettingsWindow(QWidget):
    bindings_changed = Signal()
    model_change = Signal(str, str)      # model name, device
    mic_level = Signal(float)

    def __init__(self, cfg):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool)
        self.cfg = cfg
        self.setWindowTitle(f"{APP_NAME} settings")
        self.setFixedSize(560, 720)
        self._meter_stream = None
        self._dl_timer = QTimer(self)
        self._dl_timer.timeout.connect(self._poll_download)
        self._dl_model = None      # model currently downloading, or None
        self._dl_thread = None
        self._dl_error = None
        self._dl_total = None      # expected bytes, or None while unknown

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TitleBar(f"{APP_NAME} — settings", self))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(18, 6, 18, 18)
        col.setSpacing(12)

        # ---- hotkeys ----
        box, lay = section("HOTKEYS")
        self.hold_combo = QComboBox()
        self.hold_combo.addItems(HOLD_CHORDS)
        self.hold_combo.setCurrentText(cfg.get("hold_chord"))
        self.hold_combo.currentTextChanged.connect(self._save_bindings)
        lay.addLayout(row("Hold to dictate", self.hold_combo))
        self.toggle_combo = QComboBox()
        self.toggle_combo.addItems(TOGGLE_COMBOS)
        self.toggle_combo.setCurrentText(cfg.get("toggle_combo"))
        self.toggle_combo.currentTextChanged.connect(self._save_bindings)
        lay.addLayout(row("Toggle dictation", self.toggle_combo))
        col.addWidget(box)

        # ---- microphone ----
        box, lay = section("MICROPHONE")
        self.dev_combo = QComboBox()
        self.dev_combo.currentTextChanged.connect(self._save_device)
        lay.addLayout(row("Input device", self.dev_combo))
        self.meter = LevelBar()
        lay.addWidget(self.meter)
        self.mic_level.connect(self.meter.set_level)
        col.addWidget(box)

        # ---- model ----
        box, lay = section("MODEL & LANGUAGE")
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self._on_model_selected)
        lay.addLayout(row("Model", self.model_combo))
        self.model_note = QLabel("")
        self.model_note.setProperty("muted", True)
        self.model_note.setWordWrap(True)
        lay.addWidget(self.model_note)
        dl_row = QHBoxLayout()
        self.dl_btn = QPushButton("Download")
        self.dl_btn.setProperty("accent", True)
        self.dl_btn.clicked.connect(self._start_download)
        dl_row.addWidget(self.dl_btn)
        self.dl_bar = QProgressBar()
        self.dl_bar.setRange(0, 0)
        self.dl_bar.hide()
        dl_row.addWidget(self.dl_bar, 1)
        self.dl_status = QLabel("")
        self.dl_status.setProperty("muted", True)
        dl_row.addWidget(self.dl_status)
        lay.addLayout(dl_row)
        self.device_combo = QComboBox()
        for label, code in COMPUTE_DEVICES:
            self.device_combo.addItem(label, userData=code)
        cur_dev = cfg.get("compute_device")
        for i in range(self.device_combo.count()):
            if self.device_combo.itemData(i) == cur_dev:
                self.device_combo.setCurrentIndex(i)
                break
        self.device_combo.currentIndexChanged.connect(self._save_compute)
        lay.addLayout(row("Run on", self.device_combo))
        self.lang_combo = QComboBox()
        for label, code in LANGS:
            self.lang_combo.addItem(label, userData=code)
        cur = cfg.get("language")
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == cur:
                self.lang_combo.setCurrentIndex(i)
                break
        self.lang_combo.currentIndexChanged.connect(
            lambda i: cfg.set("language", self.lang_combo.itemData(i)))
        lay.addLayout(row("Language", self.lang_combo))
        lang_hint = QLabel("“Auto — English + Hindi” transcribes both and auto-corrects Hindi "
                           "that Whisper mistakes for Urdu. Pick “English only” or “Hindi only” "
                           "for the most reliable results in one language. (English-only models "
                           "like base.en are fastest for pure English.)")
        lang_hint.setProperty("muted", True)
        lang_hint.setWordWrap(True)
        lay.addWidget(lang_hint)
        col.addWidget(box)

        # ---- typing ----
        box, lay = section("TYPING & FORMATTING")
        self.inject_combo = QComboBox()
        self.inject_combo.addItems(["Simulated typing (recommended)", "Clipboard paste"])
        self.inject_combo.setCurrentIndex(1 if cfg.get("injection") == "paste" else 0)
        self.inject_combo.currentIndexChanged.connect(
            lambda i: cfg.set("injection", "paste" if i else "type"))
        lay.addLayout(row("Insert text by", self.inject_combo))
        self.fillers_cb = QCheckBox("Remove filler words (um, uh…)")
        self.fillers_cb.setChecked(cfg.get("strip_fillers"))
        self.fillers_cb.toggled.connect(lambda v: cfg.set("strip_fillers", v))
        lay.addWidget(self.fillers_cb)
        self.sounds_cb = QCheckBox("Play sounds on start/stop")
        self.sounds_cb.setChecked(cfg.get("sounds"))
        self.sounds_cb.toggled.connect(lambda v: cfg.set("sounds", v))
        lay.addWidget(self.sounds_cb)
        self.live_cb = QCheckBox("Type as I speak (live dictation in toggle mode)")
        self.live_cb.setChecked(cfg.get("live_typing"))
        self.live_cb.toggled.connect(lambda v: cfg.set("live_typing", v))
        lay.addWidget(self.live_cb)
        live_hint = QLabel("Text appears in real time while you dictate with the toggle "
                           "hotkey. Hold-to-talk always inserts on release.")
        live_hint.setProperty("muted", True)
        live_hint.setWordWrap(True)
        lay.addWidget(live_hint)
        col.addWidget(box)

        # ---- dictionary ----
        box, lay = section("CUSTOM DICTIONARY")
        hint = QLabel("Names and jargon that Whisper should get right.")
        hint.setProperty("muted", True)
        lay.addWidget(hint)
        self.dict_list = QListWidget()
        self.dict_list.setFixedHeight(110)
        for w in cfg.get("dictionary"):
            self.dict_list.addItem(w)
        lay.addWidget(self.dict_list)
        dr = QHBoxLayout()
        self.dict_edit = QLineEdit()
        self.dict_edit.setPlaceholderText("Add a word…")
        self.dict_edit.returnPressed.connect(self._dict_add)
        dr.addWidget(self.dict_edit, 1)
        add = QPushButton("Add")
        add.clicked.connect(self._dict_add)
        dr.addWidget(add)
        rem = QPushButton("Remove")
        rem.clicked.connect(self._dict_remove)
        dr.addWidget(rem)
        lay.addLayout(dr)
        col.addWidget(box)

        # ---- history & privacy ----
        box, lay = section("HISTORY & PRIVACY")
        self.hist_cb = QCheckBox("Keep dictation history (stored only on this PC)")
        self.hist_cb.setChecked(cfg.get("history_enabled"))
        self.hist_cb.toggled.connect(lambda v: cfg.set("history_enabled", v))
        lay.addWidget(self.hist_cb)
        hr = QHBoxLayout()
        clear_btn = QPushButton("Clear history")
        clear_btn.clicked.connect(lambda: (history.clear(), self._flash(clear_btn, "Cleared")))
        hr.addWidget(clear_btn)
        open_btn = QPushButton("Open data folder")
        open_btn.clicked.connect(lambda: os.startfile(APP_DIR))
        hr.addWidget(open_btn)
        hr.addStretch()
        lay.addLayout(hr)
        col.addWidget(box)

        # ---- stats ----
        box, lay = section("SESSION STATS")
        self.stats_lbl = QLabel("")
        self.stats_lbl.setProperty("muted", True)
        lay.addWidget(self.stats_lbl)
        col.addWidget(box)

        # ---- system ----
        box, lay = section("SYSTEM")
        _autostart_label = ("Start Sotto when Windows starts" if sys.platform == "win32"
                            else "Start Sotto on login")
        self.autostart_cb = QCheckBox(_autostart_label)
        self.autostart_cb.setChecked(cfg.get("start_with_windows"))
        self.autostart_cb.toggled.connect(self._save_autostart)
        lay.addWidget(self.autostart_cb)
        about = QLabel(f"{APP_NAME} {APP_VERSION} — 100% local, open-source, free. "
                       "Audio never leaves this computer.")
        about.setProperty("muted", True)
        about.setWordWrap(True)
        lay.addWidget(about)
        col.addWidget(box)

        col.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.setStyleSheet(theme.QSS + f"QWidget {{ border: none; }} "
                           f"SettingsWindow {{ background: {theme.BG}; border: 1px solid {theme.BORDER}; "
                           f"border-radius: 0px; }}")
        self._refresh_models()

    # ---------- helpers ----------

    def _flash(self, btn, text):
        old = btn.text()
        btn.setText(text)
        QTimer.singleShot(1200, lambda: btn.setText(old))

    def _save_bindings(self):
        self.cfg.set("hold_chord", self.hold_combo.currentText())
        self.cfg.set("toggle_combo", self.toggle_combo.currentText())
        self.bindings_changed.emit()

    def _save_device(self, name):
        if name:
            self.cfg.set("input_device", None if name.startswith("System default") else name)

    def _save_compute(self, idx):
        self.cfg.set("compute_device", self.device_combo.itemData(idx))
        self.model_change.emit(self.cfg.get("model"), self.cfg.get("compute_device"))

    def _save_autostart(self, v):
        self.cfg.set("start_with_windows", v)   # config key kept for back-compat
        set_autostart(v)

    def _dict_add(self):
        w = self.dict_edit.text().strip()
        if w:
            self.dict_list.addItem(w)
            self.dict_edit.clear()
            self._save_dict()

    def _dict_remove(self):
        for item in self.dict_list.selectedItems():
            self.dict_list.takeItem(self.dict_list.row(item))
        self._save_dict()

    def _save_dict(self):
        words = [self.dict_list.item(i).text() for i in range(self.dict_list.count())]
        self.cfg.set("dictionary", words)

    # ---------- model section ----------

    def _refresh_models(self):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for name in MODELS:
            mark = "  ✓" if engine.is_downloaded(name) else ""
            self.model_combo.addItem(f"{name}{mark}", userData=name)
        current = self.cfg.get("model")
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == current:
                self.model_combo.setCurrentIndex(i)
                break
        self.model_combo.blockSignals(False)
        self._update_model_ui()

    def _selected_model(self):
        return self.model_combo.currentData()

    def _on_model_selected(self):
        name = self._selected_model()
        if not name:
            return
        self._update_model_ui()
        if engine.is_downloaded(name):
            self.cfg.set("model", name)
            self.model_change.emit(name, self.cfg.get("compute_device"))

    def _update_model_ui(self):
        """Reflect the selected model, including a download already in flight.

        Downloads outlive this window, so a reopen (or switching models and back)
        has to restore the in-progress view. It used to unconditionally re-show
        Download, which then silently no-op'd against the in-flight guard.
        """
        name = self._selected_model()
        if not name:
            return
        _repo, size, note = MODELS[name]
        self.model_note.setText(f"{size} — {note}")
        downloading = self._dl_model is not None
        showing_download = downloading and name == self._dl_model
        self.dl_btn.setVisible(not engine.is_downloaded(name) and not downloading)
        self.dl_bar.setVisible(showing_download)
        if showing_download:
            self._render_progress()
        elif downloading:
            self.dl_status.setText(f"downloading {self._dl_model}…")
        elif engine.is_downloaded(name):
            self.dl_status.setText("")
        else:
            self.dl_status.setText("")

    def _start_download(self):
        name = self._selected_model()
        if not name or self._dl_model:
            return
        self._dl_model = name
        self._dl_error = None
        self._dl_total = None
        self.dl_btn.hide()
        self.dl_bar.setRange(0, 0)      # indeterminate until the total is known
        self.dl_bar.show()
        self.dl_status.setText("starting…")

        def work():
            try:
                # total first, so the bar can be determinate; None if the Hub
                # can't be reached, in which case the download will fail anyway
                self._dl_total = engine.expected_bytes(name)
                engine.download_model(name)
                self._dl_error = None
            except Exception as e:
                self._dl_error = str(e) or e.__class__.__name__
                log.exception("model download failed: %s", name)

        self._dl_thread = threading.Thread(target=work, name="model-download",
                                           daemon=True)
        self._dl_thread.start()
        self._dl_timer.start(500)

    def _render_progress(self):
        """Paint the bar/label from bytes on disk. Safe to call any time."""
        name = self._dl_model
        if not name:
            return
        got = engine.downloaded_bytes(name)
        total = self._dl_total
        if total:
            pct = min(100, int(got * 100 / total))
            self.dl_bar.setRange(0, 100)
            self.dl_bar.setValue(pct)
            self.dl_status.setText(f"{got/1e6:.0f} / {total/1e6:.0f} MB")
        else:
            self.dl_bar.setRange(0, 0)
            self.dl_status.setText(f"{got/1e6:.0f} MB…")

    def _poll_download(self):
        name = self._dl_model
        if name is None:
            self._dl_timer.stop()
            return
        if self._dl_thread.is_alive():
            if name == self._selected_model():
                self._render_progress()
            return
        # finished (or failed) — settle the UI
        self._dl_timer.stop()
        self._dl_model = None
        self.dl_bar.hide()
        # refresh first: it re-marks "✓", restores the button, and blanks the
        # status line — so the outcome has to be written after it, not before
        self._refresh_models()
        if self._dl_error:
            self.dl_status.setText(self._download_error_text(self._dl_error))
            return
        self.dl_status.setText("downloaded ✓")
        if engine.is_downloaded(name):
            # switch to what was actually downloaded, not whatever is selected now
            self.cfg.set("model", name)
            self.model_change.emit(name, self.cfg.get("compute_device"))

    @staticmethod
    def _download_error_text(err):
        """A cause the user can act on — it isn't always the internet."""
        low = err.lower()
        if "incomplete" in low:
            return "download incomplete — click Download to resume"
        if "space" in low or "disk" in low:
            return "download failed — not enough disk space"
        if "permission" in low or "access is denied" in low:
            return "download failed — permission denied"
        if any(s in low for s in ("connect", "timeout", "timed out", "resolve",
                                  "network", "ssl", "proxy")):
            return "download failed — check your internet connection"
        return f"download failed — {err[:60]}"

    # ---------- stats + mic meter lifecycle ----------

    def _update_stats(self):
        s = self.cfg.get("stats")
        words, utt, secs = s["words"], s["utterances"], s["audio_seconds"]
        typing_min = words / 40.0                  # 40 wpm typing
        saved = max(0.0, typing_min - secs / 60.0)
        self.stats_lbl.setText(
            f"{words:,} words dictated across {utt:,} dictations · "
            f"{secs/60:.1f} min of speech · ≈{saved:.0f} min saved vs. typing")

    def _refresh_devices(self):
        self.dev_combo.blockSignals(True)
        self.dev_combo.clear()
        self.dev_combo.addItem("System default")
        current = self.cfg.get("input_device")
        for _idx, name in list_input_devices():
            self.dev_combo.addItem(name)
            if current and current == name:
                self.dev_combo.setCurrentText(name)
        self.dev_combo.blockSignals(False)

    def showEvent(self, e):
        super().showEvent(e)
        self._refresh_devices()
        self._refresh_models()
        self._update_stats()
        self._start_meter()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._stop_meter()

    def _start_meter(self):
        if self._meter_stream:
            return
        from .audio import open_input_stream, resolve_device
        try:
            def cb(indata, frames, t, status):
                rms = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
                self.mic_level.emit(min(1.0, rms * 18.0))
            self._meter_stream = open_input_stream(
                resolve_device(self.cfg.get("input_device")), cb)
            self._meter_stream.start()
        except Exception:
            log.exception("mic meter failed to open")
            self._meter_stream = None

    def _stop_meter(self):
        if self._meter_stream:
            try:
                self._meter_stream.stop()
                self._meter_stream.close()
            except Exception:
                pass
            self._meter_stream = None
