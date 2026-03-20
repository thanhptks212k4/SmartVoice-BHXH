# 1. Dùng bản CUDA 11.8 hoặc 12.1 phù hợp với RTX 2050
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# 2. Cài đặt Python và các thư viện hệ thống cho âm thanh (libsndfile1 rất quan trọng)
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    libsndfile1 \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# 3. Tạo thư mục làm việc
WORKDIR /app

# 4. Copy file requirements trước để tận dụng cache của Docker
COPY requirements.txt .

# 5. Cài đặt thư viện (Ưu tiên PyTorch bản CUDA)
RUN pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
RUN pip3 install --no-cache-dir -r requirements.txt


# 6. Copy toàn bộ code và MODEL vào container
COPY . .

# 7. Port mặc định của FastAPI
EXPOSE 8080

# 8. Chạy server
CMD ["python3","-u" ,"wordker.py"]