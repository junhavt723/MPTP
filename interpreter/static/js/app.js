'use strict';

/* ── DOM refs ── */
const $  = id => document.getElementById(id);
const tabs = document.querySelectorAll('.tab');
const tabContents = document.querySelectorAll('.tab-content');

const btnRecord     = $('btn-record');
const recIndicator  = $('recording-indicator');
const chkSpeakVoice = $('chk-speak-voice');
const chkContinuous = $('chk-continuous');
const voiceResult   = $('voice-result');
const voiceKorean   = $('voice-korean');
const voiceEnglish  = $('voice-english');
const voiceTagalog  = $('voice-tagalog');

const txtKorean     = $('txt-korean');
const btnTranslate  = $('btn-translate');
const chkSpeakText  = $('chk-speak-text');
const textResult    = $('text-result');
const textKorean    = $('text-korean');
const textEnglish   = $('text-english');
const textTagalog   = $('text-tagalog');

const historyList   = $('history-list');
const btnClearHist  = $('btn-clear-history');

const loadingOverlay = $('loading-overlay');
const loadingText    = $('loading-text');
const errorToast     = $('error-toast');
const statusText     = $('status-text');
const connDot        = $('conn-indicator');

/* ── State ── */
let socket = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let continuousTimer = null;
let history = JSON.parse(localStorage.getItem('interp-history') || '[]');

/* ── Tab switching ── */
tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    tabs.forEach(t => t.classList.remove('active'));
    tabContents.forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    $('tab-' + tab.dataset.tab).classList.add('active');
    if (tab.dataset.tab === 'history') renderHistory();
  });
});

/* ── Socket.IO ── */
function initSocket() {
  socket = io({ transports: ['websocket'] });

  socket.on('connect', () => {
    connDot.className = 'dot connected';
    checkModelStatus();
  });

  socket.on('disconnect', () => {
    connDot.className = 'dot disconnected';
    statusText.textContent = '연결 끊김';
  });

  socket.on('status', data => {
    statusText.textContent = data.message;
  });

  socket.on('partial_result', data => {
    showVoiceResult(data);
    setLoading(false);
  });

  socket.on('translation_result', data => {
    showVoiceResult(data);
    addHistory(data);
    setLoading(false);

    if (chkContinuous.checked && isRecording) {
      startSegment();
    }
  });

  socket.on('error', data => {
    showError(data.message);
    setLoading(false);
  });
}

/* ── Model status check ── */
async function checkModelStatus() {
  try {
    const r = await fetch('/api/status');
    const s = await r.json();
    if (s.ko_en_ready && s.en_tl_ready) {
      statusText.textContent = '오프라인 모드 준비됨 ✓';
    } else {
      statusText.textContent = '⚠ 모델 미설치 – download_models.py 실행 필요';
    }
  } catch { /* ignore */ }
}

/* ── Recording ── */
btnRecord.addEventListener('click', toggleRecording);

async function toggleRecording() {
  if (isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  if (!navigator.mediaDevices) {
    showError('마이크 접근 불가: HTTPS 또는 localhost 필요');
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    isRecording = true;
    btnRecord.classList.add('recording');
    btnRecord.querySelector('.mic-label').textContent = '중지';
    recIndicator.classList.remove('hidden');
    startSegment(stream);
  } catch (e) {
    showError('마이크 오류: ' + e.message);
  }
}

function stopRecording() {
  isRecording = false;
  clearTimeout(continuousTimer);
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  btnRecord.classList.remove('recording');
  btnRecord.querySelector('.mic-label').textContent = '녹음 시작';
  recIndicator.classList.add('hidden');
}

function startSegment(stream) {
  if (!stream) return;   // reuse existing stream isn't supported here simply
  audioChunks = [];
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = e => {
    if (e.data.size > 0) audioChunks.push(e.data);
  };
  mediaRecorder.onstop = sendAudioChunk;

  const segmentMs = chkContinuous.checked ? 4000 : 30000;
  mediaRecorder.start();

  if (chkContinuous.checked) {
    continuousTimer = setTimeout(() => {
      if (mediaRecorder.state !== 'inactive') mediaRecorder.stop();
    }, segmentMs);
  }
}

async function sendAudioChunk() {
  if (audioChunks.length === 0) return;
  const blob = new Blob(audioChunks, { type: 'audio/webm' });
  const arrayBuffer = await blob.arrayBuffer();
  const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));

  setLoading(true, '음성 인식 중…');
  socket.emit('audio_chunk', {
    audio: base64,
    speak: chkSpeakVoice.checked,
  });
}

/* ── Text translation ── */
btnTranslate.addEventListener('click', async () => {
  const text = txtKorean.value.trim();
  if (!text) return;

  setLoading(true, '번역 중…');
  textResult.classList.add('hidden');

  try {
    const r = await fetch('/api/translate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, speak: chkSpeakText.checked }),
    });
    const data = await r.json();
    if (data.error) { showError(data.error); return; }

    textKorean.textContent  = data.korean;
    textEnglish.textContent = data.english;
    textTagalog.textContent = data.tagalog;
    textResult.classList.remove('hidden');
    addHistory(data);
  } catch (e) {
    showError('번역 오류: ' + e.message);
  } finally {
    setLoading(false);
  }
});

/* Ctrl+Enter submits */
txtKorean.addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) btnTranslate.click();
});

/* ── Helpers ── */
function showVoiceResult({ korean, english, tagalog }) {
  voiceKorean.textContent  = korean  || '';
  voiceEnglish.textContent = english || '';
  voiceTagalog.textContent = tagalog || '';
  voiceResult.classList.remove('hidden');
}

function setLoading(on, msg = '번역 중…') {
  loadingOverlay.classList.toggle('hidden', !on);
  loadingText.textContent = msg;
}

let toastTimer;
function showError(msg) {
  errorToast.textContent = msg;
  errorToast.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => errorToast.classList.add('hidden'), 4000);
}

/* ── History ── */
function addHistory(entry) {
  history.unshift({ ...entry, time: new Date().toLocaleTimeString() });
  if (history.length > 100) history.pop();
  localStorage.setItem('interp-history', JSON.stringify(history));
}

function renderHistory() {
  if (history.length === 0) {
    historyList.innerHTML = '<p class="empty-msg">번역 기록이 없습니다.</p>';
    return;
  }
  historyList.innerHTML = history.map(h => `
    <div class="history-item">
      <span class="h-ko">${escHtml(h.korean)}</span>
      <span class="h-tl">${escHtml(h.tagalog)}</span>
      <span class="h-time">${escHtml(h.time)}</span>
    </div>
  `).join('');
}

btnClearHist.addEventListener('click', () => {
  history = [];
  localStorage.removeItem('interp-history');
  renderHistory();
});

function escHtml(str) {
  return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* ── Init ── */
initSocket();
