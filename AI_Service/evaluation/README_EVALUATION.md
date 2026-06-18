# 📊 RAG Evaluation Framework - Hướng Dẫn Chi Tiết

## 🎯 Mục Đích

Framework này giúp bạn **đo lường và chứng minh** module RAG đang hoạt động tốt thông qua các metrics khoa học.

---

## 🔑 Các Metrics Quan Trọng

### **1. Hit Rate @ K** (Tỷ lệ tìm đúng)

**Định nghĩa**: Trong top-K chunks được retrieve, có bao nhiêu % queries tìm được ít nhất 1 chunk đúng?

**Công thức**:
```
Hit Rate @ K = (Số queries tìm được chunk đúng trong top-K) / (Tổng số queries)
```

**Ý nghĩa**:
- **Hit Rate @ 1 = 80%**: 80% câu hỏi, chunk đúng nằm ở vị trí #1
- **Hit Rate @ 5 = 95%**: 95% câu hỏi, chunk đúng nằm trong top-5

**Benchmark tốt**: 
- Hit@1 > 70%
- Hit@5 > 90%

---

### **2. MRR (Mean Reciprocal Rank)**

**Định nghĩa**: Trung bình vị trí của chunk đúng đầu tiên (có trọng số giảm dần).

**Công thức**:
```
RR = 1 / rank_of_first_correct_chunk
MRR = Average(RR across all queries)
```

**Ví dụ**:
- Query 1: Chunk đúng ở vị trí #1 → RR = 1/1 = 1.0
- Query 2: Chunk đúng ở vị trí #3 → RR = 1/3 = 0.333
- Query 3: Không tìm thấy → RR = 0
- **MRR = (1.0 + 0.333 + 0) / 3 = 0.444**

**Ý nghĩa**: MRR cao = Chunk đúng thường nằm ở vị trí cao.

**Benchmark tốt**: MRR > 0.7

---

### **3. NDCG @ K (Normalized Discounted Cumulative Gain)**

**Định nghĩa**: Đo lường **chất lượng ranking** với discount theo position.

**Công thức**:
```
DCG@K = Σ (relevance_i / log2(i + 1))  for i = 1 to K
NDCG@K = DCG@K / Ideal_DCG@K
```

**Ý nghĩa**:
- NDCG = 1.0: Ranking hoàn hảo (tất cả chunk đúng lên top)
- NDCG = 0.5: Ranking trung bình
- NDCG = 0.0: Ranking tệ (không có chunk đúng)

**Benchmark tốt**: NDCG@5 > 0.8

---

### **4. Precision @ K**

**Định nghĩa**: Tỷ lệ chunks đúng trong top-K.

**Công thức**:
```
Precision@K = (Số chunks relevant trong top-K) / K
```

**Ví dụ**: Top-5 có 3 chunks đúng → Precision@5 = 3/5 = 0.6

**Benchmark tốt**: Precision@5 > 0.6

---

### **5. Average Cosine Similarity**

**Định nghĩa**: Trung bình độ tương đồng vector giữa query và retrieved chunks.

**Range**: [0, 1]
- 0.9 - 1.0: Rất tương đồng
- 0.7 - 0.9: Tương đồng
- < 0.7: Kém tương đồng

**Benchmark tốt**: Avg Similarity > 0.75

---

## 📦 Cài Đặt

```bash
cd AI_Service/evaluation
pip install numpy scikit-learn sentence-transformers qdrant-client
```

---

## 🚀 Cách Sử Dụng

### **Bước 1: Tạo Test Set Mẫu**

```bash
python rag_evaluation.py --generate-sample
```

Output: `sample_test_set.json`

```json
[
  {
    "query": "Bảo hiểm xã hội là gì?",
    "relevant_chunks": null,
    "relevant_dieu": "Điều 1",
    "ground_truth_answer": "Bảo hiểm xã hội là...",
    "category": "định nghĩa"
  },
  ...
]
```

---

### **Bước 2: Chỉnh Sửa Test Set**

Mở `sample_test_set.json` và **bổ sung ground truth** từ chuyên gia:

**Cách 1: Dùng `relevant_dieu`** (khuyến nghị cho BHXH):
```json
{
  "query": "Mức đóng BHXH là bao nhiêu?",
  "relevant_dieu": "Điều 85",  // ← Chỉ cần điền Điều liên quan
  "category": "mức đóng"
}
```

**Cách 2: Dùng `relevant_chunks`** (nếu biết chunk ID):
```json
{
  "query": "Điều kiện hưởng lương hưu?",
  "relevant_chunks": ["abc-123-def", "xyz-456-ghi"],  // ← List chunk IDs
  "relevant_dieu": "Điều 54",
  "category": "hưu trí"
}
```

