"""
RAGAS Evaluation Framework - Đánh giá End-to-End RAG System

Metrics:
1. RETRIEVAL METRICS (Vector Database):
   - Hit Rate @ K: Tỷ lệ trúng đích
   - MRR: Mean Reciprocal Rank (Thứ hạng đối nghịch trung bình)

2. GENERATION METRICS (LLM Quality - RAGAS):
   - Faithfulness: Độ trung thực (không hallucination)
   - Answer Relevance: Độ liên quan của câu trả lời
   - Context Precision: Độ chính xác của context
   - Context Recall: Độ bao phủ của context

Usage:
    python ragas_evaluation.py --test-file ground_truth.json --output ragas_results.json
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

try:
    from google import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    print("⚠️  google-genai not installed. LLM evaluation will be skipped.")


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class GroundTruthTestCase:
    """Test case với Ground Truth đầy đủ cho RAGAS"""
    query: str                          # Câu hỏi
    ground_truth_answer: str            # Câu trả lời đúng (reference)
    relevant_dieu: str = None           # Điều liên quan
    relevant_chunks: List[str] = None   # Chunk IDs liên quan
    category: str = "general"
    
    def __post_init__(self):
        if self.relevant_chunks is None:
            self.relevant_chunks = []


@dataclass
class RAGResult:
    """Kết quả đầy đủ của RAG pipeline"""
    query: str
    retrieved_contexts: List[str]       # Top-K contexts
    generated_answer: str               # Câu trả lời từ LLM
    ground_truth_answer: str            # Reference answer
    
    # Retrieval metrics
    hit: bool
    reciprocal_rank: float
    
    # RAGAS metrics
    faithfulness_score: float = None
    answer_relevance_score: float = None
    context_precision_score: float = None
    context_recall_score: float = None


@dataclass
class RAGASMetrics:
    """Tổng hợp metrics RAGAS"""
    # Retrieval
    hit_rate_at_5: float
    mrr: float
    
    # Generation (RAGAS)
    avg_faithfulness: float
    avg_answer_relevance: float
    avg_context_precision: float
    avg_context_recall: float
    
    total_queries: int
    
    def __str__(self):
        return f"""
