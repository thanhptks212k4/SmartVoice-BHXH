"""
STT WebSocket Server
Browser gửi raw PCM float32 (16kHz, mono) theo từng chunk 20ms
Server chạy: RNNoise + Silero VAD + EndpointDetector → Google STT hoặc Whisper
Trả về JSON: {"text": "...", "final": true/false}

Env:
  STT_ENGINE=google|whisper  (default: google)
  WHISPER_MODEL=tiny|base|small|medium  (default: base)
  STT_WS_PORT=8003
"""

import asyncio, json, os, time, collections
import numpy as np
import websockets
from scipy.signal import butter, lfilter_zi, lfilter
import torch
from dotenv import load_dotenv

# Load .env tu thu muc cha (AI_Service/.env)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# ── Config ──
STT_ENGINE         = os.getenv("STT_ENGINE", "google")
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
WHISPER_MODEL_DIR  = os.getenv("WHISPER_MODEL_DIR", "AI_Service/stt_service/model")
PORT               = int(os.getenv("STT_WS_PORT", 8003))

TARGET_SR    = 16000
SILERO_CHUNK = 512
SILERO_THRESH = 0.5
ENERGY_RATIO  = 1.5
NOISE_ALPHA   = 0.95
MIN_ENERGY    = 0.003
DOM_WINDOW    = 10
DOM_THRESHOLD = 0.3
SILENCE_S     = 1.2
MAX_RECORD_S  = 15.0
NO_VOICE_S    = 10.0
MIN_ENERGY    = 0.008

_HP_B, _HP_A = butter(2, 80 / (TARGET_SR / 2), btype='high')

# ── Load models ──
silero_model, _ = torch.hub.load("snakers4/silero-vad", "silero_vad", trust_repo=True)
silero_model.eval()

whisper_model = None
if STT_ENGINE == "whisper":
    import whisper as _whisper
    # Neu file model da co trong thu muc thi load tu do, khong download lai
    model_file = os.path.join(WHISPER_MODEL_DIR, f"{WHISPER_MODEL_NAME}.pt")
    if os.path.isfile(model_file):
        whisper_model = _whisper.load_model(WHISPER_MODEL_NAME, download_root=WHISPER_MODEL_DIR)
    else:
        os.makedirs(WHISPER_MODEL_DIR, exist_ok=True)
        whisper_model = _whisper.load_model(WHISPER_MODEL_NAME, download_root=WHISPER_MODEL_DIR)
else:
    import speech_recognition as sr
    _recognizer = sr.Recognizer()


# ── Silero VAD per-connection state ──
class SileroVAD:
    def __init__(self):
        self.buf     = np.zeros(SILERO_CHUNK, dtype=np.float32)
        self.buf_pos = 0
        self.last_prob = 0.0

    def reset(self):
        silero_model.reset_states()
        self.buf_pos   = 0
        self.last_prob = 0.0

    def feed(self, samples_16k):
        pos = 0
        while pos < len(samples_16k):
            space = SILERO_CHUNK - self.buf_pos
            take  = min(space, len(samples_16k) - pos)
            self.buf[self.buf_pos:self.buf_pos + take] = samples_16k[pos:pos + take]
            self.buf_pos += take
            pos += take
            if self.buf_pos >= SILERO_CHUNK:
                tensor = torch.from_numpy(self.buf.copy()).float().unsqueeze(0)
                with torch.no_grad():
                    self.last_prob = silero_model(tensor, TARGET_SR).item()
                self.buf_pos = 0
        return self.last_prob > SILERO_THRESH, self.last_prob


# ── STT ──
def run_stt(audio_np):
    """audio_np: float32 numpy array 16kHz mono"""
    if STT_ENGINE == "whisper":
        result = whisper_model.transcribe(
            audio_np,
            language="vi",
            fp16=False,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            logprob_threshold=-1.0,
            temperature=0.0,          # greedy decode, ít hallucination hơn
            beam_size=5,              # beam search cho kết quả tốt hơn
            best_of=5,
            task="transcribe",        # không dịch, chỉ nhận dạng
        )
        text = result["text"].strip()
        # Bỏ qua hallucination: chứa token đặc biệt hoặc quá ngắn
        if "<|" in text or len(text) < 2:
            return ""
        return text
    else:
        import io, wave, speech_recognition as sr
        pcm16 = (audio_np * 32768).astype(np.int16).tobytes()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(TARGET_SR)
            wf.writeframes(pcm16)
        buf.seek(0)
        with sr.AudioFile(buf) as source:
            audio_data = _recognizer.record(source)
        return _recognizer.recognize_google(audio_data, language="vi-VN").strip()


