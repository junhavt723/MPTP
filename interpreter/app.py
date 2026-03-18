"""
Korean → Tagalog Simultaneous Interpreter
Flask + SocketIO backend (works fully offline after model download)
"""

import os
import socket
import logging
import base64
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit

from translation import OfflineTranslator
from speech import SpeechRecognizer
from tts import TextToSpeech

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Lazy-loaded singletons
_translator: OfflineTranslator | None = None
_recognizer: SpeechRecognizer | None = None
_tts: TextToSpeech | None = None


def get_translator() -> OfflineTranslator:
    global _translator
    if _translator is None:
        _translator = OfflineTranslator(offline_mode=True)
        _translator.load()
    return _translator


def get_recognizer() -> SpeechRecognizer:
    global _recognizer
    if _recognizer is None:
        _recognizer = SpeechRecognizer(model_size="small", language="ko")
        _recognizer.load()
    return _recognizer


def get_tts() -> TextToSpeech:
    global _tts
    if _tts is None:
        _tts = TextToSpeech()
        _tts.load()
    return _tts


# ── HTTP Routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/translate", methods=["POST"])
def translate_text():
    """Translate plain Korean text (typed input)."""
    data = request.get_json(force=True)
    korean = (data.get("text") or "").strip()
    if not korean:
        return jsonify({"error": "텍스트를 입력해주세요."}), 400

    try:
        result = get_translator().translate_ko_to_tl(korean)
        if data.get("speak", False):
            get_tts().speak(result["tagalog"])
        return jsonify(result)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/status")
def status():
    """Return model availability status."""
    from pathlib import Path
    models_dir = Path(__file__).parent / "models"
    return jsonify({
        "ko_en_ready": (models_dir / "ko-en").exists(),
        "en_tl_ready": (models_dir / "en-tl").exists(),
        "whisper_ready": _recognizer is not None,
    })


@app.route("/static/sw.js")
def service_worker():
    """Serve service worker from /static/sw.js with correct headers."""
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "sw.js",
        mimetype="application/javascript",
    )


# ── WebSocket Events ─────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    logger.info(f"Client connected: {request.sid}")
    emit("status", {"message": "연결됨 (Connected)"})


@socketio.on("disconnect")
def on_disconnect():
    logger.info(f"Client disconnected: {request.sid}")


@socketio.on("audio_chunk")
def on_audio_chunk(data):
    """
    Receive a base64-encoded audio blob from the browser,
    transcribe → translate → emit result back.
    data: { "audio": "<base64>", "speak": true/false }
    """
    try:
        audio_b64 = data.get("audio", "")
        audio_bytes = base64.b64decode(audio_b64)
        speak = data.get("speak", False)

        recognizer = get_recognizer()
        korean = recognizer.transcribe_audio_bytes(audio_bytes)

        if not korean:
            emit("partial_result", {"korean": "", "english": "", "tagalog": ""})
            return

        emit("partial_result", {"korean": korean, "english": "...", "tagalog": "..."})

        result = get_translator().translate_ko_to_tl(korean)

        if speak:
            get_tts().speak(result["tagalog"])

        emit("translation_result", result)

    except FileNotFoundError as e:
        emit("error", {"message": str(e)})
    except Exception as e:
        logger.exception("Error processing audio chunk")
        emit("error", {"message": f"처리 오류: {e}"})


@socketio.on("translate_text")
def on_translate_text(data):
    """Translate text sent via WebSocket."""
    korean = (data.get("text") or "").strip()
    speak = data.get("speak", False)
    if not korean:
        return

    try:
        emit("partial_result", {"korean": korean, "english": "...", "tagalog": "..."})
        result = get_translator().translate_ko_to_tl(korean)
        if speak:
            get_tts().speak(result["tagalog"])
        emit("translation_result", result)
    except FileNotFoundError as e:
        emit("error", {"message": str(e)})
    except Exception as e:
        logger.exception("Translation error")
        emit("error", {"message": str(e)})


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "localhost"


def print_qr(url: str):
    """Print a tiny QR code in the terminal using unicode blocks."""
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        print()
        qr.print_ascii(invert=True)
    except ImportError:
        pass  # qrcode not installed – skip


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    local_ip = get_local_ip()
    local_url = f"https://{local_ip}:{port}"

    logger.info("=" * 55)
    logger.info("  Korean → Tagalog Interpreter  (PWA ready)")
    logger.info("=" * 55)
    logger.info(f"  Local:   https://localhost:{port}")
    logger.info(f"  Network: {local_url}")
    logger.info("")
    logger.info("  📱 같은 와이파이에서 휴대폰으로 접속:")
    logger.info(f"  {local_url}")
    logger.info("  ⚠️  브라우저에서 '보안 경고'가 뜨면 '고급 > 계속하기' 클릭")
    logger.info("  (또는 아래 QR 코드를 스캔하세요)")
    logger.info("=" * 55)

    print_qr(local_url)

    socketio.run(app, host="0.0.0.0", port=port, debug=False, ssl_context="adhoc")
