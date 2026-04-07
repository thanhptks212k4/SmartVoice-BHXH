"""
Voice AI Client — Whisper STT
Giống client.py nhưng dùng Whisper thay Google STT.

Chạy:
  python3 client_whisper.py
  python3 client_whisper.py --model small   # chọn model (tiny/base/small/medium)
"""
import time
import queue
import threading
import signal
import json
import argparse

import numpy as np
import requests
import websocket
import pyaudio
import socketio as sio_client
import webbrowser
import whisper

from STT import (
    init_rnnoise, init_silero, SileroVAD,
    MicStream, capture_audio, TARGET_SR
)

# ── Config ──
BASE_URL  = "http://172.28.251.191:3000"
WS_URL    = "ws://172.28.251.191:3000"
USER_DATA = {"username": "BHXH", "password": "123456"}
VOICE     = "nuhanoi"

TTS_CHANNELS = 1
TTS_RATE     = 24000
AUDIO_QUEUE_MAX = 5
TEXT_QUEUE_MAX  = 10

GREEN  = "\033[92m"; YELLOW = "\033[93m"
CYAN   = "\033[96m"; RED    = "\033[91m"; RESET = "\033[0m"

_pyaudio = pyaudio.PyAudio()

# ── Whisper model (load 1 lần) ──
_whisper_model = None

def load_whisper(model_name="base"):
    global _whisper_model
    print(f"[Whisper] Loading model [{model_name}]...")
    _whisper_model = whisper.load_model(model_name)
    print(f"[Whisper] San sang!")


def transcribe_audio(audio_16k: np.ndarray) -> str:
    """Thay thế Google STT bằng Whisper."""
    result = _whisper_model.transcribe(
        audio_16k,
        language="vi",
        fp16=False,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        logprob_threshold=-1.0,
    )
    text = result["text"].strip()
    # Bỏ qua hallucination
    if "<|" in text or len(text) < 2:
        return ""
    return text


# ── UIConnector ──
class UIConnector:
    def __init__(self):
        self._sio = sio_client.Client(logger=False, engineio_logger=False)
        self._connected = False

    def connect(self, url="http://localhost:5500"):
        def _try():
            try:
                self._sio.connect(url)
                self._connected = True
                print(f"{GREEN}[UI] Ket noi giao dien thanh cong{RESET}")
                webbrowser.open("http://localhost:5173")
            except Exception as e:
                print(f"{YELLOW}[UI] Khong ket noi duoc UI: {e}{RESET}")
        threading.Thread(target=_try, daemon=True).start()

    def notify(self, state: str):
        if self._connected:
            try:
                self._sio.emit("set_state", {"s": state})
            except Exception:
                pass

_ui = UIConnector()


# ── VoiceTimer ──
class VoiceTimer:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_voice = 0.0

    def touch(self):
        with self._lock:
            self._last_voice = time.monotonic()

    def elapsed(self):
        with self._lock:
            return 0.0 if self._last_voice == 0.0 else time.monotonic() - self._last_voice


# ── EndpointDetector (giữ nguyên) ──
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

    def should_finalize_silence(self, merged_text, voice_elapsed, stt_busy, audio_q_empty, mic_recording):
        if stt_busy or not audio_q_empty or mic_recording: return False
        threshold = self.get_silence_threshold(merged_text)
        n = len(merged_text.split())
        effective = min(voice_elapsed, self._text_cooldown_elapsed()) if n > self.TEXT_AGE_WORD_THRESHOLD else voice_elapsed
        return effective > threshold

    def reset(self):
        self._last_raw = ""; self._last_merged = ""
        self._repeat_count = 0; self._last_text_time = 0.0


# ── Workers ──
def mic_worker(audio_queue, mic, rnn_lib, rnn_state, silero_vad,
               voice_timer, stop_event, mic_recording, is_playing_event):
    while not stop_event.is_set():
        if is_playing_event.is_set():
            time.sleep(0.1); continue
        try:
            audio = capture_audio(mic, rnn_lib, rnn_state, silero_vad,
                                  audio_queue, voice_timer, mic_recording)
            if isinstance(audio, str) and audio == "__NO_VOICE__":
                time.sleep(0.3); continue
            if audio is None: continue
            voice_timer.touch()
            _ui.notify("listening")
            try:
                audio_queue.put_nowait(audio)
            except queue.Full:
                try: audio_queue.get_nowait()
                except queue.Empty: pass
                audio_queue.put_nowait(audio)
        except Exception as e:
            if not stop_event.is_set():
                print(f"\n[Mic] Loi: {e}")
            break


def stt_worker(audio_queue, text_queue, stop_event, stt_busy):
    while not stop_event.is_set():
        try:
            audio = audio_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        stt_busy.set()
        try:
            t0 = time.time()
            text = transcribe_audio(audio)
            dt = time.time() - t0
            if text:
                text_queue.put((text, dt))
                print(f"\n{CYAN}[Whisper] {text} ({dt:.2f}s){RESET}")
        except Exception as e:
            if not stop_event.is_set():
                print(f"\n[STT] Loi: {e}")
        finally:
            _ui.notify("idle")
            stt_busy.clear()


