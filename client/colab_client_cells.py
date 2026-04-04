# =============================================================
# File này chứa nội dung từng cell để paste vào Colab notebook
# =============================================================

# ---- CELL 1: Install ----
"""
!pip install -q openai-whisper websocket-client requests numpy scipy
"""

# ---- CELL 2: Config ----
"""
BASE_URL      = "http://YOUR_SERVER_IP:3000"
WS_URL        = "ws://YOUR_SERVER_IP:3000"
USER_DATA     = {"username": "BHXH", "password": "123456"}
VOICE         = "nuhanoi"
WHISPER_MODEL = "small"   # tiny / base / small / medium
"""

# ---- CELL 3: Load Whisper ----
"""
import whisper
print(f"Loading Whisper model: {WHISPER_MODEL}...")
whisper_model = whisper.load_model(WHISPER_MODEL)
print("Whisper ready!")
"""

# ---- CELL 4: Core logic (EndpointDetector, WebSocketHandler, ...) ----
"""
import time, queue, threading, json, io, wave, struct
import numpy as np
import requests
import websocket

GREEN  = "\033[92m"; YELLOW = "\033[93m"
CYAN   = "\033[96m"; RED    = "\033[91m"; RESET = "\033[0m"

# --- STT với Whisper ---
def transcribe_audio(audio_np_16k):
    # audio_np_16k: numpy float32 array, sample rate 16000
    result = whisper_model.transcribe(audio_np_16k, language="vi", fp16=False)
    return result["text"].strip()

# --- VoiceTimer ---
class VoiceTimer:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_voice = 0.0
    def touch(self):
        with self._lock: self._last_voice = time.monotonic()
    def elapsed(self):
        with self._lock:
            return 0.0 if self._last_voice == 0.0 else time.monotonic() - self._last_voice

# --- EndpointDetector (giữ nguyên logic gốc) ---
class EndpointDetector:
    FILLERS    = frozenset({"ờ","à","ừ","ừm","ạ","ơ","ơi","ê","hả","uhm","um","ah","uh","eh"})
    CONNECTORS = frozenset({"và","hoặc","nhưng","rồi","mà","hay","vì","nên","thì","còn","với","để","nếu","khi"})
    ENDPOINTS  = frozenset({"xong","hết","ok","được rồi","thế thôi","vậy thôi","cảm ơn","tạm biệt"})
    SILENCE_TABLE = ((3,1.2),(6,1.6),(10,2.0),(15,2.5),(20,3.0),(30,3.5))
    SILENCE_MAX = 4.5; CONNECTOR_BONUS = 1.0
    TEXT_AGE_WORD_THRESHOLD = 6; STABILITY_COUNT = 3

    def __init__(self):
        self._last_raw = ""; self._last_merged = ""
        self._repeat_count = 0; self._last_text_time = 0.0

    def on_text_received(self): self._last_text_time = time.monotonic()
    def _text_cooldown_elapsed(self):
        return float('inf') if self._last_text_time == 0.0 else time.monotonic() - self._last_text_time

    def filter_fillers(self, text):
        return " ".join(w for w in text.split() if w.lower() not in self.FILLERS)

    def is_duplicate(self, raw_text):
        n = raw_text.strip().lower()
        if n == self._last_raw: return True
        self._last_raw = n; return False

    def try_extend_buffer(self, buffer, new_text):
        if not buffer: return False
        last = buffer[-1].lower(); new_lower = new_text.lower()
        if new_lower.startswith(last) and len(new_text) > len(buffer[-1]):
            buffer[-1] = new_text; return True
        if last.startswith(new_lower): return True
        return False

    def check_punctuation(self, text): return bool(text) and text[-1] in ".?!"
    def check_keyword_endpoint(self, text):
        lower = text.lower().strip()
        return any(lower.endswith(kw) for kw in self.ENDPOINTS)

    def check_stability(self, merged_text):
        n = merged_text.strip().lower()
        if n == self._last_merged: self._repeat_count += 1
        else: self._last_merged = n; self._repeat_count = 1
        return self._repeat_count >= self.STABILITY_COUNT

    def get_silence_threshold(self, merged_text):
        words = merged_text.split(); n = len(words)
        base = self.SILENCE_MAX
        for max_w, t in self.SILENCE_TABLE:
            if n <= max_w: base = t; break
        if n > 0 and words[-1].lower() in self.CONNECTORS: base += self.CONNECTOR_BONUS
        return base

    def should_finalize_silence(self, merged_text, voice_elapsed, stt_busy, audio_q_empty):
        if stt_busy or not audio_q_empty: return False
        threshold = self.get_silence_threshold(merged_text)
        n = len(merged_text.split())
        effective = min(voice_elapsed, self._text_cooldown_elapsed()) if n > self.TEXT_AGE_WORD_THRESHOLD else voice_elapsed
        return effective > threshold

    def reset(self):
        self._last_raw = ""; self._last_merged = ""
        self._repeat_count = 0; self._last_text_time = 0.0

# --- WebSocketHandler ---
class WebSocketHandler:
    def __init__(self, token, is_playing_event):
        self.token = token
        self.ws_url = f"{WS_URL}?token={token}"
        self.ws = None; self.connected = False
        self.is_playing_event = is_playing_event

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "AI_VOICE_REPLY":
                bot_text = data.get("text")
                audio_url = data.get("audioUrl")
                if bot_text: print(f"\n{GREEN}[Bot]: {bot_text}{RESET}")
                if audio_url:
                    print(f"{CYAN}[Audio URL]: {audio_url}{RESET}")
                    threading.Thread(target=play_audio_in_browser, args=(audio_url,), daemon=True).start()
            elif msg_type == "AI_VOICE_DONE":
                print(f"{CYAN}[Bot] Hoan thanh{RESET}")
        except Exception as e:
            print(f"{RED}[WS] Loi: {e}{RESET}")

    def on_error(self, ws, error): print(f"{RED}[WS] Loi: {error}{RESET}")
    def on_close(self, ws, c, m): print(f"{YELLOW}[WS] Dong{RESET}"); self.connected = False
    def on_open(self, ws): print(f"{GREEN}[WS] Ket noi thanh cong!{RESET}"); self.connected = True

    def connect(self):
        self.ws = websocket.WebSocketApp(self.ws_url,
            on_open=self.on_open, on_message=self.on_message,
            on_error=self.on_error, on_close=self.on_close)
        return self.ws

    def send_text(self, text, timestamp, duration):
        if self.ws and self.connected:
            self.ws.send(json.dumps({"text": text, "language": "VI",
                "voice": VOICE, "timestamp": timestamp, "duration": duration}))
            print(f"{GREEN}[WS] Da gui{RESET}")

# --- Auth ---
def login_and_get_token():
    res = requests.post(f"{BASE_URL}/auth/login", json=USER_DATA, timeout=5)
    if res.status_code == 200:
        token = res.json().get("token")
        print(f"{GREEN}[Auth] Token OK{RESET}")
        return token
    print(f"{RED}[Auth] Loi: {res.text}{RESET}")
    return None

# --- Finalize ---
def finalize_sentence(buffer, detector, reason, start_time, ws_handler):
    full = " ".join(buffer)
    clean = detector.filter_fillers(full)
    if not clean: buffer.clear(); detector.reset(); return
    end_time = time.time()
    duration = end_time - start_time if start_time else 0
    timestamp = int(start_time) if start_time else int(time.time())
    print(f"\n{GREEN}>> [{reason}] {clean}{RESET} ({duration:.2f}s)")
    if ws_handler: ws_handler.send_text(clean, timestamp, round(duration, 2))
    buffer.clear(); detector.reset()

print("Core logic loaded!")
"""

