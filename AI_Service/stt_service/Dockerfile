FROM python:3.10-slim
WORKDIR /app

# System deps cho scipy/torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libsndfile1 && rm -rf /var/lib/apt/lists/*

COPY stt_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download Silero VAD model
RUN python -c "import torch; torch.hub.load('snakers4/silero-vad', 'silero_vad', trust_repo=True)"

COPY . .
ENV PYTHONPATH=/app

EXPOSE 8003
CMD ["python", "stt_service/stt_ws_server.py"]
