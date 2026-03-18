"""
Offline speech recognition using OpenAI Whisper.
Records audio from microphone and transcribes Korean speech.
"""

import io
import logging
import threading
import queue
import numpy as np
import whisper
import pyaudio

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_DURATION_SEC = 3      # process audio every N seconds
SILENCE_THRESHOLD = 0.01    # RMS below this = silence
SILENCE_CHUNKS = 2          # consecutive silent chunks before sending


class SpeechRecognizer:
    def __init__(self, model_size: str = "small", language: str = "ko"):
        self.model_size = model_size
        self.language = language
        self._model = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._running = False
        self._stream = None
        self._pa = None

    def load(self):
        logger.info(f"Loading Whisper model '{self.model_size}'...")
        self._model = whisper.load_model(self.model_size)
        logger.info("Whisper model loaded.")

    def _record_worker(self):
        chunk_size = int(SAMPLE_RATE * CHUNK_DURATION_SEC)
        frames = []
        silent_count = 0

        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=1024,
        )

        while self._running:
            raw = self._stream.read(1024, exception_on_overflow=False)
            audio_chunk = np.frombuffer(raw, dtype=np.float32)
            frames.append(audio_chunk)

            if len(frames) * 1024 >= chunk_size:
                audio_data = np.concatenate(frames)
                rms = float(np.sqrt(np.mean(audio_data ** 2)))

                if rms < SILENCE_THRESHOLD:
                    silent_count += 1
                else:
                    silent_count = 0
                    self._audio_queue.put(audio_data.copy())

                frames = []

        self._stream.stop_stream()
        self._stream.close()
        self._pa.terminate()

    def start_recording(self):
        if not self._model:
            self.load()
        self._running = True
        self._thread = threading.Thread(target=self._record_worker, daemon=True)
        self._thread.start()
        logger.info("Recording started.")

    def stop_recording(self):
        self._running = False
        logger.info("Recording stopped.")

    def transcribe_next(self, timeout: float = 5.0) -> str | None:
        """Block until audio is available, then transcribe. Returns None on timeout."""
        try:
            audio_data = self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

        result = self._model.transcribe(
            audio_data,
            language=self.language,
            fp16=False,
        )
        text = result["text"].strip()
        return text if text else None

    def transcribe_audio_bytes(self, audio_bytes: bytes) -> str:
        """Transcribe audio from raw bytes (from browser MediaRecorder)."""
        if not self._model:
            self.load()

        import soundfile as sf
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            result = self._model.transcribe(tmp_path, language=self.language, fp16=False)
            return result["text"].strip()
        finally:
            import os
            os.unlink(tmp_path)
