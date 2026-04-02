import time
import queue
import threading
import signal
import io
import wave
import json

import numpy as np
import speech_recognition as sr
import requests
import websocket
import pyaudio
import socketio as sio_client
import webbrowser
voice="nuhanoi"

from STT import (
    init_rnnoise, init_silero, SileroVAD,
    MicStream, capture_audio, TARGET_SR
)

AUDIO_QUEUE_MAX = 5
TEXT_QUEUE_MAX = 10

BASE_URL = "http://172.28.251.191:3000"
WS_URL = "ws://172.28.251.191:3000"
USER_DATA = {
    "username": "BHXH",
    "password": "123456"
}

TTS_CHANNELS = 1
TTS_RATE = 24000

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"

_recognizer = sr.Recognizer()
_pyaudio = pyaudio.PyAudio()


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


def transcribe_audio(audio_16k):
    pcm16 = (audio_16k * 32768).astype(np.int16).tobytes()

    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(TARGET_SR)
        wf.writeframes(pcm16)
    wav_buf.seek(0)

    with sr.AudioFile(wav_buf) as source:
        audio_data = _recognizer.record(source)

    return _recognizer.recognize_google(audio_data, language="vi-VN").strip()


class VoiceTimer:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_voice = 0.0

    def touch(self):
        with self._lock:
            self._last_voice = time.monotonic()

    def elapsed(self):
        with self._lock:
            if self._last_voice == 0.0:
                return 0.0
            return time.monotonic() - self._last_voice


class EndpointDetector:
    FILLERS = frozenset({
        "ờ", "à", "ừ", "ừm", "ạ", "ơ", "ơi", "ê", "hả",
        "uhm", "um", "ah", "uh", "eh",
    })

    CONNECTORS = frozenset({
        "và", "hoặc", "nhưng", "rồi", "mà", "hay", "vì", "nên",
        "thì", "còn", "với", "để", "nếu", "khi",
    })

    ENDPOINTS = frozenset({
        "xong", "hết", "ok", "được rồi", "thế thôi", "vậy thôi",
        "cảm ơn", "tạm biệt",
    })

    SILENCE_TABLE = (
        (3,   1.2),
        (6,   1.6),
        (10,  2.0),
        (15,  2.5),
        (20,  3.0),
        (30,  3.5),
    )
    SILENCE_MAX = 4.5
    CONNECTOR_BONUS = 1.0
    TEXT_AGE_WORD_THRESHOLD = 6
    STABILITY_COUNT = 3

    def __init__(self):
        self._last_raw = ""
        self._last_merged = ""
        self._repeat_count = 0
        self._last_text_time = 0.0

    def on_text_received(self):
        self._last_text_time = time.monotonic()

    def _text_cooldown_elapsed(self):
        if self._last_text_time == 0.0:
            return float('inf')
        return time.monotonic() - self._last_text_time

    def filter_fillers(self, text):
        words = text.split()
        filtered = [w for w in words if w.lower() not in self.FILLERS]
        return " ".join(filtered)

    def is_duplicate(self, raw_text):
        normalized = raw_text.strip().lower()
        if normalized == self._last_raw:
            return True
        self._last_raw = normalized
        return False

    def try_extend_buffer(self, buffer, new_text):
        if not buffer:
            return False

        last = buffer[-1].lower()
        new_lower = new_text.lower()

        if new_lower.startswith(last) and len(new_text) > len(buffer[-1]):
            buffer[-1] = new_text
            return True

        if last.startswith(new_lower):
            return True

        return False

    def check_punctuation(self, text):
        return bool(text) and text[-1] in ".?!"

    def check_keyword_endpoint(self, text):
        lower = text.lower().strip()
        for kw in self.ENDPOINTS:
            if lower.endswith(kw):
                return True
        return False

    def check_stability(self, merged_text):
        normalized = merged_text.strip().lower()
        if normalized == self._last_merged:
            self._repeat_count += 1
        else:
            self._last_merged = normalized
            self._repeat_count = 1
        return self._repeat_count >= self.STABILITY_COUNT

    def get_silence_threshold(self, merged_text):
        words = merged_text.split()
        n = len(words)

        base = self.SILENCE_MAX
        for max_words, timeout in self.SILENCE_TABLE:
            if n <= max_words:
                base = timeout
                break

        if n > 0 and words[-1].lower() in self.CONNECTORS:
            base += self.CONNECTOR_BONUS

        return base

    def should_finalize_silence(self, merged_text, voice_elapsed,
                                 stt_is_busy, audio_q_empty, mic_is_recording):
        if stt_is_busy:
            return False

        if not audio_q_empty:
            return False

        if mic_is_recording:
            return False

        threshold = self.get_silence_threshold(merged_text)
        n = len(merged_text.split())

        if n > self.TEXT_AGE_WORD_THRESHOLD:
            text_age = self._text_cooldown_elapsed()
            effective = min(voice_elapsed, text_age)
        else:
            effective = voice_elapsed

        return effective > threshold

    def reset(self):
        self._last_raw = ""
        self._last_merged = ""
        self._repeat_count = 0
        self._last_text_time = 0.0


