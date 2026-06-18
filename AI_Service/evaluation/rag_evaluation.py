"""
RAG Evaluation Framework cho SmartVoice BHXH

Metrics:
1. Retrieval Metrics (Đo lường chất lượng tìm kiếm):
   - Hit Rate@K: Có bao nhiêu % câu hỏi tìm được chunk đúng trong top-K
   - MRR (Mean Reciprocal Rank): Vị trí trung bình của chunk đúng
   - NDCG@K: Đo xếp hạng có tính trọng số
   - Precision@K: Độ chính xác trong top-K

2. Semantic Similarity Metrics:
   - Cosine Similarity: Độ tương đồng vector giữa query và retrieved chunks
   - Context Relevance Score: Đo lường mức độ liên quan của context

3. End-to-End Metrics:
   - Answer Relevance: Câu trả lời có liên quan đến câu hỏi không
   - Faithfulness: Câu trả lời có trung thực với context không
   - Answer Correctness: So sánh với ground truth answer

Usage:
    python rag_evaluation.py --test-file test_set.json --output results.json
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
import numpy as np
from sentence_transformers import SentenceTransformer, util
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.config import settings


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class TestCase:
    """Một test case cho RAG evaluation"""
    query: str                          # Câu hỏi
    relevant_chunks: List[str]          # Ground truth: List các chunk IDs đúng
    relevant_dieu: str = None           # Ground truth: Điều liên quan
    ground_truth_answer: str = None     # Ground truth: Câu trả lời mẫu
    category: str = "general"           # Loại câu hỏi


@dataclass
class RetrievalResult:
    """Kết quả retrieval cho 1 query"""
    query: str
    retrieved_chunks: List[Dict]        # Top-K chunks
    scores: List[float]                 # Similarity scores
    hit: bool                           # Có tìm thấy relevant chunk không
    reciprocal_rank: float              # 1/rank của chunk đúng đầu tiên
    precision_at_k: float               # Precision@K
    ndcg_at_k: float                    # NDCG@K
    avg_similarity: float               # Trung bình cosine similarity


@dataclass
class EvaluationMetrics:
    """Tổng hợp metrics cho toàn bộ test set"""
    hit_rate_at_1: float
    hit_rate_at_3: float
    hit_rate_at_5: float
    mrr: float                          # Mean Reciprocal Rank
    avg_precision_at_5: float
    avg_ndcg_at_5: float
    avg_similarity: float
    total_queries: int
    
    def __str__(self):
        return f"""
