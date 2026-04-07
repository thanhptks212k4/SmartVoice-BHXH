from google import genai
import sys, os, re  # UPDATED - thêm re
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
        self.collection_name = "thanhpt"
        self.chat_sessions = {}
    def get_chat_session(self, uuid ,group_id):
        if uuid not in self.chat_sessions:
            # Khởi tạo session với System Instruction để AI luôn đóng vai bé gái lớp 4
            # và tuân thủ các quy tắc định dạng số một cách bền vững
            print("check5")
            content = redis_manager.get_cache(f"group:{group_id}:content")
            print("prompt laf",content)
            # UPDATED - Thêm rule trả lời ngắn gọn vào system_instruction
            concise_rule = "\nQUY TẮC TRẢ LỜI: Trả lời ngắn gọn trong 3–5 câu nhưng phải đầy đủ ý, rõ ràng, không lan man. Ưu tiên: 1 câu trả lời chính, 1-2 câu giải thích, 1 câu kết luận hoặc gợi ý."
            system_instruction = content + concise_rule
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

    # UPDATED - Thêm câu giới thiệu đầu cuộc hội thoại
    INTRO_MESSAGE = "Tôi là một trợ lý ảo tư vấn bảo hiểm xã hội, tôi có thể giúp gì cho bạn?\n\n"

    # UPDATED - Hàm cắt response còn tối đa 5 câu
    def _truncate_response(self, text):
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) > 5:
            sentences = sentences[:5]
            # Đảm bảo câu cuối kết thúc bằng dấu câu
            if not sentences[-1][-1] in '.!?':
                sentences[-1] += '.'
        return ' '.join(sentences)

    def generate_respone(self, prompt: str, uuid: str ,group_id: str):
        try:
            print("check3")
            chat = self.get_chat_session(uuid,group_id)

            # Kiểm tra lịch sử để xác định tin nhắn đầu tiên
            history = chat.get_history()
            is_first_message = len(history) == 0

            # Nếu là tin nhắn đầu tiên, chỉ trả về câu giới thiệu (không gọi AI)
            if is_first_message:
                # Gửi prompt vào chat để lưu lịch sử context cho lần sau
                context = self.get_context(uuid, prompt ,group_id)
                full_prompt = f"THÔNG TIN HỖ TRỢ:\n{context}\n\nCÂU HỎI: {prompt}"
                print(full_prompt)
                response = chat.send_message(full_prompt)
                # Bỏ qua response của AI, chỉ trả về intro
                return self.INTRO_MESSAGE.strip()

            context = self.get_context(uuid, prompt ,group_id)
            full_prompt = f"THÔNG TIN HỖ TRỢ:\n{context}\n\nCÂU HỎI: {prompt}"
            print(full_prompt)
            response = chat.send_message(full_prompt)
            history = chat.get_history()
            for msg in history:
                print(f"role: {msg.role}")
                print(f"text: {msg.parts[0].text}")
                print("---")

            # Cắt response ngắn gọn 3-5 câu
            final_text = self._truncate_response(response.text)
            return final_text
            
        except Exception as e:
            print(f"[genAI ERROR] {e}")
            return "Tớ xin lỗi, tớ đang gặp chút trục trặc nhỏ."
        
    def delete_session(self, uuid):
        if uuid in self.chat_sessions:
            del self.chat_sessions[uuid]
            print(f"🗑 Xóa session: {uuid}")

if __name__ == "__main__":
    ai = AIEngine()