╔══════════════════════════════════════════════════════════════════╗
║                   RAGAS EVALUATION RESULTS                       ║
╠══════════════════════════════════════════════════════════════════╣
║ Total Test Cases:      {self.total_queries:<40} ║
║                                                                  ║
║ 📊 RETRIEVAL METRICS (Vector Database Quality):                 ║
║   ├─ Hit Rate @ 5:        {self.hit_rate_at_5:<33.2%} ║
║   └─ MRR:                 {self.mrr:<33.4f} ║
║                                                                  ║
║ 🤖 GENERATION METRICS (LLM Quality - RAGAS):                    ║
║   ├─ Faithfulness:        {self.avg_faithfulness:<33.4f} ║
║   │   (Độ trung thực - Không hallucination)                     ║
║   ├─ Answer Relevance:    {self.avg_answer_relevance:<33.4f} ║
║   │   (Độ liên quan câu trả lời)                                ║
║   ├─ Context Precision:   {self.avg_context_precision:<33.4f} ║
║   │   (Độ chính xác context)                                    ║
║   └─ Context Recall:      {self.avg_context_recall:<33.4f} ║
║       (Độ bao phủ context)                                      ║
╚══════════════════════════════════════════════════════════════════╝
"""


# ============================================================
# RAGAS EVALUATOR
# ============================================================

class RAGASEvaluator:
    def __init__(self, collection_name: str = "thanhpt", top_k: int = 5):
        self.qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        self.embed_model = SentenceTransformer(settings.MODEL_QDRANT)
        self.collection_name = collection_name
        self.top_k = top_k
        
        if HAS_GEMINI:
            self.gemini_client = genai.Client(api_key=settings.API_LLM)
        else:
            self.gemini_client = None
    
    # ============================================================
    # RETRIEVAL METHODS
    # ============================================================
    
    def retrieve(self, query: str, user_id: str = "base", 
                 group_id: str = None) -> Tuple[List[str], List[Dict]]:
        """
        Retrieve top-K contexts từ Qdrant
        Returns: (context_texts, full_chunks)
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
        
        contexts = []
        chunks = []
        for hit in response.points:
            contexts.append(hit.payload.get("text", ""))
            chunks.append({
                "id": hit.id,
                "text": hit.payload.get("text", ""),
                "dieu": hit.payload.get("dieu", ""),
                "score": hit.score
            })
        
        return contexts, chunks
    
    def calculate_retrieval_metrics(self, chunks: List[Dict], 
                                    relevant_dieu: str) -> Tuple[bool, float]:
        """
        Calculate Hit Rate và MRR
        Returns: (hit, reciprocal_rank)
        """
        hit = False
        rr = 0.0
        
        for rank, chunk in enumerate(chunks, start=1):
            if chunk.get("dieu") == relevant_dieu:
                hit = True
                if rr == 0.0:  # First hit
                    rr = 1.0 / rank
                break
        
        return hit, rr
    
    # ============================================================
    # GENERATION METHODS
    # ============================================================
    
    def generate_answer(self, query: str, contexts: List[str]) -> str:
        """Generate answer từ LLM với contexts"""
        if not self.gemini_client:
            return "[LLM not available]"
        
        context_text = "\n\n".join([f"Context {i+1}:\n{ctx}" 
                                   for i, ctx in enumerate(contexts)])
        
        prompt = f"""Bạn là chuyên gia tư vấn Bảo hiểm Xã hội Việt Nam.

THÔNG TIN HỖ TRỢ:
{context_text}

CÂU HỎI: {query}

YÊU CẦU:
- Trả lời ngắn gọn, chính xác dựa HOÀN TOÀN trên thông tin hỗ trợ
- Nếu thông tin không đủ để trả lời, nói rõ "Không có đủ thông tin"
- KHÔNG bịa đặt thông tin không có trong context

TRẢ LỜI:"""
        
        try:
            response = self.gemini_client.models.generate_content(
                model=settings.MODEL_NAME,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            print(f"⚠️  LLM generation error: {e}")
            return "[Generation failed]"
    
    # ============================================================
    # RAGAS METRICS CALCULATION
    # ============================================================
    
    def calculate_faithfulness(self, answer: str, contexts: List[str]) -> float:
        """
        Faithfulness: Đo lường độ trung thực (không hallucination)
        
        Method: Phân tách answer thành claims, check xem bao nhiêu claims
        được supported bởi contexts
        
        Score: [0, 1] - Higher is better
        1.0 = Tất cả claims đều có trong context (không hallucination)
        0.0 = Tất cả claims đều không có trong context (100% hallucination)
        """
        if not self.gemini_client or not answer or not contexts:
            return 0.0
        
        # Step 1: Extract claims từ answer
        claims_prompt = f"""Phân tách câu trả lời sau thành các nhận định (claims) riêng biệt:

CÂU TRẢ LỜI:
{answer}

Trả về dạng JSON list các claims:
["claim 1", "claim 2", ...]

CHỈ TRẢ VỀ JSON, KHÔNG GIẢI THÍCH:"""
        
        try:
            response = self.gemini_client.models.generate_content(
                model=settings.MODEL_NAME,
                contents=claims_prompt
            )
            claims_text = response.text.strip()
            # Parse JSON
            claims_text = claims_text.replace("```json", "").replace("```", "").strip()
            claims = json.loads(claims_text)
        except:
            # Fallback: Split by sentences
            claims = [s.strip() for s in answer.split('.') if s.strip()]
        
        if not claims:
            return 1.0  # No claims = no hallucination
        
        # Step 2: Check each claim against contexts
        context_text = "\n".join(contexts)
        supported_count = 0
        
        for claim in claims:
            verify_prompt = f"""Context:
{context_text}

Claim: {claim}

Claim này có được hỗ trợ bởi Context không? Trả lời: YES hoặc NO

TRẢ LỜI:"""
            
            try:
                response = self.gemini_client.models.generate_content(
                    model=settings.MODEL_NAME,
                    contents=verify_prompt
                )
                result = response.text.strip().upper()
                if "YES" in result:
                    supported_count += 1
            except:
                pass
        
        faithfulness = supported_count / len(claims) if claims else 1.0
        return faithfulness
    
    def calculate_answer_relevance(self, query: str, answer: str) -> float:
        """
        Answer Relevance: Đo lường độ liên quan giữa câu hỏi và câu trả lời
        
        Method: Cosine similarity giữa query và answer embeddings
        
        Score: [0, 1] - Higher is better
        """
        if not answer or not query:
            return 0.0
        
        query_emb = self.embed_model.encode(query)
        answer_emb = self.embed_model.encode(answer)
        
        similarity = util.cos_sim(query_emb, answer_emb).item()
        return max(0.0, similarity)  # Ensure non-negative
    
    def calculate_context_precision(self, contexts: List[str], 
                                   ground_truth_answer: str) -> float:
        """
        Context Precision: Đo lường độ chính xác của contexts
        
        Method: Bao nhiêu % contexts là relevant cho ground truth answer
        
        Score: [0, 1] - Higher is better
        """
        if not contexts or not ground_truth_answer:
            return 0.0
        
        relevant_count = 0
        for ctx in contexts:
            # Check if context is relevant to ground truth
            similarity = util.cos_sim(
                self.embed_model.encode(ctx),
                self.embed_model.encode(ground_truth_answer)
            ).item()
            
            if similarity > 0.5:  # Threshold
                relevant_count += 1
        
        precision = relevant_count / len(contexts)
        return precision
    
    def calculate_context_recall(self, contexts: List[str], 
                                 ground_truth_answer: str) -> float:
        """
        Context Recall: Đo lường độ bao phủ của contexts
        
        Method: Contexts có đủ thông tin để trả lời ground truth không?
        
        Score: [0, 1] - Higher is better
        """
        if not contexts or not ground_truth_answer:
            return 0.0
        
        # Combine all contexts
        all_context = " ".join(contexts)
        
        # Check coverage via similarity
        similarity = util.cos_sim(
            self.embed_model.encode(all_context),
            self.embed_model.encode(ground_truth_answer)
        ).item()
        
        return max(0.0, similarity)
    
    # ============================================================
    # MAIN EVALUATION PIPELINE
    # ============================================================
    
    def evaluate_single_query(self, test_case: GroundTruthTestCase,
                             user_id: str = "base",
                             group_id: str = None) -> RAGResult:
        """Đánh giá đầy đủ 1 query với RAGAS metrics"""
        
        # Step 1: Retrieval
        contexts, chunks = self.retrieve(test_case.query, user_id, group_id)
        
        # Step 2: Calculate retrieval metrics
        hit, rr = self.calculate_retrieval_metrics(chunks, test_case.relevant_dieu)
        
        # Step 3: Generation
        generated_answer = self.generate_answer(test_case.query, contexts)
        
        # Step 4: Calculate RAGAS metrics
        faithfulness = self.calculate_faithfulness(generated_answer, contexts)
        answer_relevance = self.calculate_answer_relevance(test_case.query, generated_answer)
        context_precision = self.calculate_context_precision(contexts, test_case.ground_truth_answer)
        context_recall = self.calculate_context_recall(contexts, test_case.ground_truth_answer)
        
        return RAGResult(
            query=test_case.query,
            retrieved_contexts=contexts,
            generated_answer=generated_answer,
            ground_truth_answer=test_case.ground_truth_answer,
            hit=hit,
            reciprocal_rank=rr,
            faithfulness_score=faithfulness,
            answer_relevance_score=answer_relevance,
            context_precision_score=context_precision,
            context_recall_score=context_recall
        )
    
    def evaluate_test_set(self, test_cases: List[GroundTruthTestCase],
                         user_id: str = "base",
                         group_id: str = None) -> Tuple[RAGASMetrics, List[RAGResult]]:
        """Đánh giá toàn bộ test set"""
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\r[{i}/{len(test_cases)}] Evaluating: {test_case.query[:60]}...", end="")
            result = self.evaluate_single_query(test_case, user_id, group_id)
            results.append(result)
        
        print()  # New line
        
        # Aggregate metrics
        hit_rate = sum(r.hit for r in results) / len(results)
        mrr = np.mean([r.reciprocal_rank for r in results])
        
        avg_faithfulness = np.mean([r.faithfulness_score for r in results if r.faithfulness_score is not None])
        avg_answer_rel = np.mean([r.answer_relevance_score for r in results if r.answer_relevance_score is not None])
        avg_ctx_precision = np.mean([r.context_precision_score for r in results if r.context_precision_score is not None])
        avg_ctx_recall = np.mean([r.context_recall_score for r in results if r.context_recall_score is not None])
        
        metrics = RAGASMetrics(
            hit_rate_at_5=hit_rate,
            mrr=mrr,
            avg_faithfulness=avg_faithfulness,
            avg_answer_relevance=avg_answer_rel,
            avg_context_precision=avg_ctx_precision,
            avg_context_recall=avg_ctx_recall,
            total_queries=len(results)
        )
        
        return metrics, results


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="RAGAS Evaluation Tool")
    parser.add_argument("--test-file", type=str, required=True,
                       help="Path to ground truth test set JSON")
    parser.add_argument("--output", type=str, default="ragas_results.json",
                       help="Output file for results")
    parser.add_argument("--top-k", type=int, default=5,
                       help="Number of contexts to retrieve")
    parser.add_argument("--group-id", type=str, help="Group ID for filtering")
    
    args = parser.parse_args()
    
    # Load test set
    with open(args.test_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        test_cases = [GroundTruthTestCase(**item) for item in data]
    
    print(f"\n🚀 Starting RAGAS Evaluation with {len(test_cases)} test cases...")
    print(f"📊 Metrics: Hit Rate, MRR, Faithfulness, Answer Relevance, Context Precision/Recall\n")
    
    # Run evaluation
    evaluator = RAGASEvaluator(top_k=args.top_k)
    metrics, results = evaluator.evaluate_test_set(test_cases, group_id=args.group_id)
    
    # Display metrics
    print(metrics)
    
    # Save results
    output_data = {
        "metrics": asdict(metrics),
        "results": [
            {
                "query": r.query,
                "generated_answer": r.generated_answer,
                "ground_truth_answer": r.ground_truth_answer,
                "hit": r.hit,
                "reciprocal_rank": r.reciprocal_rank,
                "faithfulness": r.faithfulness_score,
                "answer_relevance": r.answer_relevance_score,
                "context_precision": r.context_precision_score,
                "context_recall": r.context_recall_score,
                "contexts": [ctx[:200] for ctx in r.retrieved_contexts]  # Truncate
            } for r in results
        ]
    }
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Results saved to: {args.output}")
    
    # Interpretation
    print("\n" + "="*70)
    print("📋 ĐÁNH GIÁ:")
    print("="*70)
    
    if metrics.hit_rate_at_5 >= 0.9:
        print("✅ RETRIEVAL: Xuất sắc (Hit Rate >= 90%)")
    elif metrics.hit_rate_at_5 >= 0.75:
        print("⚠️  RETRIEVAL: Tốt (Hit Rate >= 75%)")
    else:
        print("❌ RETRIEVAL: Cần cải thiện (Hit Rate < 75%)")
    
    if metrics.avg_faithfulness >= 0.8:
        print("✅ FAITHFULNESS: Xuất sắc (Ít hallucination)")
    elif metrics.avg_faithfulness >= 0.6:
        print("⚠️  FAITHFULNESS: Chấp nhận được")
    else:
        print("❌ FAITHFULNESS: Nhiều hallucination, cần cải thiện prompt")
    
    if metrics.avg_answer_relevance >= 0.75:
        print("✅ ANSWER RELEVANCE: Câu trả lời liên quan tốt")
    else:
        print("⚠️  ANSWER RELEVANCE: Câu trả lời chưa đủ liên quan")
    
    print("="*70)


if __name__ == "__main__":
    main()