# ── Auth ──
def login_and_get_token():
    try:
        print(f"[Auth] Dang nhap: {USER_DATA['username']}...")
        res = requests.post(f"{BASE_URL}/auth/login", json=USER_DATA, timeout=5)
        if res.status_code == 200:
            token = res.json().get("token")
            print(f"{GREEN}[Auth] Lay token thanh cong!{RESET}\n")
            return token
        print(f"{RED}[Auth] Dang nhap that bai: {res.text}{RESET}")
    except requests.exceptions.ConnectionError:
        print(f"{RED}[Auth] Khong the ket noi den server {BASE_URL}{RESET}")
    except Exception as e:
        print(f"{RED}[Auth] Loi: {e}{RESET}")
    return None


# ── TTS playback (giữ nguyên từ client.py) ──
def play_audio_stream(url, is_playing_event, mic=None):
    stream = None
    try:
        is_playing_event.set()
        _ui.notify("speaking")
        if mic: mic.is_muted.set(); mic.clear()
        print(f"{CYAN}[TTS] Dang phat audio stream...{RESET}")

        header_parsed = False
        header_buf = bytearray()
        channels, rate, fmt = TTS_CHANNELS, TTS_RATE, pyaudio.paInt16

        with requests.get(url, stream=True, timeout=15) as r:
            if r.status_code != 200:
                print(f"{RED}[TTS] Loi tai audio: {r.status_code}{RESET}"); return
            for chunk in r.iter_content(chunk_size=4096):
                if not chunk: continue
                if not header_parsed:
                    header_buf.extend(chunk)
                    if len(header_buf) < 44: continue
                    pcm_start = 0
                    if header_buf[:4] == b'RIFF':
                        try:
                            import io, wave, struct
                            wav_buf = io.BytesIO(bytes(header_buf))
                            with wave.open(wav_buf, 'rb') as wf:
                                channels = wf.getnchannels(); rate = wf.getframerate()
                                sampwidth = wf.getsampwidth()
                                fmt = pyaudio.paInt16 if sampwidth == 2 else pyaudio.paFloat32
                                pcm_start = wav_buf.tell()
                        except Exception: pcm_start = 44
                    stream = _pyaudio.open(format=fmt, channels=channels, rate=rate, output=True)
                    header_parsed = True
                    pcm_chunk = bytes(header_buf[pcm_start:])
                    if pcm_chunk: stream.write(pcm_chunk)
                else:
                    stream.write(chunk)

        if stream: stream.stop_stream(); stream.close()
        print(f"{GREEN}[TTS] Phat xong!{RESET}")
        time.sleep(0.3)
    except Exception as e:
        print(f"{RED}[TTS] Loi: {e}{RESET}")
        if stream:
            try: stream.stop_stream(); stream.close()
            except: pass
    finally:
        if mic: mic.clear(); mic.is_muted.clear()
        _ui.notify("idle")
        is_playing_event.clear()


# ── WebSocket ──
class WebSocketHandler:
    def __init__(self, token, is_playing_event, mic=None):
        self.token = token
        self.ws_url = f"{WS_URL}?token={token}"
        self.ws = None; self.connected = False
        self.is_playing_event = is_playing_event; self.mic = mic

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "AI_VOICE_REPLY":
                if data.get("text"): print(f"\n{GREEN}[Bot]: {data['text']}{RESET}")
                if data.get("audioUrl"):
                    print(f"{CYAN}[Audio URL]: {data['audioUrl']}{RESET}")
                    threading.Thread(target=play_audio_stream,
                        args=(data["audioUrl"], self.is_playing_event, self.mic),
                        daemon=True).start()
            elif msg_type != "STATUS":
                print(f"{YELLOW}[WS] Event: {msg_type}{RESET}")
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
            print(f"{GREEN}[WS] Da gui len server{RESET}")


# ── Finalize ──
def finalize_sentence(buffer, detector, reason, start_time, ws_handler=None):
    full = " ".join(buffer)
    clean = detector.filter_fillers(full)
    if not clean: buffer.clear(); detector.reset(); return
    end_time = time.time()
    duration = end_time - start_time if start_time else 0
    timestamp = int(start_time) if start_time else int(time.time())
    print(f"\n{GREEN}>> Cau hoan chinh [{reason}]{RESET}")
    print(f"   {clean}\n   duration: {duration:.2f}s")
    print(f"\n{YELLOW}[DATA]{RESET}")
    print(json.dumps({"text": clean, "language": "VI",
        "timestamp": timestamp, "duration": round(duration, 2)}, ensure_ascii=False, indent=2))
    if ws_handler: ws_handler.send_text(clean, timestamp, round(duration, 2))
    print("=" * 50)
    buffer.clear(); detector.reset()


