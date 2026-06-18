"""
Auto-generate Test Set từ văn bản pháp luật

Script này tự động tạo test set từ các văn bản đã embed trong Qdrant:
1. Lấy mẫu các chunks từ Qdrant
2. Generate synthetic questions bằng LLM (Gemini)
3. Create test cases với ground truth

Usage:
    python generate_test_set_from_docs.py --output test_set_generated.json --num-samples 50
"""

import sys
import os
import json
import argparse
import random
from typing import List, Dict
from qdrant_client import QdrantClient

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.config import settings

try:
    from google import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    print("⚠️  google-genai not installed. Run: pip install google-genai")


class TestSetGenerator:
    def __init__(self, collection_name: str = "thanhpt"):
        self.qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        self.collection_name = collection_name
        
        if HAS_GEMINI:
            self.gemini_client = genai.Client(api_key=settings.API_LLM)
        else:
            self.gemini_client = None
    
    def sample_chunks(self, num_samples: int = 50, 
                     user_id: str = "base") -> List[Dict]:
        """
        Lấy mẫu random chunks từ Qdrant
        Ưu tiên chunks có metadata đầy đủ (dieu, khoan, diem)
        """
        # Scroll through collection to get all chunks
        offset = None
        all_chunks = []
        
        while True:
            response = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
            )
            
            points, next_offset = response
            
            for point in points:
                payload = point.payload
                # Filter: Only base knowledge + có Điều
                if payload.get("userId") == user_id and payload.get("dieu"):
                    all_chunks.append({
                        "id": str(point.id),
                        "text": payload.get("text", ""),
                        "dieu": payload.get("dieu", ""),
                        "khoan": payload.get("khoan", ""),
                        "diem": payload.get("diem", ""),
                        "fileName": payload.get("fileName", ""),
                        "so_hieu": payload.get("so_hieu", ""),
                        "loai_vb": payload.get("loai_vb", ""),
                    })
            
            if next_offset is None:
                break
            offset = next_offset
        
        print(f"📦 Found {len(all_chunks)} chunks with Điều metadata")
        
        # Sample randomly
        if len(all_chunks) > num_samples:
            sampled = random.sample(all_chunks, num_samples)
        else:
            sampled = all_chunks
        
        return sampled
    
    def generate_question(self, chunk: Dict) -> str:
        """
        Generate synthetic question từ chunk content bằng LLM
        """
        if not self.gemini_client:
            # Fallback: Template-based questions
            return self._generate_template_question(chunk)
        
        prompt = f"""
Bạn là chuyên gia tạo câu hỏi cho hệ thống RAG về Bảo hiểm Xã hội.

Dựa vào đoạn văn bản sau, hãy tạo 1 câu hỏi tự nhiên mà người dùng có thể hỏi:

ĐOẠN VĂN BẢN:
{chunk['text']}

METADATA:
- Điều: {chunk.get('dieu', 'N/A')}
- Văn bản: {chunk.get('so_hieu', 'N/A')}

YÊU CẦU:
1. Câu hỏi phải tự nhiên như người thật hỏi
2. Không copy nguyên văn trong text
3. Câu hỏi phải có thể trả lời được từ đoạn văn trên
4. Dùng từ khóa thông dụng (không quá chuyên ngành)

CHỈ TRẢ VỀ CÂU HỎI, KHÔNG GIẢI THÍCH:
"""
        
        try:
            response = self.gemini_client.models.generate_content(
                model=settings.MODEL_NAME,
                contents=prompt
            )
            question = response.text.strip()
            # Remove quotes if any
            question = question.strip('"\'')
            return question
        except Exception as e:
            print(f"⚠️  LLM generation failed: {e}")
            return self._generate_template_question(chunk)
    
    def _generate_template_question(self, chunk: Dict) -> str:
        """Fallback template-based question generation"""
        dieu = chunk.get('dieu', '')
        text = chunk['text'][:100]  # First 100 chars
        
        templates = [
            f"Nội dung {dieu} quy định gì?",
            f"{dieu} nói về vấn đề gì?",
            f"Theo {dieu}, điều kiện là gì?",
            f"Quy định trong {dieu} như thế nào?",
        ]
        
        return random.choice(templates)
    
    def generate_test_set(self, num_samples: int = 50, 
                         user_id: str = "base") -> List[Dict]:
        """
        Main function: Generate complete test set
        """
        print(f"🚀 Generating test set with {num_samples} samples...")
        
        # Step 1: Sample chunks
        chunks = self.sample_chunks(num_samples, user_id)
        print(f"✅ Sampled {len(chunks)} chunks")
        
        # Step 2: Generate questions
        test_cases = []
        for i, chunk in enumerate(chunks, 1):
            print(f"\r[{i}/{len(chunks)}] Generating questions...", end="")
            
            question = self.generate_question(chunk)
            
            test_case = {
                "query": question,
                "relevant_chunks": [chunk["id"]],
                "relevant_dieu": chunk["dieu"],
                "ground_truth_answer": None,  # To be filled manually
                "category": self._infer_category(chunk),
                "metadata": {
                    "chunk_text": chunk["text"][:200],  # First 200 chars
                    "so_hieu": chunk.get("so_hieu", ""),
                    "loai_vb": chunk.get("loai_vb", ""),
                }
            }
            
            test_cases.append(test_case)
        
        print()  # New line
        print(f"✅ Generated {len(test_cases)} test cases")
        
        return test_cases
    
    def _infer_category(self, chunk: Dict) -> str:
        """Tự động phân loại category dựa vào content"""
        text_lower = chunk['text'].lower()
        
        categories = {
            "mức đóng": ["mức đóng", "tỷ lệ đóng", "phần trăm", "%", "đóng góp"],
            "điều kiện hưởng": ["điều kiện", "hưởng", "được hưởng", "đủ điều kiện"],
            "thời gian": ["thời gian", "thời hạn", "ngày", "tháng", "năm"],
            "hồ sơ": ["hồ sơ", "giấy tờ", "chứng từ", "thủ tục"],
            "quyền lợi": ["quyền", "lợi ích", "trợ cấp", "tiền"],
            "thai sản": ["thai sản", "sinh con", "thai nghén", "nuôi con"],
            "hưu trí": ["hưu trí", "nghỉ hưu", "lương hưu", "tuổi nghỉ"],
            "ốm đau": ["ốm đau", "ốm", "bệnh", "điều trị"],
            "tai nạn": ["tai nạn", "tai nạn lao động", "bệnh nghề nghiệp"],
        }
        
        for category, keywords in categories.items():
            if any(kw in text_lower for kw in keywords):
                return category
        
        return "general"


def main():
    parser = argparse.ArgumentParser(
        description="Auto-generate test set from Qdrant documents"
    )
    parser.add_argument("--output", type=str, default="test_set_generated.json",
                       help="Output JSON file")
    parser.add_argument("--num-samples", type=int, default=50,
                       help="Number of test cases to generate")
    parser.add_argument("--user-id", type=str, default="base",
                       help="User ID to sample from (default: base)")
    
    args = parser.parse_args()
    
    # Generate test set
    generator = TestSetGenerator()
    test_cases = generator.generate_test_set(
        num_samples=args.num_samples,
        user_id=args.user_id
    )
    
    # Save to JSON
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(test_cases, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Test set saved to: {args.output}")
    print(f"\n📋 Next steps:")
    print(f"   1. Review generated questions (quality check)")
    print(f"   2. Optionally fill 'ground_truth_answer' field")
    print(f"   3. Run evaluation: python rag_evaluation.py --test-file {args.output}")


if __name__ == "__main__":
    main()
