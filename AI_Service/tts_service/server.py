import os
import json
import torch
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts

# ==========================================
# 1. CẤU HÌNH MÔ HÌNH
# ==========================================
MODEL_DIR = "model/"
latents_file = f"{MODEL_DIR}begai_lop_4_latents.pth"
device = "cuda:0" if torch.cuda.is_available() else "cpu"

config = XttsConfig()
config.load_json(f"{MODEL_DIR}config.json")
XTTS_MODEL = Xtts.init_from_config(config)
XTTS_MODEL.load_checkpoint(
    config,
    checkpoint_path=f"{MODEL_DIR}model.pth",
    vocab_path=f"{MODEL_DIR}vocab.json",
    use_deepspeed=False
)
XTTS_MODEL.to(device)

latents = torch.load(latents_file, map_location=device, weights_only=True)
gpt_cond_latent = latents["gpt_cond_latent"].to(device)
speaker_embedding = latents["speaker_embedding"].to(device)

def split_text_smartly(text, min_words=5):
    phrases = re.split(r'([.,!?;])', text)
    chunks = []
    current_chunk = ""
    for i in range(0, len(phrases) - 1, 2):
        phrase = phrases[i].strip()
        punct = phrases[i+1].strip()
        if not phrase:
            continue
        current_chunk += phrase + punct + " "
        if len(current_chunk.split()) >= min_words:
            chunks.append(current_chunk.strip())
            current_chunk = ""
    if len(phrases) % 2 != 0 and phrases[-1].strip():
        current_chunk += phrases[-1].strip()
    if current_chunk.strip():
        if chunks:
            chunks[-1] += " " + current_chunk.strip()
        else:
            chunks.append(current_chunk.strip())
    return chunks

# ==========================================
# 2. HTTP SERVER STREAMING
# ==========================================
class StreamingTTSHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_json = json.loads(post_data.decode('utf-8'))
            input_text = request_json.get("text", "")
            
            self.send_response(200)
            self.send_header('Content-type', 'audio/wav')
            self.send_header('Transfer-Encoding', 'chunked')
            self.end_headers()

            chunks = split_text_smartly(input_text)
            print(f"🚀 Bắt đầu Stream {len(chunks)} chunks...")

            with torch.inference_mode():
                for i, text_chunk in enumerate(chunks):
                    outputs = XTTS_MODEL.inference(
                        text=text_chunk,
                        language="vi",
                        gpt_cond_latent=gpt_cond_latent,
                        speaker_embedding=speaker_embedding,
                        repetition_penalty=2.5,
                        temperature=0.7,
                        speed=0.85
                    )

                    # Chuyển đổi Array sang Bytes thô (PCM 16bit)
                    audio_data = (outputs["wav"] * 32767).astype('int16').tobytes()
                    
                    # Gửi chunk theo định dạng HTTP Chunked
                    chunk_size = hex(len(audio_data))[2:].encode('utf-8')
                    self.wfile.write(chunk_size + b'\r\n')
                    self.wfile.write(audio_data + b'\r\n')
                    self.wfile.flush()
                    print(f" ✅ Đã gửi chunk {i+1}")

            # Gửi chunk cuối để kết thúc stream
            self.wfile.write(b'0\r\n\r\n')
            
        except Exception as e:
            print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    port = 8000
    print(f"🚀 Server đang chạy tại http://localhost:{port}")
    HTTPServer(('', port), StreamingTTSHandler).serve_forever()