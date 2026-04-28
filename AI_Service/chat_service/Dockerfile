# Sử dụng Python bản nhẹ
FROM python:3.10-slim

WORKDIR /app

# Cài đặt thư viện (Dùng file requirements của chat_service)
COPY chat_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ nội dung từ AI_Service vào /app
COPY . .

# Đặt PYTHONPATH để Python nhận diện thư mục gốc /app là nơi chứa module 'config'
ENV PYTHONPATH=/app

# Lệnh chạy ứng dụng (Trỏ vào file worker bên trong chat_service)
CMD ["python", "chat_service/worker.py"]