# ---- CELL 5: Mic capture từ browser bằng JS + phát audio ----
"""
from IPython.display import display, Javascript, Audio
import base64, tempfile, os
from google.colab import output

# Hàng đợi nhận audio từ JS
_audio_chunks = queue.Queue()

def _receive_audio_chunk(b64_data):
    raw = base64.b64decode(b64_data)
    _audio_chunks.put(raw)

output.register_callback("notebook.receive_audio", _receive_audio_chunk)

def play_audio_in_browser(url):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200: return
        b64 = base64.b64encode(r.content).decode()
        display(Javascript(f'''
            const audio = new Audio("data:audio/wav;base64,{b64}");
            audio.play();
        '''))
    except Exception as e:
        print(f"[TTS] Loi: {{e}}")

# JS capture mic liên tục, gửi chunk 2s về Python
MIC_JS = """
(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    const ctx    = new AudioContext({sampleRate: 16000});
    const src    = ctx.createMediaStreamSource(stream);
    const proc   = ctx.createScriptProcessor(4096, 1, 1);

    let buffer = [];
    let lastSend = Date.now();

    proc.onaudioprocess = (e) => {
        const f32 = e.inputBuffer.getChannelData(0);
        buffer.push(...f32);

        if (Date.now() - lastSend >= 2000) {
            lastSend = Date.now();
            const arr   = new Float32Array(buffer);
            const i16   = new Int16Array(arr.length);
            for (let i = 0; i < arr.length; i++)
                i16[i] = Math.max(-32768, Math.min(32767, arr[i] * 32768));

            // Build WAV header
            const wavLen = 44 + i16.byteLength;
            const wav    = new ArrayBuffer(wavLen);
            const view   = new DataView(wav);
            const sr     = 16000;
            const writeStr = (o, s) => { for(let i=0;i<s.length;i++) view.setUint8(o+i, s.charCodeAt(i)); };
            writeStr(0,'RIFF'); view.setUint32(4, wavLen-8, true);
            writeStr(8,'WAVE'); writeStr(12,'fmt ');
            view.setUint32(16,16,true); view.setUint16(20,1,true);
            view.setUint16(22,1,true); view.setUint32(24,sr,true);
            view.setUint32(28,sr*2,true); view.setUint16(32,2,true);
            view.setUint16(34,16,true); writeStr(36,'data');
            view.setUint32(40,i16.byteLength,true);
            new Int16Array(wav, 44).set(i16);

            const b64 = btoa(String.fromCharCode(...new Uint8Array(wav)));
            google.colab.kernel.invokeFunction('notebook.receive_audio', [b64], {});
            buffer = [];
        }
    };
    src.connect(proc);
    proc.connect(ctx.destination);
    console.log("Mic started!");
})();
"""

def start_mic():
    display(Javascript(MIC_JS))
    print(f"{GREEN}[Mic] Browser mic started — cho phep mic trong tab Colab!{RESET}")

print("Browser mic + audio playback ready!")
"""

