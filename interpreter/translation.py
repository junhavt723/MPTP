"""
Offline translation pipeline: Korean → English → Tagalog
Uses Helsinki-NLP MarianMT models (downloaded once, runs fully offline)
"""

import os
import logging
from pathlib import Path
from transformers import MarianMTModel, MarianTokenizer

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

KO_EN_MODEL = "Helsinki-NLP/opus-mt-ko-en"
EN_TL_MODEL = "Helsinki-NLP/opus-mt-en-tl"


class OfflineTranslator:
    def __init__(self, offline_mode: bool = True):
        self.offline_mode = offline_mode
        self._ko_en_tokenizer = None
        self._ko_en_model = None
        self._en_tl_tokenizer = None
        self._en_tl_model = None

    def _load_model(self, model_name: str, local_subdir: str):
        local_path = MODELS_DIR / local_subdir
        if local_path.exists():
            logger.info(f"Loading model from local cache: {local_path}")
            tokenizer = MarianTokenizer.from_pretrained(str(local_path))
            model = MarianMTModel.from_pretrained(str(local_path))
        else:
            if self.offline_mode:
                raise FileNotFoundError(
                    f"Model not found at {local_path}. "
                    "Run download_models.py first to enable offline use."
                )
            logger.info(f"Downloading model: {model_name}")
            tokenizer = MarianTokenizer.from_pretrained(model_name)
            model = MarianMTModel.from_pretrained(model_name)
            # Save for offline use
            local_path.mkdir(parents=True, exist_ok=True)
            tokenizer.save_pretrained(str(local_path))
            model.save_pretrained(str(local_path))
            logger.info(f"Model saved to {local_path}")
        return tokenizer, model

    def load(self):
        logger.info("Loading KO→EN model...")
        self._ko_en_tokenizer, self._ko_en_model = self._load_model(
            KO_EN_MODEL, "ko-en"
        )
        logger.info("Loading EN→TL model...")
        self._en_tl_tokenizer, self._en_tl_model = self._load_model(
            EN_TL_MODEL, "en-tl"
        )
        logger.info("Translation models loaded.")

    def _translate(self, text: str, tokenizer, model) -> str:
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        translated = model.generate(**inputs, num_beams=4, early_stopping=True)
        return tokenizer.decode(translated[0], skip_special_tokens=True)

    def translate_ko_to_tl(self, korean_text: str) -> dict:
        """Translate Korean text to Tagalog via English intermediate."""
        if not self._ko_en_model:
            self.load()

        english = self._translate(korean_text, self._ko_en_tokenizer, self._ko_en_model)
        tagalog = self._translate(english, self._en_tl_tokenizer, self._en_tl_model)

        return {
            "korean": korean_text,
            "english": english,
            "tagalog": tagalog,
        }