def mic_worker(audio_queue, mic, rnn_lib, rnn_state, silero_vad,
               voice_timer, stop_event, mic_recording, is_playing_event):
    while not stop_event.is_set():
        # --- Pause mic while audio is playing ---
        if is_playing_event.is_set():
            time.sleep(0.1)
            continue

        try:
            audio = capture_audio(mic, rnn_lib, rnn_state, silero_vad, audio_queue, voice_timer, mic_recording)

            if isinstance(audio, str) and audio == "__NO_VOICE__":
                time.sleep(0.3)
                continue

            if audio is None:
                continue

            voice_timer.touch()
            _ui.notify("listening")

            try:
                audio_queue.put_nowait(audio)
            except queue.Full:
                try:
                    audio_queue.get_nowait()
                except queue.Empty:
                    pass
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
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            print(f"\n[STT] Loi ket noi Google: {e}")
        except Exception as e:
            if not stop_event.is_set():
                print(f"\n[STT] Loi: {e}")
        finally:
            _ui.notify("idle")
            stt_busy.clear()


def login_and_get_token():
    try:
        print(f"[Auth] Dang nhap: {USER_DATA['username']}...")
        res = requests.post(f"{BASE_URL}/auth/login", json=USER_DATA, timeout=5)
        if res.status_code == 200:
            token = res.json().get("token")
            print(f"{GREEN}[Auth] Lay token thanh cong!{RESET}\n")
            return token
        else:
            print(f"{RED}[Auth] Dang nhap that bai: {res.text}{RESET}")
            return None
    except requests.exceptions.ConnectionError:
        print(f"{RED}[Auth] Loi: Khong the ket noi den server {BASE_URL}{RESET}")
        return None
    except requests.exceptions.Timeout:
        print(f"{RED}[Auth] Loi: Timeout ket noi den server{RESET}")
        return None
    except Exception as e:
        print(f"{RED}[Auth] Loi: {e}{RESET}")
        return None

# import soundfile as sf

# def play_audio_stream(url, is_playing_event):
#     try:
#         is_playing_event.set()
#         print(f"{CYAN}[TTS] Dang phat audio...{RESET}")

#         res = requests.get(url)
#         if res.status_code != 200:
#             print(f"{RED}[TTS] Loi tai audio{RESET}")
#             return

#         data, samplerate = sf.read(io.BytesIO(res.content), dtype='int16')

#         stream = _pyaudio.open(
#             format=pyaudio.paInt16,
#             channels=data.shape[1] if len(data.shape) > 1 else 1,
#             rate=samplerate,
#             output=True
#         )

#         stream.write(data.tobytes())

#         stream.stop_stream()
#         stream.close()
#         print(f"{GREEN}[TTS] Phat xong!{RESET}")

