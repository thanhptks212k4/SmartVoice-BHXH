# 🔊 TTS Service - XTTS v2 Vietnamese

> Text-to-Speech service với giọng nói tiếng Việt tự nhiên

## 🎯 Giới thiệu

Service này sử dụng **XTTS v2** (Coqui TTS) đã được fine-tune cho tiếng Việt để tạo giọng nói tự nhiên từ văn bản. Hỗ trợ nhiều giọng nói và streaming audio real-time.

### ✨ Tính năng

- 🇻🇳 **Giọng nói tiếng Việt tự nhiên** - Fine-tuned cho tiếng Việt
- 🎭 **Đa giọng nói** - Hỗ trợ nhiều voice profiles (nữ Hà Nội, nam miền Nam...)
- ⚡ **Streaming** - Phát audio ngay khi sinh chunk đầu tiên
- 🎵 **Chất lượng cao** - 24kHz, 16-bit PCM
- 📝 **Smart chunking** - Tách câu thông minh để giọng tự nhiên

---

## 🚀 Cài đặt nhanh

### 1. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 2. Download model

```bash
python setup_model_drive.py
```

### 3. Cấu hình

Tạo file `.env`:
```bash
EXTERNAL_HOST=localhost
EXTERNAL_PORT=8123
QUEUE_MAXSIZE=50
STREAM_GET_TIMEOUT=30
```

### 4. Chạy service

```bash
python wordker.py
```

Service sẽ chạy tại `http://localhost:8123`

---

## 📖 Sử dụng

### API Endpoint

**GET** `/stream-voice/{task_id}`

Trả về audio stream dạng WAV (chunked transfer encoding)

### Python Example

```python
from tts_service import generate_tts

text = "Xin chào, tôi là trợ lý ảo tư vấn bảo hiểm xã hội."
voice = "nuhanoi"  # Giọng nữ Hà Nội

for audio_chunk in generate_tts(text, voice):
    # audio_chunk: bytes (PCM 16-bit)
    # Xử lý hoặc stream chunk này
    pass
```

### Voice Profiles

| Voice ID | Mô tả | Giới tính |
|----------|-------|-----------|
| `nuhanoi` | Giọng nữ Hà Nội | Nữ |
| `giongnuhanoi6s` | Giọng nữ Hà Nội 6s | Nữ |
| `vi_woman` | Giọng nữ chuẩn | Nữ |
| `vi_man` | Giọng nam chuẩn | Nam |

---

## 🛠️ Cấu trúc thư mục

```
tts_service/
├── model/                    # XTTS model files
│   ├── config.json
│   ├── model.pth
│   ├── vocab.json
│   └── *.wav                # Voice samples
├── checkpoints/             # Original XTTS checkpoints
├── tts_service.py          # Core TTS engine
├── wordker.py              # FastAPI worker
├── config.py               # Configuration
└── requirements.txt
```

---

## ⚙️ Cấu hình nâng cao

### Inference Parameters

Chỉnh sửa trong `tts_service.py`:

```python
VOICE_PROFILES = {
    "nuhanoi": {
        "audio": "model/giongnuhanoi6s.wav",
        "inference": {
            "temperature": 0.7,      # Creativity (0.1-1.0)
            "top_p": 0.80,           # Nucleus sampling
            "top_k": 8,              # Top-k sampling
            "speed": 1.0,            # Speech speed
            "repetition_penalty": 20.0,
            "num_beams": 1,
            "length_penalty": 1.0,
        }
    }
}
```

### Performance Tuning

**CPU Mode:**
```python
device = "cpu"
# Latency: ~2-3s per sentence
```

**GPU Mode:**
```python
device = "cuda:0"
# Latency: ~200-400ms per sentence
# Yêu cầu: NVIDIA GPU với 4GB+ VRAM
```

---

## 🎓 Fine-tuning (Nâng cao)

Nếu bạn muốn fine-tune model cho giọng nói riêng:

### 1. Chuẩn bị dữ liệu

```
datasets/
├── wavs/
│   ├── audio001.wav
│   ├── audio002.wav
│   └── ...
├── metadata_train.csv
└── metadata_eval.csv
```

Format CSV:
```csv
audio_file|text|speaker_name
wavs/audio001.wav|Xin chào các bạn|@Speaker1
wavs/audio002.wav|Hôm nay trời đẹp|@Speaker1
```

### 2. Download pretrained model

```bash
python download_checkpoint.py --output_path checkpoints/
```

### 3. Extend vocabulary

```bash
python extend_vocab_config.py \
  --output_path=checkpoints/ \
  --metadata_path=datasets/metadata_train.csv \
  --language=vi \
  --extended_vocab_size=2000
```

### 4. Fine-tune GPT

```bash
CUDA_VISIBLE_DEVICES=0 python train_gpt_xtts.py \
  --output_path=checkpoints/ \
  --metadatas=datasets/metadata_train.csv,datasets/metadata_eval.csv,vi \
  --num_epochs=5 \
  --batch_size=8 \
  --lr=5e-6
```

**Lưu ý**: Cần ~20 giờ audio data và GPU mạnh (RTX 3090+)

---

## 🐛 Troubleshooting

### Model không load được

```bash
# Kiểm tra file model
ls -lh model/
# Cần có: config.json, model.pth, vocab.json

# Download lại nếu thiếu
python setup_model_drive.py
```

### Audio bị "bụp" đầu

→ Đã fix bằng cách gom chunk đầu tiên trong `wordker.py`

### Giọng nói không tự nhiên

→ Thử điều chỉnh `temperature` (0.5-0.9) và `repetition_penalty` (10-30)

### Out of memory (GPU)

```python
# Giảm batch size hoặc chuyển sang CPU
device = "cpu"
```

---

## 📚 Tài liệu tham khảo

- [Coqui TTS](https://github.com/coqui-ai/TTS) - Original XTTS implementation
- [Vietnamese TTS Model](https://huggingface.co/anhnh2002/vnTTS) - Pre-trained model
- [XTTS Paper](https://arxiv.org/abs/2406.04904) - Research paper

---

## 📝 License

Model XTTS v2 được phát hành dưới [Coqui Public Model License](https://coqui.ai/cpml).

---

<div align="center">

**🎤 Tạo giọng nói tiếng Việt tự nhiên với XTTS v2**

</div>