---

### **Bước 3: Chạy Evaluation**

```bash
# Evaluate với test set tự tạo
python rag_evaluation.py --test-file my_test_set.json --output results.json

# Với group cụ thể
python rag_evaluation.py \
  --test-file my_test_set.json \
  --group-id "028686bd-00d7-4def-a900-5f1aa97e2849" \
  --top-k 5 \
  --output results.json
```

---

### **Bước 4: Đọc Kết Quả**

Terminal output:
```
╔════════════════════════════════════════════════════════╗
║           RAG EVALUATION METRICS                       ║
╠════════════════════════════════════════════════════════╣
║ Total Queries:          50                             ║
║                                                        ║
║ RETRIEVAL METRICS:                                     ║
║   Hit Rate @ 1:         78.00%                         ║
║   Hit Rate @ 3:         92.00%                         ║
║   Hit Rate @ 5:         96.00%                         ║
║   MRR (Mean Reciprocal Rank): 0.8523                   ║
║                                                        ║
║ RANKING QUALITY:                                       ║
║   Precision @ 5:        0.6800                         ║
║   NDCG @ 5:             0.8912                         ║
║                                                        ║
║ SEMANTIC SIMILARITY:                                   ║
║   Avg Cosine Similarity: 0.7845                        ║
╚════════════════════════════════════════════════════════╝
```

File `results.json` chứa:
```json
{
  "metrics": { ... },
  "results": [
    {
      "query": "Bảo hiểm xã hội là gì?",
      "hit": true,
      "reciprocal_rank": 1.0,
      "precision_at_k": 0.8,
      "ndcg_at_k": 0.95,
      "avg_similarity": 0.82,
      "top_chunks": [
        {
          "text": "Bảo hiểm xã hội là hình thức bảo hiểm...",
          "dieu": "Điều 1",
          "score": 0.87
        },
        ...
      ]
    },
    ...
  ]
}
```

---

## 📝 Tạo Test Set Chuyên Nghiệp

### **Template Test Set**

```json
[
  {
    "query": "Mức đóng BHXH bắt buộc là bao nhiêu phần trăm?",
    "relevant_dieu": "Điều 85",
    "ground_truth_answer": "Mức đóng BHXH bắt buộc: Người lao động đóng 8%, người sử dụng lao động đóng 17.5%",
    "category": "mức đóng"
  },
  {
    "query": "Điều kiện hưởng trợ cấp thai sản?",
    "relevant_dieu": "Điều 38",
    "ground_truth_answer": "Người lao động nữ đã đóng BHXH từ đủ 6 tháng trở lên trước khi sinh con hoặc nhận nuôi con",
    "category": "thai sản"
  },
  {
    "query": "Tuổi nghỉ hưu của nam giới là bao nhiêu?",
    "relevant_dieu": "Điều 54",
    "ground_truth_answer": "Nam giới đủ 60 tuổi 3 tháng trở lên (từ năm 2021, tăng dần đến 62 tuổi vào năm 2028)",
    "category": "hưu trí"
  }
]
```

### **Categories Nên Cover**

1. **Định nghĩa**: Khái niệm cơ bản
2. **Mức đóng**: Tỷ lệ %, số tiền
3. **Điều kiện hưởng**: Eligibility criteria
4. **Quyền lợi**: Benefits, trợ cấp
5. **Thủ tục**: Hồ sơ, quy trình
6. **Thời hạn**: Duration, deadline
7. **Ngoại lệ**: Edge cases, special cases

### **Số Lượng Test Cases Khuyến Nghị**

- **Minimum**: 50 queries
- **Good**: 100-200 queries
- **Excellent**: 500+ queries với coverage toàn diện

---

## 🎯 Benchmark Targets

| Metric | Minimum | Good | Excellent |
|--------|---------|------|-----------|
| Hit Rate @ 1 | 60% | 75% | 85% |
| Hit Rate @ 5 | 80% | 90% | 95% |
| MRR | 0.6 | 0.75 | 0.85 |
| NDCG @ 5 | 0.7 | 0.8 | 0.9 |
| Precision @ 5 | 0.5 | 0.65 | 0.8 |
| Avg Similarity | 0.7 | 0.78 | 0.85 |

---

## 🔧 Troubleshooting

### **Nếu Hit Rate thấp (<70%)**

**Nguyên nhân có thể**:
1. ❌ Embedding model không phù hợp với tiếng Việt
2. ❌ Chunking strategy không tốt (chunk quá lớn/nhỏ)
3. ❌ Query và document có vocabulary gap

