# Third-party notices

Sotto's own source code is licensed under the [MIT License](LICENSE). Sotto bundles and depends
on the following open-source components, each under its own license:

| Component | Purpose | License |
|---|---|---|
| OpenVINO / openvino-genai | On-device Whisper inference | Apache-2.0 |
| OpenAI Whisper model weights (via Intel's OpenVINO conversions) | Speech recognition models | MIT |
| PySide6 / Qt | GUI (tray, overlay, windows) | LGPL-3.0 |
| sounddevice | Microphone capture | MIT |
| PortAudio | Audio backend | MIT-style |
| NumPy | Numerical processing | BSD-3-Clause |
| huggingface_hub | One-time model download | Apache-2.0 |
| PyInstaller | Packaging | GPL-2.0 with a bootloader exception (does not affect Sotto's license) |

These components remain under their respective licenses. The MIT license in `LICENSE` covers only
Sotto's own source code. Qt/PySide6 is used under the LGPL; the packaged build keeps the Qt
libraries as separate, replaceable files (PyInstaller onedir) to preserve LGPL relinking rights.
