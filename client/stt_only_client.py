import time
import queue
import threading
import signal
import io
import wave
import json

import numpy as np
import speech_recognition as sr
import pyaudio

from STT import (
    init_rnnoise, init_silero, SileroVAD,
    MicStream, capture_audio, TARGET_SR
)

AUDIO_QUEUE_MAX = 5
TEXT_QUEUE_MAX = 10

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"

_recognizer = sr.Recognizer()


def transcribe_audio(audio_16k):
    """Chuyển đổi audio thành text sử dụng Google Speech Recognition"""
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
    """Theo dõi thời gian từ lần cuối có giọng nói"""
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
    """Phát hiện điểm kết thúc câu dựa trên từ khóa, dấu câu và khoảng lặng"""
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
        """Loại bỏ các từ filler không cần thiết"""
        words = text.split()
        filtered = [w for w in words if w.lower() not in self.FILLERS]
        return " ".join(filtered)

    def is_duplicate(self, raw_text):
        """Kiểm tra text có bị trùng lặp không"""
        normalized = raw_text.strip().lower()
        if normalized == self._last_raw:
            return True
        self._last_raw = normalized
        return False
    def try_extend_buffer(self, buffer, new_text):
        """Thử mở rộng buffer với text mới"""
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
        """Kiểm tra text có kết thúc bằng dấu câu không"""
        return bool(text) and text[-1] in ".?!"

    def check_keyword_endpoint(self, text):
        """Kiểm tra text có chứa từ khóa kết thúc không"""
        lower = text.lower().strip()
        for kw in self.ENDPOINTS:
            if lower.endswith(kw):
                return True
        return False

    def check_stability(self, merged_text):
        """Kiểm tra text có ổn định (lặp lại nhiều lần) không"""
        normalized = merged_text.strip().lower()
        if normalized == self._last_merged:
            self._repeat_count += 1
        else:
            self._last_merged = normalized
            self._repeat_count = 1
        return self._repeat_count >= self.STABILITY_COUNT

    def get_silence_threshold(self, merged_text):
        """Tính ngưỡng thời gian im lặng dựa trên độ dài text"""
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
        """Kiểm tra có nên kết thúc câu do im lặng không"""
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
        """Reset trạng thái detector"""
        self._last_raw = ""
        self._last_merged = ""
        self._repeat_count = 0
        self._last_text_time = 0.0
def mic_worker(audio_queue, mic, rnn_lib, rnn_state, silero_vad,
               voice_timer, stop_event, mic_recording):
    """Worker thread để ghi âm và xử lý audio"""
    while not stop_event.is_set():
        try:
            audio = capture_audio(mic, rnn_lib, rnn_state, silero_vad, audio_queue, voice_timer, mic_recording)

            if isinstance(audio, str) and audio == "__NO_VOICE__":
                time.sleep(0.5)
                continue

            if audio is None:
                continue

            voice_timer.touch()

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
                print(f"\n[Mic] Lỗi: {e}")
            break


def stt_worker(audio_queue, text_queue, stop_event, stt_busy):
    """Worker thread để xử lý STT"""
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
            print(f"\n[STT] Lỗi kết nối Google: {e}")
        except Exception as e:
            if not stop_event.is_set():
                print(f"\n[STT] Lỗi: {e}")
        finally:
            stt_busy.clear()


def finalize_sentence(buffer, detector, reason, start_time):
    """Hoàn thiện và in ra câu đã nhận diện"""
    full = " ".join(buffer)
    clean = detector.filter_fillers(full)
    if not clean:
        buffer.clear()
        detector.reset()
        return
    
    end_time = time.time()
    duration = end_time - start_time if start_time else 0
    timestamp = int(start_time) if start_time else int(time.time())
    
    print(f"\n{GREEN}>> Câu hoàn chỉnh [{reason}]{RESET}")
    print(f"   {clean}")
    print(f"   Thời lượng: {duration:.2f}s")
    
    # Tạo data object để có thể sử dụng sau này
    data = {
        "text": clean,
        "language": "VI",
        "timestamp": timestamp,
        "duration": round(duration, 2)
    }
    
    print(f"\n{YELLOW}[DATA]{RESET}")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("=" * 50)
    
    buffer.clear()
    detector.reset()
