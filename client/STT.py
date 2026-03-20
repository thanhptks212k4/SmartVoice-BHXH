import numpy as np
import sounddevice as sd
import time
import ctypes
import os
import collections
import queue
import torch

from scipy.signal import butter, lfilter_zi, lfilter

MIC_SR         = 48000
TARGET_SR      = 16000

RNNOISE_FRAME  = 480

BLOCK_MS       = 20
MIC_BLOCKSIZE  = int(MIC_SR * BLOCK_MS / 1000)

MAX_RECORD_S   = 15.0
SILENCE_S      = 0.8
NO_VOICE_S     = 10.0

PRE_BUF_COUNT  = int(300 / BLOCK_MS)

SILERO_CHUNK   = 512
SILERO_THRESH  = 0.5

ENERGY_RATIO   = 1.5
NOISE_ALPHA    = 0.95
MIN_ENERGY     = 0.003

DOM_WINDOW     = 10
DOM_THRESHOLD  = 0.3

MIC_QUEUE_MAX  = 150

_HP_B, _HP_A   = butter(2, 80 / (MIC_SR / 2), btype='high')


RNNOISE_LIB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "rnnoise", ".libs", "librnnoise.so"
)

_rnn_in  = (ctypes.c_float * RNNOISE_FRAME)()
_rnn_out = (ctypes.c_float * RNNOISE_FRAME)()
_rnn_result = np.empty(MIC_BLOCKSIZE, dtype=np.float32)


def init_rnnoise():
    if not os.path.exists(RNNOISE_LIB_PATH):
        print(f"[RNNoise] Khong tim thay: {RNNOISE_LIB_PATH}")
        return None, None

    lib = ctypes.cdll.LoadLibrary(RNNOISE_LIB_PATH)
    lib.rnnoise_create.restype  = ctypes.c_void_p
    lib.rnnoise_create.argtypes = [ctypes.c_void_p]
    lib.rnnoise_process_frame.restype  = ctypes.c_float
    lib.rnnoise_process_frame.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
    ]
    lib.rnnoise_destroy.restype  = None
    lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]

    state = lib.rnnoise_create(None)
    print("[RNNoise] San sang.")
    return lib, state


def rnnoise_block(block_48k, rnn_lib, rnn_state):
    if rnn_lib is None:
        return block_48k

    for i in range(2):
        offset = i * RNNOISE_FRAME

        for j in range(RNNOISE_FRAME):
            _rnn_in[j] = block_48k[offset + j]

        rnn_lib.rnnoise_process_frame(rnn_state, _rnn_out, _rnn_in)

        _rnn_result[offset:offset + RNNOISE_FRAME] = np.frombuffer(
            _rnn_out, dtype=np.float32
        )

    return _rnn_result.copy()


def init_silero():
    print("[Silero] Dang load model VAD...")
    model, _ = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        trust_repo=True
    )
    model.eval()
    print("[Silero] San sang.")
    return model


class SileroVAD:
    def __init__(self, model):
        self.model = model
        self.buf = np.zeros(SILERO_CHUNK, dtype=np.float32)
        self.buf_pos = 0
        self.last_prob = 0.0

    def reset(self):
        self.model.reset_states()
        self.buf_pos = 0
        self.last_prob = 0.0

    def feed(self, samples_16k):
        pos = 0
        while pos < len(samples_16k):
            space = SILERO_CHUNK - self.buf_pos
            take = min(space, len(samples_16k) - pos)
            self.buf[self.buf_pos:self.buf_pos + take] = samples_16k[pos:pos + take]
            self.buf_pos += take
            pos += take

            if self.buf_pos >= SILERO_CHUNK:
                tensor = torch.from_numpy(self.buf.copy()).float().unsqueeze(0)
                with torch.no_grad():
                    self.last_prob = self.model(tensor, TARGET_SR).item()
                self.buf_pos = 0

        return self.last_prob > SILERO_THRESH, self.last_prob


class MicStream:
    def __init__(self):
        self.q = queue.Queue(maxsize=MIC_QUEUE_MAX)
        self.stream = None

    def _callback(self, indata, frames, t_info, status):
        try:
            self.q.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    def start(self):
        if self.stream is None:
            self.stream = sd.InputStream(
                samplerate=MIC_SR,
                channels=1,
                dtype="float32",
                blocksize=MIC_BLOCKSIZE,
                callback=self._callback,
            )
            self.stream.start()

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def get(self, timeout=0.5):
        return self.q.get(timeout=timeout)

    def clear(self):
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break


def capture_audio(mic, rnn_lib, rnn_state, silero_vad, audio_queue=None, voice_timer=None, recording_flag=None):
    silero_vad.reset()
    mic.clear()

    hp_zi = lfilter_zi(_HP_B, _HP_A)
    pre_buf = collections.deque(maxlen=PRE_BUF_COUNT)

    audio_frames = []
    has_voice    = False
    noise_floor  = MIN_ENERGY
    dom_buf      = collections.deque(maxlen=DOM_WINDOW)

    t_start      = time.time()
    t_last_voice = t_start
    t_first_voice = None

    print("\r[MIC] Dang lang nghe...          ", end="", flush=True)

    while True:
        try:
            block_48k = mic.get(timeout=0.5)
        except queue.Empty:
            continue

        block_48k, hp_zi = lfilter(_HP_B, _HP_A, block_48k, zi=hp_zi)
        block_48k = block_48k.astype(np.float32)

        clean_48k = rnnoise_block(block_48k, rnn_lib, rnn_state)
        clean_16k = clean_48k[::3].copy()

        is_silero, prob = silero_vad.feed(clean_16k)

        rms = np.sqrt(np.mean(clean_16k ** 2) + 1e-9)
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
                has_voice = True
                t_first_voice = now
                audio_frames.extend(pre_buf)
                pre_buf.clear()
                if recording_flag:
                    recording_flag.set()
                print("\r[MIC] Dang thu am...  ", end="", flush=True)

        if not has_voice:
            pre_buf.append(clean_16k)
        else:
            audio_frames.append(clean_16k)

        if not has_voice and (now - t_start > NO_VOICE_S):
            print("\r[WAIT] Khong phat hien giong noi.       ")
            if recording_flag:
                recording_flag.clear()
            return "__NO_VOICE__"

        if has_voice and (now - t_last_voice > SILENCE_S):
            print("\r[STOP] Cat cau (im lang).              ")
            break

        if has_voice and (now - t_first_voice > MAX_RECORD_S):
            if audio_queue is not None and audio_frames:
                audio = np.concatenate(audio_frames)
                if voice_timer:
                    voice_timer.touch()
                try:
                    audio_queue.put_nowait(audio)
                except:
                    try:
                        audio_queue.get_nowait()
                    except:
                        pass
                    audio_queue.put_nowait(audio)
                audio_frames = []
                t_first_voice = now
                print("\r[STT] Gui 15s, tiep tuc nghe...  ", end="", flush=True)
            else:
                print("\r[STOP] Dat gioi han 15s.               ")
                break

    if recording_flag:
        recording_flag.clear()

    if not audio_frames:
        return None

    return np.concatenate(audio_frames)