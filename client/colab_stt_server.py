# =============================================================
#  STT Server — Google Colab Notebook
#  Copy từng cell vào Colab, chạy theo thứ tự từ trên xuống
#
#  Luồng:
#    Browser (VoicePage.jsx)
#      → Float32 PCM 16kHz (WebSocket)
#      → [ngrok tunnel]
#      → Colab: Silero VAD + Whisper
#      → text JSON
#      → Browser → Node.js backend
# =============================================================


# ═════════════════════════════════════════════════════════════
# CELL 1: Kiểm tra GPU
# ═════════════════════════════════════════════════════════════
"""
!nvidia-smi
"""

# ═════════════════════════════════════════════════════════════
# CELL 2: Install dependencies
# ═════════════════════════════════════════════════════════════
"""
!pip install -q openai-whisper websockets scipy torch torchaudio pyngrok
"""

# ═════════════════════════════════════════════════════════════
# CELL 3: Config
# ═════════════════════════════════════════════════════════════
"""
import os

# Cấu hình
WHISPER_MODEL = "small"   # tiny / base / small / medium
STT_WS_PORT   = 8003
NGROK_TOKEN   = ""        # Lấy từ https://dashboard.ngrok.com/get-started/your-authtoken (optional, free tier không cần)

# Set env
os.environ["STT_ENGINE"] = "whisper"
os.environ["WHISPER_MODEL"] = WHISPER_MODEL
os.environ["STT_WS_PORT"] = str(STT_WS_PORT)

print(f"✓ Config: Whisper [{WHISPER_MODEL}] on port {STT_WS_PORT}")
"""

# ═════════════════════════════════════════════════════════════
# CELL 4: Load models (Silero VAD + Whisper)
# ═════════════════════════════════════════════════════════════
"""
import torch
import whisper

print("[1/2] Loading Silero VAD...")
silero_model, _ = torch.hub.load("snakers4/silero-vad", "silero_vad", trust_repo=True)
silero_model.eval()
print("✓ Silero VAD ready!")

print(f"[2/2] Loading Whisper [{WHISPER_MODEL}]...")
whisper_model = whisper.load_model(WHISPER_MODEL)
print(f"✓ Whisper [{WHISPER_MODEL}] ready!")
print(f"✓ Device: {whisper_model.device}")
"""

# ═════════════════════════════════════════════════════════════
# CELL 5: STT Server Code
# ═════════════════════════════════════════════════════════════
"""
import asyncio, json, time, collections
import numpy as np
import websockets
from scipy.signal import butter, lfilter_zi, lfilter

# ── Config ──
TARGET_SR     = 16000
SILERO_CHUNK  = 512
SILERO_THRESH = 0.5
ENERGY_RATIO  = 1.5
NOISE_ALPHA   = 0.95
MIN_ENERGY    = 0.008
DOM_WINDOW    = 10
DOM_THRESHOLD = 0.3
SILENCE_S     = 1.2
MAX_RECORD_S  = 15.0
NO_VOICE_S    = 10.0

_HP_B, _HP_A = butter(2, 80 / (TARGET_SR / 2), btype='high')

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
    \"\"\"audio_np: float32 numpy array 16kHz mono\"\"\"
    result = whisper_model.transcribe(
        audio_np,
        language="vi",
        fp16=False,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        logprob_threshold=-1.0,
        temperature=0.0,
        beam_size=5,
        best_of=5,
        task="transcribe",
    )
    text = result["text"].strip()
    # Bỏ qua hallucination
    if "<|" in text or len(text) < 2:
        return ""
    return text

# ── WebSocket handler ──
async def handle(websocket):
    client_ip = websocket.remote_address
    print(f"\\n[WS] ✓ Client connected: {client_ip}")
    
    vad       = SileroVAD()
    hp_zi     = lfilter_zi(_HP_B, _HP_A)
    pre_buf   = collections.deque(maxlen=15)
    audio_frames = []
    has_voice    = False
    noise_floor  = MIN_ENERGY
    dom_buf      = collections.deque(maxlen=DOM_WINDOW)
    t_start      = time.time()
    t_last_voice = t_start
    t_first_voice = None

    try:
        async for message in websocket:
            if isinstance(message, bytes):
                chunk = np.frombuffer(message, dtype=np.float32).copy()
            else:
                try:
                    ctrl = json.loads(message)
                    if ctrl.get("cmd") == "reset":
                        vad.reset(); pre_buf.clear(); audio_frames.clear()
                        has_voice = False; noise_floor = MIN_ENERGY
                        dom_buf.clear(); t_start = time.time()
                        t_last_voice = t_start; t_first_voice = None
                        hp_zi = lfilter_zi(_HP_B, _HP_A)
                        print(f"[WS] Reset state")
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
                    print(f"[VAD] 🎤 Speech detected")

            if not has_voice:
                pre_buf.append(chunk)
            else:
                audio_frames.append(chunk)

            if not has_voice and (now - t_start > NO_VOICE_S):
                t_start = now

            # Im lặng → finalize
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
                print(f"[VAD] 🔇 Silence detected, processing...")

                loop = asyncio.get_event_loop()
                try:
                    t0 = time.time()
                    text = await loop.run_in_executor(None, run_stt, audio)
                    dt = time.time() - t0
                    if text:
                        await websocket.send(json.dumps({"text": text, "final": True}))
                        print(f"[STT] ✓ '{text}' ({dt:.2f}s)")
                    else:
                        print(f"[STT] ✗ No text (hallucination filtered)")
                except Exception as e:
                    print(f"[STT] ✗ Error: {e}")

            # Quá 15s → partial
            if has_voice and t_first_voice and (now - t_first_voice > MAX_RECORD_S):
                audio = np.concatenate(audio_frames)
                audio_frames.clear()
                t_first_voice = now
                loop = asyncio.get_event_loop()
                try:
                    text = await loop.run_in_executor(None, run_stt, audio)
                    if text:
                        await websocket.send(json.dumps({"text": text, "final": False}))
                        print(f"[STT] Partial: '{text}'")
                except Exception as e:
                    print(f"[STT] Partial error: {e}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[WS] ✗ Client disconnected: {client_ip}")
    except Exception as e:
        print(f"[WS] ✗ Error: {e}")

print("✓ STT Server code loaded!")
"""