#     except Exception as e:
#         print(f"{RED}[TTS] Loi phat audio: {e}{RESET}")
#     finally:
#         is_playing_event.clear()
def play_audio_stream(url, is_playing_event, mic=None):
    try:
        is_playing_event.set()
        _ui.notify("speaking")
        # Mute mic ngay lập tức để không thu âm lại lúc phát
        if mic:
            mic.is_muted.set()
            mic.clear()  # Xóa sạch audio cũ trong queue
        print(f"{CYAN}[TTS] Dang phat audio...{RESET}")
        
        stream = _pyaudio.open(
            format=pyaudio.paInt16,
            channels=TTS_CHANNELS,
            rate=TTS_RATE,
            output=True
        )

        with requests.get(url, stream=True, timeout=10) as r:
            if r.status_code != 200:
                print(f"{RED}[TTS] Loi tai audio: {r.status_code}{RESET}")
                stream.close()
                return

            first_chunk = True
            for chunk in r.iter_content(chunk_size=4096):
                if not chunk:
                    continue

                if first_chunk:
                    # chunk = chunk[44:]
                    first_chunk = False
                    if not chunk:
                        continue

                stream.write(chunk)

        stream.stop_stream()
        stream.close()
        print(f"{GREEN}[TTS] Phat xong!{RESET}")
        time.sleep(0.5)  # Đợi một chút để loa tắt hẳn trước khi mở mic
        
    except Exception as e:
        print(f"{RED}[TTS] Loi phat audio: {e}{RESET}")
    finally:
        # Unmute mic và flush echo còn sót
        if mic:
            mic.clear()  # Xóa echo còn sót trong queue
            mic.is_muted.clear()
        _ui.notify("idle")
        is_playing_event.clear()