# ── Per-connection handler ──
async def handle(websocket):
    print(f"[WS] Client connected: {websocket.remote_address}")
    vad       = SileroVAD()
    hp_zi     = lfilter_zi(_HP_B, _HP_A)
    pre_buf   = collections.deque(maxlen=15)   # ~300ms pre-roll
    audio_frames = []
    has_voice    = False
    noise_floor  = MIN_ENERGY
    dom_buf      = collections.deque(maxlen=DOM_WINDOW)
    t_start      = time.time()
    t_last_voice = t_start
    t_first_voice = None

    try:
        async for message in websocket:
            # Browser gửi binary: Float32Array little-endian
            if isinstance(message, bytes):
                chunk = np.frombuffer(message, dtype=np.float32).copy()
            else:
                # JSON control message: {"cmd": "reset"} hoặc {"cmd": "engine", "value": "whisper"}
                try:
                    ctrl = json.loads(message)
                    if ctrl.get("cmd") == "reset":
                        vad.reset(); pre_buf.clear(); audio_frames.clear()
                        has_voice = False; noise_floor = MIN_ENERGY
                        dom_buf.clear(); t_start = time.time()
                        t_last_voice = t_start; t_first_voice = None
                        hp_zi = lfilter_zi(_HP_B, _HP_A)
                    elif ctrl.get("cmd") == "ping":
                        await websocket.send(json.dumps({"pong": True}))
                except Exception:
                    pass
                continue

            # High-pass filter
            chunk, hp_zi = lfilter(_HP_B, _HP_A, chunk, zi=hp_zi)
            chunk = chunk.astype(np.float32)

            # Silero VAD
            is_silero, prob = vad.feed(chunk)

            # Energy VAD
            rms = np.sqrt(np.mean(chunk ** 2) + 1e-9)
            energy_speech = rms > max(noise_floor * ENERGY_RATIO, MIN_ENERGY)
            if not energy_speech:
                noise_floor = NOISE_ALPHA * noise_floor + (1 - NOISE_ALPHA) * rms

            speech_candidate = is_silero and energy_speech
            dom_buf.append(1 if speech_candidate else 0)
            dominance = sum(dom_buf) / len(dom_buf) if dom_buf else 0

            now = time.time()

            if dominance > DOM_THRESHOLD:
                t_last_voice = now
                if not has_voice:
                    has_voice     = True
                    t_first_voice = now
                    audio_frames.extend(pre_buf)
                    pre_buf.clear()
                    await websocket.send(json.dumps({"event": "speech_start"}))

            if not has_voice:
                pre_buf.append(chunk)
            else:
                audio_frames.append(chunk)

            # Timeout không có giọng nói
            if not has_voice and (now - t_start > NO_VOICE_S):
                t_start = now

            # Im lặng sau khi nói → finalize
            if has_voice and (now - t_last_voice > SILENCE_S):
                audio = np.concatenate(audio_frames)
                audio_frames.clear()
                has_voice     = False
                t_first_voice = None
                t_start       = now
                vad.reset()
                hp_zi = lfilter_zi(_HP_B, _HP_A)
                dom_buf.clear()

                await websocket.send(json.dumps({"event": "speech_end"}))

                # Chạy STT trong thread pool để không block event loop
                loop = asyncio.get_event_loop()
                try:
                    text = await loop.run_in_executor(None, run_stt, audio)
                    if text:
                        await websocket.send(json.dumps({"text": text, "final": True}))
                        print(f"[STT] {text}")
                except Exception as e:
                    print(f"[STT] Error: {e}")

            # Quá 15s → gửi partial
            if has_voice and t_first_voice and (now - t_first_voice > MAX_RECORD_S):
                audio = np.concatenate(audio_frames)
                audio_frames.clear()
                t_first_voice = now
                loop = asyncio.get_event_loop()
                try:
                    text = await loop.run_in_executor(None, run_stt, audio)
                    if text:
                        await websocket.send(json.dumps({"text": text, "final": False}))
                except Exception as e:
                    print(f"[STT] Partial error: {e}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[WS] Client disconnected")


async def main():
    print(f"[STT-WS] Listening on ws://0.0.0.0:{PORT}")
    async with websockets.serve(handle, "0.0.0.0", PORT, ping_interval=60, ping_timeout=120):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
