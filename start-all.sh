#!/bin/bash

# Script để chạy tất cả services của SmartVoice-BHXH
# Sử dụng: bash start-all.sh

set -e

echo "🚀 Starting SmartVoice-BHXH Services..."
echo ""

# Màu sắc cho output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Start Docker services (PostgreSQL, Redis, Qdrant)
echo -e "${BLUE}[1/5]${NC} Starting Docker services (PostgreSQL, Redis, Qdrant)..."
docker compose up -d
echo -e "${GREEN}✓${NC} Docker services started"
echo ""

# Đợi Docker services khởi động
sleep 5

# 2. Start Node.js Backend
echo -e "${BLUE}[2/5]${NC} Starting Node.js Backend (port 3000)..."
cd AI_Service
npm start > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../logs/backend.pid
cd ..
echo -e "${GREEN}✓${NC} Backend started (PID: $BACKEND_PID)"
echo ""

# 3. Start STT Service
echo -e "${BLUE}[3/5]${NC} Starting STT Service (port 8003)..."
cd AI_Service/stt_service
python3 worker_stt_ws_server.py > ../../logs/stt.log 2>&1 &
STT_PID=$!
echo $STT_PID > ../../logs/stt.pid
cd ../..
echo -e "${GREEN}✓${NC} STT Service started (PID: $STT_PID)"
echo ""

# 4. Start Chat Service (RAG + LLM)
echo -e "${BLUE}[4/5]${NC} Starting Chat Service (RAG + LLM)..."
cd AI_Service/chat_service
python3 worker.py > ../../logs/chat.log 2>&1 &
CHAT_PID=$!
echo $CHAT_PID > ../../logs/chat.pid
cd ../..
echo -e "${GREEN}✓${NC} Chat Service started (PID: $CHAT_PID)"
echo ""

# 5. Start Frontend (Vite)
echo -e "${BLUE}[5/5]${NC} Starting Frontend (port 5173)..."
cd ui-ux
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../logs/frontend.pid
cd ..
echo -e "${GREEN}✓${NC} Frontend started (PID: $FRONTEND_PID)"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All services started successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📋 Service URLs:"
echo "   • Frontend:  http://localhost:5173"
echo "   • Backend:   http://localhost:3000"
echo "   • STT WS:    ws://localhost:8003"
echo ""
echo "📝 Logs location: ./logs/"
echo ""
echo "🛑 To stop all services, run: bash stop-all.sh"
echo ""
echo -e "${YELLOW}Press Ctrl+C to view logs in real-time...${NC}"
echo ""

# Theo dõi logs
tail -f logs/*.log
