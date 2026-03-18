'use strict';

/* ── Helpers ── */
const $ = id => document.getElementById(id);
const esc = s => (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

/* ── DOM ── */
const statusText  = $('status-text');
const connDot     = $('conn-dot');

const btnMic      = $('btn-mic');
const micLabel    = $('mic-label');
const wave        = $('wave');
const chkSpeak    = $('chk-speak');
const chkCont     = $('chk-continuous');

const txtKo       = $('txt-ko');
const txtEn       = $('txt-en');
const txtTl       = $('txt-tl');

const inpText     = $('inp-text');
const btnTrans    = $('btn-translate');
const chkSpeakTxt = $('chk-speak-text');
const textCard    = $('text-result-card');
const tKo         = $('t-ko');
const tEn         = $('t-en');
const tTl         = $('t-tl');

const historyList = $('history-list');
const btnClear    = $('btn-clear');

const overlay     = $('overlay');
const overlayMsg  = $('overlay-msg');
const toast       = $('toast');

/* ── State ── */
let socket       = null;
let isRecording  = false;
let mediaRec     = null;
let audioChunks  = [];
let contTimer    = null;
let micStream    = null;
let history      = JSON.parse(localStorage.getItem('interp-h') || '[]');

/* ── Bottom nav ── */
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'history') renderHistory();
  });
});

/* ── Socket.IO ── */
function initSocket() {
  socket = io({ transports: ['websocket'], reconnectionDelay: 1000 });

  socket.on('connect', () => {
    connDot.className = 'conn-dot on';
    checkStatus();
  });
  socket.on('disconnect', () => {
    connDot.className = 'conn-dot off';
    statusText.textContent = '서버 연결 끊김';
  });
  socket.on('status', d => { statusText.textContent = d.message; });

  socket.on('partial_result', d => {
    setVoiceResult(d);
    hideOverlay();
  });
  socket.on('translation_result', d => {
    setVoiceResult(d);
    addHistory(d);
    hideOverlay();
    if (chkCont.checked && isRecording) nextSegment();
  });
  socket.on('error', d => {
    showToast(d.message);
    hideOverlay();
  });
}

async function checkStatus() {
  try {
    const r = await fetch('/api/status');
    const s = await r.json();
    if (s.ko_en_ready && s.en_tl_ready) {
      statusText.textContent = '오프라인 준비 완료 ✓';
    } else {
      statusText.textContent = '⚠ 모델 미설치 – download_models.py 실행 필요';
    }
  } catch { /* ignore */ }
}

/* ── Mic recording ── */
btnMic.addEventListener('click', () => {
  if (isRecording) stopRecording();
  else startRecording();
});

async function startRecording() {
  if (!navigator.mediaDevices) {
    showToast('마이크 접근 불가: HTTPS 또는 localhost 필요');
    return;
  }
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    showToast('마이크 오류: ' + e.message);
    return;
  }
  isRecording = true;
  btnMic.classList.add('recording');
  micLabel.textContent = '중지';
  wave.classList.remove('hidden');
  removePlaceholders();
  nextSegment();
}

function stopRecording() {
  isRecording = false;
  clearTimeout(contTimer);
  if (mediaRec && mediaRec.state !== 'inactive') mediaRec.stop();
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
  btnMic.classList.remove('recording');
  micLabel.textContent = '녹음 시작';
  wave.classList.add('hidden');
}

function nextSegment() {
  if (!micStream) return;
  audioChunks = [];
  mediaRec = new MediaRecorder(micStream);
  mediaRec.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
  mediaRec.onstop = sendChunk;
  mediaRec.start();

  const ms = chkCont.checked ? 4000 : 10000;
  contTimer = setTimeout(() => {
    if (mediaRec && mediaRec.state === 'recording') mediaRec.stop();
  }, ms);
}

async function sendChunk() {
  if (!audioChunks.length) return;
  const blob = new Blob(audioChunks, { type: 'audio/webm' });
  const buf  = await blob.arrayBuffer();
  const b64  = btoa(String.fromCharCode(...new Uint8Array(buf)));
  showOverlay('음성 인식 중…');
  socket.emit('audio_chunk', { audio: b64, speak: chkSpeak.checked });
}

/* ── Voice result display ── */
function setVoiceResult({ korean, english, tagalog }) {
  if (korean)  { txtKo.textContent = korean;  txtKo.classList.remove('placeholder'); }
  if (english) { txtEn.textContent = english; txtEn.classList.remove('placeholder'); }
  if (tagalog) { txtTl.textContent = tagalog; txtTl.classList.remove('placeholder'); }
}

function removePlaceholders() {
  [txtKo, txtEn, txtTl].forEach(el => {
    el.classList.remove('placeholder');
    el.textContent = '';
  });
}

/* ── Text translation ── */
btnTrans.addEventListener('click', translateText);
inpText.addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) translateText();
});

async function translateText() {
  const text = inpText.value.trim();
  if (!text) return;
  showOverlay('번역 중…');
  textCard.style.display = 'none';
  btnTrans.disabled = true;

  try {
    const r = await fetch('/api/translate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, speak: chkSpeakTxt.checked }),
    });
    const data = await r.json();
    if (data.error) { showToast(data.error); return; }
    tKo.textContent = data.korean;
    tEn.textContent = data.english;
    tTl.textContent = data.tagalog;
    textCard.style.display = '';
    addHistory(data);
  } catch (e) {
    showToast('오류: ' + e.message);
  } finally {
    hideOverlay();
    btnTrans.disabled = false;
  }
}

/* ── History ── */
function addHistory(entry) {
  history.unshift({ ...entry, ts: new Date().toLocaleTimeString() });
  if (history.length > 100) history.pop();
  localStorage.setItem('interp-h', JSON.stringify(history));
}

function renderHistory() {
  if (!history.length) {
    historyList.innerHTML = '<p class="empty-hint">기록이 없습니다.</p>';
    return;
  }
  historyList.innerHTML = history.map(h => `
    <div class="history-item">
      <span class="h-ko">${esc(h.korean)}</span>
      <span class="h-tl">${esc(h.tagalog)}</span>
      <span class="h-ts">${esc(h.ts)}</span>
    </div>
  `).join('');
}

btnClear.addEventListener('click', () => {
  history = [];
  localStorage.removeItem('interp-h');
  renderHistory();
});

/* ── UI utilities ── */
function showOverlay(msg = '번역 중…') {
  overlayMsg.textContent = msg;
  overlay.classList.remove('hidden');
}
function hideOverlay() { overlay.classList.add('hidden'); }

let toastTimer;
function showToast(msg, type = 'error') {
  toast.textContent = msg;
  toast.className = `toast ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add('hidden'), 4000);
}

/* ── Init ── */
initSocket();
