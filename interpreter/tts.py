"""
Offline text-to-speech using pyttsx3.
Speaks the Tagalog translation aloud.
"""

import logging
import threading
import pyttsx3

logger = logging.getLogger(__name__)


class TextToSpeech:
    def __init__(self, rate: int = 150, volume: float = 1.0):
        self._rate = rate
        self._volume = volume
        self._engine = None
        self._lock = threading.Lock()

    def load(self):
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", self._rate)
        self._engine.setProperty("volume", self._volume)
        logger.info("TTS engine initialized.")

    def speak(self, text: str):
        """Speak text in a background thread (non-blocking)."""
        if not self._engine:
            self.load()

        def _run():
            with self._lock:
                self._engine.say(text)
                self._engine.runAndWait()

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def stop(self):
        if self._engine:
            with self._lock:
                self._engine.stop()