def main():
    """Hàm chính chạy STT client"""
    print("=" * 50)
    print("  Voice STT Client — Chỉ ghi âm và STT")
    print("=" * 50)
    
    # Khởi tạo RNNoise và Silero VAD
    rnn_lib, rnn_state = init_rnnoise()
    silero_model = init_silero()
    silero_vad = SileroVAD(silero_model)

    # Khởi tạo microphone
    mic = MicStream()
    mic.start()
    print("[Mic] Microphone stream đã mở.")

    print("\n[STT] Google Speech Recognition")
    print("[STT] Sẵn sàng!\n")

    # Khởi tạo các components
    voice_timer = VoiceTimer()
    audio_queue = queue.Queue(maxsize=AUDIO_QUEUE_MAX)
    text_queue = queue.Queue(maxsize=TEXT_QUEUE_MAX)
    stt_busy = threading.Event()
    mic_recording = threading.Event()
    stop_event = threading.Event()

    def signal_handler(sig, frame):
        print("\n\n[System] Đang tắt...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    # Khởi tạo worker threads
    t_mic = threading.Thread(
        target=mic_worker,
        args=(audio_queue, mic, rnn_lib, rnn_state, silero_vad,
              voice_timer, stop_event, mic_recording),
        daemon=True, name="mic_worker"
    )
    t_stt = threading.Thread(
        target=stt_worker,
        args=(audio_queue, text_queue, stop_event, stt_busy),
        daemon=True, name="stt_worker"
    )

    t_mic.start()
    t_stt.start()

    print("[System] Pipeline đang chạy. Ctrl+C để thoát.\n")
    print("-" * 50)

    try:
        detector = EndpointDetector()
        temp_text_buffer = []
        sentence_start_time = None

        while not stop_event.is_set():
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

                print(f"\n{CYAN}Bạn nói: {text}{RESET}")
                print(f"   {latency:.2f}s")

                if not temp_text_buffer:
                    sentence_start_time = time.time()

                if not detector.try_extend_buffer(temp_text_buffer, text):
                    temp_text_buffer.append(text)
                else:
                    print(f"   [MERGE] Mở rộng buffer")

                # Kiểm tra các điều kiện kết thúc câu
                if detector.check_punctuation(text):
                    finalize_sentence(temp_text_buffer, detector, "PUNCT", sentence_start_time)
                    sentence_start_time = None
                    continue

                if detector.check_keyword_endpoint(text):
                    finalize_sentence(temp_text_buffer, detector, "KEYWORD", sentence_start_time)
                    sentence_start_time = None
                    continue

                merged = " ".join(temp_text_buffer)
                if detector.check_stability(merged):
                    finalize_sentence(temp_text_buffer, detector, "STABLE", sentence_start_time)
                    sentence_start_time = None
                    continue

            except queue.Empty:
                pass

            # Kiểm tra kết thúc do im lặng
            if temp_text_buffer:
                merged = " ".join(temp_text_buffer)
                if detector.should_finalize_silence(
                    merged,
                    voice_timer.elapsed(),
                    stt_busy.is_set(),
                    audio_queue.empty(),
                    mic_recording.is_set(),
                ):
                    finalize_sentence(temp_text_buffer, detector, "SILENCE", sentence_start_time)
                    sentence_start_time = None

    except KeyboardInterrupt:
        stop_event.set()

    # Hoàn thiện câu cuối nếu có
    if temp_text_buffer:
        finalize_sentence(temp_text_buffer, detector, "EXIT", sentence_start_time)

    # Đợi threads kết thúc
    t_mic.join(timeout=3.0)
    t_stt.join(timeout=3.0)

    # Dọn dẹp
    mic.stop()
    if rnn_lib and rnn_state:
        rnn_lib.rnnoise_destroy(rnn_state)

    print("\n[System] Tạm biệt!")


if __name__ == "__main__":
    main()