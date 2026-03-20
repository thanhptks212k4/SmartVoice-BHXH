# Voice AI Client — Realtime STT Pipeline (v7)

Hệ thống nhận diện giọng nói (Speech-to-Text) thời gian thực, được thiết kế và tối ưu hoạt động trên **Raspberry Pi 5**. Hệ thống sử dụng kiến trúc Multi-thread Producer-Consumer để đảm bảo độ trễ thấp, không bị lỡ giọng nói và chặn cắt câu sai (premature sentence cutting).

## Tính năng chính

1. **Persistent MicStream**: Mở stream microphone 48kHz một lần duy nhất, tránh overhead khởi tạo lại mỗi khi capture.
2. **Xử lý âm thanh 3 lớp**:
   - **Highpass Filter**: Scipy Butterworth 80Hz cắt nhiễu điện/gió.
   - **RNNoise**: Khử ồn đa lớp từ thư viện C native (`librnnoise.so`), xử lý thẳng ở 48kHz không cần resample.
   - **VAD 2 lớp**: Kết hợp Silero VAD (Deep Learning) và Energy Threshold (so sánh RMSE) để bắt giọng nói chính xác. Dominance voting chống nhiễu vụn.
3. **Producer-Consumer 2 Thread**:
   - `mic_worker` thu âm, cắt segment -> đẩy vào `audio_queue`.
   - `stt_worker` lấy segment đọc Google STT -> đẩy vào `text_queue`.
4. **Endpoint Detection Thông Minh (v7)**:
   - Cơ chế chặn cắt câu dựa trên 4 guards: `stt_busy`, `audio_q_empty`, `mic_recording`, text cooldown.
   - Dynamic Silence Thresholds: Tự động scale thời gian chờ ghép câu dựa theo độ dài của vế trước (2 từ chỉ chờ 1.2s, 20 từ chờ tới 3s). Có text extension merge chống gộp lặp.
   - Lọc Filler Words (ờ, à, ừm...).

## Yêu cầu Hệ thống (Requirements)

### 1. System Libraries (Cấp Hệ điều hành)
Bắt buộc cài đặt trên Raspberry Pi (hoặc Ubuntu/Debian) để lấy được audio từ soundcard và biên dịch RNNoise.
```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python3-pyaudio libasound-dev
sudo apt install autoconf automake libtool pkg-config build-essential
```

### 2. Biên dịch thư viện RNNoise từ mã nguồn
Để hệ thống khử ồn chạy nhanh và tiêu thụ ít CPU nhất trên Raspberry Pi, bạn cần clone và build RNNoise từ C source.

Thực hiện các lệnh sau:
```bash
git clone https://github.com/xiph/rnnoise.git
cd rnnoise
./autogen.sh
./configure

# NẾU BẠN CHẠY TRÊN RASPBERRY PI 4 / PI 5, HÃY BUILD TỐI ƯU BẰNG LỆNH NÀY:
CFLAGS="-O3 -march=native" ./configure

# (Dùng make -j4 để dùng 4 nhân CPU build cho nhanh)
make -j4

# Cài đặt thư viện vào hệ thống
sudo make install
sudo ldconfig
```

> **Lưu ý**: Sau khi build xong, file thư viện `.so` thường nằm ở thư mục `.libs/librnnoise.so`. Hãy đảm bảo cấu trúc thư mục của project chứa file này tại `client/rnnoise/.libs/librnnoise.so` để `STT.py` có thể load được qua ctypes.

### 3. Python Dependencies

conda 3.10
Cài đặt qua pip các thư viện liệt kê trong `requiment.txt`:
```bash
pip install -r requiment.txt
```
*Chi tiết `requiment.txt`:*
- `numpy==1.26.4`: Xử lý mảng âm thanh, slicing.
- `sounddevice==0.4.6`: Giao tiếp cực nhanh với PortAudio lấy tín hiệu mic.
- `SpeechRecognition==3.10.1`: Client gọi Google Web Speech API.
- `torch==2.2.1`: Chạy mô hình Silero VAD.
- `scipy==1.12.0`: Xây dựng Highpass filter.

### 4. File cục bộ (Local Files)
Đảm bảo bạn có file thư viện C động của RNNoise trong đường dẫn sau:
`client/rnnoise/.libs/librnnoise.so`

## Cách sử dụng

Chạy file chính yếu:
```bash
python client.py
```

Khi chạy, hệ thống sẽ:
1. Load model RNNoise, Silero qua log console.
2. Khởi tạo mic chuẩn bị.
3. Báo "Google Speech Recognition Sẵn sàng!"
4. Lắng nghe và in text ra stream. Khi một câu thỏa điều kiện cuối cùng (Endpoint Detected), câu hoàn chỉnh sẽ in ở định dạng:
   `>> Cau hoan chinh [LÝ_DO_CẮT]: ...`

*(Bấm `Ctrl+C` để thoát an toàn đóng luồng).*

## Phân cấp Thư mục
```text
client/
├── client.py               # Lõi điều phối chính, STT Worker, EndpointDetector.
├── STT.py                  # Module Audio Capture (Filters, RNNoise block, VAD).
├── pipeline_description.txt# Giải thích luồng hoạt động chi tiết (Flow graph).
├── requiment.txt           # Danh sách các thư viện Python.
└── rnnoise/                # Folder chứa thư viện C RNNoise (.so).
```
