# ⚡ TEST NHANH 5 PHÚT - RAG EVALUATION

## 🎯 Mục Tiêu

Test hệ thống RAG với **2 metrics chính**:
1. **Hit Rate @ 5** + **MRR**: Retrieval quality
2. **Faithfulness** + **Answer Relevance**: LLM quality (RAGAS)

---

## 🚀 3 Bước Nhanh

### **Bước 1: Run All Tests (1 command)**

```bash
cd AI_Service/evaluation
chmod +x run_all_tests.sh
./run_all_tests.sh
```

**Output mong đợi:**
```
╔══════════════════════════════════════════════════════╗
║     RAG EVALUATION - FULL TEST SUITE                ║
╚══════════════════════════════════════════════════════╝

[1/4] Checking dependencies...
✅ Dependencies OK

[2/4] Checking services...
✅ Qdrant running
✅ Redis running

[3/4] Running Retrieval Evaluation...
...
✅ Retrieval evaluation completed

[4/4] Running RAGAS Evaluation...
...
✅ RAGAS evaluation completed

╔══════════════════════════════════════════════════════╗
║              EVALUATION COMPLETED                    ║
╚══════════════════════════════════════════════════════╝
```

---

### **Bước 2: Xem Kết Quả**

```bash
# Xem metrics tổng quan
cat results_ragas.json | jq '.metrics'
```

**Output mẫu:**
```json
{
  "hit_rate_at_5": 0.9333,
  "mrr": 0.8667,
  "avg_faithfulness": 0.8523,
  "avg_answer_relevance": 0.7845,
  "avg_context_precision": 0.7200,
  "avg_context_recall": 0.7600,
  "total_queries": 15
}
```

---

### **Bước 3: Đưa Vào Báo Cáo**

**Bảng Kết Quả:**

| Metric | Giá Trị | Đánh Giá |
|--------|---------|----------|
| **Hit Rate @ 5** | 93.33% | ✅ Xuất sắc |
| **MRR** | 0.87 | ✅ Xuất sắc |
| **Faithfulness** | 0.85 | ✅ Ít hallucination |
| **Answer Relevance** | 0.78 | ✅ Liên quan tốt |

**Kết luận cho luận văn:**
> Hệ thống được đánh giá trên 15 test cases chuyên biệt về BHXH. **Hit Rate@5 đạt 93.33%** chứng tỏ khả năng tìm kiếm chính xác. **Faithfulness 0.85** giảm thiểu hallucination khi tư vấn pháp luật.

---

## 📊 Hiểu Kết Quả

### **Hit Rate @ 5 = 93.33%**
- ✅ 14/15 câu hỏi tìm được chunk đúng trong top-5
- ❌ 1 câu hỏi miss (cần cải thiện)

### **MRR = 0.87**
- Chunk đúng thường ở vị trí #1-2
- MRR càng cao → Retrieval càng chính xác

### **Faithfulness = 0.85**
- 85% claims được supported bởi contexts
- 15% có thể là paraphrase/inference
- **< 0.6**: Nhiều hallucination ❌
- **0.6-0.8**: Chấp nhận được ⚠️
- **> 0.8**: Xuất sắc ✅

### **Answer Relevance = 0.78**
- Câu trả lời liên quan 78% với câu hỏi
- Đo bằng cosine similarity
- **> 0.75**: Tốt ✅

---

## 🔧 Troubleshooting

### **Lỗi: Services not running**

```bash
# Start Qdrant
docker start qdrant

# Start Redis
docker start redis_ai_service

# Check
curl http://localhost:6335/health
redis-cli ping
```

---

### **Lỗi: No data in Qdrant**

```bash
# Check collection size
python -c "from qdrant_client import QdrantClient; c = QdrantClient(host='localhost', port=6335); print(f'Size: {c.count(\"thanhpt\").count}')"

# Nếu = 0, cần upload file trước
# Xem: client/uploadFile.py
```

---

### **Faithfulness thấp (<0.6)**

**Fix trong `ai_engine.py`:**
```python
system_instruction = """
Bạn là chuyên gia BHXH.

QUY TẮC:
1. CHỈ trả lời dựa trên THÔNG TIN HỖ TRỢ
2. KHÔNG bịa đặt thông tin
3. Nếu không chắc: "Thông tin không đủ"
"""
```

---

## 📁 Files Tạo Ra

```
AI_Service/evaluation/
├── results_retrieval.json       # Hit Rate, MRR
├── results_ragas.json           # Full RAGAS metrics
├── ground_truth_bhxh.json       # Test set (15 câu)
└── sample_test_set.json         # Test set mẫu (5 câu)
```

---

## 🎓 Cho Báo Cáo

**Screenshot cần chụp:**
1. Terminal output (RAGAS results table)
2. `results_ragas.json` metrics
3. Bảng so sánh (SmartVoice vs Baseline)

**Viết báo cáo:**
- Section 4.3: Đánh giá module RAG
- Bảng kết quả + Biểu đồ
- Phân tích: Tại sao Hit Rate cao? Faithfulness ý nghĩa gì?

---

## ✅ Checklist

- [ ] Chạy `./run_all_tests.sh`
- [ ] Hit Rate >= 90% ✅
- [ ] Faithfulness >= 0.8 ✅
- [ ] Screenshot kết quả
- [ ] Tạo bảng cho báo cáo
- [ ] Viết phần đánh giá

---

**Done! 🎉** 

Chi tiết xem: `HUONG_DAN_TEST_SYSTEM.md`