# ---- CELL 6: STT worker dùng Whisper ----
"""
import scipy.io.wavfile as wav_io

def stt_worker_whisper(audio_queue, text_queue, stop_event, stt_busy):
    while not stop_event.is_set():
        try:
            raw_wav = audio_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        stt_busy.set()
        try:
            # Đọc WAV bytes -> numpy float32
            sr, data = wav_io.read(io.BytesIO(raw_wav))
            if data.dtype != np.float32:
                data = data.astype(np.float32) / 32768.0
            t0 = time.time()
            text = transcribe_audio(data)
            dt = time.time() - t0
            if text:
                text_queue.put((text, dt))
                print(f"{CYAN}[STT] {text} ({dt:.2f}s){RESET}")
        except Exception as e:
            print(f"{RED}[STT] Loi: {e}{RESET}")
        finally:
            stt_busy.clear()

print("STT worker ready!")
"""

# ---- CELL 7: Main pipeline ----
"""
import signal

stop_event   = threading.Event()
is_playing   = threading.Event()
audio_queue  = queue.Queue(maxsize=10)
text_queue   = queue.Queue(maxsize=10)
stt_busy     = threading.Event()
voice_timer  = VoiceTimer()

# Mic audio từ JS -> audio_queue
def mic_bridge(stop_event):
    while not stop_event.is_set():
        try:
            raw = _audio_chunks.get(timeout=1.0)
            # VAD đơn giản: bỏ chunk nếu đang phát TTS
            if is_playing.is_set():
                continue
            # Kiểm tra có tiếng nói không (RMS threshold)
            sr, data = wav_io.read(io.BytesIO(raw))
            rms = np.sqrt(np.mean(data.astype(np.float32)**2))
            if rms < 200:   # im lặng, bỏ qua
                continue
            voice_timer.touch()
            try:
                audio_queue.put_nowait(raw)
            except queue.Full:
                try: audio_queue.get_nowait()
                except: pass
                audio_queue.put_nowait(raw)
        except queue.Empty:
            continue

token = login_and_get_token()
if not token:
    print(f"{RED}Khong lay duoc token!{RESET}")
else:
    ws_handler = WebSocketHandler(token, is_playing)
    ws = ws_handler.connect()

    threading.Thread(target=ws.run_forever, daemon=True, name="ws").start()
    threading.Thread(target=mic_bridge, args=(stop_event,), daemon=True, name="mic_bridge").start()
    threading.Thread(target=stt_worker_whisper,
        args=(audio_queue, text_queue, stop_event, stt_busy), daemon=True, name="stt").start()

    start_mic()   # Bật mic trên browser
    time.sleep(1)

    print(f"\n{GREEN}Pipeline chay! Noi vao mic tren tab Colab.{RESET}")
    print("Chay cell tiep theo de bat dau vong lap xu ly text.\n")
"""

# ---- CELL 8: Text processing loop (chạy blocking, Ctrl+C để dừng) ----
"""
detector = EndpointDetector()
temp_buffer = []
sentence_start = None

print(f"{GREEN}Bat dau lang nghe... (interrupt kernel de dung){RESET}")
try:
    while True:
        try:
            raw_text, latency = text_queue.get(timeout=0.1)
            text = detector.filter_fillers(raw_text)
            if not text or detector.is_duplicate(text):
                continue
            detector.on_text_received()
            print(f"{CYAN}Ban noi: {text} ({latency:.2f}s){RESET}")

            if not temp_buffer:
                sentence_start = time.time()
            if not detector.try_extend_buffer(temp_buffer, text):
                temp_buffer.append(text)

            if detector.check_punctuation(text) or detector.check_keyword_endpoint(text):
                finalize_sentence(temp_buffer, detector, "PUNCT/KW", sentence_start, ws_handler)
                sentence_start = None; continue

            merged = " ".join(temp_buffer)
            if detector.check_stability(merged):
                finalize_sentence(temp_buffer, detector, "STABLE", sentence_start, ws_handler)
                sentence_start = None; continue

        except queue.Empty:
            pass

        if temp_buffer:
            merged = " ".join(temp_buffer)
            if detector.should_finalize_silence(merged, voice_timer.elapsed(),
                                                 stt_busy.is_set(), audio_queue.empty()):
                finalize_sentence(temp_buffer, detector, "SILENCE", sentence_start, ws_handler)
                sentence_start = None

except KeyboardInterrupt:
    stop_event.set()
    print(f"\n{YELLOW}Dung pipeline.{RESET}")
"""
