#!/bin/bash

# ============================================================
# Script Chạy Tất Cả Tests - RAG Evaluation
# ============================================================

echo "╔══════════════════════════════════════════════════════╗"
echo "║     RAG EVALUATION - FULL TEST SUITE                ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ============================================================
# Step 1: Check Dependencies
# ============================================================
echo -e "${YELLOW}[1/4] Checking dependencies...${NC}"

if ! python -c "import numpy, sklearn, sentence_transformers, qdrant_client" 2>/dev/null; then
    echo -e "${RED}❌ Missing dependencies. Installing...${NC}"
    pip install -r requirements.txt
fi

echo -e "${GREEN}✅ Dependencies OK${NC}"
echo ""

# ============================================================
# Step 2: Check Services
# ============================================================
echo -e "${YELLOW}[2/4] Checking services...${NC}"

# Check Qdrant
if curl -s http://localhost:6335/health | grep -q "ok"; then
    echo -e "${GREEN}✅ Qdrant running${NC}"
else
    echo -e "${RED}❌ Qdrant not running. Please start Qdrant first.${NC}"
    exit 1
fi

# Check Redis
if redis-cli ping | grep -q "PONG"; then
    echo -e "${GREEN}✅ Redis running${NC}"
else
    echo -e "${RED}❌ Redis not running. Please start Redis first.${NC}"
    exit 1
fi

echo ""

# ============================================================
# Step 3: Run Retrieval Evaluation
# ============================================================
echo -e "${YELLOW}[3/4] Running Retrieval Evaluation...${NC}"
echo "Testing: Hit Rate, MRR"
echo ""

python rag_evaluation.py \
    --test-file ground_truth_bhxh.json \
    --output results_retrieval.json

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Retrieval evaluation completed${NC}"
else
    echo -e "${RED}❌ Retrieval evaluation failed${NC}"
    exit 1
fi

echo ""

# ============================================================
# Step 4: Run RAGAS Evaluation (Full Pipeline)
# ============================================================
echo -e "${YELLOW}[4/4] Running RAGAS Evaluation...${NC}"
echo "Testing: Faithfulness, Answer Relevance, Context Precision/Recall"
echo ""

python ragas_evaluation.py \
    --test-file ground_truth_bhxh.json \
    --output results_ragas.json

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ RAGAS evaluation completed${NC}"
else
    echo -e "${RED}❌ RAGAS evaluation failed${NC}"
    exit 1
fi

echo ""

# ============================================================
# Summary
# ============================================================
echo "╔══════════════════════════════════════════════════════╗"
echo "║              EVALUATION COMPLETED                    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "📊 Results saved:"
echo "  - results_retrieval.json (Hit Rate, MRR)"
echo "  - results_ragas.json (Full RAGAS metrics)"
echo ""
echo "📈 View results:"
echo "  cat results_ragas.json | jq '.metrics'"
echo ""
echo -e "${GREEN}✅ All tests passed!${NC}"
