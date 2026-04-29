#!/bin/bash
# Dừng toàn bộ SmartVoice BHXH

echo "==> Dừng các process..."
pkill -f "node src/app.js"        2>/dev/null && echo "    Backend stopped" || true
pkill -f "chat_service/worker.py" 2>/dev/null && echo "    AI Worker stopped" || true
pkill -f "stt_ws_server.py"       2>/dev/null && echo "    STT stopped" || true
pkill -f "vite"                   2>/dev/null && echo "    Frontend stopped" || true

echo "==> Dừng Docker (hạ tầng)..."
docker compose stop db redis qdrant

echo "✅ Đã dừng tất cả."
