# 🎙️ 한국어 → 따갈로그어 동시통역 앱

**Korean ↔ Tagalog Simultaneous Interpreter** – 오프라인 완전 지원

---

## 기능

| 기능 | 설명 |
|------|------|
| 🎤 음성 입력 | 마이크로 한국어 말하기 → 실시간 따갈로그어 번역 |
| ⌨️ 텍스트 입력 | 한국어 타이핑 → 따갈로그어 번역 |
| 🔊 TTS 출력 | 번역된 따갈로그어를 음성으로 읽어줌 |
| 🔄 연속 통역 | 연속 모드: 자동으로 4초마다 번역 |
| 📋 번역 기록 | 세션 기록 저장 (로컬 스토리지) |
| 📡 완전 오프라인 | 최초 1회 다운로드 후 인터넷 불필요 |

## 번역 파이프라인

```
한국어 음성
    ↓ OpenAI Whisper (small, offline)
한국어 텍스트
    ↓ Helsinki-NLP/opus-mt-ko-en (offline)
English
    ↓ Helsinki-NLP/opus-mt-en-tl (offline)
Tagalog
    ↓ pyttsx3 TTS (offline)
음성 출력
```

---

## 설치 & 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt

# PyAudio가 실패할 경우 (Linux):
sudo apt-get install portaudio19-dev
pip install pyaudio

# macOS:
brew install portaudio && pip install pyaudio
```

### 2. 모델 다운로드 (최초 1회, 인터넷 필요)

```bash
python download_models.py
# Whisper 모델 크기 선택 (기본: small)
# tiny  (~75MB)  – 빠르지만 정확도 낮음
# small (~244MB) – 균형 (권장)
# medium (~769MB) – 정확도 높음
python download_models.py medium
```

### 3. 앱 실행 (오프라인 가능)

```bash
python app.py
```

브라우저에서 `http://localhost:5000` 열기

---

## 시스템 요구사항

- Python 3.10+
- RAM: 최소 4GB (small 모델 기준), 권장 8GB
- 디스크: ~1.5GB (모델 포함)
- 마이크 (음성 입력 시)

---

## 오프라인 사용 방법

1. 인터넷 연결 상태에서 `python download_models.py` 실행
2. 이후 인터넷 없이도 `python app.py` 실행 가능
3. 브라우저도 `localhost` 이므로 인터넷 불필요
