"""Entry point: python -m sotto  (or the packaged Sotto.exe)."""

import logging
import os
import sys


def main():
    from .config import APP_DIR, LOG_PATH
    os.makedirs(APP_DIR, exist_ok=True)
    logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # --selftest <wav>: transcribe a file and write result next to it (for packaged smoke tests)
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        _selftest(sys.argv[2])
        return

    from PySide6.QtWidgets import QApplication
    from . import theme, APP_NAME
    from .app import SottoApp, already_running, make_icon

    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setApplicationName(APP_NAME)
    qapp.setStyleSheet(theme.QSS)
    if already_running():
        sys.exit(0)
    qapp.setWindowIcon(make_icon())
    app = SottoApp(qapp)
    sys.exit(qapp.exec())


def _selftest(wav_path):
    import time
    import wave
    import numpy as np
    from .config import Config
    from . import engine as eng
    from . import textproc

    cfg = Config()
    with wave.open(wav_path) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    e = eng.Engine()
    done = {}
    e.on_state = lambda s: done.update(state=s)
    e.load(cfg.get("model"), cfg.get("compute_device"))
    t0 = time.time()
    while done.get("state") not in ("ready", "error") and time.time() - t0 < 180:
        time.sleep(0.2)
    t0 = time.perf_counter()
    raw = e.transcribe(audio, cfg.get("language"), None)
    dt = time.perf_counter() - t0
    text = textproc.clean(raw, cfg.get("strip_fillers"), cfg.get("dictionary"))
    out = wav_path + ".selftest.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"state={done.get('state')}\nmodel={cfg.get('model')}\n"
                f"transcribe_seconds={dt:.2f}\ntext={text}\n")
    print(f"selftest -> {out}")


if __name__ == "__main__":
    main()
