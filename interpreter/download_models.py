"""
One-time model download script.
Run this ONCE while connected to the internet:
    python download_models.py

After that the app runs fully offline.
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


def download_translation_models():
    from transformers import MarianMTModel, MarianTokenizer

    pairs = [
        ("Helsinki-NLP/opus-mt-ko-en", "ko-en"),
        ("Helsinki-NLP/opus-mt-en-tl", "en-tl"),
    ]
    for model_name, subdir in pairs:
        local = MODELS_DIR / subdir
        if local.exists():
            logger.info(f"[skip] {model_name} already downloaded at {local}")
            continue
        logger.info(f"Downloading {model_name}…")
        tok = MarianTokenizer.from_pretrained(model_name)
        mdl = MarianMTModel.from_pretrained(model_name)
        local.mkdir(parents=True, exist_ok=True)
        tok.save_pretrained(str(local))
        mdl.save_pretrained(str(local))
        logger.info(f"Saved → {local}")


def download_whisper_model(size: str = "small"):
    import whisper
    logger.info(f"Downloading Whisper '{size}' model…")
    whisper.load_model(size)
    logger.info("Whisper model cached.")


def download_socketio_js():
    """Download socket.io client for full offline browser support."""
    import urllib.request
    dest = Path(__file__).parent / "static" / "js" / "socket.io.min.js"
    if dest.exists():
        logger.info("[skip] socket.io.min.js already present")
        return
    url = "https://cdn.socket.io/4.6.0/socket.io.min.js"
    logger.info(f"Downloading socket.io client JS…")
    urllib.request.urlretrieve(url, dest)
    logger.info(f"Saved → {dest}")


if __name__ == "__main__":
    size = sys.argv[1] if len(sys.argv) > 1 else "small"

    logger.info("=" * 60)
    logger.info("Korean → Tagalog Interpreter – Model Downloader")
    logger.info(f"Whisper model size: {size}  (tiny/base/small/medium/large)")
    logger.info("=" * 60)

    try:
        download_translation_models()
    except Exception as e:
        logger.error(f"Translation model download failed: {e}")
        sys.exit(1)

    try:
        download_whisper_model(size)
    except Exception as e:
        logger.error(f"Whisper model download failed: {e}")
        sys.exit(1)

    try:
        download_socketio_js()
    except Exception as e:
        logger.warning(f"socket.io JS download failed (non-fatal): {e}")

    logger.info("")
    logger.info("All models downloaded. You can now use the app offline!")
    logger.info("Run:  python app.py")
