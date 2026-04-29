#!/bin/bash
# Khởi động toàn bộ SmartVoice BHXH
# Yêu cầu: conda env "AI_Service" đã cài sẵn thư viện

set -e
CONDA_BASE=$(conda info --base 2>/dev/null || echo "$HOME/miniconda3")
source "$CONDA_BASE/etc/profile.d/conda.sh"
conda activate AI_Service

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "==> [1/5] Khởi động hạ tầng (PostgreSQL + Redis + Qdrant)..."
docker compose up -d db redis qdrant
sleep 3

echo "==> [2/5] Khởi động Backend Node.js (port 3000)..."
npm install --silent
nohup node src/app.js > /tmp/backend.log 2>&1 &
echo "    PID backend: $!"

echo "==> [3/5] Khởi động AI Chat Worker..."
nohup python3 AI_Service/chat_service/worker.py > /tmp/ai_worker.log 2>&1 &
echo "    PID ai_worker: $!"

echo "==> [4/5] Khởi động STT WebSocket Server (port 8003)..."
nohup python3 AI_Service/stt_service/stt_ws_server.py > /tmp/stt.log 2>&1 &
echo "    PID stt: $!"

echo "==> [5/5] Khởi động Frontend React (port 5173)..."
cd ui-ux
npm install --silent
nohup npm run dev > /tmp/frontend.log 2>&1 &
echo "    PID frontend: $!"
cd "$PROJECT_DIR"

echo ""
echo "✅ Tất cả service đã khởi động!"
echo "   Frontend : http://localhost:5173"
echo "   Backend  : http://localhost:3000"
echo "   STT WS   : ws://localhost:8003"
echo ""
echo "📋 Xem log:"
echo "   tail -f /tmp/backend.log"
echo "   tail -f /tmp/ai_worker.log"
echo "   tail -f /tmp/stt.log"
echo "   tail -f /tmp/frontend.log"
echo ""
echo "🛑 Để dừng tất cả: bash stop.sh"
