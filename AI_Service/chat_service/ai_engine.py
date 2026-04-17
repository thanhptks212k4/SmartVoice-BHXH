import re
import sys
import os
from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from redis_manager import redis_manager

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.config import settings


# ---------------------------------------------------------------------------
# Hằng số
# ---------------------------------------------------------------------------

GREETING_RESPONSE = (
    "Xin chào! Tôi là trợ lý ảo tư vấn bảo hiểm xã hội. "
    "Tôi có thể giúp gì cho bạn?"
)

IDENTITY_RESPONSE = (
    "Tôi là trợ lý ảo tư vấn bảo hiểm xã hội. "
    "Tôi được xây dựng để hỗ trợ bạn giải đáp các thắc mắc liên quan đến bảo hiểm xã hội. "
    "Bạn cần tư vấn về vấn đề gì?"
)

ERROR_RESPONSE = "Xin lỗi, tôi đang gặp chút trục trặc. Vui lòng thử lại sau."

OUT_OF_SCOPE_RESPONSE = (
    "Tôi chỉ có thể tư vấn các vấn đề liên quan đến bảo hiểm xã hội. "
    "Bạn có câu hỏi nào về bảo hiểm xã hội không?"
)

GREETING_PATTERNS = [
    r"^(xin chào|chào|hello|hi|hey|chào bạn|xin chào bạn)[\s!.]*$",
    r"^(alo|alô|ơi|ê)[\s!.]*$",
    r"^(good morning|good afternoon|good evening|chào buổi (sáng|trưa|chiều|tối))[\s!.]*$",
]

IDENTITY_PATTERNS = [
    r"bạn là (ai|gì|cái gì)",
    r"(mày|cậu|ông|bà) là (ai|gì)",
    r"(giới thiệu|tự giới thiệu).*(bản thân|mình|bạn)",
    r"(ai|cái gì) (tạo ra|phát triển|làm ra) (bạn|mày)",
    r"bạn (được|do).*(tạo|phát triển|huấn luyện)",
    r"(tên|danh tính).*(của bạn|của mày)",
]

IDENTITY_RULE = (
    "\nNHẬN DIỆN VAI TRÒ: Bạn là trợ lý ảo tư vấn bảo hiểm xã hội. "
    "Khi người dùng hỏi về danh tính của bạn, hãy luôn trả lời rằng bạn là trợ lý ảo tư vấn bảo hiểm xã hội. "
    "TUYỆT ĐỐI KHÔNG được nói bạn là mô hình ngôn ngữ, AI của Google, hay bất kỳ danh tính nào khác."
)

CONCISE_RULE = (
    "\nQUY TẮC TRẢ LỜI: Trả lời ngắn gọn trong 3–5 câu, đầy đủ ý, rõ ràng, không lan man. "
    "Cấu trúc: 1 câu trả lời chính → 1-2 câu giải thích → 1 câu kết luận hoặc gợi ý tiếp theo."
)

SCOPE_RULE = (
    "\nPHẠM VI TƯ VẤN: Bạn CHỈ được trả lời các câu hỏi liên quan đến bảo hiểm xã hội (BHXH), "
    "bao gồm: chế độ ốm đau, thai sản, tai nạn lao động, hưu trí, tử tuất, thất nghiệp, "
    "mức đóng BHXH, hồ sơ thủ tục, quyền lợi người lao động. "
    "Nếu câu hỏi KHÔNG liên quan đến BHXH, hãy từ chối lịch sự và đề nghị người dùng hỏi về BHXH."
)

NO_REPEAT_GREETING_RULE = (
    "\nQUY TẮC CHÀO HỎI: TUYỆT ĐỐI KHÔNG bắt đầu câu trả lời bằng lời chào như 'Xin chào', 'Chào bạn' "
    "hay bất kỳ lời chào nào khác. Đi thẳng vào nội dung trả lời."
)

MAX_SENTENCES = 5
RAG_LIMIT = 3


# ---------------------------------------------------------------------------
# AIEngine
# ---------------------------------------------------------------------------