╔════════════════════════════════════════════════════════╗
║           RAG EVALUATION METRICS                       ║
╠════════════════════════════════════════════════════════╣
║ Total Queries:          {self.total_queries:<30} ║
║                                                        ║
║ RETRIEVAL METRICS:                                     ║
║   Hit Rate @ 1:         {self.hit_rate_at_1:<30.2%} ║
║   Hit Rate @ 3:         {self.hit_rate_at_3:<30.2%} ║
║   Hit Rate @ 5:         {self.hit_rate_at_5:<30.2%} ║
║   MRR (Mean Reciprocal Rank): {self.mrr:<20.4f} ║
║                                                        ║
║ RANKING QUALITY:                                       ║
║   Precision @ 5:        {self.avg_precision_at_5:<30.4f} ║
║   NDCG @ 5:             {self.avg_ndcg_at_5:<30.4f} ║
║                                                        ║
║ SEMANTIC SIMILARITY:                                   ║
║   Avg Cosine Similarity: {self.avg_similarity:<29.4f} ║
╚════════════════════════════════════════════════════════╝
"""


# ============================================================
# RAG EVALUATOR
# ============================================================

class RAGEvaluator:
    def __init__(self, collection_name: str = "thanhpt", top_k: int = 5):
        self.qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST, 
            port=settings.QDRANT_PORT
        )
        self.embed_model = SentenceTransformer(settings.MODEL_QDRANT)
        self.collection_name = collection_name
        self.top_k = top_k
        
    def retrieve(self, query: str, user_id: str = "base", 
                 group_id: str = None) -> Tuple[List[Dict], List[float]]:
        """
        Thực hiện retrieval giống như production
        Returns: (chunks, scores)
        """
        query_vector = self.embed_model.encode(query).tolist()
        
        filter_conditions = []
        if group_id:
            filter_conditions.append(
                FieldCondition(key="groupId", match=MatchValue(value=group_id))
            )
        
        filter_conditions.append(
            Filter(should=[
                FieldCondition(key="userId", match=MatchValue(value="base")),
                FieldCondition(key="userId", match=MatchValue(value=user_id)),
            ])
        )
        
        response = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=Filter(must=filter_conditions) if filter_conditions else None,
            limit=self.top_k,
            with_payload=True,
        )
        
        chunks = []
        scores = []
        for hit in response.points:
            chunks.append({
                "id": hit.id,
                "text": hit.payload.get("text", ""),
                "dieu": hit.payload.get("dieu", ""),
                "fileName": hit.payload.get("fileName", ""),
                "score": hit.score
            })
            scores.append(hit.score)
            
        return chunks, scores
    
    def calculate_hit(self, retrieved_chunks: List[Dict], 
                     relevant_info: Dict, k: int = None) -> bool:
        """
        Kiểm tra xem có chunk nào trong top-K match với ground truth không
        
        Match criteria:
        - Nếu có relevant_chunks (IDs): Check exact ID match
        - Nếu có relevant_dieu: Check Điều match
        - Nếu có cả hai: Match either one
        """
        if k is None:
            k = len(retrieved_chunks)
        
        top_k_chunks = retrieved_chunks[:k]
        
        # Check ID match
        if "relevant_chunks" in relevant_info and relevant_info["relevant_chunks"]:
            retrieved_ids = [c["id"] for c in top_k_chunks]
            if any(rid in relevant_info["relevant_chunks"] for rid in retrieved_ids):
                return True
        
        # Check Điều match
        if "relevant_dieu" in relevant_info and relevant_info["relevant_dieu"]:
            for chunk in top_k_chunks:
                if chunk.get("dieu") == relevant_info["relevant_dieu"]:
                    return True
        
        return False
    
    def calculate_reciprocal_rank(self, retrieved_chunks: List[Dict], 
                                  relevant_info: Dict) -> float:
        """
        Tìm vị trí của chunk đúng đầu tiên, return 1/rank
        Nếu không tìm thấy: return 0
        """
        for rank, chunk in enumerate(retrieved_chunks, start=1):
            # Check ID match
            if "relevant_chunks" in relevant_info and relevant_info["relevant_chunks"]:
                if chunk["id"] in relevant_info["relevant_chunks"]:
                    return 1.0 / rank
            
            # Check Điều match
            if "relevant_dieu" in relevant_info and relevant_info["relevant_dieu"]:
                if chunk.get("dieu") == relevant_info["relevant_dieu"]:
                    return 1.0 / rank
        
        return 0.0
    
    def calculate_precision_at_k(self, retrieved_chunks: List[Dict], 
                                 relevant_info: Dict, k: int = 5) -> float:
        """
        Precision@K = (Số chunk relevant trong top-K) / K
        """
        top_k = retrieved_chunks[:k]
        relevant_count = 0
        
        for chunk in top_k:
            if "relevant_chunks" in relevant_info and relevant_info["relevant_chunks"]:
                if chunk["id"] in relevant_info["relevant_chunks"]:
                    relevant_count += 1
                    continue
            
            if "relevant_dieu" in relevant_info and relevant_info["relevant_dieu"]:
                if chunk.get("dieu") == relevant_info["relevant_dieu"]:
                    relevant_count += 1
        
        return relevant_count / k if k > 0 else 0.0
    
    def calculate_ndcg_at_k(self, retrieved_chunks: List[Dict], 
                           relevant_info: Dict, k: int = 5) -> float:
        """
        NDCG@K (Normalized Discounted Cumulative Gain)
        Đo lường ranking quality với discount theo position
        """
        def dcg(relevances, k):
            return sum(rel / np.log2(i + 2) for i, rel in enumerate(relevances[:k]))
        
        # Compute relevance scores (1 if relevant, 0 if not)
        relevances = []
        for chunk in retrieved_chunks[:k]:
            is_relevant = False
            
            if "relevant_chunks" in relevant_info and relevant_info["relevant_chunks"]:
                if chunk["id"] in relevant_info["relevant_chunks"]:
                    is_relevant = True
            
            if not is_relevant and "relevant_dieu" in relevant_info:
                if chunk.get("dieu") == relevant_info["relevant_dieu"]:
                    is_relevant = True
            
            relevances.append(1.0 if is_relevant else 0.0)
        
        # Ideal ranking (all relevant first)
        ideal_relevances = sorted(relevances, reverse=True)
        
        dcg_score = dcg(relevances, k)
        idcg_score = dcg(ideal_relevances, k)
        
        return dcg_score / idcg_score if idcg_score > 0 else 0.0
    
    def evaluate_single_query(self, test_case: TestCase, 
                             user_id: str = "base", 
                             group_id: str = None) -> RetrievalResult:
        """Đánh giá 1 câu hỏi"""
        chunks, scores = self.retrieve(test_case.query, user_id, group_id)
        
        relevant_info = {}
        if test_case.relevant_chunks:
            relevant_info["relevant_chunks"] = test_case.relevant_chunks
        if test_case.relevant_dieu:
            relevant_info["relevant_dieu"] = test_case.relevant_dieu
        
        hit = self.calculate_hit(chunks, relevant_info)
        rr = self.calculate_reciprocal_rank(chunks, relevant_info)
        precision = self.calculate_precision_at_k(chunks, relevant_info, self.top_k)
        ndcg = self.calculate_ndcg_at_k(chunks, relevant_info, self.top_k)
        avg_sim = np.mean(scores) if scores else 0.0
        
        return RetrievalResult(
            query=test_case.query,
            retrieved_chunks=chunks,
            scores=scores,
            hit=hit,
            reciprocal_rank=rr,
            precision_at_k=precision,
            ndcg_at_k=ndcg,
            avg_similarity=avg_sim
        )
    
    def evaluate_test_set(self, test_cases: List[TestCase], 
                         user_id: str = "base", 
                         group_id: str = None) -> Tuple[EvaluationMetrics, List[RetrievalResult]]:
        """Đánh giá toàn bộ test set"""
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\r[{i}/{len(test_cases)}] Evaluating: {test_case.query[:50]}...", end="")
            result = self.evaluate_single_query(test_case, user_id, group_id)
            results.append(result)
        
        print()  # New line
        
        # Aggregate metrics
        hit_rate_1 = sum(1 for r in results if self.calculate_hit(
            r.retrieved_chunks, 
            {"relevant_chunks": test_cases[i].relevant_chunks, 
             "relevant_dieu": test_cases[i].relevant_dieu}, 
            k=1
        )) / len(results)
        
        hit_rate_3 = sum(1 for r in results if self.calculate_hit(
            r.retrieved_chunks, 
            {"relevant_chunks": test_cases[i].relevant_chunks, 
             "relevant_dieu": test_cases[i].relevant_dieu}, 
            k=3
        )) / len(results)
        
        hit_rate_5 = sum(r.hit for r in results) / len(results)
        mrr = np.mean([r.reciprocal_rank for r in results])
        avg_precision = np.mean([r.precision_at_k for r in results])
        avg_ndcg = np.mean([r.ndcg_at_k for r in results])
        avg_similarity = np.mean([r.avg_similarity for r in results])
        
        metrics = EvaluationMetrics(
            hit_rate_at_1=hit_rate_1,
            hit_rate_at_3=hit_rate_3,
            hit_rate_at_5=hit_rate_5,
            mrr=mrr,
            avg_precision_at_5=avg_precision,
            avg_ndcg_at_5=avg_ndcg,
            avg_similarity=avg_similarity,
            total_queries=len(results)
        )
        
        return metrics, results


# ============================================================
# TEST SET GENERATOR
# ============================================================

def generate_sample_test_set() -> List[TestCase]:
    """
    Tạo test set mẫu cho BHXH
    Trong thực tế, cần có chuyên gia tạo test set với ground truth
    """
    test_cases = [
        TestCase(
            query="Bảo hiểm xã hội là gì?",
            relevant_dieu="Điều 1",
            ground_truth_answer="Bảo hiểm xã hội là...",
            category="định nghĩa"
        ),
        TestCase(
            query="Mức đóng bảo hiểm xã hội là bao nhiêu phần trăm?",
            relevant_dieu="Điều 85",
            category="mức đóng"
        ),
        TestCase(
            query="Điều kiện hưởng lương hưu là gì?",
            relevant_dieu="Điều 54",
            category="hưu trí"
        ),
        TestCase(
            query="Trợ cấp thai sản được hưởng trong bao lâu?",
            relevant_dieu="Điều 39",
            category="thai sản"
        ),
        TestCase(
            query="Điều kiện hưởng trợ cấp ốm đau?",
            relevant_dieu="Điều 25",
            category="ốm đau"
        ),
    ]
    return test_cases


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="RAG Evaluation Tool")
    parser.add_argument("--test-file", type=str, help="Path to test set JSON file")
    parser.add_argument("--output", type=str, default="evaluation_results.json", 
                       help="Output file for results")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve")
    parser.add_argument("--group-id", type=str, help="Group ID for filtering")
    parser.add_argument("--generate-sample", action="store_true", 
                       help="Generate sample test set")
    
    args = parser.parse_args()
    
    # Generate sample test set
    if args.generate_sample:
        test_cases = generate_sample_test_set()
        output_file = "sample_test_set.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump([asdict(tc) for tc in test_cases], f, ensure_ascii=False, indent=2)
        print(f"✅ Generated sample test set: {output_file}")
        return
    
    # Load test set
    if args.test_file:
        with open(args.test_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            test_cases = [TestCase(**item) for item in data]
    else:
        print("⚠️  No test file provided. Using sample test set...")
        test_cases = generate_sample_test_set()
    
    # Run evaluation
    print(f"\n🚀 Starting RAG Evaluation with {len(test_cases)} test cases...")
    evaluator = RAGEvaluator(top_k=args.top_k)
    metrics, results = evaluator.evaluate_test_set(test_cases, group_id=args.group_id)
    
    # Display metrics
    print(metrics)
    
    # Save results
    output_data = {
        "metrics": asdict(metrics),
        "results": [
            {
                "query": r.query,
                "hit": r.hit,
                "reciprocal_rank": r.reciprocal_rank,
                "precision_at_k": r.precision_at_k,
                "ndcg_at_k": r.ndcg_at_k,
                "avg_similarity": r.avg_similarity,
                "top_chunks": [
                    {
                        "text": c["text"][:200],
                        "dieu": c.get("dieu", ""),
                        "score": c["score"]
                    } for c in r.retrieved_chunks
                ]
            } for r in results
        ]
    }
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Results saved to: {args.output}")


if __name__ == "__main__":
    main()