**Giải pháp**:
- Thử model khác: `vinai/phobert-base`, `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- Điều chỉnh chunk size (hiện tại: 512 chars)
- Thêm query expansion (paraphrase query)

---

### **Nếu MRR thấp nhưng Hit@5 cao**

**Ý nghĩa**: Chunk đúng có trong top-5 nhưng không phải vị trí #1

**Giải pháp**:
- Thêm re-ranking layer (cross-encoder)
- Fine-tune embedding model
- Thêm metadata boost (boost Điều match)

---

### **Nếu Cosine Similarity thấp (<0.7)**

**Ý nghĩa**: Query và chunks không semantic similar

**Giải pháp**:
- Kiểm tra lại preprocessing (lowercase, remove special chars)
- Thử embedding model khác
- Thêm synthetic query generation (data augmentation)

---

## 📊 Báo Cáo cho Đồ Án

### **Cấu Trúc Báo Cáo Evaluation**

```markdown
## 4.3 Đánh Giá Module RAG

### 4.3.1 Phương Pháp Đánh Giá

- **Test Set**: 100 câu hỏi thực tế về BHXH
- **Ground Truth**: Do chuyên gia BHXH annotate
- **Metrics**: Hit Rate, MRR, NDCG, Precision

### 4.3.2 Kết Quả

| Metric | Giá Trị | Benchmark | Đánh Giá |
|--------|---------|-----------|----------|
| Hit Rate @ 1 | 78% | >75% | ✅ Tốt |
| Hit Rate @ 5 | 96% | >90% | ✅ Xuất sắc |
| MRR | 0.85 | >0.75 | ✅ Tốt |
| NDCG @ 5 | 0.89 | >0.8 | ✅ Tốt |

**Kết luận**: Module RAG hoạt động ổn định với Hit@5 đạt 96%.

### 4.3.3 Phân Tích

- **Điểm mạnh**: 
  - Retrieval chính xác cho câu hỏi về điều kiện hưởng (95%)
  - Legal-aware chunking giữ nguyên context Điều/Khoản
  
- **Hạn chế**:
  - Câu hỏi về số liệu cụ thể còn thấp (Hit@1 = 65%)
  - Cần cải thiện với câu hỏi so sánh (A vs B)

### 4.3.4 So Sánh với Baseline

| Hệ thống | Hit@5 | MRR |
|----------|-------|-----|
| **SmartVoice (Legal Chunking)** | **96%** | **0.85** |
| Baseline (Naive Chunking) | 82% | 0.68 |
| Cải thiện | +14% | +25% |
```

---

## 🚀 Advanced: Evaluation Pipeline

### **Script Tự Động**

```bash
#!/bin/bash
# evaluate_pipeline.sh

echo "🚀 Starting RAG Evaluation Pipeline..."

# 1. Test với nhiều top-K values
for k in 1 3 5 10; do
  python rag_evaluation.py \
    --test-file test_set_full.json \
    --top-k $k \
    --output "results_k${k}.json"
done

# 2. Test với nhiều groups
for group in "group_a" "group_b" "base"; do
  python rag_evaluation.py \
    --test-file test_set_full.json \
    --group-id $group \
    --output "results_${group}.json"
done

# 3. Aggregate results
python aggregate_results.py --input "results_*.json" --output "final_report.pdf"

echo "✅ Pipeline completed!"
```

---

## 📚 Tài Liệu Tham Khảo

1. **RAG Evaluation**: [Anthropic - Evaluating RAG](https://www.anthropic.com/index/evaluating-rag)
2. **IR Metrics**: [Manning et al. - Information Retrieval](https://nlp.stanford.edu/IR-book/)
3. **NDCG**: [Wikipedia - Discounted Cumulative Gain](https://en.wikipedia.org/wiki/Discounted_cumulative_gain)

---

## ❓ FAQ

**Q: Cần bao nhiêu test cases?**  
A: Minimum 50, khuyến nghị 100-200 để có statistical significance.

**Q: Ai tạo ground truth?**  
A: Chuyên gia BHXH hoặc người hiểu rõ luật (có thể là giáo viên hướng dẫn).

**Q: Làm sao biết metrics nào quan trọng nhất?**  
A: **Hit@5** và **MRR** là quan trọng nhất cho RAG. NDCG và Precision để đánh giá ranking quality.

**Q: Nếu không có chuyên gia?**  
A: Tự tạo test set từ các câu hỏi thực tế, sau đó manually verify top-5 chunks có đúng không.

---

## 🎓 Kết Luận

Framework này giúp bạn:
1. ✅ **Chứng minh khoa học** RAG hoạt động tốt
2. ✅ **So sánh** với baseline/competitors
3. ✅ **Identify** điểm yếu để cải thiện
4. ✅ **Report** trong đồ án/luận văn

**Good luck with your evaluation!** 🚀