class AIEngine:
    def __init__(self):
        self.client = genai.Client(api_key=settings.API_LLM)
        self.qdrant_client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.embed_model = SentenceTransformer(settings.MODEL_QDRANT)
        self.collection_name = "thanhpt"
        self.chat_sessions = {}
        self.greeted_users = set()  # track user đã được chào chưa

    def get_chat_session(self, uuid, group_id):
        if uuid not in self.chat_sessions:
            content = redis_manager.get_cache(f"group:{group_id}:content") or ""
            system_instruction = content + IDENTITY_RULE + CONCISE_RULE + NO_REPEAT_GREETING_RULE + SCOPE_RULE
            self.chat_sessions[uuid] = self.client.chats.create(
                model=settings.MODEL_NAME,
                config={"system_instruction": system_instruction},
            )
        return self.chat_sessions[uuid]

    def get_context(self, user_id, query_text, group_id):
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
                                FieldCondition(key="userId", match=MatchValue(value=user_id)),
                            ]
                        ),
                    ]
                ),
                limit=RAG_LIMIT,
            )
            contexts = [hit.payload.get("text", "") for hit in response.points]
            return "\n".join(contexts)
        except Exception as e:
            print(f"[Qdrant Error] {e}")
            return ""

    @staticmethod
    def _strip_greeting(text):
        """Xóa lời chào ở đầu câu trả lời của Gemini."""
        greeting_prefixes = [
            r"^xin chào[!,.]?\s*(bạn[!,.]?)?\s*",
            r"^chào\s*(bạn[!,.]?)?\s*",
            r"^hello[!,.]?\s*",
            r"^xin chào[!,.]?\s*tôi là trợ lý ảo tư vấn bảo hiểm xã hội[!,.]?\s*",
            r"^chào bạn[!,.]?\s*tôi là trợ lý ảo tư vấn bảo hiểm xã hội[!,.]?\s*",
        ]
        normalized = text.strip()
        for pattern in greeting_prefixes:
            normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE).strip()
        # Viết hoa chữ cái đầu sau khi strip
        if normalized:
            normalized = normalized[0].upper() + normalized[1:]
        return normalized

    def _truncate_response(self, text):
        text = self._strip_greeting(text)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
        if len(sentences) > MAX_SENTENCES:
            sentences = sentences[:MAX_SENTENCES]
            if sentences[-1][-1] not in ".!?":
                sentences[-1] += "."
        return " ".join(sentences)

    # Từ khóa liên quan BHXH — nếu không có bất kỳ từ nào thì out-of-scope
    BHXH_KEYWORDS = [
        # --- Tên viết tắt & tổ chức ---
        "bảo hiểm", "bhxh", "bhyt", "bhtn", "bảo hiểm xã hội", "bảo hiểm y tế",
        "bảo hiểm thất nghiệp", "cơ quan bhxh", "bảo hiểm tự nguyện",
        "bảo hiểm bắt buộc", "quỹ bhxh", "quỹ bảo hiểm", "luật bhxh",
        "luật bảo hiểm xã hội", "luật bảo hiểm y tế",

        # --- Chế độ & quyền lợi ---
        "chế độ", "hưu trí", "lương hưu", "nghỉ hưu", "tuổi nghỉ hưu",
        "ốm đau", "thai sản", "nghỉ thai sản", "nghỉ sinh", "sinh con",
        "tai nạn lao động", "tnlđ", "bệnh nghề nghiệp", "tử tuất",
        "thất nghiệp", "trợ cấp thất nghiệp", "trợ cấp ốm đau",
        "trợ cấp thai sản", "trợ cấp hưu trí", "trợ cấp tử tuất",
        "trợ cấp một lần", "trợ cấp hàng tháng", "trợ cấp",
        "mai táng phí", "tiền tuất", "tiền dưỡng sức",
        "dưỡng sức phục hồi sức khỏe", "phục hồi sức khỏe",

        # --- Đóng & mức đóng ---
        "mức đóng", "đóng bảo hiểm", "đóng bhxh", "đóng bhyt", "đóng bhtn",
        "tỷ lệ đóng", "mức đóng góp", "đóng góp", "căn cứ đóng",
        "tiền đóng", "phí bảo hiểm", "đóng thiếu", "đóng bù",
        "truy đóng", "hoàn trả", "hoàn tiền bhxh", "rút bhxh",
        "rút bảo hiểm xã hội", "nhận bảo hiểm", "hưởng bhxh",
        "hưởng bảo hiểm", "giải quyết chế độ",

        # --- Thời gian đóng & điều kiện ---
        "thời gian đóng", "năm đóng", "tháng đóng", "đủ năm đóng",
        "thiếu năm đóng", "gián đoạn đóng", "bảo lưu", "bảo lưu thời gian",
        "tính thời gian", "cộng nối thời gian", "thời gian làm việc",

        # --- Lương & thu nhập ---
        "lương", "tiền lương", "mức lương", "lương cơ sở", "lương tối thiểu",
        "lương tháng", "thu nhập", "thu nhập tháng", "mức thu nhập",
        "tiền công", "phụ cấp", "phụ cấp lương",

        # --- Người lao động & sử dụng lao động ---
        "người lao động", "người sử dụng lao động", "nld", "nsdlđ",
        "lao động", "công nhân", "viên chức", "cán bộ", "công chức",
        "hợp đồng lao động", "hợp đồng làm việc", "thử việc",
        "sa thải", "nghỉ việc", "thôi việc", "chấm dứt hợp đồng",
        "nghỉ không lương", "tạm hoãn hợp đồng",

        # --- Doanh nghiệp & đơn vị ---
        "doanh nghiệp", "công ty", "nhà nước", "cơ quan", "đơn vị",
        "tổ chức", "hộ kinh doanh", "hợp tác xã", "cơ sở sản xuất",
        "chủ sử dụng lao động", "chủ doanh nghiệp",

        # --- Hồ sơ & thủ tục ---
        "hồ sơ", "thủ tục", "giấy tờ", "đăng ký", "khai báo",
        "nộp hồ sơ", "xét duyệt", "giải quyết hồ sơ", "cấp sổ",
        "sổ bảo hiểm", "sổ bhxh", "thẻ bhyt", "thẻ bảo hiểm y tế",
        "cấp thẻ", "gia hạn thẻ", "mất sổ", "mất thẻ",
        "điều chỉnh thông tin", "xác nhận", "xác nhận bhxh",

        # --- Khám chữa bệnh & y tế ---
        "khám bệnh", "chữa bệnh", "khám chữa bệnh", "viện phí",
        "chi phí khám", "thanh toán bhyt", "thanh toán bảo hiểm",
        "cơ sở khám chữa bệnh", "bệnh viện", "phòng khám",
        "đúng tuyến", "trái tuyến", "chuyển tuyến", "tuyến trên",
        "tuyến dưới", "đăng ký khám ban đầu", "nơi đăng ký khám",
        "mức hưởng bhyt", "mức thanh toán",

        # --- Rủi ro & sự kiện bảo hiểm ---
        "rủi ro", "sự kiện bảo hiểm", "tai nạn", "ốm", "bệnh",
        "mất việc", "mất thu nhập", "già yếu", "chết", "qua đời",
        "tàn tật", "suy giảm khả năng lao động", "thương tật",

        # --- Quyền & nghĩa vụ ---
        "quyền lợi", "nghĩa vụ", "quyền", "trách nhiệm",
        "vi phạm", "xử phạt", "khiếu nại", "tố cáo", "tranh chấp",
        "thanh tra", "kiểm tra bhxh",

        # --- Đối tượng tham gia ---
        "đối tượng", "tham gia bhxh", "bắt buộc tham gia",
        "tự nguyện tham gia", "người nước ngoài", "lao động nước ngoài",
        "lao động thời vụ", "lao động ngắn hạn", "lao động part-time",
        "người hoạt động không chuyên trách", "xã phường thị trấn",
    ]

    @classmethod
    def _is_out_of_scope(cls, text):
        normalized = text.lower().strip()
        return not any(kw in normalized for kw in cls.BHXH_KEYWORDS)

    @staticmethod
    def _is_greeting(text):
        normalized = text.lower().strip()
        return any(re.search(pattern, normalized) for pattern in GREETING_PATTERNS)

    @staticmethod
    def _is_identity_question(text):
        normalized = text.lower().strip()
        return any(re.search(pattern, normalized) for pattern in IDENTITY_PATTERNS)

    def generate_respone(self, prompt: str, uuid: str, group_id: str):
        try:
            chat = self.get_chat_session(uuid, group_id)

            # Câu chào hỏi → chỉ chào lần đầu tiên
            if self._is_greeting(prompt):
                if uuid not in self.greeted_users:
                    self.greeted_users.add(uuid)
                    return GREETING_RESPONSE
                else:
                    return "Bạn cần tư vấn về vấn đề gì?"

            # Câu hỏi về danh tính → chặn trước khi gọi AI
            if self._is_identity_question(prompt):
                return IDENTITY_RESPONSE

            # Câu hỏi ngoài phạm vi BHXH → từ chối
            if self._is_out_of_scope(prompt):
                return OUT_OF_SCOPE_RESPONSE

            # Gọi AI với context từ RAG
            context = self.get_context(uuid, prompt, group_id)
            full_prompt = f"THÔNG TIN HỖ TRỢ:\n{context}\n\nCÂU HỎI: {prompt}"
            response = chat.send_message(full_prompt)

            return self._truncate_response(response.text)

        except Exception as e:
            print(f"[genAI ERROR] {e}")
            return ERROR_RESPONSE

    def delete_session(self, uuid):
        if uuid in self.chat_sessions:
            del self.chat_sessions[uuid]
        self.greeted_users.discard(uuid)  # reset trạng thái chào khi user disconnect
        print(f"🗑 Xóa session: {uuid}")


if __name__ == "__main__":
    ai = AIEngine()