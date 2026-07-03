"""Download benchmark models to the app's models dir (Hugging Face official mirrors, free)."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from huggingface_hub import snapshot_download
from sotto.config import MODELS_DIR, MODELS

for name in ("small.en", "distil-small.en"):
    repo = MODELS[name][0]
    print(f"downloading {name} <- {repo}")
    path = snapshot_download(repo, local_dir=os.path.join(MODELS_DIR, name))
    print(f"done: {path}")