class WebSocketHandler:
    def __init__(self, token, is_playing_event, mic=None):
        self.token = token
        self.ws_url = f"{WS_URL}?token={token}"
        self.ws = None
        self.connected = False
        self.is_playing_event = is_playing_event
        self.mic = mic  # Tham chiếu đến MicStream để mute/unmute
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "AI_VOICE_REPLY":
                bot_text = data.get("text")
                audio_url = data.get("audioUrl")
                
                if bot_text:
                    print(f"\n{GREEN}[Bot]: {bot_text}{RESET}")
                
                if audio_url:
                    print(f"{CYAN}[Audio URL]: {audio_url}{RESET}")
                    threading.Thread(
                        target=play_audio_stream,
                        args=(audio_url, self.is_playing_event, self.mic),
                        daemon=True
                    ).start()
            
            elif msg_type == "AI_VOICE_DONE":
                print(f"{CYAN}[Bot] Hoan thanh phan hoi{RESET}")
                
            elif msg_type != "STATUS":
                print(f"{YELLOW}[WS] Event: {msg_type}{RESET}")
                
        except Exception as e:
            print(f"{RED}[WS] Loi xu ly message: {e}{RESET}")
    
    def on_error(self, ws, error):
        print(f"{RED}[WS] Loi: {error}{RESET}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print(f"{YELLOW}[WS] Ket noi dong{RESET}")
        self.connected = False
    
    def on_open(self, ws):
        print(f"{GREEN}[WS] Ket noi thanh cong!{RESET}")
        self.connected = True
    
    def connect(self):
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        return self.ws
    
    def send_text(self, text, timestamp, duration):
        if self.ws and self.connected:
            try:
                data = {
                    "text": text,
                    "language": "VI",
                    "voice":voice,
                    "timestamp": timestamp,
                    "duration": duration
                }
                self.ws.send(json.dumps(data))
                print(f"{GREEN}[WS] Da gui len server{RESET}")
            except Exception as e:
                print(f"{RED}[WS] Loi gui: {e}{RESET}")


def finalize_sentence(buffer, detector, reason, start_time, ws_handler=None):
    full = " ".join(buffer)
    clean = detector.filter_fillers(full)
    if not clean:
        buffer.clear()
        detector.reset()
        return
    
    end_time = time.time()
    duration = end_time - start_time if start_time else 0
    timestamp = int(start_time) if start_time else int(time.time())
    
    print(f"\n{GREEN}>> Cau hoan chinh [{reason}]{RESET}")
    print(f"   {clean}")
    print(f"   duration: {duration:.2f}s")
    
    data = {
        "text": clean,
        "language": "VI",
        "timestamp": timestamp,
        "duration": round(duration, 2)
    }
    
    print(f"\n{YELLOW}[DATA]{RESET}")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    
    if ws_handler:
        ws_handler.send_text(clean, timestamp, round(duration, 2))
    
    print("=" * 50)
    
    buffer.clear()
    detector.reset()


def main():
    print("=" * 50)
    print("  Voice AI Client — STT Pipeline")
    print("=" * 50)
    
    token = login_and_get_token()
    if not token:
        print(f"\n{RED}[Error] Khong the lay token. Thoat.{RESET}\n")
        return

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
    ws_thread = threading.Thread(
        target=ws.run_forever,
        daemon=True,
        name="websocket_worker"
    )
    ws_thread.start()
    time.sleep(1)

    print("\n[STT] Google Speech Recognition")
    print("[STT] San sang!\n")

    voice_timer = VoiceTimer()
    audio_queue = queue.Queue(maxsize=AUDIO_QUEUE_MAX)
    text_queue = queue.Queue(maxsize=TEXT_QUEUE_MAX)
    stt_busy = threading.Event()
    mic_recording = threading.Event()
    stop_event = threading.Event()

    def signal_handler(sig, frame):
        print("\n\n[System] Dang tat...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    t_mic = threading.Thread(
        target=mic_worker,
        args=(audio_queue, mic, rnn_lib, rnn_state, silero_vad,
              voice_timer, stop_event, mic_recording, is_playing_event),
        daemon=True, name="mic_worker"
    )
    t_stt = threading.Thread(
        target=stt_worker,
        args=(audio_queue, text_queue, stop_event, stt_busy),
        daemon=True, name="stt_worker"
    )

    t_mic.start()
    t_stt.start()

    print("[System] Pipeline dang chay. Ctrl+C de thoat.\n")
    print("-" * 50)

    try:
        detector = EndpointDetector()
        temp_text_buffer = []
        sentence_start_time = None
        was_playing = False

        while not stop_event.is_set():
            # --- Wait until audio playback finishes ---
            if is_playing_event.is_set():
                was_playing = True
                time.sleep(0.1)
                continue

            # --- Flush stale data after playback ends ---
            if was_playing:
                was_playing = False
                # Discard any audio/text captured during playback (echo)
                while not audio_queue.empty():
                    try:
                        audio_queue.get_nowait()
                    except queue.Empty:
                        break
                while not text_queue.empty():
                    try:
                        text_queue.get_nowait()
                    except queue.Empty:
                        break
                temp_text_buffer.clear()
                detector.reset()
                sentence_start_time = None
                print(f"\n{CYAN}[System] Audio xong, tiep tuc nghe...{RESET}")

            try:
                raw_text, latency = text_queue.get(timeout=0.1)

                text = detector.filter_fillers(raw_text)
                if not text:
                    print(f"\n[SKIP] Filler: '{raw_text}'")
                    continue

                if detector.is_duplicate(text):
                    print(f"\n[SKIP] Duplicate: '{text}'")
                    continue

                detector.on_text_received()

                print(f"\n{CYAN}Ban noi: {text}{RESET}")
                print(f"   {latency:.2f}s")

                if not temp_text_buffer:
                    sentence_start_time = time.time()

                if not detector.try_extend_buffer(temp_text_buffer, text):
                    temp_text_buffer.append(text)
                else:
                    print(f"   [MERGE] Mo rong buffer")

                if detector.check_punctuation(text):
                    finalize_sentence(temp_text_buffer, detector, "PUNCT", sentence_start_time, ws_handler)
                    sentence_start_time = None
                    continue

                if detector.check_keyword_endpoint(text):
                    finalize_sentence(temp_text_buffer, detector, "KEYWORD", sentence_start_time, ws_handler)
                    sentence_start_time = None
                    continue

                merged = " ".join(temp_text_buffer)
                if detector.check_stability(merged):
                    finalize_sentence(temp_text_buffer, detector, "STABLE", sentence_start_time, ws_handler)
                    sentence_start_time = None
                    continue

            except queue.Empty:
                pass

            if temp_text_buffer:
                merged = " ".join(temp_text_buffer)
                if detector.should_finalize_silence(
                    merged,
                    voice_timer.elapsed(),
                    stt_busy.is_set(),
                    audio_queue.empty(),
                    mic_recording.is_set(),
                ):
                    finalize_sentence(temp_text_buffer, detector, "SILENCE", sentence_start_time, ws_handler)
                    sentence_start_time = None

    except KeyboardInterrupt:
        stop_event.set()

    if temp_text_buffer:
        finalize_sentence(temp_text_buffer, detector, "EXIT", sentence_start_time, ws_handler)

    t_mic.join(timeout=3.0)
    t_stt.join(timeout=3.0)
    
    if ws_handler and ws_handler.ws:
        ws_handler.ws.close()
    if ws_thread:
        ws_thread.join(timeout=3.0)

    mic.stop()
    if rnn_lib and rnn_state:
        rnn_lib.rnnoise_destroy(rnn_state)

    print("\n[System] Tam biet!")


if __name__ == "__main__":
    main()
