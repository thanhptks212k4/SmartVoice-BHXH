#!/bin/bash

# Script để dừng tất cả services của SmartVoice-BHXH
# Sử dụng: bash stop-all.sh

echo "🛑 Stopping SmartVoice-BHXH Services..."
echo ""

# Màu sắc
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# Stop Frontend
if [ -f logs/frontend.pid ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    echo -e "Stopping Frontend (PID: $FRONTEND_PID)..."
    kill $FRONTEND_PID 2>/dev/null || echo "Frontend already stopped"
    rm logs/frontend.pid
fi

# Stop Chat Service
if [ -f logs/chat.pid ]; then
    CHAT_PID=$(cat logs/chat.pid)
    echo -e "Stopping Chat Service (PID: $CHAT_PID)..."
    kill $CHAT_PID 2>/dev/null || echo "Chat Service already stopped"
    rm logs/chat.pid
fi

# Stop STT Service
if [ -f logs/stt.pid ]; then
    STT_PID=$(cat logs/stt.pid)
    echo -e "Stopping STT Service (PID: $STT_PID)..."
    kill $STT_PID 2>/dev/null || echo "STT Service already stopped"
    rm logs/stt.pid
fi

# Stop Backend
if [ -f logs/backend.pid ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    echo -e "Stopping Backend (PID: $BACKEND_PID)..."
    kill $BACKEND_PID 2>/dev/null || echo "Backend already stopped"
    rm logs/backend.pid
fi

# Stop Docker services
echo -e "Stopping Docker services..."
docker compose down

echo ""
echo -e "${GREEN}✓ All services stopped${NC}"
