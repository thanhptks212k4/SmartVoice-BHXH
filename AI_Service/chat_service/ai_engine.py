from google import genai
import sys, os
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from redis_manager import redis_manager


sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.config import settings

class AIEngine:
    def __init__(self):
        self.client = genai.Client(api_key=settings.API_LLM)
        self.qdrant_client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.embed_model = SentenceTransformer(settings.MODEL_QDRANT)
        self.collection_name = "bytehome"
        self.chat_sessions = {}
# Bạn là một bé gái lớp 4. 
#             Bây giờ là 17h45 6/3/2025
#             QUY TẮC BẮT BUỘC: 
#             1. KHÔNG dùng ký tự số (0-9) hoặc ký hiệu (%). Phải viết bằng chữ (VD: "tám phần trăm").
#             2. KHÔNG mở ngoặc đơn để chú thích. 
#             3. Trả lời ngắn gọn 3 câu cho câu dễ, 5-10 câu cho câu khó.
#             4. Không ghi nguồn tài liệu. 
    def get_chat_session(self, uuid ,group_id):
        if uuid not in self.chat_sessions:
            # Khởi tạo session với System Instruction để AI luôn đóng vai bé gái lớp 4
            # và tuân thủ các quy tắc định dạng số một cách bền vững
            print("check5")
            content = redis_manager.get_cache(f"group:{group_id}:content")
            print("prompt laf",content)
            system_instruction = content
            self.chat_sessions[uuid] = self.client.chats.create(
                model=settings.MODEL_NAME,
                config={"system_instruction": system_instruction}
            )
        return self.chat_sessions[uuid]

    def get_context(self, user_id, query_text ,group_id):
        try:
            query_vector = self.embed_model.encode(query_text).tolist()
            response = self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=Filter(
                must=[
                    FieldCondition(key="groupId", match=MatchValue(value=group_id)),
                    Filter(
                        should=[
                            FieldCondition(key="userId", match=MatchValue(value="base")),
                            FieldCondition(key="userId", match=MatchValue(value=user_id))
                        ]
                    )
                ]
            ),
                limit=3
            )
            contexts = [hit.payload.get("text", "") for hit in response.points]
            return "\n".join(contexts)
        except Exception as e:
            print(f"[Qdrant Error] {e}")
            return ""

    def generate_respone(self, prompt: str, uuid: str ,group_id: str):
        try:
            print("check3")
            context = self.get_context(uuid, prompt ,group_id)
            chat = self.get_chat_session(uuid,group_id)
           
            full_prompt = f"THÔNG TIN HỖ TRỢ:\n{context}\n\nCÂU HỎI: {prompt}"
            print(full_prompt)
            response = chat.send_message(full_prompt)
            history = chat.get_history()
            for msg in history:
                print(f"role: {msg.role}")
                print(f"text: {msg.parts[0].text}")
                print("---")
            return response.text
            
        except Exception as e:
            print(f"[genAI ERROR] {e}")
            return "Tớ xin lỗi, tớ đang gặp chút trục trặc nhỏ."
        
    def delete_session(self, uuid):
        if uuid in self.chat_sessions:
            del self.chat_sessions[uuid]
            print(f"🗑 Xóa session: {uuid}")

if __name__ == "__main__":
    ai = AIEngine()
