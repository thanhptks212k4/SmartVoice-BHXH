# Sử dụng Python bản nhẹ (slim)
FROM python:3.10-slim

# Đặt thư mục làm việc trong container
WORKDIR /app

# Copy file requirement vào trước để tận dụng cache của Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào container
COPY . .

# Lệnh chạy ứng dụng
CMD ["python", "worker_embetddsing.py"]