# ═════════════════════════════════════════════════════════════
# CELL 6: Start ngrok tunnel
# ═════════════════════════════════════════════════════════════
"""
from pyngrok import ngrok, conf
import nest_asyncio

# Cho phép nested event loop trong Colab
nest_asyncio.apply()

# Authenticate ngrok (optional cho free tier, bỏ qua nếu không có token)
if NGROK_TOKEN:
    ngrok.set_auth_token(NGROK_TOKEN)

# Tạo TCP tunnel cho WebSocket
tunnel = ngrok.connect(STT_WS_PORT, "tcp")
public_url = tunnel.public_url

# Convert tcp://X.tcp.ngrok.io:PORT → wss://X.tcp.ngrok.io:PORT
if public_url.startswith("tcp://"):
    ws_url = public_url.replace("tcp://", "wss://")
else:
    ws_url = f"wss://{public_url.split('//')[1]}"

print("\\n" + "="*60)
print("🚀 NGROK TUNNEL ACTIVE")
print("="*60)
print(f"Public WebSocket URL: {ws_url}")
print("="*60)
print("\\n📋 Copy URL này vào file ui-ux/.env:")
print(f"\\n   VITE_STT_WS_URL={ws_url}")
print("\\n" + "="*60)
"""

# ═════════════════════════════════════════════════════════════
# CELL 7: Start WebSocket Server (blocking — chạy cuối cùng)
# ═════════════════════════════════════════════════════════════
"""
async def main():
    print(f"\\n[STT-WS] Engine: WHISPER")
    print(f"[STT-WS] Model: {WHISPER_MODEL}")
    print(f"[STT-WS] Listening on ws://0.0.0.0:{STT_WS_PORT}")
    print(f"[STT-WS] Public URL: {ws_url}")
    print(f"\\n✓ Server ready! Waiting for connections...\\n")
    
    async with websockets.serve(handle, "0.0.0.0", STT_WS_PORT, 
                                 ping_interval=60, ping_timeout=120):
        await asyncio.Future()  # Run forever

# Chạy server (blocking)
try:
    await main()
except KeyboardInterrupt:
    print("\\n[STT-WS] Server stopped by user")
"""

# ═════════════════════════════════════════════════════════════
# CELL 8 (Optional): Keep-alive để tránh Colab timeout
# ═════════════════════════════════════════════════════════════
"""
# Chạy cell này trong tab riêng nếu muốn keep-alive
# Colab timeout sau ~90 phút không tương tác

from IPython.display import display, Javascript

display(Javascript('''
  function KeepAlive() {
    console.log("Keep-alive ping");
    setTimeout(KeepAlive, 60000); // 1 phút
  }
  KeepAlive();
'''))

print("✓ Keep-alive active (ping mỗi 60s)")
"""
