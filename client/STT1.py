import sounddevice as sd
import numpy as np
import wave
import time
import ctypes
import samplerate
import torch

from scipy.signal import butter, lfilter

# ================= CONFIG =================
INPUT_SR = 16000
RNNOISE_SR = 48000

FRAME_MS = 10
FRAME_16K = int(INPUT_SR * FRAME_MS / 1000)      # 160
FRAME_48K = int(RNNOISE_SR * FRAME_MS / 1000)    # 480

MAX_RECORD_TIME = 15.0
SILENCE_TIMEOUT = 2.0
NO_VOICE_TIMEOUT = 10.0

# ---- speech decision ----
ENERGY_RATIO = 1.0
NOISE_ALPHA = 0.95
SPEECH_BAND_RATIO = 0.25
SILERO_THRESHOLD = 0.7

DOM_WINDOW = 15
DOM_THRESHOLD = 0.25

OUTPUT_WAV = "voice.wav"
# ========================================

# -------- RNNoise --------
import os
rnnoise = ctypes.cdll.LoadLibrary(os.path.expanduser("/home/doduy/Documents/rnnoise/.libs/librnnoise.so"))
rnnoise.rnnoise_process_frame.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_float),
    ctypes.POINTER(ctypes.c_float),
]
rnnoise.rnnoise_create.restype = ctypes.c_void_p
rnnoise_state = rnnoise.rnnoise_create(None)

# -------- Silero VAD --------
silero_model, silero_utils = torch.hub.load(
    repo_or_dir="snakers4/silero-vad",
    model="silero_vad",
    trust_repo=True
)
silero_model.eval()

SILERO_SAMPLES = 512
silero_buf = np.zeros(0, dtype=np.float32)

def silero_is_speech(frame_16k):
    global silero_buf

    silero_buf = np.concatenate([silero_buf, frame_16k])

    if len(silero_buf) < SILERO_SAMPLES:
        return False, 0.0

    chunk = silero_buf[:SILERO_SAMPLES]
    silero_buf = silero_buf[SILERO_SAMPLES:]

    tensor = torch.from_numpy(chunk).float().unsqueeze(0)

    with torch.no_grad():
        prob = silero_model(tensor, INPUT_SR).item()

    return prob > SILERO_THRESHOLD, prob


# -------- Filters --------
def highpass(x, cutoff=80):
    b, a = butter(1, cutoff / (INPUT_SR / 2), btype='high')
    return lfilter(b, a, x)

def speech_band_ratio(x):
    fft = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), 1 / INPUT_SR)
    speech_energy = np.sum(fft[(freqs > 300) & (freqs < 3400)])
    return speech_energy / (np.sum(fft) + 1e-9)

# -------- Resamplers --------
to_48k = samplerate.Resampler("sinc_fastest", channels=1)
to_16k = samplerate.Resampler("sinc_fastest", channels=1)

# -------- Main --------
def record():
    # print("  Hệ thống sẵn sàng...")
    silero_model.reset_states()

    frames = []
    start_time = time.time()
    last_voice = start_time

    had_voice = False
    first_voice_time = None
    no_voice_warned = False

    noise_floor = 0.001
    dom_buf = []

    with sd.InputStream(
        samplerate=INPUT_SR,
        channels=1,
        blocksize=FRAME_16K,
        dtype="float32"
    ) as stream:

        while True:
            audio, _ = stream.read(FRAME_16K)
            audio = highpass(audio[:, 0])

            # --- 16k → 48k ---
            audio_48k = to_48k.process(audio, RNNOISE_SR / INPUT_SR)
            if len(audio_48k) != FRAME_48K:
                continue

            # --- RNNoise ---
            in_buf = (ctypes.c_float * FRAME_48K)(*audio_48k)
            out_buf = (ctypes.c_float * FRAME_48K)()
            rnnoise.rnnoise_process_frame(rnnoise_state, out_buf, in_buf)
            clean_48k = np.frombuffer(out_buf, dtype=np.float32)

            # --- 48k → 16k ---
            clean_16k = to_16k.process(clean_48k, INPUT_SR / RNNOISE_SR)
            if len(clean_16k) != FRAME_16K:
                continue

            pcm16 = (clean_16k * 32768).astype(np.int16).tobytes()
            frames.append(pcm16)

            # ---- Silero VAD ----
            is_speech, prob = silero_is_speech(clean_16k)

            rms = np.sqrt(np.mean(clean_16k ** 2) + 1e-9)
            if not is_speech:
                noise_floor = NOISE_ALPHA * noise_floor + (1 - NOISE_ALPHA) * rms

            band_ratio = speech_band_ratio(clean_16k)

            speech_candidate = (
                is_speech and
                prob > SILERO_THRESHOLD and
                rms > noise_floor * ENERGY_RATIO and
                band_ratio > SPEECH_BAND_RATIO
            )

            dom_buf.append(1 if speech_candidate else 0)
            if len(dom_buf) > DOM_WINDOW:
                dom_buf.pop(0)

            dominance = sum(dom_buf) / len(dom_buf)
            now = time.time()

            if dominance > DOM_THRESHOLD:
                last_voice = now
                if not had_voice:
                    had_voice = True
                    first_voice_time = now
                print(f"  VOICE  prob={prob:.2f}", end="\r")
            else:
                print(f"  NOISE  prob={prob:.2f}", end="\r")

            # ---- warn: no voice ----
            if not had_voice and not no_voice_warned and (now - start_time > NO_VOICE_TIMEOUT):
                # print("\n  Xin lỗi, bạn có cần tôi giúp gì không?")
                no_voice_warned = True
                return "__NO_VOICE__"

            # ---- stop: silence ----
            if had_voice and (now - last_voice > SILENCE_TIMEOUT):
                print("\n⏹  Im lặng 2s → dừng")
                break

            # ---- stop: max talk ----
            if had_voice and (now - first_voice_time > MAX_RECORD_TIME):
                print("\n⏹  Đã nói đủ 15s → dừng")
                break

    if not had_voice:
        # print("  Không phát hiện giọng người → không lưu file")
        return None

    with wave.open(OUTPUT_WAV, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(INPUT_SR)
        wf.writeframes(b"".join(frames))

    # print(f" Đã lưu file: {OUTPUT_WAV}")
    return OUTPUT_WAV

# if __name__ == "__main__":
#     record()