# ── Main ──
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="base",
        choices=["tiny", "base", "small", "medium"],
        help="Whisper model size (default: base)")
    args = parser.parse_args()

    print("=" * 50)
    print("  Voice AI Client — Whisper STT Pipeline")
    print("=" * 50)

    load_whisper(args.model)

    token = login_and_get_token()
    if not token:
        print(f"\n{RED}[Error] Khong the lay token. Thoat.{RESET}\n"); return

    _ui.connect()
    is_playing_event = threading.Event()

    rnn_lib, rnn_state = init_rnnoise()
    silero_model = init_silero()
    silero_vad = SileroVAD(silero_model)

    mic = MicStream()
    mic.start()
    print("[Mic] Microphone stream da mo.")

    ws_handler = WebSocketHandler(token, is_playing_event, mic=mic)
    ws = ws_handler.connect()
    ws_thread = threading.Thread(target=ws.run_forever, daemon=True, name="ws_worker")
    ws_thread.start()
    time.sleep(1)

    print(f"\n[STT] Whisper [{args.model}]")
    print("[STT] San sang!\n")

    voice_timer  = VoiceTimer()
    audio_queue  = queue.Queue(maxsize=AUDIO_QUEUE_MAX)
    text_queue   = queue.Queue(maxsize=TEXT_QUEUE_MAX)
    stt_busy     = threading.Event()
    mic_recording = threading.Event()
    stop_event   = threading.Event()

    def signal_handler(sig, frame):
        print("\n\n[System] Dang tat..."); stop_event.set()
    signal.signal(signal.SIGINT, signal_handler)

    t_mic = threading.Thread(target=mic_worker,
        args=(audio_queue, mic, rnn_lib, rnn_state, silero_vad,
              voice_timer, stop_event, mic_recording, is_playing_event),
        daemon=True, name="mic_worker")
    t_stt = threading.Thread(target=stt_worker,
        args=(audio_queue, text_queue, stop_event, stt_busy),
        daemon=True, name="stt_worker")
    t_mic.start(); t_stt.start()

    print("[System] Pipeline dang chay. Ctrl+C de thoat.\n")
    print("-" * 50)

    try:
        detector = EndpointDetector()
        temp_text_buffer = []
        sentence_start_time = None
        was_playing = False

        while not stop_event.is_set():
            if is_playing_event.is_set():
                was_playing = True; time.sleep(0.1); continue

            if was_playing:
                was_playing = False
                while not audio_queue.empty():
                    try: audio_queue.get_nowait()
                    except queue.Empty: break
                while not text_queue.empty():
                    try: text_queue.get_nowait()
                    except queue.Empty: break
                temp_text_buffer.clear(); detector.reset()
                sentence_start_time = None
                print(f"\n{CYAN}[System] Audio xong, tiep tuc nghe...{RESET}")

            try:
                raw_text, latency = text_queue.get(timeout=0.1)
                text = detector.filter_fillers(raw_text)
                if not text: print(f"\n[SKIP] Filler: '{raw_text}'"); continue
                if detector.is_duplicate(text): print(f"\n[SKIP] Duplicate: '{text}'"); continue
                detector.on_text_received()
                print(f"\n{CYAN}Ban noi: {text}{RESET}\n   {latency:.2f}s")
                if not temp_text_buffer: sentence_start_time = time.time()
                if not detector.try_extend_buffer(temp_text_buffer, text):
                    temp_text_buffer.append(text)
                else:
                    print(f"   [MERGE] Mo rong buffer")
                if detector.check_punctuation(text):
                    finalize_sentence(temp_text_buffer, detector, "PUNCT", sentence_start_time, ws_handler)
                    sentence_start_time = None; continue
                if detector.check_keyword_endpoint(text):
                    finalize_sentence(temp_text_buffer, detector, "KEYWORD", sentence_start_time, ws_handler)
                    sentence_start_time = None; continue
                merged = " ".join(temp_text_buffer)
                if detector.check_stability(merged):
                    finalize_sentence(temp_text_buffer, detector, "STABLE", sentence_start_time, ws_handler)
                    sentence_start_time = None; continue
            except queue.Empty:
                pass

            if temp_text_buffer:
                merged = " ".join(temp_text_buffer)
                if detector.should_finalize_silence(merged, voice_timer.elapsed(),
                        stt_busy.is_set(), audio_queue.empty(), mic_recording.is_set()):
                    finalize_sentence(temp_text_buffer, detector, "SILENCE", sentence_start_time, ws_handler)
                    sentence_start_time = None

    except KeyboardInterrupt:
        stop_event.set()

    if temp_text_buffer:
        finalize_sentence(temp_text_buffer, detector, "EXIT", sentence_start_time, ws_handler)

    t_mic.join(timeout=3.0); t_stt.join(timeout=3.0)
    if ws_handler and ws_handler.ws: ws_handler.ws.close()
    ws_thread.join(timeout=3.0)
    mic.stop()
    if rnn_lib and rnn_state: rnn_lib.rnnoise_destroy(rnn_state)
    print("\n[System] Tam biet!")


if __name__ == "__main__":
    main()
